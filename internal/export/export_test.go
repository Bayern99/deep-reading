package export

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"deepread/internal/bundle"
	"deepread/internal/view"
)

func parsedView(statements string, sources map[string]view.SourceRef) *view.ParsedView {
	return &view.ParsedView{JoinedText: statements, Envelope: view.Envelope{Sources: sources}}
}

func TestExportHeadinglessDocumentHasNoGenUIChromeOrJavaScript(t *testing.T) {
	dir := t.TempDir()
	docPath := filepath.Join(dir, "plain.md")
	outPath := filepath.Join(dir, "out", "plain.html")
	raw := "A headingless document with **clean prose**.\n"
	if err := os.WriteFile(docPath, []byte(raw), 0o644); err != nil {
		t.Fatal(err)
	}

	result, err := Export(docPath, outPath, ExportOptions{})
	if err != nil {
		t.Fatalf("Export failed: %v", err)
	}
	if result.DocPath != docPath || result.OutPath != outPath || result.ModuleCount != 0 {
		t.Fatalf("unexpected result: %#v", result)
	}
	if result.BundleID == "" || result.Bytes == 0 {
		t.Fatalf("missing result metadata: %#v", result)
	}
	data, err := os.ReadFile(outPath)
	if err != nil {
		t.Fatal(err)
	}
	html := string(data)
	if result.Bytes != len(data) {
		t.Fatalf("Bytes = %d, file has %d", result.Bytes, len(data))
	}
	for _, want := range []string{"<title>plain</title>", "<strong>clean prose</strong>", `http-equiv="Content-Security-Policy"`} {
		if !strings.Contains(html, want) {
			t.Errorf("output missing %q", want)
		}
	}
	for _, banned := range []string{"<script", `class="dr-module"`, `class="dr-shortcode"`} {
		if strings.Contains(html, banned) {
			t.Errorf("zero-module export contains %q", banned)
		}
	}
}

func TestRenderHTMLUsesSingleParserSlicesAndGlobalLinkDefinitions(t *testing.T) {
	raw := strings.Join([]string{
		"# Report",
		"",
		"Read [the opening][ref].",
		"",
		"## §1 · Opening",
		"",
		"> A quotation",
		"> # Fake Heading",
		"",
		"<!-- note node=\"capex\" id=\"n1\" rev=\"1\": private reader note -->",
		"",
		"[ref]: https://example.com",
		"",
		"## §2 · Continuation",
		"",
		"Read [the opening][ref] again.",
		"",
		"Unsafe [script](javascript:alert(1)) and [data](data:text/html;base64,PHNjcmlwdD4=) links.",
	}, "\n")

	html, count, err := RenderHTML(raw, bundle.Manifest{BundleID: "K7", Revision: 1}, nil, "Report")
	if err != nil {
		t.Fatal(err)
	}
	if count != 0 {
		t.Fatalf("module count = %d, want 0", count)
	}
	if got := strings.Count(html, `href="https://example.com"`); got != 2 {
		t.Fatalf("cross-section reference resolved %d times, want 2\n%s", got, html)
	}
	if !strings.Contains(html, "<blockquote>") || !strings.Contains(html, "Fake Heading") {
		t.Fatalf("blockquote was not preserved: %s", html)
	}
	if strings.Contains(html, "private reader note") || strings.Contains(html, "note node=") {
		t.Fatalf("reader note leaked into export: %s", html)
	}
	for _, banned := range []string{`href="javascript:`, `href="data:`} {
		if strings.Contains(html, banned) {
			t.Errorf("unsafe link survived: %q", banned)
		}
	}
}

func TestRenderHTMLUsesEditorialBreakForSyntheticHeading(t *testing.T) {
	raw := "# Report\n\n## §1 · Inserted Anchor\n\nOriginal prose.\n"
	manifest := bundle.Manifest{
		BundleID:          "K7",
		SyntheticSections: []bundle.SyntheticSection{{Heading: "§1 · Inserted Anchor", Occurrence: 1}},
	}
	html, _, err := RenderHTML(raw, manifest, nil, "Report")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(html, `class="dr-sec-break"`) || !strings.Contains(html, "§1 · Inserted Anchor") {
		t.Fatalf("synthetic section divider missing: %s", html)
	}
	if strings.Contains(html, "<h2>§1 · Inserted Anchor</h2>") {
		t.Fatalf("synthetic section rendered as a heavy H2: %s", html)
	}
}

func TestRenderHTMLInterleavesMagazinePrimitives(t *testing.T) {
	raw := "# Report\n\n## §1 · Capital\n\nOriginal capital prose.\n\n## §2 · Demand\n\nOriginal demand prose.\n"
	statements := strings.Join([]string{
		"root = Col([capex])",
		`capex = Source(["s1"], [`,
		`  Title("Capital trajectory", "lg"),`,
		`  Text(["Revenue ", Text("18", "md", "#1c1b18", "semibold", true, true, true)]),`,
		`  Table(["Company", "Capex"], [["A", 18], ["B", 42]]),`,
		`  Chart("bar", chart_data, "year", ["capex"], "number", false, 220, {capex: "Capital spending"}),`,
		`  Chart("line", chart_data, "year", ["capex", "revenue"], "number", false, 240, {capex: "Capital spending", revenue: "Revenue"}),`,
		`  List([ListItem("First approval", "Initial permission", "2024"), ListItem("Expansion", "New capacity", "2025")], "none", true),`,
		`  Quote("An editorial pull quote.", "§1 · Capital"),`,
		`  Caption("Source: original figures")`,
		`])`,
		`chart_data = [{year: "2024", capex: 18, revenue: 30}, {year: "2025", capex: 42, revenue: 55}]`,
	}, "\n")
	parsed := parsedView(statements, map[string]view.SourceRef{
		"s1": {Heading: "§1 · Capital", Occurrence: 1},
	})
	manifest := bundle.Manifest{BundleID: "K7", Revision: 1}

	html, count, err := RenderHTML(raw, manifest, parsed, "Report")
	if err != nil {
		t.Fatalf("RenderHTML failed: %v", err)
	}
	if count != 1 {
		t.Fatalf("module count = %d, want 1", count)
	}
	for _, want := range []string{
		`<code class="dr-shortcode">K7·capex@r1</code>`,
		"§1 · Capital",
		`class="dr-table-wrap"`,
		`class="dr-num"`,
		"dr-timeline",
		`class="dr-quote"`,
		`<svg`,
		`viewBox="0 0 600 220"`,
		`viewBox="0 0 600 240"`,
		`class="dr-chart-legend"`,
		`<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:;">`,
	} {
		if !strings.Contains(html, want) {
			t.Errorf("module output missing %q", want)
		}
	}
	for _, banned := range []string{"<script", `class="dr-card"`, "<Card", "box-shadow"} {
		if strings.Contains(html, banned) {
			t.Errorf("module output contains banned %q", banned)
		}
	}
	proseAt := strings.Index(html, "Original capital prose.")
	moduleAt := strings.Index(html, `class="dr-module"`)
	nextSectionAt := strings.Index(html, "<h2>§2 · Demand</h2>")
	if proseAt < 0 || moduleAt < 0 || nextSectionAt < 0 || !(proseAt < moduleAt && moduleAt < nextSectionAt) {
		t.Fatalf("module not interleaved after cited prose: prose=%d module=%d next=%d", proseAt, moduleAt, nextSectionAt)
	}
}

func TestRenderHTMLRejectsMissingSourceHeading(t *testing.T) {
	raw := "# Report\n\n## §1 · Present\n\nProse.\n"
	parsed := parsedView(strings.Join([]string{
		"root = Col([capex])",
		`capex = Source(["missing"], [Quote("Quote", "Ghost")])`,
	}, "\n"), map[string]view.SourceRef{
		"missing": {Heading: "§9 · Missing", Occurrence: 1},
	})

	html, _, err := RenderHTML(raw, bundle.Manifest{BundleID: "K7", Revision: 1}, parsed, "Report")
	if err == nil {
		t.Fatalf("missing source heading was silently accepted: %s", html)
	}
	if !strings.Contains(err.Error(), "capex") || !strings.Contains(err.Error(), "§9 · Missing") {
		t.Fatalf("error is not explicit about statement and heading: %v", err)
	}
}

func TestRenderHTMLNeutralizesRawScriptsInMarkdownAndOpenUI(t *testing.T) {
	raw := "# Report\n\n## §1 · Security\n\n<script>alert(1)</script>\n\nProse.\n"
	parsed := parsedView(strings.Join([]string{
		"root = Col([security])",
		`security = Source(["s1"], [Text("<script>alert(1)</script>"), Quote("Safe quote")])`,
	}, "\n"), map[string]view.SourceRef{
		"s1": {Heading: "§1 · Security", Occurrence: 1},
	})

	html, _, err := RenderHTML(raw, bundle.Manifest{BundleID: "K7", Revision: 1}, parsed, "Report")
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(strings.ToLower(html), "<script") {
		t.Fatalf("active script tag survived: %s", html)
	}
	if !strings.Contains(html, "&lt;script&gt;alert(1)&lt;/script&gt;") {
		t.Fatalf("OpenUI script text was not visibly escaped: %s", html)
	}
}
