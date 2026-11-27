package bundle

import (
	"bytes"
	"fmt"
	"hash/fnv"
	"os"
	"strconv"
	"strings"

	"deepread/internal/markdown"

	"github.com/yuin/goldmark"
	"github.com/yuin/goldmark/ast"
	"github.com/yuin/goldmark/extension"
	extast "github.com/yuin/goldmark/extension/ast"
	"github.com/yuin/goldmark/text"
)

// Translatable block kinds. Each kind is a stable string shared with the
// translation layer schema and the export renderer.
const (
	BlockKindHeading   = "heading"
	BlockKindParagraph = "paragraph"
	BlockKindQuote     = "blockquote"
	BlockKindListItem  = "list_item"
	BlockKindTableCell = "table_cell"
	BlockKindImageAlt  = "image_alt"
)

// ExtractBlocks returns the deterministic, content-addressed translatable
// blocks of a document in reading order.
//
// The document is parsed with goldmark + GFM after inline reader notes are
// stripped, so inserting a `<!-- note ... -->` comment can never change a
// block's text, hash, or ID. Blocks are also anchored on their normalized
// prose text only, so inserting a synthetic H2 via Prepare changes section
// attribution but never invalidates an existing translation.
//
// StartByte/EndByte are offsets into the note-stripped document text (callers
// that need raw offsets must strip notes the same way).
func ExtractBlocks(docBytes []byte, manifest Manifest) []Block {
	stripped := markdown.StripNotes(string(docBytes))
	if strings.TrimSpace(stripped) == "" {
		return nil
	}
	src := []byte(stripped)
	w := &blockWalker{
		src:            src,
		manifest:       manifest,
		sectionByStart: map[int]markdown.Section{},
		blocks:         make([]Block, 0, 16),
	}
	for _, sec := range markdown.ExtractSections(stripped) {
		w.sectionByStart[sec.ByteStart()] = sec
	}

	md := goldmark.New(goldmark.WithExtensions(extension.GFM))
	doc := md.Parser().Parse(text.NewReader(src))
	w.walkChildren(doc)
	w.assignIDs()
	return w.blocks
}

// ExtractBlocksFromDoc reads docPath under the bundle's shared lock and returns
// its translatable blocks plus the manifest they were extracted against.
func ExtractBlocksFromDoc(docPath string) ([]Block, Manifest, error) {
	var blocks []Block
	var manifest Manifest
	err := WithDocRLock(docPath, func() error {
		docBytes, err := os.ReadFile(docPath)
		if err != nil {
			return err
		}
		loaded, _, err := LoadManifest(docPath, docBytes)
		if err != nil {
			return err
		}
		manifest = loaded
		blocks = ExtractBlocks(docBytes, loaded)
		return nil
	})
	if err != nil {
		return nil, Manifest{}, err
	}
	return blocks, manifest, nil
}

// BlockSourceHash returns the stable 8-hex fnv1a32 digest of normalized text.
func BlockSourceHash(normalizedText string) string {
	h := fnv.New32a()
	_, _ = h.Write([]byte(normalizedText))
	return fmt.Sprintf("%08x", h.Sum32())
}

// NormalizeBlockText collapses all whitespace runs so reflowing a paragraph
// (or stripping an inline note) never changes its content hash.
func NormalizeBlockText(s string) string {
	return strings.Join(strings.Fields(s), " ")
}

type blockWalker struct {
	src      []byte
	manifest Manifest

	sectionByStart map[int]markdown.Section
	curHeading     string
	curOccurrence  int
	curHasSection  bool

	blocks []Block
}

func (w *blockWalker) walkChildren(n ast.Node) {
	for child := n.FirstChild(); child != nil; child = child.NextSibling() {
		w.walk(child)
	}
}

func (w *blockWalker) walk(n ast.Node) {
	switch node := n.(type) {
	case *ast.Heading:
		w.handleHeading(node)
	case *ast.Blockquote:
		w.handleBlockquote(node)
	case *ast.ListItem:
		w.handleListItem(node)
	case *ast.List:
		w.walkChildren(node)
	case *ast.Paragraph:
		w.handleProse(node)
	case *ast.TextBlock:
		w.handleProse(node)
	case *extast.Table:
		w.handleTable(node)
	case *ast.Document:
		w.walkChildren(node)
	case *extast.TableHeader, *extast.TableRow:
		// Tables are handled as a whole by handleTable.
	case *ast.FencedCodeBlock, *ast.CodeBlock, *ast.HTMLBlock, *ast.ThematicBreak:
		// Not translatable prose.
	default:
		w.walkChildren(n)
	}
}

func (w *blockWalker) handleHeading(h *ast.Heading) {
	blockStart, blockEnd := w.span(h)
	// goldmark reports an ATX heading line as the heading text segment (after
	// the leading hashes), so anchor the section lookup on the line start that
	// markdown.ExtractSections records.
	sec, hasSec := w.sectionByStart[lineStartOffset(w.src, blockStart)]
	if hasSec {
		w.curHeading = sec.Heading
		w.curOccurrence = sec.Occurrence
		w.curHasSection = true
	}
	text := NormalizeBlockText(w.inlineText(h))
	if text == "" {
		return
	}
	if hasSec && w.manifest.IsSynthetic(sec.Heading, sec.Occurrence) {
		// Synthetic H2 breaks carry an optional translated heading in the
		// manifest; they are never block translation units.
		return
	}
	block := w.newBlock(BlockKindHeading, text)
	block.StartByte = blockStart
	block.EndByte = blockEnd
	if hasSec {
		block.SectionHeading = sec.Heading
		block.SectionOccurrence = sec.Occurrence
	}
	block.HeadingLevel = h.Level
	w.blocks = append(w.blocks, block)
}

func (w *blockWalker) handleProse(n ast.Node) {
	start, end := w.span(n)
	if img, ok := w.standaloneImage(n); ok {
		if alt := NormalizeBlockText(w.inlineText(img)); alt != "" {
			block := w.newBlock(BlockKindImageAlt, alt)
			block.StartByte = start
			block.EndByte = end
			w.blocks = append(w.blocks, block)
		}
		return
	}
	text := NormalizeBlockText(w.inlineText(n))
	if text == "" {
		return
	}
	block := w.newBlock(BlockKindParagraph, text)
	block.StartByte = start
	block.EndByte = end
	w.blocks = append(w.blocks, block)
}

// lineStartOffset returns the byte offset where the line containing offset starts.
func lineStartOffset(src []byte, offset int) int {
	if offset <= 0 {
		return 0
	}
	if offset > len(src) {
		offset = len(src)
	}
	if idx := bytes.LastIndexByte(src[:offset], '\n'); idx >= 0 {
		return idx + 1
	}
	return 0
}

// handleBlockquote emits one blockquote block per prose paragraph inside the
// quote (nested quotes included once) so inner paragraphs are never counted
// twice as plain paragraphs.
func (w *blockWalker) handleBlockquote(n ast.Node) {
	var visit func(ast.Node)
	visit = func(cur ast.Node) {
		for child := cur.FirstChild(); child != nil; child = child.NextSibling() {
			switch child.(type) {
			case *ast.Blockquote:
				visit(child)
			case *ast.Paragraph, *ast.TextBlock:
				text := NormalizeBlockText(w.inlineText(child))
				if text != "" {
					start, end := w.span(child)
					block := w.newBlock(BlockKindQuote, text)
					block.StartByte = start
					block.EndByte = end
					w.blocks = append(w.blocks, block)
				}
			case *ast.Heading:
				text := NormalizeBlockText(w.inlineText(child))
				if text != "" {
					start, end := w.span(child)
					block := w.newBlock(BlockKindQuote, text)
					block.StartByte = start
					block.EndByte = end
					w.blocks = append(w.blocks, block)
				}
			case *ast.List:
				visit(child)
			default:
				visit(child)
			}
		}
	}
	visit(n)
}

func (w *blockWalker) handleListItem(item *ast.ListItem) {
	var parts []string
	var nested []ast.Node
	for child := item.FirstChild(); child != nil; child = child.NextSibling() {
		switch child.(type) {
		case *ast.Paragraph, *ast.TextBlock:
			parts = append(parts, w.inlineText(child))
		case *ast.List, *ast.Blockquote:
			nested = append(nested, child)
		}
	}
	if text := NormalizeBlockText(strings.Join(parts, " ")); text != "" {
		start, end := w.span(item)
		block := w.newBlock(BlockKindListItem, text)
		block.StartByte = start
		block.EndByte = end
		w.blocks = append(w.blocks, block)
	}
	for _, n := range nested {
		w.walk(n)
	}
}

func (w *blockWalker) handleTable(n ast.Node) {
	_ = ast.Walk(n, func(cell ast.Node, entering bool) (ast.WalkStatus, error) {
		if !entering {
			return ast.WalkContinue, nil
		}
		c, ok := cell.(*extast.TableCell)
		if !ok {
			return ast.WalkContinue, nil
		}
		text := NormalizeBlockText(w.inlineText(c))
		if text == "" {
			return ast.WalkSkipChildren, nil
		}
		start, end := w.span(c)
		block := w.newBlock(BlockKindTableCell, text)
		block.StartByte = start
		block.EndByte = end
		w.blocks = append(w.blocks, block)
		return ast.WalkSkipChildren, nil
	})
}

func (w *blockWalker) newBlock(kind, text string) Block {
	return Block{
		Kind:              kind,
		Text:              text,
		SourceHash:        BlockSourceHash(text),
		SectionHeading:    w.curHeading,
		SectionOccurrence: w.curOccurrence,
	}
}

func (w *blockWalker) assignIDs() {
	seen := make(map[string]int, len(w.blocks))
	for i := range w.blocks {
		hash := w.blocks[i].SourceHash
		seen[hash]++
		if seen[hash] == 1 {
			w.blocks[i].ID = "b" + hash
			continue
		}
		w.blocks[i].ID = "b" + hash + "-" + strconv.Itoa(seen[hash])
	}
}

// span returns the byte range of a block node, falling back to its first and
// last positioned descendants for synthetic container nodes.
func (w *blockWalker) span(n ast.Node) (int, int) {
	if lines := n.Lines(); lines != nil && lines.Len() > 0 {
		return lines.At(0).Start, lines.At(lines.Len() - 1).Stop
	}
	start, end := -1, -1
	for child := n.FirstChild(); child != nil; child = child.NextSibling() {
		s, e := w.span(child)
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
	if start < 0 {
		return 0, 0
	}
	return start, end
}

// inlineText flattens inline Markdown into plain prose, keeping link labels,
// image alt text, and code span contents while dropping markup.
func (w *blockWalker) inlineText(n ast.Node) string {
	var b strings.Builder
	_ = ast.Walk(n, func(c ast.Node, entering bool) (ast.WalkStatus, error) {
		if !entering {
			return ast.WalkContinue, nil
		}
		switch t := c.(type) {
		case *ast.Text:
			seg := t.Segment
			if seg.Start >= 0 && seg.Stop <= len(w.src) && seg.Start <= seg.Stop {
				b.Write(seg.Value(w.src))
			}
		case *ast.String:
			b.Write(t.Value)
		case *ast.AutoLink:
			b.Write(t.Label(w.src))
		}
		return ast.WalkContinue, nil
	})
	return b.String()
}

// standaloneImage reports the single image child of a paragraph that carries
// nothing but that image.
func (w *blockWalker) standaloneImage(n ast.Node) (*ast.Image, bool) {
	var img *ast.Image
	for child := n.FirstChild(); child != nil; child = child.NextSibling() {
		switch c := child.(type) {
		case *ast.Image:
			if img != nil {
				return nil, false
			}
			img = c
		default:
			if strings.TrimSpace(w.inlineText(child)) != "" {
				return nil, false
			}
		}
	}
	return img, img != nil
}
