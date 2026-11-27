//go:build !unix

package bundle

import (
	"os"
	"sync"
)

var nonUnixLockMu sync.RWMutex

func lockFileExclusive(_ *os.File) (func(), error) {
	nonUnixLockMu.Lock()
	return nonUnixLockMu.Unlock, nil
}

func lockFileShared(_ *os.File) (func(), error) {
	nonUnixLockMu.RLock()
	return nonUnixLockMu.RUnlock, nil
}
