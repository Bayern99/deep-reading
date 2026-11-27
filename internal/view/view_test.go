package view

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"deepread/internal/bundle"
	"deepread/internal/genuikit"
)

const sampleDoc = `# Powering AI Data Centers

Intro paragraph.

## §1 · Capital Surge

Firm A reported $18B in 2024 cash capex. Firm B announced a $42B three-year commitment through 2026.

## §2 · Grid Queues

US interconnection queues rose from 750 GW in 2020 to 2,600 GW in 2024.
`

func TestCatalogExcludesDashboardClichés(t *testing.T) {
	text, err := CatalogTextFor(bundle.ProfileMargin)
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
		Now:     time.Date(2026, 11, 26, 8, 0, 0, 0, time.UTC),
		Profile: bundle.ProfileMargin,
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
		Profile:        bundle.ProfileMargin,
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
		Profile:        bundle.ProfileMargin,
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
			_, err := Write(doc, WriteOptions{StatementsText: tc.stmts, Sources: tc.sources, Profile: bundle.ProfileMargin})
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

func validateCanvasForTest(doc string, statements string, sources map[string]SourceRef, strict bool) (ValidationResult, error) {
	return ValidateWithOptions("article.md", []byte(doc), SplitStatementStrings(statements), sources, ValidateOptions{
		Profile:         bundle.ProfileCanvas,
		StrictEditorial: strict,
	})
}

func TestCanvasCatalogExposesFullOpenUIAndMarginStaysNarrow(t *testing.T) {
	canvas, err := CatalogText()
	if err != nil {
		t.Fatal(err)
	}
	explicit, err := CatalogTextFor(bundle.ProfileCanvas)
	if err != nil || canvas != explicit {
		t.Fatalf("CatalogText must default to the canvas profile: err=%v", err)
	}
	for _, name := range genuikit.ComponentNames() {
		if !strings.Contains(canvas, name+"(") {
			t.Errorf("canvas catalog omits %s", name)
		}
	}
	for _, want := range []string{"Example 1", "Example 2", "Example 3", "Slider(", "Source([\"s1\", \"s2\"]"} {
		if !strings.Contains(canvas, want) {
			t.Errorf("canvas catalog omits editorial guidance/example %q", want)
		}
	}
	margin, err := CatalogTextFor(bundle.ProfileMargin)
	if err != nil {
		t.Fatal(err)
	}
	for _, banned := range []string{"Card(", "Grid(", "Badge(", "Svg("} {
		if strings.Contains(margin, banned) {
			t.Errorf("margin catalog leaked %s", banned)
		}
	}
	if _, err := CatalogTextFor("unknown"); err == nil {
		t.Fatal("unknown catalog profile was accepted")
	}
}

func TestCanvasValidatesEveryCatalogComponentAndChartType(t *testing.T) {
	expressions := map[string]string{
		"Col": `Col([])`, "Row": `Row([])`, "Box": `Box([])`, "Grid": `Grid([])`, "Card": `Card([])`,
		"Divider": `Divider()`, "Spacer": `Spacer()`, "Title": `Title("Specific mechanism", "md")`,
		"Text": `Text("Body")`, "Caption": `Caption("Caption")`, "Label": `Label("Label")`,
		"Badge": `Badge("OK")`, "Link": `Link("Source site", "https://example.com")`,
		"ListItem": `ListItem("Entry")`, "List": `List([ListItem("Entry", null, "2024")], "none", true)`,
		"Markdown": `Markdown("**Body**")`, "Quote": `Quote("Quoted prose")`, "Code": `Code("const x = 1", "js")`,
		"Source": `Source(["s1"], [Text("Grounded")])`, "Table": `Table(["Subject"], [["A"]])`,
		"Chart": `Chart("bar", [{x: "A", y: 1}], "x", ["y"])`, "Icon": `Icon("check")`,
		"Image": `Image("https://example.com/a.png", "Alt")`,
		"Svg":   `Svg([Circle(1, 1, 1)], "0 0 10 10", "Mechanism")`, "G": `G([])`,
		"Circle": `Circle(1, 1, 1)`, "Ellipse": `Ellipse(1, 1, 1, 1)`, "Rect": `Rect(0, 0, 1, 1)`,
		"Line": `Line(0, 0, 1, 1)`, "Path": `Path("M 0 0 L 1 1")`,
		"Polyline": `Polyline("0,0 1,1")`, "Polygon": `Polygon("0,0 1,1 1,0")`,
		"SvgText": `SvgText("Label", 0, 0)`, "Carousel": `Carousel([])`,
		"Popover":    `Popover(Badge("Term"), Text("Definition"))`,
		"Button":     `Button("Open", @OpenUrl("https://example.com"))`,
		"IconButton": `IconButton("check", @OpenUrl("https://example.com"), "Open")`,
		"Pressable":  `Pressable(Text("Open"), @OpenUrl("https://example.com"))`,
		"Form":       `Form([])`, "Input": `Input($text)`, "TextArea": `TextArea($text)`,
		"Select": `Select($text, ["2026-01-01"])`, "Checkbox": `Checkbox($checked, "Check")`,
		"RadioGroup":       `RadioGroup($text, ["2026-01-01"])`,
		"SegmentedControl": `SegmentedControl($text, ["2026-01-01"])`,
		"Slider":           `Slider($number, 0, 10, 1, "Amount")`, "DatePicker": `DatePicker($text)`,
		"Timer": `Timer($number)`, "Flashcard": `Flashcard("Front", "Back")`, "Celebration": `Celebration(true)`,
	}
	names := genuikit.ComponentNames()
	if len(names) != 50 || len(expressions) != 50 {
		t.Fatalf("catalog/test component counts = %d/%d, want 50", len(names), len(expressions))
	}
	for _, name := range names {
		t.Run(name, func(t *testing.T) {
			statements := "root = Col([item])\nitem = " + expressions[name] + "\n$text = \"2026-01-01\"\n$number = 5\n$checked = false"
			result, err := validateCanvasForTest(sampleDoc, statements, map[string]SourceRef{
				"s1": {Heading: "§1 · Capital Surge", Occurrence: 1},
			}, false)
			if err != nil {
				t.Fatalf("%s rejected in canvas profile: %v", name, err)
			}
			if result.Root == nil {
				t.Fatalf("%s produced no root", name)
			}
		})
	}
	for _, chartType := range []string{"bar", "line", "area", "pie", "donut", "scatter"} {
		t.Run("chart_"+chartType, func(t *testing.T) {
			statements := `root = Col([chart])` + "\n" + `chart = Chart("` + chartType + `", [{x: "A", y: 1}], "x", ["y"])`
			if _, err := validateCanvasForTest(sampleDoc, statements, nil, false); err != nil {
				t.Fatalf("chart type %s rejected: %v", chartType, err)
			}
		})
	}
}

func TestCanvasMultiSourceNestedTreeAndH1Fallback(t *testing.T) {
	statements := strings.Join([]string{
		`root = Col([Title("资本与队列的相互作用", "xl"), Row([Badge("跨节综合")]), synthesis])`,
		`synthesis = Source(["s1", "s2"], [Card([Grid([Chart("line", data, "year", ["gw"]), Quote("Firm A reported $18B in 2024 cash capex.", "Capital")])])])`,
		`data = [{year: "2020", gw: 750}, {year: "2024", gw: 2600}]`,
	}, "\n")
	result, err := validateCanvasForTest(sampleDoc, statements, map[string]SourceRef{
		"s1": {Heading: "§1 · Capital Surge", Occurrence: 1},
		"s2": {Heading: "§2 · Grid Queues", Occurrence: 1},
	}, true)
	if err != nil {
		t.Fatalf("nested multi-source canvas rejected: %v", err)
	}
	if len(result.Modules) != 1 || len(result.Modules[0].Sections) != 2 {
		t.Fatalf("multi-source bindings = %#v", result.Modules)
	}
	module := result.Modules[0]
	if module.SourceID != "s1" || module.Section.Heading != "§1 · Capital Surge" || module.Sections[1].SourceID != "s2" {
		t.Fatalf("first-section compatibility or second binding lost: %#v", module)
	}
	for _, id := range []string{"s1", "s2"} {
		if result.Sources[id].Hash == "" {
			t.Errorf("source %s was not stamped", id)
		}
	}

	h1Doc := "# Standalone Note\n\nA short note with one directly useful quotation.\n"
	h1, err := validateCanvasForTest(h1Doc, "root = Col([Title(\"短文的机制\", \"xl\"), body])\nbody = Source([\"whole\"], [Quote(\"A short note with one directly useful quotation.\")])", map[string]SourceRef{
		"whole": {Heading: "Standalone Note", Occurrence: 1},
	}, true)
	if err != nil {
		t.Fatalf("H1-only canvas citation rejected instead of warned: %v", err)
	}
	if len(h1.Warnings) == 0 || h1.Warnings[0].Code != "H1_SOURCE_ALLOWED" {
		t.Fatalf("H1 fallback warning missing: %#v", h1.Warnings)
	}
}

func TestCanvasCalibratedEditorialGates(t *testing.T) {
	sources := map[string]SourceRef{"s1": {Heading: "§1 · Capital Surge", Occurrence: 1}}
	for _, tc := range []struct {
		name, statements, code string
	}{
		{"generic pair", `root = Col([m])` + "\n" + `m = Source(["s1"], [Table(["指标", "数值"], [["Capex", "$18B"]])])`, "GENERIC_KV_TABLE"},
		{"sole generic first column", `root = Col([m])` + "\n" + `m = Source(["s1"], [Title("口径差异", "md"), Table(["维度（单位）", "美国"], [["Capex", "$18B"]])])`, "GENERIC_KV_TABLE"},
		{"prose-only card wrapper", `root = Col([m])` + "\n" + `m = Source(["s1"], [Card([Title("意外后果", "md"), Text("正文已经写过的结论。"), Row([Badge("政策"), Badge("副作用")])])])`, "PROSE_WRAPPER_REJECTED"},
		{"plain bullet summary without timeline", `root = Col([m])` + "\n" + `m = Source(["s1"], [Col([Title("三条要点", "md"), List([ListItem("要点一"), ListItem("要点二")])])])`, "PROSE_WRAPPER_REJECTED"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			_, err := validateCanvasForTest(sampleDoc, tc.statements, sources, true)
			var ve *ValidationError
			if !errors.As(err, &ve) || ve.Code != tc.code {
				t.Fatalf("got %v, want %s", err, tc.code)
			}
		})
	}

	positive := `root = Col([m])` + "\n" + `m = Source(["s1"], [Table(["消费级", "工业级"], [["$18B", "$42B"]])])`
	if _, err := validateCanvasForTest(sampleDoc, positive, sources, true); err != nil {
		t.Fatalf("real two-subject comparison rejected: %v", err)
	}

	twoTablesOneChart := strings.Join([]string{
		`root = Col([a, b, c])`,
		`a = Source(["s1"], [Table(["主体", "口径"], [["A", "Cash"]])])`,
		`b = Source(["s1"], [Table(["主体", "金额"], [["B", "$42B"]])])`,
		`c = Source(["s1"], [Chart("bar", [{x: "A", y: 18}], "x", ["y"])])`,
	}, "\n")
	if _, err := validateCanvasForTest(sampleDoc, twoTablesOneChart, sources, true); err != nil {
		t.Fatalf("2 tables + 1 chart must pass strict integer threshold: %v", err)
	}
	threeTables := strings.Replace(twoTablesOneChart, `c = Source(["s1"], [Chart("bar", [{x: "A", y: 18}], "x", ["y"])])`, `c = Source(["s1"], [Table(["主体", "金额"], [["C", "$18B"]])])`, 1)
	_, err := validateCanvasForTest(sampleDoc, threeTables, sources, true)
	var ve *ValidationError
	if !errors.As(err, &ve) || ve.Code != "MONOTONE_VIEW" {
		t.Fatalf("3/3 tables got %v, want MONOTONE_VIEW", err)
	}

	threeSVGs := strings.Join([]string{
		`root = Col([a, b, c])`,
		`a = Source(["s1"], [Svg([Circle(1, 1, 1)], "0 0 10 10", "Capital flow")])`,
		`b = Source(["s1"], [Svg([Rect(0, 0, 1, 1)], "0 0 10 10", "Grid flow")])`,
		`c = Source(["s1"], [Svg([Line(0, 0, 1, 1)], "0 0 10 10", "Causal link")])`,
	}, "\n")
	if _, err := validateCanvasForTest(sampleDoc, threeSVGs, sources, true); err != nil {
		t.Fatalf("three diverse SVG mechanisms must not trigger monotone view: %v", err)
	}
}

func TestCanvasTranslationGateExemptsQuotesAndExportSkipsEditorial(t *testing.T) {
	sources := map[string]SourceRef{"s1": {Heading: "§1 · Capital Surge", Occurrence: 1}}
	positive := `root = Col([m])` + "\n" + `m = Source(["s1"], [Title("资本开支的口径", "md"), Text("原文数字不能直接相加。"), Badge("AI"), Quote("Firm A reported substantial capital expenditure during the year.", "Original")])`
	if _, err := ValidateWithOptions("article.md", []byte(sampleDoc), SplitStatementStrings(positive), sources, ValidateOptions{
		Profile: bundle.ProfileCanvas, TargetLang: "zh-CN", Mode: bundle.ReadModeTranslated, StrictEditorial: true,
	}); err != nil {
		t.Fatalf("Chinese title plus long English quote false-positive: %v", err)
	}
	negative := `root = Col([m])` + "\n" + `m = Source(["s1"], [Title("Revenue Growth Trends", "md"), Text("这是中文正文。"), Quote("Original English prose remains exempt from translation checks.")])`
	_, err := ValidateWithOptions("article.md", []byte(sampleDoc), SplitStatementStrings(negative), sources, ValidateOptions{
		Profile: bundle.ProfileCanvas, TargetLang: "zh-CN", Mode: bundle.ReadModeBilingual, StrictEditorial: true,
	})
	var ve *ValidationError
	if !errors.As(err, &ve) || ve.Code != "UNTRANSLATED_GENUI" {
		t.Fatalf("English title got %v, want UNTRANSLATED_GENUI", err)
	}
	if _, err := ValidateForExport("article.md", []byte(sampleDoc), SplitStatementStrings(negative), sources, bundle.ProfileCanvas); err != nil {
		t.Fatalf("export must not enforce translation heuristics: %v", err)
	}
}

func TestCanvasSecurityChecksApplyWithoutEditorialMode(t *testing.T) {
	for _, tc := range []struct {
		name, statements, code string
	}{
		{"missing viewBox", `root = Col([Svg([Circle(1, 1, 1)], "", "Diagram")])`, "UNSAFE_SVG"},
		{"missing label", `root = Col([Svg([Circle(1, 1, 1)], "0 0 10 10")])`, "UNSAFE_SVG"},
		{"unsafe path", `root = Col([Svg([Path("M 0 0; javascript:alert(1)")], "0 0 10 10", "Diagram")])`, "UNSAFE_SVG"},
		{"unsafe link", `root = Col([Link("Bad", "javascript:alert(1)")])`, "UNSAFE_URL"},
		{"unsafe action", `root = Col([Button("Bad", @OpenUrl("javascript:alert(1)"))])`, "UNSAFE_URL"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			_, err := validateCanvasForTest(sampleDoc, tc.statements, nil, false)
			var ve *ValidationError
			if !errors.As(err, &ve) || ve.Code != tc.code {
				t.Fatalf("got %v, want %s", err, tc.code)
			}
		})
	}
}
