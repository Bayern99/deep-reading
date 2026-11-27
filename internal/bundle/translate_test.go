package bundle

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"deepread/internal/markdown"
)

const blockFixture = `# Grid Report

First paragraph with exact numbers: $42.5B in 2024.

Second paragraph explains peak demand.

First paragraph with exact numbers: $42.5B in 2024.

## Costs

> Quotes live here.

- Item one
- Item two

| Region | Spend |
| --- | --- |
| North | $1.2B |

![Grid map](assets/map.png)

Closing paragraph.
`

func mustWriteDoc(t *testing.T, raw string) string {
	t.Helper()
	doc := filepath.Join(t.TempDir(), "article.md")
	if err := os.WriteFile(doc, []byte(raw), 0o644); err != nil {
		t.Fatal(err)
	}
	return doc
}

func TestExtractBlocksKindsSectionsAndDuplicateIDs(t *testing.T) {
	manifest, _, err := LoadManifest("article.md", []byte(blockFixture))
	if err != nil {
		t.Fatal(err)
	}
	blocks := ExtractBlocks([]byte(blockFixture), manifest)
	if len(blocks) == 0 {
		t.Fatalf("no blocks extracted")
	}

	type want struct {
		kind    string
		text    string
		heading string
		level   int
	}
	wants := []want{
		{BlockKindHeading, "Grid Report", "Grid Report", 1},
		{BlockKindParagraph, "First paragraph with exact numbers: $42.5B in 2024.", "Grid Report", 0},
		{BlockKindParagraph, "Second paragraph explains peak demand.", "Grid Report", 0},
		{BlockKindParagraph, "First paragraph with exact numbers: $42.5B in 2024.", "Grid Report", 0},
		{BlockKindHeading, "Costs", "Costs", 2},
		{BlockKindQuote, "Quotes live here.", "Costs", 0},
		{BlockKindListItem, "Item one", "Costs", 0},
		{BlockKindListItem, "Item two", "Costs", 0},
		{BlockKindTableCell, "Region", "Costs", 0},
		{BlockKindTableCell, "Spend", "Costs", 0},
		{BlockKindTableCell, "North", "Costs", 0},
		{BlockKindTableCell, "$1.2B", "Costs", 0},
		{BlockKindImageAlt, "Grid map", "Costs", 0},
		{BlockKindParagraph, "Closing paragraph.", "Costs", 0},
	}
	if len(blocks) != len(wants) {
		t.Fatalf("got %d blocks, want %d: %#v", len(blocks), len(wants), blocks)
	}
	for i, want := range wants {
		got := blocks[i]
		if got.Kind != want.kind || got.Text != want.text || got.SectionHeading != want.heading || got.HeadingLevel != want.level {
			t.Errorf("block %d = %#v, want kind=%q text=%q heading=%q level=%d", i, got, want.kind, want.text, want.heading, want.level)
		}
		if got.SourceHash != BlockSourceHash(got.Text) || len(got.SourceHash) != 8 {
			t.Errorf("block %d has unexpected SourceHash %q for text %q", i, got.SourceHash, got.Text)
		}
		if want.heading != "" && got.SectionOccurrence != 1 {
			t.Errorf("block %d occurrence = %d, want 1", i, got.SectionOccurrence)
		}
		if got.EndByte <= got.StartByte {
			t.Errorf("block %d has empty byte span %d..%d", i, got.StartByte, got.EndByte)
		}
	}

	// Identical normalized prose is content addressed: the first occurrence keeps
	// the bare ID, later ones get a deterministic -N suffix.
	first, second := blocks[1], blocks[3]
	if !strings.HasPrefix(first.ID, "b") || len(first.ID) != 9 {
		t.Fatalf("unexpected first duplicate id %q", first.ID)
	}
	if second.ID != first.ID+"-2" {
		t.Fatalf("duplicate paragraph id = %q, want %q", second.ID, first.ID+"-2")
	}

	// Extraction is pure and deterministic.
	again := ExtractBlocks([]byte(blockFixture), manifest)
	if len(again) != len(blocks) {
		t.Fatalf("second extraction returned %d blocks", len(again))
	}
	for i := range blocks {
		if again[i] != blocks[i] {
			t.Fatalf("extraction is not deterministic at block %d: %#v vs %#v", i, blocks[i], again[i])
		}
	}
}

func TestBlockIDsStableAcrossPrepareAndNoteAdd(t *testing.T) {
	doc := mustWriteDoc(t, blockFixture)
	docBytes, err := os.ReadFile(doc)
	if err != nil {
		t.Fatal(err)
	}
	manifest, _, err := LoadManifest(doc, docBytes)
	if err != nil {
		t.Fatal(err)
	}
	base := ExtractBlocks(docBytes, manifest)

	if err := SetReaderConfig(doc, ReaderConfig{SourceLang: "en", TargetLang: "zh-cn", Mode: ReadModeBilingual}); err != nil {
		t.Fatalf("SetReaderConfig: %v", err)
	}
	entries := make([]TranslationEntry, 0, len(base))
	for i, b := range base {
		entries = append(entries, TranslationEntry{ID: b.ID, SourceHash: b.SourceHash, Text: "译文 " + string(rune('A'+i))})
	}
	status, err := ApplyTranslations(doc, "zh-CN", entries)
	if err != nil {
		t.Fatalf("ApplyTranslations: %v", err)
	}
	if status.CoveragePct != 100 || status.TranslatedBlocks != len(base) {
		t.Fatalf("unexpected full coverage status: %#v", status)
	}

	// Insert a synthetic H2 between the second and third paragraph, then add an
	// inline reader note. Neither may shift a block ID or mark a translation stale.
	if _, err := Prepare(doc, []BreakSpec{{BeforeLine: 7, Title: "Demand Shift"}}); err != nil {
		t.Fatalf("Prepare: %v", err)
	}
	if _, err := AddNote(doc, AddNoteOptions{Heading: "Costs", Text: "核对数字"}); err != nil {
		t.Fatalf("AddNote: %v", err)
	}

	afterBytes, err := os.ReadFile(doc)
	if err != nil {
		t.Fatal(err)
	}
	afterManifest, _, err := LoadManifest(doc, afterBytes)
	if err != nil {
		t.Fatal(err)
	}
	if len(afterManifest.SyntheticSections) != 1 {
		t.Fatalf("expected one synthetic section, got %#v", afterManifest.SyntheticSections)
	}
	after := ExtractBlocks(afterBytes, afterManifest)
	if len(after) != len(base) {
		t.Fatalf("block count changed after prepare/note: %d -> %d", len(base), len(after))
	}
	for i := range base {
		if after[i].ID != base[i].ID || after[i].SourceHash != base[i].SourceHash || after[i].Text != base[i].Text {
			t.Fatalf("block %d drifted after prepare/note: %#v -> %#v", i, base[i], after[i])
		}
	}
	if !afterManifest.IsSynthetic("§1 · Demand Shift", 1) {
		t.Fatalf("synthetic marker missing from manifest: %#v", afterManifest.SyntheticSections)
	}
	for _, b := range after {
		if b.Kind == BlockKindHeading && strings.Contains(b.Text, "Demand Shift") {
			t.Fatalf("synthetic heading leaked into translatable blocks: %#v", b)
		}
	}

	layer, liveStatus, err := LoadTranslationUnlocked(doc, "zh-CN", afterBytes, afterManifest)
	if err != nil {
		t.Fatalf("LoadTranslationUnlocked: %v", err)
	}
	if layer == nil {
		t.Fatal("translation layer disappeared")
	}
	if liveStatus.StaleBlocks != 0 || len(liveStatus.StaleIDs) != 0 {
		t.Fatalf("translations falsely marked stale: %#v", liveStatus)
	}
	if liveStatus.CoveragePct != 100 || len(liveStatus.MissingIDs) != 0 {
		t.Fatalf("coverage drifted after prepare/note: %#v", liveStatus)
	}
}

func TestApplyTranslationsRejectsCASMismatch(t *testing.T) {
	doc := mustWriteDoc(t, "## Alpha\n\nOriginal prose here.\n\nSecond paragraph is different.\n")
	docBytes, _ := os.ReadFile(doc)
	manifest, _, err := LoadManifest(doc, docBytes)
	if err != nil {
		t.Fatal(err)
	}
	blocks := ExtractBlocks(docBytes, manifest)
	if len(blocks) != 3 {
		t.Fatalf("expected 3 blocks, got %#v", blocks)
	}
	// The CAS guard catches a caller that pairs a live block id with a hash from
	// another revision. Content-addressed ids make a natural mismatch impossible,
	// so this is the only way a stale pair can reach the writer.
	_, err = ApplyTranslations(doc, "zh-CN", []TranslationEntry{
		{ID: blocks[1].ID, SourceHash: "deadbeef", Text: "译文"},
	})
	if !errors.Is(err, ErrConflict) {
		t.Fatalf("got %v, want ErrConflict", err)
	}
	if !strings.Contains(err.Error(), blocks[1].ID) {
		t.Fatalf("conflict error should name the block: %v", err)
	}
	// Nothing was persisted by the failed batch.
	if _, statErr := os.Stat(translationFilePath(doc, "zh-CN")); !os.IsNotExist(statErr) {
		t.Fatalf("failed batch persisted a translation file: %v", statErr)
	}
	// A matching hash is accepted.
	status, err := ApplyTranslations(doc, "zh-CN", []TranslationEntry{
		{ID: blocks[1].ID, SourceHash: blocks[1].SourceHash, Text: "译文一"},
	})
	if err != nil {
		t.Fatalf("ApplyTranslations: %v", err)
	}
	if status.TranslatedBlocks != 1 || status.CoveragePct != 33 {
		t.Fatalf("unexpected status: %#v", status)
	}
}

func TestApplyTranslationsRejectsUnknownAndInvalidText(t *testing.T) {
	doc := mustWriteDoc(t, "## Alpha\n\nOriginal prose here.\n")
	if _, err := ApplyTranslations(doc, "zh-CN", []TranslationEntry{{ID: "bdeadbeef", Text: "译文"}}); !errors.Is(err, ErrNotFound) {
		t.Fatalf("unknown block: got %v, want ErrNotFound", err)
	}

	docBytes, _ := os.ReadFile(doc)
	manifest, _, _ := LoadManifest(doc, docBytes)
	blocks := ExtractBlocks(docBytes, manifest)

	cases := []struct {
		name string
		text string
	}{
		{"empty", "   \n\t "},
		{"script", `<script>alert(1)</script>`},
		{"block image", "见下图\n\n![fig](assets/x.png)"},
	}
	for _, tc := range cases {
		if _, err := ApplyTranslations(doc, "zh-CN", []TranslationEntry{{ID: blocks[0].ID, Text: tc.text}}); err == nil {
			t.Fatalf("%s translation was accepted", tc.name)
		}
	}
	// Inline markdown in translated prose is allowed.
	status, err := ApplyTranslations(doc, "zh-CN", []TranslationEntry{
		{ID: blocks[0].ID, Text: "**强调** 与 `代码` 与 [链接](https://example.com)"},
	})
	if err != nil {
		t.Fatalf("inline markdown rejected: %v", err)
	}
	if status.TranslatedBlocks != 1 {
		t.Fatalf("unexpected status: %#v", status)
	}
	// Inline images are only rejected at block level, never inside a paragraph.
	if _, err := ApplyTranslations(doc, "zh-CN", []TranslationEntry{
		{ID: blocks[1].ID, Text: "行内 ![图](assets/x.png) 图片"},
	}); err != nil {
		t.Fatalf("inline image markdown rejected: %v", err)
	}
}

func TestTranslationLanguageValidationAndCanonicalization(t *testing.T) {
	doc := mustWriteDoc(t, "## Alpha\n\nOriginal prose here.\n")
	for _, bad := range []string{"../evil", "zh/CN", "", "x", "en-a"} {
		if _, err := ApplyTranslations(doc, bad, nil); !errors.Is(err, ErrInvalidLang) {
			t.Fatalf("lang %q: got %v, want ErrInvalidLang", bad, err)
		}
		if _, err := LoadDocSnapshot(doc, bad); bad != "" && !errors.Is(err, ErrInvalidLang) {
			t.Fatalf("snapshot lang %q: got %v, want ErrInvalidLang", bad, err)
		}
	}

	docBytes, _ := os.ReadFile(doc)
	manifest, _, _ := LoadManifest(doc, docBytes)
	blocks := ExtractBlocks(docBytes, manifest)
	status, err := ApplyTranslations(doc, "zh-cn", []TranslationEntry{{ID: blocks[0].ID, Text: "译文"}})
	if err != nil {
		t.Fatalf("ApplyTranslations: %v", err)
	}
	if status.Lang != "zh-CN" {
		t.Fatalf("status.Lang = %q, want zh-CN", status.Lang)
	}
	if _, err := os.Stat(filepath.Join(TranslationsDir(doc), "zh-CN.json")); err != nil {
		t.Fatalf("expected canonical translation file: %v", err)
	}
	// The canonical name is also what TranslationPath resolves to, so lookups
	// with either casing on a case-insensitive filesystem stay consistent.
	if path, err := TranslationPath(doc, "zh-cn"); err != nil || path != filepath.Join(TranslationsDir(doc), "zh-CN.json") {
		t.Fatalf("TranslationPath did not canonicalize: %q %v", path, err)
	}
}

func TestEvaluateTranslationStatusNeverInflatesCoverage(t *testing.T) {
	blocks := make([]Block, 0, 1000)
	layer := &TranslationLayer{Entries: map[string]TranslationEntry{}}
	for i := 0; i < 1000; i++ {
		id := "b" + BlockSourceHash(strings.Repeat("x", i+1))
		blocks = append(blocks, Block{ID: id, SourceHash: "h" + id})
		if i < 999 {
			layer.Entries[id] = TranslationEntry{ID: id, SourceHash: "h" + id, Text: "译文"}
		}
	}
	status := EvaluateTranslationStatus(blocks, layer, "zh-CN")
	if status.TotalBlocks != 1000 || status.TranslatedBlocks != 999 || status.StaleBlocks != 0 {
		t.Fatalf("unexpected counts: %#v", status)
	}
	if status.CoveragePct != 99 {
		t.Fatalf("coverage = %d, want 99 (never 100 while a block is missing)", status.CoveragePct)
	}
	if len(status.MissingIDs) != 1 {
		t.Fatalf("unexpected missing ids: %#v", status.MissingIDs)
	}

	// Full coverage is exactly 100 only when every block is fresh.
	layer.Entries[blocks[999].ID] = TranslationEntry{ID: blocks[999].ID, SourceHash: "h" + blocks[999].ID, Text: "译文"}
	status = EvaluateTranslationStatus(blocks, layer, "zh-CN")
	if status.CoveragePct != 100 || status.TranslatedBlocks != 1000 {
		t.Fatalf("unexpected full status: %#v", status)
	}

	// A stale entry is neither translated nor missing.
	layer.Entries[blocks[0].ID] = TranslationEntry{ID: blocks[0].ID, SourceHash: "stale", Text: "旧译文"}
	status = EvaluateTranslationStatus(blocks, layer, "zh-CN")
	if status.TranslatedBlocks != 999 || status.StaleBlocks != 1 || status.CoveragePct != 99 {
		t.Fatalf("unexpected stale status: %#v", status)
	}
	if len(status.StaleIDs) != 1 || status.StaleIDs[0] != blocks[0].ID {
		t.Fatalf("unexpected stale ids: %#v", status.StaleIDs)
	}

	// No blocks at all means nothing is missing.
	empty := EvaluateTranslationStatus(nil, nil, "zh-CN")
	if empty.TotalBlocks != 0 || empty.CoveragePct != 100 || len(empty.MissingIDs) != 0 {
		t.Fatalf("unexpected empty status: %#v", empty)
	}
}

func TestLoadDocSnapshotIsConsistentUnderOneLock(t *testing.T) {
	doc := mustWriteDoc(t, "## Alpha\n\nOriginal prose here.\n")
	if err := SetReaderConfig(doc, ReaderConfig{TargetLang: "zh-cn", Mode: ReadModeTranslated}); err != nil {
		t.Fatal(err)
	}
	docBytes, _ := os.ReadFile(doc)
	manifest, _, _ := LoadManifest(doc, docBytes)
	if manifest.Reader == nil || manifest.Reader.TargetLang != "zh-CN" {
		t.Fatalf("manifest reader not canonical: %#v", manifest.Reader)
	}
	blocks := ExtractBlocks(docBytes, manifest)
	if _, err := ApplyTranslations(doc, "zh-CN", []TranslationEntry{{ID: blocks[1].ID, Text: "译文"}}); err != nil {
		t.Fatal(err)
	}

	snap, err := LoadDocSnapshot(doc, "")
	if err != nil {
		t.Fatalf("LoadDocSnapshot: %v", err)
	}
	if string(snap.DocBytes) != string(docBytes) || snap.ViewExists || snap.ViewBytes != nil {
		t.Fatalf("unexpected snapshot: %#v", snap)
	}
	if snap.Manifest.Reader == nil || snap.Manifest.Reader.Mode != ReadModeTranslated {
		t.Fatalf("snapshot did not carry reader config: %#v", snap.Manifest.Reader)
	}
	if snap.Translation == nil || snap.TranslationStatus == nil {
		t.Fatal("snapshot did not load the default target language translation")
	}
	if snap.TranslationStatus.TranslatedBlocks != 1 || snap.TranslationStatus.CoveragePct != 50 {
		t.Fatalf("unexpected translation status: %#v", snap.TranslationStatus)
	}
	if len(snap.Citations) != 0 {
		t.Fatalf("unexpected citations: %#v", snap.Citations)
	}

	if err := SaveCitations(doc, CitationMap{"alpha": {"s1": {blocks[1].ID}}}); err != nil {
		t.Fatal(err)
	}
	viewJSON := `{"version": 3}`
	if err := os.WriteFile(ViewPath(doc), []byte(viewJSON), 0o644); err != nil {
		t.Fatal(err)
	}
	snap, err = LoadDocSnapshot(doc, "zh-CN")
	if err != nil {
		t.Fatalf("LoadDocSnapshot: %v", err)
	}
	if !snap.ViewExists || string(snap.ViewBytes) != viewJSON {
		t.Fatalf("view not loaded: %#v", snap)
	}
	if len(snap.Citations) != 1 || snap.Citations["alpha"]["s1"][0] != blocks[1].ID {
		t.Fatalf("citations not loaded: %#v", snap.Citations)
	}
}

func TestSetReaderConfigValidatesAndClears(t *testing.T) {
	doc := mustWriteDoc(t, "## Alpha\n\nProse.\n")
	if err := SetReaderConfig(doc, ReaderConfig{TargetLang: "../evil"}); !errors.Is(err, ErrInvalidLang) {
		t.Fatalf("got %v, want ErrInvalidLang", err)
	}
	if err := SetReaderConfig(doc, ReaderConfig{Mode: "half-way"}); err == nil {
		t.Fatal("invalid read mode accepted")
	}
	if err := SetReaderConfig(doc, ReaderConfig{SourceLang: "en-us", TargetLang: "zh-hans-cn", Mode: ReadModeBilingual}); err != nil {
		t.Fatalf("SetReaderConfig: %v", err)
	}
	docBytes, _ := os.ReadFile(doc)
	manifest, _, _ := LoadManifest(doc, docBytes)
	if manifest.Reader == nil || manifest.Reader.SourceLang != "en-US" || manifest.Reader.TargetLang != "zh-Hans-CN" {
		t.Fatalf("reader not canonicalized: %#v", manifest.Reader)
	}
	if err := SetReaderConfig(doc, ReaderConfig{}); err != nil {
		t.Fatalf("clearing reader config failed: %v", err)
	}
	docBytes, _ = os.ReadFile(doc)
	manifest, _, _ = LoadManifest(doc, docBytes)
	if manifest.Reader != nil {
		t.Fatalf("reader config not cleared: %#v", manifest.Reader)
	}
}

func TestInspectReportsProfileReaderTranslationAndMultiSourceModules(t *testing.T) {
	dir := t.TempDir()
	doc := filepath.Join(dir, "article.md")
	raw := "## Alpha\n\nAlpha prose.\n\n## Beta\n\nBeta prose.\n"
	if err := os.WriteFile(doc, []byte(raw), 0o644); err != nil {
		t.Fatal(err)
	}
	docBytes, _ := os.ReadFile(doc)
	manifest, _, _ := LoadManifest(doc, docBytes)
	manifest.Profile = ProfileMargin
	if err := SaveManifest(doc, manifest); err != nil {
		t.Fatal(err)
	}
	if err := SetReaderConfig(doc, ReaderConfig{SourceLang: "en", TargetLang: "zh-cn", Mode: ReadModeBilingual}); err != nil {
		t.Fatal(err)
	}
	viewJSON := `{
  "version": 3,
  "language": "openui-lang/1.0",
  "sources": {"s1": {"heading": "Alpha", "occurrence": 1}, "s2": {"heading": "Beta", "occurrence": 1}},
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

	docBytes, _ = os.ReadFile(doc)
	manifest, _, _ = LoadManifest(doc, docBytes)
	blocks := ExtractBlocks(docBytes, manifest)
	if _, err := ApplyTranslations(doc, "zh-cn", []TranslationEntry{{ID: blocks[0].ID, Text: "译文"}}); err != nil {
		t.Fatal(err)
	}

	rep, err := Inspect(doc, InspectOptions{})
	if err != nil {
		t.Fatalf("Inspect: %v", err)
	}
	if rep.Profile != ProfileMargin {
		t.Fatalf("profile = %q, want %q", rep.Profile, ProfileMargin)
	}
	if rep.Reader == nil || rep.Reader.TargetLang != "zh-CN" || rep.Reader.Mode != ReadModeBilingual {
		t.Fatalf("reader = %#v", rep.Reader)
	}
	if rep.Translation == nil || rep.Translation.Lang != "zh-CN" || rep.Translation.TotalBlocks != len(blocks) {
		t.Fatalf("translation status = %#v", rep.Translation)
	}
	if rep.Translation.TranslatedBlocks != 1 || rep.Translation.StaleBlocks != 0 {
		t.Fatalf("unexpected translation counts: %#v", rep.Translation)
	}
	if len(rep.Modules) != 1 {
		t.Fatalf("expected one grouped module, got %#v", rep.Modules)
	}
	mod := rep.Modules[0]
	if mod.SourceID != "s1" || mod.Heading != "Alpha" || mod.Occurrence != 1 {
		t.Fatalf("backward-compatible module fields lost: %#v", mod)
	}
	if len(mod.Sections) != 2 || mod.Sections[0].SourceID != "s1" || mod.Sections[1].SourceID != "s2" {
		t.Fatalf("multi-source sections not grouped: %#v", mod.Sections)
	}
	if mod.Sections[0].Heading != "Alpha" || mod.Sections[1].Heading != "Beta" {
		t.Fatalf("unexpected section headings: %#v", mod.Sections)
	}
}

func TestExtractBlocksFromDocUsesManifest(t *testing.T) {
	doc := mustWriteDoc(t, blockFixture)
	docBytes, _ := os.ReadFile(doc)
	manifest, _, _ := LoadManifest(doc, docBytes)
	manifest.SyntheticSections = []SyntheticSection{{Heading: "Costs", Occurrence: 1}}
	if err := SaveManifest(doc, manifest); err != nil {
		t.Fatal(err)
	}
	blocks, loaded, err := ExtractBlocksFromDoc(doc)
	if err != nil {
		t.Fatalf("ExtractBlocksFromDoc: %v", err)
	}
	if loaded.SyntheticSections == nil {
		t.Fatalf("manifest not loaded: %#v", loaded)
	}
	for _, b := range blocks {
		if b.Kind == BlockKindHeading && b.Text == "Costs" {
			t.Fatalf("manifest synthetic section treated as a translatable heading: %#v", b)
		}
	}
	// A missing document must surface the read error, not an empty block list.
	if _, _, err := ExtractBlocksFromDoc(filepath.Join(t.TempDir(), "missing.md")); err == nil {
		t.Fatal("expected error for missing document")
	}
}

func TestStripNotesKeepsBlockHashesStable(t *testing.T) {
	doc := mustWriteDoc(t, "## Alpha\n\nFirst prose paragraph.\n\nSecond prose paragraph.\n")
	docBytes, _ := os.ReadFile(doc)
	manifest, _, _ := LoadManifest(doc, docBytes)
	base := ExtractBlocks(docBytes, manifest)
	if _, err := AddNote(doc, AddNoteOptions{Heading: "Alpha", Text: "请核对 42.5B"}); err != nil {
		t.Fatal(err)
	}
	withNote, _ := os.ReadFile(doc)
	if !strings.Contains(string(withNote), "<!-- note") {
		t.Fatal("note was not inserted")
	}
	after := ExtractBlocks(withNote, manifest)
	if len(after) != len(base) {
		t.Fatalf("block count changed: %d -> %d", len(base), len(after))
	}
	for i := range base {
		if after[i].ID != base[i].ID || after[i].SourceHash != base[i].SourceHash {
			t.Fatalf("note shifted block %d: %#v -> %#v", i, base[i], after[i])
		}
	}
	if got := markdown.StripNotes(string(withNote)); got != string(docBytes) {
		t.Fatalf("note strip is not byte-identical to the pre-note document")
	}
}

func TestExtractBlocksImageAndTripleDuplicateRules(t *testing.T) {
	manifest, _, err := LoadManifest("article.md", nil)
	if err != nil {
		t.Fatal(err)
	}
	raw := "Repeated sentence.\n\nRepeated sentence.\n\nRepeated sentence.\n\nText with an image ![Figure one](assets/a.png) inline.\n\n![](assets/decor.png)\n\n![Only alt text](assets/b.png)\n"
	blocks := ExtractBlocks([]byte(raw), manifest)

	var paragraphs []Block
	for _, b := range blocks {
		if b.Kind == BlockKindParagraph {
			paragraphs = append(paragraphs, b)
		}
	}
	// Three identical paragraphs plus the text+image paragraph stay paragraphs;
	// an image-only paragraph with empty alt text is not translatable at all.
	if len(paragraphs) != 4 {
		t.Fatalf("unexpected paragraph count %d: %#v", len(paragraphs), blocks)
	}
	if paragraphs[1].ID != paragraphs[0].ID+"-2" || paragraphs[2].ID != paragraphs[0].ID+"-3" {
		t.Fatalf("triple duplicate ids = %q, %q, %q", paragraphs[0].ID, paragraphs[1].ID, paragraphs[2].ID)
	}
	if !strings.Contains(paragraphs[3].Text, "Text with an image") || !strings.Contains(paragraphs[3].Text, "Figure one") {
		t.Fatalf("text+image paragraph lost content: %#v", paragraphs[3])
	}
	if blocks[len(blocks)-1].Kind != BlockKindImageAlt || blocks[len(blocks)-1].Text != "Only alt text" {
		t.Fatalf("standalone image alt block missing: %#v", blocks[len(blocks)-1])
	}
}
