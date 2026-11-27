package export

import (
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"html"
	"os"
	"path"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"

	"deepread/internal/bundle"
	"deepread/internal/genuikit"
	"deepread/internal/markdown"
	"deepread/internal/openuilang"
	"deepread/internal/view"

	"github.com/yuin/goldmark"
	"github.com/yuin/goldmark/ast"
	"github.com/yuin/goldmark/extension"
	"github.com/yuin/goldmark/parser"
	"github.com/yuin/goldmark/text"
	"github.com/yuin/goldmark/util"
)

type exportChapter struct {
	docPath   string
	prefix    string
	title     string
	snap      bundle.DocSnapshot
	parsed    *view.ParsedView
	validated view.ValidationResult
	program   *openuilang.Program
	session   *openuilang.Session
	root      *openuilang.Element
	images    *imageTransformer
	lang      string
	mode      string
}

type bookManifest struct {
	Title    string `json:"title"`
	Chapters []struct {
		Index   int    `json:"index"`
		Slug    string `json:"slug"`
		Title   string `json:"title"`
		DocPath string `json:"docPath"`
	} `json:"chapters"`
}

func exportDocument(docPath, outPath string, opts ExportOptions) (ExportResult, error) {
	if strings.TrimSpace(outPath) == "" {
		return ExportResult{}, fmt.Errorf("export output path is required")
	}
	if err := ensureSafeExportPath(docPath, outPath); err != nil {
		return ExportResult{}, err
	}
	return exportChapters(docPathsWithTitle{paths: []string{docPath}, docPath: docPath}, outPath, opts, nil)
}

type docPathsWithTitle struct {
	paths     []string
	relPaths  []string
	bookRoot  *os.Root
	title     string
	docPath   string
	aggregate bool
}

// ExportChapters aggregates independently bundled chapters in the supplied order.
func ExportChapters(docPaths []string, title string, outPath string, opts ExportOptions) (ExportResult, error) {
	if len(docPaths) == 0 {
		return ExportResult{}, fmt.Errorf("at least one chapter is required")
	}
	if strings.TrimSpace(outPath) == "" {
		return ExportResult{}, fmt.Errorf("export output path is required")
	}
	for _, docPath := range docPaths {
		if err := ensureSafeExportPath(docPath, outPath); err != nil {
			return ExportResult{}, err
		}
	}
	opts.Title = strings.TrimSpace(title)
	return exportChapters(docPathsWithTitle{paths: docPaths, title: title, docPath: docPaths[0], aggregate: true}, outPath, opts, nil)
}

// ExportBook securely resolves book.json and every chapter beneath bookDir.
func ExportBook(bookDir string, chapterSelectors []string, outPath string, opts ExportOptions) (ExportResult, error) {
	if strings.TrimSpace(outPath) == "" {
		return ExportResult{}, fmt.Errorf("export output path is required")
	}
	root, err := os.OpenRoot(bookDir)
	if err != nil {
		return ExportResult{}, fmt.Errorf("open book directory: %w", err)
	}
	defer root.Close()
	raw, err := readBookRegularFile(root, "book.json", 1<<20)
	if err != nil {
		return ExportResult{}, err
	}
	var metadata bookManifest
	if err := json.Unmarshal(raw, &metadata); err != nil {
		return ExportResult{}, fmt.Errorf("parse book.json: %w", err)
	}
	if len(metadata.Chapters) == 0 {
		return ExportResult{}, fmt.Errorf("book.json contains no chapters")
	}
	allPaths := make([]string, len(metadata.Chapters))
	allRels := make([]string, len(metadata.Chapters))
	for i, chapter := range metadata.Chapters {
		relClean, resolved, err := resolveBookChapter(root, bookDir, chapter.DocPath)
		if err != nil {
			return ExportResult{}, fmt.Errorf("chapter %d: %w", i+1, err)
		}
		allRels[i] = relClean
		allPaths[i] = resolved
	}
	bookMetaDir := filepath.Join(bookDir, ".deepread")
	for _, protected := range []string{filepath.Join(bookDir, "book.json"), filepath.Join(bookDir, "index.md")} {
		if samePath(protected, outPath) {
			return ExportResult{}, fmt.Errorf("refusing to overwrite protected book file %q", outPath)
		}
	}
	if outCanon, err := canonicalProspectivePath(outPath); err == nil {
		if metaCanon, err := canonicalProspectivePath(bookMetaDir); err == nil && pathWithinOrEqual(outCanon, metaCanon) {
			return ExportResult{}, fmt.Errorf("refusing to overwrite protected book metadata %q", outPath)
		}
	}
	for _, docPath := range allPaths {
		if err := ensureSafeExportPath(docPath, outPath); err != nil {
			return ExportResult{}, err
		}
	}
	selectedIdx, err := selectBookChapterIndices(metadata, chapterSelectors)
	if err != nil {
		return ExportResult{}, err
	}
	selected := make([]string, len(selectedIdx))
	selectedRels := make([]string, len(selectedIdx))
	for i, idx := range selectedIdx {
		selected[i] = allPaths[idx]
		selectedRels[i] = allRels[idx]
	}
	if strings.TrimSpace(opts.Title) == "" {
		opts.Title = metadata.Title
	}
	extraProtected := []string{filepath.Join(bookDir, "book.json"), filepath.Join(bookDir, "index.md"), bookMetaDir}
	return exportChapters(docPathsWithTitle{paths: selected, relPaths: selectedRels, bookRoot: root, title: opts.Title, docPath: filepath.Join(bookDir, "book.json"), aggregate: true}, outPath, opts, extraProtected, allPaths)
}

func readBookRegularFile(root *os.Root, name string, limit int64) ([]byte, error) {
	data, err := bundle.ReadRegularFileInRoot(root, name, limit)
	if err != nil {
		return nil, fmt.Errorf("open %s: %w", name, err)
	}
	return data, nil
}

func secureBookRelative(name string) (string, error) {
	trimmed := strings.TrimSpace(name)
	if trimmed == "" || strings.ContainsRune(trimmed, 0) || strings.Contains(trimmed, `\`) || filepath.IsAbs(trimmed) || strings.HasPrefix(trimmed, "/") {
		return "", fmt.Errorf("%w: unsafe book path %q", ErrUnsafeAssetPath, name)
	}
	clean := path.Clean(trimmed)
	if clean == "." || clean == ".." || strings.HasPrefix(clean, "../") {
		return "", fmt.Errorf("%w: book path %q escapes book directory", ErrUnsafeAssetPath, name)
	}
	return clean, nil
}

func resolveBookChapter(root *os.Root, bookDir, docPath string) (string, string, error) {
	clean, err := secureBookRelative(docPath)
	if err != nil {
		return "", "", err
	}
	if _, err := bundle.ReadRegularFileInRoot(root, clean, 16<<20); err != nil {
		return "", "", fmt.Errorf("%w: chapter %q: %v", ErrUnsafeAssetPath, docPath, err)
	}
	resolved := filepath.Join(bookDir, filepath.FromSlash(clean))
	canonicalRoot, err := canonicalProspectivePath(bookDir)
	if err != nil {
		return "", "", err
	}
	canonicalDoc, err := canonicalProspectivePath(resolved)
	if err != nil {
		return "", "", err
	}
	if !strictPathWithin(canonicalDoc, canonicalRoot) {
		return "", "", fmt.Errorf("%w: chapter %q resolves outside book directory", ErrUnsafeAssetPath, docPath)
	}
	return clean, resolved, nil
}

func selectBookChapterIndices(metadata bookManifest, selectors []string) ([]int, error) {
	if len(selectors) == 0 || len(selectors) == 1 && strings.EqualFold(strings.TrimSpace(selectors[0]), "all") {
		out := make([]int, len(metadata.Chapters))
		for i := range metadata.Chapters {
			out[i] = i
		}
		return out, nil
	}
	wanted := map[int]bool{}
	for _, selector := range selectors {
		selector = strings.TrimSpace(selector)
		matched := false
		if start, end, ok := parseChapterRange(selector); ok {
			for i, chapter := range metadata.Chapters {
				number := chapter.Index
				if number == 0 {
					number = i + 1
				}
				if number >= start && number <= end {
					wanted[i] = true
					matched = true
				}
			}
		} else {
			for i, chapter := range metadata.Chapters {
				if selector == chapter.Slug || selector == filepath.Base(chapter.DocPath) || selector == strings.TrimSuffix(filepath.Base(chapter.DocPath), filepath.Ext(chapter.DocPath)) || selector == chapter.Title {
					wanted[i] = true
					matched = true
				}
			}
		}
		if !matched {
			return nil, fmt.Errorf("chapter selector %q matched no chapter", selector)
		}
	}
	selected := make([]int, 0, len(wanted))
	for i := range metadata.Chapters {
		if wanted[i] {
			selected = append(selected, i)
		}
	}
	return selected, nil
}

func parseChapterRange(raw string) (int, int, bool) {
	parts := strings.Split(raw, "-")
	if len(parts) > 2 {
		return 0, 0, false
	}
	start, err := strconv.Atoi(parts[0])
	if err != nil || start < 1 {
		return 0, 0, false
	}
	end := start
	if len(parts) == 2 {
		end, err = strconv.Atoi(parts[1])
		if err != nil || end < start {
			return 0, 0, false
		}
	}
	return start, end, true
}

func samePath(a, b string) bool {
	aCanon, aErr := canonicalProspectivePath(a)
	bCanon, bErr := canonicalProspectivePath(b)
	return aErr == nil && bErr == nil && strings.EqualFold(aCanon, bCanon)
}

func exportChapters(input docPathsWithTitle, outPath string, opts ExportOptions, extraProtected []string, protectedOverride ...[]string) (ExportResult, error) {
	if len(input.paths) == 0 {
		return ExportResult{}, fmt.Errorf("no chapters selected")
	}
	protectedDocs := input.paths
	if len(protectedOverride) > 0 {
		protectedDocs = protectedOverride[0]
	}
	explicitMaxHTML := opts.MaxHTMLBytes > 0
	if opts.MaxHTMLBytes <= 0 {
		if len(input.paths) > 1 {
			opts.MaxHTMLBytes = DefaultMaxBookHTMLBytes
		} else {
			opts.MaxHTMLBytes = DefaultMaxHTMLBytes
		}
	}
	chapters := make([]*exportChapter, len(input.paths))
	for i, docPath := range input.paths {
		relPath := ""
		if i < len(input.relPaths) {
			relPath = input.relPaths[i]
		}
		chapter, err := prepareExportChapter(input.bookRoot, relPath, docPath, i, opts)
		if err != nil {
			return ExportResult{}, err
		}
		chapters[i] = chapter
	}
	face := strings.TrimSpace(opts.Face)
	if face == "" {
		face = "read"
		for _, chapter := range chapters {
			if chapter.parsed != nil && len(chapter.validated.Modules) > 0 {
				face = "dual"
				break
			}
		}
	}
	switch face {
	case "inline", "hybrid", "dual", "genui", "read", "margin":
	default:
		return ExportResult{}, fmt.Errorf("invalid export face %q", opts.Face)
	}
	if face == "margin" {
		if len(chapters) != 1 || chapters[0].snap.Manifest.Profile != bundle.ProfileMargin {
			return ExportResult{}, fmt.Errorf("margin face requires one v0.2 margin bundle")
		}
	}
	if face == "genui" {
		for _, chapter := range chapters {
			if chapter.parsed == nil {
				return ExportResult{}, fmt.Errorf("GenUI face requested but %s has no view", chapter.docPath)
			}
		}
	}
	store := &sharedImageStore{external: opts.ExternalAssets, assets: map[string]*imageAsset{}}
	store.preserveExternalNames = !input.aggregate && face == "read" && len(chapters) == 1 && chapters[0].mode == bundle.ReadModeOriginal && chapters[0].parsed == nil
	for _, chapter := range chapters {
		chapter.images = newImageTransformer(imageOptions{docPath: chapter.docPath, docDir: filepath.Dir(chapter.docPath), external: opts.ExternalAssets, maxImageBytes: opts.MaxImageBytes, shared: store, protectedDocs: protectedDocs, protectedPaths: extraProtected})
	}
	return renderExportDocument(chapters, input, outPath, opts, explicitMaxHTML, face, store)
}

func prepareExportChapter(bookRoot *os.Root, relDocPath, docPath string, index int, opts ExportOptions) (*exportChapter, error) {
	targetLang := strings.TrimSpace(opts.Lang)
	if targetLang == "" || strings.EqualFold(targetLang, "auto") || strings.EqualFold(targetLang, "original") {
		targetLang = ""
	} else {
		canonical, err := bundle.CanonicalLang(targetLang)
		if err != nil {
			return nil, err
		}
		targetLang = canonical
	}
	var (
		snap bundle.DocSnapshot
		err  error
	)
	if bookRoot != nil && relDocPath != "" {
		snap, err = bundle.LoadDocSnapshotInRoot(bookRoot, relDocPath, docPath, targetLang)
	} else {
		snap, err = bundle.LoadDocSnapshot(docPath, targetLang)
	}
	if err != nil {
		return nil, fmt.Errorf("load bundle snapshot: %w", err)
	}
	mode := strings.TrimSpace(opts.Mode)
	if mode == "" || mode == "auto" {
		mode = bundle.ReadModeOriginal
		if snap.Manifest.Reader != nil && snap.Manifest.Reader.Mode != "" {
			mode = snap.Manifest.Reader.Mode
		}
	}
	if strings.EqualFold(strings.TrimSpace(opts.Lang), "original") {
		mode = bundle.ReadModeOriginal
	}
	if err := bundle.ValidateReadMode(mode); err != nil || mode == "" {
		if err == nil {
			err = fmt.Errorf("invalid empty read mode")
		}
		return nil, err
	}
	sourceLang := "en"
	target := targetLang
	if snap.Manifest.Reader != nil {
		if snap.Manifest.Reader.SourceLang != "" {
			sourceLang = snap.Manifest.Reader.SourceLang
		}
		if target == "" {
			target = snap.Manifest.Reader.TargetLang
		}
	}
	if snap.TranslationStatus != nil && snap.TranslationStatus.Lang != "" {
		target = snap.TranslationStatus.Lang
	}
	lang := target
	if mode == bundle.ReadModeOriginal || lang == "" {
		lang = sourceLang
	}
	chapter := &exportChapter{docPath: docPath, prefix: fmt.Sprintf("c%02d", index+1), title: inferTitle(docPath, string(snap.DocBytes)), snap: snap, lang: lang, mode: mode}
	if mode == bundle.ReadModeTranslated || mode == bundle.ReadModeBilingual {
		status := snap.TranslationStatus
		if !opts.AllowPartialTranslation {
			incomplete := status == nil || target == "" || status.TranslatedBlocks < status.TotalBlocks || status.StaleBlocks > 0
			if incomplete {
				var missing, stale []string
				if status != nil {
					missing, stale = status.MissingIDs, status.StaleIDs
				} else {
					for _, block := range bundle.ExtractBlocks(snap.DocBytes, snap.Manifest) {
						missing = append(missing, block.ID)
					}
				}
				return nil, fmt.Errorf("%w: missing=[%s] stale=[%s]", bundle.ErrTranslationIncomplete, strings.Join(missing, ","), strings.Join(stale, ","))
			}
		}
	}
	if snap.ViewExists {
		parsed, err := view.ReadView(snap.ViewBytes)
		if err != nil {
			return nil, fmt.Errorf("read GenUI view: %w", err)
		}
		validated, err := view.ValidateForExport(docPath, snap.DocBytes, parsed.Statements, parsed.Envelope.Sources, snap.Manifest.Profile)
		if err != nil {
			return nil, fmt.Errorf("validate GenUI view for export: %w", err)
		}
		generatedAt := time.Date(2000, 1, 1, 0, 0, 0, 0, time.UTC)
		if parsed.Envelope.GeneratedAt != "" {
			if parsedAt, parseErr := time.Parse(time.RFC3339Nano, parsed.Envelope.GeneratedAt); parseErr == nil {
				generatedAt = parsedAt
			}
		}
		library, err := genuikit.NewLibrary(genuikit.Environment{Now: func() time.Time { return generatedAt }, Location: time.UTC, Random: func() float64 { return 0.5 }})
		if err != nil {
			return nil, err
		}
		program := library.Parse(parsed.JoinedText)
		session := openuilang.NewSession()
		session.Load(program)
		root, problems := session.Render()
		if root == nil || len(program.Errors) > 0 || len(program.Unresolved) > 0 || len(problems) > 0 {
			return nil, fmt.Errorf("evaluate deterministic GenUI view: %v %v %v", program.Errors, program.Unresolved, problems)
		}
		chapter.parsed, chapter.validated, chapter.program, chapter.session, chapter.root = parsed, validated, program, session, root
	}
	return chapter, nil
}

func renderExportDocument(chapters []*exportChapter, input docPathsWithTitle, outPath string, opts ExportOptions, explicitMaxHTML bool, face string, store *sharedImageStore) (ExportResult, error) {
	title := strings.TrimSpace(opts.Title)
	if title == "" {
		title = input.title
	}
	if title == "" {
		title = chapters[0].title
	}
	warnings := []string{}
	moduleCount, islandCount := 0, 0
	totalModules := 0
	for _, chapter := range chapters {
		totalModules += len(chapter.validated.Modules)
	}
	var body strings.Builder
	body.WriteString(renderReaderChrome(chapters, face, totalModules))
	for _, chapter := range chapters {
		moduleCount += len(chapter.validated.Modules)
		body.WriteString(`<article class="dr-chapter" id="` + chapter.prefix + `" data-chapter="` + chapter.prefix + `">`)
		switch face {
		case "margin":
			margin, _, err := renderLegacyBody(string(chapter.snap.DocBytes), chapter.snap.Manifest, chapter.parsed, chapter.title, chapter.images, true, chapter.prefix, chapter.root)
			if err != nil {
				return ExportResult{}, err
			}
			body.WriteString(margin)
		case "inline", "hybrid":
			rendered, islands, chapterWarnings, err := renderChapterInline(chapter, opts, face == "hybrid")
			if err != nil {
				return ExportResult{}, fmt.Errorf("render %s chapter %s: %w", face, chapter.prefix, err)
			}
			body.WriteString(rendered)
			islandCount += islands
			warnings = append(warnings, chapterWarnings...)
		default:
			if face == "dual" || face == "genui" {
				body.WriteString(`<div class="dr-face dr-face-genui" data-face-panel="genui">`)
				if chapter.parsed != nil {
					rendered, islands, chapterWarnings, err := renderChapterGenUI(chapter, opts)
					if err != nil {
						return ExportResult{}, fmt.Errorf("render chapter %s: %w", chapter.prefix, err)
					}
					body.WriteString(rendered)
					islandCount += islands
					warnings = append(warnings, chapterWarnings...)
				}
				body.WriteString(`</div>`)
			}
			if face == "dual" || face == "read" || chapter.parsed == nil {
				reading, err := renderChapterReading(chapter)
				if err != nil {
					return ExportResult{}, fmt.Errorf("render reading face %s: %w", chapter.prefix, err)
				}
				body.WriteString(`<div class="dr-face dr-face-read" data-face-panel="read">` + reading + `</div>`)
			}
		}
		if len(chapters) > 1 {
			body.WriteString(`<nav class="dr-chapter-nav" aria-label="Chapter navigation"><button type="button" data-chapter-step="-1">← 上一章</button><button type="button" data-chapter-step="1">下一章 →</button></nav>`)
		}
		body.WriteString(`</article>`)
	}
	backLabel := "← 返回深读"
	if face == "inline" || face == "hybrid" {
		backLabel = "← 返回图解"
	}
	body.WriteString(`<button type="button" class="dr-back-genui" data-back-genui hidden>` + backLabel + `</button>`)
	bodyString := store.finalizeInlineHTML(body.String())
	lang := chapters[0].lang
	if lang == "" {
		lang = "en"
	}
	plainStaticRead := face == "read" && len(chapters) == 1 && chapters[0].mode == bundle.ReadModeOriginal && chapters[0].parsed == nil
	runtimeEnabled := !opts.NoJS && face != "margin" && !plainStaticRead
	csp := exportContentSecurityPolicy(opts.ExternalAssets, !runtimeEnabled)
	if plainStaticRead && !opts.NoJS {
		csp = contentSecurityPolicy
		if opts.ExternalAssets {
			csp = externalContentSecurityPolicy
		}
	}
	budget := &budgetWriter{limit: opts.MaxHTMLBytes, enforce: !opts.ExternalAssets || explicitMaxHTML}
	write := func(s string) error { return budget.WriteString(s) }
	if err := write("<!doctype html>\n<html lang=\"" + html.EscapeString(lang) + "\" data-lang-mode=\"" + html.EscapeString(chapters[0].mode) + "\" data-face=\"" + html.EscapeString(face) + "\">\n<head>\n<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n<meta http-equiv=\"Content-Security-Policy\" content=\"" + csp + "\">\n<title>" + html.EscapeString(title) + "</title>\n<style>" + documentCSS + store.inlineCSS() + "</style>\n</head>\n<body>\n"); err != nil {
		return ExportResult{}, err
	}
	if err := write(`<main class="dr-document"><header class="dr-book-header"><h1>` + html.EscapeString(title) + `</h1></header>` + bodyString + `</main>` + "\n"); err != nil {
		return ExportResult{}, err
	}
	if runtimeEnabled {
		if err := write("<script>" + runtimeJS + "</script>\n"); err != nil {
			return ExportResult{}, err
		}
	}
	if err := write("</body>\n</html>\n"); err != nil {
		return ExportResult{}, err
	}
	rendered := budget.String()
	rollbackAssets := func() {}
	if opts.ExternalAssets {
		var err error
		rollbackAssets, err = chapters[0].images.commitExternalAssets(outPath)
		if err != nil {
			return ExportResult{}, err
		}
	}
	if err := bundle.WriteFileAtomic(outPath, []byte(rendered), 0o644); err != nil {
		rollbackAssets()
		return ExportResult{}, fmt.Errorf("write export: %w", err)
	}
	assetMode := "inline"
	if opts.ExternalAssets {
		assetMode = "external"
	}
	return ExportResult{DocPath: input.docPath, OutPath: outPath, BundleID: chapters[0].snap.Manifest.BundleID, Revision: chapters[0].snap.Manifest.Revision, Bytes: len([]byte(rendered)), ModuleCount: moduleCount, ImageCount: store.uniqueCount(), AssetMode: assetMode, Warnings: warnings, Face: face, Lang: lang, Mode: chapters[0].mode, ChapterCount: len(chapters), IslandCount: islandCount}, nil
}

func renderReaderChrome(chapters []*exportChapter, face string, totalModules int) string {
	var out strings.Builder
	out.WriteString(`<nav class="dr-topbar" aria-label="Reader controls">`)
	if (face == "inline" || face == "hybrid") && totalModules > 0 {
		out.WriteString(`<div class="dr-face-switch"><button type="button" data-inline-view-target="mixed" aria-pressed="true">精读</button><button type="button" data-inline-view-target="genui" aria-pressed="false">图解</button><button type="button" data-inline-view-target="prose" aria-pressed="false">纯文</button></div>`)
	} else if face == "dual" {
		out.WriteString(`<div class="dr-face-switch"><button type="button" data-face-target="genui" aria-pressed="true">深读</button><button type="button" data-face-target="read" aria-pressed="false">原文</button></div>`)
	}
	if len(chapters) > 1 {
		out.WriteString(`<details class="dr-toc" id="dr-toc"><summary>目录</summary><div class="dr-toc-drawer">`)
		for _, chapter := range chapters {
			out.WriteString(`<a href="#` + chapter.prefix + `" data-chapter-link="` + chapter.prefix + `">` + html.EscapeString(chapter.title) + `</a>`)
		}
		out.WriteString(`</div></details>`)
	}
	if chapters[0].mode != bundle.ReadModeOriginal {
		out.WriteString(`<div class="dr-language-switch"><button type="button" data-language="translated">中文</button><button type="button" data-language="original">EN</button><button type="button" data-language="bilingual">双语</button></div>`)
	}
	out.WriteString(`</nav>`)
	return out.String()
}

func findSourceStatement(value any, statement string) *openuilang.Element {
	var found *openuilang.Element
	walkIslandElements(value, func(el *openuilang.Element) {
		if found == nil && el.Type == "Source" && el.StatementID == statement {
			found = el
		}
	})
	return found
}

func renderSourceElement(chapter *exportChapter, source *openuilang.Element, moduleByStatement map[string]view.ValidatedModule, opts ExportOptions, islands *int, warnings *[]string, popoverSeq *int) (string, error) {
	module, ok := moduleByStatement[source.StatementID]
	if !ok {
		return "", fmt.Errorf("Source statement %q has no validated source binding", source.StatementID)
	}
	content := ""
	if reactiveSource(source) {
		islandID := chapter.prefix + "-i" + strconv.Itoa(*islands+1)
		evaluate := func(values map[string]any) (*openuilang.Element, *openuilang.Session, error) {
			fresh := openuilang.NewSession()
			fresh.Load(chapter.program)
			for target, value := range values {
				fresh.Assign(&openuilang.Binding{Target: target}, value)
			}
			root, problems := fresh.Render()
			if root == nil || len(problems) > 0 {
				return nil, nil, fmt.Errorf("reactive evaluation failed: %v", problems)
			}
			resolved := findSourceStatement(root, source.StatementID)
			if resolved == nil {
				return nil, nil, fmt.Errorf("reactive Source %q disappeared", source.StatementID)
			}
			return resolved, fresh, nil
		}
		island, err := buildReactiveIsland(islandID, source, chapter.session, evaluate, chapter.images, opts.NoJS, popoverSeq)
		if err != nil {
			return "", err
		}
		if island.reactive {
			*islands++
			*warnings = append(*warnings, island.warnings...)
			content = island.html
		}
	}
	if content == "" {
		staticRenderer := &genuiRenderer{images: chapter.images, session: chapter.session, disableControls: true, popoverSeq: popoverSeq}
		children, err := staticRenderer.renderNodeList(property(source.Props, "children"), false)
		if err != nil {
			return "", err
		}
		content = children
	}
	return renderDualModule(chapter, module, content), nil
}

func renderChapterGenUI(chapter *exportChapter, opts ExportOptions) (string, int, []string, error) {
	islands := 0
	warnings := []string{}
	popoverSeq := 0
	moduleByStatement := map[string]view.ValidatedModule{}
	for _, module := range chapter.validated.Modules {
		moduleByStatement[module.Statement] = module
	}
	renderer := &genuiRenderer{images: chapter.images, session: chapter.session, disableControls: opts.NoJS, popoverSeq: &popoverSeq}
	renderer.sourceHandler = func(source *openuilang.Element) (string, error) {
		return renderSourceElement(chapter, source, moduleByStatement, opts, &islands, &warnings, &popoverSeq)
	}
	rendered, err := renderer.renderNode(chapter.root, false)
	return rendered, islands, warnings, err
}

type topLevelSpan struct {
	start int
	end   int
}

func extractTopLevelSpans(doc ast.Node, src []byte) []topLevelSpan {
	var spans []topLevelSpan
	for child := doc.FirstChild(); child != nil; child = child.NextSibling() {
		start, end := astNodeByteSpan(child)
		if start < 0 || end <= start {
			continue
		}
		if end < len(src) {
			if nl := strings.IndexByte(string(src[end:]), '\n'); nl >= 0 {
				end += nl + 1
			} else {
				end = len(src)
			}
		}
		spans = append(spans, topLevelSpan{start: start, end: end})
	}
	return spans
}

func astNodeByteSpan(n ast.Node) (int, int) {
	if lines := n.Lines(); lines != nil && lines.Len() > 0 {
		return lines.At(0).Start, lines.At(lines.Len() - 1).Stop
	}
	start, end := -1, -1
	for child := n.FirstChild(); child != nil; child = child.NextSibling() {
		s, e := astNodeByteSpan(child)
		if s < 0 {
			continue
		}
		if start < 0 || s < start {
			start = s
		}
		if e > end {
			end = e
		}
	}
	return start, end
}

func topLevelEndAfter(spans []topLevelSpan, targetEnd int, fallback int) int {
	for _, sp := range spans {
		if targetEnd >= sp.start && targetEnd <= sp.end {
			return sp.end
		}
	}
	for _, sp := range spans {
		if sp.end >= targetEnd {
			return sp.end
		}
	}
	return fallback
}

func chapterHeaderCutByte(blocks []bundle.Block, spans []topLevelSpan) int {
	foundH1 := false
	cutEnd := -1
	for _, b := range blocks {
		if b.Kind == bundle.BlockKindHeading {
			if !foundH1 {
				if b.HeadingLevel == 1 {
					foundH1 = true
					cutEnd = b.EndByte
				}
				continue
			}
			// Consume an immediately following deck/subtitle (H3+), but stop before H2 sections.
			if b.HeadingLevel >= 3 {
				cutEnd = b.EndByte
				continue
			}
			break
		}
		if foundH1 {
			break
		}
	}
	if cutEnd < 0 {
		return 0
	}
	return topLevelEndAfter(spans, cutEnd, cutEnd)
}

func renderChapterInline(chapter *exportChapter, opts ExportOptions, hybrid bool) (string, int, []string, error) {
	originalRaw := markdown.StripNotes(string(chapter.snap.DocBytes))
	originalBytes := []byte(originalRaw)
	sections := markdown.ExtractSections(originalRaw)
	blocks := bundle.ExtractBlocks(chapter.snap.DocBytes, chapter.snap.Manifest)
	reverse := reverseCitations(chapter.snap.Citations)

	referenceParser := goldmark.New(goldmark.WithExtensions(extension.GFM), goldmark.WithParserOptions(parser.WithASTTransformers(util.Prioritized(safeLinkTransformer{}, 900)))).Parser()
	fullPC := parser.NewContext()
	docAST := referenceParser.Parse(text.NewReader(originalBytes), parser.WithContext(fullPC))
	globalRefs := fullPC.References()
	topSpans := extractTopLevelSpans(docAST, originalBytes)

	sectionIndexByKey := make(map[sectionKey]int, len(sections))
	for i, sec := range sections {
		sectionIndexByKey[sectionKey{markdown.NormalizeHeadingText(sec.Heading), sec.Occurrence}] = i
	}
	blockByID := make(map[string]bundle.Block, len(blocks))
	for _, b := range blocks {
		blockByID[b.ID] = b
	}

	islands := 0
	warnings := []string{}
	popoverSeq := 0

	type placedModule struct {
		cutByte int
		order   int
		html    string
	}
	var placed []placedModule

	if chapter.parsed != nil && chapter.root != nil && len(chapter.validated.Modules) > 0 {
		moduleByStatement := make(map[string]view.ValidatedModule, len(chapter.validated.Modules))
		for _, module := range chapter.validated.Modules {
			moduleByStatement[module.Statement] = module
		}
		var sourceElements []*openuilang.Element
		walkIslandElements(chapter.root, func(el *openuilang.Element) {
			if el.Type == "Source" {
				sourceElements = append(sourceElements, el)
			}
		})
		for idx, sourceEl := range sourceElements {
			renderedMod, err := renderSourceElement(chapter, sourceEl, moduleByStatement, opts, &islands, &warnings, &popoverSeq)
			if err != nil {
				return "", 0, nil, err
			}
			// In hybrid mode, elevate the first Source module into the masthead
			// hero canvas right below the article headline/subtitle.
			if hybrid && idx == 0 {
				heroCut := chapterHeaderCutByte(blocks, topSpans)
				heroHTML := `<section class="dr-hybrid-hero" data-hybrid-hero><header class="dr-hybrid-hero-head"><span>核心结构导览</span><span class="dr-hybrid-hero-hint">下滑阅读完整正文与随段图解 ↓</span></header>` + renderedMod + `</section>`
				placed = append(placed, placedModule{cutByte: heroCut, order: idx, html: heroHTML})
				continue
			}
			wrapped := `<div class="dr-inline-module" data-inline-module>` + renderedMod + `</div>`
			module := moduleByStatement[sourceEl.StatementID]

			// Prefer exact paragraph-level placement after the latest cited block.
			cutByte := -1
			if citedSources := chapter.snap.Citations[sourceEl.StatementID]; len(citedSources) > 0 {
				maxBlockEnd := -1
				for _, ids := range citedSources {
					for _, id := range ids {
						if b, ok := blockByID[id]; ok && b.EndByte > maxBlockEnd {
							maxBlockEnd = b.EndByte
						}
					}
				}
				if maxBlockEnd >= 0 {
					cutByte = topLevelEndAfter(topSpans, maxBlockEnd, maxBlockEnd)
				}
			}

			// Fallback to section end when no block citation was provided.
			if cutByte < 0 {
				anchorIdx := -1
				for _, ref := range module.Sections {
					key := sectionKey{markdown.NormalizeHeadingText(ref.Section.Heading), ref.Section.Occurrence}
					if secIdx, ok := sectionIndexByKey[key]; ok && secIdx > anchorIdx {
						anchorIdx = secIdx
					}
				}
				if anchorIdx >= 0 && sections[anchorIdx].Level == 1 && len(sections) > 1 {
					anchorIdx = len(sections) - 1
				}
				if anchorIdx >= 0 && anchorIdx < len(sections) {
					cutByte = markdown.OwnBodyEndByte(originalRaw, sections, anchorIdx)
				} else {
					cutByte = len(originalRaw)
				}
			}
			if cutByte < 0 {
				cutByte = 0
			}
			if cutByte > len(originalRaw) {
				cutByte = len(originalRaw)
			}
			placed = append(placed, placedModule{cutByte: cutByte, order: idx, html: wrapped})
		}
	}

	sort.Slice(placed, func(i, j int) bool {
		if placed[i].cutByte != placed[j].cutByte {
			return placed[i].cutByte < placed[j].cutByte
		}
		return placed[i].order < placed[j].order
	})

	renderProseSlice := func(sliceStart, sliceEnd int) (string, error) {
		if sliceStart >= sliceEnd {
			return "", nil
		}
		sliceRaw := originalRaw[sliceStart:sliceEnd]
		if strings.TrimSpace(sliceRaw) == "" {
			return "", nil
		}
		var sliceSections []markdown.Section
		sectionOffset := -1
		for i, sec := range sections {
			if sec.ByteStart() >= sliceStart && sec.ByteStart() < sliceEnd {
				if sectionOffset < 0 {
					sectionOffset = i
				}
				sliceSections = append(sliceSections, sec)
			}
		}
		if sectionOffset < 0 {
			sectionOffset = 0
		}
		sliceBlocks := make([]bundle.Block, 0, 8)
		for _, b := range blocks {
			if b.StartByte >= sliceStart && b.EndByte <= sliceEnd {
				shifted := b
				shifted.StartByte -= sliceStart
				shifted.EndByte -= sliceStart
				sliceBlocks = append(sliceBlocks, shifted)
			}
		}
		originalHTML, err := renderMarkdownWithImagesAndRefs(sliceRaw, chapter.images, globalRefs)
		if err != nil {
			return "", err
		}
		if chapter.mode == bundle.ReadModeOriginal {
			anchored := anchorReadingHTMLWithOffset(originalHTML, sliceSections, sliceBlocks, sectionOffset, chapter.prefix, chapter.snap.Manifest, reverse, false)
			return `<div class="dr-sec-prose" data-prose-block>` + anchored + `</div>`, nil
		}
		translatedRaw := translatedMarkdownSlice(sliceRaw, sliceStart, sliceSections, sliceBlocks, chapter.snap.Translation, chapter.snap.Manifest)
		translatedHTML, err := renderMarkdownWithImagesAndRefs(translatedRaw, chapter.images, globalRefs)
		if err != nil {
			return "", err
		}
		primary := anchorReadingHTMLWithOffset(translatedHTML, sliceSections, sliceBlocks, sectionOffset, chapter.prefix, chapter.snap.Manifest, reverse, true)
		return `<div class="dr-sec-prose" data-prose-block><div class="dr-translated" lang="` + html.EscapeString(chapter.lang) + `">` + primary + `</div><div class="dr-orig" lang="en"><div class="dr-orig-full">` + originalHTML + `</div></div></div>`, nil
	}

	var out strings.Builder
	out.WriteString(`<div class="dr-inline-body">`)
	cursor := 0
	for i := 0; i < len(placed); {
		cut := placed[i].cutByte
		if cut > cursor {
			frag, err := renderProseSlice(cursor, cut)
			if err != nil {
				return "", 0, nil, err
			}
			out.WriteString(frag)
			cursor = cut
		}
		for i < len(placed) && placed[i].cutByte == cut {
			out.WriteString(placed[i].html)
			i++
		}
	}
	if cursor < len(originalRaw) {
		frag, err := renderProseSlice(cursor, len(originalRaw))
		if err != nil {
			return "", 0, nil, err
		}
		out.WriteString(frag)
	}
	if len(chapter.validated.Modules) == 0 {
		out.WriteString(`<p class="dr-inline-empty">本章正文流畅清晰，未附加图解模块。</p>`)
	}
	out.WriteString(`</div>`)
	return out.String(), islands, warnings, nil
}

func reactiveSource(source *openuilang.Element) bool {
	reactive := false
	walkIslandElements(source, func(el *openuilang.Element) {
		if isIslandControlElement(el) {
			reactive = true
		}
	})
	return reactive
}

func renderDualModule(chapter *exportChapter, module view.ValidatedModule, content string) string {
	revision := chapter.snap.Manifest.Revision
	if revision < 1 {
		revision = 1
	}
	shortCode := fmt.Sprintf("%s·%s@r%d", chapter.snap.Manifest.BundleID, module.Statement, revision)
	moduleAnchor := chapter.prefix + "-g-" + safeAnchorToken(module.Statement)
	var out strings.Builder
	out.WriteString(`<section id="` + moduleAnchor + `" class="dr-module">`)
	out.WriteString(content)
	out.WriteString(`<footer class="dr-module-footer"><div class="dr-source-chips">`)
	for i, source := range module.Sections {
		target, excerpt := chapterCitationTarget(chapter, module.Statement, source)
		popoverID := moduleAnchor + "-preview-" + strconv.Itoa(i)
		out.WriteString(`<span class="dr-source-chip-wrap"><a class="dr-source-chip" href="#` + target + `" data-jump-target="#` + target + `" data-origin="#` + moduleAnchor + `">查看原文 ↗</a><button type="button" class="dr-preview-button" popovertarget="` + popoverID + `" aria-label="预览原文">预览</button><span class="dr-source-popover" popover id="` + popoverID + `">` + html.EscapeString(excerpt) + `</span></span>`)
	}
	out.WriteString(`</div><details class="dr-feedback"><summary>反馈码</summary><button type="button" data-copy-code="` + html.EscapeString(shortCode) + `"><code class="dr-shortcode">` + html.EscapeString(shortCode) + `</code></button></details></footer></section>` + "\n")
	return out.String()
}

func chapterCitationTarget(chapter *exportChapter, statement string, source view.ValidatedSourceRef) (string, string) {
	if citations := chapter.snap.Citations[statement]; citations != nil {
		if ids := citations[source.SourceID]; len(ids) > 0 {
			for _, block := range bundle.ExtractBlocks(chapter.snap.DocBytes, chapter.snap.Manifest) {
				if block.ID == ids[0] {
					return chapter.prefix + "-" + block.ID, block.Text
				}
			}
		}
	}
	sections := markdown.ExtractSections(string(chapter.snap.DocBytes))
	key := sectionKey{markdown.NormalizeHeadingText(source.Section.Heading), source.Section.Occurrence}
	for i, section := range sections {
		if (sectionKey{markdown.NormalizeHeadingText(section.Heading), section.Occurrence}) == key {
			excerpt := ""
			for _, block := range bundle.ExtractBlocks(chapter.snap.DocBytes, chapter.snap.Manifest) {
				if markdown.NormalizeHeadingText(block.SectionHeading) == key.heading && block.SectionOccurrence == key.occurrence && block.Kind != bundle.BlockKindHeading {
					excerpt = block.Text
					break
				}
			}
			if excerpt == "" {
				excerpt = section.Heading
			}
			return fmt.Sprintf("%s-s%02d", chapter.prefix, i+1), excerpt
		}
	}
	return chapter.prefix, source.Section.Heading
}

var proseOpeningTagRE = regexp.MustCompile(`<(/?)(h[1-6]|p|li|t[dh])(?:\s[^>]*)?>`)

func renderChapterReading(chapter *exportChapter) (string, error) {
	originalRaw := markdown.StripNotes(string(chapter.snap.DocBytes))
	sections := markdown.ExtractSections(originalRaw)
	blocks := bundle.ExtractBlocks(chapter.snap.DocBytes, chapter.snap.Manifest)
	reverse := reverseCitations(chapter.snap.Citations)
	originalHTML, err := renderMarkdownWithImages(originalRaw, chapter.images)
	if err != nil {
		return "", err
	}
	if chapter.mode == bundle.ReadModeOriginal {
		return anchorReadingHTML(originalHTML, sections, blocks, chapter.prefix, chapter.snap.Manifest, reverse, false), nil
	}
	translatedRaw := translatedMarkdown(originalRaw, blocks, chapter.snap.Translation, chapter.snap.Manifest)
	translatedHTML, err := renderMarkdownWithImages(translatedRaw, chapter.images)
	if err != nil {
		return "", err
	}
	primary := anchorReadingHTML(translatedHTML, sections, blocks, chapter.prefix, chapter.snap.Manifest, reverse, true)
	original := originalHTML
	return `<div class="dr-translated" lang="` + html.EscapeString(chapter.lang) + `">` + primary + `</div><div class="dr-orig" lang="en"><div class="dr-orig-full">` + original + `</div></div>`, nil
}

var markdownImageAltRE = regexp.MustCompile(`!\[[^\]]*\]`)

type translationReplacement struct {
	start, end int
	text       string
}

func translatedMarkdown(originalRaw string, blocks []bundle.Block, layer *bundle.TranslationLayer, manifest bundle.Manifest) string {
	return translatedMarkdownSlice(originalRaw, 0, markdown.ExtractSections(originalRaw), blocks, layer, manifest)
}

func translatedMarkdownSlice(sliceRaw string, sliceStart int, sliceSections []markdown.Section, blocks []bundle.Block, layer *bundle.TranslationLayer, manifest bundle.Manifest) string {
	if layer == nil {
		layer = &bundle.TranslationLayer{Entries: map[string]bundle.TranslationEntry{}}
	}
	replacements := make([]translationReplacement, 0, len(blocks))
	for _, section := range sliceSections {
		if !manifest.IsSynthetic(section.Heading, section.Occurrence) {
			continue
		}
		translatedHeading := ""
		for _, synthetic := range manifest.SyntheticSections {
			if strings.EqualFold(strings.Join(strings.Fields(synthetic.Heading), " "), strings.Join(strings.Fields(section.Heading), " ")) && synthetic.Occurrence == section.Occurrence {
				translatedHeading = strings.TrimSpace(synthetic.TranslatedHeading)
				break
			}
		}
		if translatedHeading == "" {
			continue
		}
		relStart := section.ByteStart() - sliceStart
		if relStart < 0 || relStart > len(sliceRaw) {
			continue
		}
		lineEnd := strings.IndexByte(sliceRaw[relStart:], '\n')
		if lineEnd < 0 {
			lineEnd = len(sliceRaw)
		} else {
			lineEnd += relStart
		}
		prefix := strings.Repeat("#", section.Level) + " "
		replacements = append(replacements, translationReplacement{start: relStart, end: lineEnd, text: prefix + translatedHeading})
	}
	for _, block := range blocks {
		entry, ok := layer.Entries[block.ID]
		if !ok || entry.SourceHash != block.SourceHash || block.StartByte < 0 || block.EndByte > len(sliceRaw) || block.StartByte > block.EndByte {
			continue
		}
		text := entry.Text
		if block.Kind == bundle.BlockKindImageAlt {
			segment := sliceRaw[block.StartByte:block.EndByte]
			label := markdownImageAltRE.FindStringIndex(segment)
			if label == nil {
				continue
			}
			escapedAlt := strings.NewReplacer(`\`, `\\`, `[`, `\[`, `]`, `\]`).Replace(text)
			text = segment[:label[0]] + "![" + escapedAlt + "]" + segment[label[1]:]
		}
		replacements = append(replacements, translationReplacement{start: block.StartByte, end: block.EndByte, text: text})
	}
	sort.Slice(replacements, func(i, j int) bool { return replacements[i].start > replacements[j].start })
	out := sliceRaw
	for _, replacement := range replacements {
		out = out[:replacement.start] + replacement.text + out[replacement.end:]
	}
	return out
}

func reverseCitations(citations bundle.CitationMap) map[string][]string {
	out := map[string][]string{}
	for statement, sources := range citations {
		for _, ids := range sources {
			for _, id := range ids {
				out[id] = append(out[id], statement)
			}
		}
	}
	for id := range out {
		sort.Strings(out[id])
	}
	return out
}

func anchorReadingHTML(rendered string, sections []markdown.Section, blocks []bundle.Block, prefix string, manifest bundle.Manifest, reverse map[string][]string, bilingual bool) string {
	return anchorReadingHTMLWithOffset(rendered, sections, blocks, 0, prefix, manifest, reverse, bilingual)
}

var htmlTagStripRE = regexp.MustCompile(`<[^>]*>`)

// isImageOnlyParagraphHTML reports whether the inner HTML of a <p> element
// contains only rendered image markup (e.g. `<span class="dr-image ..."></span>`
// or `<img ...>`) with no visible prose text.
func isImageOnlyParagraphHTML(inner string) bool {
	if !strings.Contains(inner, "dr-image") && !strings.Contains(inner, "<img") {
		return false
	}
	return strings.TrimSpace(htmlTagStripRE.ReplaceAllString(inner, "")) == ""
}

func anchorReadingHTMLWithOffset(rendered string, sections []markdown.Section, blocks []bundle.Block, sectionOffset int, prefix string, manifest bundle.Manifest, reverse map[string][]string, bilingual bool) string {
	sectionIndex, blockIndex, listDepth := 0, 0, 0
	openBlocks := map[string][]bundle.Block{}
	reverseHTML := func(blockID string) string {
		var out strings.Builder
		for _, statement := range reverse[blockID] {
			target := prefix + "-g-" + safeAnchorToken(statement)
			out.WriteString(`<a class="dr-citation-reverse" href="#` + target + `" data-jump-genui="#` + target + `">↩ 图解</a>`)
		}
		return out.String()
	}
	matches := proseOpeningTagRE.FindAllStringSubmatchIndex(rendered, -1)
	if len(matches) == 0 {
		return rendered
	}
	var out strings.Builder
	out.Grow(len(rendered) + 256)
	pos := 0
	for _, m := range matches {
		start, end := m[0], m[1]
		out.WriteString(rendered[pos:start])
		pos = end
		tag := rendered[start:end]
		closing := m[2] != m[3]
		name := rendered[m[4]:m[5]]
		if closing {
			if name == "li" && listDepth > 0 {
				listDepth--
			}
			if stack := openBlocks[name]; len(stack) > 0 {
				block := stack[len(stack)-1]
				openBlocks[name] = stack[:len(stack)-1]
				if bilingual && block.Kind != bundle.BlockKindImageAlt {
					out.WriteString(`<span class="dr-orig-inline" lang="en">` + html.EscapeString(block.Text) + `</span>`)
				}
			}
			out.WriteString(tag)
			continue
		}
		if name == "p" && listDepth > 0 {
			out.WriteString(tag)
			continue
		}
		if strings.HasPrefix(name, "h") {
			if sectionIndex >= len(sections) {
				out.WriteString(tag)
				continue
			}
			section := sections[sectionIndex]
			sectionIndex++
			class := ""
			if manifest.IsSynthetic(section.Heading, section.Occurrence) {
				class = ` class="dr-sec-break"`
			}
			prefixAnchor := ""
			dataBlock, citations := "", ""
			if blockIndex < len(blocks) && blocks[blockIndex].Kind == bundle.BlockKindHeading {
				block := blocks[blockIndex]
				blockIndex++
				openBlocks[name] = append(openBlocks[name], block)
				prefixAnchor = `<span id="` + prefix + `-` + block.ID + `" class="dr-block-anchor" aria-hidden="true"></span>`
				dataBlock = ` data-block="` + block.ID + `"`
				citations = reverseHTML(block.ID)
			}
			out.WriteString(prefixAnchor + strings.TrimSuffix(tag, ">") + ` id="` + fmt.Sprintf("%s-s%02d", prefix, sectionOffset+sectionIndex) + `"` + dataBlock + class + `>` + citations)
			continue
		}
		if blockIndex >= len(blocks) {
			if name == "li" {
				listDepth++
			}
			out.WriteString(tag)
			continue
		}
		block := blocks[blockIndex]
		matched := false
		switch name {
		case "p":
			imgOnly := false
			if closeIdx := strings.Index(rendered[end:], "</p>"); closeIdx >= 0 {
				imgOnly = isImageOnlyParagraphHTML(rendered[end : end+closeIdx])
			}
			if imgOnly {
				matched = block.Kind == bundle.BlockKindImageAlt
			} else {
				matched = block.Kind == bundle.BlockKindParagraph || block.Kind == bundle.BlockKindQuote
			}
		case "li":
			matched = block.Kind == bundle.BlockKindListItem
		case "td", "th":
			matched = block.Kind == bundle.BlockKindTableCell
		}
		if name == "li" {
			listDepth++
		}
		if !matched {
			out.WriteString(tag)
			continue
		}
		blockIndex++
		openBlocks[name] = append(openBlocks[name], block)
		out.WriteString(strings.TrimSuffix(tag, ">") + ` id="` + prefix + `-` + block.ID + `" data-block="` + block.ID + `" class="dr-reading-block">` + reverseHTML(block.ID))
	}
	out.WriteString(rendered[pos:])
	return out.String()
}

func runtimeCSPHash() string {
	sum := sha256.Sum256([]byte(runtimeJS))
	return base64.StdEncoding.EncodeToString(sum[:])
}
