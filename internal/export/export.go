package export

import (
	"errors"
	"fmt"
	"html"
	"os"
	"path/filepath"
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
	DefaultMaxImageBytes    = 512 << 10
	DefaultMaxHTMLBytes     = 1536 << 10
	DefaultMaxBookHTMLBytes = 6 * 1024 * 1024
)

var ErrAssetBudgetExceeded = errors.New("asset budget exceeded")
var ErrUnsafeAssetPath = errors.New("unsafe asset path")

// ExportOptions configures an HTML export. Empty Face, Lang and Mode preserve
// the bundle's reading contract while selecting the v0.3 dual-face reader.
type ExportOptions struct {
	Title                   string
	ExternalAssets          bool
	MaxImageBytes           int
	MaxHTMLBytes            int
	Face                    string // inline | dual | genui | read | margin
	Lang                    string // auto | original | BCP 47 target language
	Mode                    string // auto | original | translated | bilingual
	NoJS                    bool
	AllowPartialTranslation bool
}

// ExportResult describes the generated standalone HTML document.
type ExportResult struct {
	DocPath      string   `json:"docPath"`
	OutPath      string   `json:"outPath"`
	BundleID     string   `json:"bundleId"`
	Revision     int      `json:"revision"`
	Bytes        int      `json:"bytes"`
	ModuleCount  int      `json:"moduleCount"`
	ImageCount   int      `json:"imageCount"`
	AssetMode    string   `json:"assetMode"`
	Warnings     []string `json:"warnings,omitempty"`
	Face         string   `json:"face"`
	Lang         string   `json:"lang"`
	Mode         string   `json:"mode"`
	ChapterCount int      `json:"chapterCount"`
	IslandCount  int      `json:"islandCount"`
}

// Export reads one DeepRead bundle and atomically publishes its reader.
func Export(docPath, outPath string, opts ExportOptions) (ExportResult, error) {
	return exportDocument(docPath, outPath, opts)
}

// ensureSafeExportPath prevents HTML or asset output from clobbering any
// source, sidecar, translation, citation, history, lock, or other .deepread file.
func ensureSafeExportPath(docPath, outPath string) error {
	canon := canonicalProspectivePath
	outCanon, err := canon(outPath)
	if err != nil {
		return fmt.Errorf("resolve export output path: %w", err)
	}
	outStat, outStatErr := os.Stat(outPath)
	pathsEqual := func(a, b string) bool { return a == b || strings.EqualFold(a, b) }
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
		docPath, viewPath, bundle.PrevViewPath(viewPath), bundle.ManifestPath(docPath),
		bundle.LedgerPath(docPath), bundle.CitationsPath(docPath), filepath.Join(bundle.MetaDir(docPath), ".lock"),
	}
	for _, p := range protected {
		protectedCanon, err := canon(p)
		if err == nil && pathsEqual(outCanon, protectedCanon) {
			return fmt.Errorf("refusing to overwrite protected bundle file %q with HTML export", outPath)
		}
		if outStatErr == nil {
			if pStat, err := os.Stat(p); err == nil && os.SameFile(outStat, pStat) {
				return fmt.Errorf("refusing to overwrite protected bundle file %q with HTML export", outPath)
			}
		}
	}
	metadataRoot, err := canon(bundle.MetaDir(docPath))
	if err == nil && isWithinDir(outCanon, metadataRoot) {
		return fmt.Errorf("refusing to write HTML export inside protected .deepread directory %q", outPath)
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

// RenderHTML retains the v0.2 static interleaved API for existing integrations.
// New file exports use ValidateForExport and the dual-face reader in book.go.
func RenderHTML(docRaw string, manifest bundle.Manifest, parsed *view.ParsedView, title string) (string, int, error) {
	images := newImageTransformer(imageOptions{})
	body, count, err := renderLegacyBody(docRaw, manifest, parsed, title, images, false, "c01", nil)
	if err != nil {
		return "", 0, err
	}
	csp := contentSecurityPolicy
	if images.external {
		csp = externalContentSecurityPolicy
	}
	rendered := renderDocumentWithCSP(title, body, csp)
	if !images.external && images.maxHTMLBytes > 0 && len(rendered) > images.maxHTMLBytes {
		return "", 0, fmt.Errorf("%w: total HTML exceeds budget; re-run with --external-assets or compress images", ErrAssetBudgetExceeded)
	}
	return rendered, count, nil
}

func renderHTMLWithImages(docRaw string, manifest bundle.Manifest, parsed *view.ParsedView, title string, images *imageTransformer) (string, int, error) {
	body, count, err := renderLegacyBody(docRaw, manifest, parsed, title, images, false, "c01", nil)
	if err != nil {
		return "", 0, err
	}
	csp := contentSecurityPolicy
	if images.external {
		csp = externalContentSecurityPolicy
	}
	return renderDocumentWithCSP(title, body, csp), count, nil
}

func renderLegacyBody(docRaw string, manifest bundle.Manifest, parsed *view.ParsedView, title string, images *imageTransformer, forExport bool, prefix string, fixedRoot *openuilang.Element) (string, int, error) {
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
	if parsed != nil {
		var validated view.ValidationResult
		var err error
		if forExport {
			validated, err = view.ValidateForExport("", []byte(docRaw), parsed.Statements, parsed.Envelope.Sources, manifest.Profile)
		} else {
			validatedPtr, strictErr := view.ValidateStrict(docRaw, parsed.JoinedText, parsed.Envelope.Sources)
			err = strictErr
			if validatedPtr != nil {
				validated = *validatedPtr
			}
		}
		if err != nil {
			return "", 0, fmt.Errorf("validate GenUI view: %w", err)
		}
		if fixedRoot != nil {
			validated.Root = fixedRoot
		}
		children, _ := validated.Root.Props.Values["children"].([]any)
		if manifest.Profile != bundle.ProfileMargin && forExport {
			// Canvas roots may contain headings and other non-Source children; the
			// dual-face renderer handles those separately. Margin remains direct Source-only.
		} else {
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
	}
	body := &budgetWriter{}
	write := func(s string) error { return body.WriteString(s) }
	renderSlice := func(raw string) error {
		fragment, err := renderMarkdownWithImagesAndRefs(raw, images, nil)
		if err != nil {
			return err
		}
		return write(fragment)
	}
	// Parse references once without touching image IO, then reuse them in each
	// disjoint source slice so cross-section reference links keep working.
	referenceParser := goldmark.New(goldmark.WithExtensions(extension.GFM), goldmark.WithParserOptions(parser.WithASTTransformers(util.Prioritized(safeLinkTransformer{}, 900)))).Parser()
	fullPC := parser.NewContext()
	_ = referenceParser.Parse(text.NewReader([]byte(markdown.StripNotes(docRaw))), parser.WithContext(fullPC))
	globalRefs := fullPC.References()
	renderSlice = func(raw string) error {
		fragment, err := renderMarkdownWithImagesAndRefs(raw, images, globalRefs)
		if err != nil {
			return err
		}
		return write(fragment)
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
				if forExport {
					if err := write(`<h2 id="` + prefix + `-s` + fmt.Sprintf("%02d", i+1) + `" class="dr-sec-break"><span>` + html.EscapeString(sec.Heading) + `</span></h2>` + "\n"); err != nil {
						return "", 0, err
					}
				} else if err := write(`<div class="dr-sec-break"><span>` + html.EscapeString(sec.Heading) + `</span></div>` + "\n"); err != nil {
					return "", 0, err
				}
			}
			if err := renderSlice(raw); err != nil {
				return "", 0, fmt.Errorf("render Markdown section %q occurrence %d: %w", sec.Heading, sec.Occurrence, err)
			}
			for _, pm := range modulesBySection[i] {
				moduleHTML, err := renderLegacyModule(pm.el, pm.module, manifest, images, prefix, forExport)
				if err != nil {
					return "", 0, fmt.Errorf("render module %q: %w", pm.module.Statement, err)
				}
				if err := write(moduleHTML); err != nil {
					return "", 0, err
				}
			}
		}
	}
	return body.String(), moduleCount, nil
}

func renderLegacyModule(source *openuilang.Element, module view.ValidatedModule, manifest bundle.Manifest, images *imageTransformer, prefix string, forExport bool) (string, error) {
	revision := manifest.Revision
	if revision < 1 {
		revision = 1
	}
	shortCode := fmt.Sprintf("%s·%s@r%d", manifest.BundleID, module.Statement, revision)
	renderer := &genuiRenderer{images: images, disableControls: true}
	children, err := renderer.renderNodeList(source.Props.Values["children"], false)
	if err != nil {
		return "", err
	}
	id := ""
	meta := `<header class="dr-module-meta"><code class="dr-shortcode">` + html.EscapeString(shortCode) + `</code><span class="dr-module-source">` + html.EscapeString(module.Section.Heading) + `</span></header>`
	if forExport {
		id = ` id="` + prefix + `-g-` + safeAnchorToken(module.Statement) + `"`
		meta = `<details class="dr-feedback"><summary>反馈码</summary><code class="dr-shortcode">` + html.EscapeString(shortCode) + `</code></details>`
	}
	return `<section` + id + ` class="dr-module">` + meta + children + `</section>` + "\n", nil
}

func renderMarkdownWithImages(raw string, images *imageTransformer) (string, error) {
	return renderMarkdownWithImagesAndRefs(raw, images, nil)
}

func renderMarkdownWithImagesAndRefs(raw string, images *imageTransformer, refs []parser.Reference) (string, error) {
	transformers := []util.PrioritizedValue{util.Prioritized(safeLinkTransformer{}, 900)}
	if images != nil {
		transformers = append(transformers, util.Prioritized(images, 901))
	}
	renderer := goldmark.New(goldmark.WithExtensions(extension.GFM), goldmark.WithParserOptions(parser.WithASTTransformers(transformers...)))
	pc := parser.NewContext()
	for _, ref := range refs {
		pc.AddReference(ref)
	}
	var out strings.Builder
	if err := renderer.Convert([]byte(markdown.StripNotes(raw)), &out, parser.WithContext(pc)); err != nil {
		return "", err
	}
	if images != nil && images.err != nil {
		return "", images.err
	}
	return out.String(), nil
}

// budgetWriter is the single aggregate output ceiling used by all v0.3 faces.
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
	case strings.HasPrefix(probe, "http://"), strings.HasPrefix(probe, "https://"), strings.HasPrefix(probe, "mailto:"):
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

func safeAnchorToken(raw string) string {
	var out strings.Builder
	for _, r := range raw {
		if r >= 'a' && r <= 'z' || r >= 'A' && r <= 'Z' || r >= '0' && r <= '9' || r == '_' || r == '-' {
			out.WriteRune(r)
		} else {
			out.WriteByte('-')
		}
	}
	if out.Len() == 0 {
		return "module"
	}
	return out.String()
}
