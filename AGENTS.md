# Agent instructions

Daily newspaper, not a lab dump. Content changes every issue; principles do not.

**Before building or restyling an issue, read `FOUNDATION.md` then `DESIGN.md`.**

- `FOUNDATION.md` — product constitution (reader surface, front.json, invariants, next).
- `DESIGN.md` — visual canon (AJ × WIRED tokens, type, components).
- Build: `cd render && python3 build.py --issue YYYY-MM-DD` → `../YYYY-MM-DD/dist/index.html`.
- Per-issue selection: `<date>/front.json`. Do not hardcode story ids in the renderer.

## Agent skills

### Issue tracker

Issues and specs live as GitHub issues in this repo (Bayern99/deep-reading), driven by the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-role vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
