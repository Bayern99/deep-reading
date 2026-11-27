package bundle

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"deepread/internal/markdown"
)

func TestPrepareInsertsSyntheticH2WithoutAlteringProse(t *testing.T) {
	dir := t.TempDir()
	doc := filepath.Join(dir, "essay.md")
	original := "# Why Grids Strain\n\nFirst paragraph with exact numbers: $42.5B in 2024.\n\nSecond paragraph explains peak demand.\n\nThird paragraph covers transmission delays.\n"
	if err := os.WriteFile(doc, []byte(original), 0o644); err != nil {
		t.Fatal(err)
	}

	res, err := Prepare(doc, []BreakSpec{
		{BeforeLine: 3, Title: "Capital Surge"},
		{BeforeLine: 7, Title: "Grid Bottlenecks"},
	})
	if err != nil {
		t.Fatalf("Prepare failed: %v", err)
	}
	if res.Inserted != 2 || len(res.SyntheticSections) != 2 {
		t.Fatalf("unexpected PrepareResult: %#v", res)
	}

	updatedBytes, err := os.ReadFile(doc)
	if err != nil {
		t.Fatal(err)
	}
	updated := string(updatedBytes)
	// Strip synthetic H2 lines and verify every original prose line is untouched.
	for _, want := range []string{
		"# Why Grids Strain",
		"First paragraph with exact numbers: $42.5B in 2024.",
		"Second paragraph explains peak demand.",
		"Third paragraph covers transmission delays.",
	} {
		if !strings.Contains(updated, want) {
			t.Fatalf("original prose missing after Prepare: %q", want)
		}
	}

	secs := markdown.ExtractSections(updated)
	if len(secs) != 3 {
		t.Fatalf("expected 3 sections (1 H1 + 2 synthetic H2), got %d", len(secs))
	}

	rep, err := Inspect(doc, InspectOptions{Heading: "§1 · Capital Surge", Occurrence: 1})
	if err != nil {
		t.Fatalf("Inspect failed: %v", err)
	}
	if !rep.Sections[1].Synthetic || !rep.Sections[2].Synthetic {
		t.Fatalf("expected synthetic flags set on H2s: %#v", rep.Sections)
	}
	if rep.Excerpt == nil || !strings.Contains(rep.Excerpt.Text, "$42.5B in 2024.") {
		t.Fatalf("unexpected excerpt: %#v", rep.Excerpt)
	}
}

func TestPrepareRejectsInvalidBreakInsideFence(t *testing.T) {
	dir := t.TempDir()
	doc := filepath.Join(dir, "code.md")
	raw := "Intro.\n\n```go\nfmt.Println(\"hi\")\n```\n\nAfter.\n"
	if err := os.WriteFile(doc, []byte(raw), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := Prepare(doc, []BreakSpec{{BeforeLine: 4, Title: "Inside Fence"}}); err == nil {
		t.Fatalf("expected error when inserting break inside fenced code block")
	}
}

func TestInspectDetectsDesktopNotesWithoutLedger(t *testing.T) {
	dir := t.TempDir()
	doc := filepath.Join(dir, "article.md")
	raw := "## Spending\nFirm A spent $10B in 2024.\n\n<!-- note: compare annualized vs 3-year total -->\n"
	if err := os.WriteFile(doc, []byte(raw), 0o644); err != nil {
		t.Fatal(err)
	}
	rep, err := Inspect(doc, InspectOptions{})
	if err != nil {
		t.Fatalf("Inspect failed: %v", err)
	}
	if len(rep.OpenNotes) != 1 || rep.OpenNotes[0].Origin != "desktop" || rep.OpenNotes[0].SectionHeading != "Spending" {
		t.Fatalf("unexpected open notes: %#v", rep.OpenNotes)
	}
}
