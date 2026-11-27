package view

import (
	"fmt"
	"regexp"
	"strings"

	"deepread/internal/genuikit"
	"deepread/internal/markdown"
	"deepread/internal/openuilang"
)

// ValidationError is a structured rejection (CLI exit code 3) with actionable
// repair guidance for the host Agent.
type ValidationError struct {
	Code      string `json:"code"`
	Statement string `json:"statement,omitempty"`
	Path      string `json:"path,omitempty"`
	Message   string `json:"message"`
	Hint      string `json:"hint,omitempty"`
}

func (e *ValidationError) Error() string {
	if e.Statement != "" {
		return fmt.Sprintf("%s (%s): %s", e.Code, e.Statement, e.Message)
	}
	return fmt.Sprintf("%s: %s", e.Code, e.Message)
}

var bannedTitles = map[string]bool{
	"summary":           true,
	"executive summary": true,
	"key takeaways":     true,
	"takeaways":         true,
	"tl;dr":             true,
	"tldr":              true,
	"highlights":        true,
	"overview":          true,
	"要点":                true,
	"核心要点":              true,
	"总结":                true,
	"摘要":                true,
	"全文总结":              true,
}

var rootColItemsRe = regexp.MustCompile(`^root\s*=\s*Col\s*\(\s*\[([^\]]*)\]\s*\)\s*$`)

// ValidatedModule records one verified top-level Source module binding.
type ValidatedModule struct {
	Statement string
	SourceID  string
	Section   markdown.Section
}

// ValidationResult captures the verified statements, stamped sources, and module list.
type ValidationResult struct {
	Statements []string
	Sources    map[string]SourceRef
	Modules    []ValidatedModule
	Root       *openuilang.Element
}

// ValidateStrict enforces DeepRead's strict zero-fault, narrowed-catalog,
// single-section top-level Source topology, and anti-cliché guardrails.
func ValidateStrict(docRaw string, statementsText string, rawSources map[string]SourceRef) (*ValidationResult, error) {
	lib, err := genuikit.Library()
	if err != nil {
		return nil, err
	}

	stmts := SplitStatementStrings(statementsText)
	if len(stmts) == 0 {
		return nil, &ValidationError{
			Code:    "EMPTY_STATEMENTS",
			Path:    "/statements",
			Message: "statements cannot be empty; use `root = Col([])` for a zero-module view",
			Hint:    "Provide at least `root = Col([])`.",
		}
	}

	// Ensure every statement parses as a single named assignment with unique names.
	stmtByName := make(map[string]string, len(stmts))
	for _, s := range stmts {
		names := openuilang.Names(s)
		if len(names) != 1 {
			return nil, &ValidationError{
				Code:    "INVALID_STATEMENT",
				Path:    "/statements",
				Message: fmt.Sprintf("invalid statement: %q", s),
				Hint:    "Write one `name = Component(...)` assignment per statement.",
			}
		}
		if _, dup := stmtByName[names[0]]; dup {
			return nil, &ValidationError{
				Code:      "DUPLICATE_STATEMENT",
				Statement: names[0],
				Message:   fmt.Sprintf("statement %q is defined more than once", names[0]),
				Hint:      "Give each statement a unique name.",
			}
		}
		stmtByName[names[0]] = s
	}

	rootStmt, hasRoot := stmtByName["root"]
	if !hasRoot {
		return nil, &ValidationError{
			Code:    "NO_ROOT",
			Path:    "/root",
			Message: "missing root statement",
			Hint:    "Start with `root = Col([mod1, mod2])` or `root = Col([])`.",
		}
	}

	// Enforce that root = Col([...]) lists only named top-level identifiers.
	m := rootColItemsRe.FindStringSubmatch(strings.TrimSpace(rootStmt))
	if m == nil {
		return nil, &ValidationError{
			Code:      "INVALID_ROOT_TOPOLOGY",
			Statement: "root",
			Message:   "root must be `root = Col([stmt1, stmt2, ...])` referencing only named top-level Source statements",
			Hint:      "Put each Source in its own named statement (e.g. `capex = Source([\"s1\"], [...])`) and reference it in `root = Col([capex])`.",
		}
	}
	var rootRefs []string
	if inner := strings.TrimSpace(m[1]); inner != "" {
		for _, part := range strings.Split(inner, ",") {
			ref := strings.TrimSpace(part)
			if ref == "" || strings.ContainsAny(ref, "()[]{}\"' \t") {
				return nil, &ValidationError{
					Code:      "INVALID_ROOT_CHILD",
					Statement: "root",
					Message:   fmt.Sprintf("root child %q must be a named statement identifier, not an inline expression", ref),
					Hint:      "Define each module as its own named statement and list its name in `root = Col([...])`.",
				}
			}
			rootRefs = append(rootRefs, ref)
		}
	}

	// Module budget cap: 0..4 default, up to 6 for long texts (>6000 words).
	words := len(strings.Fields(docRaw))
	maxModules := 4
	if words > 6000 {
		maxModules = 6
	}
	if len(rootRefs) > maxModules {
		return nil, &ValidationError{
			Code:      "TOO_MANY_MODULES",
			Statement: "root",
			Message:   fmt.Sprintf("%d modules exceeds sparse budget limit %d", len(rootRefs), maxModules),
			Hint:      "Keep only the highest-leverage cognitive scaffolds (typically 0 to 4).",
		}
	}

	joined := strings.Join(stmts, "\n")
	program := lib.Parse(joined)
	session := openuilang.NewSession()
	session.Load(program)
	root, problems := session.Render()

	// Strict zero-fault check (overrides Mark Go Go's fault tolerance floor).
	for _, p := range append(program.Errors, problems...) {
		return nil, &ValidationError{
			Code:      "OPENUI_ERROR",
			Statement: p.StatementID,
			Path:      p.Path,
			Message:   p.Message,
			Hint:      "Fix the syntax, argument types, or component properties so zero errors remain.",
		}
	}
	if len(program.Unresolved) > 0 {
		return nil, &ValidationError{
			Code:    "UNRESOLVED_IDENTIFIER",
			Message: fmt.Sprintf("unresolved identifier(s): %s", strings.Join(program.Unresolved, ", ")),
			Hint:    "Define every referenced statement or remove unused references.",
		}
	}
	if root == nil || root.Type != "Col" {
		return nil, &ValidationError{
			Code:      "INVALID_ROOT",
			Statement: "root",
			Message:   "root did not evaluate to Col",
		}
	}

	// Build section lookup map from live Markdown document.
	sections := markdown.ExtractSections(docRaw)
	type secKey struct {
		norm string
		occ  int
	}
	secByKey := make(map[secKey]markdown.Section, len(sections))
	for _, s := range sections {
		secByKey[secKey{markdown.NormalizeHeadingText(s.Heading), s.Occurrence}] = s
	}

	// Check each top-level child of root corresponds 1:1 with rootRefs and is a valid Source.
	children, _ := root.Props.Values["children"].([]any)
	if len(children) != len(rootRefs) {
		return nil, &ValidationError{
			Code:      "INVALID_ROOT_CHILDREN",
			Statement: "root",
			Message:   fmt.Sprintf("root evaluated to %d children, expected %d", len(children), len(rootRefs)),
		}
	}

	stampedSources := make(map[string]SourceRef)
	usedSections := make(map[secKey]string)
	modules := make([]ValidatedModule, 0, len(rootRefs))

	for i, refName := range rootRefs {
		el, ok := children[i].(*openuilang.Element)
		if !ok || el == nil || el.Type != "Source" {
			return nil, &ValidationError{
				Code:      "TOP_LEVEL_MUST_BE_SOURCE",
				Statement: refName,
				Message:   fmt.Sprintf("root child %q must evaluate to a Source([...], [...]) element", refName),
				Hint:      "Wrap every top-level module in `Source([\"srcId\"], [...])`.",
			}
		}
		// Require refName itself to directly assign a single `Source(...)` call
		// with no trailing ternary/expression tokens (rejecting alias chains,
		// `true ? helper : Source(...)`, and `Source(...) ? helper : Source(...)`)
		// so write, inspect, export, and patch --replace always agree on module names.
		if !isDirectSourceAssignment(stmtByName[refName], refName) {
			return nil, &ValidationError{
				Code:      "TOP_LEVEL_MUST_BE_SOURCE",
				Statement: refName,
				Message:   fmt.Sprintf("root child %q must directly define a single `Source(...)` call rather than an alias or compound expression", refName),
				Hint:      fmt.Sprintf("Write `%s = Source([\"srcId\"], [...])` directly.", refName),
			}
		}

		// Each Source must cite exactly ONE section.
		rawIDs, _ := el.Props.Values["sources"].([]any)
		if len(rawIDs) != 1 {
			return nil, &ValidationError{
				Code:      "SINGLE_SOURCE_REQUIRED",
				Statement: refName,
				Message:   fmt.Sprintf("Source %q must cite exactly 1 source id (got %d)", refName, len(rawIDs)),
				Hint:      "Attach each module to one specific non-H1 section so it interleaves unambiguously.",
			}
		}
		srcID, ok := rawIDs[0].(string)
		if !ok || strings.TrimSpace(srcID) == "" {
			return nil, &ValidationError{
				Code:      "INVALID_SOURCE_ID",
				Statement: refName,
				Message:   "Source id must be a non-empty string",
			}
		}
		target, exists := rawSources[srcID]
		if !exists {
			return nil, &ValidationError{
				Code:      "MISSING_SOURCE_MAPPING",
				Statement: refName,
				Path:      "/sources/" + srcID,
				Message:   fmt.Sprintf("source id %q is not mapped to any document section", srcID),
				Hint:      fmt.Sprintf("Pass `--source %s=\"Exact Heading\"#1`.", srcID),
			}
		}
		occ := target.Occurrence
		if occ < 1 {
			occ = 1
		}
		k := secKey{markdown.NormalizeHeadingText(target.Heading), occ}
		sec, found := secByKey[k]
		if !found {
			return nil, &ValidationError{
				Code:      "UNKNOWN_SECTION",
				Statement: refName,
				Path:      "/sources/" + srcID,
				Message:   fmt.Sprintf("section %q (occurrence %d) does not exist in document", target.Heading, occ),
				Hint:      "Run `deepread inspect <doc.md>` to check exact headings, or run `deepread prepare` if the document has no H2 sections.",
			}
		}
		if sec.Level == 1 {
			return nil, &ValidationError{
				Code:      "H1_SOURCE_FORBIDDEN",
				Statement: refName,
				Path:      "/sources/" + srcID,
				Message:   fmt.Sprintf("section %q is an H1 covering the whole document and cannot be cited as a module anchor", sec.Heading),
				Hint:      "Cite an H2/H3 section, or run `deepread prepare` to add synthetic H2 anchors.",
			}
		}
		if prevStmt, dupSec := usedSections[k]; dupSec {
			return nil, &ValidationError{
				Code:      "DUPLICATE_SECTION_MODULE",
				Statement: refName,
				Message:   fmt.Sprintf("section %q (occurrence %d) already has module %q; max 1 module per section", sec.Heading, occ, prevStmt),
				Hint:      "Merge into one focused scaffold or keep only the strongest intervention for this section.",
			}
		}
		usedSections[k] = refName

		// Walk subtree for whitelist, no nested Source, banned titles, and structural primitive presence.
		hasStructural := false
		if err := walkModuleSubtree(refName, el.Props.Values["children"], &hasStructural); err != nil {
			return nil, err
		}
		if !hasStructural {
			return nil, &ValidationError{
				Code:      "PROSE_ONLY_SUMMARY_REJECTED",
				Statement: refName,
				Message:   fmt.Sprintf("module %q contains only text/bullet elements and no structural cognitive primitive", refName),
				Hint:      "Include at least one `Table`, `Chart` (bar/line), `Quote`, or `List` with `timeline=true`, or drop this module if prose alone is sufficient.",
			}
		}

		stampedSources[srcID] = SourceRef{
			Heading:    sec.Heading,
			Occurrence: sec.Occurrence,
			Hash:       sec.Hash,
		}
		modules = append(modules, ValidatedModule{
			Statement: refName,
			SourceID:  srcID,
			Section:   sec,
		})
	}

	return &ValidationResult{
		Statements: stmts,
		Sources:    stampedSources,
		Modules:    modules,
		Root:       root,
	}, nil
}

// isDirectSourceAssignment reports whether stmt is strictly `<name> = Source(...)`
// with nothing following the matching closing parenthesis.
func isDirectSourceAssignment(stmt, name string) bool {
	trimmed := strings.TrimSpace(stmt)
	prefixRe := regexp.MustCompile(`^` + regexp.QuoteMeta(name) + `\s*=\s*Source\s*\(`)
	loc := prefixRe.FindStringIndex(trimmed)
	if loc == nil {
		return false
	}
	depth := 1
	var inStr byte
	esc := false
	for i := loc[1]; i < len(trimmed); i++ {
		c := trimmed[i]
		if esc {
			esc = false
			continue
		}
		if inStr != 0 {
			if c == '\\' {
				esc = true
			} else if c == inStr {
				inStr = 0
			}
			continue
		}
		switch c {
		case '"', '\'':
			inStr = c
		case '(':
			depth++
		case ')':
			depth--
			if depth == 0 {
				return strings.TrimSpace(trimmed[i+1:]) == ""
			}
		}
	}
	return false
}

func walkModuleSubtree(stmtName string, value any, hasStructural *bool) error {
	switch v := value.(type) {
	case []any:
		for _, item := range v {
			if err := walkModuleSubtree(stmtName, item, hasStructural); err != nil {
				return err
			}
		}
	case *openuilang.Object:
		if v == nil {
			return nil
		}
		for _, key := range v.Keys {
			if err := walkModuleSubtree(stmtName, v.Values[key], hasStructural); err != nil {
				return err
			}
		}
	case *openuilang.Element:
		if v == nil {
			return nil
		}
		if v.Type == "Source" {
			return &ValidationError{
				Code:      "NESTED_SOURCE_FORBIDDEN",
				Statement: stmtName,
				Message:   "nested Source elements are forbidden",
				Hint:      "Keep Source strictly at top level under root.",
			}
		}
		if !AllowedComponents[v.Type] {
			return &ValidationError{
				Code:      "DISALLOWED_COMPONENT",
				Statement: stmtName,
				Message:   fmt.Sprintf("component %q is outside DeepRead's 10-primitive reading whitelist", v.Type),
				Hint:      "Run `deepread catalog` to see allowed static reading primitives (no Card/Grid/Badge/Box/form widgets).",
			}
		}
		switch v.Type {
		case "Table", "Quote":
			*hasStructural = true
		case "Chart":
			ct, _ := v.Props.Values["type"].(string)
			if !AllowedChartTypes[ct] {
				return &ValidationError{
					Code:      "DISALLOWED_CHART_TYPE",
					Statement: stmtName,
					Message:   fmt.Sprintf("Chart type %q is not supported in v1 (allowed: bar, line)", ct),
					Hint:      "Use `Chart(\"bar\", ...)` or `Chart(\"line\", ...)`.",
				}
			}
			*hasStructural = true
		case "List":
			if tl, ok := v.Props.Values["timeline"].(bool); ok && tl {
				*hasStructural = true
			}
		case "Title":
			txt, _ := v.Props.Values["text"].(string)
			norm := strings.ToLower(strings.TrimSpace(txt))
			if bannedTitles[norm] {
				return &ValidationError{
					Code:      "CLICHE_TITLE_REJECTED",
					Statement: stmtName,
					Message:   fmt.Sprintf("cliché summary title %q is forbidden", txt),
					Hint:      "Use a specific, analytical title describing the exact comparison, mechanism, or tension.",
				}
			}
		}
		if v.Props != nil {
			for _, key := range v.Props.Keys {
				if err := walkModuleSubtree(stmtName, v.Props.Values[key], hasStructural); err != nil {
					return err
				}
			}
		}
	}
	return nil
}
