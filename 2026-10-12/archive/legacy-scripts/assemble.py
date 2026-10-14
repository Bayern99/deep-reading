#!/usr/bin/env python3
"""Assemble final.json = merged.json (EN source) + trans-T*.json (CN drafts).
The CN strings are copied verbatim — no editing here. QA fixes go into the
trans files or a patches file, never into this script's logic."""
import json, os

# Archived into 2026-10-12/archive/legacy-scripts/; WORK stays the issue directory.
WORK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
merged = json.load(open(f"{WORK}/merged.json", encoding="utf-8"))

trans = {}
for n in ("T1", "T2", "T3", "T4"):
    p = f"{WORK}/trans-{n}.json"
    if os.path.exists(p):
        trans.update(json.load(open(p, encoding="utf-8")))
print(f"trans entries loaded: {len(trans)}")

missing, final = [], []
for e in merged:
    fid = e["final_id"]
    t = trans.get(fid)
    if not t:
        missing.append(fid)
        continue
    f = dict(e)
    # raw data tables go to the appendix section (keep original section)
    if f.get("type") == "data_table":
        f["orig_section"] = f.get("section")
        f["section"] = "Data"
    f["title_cn"] = t.get("title_cn", "")
    f["dek_cn"] = t.get("dek_cn")
    f["body_cn"] = t.get("body_cn", "")
    f["context_cn"] = t.get("context_cn")
    f["context_attr"] = t.get("context_attr")
    final.append(f)

print(f"final entries: {len(final)}, missing trans: {missing}")
json.dump(final, open(f"{WORK}/final.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
# also write report.md (structured draft, the source of truth)
with open(f"{WORK}/report.md", "w", encoding="utf-8") as r:
    r.write("# WSJ 深读 2026-10-12（周一）— 结构化底稿\n\n")
    r.write(f"共 {len(final)} 条。P1/P2/P3 按条目标注。\n\n---\n\n")
    for f in final:
        r.write(f"## [{f['final_id']}] {f.get('title_cn') or ''}（{f.get('priority')}·{f.get('page')}·{f.get('section')}）\n\n")
        r.write(f"EN: {f.get('title')}\n\n")
        if f.get("byline"): r.write(f"作者：{f['byline']}\n\n")
        if f.get("body_cn"): r.write(f["body_cn"] + "\n\n")
        if f.get("context_cn"): r.write(f"背景（{f.get('context_attr','')}）：\n{f['context_cn']}\n\n")
        r.write("---\n\n")
print("wrote final.json and report.md")
