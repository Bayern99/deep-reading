.PHONY: build test race vet check cross-build

LDFLAGS ?= -s -w

build:
	CGO_ENABLED=0 go build -trimpath -ldflags "$(LDFLAGS)" -o dist/deepread ./cmd/deepread

test:
	CGO_ENABLED=0 go test -count=1 ./...

race:
	go test -race -count=1 ./...

vet:
	CGO_ENABLED=0 go vet ./...

check: vet test race
	python3 scripts/check_distribution.py --staged

cross-build:
	mkdir -p dist
	GOOS=darwin  GOARCH=arm64 CGO_ENABLED=0 go build -trimpath -ldflags "$(LDFLAGS)" -o dist/deepread-darwin-arm64 ./cmd/deepread
	GOOS=linux   GOARCH=amd64 CGO_ENABLED=0 go build -trimpath -ldflags "$(LDFLAGS)" -o dist/deepread-linux-amd64 ./cmd/deepread
	GOOS=linux   GOARCH=arm64 CGO_ENABLED=0 go build -trimpath -ldflags "$(LDFLAGS)" -o dist/deepread-linux-arm64 ./cmd/deepread
	GOOS=windows GOARCH=amd64 CGO_ENABLED=0 go build -trimpath -ldflags "$(LDFLAGS)" -o dist/deepread-windows-amd64.exe ./cmd/deepread
