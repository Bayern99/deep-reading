#!/usr/bin/env python3
"""Merge the three extractor JSONs: drop metadata elements, merge turn-to-page
continuations (E1<->E2), assign final sequential IDs, normalize sections."""
import json, os, difflib

# Archived into 2026-10-12/archive/legacy-scripts/; WORK stays the issue directory.
WORK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def load_entries(path):
    raw = json.load(open(path, encoding="utf-8"))
    out = []
    for x in raw:
        if isinstance(x, dict) and "id" in x and "title" in x:
            out.append(x)
        elif isinstance(x, dict) and "skipped_ads" in x:
            print(f"{path}: skipped_ads={len(x['skipped_ads'])}")
    return out

e1 = load_entries(f"{WORK}/extract-E1.json")
e2 = load_entries(f"{WORK}/extract-E2.json")
e3 = load_entries(f"{WORK}/extract-E3.json")
print(f"E1={len(e1)} E2={len(e2)} E3={len(e3)}")

# --- merge E1 A1-part with E2 continuation ---
def norm(t): return (t or "").lower().strip()

merged_e2_ids = set()
merged = []
for a in e1:
    if not a.get("turn_to"):
        merged.append(a); continue
    # find matching E2 continuation
    best, best_r = None, 0
    for b in e2:
        if b.get("continued_from") == "A1":
            r = difflib.SequenceMatcher(None, norm(a["title"]), norm(b["title"])).ratio()
            if r > best_r: best, best_r = b, r
    if best and best_r > 0.6 and best["id"] not in merged_e2_ids:
        merged_e2_ids.add(best["id"])
        ba, bb = a.get("body_en",""), best.get("body_en","")
        # dedup: if A1 part already inside continuation, use continuation
        if ba.strip() and ba.strip()[:200] in bb:
            body = bb
        elif bb.strip() and bb.strip()[:200] in ba:
            body = ba
        else:
            body = ba.rstrip() + "\n\n" + bb.lstrip()
        pri = {"P1":3,"P2":2,"P3":1}
        m = dict(best)
        m["body_en"] = body
        m["page"] = a.get("page","A1")
        m["priority"] = a["priority"] if pri.get(a["priority"],0) > pri.get(best["priority"],0) else best["priority"]
        m["dek"] = m.get("dek") or a.get("dek")
        m["byline"] = m.get("byline") or a.get("byline")
        m["merged_from"] = [a["id"], best["id"]]
        m.pop("turn_to", None); m.pop("continued_from", None)
        # merge terms
        seen = {t["en"] for t in m.get("terms",[])}
        for t in a.get("terms",[]):
            if t["en"] not in seen: m.setdefault("terms",[]).append(t)
        merged.append(m)
        print(f"MERGED {a['id']} + {best['id']}: {a['title'][:45]} (body {len(body)})")
    else:
        merged.append(a)
        print(f"WARN no continuation match for {a['id']} {a['title'][:45]} turn_to={a.get('turn_to')}")

for b in e2:
    if b["id"] not in merged_e2_ids:
        merged.append(b)

# order: E1 (A1-A9), E2 (A10-A18), E3 (B1-B8) — merged A1 stories stay in A1 position
all_entries = merged + e3

# final IDs
for i, e in enumerate(all_entries, 1):
    e["final_id"] = f"{i:03d}"

json.dump(all_entries, open(f"{WORK}/merged.json","w",encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"total merged entries: {len(all_entries)}")

# priority/type stats
from collections import Counter
print("priority:", Counter(e.get("priority") for e in all_entries))
print("type:", Counter(e.get("type") for e in all_entries))
print("sections:", Counter(e.get("section") for e in all_entries))
