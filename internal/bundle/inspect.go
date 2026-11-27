package bundle

import (
	"encoding/json"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"slices"
	"sort"
	"strings"

	"deepread/internal/markdown"
	"deepread/internal/openuilang"
)

// InspectOptions configures optional prose excerpts in Inspect.
type InspectOptions struct {
	Heading    string
	Occurrence int
	StartLine  int
	EndLine    int
}

// SectionSummary describes one extracted section for Agent inspection.
type SectionSummary struct {
	Heading    string `json:"heading"`
	Level      int    `json:"level"`
	Occurrence int    `json:"occurrence"`
	StartLine  int    `json:"startLine"`
	EndLine    int    `json:"endLine"`
	Hash       string `json:"hash"`
	Synthetic  bool   `json:"synthetic,omitempty"`
}

// OpenNote describes a pending reader note (either tracked in ledger.json or
// newly written in Mark Go Go desktop).
type OpenNote struct {
	NoteID            string `json:"noteId,omitempty"`
	Origin            string `json:"origin"` // "ledger" | "desktop"
	Node              string `json:"node,omitempty"`
	BaseRev           int    `json:"baseRev,omitempty"`
	SectionHeading    string `json:"sectionHeading,omitempty"`
	SectionOccurrence int    `json:"sectionOccurrence,omitempty"`
	Text              string `json:"text"`
}

// SourceIssue reports a stale or missing source reference in .genui.json.
type SourceIssue struct {
	SourceID   string `json:"sourceId"`
	Heading    string `json:"heading"`
	Occurrence int    `json:"occurrence"`
	SavedHash  string `json:"savedHash,omitempty"`
	LiveHash   string `json:"liveHash,omitempty"`
}

// Excerpt holds requested prose lines so the Agent can verify exact figures.
type Excerpt struct {
	StartLine int    `json:"startLine"`
	EndLine   int    `json:"endLine"`
	Text      string `json:"text"`
}

// InspectReport is the single structured read-state output of `deepread inspect`.
type InspectReport struct {
	BundleID           string             `json:"bundleId"`
	DocPath            string             `json:"docPath"`
	Revision           int                `json:"revision"`
	Profile            string             `json:"profile,omitempty"`
	Reader             *ReaderConfig      `json:"reader,omitempty"`
	Translation        *TranslationStatus `json:"translation,omitempty"`
	ViewExists         bool               `json:"viewExists"`
	ViewHash           string             `json:"viewHash,omitempty"`
	LineCount          int                `json:"lineCount"`
	Sections           []SectionSummary   `json:"sections"`
	Modules            []ModuleBinding    `json:"modules,omitempty"`
	OpenNotes          []OpenNote         `json:"openNotes"`
	StaleSources       []SourceIssue      `json:"staleSources"`
	MissingSources     []SourceIssue      `json:"missingSources"`
	AffectedStatements []string           `json:"affectedStatements"`
	Excerpt            *Excerpt           `json:"excerpt,omitempty"`
}

// ModuleBinding maps a Source statement in .genui.json to its target section(s).
type ModuleBinding struct {
	Statement  string          `json:"statement"`
	SourceID   string          `json:"sourceId"`
	Heading    string          `json:"heading"`
	Occurrence int             `json:"occurrence"`
	Sections   []SourceBinding `json:"sections,omitempty"`
	ShortCode  string          `json:"shortCode"`
}

// ViewPath returns the Mark Go Go-compatible sidecar path (.<base>.genui.json).
func ViewPath(docPath string) string {
	if docPath == "" {
		return ""
	}
	return filepath.Join(filepath.Dir(docPath), "."+filepath.Base(docPath)+".genui.json")
}

// PrevViewPath returns Mark Go Go's exact undo backup path (.<base>.genui.prev.json).
func PrevViewPath(viewPath string) string {
	return strings.TrimSuffix(viewPath, ".json") + ".prev.json"
}

// Inspect computes the complete bundle state for docPath without mutating disk.
func Inspect(docPath string, opts InspectOptions) (InspectReport, error) {
	var out InspectReport
	err := WithDocRLock(docPath, func() error {
		rep, err := inspectUnlocked(docPath, opts)
		if err != nil {
			return err
		}
		out = rep
		return nil
	})
	return out, err
}

func inspectUnlocked(docPath string, opts InspectOptions) (InspectReport, error) {
	rawBytes, err := os.ReadFile(docPath)
	if err != nil {
		return InspectReport{}, err
	}
	raw := string(rawBytes)
	manifest, _, err := LoadManifest(docPath, rawBytes)
	if err != nil {
		return InspectReport{}, err
	}
	ledger, err := LoadLedger(docPath)
	if err != nil {
		return InspectReport{}, err
	}

	sections := markdown.ExtractSections(raw)
	secSummaries := make([]SectionSummary, len(sections))
	type secKey struct {
		norm string
		occ  int
	}
	secMap := make(map[secKey]markdown.Section, len(sections))
	for i, s := range sections {
		secSummaries[i] = SectionSummary{
			Heading:    s.Heading,
			Level:      s.Level,
			Occurrence: s.Occurrence,
			StartLine:  s.StartLine,
			EndLine:    s.EndLine,
			Hash:       s.Hash,
			Synthetic:  manifest.IsSynthetic(s.Heading, s.Occurrence),
		}
		secMap[secKey{markdown.NormalizeHeadingText(s.Heading), s.Occurrence}] = s
	}

	report := InspectReport{
		BundleID:           manifest.BundleID,
		DocPath:            docPath,
		Revision:           manifest.Revision,
		Profile:            manifest.Profile,
		Reader:             manifest.Reader,
		LineCount:          len(strings.Split(strings.ReplaceAll(raw, "\r\n", "\n"), "\n")),
		Sections:           secSummaries,
		OpenNotes:          []OpenNote{},
		StaleSources:       []SourceIssue{},
		MissingSources:     []SourceIssue{},
		AffectedStatements: []string{},
	}

	// Translation coverage is loaded under the same lock as the rest of the
	// report so status never disagrees with the sections above.
	if manifest.Reader != nil && strings.TrimSpace(manifest.Reader.TargetLang) != "" {
		_, status, err := LoadTranslationUnlocked(docPath, manifest.Reader.TargetLang, rawBytes, manifest)
		if err != nil {
			return InspectReport{}, err
		}
		report.Translation = &status
	}

	// Inspect sidecar if present.
	sourceToStmts := map[string][]string{}
	secToStmts := map[secKey][]string{}
	viewBytes, err := os.ReadFile(ViewPath(docPath))
	if err == nil {
		if len(viewBytes) > MaxViewBytes {
			return InspectReport{}, fmt.Errorf("view exceeds %d bytes (%d bytes)", MaxViewBytes, len(viewBytes))
		}
		report.ViewExists = true
		report.ViewHash = SHA256Hex(viewBytes)
		var env struct {
			Sources map[string]struct {
				Heading    string `json:"heading"`
				Occurrence int    `json:"occurrence"`
				Hash       string `json:"hash"`
			} `json:"sources"`
			A2UI []struct {
				CreateSurface    *struct{ Components []string } `json:"createSurface"`
				UpdateComponents *struct{ Components []string } `json:"updateComponents"`
			} `json:"a2ui"`
		}
		if err := json.Unmarshal(viewBytes, &env); err != nil {
			return InspectReport{}, fmt.Errorf("parse view JSON: %w", err)
		}
		if true {
			mergedText := ""
			for _, m := range env.A2UI {
				if m.CreateSurface != nil {
					mergedText = openuilang.Overlay(mergedText, strings.Join(m.CreateSurface.Components, "\n"))
				} else if m.UpdateComponents != nil {
					mergedText = openuilang.Overlay(mergedText, strings.Join(m.UpdateComponents.Components, "\n"))
				}
			}
			// One ModuleBinding per Source statement; a multi-section
			// Source(["s1", "s2"], [...]) call keeps every section in Sections
			// while SourceID/Heading/Occurrence mirror the first section for
			// backward compatibility with single-source consumers.
			moduleIdx := map[string]int{}
			rev := manifest.Revision
			if rev < 1 {
				rev = 1
			}
			for _, use := range openuilang.FirstArgumentStrings(mergedText, "Source") {
				binding := ModuleBinding{
					Statement: use.Statement,
					ShortCode: fmt.Sprintf("%s·%s@r%d", manifest.BundleID, use.Statement, rev),
				}
				for _, sid := range use.Strings {
					sid = strings.TrimSpace(sid)
					if sid == "" {
						continue
					}
					sourceToStmts[sid] = append(sourceToStmts[sid], use.Statement)
					src, ok := env.Sources[sid]
					if !ok {
						continue
					}
					occ := src.Occurrence
					if occ < 1 {
						occ = 1
					}
					k := secKey{markdown.NormalizeHeadingText(src.Heading), occ}
					secToStmts[k] = append(secToStmts[k], use.Statement)
					binding.Sections = append(binding.Sections, SourceBinding{
						SourceID:   sid,
						Heading:    src.Heading,
						Occurrence: occ,
					})
				}
				if len(binding.Sections) == 0 {
					continue
				}
				first := binding.Sections[0]
				binding.SourceID = first.SourceID
				binding.Heading = first.Heading
				binding.Occurrence = first.Occurrence
				if idx, ok := moduleIdx[use.Statement]; ok {
					report.Modules[idx].Sections = append(report.Modules[idx].Sections, binding.Sections...)
					continue
				}
				moduleIdx[use.Statement] = len(report.Modules)
				report.Modules = append(report.Modules, binding)
			}
			// Sort source IDs deterministically.
			sids := make([]string, 0, len(env.Sources))
			for sid := range env.Sources {
				sids = append(sids, sid)
			}
			sort.Strings(sids)
			affectedSet := map[string]bool{}
			for _, sid := range sids {
				src := env.Sources[sid]
				occ := src.Occurrence
				if occ < 1 {
					occ = 1
				}
				sec, ok := secMap[secKey{markdown.NormalizeHeadingText(src.Heading), occ}]
				if !ok {
					report.MissingSources = append(report.MissingSources, SourceIssue{
						SourceID:   sid,
						Heading:    src.Heading,
						Occurrence: occ,
						SavedHash:  src.Hash,
					})
					for _, stmt := range sourceToStmts[sid] {
						affectedSet[stmt] = true
					}
					continue
				}
				if src.Hash != "" && !sec.UnchangedSince(src.Hash) {
					report.StaleSources = append(report.StaleSources, SourceIssue{
						SourceID:   sid,
						Heading:    src.Heading,
						Occurrence: occ,
						SavedHash:  src.Hash,
						LiveHash:   sec.Hash,
					})
					for _, stmt := range sourceToStmts[sid] {
						affectedSet[stmt] = true
					}
				}
			}
			for stmt := range affectedSet {
				report.AffectedStatements = append(report.AffectedStatements, stmt)
			}
		}
	} else if !errors.Is(err, fs.ErrNotExist) {
		return InspectReport{}, err
	}

	// Merge open notes from ledger + untracked desktop inline notes.
	trackedIDs := map[string]bool{}
	affectedSet := map[string]bool{}
	for _, stmt := range report.AffectedStatements {
		affectedSet[stmt] = true
	}
	for _, entry := range ledger.Notes {
		trackedIDs[entry.NoteID] = true
		if entry.Status == NoteStatusOpen {
			report.OpenNotes = append(report.OpenNotes, OpenNote{
				NoteID:            entry.NoteID,
				Origin:            "ledger",
				Node:              entry.Node,
				BaseRev:           entry.BaseRev,
				SectionHeading:    entry.SectionHeading,
				SectionOccurrence: entry.SectionOccurrence,
				Text:              entry.Text,
			})
			if entry.Node != "" {
				affectedSet[entry.Node] = true
			} else if entry.SectionHeading != "" {
				occ := entry.SectionOccurrence
				if occ < 1 {
					occ = 1
				}
				for _, stmt := range secToStmts[secKey{markdown.NormalizeHeadingText(entry.SectionHeading), occ}] {
					affectedSet[stmt] = true
				}
			}
		}
	}

	for _, n := range markdown.ExtractNotes(raw) {
		attrs := markdown.NoteAttrs(raw, n)
		if id := attrs["id"]; id != "" && trackedIDs[id] {
			continue
		}
		node := attrs["node"]
		report.OpenNotes = append(report.OpenNotes, OpenNote{
			NoteID:            attrs["id"],
			Origin:            "desktop",
			Node:              node,
			SectionHeading:    n.SectionHeading,
			SectionOccurrence: n.SectionOccurrence,
			Text:              n.Text,
		})
		if node != "" {
			affectedSet[node] = true
		} else if n.SectionHeading != "" {
			occ := n.SectionOccurrence
			if occ < 1 {
				occ = 1
			}
			for _, stmt := range secToStmts[secKey{markdown.NormalizeHeadingText(n.SectionHeading), occ}] {
				affectedSet[stmt] = true
			}
		}
	}

	report.AffectedStatements = report.AffectedStatements[:0]
	for stmt := range affectedSet {
		report.AffectedStatements = append(report.AffectedStatements, stmt)
	}
	slices.Sort(report.AffectedStatements)

	// Optional prose excerpt.
	if opts.Heading != "" {
		occ := opts.Occurrence
		if occ < 1 {
			occ = 1
		}
		sec, ok := secMap[secKey{markdown.NormalizeHeadingText(opts.Heading), occ}]
		if !ok {
			return InspectReport{}, fmt.Errorf("%w: section %q (occurrence %d)", ErrNotFound, opts.Heading, occ)
		}
		idx := -1
		for i, s := range sections {
			if s.Heading == sec.Heading && s.Occurrence == sec.Occurrence {
				idx = i
				break
			}
		}
		endByte := markdown.OwnBodyEndByte(raw, sections, idx)
		report.Excerpt = &Excerpt{
			StartLine: sec.StartLine,
			EndLine:   sec.EndLine,
			Text:      raw[sec.ByteStart():endByte],
		}
	} else if opts.StartLine > 0 || opts.EndLine > 0 {
		lines := strings.Split(strings.ReplaceAll(raw, "\r\n", "\n"), "\n")
		start, end := opts.StartLine, opts.EndLine
		if start < 1 {
			start = 1
		}
		if end == 0 || end > len(lines) {
			end = len(lines)
		}
		if start > end || start > len(lines) {
			return InspectReport{}, fmt.Errorf("invalid line range %d:%d (document has %d lines)", start, end, len(lines))
		}
		var b strings.Builder
		for i := start; i <= end; i++ {
			fmt.Fprintf(&b, "%d: %s\n", i, lines[i-1])
		}
		report.Excerpt = &Excerpt{
			StartLine: start,
			EndLine:   end,
			Text:      b.String(),
		}
	}

	return report, nil
}
