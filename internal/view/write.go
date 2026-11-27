package view

import (
	"fmt"
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
		validated, err := ValidateStrict(string(docBytes), opts.StatementsText, opts.Sources)
		if err != nil {
			return err
		}

		manifest, _, err := bundle.LoadManifest(docPath, docBytes)
		if err != nil {
			return err
		}
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
		if err := bundle.SaveManifest(docPath, manifest); err != nil {
			rollbackView()
			return err
		}

		bindings := make([]bundle.ModuleBinding, 0, len(validated.Modules))
		for _, m := range validated.Modules {
			bindings = append(bindings, bundle.ModuleBinding{
				Statement:  m.Statement,
				SourceID:   m.SourceID,
				Heading:    m.Section.Heading,
				Occurrence: m.Section.Occurrence,
				ShortCode:  fmt.Sprintf("%s·%s@r%d", manifest.BundleID, m.Statement, nextRev),
			})
		}

		out = WriteResult{
			BundleID:    manifest.BundleID,
			ViewPath:    bundle.ViewPath(docPath),
			Revision:    nextRev,
			ViewHash:    bundle.SHA256Hex(rawView),
			ModuleCount: len(bindings),
			Modules:     bindings,
		}
		return nil
	})
	return out, err
}
