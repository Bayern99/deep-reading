// Package ingest converts Markdown and EPUB inputs into deepread document bundles.
package ingest

import (
	"bytes"
	"errors"
	"fmt"
	"path/filepath"
	"strings"
)

const (
	DefaultMaxTotalBytes int64 = 64 << 20
	DefaultMaxFileBytes  int64 = 16 << 20
	DefaultMaxEntries    int   = 2000
)

var (
	ErrUnsupportedFormat = errors.New("unsupported input format")
	ErrUnsafeArchive     = errors.New("unsafe archive or path")
	ErrArchiveLimit      = errors.New("archive exceeds safety limit")
)

// Options bounds the amount of input that an ingest operation may decompress.
// Non-positive values select the corresponding defaults.
type Options struct {
	MaxTotalBytes int64
	MaxFileBytes  int64
	MaxEntries    int
}

// ChapterInfo describes one independently bundled EPUB chapter.
type ChapterInfo struct {
	Index      int    `json:"index"`
	Slug       string `json:"slug"`
	Title      string `json:"title"`
	WordCount  int    `json:"wordCount"`
	ImageCount int    `json:"imageCount"`
	BundleID   string `json:"bundleId"`
	DocPath    string `json:"docPath"`
}

// Result describes the document or book produced by Ingest.
type Result struct {
	Kind       string        `json:"kind"`
	Title      string        `json:"title"`
	Author     string        `json:"author,omitempty"`
	OutDir     string        `json:"outDir"`
	DocPath    string        `json:"docPath,omitempty"`
	IndexPath  string        `json:"indexPath,omitempty"`
	BookJSON   string        `json:"bookJson,omitempty"`
	BundleID   string        `json:"bundleId,omitempty"`
	ImageCount int           `json:"imageCount"`
	Chapters   []ChapterInfo `json:"chapters,omitempty"`
}

// Ingest imports a local Markdown or EPUB file. Format support is deliberately
// limited to those two formats; no external converters or network fetches are used.
func Ingest(srcPath, outDir string, opts Options) (Result, error) {
	opts = opts.withDefaults()
	switch strings.ToLower(filepath.Ext(srcPath)) {
	case ".md", ".markdown":
		return ingestMarkdown(srcPath, outDir, opts)
	case ".epub":
		return ingestEPUB(srcPath, outDir, opts)
	default:
		return Result{}, fmt.Errorf("%w: %q", ErrUnsupportedFormat, filepath.Ext(srcPath))
	}
}

func (o Options) withDefaults() Options {
	if o.MaxTotalBytes <= 0 {
		o.MaxTotalBytes = DefaultMaxTotalBytes
	}
	if o.MaxFileBytes <= 0 {
		o.MaxFileBytes = DefaultMaxFileBytes
	}
	if o.MaxEntries <= 0 {
		o.MaxEntries = DefaultMaxEntries
	}
	return o
}

// rasterImageExtension sniffs the actual payload rather than trusting its name.
func rasterImageExtension(data []byte) (string, bool) {
	switch {
	case len(data) >= 8 && bytes.Equal(data[:8], []byte{0x89, 'P', 'N', 'G', '\r', '\n', 0x1a, '\n'}):
		return ".png", true
	case len(data) >= 3 && bytes.Equal(data[:3], []byte{0xff, 0xd8, 0xff}):
		return ".jpg", true
	case len(data) >= 6 && (string(data[:6]) == "GIF87a" || string(data[:6]) == "GIF89a"):
		return ".gif", true
	case len(data) >= 12 && string(data[:4]) == "RIFF" && string(data[8:12]) == "WEBP":
		return ".webp", true
	case len(data) >= 12 && string(data[4:8]) == "ftyp":
		brand := string(data[8:12])
		if brand == "avif" || brand == "avis" {
			return ".avif", true
		}
	}
	return "", false
}
