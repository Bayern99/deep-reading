# WSJ 深读 · Foundation

Date locked: 2026-10-13. Branch: `reboot/reconstruction-brief`.
Audience: the agent (or person) who builds **tomorrow's** issue.

This file is the product constitution. `DESIGN.md` is the visual canon.
Content changes every day. These rules do not.

---

## Product

A Chinese digital newspaper people open every day: faithful WSJ content, selective editorial help, AJ × WIRED design, mobile-first, bilingual.

One-line test: **does this look like a newspaper, or a production log?**
If a reader can see the pipeline, the surface is wrong.

---

## What is foundation (stable)

| Layer | File | Changes when |
|---|---|---|
| Visual tokens, type, measure | `DESIGN.md`, `render/tokens.css`, `reference/hybrid-v3/` | Almost never. Jerry already accepted hybrid-v3. |
| Reader surface rules | this file | When the newspaper identity changes, not when a story changes. |
| Renderer | `render/issue.py` `article.py` `components.py` `build.py` | Bugfix / new type, not per-article hacks. |
| Integrity | `render/integrity_gate.py`, build assertions | When a new failure mode appears. |

## What is daily (must change)

| Layer | File | Owner |
|---|---|---|
| Copy | `<date>/final.json` | extraction → glossary → translation → QA |
| Front-page selection | `<date>/front.json` | editor / agent following § Front |
| Editorial plans | `<date>/editorial-plans/*.json` | only where a module earns its place |
| Photos / charts | `render/images.json` + issue `assets/` | verified crops only |
| Delivery | `<date>/dist/index.html` | `python3 build.py --issue <date>` |

Do not copy 2026-10-12 story IDs into renderer code. Pin them in that day's `front.json`.

---

## Invariants

1. **Verbatim body.** `final.json` is the only copy source. The renderer does not rewrite, retranslate, or pretty-wrap Chinese (`text-wrap: pretty` is banned).
2. **AJ structure, WIRED type.** Tokens, 640px body / 760px head, orange only as square + kicker bar, red only as timeline dots, radius 0 on news modules. See `DESIGN.md`.
3. **No pipeline chrome on the reader surface.** Forbidden on `index.html`: 「机器辅助翻译」, 「逐版摘要」, 「P1 必读」, 「编辑增强」, 「对照纯排版」, article counts as dek, baseline links. Internal ids may exist hidden for asserts.
4. **No invented modules.** key_figures / timeline / quote / photos appear only from plans, `images.json`, or `context_cn`. Empty plan → clean article.
5. **No restatement.** A module must add a view the body does not already give. If the dek already says 「至少 12 人死亡」, key_figures must not say it again.
6. **No 「主张与现实」 / duel.** Deleted. Do not revive.
7. **Type is layout.** `article`/`opinion` full head; `brief`/`letter` compact; `index_digest` What's News column; `photo_caption` caption entry; `data_table` appendix table. Do not stamp the long-article header on a digest.
8. **Single-file delivery.** `dist/index.html`, Google Fonts only, no npm.
9. **Mobile is the product.** 390px must read as a newspaper: 0 horizontal overflow, 16px body, rail gone.

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

## Daily build

```bash
cd render && python3 build.py --issue YYYY-MM-DD
# → ../YYYY-MM-DD/dist/index.html
```

Done when:

1. Assertions pass (verbatim paras, no duel, no pretty, gate).
2. `index.html` contains none of the pipeline strings in § Invariants.
3. Front pack shows the chosen lead + two also-reads.
4. What's News is a column, not a 40px story.
5. Screenshots at 1440 and 390: masthead, front, one enhanced article, one digest — 0 overflow.

---

## Next (in order)

1. **Run a second date through this foundation** without editing renderer principles. Only `final.json` + `front.json` + whatever plans/images that day earns. That is the proof the foundation holds.
2. Keep enhancement rare. The 10-12 issue proved five plans can ship; it did not prove 117 should.
3. Move remaining pipeline reports out of the reader path. `baseline.html` is an internal artifact, not a link from the newspaper.
4. Do not invent a new design system. If hybrid-v3 and `DESIGN.md` feel tight, the work is selection and restraint, not tokens.
