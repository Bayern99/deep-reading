package view

import (
	"errors"
	"fmt"
	"io/fs"
	"os"
	"strconv"
	"strings"
	"time"

	"deepread/internal/bundle"
)

// WriteOptions configures `deepread write`.
type WriteOptions struct {
	StatementsText string
	Sources        map[string]SourceRef
	Profile        string
	Citations      bundle.CitationMap
	Model          string
	Request        string
	Now            time.Time
}

// WriteResult summarizes a committed v3 view.
type WriteResult struct {
	BundleID    string                 `json:"bundleId"`
	ViewPath    string                 `json:"viewPath"`
	Revision    int                    `json:"revision"`
	ViewHash    string                 `json:"viewHash"`
	ModuleCount int                    `json:"moduleCount"`
	Modules     []bundle.ModuleBinding `json:"modules"`
}

// ParseSourceFlag parses `--source id="Exact Heading"#occ` (where `#occ` is
// optional and defaults to 1).
func ParseSourceFlag(spec string) (id string, ref SourceRef, err error) {
	eq := strings.IndexByte(spec, '=')
	if eq <= 0 || eq == len(spec)-1 {
		return "", SourceRef{}, fmt.Errorf("invalid --source %q: expected id=Heading or id=Heading#occurrence", spec)
	}
	id = strings.TrimSpace(spec[:eq])
	rhs := strings.TrimSpace(spec[eq+1:])
	occ := 1
	if hash := strings.LastIndexByte(rhs, '#'); hash > 0 && hash < len(rhs)-1 {
		if n, convErr := strconv.Atoi(rhs[hash+1:]); convErr == nil && n >= 1 {
			occ = n
			rhs = strings.TrimSpace(rhs[:hash])
		}
	}
	if rhs == "" {
		return "", SourceRef{}, fmt.Errorf("invalid --source %q: heading cannot be empty", spec)
	}
	return id, SourceRef{Heading: rhs, Occurrence: occ}, nil
}

// Write validates bare openui-lang statements strictly against docPath and
// commits a Mark Go Go-compatible compacted v3 sidecar under a cross-process lock.
func Write(docPath string, opts WriteOptions) (WriteResult, error) {
	var out WriteResult
	err := bundle.WithDocLock(docPath, func() error {
		docBytes, err := os.ReadFile(docPath)
		if err != nil {
			return err
		}
		manifest, hadManifest, err := bundle.LoadManifest(docPath, docBytes)
		if err != nil {
			return err
		}
		profile := opts.Profile
		if profile == "" {
			profile = bundle.ProfileCanvas
		}
		reader := manifest.Reader
		targetLang, mode := "", ""
		if reader != nil {
			targetLang, mode = reader.TargetLang, reader.Mode
		}
		validated, err := ValidateWithOptions(docPath, docBytes, SplitStatementStrings(opts.StatementsText), opts.Sources, ValidateOptions{
			Profile: profile, TargetLang: targetLang, Mode: mode, StrictEditorial: true,
		})
		if err != nil {
			return err
		}

		previousManifest := manifest
		nextRev := manifest.Revision + 1
		rawView, err := BuildCompactedEnvelope(validated.Statements, validated.Sources, opts.Model, opts.Request, opts.Now)
		if err != nil {
			return err
		}
		rollbackView, err := CommitViewFile(docPath, rawView, "", nextRev)
		if err != nil {
			return err
		}

		manifest.Revision = nextRev
		manifest.SourceDigest = bundle.SHA256Hex(docBytes)
		manifest.Profile = profile
		if err := bundle.SaveManifest(docPath, manifest); err != nil {
			rollbackView()
			return err
		}
		rollbackCitations := func() {}
		if opts.Citations != nil {
			rollbackCitations, err = saveCitationsWithRollback(docPath, opts.Citations)
			if err != nil {
				rollbackView()
				restoreManifest(docPath, previousManifest, hadManifest)
				return err
			}
		}
		_ = rollbackCitations // no fallible operation follows a successful citation write

		out = WriteResult{
			BundleID:    manifest.BundleID,
			ViewPath:    bundle.ViewPath(docPath),
			Revision:    nextRev,
			ViewHash:    bundle.SHA256Hex(rawView),
			ModuleCount: len(validated.Modules),
			Modules:     validatedModuleBindings(validated.Modules, validated.Sources, manifest.BundleID, nextRev),
		}
		return nil
	})
	return out, err
}

func validatedModuleBindings(modules []ValidatedModule, sources map[string]SourceRef, bundleID string, revision int) []bundle.ModuleBinding {
	bindings := make([]bundle.ModuleBinding, 0, len(modules))
	for _, module := range modules {
		shortCode := fmt.Sprintf("%s·%s@r%d", bundleID, module.Statement, revision)
		module.ShortCode = shortCode
		sections := make([]bundle.SourceBinding, 0, len(module.Sections))
		for _, ref := range module.Sections {
			sections = append(sections, bundle.SourceBinding{
				SourceID:   ref.SourceID,
				Heading:    ref.Section.Heading,
				Occurrence: ref.Section.Occurrence,
				SourceHash: sources[ref.SourceID].Hash,
			})
		}
		bindings = append(bindings, bundle.ModuleBinding{
			Statement:  module.Statement,
			SourceID:   module.SourceID,
			Heading:    module.Section.Heading,
			Occurrence: module.Section.Occurrence,
			Sections:   sections,
			ShortCode:  shortCode,
		})
	}
	return bindings
}

// saveCitationsWithRollback persists citations only when the caller supplied a
// map, and returns an exact-byte rollback for any later metadata failure.
func saveCitationsWithRollback(docPath string, citations bundle.CitationMap) (func(), error) {
	path := bundle.CitationsPath(docPath)
	previous, err := os.ReadFile(path)
	hadPrevious := err == nil
	if err != nil && !errors.Is(err, fs.ErrNotExist) {
		return nil, err
	}
	if err := bundle.SaveCitations(docPath, citations); err != nil {
		return nil, err
	}
	return func() {
		if hadPrevious {
			_ = bundle.WriteFileAtomic(path, previous, 0o644)
		} else {
			_ = os.Remove(path)
		}
	}, nil
}

func restoreManifest(docPath string, manifest bundle.Manifest, existed bool) {
	if existed {
		_ = bundle.SaveManifest(docPath, manifest)
	} else {
		_ = os.Remove(bundle.ManifestPath(docPath))
	}
}
