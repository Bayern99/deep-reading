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

const patchTestDoc = `# Report

## Alpha

Original alpha prose.

## Beta

Original beta prose.
`

const patchTestInitialStatements = `root = Col([alpha, beta])
alpha = Source(["s1"], [Chart("bar", alphaData, "name", ["value"], "number", false, 200)])
alphaData = [{name: "A", value: 1}]
beta = Source(["s2"], [Quote("Original beta prose.", "Beta")])`

func writePatchTestBundle(t *testing.T) (doc string, initial []byte) {
	t.Helper()
	dir := t.TempDir()
	doc = filepath.Join(dir, "article.md")
	if err := os.WriteFile(doc, []byte(patchTestDoc), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := Write(doc, WriteOptions{
		StatementsText: patchTestInitialStatements,
		Sources: map[string]SourceRef{
			"s1": {Heading: "Alpha", Occurrence: 1},
			"s2": {Heading: "Beta", Occurrence: 1},
		},
		Now:     time.Date(2026, 11, 26, 8, 0, 0, 0, time.UTC),
		Profile: bundle.ProfileMargin,
	}); err != nil {
		t.Fatalf("Write seed failed: %v", err)
	}
	var err error
	initial, err = os.ReadFile(bundle.ViewPath(doc))
	if err != nil {
		t.Fatal(err)
	}
	return doc, initial
}

func patchTestStatementsByName(t *testing.T, raw []byte) map[string]string {
	t.Helper()
	parsed, err := ReadView(raw)
	if err != nil {
		t.Fatalf("ReadView failed: %v", err)
	}
	out := map[string]string{}
	for _, stmt := range parsed.Statements {
		name := strings.SplitN(strings.TrimSpace(stmt), " ", 2)[0]
		out[name] = stmt
	}
	return out
}

func patchTestFileBytes(t *testing.T, path string) []byte {
	t.Helper()
	raw, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return nil
	}
	if err != nil {
		t.Fatal(err)
	}
	return raw
}

func TestPatchTwoRoundsCompactsAndPreservesUntouchedStatements(t *testing.T) {
	doc, initial := writePatchTestBundle(t)
	initialStatements := patchTestStatementsByName(t, initial)
	betaBefore := initialStatements["beta"]
	betaHashBefore := func() string {
		parsed, err := ReadView(initial)
		if err != nil {
			t.Fatal(err)
		}
		return parsed.Envelope.Sources["s2"].Hash
	}()

	note, err := bundle.AddNote(doc, bundle.AddNoteOptions{
		Heading: "Alpha",
		Text:    "Replace the chart with a table, then a quote.",
		MsgID:   "patch-note-1",
	})
	if err != nil {
		t.Fatalf("AddNote failed: %v", err)
	}

	patch1Bytes := `alpha = Source(["s1"], [Table(["Metric"], [["Round one"]])])`
	res1, err := Patch(doc, PatchOptions{
		Replace:        []string{"alpha"},
		ExpectHash:     bundle.SHA256Hex(initial),
		StatementsText: patch1Bytes,
		Model:          "patch-model",
		Request:        "round one",
		Now:            time.Date(2026, 11, 26, 9, 0, 0, 0, time.UTC),
	})
	if err != nil {
		t.Fatalf("Patch round 1 failed: %v", err)
	}
	if res1.Revision != 2 || len(res1.Replaced) != 1 || res1.Replaced[0] != "alpha" || len(res1.Modules) != 2 {
		t.Fatalf("unexpected round 1 result: %#v", res1)
	}
	view1, err := os.ReadFile(bundle.ViewPath(doc))
	if err != nil {
		t.Fatal(err)
	}
	parsed1, err := ReadView(view1)
	if err != nil {
		t.Fatal(err)
	}
	if len(parsed1.Envelope.A2UI) != 1 || parsed1.Envelope.A2UI[0].CreateSurface == nil {
		t.Fatalf("round 1 was not compacted to one createSurface: %#v", parsed1.Envelope.A2UI)
	}
	statements1 := patchTestStatementsByName(t, view1)
	if statements1["beta"] != betaBefore {
		t.Fatalf("untouched beta changed in round 1:\nbefore: %q\nafter:  %q", betaBefore, statements1["beta"])
	}
	if _, found := statements1["alphaData"]; found {
		t.Fatalf("unreachable old private helper survived compaction: %#v", statements1)
	}
	if parsed1.Envelope.Sources["s2"].Hash != betaHashBefore {
		t.Fatalf("untouched beta source hash changed: %s -> %s", betaHashBefore, parsed1.Envelope.Sources["s2"].Hash)
	}
	if _, err := os.Stat(bundle.PrevViewPath(bundle.ViewPath(doc))); err != nil {
		t.Fatalf("round 1 did not create previous-view backup: %v", err)
	}
	history2 := filepath.Join(bundle.MetaDir(doc), "history", "r2.genui.json")
	if raw, err := os.ReadFile(history2); err != nil || string(raw) != string(view1) {
		t.Fatalf("round 1 history mismatch: err=%v", err)
	}

	res2, err := Patch(doc, PatchOptions{
		Replace:        []string{"alpha"},
		ExpectHash:     bundle.SHA256Hex(view1),
		StatementsText: `alpha = Source(["s1"], [Quote("Round two", "Alpha")])`,
		ResolveNotes:   []string{note.NoteID},
		Now:            time.Date(2026, 11, 26, 10, 0, 0, 0, time.UTC),
	})
	if err != nil {
		t.Fatalf("Patch round 2 failed: %v", err)
	}
	if res2.Revision != 3 || len(res2.ResolvedNotes) != 1 || res2.ResolvedNotes[0] != note.NoteID {
		t.Fatalf("unexpected round 2 result: %#v", res2)
	}
	view2, err := os.ReadFile(bundle.ViewPath(doc))
	if err != nil {
		t.Fatal(err)
	}
	parsed2, err := ReadView(view2)
	if err != nil {
		t.Fatal(err)
	}
	if len(parsed2.Envelope.A2UI) != 1 || parsed2.Envelope.A2UI[0].CreateSurface == nil {
		t.Fatalf("round 2 was not compacted to one createSurface: %#v", parsed2.Envelope.A2UI)
	}
	statements2 := patchTestStatementsByName(t, view2)
	if statements2["beta"] != betaBefore {
		t.Fatalf("untouched beta changed in round 2:\nbefore: %q\nafter:  %q", betaBefore, statements2["beta"])
	}
	if prev, err := os.ReadFile(bundle.PrevViewPath(bundle.ViewPath(doc))); err != nil || string(prev) != string(view1) {
		t.Fatalf("previous-view backup does not contain round 1: err=%v", err)
	}
	if _, err := os.Stat(history2); err != nil {
		t.Fatalf("r2 history disappeared after round 2: %v", err)
	}
	if _, err := os.Stat(filepath.Join(bundle.MetaDir(doc), "history", "r3.genui.json")); err != nil {
		t.Fatalf("round 2 did not write r3 history: %v", err)
	}

	report, err := bundle.Inspect(doc, bundle.InspectOptions{})
	if err != nil {
		t.Fatal(err)
	}
	if len(report.OpenNotes) != 0 {
		t.Fatalf("resolved note is still open: %#v", report.OpenNotes)
	}
}

func TestPatchRejectsStaleHashWithoutDiskMutation(t *testing.T) {
	doc, initial := writePatchTestBundle(t)
	manifestPath := bundle.ManifestPath(doc)
	manifestBefore := patchTestFileBytes(t, manifestPath)

	_, err := Patch(doc, PatchOptions{
		Replace:        []string{"alpha"},
		ExpectHash:     strings.Repeat("0", 64),
		StatementsText: `alpha = Source(["s1"], [Quote("Changed", "Alpha")])`,
	})
	if !errors.Is(err, ErrHashConflict) {
		t.Fatalf("got %v, want ErrHashConflict", err)
	}
	if after := patchTestFileBytes(t, bundle.ViewPath(doc)); string(after) != string(initial) {
		t.Fatalf("stale hash mutated view")
	}
	if after := patchTestFileBytes(t, manifestPath); string(after) != string(manifestBefore) {
		t.Fatalf("stale hash mutated manifest")
	}
	if prev := patchTestFileBytes(t, bundle.PrevViewPath(bundle.ViewPath(doc))); prev != nil {
		t.Fatalf("stale hash created previous-view backup")
	}
	if history := patchTestFileBytes(t, filepath.Join(bundle.MetaDir(doc), "history", "r2.genui.json")); history != nil {
		t.Fatalf("stale hash created r2 history")
	}
}

func TestPatchCanvasMultiSourceAndVariableCompactsWithCitations(t *testing.T) {
	dir := t.TempDir()
	doc := filepath.Join(dir, "article.md")
	if err := os.WriteFile(doc, []byte(sampleDoc), 0o644); err != nil {
		t.Fatal(err)
	}
	initialStatements := strings.Join([]string{
		`root = Col([Title("资本与队列", "xl"), synthesis])`,
		`$months = 6`,
		`synthesis = Source(["s1", "s2"], [Card([Slider($months, 6, 12, 1, "Months"), Chart("line", data, "year", ["gw"])])])`,
		`data = [{year: "2020", gw: 750}, {year: "2024", gw: 2600}]`,
	}, "\n")
	written, err := Write(doc, WriteOptions{
		StatementsText: initialStatements,
		Sources: map[string]SourceRef{
			"s1": {Heading: "§1 · Capital Surge", Occurrence: 1},
			"s2": {Heading: "§2 · Grid Queues", Occurrence: 1},
		},
		Citations: bundle.CitationMap{"synthesis": {"s1": {"b1"}, "s2": {"b2"}}},
	})
	if err != nil {
		t.Fatalf("canvas Write failed: %v", err)
	}
	if len(written.Modules) != 1 || len(written.Modules[0].Sections) != 2 || written.Modules[0].ShortCode == "" {
		t.Fatalf("multi-source write bindings = %#v", written.Modules)
	}
	manifest, _, err := bundle.LoadManifest(doc, []byte(sampleDoc))
	if err != nil || manifest.Profile != bundle.ProfileCanvas {
		t.Fatalf("manifest profile = %q, err=%v", manifest.Profile, err)
	}
	citations, err := bundle.LoadCitations(doc)
	if err != nil || len(citations["synthesis"]["s2"]) != 1 {
		t.Fatalf("citations not persisted: %#v, err=%v", citations, err)
	}
	rawInitial, err := os.ReadFile(bundle.ViewPath(doc))
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(rawInitial), `"profile"`) {
		t.Fatal("DeepRead profile leaked into the Mark Go Go v3 envelope")
	}

	patched, err := Patch(doc, PatchOptions{
		Replace:        []string{"synthesis", "$months"},
		ExpectHash:     written.ViewHash,
		StatementsText: "$months = 12\nsynthesis = Source([\"s1\", \"s2\"], [Grid([Card([Slider($months, 6, 12, 1, \"Months\")]), Popover(Badge(\"GW\"), Text(\"Queued capacity\"))])])",
		Citations:      bundle.CitationMap{"synthesis": {"s1": {"b1-new"}, "s2": {"b2-new"}}},
	})
	if err != nil {
		t.Fatalf("multi-source + variable Patch failed: %v", err)
	}
	if patched.Revision != 2 || len(patched.Replaced) != 2 || len(patched.Modules[0].Sections) != 2 {
		t.Fatalf("unexpected canvas patch result: %#v", patched)
	}
	rawPatched, err := os.ReadFile(bundle.ViewPath(doc))
	if err != nil {
		t.Fatal(err)
	}
	parsed, err := ReadView(rawPatched)
	if err != nil {
		t.Fatal(err)
	}
	if len(parsed.Envelope.A2UI) != 1 || parsed.Envelope.A2UI[0].CreateSurface == nil || !strings.Contains(parsed.JoinedText, "$months = 12") {
		t.Fatalf("patch did not compact variable update: %#v\n%s", parsed.Envelope.A2UI, parsed.JoinedText)
	}
	previous, err := os.ReadFile(bundle.PrevViewPath(bundle.ViewPath(doc)))
	if err != nil || string(previous) != string(rawInitial) {
		t.Fatalf("undo backup mismatch: err=%v", err)
	}
	citations, err = bundle.LoadCitations(doc)
	if err != nil || citations["synthesis"]["s1"][0] != "b1-new" {
		t.Fatalf("patched citations not persisted: %#v, err=%v", citations, err)
	}
}

func TestPatchRejectsOutOfScopeStatementsWithoutDiskMutation(t *testing.T) {
	for _, tc := range []struct {
		name       string
		statements string
	}{
		{name: "existing statement not requested", statements: `beta = Source(["s2"], [Quote("Mutated", "Beta")])`},
		{name: "root", statements: `root = Col([alpha])`},
	} {
		t.Run(tc.name, func(t *testing.T) {
			doc, initial := writePatchTestBundle(t)
			manifestPath := bundle.ManifestPath(doc)
			manifestBefore := patchTestFileBytes(t, manifestPath)

			_, err := Patch(doc, PatchOptions{
				Replace:        []string{"alpha"},
				ExpectHash:     bundle.SHA256Hex(initial),
				StatementsText: tc.statements,
			})
			var validationErr *ValidationError
			if !errors.As(err, &validationErr) {
				t.Fatalf("got %v, want ValidationError", err)
			}
			if after := patchTestFileBytes(t, bundle.ViewPath(doc)); string(after) != string(initial) {
				t.Fatalf("out-of-scope patch mutated view")
			}
			if after := patchTestFileBytes(t, manifestPath); string(after) != string(manifestBefore) {
				t.Fatalf("out-of-scope patch mutated manifest")
			}
			if prev := patchTestFileBytes(t, bundle.PrevViewPath(bundle.ViewPath(doc))); prev != nil {
				t.Fatalf("out-of-scope patch created previous-view backup")
			}
		})
	}
}
