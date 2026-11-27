package bundle

import (
	"errors"
	"fmt"
	"os"
	"strings"

	"deepread/internal/markdown"
)

// BreakSpec defines one synthetic H2 break to insert before 1-based line number BeforeLine.
type BreakSpec struct {
	BeforeLine int    `json:"beforeLine"`
	Title      string `json:"title"`
}

// PrepareResult reports the synthetic sections created by Prepare.
type PrepareResult struct {
	BundleID          string             `json:"bundleId"`
	DocPath           string             `json:"docPath"`
	Inserted          int                `json:"inserted"`
	SyntheticSections []SyntheticSection `json:"syntheticSections"`
}

// Prepare deterministically inserts synthetic H2 headings (`## §n · Title`)
// into a Markdown document without altering any existing prose line, and
// records the synthetic sections in .deepread/manifest.json.
func Prepare(docPath string, breaks []BreakSpec) (PrepareResult, error) {
	if len(breaks) == 0 {
		return PrepareResult{}, errors.New("at least one break is required")
	}
	var result PrepareResult
	err := WithDocLock(docPath, func() error {
		rawBytes, err := os.ReadFile(docPath)
		if err != nil {
			return err
		}
		// Validate existing manifest BEFORE mutating docPath so a corrupt or
		// mismatched manifest can never leave synthetic headings stranded.
		manifest, _, err := LoadManifest(docPath, rawBytes)
		if err != nil {
			return err
		}
		fileMode := FilePerm(docPath)
		raw := string(rawBytes)
		newline := "\n"
		if strings.Contains(raw, "\r\n") {
			newline = "\r\n"
		}
		// Split keeping each line's original line ending intact so mixed LF/CRLF
		// prose lines remain byte-for-byte unchanged.
		rawLines := strings.SplitAfter(raw, "\n")
		if len(rawLines) > 1 && rawLines[len(rawLines)-1] == "" {
			rawLines = rawLines[:len(rawLines)-1]
		}
		lines := make([]string, len(rawLines))
		for i, rl := range rawLines {
			lines[i] = strings.TrimRight(rl, "\r\n")
		}

		// Precompute fenced code block mask so breaks never land inside a fence.
		inFence := make([]bool, len(lines))
		fenceOpen := false
		var fenceChar byte
		fenceLen := 0
		for i, line := range lines {
			trimmed := strings.TrimLeft(line, " \t")
			if !fenceOpen {
				if len(trimmed) >= 3 && (trimmed[0] == '`' || trimmed[0] == '~') {
					ch := trimmed[0]
					n := 0
					for n < len(trimmed) && trimmed[n] == ch {
						n++
					}
					if n >= 3 {
						fenceOpen = true
						fenceChar = ch
						fenceLen = n
						inFence[i] = true
						continue
					}
				}
			} else {
				inFence[i] = true
				n := 0
				for n < len(trimmed) && trimmed[n] == fenceChar {
					n++
				}
				if n >= fenceLen && strings.TrimSpace(trimmed[n:]) == "" {
					fenceOpen = false
				}
			}
		}

		// Validate breaks strictly in ascending line order.
		prevLine := 0
		for i, br := range breaks {
			title := strings.TrimSpace(br.Title)
			if title == "" || strings.ContainsAny(title, "\r\n") {
				return fmt.Errorf("break %d has empty or multiline title", i+1)
			}
			if strings.HasPrefix(title, "#") {
				return fmt.Errorf("break %d title %q must not start with #", i+1, title)
			}
			if br.BeforeLine < 1 || br.BeforeLine > len(lines) {
				return fmt.Errorf("break %d beforeLine %d out of range 1..%d", i+1, br.BeforeLine, len(lines))
			}
			if br.BeforeLine <= prevLine {
				return fmt.Errorf("breaks must be strictly ascending (got %d after %d)", br.BeforeLine, prevLine)
			}
			if strings.TrimSpace(lines[br.BeforeLine-1]) == "" {
				return fmt.Errorf("break %d beforeLine %d points to a blank line; point to the paragraph start", i+1, br.BeforeLine)
			}
			if inFence[br.BeforeLine-1] {
				return fmt.Errorf("break %d beforeLine %d is inside a fenced code block", i+1, br.BeforeLine)
			}
			prevLine = br.BeforeLine
		}

		breakAt := make(map[int]string, len(breaks))
		insertedHeadings := make([]string, 0, len(breaks))
		for i, br := range breaks {
			heading := fmt.Sprintf("§%d · %s", i+1, strings.TrimSpace(br.Title))
			breakAt[br.BeforeLine-1] = heading
			insertedHeadings = append(insertedHeadings, heading)
		}

		var out strings.Builder
		out.Grow(len(raw) + len(breaks)*48)
		prevNonBlank := false
		for idx, rl := range rawLines {
			if heading, ok := breakAt[idx]; ok {
				if idx > 0 {
					if !strings.HasSuffix(out.String(), "\n") {
						out.WriteString(newline)
					}
					if prevNonBlank {
						out.WriteString(newline)
					}
				}
				out.WriteString("## " + heading + newline + newline)
			}
			out.WriteString(rl)
			prevNonBlank = strings.TrimSpace(lines[idx]) != ""
		}
		updated := out.String()

		if err := WriteFileAtomic(docPath, []byte(updated), fileMode); err != nil {
			return err
		}

		sections := markdown.ExtractSections(updated)
		insertedSet := make(map[string]bool, len(insertedHeadings))
		for _, h := range insertedHeadings {
			insertedSet[markdown.NormalizeHeadingText(h)] = true
		}

		var syn []SyntheticSection
		for _, s := range sections {
			if s.Level == 2 && insertedSet[markdown.NormalizeHeadingText(s.Heading)] {
				syn = append(syn, SyntheticSection{Heading: s.Heading, Occurrence: s.Occurrence})
			}
		}
		manifest.SyntheticSections = append(manifest.SyntheticSections, syn...)
		manifest.SourceDigest = SHA256Hex([]byte(updated))
		if err := SaveManifest(docPath, manifest); err != nil {
			_ = WriteFileAtomic(docPath, rawBytes, fileMode)
			return err
		}

		result = PrepareResult{
			BundleID:          manifest.BundleID,
			DocPath:           docPath,
			Inserted:          len(breaks),
			SyntheticSections: manifest.SyntheticSections,
		}
		return nil
	})
	return result, err
}
