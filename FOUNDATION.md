# WSJ 深读 · Foundation

Audience: the person or agent building and maintaining future issues.

This file is the product constitution. `DESIGN.md` is the visual canon.
Current modules and limitations live in `ARCHITECTURE.md`; commands and recovery live in `render/BUILD.md`.
Content changes every day. These principles do not.

---

## Product

A Chinese AI-native digital newspaper people open every day: faithful WSJ journalism, editorial judgment from typography through whole-issue composition, a distinctive identity developed from AJ × WIRED, mobile-first, bilingual.

One-line test: **does this look like a newspaper, or a production log?**
If a reader can see the pipeline, the surface is wrong.

---

## What is foundation (stable)

| Layer | File | Changes when |
|---|---|---|
| Visual tokens, type, measure | `DESIGN.md`, `render/tokens.css`, `reference/hybrid-v3/` | Evolve from the accepted baseline when real reading evidence justifies it; preserve the publication's identity. |
| Reader surface rules | this file | When the newspaper identity changes, not when a story changes. |
| Publishing implementations | Static renderer and generated-article compiler / publisher | Bugfixes and reusable capabilities, not per-article renderer hacks. |
| Integrity | Shared source projection, gate and compiler audits | When a new failure mode appears. |

## What is daily (must change)

| Layer | File | Owner |
|---|---|---|
| Copy | `<date>/final.json` | extraction → glossary → translation → QA |
| Front-page selection | `<date>/front.json` | editor / agent following § Front |
| Editorial plans | `<date>/editorial-plans/*.json` | only where a module earns its place |
| Photos / charts | issue `assets/` and verified manifests | verified crops only; legacy global manifests are described in ARCHITECTURE |
| Generated article versions | `<date>/editorial-artifacts/` | publisher; preserve prior verified versions |
| Delivery | issue `dist/` | deterministic issue build or saved-artifact Reader export |

Do not copy 2026-10-12 story IDs into renderer code. Pin them in that day's `front.json`.

---

## Invariants

1. **Verbatim body.** `final.json` is the approved copy source. Both publishing paths use its auditable bilingual projection; verified artifacts preserve their source digest. Formatting and generation never rewrite or retranslate canonical narrative text, and never use `text-wrap: pretty` on Chinese prose.
2. **Coherent editorial identity.** Develop from AJ × WIRED: 640px body / 760px head, restrained color and structure; variation must express real content relationships. Typography is reading craft, not a frozen prototype. See `DESIGN.md`.
3. **No pipeline chrome on the reader surface.** Forbidden on `index.html`: 「机器辅助翻译」, 「逐版摘要」, 「P1 必读」, 「编辑增强」, 「对照纯排版」, article counts as dek, baseline links. Internal ids may exist hidden for asserts.
4. **No invented modules.** key_figures / timeline / quote / photos appear only from plans, `images.json`, or `context_cn`. Empty plan → clean article.
5. **No restatement.** A module must add a view the body does not already give. If the dek already says 「至少 12 人死亡」, key_figures must not say it again.
6. **No 「主张与现实」 / duel.** Deleted. Do not revive.
7. **Type is layout.** `article`/`opinion` full head; `brief`/`letter` compact; `index_digest` What's News column; `photo_caption` caption entry; `data_table` appendix table. Do not stamp the long-article header on a digest.
8. **Self-contained delivery.** The whole issue and saved-article Reader export as standalone HTML; Google Fonts may be external, with no npm runtime. Live Studio generation and queue controls require the local server.
9. **Mobile is the product.** 390px must read comfortably: 17px / 1.85 body, one 20px inset per side, semantic reflow of notes and comparisons. Zero overflow alone does not prove reading quality.
10. **Confirmed alignment repair only.** A QA-confirmed extraction defect (duplicated print marker, sentence split by a column break) is repaired from `render/alignment_overrides.json` — per article, exact-match text, applied identically on ordinary/enhanced/baseline paths, and folded into each plan's `content_digest`. The renderer never silently edits copy; unconfirmed misalignment fails the build (receipt `alignment_mismatch` / `en_tail_dropped`) instead of truncating.
11. **Digest number fidelity.** A live `data_table`/`index_digest` must show every decimal number of its source. A curated summary (`suppress_body`) must present the same decimal-number set in `insight_cn` and `insight_en`: a summary may drop rows, never make one language's reader blind to a number the other language kept.

---

## Front (every issue)

File: `<date>/front.json`

```json
{
  "date_cn": "2026年10月12日",
  "date_en": "October 12, 2026",
  "weekday_cn": "星期一",
  "weekday_en": "Mon",
  "dek_cn": "一句值得打开的话。",
  "dek_en": "One sentence worth opening.",
  "lead_id": "E1-005",
  "also_ids": ["E2-002", "E2-001"]
}
```

Rules:

- **dek** is today's reason to open, not a production statistic.
- **lead** is one A1 *news* article. Not What's News, not a photo caption, not Personal Journal, not a table.
- **also** is two more A1 news articles. Same exclusions.
- Jump TOC is section names only (最新消息 / 要闻 / 美国 / 世界 / 生活 / 观点 / 商业与金融 / 数据). Not a 90-row file tree.
- If `front.json` is missing, the renderer falls back to A1 news by priority. Still never puts digest/caption/life in the lead slot.

Kicker on stories: `section label · page` only. Priority (P1/P2/P3) is internal.

---

## Editorial plans

Plans live in `<date>/editorial-plans/<id>.json` (`enhanced-v1`). They are optional.

Use a module when it changes how a reader *moves through* the piece (timeline for escalation, condensed figures the body buries, one direct quote). Decline when it restates, fills a column, or was copied from yesterday.

Do not regenerate all enhanced pages for a new date. Start from a clean issue; enhance fewer stories than you think.

---

## Acceptance principles

A published reading experience preserves source copy, bilingual order, verified visual evidence and the publication's editorial identity. Compiler/gate success does not replace reading and visual review.

Inspect desktop and 390px mobile, Chinese and English, navigation, figures and at least one long article and digest. Confirm no horizontal overflow, no duplicated interventions and comfortable continuous reading. Baseline comparisons use identical source repairs and verified assets.

Operational commands and their current limitations are maintained in `render/BUILD.md` and `ARCHITECTURE.md`, not repeated here.

