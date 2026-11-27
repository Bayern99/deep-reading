//go:build unix

package bundle

import (
	"fmt"
	"io"
	"os"
	"syscall"
)

// ReadRegularFileInRoot opens relPath inside root with O_NONBLOCK so FIFOs
// cannot block the caller, verifies it is a regular file, and reads at most limit bytes.
func ReadRegularFileInRoot(root *os.Root, relPath string, limit int64) ([]byte, error) {
	file, err := root.OpenFile(relPath, os.O_RDONLY|syscall.O_NONBLOCK, 0)
	if err != nil {
		return nil, err
	}
	defer file.Close()
	info, err := file.Stat()
	if err != nil {
		return nil, err
	}
	if !info.Mode().IsRegular() {
		return nil, fmt.Errorf("%s is not a regular file", relPath)
	}
	if limit > 0 {
		data, err := io.ReadAll(io.LimitReader(file, limit+1))
		if err != nil {
			return nil, err
		}
		if int64(len(data)) > limit {
			return nil, fmt.Errorf("%s exceeds %d bytes", relPath, limit)
		}
		return data, nil
	}
	return io.ReadAll(file)
}

// openRegularLockInRoot opens or creates a lock file inside root with O_NONBLOCK
// and verifies it is a regular file so FIFOs/symlinks cannot block or escape root.
func openRegularLockInRoot(root *os.Root, relPath string) (*os.File, error) {
	file, err := root.OpenFile(relPath, os.O_CREATE|os.O_RDONLY|syscall.O_NONBLOCK, 0o644)
	if err != nil {
		return nil, err
	}
	info, err := file.Stat()
	if err != nil {
		file.Close()
		return nil, err
	}
	if !info.Mode().IsRegular() {
		file.Close()
		return nil, fmt.Errorf("%s is not a regular file", relPath)
	}
	return file, nil
}
