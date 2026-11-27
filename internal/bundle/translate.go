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
	"time"
)

var (
	rawScriptTagRe        = regexp.MustCompile(`(?i)<\s*script\b`)
	blockLevelImageMarkRe = regexp.MustCompile(`(?m)(^|\n)[ \t]*!\[[^\]\n]*\]\(`)
)

// ApplyTranslations merges translated blocks into
// .deepread/translations/<lang>.json after validating every entry against the
// live document blocks and their source hashes.
//
// Entries whose SourceHash is stale are rejected with ErrConflict so the host
// agent re-reads the live block instead of silently overwriting fresh prose.
func ApplyTranslations(docPath, lang string, entries []TranslationEntry) (TranslationStatus, error) {
	canon, err := CanonicalLang(lang)
	if err != nil {
		return TranslationStatus{}, err
	}
	var status TranslationStatus
	err = WithDocLock(docPath, func() error {
		docBytes, err := os.ReadFile(docPath)
		if err != nil {
			return err
		}
		manifest, _, err := LoadManifest(docPath, docBytes)
		if err != nil {
			return err
		}
		blocks := ExtractBlocks(docBytes, manifest)
		live := make(map[string]Block, len(blocks))
		for _, b := range blocks {
			live[b.ID] = b
		}

		layer, exists, err := loadTranslationLayer(docPath, canon)
		if err != nil {
			return err
		}
		if !exists {
			layer = &TranslationLayer{
				SchemaVersion: TranslationSchemaVersion,
				Lang:          canon,
				Entries:       map[string]TranslationEntry{},
			}
		}

		// Validate every entry before mutating the in-memory layer so a bad
		// batch never leaves a partially applied translation file behind.
		pending := make([]TranslationEntry, 0, len(entries))
		for _, entry := range entries {
			id := strings.TrimSpace(entry.ID)
			if id == "" {
				return errors.New("translation entry requires a non-empty block id")
			}
			block, ok := live[id]
			if !ok {
				return fmt.Errorf("%w: block %q is not present in %s (run `deepread inspect` for live block ids)", ErrNotFound, id, filepath.Base(docPath))
			}
			if entry.SourceHash != "" && entry.SourceHash != block.SourceHash {
				return fmt.Errorf("%w: block %s source hash mismatch (expected %s, live %s)", ErrConflict, id, entry.SourceHash, block.SourceHash)
			}
			text := NormalizeTranslatedText(entry.Text)
			if err := validateTranslatedBlock(block.Kind, text); err != nil {
				return fmt.Errorf("block %s: %w", id, err)
			}
			pending = append(pending, TranslationEntry{
				ID:         id,
				SourceHash: block.SourceHash,
				Text:       text,
			})
		}
		for _, entry := range pending {
			layer.Entries[entry.ID] = entry
		}
		layer.SchemaVersion = TranslationSchemaVersion
		layer.Lang = canon
		layer.UpdatedAt = time.Now().UTC().Format(time.RFC3339)

		if err := saveTranslationLayer(docPath, canon, layer); err != nil {
			return err
		}
		status = EvaluateTranslationStatus(blocks, layer, canon)
		return nil
	})
	if err != nil {
		return TranslationStatus{}, err
	}
	return status, nil
}

// SetReaderConfig persists the agreed reading contract in the bundle manifest.
// An empty config clears any previously recorded contract.
func SetReaderConfig(docPath string, cfg ReaderConfig) error {
	return WithDocLock(docPath, func() error {
		docBytes, err := os.ReadFile(docPath)
		if err != nil {
			return err
		}
		manifest, _, err := LoadManifest(docPath, docBytes)
		if err != nil {
			return err
		}
		normalized, err := canonicalReaderConfig(cfg)
		if err != nil {
			return err
		}
		manifest.Reader = normalized
		return SaveManifest(docPath, manifest)
	})
}

// canonicalReaderConfig validates a reader contract and canonicalizes its
// language tags so on-disk translation filenames stay portable.
func canonicalReaderConfig(cfg ReaderConfig) (*ReaderConfig, error) {
	out := ReaderConfig{Mode: strings.TrimSpace(cfg.Mode)}
	if err := ValidateReadMode(out.Mode); err != nil {
		return nil, err
	}
	if strings.TrimSpace(cfg.SourceLang) != "" {
		canon, err := CanonicalLang(cfg.SourceLang)
		if err != nil {
			return nil, err
		}
		out.SourceLang = canon
	}
	if strings.TrimSpace(cfg.TargetLang) != "" {
		canon, err := CanonicalLang(cfg.TargetLang)
		if err != nil {
			return nil, err
		}
		out.TargetLang = canon
	}
	if out.SourceLang == "" && out.TargetLang == "" && out.Mode == "" {
		return nil, nil
	}
	return &out, nil
}

// LoadTranslationUnlocked loads the translation layer and its coverage status
// for docBytes. Callers must already hold a bundle lock.
func LoadTranslationUnlocked(docPath, lang string, docBytes []byte, manifest Manifest) (*TranslationLayer, TranslationStatus, error) {
	canon, err := CanonicalLang(lang)
	if err != nil {
		return nil, TranslationStatus{}, err
	}
	layer, _, err := loadTranslationLayer(docPath, canon)
	if err != nil {
		return nil, TranslationStatus{}, err
	}
	blocks := ExtractBlocks(docBytes, manifest)
	return layer, EvaluateTranslationStatus(blocks, layer, canon), nil
}

// EvaluateTranslationStatus computes exact translation coverage for blocks.
// It is a pure function: no disk access, no mutation.
func EvaluateTranslationStatus(blocks []Block, layer *TranslationLayer, lang string) TranslationStatus {
	status := TranslationStatus{Lang: lang, TotalBlocks: len(blocks)}
	for _, block := range blocks {
		var entry TranslationEntry
		var ok bool
		if layer != nil && layer.Entries != nil {
			entry, ok = layer.Entries[block.ID]
		}
		switch {
		case !ok:
			status.MissingIDs = append(status.MissingIDs, block.ID)
		case entry.SourceHash != block.SourceHash:
			status.StaleBlocks++
			status.StaleIDs = append(status.StaleIDs, block.ID)
		default:
			status.TranslatedBlocks++
		}
	}
	switch {
	case status.TotalBlocks == 0:
		status.CoveragePct = 100
	case status.TranslatedBlocks == status.TotalBlocks:
		status.CoveragePct = 100
	default:
		// Integer division never rounds 99.x% up to 100%.
		status.CoveragePct = (status.TranslatedBlocks * 100) / status.TotalBlocks
	}
	return status
}

// LoadDocSnapshot loads every read-side artifact of a bundle under one shared
// lock so `inspect` and `export` can never observe torn state.
func LoadDocSnapshot(docPath, targetLang string) (DocSnapshot, error) {
	lang := ""
	if strings.TrimSpace(targetLang) != "" {
		canon, err := CanonicalLang(targetLang)
		if err != nil {
			return DocSnapshot{}, err
		}
		lang = canon
	}
	var snap DocSnapshot
	err := WithDocRLock(docPath, func() error {
		docBytes, err := os.ReadFile(docPath)
		if err != nil {
			return err
		}
		manifest, _, err := LoadManifest(docPath, docBytes)
		if err != nil {
			return err
		}
		snap = DocSnapshot{
			DocPath:  docPath,
			DocBytes: docBytes,
			Manifest: manifest,
		}
		viewBytes, err := os.ReadFile(ViewPath(docPath))
		switch {
		case err == nil:
			if len(viewBytes) > MaxViewBytes {
				return fmt.Errorf("view exceeds %d bytes (%d bytes)", MaxViewBytes, len(viewBytes))
			}
			snap.ViewBytes = viewBytes
			snap.ViewExists = true
		case !errors.Is(err, fs.ErrNotExist):
			return err
		}
		citations, err := LoadCitations(docPath)
		if err != nil {
			return err
		}
		snap.Citations = citations

		effective := lang
		if effective == "" && manifest.Reader != nil {
			effective = strings.TrimSpace(manifest.Reader.TargetLang)
		}
		if effective != "" {
			layer, status, err := LoadTranslationUnlocked(docPath, effective, docBytes, manifest)
			if err != nil {
				return err
			}
			snap.Translation = layer
			snap.TranslationStatus = &status
		}
		return nil
	})
	if err != nil {
		return DocSnapshot{}, err
	}
	return snap, nil
}

// LoadDocSnapshotInRoot loads a chapter bundle snapshot strictly through root
// using non-blocking regular-file opens so no file can escape root between
// path validation and read.
func LoadDocSnapshotInRoot(root *os.Root, relDocPath, fullDocPath, targetLang string) (DocSnapshot, error) {
	lang := ""
	if strings.TrimSpace(targetLang) != "" {
		canon, err := CanonicalLang(targetLang)
		if err != nil {
			return DocSnapshot{}, err
		}
		lang = canon
	}
	relClean := filepath.ToSlash(relDocPath)
	relDir := filepath.ToSlash(filepath.Dir(relDocPath))
	relBase := filepath.Base(relDocPath)
	joinRel := func(parts ...string) string {
		if relDir == "" || relDir == "." {
			return strings.Join(parts, "/")
		}
		all := append([]string{relDir}, parts...)
		return strings.Join(all, "/")
	}

	var snap DocSnapshot
	err := WithDocRLockInRoot(root, relClean, func() error {
		docBytes, err := ReadRegularFileInRoot(root, relClean, 16<<20)
		if err != nil {
			return err
		}
		manifest := Manifest{
			SchemaVersion: ManifestSchemaVersion,
			BundleID:      DefaultBundleID(fullDocPath, docBytes),
			DocID:         relBase,
			Revision:      0,
			SourceDigest:  SHA256Hex(docBytes),
		}
		if rawManifest, err := ReadRegularFileInRoot(root, joinRel(".deepread", "manifest.json"), 1<<20); err == nil {
			var loaded Manifest
			if err := json.Unmarshal(rawManifest, &loaded); err != nil {
				return err
			}
			if loaded.SchemaVersion == 0 {
				loaded.SchemaVersion = ManifestSchemaVersion
			}
			if loaded.BundleID == "" {
				loaded.BundleID = DefaultBundleID(fullDocPath, docBytes)
			}
			if loaded.DocID != "" && loaded.DocID != relBase {
				return fmt.Errorf("%w: bundle directory belongs to %q, not %q (use a separate directory per document)", ErrDocMismatch, loaded.DocID, relBase)
			}
			if loaded.DocID == "" {
				loaded.DocID = relBase
			}
			manifest = loaded
		} else if !errors.Is(err, fs.ErrNotExist) {
			return err
		}

		snap = DocSnapshot{
			DocPath:   fullDocPath,
			DocBytes:  docBytes,
			Manifest:  manifest,
			Citations: CitationMap{},
		}
		viewBytes, err := ReadRegularFileInRoot(root, joinRel("."+relBase+".genui.json"), MaxViewBytes)
		switch {
		case err == nil:
			snap.ViewBytes = viewBytes
			snap.ViewExists = true
		case !errors.Is(err, fs.ErrNotExist):
			return err
		}
		if rawCitations, err := ReadRegularFileInRoot(root, joinRel(".deepread", "citations.json"), 1<<20); err == nil {
			var citations CitationMap
			if err := json.Unmarshal(rawCitations, &citations); err != nil {
				return fmt.Errorf("parse citations.json: %w", err)
			}
			if citations != nil {
				snap.Citations = citations
			}
		} else if !errors.Is(err, fs.ErrNotExist) {
			return err
		}

		effective := lang
		if effective == "" && manifest.Reader != nil {
			effective = strings.TrimSpace(manifest.Reader.TargetLang)
		}
		if effective != "" {
			canon, err := CanonicalLang(effective)
			if err != nil {
				return err
			}
			blocks := ExtractBlocks(docBytes, manifest)
			rawTrans, err := ReadRegularFileInRoot(root, joinRel(".deepread", "translations", canon+".json"), 16<<20)
			switch {
			case err == nil:
				var layer TranslationLayer
				if err := json.Unmarshal(rawTrans, &layer); err != nil {
					return fmt.Errorf("parse translation %s: %w", canon, err)
				}
				if layer.Entries == nil {
					layer.Entries = map[string]TranslationEntry{}
				}
				if layer.Lang == "" {
					layer.Lang = canon
				}
				status := EvaluateTranslationStatus(blocks, &layer, canon)
				snap.Translation = &layer
				snap.TranslationStatus = &status
			case errors.Is(err, fs.ErrNotExist):
				status := EvaluateTranslationStatus(blocks, nil, canon)
				snap.Translation = nil
				snap.TranslationStatus = &status
			default:
				return err
			}
		}
		return nil
	})
	if err != nil {
		return DocSnapshot{}, err
	}
	return snap, nil
}

// NormalizeTranslatedText canonicalizes line endings and trims outer whitespace.
func NormalizeTranslatedText(text string) string {
	text = strings.ReplaceAll(text, "\r\n", "\n")
	text = strings.ReplaceAll(text, "\r", "\n")
	return strings.TrimSpace(text)
}

func validateTranslatedBlock(kind, text string) error {
	if strings.TrimSpace(text) == "" {
		return errors.New("translated text cannot be empty")
	}
	if rawScriptTagRe.MatchString(text) {
		return errors.New("translated text must not contain raw <script> tags")
	}
	if kind != BlockKindImageAlt && blockLevelImageMarkRe.MatchString(text) {
		return fmt.Errorf("translated %s block must not contain block-level image markdown", kind)
	}
	return nil
}

func translationFilePath(docPath, canon string) string {
	return filepath.Join(TranslationsDir(docPath), canon+".json")
}

func loadTranslationLayer(docPath, canon string) (*TranslationLayer, bool, error) {
	path := translationFilePath(docPath, canon)
	raw, err := os.ReadFile(path)
	if errors.Is(err, fs.ErrNotExist) {
		return nil, false, nil
	}
	if err != nil {
		return nil, false, err
	}
	var layer TranslationLayer
	if err := json.Unmarshal(raw, &layer); err != nil {
		return nil, true, fmt.Errorf("parse translation file %s: %w", path, err)
	}
	if layer.Entries == nil {
		layer.Entries = map[string]TranslationEntry{}
	}
	if layer.Lang == "" {
		layer.Lang = canon
	}
	return &layer, true, nil
}

func saveTranslationLayer(docPath, canon string, layer *TranslationLayer) error {
	data, err := json.MarshalIndent(layer, "", "  ")
	if err != nil {
		return err
	}
	return WriteFileAtomic(translationFilePath(docPath, canon), append(data, '\n'), 0o644)
}
