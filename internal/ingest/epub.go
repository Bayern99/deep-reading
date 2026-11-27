package ingest

import (
	"archive/zip"
	"encoding/json"
	"encoding/xml"
	"errors"
	"fmt"
	"io"
	"net/url"
	"os"
	"path"
	"path/filepath"
	"strings"
	"unicode"

	"deepread/internal/bundle"
	"golang.org/x/net/html"
)

type zipArchive struct {
	files    map[string]*zip.File
	maxFile  int64
	maxTotal int64
	total    int64
}

type opfDocument struct {
	Metadata struct {
		Titles   []string `xml:"title"`
		Creators []string `xml:"creator"`
	} `xml:"metadata"`
	Manifest []struct {
		ID         string `xml:"id,attr"`
		Href       string `xml:"href,attr"`
		MediaType  string `xml:"media-type,attr"`
		Properties string `xml:"properties,attr"`
	} `xml:"manifest>item"`
	Spine struct {
		TOC      string `xml:"toc,attr"`
		Itemrefs []struct {
			IDRef  string `xml:"idref,attr"`
			Linear string `xml:"linear,attr"`
		} `xml:"itemref"`
	} `xml:"spine"`
}

type manifestItem struct {
	ID         string
	ZipPath    string
	MediaType  string
	Properties string
}

type chapterDraft struct {
	info     ChapterInfo
	markdown []byte
	images   []markdownImage
	manifest bundle.Manifest
	docPath  string
}

func ingestEPUB(srcPath, outDir string, opts Options) (Result, error) {
	reader, err := zip.OpenReader(srcPath)
	if err != nil {
		return Result{}, fmt.Errorf("open EPUB: %w", err)
	}
	defer reader.Close()
	if len(reader.File) > opts.MaxEntries {
		return Result{}, fmt.Errorf("%w: %d entries exceeds %d", ErrArchiveLimit, len(reader.File), opts.MaxEntries)
	}
	archive := &zipArchive{
		files:    make(map[string]*zip.File, len(reader.File)),
		maxFile:  opts.MaxFileBytes,
		maxTotal: opts.MaxTotalBytes,
	}
	for _, file := range reader.File {
		if err := validateZipEntryPath(file.Name); err != nil {
			return Result{}, err
		}
		clean := path.Clean(file.Name)
		if _, duplicate := archive.files[clean]; duplicate && !file.FileInfo().IsDir() {
			return Result{}, fmt.Errorf("%w: duplicate ZIP entry %q", ErrUnsafeArchive, clean)
		}
		archive.files[clean] = file
	}

	containerData, err := archive.read("META-INF/container.xml")
	if err != nil {
		return Result{}, fmt.Errorf("read EPUB container: %w", err)
	}
	var container struct {
		Rootfiles []struct {
			FullPath string `xml:"full-path,attr"`
		} `xml:"rootfiles>rootfile"`
	}
	if err := xml.Unmarshal(containerData, &container); err != nil {
		return Result{}, fmt.Errorf("parse EPUB container: %w", err)
	}
	if len(container.Rootfiles) == 0 || strings.TrimSpace(container.Rootfiles[0].FullPath) == "" {
		return Result{}, fmt.Errorf("EPUB container has no package rootfile")
	}
	opfPath, err := resolveZipReference("", container.Rootfiles[0].FullPath)
	if err != nil {
		return Result{}, err
	}
	opfData, err := archive.read(opfPath)
	if err != nil {
		return Result{}, fmt.Errorf("read EPUB package: %w", err)
	}
	var opf opfDocument
	if err := xml.Unmarshal(opfData, &opf); err != nil {
		return Result{}, fmt.Errorf("parse EPUB package: %w", err)
	}

	opfDir := path.Dir(opfPath)
	manifest := make(map[string]manifestItem, len(opf.Manifest))
	for _, item := range opf.Manifest {
		resolved, err := resolveZipReference(opfDir, item.Href)
		if err != nil {
			return Result{}, fmt.Errorf("manifest item %q: %w", item.ID, err)
		}
		manifest[item.ID] = manifestItem{ID: item.ID, ZipPath: resolved, MediaType: item.MediaType, Properties: item.Properties}
	}
	tocTitles, err := epubTOCTitles(archive, manifest, opf.Spine.TOC)
	if err != nil {
		return Result{}, err
	}

	var drafts []chapterDraft
	for _, itemref := range opf.Spine.Itemrefs {
		if strings.EqualFold(strings.TrimSpace(itemref.Linear), "no") {
			continue
		}
		item, ok := manifest[itemref.IDRef]
		if !ok {
			return Result{}, fmt.Errorf("EPUB spine references unknown manifest item %q", itemref.IDRef)
		}
		if hasProperty(item.Properties, "nav") {
			continue
		}
		mediaType := strings.ToLower(strings.TrimSpace(item.MediaType))
		if mediaType != "application/xhtml+xml" && mediaType != "text/html" {
			continue
		}
		chapterHTML, err := archive.read(item.ZipPath)
		if err != nil {
			return Result{}, fmt.Errorf("read spine item %q: %w", item.ID, err)
		}

		usedNames := make(map[string]bool)
		imagesByPath := make(map[string]markdownImage)
		var images []markdownImage
		resolveImage := func(src, alt string) (string, error) {
			lower := strings.ToLower(strings.TrimSpace(src))
			if strings.HasPrefix(lower, "http://") || strings.HasPrefix(lower, "https://") || strings.HasPrefix(lower, "data:") {
				return "", nil
			}
			imagePath, err := resolveZipReference(path.Dir(item.ZipPath), src)
			if err != nil {
				return "", err
			}
			if image, ok := imagesByPath[imagePath]; ok {
				return "assets/" + image.name, nil
			}
			data, err := archive.read(imagePath)
			if err != nil {
				return "", fmt.Errorf("read chapter image %q: %w", src, err)
			}
			ext, safe := rasterImageExtension(data)
			if !safe {
				return "", fmt.Errorf("%w: chapter image %q is not a supported raster image", ErrUnsafeArchive, src)
			}
			name := uniqueAssetName(path.Base(imagePath), ext, usedNames)
			image := markdownImage{canonical: imagePath, data: data, name: name}
			imagesByPath[imagePath] = image
			images = append(images, image)
			return "assets/" + name, nil
		}
		converted, err := convertHTMLToMarkdown(chapterHTML, resolveImage)
		if err != nil {
			return Result{}, fmt.Errorf("convert spine item %q: %w", item.ID, err)
		}
		title := cleanInline(tocTitles[item.ZipPath])
		if title == "" {
			title = converted.FirstHeading
		}
		if title == "" {
			title = converted.DocumentTitle
		}
		if title == "" {
			title = fmt.Sprintf("Chapter %d", len(drafts)+1)
		}
		markdown := ensureChapterTitle(StripDownloaderBoilerplate(converted.Markdown), title)
		drafts = append(drafts, chapterDraft{
			info: ChapterInfo{
				Title:      title,
				WordCount:  converted.WordCount,
				ImageCount: len(images),
			},
			markdown: []byte(markdown),
			images:   images,
		})
	}
	if len(drafts) == 0 {
		return Result{}, fmt.Errorf("EPUB contains no readable HTML chapters")
	}
	if len(drafts) > 1 {
		kept := drafts[:0]
		for _, draft := range drafts {
			if draft.info.WordCount >= 8 {
				kept = append(kept, draft)
			}
		}
		if len(kept) > 0 {
			drafts = kept
		} else {
			drafts = drafts[:1]
		}
	}

	usedBundleIDs := make(map[string]bool)
	for i := range drafts {
		draft := &drafts[i]
		index := i + 1
		slug := chapterSlug(draft.info.Title)
		relDocPath := path.Join("chapters", fmt.Sprintf("%02d-%s", index, slug), "chapter.md")
		docPath := filepath.Join(outDir, filepath.FromSlash(relDocPath))
		manifest, _, err := bundle.LoadManifest(docPath, draft.markdown)
		if err != nil {
			return Result{}, err
		}
		if manifest.BundleID == "" || usedBundleIDs[manifest.BundleID] {
			base := bundle.DefaultBundleID(docPath, draft.markdown)
			manifest.BundleID = fmt.Sprintf("%s-%02d", base, index)
			for suffix := 2; usedBundleIDs[manifest.BundleID]; suffix++ {
				manifest.BundleID = fmt.Sprintf("%s-%02d-%d", base, index, suffix)
			}
		}
		usedBundleIDs[manifest.BundleID] = true
		manifest.Reader = opts.readerConfig()
		draft.manifest = manifest
		draft.docPath = docPath
		draft.info.Index = index
		draft.info.Slug = slug
		draft.info.BundleID = manifest.BundleID
		draft.info.DocPath = relDocPath
	}

	absOutDir, err := filepath.Abs(outDir)
	if err != nil {
		return Result{}, err
	}
	// Refuse to overwrite a non-empty output directory or symlinked target before
	// writing a single byte.
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

	parentDir := filepath.Dir(absOutDir)
	if err := os.MkdirAll(parentDir, 0o755); err != nil {
		return Result{}, err
	}
	stageDir, err := os.MkdirTemp(parentDir, ".deepread-epub-stage-*")
	if err != nil {
		return Result{}, err
	}
	cleanupStage := true
	defer func() {
		if cleanupStage {
			_ = os.RemoveAll(stageDir)
		}
	}()

	result := Result{
		Kind:      "epub",
		Title:     firstNonEmpty(opf.Metadata.Titles),
		Author:    firstNonEmpty(opf.Metadata.Creators),
		OutDir:    outDir,
		IndexPath: "index.md",
		BookJSON:  "book.json",
		Chapters:  make([]ChapterInfo, 0, len(drafts)),
		Reader:    opts.readerConfig(),
	}
	if result.Title == "" {
		result.Title = strings.TrimSuffix(filepath.Base(srcPath), filepath.Ext(srcPath))
	}
	for _, draft := range drafts {
		stageDocPath := filepath.Join(stageDir, filepath.FromSlash(draft.info.DocPath))
		for _, image := range draft.images {
			assetPath := filepath.Join(filepath.Dir(stageDocPath), "assets", image.name)
			if err := bundle.WriteFileAtomic(assetPath, image.data, 0o644); err != nil {
				return Result{}, fmt.Errorf("write chapter image: %w", err)
			}
		}
		if err := bundle.WriteFileAtomic(stageDocPath, draft.markdown, 0o644); err != nil {
			return Result{}, fmt.Errorf("write chapter: %w", err)
		}
		draft.manifest.SourceDigest = bundle.SHA256Hex(draft.markdown)
		if err := bundle.SaveManifest(stageDocPath, draft.manifest); err != nil {
			return Result{}, fmt.Errorf("save chapter manifest: %w", err)
		}
		result.ImageCount += draft.info.ImageCount
		result.Chapters = append(result.Chapters, draft.info)
	}

	index := buildBookIndex(result)
	if err := bundle.WriteFileAtomic(filepath.Join(stageDir, "index.md"), []byte(index), 0o644); err != nil {
		return Result{}, fmt.Errorf("write book index: %w", err)
	}
	bookJSON, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		return Result{}, err
	}
	if err := bundle.WriteFileAtomic(filepath.Join(stageDir, "book.json"), append(bookJSON, '\n'), 0o644); err != nil {
		return Result{}, fmt.Errorf("write book manifest: %w", err)
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
		return Result{}, fmt.Errorf("publish EPUB bundle: %w", err)
	}
	cleanupStage = false
	return result, nil
}

func (a *zipArchive) read(name string) ([]byte, error) {
	if err := validateZipEntryPath(name); err != nil {
		return nil, err
	}
	file, ok := a.files[path.Clean(name)]
	if !ok {
		return nil, fmt.Errorf("ZIP entry %q not found", name)
	}
	if file.FileInfo().IsDir() {
		return nil, fmt.Errorf("ZIP entry %q is a directory", name)
	}
	remaining := a.maxTotal - a.total
	if remaining < 0 {
		return nil, fmt.Errorf("%w: cumulative EPUB data exceeds %d bytes", ErrArchiveLimit, a.maxTotal)
	}
	limit := a.maxFile
	if remaining < limit {
		limit = remaining
	}
	rc, err := file.Open()
	if err != nil {
		return nil, err
	}
	defer rc.Close()
	data, readErr := io.ReadAll(io.LimitReader(rc, limit+1))
	a.total += int64(len(data))
	if readErr != nil {
		return nil, readErr
	}
	if int64(len(data)) > limit {
		if a.maxFile <= remaining {
			return nil, fmt.Errorf("%w: ZIP entry %q exceeds %d bytes", ErrArchiveLimit, name, a.maxFile)
		}
		return nil, fmt.Errorf("%w: cumulative EPUB data exceeds %d bytes", ErrArchiveLimit, a.maxTotal)
	}
	return data, nil
}

func validateZipEntryPath(name string) error {
	if name == "" || strings.ContainsRune(name, '\x00') || strings.Contains(name, "\\") || strings.HasPrefix(name, "/") || path.IsAbs(name) {
		return fmt.Errorf("%w: invalid ZIP path %q", ErrUnsafeArchive, name)
	}
	if len(name) >= 2 && ((name[0] >= 'A' && name[0] <= 'Z') || (name[0] >= 'a' && name[0] <= 'z')) && name[1] == ':' {
		return fmt.Errorf("%w: absolute ZIP path %q", ErrUnsafeArchive, name)
	}
	for _, segment := range strings.Split(name, "/") {
		if segment == ".." {
			return fmt.Errorf("%w: parent path segment in %q", ErrUnsafeArchive, name)
		}
	}
	return nil
}

func resolveZipReference(baseDir, reference string) (string, error) {
	reference = strings.TrimSpace(reference)
	if reference == "" || strings.ContainsRune(reference, '\x00') || strings.Contains(reference, "\\") {
		return "", fmt.Errorf("%w: invalid archive reference %q", ErrUnsafeArchive, reference)
	}
	u, err := url.Parse(reference)
	if err != nil || u.IsAbs() || u.Host != "" || strings.HasPrefix(reference, "//") || strings.HasPrefix(u.Path, "/") {
		return "", fmt.Errorf("%w: external or absolute archive reference %q", ErrUnsafeArchive, reference)
	}
	// url.Parse already percent-decodes u.Path once; do not call PathUnescape a
	// second time or literal '%' characters (e.g. %25) would be double-decoded.
	referencePath := u.Path
	resolved := path.Clean(path.Join(baseDir, referencePath))
	if resolved == "." || resolved == ".." || strings.HasPrefix(resolved, "../") {
		return "", fmt.Errorf("%w: archive reference %q escapes the ZIP root", ErrUnsafeArchive, reference)
	}
	if err := validateZipEntryPath(resolved); err != nil {
		return "", err
	}
	return resolved, nil
}

func epubTOCTitles(archive *zipArchive, manifest map[string]manifestItem, spineTOC string) (map[string]string, error) {
	for _, item := range manifest {
		if hasProperty(item.Properties, "nav") {
			data, err := archive.read(item.ZipPath)
			if err != nil {
				return nil, fmt.Errorf("read EPUB navigation document: %w", err)
			}
			return parseNavTitles(data, path.Dir(item.ZipPath))
		}
	}
	var ncx *manifestItem
	if item, ok := manifest[spineTOC]; ok && strings.EqualFold(item.MediaType, "application/x-dtbncx+xml") {
		copy := item
		ncx = &copy
	} else {
		for _, item := range manifest {
			if strings.EqualFold(item.MediaType, "application/x-dtbncx+xml") {
				copy := item
				ncx = &copy
				break
			}
		}
	}
	if ncx == nil {
		return map[string]string{}, nil
	}
	if _, ok := archive.files[ncx.ZipPath]; !ok {
		// Some EPUB 2 producers leave a stale toc attribute; chapters remain usable.
		return map[string]string{}, nil
	}
	data, err := archive.read(ncx.ZipPath)
	if err != nil {
		return nil, fmt.Errorf("read EPUB NCX: %w", err)
	}
	return parseNCXTitles(data, path.Dir(ncx.ZipPath))
}

func parseNavTitles(data []byte, baseDir string) (map[string]string, error) {
	doc, err := html.Parse(strings.NewReader(string(data)))
	if err != nil {
		return nil, fmt.Errorf("parse EPUB navigation: %w", err)
	}
	var toc *html.Node
	var findTOC func(*html.Node)
	findTOC = func(n *html.Node) {
		if toc != nil {
			return
		}
		if n.Type == html.ElementNode && strings.EqualFold(n.Data, "nav") {
			navType := ""
			for _, attr := range n.Attr {
				if strings.EqualFold(attr.Key, "type") || strings.EqualFold(attr.Key, "epub:type") {
					navType = attr.Val
					break
				}
			}
			if hasProperty(navType, "toc") {
				toc = n
				return
			}
		}
		for child := n.FirstChild; child != nil; child = child.NextSibling {
			findTOC(child)
		}
	}
	findTOC(doc)
	titles := make(map[string]string)
	if toc == nil {
		return titles, nil
	}
	var addLinks func(*html.Node) error
	addLinks = func(n *html.Node) error {
		if n.Type == html.ElementNode && strings.EqualFold(n.Data, "a") {
			title := cleanInline(nodeText(n))
			href := attribute(n, "href")
			if title != "" && href != "" {
				resolved, err := resolveZipReference(baseDir, href)
				if err != nil {
					return err
				}
				if titles[resolved] == "" {
					titles[resolved] = title
				}
			}
		}
		for child := n.FirstChild; child != nil; child = child.NextSibling {
			if err := addLinks(child); err != nil {
				return err
			}
		}
		return nil
	}
	if err := addLinks(toc); err != nil {
		return nil, err
	}
	return titles, nil
}

func parseNCXTitles(data []byte, baseDir string) (map[string]string, error) {
	type navPoint struct {
		Label   string `xml:"navLabel>text"`
		Content struct {
			Src string `xml:"src,attr"`
		} `xml:"content"`
		Children []navPoint `xml:"navPoint"`
	}
	var ncx struct {
		NavMap struct {
			Points []navPoint `xml:"navPoint"`
		} `xml:"navMap"`
	}
	if err := xml.Unmarshal(data, &ncx); err != nil {
		return nil, fmt.Errorf("parse EPUB NCX: %w", err)
	}
	titles := make(map[string]string)
	var addPoints func([]navPoint) error
	addPoints = func(points []navPoint) error {
		for _, point := range points {
			title := cleanInline(point.Label)
			if title != "" && point.Content.Src != "" {
				resolved, err := resolveZipReference(baseDir, point.Content.Src)
				if err != nil {
					return err
				}
				if titles[resolved] == "" {
					titles[resolved] = title
				}
			}
			if err := addPoints(point.Children); err != nil {
				return err
			}
		}
		return nil
	}
	if err := addPoints(ncx.NavMap.Points); err != nil {
		return nil, err
	}
	return titles, nil
}

func hasProperty(properties, wanted string) bool {
	for _, property := range strings.Fields(properties) {
		if strings.EqualFold(property, wanted) {
			return true
		}
	}
	return false
}

func firstNonEmpty(values []string) string {
	for _, value := range values {
		if value = cleanInline(value); value != "" {
			return value
		}
	}
	return ""
}

func ensureChapterTitle(markdown, title string) string {
	title = cleanInline(title)
	lines := strings.Split(markdown, "\n")
	for i, line := range lines {
		if strings.HasPrefix(line, "# ") {
			lines[i] = "# " + title
			return cleanConvertedMarkdown(strings.Join(lines, "\n"))
		}
	}
	if markdown == "" {
		return "# " + title + "\n"
	}
	return "# " + title + "\n\n" + markdown
}

func plainWordCount(text string) int {
	count := 0
	for _, field := range strings.Fields(text) {
		if strings.IndexFunc(field, unicode.IsLetter) >= 0 || strings.IndexFunc(field, unicode.IsDigit) >= 0 {
			count++
		}
	}
	return count
}

func chapterSlug(title string) string {
	var out strings.Builder
	lastDash := true
	for _, r := range strings.ToLower(title) {
		if unicode.IsLetter(r) || unicode.IsDigit(r) {
			out.WriteRune(r)
			lastDash = false
		} else if !lastDash {
			out.WriteByte('-')
			lastDash = true
		}
	}
	slug := strings.Trim(out.String(), "-")
	if slug == "" {
		slug = "chapter"
	}
	runes := []rune(slug)
	if len(runes) > 64 {
		slug = string(runes[:64])
	}
	return slug
}

func buildBookIndex(result Result) string {
	var out strings.Builder
	out.WriteString("# " + result.Title + "\n\n")
	if result.Author != "" {
		out.WriteString("Author: " + result.Author + "\n\n")
	}
	out.WriteString("| # | Title | Words | Images | Path |\n")
	out.WriteString("| ---: | --- | ---: | ---: | --- |\n")
	for _, chapter := range result.Chapters {
		title := strings.ReplaceAll(chapter.Title, "|", "\\|")
		fmt.Fprintf(&out, "| %d | %s | %d | %d | [%s](%s) |\n", chapter.Index, title, chapter.WordCount, chapter.ImageCount, chapter.DocPath, chapter.DocPath)
	}
	return out.String()
}
