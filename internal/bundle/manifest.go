package bundle

import (
	"crypto/sha256"
	"encoding/json"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
)

const ManifestSchemaVersion = 1

// Manifest stores minimal bundle metadata outside the Markdown/GenUI files.
type Manifest struct {
	SchemaVersion     int                `json:"schemaVersion"`
	BundleID          string             `json:"bundleId"`
	DocID             string             `json:"docId"`
	Revision          int                `json:"revision"`
	SourceDigest      string             `json:"sourceDigest,omitempty"`
	SyntheticSections []SyntheticSection `json:"syntheticSections,omitempty"`
}

// SyntheticSection marks an H2 inserted by `deepread prepare` so `export`
// can render it as a subtle editorial break rather than a heavy author heading.
type SyntheticSection struct {
	Heading    string `json:"heading"`
	Occurrence int    `json:"occurrence"`
}

// ManifestPath returns the path to .deepread/manifest.json for docPath.
func ManifestPath(docPath string) string {
	return filepath.Join(MetaDir(docPath), "manifest.json")
}

// DefaultBundleID derives a compact, human-typable 2-character alphanumeric ID
// (avoiding visually ambiguous chars like O/0/I/1) from docPath and content.
func DefaultBundleID(docPath string, content []byte) string {
	const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
	h := sha256.New()
	h.Write([]byte(filepath.Base(docPath)))
	h.Write([]byte{0})
	h.Write(content)
	sum := h.Sum(nil)
	return string([]byte{
		alphabet[int(sum[0])%len(alphabet)],
		alphabet[int(sum[1])%len(alphabet)],
	})
}

// LoadManifest reads .deepread/manifest.json, or returns a sensible default
// in-memory manifest when none exists yet.
func LoadManifest(docPath string, docBytes []byte) (Manifest, bool, error) {
	path := ManifestPath(docPath)
	raw, err := os.ReadFile(path)
	if errors.Is(err, fs.ErrNotExist) {
		return Manifest{
			SchemaVersion: ManifestSchemaVersion,
			BundleID:      DefaultBundleID(docPath, docBytes),
			DocID:         filepath.Base(docPath),
			Revision:      0,
			SourceDigest:  SHA256Hex(docBytes),
		}, false, nil
	}
	if err != nil {
		return Manifest{}, false, err
	}
	var m Manifest
	if err := json.Unmarshal(raw, &m); err != nil {
		return Manifest{}, true, err
	}
	if m.SchemaVersion == 0 {
		m.SchemaVersion = ManifestSchemaVersion
	}
	if m.BundleID == "" {
		m.BundleID = DefaultBundleID(docPath, docBytes)
	}
	if m.DocID != "" && m.DocID != filepath.Base(docPath) {
		return Manifest{}, true, fmt.Errorf("%w: bundle directory belongs to %q, not %q (use a separate directory per document)", ErrDocMismatch, m.DocID, filepath.Base(docPath))
	}
	if m.DocID == "" {
		m.DocID = filepath.Base(docPath)
	}
	return m, true, nil
}

// SaveManifest atomically persists .deepread/manifest.json.
func SaveManifest(docPath string, m Manifest) error {
	if m.SchemaVersion == 0 {
		m.SchemaVersion = ManifestSchemaVersion
	}
	if m.DocID == "" {
		m.DocID = filepath.Base(docPath)
	}
	data, err := json.MarshalIndent(m, "", "  ")
	if err != nil {
		return err
	}
	return WriteFileAtomic(ManifestPath(docPath), append(data, '\n'), 0o644)
}

// IsSynthetic reports whether a (heading, occurrence) pair was inserted by prepare.
func (m Manifest) IsSynthetic(heading string, occurrence int) bool {
	norm := strings.ToLower(strings.Join(strings.Fields(heading), " "))
	for _, s := range m.SyntheticSections {
		if strings.ToLower(strings.Join(strings.Fields(s.Heading), " ")) == norm && s.Occurrence == occurrence {
			return true
		}
	}
	return false
}
