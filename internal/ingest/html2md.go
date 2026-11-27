package ingest

import (
	"bytes"
	"fmt"
	"net/url"
	"strconv"
	"strings"

	"golang.org/x/net/html"
)

type chapterImageResolver func(src, alt string) (string, error)

type htmlConversion struct {
	Markdown      string
	FirstHeading  string
	DocumentTitle string
	WordCount     int
}

type htmlRenderer struct {
	resolveImage chapterImageResolver
	firstHeading string
}

func convertHTMLToMarkdown(data []byte, resolve chapterImageResolver) (htmlConversion, error) {
	doc, err := html.Parse(bytes.NewReader(data))
	if err != nil {
		return htmlConversion{}, fmt.Errorf("parse XHTML: %w", err)
	}
	r := &htmlRenderer{resolveImage: resolve}
	body, err := r.renderBlockChildren(doc, 0)
	if err != nil {
		return htmlConversion{}, err
	}
	return htmlConversion{
		Markdown:      cleanConvertedMarkdown(body),
		FirstHeading:  r.firstHeading,
		DocumentTitle: cleanInline(findElementText(doc, "title")),
		WordCount:     plainWordCount(visibleProseText(doc)),
	}, nil
}

func (r *htmlRenderer) renderBlockChildren(parent *html.Node, depth int) (string, error) {
	var out strings.Builder
	for child := parent.FirstChild; child != nil; child = child.NextSibling {
		part, err := r.renderBlock(child, depth)
		if err != nil {
			return "", err
		}
		out.WriteString(part)
	}
	return out.String(), nil
}

func (r *htmlRenderer) renderBlock(n *html.Node, depth int) (string, error) {
	if n.Type == html.TextNode {
		return escapeInlineMarkdownText(n.Data), nil
	}
	if n.Type != html.ElementNode {
		return "", nil
	}
	switch strings.ToLower(n.Data) {
	case "script", "style", "noscript", "svg", "head", "nav":
		return "", nil
	case "h1", "h2", "h3", "h4", "h5", "h6":
		level, _ := strconv.Atoi(strings.TrimPrefix(strings.ToLower(n.Data), "h"))
		text, err := r.renderInlineChildren(n)
		if err != nil {
			return "", err
		}
		text = cleanInline(text)
		if text == "" {
			return "", nil
		}
		if r.firstHeading == "" {
			r.firstHeading = text
		}
		return strings.Repeat("#", level) + " " + text + "\n\n", nil
	case "p":
		text, err := r.renderInlineChildren(n)
		if err != nil {
			return "", err
		}
		text = cleanInline(text)
		if text == "" {
			return "", nil
		}
		return text + "\n\n", nil
	case "blockquote":
		body, err := r.renderBlockChildren(n, depth)
		if err != nil {
			return "", err
		}
		body = strings.TrimSpace(body)
		if body == "" {
			return "", nil
		}
		lines := strings.Split(body, "\n")
		for i, line := range lines {
			if strings.TrimSpace(line) == "" {
				lines[i] = ">"
			} else {
				lines[i] = "> " + line
			}
		}
		return strings.Join(lines, "\n") + "\n\n", nil
	case "ul", "ol":
		return r.renderList(n, depth)
	case "pre":
		text := strings.ReplaceAll(nodeText(n), "\r\n", "\n")
		text = strings.Trim(text, "\n")
		if strings.TrimSpace(text) == "" {
			return "", nil
		}
		fence := "```"
		if strings.Contains(text, "```") {
			fence = "~~~"
		}
		return fence + "\n" + text + "\n" + fence + "\n\n", nil
	case "table":
		return r.renderTable(n)
	case "hr":
		return "---\n\n", nil
	case "br":
		return "  \n", nil
	case "img", "image":
		return r.renderImage(n)
	case "html", "body", "main", "article", "section", "div", "header", "footer", "aside", "figure", "figcaption", "thead", "tbody", "tfoot":
		return r.renderBlockChildren(n, depth)
	default:
		return r.renderInline(n)
	}
}

func (r *htmlRenderer) renderInlineChildren(parent *html.Node) (string, error) {
	var out strings.Builder
	for child := parent.FirstChild; child != nil; child = child.NextSibling {
		part, err := r.renderInline(child)
		if err != nil {
			return "", err
		}
		out.WriteString(part)
	}
	return out.String(), nil
}

func (r *htmlRenderer) renderInline(n *html.Node) (string, error) {
	if n.Type == html.TextNode {
		return escapeInlineMarkdownText(n.Data), nil
	}
	if n.Type != html.ElementNode {
		return "", nil
	}
	switch strings.ToLower(n.Data) {
	case "script", "style", "noscript", "svg", "head", "nav":
		return "", nil
	case "em", "i":
		text, err := r.renderInlineChildren(n)
		if err != nil {
			return "", err
		}
		if strings.TrimSpace(text) == "" {
			return text, nil
		}
		return "*" + strings.TrimSpace(text) + "*", nil
	case "strong", "b":
		text, err := r.renderInlineChildren(n)
		if err != nil {
			return "", err
		}
		if strings.TrimSpace(text) == "" {
			return text, nil
		}
		return "**" + strings.TrimSpace(text) + "**", nil
	case "code":
		text := nodeText(n)
		if text == "" {
			return "", nil
		}
		if strings.Contains(text, "`") {
			return "`` " + text + " ``", nil
		}
		return "`" + text + "`", nil
	case "a":
		text, err := r.renderInlineChildren(n)
		if err != nil {
			return "", err
		}
		text = cleanInline(text)
		href := strings.TrimSpace(attribute(n, "href"))
		if !safeExternalLink(href) {
			return text, nil
		}
		if text == "" {
			text = href
		}
		return "[" + strings.ReplaceAll(text, "]", "\\]") + "](" + href + ")", nil
	case "img", "image":
		return r.renderImage(n)
	case "br":
		return "  \n", nil
	case "hr":
		return "\n---\n", nil
	default:
		return r.renderInlineChildren(n)
	}
}

func (r *htmlRenderer) renderImage(n *html.Node) (string, error) {
	src := attribute(n, "src")
	if src == "" {
		src = attribute(n, "href")
	}
	if src == "" {
		src = attribute(n, "xlink:href")
	}
	alt := cleanInline(attribute(n, "alt"))
	if src == "" || r.resolveImage == nil {
		return alt, nil
	}
	ref, err := r.resolveImage(strings.TrimSpace(src), alt)
	if err != nil {
		return "", err
	}
	if ref == "" {
		return alt, nil
	}
	return "![" + strings.ReplaceAll(alt, "]", "\\]") + "](" + ref + ")", nil
}

func (r *htmlRenderer) renderList(n *html.Node, depth int) (string, error) {
	ordered := strings.EqualFold(n.Data, "ol")
	number := 1
	if start, err := strconv.Atoi(attribute(n, "start")); err == nil && start > 0 {
		number = start
	}
	var out strings.Builder
	for child := n.FirstChild; child != nil; child = child.NextSibling {
		if child.Type != html.ElementNode || !strings.EqualFold(child.Data, "li") {
			continue
		}
		var ordinary, nested strings.Builder
		for part := child.FirstChild; part != nil; part = part.NextSibling {
			if part.Type == html.ElementNode && (strings.EqualFold(part.Data, "ul") || strings.EqualFold(part.Data, "ol")) {
				text, err := r.renderList(part, depth+1)
				if err != nil {
					return "", err
				}
				nested.WriteString(text)
				continue
			}
			text, err := r.renderBlock(part, depth)
			if err != nil {
				return "", err
			}
			ordinary.WriteString(text)
		}
		indent := strings.Repeat("  ", depth)
		marker := "- "
		if ordered {
			marker = strconv.Itoa(number) + ". "
			number++
		}
		text := strings.TrimSpace(ordinary.String())
		if text == "" {
			out.WriteString(indent + marker + "\n")
		} else {
			lines := strings.Split(text, "\n")
			out.WriteString(indent + marker + lines[0] + "\n")
			for _, line := range lines[1:] {
				if strings.TrimSpace(line) != "" {
					out.WriteString(indent + "  " + line + "\n")
				}
			}
		}
		out.WriteString(nested.String())
	}
	if out.Len() > 0 {
		out.WriteString("\n")
	}
	return out.String(), nil
}

func (r *htmlRenderer) renderTable(n *html.Node) (string, error) {
	var rows [][]string
	var walk func(*html.Node) error
	walk = func(node *html.Node) error {
		for child := node.FirstChild; child != nil; child = child.NextSibling {
			if child.Type != html.ElementNode {
				continue
			}
			if strings.EqualFold(child.Data, "table") {
				continue
			}
			if strings.EqualFold(child.Data, "tr") {
				var row []string
				for cell := child.FirstChild; cell != nil; cell = cell.NextSibling {
					if cell.Type == html.ElementNode && (strings.EqualFold(cell.Data, "td") || strings.EqualFold(cell.Data, "th")) {
						text, err := r.renderInlineChildren(cell)
						if err != nil {
							return err
						}
						text = strings.ReplaceAll(cleanInline(text), "|", "\\|")
						row = append(row, text)
					}
				}
				if len(row) > 0 {
					rows = append(rows, row)
				}
				continue
			}
			if err := walk(child); err != nil {
				return err
			}
		}
		return nil
	}
	if err := walk(n); err != nil {
		return "", err
	}
	if len(rows) == 0 {
		return "", nil
	}
	columns := 0
	for _, row := range rows {
		if len(row) > columns {
			columns = len(row)
		}
	}
	var out strings.Builder
	writeRow := func(row []string) {
		out.WriteString("|")
		for i := 0; i < columns; i++ {
			cell := ""
			if i < len(row) {
				cell = row[i]
			}
			out.WriteString(" " + cell + " |")
		}
		out.WriteString("\n")
	}
	writeRow(rows[0])
	out.WriteString("|")
	for i := 0; i < columns; i++ {
		out.WriteString(" --- |")
	}
	out.WriteString("\n")
	for _, row := range rows[1:] {
		writeRow(row)
	}
	out.WriteString("\n")
	return out.String(), nil
}

func safeExternalLink(href string) bool {
	if href == "" || strings.ContainsAny(href, "\x00\r\n") {
		return false
	}
	u, err := url.Parse(href)
	if err != nil {
		return false
	}
	return strings.EqualFold(u.Scheme, "http") || strings.EqualFold(u.Scheme, "https")
}

func attribute(n *html.Node, name string) string {
	for _, attr := range n.Attr {
		if strings.EqualFold(attr.Key, name) || (name == "xlink:href" && strings.EqualFold(attr.Namespace, "xlink") && strings.EqualFold(attr.Key, "href")) {
			return attr.Val
		}
	}
	return ""
}

func nodeText(n *html.Node) string {
	if n.Type == html.TextNode {
		return n.Data
	}
	var out strings.Builder
	for child := n.FirstChild; child != nil; child = child.NextSibling {
		out.WriteString(nodeText(child))
	}
	return out.String()
}

func findElementText(n *html.Node, name string) string {
	if n.Type == html.ElementNode && strings.EqualFold(n.Data, name) {
		return nodeText(n)
	}
	for child := n.FirstChild; child != nil; child = child.NextSibling {
		if text := findElementText(child, name); text != "" {
			return text
		}
	}
	return ""
}

func visibleProseText(n *html.Node) string {
	var out strings.Builder
	var walk func(*html.Node)
	walk = func(node *html.Node) {
		if node.Type == html.TextNode {
			out.WriteString(node.Data)
			out.WriteByte(' ')
			return
		}
		if node.Type == html.ElementNode {
			switch strings.ToLower(node.Data) {
			case "script", "style", "noscript", "svg", "head", "nav", "img", "image":
				return
			}
		}
		for child := node.FirstChild; child != nil; child = child.NextSibling {
			walk(child)
		}
	}
	walk(n)
	return out.String()
}

// cleanInline normalizes whitespace while preserving explicit Markdown hard
// line breaks ("  \n") produced by <br> elements inside paragraphs.
func cleanInline(text string) string {
	lines := strings.Split(text, "\n")
	if len(lines) == 1 {
		return strings.Join(strings.Fields(text), " ")
	}
	out := make([]string, 0, len(lines))
	for i, line := range lines {
		hadHardBreak := strings.HasSuffix(line, "  ") && i < len(lines)-1
		cleaned := strings.Join(strings.Fields(line), " ")
		if cleaned == "" && !hadHardBreak {
			continue
		}
		if hadHardBreak {
			cleaned += "  "
		}
		out = append(out, cleaned)
	}
	return strings.Join(out, "\n")
}

// escapeInlineMarkdownText escapes literal Markdown inline syntax triggers in
// EPUB HTML text nodes so prose characters like '*' or '_' are never misparsed
// as emphasis.
func escapeInlineMarkdownText(text string) string {
	if !strings.ContainsAny(text, `\*_`+"`") {
		return text
	}
	var out strings.Builder
	out.Grow(len(text) + 8)
	for _, r := range text {
		switch r {
		case '\\', '*', '_', '`':
			out.WriteByte('\\')
		}
		out.WriteRune(r)
	}
	return out.String()
}

func cleanConvertedMarkdown(text string) string {
	text = strings.ReplaceAll(text, "\r\n", "\n")
	for strings.Contains(text, "\n\n\n") {
		text = strings.ReplaceAll(text, "\n\n\n", "\n\n")
	}
	text = strings.TrimSpace(text)
	if text != "" {
		text += "\n"
	}
	return text
}
