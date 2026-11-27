package export

import (
	"encoding/base64"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

const testPixelPNGBase64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="

func testPixelPNG(t *testing.T) []byte {
	t.Helper()
	data, err := base64.StdEncoding.DecodeString(testPixelPNGBase64)
	if err != nil {
		t.Fatal(err)
	}
	return data
}

func writeImageFixture(t *testing.T, docPath, name string, data []byte) string {
	t.Helper()
	path := filepath.Join(filepath.Dir(docPath), filepath.FromSlash(name))
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatal(err)
	}
	return path
}

func TestExportInlineImageEmbedding(t *testing.T) {
	dir := t.TempDir()
	docPath := filepath.Join(dir, "article.md")
	outPath := filepath.Join(dir, "out", "article.html")
	writeImageFixture(t, docPath, "assets/pixel.png", testPixelPNG(t))
	raw := "# Illustrated\n\n![One pixel](assets/pixel.png)\n"
	if err := os.WriteFile(docPath, []byte(raw), 0o644); err != nil {
		t.Fatal(err)
	}

	result, err := Export(docPath, outPath, ExportOptions{})
	if err != nil {
		t.Fatalf("Export failed: %v", err)
	}
	if result.ImageCount != 1 || result.AssetMode != "inline" {
		t.Fatalf("unexpected image metadata: %#v", result)
	}
	data, err := os.ReadFile(outPath)
	if err != nil {
		t.Fatal(err)
	}
	rendered := string(data)
	for _, want := range []string{
		`src="data:image/png;base64,` + testPixelPNGBase64 + `"`,
		`img-src data:;`,
		`display: block`,
		`max-width: 100%`,
	} {
		if !strings.Contains(rendered, want) {
			t.Errorf("inline output missing %q:\n%s", want, rendered)
		}
	}
	if strings.Contains(strings.ToLower(rendered), "<script") {
		t.Fatalf("inline output contains script: %s", rendered)
	}
}

func TestExportInlineImageBudgetsAreAtomic(t *testing.T) {
	t.Run("per-image budget", func(t *testing.T) {
		dir := t.TempDir()
		docPath := filepath.Join(dir, "article.md")
		outPath := filepath.Join(dir, "out", "article.html")
		pixel := testPixelPNG(t)
		writeImageFixture(t, docPath, "assets/pixel.png", pixel)
		if err := os.WriteFile(docPath, []byte("![Pixel](assets/pixel.png)\n"), 0o644); err != nil {
			t.Fatal(err)
		}

		_, err := Export(docPath, outPath, ExportOptions{MaxImageBytes: len(pixel) - 1})
		if !errors.Is(err, ErrAssetBudgetExceeded) {
			t.Fatalf("error = %v, want ErrAssetBudgetExceeded", err)
		}
		if !strings.Contains(err.Error(), "re-run with --external-assets or compress the image") {
			t.Fatalf("budget error lacks remediation hint: %v", err)
		}
		if _, statErr := os.Stat(outPath); !errors.Is(statErr, os.ErrNotExist) {
			t.Fatalf("partial output exists after budget failure: %v", statErr)
		}
	})

	t.Run("total HTML budget", func(t *testing.T) {
		dir := t.TempDir()
		docPath := filepath.Join(dir, "article.md")
		outPath := filepath.Join(dir, "out", "article.html")
		writeImageFixture(t, docPath, "assets/pixel.png", testPixelPNG(t))
		if err := os.WriteFile(docPath, []byte("![Pixel](assets/pixel.png)\n"), 0o644); err != nil {
			t.Fatal(err)
		}

		_, err := Export(docPath, outPath, ExportOptions{MaxHTMLBytes: 128})
		if !errors.Is(err, ErrAssetBudgetExceeded) {
			t.Fatalf("error = %v, want ErrAssetBudgetExceeded", err)
		}
		if !strings.Contains(err.Error(), "total HTML exceeds budget; re-run with --external-assets or compress images") {
			t.Fatalf("budget error lacks remediation hint: %v", err)
		}
		if _, statErr := os.Stat(outPath); !errors.Is(statErr, os.ErrNotExist) {
			t.Fatalf("partial output exists after budget failure: %v", statErr)
		}
	})
}

func TestExportInlineImageRejectsUnsafePathsAndInvalidContent(t *testing.T) {
	dir := t.TempDir()
	docPath := filepath.Join(dir, "article.md")
	outPath := filepath.Join(dir, "out", "article.html")
	outside := filepath.Join(filepath.Dir(dir), "outside.png")
	if err := os.WriteFile(outside, testPixelPNG(t), 0o644); err != nil {
		t.Fatal(err)
	}

	tests := []struct {
		name        string
		destination string
		prepare     func(t *testing.T)
		unsafePath  bool
	}{
		{name: "parent traversal", destination: "../outside.png", unsafePath: true},
		{name: "absolute path", destination: "/etc/hosts", unsafePath: true},
		{name: "percent-decoded traversal", destination: "%2E%2E/outside.png?ignored=1#fragment", unsafePath: true},
		{name: "symlink outside document directory", destination: "assets/escape.png", unsafePath: true, prepare: func(t *testing.T) {
			if err := os.MkdirAll(filepath.Join(dir, "assets"), 0o755); err != nil {
				t.Fatal(err)
			}
			if err := os.Symlink(outside, filepath.Join(dir, "assets", "escape.png")); err != nil {
				t.Skipf("symlinks unavailable: %v", err)
			}
		}},
		{name: "protected metadata", destination: ".deepread/manifest.json", unsafePath: true},
		{name: "symlink into protected metadata", destination: "assets/metadata.png", unsafePath: true, prepare: func(t *testing.T) {
			metadataDir := filepath.Join(dir, ".deepread")
			if err := os.MkdirAll(metadataDir, 0o755); err != nil {
				t.Fatal(err)
			}
			metadataImage := filepath.Join(metadataDir, "hidden.png")
			if err := os.WriteFile(metadataImage, testPixelPNG(t), 0o644); err != nil {
				t.Fatal(err)
			}
			if err := os.MkdirAll(filepath.Join(dir, "assets"), 0o755); err != nil {
				t.Fatal(err)
			}
			if err := os.Symlink(metadataImage, filepath.Join(dir, "assets", "metadata.png")); err != nil {
				t.Skipf("symlinks unavailable: %v", err)
			}
		}},
		{name: "spoofed PNG", destination: "assets/fake.png", prepare: func(t *testing.T) {
			writeImageFixture(t, docPath, "assets/fake.png", []byte(`<svg><script>alert(1)</script></svg>`))
		}},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			if tc.prepare != nil {
				tc.prepare(t)
			}
			raw := "![Unsafe](" + tc.destination + ")\n"
			if err := os.WriteFile(docPath, []byte(raw), 0o644); err != nil {
				t.Fatal(err)
			}
			_, err := Export(docPath, outPath, ExportOptions{})
			if err == nil {
				t.Fatal("unsafe image was exported")
			}
			if tc.unsafePath && !errors.Is(err, ErrUnsafeAssetPath) {
				t.Fatalf("error = %v, want ErrUnsafeAssetPath", err)
			}
			if !tc.unsafePath && !strings.Contains(strings.ToLower(err.Error()), "mime") {
				t.Fatalf("error = %v, want invalid image MIME error", err)
			}
			if _, statErr := os.Stat(outPath); !errors.Is(statErr, os.ErrNotExist) {
				t.Fatalf("partial output exists after unsafe image failure: %v", statErr)
			}
		})
	}
}

func TestExportInlineImageNeutralizesUnsafeSchemesAndPreservesLinksSecurity(t *testing.T) {
	dir := t.TempDir()
	docPath := filepath.Join(dir, "article.md")
	outPath := filepath.Join(dir, "article.html")
	raw := strings.Join([]string{
		"![Script](javascript:alert(1))",
		"![HTML](data:text/html;base64,PHNjcmlwdD4=)",
		"![SVG](data:image/svg+xml;base64,PHN2Zz4=)",
		"![Remote](https://example.com/remote.png)",
		"[script](javascript:alert(1)) [data](data:text/html,boom)",
	}, "\n\n")
	if err := os.WriteFile(docPath, []byte(raw), 0o644); err != nil {
		t.Fatal(err)
	}
	result, err := Export(docPath, outPath, ExportOptions{})
	if err != nil {
		t.Fatalf("Export failed: %v", err)
	}
	if result.ImageCount != 0 || result.AssetMode != "inline" {
		t.Fatalf("unexpected image metadata: %#v", result)
	}
	data, err := os.ReadFile(outPath)
	if err != nil {
		t.Fatal(err)
	}
	rendered := string(data)
	for _, banned := range []string{`src="javascript:`, `src="data:text/html`, `src="data:image/svg+xml`, `href="javascript:`, `href="data:`} {
		if strings.Contains(rendered, banned) {
			t.Errorf("unsafe URL survived as %q: %s", banned, rendered)
		}
	}
	if !strings.Contains(rendered, `src="https://example.com/remote.png"`) {
		t.Fatalf("remote HTTPS image was not preserved: %s", rendered)
	}
}

func TestExportExternalImagesCopiesAssets(t *testing.T) {
	dir := t.TempDir()
	docPath := filepath.Join(dir, "source", "article.md")
	outDir := filepath.Join(dir, "published")
	outPath := filepath.Join(outDir, "index.html")
	sourceImage := writeImageFixture(t, docPath, "assets/chart.png", testPixelPNG(t))
	if err := os.MkdirAll(filepath.Dir(docPath), 0o755); err != nil {
		t.Fatal(err)
	}
	raw := "# External\n\n![Chart](./assets/chart.png?view=print#figure)\n"
	if err := os.WriteFile(docPath, []byte(raw), 0o644); err != nil {
		t.Fatal(err)
	}

	result, err := Export(docPath, outPath, ExportOptions{ExternalAssets: true})
	if err != nil {
		t.Fatalf("Export failed: %v", err)
	}
	if result.ImageCount != 1 || result.AssetMode != "external" {
		t.Fatalf("unexpected image metadata: %#v", result)
	}
	data, err := os.ReadFile(outPath)
	if err != nil {
		t.Fatal(err)
	}
	rendered := string(data)
	for _, want := range []string{`src="assets/chart.png"`, `img-src 'self' data:;`} {
		if !strings.Contains(rendered, want) {
			t.Errorf("external output missing %q: %s", want, rendered)
		}
	}
	if strings.Contains(strings.ToLower(rendered), "<script") {
		t.Fatalf("external output contains script: %s", rendered)
	}
	copied, err := os.ReadFile(filepath.Join(outDir, "assets", "chart.png"))
	if err != nil {
		t.Fatalf("copied image missing: %v", err)
	}
	source, err := os.ReadFile(sourceImage)
	if err != nil {
		t.Fatal(err)
	}
	if string(copied) != string(source) {
		t.Fatal("copied image differs from source")
	}
}
