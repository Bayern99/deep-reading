package view

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"deepread/internal/bundle"
)

const sampleDoc = `# Powering AI Data Centers

Intro paragraph.

## §1 · Capital Surge

Firm A reported $18B in 2024 cash capex. Firm B announced a $42B three-year commitment through 2026.

## §2 · Grid Queues

US interconnection queues rose from 750 GW in 2020 to 2,600 GW in 2024.
`

func TestCatalogExcludesDashboardClichés(t *testing.T) {
	text, err := CatalogText()
	if err != nil {
		t.Fatal(err)
	}
	for _, want := range []string{"Table(", "Chart(", "Quote(", "List(", "Source("} {
		if !strings.Contains(text, want) {
			t.Fatalf("catalog missing expected primitive %q", want)
		}
	}
	for _, banned := range []string{"Card(", "Grid(", "Badge(", "Carousel("} {
		if strings.Contains(text, banned) {
			t.Fatalf("catalog leaked banned dashboard component %q", banned)
		}
	}
}

func TestWriteStrictHappyPathAndPrevBackup(t *testing.T) {
	dir := t.TempDir()
	doc := filepath.Join(dir, "article.md")
	if err := os.WriteFile(doc, []byte(sampleDoc), 0o644); err != nil {
		t.Fatal(err)
	}

	stmts := strings.Join([]string{
		`root = Col([capex_cmp, queue_chart])`,
		`capex_cmp = Source(["s1"], [Title("资本开支统计口径差异", "md"), Table(["主体", "口径", "原文数值"], [["Firm A", "2024 单年现金", "$18B"], ["Firm B", "三年累计承诺", "$42B"]])])`,
		`queue_chart = Source(["s2"], [Title("并网队列容量（GW）", "md"), Chart("line", qdata, "year", ["gw"], "number", false, 200)])`,
		`qdata = [{year: "2020", gw: 750}, {year: "2024", gw: 2600}]`,
	}, "\n")

	res1, err := Write(doc, WriteOptions{
		StatementsText: stmts,
		Sources: map[string]SourceRef{
			"s1": {Heading: "§1 · Capital Surge", Occurrence: 1},
			"s2": {Heading: "§2 · Grid Queues", Occurrence: 1},
		},
		Now: time.Date(2026, 11, 26, 8, 0, 0, 0, time.UTC),
	})
	if err != nil {
		t.Fatalf("Write r1 failed: %v", err)
	}
	if res1.Revision != 1 || res1.ModuleCount != 2 {
		t.Fatalf("unexpected r1 result: %#v", res1)
	}

	// Verify Mark Go Go v3 exact contract on disk.
	raw, err := os.ReadFile(bundle.ViewPath(doc))
	if err != nil {
		t.Fatal(err)
	}
	parsed, err := ReadView(raw)
	if err != nil {
		t.Fatalf("ReadView failed: %v", err)
	}
	if parsed.Envelope.Language != "openui-lang/1.0" || parsed.Envelope.A2UI[0].CreateSurface.CatalogID != "markgogo.dev:genui/v3" {
		t.Fatalf("v3 compatibility mismatch: %#v", parsed.Envelope)
	}
	if parsed.Envelope.Sources["s1"].Hash == "" || parsed.Envelope.Sources["s2"].Hash == "" {
		t.Fatalf("expected fnv1a32 source hashes stamped: %#v", parsed.Envelope.Sources)
	}

	// Second write must create Mark Go Go's exact `.genui.prev.json` backup.
	res2, err := Write(doc, WriteOptions{
		StatementsText: `root = Col([])`,
		Sources:        map[string]SourceRef{},
	})
	if err != nil {
		t.Fatalf("Write r2 (0 modules) failed: %v", err)
	}
	if res2.Revision != 2 || res2.ModuleCount != 0 {
		t.Fatalf("unexpected r2 result: %#v", res2)
	}
	if _, err := os.Stat(bundle.PrevViewPath(bundle.ViewPath(doc))); err != nil {
		t.Fatalf("expected .genui.prev.json backup for Mark Go Go undo: %v", err)
	}
	if !strings.HasSuffix(bundle.PrevViewPath(bundle.ViewPath(doc)), ".article.md.genui.prev.json") {
		t.Fatalf("wrong prev backup name: %s", bundle.PrevViewPath(bundle.ViewPath(doc)))
	}
}

func TestWriteRejectsViolationsWithoutCorruptingExistingView(t *testing.T) {
	dir := t.TempDir()
	doc := filepath.Join(dir, "article.md")
	if err := os.WriteFile(doc, []byte(sampleDoc), 0o644); err != nil {
		t.Fatal(err)
	}
	// Seed valid r1 view.
	validStmts := "root = Col([q])\nq = Source([\"s1\"], [Quote(\"Firm A reported $18B.\", \"§1\")])\n"
	if _, err := Write(doc, WriteOptions{
		StatementsText: validStmts,
		Sources:        map[string]SourceRef{"s1": {Heading: "§1 · Capital Surge", Occurrence: 1}},
	}); err != nil {
		t.Fatal(err)
	}
	before, _ := os.ReadFile(bundle.ViewPath(doc))

	cases := []struct {
		name     string
		stmts    string
		sources  map[string]SourceRef
		wantCode string
	}{
		{
			name:     "disallowed Card component",
			stmts:    "root = Col([m])\nm = Source([\"s1\"], [Card([Table([\"A\"], [[\"1\"]])])])",
			sources:  map[string]SourceRef{"s1": {Heading: "§1 · Capital Surge", Occurrence: 1}},
			wantCode: "DISALLOWED_COMPONENT",
		},
		{
			name:     "prose-only summary rejected",
			stmts:    "root = Col([m])\nm = Source([\"s1\"], [Title(\"Capital\", \"md\"), List([\"Point 1\", \"Point 2\"])])",
			sources:  map[string]SourceRef{"s1": {Heading: "§1 · Capital Surge", Occurrence: 1}},
			wantCode: "PROSE_ONLY_SUMMARY_REJECTED",
		},
		{
			name:     "cliché title rejected",
			stmts:    "root = Col([m])\nm = Source([\"s1\"], [Title(\"Key Takeaways\", \"md\"), Quote(\"Quote\", \"§1\")])",
			sources:  map[string]SourceRef{"s1": {Heading: "§1 · Capital Surge", Occurrence: 1}},
			wantCode: "CLICHE_TITLE_REJECTED",
		},
		{
			name:     "H1 anchor forbidden",
			stmts:    "root = Col([m])\nm = Source([\"s1\"], [Quote(\"Quote\", \"H1\")])",
			sources:  map[string]SourceRef{"s1": {Heading: "Powering AI Data Centers", Occurrence: 1}},
			wantCode: "H1_SOURCE_FORBIDDEN",
		},
		{
			name:     "unknown section rejected",
			stmts:    "root = Col([m])\nm = Source([\"s1\"], [Quote(\"Quote\", \"Ghost\")])",
			sources:  map[string]SourceRef{"s1": {Heading: "Does Not Exist", Occurrence: 1}},
			wantCode: "UNKNOWN_SECTION",
		},
		{
			name:     "multi-section Source rejected",
			stmts:    "root = Col([m])\nm = Source([\"s1\", \"s2\"], [Quote(\"Quote\", \"Both\")])",
			sources:  map[string]SourceRef{"s1": {Heading: "§1 · Capital Surge", Occurrence: 1}, "s2": {Heading: "§2 · Grid Queues", Occurrence: 1}},
			wantCode: "SINGLE_SOURCE_REQUIRED",
		},
		{
			name:     "disallowed chart type pie",
			stmts:    "root = Col([m])\nm = Source([\"s1\"], [Chart(\"pie\", [{k: \"a\", v: 1}], \"k\", [\"v\"])])",
			sources:  map[string]SourceRef{"s1": {Heading: "§1 · Capital Surge", Occurrence: 1}},
			wantCode: "DISALLOWED_CHART_TYPE",
		},
		{
			name:     "unknown component strict zero-fault",
			stmts:    "root = Col([m])\nm = Source([\"s1\"], [BogusWidget(\"x\"), Quote(\"hi\")])",
			sources:  map[string]SourceRef{"s1": {Heading: "§1 · Capital Surge", Occurrence: 1}},
			wantCode: "OPENUI_ERROR",
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			_, err := Write(doc, WriteOptions{StatementsText: tc.stmts, Sources: tc.sources})
			var ve *ValidationError
			if !errors.As(err, &ve) {
				t.Fatalf("expected ValidationError(%s), got %v", tc.wantCode, err)
			}
			if ve.Code != tc.wantCode {
				t.Fatalf("got code %q (%s), want %q", ve.Code, ve.Message, tc.wantCode)
			}
		})
	}

	after, _ := os.ReadFile(bundle.ViewPath(doc))
	if string(after) != string(before) {
		t.Fatalf("rejected writes corrupted existing view")
	}
}
