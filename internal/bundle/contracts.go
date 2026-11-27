package bundle

import (
	"encoding/json"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"regexp"
	"strings"

	"golang.org/x/text/language"
)

const (
	ReadModeOriginal   = "original"
	ReadModeTranslated = "translated"
	ReadModeBilingual  = "bilingual"

	ProfileCanvas = "canvas"
	ProfileMargin = "margin"

	TranslationSchemaVersion = 1
)

var (
	// ErrConflict indicates a compare-and-swap hash mismatch (maps to CLI exit 5).
	ErrConflict = errors.New("compare-and-swap conflict")
	// ErrTranslationIncomplete indicates missing or stale translated blocks when
	// exporting translated/bilingual mode (maps to CLI exit 3).
	ErrTranslationIncomplete = errors.New("translation incomplete")
	// ErrInvalidLang indicates a malformed or unsafe BCP 47 language tag.
	ErrInvalidLang = errors.New("invalid language tag")
)

// ReaderConfig records the reading contract agreed upon for a bundle.
type ReaderConfig struct {
	SourceLang string `json:"sourceLang,omitempty"`
	TargetLang string `json:"targetLang,omitempty"`
	Mode       string `json:"mode,omitempty"` // original | translated | bilingual
}

// SourceBinding identifies one cited section inside a Source statement.
type SourceBinding struct {
	SourceID   string `json:"sourceId"`
	Heading    string `json:"heading"`
	Occurrence int    `json:"occurrence"`
	SourceHash string `json:"sourceHash,omitempty"`
}

// Block describes one deterministic, content-addressed translatable unit
// extracted from a Markdown document (with inline reader notes stripped).
type Block struct {
	ID                string `json:"id"`
	Kind              string `json:"kind"` // heading | paragraph | blockquote | list_item | table_cell | image_alt
	SectionHeading    string `json:"sectionHeading,omitempty"`
	SectionOccurrence int    `json:"sectionOccurrence,omitempty"`
	HeadingLevel      int    `json:"headingLevel,omitempty"`
	StartByte         int    `json:"startByte"`
	EndByte           int    `json:"endByte"`
	SourceHash        string `json:"sourceHash"`
	Text              string `json:"text"`
}

// TranslationEntry stores one translated block anchored by its source hash.
type TranslationEntry struct {
	ID         string `json:"id"`
	SourceHash string `json:"sourceHash"`
	Text       string `json:"text"`
}

// TranslationLayer is the on-disk schema of .deepread/translations/<lang>.json.
type TranslationLayer struct {
	SchemaVersion int                         `json:"schemaVersion"`
	Lang          string                      `json:"lang"`
	UpdatedAt     string                      `json:"updatedAt,omitempty"`
	Entries       map[string]TranslationEntry `json:"entries"`
}

// TranslationStatus summarizes translation coverage and staleness for a document.
type TranslationStatus struct {
	Lang             string   `json:"lang"`
	TotalBlocks      int      `json:"totalBlocks"`
	TranslatedBlocks int      `json:"translatedBlocks"`
	StaleBlocks      int      `json:"staleBlocks"`
	CoveragePct      int      `json:"coveragePct"`
	MissingIDs       []string `json:"missingIds,omitempty"`
	StaleIDs         []string `json:"staleIds,omitempty"`
}

// CitationMap maps statement name -> sourceId -> list of cited block IDs.
// Persisted in .deepread/citations.json without altering Mark Go Go v3 sidecars.
type CitationMap map[string]map[string][]string

// DocSnapshot holds a consistent read snapshot loaded under a single shared lock.
type DocSnapshot struct {
	DocPath           string
	DocBytes          []byte
	Manifest          Manifest
	ViewBytes         []byte
	ViewExists        bool
	Translation       *TranslationLayer
	TranslationStatus *TranslationStatus
	Citations         CitationMap
}

var bcp47SubtagRe = regexp.MustCompile(`^[A-Za-z0-9]{1,8}$`)

// CanonicalLang validates and canonicalizes a BCP 47 language tag (e.g. "zh-cn" -> "zh-CN")
// so it is safe to use in filenames across case-sensitive and case-insensitive filesystems.
func CanonicalLang(raw string) (string, error) {
	s := strings.TrimSpace(strings.ReplaceAll(raw, "_", "-"))
	if s == "" || len(s) > 35 {
		return "", fmt.Errorf("%w: %q", ErrInvalidLang, raw)
	}
	parts := strings.Split(s, "-")
	if len(parts) == 0 || len(parts[0]) < 2 || len(parts[0]) > 3 || !isAllAlpha(parts[0]) {
		return "", fmt.Errorf("%w: %q", ErrInvalidLang, raw)
	}
	for _, p := range parts {
		if !bcp47SubtagRe.MatchString(p) {
			return "", fmt.Errorf("%w: %q", ErrInvalidLang, raw)
		}
	}
	tag, err := language.Parse(s)
	if err != nil || tag == language.Und {
		return "", fmt.Errorf("%w: %q", ErrInvalidLang, raw)
	}
	canon := tag.String()
	if canon == "" || strings.EqualFold(canon, "und") || len(canon) > 35 {
		return "", fmt.Errorf("%w: %q", ErrInvalidLang, raw)
	}
	for _, p := range strings.Split(canon, "-") {
		if !bcp47SubtagRe.MatchString(p) {
			return "", fmt.Errorf("%w: %q", ErrInvalidLang, raw)
		}
	}
	return canon, nil
}

func isAllAlpha(s string) bool {
	for i := 0; i < len(s); i++ {
		if (s[i] < 'A' || s[i] > 'Z') && (s[i] < 'a' || s[i] > 'z') {
			return false
		}
	}
	return len(s) > 0
}

// ValidateReadMode verifies mode is empty or one of original|translated|bilingual.
func ValidateReadMode(mode string) error {
	switch strings.TrimSpace(mode) {
	case "", ReadModeOriginal, ReadModeTranslated, ReadModeBilingual:
		return nil
	default:
		return fmt.Errorf("invalid read mode %q (expected original, translated, or bilingual)", mode)
	}
}

// TranslationsDir returns .deepread/translations for docPath.
func TranslationsDir(docPath string) string {
	return filepath.Join(MetaDir(docPath), "translations")
}

// TranslationPath returns the canonical .deepread/translations/<lang>.json path.
func TranslationPath(docPath, lang string) (string, error) {
	canon, err := CanonicalLang(lang)
	if err != nil {
		return "", err
	}
	return filepath.Join(TranslationsDir(docPath), canon+".json"), nil
}

// CitationsPath returns .deepread/citations.json for docPath.
func CitationsPath(docPath string) string {
	return filepath.Join(MetaDir(docPath), "citations.json")
}

// LoadCitations reads .deepread/citations.json if present.
func LoadCitations(docPath string) (CitationMap, error) {
	raw, err := os.ReadFile(CitationsPath(docPath))
	if errors.Is(err, fs.ErrNotExist) {
		return CitationMap{}, nil
	}
	if err != nil {
		return nil, err
	}
	var out CitationMap
	if err := json.Unmarshal(raw, &out); err != nil {
		return nil, fmt.Errorf("parse citations.json: %w", err)
	}
	if out == nil {
		out = CitationMap{}
	}
	return out, nil
}

// SaveCitations atomically writes .deepread/citations.json (or removes it when empty).
func SaveCitations(docPath string, citations CitationMap) error {
	path := CitationsPath(docPath)
	if len(citations) == 0 {
		if err := os.Remove(path); err != nil && !errors.Is(err, fs.ErrNotExist) {
			return err
		}
		return nil
	}
	data, err := json.MarshalIndent(citations, "", "  ")
	if err != nil {
		return err
	}
	return WriteFileAtomic(path, append(data, '\n'), 0o644)
}
