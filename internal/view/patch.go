package view

import (
	"fmt"
	"os"
	"strings"
	"time"

	"deepread/internal/bundle"
	"deepread/internal/markdown"
	"deepread/internal/openuilang"
)

// PatchOptions configures a compare-and-swap update of selected Source modules.
type PatchOptions struct {
	Replace            []string             // Top-level Source statement names to replace.
	ExpectHash         string               // Required SHA-256 of the current sidecar.
	ExpectSourceHashes map[string]string    // Optional sourceId -> live fnv1a32 hash (required when target prose changed).
	StatementsText     string               // Replacement statements and optional new helpers.
	AddedSources       map[string]SourceRef // Optional additional source mappings.
	ResolveNotes       []string             // Ledger note IDs to resolve upon commit.
	Model              string
	Request            string
	Now                time.Time
}

// PatchResult summarizes a compacted, committed patch revision.
type PatchResult struct {
	BundleID      string                 `json:"bundleId"`
	ViewPath      string                 `json:"viewPath"`
	Revision      int                    `json:"revision"`
	ViewHash      string                 `json:"viewHash"`
	Replaced      []string               `json:"replaced"`
	ResolvedNotes []string               `json:"resolvedNotes,omitempty"`
	Modules       []bundle.ModuleBinding `json:"modules"`
}

// Patch replaces explicitly selected top-level Source statements, validates the
// merged program, and commits a single-createSurface sidecar under CAS.
func Patch(docPath string, opts PatchOptions) (PatchResult, error) {
	var out PatchResult
	if len(opts.Replace) == 0 {
		return out, &ValidationError{Code: "EMPTY_REPLACEMENT", Path: "/replace", Message: "replace must name at least one top-level Source statement"}
	}
	expectHash := strings.ToLower(strings.TrimSpace(opts.ExpectHash))
	if expectHash == "" {
		return out, &ValidationError{Code: "MISSING_EXPECT_HASH", Path: "/expectHash", Message: "expectHash is required for compare-and-swap patching"}
	}

	err := bundle.WithDocLock(docPath, func() error {
		rawView, err := os.ReadFile(bundle.ViewPath(docPath))
		if err != nil {
			return err
		}
		if bundle.SHA256Hex(rawView) != expectHash {
			return fmt.Errorf("%w: view changed since read (expected %s)", ErrHashConflict, expectHash)
		}
		parsed, err := ReadView(rawView)
		if err != nil {
			return err
		}
		current, err := patchStatementsByName(parsed.Statements)
		if err != nil {
			return err
		}
		rootRefs, err := patchRootReferences(current)
		if err != nil {
			return err
		}

		sourceCalls := map[string]openuilang.CallStrings{}
		for _, call := range openuilang.FirstArgumentStrings(parsed.JoinedText, "Source") {
			if _, exists := sourceCalls[call.Statement]; exists {
				return &ValidationError{Code: "INVALID_CURRENT_VIEW", Statement: call.Statement, Message: "statement contains multiple Source calls"}
			}
			sourceCalls[call.Statement] = call
		}

		replaced := make([]string, 0, len(opts.Replace))
		replaceSet := make(map[string]bool, len(opts.Replace))
		for _, rawName := range opts.Replace {
			name := strings.TrimSpace(rawName)
			if name == "" {
				return &ValidationError{Code: "INVALID_REPLACEMENT_TARGET", Message: "replacement statement name cannot be empty"}
			}
			if replaceSet[name] {
				return &ValidationError{Code: "DUPLICATE_REPLACEMENT_TARGET", Statement: name, Message: fmt.Sprintf("statement %q is listed more than once", name)}
			}
			_, exists := current[name]
			_, isSource := sourceCalls[name]
			if name == "root" || !exists || !rootRefs[name] || !isSource {
				return &ValidationError{
					Code:      "INVALID_REPLACEMENT_TARGET",
					Statement: name,
					Message:   fmt.Sprintf("statement %q is not a top-level Source referenced by root", name),
					Hint:      "Replace only existing root children; root itself and private helpers cannot be replacement targets.",
				}
			}
			replaceSet[name] = true
			replaced = append(replaced, name)
		}

		patchStatements := SplitStatementStrings(opts.StatementsText)
		patchByName, err := patchStatementsByName(patchStatements)
		if err != nil {
			return err
		}
		for name := range patchByName {
			_, exists := current[name]
			if name == "root" || (exists && !replaceSet[name]) {
				return &ValidationError{
					Code:      "PATCH_SCOPE_VIOLATION",
					Statement: name,
					Message:   fmt.Sprintf("statement %q is root or an existing statement not listed in replace", name),
					Hint:      "List every existing statement to modify in replace; new private helper names must not already exist.",
				}
			}
		}
		for _, name := range replaced {
			if _, ok := patchByName[name]; !ok {
				return &ValidationError{Code: "MISSING_REPLACEMENT", Statement: name, Message: fmt.Sprintf("replacement statement %q is missing from statementsText", name)}
			}
		}

		mergedText := openuilang.Merge(parsed.JoinedText, strings.Join(patchStatements, "\n"))
		mergedSources := make(map[string]SourceRef, len(parsed.Envelope.Sources)+len(opts.AddedSources))
		for id, source := range parsed.Envelope.Sources {
			mergedSources[id] = source
		}
		for id, source := range opts.AddedSources {
			if strings.TrimSpace(id) == "" {
				return &ValidationError{Code: "INVALID_SOURCE_ID", Path: "/sources", Message: "added source ID cannot be empty"}
			}
			if source.Occurrence < 1 {
				source.Occurrence = 1
			}
			source.Hash = "" // Live validation, never caller input, stamps hashes.
			if existing, ok := mergedSources[id]; ok {
				if !patchSameSourceSection(existing, source) {
					return &ValidationError{
						Code:    "SOURCE_CONFLICT",
						Path:    "/sources/" + id,
						Message: fmt.Sprintf("source %q is already mapped to a different section", id),
						Hint:    "Use a new source ID or keep the existing heading and occurrence unchanged.",
					}
				}
				continue
			}
			mergedSources[id] = source
		}

		docBytes, err := os.ReadFile(docPath)
		if err != nil {
			return err
		}
		validated, err := ValidateStrict(string(docBytes), mergedText, mergedSources)
		if err != nil {
			return err
		}

		type sectionKey struct {
			heading string
			occ     int
		}
		replacedSections := map[sectionKey]bool{}
		for _, name := range replaced {
			call := sourceCalls[name]
			if !call.Literal || len(call.Strings) != 1 {
				continue
			}
			if source, ok := parsed.Envelope.Sources[call.Strings[0]]; ok {
				occ := source.Occurrence
				if occ < 1 {
					occ = 1
				}
				replacedSections[sectionKey{markdown.NormalizeHeadingText(source.Heading), occ}] = true
			}
		}
		for _, module := range validated.Modules {
			if replaceSet[module.Statement] {
				continue
			}
			key := sectionKey{markdown.NormalizeHeadingText(module.Section.Heading), module.Section.Occurrence}
			if replacedSections[key] {
				continue
			}
			if previous, ok := parsed.Envelope.Sources[module.SourceID]; ok && patchSameSourceSection(previous, validated.Sources[module.SourceID]) {
				source := validated.Sources[module.SourceID]
				source.Hash = previous.Hash
				validated.Sources[module.SourceID] = source
			}
		}

		// Guard against silently clearing a stale-source flag when target prose
		// changed after the sidecar was written — checked by (heading, occurrence)
		// across ALL previous sources so renaming a source ID (e.g. s1 -> fresh)
		// cannot bypass staleness detection.
		prevHashBySection := map[sectionKey]string{}
		for _, prev := range parsed.Envelope.Sources {
			if prev.Hash == "" {
				continue
			}
			occ := prev.Occurrence
			if occ < 1 {
				occ = 1
			}
			k := sectionKey{markdown.NormalizeHeadingText(prev.Heading), occ}
			prevHashBySection[k] = prev.Hash
		}
		for _, module := range validated.Modules {
			if !replaceSet[module.Statement] {
				continue
			}
			expected, hasExpected := opts.ExpectSourceHashes[module.SourceID]
			if hasExpected {
				if !module.Section.UnchangedSince(strings.TrimSpace(expected)) {
					return fmt.Errorf("%w: target section %q (%s) changed since inspect (expected %s, live %s)", ErrHashConflict, module.Section.Heading, module.SourceID, expected, module.Section.Hash)
				}
				continue
			}
			k := sectionKey{markdown.NormalizeHeadingText(module.Section.Heading), module.Section.Occurrence}
			if prevHash, existed := prevHashBySection[k]; existed && prevHash != "" {
				if !module.Section.UnchangedSince(prevHash) {
					return fmt.Errorf("%w: target section %q (%s) prose changed since sidecar (saved %s, live %s); inspect the updated section and pass --expect-source-hash %s=%s", ErrHashConflict, module.Section.Heading, module.SourceID, prevHash, module.Section.Hash, module.SourceID, module.Section.Hash)
				}
			}
		}

		manifest, hadManifest, err := bundle.LoadManifest(docPath, docBytes)
		if err != nil {
			return err
		}
		prevManifest := manifest
		nextRev := manifest.Revision + 1
		now := opts.Now
		if now.IsZero() {
			now = time.Now()
		}

		var ledger bundle.Ledger
		if len(opts.ResolveNotes) > 0 {
			ledger, err = bundle.LoadLedger(docPath)
			if err != nil {
				return err
			}
			// Resolve in memory before committing so an unknown note ID cannot
			// leave a partially committed view or manifest behind.
			for _, noteID := range opts.ResolveNotes {
				if err := ledger.Resolve(noteID, now); err != nil {
					return fmt.Errorf("%w: %v", bundle.ErrNotFound, err)
				}
			}
		}

		compacted, err := BuildCompactedEnvelope(validated.Statements, validated.Sources, opts.Model, opts.Request, now)
		if err != nil {
			return err
		}
		rollbackView, err := CommitViewFile(docPath, compacted, expectHash, nextRev)
		if err != nil {
			return err
		}
		manifest.Revision = nextRev
		manifest.SourceDigest = bundle.SHA256Hex(docBytes)
		if err := bundle.SaveManifest(docPath, manifest); err != nil {
			rollbackView()
			return err
		}
		if len(opts.ResolveNotes) > 0 {
			if err := bundle.SaveLedger(docPath, ledger); err != nil {
				rollbackView()
				if hadManifest {
					_ = bundle.SaveManifest(docPath, prevManifest)
				}
				return err
			}
		}

		modules := make([]bundle.ModuleBinding, 0, len(validated.Modules))
		for _, module := range validated.Modules {
			modules = append(modules, bundle.ModuleBinding{
				Statement:  module.Statement,
				SourceID:   module.SourceID,
				Heading:    module.Section.Heading,
				Occurrence: module.Section.Occurrence,
				ShortCode:  fmt.Sprintf("%s·%s@r%d", manifest.BundleID, module.Statement, nextRev),
			})
		}
		out = PatchResult{
			BundleID:      manifest.BundleID,
			ViewPath:      bundle.ViewPath(docPath),
			Revision:      nextRev,
			ViewHash:      bundle.SHA256Hex(compacted),
			Replaced:      append([]string(nil), replaced...),
			ResolvedNotes: append([]string(nil), opts.ResolveNotes...),
			Modules:       modules,
		}
		return nil
	})
	return out, err
}

func patchStatementsByName(statements []string) (map[string]string, error) {
	out := make(map[string]string, len(statements))
	for _, statement := range statements {
		names := openuilang.Names(statement)
		if len(names) != 1 || strings.TrimSpace(names[0]) == "" {
			return nil, &ValidationError{
				Code:    "INVALID_STATEMENT",
				Path:    "/statements",
				Message: fmt.Sprintf("invalid statement: %q", statement),
				Hint:    "Write exactly one named assignment per statement.",
			}
		}
		name := names[0]
		if _, exists := out[name]; exists {
			return nil, &ValidationError{Code: "DUPLICATE_STATEMENT", Statement: name, Message: fmt.Sprintf("statement %q is defined more than once", name)}
		}
		out[name] = statement
	}
	return out, nil
}

func patchRootReferences(statements map[string]string) (map[string]bool, error) {
	root, ok := statements["root"]
	if !ok {
		return nil, &ValidationError{Code: "NO_ROOT", Statement: "root", Message: "current view has no root statement"}
	}
	match := rootColItemsRe.FindStringSubmatch(strings.TrimSpace(root))
	if match == nil {
		return nil, &ValidationError{Code: "INVALID_ROOT_TOPOLOGY", Statement: "root", Message: "current view root must be root = Col([statement, ...])"}
	}
	refs := map[string]bool{}
	if inner := strings.TrimSpace(match[1]); inner != "" {
		for _, item := range strings.Split(inner, ",") {
			name := strings.TrimSpace(item)
			if name == "" || strings.ContainsAny(name, "()[]{}\"' \t") {
				return nil, &ValidationError{Code: "INVALID_ROOT_CHILD", Statement: "root", Message: fmt.Sprintf("invalid root child %q", name)}
			}
			refs[name] = true
		}
	}
	return refs, nil
}

func patchSameSourceSection(a, b SourceRef) bool {
	aOcc, bOcc := a.Occurrence, b.Occurrence
	if aOcc < 1 {
		aOcc = 1
	}
	if bOcc < 1 {
		bOcc = 1
	}
	return markdown.NormalizeHeadingText(a.Heading) == markdown.NormalizeHeadingText(b.Heading) && aOcc == bOcc
}
