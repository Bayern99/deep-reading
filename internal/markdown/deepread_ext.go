package markdown

import (
	"regexp"
	"strings"
)

var noteAttrRe = regexp.MustCompile(`([A-Za-z_][\w-]*)="([^"]*)"`)

// OwnBodyEndByte returns the byte offset where section idx's own body ends,
// strictly before the next heading (whether child or sibling) or EOF.
// Slicing raw by [0:sections[0].ByteStart()] and [sections[i].ByteStart():OwnBodyEndByte(raw, sections, i)]
// partitions the entire document into exact, disjoint byte ranges.
func OwnBodyEndByte(raw string, sections []Section, idx int) int {
	if idx < 0 || idx >= len(sections) {
		return len(raw)
	}
	if idx+1 < len(sections) {
		return sections[idx+1].ByteStart()
	}
	return len(raw)
}

// NoteAttrs extracts key="value" attributes from the opening header of an
// attributed inline note such as <!-- note node="capex" id="n1" rev="1": ... -->.
func NoteAttrs(raw string, n Note) map[string]string {
	start, end := n.ByteRange()
	if start < 0 || end > len(raw) || start >= end {
		return nil
	}
	head, _, ok := ReadNote(raw[start:end])
	if !ok {
		return nil
	}
	matches := noteAttrRe.FindAllStringSubmatch(head, -1)
	if len(matches) == 0 {
		return nil
	}
	attrs := make(map[string]string, len(matches))
	for _, m := range matches {
		attrs[m[1]] = m[2]
	}
	return attrs
}

// StripNotes removes all parsed inline notes (including the blank-line gap
// inserted right before each note) so callers can verify prose byte-parity.
func StripNotes(raw string) string {
	notes := ExtractNotes(raw)
	if len(notes) == 0 {
		return raw
	}
	var b strings.Builder
	b.Grow(len(raw))
	cursor := 0
	for _, n := range notes {
		cut := n.CutStartByte()
		_, end := n.ByteRange()
		if cut > cursor {
			b.WriteString(raw[cursor:cut])
		}
		if end > cursor {
			cursor = end
		}
	}
	if cursor < len(raw) {
		b.WriteString(raw[cursor:])
	}
	return b.String()
}
