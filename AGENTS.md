# Agent instructions

WSJ 深读 is a daily newspaper with a local editorial Studio. Preserve the validated Phase 1–7 behavior and source data.

## Navigate

- Start with `README.md` for setup and commands; read `ARCHITECTURE.md` before changing module/data contracts or persistence.
- Before building or restyling, read `FOUNDATION.md`, then `DESIGN.md`. Product principles and accepted design experiments are distinct.
- For content, artifacts, backups or Git cleanup, read `docs/data-policy.md`.
- For publishing, queue startup or recovery, read `render/BUILD.md`.
- For domain terms, read `GLOSSARY.md`; translation terminology remains in each issue's separate glossary. Domain-doc convention: `docs/agents/domain.md`.
- For earlier design/audit claims, use `docs/history/README.md`. Historical drivers under `archive/render-experiments/` and issue folders are not production entry points.

## Work and verify

Run from the root: bootstrap `.venv` with `requirements.txt`; `make test` runs both test styles, `make smoke` exercises both production paths in an isolated copy without model calls. `make check` runs both; `make hooks` installs the tracked hooks that keep live data out of commits and run `make check` before a push. `make studio ISSUE=YYYY-MM-DD` launches local Reader/Studio; `make build` and `make reader` export different output families.

Inspect current Git changes before editing; preserve the user's work. Keep final source, translation provenance, verified assets, plans and artifact versions. Treat accepted source as read-only during formatting; exact alignment repairs are auditable projections. Story IDs are scoped to an issue; known legacy global records need an explicit migration before second-date publication.

Studio startup can resume the persistent queue. Use one writer per issue/checkout; stop it before backup. Use isolated inputs for smoke runs. Confirm model generation intentionally; reopening saved content does not require generation.

Finish a change with the affected checks and actual runtime path; UI changes require desktop/mobile bilingual inspection. Update the authoritative document for changed behavior. Avoid incidental package migrations or redesigns. Major refactors, important data deletion, history rewriting, merges, deployment and remote pushes require Jerry's approval. Reply to Jerry in Chinese; keep commits, code comments and documents in English.

## Tracker

Issues/specs: private `Bayern99/deep-reading` via `gh`; see `docs/agents/issue-tracker.md`. Default triage roles: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`; see `docs/agents/triage-labels.md`.
