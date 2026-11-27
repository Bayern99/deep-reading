# DeepRead (`deepread`)

[中文说明](README.zh-CN.md) · [Host Agent Manual (`SKILL.md`)](SKILL.md) · [ADR 0006](docs/adr/0006-headless-go-deepread-engine.md) · [ADR 0007](docs/adr/0007-dual-face-genui-and-translation-layer.md)

A headless, single-binary Go deep-reading engine and agent skill for Markdown and EPUB long-form texts. Designed to be installed and operated directly by AI agents (cloud computers, Muse, group bots, Claude Code, Codex, Pi, Antigravity) to deliver **one** offline HTML reader: a **full-information structured reading canvas** (`dual` default — zero dense walls of prose while preserving ~95%+ of facts, actors, quotes, original charts, causal SVGs, interactive sliders/toggles, tables, and timelines) paired with the immutable verbatim prose + parallel translation layer (`中文 / EN / 双语`), plus optional `--face inline` (paragraph-interleaved prose) and `--face hybrid` (masthead hero + paragraph-interleaved prose), with one-way `Mark Go Go` v3 compatibility.

> Built as a clean-slate pure-Go rewrite (`v0.2.0`), replacing an earlier retired Python prototype; `v0.3.0` adds the translation layer, the canvas profile, and multi-chapter book export.

---

## For Humans: Send This Prompt to Your Agent

You do not need to install this manually. Copy and send the prompt below to your cloud-computer agent or coding agent:

```text
Please install and configure `deepread` from https://github.com/Bayern99/deep-reading on this machine.
Read the repository README and follow the "For Agents: Self-Install & Verification Runbook" section step by step:
1. Download the right `deepread` static binary for this OS/arch from the latest GitHub Release (verify SHA-256) and put it on PATH.
2. Install `SKILL.md` into your active skills directory so you can use `deepread` in future sessions.
3. Run the smoke test in a temporary directory and clean it up.
4. Report back the binary path, skill path, and smoke-test result. Do not ask me to run commands manually unless network access is blocked.
```

---

## For Agents: Self-Install & Verification Runbook

Read this section carefully and execute it end to end. Do not guess flags or skip verification.

### Done Criteria

Setup is complete only when all three hold:
1. `deepread` is executable on `PATH` (e.g. `~/.local/bin/deepread`) and `deepread catalog` exits `0`.
2. `SKILL.md` is installed verbatim in the host agent's skill directory.
3. The temporary-directory smoke test below exits `0`, produces a non-empty HTML file, and cleans up after itself.

### Step 1: Detect Platform

Map `uname -s` and `uname -m` to the exact release binary name:

| OS (`uname -s`) | Arch (`uname -m`) | Release asset |
|---|---|---|
| `Linux` | `x86_64` / `amd64` | `deepread-linux-amd64` |
| `Linux` | `aarch64` / `arm64` | `deepread-linux-arm64` |
| `Darwin` | `arm64` | `deepread-darwin-arm64` |
| Windows | `amd64` | `deepread-windows-amd64.exe` |

Check if already installed before downloading:

```bash
command -v deepread && deepread catalog >/dev/null 2>&1 && echo "ALREADY_INSTALLED"
```

### Step 2: Install Binary and `SKILL.md`

Pick the **first** available path below.

#### Path A — Direct Download from Public GitHub Release (Preferred, No Go or `gh` Auth Required)

Download the latest release binary, `SKILL.md`, and `SHA256SUMS.txt` directly via `curl` (or `gh release download` if preferred):

```bash
ASSET="deepread-linux-amd64" # Replace using the platform table above
BASE="https://github.com/Bayern99/deep-reading/releases/latest/download"
TMP_DL="$(mktemp -d)"

curl -fsSL "$BASE/$ASSET" -o "$TMP_DL/$ASSET"
curl -fsSL "$BASE/SKILL.md" -o "$TMP_DL/SKILL.md"
curl -fsSL "$BASE/SHA256SUMS.txt" -o "$TMP_DL/SHA256SUMS.txt"

# Verify checksum (Linux: sha256sum, macOS: shasum -a 256)
(
  cd "$TMP_DL"
  if command -v sha256sum >/dev/null 2>&1; then
    grep -E "  (${ASSET}|SKILL\.md)$" SHA256SUMS.txt | sha256sum -c -
  else
    grep -E "  (${ASSET}|SKILL\.md)$" SHA256SUMS.txt | shasum -a 256 -c -
  fi
)

mkdir -p "$HOME/.local/bin"
install -m 0755 "$TMP_DL/$ASSET" "$HOME/.local/bin/deepread"
export PATH="$HOME/.local/bin:$PATH"
```

Persist `$HOME/.local/bin` on `PATH` in the shell profile (e.g. `~/.bashrc` or `~/.zshrc`) if it is not already present.

#### Path B — Build from Source (Fallback when Go Is Installed)

If `curl` to GitHub Releases is unavailable and the repository is cloned locally with `go` installed:

```bash
mkdir -p "$HOME/.local/bin"
CGO_ENABLED=0 go build -trimpath -ldflags "-s -w" -o "$HOME/.local/bin/deepread" ./cmd/deepread
export PATH="$HOME/.local/bin:$PATH"
```

#### If Neither Path Works

Stop immediately and tell the user which prerequisite is missing:
- Either enable outbound access to `github.com` (or download from `https://github.com/Bayern99/deep-reading/releases/latest`), **or**
- Send the release binary (`$ASSET`) and `SKILL.md` directly.

### Step 3: Register `SKILL.md`

Place `SKILL.md` verbatim into your host's skill directory (check which skill directory your runtime actually scans; do not overwrite unrelated skills):

- Claude Code: `~/.claude/skills/deepread/SKILL.md`
- Codex: `~/.codex/skills/deepread/SKILL.md`
- Cross-agent / generic hosts (Muse, Pi, OpenClaw, Antigravity, etc.): check your host's configured skills directory (often `~/.agents/skills/deepread/SKILL.md` or `<workspace>/skills/deepread/SKILL.md`).

Never summarize or truncate `SKILL.md`—keep the full file intact. Remove `$TMP_DL` once copied.

### Step 4: Mandatory Smoke Test

Run this exact self-contained check before reporting completion:

```bash
TMP_SMOKE="$(mktemp -d)"
cat > "$TMP_SMOKE/sample.md" <<'EOF'
# Smoke Test

## Why Sparse Reading Works

Long prose loses coherence when rewritten into bullet cards. Keeping the original paragraphs untouched while adding one focused diagram preserves the author's voice and clarifies structure.
EOF

deepread ingest "$TMP_SMOKE/sample.md" -o "$TMP_SMOKE/bundle" >/dev/null
deepread catalog >/dev/null
cat <<'EOF' | deepread write "$TMP_SMOKE/bundle/sample.md" --statements - --source s1="Why Sparse Reading Works"#1 >/dev/null
root = Col([mode_check])
mode_check = Source(["s1"], [Title("Reading Mode Comparison", "md"), Table(["Mode", "Prose", "Scaffold"], [["Summary card", "Rewritten", "Redundant"], ["DeepRead", "Untouched", "Sparse table"]])])
EOF
deepread export "$TMP_SMOKE/bundle/sample.md" -o "$TMP_SMOKE/out.html" >/dev/null
test -s "$TMP_SMOKE/out.html" && echo "SMOKE_TEST_OK"
rm -rf "$TMP_SMOKE"
```

### Step 5: Report Back to the User

Reply concisely with:
1. Binary path (`which deepread`) and verified asset name.
2. Installed `SKILL.md` path.
3. Smoke-test result (`SMOKE_TEST_OK`).
4. One line letting the user know they can now send any `.md` article or `.epub` book to start deep reading.

---

## Operating Contract (Summary)

Read [SKILL.md](SKILL.md) in full before running your first real deep-reading task. Core invariants:

- **Step 0 reading contract**: decide `targetLang`, `mode`, `scope`, and delivery (**one** unified offline HTML) before writing anything. If the user already named a language, adopt it immediately and do not ask again.
- **One document per bundle directory**: Every article or EPUB chapter owns its own directory (`<doc>.md`, `assets/`, `.deepread/`). Never mix two documents in one directory.
- **Prose-by-Reference**: Original prose paragraphs are never rewritten, and translations never overwrite them; GenUI scaffolds live in `.<doc>.genui.json` (full 50-component canvas by default, `--profile margin` for the legacy 10 primitives) and translations live in `.deepread/translations/<lang>.json`.
- **Parallel translation layer**: `deepread blocks` lists the live units, `deepread translate` stores `{id, sourceHash, text}` batches from JSON, `{"entries":[…]}` or JSONL, and `inspect` reports `coveragePct`/`staleBlocks`. Export refuses translated/bilingual output until coverage is 100% with zero stale blocks.
- **Two-phase EPUB, one unified HTML**: `deepread ingest book.epub -o <dir>` extracts `index.md`, `book.json`, and isolated chapter bundles under `chapters/<NN>-<slug>/chapter.md`; deliver with `deepread export --book <dir> --chapters <spec> -o <one>.html`.
- **Dual-face offline reader**: `深读 ↔ 原文` switching, `查看原文 ↗` paragraph anchors from `--cite`, reactive islands pre-rendered by Go, and a single constant runtime script pinned by a SHA-256 CSP hash (`--no-js` for a static page). Images inline under hard byte budgets (512 KiB/image, 1.5 MiB page) or ship beside the HTML with `--external-assets`.
- **Short-code feedback loop**: Every module shows `<bundleId>·<statement>@r<rev>` so readers can reply in chat and trigger idempotent `note add` + compacted CAS `patch`.

```bash
deepread ingest    <article.md|book.epub> -o <bundle-dir> [--lang <bcp47>] [--source-lang <bcp47>] [--mode original|translated|bilingual]
deepread inspect   <doc.md> [--heading <h> [--occurrence <n>] | --lines <a:b>]
deepread prepare   <doc.md> --breaks <file|->
deepread catalog   [--profile canvas|margin]
deepread blocks    <doc.md>
deepread write     <doc.md> --statements <file|-> --source <id>="<Heading>"[#<occ>] [--cite <stmt>:<srcId>=<blockId>] [--profile canvas|margin]
deepread translate <doc.md> --lang <bcp47> --input <file|-> [--mode translated|bilingual]
deepread note add  <doc.md> (--node <stmt> [--source <srcId>] | --heading <h>) --text "<note>" [--rev <r>] [--msg-id <id>]
deepread patch     <doc.md> --replace <stmt> --expect-hash <sha256> --statements <file|-> [--resolve-note <id>]
deepread export    <doc.md> -o <out.html>                     # or: <doc1.md> <doc2.md> … / --book <dir> --chapters <spec>
```

## Development & Verification

```bash
make check        # CGO_ENABLED=0 vet, test, -race, and staged distribution check
make cross-build  # Static binaries for darwin/arm64, linux/amd64, linux/arm64, windows/amd64
```

See [AGENTS.md](AGENTS.md) for contributor invariants, [SKILL.md](SKILL.md) for the complete host-agent manual and exit codes (`0`–`5`), [ADR 0007](docs/adr/0007-dual-face-genui-and-translation-layer.md) for the dual-face/translation decisions, and [UPSTREAM.md](UPSTREAM.md) for `Mark Go Go` (`f203c83`) attribution.
