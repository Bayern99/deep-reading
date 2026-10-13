# Reboot Proof · Reading Notes

Issue: `dist/index.html` (production) + `dist/baseline.html` (plain)  
Four enhanced plans: `2026-10-12/editorial-plans/{E2-002,E1-010,E3-004,E1-014}.json`  
Slim visual strip: `dist/reboot-four.html`

## Integration result

Editorial plans with `schema_version: enhanced-v1` now drive the **same** `build.py → issue.py` path as the full newspaper. No separate prototype renderer.

| Article | Role | What changed |
|---|---|---|
| E2-002 摄像头 | New long narrative | T01/T03/T06, scene group, L02 sidenote, one quote; source heads promoted to subheads; no timeline/key figures/image |
| E1-010 债券收益率 | New analytical | L03 Oct vs July yield compare, L02 CBO note, two T11 roadmarks, one quote; **rejected** key_figures (would triple-count) |
| E3-004 AI God | New opinion | Three T11 beats, L02 Babel note, opening group, one quote; no data modules |
| E1-014 短讯 | New brief | **Zero** treatments — reviewed restraint |

## Per-article QA

### E2-002
- Content: frozen `final.json` verbatim; source section titles (`隐藏的宝藏` etc.) kept as typography, not invented.
- Editorial: bold only the thesis line; numbers keep 约/大约; Recorded Future explained once in L02, not restated in quote attribution beyond name.
- Design: single column + margin note + pull quote; AJ×WIRED tokens unchanged.
- Reading: long piece becomes scannable without component spam.

### E1-010
- Content: compare cells are condensed labels over numbers that appear in p4–p5.
- Editorial: L03 is the right tool; key_figures declined. CBO/OMB fake-parallel declined.
- Design: desktop side-by-side; mobile A→B per dimension (layout grammar).
- Reading: the “rates were revised up” claim is visible without rereading two dense paragraphs.

### E3-004
- Content: p22 photo caption residue remains text (no fake pope photo).
- Editorial: roadmarks for 教会 / 神学 / 实验室; only Hutchinson’s thesis line as quote.
- Design: typography-led opinion page.
- Reading: clearer argument arc than plain wall of prose.

### E1-014
- Success = almost nothing. Compact head, two paragraphs, review note only.

## How to check

```bash
open 2026-10-12/dist/index.html
# or: python3 -m http.server 8765  (from dist/)
# enhanced ↔ baseline links are in each enhanced article header
```

Shots: `dist/shots/reboot-four-d.png`, `reboot-four-m.png`.
