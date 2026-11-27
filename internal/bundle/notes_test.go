package bundle

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"deepread/internal/markdown"
)

func TestAddNoteKeepsH2AttributionAndRoundTripsCRLF(t *testing.T) {
	dir := t.TempDir()
	doc := filepath.Join(dir, "article.md")
	before := strings.Join([]string{
		"# Report",
		"",
		"## Alpha",
		"",
		"Emoji 🎯 and 中文 stay untouched.",
		"",
		"### Child",
		"",
		"Child prose.",
		"",
		"## Beta",
		"",
		"Beta prose.",
		"",
	}, "\r\n")
	if err := os.WriteFile(doc, []byte(before), 0o644); err != nil {
		t.Fatal(err)
	}
	manifest, _, err := LoadManifest(doc, []byte(before))
	if err != nil {
		t.Fatal(err)
	}
	manifest.Revision = 2
	if err := SaveManifest(doc, manifest); err != nil {
		t.Fatal(err)
	}
	beforeSections := markdown.ExtractSections(before)

	res, err := AddNote(doc, AddNoteOptions{
		Heading: "Alpha",
		Text:    "  修正 --> 数值 🎯\r\n第二行  ",
		MsgID:   "msg-crlf",
		Now:     time.Date(2026, 11, 26, 9, 30, 0, 0, time.UTC),
	})
	if err != nil {
		t.Fatalf("AddNote failed: %v", err)
	}
	if res.NoteID != "n1" || res.Duplicate || res.SectionHeading != "Alpha" || res.SectionOccurrence != 1 || res.BaseRev != 2 {
		t.Fatalf("unexpected AddNoteResult: %#v", res)
	}
	if res.Text != "修正 --> 数值 🎯 第二行" {
		t.Fatalf("note text was not normalized to one trimmed line: %q", res.Text)
	}

	afterBytes, err := os.ReadFile(doc)
	if err != nil {
		t.Fatal(err)
	}
	after := string(afterBytes)
	if !strings.Contains(after, "\r\n<!-- note id=\"n1\" rev=\"2\": 修正 --\\> 数值 🎯 第二行 -->\r\n") {
		t.Fatalf("missing CRLF inline note with escaped closer:\n%q", after)
	}
	if strings.Index(after, "<!-- note") > strings.Index(after, "### Child") {
		t.Fatalf("note was inserted after the H3 heading: %q", after)
	}
	if got := markdown.StripNotes(after); got != before {
		t.Fatalf("StripNotes did not restore original bytes:\ngot:  %q\nwant: %q", got, before)
	}
	notes := markdown.ExtractNotes(after)
	if len(notes) != 1 || notes[0].SectionHeading != "Alpha" || notes[0].SectionOccurrence != 1 {
		t.Fatalf("note slipped out of H2 own body: %#v", notes)
	}
	if notes[0].Text != "修正 --> 数值 🎯 第二行" {
		t.Fatalf("escaped closer did not round-trip: %q", notes[0].Text)
	}
	afterSections := markdown.ExtractSections(after)
	if len(afterSections) != len(beforeSections) {
		t.Fatalf("section count changed: %d -> %d", len(beforeSections), len(afterSections))
	}
	for i := range beforeSections {
		if afterSections[i].Hash != beforeSections[i].Hash {
			t.Errorf("section %q hash changed: %s -> %s", beforeSections[i].Heading, beforeSections[i].Hash, afterSections[i].Hash)
		}
	}

	ledger, err := LoadLedger(doc)
	if err != nil {
		t.Fatal(err)
	}
	if ledger.NextNoteSeq != 2 || len(ledger.Notes) != 1 || ledger.Notes[0].Status != NoteStatusOpen {
		t.Fatalf("unexpected ledger: %#v", ledger)
	}
	if ledger.Notes[0].CreatedAt != "2026-11-26T09:30:00Z" {
		t.Fatalf("unexpected createdAt: %q", ledger.Notes[0].CreatedAt)
	}
}

func TestAddNoteDuplicateMsgIDDoesNotMutateDocumentOrLedger(t *testing.T) {
	dir := t.TempDir()
	doc := filepath.Join(dir, "article.md")
	before := "## Alpha\n\nOriginal prose.\n\n### Child\n\nChild prose.\n"
	if err := os.WriteFile(doc, []byte(before), 0o644); err != nil {
		t.Fatal(err)
	}
	first, err := AddNote(doc, AddNoteOptions{Heading: "Alpha", Text: "Check this", MsgID: "chat-1"})
	if err != nil {
		t.Fatal(err)
	}
	docBeforeDuplicate, _ := os.ReadFile(doc)
	ledgerBeforeDuplicate, _ := os.ReadFile(LedgerPath(doc))

	second, err := AddNote(doc, AddNoteOptions{Heading: "Alpha", Text: "A different redelivery", MsgID: "chat-1"})
	if err != nil {
		t.Fatal(err)
	}
	if !second.Duplicate || second.NoteID != first.NoteID || second.Text != first.Text {
		t.Fatalf("duplicate did not return original ledger entry: first=%#v second=%#v", first, second)
	}
	docAfterDuplicate, _ := os.ReadFile(doc)
	ledgerAfterDuplicate, _ := os.ReadFile(LedgerPath(doc))
	if string(docAfterDuplicate) != string(docBeforeDuplicate) {
		t.Fatalf("duplicate MsgID appended another note")
	}
	if string(ledgerAfterDuplicate) != string(ledgerBeforeDuplicate) {
		t.Fatalf("duplicate MsgID mutated ledger")
	}
	if got := strings.Count(string(docAfterDuplicate), "<!-- note"); got != 1 {
		t.Fatalf("got %d inline notes, want 1", got)
	}
}

func TestAddNoteRejectsStaleBaseRevisionWithoutMutation(t *testing.T) {
	dir := t.TempDir()
	doc := filepath.Join(dir, "article.md")
	before := "## Alpha\n\nOriginal prose.\n"
	if err := os.WriteFile(doc, []byte(before), 0o644); err != nil {
		t.Fatal(err)
	}
	manifest, _, err := LoadManifest(doc, []byte(before))
	if err != nil {
		t.Fatal(err)
	}
	manifest.Revision = 3
	if err := SaveManifest(doc, manifest); err != nil {
		t.Fatal(err)
	}

	_, err = AddNote(doc, AddNoteOptions{Heading: "Alpha", Text: "Stale edit", BaseRev: 2})
	if !errors.Is(err, ErrStaleRevision) {
		t.Fatalf("got %v, want ErrStaleRevision", err)
	}
	after, _ := os.ReadFile(doc)
	if string(after) != before {
		t.Fatalf("stale revision mutated document")
	}
	if _, statErr := os.Stat(LedgerPath(doc)); !os.IsNotExist(statErr) {
		t.Fatalf("stale revision created or mutated ledger: %v", statErr)
	}
}

func TestAddNoteResolvesNodeThroughCurrentView(t *testing.T) {
	dir := t.TempDir()
	doc := filepath.Join(dir, "article.md")
	raw := "## Alpha\n\nOriginal prose.\n"
	if err := os.WriteFile(doc, []byte(raw), 0o644); err != nil {
		t.Fatal(err)
	}
	viewJSON := `{
  "version": 3,
  "language": "openui-lang/1.0",
  "generatedAt": "2026-11-26T00:00:00Z",
  "sources": {"s1": {"heading": "Alpha", "occurrence": 1}},
  "a2ui": [{
    "version": "1.0",
    "createSurface": {
      "surfaceId": "view",
      "catalogId": "markgogo.dev:genui/v3",
      "components": ["root = Col([alpha])", "alpha = Source([\"s1\"], [Quote(\"A\", \"Alpha\")])"]
    }
  }]
}
`
	if err := os.WriteFile(ViewPath(doc), []byte(viewJSON), 0o644); err != nil {
		t.Fatal(err)
	}
	res, err := AddNote(doc, AddNoteOptions{Node: "alpha", Text: "Node note"})
	if err != nil {
		t.Fatalf("AddNote by node failed: %v", err)
	}
	if res.Node != "alpha" || res.SectionHeading != "Alpha" || res.SectionOccurrence != 1 {
		t.Fatalf("node did not resolve through sources: %#v", res)
	}
	after, _ := os.ReadFile(doc)
	if !strings.Contains(string(after), `<!-- note node="alpha" id="n1" rev="0": Node note -->`) {
		t.Fatalf("missing node attribute in inline note: %q", after)
	}
}

func writeMultiSourceView(t *testing.T, doc string) {
	t.Helper()
	viewJSON := `{
  "version": 3,
  "language": "openui-lang/1.0",
  "generatedAt": "2026-11-26T00:00:00Z",
  "sources": {
    "s1": {"heading": "Alpha", "occurrence": 1},
    "s2": {"heading": "Beta", "occurrence": 1}
  },
  "a2ui": [{
    "version": "1.0",
    "createSurface": {
      "surfaceId": "view",
      "catalogId": "markgogo.dev:genui/v3",
      "components": ["root = Col([both])", "both = Source([\"s1\", \"s2\"], [Quote(\"A\", \"Alpha\"), Quote(\"B\", \"Beta\")])"]
    }
  }]
}
`
	if err := os.WriteFile(ViewPath(doc), []byte(viewJSON), 0o644); err != nil {
		t.Fatal(err)
	}
}

func TestAddNoteMultiSourceNodeRequiresSourceID(t *testing.T) {
	dir := t.TempDir()
	doc := filepath.Join(dir, "article.md")
	raw := "## Alpha\n\nAlpha prose.\n\n## Beta\n\nBeta prose.\n"
	if err := os.WriteFile(doc, []byte(raw), 0o644); err != nil {
		t.Fatal(err)
	}
	writeMultiSourceView(t, doc)

	_, err := AddNote(doc, AddNoteOptions{Node: "both", Text: "Missing source"})
	if err == nil {
		t.Fatal("multi-source node without SourceID was accepted")
	}
	for _, want := range []string{"--source", "s1", "s2", "both"} {
		if !strings.Contains(err.Error(), want) {
			t.Fatalf("error %q does not mention %q", err, want)
		}
	}
	after, _ := os.ReadFile(doc)
	if string(after) != raw {
		t.Fatalf("ambiguous multi-source note mutated the document")
	}

	_, err = AddNote(doc, AddNoteOptions{Node: "both", SourceID: "s3", Text: "Unknown source"})
	if err == nil || !strings.Contains(err.Error(), "s2") {
		t.Fatalf("unknown SourceID error = %v, want a message listing valid ids", err)
	}

	res, err := AddNote(doc, AddNoteOptions{Node: "both", SourceID: "s2", Text: "Beta note", MsgID: "multi-1"})
	if err != nil {
		t.Fatalf("AddNote with SourceID failed: %v", err)
	}
	if res.Node != "both" || res.SectionHeading != "Beta" || res.SectionOccurrence != 1 {
		t.Fatalf("SourceID did not select the Beta section: %#v", res)
	}
	updated, _ := os.ReadFile(doc)
	if strings.Index(string(updated), "Beta note") < strings.Index(string(updated), "## Beta") {
		t.Fatalf("note inserted before the Beta heading: %q", updated)
	}
}

func TestAddNoteSingleSourceAcceptsMatchingSourceID(t *testing.T) {
	dir := t.TempDir()
	doc := filepath.Join(dir, "article.md")
	raw := "## Alpha\n\nAlpha prose.\n\n## Beta\n\nBeta prose.\n"
	if err := os.WriteFile(doc, []byte(raw), 0o644); err != nil {
		t.Fatal(err)
	}
	writeMultiSourceView(t, doc)

	res, err := AddNote(doc, AddNoteOptions{Node: "both", SourceID: "s1", Text: "Alpha note"})
	if err != nil {
		t.Fatalf("AddNote failed: %v", err)
	}
	if res.SectionHeading != "Alpha" {
		t.Fatalf("unexpected section: %#v", res)
	}

	viewJSON := `{
  "version": 3,
  "sources": {"s1": {"heading": "Alpha", "occurrence": 1}},
  "a2ui": [{"createSurface": {"surfaceId": "view", "catalogId": "markgogo.dev:genui/v3",
    "components": ["root = Col([single])", "single = Source([\"s1\"], [Quote(\"A\", \"Alpha\")])"]}}]
}
`
	if err := os.WriteFile(ViewPath(doc), []byte(viewJSON), 0o644); err != nil {
		t.Fatal(err)
	}
	// A single-source statement keeps working exactly as before when --source is omitted.
	res, err = AddNote(doc, AddNoteOptions{Node: "single", Text: "Implicit source"})
	if err != nil {
		t.Fatalf("single-source node without SourceID failed: %v", err)
	}
	if res.SectionHeading != "Alpha" {
		t.Fatalf("unexpected section: %#v", res)
	}
	// A mismatched explicit source is a clear error, not a silent mis-target.
	if _, err := AddNote(doc, AddNoteOptions{Node: "single", SourceID: "s2", Text: "Wrong source"}); err == nil {
		t.Fatal("mismatched SourceID accepted for a single-source node")
	}
}
