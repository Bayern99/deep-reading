package bundle

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestAuditRegressionsBundle(t *testing.T) {
	t.Run("second doc in same bundle dir rejected with ErrDocMismatch", func(t *testing.T) {
		dir := t.TempDir()
		docA := filepath.Join(dir, "a.md")
		docB := filepath.Join(dir, "b.md")
		_ = os.WriteFile(docA, []byte("## Sec\nHello A.\n"), 0o644)
		_ = os.WriteFile(docB, []byte("## Sec\nHello B.\n"), 0o644)

		if _, err := AddNote(docA, AddNoteOptions{Heading: "Sec", Text: "first note locks docId"}); err != nil {
			t.Fatalf("AddNote on docA failed: %v", err)
		}
		if _, err := Inspect(docB, InspectOptions{}); !errors.Is(err, ErrDocMismatch) {
			t.Fatalf("expected ErrDocMismatch for second doc in same dir, got %v", err)
		}
	})

	t.Run("first note add failure on manifest save leaves zero ledger or doc mutation", func(t *testing.T) {
		dir := t.TempDir()
		docA := filepath.Join(dir, "a.md")
		orig := "## Sec\nHello A.\n"
		_ = os.WriteFile(docA, []byte(orig), 0o644)
		// Block manifest.json with a directory so SaveManifest fails.
		_ = os.MkdirAll(ManifestPath(docA), 0o755)

		if _, err := AddNote(docA, AddNoteOptions{Heading: "Sec", MsgID: "m-fail", Text: "should rollback"}); err == nil {
			t.Fatalf("expected AddNote to fail when manifest cannot be saved")
		}
		afterDoc, _ := os.ReadFile(docA)
		if string(afterDoc) != orig {
			t.Fatalf("doc was mutated on manifest failure")
		}
		if _, err := os.Stat(LedgerPath(docA)); !errors.Is(err, os.ErrNotExist) {
			t.Fatalf("ledger.json should not exist after manifest save failure, stat err=%v", err)
		}
	})

	t.Run("prepare validates corrupt manifest before mutating doc", func(t *testing.T) {
		dir := t.TempDir()
		doc := filepath.Join(dir, "essay.md")
		orig := "Paragraph one.\n\nParagraph two.\n"
		_ = os.WriteFile(doc, []byte(orig), 0o644)
		_ = os.MkdirAll(MetaDir(doc), 0o755)
		_ = os.WriteFile(ManifestPath(doc), []byte("{corrupt json"), 0o644)

		if _, err := Prepare(doc, []BreakSpec{{BeforeLine: 1, Title: "One"}}); err == nil {
			t.Fatalf("expected prepare to fail on corrupt manifest")
		}
		after, _ := os.ReadFile(doc)
		if string(after) != orig {
			t.Fatalf("prepare mutated doc despite corrupt manifest:\ngot:  %q\nwant: %q", string(after), orig)
		}
	})

	t.Run("preserve 0600 permissions and mixed LF/CRLF line endings", func(t *testing.T) {
		dir := t.TempDir()
		doc := filepath.Join(dir, "mixed.md")
		orig := "Line one LF.\n\nLine two CRLF.\r\n\r\nLine three LF.\n"
		if err := os.WriteFile(doc, []byte(orig), 0o600); err != nil {
			t.Fatal(err)
		}
		if _, err := Prepare(doc, []BreakSpec{{BeforeLine: 3, Title: "Middle"}}); err != nil {
			t.Fatalf("Prepare failed: %v", err)
		}
		info, _ := os.Stat(doc)
		if info.Mode().Perm() != 0o600 {
			t.Fatalf("Prepare changed mode to %o, want 0600", info.Mode().Perm())
		}
		updated, _ := os.ReadFile(doc)
		if !strings.Contains(string(updated), "Line one LF.\n") || !strings.Contains(string(updated), "Line two CRLF.\r\n") || !strings.Contains(string(updated), "Line three LF.\n") {
			t.Fatalf("Prepare altered existing mixed line endings: %q", string(updated))
		}
		if _, err := AddNote(doc, AddNoteOptions{Heading: "§1 · Middle", Text: "keep perms"}); err != nil {
			t.Fatalf("AddNote failed: %v", err)
		}
		info2, _ := os.Stat(doc)
		if info2.Mode().Perm() != 0o600 {
			t.Fatalf("AddNote changed mode to %o, want 0600", info2.Mode().Perm())
		}
	})

	t.Run("inspect rejects oversized and corrupt sidecar and returns ErrNotFound for missing heading", func(t *testing.T) {
		dir := t.TempDir()
		doc := filepath.Join(dir, "doc.md")
		_ = os.WriteFile(doc, []byte("## Real\nBody.\n"), 0o644)

		if _, err := Inspect(doc, InspectOptions{Heading: "Missing"}); !errors.Is(err, ErrNotFound) {
			t.Fatalf("expected ErrNotFound for missing heading, got %v", err)
		}
		// Corrupt sidecar
		_ = os.WriteFile(ViewPath(doc), []byte("{not json"), 0o644)
		if _, err := Inspect(doc, InspectOptions{}); err == nil {
			t.Fatalf("expected Inspect to fail on corrupt sidecar")
		}
		// Oversized > 1 MiB sidecar
		big := make([]byte, MaxViewBytes+1)
		for i := range big {
			big[i] = ' '
		}
		_ = os.WriteFile(ViewPath(doc), big, 0o644)
		if _, err := Inspect(doc, InspectOptions{}); err == nil {
			t.Fatalf("expected Inspect to fail on >1MiB sidecar")
		}
		if _, err := AddNote(doc, AddNoteOptions{Node: "m", Text: "hi"}); err == nil {
			t.Fatalf("expected AddNote --node to fail on >1MiB sidecar")
		}
	})
}
