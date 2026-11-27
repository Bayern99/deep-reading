package export

import (
	"errors"
	"fmt"
	"html"
	"io/fs"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"

	"deepread/internal/bundle"
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

const (
	DefaultMaxImageBytes = 512 << 10  // 512 KiB per raw image in inline mode
	DefaultMaxHTMLBytes  = 1536 << 10 // 1.5 MiB total HTML output in inline mode
)

var ErrAssetBudgetExceeded = errors.New("asset budget exceeded")
var ErrUnsafeAssetPath = errors.New("unsafe asset path")

// ExportOptions configures an HTML export.
type ExportOptions struct {
	Title          string // optional override; default inferred from first H1 or doc filename
	ExternalAssets bool   // false: inline base64 data URIs; true: relative assets for HTTPS directory hosting
	MaxImageBytes  int    // optional inline per-image raw byte cap (<=0 uses DefaultMaxImageBytes)
	MaxHTMLBytes   int    // optional inline total HTML byte cap (<=0 uses DefaultMaxHTMLBytes)
}

// ExportResult describes the generated standalone HTML document.
type ExportResult struct {
	DocPath     string `json:"docPath"`
	OutPath     string `json:"outPath"`
	BundleID    string `json:"bundleId"`
	Revision    int    `json:"revision"`
	Bytes       int    `json:"bytes"`
	ModuleCount int    `json:"moduleCount"`
	ImageCount  int    `json:"imageCount"`
	AssetMode   string `json:"assetMode"`
}

// Export reads a DeepRead bundle and writes one standalone, zero-JavaScript HTML file.
func Export(docPath, outPath string, opts ExportOptions) (ExportResult, error) {
	if strings.TrimSpace(outPath) == "" {
		return ExportResult{}, fmt.Errorf("export output path is required")
	}
	if err := ensureSafeExportPath(docPath, outPath); err != nil {
		return ExportResult{}, err
	}

	var docBytes []byte
	var manifest bundle.Manifest
	var parsed *view.ParsedView
	if err := bundle.WithDocRLock(docPath, func() error {
		var err error
		docBytes, err = os.ReadFile(docPath)
		if err != nil {
			return err
		}
		manifest, _, err = bundle.LoadManifest(docPath, docBytes)
		if err != nil {
			return fmt.Errorf("load manifest: %w", err)
		}
		viewBytes, err := os.ReadFile(bundle.ViewPath(docPath))
		switch {
		case err == nil:
			parsed, err = view.ReadView(viewBytes)
			if err != nil {
				return fmt.Errorf("read GenUI view: %w", err)
			}
		case errors.Is(err, fs.ErrNotExist):
			// Prose-only bundles intentionally have no sidecar.
		default:
			return fmt.Errorf("read GenUI view: %w", err)
		}
		return nil
	}); err != nil {
		return ExportResult{}, err
	}

	title := strings.TrimSpace(opts.Title)
	if title == "" {
		title = inferTitle(docPath, string(docBytes))
	}
	images := newImageTransformer(imageOptions{
		docPath:       docPath,
		docDir:        filepath.Dir(docPath),
		external:      opts.ExternalAssets,
		maxImageBytes: opts.MaxImageBytes,
		maxHTMLBytes:  opts.MaxHTMLBytes,
	})
	rendered, moduleCount, err := renderHTMLWithImages(string(docBytes), manifest, parsed, title, images)
	if err != nil {
		return ExportResult{}, err
	}
	if err := images.copyExternalAssets(outPath); err != nil {
		return ExportResult{}, err
	}
	if err := bundle.WriteFileAtomic(outPath, []byte(rendered), 0o644); err != nil {
		return ExportResult{}, fmt.Errorf("write export: %w", err)
	}
	assetMode := "inline"
	if opts.ExternalAssets {
		assetMode = "external"
	}
	return ExportResult{
		DocPath:     docPath,
		OutPath:     outPath,
		BundleID:    manifest.BundleID,
		Revision:    manifest.Revision,
		Bytes:       len([]byte(rendered)),
		ModuleCount: moduleCount,
		ImageCount:  images.count,
		AssetMode:   assetMode,
	}, nil
}

// ensureSafeExportPath prevents `deepread export` from clobbering the source
// Markdown, its sidecars, or protected `.deepread/` metadata files (including
// via relative path aliases or symlinks).
func ensureSafeExportPath(docPath, outPath string) error {
	canon := func(p string) string {
		abs, err := filepath.Abs(p)
		if err != nil {
			return filepath.Clean(p)
		}
		if resolved, err := filepath.EvalSymlinks(abs); err == nil {
			return resolved
		}
		if resolvedDir, err := filepath.EvalSymlinks(filepath.Dir(abs)); err == nil {
			return filepath.Join(resolvedDir, filepath.Base(abs))
		}
		return abs
	}

	outCanon := canon(outPath)
	outStat, outStatErr := os.Stat(outPath)
	// Always compare protected bundle paths case-insensitively across all OSes
	// so case-folded mounts (APFS, SMB/CIFS, ext4 casefold) cannot be bypassed
	// even before `.deepread/history` exists on disk.
	pathsEqual := func(a, b string) bool {
		return a == b || strings.EqualFold(a, b)
	}
	isWithinDir := func(candidate, dir string) bool {
		dirStat, dirStatErr := os.Stat(dir)
		for cur := candidate; ; {
			if pathsEqual(cur, dir) {
				return true
			}
			if dirStatErr == nil {
				if st, err := os.Stat(cur); err == nil && os.SameFile(st, dirStat) {
					return true
				}
			}
			parent := filepath.Dir(cur)
			if parent == cur {
				return false
			}
			cur = parent
		}
	}

	viewPath := bundle.ViewPath(docPath)
	protected := []string{
		docPath,
		viewPath,
		bundle.PrevViewPath(viewPath),
		bundle.ManifestPath(docPath),
		bundle.LedgerPath(docPath),
		filepath.Join(bundle.MetaDir(docPath), ".lock"),
	}
	for _, p := range protected {
		if pathsEqual(outCanon, canon(p)) {
			return fmt.Errorf("refusing to overwrite protected bundle file %q with HTML export", outPath)
		}
		if outStatErr == nil {
			if pStat, err := os.Stat(p); err == nil && os.SameFile(outStat, pStat) {
				return fmt.Errorf("refusing to overwrite protected bundle file %q with HTML export", outPath)
			}
		}
	}
	histDir := canon(filepath.Join(bundle.MetaDir(docPath), "history"))
	if isWithinDir(outCanon, histDir) {
		return fmt.Errorf("refusing to write HTML export inside protected history directory %q", outPath)
	}
	return nil
}

func inferTitle(docPath, raw string) string {
	for _, sec := range markdown.ExtractSections(raw) {
		if sec.Level == 1 && strings.TrimSpace(sec.Heading) != "" {
			return sec.Heading
		}
	}
	base := filepath.Base(docPath)
	return strings.TrimSuffix(base, filepath.Ext(base))
}

type sectionKey struct {
	heading    string
	occurrence int
}

// RenderHTML renders prose and evaluated reading modules in exact document order.
// Raw HTML remains disabled in goldmark, and every OpenUI string is escaped by
// the static primitive renderers.
func RenderHTML(docRaw string, manifest bundle.Manifest, parsed *view.ParsedView, title string) (string, int, error) {
	images := newImageTransformer(imageOptions{})
	return renderHTMLWithImages(docRaw, manifest, parsed, title, images)
}

func renderHTMLWithImages(docRaw string, manifest bundle.Manifest, parsed *view.ParsedView, title string, images *imageTransformer) (string, int, error) {
	sections := markdown.ExtractSections(docRaw)
	type pendingModule struct {
		el     *openuilang.Element
		module view.ValidatedModule
	}
	modulesBySection := map[int][]pendingModule{}
	moduleCount := 0

	if strings.TrimSpace(title) == "" {
		title = "DeepRead"
	}
	csp := contentSecurityPolicy
	if images.external {
		csp = externalContentSecurityPolicy
	}
	shellBytes := len(renderDocumentWithCSP(title, "", csp))
	maxBodyBytes := 0
	enforceBudget := !images.external && images.maxHTMLBytes > 0
	if enforceBudget {
		maxBodyBytes = images.maxHTMLBytes - shellBytes
		if maxBodyBytes < 0 {
			return "", 0, fmt.Errorf("%w: total HTML exceeds budget; re-run with --external-assets or compress images", ErrAssetBudgetExceeded)
		}
	}

	if parsed != nil {
		validated, err := view.ValidateStrict(docRaw, parsed.JoinedText, parsed.Envelope.Sources)
		if err != nil {
			return "", 0, fmt.Errorf("validate GenUI view: %w", err)
		}
		children, _ := validated.Root.Props.Values["children"].([]any)
		if len(children) != len(validated.Modules) {
			return "", 0, fmt.Errorf("GenUI root has %d children for %d validated modules", len(children), len(validated.Modules))
		}
		for i, module := range validated.Modules {
			el, ok := children[i].(*openuilang.Element)
			if !ok || el == nil || el.Type != "Source" {
				return "", 0, fmt.Errorf("GenUI root child %q is not a Source", module.Statement)
			}
			matches := make([]int, 0, 1)
			key := sectionKey{markdown.NormalizeHeadingText(module.Section.Heading), module.Section.Occurrence}
			for idx, sec := range sections {
				if (sectionKey{markdown.NormalizeHeadingText(sec.Heading), sec.Occurrence}) == key {
					matches = append(matches, idx)
				}
			}
			if len(matches) != 1 {
				return "", 0, fmt.Errorf("source for statement %q resolves to %d sections for %q occurrence %d; want exactly one", module.Statement, len(matches), module.Section.Heading, module.Section.Occurrence)
			}
			target := matches[0]
			modulesBySection[target] = append(modulesBySection[target], pendingModule{el: el, module: module})
			moduleCount++
		}
	}

	transformers := []util.PrioritizedValue{
		util.Prioritized(safeLinkTransformer{}, 900),
		util.Prioritized(images, 901),
	}
	renderer := goldmark.New(
		goldmark.WithExtensions(extension.GFM),
		goldmark.WithParserOptions(parser.WithASTTransformers(transformers...)),
	)
	// Reference collection needs only link transforms. Keeping image I/O out of
	// this preliminary parse ensures each image is resolved once per rendered slice.
	referenceParser := goldmark.New(
		goldmark.WithExtensions(extension.GFM),
		goldmark.WithParserOptions(
			parser.WithASTTransformers(util.Prioritized(safeLinkTransformer{}, 900)),
		),
	).Parser()
	fullPC := parser.NewContext()
	_ = referenceParser.Parse(text.NewReader([]byte(markdown.StripNotes(docRaw))), parser.WithContext(fullPC))
	globalRefs := fullPC.References()
	body := &budgetWriter{limit: maxBodyBytes, enforce: enforceBudget}

	renderSlice := func(raw string) error {
		raw = markdown.StripNotes(raw)
		pc := parser.NewContext()
		for _, ref := range globalRefs {
			pc.AddReference(ref)
		}
		if err := renderer.Convert([]byte(raw), body, parser.WithContext(pc)); err != nil {
			if images.err != nil {
				return images.err
			}
			return err
		}
		if images.err != nil {
			return images.err
		}
		return nil
	}

	if len(sections) == 0 {
		if err := renderSlice(docRaw); err != nil {
			return "", 0, fmt.Errorf("render Markdown: %w", err)
		}
	} else {
		if sections[0].ByteStart() > 0 {
			if err := renderSlice(docRaw[:sections[0].ByteStart()]); err != nil {
				return "", 0, fmt.Errorf("render Markdown preamble: %w", err)
			}
		}
		for i, sec := range sections {
			end := markdown.OwnBodyEndByte(docRaw, sections, i)
			raw := docRaw[sec.ByteStart():end]
			if manifest.IsSynthetic(sec.Heading, sec.Occurrence) {
				raw = withoutLeadingHeading(raw, sec)
				if err := body.WriteString(`<div class="dr-sec-break"><span>` + html.EscapeString(sec.Heading) + `</span></div>` + "\n"); err != nil {
					return "", 0, err
				}
			}
			if err := renderSlice(raw); err != nil {
				return "", 0, fmt.Errorf("render Markdown section %q occurrence %d: %w", sec.Heading, sec.Occurrence, err)
			}
			for _, pm := range modulesBySection[i] {
				moduleHTML, err := renderModule(pm.el, pm.module, manifest)
				if err != nil {
					return "", 0, fmt.Errorf("render module %q: %w", pm.module.Statement, err)
				}
				if err := body.WriteString(moduleHTML); err != nil {
					return "", 0, err
				}
			}
		}
	}

	rendered := renderDocumentWithCSP(title, body.String(), csp)
	if enforceBudget && len(rendered) > images.maxHTMLBytes {
		return "", 0, fmt.Errorf("%w: total HTML exceeds budget; re-run with --external-assets or compress images", ErrAssetBudgetExceeded)
	}
	return rendered, moduleCount, nil
}

// budgetWriter streams HTML directly into a strings.Builder while enforcing an
// exact byte ceiling before allocating oversized buffers.
type budgetWriter struct {
	buf     strings.Builder
	limit   int
	enforce bool
}

func (w *budgetWriter) Write(p []byte) (int, error) {
	if w.enforce && w.buf.Len()+len(p) > w.limit {
		return 0, fmt.Errorf("%w: total HTML exceeds budget; re-run with --external-assets or compress images", ErrAssetBudgetExceeded)
	}
	return w.buf.Write(p)
}

func (w *budgetWriter) WriteString(s string) error {
	if w.enforce && w.buf.Len()+len(s) > w.limit {
		return fmt.Errorf("%w: total HTML exceeds budget; re-run with --external-assets or compress images", ErrAssetBudgetExceeded)
	}
	_, err := w.buf.WriteString(s)
	return err
}

func (w *budgetWriter) String() string { return w.buf.String() }

// safeLinkTransformer strips unsafe URL schemes (including all data: and
// javascript: URIs) from Markdown hyperlinks so anchor hrefs can never carry
// executable or inline data payloads.
type safeLinkTransformer struct{}

func (safeLinkTransformer) Transform(node *ast.Document, reader text.Reader, _ parser.Context) {
	source := reader.Source()
	var badAutoLinks []*ast.AutoLink
	_ = ast.Walk(node, func(n ast.Node, entering bool) (ast.WalkStatus, error) {
		if !entering {
			return ast.WalkContinue, nil
		}
		switch target := n.(type) {
		case *ast.Link:
			if isUnsafeHref(string(target.Destination)) {
				target.Destination = nil
			}
		case *ast.AutoLink:
			if isUnsafeHref(string(target.URL(source))) {
				badAutoLinks = append(badAutoLinks, target)
			}
		}
		return ast.WalkContinue, nil
	})
	for _, al := range badAutoLinks {
		if parent := al.Parent(); parent != nil {
			plain := ast.NewString(al.Label(source))
			parent.ReplaceChild(parent, al, plain)
		}
	}
}

func isUnsafeHref(dest string) bool {
	probe := strings.ToLower(urlSchemeProbe(dest))
	if !hasURIScheme(probe) {
		return false
	}
	switch {
	case strings.HasPrefix(probe, "http://"),
		strings.HasPrefix(probe, "https://"),
		strings.HasPrefix(probe, "mailto:"):
		return false
	default:
		return true
	}
}

func withoutLeadingHeading(raw string, sec markdown.Section) string {
	firstEnd := strings.IndexByte(raw, '\n')
	if firstEnd < 0 {
		firstEnd = len(raw)
	} else {
		firstEnd++
	}
	firstLine := strings.TrimRight(raw[:firstEnd], "\r\n")
	if level, _, ok := markdown.ATXHeading(firstLine); ok && level == sec.Level {
		return raw[firstEnd:]
	}
	// Be conservative for Setext headings: remove the two source lines only
	// when the extractor identified this same section level.
	if firstEnd < len(raw) {
		secondEndRelative := strings.IndexByte(raw[firstEnd:], '\n')
		secondEnd := len(raw)
		if secondEndRelative >= 0 {
			secondEnd = firstEnd + secondEndRelative + 1
		}
		secondLine := strings.TrimRight(raw[firstEnd:secondEnd], "\r\n")
		if markdown.SetextLevel(secondLine) == sec.Level {
			return raw[secondEnd:]
		}
	}
	return raw
}

func renderModule(source *openuilang.Element, module view.ValidatedModule, manifest bundle.Manifest) (string, error) {
	revision := manifest.Revision
	if revision < 1 {
		revision = 1
	}
	shortCode := fmt.Sprintf("%s·%s@r%d", manifest.BundleID, module.Statement, revision)
	children, err := renderNodeList(source.Props.Values["children"], false)
	if err != nil {
		return "", err
	}
	return `<section class="dr-module">` +
		`<header class="dr-module-meta"><code class="dr-shortcode">` + html.EscapeString(shortCode) + `</code>` +
		`<span class="dr-module-source">` + html.EscapeString(module.Section.Heading) + `</span></header>` +
		children + `</section>` + "\n", nil
}

func renderNodeList(value any, inline bool) (string, error) {
	items, ok := value.([]any)
	if !ok {
		return "", nil
	}
	var out strings.Builder
	for _, item := range items {
		rendered, err := renderNode(item, inline)
		if err != nil {
			return "", err
		}
		out.WriteString(rendered)
	}
	return out.String(), nil
}

func renderNode(value any, inline bool) (string, error) {
	switch v := value.(type) {
	case nil:
		return "", nil
	case string:
		return html.EscapeString(v), nil
	case float64:
		return strconv.FormatFloat(v, 'f', -1, 64), nil
	case bool:
		return strconv.FormatBool(v), nil
	case []any:
		return renderNodeList(v, inline)
	case *openuilang.Element:
		return renderElement(v, inline)
	default:
		return "", fmt.Errorf("unsupported OpenUI value %T", value)
	}
}

func renderElement(el *openuilang.Element, inline bool) (string, error) {
	if el == nil {
		return "", nil
	}
	props := el.Props
	switch el.Type {
	case "Col":
		children, err := renderNodeList(props.Values["children"], false)
		return `<div class="dr-col">` + children + `</div>` + "\n", err
	case "Title":
		size := stringProperty(props, "size", "md")
		switch size {
		case "sm", "md", "lg", "xl", "2xl", "3xl":
		default:
			size = "md"
		}
		return `<h3 class="dr-title dr-title-` + size + `"` + colorStyle(stringProperty(props, "color", "")) + `>` +
			html.EscapeString(stringProperty(props, "text", "")) + `</h3>` + "\n", nil
	case "Text":
		return renderText(el, inline)
	case "Caption":
		return `<p class="dr-caption"` + colorStyle(stringProperty(props, "color", "")) + `>` +
			html.EscapeString(stringProperty(props, "text", "")) + `</p>` + "\n", nil
	case "Quote":
		quote := `<figure class="dr-quote"><blockquote>` + html.EscapeString(stringProperty(props, "text", "")) + `</blockquote>`
		if cite := stringProperty(props, "cite", ""); cite != "" {
			quote += `<figcaption>` + html.EscapeString(cite) + `</figcaption>`
		}
		return quote + `</figure>` + "\n", nil
	case "List":
		return renderList(el)
	case "ListItem":
		return renderStandaloneListItem(el)
	case "Table":
		return renderTable(el)
	case "Chart":
		return renderChart(el)
	case "Source":
		return "", fmt.Errorf("nested Source elements are not renderable")
	default:
		return "", fmt.Errorf("unsupported component %q", el.Type)
	}
}

func renderText(el *openuilang.Element, inline bool) (string, error) {
	props := el.Props
	classes := []string{"dr-text"}
	size := stringProperty(props, "size", "md")
	switch size {
	case "xs", "sm", "md", "lg":
		classes = append(classes, "dr-text-"+size)
	default:
		classes = append(classes, "dr-text-md")
	}
	if weight := stringProperty(props, "weight", ""); weight == "medium" || weight == "semibold" {
		classes = append(classes, "dr-weight-"+weight)
	}
	if boolProperty(props, "italic") {
		classes = append(classes, "dr-italic")
	}
	if boolProperty(props, "lineThrough") {
		classes = append(classes, "dr-line-through")
	}
	if boolProperty(props, "tabularNums") {
		classes = append(classes, "dr-tabular")
	}

	var content string
	switch text := props.Values["text"].(type) {
	case string:
		content = html.EscapeString(text)
	case []any:
		var err error
		content, err = renderNodeList(text, true)
		if err != nil {
			return "", err
		}
	default:
		content = ""
	}
	tag := "p"
	suffix := "\n"
	if inline {
		tag = "span"
		suffix = ""
	}
	return `<` + tag + ` class="` + strings.Join(classes, " ") + `"` + colorStyle(stringProperty(props, "color", "")) + `>` + content + `</` + tag + `>` + suffix, nil
}

func renderList(el *openuilang.Element) (string, error) {
	props := el.Props
	marker := stringProperty(props, "marker", "bullet")
	tag := "ul"
	class := "dr-list"
	if marker == "number" {
		tag = "ol"
	}
	if marker == "none" {
		class += " dr-list-none"
	}
	if boolProperty(props, "timeline") {
		class += " dr-timeline"
	}
	items, _ := props.Values["items"].([]any)
	var out strings.Builder
	out.WriteString(`<` + tag + ` class="` + class + `">`)
	for _, item := range items {
		switch v := item.(type) {
		case string:
			out.WriteString(`<li>` + html.EscapeString(v) + `</li>`)
		case *openuilang.Element:
			if v == nil || v.Type != "ListItem" {
				return "", fmt.Errorf("List item must be text or ListItem, got %T", item)
			}
			rendered, err := renderListItem(v)
			if err != nil {
				return "", err
			}
			out.WriteString(rendered)
		default:
			return "", fmt.Errorf("unsupported List item %T", item)
		}
	}
	out.WriteString(`</` + tag + `>` + "\n")
	return out.String(), nil
}

func renderListItem(el *openuilang.Element) (string, error) {
	props := el.Props
	var out strings.Builder
	out.WriteString(`<li class="dr-list-item">`)
	if marker := stringProperty(props, "marker", ""); marker != "" {
		out.WriteString(`<span class="dr-list-marker">` + html.EscapeString(marker) + `</span>`)
	}
	out.WriteString(`<div class="dr-list-content"><div class="dr-list-title">` + html.EscapeString(stringProperty(props, "title", "")) + `</div>`)
	if description := stringProperty(props, "description", ""); description != "" {
		out.WriteString(`<div class="dr-list-description">` + html.EscapeString(description) + `</div>`)
	}
	children, err := renderNodeList(props.Values["children"], false)
	if err != nil {
		return "", err
	}
	out.WriteString(children + `</div></li>`)
	return out.String(), nil
}

func renderStandaloneListItem(el *openuilang.Element) (string, error) {
	item, err := renderListItem(el)
	if err != nil {
		return "", err
	}
	return `<ul class="dr-list dr-list-none">` + item + `</ul>` + "\n", nil
}

func renderTable(el *openuilang.Element) (string, error) {
	props := el.Props
	columns, _ := props.Values["columns"].([]any)
	rows, _ := props.Values["rows"].([]any)
	numeric := make([]bool, len(columns))
	for col := range columns {
		numeric[col] = true
		hasValue := false
		for _, rawRow := range rows {
			row, _ := rawRow.([]any)
			if col >= len(row) || row[col] == nil {
				continue
			}
			if _, ok := row[col].(float64); !ok {
				numeric[col] = false
				break
			}
			hasValue = true
		}
		numeric[col] = numeric[col] && hasValue
	}

	var out strings.Builder
	out.WriteString(`<div class="dr-table-wrap" role="region" tabindex="0"><table class="dr-table"><thead><tr>`)
	for i, column := range columns {
		class := ""
		if i < len(numeric) && numeric[i] {
			class = ` class="dr-num"`
		}
		out.WriteString(`<th scope="col"` + class + `>` + html.EscapeString(fmt.Sprint(column)) + `</th>`)
	}
	out.WriteString(`</tr></thead><tbody>`)
	for _, rawRow := range rows {
		row, ok := rawRow.([]any)
		if !ok {
			return "", fmt.Errorf("Table row must be an array, got %T", rawRow)
		}
		out.WriteString(`<tr>`)
		for i, cell := range row {
			class := ""
			if i < len(numeric) && numeric[i] {
				class = ` class="dr-num"`
			}
			out.WriteString(`<td` + class + `>`)
			if number, ok := cell.(float64); ok {
				out.WriteString(strconv.FormatFloat(number, 'f', -1, 64))
			} else {
				rendered, err := renderNode(cell, true)
				if err != nil {
					return "", err
				}
				out.WriteString(rendered)
			}
			out.WriteString(`</td>`)
		}
		out.WriteString(`</tr>`)
	}
	out.WriteString(`</tbody></table></div>` + "\n")
	return out.String(), nil
}

func stringProperty(props *openuilang.Object, name, fallback string) string {
	if props == nil {
		return fallback
	}
	if value, ok := props.Values[name].(string); ok {
		return value
	}
	return fallback
}

func boolProperty(props *openuilang.Object, name string) bool {
	if props == nil {
		return false
	}
	value, _ := props.Values[name].(bool)
	return value
}

var safeHexColorRE = regexp.MustCompile(`^#[0-9A-Fa-f]{3,8}$`)
var safeNamedColorRE = regexp.MustCompile(`^[A-Za-z]+$`)
var safeFunctionalColorRE = regexp.MustCompile(`^(?i:(?:rgb|rgba|hsl|hsla))\([0-9.,%+\- /]+\)$`)

func colorStyle(color string) string {
	color = strings.TrimSpace(color)
	if color == "" || !safeHexColorRE.MatchString(color) && !safeNamedColorRE.MatchString(color) && !safeFunctionalColorRE.MatchString(color) {
		return ""
	}
	return ` style="color:` + html.EscapeString(color) + `"`
}
