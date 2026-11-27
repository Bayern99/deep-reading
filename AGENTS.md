# Agent Instructions / Agent 指示

`deepread` is a headless, single-binary Go capability layer for sparse, prose-preserving deep reading of Markdown and EPUB long-form texts. The host agent is the editorial brain; this repository provides the deterministic Go runtime and [SKILL.md](SKILL.md). Follow [ADR 0006](docs/adr/0006-headless-go-deepread-engine.md).

`deepread` 是一个无头、纯 Go 单二进制的长文深读能力层，支持 Markdown 与 EPUB 的原文保真与稀疏认知支架。宿主 Agent 是编辑大脑，本仓库提供确定性 Go 运行时与 [SKILL.md](SKILL.md)。请遵循 [ADR 0006](docs/adr/0006-headless-go-deepread-engine.zh-CN.md)。

## Navigate / 导航

- Quickstart and CLI overview: [README.md](README.md) · [README.zh-CN.md](README.zh-CN.md)
- Host-agent operating manual (8-command workflow & exit codes): [SKILL.md](SKILL.md)
- Upstream `Mark Go Go` (`f203c83`) sync attribution: [UPSTREAM.md](UPSTREAM.md)
- Architecture decision record: [ADR 0006](docs/adr/0006-headless-go-deepread-engine.md) · [ADR 0006 (中文)](docs/adr/0006-headless-go-deepread-engine.zh-CN.md)

## Repository Layout / 代码布局

- `cmd/deepread/` — Thin 8-command CLI (`ingest`, `inspect`, `prepare`, `catalog`, `write`, `note add`, `patch`, `export`), structured stderr JSON errors, stable exit codes `0..5`.
- `internal/ingest/` — Pure-Go Markdown and EPUB 2/3 secure two-phase ingestion (`os.OpenRoot`, non-blocking regular-file opens, zip-slip/zip-bomb caps, atomic sibling staging, one chapter per isolated directory).
- `internal/bundle/` — Single-doc-per-dir manifest, note ledger, advisory locks (`flock_unix.go`/`flock_other.go`), synthetic H2 `prepare`, attributed `note add`, and `inspect`.
- `internal/view/` — Narrowed 10-primitive reading catalog, zero-fault strict validation, anti-cliché guardrails, and compacted CAS `patch` (`.genui.json`, `.genui.prev.json`, `.deepread/history/`).
- `internal/export/` — Zero-JS 390px-first magazine HTML renderer, pure SVG bar/line charts, streaming `budgetWriter`, dual inline/external raster image modes, and protected-path collision guards.
- `internal/openuilang/`, `internal/genuikit/`, `internal/markdown/` — Synced pure-Go headless packages from `Mark Go Go` (`f203c83`). Keep upstream files clean; place DeepRead extensions in `deepread_ext.go`.

## Engineering Invariants / 工程红线

- **Zero GUI, zero CGO, zero external runtime binaries**: Always keep `CGO_ENABLED=0` cross-builds working across `darwin/arm64`, `linux/amd64`, and `windows/amd64`.
- **One-way `Mark Go Go` v3 compatibility**: Never break `version: 3`, `language: "openui-lang/1.0"`, `catalogId: "markgogo.dev:genui/v3"`, `.genui.prev.json`, `fnv1a32` hashes, or attributed `<!-- note ... -->` parsing. Do not modify the separate `Mark Go Go` repository.
- **No private books/articles in the tool repo**: Keep real EPUBs, articles, generated bundles, and HTML outputs outside Git tracking. Never bypass `scripts/check_distribution.py`.
- **Verify changes**: Run `CGO_ENABLED=0 go test -count=1 ./...` and `go test -race -count=1 ./...` after code edits; run `python3 scripts/check_distribution.py --staged` before committing.
- **Bilingual docs & handoff**: Reply to Jerry in Chinese. Keep commit messages and code comments in English. Maintain user-facing documentation in English and Chinese. Ask Jerry before major refactors, permanent deletion of important data, Git history rewrites, merges to `main`, or remote pushes.
