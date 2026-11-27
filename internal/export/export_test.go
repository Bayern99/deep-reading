package export

import (
	"crypto/sha256"
	"encoding/base64"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"deepread/internal/bundle"
	"deepread/internal/genuikit"
	"deepread/internal/openuilang"
	"deepread/internal/view"
)

func parsedView(statements string, sources map[string]view.SourceRef) *view.ParsedView {
	return &view.ParsedView{JoinedText: statements, Envelope: view.Envelope{Sources: sources}}
}

func TestExportHeadinglessDocumentHasNoGenUIChrome(t *testing.T) {
	dir := t.TempDir()
	docPath := filepath.Join(dir, "plain.md")
	outPath := filepath.Join(dir, "out", "plain.html")
	raw := "A headingless document with **clean prose**.\n"
	if err := os.WriteFile(docPath, []byte(raw), 0o644); err != nil {
		t.Fatal(err)
	}

	result, err := Export(docPath, outPath, ExportOptions{NoJS: true})
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
	for _, banned := range []string{"<script", `class="dr-card"`, "<Card"} {
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

func writeExportView(t *testing.T, docPath, statements string, sources map[string]view.SourceRef) {
	t.Helper()
	raw, err := view.BuildCompactedEnvelope(view.SplitStatementStrings(statements), sources, "test", "", time.Date(2026, 1, 2, 3, 4, 5, 0, time.UTC))
	if err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(filepath.Dir(bundle.ViewPath(docPath)), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(bundle.ViewPath(docPath), raw, 0o644); err != nil {
		t.Fatal(err)
	}
}

func TestExportDualFaceTranslationCitationsAndCoverage(t *testing.T) {
	dir := t.TempDir()
	doc := filepath.Join(dir, "article.md")
	out := filepath.Join(dir, "reader.html")
	raw := "# Report\n\n## Capital\n\nOriginal **capital** prose.\n"
	if err := os.WriteFile(doc, []byte(raw), 0o644); err != nil {
		t.Fatal(err)
	}
	manifest := bundle.Manifest{BundleID: "AA", Revision: 2, Profile: bundle.ProfileCanvas, Reader: &bundle.ReaderConfig{SourceLang: "en", TargetLang: "zh-CN", Mode: bundle.ReadModeTranslated}}
	if err := bundle.SaveManifest(doc, manifest); err != nil {
		t.Fatal(err)
	}
	writeExportView(t, doc, "root = Col([mod])\nmod = Source([\"s1\"], [Title(\"资本\")])", map[string]view.SourceRef{"s1": {Heading: "Capital", Occurrence: 1}})
	blocks := bundle.ExtractBlocks([]byte(raw), manifest)
	entries := make([]bundle.TranslationEntry, 0, len(blocks))
	for _, block := range blocks {
		entries = append(entries, bundle.TranslationEntry{ID: block.ID, SourceHash: block.SourceHash, Text: "译文 " + block.Text})
	}
	if _, err := bundle.ApplyTranslations(doc, "zh-CN", entries); err != nil {
		t.Fatal(err)
	}
	paragraph := blocks[len(blocks)-1]
	if err := bundle.SaveCitations(doc, bundle.CitationMap{"mod": {"s1": {paragraph.ID}}}); err != nil {
		t.Fatal(err)
	}
	result, err := Export(doc, out, ExportOptions{})
	if err != nil {
		t.Fatal(err)
	}
	if result.Face != "dual" || result.Lang != "zh-CN" || result.Mode != bundle.ReadModeTranslated || result.ChapterCount != 1 {
		t.Fatalf("unexpected default dual metadata: %+v", result)
	}
	data, err := os.ReadFile(out)
	if err != nil {
		t.Fatal(err)
	}
	html := string(data)
	for _, want := range []string{
		`id="c01-s01"`, `id="c01-s02"`, `id="c01-` + paragraph.ID + `"`, `id="c01-g-mod"`,
		`data-face-target="genui"`, `data-face-target="read"`,
		"查看原文 ↗", `popover id=`, `class="dr-orig"`, `data-jump-genui`, `反馈码`, "AA·mod@r2",
		`<html lang="zh-CN"`, `data-lang-mode="translated"`, `<script>`,
	} {
		if !strings.Contains(html, want) {
			t.Errorf("dual export missing %q", want)
		}
	}
	inlineOut := filepath.Join(dir, "inline.html")
	inlineResult, err := Export(doc, inlineOut, ExportOptions{Face: "inline"})
	if err != nil {
		t.Fatal(err)
	}
	if inlineResult.Face != "inline" || inlineResult.Lang != "zh-CN" || inlineResult.Mode != bundle.ReadModeTranslated || inlineResult.ChapterCount != 1 {
		t.Fatalf("unexpected inline metadata: %+v", inlineResult)
	}
	inlineData, err := os.ReadFile(inlineOut)
	if err != nil {
		t.Fatal(err)
	}
	inlineHTML := string(inlineData)
	for _, want := range []string{
		`data-face="inline"`, `data-inline-view-target="mixed"`, `data-inline-view-target="genui"`, `data-inline-view-target="prose"`,
		`id="c01-s01"`, `id="c01-s02"`, `id="c01-` + paragraph.ID + `"`, `id="c01-g-mod"`,
		`class="dr-inline-module"`, `class="dr-orig-inline" lang="en"`,
		"查看原文 ↗", `popover id=`, `class="dr-orig"`, `data-jump-genui`, `反馈码`, "AA·mod@r2",
		`<html lang="zh-CN"`, `data-lang-mode="translated"`, `<script>`,
	} {
		if !strings.Contains(inlineHTML, want) {
			t.Errorf("inline export missing %q", want)
		}
	}
	prosePos := strings.Index(inlineHTML, "译文 Original")
	modPos := strings.Index(inlineHTML, `id="c01-g-mod"`)
	if prosePos < 0 || modPos < 0 || prosePos > modPos {
		t.Fatalf("inline module should appear after cited prose: prose=%d mod=%d", prosePos, modPos)
	}
	bilingualOut := filepath.Join(dir, "bilingual.html")
	if _, err := Export(doc, bilingualOut, ExportOptions{Mode: bundle.ReadModeBilingual}); err != nil {
		t.Fatal(err)
	}
	bilingual, _ := os.ReadFile(bilingualOut)
	if !strings.Contains(string(bilingual), `class="dr-orig-inline" lang="en"`) || !strings.Contains(string(bilingual), `data-lang-mode="bilingual"`) {
		t.Fatalf("bilingual blocks are not paired with original prose")
	}

	if err := os.MkdirAll(filepath.Join(dir, "partial"), 0o755); err != nil {
		t.Fatal(err)
	}
	partial := filepath.Join(dir, "partial", "partial.md")
	if err := os.WriteFile(partial, []byte(raw), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := bundle.SaveManifest(partial, manifest); err != nil {
		t.Fatal(err)
	}
	if _, err := bundle.ApplyTranslations(partial, "zh-CN", entries[:1]); err != nil {
		t.Fatal(err)
	}
	_, err = Export(partial, filepath.Join(dir, "partial", "partial.html"), ExportOptions{})
	if !errors.Is(err, bundle.ErrTranslationIncomplete) {
		t.Fatalf("partial translation error = %v", err)
	}
	if _, statErr := os.Stat(filepath.Join(dir, "partial", "partial.html")); !errors.Is(statErr, os.ErrNotExist) {
		t.Fatalf("partial translation wrote output: %v", statErr)
	}
}

func TestExportReactiveIslandStatesAndLimits(t *testing.T) {
	makeDoc := func(t *testing.T, statements string) (string, string) {
		dir := t.TempDir()
		doc := filepath.Join(dir, "article.md")
		raw := "# Report\n\n## Scenario\n\nProse.\n"
		if err := os.WriteFile(doc, []byte(raw), 0o644); err != nil {
			t.Fatal(err)
		}
		if err := bundle.SaveManifest(doc, bundle.Manifest{BundleID: "AA", Profile: bundle.ProfileCanvas}); err != nil {
			t.Fatal(err)
		}
		writeExportView(t, doc, statements, map[string]view.SourceRef{"s1": {Heading: "Scenario", Occurrence: 1}})
		return doc, filepath.Join(dir, "out.html")
	}

	t.Run("decimal slider uses exact values and integer keys", func(t *testing.T) {
		doc, out := makeDoc(t, "root = Col([mod])\n$x = 0\nmod = Source([\"s1\"], [Slider($x, 0, 1, 0.1, \"Rate\"), Text(@Format($x, \"number\", 1))])")
		if _, err := Export(doc, out, ExportOptions{}); err != nil {
			t.Fatal(err)
		}
		data, _ := os.ReadFile(out)
		html := string(data)
		for _, want := range []string{`data-state="0"`, `data-state="3"`, `data-state="10"`, `type="range"`, `max="10"`} {
			if !strings.Contains(html, want) {
				t.Errorf("slider export missing %q", want)
			}
		}
		if strings.Contains(html, "0.30000000000000004") || !strings.Contains(html, ">0.3<") {
			t.Fatalf("slider values drifted or missing")
		}
	})

	options := func(n int) string {
		parts := make([]string, n)
		for i := range parts {
			parts[i] = fmt.Sprintf("\"%d\"", i)
		}
		return "[" + strings.Join(parts, ",") + "]"
	}
	for _, tc := range []struct {
		name       string
		second     int
		wantStates int
		degraded   bool
	}{{"64 states", 8, 64, false}, {"72 states degrades", 9, 0, true}} {
		t.Run(tc.name, func(t *testing.T) {
			stmts := "root = Col([mod])\n$a = \"0\"\n$b = \"0\"\nmod = Source([\"s1\"], [SegmentedControl($a, " + options(8) + "), SegmentedControl($b, " + options(tc.second) + "), Text($a + $b)])"
			doc, out := makeDoc(t, stmts)
			result, err := Export(doc, out, ExportOptions{})
			if err != nil {
				t.Fatal(err)
			}
			data, _ := os.ReadFile(out)
			html := string(data)
			if got := strings.Count(html, `<template data-island=`); got != tc.wantStates {
				t.Fatalf("template count = %d, want %d", got, tc.wantStates)
			}
			if tc.degraded {
				if len(result.Warnings) == 0 || !strings.Contains(strings.Join(result.Warnings, " "), "REACTIVE_STATE_EXPLOSION") || !strings.Contains(html, "disabled") {
					t.Fatalf("degradation missing: %+v", result)
				}
			}
		})
	}
}

func TestExportReadingAnchorsCoverListsTablesQuotesAndSyntheticSections(t *testing.T) {
	dir := t.TempDir()
	doc := filepath.Join(dir, "article.md")
	raw := "# Report\n\n## §1 · Synthetic\n\n- First item\n- Second item\n\n> Quoted prose\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n"
	if err := os.WriteFile(doc, []byte(raw), 0o644); err != nil {
		t.Fatal(err)
	}
	manifest := bundle.Manifest{BundleID: "AA", SyntheticSections: []bundle.SyntheticSection{{Heading: "§1 · Synthetic", Occurrence: 1}}}
	if err := bundle.SaveManifest(doc, manifest); err != nil {
		t.Fatal(err)
	}
	out := filepath.Join(dir, "out.html")
	if _, err := Export(doc, out, ExportOptions{NoJS: true}); err != nil {
		t.Fatal(err)
	}
	data, _ := os.ReadFile(out)
	html := string(data)
	for _, block := range bundle.ExtractBlocks([]byte(raw), manifest) {
		if got := strings.Count(html, `id="c01-`+block.ID+`"`); got != 1 {
			t.Errorf("block %s (%s) anchor count = %d", block.ID, block.Kind, got)
		}
	}
	if !strings.Contains(html, `<h2 id="c01-s02" class="dr-sec-break">`) {
		t.Fatalf("synthetic section is not a semantic anchored h2")
	}
}

func TestExportRuntimeSecurityAndNoJS(t *testing.T) {
	dir := t.TempDir()
	doc := filepath.Join(dir, "article.md")
	raw := "# Report\n\n## Security\n\nProse.\n"
	if err := os.WriteFile(doc, []byte(raw), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := bundle.SaveManifest(doc, bundle.Manifest{BundleID: "AA", Profile: bundle.ProfileCanvas}); err != nil {
		t.Fatal(err)
	}
	writeExportView(t, doc, "root = Col([mod])\nmod = Source([\"s1\"], [Text(\"</script><img onerror=alert(1)>\")])", map[string]view.SourceRef{"s1": {Heading: "Security", Occurrence: 1}})
	out := filepath.Join(dir, "out.html")
	if _, err := Export(doc, out, ExportOptions{}); err != nil {
		t.Fatal(err)
	}
	data, _ := os.ReadFile(out)
	html := string(data)
	sum := sha256.Sum256([]byte(runtimeJS))
	if !strings.Contains(html, "script-src 'sha256-"+base64.StdEncoding.EncodeToString(sum[:])+"'") {
		t.Fatalf("CSP hash does not cover runtime bytes")
	}
	if strings.Count(strings.ToLower(html), "</script>") != 1 || strings.Contains(html, "<img onerror") {
		t.Fatalf("user text broke out of script or HTML")
	}
	noJS := filepath.Join(dir, "nojs.html")
	if _, err := Export(doc, noJS, ExportOptions{NoJS: true}); err != nil {
		t.Fatal(err)
	}
	data, _ = os.ReadFile(noJS)
	html = string(data)
	if strings.Contains(strings.ToLower(html), "<script") || strings.Contains(html, "script-src") {
		t.Fatalf("NoJS emitted script runtime or CSP")
	}
	if !strings.Contains(html, `class="dr-face dr-face-genui"`) || !strings.Contains(html, `class="dr-face dr-face-read"`) {
		t.Fatalf("dual NoJS does not retain both faces")
	}
	noJSInline := filepath.Join(dir, "nojs-inline.html")
	if _, err := Export(doc, noJSInline, ExportOptions{Face: "inline", NoJS: true}); err != nil {
		t.Fatal(err)
	}
	inlineData, _ := os.ReadFile(noJSInline)
	inlineHTML := string(inlineData)
	if !strings.Contains(inlineHTML, `class="dr-sec-prose"`) || !strings.Contains(inlineHTML, `class="dr-inline-module"`) {
		t.Fatalf("inline NoJS does not retain both prose and embedded module")
	}
}

func TestExportReactiveSVGAndLinksAreSanitizedInEveryState(t *testing.T) {
	dir := t.TempDir()
	doc := filepath.Join(dir, "article.md")
	if err := os.WriteFile(doc, []byte("# Report\n\n## Security\n\nProse.\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := bundle.SaveManifest(doc, bundle.Manifest{BundleID: "AA", Profile: bundle.ProfileCanvas}); err != nil {
		t.Fatal(err)
	}
	statements := strings.Join([]string{
		"root = Col([mod])", "$x = 0",
		`mod = Source(["s1"], [Slider($x, 0, 1, 1, "State"), Svg([Path($x == 0 ? "M 0 0 L 1 1" : "M 0 0; javascript:alert(1)", $x == 0 ? "none" : "url(javascript:alert(1))")], "0 0 10 10", "Mechanism"), Link("Link", $x == 0 ? "https://example.com" : "javascript:alert(1)")])`,
	}, "\n")
	writeExportView(t, doc, statements, map[string]view.SourceRef{"s1": {Heading: "Security", Occurrence: 1}})
	out := filepath.Join(dir, "out.html")
	if _, err := Export(doc, out, ExportOptions{}); err != nil {
		t.Fatal(err)
	}
	data, _ := os.ReadFile(out)
	html := string(data)
	for _, banned := range []string{"url(javascript:", `d="M 0 0;`, `href="javascript:`} {
		if strings.Contains(html, banned) {
			t.Fatalf("unsafe reactive state survived as %q", banned)
		}
	}
	if !strings.Contains(html, `d="M 0 0 L 1 1"`) || !strings.Contains(html, `href="https://example.com"`) {
		t.Fatalf("safe default state was not preserved")
	}
}

func TestExportReactiveTemplateByteCapAndDefaultState(t *testing.T) {
	t.Run("128 KiB cap degrades", func(t *testing.T) {
		dir := t.TempDir()
		doc := filepath.Join(dir, "article.md")
		if err := os.WriteFile(doc, []byte("# Report\n\n## Large\n\nProse.\n"), 0o644); err != nil {
			t.Fatal(err)
		}
		if err := bundle.SaveManifest(doc, bundle.Manifest{BundleID: "AA", Profile: bundle.ProfileCanvas}); err != nil {
			t.Fatal(err)
		}
		huge := strings.Repeat("界", 45000)
		writeExportView(t, doc, "root = Col([mod])\n$x = 0\nmod = Source([\"s1\"], [Slider($x, 0, 1, 1), Text(\""+huge+"\")])", map[string]view.SourceRef{"s1": {Heading: "Large", Occurrence: 1}})
		result, err := Export(doc, filepath.Join(dir, "out.html"), ExportOptions{})
		if err != nil {
			t.Fatal(err)
		}
		if !strings.Contains(strings.Join(result.Warnings, " "), "REACTIVE_STATE_EXPLOSION") {
			t.Fatalf("missing template cap warning: %+v", result)
		}
	})

	t.Run("nonzero default and Set Reset actions", func(t *testing.T) {
		dir := t.TempDir()
		doc := filepath.Join(dir, "article.md")
		if err := os.WriteFile(doc, []byte("# Report\n\n## Action\n\nProse.\n"), 0o644); err != nil {
			t.Fatal(err)
		}
		if err := bundle.SaveManifest(doc, bundle.Manifest{BundleID: "AA", Profile: bundle.ProfileCanvas}); err != nil {
			t.Fatal(err)
		}
		writeExportView(t, doc, "root = Col([mod])\n$x = 0.5\nmod = Source([\"s1\"], [Slider($x, 0, 1, 0.1), Button(\"Set\", @Set($x, 0.8)), Button(\"Reset\", @Reset($x)), Text(@Format($x, \"number\", 1)), Text(@Now())])", map[string]view.SourceRef{"s1": {Heading: "Action", Occurrence: 1}})
		out := filepath.Join(dir, "out.html")
		result, err := Export(doc, out, ExportOptions{})
		if err != nil {
			t.Fatal(err)
		}
		data, _ := os.ReadFile(out)
		html := string(data)
		if !strings.Contains(html, "2026-01-02T03:04:05.000Z") {
			t.Fatalf("deterministic OpenUI clock was not used")
		}
		if result.IslandCount != 1 || !strings.Contains(html, `class="dr-island" data-island="c01-i1" data-state="5"`) || !strings.Contains(html, `data-island-transition=`) || !strings.Contains(html, `data-to="8"`) {
			t.Fatalf("default/action island state missing: %+v", result)
		}
		second := filepath.Join(dir, "second.html")
		if _, err := Export(doc, second, ExportOptions{}); err != nil {
			t.Fatal(err)
		}
		secondBytes, _ := os.ReadFile(second)
		if string(data) != string(secondBytes) {
			t.Fatal("reactive export is not deterministic")
		}
	})
}

func TestExportForExportSkipsEditorialHeuristicsAndMarginIsCompatible(t *testing.T) {
	dir := t.TempDir()
	doc := filepath.Join(dir, "article.md")
	raw := "# Report\n\n## Metrics\n\nProse.\n"
	if err := os.WriteFile(doc, []byte(raw), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := bundle.SaveManifest(doc, bundle.Manifest{BundleID: "AA", Profile: bundle.ProfileMargin}); err != nil {
		t.Fatal(err)
	}
	writeExportView(t, doc, "root = Col([mod])\nmod = Source([\"s1\"], [Title(\"Summary\"), Table([\"Metric\", \"Value\"], [[\"A\", 1]])])", map[string]view.SourceRef{"s1": {Heading: "Metrics", Occurrence: 1}})
	out := filepath.Join(dir, "margin.html")
	result, err := Export(doc, out, ExportOptions{Face: "margin"})
	if err != nil {
		t.Fatalf("ValidateForExport tripped editorial heuristics: %v", err)
	}
	data, _ := os.ReadFile(out)
	if result.Face != "margin" || strings.Contains(string(data), "<script") || strings.Contains(string(data), "min-width: 30rem") {
		t.Fatalf("margin compatibility/mobile table regression")
	}
}

func TestRenderAllChartTypes(t *testing.T) {
	lib, err := genuikit.NewLibrary(genuikit.Environment{})
	if err != nil {
		t.Fatal(err)
	}
	for _, kind := range []string{"bar", "line", "area", "pie", "donut", "scatter"} {
		t.Run(kind, func(t *testing.T) {
			program := lib.Parse(`root = Col([Chart("` + kind + `", [{x: 1, y: 2}, {x: 2, y: 4}], "x", ["y"], "number", false, 220, {y: "Value"})])`)
			session := openuilang.NewSession()
			session.Load(program)
			root, problems := session.Render()
			if root == nil || len(problems) > 0 {
				t.Fatalf("chart evaluation failed: %v", problems)
			}
			rendered, err := (&genuiRenderer{}).renderNode(root, false)
			needsSeriesLabel := kind != "pie" && kind != "donut"
			if err != nil || !strings.Contains(rendered, `class="dr-chart dr-chart-`+kind+`"`) || !strings.Contains(rendered, `role="img"`) || needsSeriesLabel && !strings.Contains(rendered, "Value") {
				t.Fatalf("chart %s did not render with labels/legend: %v", kind, err)
			}
		})
	}
}

func TestRenderAllCatalogComponents(t *testing.T) {
	expressions := map[string]string{
		"Col": `Col([Text("child")])`, "Row": `Row([Text("child")])`, "Box": `Box([Text("child")])`,
		"Grid": `Grid([Text("child")], 2)`, "Card": `Card([Text("child")])`, "Divider": `Divider()`, "Spacer": `Spacer()`,
		"Title": `Title("Title")`, "Text": `Text(["bold ", Text("child")])`, "Caption": `Caption("Caption")`,
		"Label": `Label("Label")`, "Badge": `Badge("Badge")`, "Link": `Link("Link", "https://example.com")`,
		"ListItem": `ListItem("Item")`, "List": `List(["One", "Two"], "number")`, "Markdown": `Markdown("**Body**")`,
		"Quote": `Quote("Quote")`, "Code": `Code("const x = 1", "js")`, "Source": `Source(["s1"], [Text("Grounded")])`,
		"Table": `Table(["Subject"], [["A"]])`, "Chart": `Chart("bar", [{x: "A", y: 1}], "x", ["y"])`,
		"Icon": `Icon("check-circle")`, "Image": `Image("https://example.com/a.png", "Alt")`,
		"Svg": `Svg([Circle(1, 1, 1)], "0 0 10 10", "Mechanism")`, "G": `G([Circle(1, 1, 1)])`,
		"Circle": `Circle(1, 1, 1)`, "Ellipse": `Ellipse(1, 1, 1, 1)`, "Rect": `Rect(0, 0, 1, 1)`,
		"Line": `Line(0, 0, 1, 1)`, "Path": `Path("M 0 0 L 1 1")`, "Polyline": `Polyline("0,0 1,1")`,
		"Polygon": `Polygon("0,0 1,1 1,0")`, "SvgText": `SvgText("Label", 0, 0)`, "Carousel": `Carousel([Card([Text("One")])])`,
		"Popover": `Popover(Button("Open"), Text("Contents"))`, "Button": `Button("Open")`,
		"IconButton": `IconButton("check-circle", null, "Open")`, "Pressable": `Pressable(Text("Open"))`,
		"Form": `Form([Input($text)])`, "Input": `Input($text)`, "TextArea": `TextArea($text)`,
		"Select": `Select($text, ["a"])`, "Checkbox": `Checkbox($checked, "Check")`,
		"RadioGroup": `RadioGroup($text, ["a"])`, "SegmentedControl": `SegmentedControl($text, ["a"])`,
		"Slider": `Slider($number, 0, 10, 1, "Amount")`, "DatePicker": `DatePicker($text)`,
		"Timer": `Timer($number)`, "Flashcard": `Flashcard("Front", "Back")`, "Celebration": `Celebration(true)`,
	}
	names := genuikit.ComponentNames()
	if len(names) != 50 || len(expressions) != 50 {
		t.Fatalf("catalog/test component counts = %d/%d", len(names), len(expressions))
	}
	lib, err := genuikit.NewLibrary(genuikit.Environment{Now: func() time.Time { return time.Unix(0, 0).UTC() }})
	if err != nil {
		t.Fatal(err)
	}
	for _, name := range names {
		t.Run(name, func(t *testing.T) {
			program := lib.Parse("$text = \"a\"\n$checked = false\n$number = 1\nroot = Col([" + expressions[name] + "])")
			session := openuilang.NewSession()
			session.Load(program)
			root, problems := session.Render()
			if root == nil || len(program.Errors) > 0 || len(problems) > 0 {
				t.Fatalf("parse/render errors: %v %v", program.Errors, problems)
			}
			html, err := (&genuiRenderer{}).renderNode(root, false)
			if err != nil || strings.TrimSpace(html) == "" || strings.Contains(html, "unsupported component") {
				t.Fatalf("component did not render cleanly: %q, %v", html, err)
			}
		})
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

func TestExportParagraphInterleavingHybridHeroAndBilingualImageAlignment(t *testing.T) {
	dir := t.TempDir()
	assetsDir := filepath.Join(dir, "assets")
	if err := os.MkdirAll(assetsDir, 0o755); err != nil {
		t.Fatal(err)
	}
	// Minimal 1x1 PNG.
	pngBytes := []byte{
		0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d,
		0x49, 0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
		0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53, 0xde, 0x00, 0x00, 0x00,
		0x0c, 0x49, 0x44, 0x41, 0x54, 0x08, 0xd7, 0x63, 0xf8, 0xcf, 0xc0, 0x00,
		0x00, 0x03, 0x01, 0x01, 0x00, 0x18, 0xdd, 0x8d, 0xb0, 0x00, 0x00, 0x00,
		0x00, 0x49, 0x45, 0x4e, 0x44, 0xae, 0x42, 0x60, 0x82,
	}
	if err := os.WriteFile(filepath.Join(assetsDir, "photo.png"), pngBytes, 0o644); err != nil {
		t.Fatal(err)
	}

	doc := filepath.Join(dir, "article.md")
	raw := strings.Join([]string{
		"Finance | Rates",
		"",
		"# Bond yields diverge",
		"",
		"### Why China moves opposite the rich world",
		"",
		"![](assets/photo.png)",
		"",
		"First paragraph introduces the global surge in sovereign yields.",
		"",
		"Second paragraph explains the domestic deflation mechanism in detail.",
		"",
		"Third paragraph concludes with investor positioning and outlook.",
	}, "\n") + "\n"
	if err := os.WriteFile(doc, []byte(raw), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := bundle.SetReaderConfig(doc, bundle.ReaderConfig{
		SourceLang: "en",
		TargetLang: "zh-CN",
		Mode:       bundle.ReadModeTranslated,
	}); err != nil {
		t.Fatal(err)
	}

	blocks, _, err := bundle.ExtractBlocksFromDoc(doc)
	if err != nil {
		t.Fatal(err)
	}
	var p1, p2 bundle.Block
	entries := make([]bundle.TranslationEntry, 0, len(blocks))
	for _, b := range blocks {
		tr := "译文：" + b.Text
		if strings.HasPrefix(b.Text, "First paragraph") {
			p1 = b
			tr = "第一段中文：全球主权债收益率飙升。"
		} else if strings.HasPrefix(b.Text, "Second paragraph") {
			p2 = b
			tr = "第二段中文：国内通缩机制详解。"
		} else if strings.HasPrefix(b.Text, "Third paragraph") {
			tr = "第三段中文：投资者仓位与展望。"
		}
		entries = append(entries, bundle.TranslationEntry{ID: b.ID, SourceHash: b.SourceHash, Text: tr})
	}
	if p1.ID == "" || p2.ID == "" {
		t.Fatalf("expected p1 and p2 blocks, got %+v", blocks)
	}
	if _, err := bundle.ApplyTranslations(doc, "zh-CN", entries); err != nil {
		t.Fatal(err)
	}

	statements := strings.Join([]string{
		`root = Col([overview, detail])`,
		`overview = Source(["s1"], [Chart("bar", [{k: "美债", v: 4.4}, {k: "中债", v: 2.1}], "k", ["v"], "percent", false, 180, {v: "10年期收益率"})])`,
		`detail = Source(["s1"], [Svg([Rect(10, 10, 120, 40, "surface"), SvgText("通缩传导", 70, 34)], "0 0 140 60", "机制图")])`,
	}, "\n")
	_, err = view.Write(doc, view.WriteOptions{
		StatementsText: statements,
		Sources:        map[string]view.SourceRef{"s1": {Heading: "Why China moves opposite the rich world", Occurrence: 1}},
		Citations: bundle.CitationMap{
			"overview": {"s1": {p1.ID}},
			"detail":   {"s1": {p2.ID}},
		},
	})
	if err != nil {
		t.Fatal(err)
	}

	// 1. Inline face: modules interleave right after their cited paragraphs (not bundled at the end)
	// and empty-alt image paragraph does not shift bilingual dr-orig-inline alignment.
	inlineOut := filepath.Join(dir, "inline.html")
	if _, err := Export(doc, inlineOut, ExportOptions{Face: "inline"}); err != nil {
		t.Fatalf("inline export failed: %v", err)
	}
	inlineHTMLBytes, err := os.ReadFile(inlineOut)
	if err != nil {
		t.Fatal(err)
	}
	inlineHTML := string(inlineHTMLBytes)
	posP1 := strings.Index(inlineHTML, "第一段中文：全球主权债收益率飙升。")
	posMod1 := strings.Index(inlineHTML, `id="c01-g-overview"`)
	posP2 := strings.Index(inlineHTML, "第二段中文：国内通缩机制详解。")
	posMod2 := strings.Index(inlineHTML, `id="c01-g-detail"`)
	posP3 := strings.Index(inlineHTML, "第三段中文：投资者仓位与展望。")
	if !(posP1 > 0 && posP1 < posMod1 && posMod1 < posP2 && posP2 < posMod2 && posMod2 < posP3) {
		t.Fatalf("expected paragraph-level interleaving p1(%d) < mod1(%d) < p2(%d) < mod2(%d) < p3(%d)", posP1, posMod1, posP2, posMod2, posP3)
	}
	wantAligned := `第一段中文：全球主权债收益率飙升。<span class="dr-orig-inline" lang="en">First paragraph introduces the global surge in sovereign yields.</span>`
	if !strings.Contains(inlineHTML, wantAligned) {
		t.Fatalf("bilingual inline alignment shifted after image paragraph; missing %q", wantAligned)
	}

	// 2. Hybrid face: first module elevated into masthead hero below H3 subtitle, before paragraph 1;
	// second module still interleaved right after paragraph 2 and before paragraph 3.
	hybridOut := filepath.Join(dir, "hybrid.html")
	hybridRes, err := Export(doc, hybridOut, ExportOptions{Face: "hybrid"})
	if err != nil {
		t.Fatalf("hybrid export failed: %v", err)
	}
	if hybridRes.Face != "hybrid" {
		t.Fatalf("hybrid face = %q, want hybrid", hybridRes.Face)
	}
	hybridHTMLBytes, err := os.ReadFile(hybridOut)
	if err != nil {
		t.Fatal(err)
	}
	hybridHTML := string(hybridHTMLBytes)
	hSub := strings.Index(hybridHTML, "译文：Why China moves opposite the rich world")
	hHero := strings.Index(hybridHTML, `class="dr-hybrid-hero"`)
	hP1 := strings.Index(hybridHTML, "第一段中文：全球主权债收益率飙升。")
	hP2 := strings.Index(hybridHTML, "第二段中文：国内通缩机制详解。")
	hMod2 := strings.Index(hybridHTML, `id="c01-g-detail"`)
	hP3 := strings.Index(hybridHTML, "第三段中文：投资者仓位与展望。")
	if !(hSub > 0 && hSub < hHero && hHero < hP1 && hP1 < hP2 && hP2 < hMod2 && hMod2 < hP3) {
		t.Fatalf("expected hybrid order sub(%d) < hero(%d) < p1(%d) < p2(%d) < mod2(%d) < p3(%d)", hSub, hHero, hP1, hP2, hMod2, hP3)
	}
}
