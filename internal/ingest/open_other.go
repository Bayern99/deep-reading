//go:build !unix

package ingest

import (
	"fmt"
	"os"
)

func openRegularFile(path string) (*os.File, error) {
	info, err := os.Stat(path)
	if err != nil {
		return nil, err
	}
	if !info.Mode().IsRegular() {
		return nil, fmt.Errorf("%w: %s is not a regular file", ErrUnsafeArchive, path)
	}
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	fInfo, err := f.Stat()
	if err != nil {
		_ = f.Close()
		return nil, err
	}
	if !fInfo.Mode().IsRegular() {
		_ = f.Close()
		return nil, fmt.Errorf("%w: %s is not a regular file", ErrUnsafeArchive, path)
	}
	return f, nil
}

func openRootRegularFile(root *os.Root, relPath string) (*os.File, error) {
	info, err := root.Stat(relPath)
	if err != nil {
		return nil, err
	}
	if !info.Mode().IsRegular() {
		return nil, fmt.Errorf("%w: %s is not a regular file", ErrUnsafeArchive, relPath)
	}
	f, err := root.Open(relPath)
	if err != nil {
		return nil, err
	}
	fInfo, err := f.Stat()
	if err != nil {
		_ = f.Close()
		return nil, err
	}
	if !fInfo.Mode().IsRegular() {
		_ = f.Close()
		return nil, fmt.Errorf("%w: %s is not a regular file", ErrUnsafeArchive, relPath)
	}
	return f, nil
}
