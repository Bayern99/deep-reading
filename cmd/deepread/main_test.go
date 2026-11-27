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

func findBlock(t *testing.T, blocks []bundle.Block, prefix string) bundle.Block {
	t.Helper()
	for _, block := range blocks {
		if strings.HasPrefix(block.Text, prefix) {
			return block
		}
	}
	t.Fatalf("no block starts with %q in %#v", prefix, blocks)
	return bundle.Block{}
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

	// 2. blocks — every translatable unit, with a stable block id + source hash.
	blockReport := decode[blocksReport](t, mustRun(t, "", "blocks", doc))
	if blockReport.DocPath != doc || blockReport.BundleID != prepareResult.BundleID {
		t.Fatalf("blocks did not report the bundle: %#v", blockReport)
	}
	if blockReport.TotalBlocks != 3 || len(blockReport.Blocks) != 3 {
		t.Fatalf("blocks = %d/%d, want 3 (H1 + 2 paragraphs; synthetic anchors are not units): %#v",
			blockReport.TotalBlocks, len(blockReport.Blocks), blockReport.Blocks)
	}
	capexBlock := findBlock(t, blockReport.Blocks, "Firm A reported $18B")
	queueBlock := findBlock(t, blockReport.Blocks, "US interconnection queues rose")
	if capexBlock.ID == "" || capexBlock.SourceHash == "" || capexBlock.SectionHeading != "§1 · Capital Basis" {
		t.Fatalf("unexpected capex block: %#v", capexBlock)
	}
	if queueBlock.SectionHeading != "§2 · Grid Queues" {
		t.Fatalf("unexpected queue block: %#v", queueBlock)
	}

	// 3. inspect — line excerpt, then the exact section prose.
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
	if lineReport.Translation != nil {
		t.Fatalf("original-mode bundle must not report a translation layer: %#v", lineReport.Translation)
	}

	sectionReport := decode[bundle.InspectReport](t, mustRun(t, "", "inspect", doc, "--heading", "§1 · Capital Basis"))
	if sectionReport.Excerpt == nil || !strings.Contains(sectionReport.Excerpt.Text, "$18B") {
		t.Fatalf("inspect --heading excerpt missing source figure: %#v", sectionReport.Excerpt)
	}

	// 4. catalog — the default canvas contract (50 components) and the legacy margin subset.
	canvas := mustRun(t, "", "catalog")
	for _, want := range []string{"Col(", "Source(", "Table(", "Chart(", "Quote(", "List(", "Svg(", "Grid(", "Card(", "Row(", "Slider(", "SegmentedControl("} {
		if !strings.Contains(canvas, want) {
			t.Fatalf("canvas catalog missing %q", want)
		}
	}
	margin := mustRun(t, "", "catalog", "--profile", "margin")
	if !strings.Contains(margin, "--profile margin") && !strings.Contains(margin, "10 Static Reading Primitives") {
		t.Fatalf("margin catalog is not the legacy 10-primitive contract:\n%s", margin)
	}
	for _, want := range []string{"Table(", "Chart(", "Quote(", "List(", "Source(", "Caption("} {
		if !strings.Contains(margin, want) {
			t.Fatalf("margin catalog missing %q", want)
		}
	}
	for _, banned := range []string{"Card(", "Grid(", "Badge(", "Slider("} {
		if strings.Contains(margin, banned) {
			t.Fatalf("margin catalog leaked banned component %q", banned)
		}
	}

	// 5. write — a canvas view (Row/Card/Grid/Svg/Chart) with exact citations.
	statements := strings.Join([]string{
		`root = Col([head, capex_cmp, queue_mechanism])`,
		`head = Row([Title("资本开支口径与并网排队机制", "xl"), Badge("原文保真", "info")], 2)`,
		`capex_cmp = Source(["s1"], [Grid([Card([Title("Firm A", "md"), Text("2024 单年现金支出", "sm"), Badge("$18B")]), Card([Title("Firm B", "md"), Text("三年累计承诺", "sm"), Badge("$42B")])], 2, 200, 3), Caption("依据原文 §1")])`,
		`queue_mechanism = Source(["s2"], [Svg([Rect(5, 10, 30, 20, "surface"), Path("M 35 20 L 60 20", null, "info", 2), Circle(70, 20, 10, "warning"), SvgText("Queue", 15, 25)], "0 0 100 50", "项目进入受限并网队列"), Chart("line", qdata, "year", ["gw"], "number", false, 200, {gw: "待并网容量 (GW)"})])`,
		`qdata = [{year: "2020", gw: 750}, {year: "2024", gw: 2600}]`,
	}, "\n")
	writeResult := decode[view.WriteResult](t, mustRun(t, statements,
		"write", "--statements", "-", doc,
		"--source", "s1=§1 · Capital Basis#1",
		"--source", "s2=§2 · Grid Queues#1",
		"--cite", "capex_cmp:s1="+capexBlock.ID,
		"--cite", "queue_mechanism:s2="+queueBlock.ID,
		"--model", "cli-test-model",
		"--request", "lifecycle",
	))
	if writeResult.Revision != 1 || writeResult.ModuleCount != 2 || len(writeResult.Modules) != 2 {
		t.Fatalf("unexpected write result: %#v", writeResult)
	}
	if writeResult.ViewHash == "" || writeResult.BundleID != prepareResult.BundleID {
		t.Fatalf("write did not report viewHash/bundleId: %#v", writeResult)
	}
	if citations, err := bundle.LoadCitations(doc); err != nil || len(citations["capex_cmp"]["s1"]) != 1 {
		t.Fatalf("citations were not persisted: %#v err=%v", citations, err)
	}
	shortCodes := map[string]string{}
	for _, module := range writeResult.Modules {
		shortCodes[module.Statement] = module.ShortCode
		wantPrefix := writeResult.BundleID + "·" + module.Statement + "@r1"
		if module.ShortCode != wantPrefix {
			t.Fatalf("shortCode %q, want %q", module.ShortCode, wantPrefix)
		}
	}
	if shortCodes["capex_cmp"] == "" || shortCodes["queue_mechanism"] == "" {
		t.Fatalf("missing module short codes: %#v", writeResult.Modules)
	}

	// 6. export r1 — dual-face full-information structured reader by default, both modules, exact citation anchors.
	htmlPath := filepath.Join(dir, "grid.html")
	exportResult := decode[export.ExportResult](t, mustRun(t, "", "export", doc, "-o", htmlPath))
	if exportResult.ModuleCount != 2 || exportResult.Revision != 1 || exportResult.Bytes == 0 {
		t.Fatalf("unexpected export result: %#v", exportResult)
	}
	if exportResult.Face != "dual" || exportResult.ChapterCount != 1 {
		t.Fatalf("default export must be the dual face: %#v", exportResult)
	}
	html := readFile(t, htmlPath)
	for _, want := range []string{
		shortCodes["capex_cmp"],
		shortCodes["queue_mechanism"],
		"$18B",
		"dr-module",
		"dr-chart",
		"<svg",
		`data-face="dual"`,
		`data-face-target="genui"`,
		"查看原文 ↗",
		`id="c01-` + capexBlock.ID + `"`,
		`data-jump-target="#c01-` + capexBlock.ID + `"`,
		`<script>`,
	} {
		if !strings.Contains(html, want) {
			t.Fatalf("exported HTML missing %q", want)
		}
	}
	// The only script is the constant island runtime, pinned by a SHA-256 CSP hash.
	if got := strings.Count(html, "<script>"); got != 1 {
		t.Fatalf("exported HTML has %d scripts, want exactly 1 runtime", got)
	}
	if !strings.Contains(html, "script-src 'sha256-") {
		t.Fatal("runtime script is not pinned by a SHA-256 CSP hash")
	}
	if strings.Contains(strings.ToLower(html), "javascript:") {
		t.Fatal("exported HTML contains a javascript: URL")
	}

	// 7. note add — record a reader note, then replay the same platform message.
	noteText := "这两家的口径不同，不应放在同一根坐标轴上"
	noteResult := decode[bundle.AddNoteResult](t, mustRun(t, "",
		"note", "add", doc, "--node", "queue_mechanism", "--msg-id", "m1", "--rev", "1", "--text", noteText))
	if noteResult.NoteID != "n1" || noteResult.Duplicate {
		t.Fatalf("unexpected note result: %#v", noteResult)
	}
	if noteResult.Node != "queue_mechanism" || noteResult.SectionHeading != "§2 · Grid Queues" {
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

	// 8. inspect — one open note, and it targets the queue module.
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
	if !containsString(noteReport.AffectedStatements, "queue_mechanism") {
		t.Fatalf("affectedStatements does not target queue_mechanism: %#v", noteReport.AffectedStatements)
	}

	// 9. patch — replace the noted module and resolve the note.
	replacement := `queue_mechanism = Source(["s2"], [Title("并网队列：750 GW → 2,600 GW", "md"), List([ListItem("2020", "待并网容量 750 GW", "2020"), ListItem("2024", "待并网容量 2,600 GW", "2024")], "none", true), Caption("数据取自原文 §2")])`
	patchResult := decode[view.PatchResult](t, mustRun(t, replacement,
		"patch", doc,
		"--replace", "queue_mechanism",
		"--expect-hash", noteReport.ViewHash,
		"--statements", "-",
		"--resolve-note", "n1",
	))
	if patchResult.Revision != 2 || patchResult.ViewHash == noteReport.ViewHash {
		t.Fatalf("unexpected patch result: %#v", patchResult)
	}
	if len(patchResult.Replaced) != 1 || patchResult.Replaced[0] != "queue_mechanism" {
		t.Fatalf("patch replaced %v", patchResult.Replaced)
	}
	if len(patchResult.ResolvedNotes) != 1 || patchResult.ResolvedNotes[0] != "n1" {
		t.Fatalf("patch resolved %v", patchResult.ResolvedNotes)
	}

	// 10. inspect — the note is gone and the revision advanced.
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

	// 11. export r2 — the revised module renders with the r2 short code.
	htmlPath2 := filepath.Join(dir, "grid-r2.html")
	exportResult2 := decode[export.ExportResult](t, mustRun(t, "", "export", doc, "-o", htmlPath2, "--title", "Grid Strains"))
	if exportResult2.Revision != 2 || exportResult2.ModuleCount != 2 {
		t.Fatalf("unexpected r2 export result: %#v", exportResult2)
	}
	html2 := readFile(t, htmlPath2)
	for _, want := range []string{
		writeResult.BundleID + "·queue_mechanism@r2",
		writeResult.BundleID + "·capex_cmp@r2",
		"2,600",
		"<title>Grid Strains</title>",
	} {
		if !strings.Contains(html2, want) {
			t.Fatalf("r2 HTML missing %q", want)
		}
	}
	if strings.Contains(html2, writeResult.BundleID+"·queue_mechanism@r1") {
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
		{"export", doc, "--face", "purple"},
		{"export", doc, "--lang", "not a tag"},
		{"export", doc, "--mode", "sparse"},
		{"export", doc, "--chapters", "1"},
		{"export", "--book", dir, doc},
		{"patch", doc},
		{"note", "add", doc, "--text", "orphan"},
		{"note", "add", doc, "--node", "m", "--heading", "Alpha", "--text", "both"},
		{"note", "add", doc, "--node", "m"},
		{"ingest"},
		{"ingest", doc},
		{"ingest", doc, "-o", filepath.Join(dir, "bad-mode"), "--mode", "summary"},
		{"ingest", doc, "-o", filepath.Join(dir, "bad-lang"), "--lang", "!!"},
		{"blocks"},
		{"translate", doc, "--lang", "zh-CN"},
		{"translate", doc, "--input", "-"},
		{"translate", doc, "--lang", "zh CN", "--input", "-"},
		{"catalog", "--profile", "purple"},
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
		extra      []string
		wantCode   string
		wantStmt   string
	}{
		{
			name:       "card rejected in margin profile",
			statements: "root = Col([m])\nm = Source([\"s1\"], [Card([Table([\"A\"], [[\"1\"]])])])",
			extra:      []string{"--profile", "margin"},
			wantCode:   "DISALLOWED_COMPONENT",
			wantStmt:   "m",
		},
		{
			name:       "generic key-value table rejected on canvas",
			statements: "root = Col([m])\nm = Source([\"s1\"], [Table([\"指标\", \"数值\"], [[\"Capex\", \"$18B\"]])])",
			wantCode:   "GENERIC_KV_TABLE",
			wantStmt:   "m",
		},
		{
			name:       "cliché title",
			statements: "root = Col([m])\nm = Source([\"s1\"], [Title(\"Key Takeaways\", \"md\"), Quote(\"Firm A reported $18B in 2024.\", \"Alpha\")])",
			wantCode:   "CLICHE_TITLE_REJECTED",
			wantStmt:   "m",
		},
	}
	for _, tc := range rejections {
		t.Run(tc.name, func(t *testing.T) {
			args := append([]string{"write", doc, "--statements", "-", "--source", "s1=Alpha#1"}, tc.extra...)
			stdout, stderr, code := runCLI(t, tc.statements, args...)
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
			if body.Error.Statement != tc.wantStmt {
				t.Fatalf("statement %q, want %q", body.Error.Statement, tc.wantStmt)
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
	for _, command := range []string{"ingest", "inspect", "prepare", "catalog", "blocks", "write", "translate", "note add", "patch", "export"} {
		if !strings.Contains(help, command) {
			t.Fatalf("help text does not document %q", command)
		}
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
	if ingested.Reader != nil {
		t.Fatalf("ingest without --lang must not record a reading contract: %+v", ingested.Reader)
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

	// One unified offline HTML for the whole (selected) book — never one file per chapter.
	readerPath := filepath.Join(t.TempDir(), "grid-book.html")
	unified := decode[export.ExportResult](t, mustRun(t, "", "export", "--book", outDir, "--chapters", "1,2", "-o", readerPath))
	if unified.ChapterCount != 2 || unified.Bytes == 0 {
		t.Fatalf("unexpected book export result: %+v", unified)
	}
	unifiedHTML := readFile(t, readerPath)
	for _, want := range []string{
		`data-chapter="c01"`,
		`data-chapter="c02"`,
		"<title>Synthetic Grid Book</title>",
		"Opening Chapter",
		"Second Chapter",
		"data-chapter-link",
	} {
		if !strings.Contains(unifiedHTML, want) {
			t.Fatalf("unified book HTML missing %q", want)
		}
	}
	if _, err := os.Stat(filepath.Join(outDir, "chapters", "01-opening-chapter", "chapter.html")); !os.IsNotExist(err) {
		t.Fatalf("book export must not write per-chapter HTML: %v", err)
	}

	// A single chapter selector keeps just that chapter in the same file.
	singlePath := filepath.Join(t.TempDir(), "chapter-two.html")
	single := decode[export.ExportResult](t, mustRun(t, "", "export", "--book", outDir, "--chapters", "2", "-o", singlePath))
	if single.ChapterCount != 1 {
		t.Fatalf("chapter selector did not narrow the export: %+v", single)
	}
	singleHTML := readFile(t, singlePath)
	if !strings.Contains(singleHTML, `data-chapter="c01"`) || strings.Contains(singleHTML, `data-chapter="c02"`) {
		t.Fatalf("selected chapter was not the only rendered chapter")
	}
	if !strings.Contains(singleHTML, "Second Chapter") {
		t.Fatal("selected chapter lost its title")
	}

	// Unknown selectors are usage-independent failures (exit 1) and write nothing.
	stdout, stderr, code := runCLI(t, "", "export", "--book", outDir, "--chapters", "9", "-o", filepath.Join(t.TempDir(), "x.html"))
	if code != 1 {
		t.Fatalf("unknown chapter selector exited %d, want 1 (stdout: %s, stderr: %s)", code, stdout, stderr)
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

// writeTranslatableArticle writes an English article whose chosen target
// language is Chinese, so the whole v0.3 translation workflow is exercised.
func writeTranslatableArticle(t *testing.T, dir string) string {
	t.Helper()
	doc := filepath.Join(dir, "grid.md")
	raw := strings.Join([]string{
		"# Why the Grid Strains",
		"",
		"## Interconnection queues",
		"",
		"Queues rose from 750 GW in 2020 to 2,600 GW in 2024.",
		"",
		"## Capital basis",
		"",
		"Firm A reported $18B in 2024 cash capex; Firm B announced a $42B three-year commitment through 2026.",
		"",
	}, "\n")
	if err := os.WriteFile(doc, []byte(raw), 0o644); err != nil {
		t.Fatal(err)
	}
	return doc
}

func TestCLITranslationWorkflow(t *testing.T) {
	srcDir := t.TempDir()
	src := writeTranslatableArticle(t, srcDir)
	outDir := filepath.Join(t.TempDir(), "bundle")

	// 1. ingest with an explicit reading contract — --lang alone implies translated.
	ingested := decode[ingest.Result](t, mustRun(t, "", "ingest", src, "-o", outDir, "--lang", "zh-cn", "--source-lang", "en"))
	if ingested.Reader == nil || ingested.Reader.TargetLang != "zh-CN" || ingested.Reader.SourceLang != "en" || ingested.Reader.Mode != bundle.ReadModeTranslated {
		t.Fatalf("ingest did not record the translated contract: %+v", ingested.Reader)
	}
	doc := filepath.Join(outDir, ingested.DocPath)

	// 2. blocks — the live translation units.
	blockReport := decode[blocksReport](t, mustRun(t, "", "blocks", doc))
	// H1 + two H2 headings + two body paragraphs.
	if blockReport.TotalBlocks != 5 || len(blockReport.Blocks) != 5 {
		t.Fatalf("blocks = %d/%d, want 5: %#v", blockReport.TotalBlocks, len(blockReport.Blocks), blockReport.Blocks)
	}
	queueBlock := findBlock(t, blockReport.Blocks, "Queues rose from 750 GW")
	capexBlock := findBlock(t, blockReport.Blocks, "Firm A reported $18B")

	// 3. inspect reports zero coverage before any translation.
	initial := decode[bundle.InspectReport](t, mustRun(t, "", "inspect", doc))
	if initial.Reader == nil || initial.Reader.Mode != bundle.ReadModeTranslated {
		t.Fatalf("inspect lost the reading contract: %#v", initial.Reader)
	}
	if initial.Translation == nil || initial.Translation.CoveragePct != 0 || initial.Translation.TotalBlocks != 5 {
		t.Fatalf("unexpected initial translation status: %#v", initial.Translation)
	}

	// 4. exporting a translated bundle before translating is a structured exit 3.
	earlyPath := filepath.Join(outDir, "early.html")
	stdout, stderr, code := runCLI(t, "", "export", doc, "-o", earlyPath)
	if code != 3 {
		t.Fatalf("incomplete translation export exited %d, want 3 (stdout: %s, stderr: %s)", code, stdout, stderr)
	}
	if stdout != "" {
		t.Fatalf("incomplete translation export wrote to stdout: %q", stdout)
	}
	incomplete := decode[errorEnvelope](t, stderr)
	if incomplete.Error.Code != "TRANSLATION_INCOMPLETE" {
		t.Fatalf("code %q, want TRANSLATION_INCOMPLETE", incomplete.Error.Code)
	}
	if !strings.Contains(incomplete.Error.Message, "missing=[") || !strings.Contains(incomplete.Error.Message, queueBlock.ID) {
		t.Fatalf("incomplete message does not name the missing block ids: %q", incomplete.Error.Message)
	}
	if incomplete.Error.Hint == "" {
		t.Fatal("incomplete translation error has no hint")
	}
	if _, err := os.Stat(earlyPath); !os.IsNotExist(err) {
		t.Fatalf("rejected export still wrote HTML: %v", err)
	}

	// 5. a stale source hash is a compare-and-swap conflict (exit 5).
	stale := `[{"id":"` + queueBlock.ID + `","sourceHash":"deadbeef","text":"译文"}]`
	stdout, stderr, code = runCLI(t, stale, "translate", doc, "--lang", "zh-CN", "--input", "-")
	if code != 5 {
		t.Fatalf("stale translation hash exited %d, want 5 (stdout: %s, stderr: %s)", code, stdout, stderr)
	}
	if body := decode[errorEnvelope](t, stderr); body.Error.Code != "CONFLICT" {
		t.Fatalf("stale translation hash code %q, want CONFLICT", body.Error.Code)
	}

	// 6. unknown blocks and unsafe text are validation rejections (exit 3).
	for _, tc := range []struct {
		name  string
		entry string
	}{
		{"unknown block", `[{"id":"bdeadbeef","text":"译文"}]`},
		{"empty text", `[{"id":"` + queueBlock.ID + `","sourceHash":"` + queueBlock.SourceHash + `","text":"   "}]`},
		{"raw script", `[{"id":"` + queueBlock.ID + `","sourceHash":"` + queueBlock.SourceHash + `","text":"<script>alert(1)</script>"}]`},
	} {
		stdout, stderr, code = runCLI(t, tc.entry, "translate", doc, "--lang", "zh-CN", "--input", "-")
		if code != 3 {
			t.Fatalf("%s exited %d, want 3 (stdout: %s, stderr: %s)", tc.name, code, stdout, stderr)
		}
		body := decode[errorEnvelope](t, stderr)
		if body.Error.Code != "VALIDATION_FAILED" || body.Error.Hint == "" {
			t.Fatalf("%s payload = %#v", tc.name, body.Error)
		}
	}

	// 7. JSONL input translates the article + section headings in one batch.
	var jsonl strings.Builder
	for _, block := range blockReport.Blocks {
		entry, err := json.Marshal(bundle.TranslationEntry{ID: block.ID, SourceHash: block.SourceHash, Text: "中译：" + block.Text})
		if err != nil {
			t.Fatal(err)
		}
		jsonl.Write(entry)
		jsonl.WriteString("\n")
	}
	jsonlStatus := decode[bundle.TranslationStatus](t, mustRun(t, jsonl.String(), "translate", doc, "--lang", "zh-CN", "--input", "-"))
	if jsonlStatus.CoveragePct != 100 || jsonlStatus.TranslatedBlocks != 5 || jsonlStatus.Lang != "zh-CN" {
		t.Fatalf("unexpected JSONL status: %#v", jsonlStatus)
	}

	// 8. A JSON array batch re-translates one block and keeps full coverage.
	array := `[{"id":"` + capexBlock.ID + `","sourceHash":"` + capexBlock.SourceHash + `","text":"甲乙公司：单年现金支出与三年累计承诺。"}]`
	arrayStatus := decode[bundle.TranslationStatus](t, mustRun(t, array, "translate", doc, "--lang", "zh-CN", "--input", "-"))
	if arrayStatus.CoveragePct != 100 || len(arrayStatus.MissingIDs) != 0 || arrayStatus.StaleBlocks != 0 {
		t.Fatalf("unexpected JSON array status: %#v", arrayStatus)
	}

	// 9. {"entries": [...]} is the third accepted shape.
	entryFile := filepath.Join(outDir, "entries.json")
	wrapped := `{"entries":[{"id":"` + queueBlock.ID + `","sourceHash":"` + queueBlock.SourceHash + `","text":"并网排队容量从 2020 年的 750 GW 增至 2024 年的 2,600 GW。"}]}`
	if err := os.WriteFile(entryFile, []byte(wrapped), 0o644); err != nil {
		t.Fatal(err)
	}
	wrappedStatus := decode[bundle.TranslationStatus](t, mustRun(t, "", "translate", doc, "--lang", "zh-CN", "--input", entryFile))
	if wrappedStatus.CoveragePct != 100 {
		t.Fatalf("unexpected wrapped status: %#v", wrappedStatus)
	}

	// 10. write a Chinese canvas view citing the exact translated blocks.
	statements := strings.Join([]string{
		`root = Col([head, mechanism, comparison])`,
		`head = Row([Title("电网为何承压：并网排队与资本口径", "xl"), Badge("原文保真", "info")], 2)`,
		`mechanism = Source(["s1"], [Svg([Rect(5, 10, 30, 20, "surface"), Path("M 35 20 L 60 20", null, "info", 2), Circle(70, 20, 10, "warning"), SvgText("排队", 15, 25)], "0 0 100 50", "项目进入受限的并网排队")])`,
		`comparison = Source(["s2"], [Grid([Card([Title("Firm A", "md"), Text("2024 单年现金支出", "sm"), Badge("$18B")]), Card([Title("Firm B", "md"), Text("三年累计承诺（2024–2026）", "sm"), Badge("$42B")])], 2, 200, 3), Caption("依据原文 §2 口径")])`,
	}, "\n")
	writeResult := decode[view.WriteResult](t, mustRun(t, statements,
		"write", "--statements", "-", doc,
		"--source", "s1=Interconnection queues#1",
		"--source", "s2=Capital basis#1",
		"--cite", "mechanism:s1="+queueBlock.ID,
		"--cite", "comparison:s2="+capexBlock.ID,
	))
	if writeResult.Revision != 1 || writeResult.ModuleCount != 2 {
		t.Fatalf("unexpected write result: %#v", writeResult)
	}

	// 11. export the finished dual-face reader (structured GenUI canvas + translated/bilingual original).
	readerPath := filepath.Join(t.TempDir(), "grid-reader.html")
	exported := decode[export.ExportResult](t, mustRun(t, "", "export", doc, "-o", readerPath))
	if exported.Face != "dual" || exported.Lang != "zh-CN" || exported.Mode != bundle.ReadModeTranslated {
		t.Fatalf("unexpected translated export metadata: %+v", exported)
	}
	html := readFile(t, readerPath)
	for _, want := range []string{
		`<html lang="zh-CN"`,
		`data-lang-mode="translated"`,
		`data-face="dual"`,
		"查看原文 ↗",
		`id="c01-` + queueBlock.ID + `"`,
		`id="c01-` + capexBlock.ID + `"`,
		"并网排队容量从 2020 年的 750 GW 增至 2024 年的 2,600 GW。",
		"中译：Why the Grid Strains",
		"dr-module",
		"<script>",
	} {
		if !strings.Contains(html, want) {
			t.Fatalf("translated reader missing %q", want)
		}
	}

	// 12. explicit --no-js keeps the page fully static while staying dual.
	noJSPath := filepath.Join(t.TempDir(), "grid-nojs.html")
	noJS := decode[export.ExportResult](t, mustRun(t, "", "export", doc, "-o", noJSPath, "--no-js"))
	if noJS.Face != "dual" {
		t.Fatalf("--no-js changed the face: %+v", noJS)
	}
	if strings.Contains(readFile(t, noJSPath), "<script") {
		t.Fatal("--no-js export still emitted a script")
	}

	// 13. inspect confirms 100% coverage with no stale blocks.
	final := decode[bundle.InspectReport](t, mustRun(t, "", "inspect", doc))
	if final.Translation == nil || final.Translation.CoveragePct != 100 || final.Translation.StaleBlocks != 0 {
		t.Fatalf("unexpected final translation status: %#v", final.Translation)
	}

	// 14. Editing prose stales the anchor: the same export must reject again.
	edited := readFile(t, doc) + "\nA new closing sentence changes the queue block.\n"
	if err := os.WriteFile(doc, []byte(edited), 0o644); err != nil {
		t.Fatal(err)
	}
	stdout, stderr, code = runCLI(t, "", "export", doc, "-o", filepath.Join(t.TempDir(), "stale.html"))
	if code != 3 {
		t.Fatalf("stale translation export exited %d, want 3 (stdout: %s, stderr: %s)", code, stdout, stderr)
	}
	if body := decode[errorEnvelope](t, stderr); body.Error.Code != "TRANSLATION_INCOMPLETE" {
		t.Fatalf("stale export code %q, want TRANSLATION_INCOMPLETE", body.Error.Code)
	}

	// 15. --allow-partial-translation still publishes the reader.
	partial := decode[export.ExportResult](t, mustRun(t, "", "export", doc, "-o", filepath.Join(t.TempDir(), "partial.html"), "--allow-partial-translation"))
	if partial.Bytes == 0 || partial.Mode != bundle.ReadModeTranslated {
		t.Fatalf("unexpected partial export: %+v", partial)
	}
}

func TestCLINoteAddMultiSource(t *testing.T) {
	dir := t.TempDir()
	doc := filepath.Join(dir, "article.md")
	raw := strings.Join([]string{
		"# Capital",
		"",
		"## Single-year cash",
		"",
		"Firm A reported $18B in 2024 cash capex.",
		"",
		"## Multi-year commitment",
		"",
		"Firm B announced a $42B three-year commitment through 2026.",
		"",
	}, "\n")
	if err := os.WriteFile(doc, []byte(raw), 0o644); err != nil {
		t.Fatal(err)
	}

	statements := strings.Join([]string{
		`root = Col([basis])`,
		`basis = Source(["s1", "s2"], [Table(["主体", "披露口径", "原文数值"], [["Firm A", "2024 单年现金", "$18B"], ["Firm B", "三年累计承诺（2024–2026）", "$42B"]]), Caption("依据原文两节口径注释")])`,
	}, "\n")
	stdout, stderr, code := runCLI(t, statements, "write", doc, "--statements", "-",
		"--source", "s1=Single-year cash#1", "--source", "s2=Multi-year commitment#1")
	if code != 0 {
		t.Fatalf("multi-source write exited %d (stdout: %s, stderr: %s)", code, stdout, stderr)
	}
	report := decode[bundle.InspectReport](t, mustRun(t, "", "inspect", doc))
	if len(report.Modules) != 1 || len(report.Modules[0].Sections) != 2 {
		t.Fatalf("unexpected multi-section module binding: %#v", report.Modules)
	}

	// Without --source a multi-section statement is ambiguous and rejected.
	stdout, stderr, code = runCLI(t, "", "note", "add", doc, "--node", "basis", "--text", "which section?")
	if code == 0 {
		t.Fatalf("ambiguous multi-source note was accepted: %s", stdout)
	}
	if stdout != "" {
		t.Fatalf("ambiguous note wrote to stdout: %q", stdout)
	}

	// --source picks the exact section, so the note lands on the right prose.
	note := decode[bundle.AddNoteResult](t, mustRun(t, "",
		"note", "add", doc, "--node", "basis", "--source", "s2", "--text", "三年承诺不能和单年现金直接相加"))
	if note.SectionHeading != "Multi-year commitment" || note.SectionOccurrence != 1 {
		t.Fatalf("note landed on %q#%d, want Multi-year commitment#1", note.SectionHeading, note.SectionOccurrence)
	}
	if note.Node != "basis" {
		t.Fatalf("note did not keep its node: %#v", note)
	}
	if !strings.Contains(readFile(t, doc), `node="basis"`) {
		t.Fatal("note was not written as an attributed inline comment")
	}

	// A source id the statement does not cite is a not-found rejection (exit 4).
	stdout, stderr, code = runCLI(t, "", "note", "add", doc, "--node", "basis", "--source", "s9", "--text", "nope")
	if code != 4 {
		t.Fatalf("unknown source id exited %d, want 4 (stdout: %s, stderr: %s)", code, stdout, stderr)
	}
	if body := decode[errorEnvelope](t, stderr); body.Error.Code != "NOT_FOUND" {
		t.Fatalf("unknown source id code %q, want NOT_FOUND", body.Error.Code)
	}
}

func TestCLICanvasEditorialGuardrails(t *testing.T) {
	dir := t.TempDir()
	doc := filepath.Join(dir, "grid.md")
	raw := strings.Join([]string{
		"# Grid",
		"",
		"## One",
		"",
		"Firm A reported $18B in 2024.",
		"",
		"## Two",
		"",
		"Queues rose from 750 GW in 2020 to 2,600 GW in 2024.",
		"",
		"## Three",
		"",
		"Firm B announced a $42B three-year commitment through 2026.",
		"",
	}, "\n")
	if err := os.WriteFile(doc, []byte(raw), 0o644); err != nil {
		t.Fatal(err)
	}
	sources := []string{"--source", "s1=One#1", "--source", "s2=Two#1", "--source", "s3=Three#1"}

	// MONOTONE_VIEW — three near-identical tables are rejected on canvas.
	monotone := strings.Join([]string{
		`root = Col([a, b, c])`,
		`a = Source(["s1"], [Table(["主体", "口径", "数值"], [["Firm A", "2024 单年", "$18B"]])])`,
		`b = Source(["s2"], [Table(["主体", "口径", "数值"], [["Queue", "2024", "2,600 GW"]])])`,
		`c = Source(["s3"], [Table(["主体", "口径", "数值"], [["Firm B", "三年累计", "$42B"]])])`,
	}, "\n")
	stdout, stderr, code := runCLI(t, monotone, append([]string{"write", doc, "--statements", "-"}, sources...)...)
	if code != 3 {
		t.Fatalf("monotone view exited %d, want 3 (stdout: %s, stderr: %s)", code, stdout, stderr)
	}
	if body := decode[errorEnvelope](t, stderr); body.Error.Code != "MONOTONE_VIEW" || body.Error.Statement != "root" {
		t.Fatalf("monotone payload = %#v", body.Error)
	}

	// The same three sections pass once the view diversifies its media.
	diverse := strings.Join([]string{
		`root = Col([a, b, c])`,
		`a = Source(["s1"], [Table(["主体", "口径", "数值"], [["Firm A", "2024 单年", "$18B"], ["Firm B", "三年累计", "$42B"]])])`,
		`b = Source(["s2"], [Chart("line", qdata, "year", ["gw"], "number", false, 200, {gw: "待并网容量 (GW)"})])`,
		`qdata = [{year: "2020", gw: 750}, {year: "2024", gw: 2600}]`,
		`c = Source(["s3"], [List([ListItem("Firm B 三年承诺", "2024–2026 累计 $42B", "2024")], "none", true)])`,
	}, "\n")
	if result := decode[view.WriteResult](t, mustRun(t, diverse, append([]string{"write", doc, "--statements", "-"}, sources...)...)); result.ModuleCount != 3 {
		t.Fatalf("diverse view was not accepted: %#v", result)
	}

	// Old v0.2 assertions must still hold when the margin profile is requested.
	stdout, stderr, code = runCLI(t, "root = Col([m])\nm = Source([\"s1\"], [Card([Table([\"A\"], [[\"1\"]])])])",
		"write", doc, "--statements", "-", "--source", "s1=One#1", "--profile", "margin")
	if code != 3 {
		t.Fatalf("margin Card exited %d, want 3 (stdout: %s, stderr: %s)", code, stdout, stderr)
	}
	if body := decode[errorEnvelope](t, stderr); body.Error.Code != "DISALLOWED_COMPONENT" || !strings.Contains(body.Error.Hint, "--profile margin") {
		t.Fatalf("margin rejection payload = %#v", body.Error)
	}
}

func TestCLICanvasUntranslatedGenUIRejected(t *testing.T) {
	srcDir := t.TempDir()
	src := writeTranslatableArticle(t, srcDir)
	outDir := filepath.Join(t.TempDir(), "bundle")
	ingested := decode[ingest.Result](t, mustRun(t, "", "ingest", src, "-o", outDir, "--lang", "zh-CN"))
	doc := filepath.Join(outDir, ingested.DocPath)

	english := strings.Join([]string{
		`root = Col([m])`,
		`m = Source(["s1"], [Title("Queue endpoints in GW", "md"), Chart("line", qdata, "year", ["gw"], "number", false, 200)])`,
		`qdata = [{year: "2020", gw: 750}, {year: "2024", gw: 2600}]`,
	}, "\n")
	stdout, stderr, code := runCLI(t, english, "write", doc, "--statements", "-", "--source", "s1=Interconnection queues#1")
	if code != 3 {
		t.Fatalf("English GenUI under zh-CN contract exited %d, want 3 (stdout: %s, stderr: %s)", code, stdout, stderr)
	}
	body := decode[errorEnvelope](t, stderr)
	if body.Error.Code != "UNTRANSLATED_GENUI" || !strings.Contains(body.Error.Message, "Queue endpoints in GW") || !strings.Contains(body.Error.Message, "zh-CN") {
		t.Fatalf("untranslated payload = %#v", body.Error)
	}

	// Translated GenUI text satisfies the same gate.
	chinese := strings.Join([]string{
		`root = Col([m])`,
		`m = Source(["s1"], [Title("并网排队容量（GW）", "md"), Chart("line", qdata, "year", ["gw"], "number", false, 200, {gw: "待并网容量"})])`,
		`qdata = [{year: "2020", gw: 750}, {year: "2024", gw: 2600}]`,
	}, "\n")
	if result := decode[view.WriteResult](t, mustRun(t, chinese, "write", doc, "--statements", "-", "--source", "s1=Interconnection queues#1")); result.ModuleCount != 1 {
		t.Fatalf("translated GenUI was rejected: %#v", result)
	}
}

// TestCLIExitCodeErrorEnvelopeIsValidJSON guards the structured stderr contract
// used by every host agent: a single JSON object with a machine-readable code.
func TestCLIExitCodeErrorEnvelopeIsValidJSON(t *testing.T) {
	_, stderr, code := runCLI(t, "", "catalog", "--profile", "nope")
	if code != 2 {
		t.Fatalf("catalog --profile nope exited %d, want 2", code)
	}
	var envelope map[string]map[string]string
	if err := json.Unmarshal([]byte(stderr), &envelope); err != nil {
		t.Fatalf("stderr is not JSON: %v (%q)", err, stderr)
	}
	if envelope["error"]["code"] != "INVALID_ARGS" {
		t.Fatalf("unexpected error envelope: %#v", envelope)
	}
}

func TestCLIBlocksOnMissingDoc(t *testing.T) {
	dir := t.TempDir()
	stdout, stderr, code := runCLI(t, "", "blocks", filepath.Join(dir, "missing.md"))
	if code != 4 {
		t.Fatalf("blocks on a missing doc exited %d, want 4 (stdout: %s, stderr: %s)", code, stdout, stderr)
	}
	if body := decode[errorEnvelope](t, stderr); body.Error.Code != "NOT_FOUND" {
		t.Fatalf("missing doc code %q, want NOT_FOUND", body.Error.Code)
	}
}

// TestCLICanvasIslandExport proves a $variable + Slider scenario (grounded in the
// source's own endpoints) survives validation and renders Go-precomputed island
// states in the exported page.
func TestCLICanvasIslandExport(t *testing.T) {
	dir := t.TempDir()
	doc := filepath.Join(dir, "capital.md")
	raw := strings.Join([]string{
		"# Capital",
		"",
		"## Commitment schedule",
		"",
		"Firm B announced a $42B three-year commitment, about $14B per year.",
		"",
	}, "\n")
	if err := os.WriteFile(doc, []byte(raw), 0o644); err != nil {
		t.Fatal(err)
	}

	statements := strings.Join([]string{
		`root = Col([scenario])`,
		`$years = 1`,
		`scenario = Source(["s1"], [Card([Title("三年承诺的分年支出", "md"), Slider($years, 1, 3, 1, "年数"), Text(@Format($years * 14, "currency", 0), "lg")])])`,
	}, "\n")
	result := decode[view.WriteResult](t, mustRun(t, statements, "write", doc, "--statements", "-", "--source", "s1=Commitment schedule#1"))
	if result.ModuleCount != 1 {
		t.Fatalf("unexpected island write result: %#v", result)
	}

	outPath := filepath.Join(dir, "capital.html")
	exported := decode[export.ExportResult](t, mustRun(t, "", "export", doc, "-o", outPath))
	if exported.IslandCount != 1 || exported.Face != "dual" {
		t.Fatalf("expected one reactive island in a dual export: %+v", exported)
	}
	html := readFile(t, outPath)
	for _, want := range []string{`type="range"`, "data-island", `data-state="2"`, "$42B", "三年承诺的分年支出"} {
		if !strings.Contains(html, want) {
			t.Fatalf("island HTML missing %q", want)
		}
	}
	if got := strings.Count(html, "<template data-island="); got != 3 {
		t.Fatalf("slider rendered %d pre-computed states, want 3", got)
	}
}

// TestCLICitationsMergeAcrossRevisions guards reader anchors: citing one module
// must never strip another module's 查看原文 target.
func TestCLICitationsMergeAcrossRevisions(t *testing.T) {
	dir := t.TempDir()
	doc := filepath.Join(dir, "grid.md")
	raw := strings.Join([]string{
		"# Grid",
		"",
		"## Queues",
		"",
		"Queues rose from 750 GW in 2020 to 2,600 GW in 2024.",
		"",
		"## Capital",
		"",
		"Firm A reported $18B in 2024 cash capex.",
		"",
	}, "\n")
	if err := os.WriteFile(doc, []byte(raw), 0o644); err != nil {
		t.Fatal(err)
	}
	blocks := decode[blocksReport](t, mustRun(t, "", "blocks", doc)).Blocks
	queue := findBlock(t, blocks, "Queues rose")
	capex := findBlock(t, blocks, "Firm A reported")

	first := strings.Join([]string{
		`root = Col([q, c])`,
		`q = Source(["s1"], [Chart("line", qdata, "year", ["gw"], "number", false, 180, {gw: "待并网 (GW)"})])`,
		`qdata = [{year: "2020", gw: 750}, {year: "2024", gw: 2600}]`,
		`c = Source(["s2"], [Table(["主体", "口径", "数值"], [["Firm A", "2024 单年", "$18B"]])])`,
	}, "\n")
	written := decode[view.WriteResult](t, mustRun(t, first, "write", doc, "--statements", "-",
		"--source", "s1=Queues#1", "--source", "s2=Capital#1",
		"--cite", "q:s1="+queue.ID, "--cite", "c:s2="+capex.ID))

	// Replacing only q with a fresh citation must keep c's anchor intact.
	patched := decode[view.PatchResult](t, mustRun(t,
		`q = Source(["s1"], [Chart("bar", qdata, "year", ["gw"], "number", false, 180, {gw: "待并网 (GW)"})])`,
		"patch", doc, "--replace", "q", "--expect-hash", written.ViewHash, "--statements", "-",
		"--cite", "q:s1="+queue.ID))
	if patched.Revision != 2 {
		t.Fatalf("unexpected patch result: %#v", patched)
	}
	citations, err := bundle.LoadCitations(doc)
	if err != nil {
		t.Fatal(err)
	}
	if len(citations["q"]["s1"]) != 1 || citations["q"]["s1"][0] != queue.ID {
		t.Fatalf("queue citation not refreshed: %#v", citations)
	}
	if len(citations["c"]["s2"]) != 1 || citations["c"]["s2"][0] != capex.ID {
		t.Fatalf("capital citation was dropped by the patch: %#v", citations)
	}

	out := filepath.Join(dir, "grid.html")
	mustRun(t, "", "export", doc, "-o", out)
	html := readFile(t, out)
	for _, want := range []string{`data-jump-target="#c01-` + queue.ID + `"`, `data-jump-target="#c01-` + capex.ID + `"`} {
		if !strings.Contains(html, want) {
			t.Fatalf("exported anchors missing %q", want)
		}
	}
}
