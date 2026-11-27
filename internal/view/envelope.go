package view

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"time"

	"deepread/internal/bundle"
	"deepread/internal/openuilang"
)

const (
	ViewVersion  = 3
	ViewLanguage = "openui-lang/1.0"
	CatalogID    = "markgogo.dev:genui/v3"
	SurfaceID    = "view"
	A2UIVersion  = "1.0"
	MaxViewBytes = 1 << 20 // 1 MiB — matches Mark Go Go's MaxViewBytes limit.
)

// SourceRef matches Mark Go Go's ViewSource JSON format.
type SourceRef struct {
	Heading    string `json:"heading"`
	Occurrence int    `json:"occurrence"`
	Hash       string `json:"hash,omitempty"`
}

// Envelope is Mark Go Go's exact v3 sidecar JSON structure.
type Envelope struct {
	Version     int                  `json:"version"`
	Language    string               `json:"language"`
	GeneratedAt string               `json:"generatedAt"`
	Model       string               `json:"model,omitempty"`
	Request     string               `json:"request,omitempty"`
	Sources     map[string]SourceRef `json:"sources"`
	A2UI        []A2UIMessage        `json:"a2ui"`
}

// A2UIMessage represents either createSurface or updateComponents in v3.
type A2UIMessage struct {
	Version          string            `json:"version"`
	CreateSurface    *CreateSurface    `json:"createSurface,omitempty"`
	UpdateComponents *UpdateComponents `json:"updateComponents,omitempty"`
}

// CreateSurface initializes the view surface with statement strings.
type CreateSurface struct {
	SurfaceID  string   `json:"surfaceId"`
	CatalogID  string   `json:"catalogId"`
	Components []string `json:"components"`
}

// UpdateComponents represents a Mark Go Go incremental update batch.
type UpdateComponents struct {
	SurfaceID  string   `json:"surfaceId"`
	Components []string `json:"components"`
}

// ParsedView holds a decoded Mark Go Go v3 sidecar with overlaid statements.
type ParsedView struct {
	Raw        []byte
	Envelope   Envelope
	Statements []string // Compacted active statements after overlaying all batches.
	JoinedText string
}

// ReadView parses any valid Mark Go Go v3 sidecar (single createSurface or
// multi-message createSurface + updateComponents).
func ReadView(raw []byte) (*ParsedView, error) {
	if len(raw) > MaxViewBytes {
		return nil, &ValidationError{
			Code:    "VIEW_TOO_LARGE",
			Path:    "/",
			Message: fmt.Sprintf("view exceeds %d bytes (%d bytes)", MaxViewBytes, len(raw)),
			Hint:    "Compact the view or reduce module size.",
		}
	}
	var env Envelope
	if err := json.Unmarshal(raw, &env); err != nil {
		return nil, &ValidationError{Code: "INVALID_JSON", Path: "/", Message: err.Error()}
	}
	if env.Version != ViewVersion {
		return nil, &ValidationError{Code: "INVALID_VERSION", Path: "/version", Message: fmt.Sprintf("expected version %d, got %d", ViewVersion, env.Version)}
	}
	if env.Language != ViewLanguage {
		return nil, &ValidationError{Code: "INVALID_LANGUAGE", Path: "/language", Message: fmt.Sprintf("expected language %q, got %q", ViewLanguage, env.Language)}
	}
	if len(env.A2UI) == 0 {
		return nil, &ValidationError{Code: "EMPTY_MESSAGES", Path: "/a2ui", Message: "a2ui must contain at least one message"}
	}
	if env.Sources == nil {
		env.Sources = map[string]SourceRef{}
	}

	surface := ""
	joined := ""
	for i, msg := range env.A2UI {
		if msg.Version != A2UIVersion {
			return nil, &ValidationError{Code: "INVALID_MESSAGE", Path: fmt.Sprintf("/a2ui/%d/version", i), Message: "a2ui message version must be 1.0"}
		}
		if i == 0 {
			if msg.CreateSurface == nil || msg.UpdateComponents != nil {
				return nil, &ValidationError{Code: "INVALID_MESSAGE", Path: "/a2ui/0", Message: "first message must be createSurface"}
			}
			if msg.CreateSurface.CatalogID != CatalogID {
				return nil, &ValidationError{Code: "INVALID_CATALOG", Path: "/a2ui/0/createSurface/catalogId", Message: fmt.Sprintf("expected catalogId %q, got %q", CatalogID, msg.CreateSurface.CatalogID)}
			}
			if msg.CreateSurface.SurfaceID == "" {
				return nil, &ValidationError{Code: "INVALID_SURFACE", Path: "/a2ui/0/createSurface/surfaceId", Message: "surfaceId is required"}
			}
			surface = msg.CreateSurface.SurfaceID
			joined = openuilang.Overlay(joined, strings.Join(msg.CreateSurface.Components, "\n"))
		} else {
			if msg.UpdateComponents == nil || msg.CreateSurface != nil {
				return nil, &ValidationError{Code: "INVALID_MESSAGE", Path: fmt.Sprintf("/a2ui/%d", i), Message: "subsequent messages must be updateComponents"}
			}
			if msg.UpdateComponents.SurfaceID != surface {
				return nil, &ValidationError{Code: "INVALID_SURFACE", Path: fmt.Sprintf("/a2ui/%d/updateComponents/surfaceId", i), Message: "surfaceId must match createSurface"}
			}
			joined = openuilang.Overlay(joined, strings.Join(msg.UpdateComponents.Components, "\n"))
		}
	}

	return &ParsedView{
		Raw:        append([]byte(nil), raw...),
		Envelope:   env,
		Statements: SplitStatementStrings(joined),
		JoinedText: joined,
	}, nil
}

// BuildCompactedEnvelope wraps statements and sources in a single createSurface
// Mark Go Go v3 envelope, keeping sidecars strictly bounded well under 1 MiB.
func BuildCompactedEnvelope(statements []string, sources map[string]SourceRef, model, request string, now time.Time) ([]byte, error) {
	if now.IsZero() {
		now = time.Now()
	}
	if sources == nil {
		sources = map[string]SourceRef{}
	}
	env := Envelope{
		Version:     ViewVersion,
		Language:    ViewLanguage,
		GeneratedAt: now.UTC().Format(time.RFC3339),
		Model:       model,
		Request:     request,
		Sources:     sources,
		A2UI: []A2UIMessage{
			{
				Version: A2UIVersion,
				CreateSurface: &CreateSurface{
					SurfaceID:  SurfaceID,
					CatalogID:  CatalogID,
					Components: statements,
				},
			},
		},
	}
	data, err := json.MarshalIndent(env, "", "  ")
	if err != nil {
		return nil, err
	}
	data = append(data, '\n')
	if len(data) > MaxViewBytes {
		return nil, &ValidationError{
			Code:    "VIEW_TOO_LARGE",
			Path:    "/",
			Message: fmt.Sprintf("compacted view is %d bytes (limit %d)", len(data), MaxViewBytes),
			Hint:    "Reduce data points or split into fewer modules.",
		}
	}
	return data, nil
}

// ErrHashConflict signals that the sidecar changed since the caller read it.
var ErrHashConflict = errors.New("view hash conflict")

// CommitViewFile atomically writes newBytes to viewPath with optional CAS check
// (`expectHash`), preserves the prior file at Mark Go Go's exact `.genui.prev.json`
// undo path, writes a revision snapshot into `.deepread/history/`, and returns
// a rollback closure so callers can undo the commit if subsequent metadata
// writes fail.
func CommitViewFile(docPath string, newBytes []byte, expectHash string, revision int) (func(), error) {
	viewPath := bundle.ViewPath(docPath)
	prevPath := bundle.PrevViewPath(viewPath)
	current, err := os.ReadFile(viewPath)
	hadView := err == nil
	if err != nil && !errors.Is(err, fs.ErrNotExist) {
		return nil, err
	}
	if expectHash != "" {
		if !hadView || bundle.SHA256Hex(current) != strings.ToLower(strings.TrimSpace(expectHash)) {
			return nil, fmt.Errorf("%w: view changed since read (expected %s)", ErrHashConflict, expectHash)
		}
	}

	var histPath string
	var oldHist []byte
	hadHist := false
	if revision > 0 {
		histPath = filepath.Join(bundle.MetaDir(docPath), "history", fmt.Sprintf("r%d.genui.json", revision))
		if prevHist, rErr := os.ReadFile(histPath); rErr == nil {
			oldHist = prevHist
			hadHist = true
		}
		if err := bundle.WriteFileAtomic(histPath, newBytes, 0o644); err != nil {
			return nil, fmt.Errorf("write revision snapshot: %w", err)
		}
	}
	undoHist := func() {
		if histPath == "" {
			return
		}
		if hadHist {
			_ = bundle.WriteFileAtomic(histPath, oldHist, 0o644)
		} else {
			_ = os.Remove(histPath)
		}
	}

	oldBackup, backupErr := os.ReadFile(prevPath)
	hadBackup := backupErr == nil
	if hadView {
		if err := bundle.WriteFileAtomic(prevPath, current, 0o644); err != nil {
			undoHist()
			return nil, err
		}
		if err := bundle.WriteFileAtomic(viewPath, newBytes, 0o644); err != nil {
			if hadBackup {
				_ = bundle.WriteFileAtomic(prevPath, oldBackup, 0o644)
			} else {
				_ = os.Remove(prevPath)
			}
			undoHist()
			return nil, err
		}
		rollback := func() {
			_ = bundle.WriteFileAtomic(viewPath, current, 0o644)
			if hadBackup {
				_ = bundle.WriteFileAtomic(prevPath, oldBackup, 0o644)
			} else {
				_ = os.Remove(prevPath)
			}
			undoHist()
		}
		return rollback, nil
	}

	if err := bundle.WriteFileAtomic(viewPath, newBytes, 0o644); err != nil {
		undoHist()
		return nil, err
	}
	rollback := func() {
		_ = os.Remove(viewPath)
		undoHist()
	}
	return rollback, nil
}

// SplitStatementStrings splits joined openui-lang source into individual
// statement strings (preserving multi-line statements cleanly).
func SplitStatementStrings(text string) []string {
	var out []string
	// openuilang.Names returns statement names in source order; we extract each
	// top-level assignment using the same balanced delimiter scan.
	norm := strings.ReplaceAll(strings.TrimSpace(text), "\r\n", "\n")
	if norm == "" {
		return []string{}
	}
	var cur bytes.Buffer
	depth := 0
	var inStr byte
	esc := false
	flush := func() {
		s := strings.TrimSpace(cur.String())
		if s != "" {
			out = append(out, s)
		}
		cur.Reset()
	}
	for i := 0; i < len(norm); i++ {
		c := norm[i]
		if esc {
			cur.WriteByte(c)
			esc = false
			continue
		}
		if inStr != 0 {
			cur.WriteByte(c)
			if c == '\\' {
				esc = true
			} else if c == inStr {
				inStr = 0
			}
			continue
		}
		switch c {
		case '"', '\'':
			inStr = c
			cur.WriteByte(c)
		case '(', '[', '{':
			depth++
			cur.WriteByte(c)
		case ')', ']', '}':
			if depth > 0 {
				depth--
			}
			cur.WriteByte(c)
		case '\n':
			if depth == 0 {
				flush()
			} else {
				cur.WriteByte(' ')
			}
		default:
			cur.WriteByte(c)
		}
	}
	flush()
	return out
}
