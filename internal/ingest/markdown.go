package ingest

import (
	"errors"
	"fmt"
	"io"
	"net/url"
	"os"
	"path"
	"path/filepath"
	"regexp"
	"strings"
	"unicode"

	"deepread/internal/bundle"
	"deepread/internal/markdown"

	"github.com/yuin/goldmark"
	"github.com/yuin/goldmark/ast"
	"github.com/yuin/goldmark/extension"
	"github.com/yuin/goldmark/parser"
	"github.com/yuin/goldmark/text"
)

var (
	inlineImagePattern = regexp.MustCompile(`!\[[^\]\n]*\]\(\s*(<[^>\n]+>|[^)\s]+)(?:\s+(?:"[^"\n]*"|'[^'\n]*'|\([^)\n]*\)))?\s*\)`)
	refDefPattern      = regexp.MustCompile(`^[ ]{0,3}\[([^\]]+)\]:[ \t]*(<[^>\n]+>|[^ \t\r\n]+)(?:[ \t]+.*)?$`)
)

type markdownImage struct {
	canonical string
	data      []byte
	name      string
}

func ingestMarkdown(srcPath, outDir string, opts Options) (Result, error) {
	raw, err := readBoundedFile(srcPath, opts.MaxFileBytes)
	if err != nil {
		return Result{}, err
	}
	absOutDir, err := filepath.Abs(outDir)
	if err != nil {
		return Result{}, err
	}

	// Refuse symlinked or non-empty output directories BEFORE parsing any
	// potentially corrupt manifest inside outDir (ensures exit 5 CONFLICT even
	// if outDir contains a corrupt .deepread/manifest.json).
	hadEmptyOutDir := false
	if st, statErr := os.Lstat(absOutDir); statErr == nil {
		if st.Mode()&os.ModeSymlink != 0 || !st.IsDir() {
			return Result{}, fmt.Errorf("%w: output path %q already exists and is not an empty directory", bundle.ErrDocMismatch, outDir)
		}
		entries, readErr := os.ReadDir(absOutDir)
		if readErr != nil {
			return Result{}, readErr
		}
		if len(entries) > 0 {
			return Result{}, fmt.Errorf("%w: output directory %q is not empty", bundle.ErrDocMismatch, outDir)
		}
		hadEmptyOutDir = true
	} else if !errors.Is(statErr, os.ErrNotExist) {
		return Result{}, statErr
	}

	rewritten, images, err := collectMarkdownImages(raw, srcPath, opts.MaxFileBytes)
	if err != nil {
		return Result{}, err
	}
	rewritten = []byte(StripDownloaderBoilerplate(string(rewritten)))

	parentDir := filepath.Dir(absOutDir)
	if err := os.MkdirAll(parentDir, 0o755); err != nil {
		return Result{}, err
	}
	stageDir, err := os.MkdirTemp(parentDir, ".deepread-md-stage-*")
	if err != nil {
		return Result{}, err
	}
	cleanupStage := true
	defer func() {
		if cleanupStage {
			_ = os.RemoveAll(stageDir)
		}
	}()

	stageDocPath := filepath.Join(stageDir, filepath.Base(srcPath))
	for _, image := range images {
		if err := bundle.WriteFileAtomic(filepath.Join(stageDir, "assets", image.name), image.data, 0o644); err != nil {
			return Result{}, fmt.Errorf("write image asset: %w", err)
		}
	}
	if err := bundle.WriteFileAtomic(stageDocPath, rewritten, 0o644); err != nil {
		return Result{}, fmt.Errorf("write Markdown document: %w", err)
	}
	manifest := bundle.Manifest{
		SchemaVersion: bundle.ManifestSchemaVersion,
		BundleID:      bundle.DefaultBundleID(stageDocPath, rewritten),
		DocID:         filepath.Base(srcPath),
		Revision:      0,
		SourceDigest:  bundle.SHA256Hex(rewritten),
		Reader:        opts.readerConfig(),
	}
	if err := bundle.SaveManifest(stageDocPath, manifest); err != nil {
		return Result{}, fmt.Errorf("save bundle manifest: %w", err)
	}

	if hadEmptyOutDir {
		if err := os.Remove(absOutDir); err != nil {
			return Result{}, fmt.Errorf("prepare empty output directory for atomic publish: %w", err)
		}
	}
	if err := os.Rename(stageDir, absOutDir); err != nil {
		if hadEmptyOutDir {
			_ = os.Mkdir(absOutDir, 0o755)
		}
		return Result{}, fmt.Errorf("publish Markdown bundle: %w", err)
	}
	cleanupStage = false

	return Result{
		Kind:       "markdown",
		Title:      markdownTitle(rewritten, filepath.Base(srcPath)),
		OutDir:     outDir,
		DocPath:    filepath.Base(srcPath),
		BundleID:   manifest.BundleID,
		ImageCount: len(images),
		Reader:     manifest.Reader,
	}, nil
}

func readBoundedFile(path string, maxBytes int64) ([]byte, error) {
	f, err := openRegularFile(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	data, err := io.ReadAll(io.LimitReader(f, maxBytes+1))
	if err != nil {
		return nil, err
	}
	if int64(len(data)) > maxBytes {
		return nil, fmt.Errorf("%w: %s exceeds %d bytes", ErrArchiveLimit, path, maxBytes)
	}
	return data, nil
}

func readBoundedRootFile(root *os.Root, relPath string, maxBytes int64) ([]byte, error) {
	f, err := openRootRegularFile(root, relPath)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	data, err := io.ReadAll(io.LimitReader(f, maxBytes+1))
	if err != nil {
		return nil, err
	}
	if int64(len(data)) > maxBytes {
		return nil, fmt.Errorf("%w: %s exceeds %d bytes", ErrArchiveLimit, relPath, maxBytes)
	}
	return data, nil
}

// collectMarkdownImages parses Markdown with goldmark so inline code spans and
// fenced code blocks are never touched, while both inline `![alt](path)` and
// reference-style `![alt][ref]` / `[ref]: path` local raster images are
// safely extracted via os.OpenRoot and rewritten to `assets/<name>`.
func collectMarkdownImages(raw []byte, srcPath string, maxFileBytes int64) ([]byte, []markdownImage, error) {
	md := goldmark.New(goldmark.WithExtensions(extension.GFM))
	pc := parser.NewContext()
	doc := md.Parser().Parse(text.NewReader(raw), parser.WithContext(pc))

	// Collect all real image destinations discovered by the Markdown parser.
	astDestinations := map[string]bool{}
	_ = ast.Walk(doc, func(n ast.Node, entering bool) (ast.WalkStatus, error) {
		if !entering {
			return ast.WalkContinue, nil
		}
		if img, ok := n.(*ast.Image); ok {
			dest := strings.TrimSpace(string(img.Destination))
			if dest != "" {
				astDestinations[dest] = true
			}
		}
		return ast.WalkContinue, nil
	})
	if len(astDestinations) == 0 {
		return raw, nil, nil
	}

	// Map normalized reference labels whose destination is actually used by an image.
	imageRefLabels := map[string]bool{}
	for _, ref := range pc.References() {
		if astDestinations[strings.TrimSpace(string(ref.Destination()))] {
			imageRefLabels[strings.ToLower(strings.TrimSpace(string(ref.Label())))] = true
		}
	}

	sourceDir, err := filepath.EvalSymlinks(filepath.Dir(srcPath))
	if err != nil {
		return nil, nil, fmt.Errorf("resolve Markdown source directory: %w", err)
	}
	sourceDir, err = filepath.Abs(sourceDir)
	if err != nil {
		return nil, nil, err
	}
	rootFS, err := os.OpenRoot(sourceDir)
	if err != nil {
		return nil, nil, fmt.Errorf("open Markdown source root: %w", err)
	}
	defer rootFS.Close()

	canonicalSrcPath := filepath.Join(sourceDir, filepath.Base(srcPath))
	protectedFiles := []string{
		bundle.ViewPath(canonicalSrcPath),
		bundle.PrevViewPath(bundle.ViewPath(canonicalSrcPath)),
	}

	imagesByPath := make(map[string]markdownImage)
	usedNames := make(map[string]bool)
	var images []markdownImage

	resolveAndRead := func(rawRef string) (string, bool, error) {
		ref := strings.TrimSpace(strings.TrimSuffix(strings.TrimPrefix(rawRef, "<"), ">"))
		lower := strings.ToLower(ref)
		if strings.HasPrefix(lower, "http://") || strings.HasPrefix(lower, "https://") || strings.HasPrefix(lower, "data:") {
			return "", false, nil
		}
		if cut := strings.IndexAny(ref, "?#"); cut >= 0 {
			ref = ref[:cut]
		}
		decoded, err := url.PathUnescape(ref)
		if err != nil || decoded == "" || strings.ContainsRune(decoded, '\x00') {
			return "", false, fmt.Errorf("%w: invalid local image path %q", ErrUnsafeArchive, rawRef)
		}
		decoded = strings.ReplaceAll(decoded, `\`, "/")
		if strings.HasPrefix(decoded, "/") || filepath.IsAbs(filepath.FromSlash(decoded)) {
			return "", false, fmt.Errorf("%w: invalid local image path %q", ErrUnsafeArchive, rawRef)
		}
		cleanRel := path.Clean(decoded)
		if cleanRel == "." || cleanRel == ".." || strings.HasPrefix(cleanRel, "../") {
			return "", false, fmt.Errorf("%w: image %q escapes the source directory", ErrUnsafeArchive, rawRef)
		}
		for _, seg := range strings.Split(cleanRel, "/") {
			if strings.EqualFold(seg, ".deepread") {
				return "", false, fmt.Errorf("%w: image %q reads protected .deepread metadata", ErrUnsafeArchive, rawRef)
			}
		}

		// Verify symlink resolution stays strictly inside sourceDir and is not
		// a protected sidecar file.
		candidate := filepath.Join(sourceDir, filepath.FromSlash(cleanRel))
		canonical, err := filepath.EvalSymlinks(candidate)
		if err != nil {
			return "", false, fmt.Errorf("%w: resolve image %q: %v", ErrUnsafeArchive, rawRef, err)
		}
		canonical, err = filepath.Abs(canonical)
		if err != nil {
			return "", false, err
		}
		if !pathStrictlyWithin(sourceDir, canonical) {
			return "", false, fmt.Errorf("%w: image %q escapes the source directory", ErrUnsafeArchive, rawRef)
		}
		for _, seg := range strings.Split(filepath.ToSlash(strings.TrimPrefix(canonical, sourceDir+string(filepath.Separator))), "/") {
			if strings.EqualFold(seg, ".deepread") {
				return "", false, fmt.Errorf("%w: image %q resolves inside protected .deepread metadata", ErrUnsafeArchive, rawRef)
			}
		}
		for _, p := range protectedFiles {
			if pCanon, pErr := filepath.EvalSymlinks(p); pErr == nil && strings.EqualFold(pCanon, canonical) {
				return "", false, fmt.Errorf("%w: image %q reads a protected sidecar", ErrUnsafeArchive, rawRef)
			} else if strings.EqualFold(filepath.Clean(p), canonical) {
				return "", false, fmt.Errorf("%w: image %q reads a protected sidecar", ErrUnsafeArchive, rawRef)
			}
		}

		relUnderRoot, err := filepath.Rel(sourceDir, canonical)
		if err != nil || strings.HasPrefix(relUnderRoot, "..") {
			return "", false, fmt.Errorf("%w: image %q escapes the source directory", ErrUnsafeArchive, rawRef)
		}

		img, ok := imagesByPath[canonical]
		if !ok {
			data, err := readBoundedRootFile(rootFS, relUnderRoot, maxFileBytes)
			if err != nil {
				return "", false, err
			}
			ext, safe := rasterImageExtension(data)
			if !safe {
				return "", false, fmt.Errorf("%w: image %q is not a supported raster image", ErrUnsafeArchive, rawRef)
			}
			name := uniqueAssetName(filepath.Base(canonical), ext, usedNames)
			img = markdownImage{canonical: canonical, data: data, name: name}
			imagesByPath[canonical] = img
			images = append(images, img)
		}
		return "assets/" + img.name, true, nil
	}

	// Compute document-wide inline code span ranges (including multi-line backtick
	// code spans) outside fenced code blocks so code examples are never rewritten.
	docStr := string(raw)
	codeRanges := documentCodeRanges(docStr)

	type replacement struct {
		start, end int
		value      string
	}
	var replacements []replacement
	inFence := false
	var fenceMark byte
	offset := 0
	for _, rawLine := range strings.SplitAfter(docStr, "\n") {
		plain := strings.TrimRight(rawLine, "\r\n")
		if inFence {
			if markdown.FenceClosed(plain, fenceMark) {
				inFence = false
			}
			offset += len(rawLine)
			continue
		}
		if ok, mark := markdown.IsFenceOpen(plain); ok {
			inFence = true
			fenceMark = mark
			offset += len(rawLine)
			continue
		}
		// 1. Check reference-style definition line `[label]: dest` used by an image.
		if !insideAnyRange(offset, codeRanges) {
			if m := refDefPattern.FindStringSubmatchIndex(plain); m != nil {
				label := strings.ToLower(strings.TrimSpace(plain[m[2]:m[3]]))
				if imageRefLabels[label] {
					destRaw := plain[m[4]:m[5]]
					rewrittenDest, changed, err := resolveAndRead(destRaw)
					if err != nil {
						return nil, nil, err
					}
					if changed {
						replacements = append(replacements, replacement{
							start: offset + m[4],
							end:   offset + m[5],
							value: rewrittenDest,
						})
					}
				}
				offset += len(rawLine)
				continue
			}
		}
		// 2. Check inline `![alt](dest)` occurrences outside all single/multi-line code spans.
		for _, m := range inlineImagePattern.FindAllStringSubmatchIndex(plain, -1) {
			absStart := offset + m[0]
			if insideAnyRange(absStart, codeRanges) {
				continue
			}
			destRaw := plain[m[2]:m[3]]
			rewrittenDest, changed, err := resolveAndRead(destRaw)
			if err != nil {
				return nil, nil, err
			}
			if changed {
				replacements = append(replacements, replacement{
					start: offset + m[2],
					end:   offset + m[3],
					value: rewrittenDest,
				})
			}
		}
		offset += len(rawLine)
	}

	if len(replacements) == 0 {
		return raw, images, nil
	}
	var out strings.Builder
	out.Grow(len(raw))
	last := 0
	for _, r := range replacements {
		out.Write(raw[last:r.start])
		out.WriteString(r.value)
		last = r.end
	}
	out.Write(raw[last:])
	return []byte(out.String()), images, nil
}

// documentCodeRanges returns byte ranges of all fenced code blocks and single-
// or multi-line CommonMark backtick code spans (bounded by paragraph blank lines).
func documentCodeRanges(doc string) [][2]int {
	var ranges [][2]int
	inFence := false
	var fenceMark byte
	fenceStart := 0
	offset := 0
	var nonFenceSegs [][2]int
	segStart := 0
	for _, rawLine := range strings.SplitAfter(doc, "\n") {
		plain := strings.TrimRight(rawLine, "\r\n")
		if inFence {
			if markdown.FenceClosed(plain, fenceMark) {
				ranges = append(ranges, [2]int{fenceStart, offset + len(rawLine)})
				inFence = false
				segStart = offset + len(rawLine)
			}
			offset += len(rawLine)
			continue
		}
		if ok, mark := markdown.IsFenceOpen(plain); ok {
			if offset > segStart {
				nonFenceSegs = append(nonFenceSegs, [2]int{segStart, offset})
			}
			inFence = true
			fenceMark = mark
			fenceStart = offset
		}
		offset += len(rawLine)
	}
	if inFence {
		ranges = append(ranges, [2]int{fenceStart, len(doc)})
	} else if len(doc) > segStart {
		nonFenceSegs = append(nonFenceSegs, [2]int{segStart, len(doc)})
	}

	// Within each non-fence segment, match single- and multi-line backtick spans
	// (stopping a search at blank-line paragraph breaks).
	for _, seg := range nonFenceSegs {
		s := doc[seg[0]:seg[1]]
		for i := 0; i < len(s); {
			// Outside a code span, CommonMark treats backslash before ASCII
			// punctuation (including \`) as an escaped literal character.
			if s[i] == '\\' && i+1 < len(s) && s[i+1] >= 0x21 && s[i+1] <= 0x7e {
				i += 2
				continue
			}
			if s[i] != '`' {
				i++
				continue
			}
			ticks := 0
			for i+ticks < len(s) && s[i+ticks] == '`' {
				ticks++
			}
			start := i
			j := i + ticks
			found := false
			for j < len(s) {
				if s[j] == '\n' && (j+1 < len(s) && (s[j+1] == '\n' || (s[j+1] == '\r' && j+2 < len(s) && s[j+2] == '\n'))) {
					break
				}
				if s[j] != '`' {
					j++
					continue
				}
				closeTicks := 0
				for j+closeTicks < len(s) && s[j+closeTicks] == '`' {
					closeTicks++
				}
				if closeTicks == ticks {
					ranges = append(ranges, [2]int{seg[0] + start, seg[0] + j + closeTicks})
					i = j + closeTicks
					found = true
					break
				}
				j += closeTicks
			}
			if !found {
				i += ticks
			}
		}
	}
	return ranges
}

func insideAnyRange(pos int, ranges [][2]int) bool {
	for _, r := range ranges {
		if pos >= r[0] && pos < r[1] {
			return true
		}
	}
	return false
}

func pathStrictlyWithin(dir, path string) bool {
	rel, err := filepath.Rel(dir, path)
	if err != nil || rel == "." || filepath.IsAbs(rel) {
		return false
	}
	return rel != ".." && !strings.HasPrefix(rel, ".."+string(filepath.Separator))
}

func uniqueAssetName(original, ext string, used map[string]bool) string {
	base := safeAssetName(original, ext)
	name := base
	for i := 2; used[strings.ToLower(name)]; i++ {
		stem := strings.TrimSuffix(base, filepath.Ext(base))
		name = fmt.Sprintf("%s-%d%s", stem, i, filepath.Ext(base))
	}
	used[strings.ToLower(name)] = true
	return name
}

func safeAssetName(original, ext string) string {
	stem := strings.TrimSuffix(filepath.Base(original), filepath.Ext(original))
	stem = strings.Map(func(r rune) rune {
		switch {
		case unicode.IsLetter(r), unicode.IsDigit(r), r == '-', r == '_':
			return r
		default:
			return '-'
		}
	}, stem)
	stem = strings.Trim(stem, "-_")
	if stem == "" {
		stem = "image"
	}
	runes := []rune(stem)
	if len(runes) > 80 {
		stem = string(runes[:80])
	}
	return stem + ext
}

func markdownTitle(raw []byte, fallback string) string {
	for _, line := range strings.Split(strings.ReplaceAll(string(raw), "\r\n", "\n"), "\n") {
		trimmed := strings.TrimSpace(line)
		if strings.HasPrefix(trimmed, "# ") {
			if title := strings.TrimSpace(strings.TrimPrefix(trimmed, "# ")); title != "" {
				return strings.TrimSpace(strings.TrimRight(title, "#"))
			}
		}
	}
	return strings.TrimSuffix(fallback, filepath.Ext(fallback))
}
