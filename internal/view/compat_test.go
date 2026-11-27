package view

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
	"time"

	"deepread/internal/bundle"
)

// These fixtures are modeled on Mark Go Go's native GenUI testdata
// (`internal/nativegenui/testdata/trip.report.md.genui.json` at pinned commit
// f203c83). The compatibility contract is therefore pinned against real
// upstream output instead of an invented shape: `deepread` must keep reading
// what Mark Go Go writes, one way only (upstream -> deepread).
const upstreamTripView = `{
  "version": 3,
  "language": "openui-lang/1.0",
  "generatedAt": "2026-11-20T09:12:00Z",
  "model": "markgogo/desktop",
  "request": "Three days in Lisbon on about €120 a day",
  "sources": {
    "sec1": {"heading": "Day by day", "occurrence": 1, "hash": "fnv1a32:1a2b3c4d"},
    "sec2": {"heading": "Budget", "occurrence": 1, "hash": "fnv1a32:5e6f7a8b"}
  },
  "a2ui": [
    {
      "version": "1.0",
      "createSurface": {
        "surfaceId": "view",
        "catalogId": "markgogo.dev:genui/v3",
        "components": [
          "root = Col([plan_mod, budget_mod])",
          "plan_mod = Source([\"sec1\"], [Title(\"Three days in Lisbon\", \"lg\"), List([ListItem(\"Day 1\", \"Alfama and São Jorge Castle\", \"08:40\"), ListItem(\"Day 2\", \"Belém: monastery, tower, pastéis\", \"09:00\"), ListItem(\"Day 3\", \"Sintra: Pena Palace, book 9 AM\", \"08:40\")], \"none\", true), Caption(\"From the printed day-by-day plan\")])",
          "budget_mod = Source([\"sec2\"], [Title(\"Where the €120 a day goes\", \"md\"), Chart(\"bar\", spend, \"day\", [\"Food\", \"Transport\", \"Sights\"], \"number\", false, 220), Table([\"Item\", \"When\", \"Price\"], [[\"São Jorge Castle\", \"Day 1\", \"€15\"], [\"Jerónimos Monastery\", \"Day 2\", \"€12\"], [\"Pena Palace\", \"Day 3\", \"€20\"]]), Caption(\"Daily spend per person, in euros\")])",
          "spend = [{day: \"Day 1\", Food: 48, Transport: 7, Sights: 15}, {day: \"Day 2\", Food: 42, Transport: 12, Sights: 28}, {day: \"Day 3\", Food: 39, Transport: 21, Sights: 34}]"
        ]
      }
    }
  ]
}
`

// upstreamStreamedView is the multi-message shape Mark Go Go emits while a
// response streams: createSurface first, then incremental updateComponents
// batches that may delete an earlier helper statement with `= null`.
const upstreamStreamedView = `{
  "version": 3,
  "language": "openui-lang/1.0",
  "generatedAt": "2026-11-21T07:45:00Z",
  "sources": {
    "sec1": {"heading": "Grid Queues", "occurrence": 1, "hash": "fnv1a32:0badc0de"},
    "sec2": {"heading": "Interconnection by region", "occurrence": 2, "hash": "fnv1a32:0ddba11"}
  },
  "a2ui": [
    {
      "version": "1.0",
      "createSurface": {
        "surfaceId": "view",
        "catalogId": "markgogo.dev:genui/v3",
        "components": [
          "root = Col([hero, ledger_mod])",
          "hero = Source([\"sec1\"], [Title(\"Grid queue backlog\", \"md\"), Chart(\"line\", qdata, \"year\", [\"queued\"], \"number\", false, 200)])",
          "old_helper = Caption(\"draft helper, deleted by the next batch\")",
          "ledger_mod = Source([\"sec2\"], [Title(\"Interconnection by region (GW)\", \"md\"), Table([\"Region\", \"2020\", \"2024\"], [[\"ERCOT\", \"120\", \"310\"], [\"MISO\", \"90\", \"220\"]])])"
        ]
      }
    },
    {
      "version": "1.0",
      "updateComponents": {
        "surfaceId": "view",
        "components": [
          "old_helper = null",
          "hero = Source([\"sec1\"], [Title(\"Grid queue backlog (GW)\", \"md\"), Chart(\"bar\", qdata, \"year\", [\"queued\"], \"number\", false, 200)])",
          "qdata = [{year: \"2020\", queued: 750}, {year: \"2024\", queued: 2600}]",
          "footer = Caption(\"Values quoted from the cited sections\")"
        ]
      }
    }
  ]
}
`

func TestCompatReadsUpstreamMarkGoGoViews(t *testing.T) {
	t.Run("single createSurface upstream view", func(t *testing.T) {
		parsed, err := ReadView([]byte(upstreamTripView))
		if err != nil {
			t.Fatalf("ReadView rejected upstream trip view: %v", err)
		}
		if parsed.Envelope.Version != ViewVersion {
			t.Fatalf("version = %d, want %d", parsed.Envelope.Version, ViewVersion)
		}
		if parsed.Envelope.Language != ViewLanguage {
			t.Fatalf("language = %q, want %q", parsed.Envelope.Language, ViewLanguage)
		}
		if len(parsed.Envelope.A2UI) != 1 {
			t.Fatalf("a2ui messages = %d, want 1", len(parsed.Envelope.A2UI))
		}
		msg := parsed.Envelope.A2UI[0]
		if msg.Version != A2UIVersion {
			t.Fatalf("a2ui version = %q, want %q", msg.Version, A2UIVersion)
		}
		if msg.CreateSurface == nil || msg.UpdateComponents != nil {
			t.Fatalf("expected a single createSurface message, got %#v", msg)
		}
		if msg.CreateSurface.CatalogID != CatalogID {
			t.Fatalf("catalogId = %q, want %q", msg.CreateSurface.CatalogID, CatalogID)
		}
		if msg.CreateSurface.SurfaceID != SurfaceID {
			t.Fatalf("surfaceId = %q, want %q", msg.CreateSurface.SurfaceID, SurfaceID)
		}
		if got, want := len(parsed.Statements), len(msg.CreateSurface.Components); got != want {
			t.Fatalf("statements = %d, want %d", got, want)
		}
		if !strings.HasPrefix(parsed.Statements[0], "root = Col([plan_mod, budget_mod])") {
			t.Fatalf("first statement lost source order: %q", parsed.Statements[0])
		}
		for _, want := range []string{"Chart(\"bar\"", "Table([\"Item\"", "], \"none\", true)"} {
			if !strings.Contains(parsed.JoinedText, want) {
				t.Fatalf("joined text lost upstream primitive %q", want)
			}
		}
		if len(parsed.Envelope.Sources) != 2 {
			t.Fatalf("sources = %d, want 2", len(parsed.Envelope.Sources))
		}
		if got := parsed.Envelope.Sources["sec1"]; got.Heading != "Day by day" || got.Hash != "fnv1a32:1a2b3c4d" {
			t.Fatalf("source ref was not preserved: %#v", got)
		}

		// Reading is deterministic: no map-order or timestamp leakage.
		again, err := ReadView([]byte(upstreamTripView))
		if err != nil {
			t.Fatal(err)
		}
		if !reflect.DeepEqual(parsed.Statements, again.Statements) {
			t.Fatalf("statements are not deterministic:\n%v\n%v", parsed.Statements, again.Statements)
		}
	})

	t.Run("multi-message overlay with null deletion", func(t *testing.T) {
		parsed, err := ReadView([]byte(upstreamStreamedView))
		if err != nil {
			t.Fatalf("ReadView rejected streamed upstream view: %v", err)
		}
		if len(parsed.Envelope.A2UI) != 2 {
			t.Fatalf("a2ui messages = %d, want 2", len(parsed.Envelope.A2UI))
		}
		if parsed.Envelope.A2UI[1].UpdateComponents == nil {
			t.Fatalf("second message must be updateComponents: %#v", parsed.Envelope.A2UI[1])
		}

		names := make([]string, len(parsed.Statements))
		for i, stmt := range parsed.Statements {
			names[i] = strings.SplitN(stmt, "=", 2)[0]
			names[i] = strings.TrimSpace(names[i])
		}
		want := []string{"root", "hero", "ledger_mod", "qdata", "footer"}
		if !reflect.DeepEqual(names, want) {
			t.Fatalf("overlaid statement order = %v, want %v", names, want)
		}
		if strings.Contains(parsed.JoinedText, "old_helper") {
			t.Fatalf("null deletion left old_helper behind:\n%s", parsed.JoinedText)
		}
		if n := strings.Count(parsed.JoinedText, "hero = Source("); n != 1 {
			t.Fatalf("hero redefined %d times, want exactly 1", n)
		}
		if !strings.Contains(parsed.JoinedText, `Chart("bar", qdata`) {
			t.Fatalf("later batch did not replace hero:\n%s", parsed.JoinedText)
		}
		if !strings.Contains(parsed.JoinedText, "footer = Caption(") {
			t.Fatalf("later batch did not append footer:\n%s", parsed.JoinedText)
		}
	})

	t.Run("deepread written CJK CRLF view stays a v3 sidecar", func(t *testing.T) {
		dir := t.TempDir()
		doc := filepath.Join(dir, "article.md")
		// CRLF source, Chinese headings, emoji, and multiple Source anchors.
		docRaw := strings.Join([]string{
			"# 欧洲电网的隐形瓶颈 ⚡",
			"",
			"导语段落，保留原文。",
			"",
			"## 第一节 · 并网排队",
			"",
			"2020 年排队容量 750 GW，2024 年升至 2,600 GW。研究员说：“排队不等于建成。” 🚧",
			"",
			"## 第二节 · 资本开支口径",
			"",
			"甲公司披露 2024 年现金资本开支 $18B；乙公司披露 2024–2026 三年累计承诺 $42B（含未实付部分）。",
			"",
		}, "\r\n")
		if err := os.WriteFile(doc, []byte(docRaw), 0o644); err != nil {
			t.Fatal(err)
		}
		if !strings.Contains(docRaw, "\r\n") {
			t.Fatal("fixture must keep CRLF line endings")
		}

		stmts := strings.Join([]string{
			`root = Col([queue_mod, capex_mod])`,
			`queue_mod = Source(["s1"], [Title("并网排队 🚧 容量（GW，2020→2024）", "md"), Chart("bar", qdata, "year", ["queued"], "number", false, 200), Caption("数据取自第一节原文")])`,
			`qdata = [{year: "2020", queued: 750}, {year: "2024", queued: 2600}]`,
			`capex_mod = Source(["s2"], [Title("资本开支统计口径不可直接相加", "md"), Table(["主体", "披露口径", "原文数值", "口径差异"], [["甲公司", "2024 单年实付", "$18B", "仅含当年现金流出"], ["乙公司", "三年累计承诺（2024–2026）", "$42B", "含未来未实付承诺，年均约 $14B"]]), Quote("排队不等于建成。", "第一节 · 并网排队")])`,
		}, "\n")

		now := time.Date(2026, 11, 26, 8, 0, 0, 0, time.UTC)
		res1, err := Write(doc, WriteOptions{
			StatementsText: stmts,
			Sources: map[string]SourceRef{
				"s1": {Heading: "第一节 · 并网排队", Occurrence: 1},
				"s2": {Heading: "第二节 · 资本开支口径", Occurrence: 1},
			},
			Now:     now,
			Profile: bundle.ProfileMargin,
		})
		if err != nil {
			t.Fatalf("Write rejected CJK/CRLF view: %v", err)
		}
		if res1.Revision != 1 || res1.ModuleCount != 2 {
			t.Fatalf("unexpected write result: %#v", res1)
		}

		viewPath := bundle.ViewPath(doc)
		if want := filepath.Join(dir, ".article.md.genui.json"); viewPath != want {
			t.Fatalf("sidecar path = %q, want %q", viewPath, want)
		}
		raw, err := os.ReadFile(viewPath)
		if err != nil {
			t.Fatal(err)
		}

		var env Envelope
		if err := json.Unmarshal(raw, &env); err != nil {
			t.Fatalf("sidecar is not valid JSON: %v", err)
		}
		if env.Version != 3 || env.Language != "openui-lang/1.0" {
			t.Fatalf("header = version %d / %q, want 3 / openui-lang/1.0", env.Version, env.Language)
		}
		if len(env.A2UI) != 1 {
			t.Fatalf("a2ui messages = %d, want exactly 1 compacted message", len(env.A2UI))
		}
		msg := env.A2UI[0]
		if msg.Version != "1.0" {
			t.Fatalf("a2ui[0].version = %q, want 1.0", msg.Version)
		}
		if msg.CreateSurface == nil || msg.UpdateComponents != nil {
			t.Fatalf("compacted sidecar must be a single createSurface, got %#v", msg)
		}
		if msg.CreateSurface.SurfaceID != "view" {
			t.Fatalf("createSurface.surfaceId = %q, want view", msg.CreateSurface.SurfaceID)
		}
		if msg.CreateSurface.CatalogID != "markgogo.dev:genui/v3" {
			t.Fatalf("createSurface.catalogId = %q, want markgogo.dev:genui/v3", msg.CreateSurface.CatalogID)
		}
		if len(msg.CreateSurface.Components) != 4 {
			t.Fatalf("components = %d, want 4", len(msg.CreateSurface.Components))
		}
		for _, sid := range []string{"s1", "s2"} {
			src, ok := env.Sources[sid]
			if !ok {
				t.Fatalf("sources missing %q: %#v", sid, env.Sources)
			}
			if !strings.HasPrefix(src.Hash, "fnv1a32:") || len(src.Hash) != len("fnv1a32:")+8 {
				t.Fatalf("source %q hash = %q, want fnv1a32:xxxxxxxx", sid, src.Hash)
			}
			if src.Occurrence != 1 {
				t.Fatalf("source %q occurrence = %d, want 1", sid, src.Occurrence)
			}
		}
		if env.Sources["s1"].Heading != "第一节 · 并网排队" {
			t.Fatalf("source heading lost its exact bytes: %q", env.Sources["s1"].Heading)
		}
		// Go's JSON encoder must emit UTF-8, not \uXXXX escapes: Mark Go Go reads raw text.
		if !strings.Contains(string(raw), "并网排队") || !strings.Contains(string(raw), "🚧") {
			t.Fatalf("sidecar escaped CJK/emoji instead of writing UTF-8:\n%s", raw)
		}
		if strings.Contains(string(raw), `"updateComponents"`) {
			t.Fatalf("compacted sidecar must not carry update batches:\n%s", raw)
		}

		parsed, err := ReadView(raw)
		if err != nil {
			t.Fatalf("ReadView rejected DeepRead's own sidecar: %v", err)
		}
		if len(parsed.Statements) != 4 {
			t.Fatalf("re-read statements = %d, want 4", len(parsed.Statements))
		}
		if !strings.Contains(parsed.JoinedText, "🚧") || !strings.Contains(parsed.JoinedText, "$42B") {
			t.Fatalf("re-read view lost CJK/emoji/figures:\n%s", parsed.JoinedText)
		}

		// CRLF section hashes must stay live for Mark Go Go and for inspect.
		report, err := bundle.Inspect(doc, bundle.InspectOptions{})
		if err != nil {
			t.Fatal(err)
		}
		if len(report.StaleSources) != 0 || len(report.MissingSources) != 0 {
			t.Fatalf("CRLF anchors reported stale/missing: stale=%#v missing=%#v", report.StaleSources, report.MissingSources)
		}
		if report.ViewHash == "" || report.ViewHash != bundle.SHA256Hex(raw) {
			t.Fatalf("inspect viewHash = %q, want %q", report.ViewHash, bundle.SHA256Hex(raw))
		}

		// Second write must leave Mark Go Go's exact undo backup beside the sidecar.
		if _, err := Write(doc, WriteOptions{StatementsText: `root = Col([])`, Sources: map[string]SourceRef{}, Now: now, Profile: bundle.ProfileMargin}); err != nil {
			t.Fatalf("Write r2 failed: %v", err)
		}
		prevPath := bundle.PrevViewPath(viewPath)
		if want := filepath.Join(dir, ".article.md.genui.prev.json"); prevPath != want {
			t.Fatalf("prev backup path = %q, want %q", prevPath, want)
		}
		prev, err := os.ReadFile(prevPath)
		if err != nil {
			t.Fatalf("expected Mark Go Go undo backup: %v", err)
		}
		if string(prev) != string(raw) {
			t.Fatalf("prev backup is not the r1 sidecar")
		}
		if _, err := ReadView(prev); err != nil {
			t.Fatalf("prev backup is not a readable v3 view: %v", err)
		}
	})
}

func TestCompatValidateForExportAcceptsUpstreamFullCanvas(t *testing.T) {
	docRaw := "# Grid\n\n## Grid Queues\n\nQueues rose to 2,600 GW.\n\n## Interconnection by region\n\nFirst regional table.\n\n## Interconnection by region\n\nSecond regional table.\n"
	// Extend the streamed fixture with a full-canvas header and nested components.
	raw := strings.Replace(upstreamStreamedView, `"root = Col([hero, ledger_mod])"`, `"root = Col([header, hero, ledger_mod, details, extras])", "header = Row([Title(\"Grid mechanisms\", \"xl\"), Spacer(), Badge(\"LIVE\")])", "details = Grid([Card([Box([List([ListItem(\"Step\")]), Markdown(\"**Grounded**\")])]), Popover(Badge(\"Term\"), Text(\"Definition\"))])", "extras = Source([\"sec1\"], [Quote(\"Quoted prose\"), Code(\"queue.push(job)\", \"go\"), Link(\"Reference\", \"https://example.com\")])"`, 1)
	parsed, err := ReadView([]byte(raw))
	if err != nil {
		t.Fatalf("ReadView rejected full-canvas upstream fixture: %v\n%s", err, raw)
	}
	if _, err := ValidateForExport("trip.md", []byte(docRaw), parsed.Statements, parsed.Envelope.Sources, bundle.ProfileCanvas); err != nil {
		t.Fatalf("ValidateForExport rejected upstream createSurface + updateComponents: %v", err)
	}

	marginDoc := "# Report\n\n## Alpha\n\nOriginal prose.\n"
	margin := `root = Col([m])` + "\n" + `m = Source(["s1"], [Title("Key Takeaways", "md"), Text("A prose-only legacy margin view")])`
	if _, err := ValidateStrict(marginDoc, margin, map[string]SourceRef{"s1": {Heading: "Alpha", Occurrence: 1}}); err == nil {
		t.Fatal("strict margin unexpectedly accepted prose-only cliché view")
	}
	if _, err := ValidateForExport("margin.md", []byte(marginDoc), SplitStatementStrings(margin), map[string]SourceRef{"s1": {Heading: "Alpha", Occurrence: 1}}, bundle.ProfileMargin); err != nil {
		t.Fatalf("export enforced margin editorial heuristics: %v", err)
	}
}

func TestCompatRejectsCorruptOrOversizedView(t *testing.T) {
	padding := strings.Repeat("A", MaxViewBytes)
	oversized := strings.Replace(upstreamTripView, `"hash": "fnv1a32:1a2b3c4d"`, `"hash": "`+padding+`"`, 1)
	if len(oversized) <= MaxViewBytes {
		t.Fatalf("oversized fixture is only %d bytes", len(oversized))
	}

	cases := []struct {
		name     string
		raw      string
		wantCode string
	}{
		{
			name:     "wrong language",
			raw:      strings.Replace(upstreamTripView, `"language": "openui-lang/1.0"`, `"language": "openui-lang"`, 1),
			wantCode: "INVALID_LANGUAGE",
		},
		{
			name:     "wrong catalogId",
			raw:      strings.Replace(upstreamTripView, "markgogo.dev:genui/v3", "markgogo.dev:genui/v2", 1),
			wantCode: "INVALID_CATALOG",
		},
		{
			name:     "missing createSurface",
			raw:      `{"version":3,"language":"openui-lang/1.0","sources":{},"a2ui":[{"version":"1.0"}]}`,
			wantCode: "INVALID_MESSAGE",
		},
		{
			name:     "updateComponents first",
			raw:      `{"version":3,"language":"openui-lang/1.0","sources":{},"a2ui":[{"version":"1.0","updateComponents":{"surfaceId":"view","components":["root = Col([])"]}}]}`,
			wantCode: "INVALID_MESSAGE",
		},
		{
			name:     "wrong envelope version",
			raw:      strings.Replace(upstreamTripView, `"version": 3`, `"version": 2`, 1),
			wantCode: "INVALID_VERSION",
		},
		{
			name:     "oversized payload",
			raw:      oversized,
			wantCode: "VIEW_TOO_LARGE",
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if tc.wantCode != "VIEW_TOO_LARGE" && tc.raw == upstreamTripView {
				t.Fatalf("fixture was not mutated for case %q", tc.name)
			}
			_, err := ReadView([]byte(tc.raw))
			var ve *ValidationError
			if !errors.As(err, &ve) {
				t.Fatalf("expected ValidationError(%s), got %v", tc.wantCode, err)
			}
			if ve.Code != tc.wantCode {
				t.Fatalf("code = %q (%s), want %q", ve.Code, ve.Message, tc.wantCode)
			}
			if ve.Message == "" {
				t.Fatalf("rejection %q must explain the problem", ve.Code)
			}
		})
	}

	if _, err := ReadView(make([]byte, MaxViewBytes+1)); err == nil {
		t.Fatalf("ReadView accepted a payload above MaxViewBytes (%d)", MaxViewBytes)
	}
	ve := &ValidationError{}
	_, err := ReadView([]byte(oversized))
	if !errors.As(err, &ve) || ve.Hint == "" {
		t.Fatalf("VIEW_TOO_LARGE must carry a repair hint, got %v", err)
	}
}
