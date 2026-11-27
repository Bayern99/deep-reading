package bundle

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
)

// MaxViewBytes matches Mark Go Go's 1 MiB sidecar limit.
const MaxViewBytes = 1 << 20

var (
	// ErrNotFound marks missing sections, nodes, or bundle targets (CLI exit 4).
	ErrNotFound = errors.New("not found")
	// ErrDocMismatch rejects mixing a second document into an already-bound bundle dir.
	ErrDocMismatch = errors.New("bundle document mismatch")
)

// FilePerm returns path's existing permission bits, defaulting to 0o644.
func FilePerm(path string) os.FileMode {
	if info, err := os.Stat(path); err == nil {
		return info.Mode().Perm()
	}
	return 0o644
}

// WithDocRLock acquires a shared advisory lock whenever the bundle's .deepread
// directory exists (creating .lock if needed inside an existing .deepread/),
// ensuring readers observe a consistent snapshot without creating .deepread/ on
// virgin read-only documents.
func WithDocRLock(docPath string, fn func() error) error {
	meta := MetaDir(docPath)
	if _, err := os.Stat(meta); errors.Is(err, fs.ErrNotExist) {
		return fn()
	} else if err != nil {
		return fmt.Errorf("stat bundle metadata dir: %w", err)
	}
	lockPath := filepath.Join(meta, ".lock")
	f, err := os.OpenFile(lockPath, os.O_CREATE|os.O_RDONLY, 0o644)
	if err != nil {
		return fmt.Errorf("open bundle read lock: %w", err)
	}
	defer f.Close()
	unlock, err := lockFileShared(f)
	if err != nil {
		return fmt.Errorf("acquire bundle read lock: %w", err)
	}
	defer unlock()
	return fn()
}

// WithDocRLockInRoot acquires a shared advisory lock strictly inside root,
// using non-blocking regular-file opens so lock access cannot escape root or block on a FIFO.
func WithDocRLockInRoot(root *os.Root, relDocPath string, fn func() error) error {
	relDir := filepath.ToSlash(filepath.Dir(relDocPath))
	metaRel := ".deepread"
	if relDir != "" && relDir != "." {
		metaRel = relDir + "/.deepread"
	}
	info, err := root.Stat(metaRel)
	if errors.Is(err, fs.ErrNotExist) {
		return fn()
	}
	if err != nil {
		return fmt.Errorf("stat bundle metadata dir: %w", err)
	}
	if !info.IsDir() {
		return fmt.Errorf("bundle metadata path %q is not a directory", metaRel)
	}
	f, err := openRegularLockInRoot(root, metaRel+"/.lock")
	if err != nil {
		return fmt.Errorf("open bundle read lock: %w", err)
	}
	defer f.Close()
	unlock, err := lockFileShared(f)
	if err != nil {
		return fmt.Errorf("acquire bundle read lock: %w", err)
	}
	defer unlock()
	return fn()
}

// MetaDir returns the .deepread metadata directory alongside a document.
func MetaDir(docPath string) string {
	return filepath.Join(filepath.Dir(docPath), ".deepread")
}

// WriteFileAtomic writes data via a temporary file in the target directory and
// renames it into place so readers never observe partial writes.
func WriteFileAtomic(path string, data []byte, mode os.FileMode) error {
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	tmp, err := os.CreateTemp(dir, ".deepread-tmp-*")
	if err != nil {
		return err
	}
	tmpName := tmp.Name()
	cleanup := true
	defer func() {
		if cleanup {
			_ = os.Remove(tmpName)
		}
	}()
	if _, err := tmp.Write(data); err != nil {
		_ = tmp.Close()
		return err
	}
	if err := tmp.Chmod(mode); err != nil {
		_ = tmp.Close()
		return err
	}
	if err := tmp.Sync(); err != nil {
		_ = tmp.Close()
		return err
	}
	if err := tmp.Close(); err != nil {
		return err
	}
	if err := os.Rename(tmpName, path); err != nil {
		return err
	}
	cleanup = false
	return nil
}

// WithDocLock serializes cross-process mutations for a bundle directory using
// an exclusive advisory file lock on .deepread/.lock.
func WithDocLock(docPath string, fn func() error) error {
	meta := MetaDir(docPath)
	if err := os.MkdirAll(meta, 0o755); err != nil {
		return err
	}
	lockPath := filepath.Join(meta, ".lock")
	f, err := os.OpenFile(lockPath, os.O_CREATE|os.O_RDWR, 0o644)
	if err != nil {
		return fmt.Errorf("open bundle lock: %w", err)
	}
	defer f.Close()
	unlock, err := lockFileExclusive(f)
	if err != nil {
		return fmt.Errorf("acquire bundle lock: %w", err)
	}
	defer unlock()
	return fn()
}

// SHA256Hex returns the lowercase hex SHA-256 digest of data.
func SHA256Hex(data []byte) string {
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}
