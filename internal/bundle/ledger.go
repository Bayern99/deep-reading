package bundle

import (
	"encoding/json"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"time"
)

const LedgerSchemaVersion = 1

const (
	NoteStatusOpen     = "open"
	NoteStatusResolved = "resolved"
)

// Ledger tracks reader notes and external message IDs so `inspect` can report
// exact pending tasks without re-triggering already processed notes.
type Ledger struct {
	SchemaVersion int           `json:"schemaVersion"`
	NextNoteSeq   int           `json:"nextNoteSeq"`
	Notes         []LedgerEntry `json:"notes"`
}

// LedgerEntry records one tracked reader note.
type LedgerEntry struct {
	NoteID            string `json:"noteId"`
	MsgID             string `json:"msgId,omitempty"`
	Node              string `json:"node,omitempty"`
	SectionHeading    string `json:"sectionHeading"`
	SectionOccurrence int    `json:"sectionOccurrence"`
	BaseRev           int    `json:"baseRev,omitempty"`
	Text              string `json:"text"`
	Status            string `json:"status"`
	CreatedAt         string `json:"createdAt"`
	ResolvedAt        string `json:"resolvedAt,omitempty"`
}

// LedgerPath returns .deepread/ledger.json for docPath.
func LedgerPath(docPath string) string {
	return filepath.Join(MetaDir(docPath), "ledger.json")
}

// LoadLedger reads .deepread/ledger.json or returns an empty ledger.
func LoadLedger(docPath string) (Ledger, error) {
	raw, err := os.ReadFile(LedgerPath(docPath))
	if errors.Is(err, fs.ErrNotExist) {
		return Ledger{SchemaVersion: LedgerSchemaVersion, NextNoteSeq: 1}, nil
	}
	if err != nil {
		return Ledger{}, err
	}
	var l Ledger
	if err := json.Unmarshal(raw, &l); err != nil {
		return Ledger{}, err
	}
	if l.SchemaVersion == 0 {
		l.SchemaVersion = LedgerSchemaVersion
	}
	if l.NextNoteSeq < 1 {
		l.NextNoteSeq = len(l.Notes) + 1
	}
	return l, nil
}

// SaveLedger atomically writes .deepread/ledger.json.
func SaveLedger(docPath string, l Ledger) error {
	if l.SchemaVersion == 0 {
		l.SchemaVersion = LedgerSchemaVersion
	}
	data, err := json.MarshalIndent(l, "", "  ")
	if err != nil {
		return err
	}
	return WriteFileAtomic(LedgerPath(docPath), append(data, '\n'), 0o644)
}

// FindByMsgID returns an existing ledger entry for an external chat message ID.
func (l *Ledger) FindByMsgID(msgID string) (*LedgerEntry, bool) {
	if msgID == "" {
		return nil, false
	}
	for i := range l.Notes {
		if l.Notes[i].MsgID == msgID {
			return &l.Notes[i], true
		}
	}
	return nil, false
}

// Resolve marks a note as resolved by ID.
func (l *Ledger) Resolve(noteID string, now time.Time) error {
	for i := range l.Notes {
		if l.Notes[i].NoteID == noteID {
			l.Notes[i].Status = NoteStatusResolved
			l.Notes[i].ResolvedAt = now.UTC().Format(time.RFC3339)
			return nil
		}
	}
	return fmt.Errorf("note %q not found in ledger", noteID)
}
