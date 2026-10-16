# Data preservation and Git policy

## Data classes

| Class | Examples | Treatment |
|---|---|
| Primary Vector Signals and bilingual units | issue `native.json`, inventory, reviewed translations, QA notes, issue translation glossary | Preserve and review as content. Keep in the private project history; take an external backup before any content migration. |
| Verified media | union-cropped print charts, recovered figures, issue `assets/` | Preserve, track deliberately and retain source attribution. |
| Issue Artifact compiles | `/tmp` HTML, repo-root `wsj-*.html`, `gate-report.json`, `oracle-certification.json` | Workspace output, not source. Do not treat a compile snapshot as approved narrative. |
| Dated evidence (Studio-era) | `2026-10-12/` Final Source, `editorial-artifacts/` versions, `_queue.json`, `dist/` snapshots, experiments, dated reports | Durable primary evidence of the superseded pipeline, not a regenerable cache and not a daily runner. Keep existing data; inspect model output/notes for credentials before adding a version to Git. |
| Local configuration/cache | `.venv/`, `.env*`, bytecode, test/tool caches, logs | Ignored. `.env.example` is the tracked credential-free exception. Credentials belong in environment variables or a secret manager. |
| Source PDF | An externally supplied issue PDF | Not in the repository. Retain an external protected original; approve its storage/distribution separately rather than adding it incidentally. Pins currently live in `render/tracer/compose.py`. |

Newspaper data and historical model outputs are not disposable fixtures. Re-running a Studio-era generation may incur cost and does not reproduce the same artifact. The Issue Artifact path does not keep a per-article version store.

## Safe local Git work

`make hooks` installs the tracked hooks: `commit-msg` refuses to commit queue state, the artifact index or a `dist/` snapshot unless the commit message carries the `[data]` marker (or `WSJ_ALLOW_DATA_COMMIT=1` is set); `pre-push` runs `make check` (tracer tests + `--fast` smoke). Hooks live in `.git/hooks` and are per-checkout, so run `make hooks` after cloning.

Inspect `git status` before editing. Existing staged/unstaged/untracked changes belong to the user; preserve them. Review explicit paths before staging. Avoid blanket `git add .`, `git clean`, reset/restore of the entire tree, or removing ignored directories as cleanup.

`.gitignore` covers new issue `dist/` snapshots, environments, credentials and transient queue-write files. It intentionally does not hide historical source, artifact versions, experiments or dated evidence. `.gitattributes` declares text line endings and binary media; no bulk renormalization was performed.

History currently contains many HTML/image versions from the Studio era. Preserve them. The frozen runtime is git branch `archive/studio-phase1-7`. History rewriting, LFS migration and important data deletion require Jerry's approval. An ignore rule cannot remove a secret already present in history; handle any future leak as a separately authorized credential/history incident.

## Backup and restore

For the Issue Artifact path: retain the print PDF, `PILOT_ROOT` (or the future issue-local vector/translation tree) and any workspace reports you still need. There is no Studio writer lock on this path.

Studio-era trees remain restorable evidence: if you copy `2026-10-12/editorial-artifacts/`, stop leftover writers first and copy queue/index/latest together. Do not revive that store as daily publishing. [BUILD](../render/BUILD.md#recovery) describes current recovery on the product path.
