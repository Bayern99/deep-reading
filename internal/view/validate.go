package view

import (
	"fmt"
	"math"
	"net/url"
	"regexp"
	"strconv"
	"strings"
	"unicode"
	"unicode/utf8"

	"deepread/internal/bundle"
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

// ValidationWarning records a permitted but noteworthy structural fallback.
type ValidationWarning struct {
	Code      string `json:"code"`
	Statement string `json:"statement,omitempty"`
	Message   string `json:"message"`
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
var safeSVGPathRe = regexp.MustCompile(`^[MmLlHhVvCcSsQqTtAaZz0-9eE.,+\-\s]*$`)
var latinWordRe = regexp.MustCompile(`[A-Za-z]+(?:['’\-][A-Za-z]+)*`)

// SourceSpec is the validation-facing name for Mark Go Go's SourceRef.
type SourceSpec = SourceRef

// ValidatedSourceRef binds one source ID to its resolved live section.
type ValidatedSourceRef struct {
	SourceID string
	Section  markdown.Section
}

// ValidatedModule records one verified Source statement. SourceID and Section
// mirror the first entry in Sections for v0.2 callers.
type ValidatedModule struct {
	Statement string
	SourceID  string
	Section   markdown.Section
	ShortCode string
	Sections  []ValidatedSourceRef
}

// ValidationResult captures the verified statements, stamped sources, and module list.
type ValidationResult struct {
	Statements []string
	Sources    map[string]SourceRef
	Modules    []ValidatedModule
	Root       *openuilang.Element
	Warnings   []ValidationWarning
}

// ValidateOptions selects structural compatibility and opt-in editorial gates.
type ValidateOptions struct {
	Profile         string // canvas (default) | margin
	TargetLang      string
	Mode            string // original | translated | bilingual
	StrictEditorial bool
}

// ValidateStrict preserves the v0.2 margin validator for existing callers.
func ValidateStrict(docRaw string, statementsText string, rawSources map[string]SourceRef) (*ValidationResult, error) {
	result, err := ValidateWithOptions("", []byte(docRaw), SplitStatementStrings(statementsText), rawSources, ValidateOptions{
		Profile:         bundle.ProfileMargin,
		StrictEditorial: true,
	})
	if err != nil {
		return nil, err
	}
	return &result, nil
}

// ValidateWithOptions validates already-split OpenUI statements against docBytes.
// docPath is retained in the API for caller context; validation never reads disk.
func ValidateWithOptions(docPath string, docBytes []byte, stmts []string, sourceMap map[string]SourceSpec, opts ValidateOptions) (ValidationResult, error) {
	_ = docPath
	profile, err := normalizeProfile(opts.Profile)
	if err != nil {
		return ValidationResult{}, err
	}
	opts.Profile = profile
	statements := SplitStatementStrings(strings.Join(stmts, "\n"))
	return validateProgram(string(docBytes), statements, sourceMap, opts)
}

// ValidateForExport runs structural, OpenUI, source-resolution, and security
// checks without editorial heuristics, so upstream Mark Go Go views export.
func ValidateForExport(docPath string, docBytes []byte, stmts []string, sourceMap map[string]SourceSpec, profile string) (ValidationResult, error) {
	return ValidateWithOptions(docPath, docBytes, stmts, sourceMap, ValidateOptions{Profile: profile, StrictEditorial: false})
}

func normalizeProfile(profile string) (string, error) {
	if strings.TrimSpace(profile) == "" {
		return bundle.ProfileCanvas, nil
	}
	profile = strings.TrimSpace(profile)
	if profile != bundle.ProfileCanvas && profile != bundle.ProfileMargin {
		return "", &ValidationError{Code: "INVALID_PROFILE", Path: "/profile", Message: fmt.Sprintf("unknown view profile %q", profile), Hint: "Use canvas or margin."}
	}
	return profile, nil
}

type validationSectionKey struct {
	norm string
	occ  int
}

type sourceModule struct {
	module  ValidatedModule
	element *openuilang.Element
}

func validateProgram(docRaw string, stmts []string, rawSources map[string]SourceRef, opts ValidateOptions) (ValidationResult, error) {
	empty := ValidationResult{}
	if len(stmts) == 0 {
		return empty, &ValidationError{
			Code:    "EMPTY_STATEMENTS",
			Path:    "/statements",
			Message: "statements cannot be empty; use `root = Col([])` for a zero-module view",
			Hint:    "Provide at least `root = Col([])`.",
		}
	}

	stmtByName := make(map[string]string, len(stmts))
	for _, statement := range stmts {
		names := openuilang.Names(statement)
		if len(names) != 1 {
			return empty, &ValidationError{Code: "INVALID_STATEMENT", Path: "/statements", Message: fmt.Sprintf("invalid statement: %q", statement), Hint: "Write one `name = Component(...)` assignment per statement."}
		}
		if _, duplicate := stmtByName[names[0]]; duplicate {
			return empty, &ValidationError{Code: "DUPLICATE_STATEMENT", Statement: names[0], Message: fmt.Sprintf("statement %q is defined more than once", names[0]), Hint: "Give each statement a unique name."}
		}
		stmtByName[names[0]] = statement
	}
	rootStatement, hasRoot := stmtByName["root"]
	if !hasRoot {
		return empty, &ValidationError{Code: "NO_ROOT", Path: "/root", Message: "missing root statement", Hint: "Start with `root = Col([mod1, mod2])` or `root = Col([])`."}
	}

	var rootRefs []string
	if opts.Profile == bundle.ProfileMargin {
		var err error
		rootRefs, err = marginRootReferences(rootStatement)
		if err != nil {
			return empty, err
		}
		maxModules := 4
		if len(strings.Fields(docRaw)) > 6000 {
			maxModules = 6
		}
		if len(rootRefs) > maxModules {
			return empty, &ValidationError{Code: "TOO_MANY_MODULES", Statement: "root", Message: fmt.Sprintf("%d modules exceeds sparse budget limit %d", len(rootRefs), maxModules), Hint: "Keep only the highest-leverage cognitive scaffolds (typically 0 to 4)."}
		}
	}

	lib, err := genuikit.Library()
	if err != nil {
		return empty, err
	}
	program := lib.Parse(strings.Join(stmts, "\n"))
	session := openuilang.NewSession()
	session.Load(program)
	root, problems := session.Render()
	for _, problem := range append(program.Errors, problems...) {
		return empty, &ValidationError{Code: "OPENUI_ERROR", Statement: problem.StatementID, Path: problem.Path, Message: problem.Message, Hint: "Fix the syntax, argument types, or component properties so zero errors remain."}
	}
	if len(program.Unresolved) > 0 {
		return empty, &ValidationError{Code: "UNRESOLVED_IDENTIFIER", Message: fmt.Sprintf("unresolved identifier(s): %s", strings.Join(program.Unresolved, ", ")), Hint: "Define every referenced statement or remove unused references."}
	}
	if root == nil || root.Type != "Col" {
		return empty, &ValidationError{Code: "INVALID_ROOT", Statement: "root", Message: "root did not evaluate to Col"}
	}

	sections := markdown.ExtractSections(docRaw)
	sectionByKey := make(map[validationSectionKey]markdown.Section, len(sections))
	hasDeepSection := false
	for _, section := range sections {
		sectionByKey[validationSectionKey{markdown.NormalizeHeadingText(section.Heading), section.Occurrence}] = section
		if section.Level >= 2 {
			hasDeepSection = true
		}
	}
	resolver := sourceResolver{
		rawSources:     rawSources,
		sectionByKey:   sectionByKey,
		hasDeepSection: hasDeepSection,
		stampedSources: map[string]SourceRef{},
	}

	if opts.Profile == bundle.ProfileMargin {
		return validateMarginRoot(root, rootRefs, stmtByName, stmts, &resolver, opts)
	}
	return validateCanvasRoot(root, stmts, &resolver, opts, len(strings.Fields(docRaw)))
}

func marginRootReferences(rootStatement string) ([]string, error) {
	match := rootColItemsRe.FindStringSubmatch(strings.TrimSpace(rootStatement))
	if match == nil {
		return nil, &ValidationError{Code: "INVALID_ROOT_TOPOLOGY", Statement: "root", Message: "root must be `root = Col([stmt1, stmt2, ...])` referencing only named top-level Source statements", Hint: "Put each Source in its own named statement (e.g. `capex = Source([\"s1\"], [...])`) and reference it in `root = Col([capex])`."}
	}
	var refs []string
	if inner := strings.TrimSpace(match[1]); inner != "" {
		for _, part := range strings.Split(inner, ",") {
			ref := strings.TrimSpace(part)
			if ref == "" || strings.ContainsAny(ref, "()[]{}\"' \t") {
				return nil, &ValidationError{Code: "INVALID_ROOT_CHILD", Statement: "root", Message: fmt.Sprintf("root child %q must be a named statement identifier, not an inline expression", ref), Hint: "Define each module as its own named statement and list its name in `root = Col([...])`."}
			}
			refs = append(refs, ref)
		}
	}
	return refs, nil
}

type sourceResolver struct {
	rawSources     map[string]SourceRef
	sectionByKey   map[validationSectionKey]markdown.Section
	hasDeepSection bool
	stampedSources map[string]SourceRef
	warnings       []ValidationWarning
}

func (r *sourceResolver) resolve(element *openuilang.Element, profile string) (ValidatedModule, error) {
	statement := element.StatementID
	rawIDs, _ := element.Props.Values["sources"].([]any)
	if profile == bundle.ProfileMargin && len(rawIDs) != 1 {
		return ValidatedModule{}, &ValidationError{Code: "SINGLE_SOURCE_REQUIRED", Statement: statement, Message: fmt.Sprintf("Source %q must cite exactly 1 source id (got %d)", statement, len(rawIDs)), Hint: "Attach each module to one specific non-H1 section so it interleaves unambiguously."}
	}
	if len(rawIDs) == 0 {
		return ValidatedModule{}, &ValidationError{Code: "SOURCE_REQUIRED", Statement: statement, Message: "Source must cite at least one source id"}
	}
	module := ValidatedModule{Statement: statement, Sections: make([]ValidatedSourceRef, 0, len(rawIDs))}
	for _, rawID := range rawIDs {
		sourceID, ok := rawID.(string)
		if !ok || strings.TrimSpace(sourceID) == "" {
			return ValidatedModule{}, &ValidationError{Code: "INVALID_SOURCE_ID", Statement: statement, Message: "Source id must be a non-empty string"}
		}
		target, exists := r.rawSources[sourceID]
		if !exists {
			return ValidatedModule{}, &ValidationError{Code: "MISSING_SOURCE_MAPPING", Statement: statement, Path: "/sources/" + sourceID, Message: fmt.Sprintf("source id %q is not mapped to any document section", sourceID), Hint: fmt.Sprintf("Pass `--source %s=\"Exact Heading\"#1`.", sourceID)}
		}
		occurrence := target.Occurrence
		if occurrence < 1 {
			occurrence = 1
		}
		key := validationSectionKey{markdown.NormalizeHeadingText(target.Heading), occurrence}
		section, found := r.sectionByKey[key]
		if !found {
			return ValidatedModule{}, &ValidationError{Code: "UNKNOWN_SECTION", Statement: statement, Path: "/sources/" + sourceID, Message: fmt.Sprintf("section %q (occurrence %d) does not exist in document", target.Heading, occurrence), Hint: "Run `deepread inspect <doc.md>` to check exact headings, or run `deepread prepare` if the document has no H2 sections."}
		}
		if section.Level == 1 {
			if profile == bundle.ProfileMargin || r.hasDeepSection {
				return ValidatedModule{}, &ValidationError{Code: "H1_SOURCE_FORBIDDEN", Statement: statement, Path: "/sources/" + sourceID, Message: fmt.Sprintf("section %q is an H1 covering the whole document and cannot be cited as a module anchor", section.Heading), Hint: "Cite an H2/H3 section, or run `deepread prepare` to add synthetic H2 anchors."}
			}
			r.warnings = append(r.warnings, ValidationWarning{Code: "H1_SOURCE_ALLOWED", Statement: statement, Message: fmt.Sprintf("H1 %q is cited because the document has no H2+ sections", section.Heading)})
		}
		r.stampedSources[sourceID] = SourceRef{Heading: section.Heading, Occurrence: section.Occurrence, Hash: section.Hash}
		module.Sections = append(module.Sections, ValidatedSourceRef{SourceID: sourceID, Section: section})
	}
	module.SourceID = module.Sections[0].SourceID
	module.Section = module.Sections[0].Section
	return module, nil
}

func validateMarginRoot(root *openuilang.Element, rootRefs []string, stmtByName map[string]string, stmts []string, resolver *sourceResolver, opts ValidateOptions) (ValidationResult, error) {
	empty := ValidationResult{}
	children, _ := root.Props.Values["children"].([]any)
	if len(children) != len(rootRefs) {
		return empty, &ValidationError{Code: "INVALID_ROOT_CHILDREN", Statement: "root", Message: fmt.Sprintf("root evaluated to %d children, expected %d", len(children), len(rootRefs))}
	}
	usedSections := map[validationSectionKey]string{}
	modules := make([]ValidatedModule, 0, len(rootRefs))
	for index, refName := range rootRefs {
		element, ok := children[index].(*openuilang.Element)
		if !ok || element == nil || element.Type != "Source" || !isDirectSourceAssignment(stmtByName[refName], refName) {
			return empty, &ValidationError{Code: "TOP_LEVEL_MUST_BE_SOURCE", Statement: refName, Message: fmt.Sprintf("root child %q must directly define a single `Source(...)` call", refName), Hint: fmt.Sprintf("Write `%s = Source([\"srcId\"], [...])` directly.", refName)}
		}
		module, err := resolver.resolve(element, bundle.ProfileMargin)
		if err != nil {
			return empty, err
		}
		key := validationSectionKey{markdown.NormalizeHeadingText(module.Section.Heading), module.Section.Occurrence}
		if previous, duplicate := usedSections[key]; duplicate {
			return empty, &ValidationError{Code: "DUPLICATE_SECTION_MODULE", Statement: refName, Message: fmt.Sprintf("section %q (occurrence %d) already has module %q; max 1 module per section", module.Section.Heading, module.Section.Occurrence, previous), Hint: "Merge into one focused scaffold or keep only the strongest intervention for this section."}
		}
		usedSections[key] = refName

		hasStructural := false
		if err := walkModuleSubtree(refName, element.Props.Values["children"], &hasStructural, opts.StrictEditorial); err != nil {
			return empty, err
		}
		if opts.StrictEditorial && !hasStructural {
			return empty, &ValidationError{Code: "PROSE_ONLY_SUMMARY_REJECTED", Statement: refName, Message: fmt.Sprintf("module %q contains only text/bullet elements and no structural cognitive primitive", refName), Hint: "Include at least one `Table`, `Chart` (bar/line), `Quote`, or `List` with `timeline=true`, or drop this module if prose alone is sufficient."}
		}
		modules = append(modules, module)
	}
	if err := walkOpenUI(root, func(element *openuilang.Element) error { return validateElementSecurity(element) }); err != nil {
		return empty, err
	}
	return ValidationResult{Statements: stmts, Sources: resolver.stampedSources, Modules: modules, Root: root, Warnings: resolver.warnings}, nil
}

func validateCanvasRoot(root *openuilang.Element, stmts []string, resolver *sourceResolver, opts ValidateOptions, words int) (ValidationResult, error) {
	empty := ValidationResult{}
	allowed := map[string]bool{}
	for _, name := range genuikit.ComponentNames() {
		allowed[name] = true
	}
	var sourceModules []sourceModule
	err := walkOpenUI(root, func(element *openuilang.Element) error {
		if !allowed[element.Type] {
			return &ValidationError{Code: "DISALLOWED_COMPONENT", Statement: element.StatementID, Message: fmt.Sprintf("component %q is outside the OpenUI v3 catalog", element.Type)}
		}
		if err := validateElementSecurity(element); err != nil {
			return err
		}
		if opts.StrictEditorial && element.Type == "Title" {
			if err := validateTitle(element); err != nil {
				return err
			}
		}
		if opts.StrictEditorial && element.Type == "Table" {
			if err := validateGenericTablePair(element); err != nil {
				return err
			}
		}
		if element.Type == "Source" {
			module, err := resolver.resolve(element, bundle.ProfileCanvas)
			if err != nil {
				return err
			}
			sourceModules = append(sourceModules, sourceModule{module: module, element: element})
		}
		return nil
	})
	if err != nil {
		return empty, err
	}
	maxModules := 8
	if words > 2500 {
		maxModules = 12
	}
	if len(sourceModules) > maxModules {
		return empty, &ValidationError{Code: "TOO_MANY_MODULES", Statement: "root", Message: fmt.Sprintf("%d Source modules exceeds canvas budget %d", len(sourceModules), maxModules), Hint: "Keep only high-leverage cognitive scaffolds and combine cross-section synthesis narrowly."}
	}
	modules := make([]ValidatedModule, 0, len(sourceModules))
	for _, source := range sourceModules {
		modules = append(modules, source.module)
		if opts.StrictEditorial {
			if err := validateSoleGenericTable(source.element); err != nil {
				return empty, err
			}
			if err := validateSubstantiveMedium(source.element); err != nil {
				return empty, err
			}
		}
	}
	if opts.StrictEditorial {
		if err := validateMonotoneView(sourceModules); err != nil {
			return empty, err
		}
		if err := validateTranslatedCanvas(root, opts); err != nil {
			return empty, err
		}
	}
	return ValidationResult{Statements: stmts, Sources: resolver.stampedSources, Modules: modules, Root: root, Warnings: resolver.warnings}, nil
}

// isDirectSourceAssignment reports whether stmt is strictly `<name> = Source(...)`
// with nothing following the matching closing parenthesis.
func isDirectSourceAssignment(stmt, name string) bool {
	trimmed := strings.TrimSpace(stmt)
	prefixRe := regexp.MustCompile(`^` + regexp.QuoteMeta(name) + `\s*=\s*Source\s*\(`)
	location := prefixRe.FindStringIndex(trimmed)
	if location == nil {
		return false
	}
	depth := 1
	var inString byte
	escaped := false
	for index := location[1]; index < len(trimmed); index++ {
		char := trimmed[index]
		if escaped {
			escaped = false
			continue
		}
		if inString != 0 {
			if char == '\\' {
				escaped = true
			} else if char == inString {
				inString = 0
			}
			continue
		}
		switch char {
		case '"', '\'':
			inString = char
		case '(':
			depth++
		case ')':
			depth--
			if depth == 0 {
				return strings.TrimSpace(trimmed[index+1:]) == ""
			}
		}
	}
	return false
}

func walkModuleSubtree(statement string, value any, hasStructural *bool, strictEditorial bool) error {
	switch typed := value.(type) {
	case []any:
		for _, item := range typed {
			if err := walkModuleSubtree(statement, item, hasStructural, strictEditorial); err != nil {
				return err
			}
		}
	case *openuilang.Object:
		if typed == nil {
			return nil
		}
		for _, key := range typed.Keys {
			if err := walkModuleSubtree(statement, typed.Values[key], hasStructural, strictEditorial); err != nil {
				return err
			}
		}
	case *openuilang.Element:
		if typed == nil {
			return nil
		}
		if typed.Type == "Source" {
			return &ValidationError{Code: "NESTED_SOURCE_FORBIDDEN", Statement: statement, Message: "nested Source elements are forbidden", Hint: "Keep Source strictly at top level under root."}
		}
		if !AllowedComponents[typed.Type] {
			return &ValidationError{Code: "DISALLOWED_COMPONENT", Statement: statement, Message: fmt.Sprintf("component %q is outside DeepRead's 10-primitive reading whitelist", typed.Type), Hint: "Run `deepread catalog --profile margin` to see allowed static reading primitives."}
		}
		switch typed.Type {
		case "Table", "Quote":
			*hasStructural = true
		case "Chart":
			chartType, _ := typed.Props.Values["type"].(string)
			if !AllowedChartTypes[chartType] {
				return &ValidationError{Code: "DISALLOWED_CHART_TYPE", Statement: statement, Message: fmt.Sprintf("Chart type %q is not supported in margin (allowed: bar, line)", chartType), Hint: "Use `Chart(\"bar\", ...)` or `Chart(\"line\", ...)`."}
			}
			*hasStructural = true
		case "List":
			if timeline, ok := typed.Props.Values["timeline"].(bool); ok && timeline {
				*hasStructural = true
			}
		case "Title":
			if strictEditorial {
				if err := validateTitle(typed); err != nil {
					return err
				}
			}
		}
		if typed.Props != nil {
			for _, key := range typed.Props.Keys {
				if err := walkModuleSubtree(statement, typed.Props.Values[key], hasStructural, strictEditorial); err != nil {
					return err
				}
			}
		}
	}
	return nil
}

func validateTitle(element *openuilang.Element) error {
	text, _ := element.Props.Values["text"].(string)
	if bannedTitles[strings.ToLower(strings.TrimSpace(text))] {
		return &ValidationError{Code: "CLICHE_TITLE_REJECTED", Statement: element.StatementID, Message: fmt.Sprintf("cliché summary title %q is forbidden", text), Hint: "Use a specific, analytical title describing the exact comparison, mechanism, or tension."}
	}
	return nil
}

// walkOpenUI visits every reachable element and checks every evaluated OpenUrl action.
func walkOpenUI(value any, visit func(*openuilang.Element) error) error {
	return walkOpenUIStatement(value, "", visit)
}

func walkOpenUIStatement(value any, inheritedStatement string, visit func(*openuilang.Element) error) error {
	switch typed := value.(type) {
	case []any:
		for _, item := range typed {
			if err := walkOpenUIStatement(item, inheritedStatement, visit); err != nil {
				return err
			}
		}
	case *openuilang.Object:
		if typed != nil {
			for _, key := range typed.Keys {
				if err := walkOpenUIStatement(typed.Values[key], inheritedStatement, visit); err != nil {
					return err
				}
			}
		}
	case *openuilang.Element:
		if typed == nil {
			return nil
		}
		statement := typed.StatementID
		if statement == "" {
			statement = inheritedStatement
			copied := *typed
			copied.StatementID = statement
			typed = &copied
		}
		if err := visit(typed); err != nil {
			return err
		}
		if typed.Props != nil {
			for _, key := range typed.Props.Keys {
				if err := walkOpenUIStatement(typed.Props.Values[key], statement, visit); err != nil {
					return err
				}
			}
		}
	case *openuilang.ActionPlan:
		if typed != nil {
			for _, step := range typed.Steps {
				if step.Type == "open_url" {
					statement := step.StatementID
					if statement == "" {
						statement = inheritedStatement
					}
					if err := validateSafeURL(step.URL, statement); err != nil {
						return err
					}
				}
				if err := walkOpenUIStatement(step.Params, inheritedStatement, visit); err != nil {
					return err
				}
			}
		}
	}
	return nil
}

func validateElementSecurity(element *openuilang.Element) error {
	statement := element.StatementID
	if element.Type == "Link" {
		link, _ := element.Props.Values["url"].(string)
		if err := validateSafeURL(link, statement); err != nil {
			return err
		}
	}
	if element.Type == "Svg" {
		viewBox, _ := element.Props.Values["viewBox"].(string)
		label, _ := element.Props.Values["label"].(string)
		if !validViewBox(viewBox) || strings.TrimSpace(label) == "" {
			return &ValidationError{Code: "UNSAFE_SVG", Statement: statement, Message: "Svg requires a finite four-number viewBox and a non-empty accessibility label", Hint: "Use Svg(children, \"0 0 100 100\", \"Short mechanism description\")."}
		}
	}
	if element.Type == "Path" {
		path, _ := element.Props.Values["d"].(string)
		if !safeSVGPathRe.MatchString(path) {
			return &ValidationError{Code: "UNSAFE_SVG", Statement: statement, Message: "Path.d contains characters outside safe SVG path syntax", Hint: "Use only path commands, numbers, separators, and exponents."}
		}
	}
	if isSVGComponent(element.Type) && element.Props != nil {
		for _, key := range element.Props.Keys {
			lowerKey := strings.ToLower(key)
			value, _ := element.Props.Values[key].(string)
			lowerValue := strings.ToLower(value)
			if strings.HasPrefix(lowerKey, "on") || ((lowerKey == "style" || lowerKey == "color" || lowerKey == "fill" || lowerKey == "stroke" || lowerKey == "background") && (strings.Contains(lowerValue, "url(") || strings.Contains(lowerValue, ";") || strings.Contains(lowerValue, "javascript:"))) {
				return &ValidationError{Code: "UNSAFE_SVG", Statement: statement, Message: fmt.Sprintf("unsafe SVG property %s", key), Hint: "Use plain colors and static numeric geometry; never use URLs, event handlers, or style declarations."}
			}
		}
	}
	return nil
}

func isSVGComponent(name string) bool {
	switch name {
	case "Svg", "G", "Circle", "Ellipse", "Rect", "Line", "Path", "Polyline", "Polygon", "SvgText":
		return true
	default:
		return false
	}
}

func validViewBox(raw string) bool {
	parts := strings.FieldsFunc(raw, func(r rune) bool { return unicode.IsSpace(r) || r == ',' })
	if len(parts) != 4 {
		return false
	}
	for _, part := range parts {
		value, err := strconv.ParseFloat(part, 64)
		if err != nil || math.IsNaN(value) || math.IsInf(value, 0) {
			return false
		}
	}
	return true
}

func validateSafeURL(raw, statement string) error {
	parsed, err := url.Parse(strings.TrimSpace(raw))
	if err != nil {
		return &ValidationError{Code: "UNSAFE_URL", Statement: statement, Message: fmt.Sprintf("invalid URL %q", raw)}
	}
	switch strings.ToLower(parsed.Scheme) {
	case "http", "https", "mailto":
		return nil
	default:
		return &ValidationError{Code: "UNSAFE_URL", Statement: statement, Message: fmt.Sprintf("URL scheme %q is forbidden", parsed.Scheme), Hint: "Use only http:, https:, or mailto: URLs."}
	}
}

var genericTablePairs = map[string]bool{
	"指标|数值": true, "项目|事实": true, "项目|数值": true, "对象|事实": true,
	"案例|事实": true, "项目|原文事实": true, "metric|value": true, "item|fact": true,
	"key|value": true, "fact|detail": true, "indicator|value": true,
}

var genericFirstColumns = map[string]bool{
	"指标": true, "项目": true, "维度": true, "数据": true, "事实": true, "信息": true,
	"要点": true, "概述": true, "metric": true, "item": true, "field": true, "key": true, "dimension": true,
}

func tableColumns(element *openuilang.Element) []string {
	raw, _ := element.Props.Values["columns"].([]any)
	columns := make([]string, 0, len(raw))
	for _, value := range raw {
		text, _ := value.(string)
		columns = append(columns, text)
	}
	return columns
}

func validateGenericTablePair(element *openuilang.Element) error {
	columns := tableColumns(element)
	if len(columns) != 2 {
		return nil
	}
	pair := normalizeTableHeader(columns[0]) + "|" + normalizeTableHeader(columns[1])
	if genericTablePairs[pair] {
		return &ValidationError{Code: "GENERIC_KV_TABLE", Statement: element.StatementID, Message: fmt.Sprintf("generic two-column key-value table %q is not a reading scaffold", pair), Hint: "Compare real subjects on meaningful dimensions, or use a mechanism, chart, timeline, or annotated quote."}
	}
	return nil
}

func normalizeTableHeader(raw string) string {
	var b strings.Builder
	depth := 0
	for _, r := range strings.ToLower(strings.TrimSpace(raw)) {
		switch r {
		case '(', '（', '[', '【':
			depth++
			continue
		case ')', '）', ']', '】':
			if depth > 0 {
				depth--
			}
			continue
		}
		if depth > 0 || unicode.IsSpace(r) || unicode.IsPunct(r) {
			continue
		}
		b.WriteRune(r)
	}
	return b.String()
}

func validateSoleGenericTable(source *openuilang.Element) error {
	tables, otherVisuals := 0, 0
	countSourceVisuals(source.Props.Values["children"], &tables, &otherVisuals)
	if tables != 1 || otherVisuals != 0 {
		return nil
	}
	var table *openuilang.Element
	findFirstTable(source.Props.Values["children"], &table)
	if table == nil {
		return nil
	}
	columns := tableColumns(table)
	if len(columns) == 2 && genericFirstColumns[normalizeTableHeader(columns[0])] {
		return &ValidationError{Code: "GENERIC_KV_TABLE", Statement: source.StatementID, Message: "a Source whose only visual block is a generic two-column dump is forbidden", Hint: "Use subject-named columns or add a genuinely different explanatory medium."}
	}
	return nil
}

func validateSubstantiveMedium(source *openuilang.Element) error {
	if hasSubstantiveMedium(source.Props.Values["children"]) {
		return nil
	}
	return &ValidationError{
		Code:      "PROSE_WRAPPER_REJECTED",
		Statement: source.StatementID,
		Message:   "Source contains only text, cards, or badges without a visual, structural, or interactive medium",
		Hint:      "Do not wrap narrative prose in a Card/Text/Badge box — the reader already has the full prose. Emit a Source only when Svg, Chart, multi-column Table, Timeline, comparative Grid (>=2 items), Popover/Flashcard, or an interactive Slider/SegmentedControl reveals structure prose cannot.",
	}
}

func hasSubstantiveMedium(value any) bool {
	switch typed := value.(type) {
	case []any:
		for _, item := range typed {
			if hasSubstantiveMedium(item) {
				return true
			}
		}
	case *openuilang.Object:
		if typed != nil {
			for _, key := range typed.Keys {
				if hasSubstantiveMedium(typed.Values[key]) {
					return true
				}
			}
		}
	case *openuilang.Element:
		if typed == nil || typed.Type == "Source" {
			return false
		}
		switch typed.Type {
		case "Svg", "Chart", "Table", "Quote", "Code", "Image", "Popover", "Flashcard", "Celebration":
			return true
		case "List":
			if timeline, ok := typed.Props.Values["timeline"].(bool); ok && timeline {
				return true
			}
			if items, ok := typed.Props.Values["items"].([]any); ok {
				structured := 0
				for _, item := range items {
					if li, ok := item.(*openuilang.Element); ok && li != nil && li.Type == "ListItem" {
						t, _ := li.Props.Values["title"].(string)
						d, _ := li.Props.Values["description"].(string)
						if strings.TrimSpace(t) != "" && strings.TrimSpace(d) != "" {
							structured++
						}
					}
				}
				if structured >= 2 {
					return true
				}
			}
		case "Grid", "Carousel":
			if children, ok := typed.Props.Values["children"].([]any); ok && len(children) >= 2 {
				return true
			}
		default:
			if interactiveComponents[typed.Type] {
				return true
			}
		}
		if typed.Props != nil {
			for _, key := range typed.Props.Keys {
				if hasSubstantiveMedium(typed.Props.Values[key]) {
					return true
				}
			}
		}
	}
	return false
}

func countSourceVisuals(value any, tables, others *int) {
	switch typed := value.(type) {
	case []any:
		for _, item := range typed {
			countSourceVisuals(item, tables, others)
		}
	case *openuilang.Object:
		if typed != nil {
			for _, key := range typed.Keys {
				countSourceVisuals(typed.Values[key], tables, others)
			}
		}
	case *openuilang.Element:
		if typed == nil {
			return
		}
		switch typed.Type {
		case "Col", "Row", "Box", "Grid", "Card", "Form":
			// Layout wrappers are transparent when identifying the sole visual block.
		case "Title", "Text", "Caption", "Markdown", "Label", "Badge", "Divider", "Spacer":
			// Headings, prose, and badges annotate the visual block.
		case "Table":
			*tables++
		case "Source":
			return
		default:
			*others++
		}
		if typed.Type != "Source" && typed.Props != nil {
			for _, key := range typed.Props.Keys {
				countSourceVisuals(typed.Props.Values[key], tables, others)
			}
		}
	}
}

func findFirstTable(value any, found **openuilang.Element) {
	if *found != nil {
		return
	}
	switch typed := value.(type) {
	case []any:
		for _, item := range typed {
			findFirstTable(item, found)
		}
	case *openuilang.Object:
		if typed != nil {
			for _, key := range typed.Keys {
				findFirstTable(typed.Values[key], found)
			}
		}
	case *openuilang.Element:
		if typed == nil {
			return
		}
		if typed.Type == "Table" {
			*found = typed
			return
		}
		if typed.Type != "Source" && typed.Props != nil {
			for _, key := range typed.Props.Keys {
				findFirstTable(typed.Props.Values[key], found)
			}
		}
	}
}

var interactiveComponents = map[string]bool{
	"Button": true, "IconButton": true, "Pressable": true, "Input": true, "TextArea": true,
	"Select": true, "Checkbox": true, "RadioGroup": true, "SegmentedControl": true,
	"Slider": true, "DatePicker": true, "Timer": true, "Flashcard": true,
}

func sourceCategory(source *openuilang.Element) string {
	return categoryRankedValue(source.Props.Values["children"])
}

func categoryRankedValue(value any) string {
	best, bestRank := "Text", 0
	var visit func(any)
	visit = func(value any) {
		switch typed := value.(type) {
		case []any:
			for _, item := range typed {
				visit(item)
			}
		case *openuilang.Object:
			if typed != nil {
				for _, key := range typed.Keys {
					visit(typed.Values[key])
				}
			}
		case *openuilang.Element:
			if typed == nil || typed.Type == "Source" {
				return
			}
			category, rank := "Text", 0
			switch {
			case typed.Type == "Svg":
				category, rank = "Svg", 8
			case typed.Type == "Chart":
				category, rank = "Chart", 7
			case typed.Type == "Table":
				category, rank = "Table", 6
			case typed.Type == "List" && typed.Props.Values["timeline"] == true:
				category, rank = "Timeline", 5
			case typed.Type == "Grid" || typed.Type == "Card":
				category, rank = "Grid/Card", 4
			case interactiveComponents[typed.Type]:
				category, rank = "Interactive", 3
			case typed.Type == "Quote":
				category, rank = "Quote", 2
			case typed.Type == "Text" || typed.Type == "Markdown":
				category, rank = "Text", 1
			}
			if rank > bestRank {
				best, bestRank = category, rank
			}
			if typed.Props != nil {
				for _, key := range typed.Props.Keys {
					visit(typed.Props.Values[key])
				}
			}
		}
	}
	visit(value)
	return best
}

func validateMonotoneView(sources []sourceModule) error {
	if len(sources) < 3 {
		return nil
	}
	counts := map[string]int{}
	for _, source := range sources {
		counts[sourceCategory(source.element)]++
	}
	dominant, maxCount := "", 0
	for _, category := range []string{"Svg", "Chart", "Table", "Timeline", "Grid/Card", "Interactive", "Quote", "Text"} {
		if counts[category] > maxCount {
			dominant, maxCount = category, counts[category]
		}
	}
	if (dominant == "Table" || dominant == "Text") && maxCount*3 > 2*len(sources) {
		return &ValidationError{Code: "MONOTONE_VIEW", Statement: "root", Message: fmt.Sprintf("%d of %d Source blocks are dominated by %s", maxCount, len(sources), dominant), Hint: "Diversify with a grounded mechanism, chart, timeline, comparison, or interactive scenario; do not repeat the same figures."}
	}
	return nil
}

type renderedTextNode struct {
	text      string
	statement string
	title     bool
}

func validateTranslatedCanvas(root *openuilang.Element, opts ValidateOptions) error {
	if !strings.HasPrefix(strings.ToLower(strings.TrimSpace(opts.TargetLang)), "zh") || opts.Mode == bundle.ReadModeOriginal {
		return nil
	}
	var nodes []renderedTextNode
	collectRenderedText(root, &nodes)
	english := 0
	for _, node := range nodes {
		if isEnglishOnly(node.text) {
			if node.title {
				return &ValidationError{Code: "UNTRANSLATED_GENUI", Statement: node.statement, Message: fmt.Sprintf("Title %q remains English-only in a %s %s view", node.text, opts.TargetLang, opts.Mode), Hint: "Translate editorial GenUI text while leaving original quotations and code unchanged."}
			}
			english++
		}
	}
	if len(nodes) >= 2 && english*2 > len(nodes) {
		return &ValidationError{Code: "UNTRANSLATED_GENUI", Statement: "root", Message: fmt.Sprintf("%d of %d eligible rendered text nodes remain English-only", english, len(nodes)), Hint: "Translate GenUI analysis into the target language; Quote, Code, URLs, and short Badge/Label acronyms are exempt."}
	}
	return nil
}

func isEnglishOnly(text string) bool {
	for _, r := range text {
		if unicode.Is(unicode.Han, r) {
			return false
		}
	}
	return len(latinWordRe.FindAllString(text, -1)) >= 3
}

func collectRenderedText(value any, nodes *[]renderedTextNode) {
	switch typed := value.(type) {
	case []any:
		for _, item := range typed {
			collectRenderedText(item, nodes)
		}
	case *openuilang.Object:
		if typed != nil {
			for _, key := range typed.Keys {
				collectRenderedText(typed.Values[key], nodes)
			}
		}
	case *openuilang.Element:
		if typed == nil || typed.Type == "Quote" || typed.Type == "Code" || typed.Props == nil {
			return
		}
		add := func(text string, title, shortExempt bool) {
			if shortExempt && utf8.RuneCountInString(strings.TrimSpace(text)) <= 24 {
				return
			}
			if strings.TrimSpace(text) != "" {
				*nodes = append(*nodes, renderedTextNode{text: text, statement: typed.StatementID, title: title})
			}
		}
		addDirectStrings := func(value any, title, shortExempt bool) {
			switch item := value.(type) {
			case string:
				add(item, title, shortExempt)
			case []any:
				for _, nested := range item {
					if text, ok := nested.(string); ok {
						add(text, title, shortExempt)
					}
				}
			}
		}
		switch typed.Type {
		case "Title":
			addDirectStrings(typed.Props.Values["text"], true, false)
		case "Text", "Caption", "Markdown", "Link", "SvgText":
			addDirectStrings(typed.Props.Values["text"], false, false)
		case "Badge", "Label":
			addDirectStrings(typed.Props.Values["text"], false, true)
		case "ListItem":
			for _, key := range []string{"title", "description", "marker"} {
				addDirectStrings(typed.Props.Values[key], false, false)
			}
		case "Table":
			addDirectStrings(typed.Props.Values["columns"], false, false)
			rows, _ := typed.Props.Values["rows"].([]any)
			for _, row := range rows {
				addDirectStrings(row, false, false)
			}
		case "Image":
			addDirectStrings(typed.Props.Values["alt"], false, false)
		case "Button", "IconButton":
			addDirectStrings(typed.Props.Values["label"], false, false)
		case "Input", "TextArea", "Select", "Checkbox", "RadioGroup", "Slider", "DatePicker", "Timer":
			for _, key := range []string{"label", "placeholder"} {
				addDirectStrings(typed.Props.Values[key], false, false)
			}
		case "Flashcard":
			for _, key := range []string{"front", "back", "hint"} {
				addDirectStrings(typed.Props.Values[key], false, false)
			}
		case "Chart":
			if labels, ok := typed.Props.Values["seriesLabels"].(*openuilang.Object); ok {
				for _, key := range labels.Keys {
					addDirectStrings(labels.Values[key], false, false)
				}
			}
		}
		// Recurse only into containers; scalar style/type/URL properties are ignored.
		for _, key := range typed.Props.Keys {
			collectRenderedTextContainers(typed.Props.Values[key], nodes)
		}
	}
}

func collectRenderedTextContainers(value any, nodes *[]renderedTextNode) {
	switch value.(type) {
	case []any, *openuilang.Object, *openuilang.Element:
		collectRenderedText(value, nodes)
	}
}
