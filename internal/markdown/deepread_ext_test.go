package markdown

import "testing"

func TestOwnBodyEndByteAndPartitions(t *testing.T) {
	raw := "Preamble line.\n\n## Alpha\nAlpha prose.\n\n### Child\nChild prose.\n\n## Beta\nBeta prose.\n"
	secs := ExtractSections(raw)
	if len(secs) != 3 {
		t.Fatalf("expected 3 sections, got %d", len(secs))
	}
	var reconstructed string
	reconstructed += raw[:secs[0].ByteStart()]
	for i := range secs {
		end := OwnBodyEndByte(raw, secs, i)
		reconstructed += raw[secs[i].ByteStart():end]
	}
	if reconstructed != raw {
		t.Fatalf("partition did not reconstruct raw byte-for-byte:\ngot:  %q\nwant: %q", reconstructed, raw)
	}
	// Alpha's own body must stop before ### Child, not include Child.
	alphaEnd := OwnBodyEndByte(raw, secs, 0)
	if raw[secs[0].ByteStart():alphaEnd] != "## Alpha\nAlpha prose.\n\n" {
		t.Fatalf("unexpected Alpha own body: %q", raw[secs[0].ByteStart():alphaEnd])
	}
}

func TestNoteAttrsAndStripNotes(t *testing.T) {
	base := "## Alpha\nSome prose with emoji 🎯 and 中文.\n\n### Child\nChild text.\n"
	withNote := "## Alpha\nSome prose with emoji 🎯 and 中文.\n\n<!-- note node=\"capex\" id=\"n1\" rev=\"2\": Fix --\\> chart -->\n\n### Child\nChild text.\n"
	notes := ExtractNotes(withNote)
	if len(notes) != 1 {
		t.Fatalf("expected 1 note, got %d", len(notes))
	}
	if notes[0].SectionHeading != "Alpha" {
		t.Fatalf("expected note attributed to Alpha (not Child), got %q", notes[0].SectionHeading)
	}
	if notes[0].Text != "Fix --> chart" {
		t.Fatalf("unexpected unescaped note text: %q", notes[0].Text)
	}
	attrs := NoteAttrs(withNote, notes[0])
	if attrs["node"] != "capex" || attrs["id"] != "n1" || attrs["rev"] != "2" {
		t.Fatalf("unexpected attrs: %#v", attrs)
	}
	stripped := StripNotes(withNote)
	if stripped != base {
		t.Fatalf("StripNotes mismatch:\ngot:  %q\nwant: %q", stripped, base)
	}
}
