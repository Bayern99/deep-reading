# Reboot Proof · 2026-10-12

First Working Proof per PROJECT_RECONSTRUCTION_BRIEF.md §E. Canonical build
artifacts live in `dist/` (the production builder output); this directory is
the proof index — no duplicated files.

## Articles

| # | Article | Plan | What it proves |
|---|---|---|---|
| 1 | E2-002 摄像头 | `../editorial-plans/E2-002.json` | Long narrative; restraint vs over-modularization; source heads as typography |
| 2 | E1-010 债券收益率 | `../editorial-plans/E1-010.json` | Analytical compare (L03); declining key_figures to avoid triple-count |
| 3 | E3-004 AI上帝问题 | `../editorial-plans/E3-004.json` | Opinion hierarchy; no invented data modules |
| 4 | E1-014 短讯 | `../editorial-plans/E1-014.json` | Brief = near-zero intervention |

## Artifacts

- Production issue with 4 enhanced articles: `../dist/index.html`
- Plain baseline (same renderer, no plans): `../dist/baseline.html`
- Four-article visual strip: `../dist/reboot-four.html`
- Reading notes: `../dist/REBOOT_READING_NOTES.md`
- Screenshots (desktop 1440 / phone 390, CN + EN): `../dist/shots/`

## Reproduce

```bash
cd ../../render && python3 build.py --issue 2026-10-12 && python3 build_reboot_four.py
```
