package ingest

import (
	"regexp"
	"strings"
)

// StripDownloaderBoilerplate removes trailing download-watermark paragraphs
// such as
//
//	This article was downloaded by [zlibrary](https://z-lib.org) from https://wsj.com/...
//	Downloaded from https://example.com/article
//
// that e-book downloaders append to an otherwise clean article or chapter.
// Only trailing paragraphs are considered, the match is anchored at the
// paragraph start, and URL-less prose is never touched, so real journalistic
// endings survive untouched.
func StripDownloaderBoilerplate(md string) string {
	lines := strings.SplitAfter(md, "\n")
	removed := false
	for {
		last := len(lines) - 1
		for last >= 0 && strings.TrimSpace(lines[last]) == "" {
			last--
		}
		if last < 0 {
			break
		}
		start := last
		for start > 0 && strings.TrimSpace(lines[start-1]) != "" {
			start--
		}
		if !isDownloaderWatermark(strings.Join(lines[start:last+1], "")) {
			break
		}
		lines = lines[:start]
		removed = true
	}
	if !removed {
		return md
	}
	newline := "\n"
	if strings.Contains(md, "\r\n") {
		newline = "\r\n"
	}
	out := strings.TrimRight(strings.Join(lines, ""), " \t\r\n")
	if out == "" {
		return ""
	}
	return out + newline
}

const maxWatermarkLength = 400

func isDownloaderWatermark(paragraph string) bool {
	text := strings.Join(strings.Fields(paragraph), " ")
	if text == "" || len(text) > maxWatermarkLength {
		return false
	}
	lower := strings.ToLower(text)
	for _, prefix := range []string{
		"this article was downloaded by",
		"this document was downloaded by",
		"this content was downloaded by",
		"this book was downloaded by",
		"this chapter was downloaded by",
		"this paper was downloaded by",
	} {
		if strings.HasPrefix(lower, prefix) {
			return true
		}
	}
	for _, prefix := range []string{
		"downloaded from ",
		"download from ",
		"downloaded by ",
		"downloaded at ",
	} {
		if strings.HasPrefix(lower, prefix) {
			return isURLLikeTail(text[len(prefix):])
		}
	}
	return false
}

// isURLLikeTail reports whether the remainder of a watermark paragraph is a
// single URL or Markdown link, never a sentence of prose.
func isURLLikeTail(tail string) bool {
	tail = strings.TrimSpace(strings.TrimRight(strings.TrimSpace(tail), ".,;"))
	if tail == "" {
		return false
	}
	lower := strings.ToLower(tail)
	if strings.HasPrefix(lower, "http://") || strings.HasPrefix(lower, "https://") || strings.HasPrefix(lower, "www.") {
		return !strings.Contains(tail, " ")
	}
	// Markdown link: [label](destination)
	return markdownLinkTailRe.MatchString(tail)
}

var markdownLinkTailRe = regexp.MustCompile(`^\[[^\]]*\]\([^)\s]+\)$`)
