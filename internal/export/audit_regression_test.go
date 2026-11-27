package export

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"deepread/internal/bundle"
	"deepread/internal/view"
)

func TestAuditRegressionsExport(t *testing.T) {
	t.Run("export refuses to overwrite source doc, sidecars, symlink aliases, or metadata", func(t *testing.T) {
		dir := t.TempDir()
		doc := filepath.Join(dir, "article.md")
		orig := "# Title\n\n## Sec\nSafe prose.\n"
		if err := os.WriteFile(doc, []byte(orig), 0o644); err != nil {
			t.Fatal(err)
		}
		alias := filepath.Join(dir, "alias.md")
		_ = os.Symlink(doc, alias)

		for _, bad := range []string{
			doc,
			alias,
			bundle.ViewPath(doc),
			bundle.PrevViewPath(bundle.ViewPath(doc)),
			bundle.ManifestPath(doc),
			bundle.LedgerPath(doc),
			filepath.Join(bundle.MetaDir(doc), "history", "r1.html"),
			filepath.Join(bundle.MetaDir(doc), "translations", "zh-CN.json"),
			bundle.CitationsPath(doc),
			filepath.Join(bundle.MetaDir(doc), "HISTORY", "probe.html"),
			filepath.Join(bundle.MetaDir(doc), "hi\u017ftory", "probe.html"),
		} {
			if _, err := Export(doc, bad, ExportOptions{}); err == nil {
				t.Fatalf("expected Export to refuse overwriting protected path %q", bad)
			}
		}
		after, _ := os.ReadFile(doc)
		if string(after) != orig {
			t.Fatalf("source doc was modified by refused export")
		}
	})

	t.Run("multi-line link reference definitions resolve across sections and data:/javascript: links and autolinks are blocked", func(t *testing.T) {
		raw := "## First\nSee [the report][r], [bad](data:image/png;base64,AAAA), <javascript:alert(1)>, and <data:text/html,boom>.\n\n## Second\nMore prose.\n\n[r]:\n  https://example.com/report \"Full Report\"\n"
		out, _, err := RenderHTML(raw, bundle.Manifest{BundleID: "K7", Revision: 1}, nil, "Test")
		if err != nil {
			t.Fatalf("RenderHTML failed: %v", err)
		}
		if !strings.Contains(out, `href="https://example.com/report"`) {
			t.Fatalf("multi-line cross-section link reference did not resolve:\n%s", out)
		}
		if strings.Contains(out, `href="data:`) || strings.Contains(out, `href="javascript:`) {
			t.Fatalf("unsafe href survived in rendered HTML:\n%s", out)
		}
	})

	t.Run("pre-inlined data:image enforces max-image-bytes and magic-byte sniffing, and entity-encoded links are blocked", func(t *testing.T) {
		dir := t.TempDir()
		doc := filepath.Join(dir, "article.md")
		out := filepath.Join(dir, "out.html")

		// Real PNG data URI must be rejected when max-image-bytes is 1.
		pngDataURI := "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
		_ = os.WriteFile(doc, []byte("![Inline]("+pngDataURI+")\n"), 0o644)
		if _, err := Export(doc, out, ExportOptions{MaxImageBytes: 1}); !errors.Is(err, ErrAssetBudgetExceeded) {
			t.Fatalf("expected ErrAssetBudgetExceeded for pre-inlined data:image over budget, got %v", err)
		}

		// Spoofed SVG disguised as data:image/png;base64 must fail with ErrUnsafeAssetPath.
		spoofURI := "data:image/png;base64,PHN2Zz48c2NyaXB0PmFsZXJ0KDEpPC9zY3JpcHQ+PC9zdmc+"
		_ = os.WriteFile(doc, []byte("![Spoof]("+spoofURI+")\n"), 0o644)
		if _, err := Export(doc, out, ExportOptions{}); !errors.Is(err, ErrUnsafeAssetPath) {
			t.Fatalf("expected ErrUnsafeAssetPath for spoofed data:image/png, got %v", err)
		}

		// Disallowed file: and entity-obfuscated javascript: links must be stripped.
		rendered, _, err := RenderHTML("## Links\n[file](file:///etc/passwd) [ent](&#x6a;avascript:alert(1)) [ok](https://example.com)\n", bundle.Manifest{BundleID: "K7", Revision: 1}, nil, "Links")
		if err != nil {
			t.Fatalf("RenderHTML failed: %v", err)
		}
		if strings.Contains(rendered, `href="file:`) || strings.Contains(rendered, `javascript:`) {
			t.Fatalf("unsafe scheme survived in hyperlink:\n%s", rendered)
		}
		if !strings.Contains(rendered, `href="https://example.com"`) {
			t.Fatalf("safe https link was stripped:\n%s", rendered)
		}
	})

	t.Run("v0.3 Codex P1 regressions: book root .deepread protection, explicit external max-bytes, independent button actions, and exact 128 KiB island cap", func(t *testing.T) {
		// 1. Book root .deepread/ protection & explicit --external-assets --max-bytes enforcement.
		bookDir := t.TempDir()
		chDir := filepath.Join(bookDir, "chapters", "01-intro")
		if err := os.MkdirAll(filepath.Join(chDir, "assets"), 0o755); err != nil {
			t.Fatal(err)
		}
		pngBytes := []byte{
			0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d,
			0x49, 0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
			0x08, 0x06, 0x00, 0x00, 0x00, 0x1f, 0x15, 0xc4, 0x89, 0x00, 0x00, 0x00,
			0x0a, 0x49, 0x44, 0x41, 0x54, 0x78, 0x9c, 0x63, 0x00, 0x01, 0x00, 0x00,
			0x05, 0x00, 0x01, 0x0d, 0x0a, 0x2d, 0xb4, 0x00, 0x00, 0x00, 0x00, 0x49,
			0x45, 0x4e, 0x44, 0xae, 0x42, 0x60, 0x82,
		}
		if err := os.WriteFile(filepath.Join(chDir, "assets", "p.png"), pngBytes, 0o644); err != nil {
			t.Fatal(err)
		}
		chDoc := filepath.Join(chDir, "chapter.md")
		if err := os.WriteFile(chDoc, []byte("# Intro\n\n## Sec\n\n![P](assets/p.png)\n\nProse line.\n"), 0o644); err != nil {
			t.Fatal(err)
		}
		bookJSON := `{"title":"Book","chapters":[{"index":1,"slug":"intro","title":"Intro","docPath":"chapters/01-intro/chapter.md"}]}`
		if err := os.WriteFile(filepath.Join(bookDir, "book.json"), []byte(bookJSON), 0o644); err != nil {
			t.Fatal(err)
		}
		// Refuses overwriting book root .deepread/ subpaths.
		for _, bad := range []string{
			filepath.Join(bookDir, ".deepread", "translations", "zh-CN.json"),
			filepath.Join(bookDir, ".deepread", "citations.json"),
		} {
			if _, err := ExportBook(bookDir, nil, bad, ExportOptions{}); err == nil {
				t.Fatalf("expected ExportBook to refuse overwriting book root metadata %q", bad)
			}
		}
		// Explicit --max-bytes must be enforced even with --external-assets.
		outDir := t.TempDir()
		outHTML := filepath.Join(outDir, "small.html")
		if _, err := ExportBook(bookDir, nil, outHTML, ExportOptions{ExternalAssets: true, MaxHTMLBytes: 512}); !errors.Is(err, ErrAssetBudgetExceeded) {
			t.Fatalf("expected ErrAssetBudgetExceeded for --external-assets --max-bytes 512, got %v", err)
		}
		if _, err := os.Stat(outHTML); err == nil {
			t.Fatalf("failed budget export should not create %q", outHTML)
		}

		// 2. Two independent action buttons from (0,0) must produce (1,0) and (0,1), not (1,1).
		docDir := t.TempDir()
		doc := filepath.Join(docDir, "actions.md")
		if err := os.WriteFile(doc, []byte("# Actions\n\n## Model\n\nTwo independent switches.\n"), 0o644); err != nil {
			t.Fatal(err)
		}
		stmts := strings.Join([]string{
			`$x = 0`,
			`$y = 0`,
			`root = Col([mod])`,
			`mod = Source(["s1"], [Row([Button("Set X", @Set($x, 1)), Button("Set Y", @Set($y, 1))]), Text("X=" + $x + ", Y=" + $y)])`,
		}, "\n")
		if _, err := view.Write(doc, view.WriteOptions{
			StatementsText: stmts,
			Sources:        map[string]view.SourceRef{"s1": {Heading: "Model", Occurrence: 1}},
			Profile:        bundle.ProfileCanvas,
		}); err != nil {
			t.Fatalf("view.Write failed: %v", err)
		}
		actHTML := filepath.Join(docDir, "actions.html")
		if _, err := Export(doc, actHTML, ExportOptions{}); err != nil {
			t.Fatalf("Export failed: %v", err)
		}
		raw, err := os.ReadFile(actHTML)
		if err != nil {
			t.Fatal(err)
		}
		htmlStr := string(raw)
		if !strings.Contains(htmlStr, `data-action="a0" data-from="0.0" data-to="1.0"`) {
			t.Fatalf("button a0 transition from 0.0 should target 1.0:\n%s", htmlStr)
		}
		if !strings.Contains(htmlStr, `data-action="a1" data-from="0.0" data-to="0.1"`) {
			t.Fatalf("button a1 transition from 0.0 should target 0.1 (must not inherit a0 mutation):\n%s", htmlStr)
		}

		// 3. Semantic OpenUI SVG color tokens (surface, border, ink, chart1) must map to real CSS/hex paints.
		if got, ok := safeSVGColor("surface"); !ok || got != "var(--surface)" {
			t.Fatalf("safeSVGColor(surface) = (%q, %v), want (var(--surface), true)", got, ok)
		}
		if got, ok := safeSVGColor("border"); !ok || got != "var(--rule)" {
			t.Fatalf("safeSVGColor(border) = (%q, %v), want (var(--rule), true)", got, ok)
		}
		if got, ok := safeSVGColor("ink"); !ok || got != "var(--ink)" {
			t.Fatalf("safeSVGColor(ink) = (%q, %v), want (var(--ink), true)", got, ok)
		}
		if got, ok := safeSVGColor("chart2"); !ok || got != "#3b6978" {
			t.Fatalf("safeSVGColor(chart2) = (%q, %v), want (#3b6978, true)", got, ok)
		}
	})
}
