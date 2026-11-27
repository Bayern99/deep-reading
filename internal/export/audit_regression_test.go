package export

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"deepread/internal/bundle"
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
}
