package main

import (
	"archive/zip"
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"deepread/internal/bundle"
	"deepread/internal/export"
	"deepread/internal/ingest"
	"deepread/internal/view"
)

// runCLI drives the full CLI in-process; no subprocess is spawned.
func runCLI(t *testing.T, stdin string, args ...string) (stdout, stderr string, code int) {
	t.Helper()
	var out, errOut bytes.Buffer
	code = run(strings.NewReader(stdin), args, &out, &errOut)
	return out.String(), errOut.String(), code
}

func mustRun(t *testing.T, stdin string, args ...string) string {
	t.Helper()
	out, errOut, code := runCLI(t, stdin, args...)
	if code != 0 {
		t.Fatalf("deepread %v exited %d\nstdout: %s\nstderr: %s", args, code, out, errOut)
	}
	return out
}

func decode[T any](t *testing.T, raw string) T {
	t.Helper()
	var value T
	if err := json.Unmarshal([]byte(raw), &value); err != nil {
		t.Fatalf("decode %q: %v", raw, err)
	}
	return value
}

func readFile(t *testing.T, path string) string {
	t.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read %s: %v", path, err)
	}
	return string(data)
}

// writeHeadinglessDoc writes a Markdown article with an H1 but no H2 sections,
// so the lifecycle test must start with `prepare` to create citation anchors.
func writeHeadinglessDoc(t *testing.T, dir string) string {
	t.Helper()
	doc := filepath.Join(dir, "grid.md")
	raw := strings.Join([]string{
		"# Why the Grid Strains",
		"",
		"Firm A reported $18B in 2024 cash capex; Firm B announced a $42B three-year commitment through 2026.",
		"",
		"US interconnection queues rose from 750 GW in 2020 to 2,600 GW in 2024.",
		"",
	}, "\n")
	if err := os.WriteFile(doc, []byte(raw), 0o644); err != nil {
		t.Fatal(err)
	}
	return doc
}

func TestCLIFullLifecycle(t *testing.T) {
	dir := t.TempDir()
	doc := writeHeadinglessDoc(t, dir)

	// 1. prepare — insert synthetic H2 anchors into a headingless article.
	breaks := `[{"beforeLine": 3, "title": "Capital Basis"}, {"beforeLine": 5, "title": "Grid Queues"}]`
	prepareResult := decode[bundle.PrepareResult](t, mustRun(t, breaks, "prepare", doc, "--breaks", "-"))
	if prepareResult.Inserted != 2 || len(prepareResult.SyntheticSections) != 2 {
		t.Fatalf("unexpected prepare result: %#v", prepareResult)
	}
	if prepareResult.SyntheticSections[0].Heading != "§1 · Capital Basis" ||
		prepareResult.SyntheticSections[1].Heading != "§2 · Grid Queues" {
		t.Fatalf("unexpected synthetic headings: %#v", prepareResult.SyntheticSections)
	}
	if prepareResult.BundleID == "" {
		t.Fatal("prepare did not report a bundleId")
	}

	// 2. inspect — line excerpt, then the exact section prose.
	lineReport := decode[bundle.InspectReport](t, mustRun(t, "", "inspect", doc, "--lines", "1:5"))
	if lineReport.Excerpt == nil {
		t.Fatal("inspect --lines did not return an excerpt")
	}
	if lineReport.Excerpt.StartLine != 1 || lineReport.Excerpt.EndLine != 5 {
		t.Fatalf("unexpected excerpt range: %#v", lineReport.Excerpt)
	}
	if !strings.Contains(lineReport.Excerpt.Text, "1: # Why the Grid Strains") {
		t.Fatalf("excerpt is not line-numbered: %q", lineReport.Excerpt.Text)
	}
	if len(lineReport.Sections) != 3 {
		t.Fatalf("expected H1 + 2 synthetic H2 sections, got %#v", lineReport.Sections)
	}
	for _, section := range lineReport.Sections[1:] {
		if !section.Synthetic {
			t.Fatalf("section %q was not flagged synthetic", section.Heading)
		}
	}
	if lineReport.ViewExists {
		t.Fatal("view must not exist before the first write")
	}

	sectionReport := decode[bundle.InspectReport](t, mustRun(t, "", "inspect", doc, "--heading", "§1 · Capital Basis"))
	if sectionReport.Excerpt == nil || !strings.Contains(sectionReport.Excerpt.Text, "$18B") {
		t.Fatalf("inspect --heading excerpt missing source figure: %#v", sectionReport.Excerpt)
	}

	// 3. catalog — the narrowed reading whitelist.
	catalog := mustRun(t, "", "catalog")
	for _, want := range []string{"Table(", "Chart(", "Quote(", "List(", "Source("} {
		if !strings.Contains(catalog, want) {
			t.Fatalf("catalog missing %q", want)
		}
	}
	for _, banned := range []string{"Card(", "Grid(", "Badge("} {
		if strings.Contains(catalog, banned) {
			t.Fatalf("catalog leaked banned component %q", banned)
		}
	}

	// 4. write — two modules, with flags deliberately placed before <doc.md>.
	statements := strings.Join([]string{
		`root = Col([capex_cmp, queue_chart])`,
		`capex_cmp = Source(["s1"], [Title("资本开支统计口径差异", "md"), Table(["主体", "口径", "原文数值"], [["Firm A", "2024 单年现金", "$18B"], ["Firm B", "三年累计承诺", "$42B"]]), Caption("依据原文 §1")])`,
		`queue_chart = Source(["s2"], [Title("并网队列容量（GW）", "md"), Chart("line", qdata, "year", ["gw"], "number", false, 200), Caption("数据取自原文 §2")])`,
		`qdata = [{year: "2020", gw: 750}, {year: "2024", gw: 2600}]`,
	}, "\n")
	writeResult := decode[view.WriteResult](t, mustRun(t, statements,
		"write", "--statements", "-", doc,
		"--source", "s1=§1 · Capital Basis#1",
		"--source", "s2=§2 · Grid Queues#1",
		"--model", "cli-test-model",
		"--request", "lifecycle",
	))
	if writeResult.Revision != 1 || writeResult.ModuleCount != 2 || len(writeResult.Modules) != 2 {
		t.Fatalf("unexpected write result: %#v", writeResult)
	}
	if writeResult.ViewHash == "" || writeResult.BundleID != prepareResult.BundleID {
		t.Fatalf("write did not report viewHash/bundleId: %#v", writeResult)
	}
	shortCodes := map[string]string{}
	for _, module := range writeResult.Modules {
		shortCodes[module.Statement] = module.ShortCode
		wantPrefix := writeResult.BundleID + "·" + module.Statement + "@r1"
		if module.ShortCode != wantPrefix {
			t.Fatalf("shortCode %q, want %q", module.ShortCode, wantPrefix)
		}
	}
	if shortCodes["capex_cmp"] == "" || shortCodes["queue_chart"] == "" {
		t.Fatalf("missing module short codes: %#v", writeResult.Modules)
	}

	// 5. export r1 — both modules, visible short codes, zero JavaScript.
	htmlPath := filepath.Join(dir, "grid.html")
	exportResult := decode[export.ExportResult](t, mustRun(t, "", "export", doc, "-o", htmlPath))
	if exportResult.ModuleCount != 2 || exportResult.Revision != 1 || exportResult.Bytes == 0 {
		t.Fatalf("unexpected export result: %#v", exportResult)
	}
	html := readFile(t, htmlPath)
	for _, want := range []string{
		shortCodes["capex_cmp"],
		shortCodes["queue_chart"],
		"$18B",
		"dr-module",
		"dr-chart",
		"<svg",
	} {
		if !strings.Contains(html, want) {
			t.Fatalf("exported HTML missing %q", want)
		}
	}
	if strings.Contains(strings.ToLower(html), "<script") {
		t.Fatal("exported HTML contains a <script> tag")
	}
	if strings.Contains(strings.ToLower(html), "javascript:") {
		t.Fatal("exported HTML contains a javascript: URL")
	}

	// 6. note add — record a reader note, then replay the same platform message.
	noteText := "这两家的口径不同，不应放在同一根坐标轴上"
	noteResult := decode[bundle.AddNoteResult](t, mustRun(t, "",
		"note", "add", doc, "--node", "queue_chart", "--msg-id", "m1", "--rev", "1", "--text", noteText))
	if noteResult.NoteID != "n1" || noteResult.Duplicate {
		t.Fatalf("unexpected note result: %#v", noteResult)
	}
	if noteResult.Node != "queue_chart" || noteResult.SectionHeading != "§2 · Grid Queues" {
		t.Fatalf("note did not resolve to its source section: %#v", noteResult)
	}
	if noteResult.BaseRev != 1 || noteResult.Text != noteText {
		t.Fatalf("note did not record revision/text verbatim: %#v", noteResult)
	}
	duplicate := decode[bundle.AddNoteResult](t, mustRun(t, "",
		"note", "add", doc, "--node", "capex_cmp", "--msg-id", "m1", "--text", "重放的消息"))
	if !duplicate.Duplicate || duplicate.NoteID != "n1" || duplicate.Text != noteText {
		t.Fatalf("duplicate --msg-id did not return the original note: %#v", duplicate)
	}

	// 7. inspect — one open note, and it targets the queue module.
	noteReport := decode[bundle.InspectReport](t, mustRun(t, "", "inspect", doc))
	if noteReport.Revision != 1 || !noteReport.ViewExists {
		t.Fatalf("unexpected pre-patch state: %#v", noteReport)
	}
	if noteReport.ViewHash != writeResult.ViewHash {
		t.Fatalf("inspect viewHash %q != write viewHash %q", noteReport.ViewHash, writeResult.ViewHash)
	}
	if len(noteReport.OpenNotes) != 1 || noteReport.OpenNotes[0].NoteID != "n1" {
		t.Fatalf("unexpected open notes: %#v", noteReport.OpenNotes)
	}
	if !containsString(noteReport.AffectedStatements, "queue_chart") {
		t.Fatalf("affectedStatements does not target queue_chart: %#v", noteReport.AffectedStatements)
	}

	// 8. patch — replace the noted module and resolve the note.
	replacement := `queue_chart = Source(["s2"], [Title("并网队列容量：750 GW 到 2,600 GW", "md"), Table(["年份", "待并网容量（GW）"], [["2020", "750"], ["2024", "2,600"]]), Caption("数据取自原文 §2")])`
	patchResult := decode[view.PatchResult](t, mustRun(t, replacement,
		"patch", doc,
		"--replace", "queue_chart",
		"--expect-hash", noteReport.ViewHash,
		"--statements", "-",
		"--resolve-note", "n1",
	))
	if patchResult.Revision != 2 || patchResult.ViewHash == noteReport.ViewHash {
		t.Fatalf("unexpected patch result: %#v", patchResult)
	}
	if len(patchResult.Replaced) != 1 || patchResult.Replaced[0] != "queue_chart" {
		t.Fatalf("patch replaced %v", patchResult.Replaced)
	}
	if len(patchResult.ResolvedNotes) != 1 || patchResult.ResolvedNotes[0] != "n1" {
		t.Fatalf("patch resolved %v", patchResult.ResolvedNotes)
	}

	// 9. inspect — the note is gone and the revision advanced.
	finalReport := decode[bundle.InspectReport](t, mustRun(t, "", "inspect", doc))
	if finalReport.Revision != 2 {
		t.Fatalf("revision = %d, want 2", finalReport.Revision)
	}
	if len(finalReport.OpenNotes) != 0 {
		t.Fatalf("openNotes not empty after resolve: %#v", finalReport.OpenNotes)
	}
	if len(finalReport.AffectedStatements) != 0 {
		t.Fatalf("affectedStatements not empty after resolve: %#v", finalReport.AffectedStatements)
	}
	if finalReport.ViewHash != patchResult.ViewHash {
		t.Fatalf("inspect viewHash %q != patch viewHash %q", finalReport.ViewHash, patchResult.ViewHash)
	}

	// 10. export r2 — the revised module renders with the r2 short code.
	htmlPath2 := filepath.Join(dir, "grid-r2.html")
	exportResult2 := decode[export.ExportResult](t, mustRun(t, "", "export", doc, "-o", htmlPath2, "--title", "Grid Strains"))
	if exportResult2.Revision != 2 || exportResult2.ModuleCount != 2 {
		t.Fatalf("unexpected r2 export result: %#v", exportResult2)
	}
	html2 := readFile(t, htmlPath2)
	for _, want := range []string{
		writeResult.BundleID + "·queue_chart@r2",
		writeResult.BundleID + "·capex_cmp@r2",
		"2,600",
		"<title>Grid Strains</title>",
	} {
		if !strings.Contains(html2, want) {
			t.Fatalf("r2 HTML missing %q", want)
		}
	}
	if strings.Contains(strings.ToLower(html2), "<script") {
		t.Fatal("r2 HTML contains a <script> tag")
	}
	if strings.Contains(html2, writeResult.BundleID+"·queue_chart@r1") {
		t.Fatal("r2 HTML still shows the r1 short code")
	}
}

func TestCLIExitCodes(t *testing.T) {
	dir := t.TempDir()
	doc := filepath.Join(dir, "article.md")
	raw := "# Grid\n\n## Alpha\n\nFirm A reported $18B in 2024.\n"
	if err := os.WriteFile(doc, []byte(raw), 0o644); err != nil {
		t.Fatal(err)
	}

	// Exit 2 — invalid CLI flags and missing required arguments.
	usageCases := [][]string{
		{},
		{"nope"},
		{"inspect"},
		{"inspect", doc, "--bogus"},
		{"inspect", doc, "--occurrence", "abc"},
		{"inspect", doc, "--lines", "9"},
		{"prepare", doc},
		{"write", doc},
		{"export", doc},
		{"patch", doc},
		{"note", "add", doc, "--text", "orphan"},
		{"note", "add", doc, "--node", "m", "--heading", "Alpha", "--text", "both"},
		{"note", "add", doc, "--node", "m"},
		{"ingest"},
		{"ingest", doc},
		{"export", doc, "--max-bytes", "0"},
		{"export", doc, "--max-image-bytes", "-5"},
	}
	for _, args := range usageCases {
		stdout, stderr, code := runCLI(t, "", args...)
		if code != 2 {
			t.Fatalf("deepread %v exited %d, want 2 (stderr: %s)", args, code, stderr)
		}
		if stdout != "" {
			t.Fatalf("deepread %v wrote to stdout on failure: %q", args, stdout)
		}
		body := decode[errorEnvelope](t, stderr)
		if body.Error.Code != "INVALID_ARGS" {
			t.Fatalf("deepread %v code %q, want INVALID_ARGS", args, body.Error.Code)
		}
	}

	// Exit 4 — not found.
	stdout, stderr, code := runCLI(t, "", "inspect", filepath.Join(dir, "missing.md"))
	if code != 4 {
		t.Fatalf("missing doc exited %d, want 4 (stderr: %s)", code, stderr)
	}
	if stdout != "" {
		t.Fatalf("missing doc wrote to stdout: %q", stdout)
	}
	if body := decode[errorEnvelope](t, stderr); body.Error.Code != "NOT_FOUND" {
		t.Fatalf("missing doc code %q, want NOT_FOUND", body.Error.Code)
	}

	// Exit 3 — guardrail rejections with a structured code and hint.
	rejections := []struct {
		name       string
		statements string
		wantCode   string
	}{
		{
			name:       "disallowed card component",
			statements: "root = Col([m])\nm = Source([\"s1\"], [Card([Table([\"A\"], [[\"1\"]])])])",
			wantCode:   "DISALLOWED_COMPONENT",
		},
		{
			name:       "cliché title",
			statements: "root = Col([m])\nm = Source([\"s1\"], [Title(\"Key Takeaways\", \"md\"), Quote(\"Firm A reported $18B in 2024.\", \"Alpha\")])",
			wantCode:   "CLICHE_TITLE_REJECTED",
		},
	}
	for _, tc := range rejections {
		t.Run(tc.name, func(t *testing.T) {
			stdout, stderr, code := runCLI(t, tc.statements, "write", doc, "--statements", "-", "--source", "s1=Alpha#1")
			if code != 3 {
				t.Fatalf("exited %d, want 3 (stdout: %s, stderr: %s)", code, stdout, stderr)
			}
			if stdout != "" {
				t.Fatalf("validation rejection wrote to stdout: %q", stdout)
			}
			body := decode[errorEnvelope](t, stderr)
			if body.Error.Code != tc.wantCode {
				t.Fatalf("code %q, want %q (message: %s)", body.Error.Code, tc.wantCode, body.Error.Message)
			}
			if body.Error.Statement != "m" {
				t.Fatalf("statement %q, want %q", body.Error.Statement, "m")
			}
			if body.Error.Hint == "" {
				t.Fatalf("validation rejection %q has no hint", tc.wantCode)
			}
		})
	}
	if _, err := os.Stat(bundle.ViewPath(doc)); !os.IsNotExist(err) {
		t.Fatalf("rejected writes created a sidecar: %v", err)
	}

	// Seed a committed view so conflict paths are reachable.
	seed := "root = Col([m])\nm = Source([\"s1\"], [Table([\"主体\", \"原文数值\"], [[\"Firm A\", \"$18B\"]]), Caption(\"依据原文 Alpha\")])"
	writeResult := decode[view.WriteResult](t, mustRun(t, seed, "write", doc, "--statements", "-", "--source", "s1=Alpha#1"))
	if writeResult.Revision != 1 {
		t.Fatalf("seed write revision = %d, want 1", writeResult.Revision)
	}

	// Exit 5 — stale --expect-hash on patch.
	stdout, stderr, code = runCLI(t,
		`m = Source(["s1"], [Table(["A"], [["1"]]), Caption("stale")])`,
		"patch", doc, "--replace", "m", "--expect-hash", strings.Repeat("0", 64), "--statements", "-")
	if code != 5 {
		t.Fatalf("stale patch hash exited %d, want 5 (stdout: %s, stderr: %s)", code, stdout, stderr)
	}
	if stdout != "" {
		t.Fatalf("stale patch wrote to stdout: %q", stdout)
	}
	conflict := decode[errorEnvelope](t, stderr)
	if conflict.Error.Code != "CONFLICT" || !strings.Contains(conflict.Error.Hint, "deepread inspect") {
		t.Fatalf("unexpected conflict payload: %#v", conflict.Error)
	}

	// Exit 5 — stale --rev on note add.
	stdout, stderr, code = runCLI(t, "", "note", "add", doc, "--node", "m", "--rev", "2", "--text", "stale note")
	if code != 5 {
		t.Fatalf("stale note revision exited %d, want 5 (stdout: %s, stderr: %s)", code, stdout, stderr)
	}
	if stdout != "" {
		t.Fatalf("stale note wrote to stdout: %q", stdout)
	}
	conflict = decode[errorEnvelope](t, stderr)
	if conflict.Error.Code != "CONFLICT" || !strings.Contains(conflict.Error.Hint, "deepread inspect") {
		t.Fatalf("unexpected conflict payload: %#v", conflict.Error)
	}
	if _, err := os.Stat(bundle.LedgerPath(doc)); !os.IsNotExist(err) {
		t.Fatalf("stale note created a ledger: %v", err)
	}

	// Exit 1 — unexpected runtime/I-O error.
	stdout, stderr, code = runCLI(t, "", "inspect", doc, "--lines", "900:1000")
	if code != 1 {
		t.Fatalf("out-of-range lines exited %d, want 1 (stderr: %s)", code, stderr)
	}
	if stdout != "" {
		t.Fatalf("runtime error wrote to stdout: %q", stdout)
	}
	if body := decode[errorEnvelope](t, stderr); body.Error.Code != "RUNTIME_ERROR" {
		t.Fatalf("runtime error code %q, want RUNTIME_ERROR", body.Error.Code)
	}
}

func TestCLIFlagOrderAndHelp(t *testing.T) {
	dir := t.TempDir()
	doc := writeHeadinglessDoc(t, dir)

	// Flags before, between, and after positionals all resolve the same way.
	breaks := `[{"beforeLine": 3, "title": "Only Section"}]`
	flagsFirst := decode[bundle.PrepareResult](t, mustRun(t, breaks, "prepare", "--breaks", "-", doc))
	if flagsFirst.Inserted != 1 || len(flagsFirst.SyntheticSections) != 1 {
		t.Fatalf("unexpected prepare result with flags-first ordering: %#v", flagsFirst)
	}

	// `--` stops flag parsing so a document named like a flag stays positional.
	report := decode[bundle.InspectReport](t, mustRun(t, "", "inspect", "--", doc))
	if report.DocPath != doc {
		t.Fatalf("`--` did not preserve the positional doc: %#v", report)
	}

	help := mustRun(t, "", "help")
	if !strings.Contains(help, "deepread") || !strings.Contains(help, "inspect") {
		t.Fatalf("unexpected help text: %q", help)
	}
	if version := strings.TrimSpace(mustRun(t, "", "--version")); version != "deepread "+cliVersion {
		t.Fatalf("unexpected version output: %q", version)
	}
	if out := mustRun(t, "", "catalog", "--help"); !strings.Contains(out, "Exit codes") {
		t.Fatalf("per-command --help did not print usage: %q", out)
	}
}

func containsString(values []string, want string) bool {
	for _, value := range values {
		if value == want {
			return true
		}
	}
	return false
}

// testPNG is a minimal PNG payload: ingestion and export sniff bytes, never
// the file name, so the marker plus a truncated IHDR is enough for both paths.
var testPNG = []byte{
	0x89, 'P', 'N', 'G', '\r', '\n', 0x1a, '\n',
	0, 0, 0, 13, 'I', 'H', 'D', 'R',
	0, 0, 0, 1, 0, 0, 0, 1, 8, 6, 0, 0, 0,
}

func TestCLIIngestMarkdownAndDualExport(t *testing.T) {
	srcDir := t.TempDir()
	if err := os.MkdirAll(filepath.Join(srcDir, "images"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(srcDir, "images", "cover.png"), testPNG, 0o644); err != nil {
		t.Fatal(err)
	}
	prose := strings.Join([]string{
		"# Why the Grid Strains",
		"",
		"## Interconnection queues",
		"",
		"Queues rose from 750 GW in 2020 to 2,600 GW in 2024.",
		"",
		"![Queue growth](images/cover.png \"Rising queues\")",
		"",
	}, "\n")
	src := filepath.Join(srcDir, "grid.md")
	if err := os.WriteFile(src, []byte(prose), 0o644); err != nil {
		t.Fatal(err)
	}

	// `-o` before the positional source resolves exactly like `--out` after it.
	outDir := filepath.Join(t.TempDir(), "bundle")
	ingested := decode[ingest.Result](t, mustRun(t, "", "ingest", "-o", outDir, src))
	if ingested.Kind != "markdown" || ingested.Title != "Why the Grid Strains" ||
		ingested.DocPath != "grid.md" || ingested.ImageCount != 1 || ingested.BundleID == "" {
		t.Fatalf("unexpected ingest result: %+v", ingested)
	}

	doc := filepath.Join(outDir, ingested.DocPath)
	rewritten := readFile(t, doc)
	if !strings.Contains(rewritten, "assets/cover.png") || strings.Contains(rewritten, "images/cover.png") {
		t.Fatalf("image reference was not rewritten to assets/:\n%s", rewritten)
	}
	if strings.Replace(rewritten, "assets/cover.png", "images/cover.png", 1) != prose {
		t.Fatalf("ingest rewrote prose beyond the image reference:\n%s", rewritten)
	}
	copiedAsset := filepath.Join(outDir, "assets", "cover.png")
	if data, err := os.ReadFile(copiedAsset); err != nil || !bytes.Equal(data, testPNG) {
		t.Fatalf("assets/cover.png = %v, want the source bytes (err: %v)", data, err)
	}
	if _, err := os.Stat(bundle.ManifestPath(doc)); err != nil {
		t.Fatalf("ingest did not create .deepread/manifest.json: %v", err)
	}
	manifest, found, err := bundle.LoadManifest(doc, []byte(rewritten))
	if err != nil || !found || manifest.BundleID != ingested.BundleID || manifest.DocID != "grid.md" {
		t.Fatalf("manifest = %+v found=%v err=%v", manifest, found, err)
	}

	// Inline export — images become base64 data URIs in a single HTML file.
	htmlPath := filepath.Join(outDir, "grid.html")
	inline := decode[export.ExportResult](t, mustRun(t, "", "export", doc, "-o", htmlPath))
	if inline.AssetMode != "inline" || inline.ImageCount != 1 || inline.Bytes == 0 {
		t.Fatalf("unexpected inline export result: %+v", inline)
	}
	inlineHTML := readFile(t, htmlPath)
	if !strings.Contains(inlineHTML, "data:image/png;base64,") {
		t.Fatal("inline export did not embed the image as a base64 data URI")
	}
	if !strings.Contains(inlineHTML, `content="default-src 'none'; style-src 'unsafe-inline'; img-src data:;"`) {
		t.Fatal("inline export did not declare the data-only image CSP")
	}

	// Over-budget inline export — exit 3 with a structured code and no output file.
	budgetPath := filepath.Join(outDir, "budget.html")
	stdout, stderr, code := runCLI(t, "", "export", doc, "-o", budgetPath, "--max-bytes", "100")
	if code != 3 {
		t.Fatalf("over-budget export exited %d, want 3 (stdout: %s, stderr: %s)", code, stdout, stderr)
	}
	if stdout != "" {
		t.Fatalf("over-budget export wrote to stdout: %q", stdout)
	}
	budget := decode[errorEnvelope](t, stderr)
	if budget.Error.Code != "ASSET_BUDGET_EXCEEDED" {
		t.Fatalf("over-budget code %q, want ASSET_BUDGET_EXCEEDED (message: %s)", budget.Error.Code, budget.Error.Message)
	}
	if !strings.Contains(budget.Error.Hint, "--external-assets") {
		t.Fatalf("over-budget hint does not name --external-assets: %q", budget.Error.Hint)
	}
	if _, err := os.Stat(budgetPath); !os.IsNotExist(err) {
		t.Fatalf("rejected export still wrote HTML: %v", err)
	}

	// External-asset export to another directory — relative assets plus a
	// `self`-allowing image CSP for HTTPS directory hosting.
	hostDir := filepath.Join(t.TempDir(), "host")
	hostPath := filepath.Join(hostDir, "grid.html")
	external := decode[export.ExportResult](t, mustRun(t, "", "export", "--external-assets", doc, "--out", hostPath))
	if external.AssetMode != "external" || external.ImageCount != 1 {
		t.Fatalf("unexpected external export result: %+v", external)
	}
	externalHTML := readFile(t, hostPath)
	if !strings.Contains(externalHTML, `content="default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:;"`) {
		t.Fatal("external export did not declare the self-allowing image CSP")
	}
	if !strings.Contains(externalHTML, `src="assets/cover.png"`) {
		t.Fatal("external export did not keep a relative asset reference")
	}
	if strings.Contains(externalHTML, "data:image/png;base64,") {
		t.Fatal("external export still inlined the image")
	}
	if data, err := os.ReadFile(filepath.Join(hostDir, "assets", "cover.png")); err != nil || !bytes.Equal(data, testPNG) {
		t.Fatalf("external assets/cover.png = %v, want the source bytes (err: %v)", data, err)
	}
}

// writeTestEPUB builds a minimal valid EPUB 3 with two chapters and one embedded
// PNG so the CLI can be driven through the real archive reader.
func writeTestEPUB(t *testing.T, dir string) string {
	t.Helper()
	var buf bytes.Buffer
	zw := zip.NewWriter(&buf)
	add := func(name string, data []byte) {
		t.Helper()
		w, err := zw.Create(name)
		if err != nil {
			t.Fatal(err)
		}
		if _, err := w.Write(data); err != nil {
			t.Fatal(err)
		}
	}
	add("mimetype", []byte("application/epub+zip"))
	add("META-INF/container.xml", []byte(`<?xml version="1.0"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>`))
	add("OEBPS/content.opf", []byte(`<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">urn:uuid:deepread-cli-test</dc:identifier>
    <dc:title>Synthetic Grid Book</dc:title>
    <dc:creator>CLI Test Author</dc:creator>
    <dc:language>en</dc:language>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
    <item id="ch2" href="ch2.xhtml" media-type="application/xhtml+xml"/>
    <item id="figure" href="images/figure.png" media-type="image/png"/>
  </manifest>
  <spine><itemref idref="ch1"/><itemref idref="ch2"/></spine>
</package>`))
	add("OEBPS/nav.xhtml", []byte(`<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><body><nav epub:type="toc"><ol><li><a href="ch1.xhtml">Opening Chapter</a></li><li><a href="ch2.xhtml">Second Chapter</a></li></ol></nav></body></html>`))
	add("OEBPS/ch1.xhtml", []byte(`<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Document fallback one</title></head><body><p>This opening chapter contains enough thoughtful words to remain a real chapter in the finished book.</p><p><img src="images/figure.png" alt="Grid figure"/></p></body></html>`))
	add("OEBPS/ch2.xhtml", []byte(`<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Document fallback two</title></head><body><p>The second chapter also has ample prose so that its distinct contents title can be verified properly.</p></body></html>`))
	add("OEBPS/images/figure.png", testPNG)
	if err := zw.Close(); err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(dir, "book.epub")
	if err := os.WriteFile(path, buf.Bytes(), 0o644); err != nil {
		t.Fatal(err)
	}
	return path
}

func TestCLIIngestEPUBTwoPhase(t *testing.T) {
	book := writeTestEPUB(t, t.TempDir())
	outDir := filepath.Join(t.TempDir(), "book")

	result := decode[ingest.Result](t, mustRun(t, "", "ingest", book, "-o", outDir))
	if result.Kind != "epub" || result.Title != "Synthetic Grid Book" || result.Author != "CLI Test Author" {
		t.Fatalf("unexpected EPUB ingest result: %+v", result)
	}
	if result.IndexPath != "index.md" || result.BookJSON != "book.json" {
		t.Fatalf("EPUB ingest did not report index/book paths: %+v", result)
	}
	if len(result.Chapters) != 2 || result.ImageCount != 1 {
		t.Fatalf("EPUB ingest chapters/images = %d/%d, want 2/1", len(result.Chapters), result.ImageCount)
	}
	wantPaths := []string{"chapters/01-opening-chapter/chapter.md", "chapters/02-second-chapter/chapter.md"}
	for i, wantPath := range wantPaths {
		chapter := result.Chapters[i]
		if chapter.DocPath != wantPath {
			t.Fatalf("chapter %d docPath = %q, want %q", i+1, chapter.DocPath, wantPath)
		}
		if chapter.BundleID == "" || chapter.Index != i+1 {
			t.Fatalf("chapter %d metadata incomplete: %+v", i+1, chapter)
		}
		doc := filepath.Join(outDir, filepath.FromSlash(wantPath))
		if _, err := os.Stat(doc); err != nil {
			t.Fatalf("chapter %d document missing: %v", i+1, err)
		}
		if _, err := os.Stat(bundle.ManifestPath(doc)); err != nil {
			t.Fatalf("chapter %d is not an isolated bundle: %v", i+1, err)
		}
	}
	if data, err := os.ReadFile(filepath.Join(outDir, filepath.FromSlash("chapters/01-opening-chapter/assets/figure.png"))); err != nil || !bytes.Equal(data, testPNG) {
		t.Fatalf("chapter image = %v, want the embedded bytes (err: %v)", data, err)
	}

	index := readFile(t, filepath.Join(outDir, "index.md"))
	for _, want := range []string{"# Synthetic Grid Book", "CLI Test Author", wantPaths[0], wantPaths[1]} {
		if !strings.Contains(index, want) {
			t.Fatalf("index.md missing %q:\n%s", want, index)
		}
	}
	persisted := decode[ingest.Result](t, readFile(t, filepath.Join(outDir, "book.json")))
	if persisted.Title != result.Title || len(persisted.Chapters) != 2 {
		t.Fatalf("book.json differs from the CLI result: %+v", persisted)
	}
	for _, want := range []string{wantPaths[0], wantPaths[1]} {
		if !strings.Contains(readFile(t, filepath.Join(outDir, "book.json")), want) {
			t.Fatalf("book.json does not list chapter %q", want)
		}
	}

	// Two-phase reading: each chapter is its own single-doc bundle, so `inspect`
	// runs on exactly one requested chapter at a time and never reports a
	// document/bundle mismatch.
	for _, chapter := range result.Chapters {
		doc := filepath.Join(outDir, filepath.FromSlash(chapter.DocPath))
		stdout, stderr, code := runCLI(t, "", "inspect", doc)
		if code != 0 {
			t.Fatalf("inspect %s exited %d (stdout: %s, stderr: %s)", chapter.DocPath, code, stdout, stderr)
		}
		if stderr != "" {
			t.Fatalf("inspect %s wrote to stderr: %q", chapter.DocPath, stderr)
		}
		report := decode[bundle.InspectReport](t, stdout)
		if report.BundleID != chapter.BundleID || report.DocPath != doc {
			t.Fatalf("inspect %s bundle = %q docPath = %q, want %q / %q",
				chapter.DocPath, report.BundleID, report.DocPath, chapter.BundleID, doc)
		}
		if len(report.Sections) == 0 {
			t.Fatalf("inspect %s found no sections", chapter.DocPath)
		}
		if report.Revision != 0 || report.ViewExists {
			t.Fatalf("inspect %s should be pristine before any write: %+v", chapter.DocPath, report)
		}
	}
}

func TestCLIIngestUnsupportedFormatExit2(t *testing.T) {
	dir := t.TempDir()
	for _, name := range []string{"report.docx", "paper.pdf"} {
		src := filepath.Join(dir, name)
		if err := os.WriteFile(src, []byte("not a supported deepread source"), 0o644); err != nil {
			t.Fatal(err)
		}
		outDir := filepath.Join(dir, strings.TrimSuffix(name, filepath.Ext(name))+"-out")
		stdout, stderr, code := runCLI(t, "", "ingest", src, "-o", outDir)
		if code != 2 {
			t.Fatalf("ingest %s exited %d, want 2 (stdout: %s, stderr: %s)", name, code, stdout, stderr)
		}
		if stdout != "" {
			t.Fatalf("ingest %s wrote to stdout on failure: %q", name, stdout)
		}
		body := decode[errorEnvelope](t, stderr)
		if body.Error.Code != "INVALID_ARGS" {
			t.Fatalf("ingest %s code %q, want INVALID_ARGS", name, body.Error.Code)
		}
		if !strings.Contains(body.Error.Hint, ".epub") || !strings.Contains(body.Error.Hint, ".md") {
			t.Fatalf("ingest %s hint does not list the supported formats: %q", name, body.Error.Hint)
		}
		if _, err := os.Stat(outDir); !os.IsNotExist(err) {
			t.Fatalf("rejected ingest %s created %q: %v", name, outDir, err)
		}
	}
}
