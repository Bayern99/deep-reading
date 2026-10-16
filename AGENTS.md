# Agent instructions

WSJ 深读 is a daily newspaper delivered as one Issue Artifact. Product path: Primary Vector Signals → three-tier editorial composition → LQA Funnel → Certification Oracles ([ADR 0001](docs/adr/0001-three-tier-editorial-composition.md), [ADR 0002](docs/adr/0002-issue-artifact-only-product.md)). Do not publish through Studio.

## Navigate

- Start with `README.md` for setup and commands; read `ARCHITECTURE.md` before changing module/data contracts.
- Before building or restyling, read `FOUNDATION.md`, then `DESIGN.md`. Product principles and the Issue Artifact visual canon are distinct files.
- For content, backups or Git cleanup, read `docs/data-policy.md`.
- For compile, LQA and Oracle commands, read `render/BUILD.md`.
- For domain terms, read `GLOSSARY.md`; translation terminology remains in each issue's separate glossary. Domain-doc convention: `docs/agents/domain.md`.
- For earlier design/audit claims, including the superseded claim-provenance sidecar, use `docs/history/README.md`. Historical drivers under `archive/render-experiments/` are not production entry points. Frozen Studio-era runtime lives on `archive/studio-phase1-7`.

## Work and verify

Run from the root: bootstrap `.venv` with `requirements.txt`. Product proof is `make tracer-certify` (needs the pinned PDF and `PILOT_ROOT` in `render/tracer/compose.py`). `make test` runs the tracer suites; `make smoke` runs `scripts/smoke.py --fast`. `make check` is both.

Inspect current Git changes before editing; preserve the user's work. Keep Primary Vector Signals, translation provenance, verified chart evidence, plans and dated reports. Treat approved narrative as read-only during compilation; the LQA Funnel records dispositions and never rewrites paragraphs. Story IDs are scoped to an issue.

Finish a change with the affected tracer tests and an actual `make tracer` (or `--fast` when raster is out of scope). Reader-surface changes require desktop/mobile inspection in 中文, EN and 双语. Update the authoritative document for changed behavior. Avoid incidental package migrations or redesigns. Major refactors, important data deletion, history rewriting, merges, deployment and remote pushes require Jerry's approval. Reply to Jerry in Chinese; keep commits, code comments and documents in English.

## Tracker

Issues/specs: private `Bayern99/deep-reading` via `gh`; see `docs/agents/issue-tracker.md`. Default triage roles: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`; see `docs/agents/triage-labels.md`.
