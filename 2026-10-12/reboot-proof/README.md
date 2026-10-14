# Reboot Proof · 2026-10-12

Production HTML lives in `../dist/`. This directory records editorial decisions
and actual browser evidence. The five production plans include the Saudi lead
and the four articles below; published content still follows curation and integrity gates.

## Articles

| # | Article | Plan | What it proves |
|---|---|---|---|
| 1 | E2-002 摄像头 | `../editorial-plans/E2-002.json` | Long narrative; restraint vs over-modularization; source heads as typography |
| 2 | E1-010 债券收益率 | `../editorial-plans/E1-010.json` | Analytical compare (L03); declining key_figures to avoid triple-count |
| 3 | E3-004 AI上帝问题 | `../editorial-plans/E3-004.json` | Opinion hierarchy; no invented data modules |
| 4 | E1-014 短讯 | `../editorial-plans/E1-014.json` | Brief = near-zero intervention |

## Artifacts

- Current production issue: `../dist/index.html` (92 published items, 5 reviewed editorial plans).
- Internal baseline from the same renderer: `../dist/baseline.html`.
- Front-page hierarchy: `editorial-front-1440.png`, `editorial-front-390.png`.
- Investigative narrative and protected headline: `editorial-investigation-1440.png`, `editorial-investigation-390.png`.
- Rates comparison within the narrative: `editorial-rates-1440.png`.
- Continuous feature opening: `editorial-profile-390.png`.

## Reproduce

```bash
cd ../../render && python3 build.py --issue 2026-10-12
```

## Reading evidence · v1.1

- Real Chromium surface at 1440, 768, 390 and 320px, in Chinese and English: no page overflow; note follows its paragraph on smaller screens; title/body/metadata retain their own font families.
- All 733 body paragraphs share 17px / 1.85 typography, including grouped and annotated paragraphs. All 62 published article/opinion/brief/letter Chinese narratives match the source paragraphs in order.
- Camera headline phrases stay whole at each checked width. Camera and AI/religion openings retain their narrative groups; duplicated quotes removed. Saudi figures follow the complete airport scene. Rates retain the three genuine paired comparisons.
- All 18 embedded images load. Source recovery and translation accuracy remain separate requirements; this check does not establish missing chart completeness or Safari/Firefox behavior.
- Build gate: 113 PASS / 4 WARN / 0 BLOCK across 117 source records. Published item count is 92 after existing curation and review exclusions.

