# Upstream Attribution / 上游归属说明

The pure-Go headless packages under `internal/openuilang`, `internal/genuikit`, and `internal/markdown` are synced from `Mark Go Go` (`github.com/Bayern99/mark-go-go`, MIT License) at pinned commit `f203c83`.

- `internal/openuilang`: OpenUI Lang 1.0 parser, evaluator, session, merger, and conformance fixtures (see `internal/openuilang/testdata/SOURCE.md`, originally derived from `thesysdev/openui`, MIT License).
- `internal/genuikit`: Single authoritative `catalog.json` and function definitions.
- `internal/markdown`: Heading section extraction, `fnv1a32` hashing, and attributed `<!-- note ... -->` parsing.

`deepread` maintains strict one-way compatibility with `Mark Go Go` v3 (`language: "openui-lang/1.0"`, `catalogId: "markgogo.dev:genui/v3"`, `.genui.prev.json` backup naming) without modifying the upstream `Mark Go Go` repository.
