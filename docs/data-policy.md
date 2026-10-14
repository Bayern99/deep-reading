# Data preservation and Git policy

## Data classes

| Class | Examples | Treatment |
|---|---|---|
| Approved source and provenance | issue `final.json`, `raw.txt`, `extract-E*.json`, `merged.json`, `trans-T*.json`, QA notes, issue translation glossary | Preserve and review as content. Keep in the private project history; take an external backup before any content migration. |
| Verified media and editorial decisions | issue assets, `cases/assets/`, recovered figures, `front.json`, plans, alignment repairs and manifests | Preserve, track deliberately and retain source attribution. Some historically placed assets remain production dependencies. |
| Saved model output and evidence | `editorial-artifacts/` versions, failures, canonical snapshots, audits, screenshots, experiments and dated reports | Durable primary evidence, not a regenerable cache. Keep existing data; inspect model output/notes for credentials before adding a version to Git. |
| Queue and mutable pointers | `_queue.json`, `_index.json`, `latest.json` | Persist and back up with artifact files while writers are stopped. Track deliberate release checkpoints, not every transient status update; do not omit them from a recovery backup. |
| Reproducible delivery | issue `dist/` HTML and receipts | New outputs are ignored. Existing tracked deliveries stay tracked as historical acceptance evidence; ignoring does not untrack them. |
| Local configuration/cache | `.venv/`, `.env*`, bytecode, test/tool caches, logs, interrupted queue temporary files | Ignored. `.env.example` is the tracked credential-free exception. Credentials belong in environment variables or a secret manager. |
| Source PDF | An externally supplied issue PDF | No source PDF is currently in the repository. Retain an external protected original before extraction; approve its storage/distribution separately rather than adding it incidentally. |

The newspaper data and model outputs are not disposable development fixtures. Re-running generation may incur cost and does not reproduce the same artifact. `canonical.json` is the most recent canonical snapshot, not a per-version source archive; version records retain the source digest and injected copy.

## Safe local Git work

`make hooks` installs the tracked hooks: `commit-msg` refuses to commit queue state, the artifact index or a `dist/` snapshot unless the commit message carries the `[data]` marker (or `WSJ_ALLOW_DATA_COMMIT=1` is set), which keeps a live-data checkpoint a deliberate act; `pre-push` runs `make check`. Hooks live in `.git/hooks` and are per-checkout, so run `make hooks` after cloning.

Inspect `git status` before editing. Existing staged/unstaged/untracked changes belong to the user; preserve them. Review explicit paths before staging. Avoid blanket `git add .`, `git clean`, reset/restore of the entire tree, or removing ignored directories as cleanup.

The local governance checkpoint includes the initially uncommitted Phase 5–7 implementation, its required fixtures and preserved evidence. It is a local review point, not a release or deployment. Governance did not untrack saved deliveries, add LFS, compact/garbage-collect objects, rewrite history, merge or push. Review checkpoint content before any release or remote publication.

`.gitignore` covers new issue `dist/` snapshots, environments, credentials and transient queue-write files. It intentionally does not hide final source, artifact versions/index/queue, experiments or historical evidence. `.gitattributes` declares text line endings and binary media; no bulk renormalization was performed.

History currently contains many HTML/image versions. Preserve them. If repository growth later warrants LFS, external evidence storage or retention limits, propose a migration with a backup and explicit compatibility plan; history rewriting and important data deletion require Jerry's approval. An ignore rule cannot remove a secret already present in history; handle any future leak as a separately authorized credential/history incident.

## Backup and restore

Stop writers before taking a backup outside the repository. Copy source, plans, assets and the entire `editorial-artifacts/` tree together, including queue/index/latest records and failed attempts. A file copy taken during generation is not guaranteed consistent. The store is currently single-writer and not transactional across files.

Preserve damaged metadata rather than recreating it as an empty store. Restore from a complete, known-good backup and inspect source digests and version audits before resuming pending work. Keep archival snapshots distinct from the active issue directory. [BUILD](../render/BUILD.md#recovery) describes current recovery behavior and limitations.
