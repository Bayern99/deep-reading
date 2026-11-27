package ingest

import (
	"archive/zip"
	"bytes"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"deepread/internal/bundle"
)

func TestAuditRegressionsIngest(t *testing.T) {
	t.Run("same-named markdown from another dir cannot overwrite existing bundle", func(t *testing.T) {
		dirA := t.TempDir()
		dirB := t.TempDir()
		outDir := filepath.Join(t.TempDir(), "bundle")
		docA := filepath.Join(dirA, "s.md")
		docB := filepath.Join(dirB, "s.md")
		_ = os.WriteFile(docA, []byte("# A\n\nBody A.\n"), 0o644)
		_ = os.WriteFile(docB, []byte("# B\n\nBody B.\n"), 0o644)

		if _, err := Ingest(docA, outDir, Options{}); err != nil {
			t.Fatalf("first ingest failed: %v", err)
		}
		if _, err := Ingest(docB, outDir, Options{}); !errors.Is(err, bundle.ErrDocMismatch) {
			t.Fatalf("expected ErrDocMismatch overwriting existing bundle, got %v", err)
		}
		got, _ := os.ReadFile(filepath.Join(outDir, "s.md"))
		if !strings.Contains(string(got), "Body A.") {
			t.Fatalf("existing bundle prose was overwritten: %q", string(got))
		}
	})

	t.Run("reference-style image, percent-encoded path, and inline/fenced code spans", func(t *testing.T) {
		srcDir := t.TempDir()
		outDir := t.TempDir()
		_ = os.MkdirAll(filepath.Join(srcDir, "img dir"), 0o755)
		_ = os.WriteFile(filepath.Join(srcDir, "img dir", "my fig.png"), testPNG, 0o644)
		_ = os.WriteFile(filepath.Join(srcDir, "ref.png"), testPNG, 0o644)

		raw := strings.Join([]string{
			"# Essay",
			"",
			"Inline code example stays untouched: `![example](img%20dir/my%20fig.png)`.",
			"",
			"Multi-line code span stays untouched: `see",
			"![manual](manual.png)`.",
			"",
			"Escaped backtick before code span: \\` and `![escaped](img%20dir/my%20fig.png)`.",
			"",
			"```markdown",
			"![fenced](img%20dir/my%20fig.png)",
			"```",
			"",
			"![Encoded](img%20dir/my%20fig.png)",
			"",
			"![RefImg][figref]",
			"",
			"[figref]: ref.png",
			"",
		}, "\n")
		src := filepath.Join(srcDir, "essay.md")
		_ = os.WriteFile(src, []byte(raw), 0o644)

		res, err := Ingest(src, outDir, Options{})
		if err != nil {
			t.Fatalf("Ingest failed: %v", err)
		}
		if res.ImageCount != 2 {
			t.Fatalf("ImageCount = %d, want 2", res.ImageCount)
		}
		outBytes, _ := os.ReadFile(filepath.Join(outDir, "essay.md"))
		outText := string(outBytes)
		if !strings.Contains(outText, "`![example](img%20dir/my%20fig.png)`") {
			t.Fatalf("inline code span was wrongly rewritten:\n%s", outText)
		}
		if !strings.Contains(outText, "![manual](manual.png)") {
			t.Fatalf("multi-line code span was wrongly rewritten:\n%s", outText)
		}
		if !strings.Contains(outText, "`![escaped](img%20dir/my%20fig.png)`") {
			t.Fatalf("code span after escaped backtick was wrongly rewritten:\n%s", outText)
		}
		if !strings.Contains(outText, "![fenced](img%20dir/my%20fig.png)") {
			t.Fatalf("fenced code block was wrongly rewritten:\n%s", outText)
		}
		if !strings.Contains(outText, "![Encoded](assets/my-fig.png)") {
			t.Fatalf("percent-encoded image was not rewritten:\n%s", outText)
		}
		if !strings.Contains(outText, "[figref]: assets/ref.png") {
			t.Fatalf("reference-style image definition was not rewritten:\n%s", outText)
		}
	})

	t.Run("markdown ingest blocks reading protected .deepread metadata or sidecar", func(t *testing.T) {
		srcDir := t.TempDir()
		_ = os.MkdirAll(filepath.Join(srcDir, ".deepread"), 0o755)
		_ = os.WriteFile(filepath.Join(srcDir, ".deepread", "hidden.png"), testPNG, 0o644)
		src := filepath.Join(srcDir, "doc.md")
		_ = os.WriteFile(src, []byte("![bad](.deepread/hidden.png)\n"), 0o644)

		out := filepath.Join(t.TempDir(), "out")
		if _, err := Ingest(src, out, Options{}); !errors.Is(err, ErrUnsafeArchive) {
			t.Fatalf("expected ErrUnsafeArchive for .deepread image, got %v", err)
		}
		if _, statErr := os.Stat(out); !errors.Is(statErr, os.ErrNotExist) {
			t.Fatalf("output created despite rejected ingest")
		}

		// Relative srcPath referencing its own sidecar must also be rejected.
		wd, _ := os.Getwd()
		defer func() { _ = os.Chdir(wd) }()
		_ = os.WriteFile(filepath.Join(srcDir, ".rel.md.genui.json"), testPNG, 0o644)
		_ = os.WriteFile(filepath.Join(srcDir, "rel.md"), []byte("![sidecar](.rel.md.genui.json)\n"), 0o644)
		if err := os.Chdir(srcDir); err == nil {
			if _, err := Ingest("rel.md", filepath.Join(t.TempDir(), "out"), Options{}); !errors.Is(err, ErrUnsafeArchive) {
				t.Fatalf("expected ErrUnsafeArchive for relative srcPath sidecar image, got %v", err)
			}
		}

		// Target directory containing only a corrupt .deepread/manifest.json must
		// still return ErrDocMismatch (exit 5), not a JSON parse error (exit 1).
		corruptOut := t.TempDir()
		_ = os.MkdirAll(filepath.Join(corruptOut, ".deepread"), 0o755)
		_ = os.WriteFile(filepath.Join(corruptOut, ".deepread", "manifest.json"), []byte("{corrupt"), 0o644)
		cleanDoc := filepath.Join(srcDir, "clean.md")
		_ = os.WriteFile(cleanDoc, []byte("# Clean\n\nBody.\n"), 0o644)
		if _, err := Ingest(cleanDoc, corruptOut, Options{}); !errors.Is(err, bundle.ErrDocMismatch) {
			t.Fatalf("expected ErrDocMismatch for non-empty dir with corrupt manifest, got %v", err)
		}
	})

	t.Run("EPUB rejects non-empty output dir cleanly without partial writes, preserves br/asterisks and literal percent filenames", func(t *testing.T) {
		epubPath := filepath.Join(t.TempDir(), "sample.epub")
		var buf bytes.Buffer
		zw := zip.NewWriter(&buf)
		add := func(name string, data []byte) {
			w, err := zw.Create(name)
			if err != nil {
				t.Fatal(err)
			}
			if _, err := w.Write(data); err != nil {
				t.Fatal(err)
			}
		}
		add("META-INF/container.xml", []byte(`<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>`))
		add("OEBPS/content.opf", []byte(`<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Book</dc:title></metadata><manifest><item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/><item id="img1" href="fig%251.png" media-type="image/png"/></manifest><spine><itemref idref="ch1"/></spine></package>`))
		add("OEBPS/fig%1.png", testPNG)
		add("OEBPS/ch1.xhtml", []byte(`<html><body><h1>Chapter One</h1><div>Direct div *literal* text.</div><p>Line one<br/>Line two with 2*3*4 literal asterisks and enough words to count as prose.</p><img src="fig%251.png" alt="Pct"/></body></html>`))
		if err := zw.Close(); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(epubPath, buf.Bytes(), 0o644); err != nil {
			t.Fatal(err)
		}

		// Non-empty directory must be rejected with ErrDocMismatch and untouched.
		occupied := t.TempDir()
		_ = os.WriteFile(filepath.Join(occupied, "keep.txt"), []byte("keep"), 0o644)
		if _, err := Ingest(epubPath, occupied, Options{}); !errors.Is(err, bundle.ErrDocMismatch) {
			t.Fatalf("expected ErrDocMismatch for non-empty EPUB outDir, got %v", err)
		}
		if _, statErr := os.Stat(filepath.Join(occupied, "index.md")); !errors.Is(statErr, os.ErrNotExist) {
			t.Fatalf("partial index.md left in occupied dir")
		}

		// Fresh target succeeds with preserved <br>, escaped literal '*', and single-decoded %25 -> %.
		fresh := filepath.Join(t.TempDir(), "book")
		res, err := Ingest(epubPath, fresh, Options{})
		if err != nil {
			t.Fatalf("EPUB ingest failed: %v", err)
		}
		if res.ImageCount != 1 || len(res.Chapters) != 1 {
			t.Fatalf("unexpected EPUB result: %#v", res)
		}
		chBytes, _ := os.ReadFile(filepath.Join(fresh, filepath.FromSlash(res.Chapters[0].DocPath)))
		chText := string(chBytes)
		if !strings.Contains(chText, "Line one  \nLine two") {
			t.Fatalf("paragraph <br> hard line break was collapsed:\n%s", chText)
		}
		if !strings.Contains(chText, `2\*3\*4`) || !strings.Contains(chText, `\*literal\*`) {
			t.Fatalf("literal asterisks were not escaped in <p> or <div>:\n%s", chText)
		}
	})
}
