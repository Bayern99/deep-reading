//go:build !unix

package bundle

import (
	"fmt"
	"io"
	"os"
)

// ReadRegularFileInRoot opens relPath inside root, verifies it is a regular file,
// and reads at most limit bytes.
func ReadRegularFileInRoot(root *os.Root, relPath string, limit int64) ([]byte, error) {
	info, err := root.Stat(relPath)
	if err != nil {
		return nil, err
	}
	if !info.Mode().IsRegular() {
		return nil, fmt.Errorf("%s is not a regular file", relPath)
	}
	file, err := root.Open(relPath)
	if err != nil {
		return nil, err
	}
	defer file.Close()
	info, err = file.Stat()
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

func openRegularLockInRoot(root *os.Root, relPath string) (*os.File, error) {
	if info, err := root.Stat(relPath); err == nil && !info.Mode().IsRegular() {
		return nil, fmt.Errorf("%s is not a regular file", relPath)
	}
	file, err := root.OpenFile(relPath, os.O_CREATE|os.O_RDONLY, 0o644)
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
