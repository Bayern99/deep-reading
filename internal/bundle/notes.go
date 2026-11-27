package bundle

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"regexp"
	"strings"
	"time"

	"deepread/internal/markdown"
	"deepread/internal/openuilang"
)

// AddNoteOptions configures one reader note attached to a document section.
type AddNoteOptions struct {
	Node       string // Target statement name, resolved through the current view.
	Heading    string // Alternative: target a section heading directly.
	Occurrence int    // Defaults to 1 when a heading is used.
	Text       string // Required non-empty note text.
	BaseRev    int    // Optional compare-and-swap revision.
	MsgID      string // Optional external message ID for idempotent delivery.
	SourceID   string // Optional source ID for a multi-section Source statement.
	Now        time.Time
}

// ErrStaleRevision indicates that the reader based a note on an older view.
var ErrStaleRevision = errors.New("stale revision")

// AddNoteResult describes the persisted note, or an idempotent duplicate.
type AddNoteResult struct {
	NoteID            string `json:"noteId"`
	Duplicate         bool   `json:"duplicate,omitempty"`
	Node              string `json:"node,omitempty"`
	SectionHeading    string `json:"sectionHeading"`
	SectionOccurrence int    `json:"sectionOccurrence"`
	BaseRev           int    `json:"baseRev"`
	Text              string `json:"text"`
}

var noteCommentCloserRe = regexp.MustCompile(`--[\\]*!?>`)

// AddNote inserts a Mark Go Go-compatible inline note at the target section's
// own-body end and records it in the ledger under the document lock.
func AddNote(docPath string, opts AddNoteOptions) (AddNoteResult, error) {
	var out AddNoteResult
	err := WithDocLock(docPath, func() error {
		text := normalizeNoteLine(opts.Text)
		if text == "" {
			return errors.New("note text cannot be empty")
		}
		node := strings.TrimSpace(opts.Node)
		heading := strings.TrimSpace(opts.Heading)
		if node == "" && heading == "" {
			return errors.New("note target requires either node or heading")
		}

		docBytes, err := os.ReadFile(docPath)
		if err != nil {
			return err
		}
		fileMode := FilePerm(docPath)
		raw := string(docBytes)
		manifest, manifestExisted, err := LoadManifest(docPath, docBytes)
		if err != nil {
			return err
		}
		ledger, err := LoadLedger(docPath)
		if err != nil {
			return err
		}

		if opts.MsgID != "" {
			if existing, ok := ledger.FindByMsgID(opts.MsgID); ok {
				out = addNoteResultFromEntry(*existing)
				out.Duplicate = true
				return nil
			}
		}
		if opts.BaseRev > 0 && manifest.Revision > 0 && opts.BaseRev != manifest.Revision {
			return fmt.Errorf("%w: base revision %d, current revision %d", ErrStaleRevision, opts.BaseRev, manifest.Revision)
		}

		occurrence := opts.Occurrence
		if occurrence < 1 {
			occurrence = 1
		}
		if node != "" {
			heading, occurrence, err = noteTargetForNode(docPath, node, opts.SourceID)
			if err != nil {
				return err
			}
		}

		sections := markdown.ExtractSections(raw)
		sectionIdx := -1
		normalizedHeading := markdown.NormalizeHeadingText(heading)
		for i, sec := range sections {
			if markdown.NormalizeHeadingText(sec.Heading) == normalizedHeading && sec.Occurrence == occurrence {
				sectionIdx = i
				break
			}
		}
		if sectionIdx < 0 {
			return fmt.Errorf("%w: section %q (occurrence %d)", ErrNotFound, heading, occurrence)
		}
		heading = sections[sectionIdx].Heading
		occurrence = sections[sectionIdx].Occurrence

		baseRev := opts.BaseRev
		if baseRev <= 0 {
			baseRev = manifest.Revision
		}
		noteID := fmt.Sprintf("n%d", ledger.NextNoteSeq)
		escapedText := noteCommentCloserRe.ReplaceAllStringFunc(text, func(closer string) string {
			return "--\\" + closer[2:]
		})
		comment := ""
		if node != "" {
			comment = fmt.Sprintf(`<!-- note node="%s" id="%s" rev="%d": %s -->`, sanitizeNoteAttribute(node), noteID, baseRev, escapedText)
		} else {
			comment = fmt.Sprintf(`<!-- note id="%s" rev="%d": %s -->`, noteID, baseRev, escapedText)
		}
		// Persist manifest first when initializing a new bundle so a failure to
		// save manifest can never strand an orphan note in docPath or ledger.json.
		if !manifestExisted {
			manifest.SourceDigest = SHA256Hex(docBytes)
			if err := SaveManifest(docPath, manifest); err != nil {
				return err
			}
		}

		updated := insertNoteComment(raw, sections, sectionIdx, comment)
		if err := WriteFileAtomic(docPath, []byte(updated), fileMode); err != nil {
			if !manifestExisted {
				_ = os.Remove(ManifestPath(docPath))
			}
			return err
		}

		now := opts.Now
		if now.IsZero() {
			now = time.Now()
		}
		entry := LedgerEntry{
			NoteID:            noteID,
			MsgID:             opts.MsgID,
			Node:              node,
			SectionHeading:    heading,
			SectionOccurrence: occurrence,
			BaseRev:           baseRev,
			Text:              text,
			Status:            NoteStatusOpen,
			CreatedAt:         now.UTC().Format(time.RFC3339),
		}
		ledger.Notes = append(ledger.Notes, entry)
		ledger.NextNoteSeq++
		if err := SaveLedger(docPath, ledger); err != nil {
			// Keep the document, manifest, and ledger from diverging if the
			// ledger write fails.
			_ = WriteFileAtomic(docPath, docBytes, fileMode)
			if !manifestExisted {
				_ = os.Remove(ManifestPath(docPath))
			}
			return err
		}
		out = addNoteResultFromEntry(entry)
		return nil
	})
	return out, err
}

func addNoteResultFromEntry(entry LedgerEntry) AddNoteResult {
	return AddNoteResult{
		NoteID:            entry.NoteID,
		Node:              entry.Node,
		SectionHeading:    entry.SectionHeading,
		SectionOccurrence: entry.SectionOccurrence,
		BaseRev:           entry.BaseRev,
		Text:              entry.Text,
	}
}

func normalizeNoteLine(text string) string {
	text = strings.ReplaceAll(text, "\r\n", " ")
	text = strings.NewReplacer("\r", " ", "\n", " ").Replace(text)
	return strings.TrimSpace(text)
}

func sanitizeNoteAttribute(value string) string {
	value = normalizeNoteLine(value)
	return strings.ReplaceAll(value, `"`, "&quot;")
}

func noteTargetForNode(docPath, node, preferredSourceID string) (heading string, occurrence int, err error) {
	raw, err := os.ReadFile(ViewPath(docPath))
	if err != nil {
		return "", 0, fmt.Errorf("resolve node %q: read view: %w", node, err)
	}
	if len(raw) > MaxViewBytes {
		return "", 0, fmt.Errorf("resolve node %q: view exceeds %d bytes (%d bytes)", node, MaxViewBytes, len(raw))
	}
	var env struct {
		Sources map[string]struct {
			Heading    string `json:"heading"`
			Occurrence int    `json:"occurrence"`
		} `json:"sources"`
		A2UI []struct {
			CreateSurface *struct {
				Components []string `json:"components"`
			} `json:"createSurface"`
			UpdateComponents *struct {
				Components []string `json:"components"`
			} `json:"updateComponents"`
		} `json:"a2ui"`
	}
	if err := json.Unmarshal(raw, &env); err != nil {
		return "", 0, fmt.Errorf("resolve node %q: parse view: %w", node, err)
	}
	joined := ""
	for _, msg := range env.A2UI {
		if msg.CreateSurface != nil {
			joined = openuilang.Overlay(joined, strings.Join(msg.CreateSurface.Components, "\n"))
		} else if msg.UpdateComponents != nil {
			joined = openuilang.Overlay(joined, strings.Join(msg.UpdateComponents.Components, "\n"))
		}
	}

	var sourceIDs []string
	for _, call := range openuilang.FirstArgumentStrings(joined, "Source") {
		if call.Statement != node {
			continue
		}
		if !call.Literal || len(call.Strings) == 0 {
			return "", 0, fmt.Errorf("node %q must have at least one literal Source ID", node)
		}
		if len(sourceIDs) > 0 {
			return "", 0, fmt.Errorf("node %q has multiple Source calls", node)
		}
		for _, raw := range call.Strings {
			if id := strings.TrimSpace(raw); id != "" {
				sourceIDs = append(sourceIDs, id)
			}
		}
	}
	if len(sourceIDs) == 0 {
		return "", 0, fmt.Errorf("%w: node %q is not a Source statement in current view", ErrNotFound, node)
	}
	sourceID, err := selectSourceID(node, sourceIDs, strings.TrimSpace(preferredSourceID))
	if err != nil {
		return "", 0, err
	}
	source, ok := env.Sources[sourceID]
	if !ok {
		return "", 0, fmt.Errorf("node %q references unmapped source %q", node, sourceID)
	}
	occurrence = source.Occurrence
	if occurrence < 1 {
		occurrence = 1
	}
	if strings.TrimSpace(source.Heading) == "" {
		return "", 0, fmt.Errorf("node %q source %q has an empty heading", node, sourceID)
	}
	return source.Heading, occurrence, nil
}

// selectSourceID resolves which cited source a note belongs to. A single-source
// Source(["s1"], ...) statement keeps working unchanged; a multi-section
// statement requires an explicit, matching source ID.
func selectSourceID(node string, sourceIDs []string, preferred string) (string, error) {
	valid := strings.Join(sourceIDs, ", ")
	if preferred != "" {
		for _, id := range sourceIDs {
			if id == preferred {
				return id, nil
			}
		}
		return "", fmt.Errorf("%w: node %q does not reference source %q (valid: %s)", ErrNotFound, node, preferred, valid)
	}
	if len(sourceIDs) == 1 {
		return sourceIDs[0], nil
	}
	return "", fmt.Errorf("node %q references multiple sources (%s); pass --source with one of: %s", node, valid, valid)
}

func insertNoteComment(raw string, sections []markdown.Section, sectionIdx int, comment string) string {
	end := markdown.OwnBodyEndByte(raw, sections, sectionIdx)
	prefix, suffix := raw[:end], raw[end:]

	// The Markdown parser cuts a note from the end of the preceding block's
	// final line. Reproduce the exact original gap after the comment so
	// StripNotes(inserted) is byte-identical to the input, including CRLF,
	// trailing spaces, and blank lines at EOF.
	contentEnd := len(strings.TrimRight(prefix, " \t\r\n"))
	gapStart := contentEnd
	for gapStart < len(prefix) && (prefix[gapStart] == ' ' || prefix[gapStart] == '\t') {
		gapStart++
	}
	originalGap := prefix[gapStart:]

	lineEnding := "\n"
	if strings.Contains(strings.TrimRight(raw, " \t\r\n"), "\r\n") {
		lineEnding = "\r\n"
	}
	lineBreaks := strings.Count(originalGap, "\n")
	extraBefore := ""
	if lineBreaks < 2 {
		extraBefore = strings.Repeat(lineEnding, 2-lineBreaks)
	}
	return prefix + extraBefore + comment + originalGap + suffix
}
