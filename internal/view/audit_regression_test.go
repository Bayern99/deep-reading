package view

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"deepread/internal/bundle"
)

func TestAuditRegressionsView(t *testing.T) {
	t.Run("stale target prose rejects patch until --expect-source-hash matches live hash", func(t *testing.T) {
		dir := t.TempDir()
		doc := filepath.Join(dir, "article.md")
		if err := os.WriteFile(doc, []byte(sampleDoc), 0o644); err != nil {
			t.Fatal(err)
		}
		stmts := strings.Join([]string{
			`root = Col([capex_cmp])`,
			`capex_cmp = Source(["s1"], [Quote("Firm A reported $18B in 2024 cash capex.", "§1")])`,
		}, "\n")
		w, err := Write(doc, WriteOptions{
			StatementsText: stmts,
			Sources:        map[string]SourceRef{"s1": {Heading: "§1 · Capital Surge", Occurrence: 1}},
		})
		if err != nil {
			t.Fatal(err)
		}

		// Modify prose in §1 so saved sidecar hash becomes stale.
		edited := strings.Replace(sampleDoc, "$18B", "$21B", 1)
		if err := os.WriteFile(doc, []byte(edited), 0o644); err != nil {
			t.Fatal(err)
		}

		// Blind patch with only old viewHash MUST fail with ErrHashConflict.
		_, err = Patch(doc, PatchOptions{
			Replace:        []string{"capex_cmp"},
			ExpectHash:     w.ViewHash,
			StatementsText: `capex_cmp = Source(["s1"], [Quote("Firm A reported $18B in 2024 cash capex.", "§1")])`,
		})
		if !errors.Is(err, ErrHashConflict) {
			t.Fatalf("expected ErrHashConflict when patching stale target prose without ExpectSourceHashes, got %v", err)
		}

		// Blind patch renaming s1 -> fresh for the SAME stale section MUST also fail.
		_, err = Patch(doc, PatchOptions{
			Replace:        []string{"capex_cmp"},
			ExpectHash:     w.ViewHash,
			AddedSources:   map[string]SourceRef{"fresh": {Heading: "§1 · Capital Surge", Occurrence: 1}},
			StatementsText: `capex_cmp = Source(["fresh"], [Quote("Firm A reported $18B in 2024 cash capex.", "§1")])`,
		})
		if !errors.Is(err, ErrHashConflict) {
			t.Fatalf("expected ErrHashConflict when renaming source ID for stale section without ExpectSourceHashes, got %v", err)
		}

		// Inspect fetches live section hash; passing ExpectSourceHashes succeeds.
		rep, err := bundle.Inspect(doc, bundle.InspectOptions{})
		if err != nil {
			t.Fatal(err)
		}
		if len(rep.StaleSources) != 1 {
			t.Fatalf("expected 1 stale source, got %#v", rep.StaleSources)
		}
		liveHash := rep.StaleSources[0].LiveHash
		res, err := Patch(doc, PatchOptions{
			Replace:            []string{"capex_cmp"},
			ExpectHash:         w.ViewHash,
			ExpectSourceHashes: map[string]string{"s1": liveHash},
			StatementsText:     `capex_cmp = Source(["s1"], [Quote("Firm A reported $21B in 2024 cash capex.", "§1")])`,
		})
		if err != nil {
			t.Fatalf("patch with matching ExpectSourceHashes failed: %v", err)
		}
		if res.Revision != 2 {
			t.Fatalf("expected revision 2, got %d", res.Revision)
		}
	})

	t.Run("alias indirection root=[m], m=helper, helper=Source is rejected", func(t *testing.T) {
		dir := t.TempDir()
		doc := filepath.Join(dir, "article.md")
		_ = os.WriteFile(doc, []byte(sampleDoc), 0o644)

		stmts := strings.Join([]string{
			`root = Col([m])`,
			`m = helper`,
			`helper = Source(["s1"], [Quote("Firm A reported $18B.", "§1")])`,
		}, "\n")
		_, err := Write(doc, WriteOptions{
			StatementsText: stmts,
			Sources:        map[string]SourceRef{"s1": {Heading: "§1 · Capital Surge", Occurrence: 1}},
		})
		var ve *ValidationError
		if !errors.As(err, &ve) || ve.Code != "TOP_LEVEL_MUST_BE_SOURCE" {
			t.Fatalf("expected TOP_LEVEL_MUST_BE_SOURCE for alias chain, got %v", err)
		}

		// Ternary conditional wrapping a dead-branch Source(...) must also be rejected.
		ternaryStmts := strings.Join([]string{
			`root = Col([m])`,
			`m = true ? helper : Source(["s1"], [Quote("Firm A reported $18B.", "§1")])`,
			`helper = Source(["s1"], [Quote("Firm A reported $18B.", "§1")])`,
		}, "\n")
		_, err = Write(doc, WriteOptions{
			StatementsText: ternaryStmts,
			Sources:        map[string]SourceRef{"s1": {Heading: "§1 · Capital Surge", Occurrence: 1}},
		})
		if !errors.As(err, &ve) || ve.Code != "TOP_LEVEL_MUST_BE_SOURCE" {
			t.Fatalf("expected TOP_LEVEL_MUST_BE_SOURCE for ternary expression, got %v", err)
		}

		// Ternary whose condition starts with Source(...) must also be rejected.
		leadingSourceTernary := strings.Join([]string{
			`root = Col([m])`,
			`m = Source(["s1"], [Quote("A", "§1")]) ? helper : Source(["s1"], [Quote("B", "§1")])`,
			`helper = Source(["s1"], [Quote("Firm A reported $18B.", "§1")])`,
		}, "\n")
		_, err = Write(doc, WriteOptions{
			StatementsText: leadingSourceTernary,
			Sources:        map[string]SourceRef{"s1": {Heading: "§1 · Capital Surge", Occurrence: 1}},
		})
		if !errors.As(err, &ve) || ve.Code != "TOP_LEVEL_MUST_BE_SOURCE" {
			t.Fatalf("expected TOP_LEVEL_MUST_BE_SOURCE for leading-Source ternary expression, got %v", err)
		}
	})

	t.Run("unwritable history path fails write cleanly without leaving sidecar", func(t *testing.T) {
		dir := t.TempDir()
		doc := filepath.Join(dir, "article.md")
		_ = os.WriteFile(doc, []byte(sampleDoc), 0o644)
		_ = os.MkdirAll(bundle.MetaDir(doc), 0o755)
		// Block .deepread/history with a regular file.
		_ = os.WriteFile(filepath.Join(bundle.MetaDir(doc), "history"), []byte("blocker"), 0o644)

		_, err := Write(doc, WriteOptions{
			StatementsText: "root = Col([q])\nq = Source([\"s1\"], [Quote(\"Firm A reported $18B.\", \"§1\")])",
			Sources:        map[string]SourceRef{"s1": {Heading: "§1 · Capital Surge", Occurrence: 1}},
		})
		if err == nil {
			t.Fatalf("expected Write to fail when history snapshot cannot be written")
		}
		if _, statErr := os.Stat(bundle.ViewPath(doc)); !errors.Is(statErr, os.ErrNotExist) {
			t.Fatalf("expected no partial sidecar left after history write failure, stat err=%v", statErr)
		}
	})
}
