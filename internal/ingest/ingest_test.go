package ingest

import (
	"archive/zip"
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"deepread/internal/bundle"
)

var testPNG = []byte{
	0x89, 'P', 'N', 'G', '\r', '\n', 0x1a, '\n',
	0, 0, 0, 13, 'I', 'H', 'D', 'R',
	0, 0, 0, 1, 0, 0, 0, 1, 8, 6, 0, 0, 0,
}

func TestMarkdownIngestExtractsImagesAndInitializesBundle(t *testing.T) {
	srcDir := t.TempDir()
	outDir := t.TempDir()
	if err := os.Mkdir(filepath.Join(srcDir, "images"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(srcDir, "images", "cover.png"), testPNG, 0o644); err != nil {
		t.Fatal(err)
	}
	prose := "# A Local Essay\n\nUnchanged prose, with *formatting* and 中文。\n\n![Cover](images/cover.png \"A cover\")\n\nFinal prose stays byte-for-byte intact.\n"
	src := filepath.Join(srcDir, "essay.md")
	if err := os.WriteFile(src, []byte(prose), 0o644); err != nil {
		t.Fatal(err)
	}

	got, err := Ingest(src, outDir, Options{})
	if err != nil {
		t.Fatalf("Ingest: %v", err)
	}
	if got.Kind != "markdown" || got.Title != "A Local Essay" || got.DocPath != "essay.md" || got.ImageCount != 1 || got.BundleID == "" {
		t.Fatalf("unexpected result: %+v", got)
	}
	raw, err := os.ReadFile(filepath.Join(outDir, "essay.md"))
	if err != nil {
		t.Fatal(err)
	}
	want := strings.Replace(prose, "images/cover.png", "assets/cover.png", 1)
	if string(raw) != want {
		t.Fatalf("prose changed\nwant:\n%s\ngot:\n%s", want, raw)
	}
	image, err := os.ReadFile(filepath.Join(outDir, "assets", "cover.png"))
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(image, testPNG) {
		t.Fatal("copied image differs from source")
	}
	m, found, err := bundle.LoadManifest(filepath.Join(outDir, "essay.md"), raw)
	if err != nil || !found || m.DocID != "essay.md" || m.BundleID != got.BundleID {
		t.Fatalf("manifest = %+v, found=%v, err=%v", m, found, err)
	}
	report, err := bundle.Inspect(filepath.Join(outDir, got.DocPath), bundle.InspectOptions{})
	if err != nil {
		t.Fatalf("Inspect: %v", err)
	}
	if report.BundleID != got.BundleID || len(report.Sections) != 1 {
		t.Fatalf("unexpected inspection: %+v", report)
	}
}

func TestMarkdownIngestSecurityAndDocMismatch(t *testing.T) {
	t.Run("parent escape", func(t *testing.T) {
		srcDir := t.TempDir()
		src := filepath.Join(srcDir, "essay.md")
		if err := os.WriteFile(src, []byte("![secret](../secret.png)"), 0o644); err != nil {
			t.Fatal(err)
		}
		out := filepath.Join(t.TempDir(), "out")
		_, err := Ingest(src, out, Options{})
		if !errors.Is(err, ErrUnsafeArchive) {
			t.Fatalf("error = %v, want ErrUnsafeArchive", err)
		}
		if _, statErr := os.Stat(out); !errors.Is(statErr, os.ErrNotExist) {
			t.Fatalf("output was mutated on rejection: %v", statErr)
		}
	})

	t.Run("symlink escape", func(t *testing.T) {
		srcDir := t.TempDir()
		outside := t.TempDir()
		if err := os.WriteFile(filepath.Join(outside, "outside.png"), testPNG, 0o644); err != nil {
			t.Fatal(err)
		}
		if err := os.Symlink(filepath.Join(outside, "outside.png"), filepath.Join(srcDir, "linked.png")); err != nil {
			t.Skipf("symlink unavailable: %v", err)
		}
		src := filepath.Join(srcDir, "essay.md")
		if err := os.WriteFile(src, []byte("![outside](linked.png)"), 0o644); err != nil {
			t.Fatal(err)
		}
		_, err := Ingest(src, t.TempDir(), Options{})
		if !errors.Is(err, ErrUnsafeArchive) {
			t.Fatalf("error = %v, want ErrUnsafeArchive", err)
		}
	})

	t.Run("SVG pretending to be PNG", func(t *testing.T) {
		srcDir := t.TempDir()
		if err := os.WriteFile(filepath.Join(srcDir, "fake.png"), []byte(`<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>`), 0o644); err != nil {
			t.Fatal(err)
		}
		src := filepath.Join(srcDir, "essay.md")
		if err := os.WriteFile(src, []byte("![fake](fake.png)"), 0o644); err != nil {
			t.Fatal(err)
		}
		_, err := Ingest(src, t.TempDir(), Options{})
		if !errors.Is(err, ErrUnsafeArchive) {
			t.Fatalf("error = %v, want ErrUnsafeArchive", err)
		}
	})

	t.Run("existing different document", func(t *testing.T) {
		srcDir := t.TempDir()
		src := filepath.Join(srcDir, "incoming.md")
		raw := []byte("# Incoming\n")
		if err := os.WriteFile(src, raw, 0o644); err != nil {
			t.Fatal(err)
		}
		out := t.TempDir()
		existing := filepath.Join(out, "chapter.md")
		if err := bundle.WriteFileAtomic(existing, []byte("# Existing\n"), 0o644); err != nil {
			t.Fatal(err)
		}
		m, _, err := bundle.LoadManifest(existing, []byte("# Existing\n"))
		if err != nil {
			t.Fatal(err)
		}
		if err := bundle.SaveManifest(existing, m); err != nil {
			t.Fatal(err)
		}
		before, err := os.ReadFile(bundle.ManifestPath(existing))
		if err != nil {
			t.Fatal(err)
		}
		_, err = Ingest(src, out, Options{})
		if !errors.Is(err, bundle.ErrDocMismatch) {
			t.Fatalf("error = %v, want ErrDocMismatch", err)
		}
		if _, statErr := os.Stat(filepath.Join(out, "incoming.md")); !errors.Is(statErr, os.ErrNotExist) {
			t.Fatalf("incoming document was written: %v", statErr)
		}
		after, readErr := os.ReadFile(bundle.ManifestPath(existing))
		if readErr != nil || !bytes.Equal(before, after) {
			t.Fatalf("existing manifest changed: %v", readErr)
		}
	})
}

func TestEPUB3IngestChaptersTOCImagesAndIsolatedBundles(t *testing.T) {
	book := makeEPUB(t, epubOptions{
		epub3:   true,
		title:   "The Example Book",
		creator: "Ada Author",
		files: map[string]string{
			"OEBPS/ch1.xhtml": `<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Fallback One</title><style>p{display:none}</style></head><body><h1>Opening</h1><p>This opening chapter contains enough thoughtful words to remain a real chapter in the finished book.</p><blockquote>A quotation worth keeping.</blockquote><ul><li>First item</li><li>Second item</li></ul><table><tr><th>Name</th><th>Value</th></tr><tr><td>Alpha</td><td>One</td></tr></table><p><a href="https://example.com">Safe link</a> <a href="javascript:alert(1)">Unsafe link</a> <a href="other.xhtml">Internal link</a></p><script>alert("remove me")</script><p><img src="images/photo.png" alt="Photograph" /></p></body></html>`,
			"OEBPS/ch2.xhtml": `<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Second Document Title</title></head><body><p>The second chapter also has ample prose so that its distinct table of contents title can be checked.</p><ol><li>One</li><li>Two</li></ol><hr /></body></html>`,
			"OEBPS/nav.xhtml": `<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><body><nav epub:type="toc"><ol><li><a href="ch1.xhtml">Contents Opening</a></li><li><a href="ch2.xhtml">Contents Second</a></li></ol></nav></body></html>`,
		},
		images: map[string][]byte{"OEBPS/images/photo.png": testPNG},
		spine:  []string{"ch1", "ch2"},
	})

	out := t.TempDir()
	got, err := Ingest(book, out, Options{})
	if err != nil {
		t.Fatalf("Ingest EPUB 3: %v", err)
	}
	if got.Kind != "epub" || got.Title != "The Example Book" || got.Author != "Ada Author" || got.IndexPath != "index.md" || got.BookJSON != "book.json" || len(got.Chapters) != 2 || got.ImageCount != 1 {
		t.Fatalf("unexpected result: %+v", got)
	}
	if got.Chapters[0].Title != "Contents Opening" || got.Chapters[1].Title != "Contents Second" {
		t.Fatalf("TOC titles not used: %+v", got.Chapters)
	}
	if got.Chapters[0].WordCount < 8 || got.Chapters[0].ImageCount != 1 || got.Chapters[1].Index != 2 {
		t.Fatalf("unexpected chapter stats: %+v", got.Chapters)
	}

	ch1 := filepath.Join(out, filepath.FromSlash(got.Chapters[0].DocPath))
	raw, err := os.ReadFile(ch1)
	if err != nil {
		t.Fatal(err)
	}
	text := string(raw)
	for _, want := range []string{"# Contents Opening", "> A quotation worth keeping.", "- First item", "| Name | Value |", "[Safe link](https://example.com)", "![Photograph](assets/photo.png)"} {
		if !strings.Contains(text, want) {
			t.Errorf("chapter missing %q:\n%s", want, text)
		}
	}
	for _, unwanted := range []string{"alert(", "display:none", "](javascript:", "](other.xhtml)"} {
		if strings.Contains(text, unwanted) {
			t.Errorf("chapter contains unsafe/stripped content %q:\n%s", unwanted, text)
		}
	}
	if !strings.Contains(text, "Unsafe link") || !strings.Contains(text, "Internal link") {
		t.Fatalf("unsafe/internal links should remain plain text:\n%s", text)
	}
	if _, err := os.Stat(filepath.Join(filepath.Dir(ch1), "assets", "photo.png")); err != nil {
		t.Fatalf("chapter-local image: %v", err)
	}
	for _, chapter := range got.Chapters {
		doc := filepath.Join(out, filepath.FromSlash(chapter.DocPath))
		m, found, err := bundle.LoadManifest(doc, mustReadFile(t, doc))
		if err != nil || !found || m.DocID != "chapter.md" || m.BundleID != chapter.BundleID {
			t.Fatalf("chapter manifest = %+v found=%v err=%v", m, found, err)
		}
		report, err := bundle.Inspect(doc, bundle.InspectOptions{})
		if err != nil {
			t.Fatalf("Inspect %s: %v", chapter.DocPath, err)
		}
		if report.BundleID != chapter.BundleID {
			t.Fatalf("Inspect bundle ID = %q, want %q", report.BundleID, chapter.BundleID)
		}
	}
	index := string(mustReadFile(t, filepath.Join(out, "index.md")))
	if !strings.Contains(index, "The Example Book") || !strings.Contains(index, "Ada Author") || !strings.Contains(index, "| # | Title | Words | Images | Path |") || !strings.Contains(index, got.Chapters[0].DocPath) {
		t.Fatalf("unexpected index:\n%s", index)
	}
	var persisted Result
	if err := json.Unmarshal(mustReadFile(t, filepath.Join(out, "book.json")), &persisted); err != nil {
		t.Fatalf("book.json: %v", err)
	}
	if persisted.Title != got.Title || len(persisted.Chapters) != len(got.Chapters) {
		t.Fatalf("book.json differs: %+v", persisted)
	}
}

func TestEPUB2NCXAndShortChapterHandling(t *testing.T) {
	book := makeEPUB(t, epubOptions{
		title:   "EPUB Two",
		creator: "Grace Writer",
		files: map[string]string{
			"OPS/one.xhtml": `<html><head><title>Ignored fallback</title></head><body><h2>Heading in body</h2><p>A complete first chapter with enough plain prose to be retained by the ingestion filter.</p></body></html>`,
			"OPS/two.xhtml": `<html><body><p>Tiny.</p></body></html>`,
			"OPS/toc.ncx":   `<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/"><navMap><navPoint><navLabel><text>NCX Opening</text></navLabel><content src="one.xhtml#start" /></navPoint><navPoint><navLabel><text>NCX Tiny</text></navLabel><content src="two.xhtml" /></navPoint></navMap></ncx>`,
		},
		spine: []string{"one", "two"},
		ncxID: "ncx",
	})
	got, err := Ingest(book, t.TempDir(), Options{})
	if err != nil {
		t.Fatalf("Ingest EPUB 2: %v", err)
	}
	if len(got.Chapters) != 1 || got.Chapters[0].Title != "NCX Opening" {
		t.Fatalf("EPUB 2 chapters = %+v", got.Chapters)
	}
	if got.Chapters[0].Index != 1 || got.Chapters[0].DocPath != "chapters/01-ncx-opening/chapter.md" {
		t.Fatalf("chapter renumbering/path = %+v", got.Chapters[0])
	}

	onlyShort := makeEPUB(t, epubOptions{
		title: "Short Book",
		files: map[string]string{"OPS/only.xhtml": `<html><body><p>A brief but valid complete chapter.</p></body></html>`},
		spine: []string{"only"},
	})
	shortResult, err := Ingest(onlyShort, t.TempDir(), Options{})
	if err != nil || len(shortResult.Chapters) != 1 {
		t.Fatalf("only short chapter must survive: result=%+v err=%v", shortResult, err)
	}
}

func TestEPUBSkipsCoverDespiteLongDocumentTitle(t *testing.T) {
	book := makeEPUB(t, epubOptions{
		files: map[string]string{
			"OEBPS/cover.xhtml": `<html><head><title>A very long cover document title with more than eight words</title></head><body><p>Cover</p></body></html>`,
			"OEBPS/ch.xhtml":    `<html><body><h1>Real Chapter</h1><p>This chapter has substantial visible prose and should be the only retained section.</p></body></html>`,
		},
		spine: []string{"cover", "ch"},
	})
	got, err := Ingest(book, t.TempDir(), Options{})
	if err != nil {
		t.Fatal(err)
	}
	if len(got.Chapters) != 1 || got.Chapters[0].Title != "Real Chapter" {
		t.Fatalf("cover was not filtered: %+v", got.Chapters)
	}
}

func TestEPUBArchiveSecurity(t *testing.T) {
	t.Run("zip slip", func(t *testing.T) {
		book := makeEPUB(t, epubOptions{
			files: map[string]string{"../../evil.xhtml": `<html><body><p>This malicious chapter has enough words to matter.</p></body></html>`},
			spine: []string{"evil"},
		})
		_, err := Ingest(book, t.TempDir(), Options{})
		if !errors.Is(err, ErrUnsafeArchive) {
			t.Fatalf("error = %v, want ErrUnsafeArchive", err)
		}
	})

	t.Run("decompression bomb total cap", func(t *testing.T) {
		book := makeEPUB(t, epubOptions{
			files: map[string]string{"OPS/ch.xhtml": `<html><body><p>` + strings.Repeat("bomb ", 400) + `</p></body></html>`},
			spine: []string{"ch"},
		})
		_, err := Ingest(book, t.TempDir(), Options{MaxTotalBytes: 700, MaxFileBytes: 4096, MaxEntries: 20})
		if !errors.Is(err, ErrArchiveLimit) {
			t.Fatalf("error = %v, want ErrArchiveLimit", err)
		}
	})

	t.Run("entry count cap", func(t *testing.T) {
		book := makeEPUB(t, epubOptions{files: map[string]string{"OPS/ch.xhtml": `<html><body><p>Enough words are present in this chapter to make it valid input.</p></body></html>`}, spine: []string{"ch"}})
		_, err := Ingest(book, t.TempDir(), Options{MaxEntries: 1})
		if !errors.Is(err, ErrArchiveLimit) {
			t.Fatalf("error = %v, want ErrArchiveLimit", err)
		}
	})
}

func TestIngestUnsupportedAndPerFileLimit(t *testing.T) {
	if _, err := Ingest("book.docx", t.TempDir(), Options{}); !errors.Is(err, ErrUnsupportedFormat) {
		t.Fatalf("unsupported error = %v", err)
	}
	srcDir := t.TempDir()
	src := filepath.Join(srcDir, "large.md")
	if err := os.WriteFile(src, []byte(strings.Repeat("x", 65)), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := Ingest(src, t.TempDir(), Options{MaxFileBytes: 64}); !errors.Is(err, ErrArchiveLimit) {
		t.Fatalf("markdown limit error = %v", err)
	}
}

type epubOptions struct {
	epub3   bool
	title   string
	creator string
	files   map[string]string
	images  map[string][]byte
	spine   []string
	ncxID   string
}

func makeEPUB(t *testing.T, opts epubOptions) string {
	t.Helper()
	if opts.title == "" {
		opts.title = "Synthetic Book"
	}
	if opts.creator == "" {
		opts.creator = "Test Author"
	}
	if opts.ncxID == "" && !opts.epub3 {
		opts.ncxID = "ncx"
	}
	var buf bytes.Buffer
	zw := zip.NewWriter(&buf)
	write := func(name string, data []byte) {
		t.Helper()
		w, err := zw.Create(name)
		if err != nil {
			t.Fatal(err)
		}
		if _, err := w.Write(data); err != nil {
			t.Fatal(err)
		}
	}
	write("mimetype", []byte("application/epub+zip"))
	opfDir := "OEBPS"
	if strings.Contains(fmt.Sprint(opts.files), "OPS/") || opts.files["OPS/toc.ncx"] != "" {
		opfDir = "OPS"
	}
	for name := range opts.files {
		if strings.HasPrefix(name, "OPS/") {
			opfDir = "OPS"
		}
	}
	write("META-INF/container.xml", []byte(`<?xml version="1.0"?><container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="`+opfDir+`/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>`))

	var manifest, spine strings.Builder
	ids := map[string]string{}
	for _, id := range opts.spine {
		ids[id] = id + ".xhtml"
	}
	for _, id := range opts.spine {
		href := ids[id]
		if _, ok := opts.files[opfDir+"/"+href]; !ok {
			href = "../" + map[string]string{"OPS": "OEBPS", "OEBPS": "OPS"}[opfDir] + "/" + href
		}
		fmt.Fprintf(&manifest, `<item id=%q href=%q media-type="application/xhtml+xml"/>`, id, href)
		fmt.Fprintf(&spine, `<itemref idref=%q/>`, id)
	}
	if opts.epub3 {
		manifest.WriteString(`<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>`)
	} else {
		manifest.WriteString(`<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>`)
	}
	for name := range opts.images {
		href := strings.TrimPrefix(name, opfDir+"/")
		manifest.WriteString(`<item id="img` + fmt.Sprint(len(ids)) + `" href="` + href + `" media-type="image/png"/>`)
		ids[name] = name
	}
	tocAttr := ""
	if !opts.epub3 {
		tocAttr = ` toc="ncx"`
	}
	opf := `<package xmlns="http://www.idpf.org/2007/opf" xmlns:dc="http://purl.org/dc/elements/1.1/"><metadata><dc:title>` + opts.title + `</dc:title><dc:creator>` + opts.creator + `</dc:creator></metadata><manifest>` + manifest.String() + `</manifest><spine` + tocAttr + `>` + spine.String() + `</spine></package>`
	write(opfDir+"/content.opf", []byte(opf))
	for name, body := range opts.files {
		write(name, []byte(body))
	}
	for name, data := range opts.images {
		write(name, data)
	}
	if err := zw.Close(); err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(t.TempDir(), "book.epub")
	if err := os.WriteFile(path, buf.Bytes(), 0o644); err != nil {
		t.Fatal(err)
	}
	return path
}

func mustReadFile(t *testing.T, path string) []byte {
	t.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	return data
}

func TestStripDownloaderBoilerplate(t *testing.T) {
	cases := []struct {
		name string
		in   string
		want string
	}{
		{
			name: "zlibrary footer with markdown link",
			in:   "Real prose about tariffs.\n\nThis article was downloaded by [zlibrary](https://z-lib.org) from https://wsj.com/articles/tariffs\n",
			want: "Real prose about tariffs.\n",
		},
		{
			name: "plain download footer",
			in:   "Real prose about tariffs.\r\n\r\nThis article was downloaded by zlibrary from https://wsj.com/x\r\n",
			want: "Real prose about tariffs.\r\n",
		},
		{
			name: "downloaded from trailing url",
			in:   "Real prose.\n\nDownloaded from https://example.com/article\n\n\n",
			want: "Real prose.\n",
		},
		{
			name: "stacked footers",
			in:   "Real prose.\n\nDownloaded from https://example.com/a\n\nThis article was downloaded by zlibrary from https://example.com/a\n",
			want: "Real prose.\n",
		},
		{
			name: "real prose ending keeps everything",
			in:   "Real prose.\n\nDownloaded from the archives, the documents reveal a much longer story.\n",
			want: "Real prose.\n\nDownloaded from the archives, the documents reveal a much longer story.\n",
		},
		{
			name: "download mentioned mid-document is untouched",
			in:   "Downloaded from https://example.com/a\n\nThis is the body of the article.\n",
			want: "Downloaded from https://example.com/a\n\nThis is the body of the article.\n",
		},
		{
			name: "no trailing newline",
			in:   "Real prose.\n\nDownloaded from https://example.com/a",
			want: "Real prose.\n",
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := StripDownloaderBoilerplate(tc.in); got != tc.want {
				t.Fatalf("StripDownloaderBoilerplate mismatch:\ngot:  %q\nwant: %q", got, tc.want)
			}
		})
	}
}

func TestMarkdownIngestStripsWatermarkAndRecordsReaderContract(t *testing.T) {
	srcDir := t.TempDir()
	src := filepath.Join(srcDir, "article.md")
	body := "# Grid Report\n\nExact figures stay: $42.5B in 2024.\n\nThis article was downloaded by [zlibrary](https://z-lib.org) from https://wsj.com/articles/grid\n"
	if err := os.WriteFile(src, []byte(body), 0o644); err != nil {
		t.Fatal(err)
	}
	out := t.TempDir()
	res, err := Ingest(src, out, Options{SourceLang: "en-us", TargetLang: "zh-cn", Mode: bundle.ReadModeBilingual})
	if err != nil {
		t.Fatalf("Ingest: %v", err)
	}
	docPath := filepath.Join(out, filepath.Base(src))
	got := string(mustReadFile(t, docPath))
	if strings.Contains(got, "zlibrary") || strings.Contains(got, "This article was downloaded") {
		t.Fatalf("downloader watermark survived ingest:\n%s", got)
	}
	if !strings.Contains(got, "Exact figures stay: $42.5B in 2024.") {
		t.Fatalf("real prose was altered:\n%s", got)
	}
	if res.Reader == nil || res.Reader.SourceLang != "en-US" || res.Reader.TargetLang != "zh-CN" || res.Reader.Mode != bundle.ReadModeBilingual {
		t.Fatalf("result reader contract = %#v", res.Reader)
	}
	manifest, found, err := bundle.LoadManifest(docPath, mustReadFile(t, docPath))
	if err != nil || !found {
		t.Fatalf("manifest: found=%v err=%v", found, err)
	}
	if manifest.Reader == nil || manifest.Reader.TargetLang != "zh-CN" || manifest.Reader.SourceLang != "en-US" {
		t.Fatalf("manifest reader contract = %#v", manifest.Reader)
	}
	blocks := bundle.ExtractBlocks(mustReadFile(t, docPath), manifest)
	for _, b := range blocks {
		if strings.Contains(b.Text, "zlibrary") {
			t.Fatalf("watermark leaked into translatable blocks: %#v", b)
		}
	}
	// toolchain: the reader contract must be inspectable without re-reading options.
	report, err := bundle.Inspect(docPath, bundle.InspectOptions{})
	if err != nil {
		t.Fatalf("Inspect: %v", err)
	}
	if report.Reader == nil || report.Reader.Mode != bundle.ReadModeBilingual {
		t.Fatalf("inspect did not report the reader contract: %#v", report.Reader)
	}
	if report.Translation == nil || report.Translation.Lang != "zh-CN" || report.Translation.TotalBlocks != len(blocks) {
		t.Fatalf("inspect translation status = %#v", report.Translation)
	}
}

func TestIngestRejectsInvalidReaderContractBeforeStaging(t *testing.T) {
	srcDir := t.TempDir()
	src := filepath.Join(srcDir, "article.md")
	if err := os.WriteFile(src, []byte("# Title\n\nProse.\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	out := filepath.Join(t.TempDir(), "bundle")
	if _, err := Ingest(src, out, Options{TargetLang: "../evil"}); !errors.Is(err, bundle.ErrInvalidLang) {
		t.Fatalf("traversal lang error = %v, want ErrInvalidLang", err)
	}
	if _, err := Ingest(src, out, Options{SourceLang: "zh/CN"}); !errors.Is(err, bundle.ErrInvalidLang) {
		t.Fatalf("slash lang error = %v, want ErrInvalidLang", err)
	}
	if _, err := Ingest(src, out, Options{Mode: "half"}); err == nil {
		t.Fatal("invalid read mode accepted")
	}
	if _, err := os.Stat(out); !os.IsNotExist(err) {
		t.Fatalf("invalid options created an output directory: %v", err)
	}
}

func TestEPUBIngestStripsWatermarkAndRecordsReaderContract(t *testing.T) {
	book := makeEPUB(t, epubOptions{
		epub3: true,
		title: "Watermarked Book",
		files: map[string]string{
			"OEBPS/ch1.xhtml": `<html xmlns="http://www.w3.org/1999/xhtml"><body><h1>Markets</h1><p>This chapter keeps enough real prose words to survive the short chapter filter.</p><p>This article was downloaded by [zlibrary](https://z-lib.org) from https://wsj.com/articles/markets</p></body></html>`,
			"OEBPS/nav.xhtml": `<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><body><nav epub:type="toc"><ol><li><a href="ch1.xhtml">Markets</a></li></ol></nav></body></html>`,
		},
		spine: []string{"ch1"},
	})
	out := t.TempDir()
	res, err := Ingest(book, out, Options{SourceLang: "en", TargetLang: "zh-Hans", Mode: bundle.ReadModeTranslated})
	if err != nil {
		t.Fatalf("Ingest EPUB: %v", err)
	}
	if res.Reader == nil || res.Reader.TargetLang != "zh-Hans" {
		t.Fatalf("result reader = %#v", res.Reader)
	}
	if len(res.Chapters) != 1 {
		t.Fatalf("unexpected chapters: %#v", res.Chapters)
	}
	docPath := filepath.Join(out, filepath.FromSlash(res.Chapters[0].DocPath))
	chapter := string(mustReadFile(t, docPath))
	if strings.Contains(chapter, "zlibrary") || strings.Contains(chapter, "was downloaded by") {
		t.Fatalf("watermark survived EPUB ingest:\n%s", chapter)
	}
	manifest, _, err := bundle.LoadManifest(docPath, mustReadFile(t, docPath))
	if err != nil {
		t.Fatal(err)
	}
	if manifest.Reader == nil || manifest.Reader.Mode != bundle.ReadModeTranslated || manifest.Reader.TargetLang != "zh-Hans" {
		t.Fatalf("chapter manifest reader = %#v", manifest.Reader)
	}
	var persisted BookMetadata
	if err := json.Unmarshal(mustReadFile(t, filepath.Join(out, "book.json")), &persisted); err != nil {
		t.Fatalf("book.json: %v", err)
	}
	if persisted.Reader == nil || persisted.Reader.TargetLang != "zh-Hans" {
		t.Fatalf("book.json reader = %#v", persisted.Reader)
	}
}
