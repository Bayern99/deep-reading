package export

import (
	"bytes"
	"crypto/sha256"
	"encoding/base64"
	"errors"
	"fmt"
	stdhtml "html"
	"image"
	_ "image/gif"
	_ "image/jpeg"
	_ "image/png"
	"io"
	"io/fs"
	"net/http"
	"net/url"
	"os"
	"path"
	"path/filepath"
	"regexp"
	"strings"
	"unicode"

	"deepread/internal/bundle"

	"github.com/yuin/goldmark/ast"
	"github.com/yuin/goldmark/parser"
	"github.com/yuin/goldmark/text"
)

const externalMaxImageBytes = 16 << 10 << 10

type imageOptions struct {
	docPath        string
	docDir         string
	external       bool
	maxImageBytes  int
	maxHTMLBytes   int
	shared         *sharedImageStore
	protectedDocs  []string
	protectedPaths []string
}

type imageAsset struct {
	source       string
	relativePath string
	data         []byte
	hash         string
	mime         string
	inlineURI    string
	refs         int
	width        int
	height       int
}

type sharedImageStore struct {
	external              bool
	preserveExternalNames bool
	assets                map[string]*imageAsset
	order                 []string
}

type imageTransformer struct {
	docPath          string
	docDir           string
	external         bool
	maxImageBytes    int
	maxHTMLBytes     int
	totalInlineBytes int
	count            int
	assets           []imageAsset
	shared           *sharedImageStore
	protectedDocs    []string
	protectedPaths   []string
	err              error
}

func newImageTransformer(opts imageOptions) *imageTransformer {
	if opts.maxImageBytes <= 0 {
		opts.maxImageBytes = DefaultMaxImageBytes
	}
	if opts.maxHTMLBytes <= 0 {
		opts.maxHTMLBytes = DefaultMaxHTMLBytes
	}
	if opts.shared != nil {
		opts.maxHTMLBytes = 0 // the shared budgetWriter owns the aggregate ceiling
	}
	return &imageTransformer{
		docPath:        opts.docPath,
		docDir:         opts.docDir,
		external:       opts.external,
		maxImageBytes:  opts.maxImageBytes,
		maxHTMLBytes:   opts.maxHTMLBytes,
		shared:         opts.shared,
		protectedDocs:  opts.protectedDocs,
		protectedPaths: opts.protectedPaths,
	}
}

// Transform neutralizes active image URLs and resolves local raster images.
// Goldmark transformers cannot return errors directly, so the first resolution
// error is retained and checked immediately after each conversion.
func (t *imageTransformer) Transform(node *ast.Document, _ text.Reader, _ parser.Context) {
	if t.err != nil {
		return
	}
	_ = ast.Walk(node, func(n ast.Node, entering bool) (ast.WalkStatus, error) {
		if !entering || t.err != nil {
			return ast.WalkContinue, nil
		}
		image, ok := n.(*ast.Image)
		if !ok {
			return ast.WalkContinue, nil
		}
		if err := t.transformImage(image); err != nil {
			t.err = err
			return ast.WalkStop, err
		}
		return ast.WalkContinue, nil
	})
}

func (t *imageTransformer) transformImage(image *ast.Image) error {
	destination := strings.TrimSpace(string(image.Destination))
	probe := strings.ToLower(urlSchemeProbe(destination))
	switch {
	case strings.HasPrefix(probe, "http://"), strings.HasPrefix(probe, "https://"):
		return nil
	case strings.HasPrefix(probe, "data:"):
		if !safeDataImageURI(probe) {
			image.Destination = nil
			return nil
		}
		if err := t.validateInlineDataImage(destination); err != nil {
			return err
		}
		if t.shared != nil {
			comma := strings.IndexByte(destination, ',')
			payload := strings.Map(func(r rune) rune {
				if unicode.IsSpace(r) {
					return -1
				}
				return r
			}, destination[comma+1:])
			data, err := base64.StdEncoding.DecodeString(payload)
			if err != nil {
				data, err = base64.RawStdEncoding.DecodeString(payload)
			}
			if err != nil {
				return fmt.Errorf("%w: invalid base64 in data: image URI", ErrUnsafeAssetPath)
			}
			mime := sniffRasterMIME(data)
			return t.shared.resolve(t, "", data, mime, image)
		}
		t.count++
		return nil
	case hasURIScheme(probe):
		image.Destination = nil
		return nil
	}

	// The backwards-compatible RenderHTML entry point has no filesystem root.
	// It retains relative references while still neutralizing active schemes.
	if t.docDir == "" {
		return nil
	}
	rel, err := cleanLocalImagePath(destination)
	if err != nil {
		return err
	}
	if hasURIScheme(urlSchemeProbe(rel)) {
		return fmt.Errorf("%w: image destination %q becomes an active URL after decoding", ErrUnsafeAssetPath, destination)
	}
	source, err := t.resolveLocalImage(rel, destination)
	if err != nil {
		return err
	}
	data, mime, err := t.readRasterImage(source, destination)
	if err != nil {
		return err
	}

	if t.shared != nil {
		return t.shared.resolve(t, rel, data, mime, image)
	}

	t.count++
	if t.external {
		image.Destination = []byte(rel)
		t.assets = append(t.assets, imageAsset{source: source, relativePath: rel, data: data})
		return nil
	}
	encoded := "data:" + mime + ";base64," + base64.StdEncoding.EncodeToString(data)
	t.totalInlineBytes += len(encoded)
	if t.maxHTMLBytes > 0 && t.totalInlineBytes > t.maxHTMLBytes {
		return fmt.Errorf("%w: total HTML exceeds budget; re-run with --external-assets or compress images", ErrAssetBudgetExceeded)
	}
	image.Destination = []byte(encoded)
	return nil
}

func (t *imageTransformer) validateInlineDataImage(destination string) error {
	limit := t.maxImageBytes
	if t.external {
		limit = externalMaxImageBytes
	}
	if limit <= 0 {
		limit = DefaultMaxImageBytes
	}
	comma := strings.IndexByte(destination, ',')
	if comma < 0 {
		return fmt.Errorf("%w: malformed data: image URI", ErrUnsafeAssetPath)
	}
	meta := strings.ToLower(urlSchemeProbe(destination[:comma]))
	if !strings.HasPrefix(meta, "data:") || !strings.HasSuffix(meta, ";base64") {
		return fmt.Errorf("%w: inline data: image URI must use base64 encoding", ErrUnsafeAssetPath)
	}
	declaredMIME := strings.TrimSuffix(strings.TrimPrefix(meta, "data:"), ";base64")
	payload := strings.Map(func(r rune) rune {
		if unicode.IsSpace(r) {
			return -1
		}
		return r
	}, destination[comma+1:])

	// Check encoded length BEFORE allocating a full decoded slice.
	maxEncoded := base64.StdEncoding.EncodedLen(limit) + 4
	if len(payload) > maxEncoded {
		return fmt.Errorf("%w: inline data: image exceeds %d bytes; re-run with --external-assets or compress the image", ErrAssetBudgetExceeded, limit)
	}
	decoded, err := base64.StdEncoding.DecodeString(payload)
	if err != nil {
		decoded, err = base64.RawStdEncoding.DecodeString(payload)
		if err != nil {
			return fmt.Errorf("%w: invalid base64 in data: image URI", ErrUnsafeAssetPath)
		}
	}
	if len(decoded) > limit {
		return fmt.Errorf("%w: inline data: image exceeds %d bytes; re-run with --external-assets or compress the image", ErrAssetBudgetExceeded, limit)
	}
	actualMIME := sniffRasterMIME(decoded)
	switch actualMIME {
	case "image/png", "image/jpeg", "image/gif", "image/webp", "image/avif":
	default:
		return fmt.Errorf("%w: inline data: image has invalid image MIME type %q; only safe raster images are allowed", ErrUnsafeAssetPath, actualMIME)
	}
	if actualMIME != declaredMIME {
		return fmt.Errorf("%w: inline data: image declared %q but sniffed %q", ErrUnsafeAssetPath, declaredMIME, actualMIME)
	}
	if !t.external && t.shared == nil {
		t.totalInlineBytes += len(destination)
		if t.maxHTMLBytes > 0 && t.totalInlineBytes > t.maxHTMLBytes {
			return fmt.Errorf("%w: cumulative inline images exceed total HTML budget (%d bytes); re-run with --external-assets or compress images", ErrAssetBudgetExceeded, t.maxHTMLBytes)
		}
	}
	return nil
}

func urlSchemeProbe(destination string) string {
	return strings.Map(func(r rune) rune {
		if unicode.IsSpace(r) || unicode.IsControl(r) {
			return -1
		}
		return r
	}, stdhtml.UnescapeString(destination))
}

func hasURIScheme(destination string) bool {
	colon := strings.IndexByte(destination, ':')
	if colon <= 0 {
		return false
	}
	for i, r := range destination[:colon] {
		if i == 0 {
			if !unicode.IsLetter(r) {
				return false
			}
			continue
		}
		if !unicode.IsLetter(r) && !unicode.IsDigit(r) && r != '+' && r != '-' && r != '.' {
			return false
		}
	}
	return true
}

func safeDataImageURI(lowerDestination string) bool {
	header := strings.TrimPrefix(lowerDestination, "data:")
	end := strings.IndexAny(header, ";,")
	if end >= 0 {
		header = header[:end]
	}
	switch header {
	case "image/png", "image/jpeg", "image/gif", "image/webp", "image/avif":
		return true
	default:
		return false
	}
}

func cleanLocalImagePath(destination string) (string, error) {
	rawPath := destination
	if cut := strings.IndexAny(rawPath, "?#"); cut >= 0 {
		rawPath = rawPath[:cut]
	}
	decoded, err := url.PathUnescape(rawPath)
	if err != nil || strings.ContainsRune(decoded, 0) {
		return "", fmt.Errorf("%w: image destination %q cannot be decoded safely", ErrUnsafeAssetPath, destination)
	}
	decoded = strings.ReplaceAll(decoded, `\`, "/")
	if decoded == "" || strings.HasPrefix(decoded, "/") || filepath.IsAbs(filepath.FromSlash(decoded)) {
		return "", fmt.Errorf("%w: image destination %q is empty or absolute", ErrUnsafeAssetPath, destination)
	}
	clean := path.Clean(decoded)
	if clean == "." || clean == ".." || strings.HasPrefix(clean, "../") {
		return "", fmt.Errorf("%w: image destination %q escapes the document directory", ErrUnsafeAssetPath, destination)
	}
	for _, component := range strings.Split(clean, "/") {
		if strings.EqualFold(component, ".deepread") {
			return "", fmt.Errorf("%w: image destination %q reads protected bundle metadata", ErrUnsafeAssetPath, destination)
		}
	}
	return clean, nil
}

func (t *imageTransformer) resolveLocalImage(rel, original string) (string, error) {
	docRoot, err := filepath.Abs(t.docDir)
	if err != nil {
		return "", fmt.Errorf("resolve document directory: %w", err)
	}
	docRoot, err = filepath.EvalSymlinks(docRoot)
	if err != nil {
		return "", fmt.Errorf("resolve document directory: %w", err)
	}
	candidate := filepath.Join(docRoot, filepath.FromSlash(rel))
	resolved, err := filepath.EvalSymlinks(candidate)
	if err != nil {
		return "", fmt.Errorf("resolve image %q: %w", original, err)
	}
	if !strictPathWithin(resolved, docRoot) {
		return "", fmt.Errorf("%w: image destination %q resolves outside the document directory", ErrUnsafeAssetPath, original)
	}
	metadataRoot, err := canonicalProspectivePath(bundle.MetaDir(t.docPath))
	if err == nil && pathWithinOrEqual(resolved, metadataRoot) {
		return "", fmt.Errorf("%w: image destination %q resolves inside protected bundle metadata", ErrUnsafeAssetPath, original)
	}
	for _, sidecar := range []string{bundle.ViewPath(t.docPath), bundle.PrevViewPath(bundle.ViewPath(t.docPath))} {
		if sameExistingFile(resolved, sidecar) {
			return "", fmt.Errorf("%w: image destination %q reads a protected sidecar", ErrUnsafeAssetPath, original)
		}
	}
	return resolved, nil
}

func sameExistingFile(candidate, protected string) bool {
	candidateInfo, candidateErr := os.Stat(candidate)
	protectedInfo, protectedErr := os.Stat(protected)
	if candidateErr == nil && protectedErr == nil && os.SameFile(candidateInfo, protectedInfo) {
		return true
	}
	candidateCanon, candidateErr := canonicalProspectivePath(candidate)
	protectedCanon, protectedErr := canonicalProspectivePath(protected)
	return candidateErr == nil && protectedErr == nil && strings.EqualFold(candidateCanon, protectedCanon)
}

// pathWithinOrEqual is used conservatively for protected-path DENIAL checks
// (case-folded so case-insensitive mounts cannot bypass metadata/sidecar blocks).
func pathWithinOrEqual(candidate, root string) bool {
	rootInfo, rootErr := os.Stat(root)
	for current := candidate; ; current = filepath.Dir(current) {
		if strings.EqualFold(current, root) {
			return true
		}
		if rootErr == nil {
			if info, err := os.Stat(current); err == nil && os.SameFile(info, rootInfo) {
				return true
			}
		}
		parent := filepath.Dir(current)
		if parent == current {
			return false
		}
	}
}

// strictPathWithin is used for AUTHORIZATION checks (allowing reads/writes only
// inside an exact canonical root directory — never widens boundary via case
// folding, including on case-sensitive Windows directories where filepath.Rel
// folds case).
func strictPathWithin(candidate, root string) bool {
	cleanCand := filepath.Clean(candidate)
	cleanRoot := filepath.Clean(root)
	sep := string(filepath.Separator)
	prefix := cleanRoot
	if !strings.HasSuffix(prefix, sep) {
		prefix += sep
	}
	if len(cleanCand) > len(prefix) && strings.HasPrefix(cleanCand, prefix) {
		return true
	}
	rootInfo, rootErr := os.Stat(cleanRoot)
	if rootErr != nil {
		return false
	}
	for current := filepath.Dir(cleanCand); ; {
		if info, err := os.Stat(current); err == nil && os.SameFile(info, rootInfo) {
			return true
		}
		parent := filepath.Dir(current)
		if parent == current {
			return false
		}
		current = parent
	}
}

func (t *imageTransformer) resolveDestination(destination string) (string, error) {
	link := ast.NewLink()
	link.Destination = []byte(destination)
	image := ast.NewImage(link)
	if err := t.transformImage(image); err != nil {
		return "", err
	}
	return string(image.Destination), nil
}

func (s *sharedImageStore) resolve(t *imageTransformer, rel string, data []byte, mime string, node *ast.Image) error {
	sum := sha256.Sum256(data)
	hash := fmt.Sprintf("%x", sum[:])
	asset, exists := s.assets[hash]
	if !exists {
		ext := map[string]string{"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/webp": ".webp", "image/avif": ".avif"}[mime]
		relativePath := "assets/" + hash[:16] + ext
		if s.external && s.preserveExternalNames && rel != "" {
			relativePath = rel
		}
		asset = &imageAsset{source: rel, relativePath: relativePath, data: append([]byte(nil), data...), hash: hash, mime: mime}
		asset.inlineURI = "data:" + mime + ";base64," + base64.StdEncoding.EncodeToString(data)
		if config, _, err := image.DecodeConfig(bytes.NewReader(data)); err == nil {
			asset.width, asset.height = config.Width, config.Height
		}
		s.assets[hash] = asset
		s.order = append(s.order, hash)
	}
	asset.refs++
	t.count++
	if s.external {
		node.Destination = []byte(asset.relativePath)
	} else {
		node.Destination = []byte(asset.inlineURI)
	}
	return nil
}

func (s *sharedImageStore) uniqueCount() int { return len(s.assets) }

func (s *sharedImageStore) inlineCSS() string {
	if s == nil || s.external {
		return ""
	}
	var out strings.Builder
	for _, hash := range s.order {
		asset := s.assets[hash]
		if asset.refs < 2 {
			continue
		}
		width, height := asset.width, asset.height
		if width <= 0 || height <= 0 {
			width, height = 16, 9
		}
		fmt.Fprintf(&out, ".dr-img-%s{display:block;width:100%%;max-width:100%%;aspect-ratio:%d / %d;background-image:url(\"%s\");background-size:contain;background-repeat:no-repeat;background-position:center;margin:1.5rem auto}", hash[:12], width, height, asset.inlineURI)
	}
	return out.String()
}

func (s *sharedImageStore) finalizeInlineHTML(rendered string) string {
	if s == nil || s.external {
		return rendered
	}
	for _, hash := range s.order {
		asset := s.assets[hash]
		if asset.refs < 2 {
			continue
		}
		uri := stdhtml.EscapeString(asset.inlineURI)
		pattern := regexp.MustCompile(`<img\b[^>]*src="` + regexp.QuoteMeta(uri) + `"[^>]*>`)
		rendered = pattern.ReplaceAllStringFunc(rendered, func(tag string) string {
			alt := ""
			if match := regexp.MustCompile(`alt="([^"]*)"`).FindStringSubmatch(tag); len(match) == 2 {
				alt = match[1]
			}
			return `<span class="dr-image dr-img-` + hash[:12] + `" role="img" aria-label="` + alt + `"></span>`
		})
	}
	return rendered
}

func (s *sharedImageStore) allAssets() []imageAsset {
	out := make([]imageAsset, 0, len(s.order))
	for _, hash := range s.order {
		out = append(out, *s.assets[hash])
	}
	return out
}

func (t *imageTransformer) readRasterImage(source, original string) ([]byte, string, error) {
	file, err := os.Open(source)
	if err != nil {
		return nil, "", fmt.Errorf("read image %q: %w", original, err)
	}
	defer file.Close()
	info, err := file.Stat()
	if err != nil {
		return nil, "", fmt.Errorf("stat image %q: %w", original, err)
	}
	if !info.Mode().IsRegular() {
		return nil, "", fmt.Errorf("%w: image destination %q is not a regular file", ErrUnsafeAssetPath, original)
	}
	limit := t.maxImageBytes
	if t.external {
		limit = externalMaxImageBytes
	}
	data, err := io.ReadAll(io.LimitReader(file, int64(limit)+1))
	if err != nil {
		return nil, "", fmt.Errorf("read image %q: %w", original, err)
	}
	if len(data) > limit {
		if t.external {
			return nil, "", fmt.Errorf("%w: image %q exceeds the %d-byte external safety cap", ErrAssetBudgetExceeded, original, limit)
		}
		return nil, "", fmt.Errorf("%w: image %q exceeds %d bytes; re-run with --external-assets or compress the image", ErrAssetBudgetExceeded, original, limit)
	}
	mime := sniffRasterMIME(data)
	switch mime {
	case "image/png", "image/jpeg", "image/gif", "image/webp", "image/avif":
		return data, mime, nil
	default:
		return nil, "", fmt.Errorf("%w: image %q has invalid image MIME type %q; only safe raster images are allowed", ErrUnsafeAssetPath, original, mime)
	}
}

func sniffRasterMIME(data []byte) string {
	if len(data) >= 12 && string(data[:4]) == "RIFF" && string(data[8:12]) == "WEBP" {
		return "image/webp"
	}
	if len(data) >= 12 && string(data[4:8]) == "ftyp" {
		switch string(data[8:12]) {
		case "avif", "avis":
			return "image/avif"
		}
	}
	mime := http.DetectContentType(data)
	if semicolon := strings.IndexByte(mime, ';'); semicolon >= 0 {
		mime = mime[:semicolon]
	}
	return mime
}

func (t *imageTransformer) commitExternalAssets(outPath string) (func(), error) {
	noop := func() {}
	assets := t.assets
	if t.shared != nil {
		assets = t.shared.allAssets()
	}
	if !t.external || len(assets) == 0 {
		return noop, nil
	}
	outDir := filepath.Dir(outPath)
	same, err := sameDirectory(t.docDir, outDir)
	if err != nil {
		return nil, fmt.Errorf("resolve external asset output directory: %w", err)
	}
	if same && t.shared == nil {
		return noop, nil
	}
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		return nil, fmt.Errorf("create external asset output directory: %w", err)
	}
	outRoot, err := filepath.EvalSymlinks(outDir)
	if err != nil {
		return nil, fmt.Errorf("resolve external asset output directory: %w", err)
	}
	outRootInfo, err := os.Stat(outRoot)
	if err != nil || !outRootInfo.IsDir() {
		return nil, fmt.Errorf("external asset output %q is not a directory", outDir)
	}

	type copyPlan struct {
		destination string
		data        []byte
	}
	plans := make([]copyPlan, 0, len(assets))
	seen := map[string]struct{}{}
	outCanon, err := canonicalProspectivePath(outPath)
	if err != nil {
		return nil, fmt.Errorf("resolve export output path: %w", err)
	}
	for _, asset := range assets {
		destination, err := canonicalProspectivePath(filepath.Join(outRoot, filepath.FromSlash(asset.relativePath)))
		if err != nil {
			return nil, fmt.Errorf("resolve external image destination %q: %w", asset.relativePath, err)
		}
		if !strictPathWithin(destination, outRoot) {
			return nil, fmt.Errorf("%w: external image destination %q escapes the output directory", ErrUnsafeAssetPath, asset.relativePath)
		}
		if strings.EqualFold(destination, outCanon) {
			return nil, fmt.Errorf("%w: external image %q collides with the HTML output", ErrUnsafeAssetPath, asset.relativePath)
		}
		docs := t.protectedDocs
		if len(docs) == 0 {
			docs = []string{t.docPath}
		}
		for _, docPath := range docs {
			if err := ensureSafeExportPath(docPath, destination); err != nil {
				return nil, fmt.Errorf("%w: external image destination %q collides with protected bundle data: %v", ErrUnsafeAssetPath, asset.relativePath, err)
			}
		}
		for _, protected := range t.protectedPaths {
			same, err := canonicalProspectivePath(protected)
			if err != nil {
				continue
			}
			if strings.EqualFold(same, destination) || pathWithinOrEqual(destination, same) {
				return nil, fmt.Errorf("%w: external image destination %q collides with protected book data", ErrUnsafeAssetPath, asset.relativePath)
			}
		}
		metadataRoot, metadataErr := canonicalProspectivePath(bundle.MetaDir(t.docPath))
		if metadataErr == nil && pathWithinOrEqual(destination, metadataRoot) {
			return nil, fmt.Errorf("%w: external image destination %q collides with protected bundle metadata", ErrUnsafeAssetPath, asset.relativePath)
		}
		if _, ok := seen[destination]; ok {
			continue
		}
		seen[destination] = struct{}{}
		plans = append(plans, copyPlan{destination: destination, data: asset.data})
	}
	type rollbackEntry struct {
		path    string
		existed bool
		prev    []byte
		mode    os.FileMode
	}
	committed := make([]rollbackEntry, 0, len(plans))
	rollback := func() {
		for i := len(committed) - 1; i >= 0; i-- {
			entry := committed[i]
			if entry.existed {
				_ = bundle.WriteFileAtomic(entry.path, entry.prev, entry.mode)
			} else {
				_ = os.Remove(entry.path)
			}
		}
	}
	for _, plan := range plans {
		rec := rollbackEntry{path: plan.destination, mode: 0o644}
		if info, err := os.Stat(plan.destination); err == nil && info.Mode().IsRegular() {
			prev, readErr := os.ReadFile(plan.destination)
			if readErr != nil {
				rollback()
				return nil, fmt.Errorf("snapshot existing external image %q: %w", plan.destination, readErr)
			}
			rec.existed = true
			rec.prev = prev
			rec.mode = info.Mode().Perm()
		}
		if err := bundle.WriteFileAtomic(plan.destination, plan.data, 0o644); err != nil {
			rollback()
			return nil, fmt.Errorf("copy external image %q: %w", plan.destination, err)
		}
		committed = append(committed, rec)
	}
	return rollback, nil
}

func (t *imageTransformer) copyExternalAssets(outPath string) error {
	_, err := t.commitExternalAssets(outPath)
	return err
}

func sameDirectory(a, b string) (bool, error) {
	aCanon, err := canonicalProspectivePath(a)
	if err != nil {
		return false, err
	}
	bCanon, err := canonicalProspectivePath(b)
	if err != nil {
		return false, err
	}
	if aCanon == bCanon {
		return true, nil
	}
	aInfo, aErr := os.Stat(aCanon)
	bInfo, bErr := os.Stat(bCanon)
	return aErr == nil && bErr == nil && os.SameFile(aInfo, bInfo), nil
}

// canonicalProspectivePath resolves every existing ancestor, including when
// the final path or several of its parent directories do not exist yet.
func canonicalProspectivePath(filePath string) (string, error) {
	abs, err := filepath.Abs(filePath)
	if err != nil {
		return "", err
	}
	if resolved, err := filepath.EvalSymlinks(abs); err == nil {
		return resolved, nil
	} else if !errors.Is(err, fs.ErrNotExist) {
		return "", err
	}
	var missing []string
	current := abs
	for {
		missing = append([]string{filepath.Base(current)}, missing...)
		parent := filepath.Dir(current)
		if parent == current {
			return "", fmt.Errorf("resolve path %q: no existing ancestor", filePath)
		}
		resolved, err := filepath.EvalSymlinks(parent)
		if err == nil {
			parts := append([]string{resolved}, missing...)
			return filepath.Join(parts...), nil
		}
		if !errors.Is(err, fs.ErrNotExist) {
			return "", err
		}
		current = parent
	}
}
