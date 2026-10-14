#!/usr/bin/env python3
"""T1 翻译管线：001-030 初译（TranslateGemma 只做初译），逐条增量写入 trans-T1-draft.json。"""
import importlib.util, json, os, sys, time

BASE = os.path.expanduser("~/workspace/wsj-deep-read/2026-10-12")
spec = importlib.util.spec_from_file_location("tg", "/home/hatch/workspace/translate-gemma.py")
tg = importlib.util.module_from_spec(spec); spec.loader.exec_module(tg)

merged = json.load(open(os.path.join(BASE, "merged.json")))
glossary = json.load(open(os.path.join(BASE, "glossary.json")))
entries = {x["final_id"]: x for x in merged}
DRAFT = os.path.join(BASE, "trans-T1-draft.json")

draft = json.load(open(DRAFT)) if os.path.exists(DRAFT) else {}
fids = ["%03d" % n for n in range(1, 31)]

def subset_glossary(terms):
    sub, missing = {}, []
    for t in terms or []:
        en = t["en"]
        if en in glossary:
            sub[en] = glossary[en]
        else:
            missing.append(en)
            if t.get("zh_suggested"):
                sub[en] = t["zh_suggested"]
    return sub, missing

def t_translate(text, sub, max_tokens=4000):
    """先试3次退避（引擎内置），若仍失败等30秒再来一次。"""
    try:
        return tg.translate(text, src="en", tgt="zh", glossary=sub, max_tokens=max_tokens)
    except Exception as e1:
        print("  [retry] first pass failed:", repr(e1)[:120], "-> sleep 30s", flush=True)
        time.sleep(30)
        try:
            return tg.translate(text, src="en", tgt="zh", glossary=sub, max_tokens=max_tokens)
        except Exception as e2:
            print("  [retry] second pass failed:", repr(e2)[:120], flush=True)
            raise

def chunk_body(body):
    paras = [p for p in body.split("\n\n") if p.strip()]
    chunks, cur, curw = [], [], 0
    for p in paras:
        w = len(p.split())
        if (len(cur) >= 6 and curw + w > 1200) or len(cur) >= 10:
            chunks.append("\n\n".join(cur)); cur, curw = [], 0
        cur.append(p); curw += w
    if cur:
        chunks.append("\n\n".join(cur))
    return chunks

def save():
    json.dump(draft, open(DRAFT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

for fid in fids:
    if fid in draft and draft[fid].get("_done"):
        print(fid, "already done, skip", flush=True)
        continue
    e = entries[fid]
    sub, missing = subset_glossary(e.get("terms"))
    rec = {
        "_done": False, "type": e.get("type"), "priority": e.get("priority"),
        "title_en": e.get("title"), "dek_en": e.get("dek"),
        "glossary_missing": missing, "glossary_n": len(sub),
    }
    t = time.time()
    try:
        if e.get("type") == "data_table":
            rec["title_cn_draft"] = t_translate(e["title"], sub)
            rec["body_chunks"] = []
        else:
            title_src = e["title"] + ("\n" + e["dek"] if e.get("dek") else "")
            head = t_translate(title_src, sub, max_tokens=800)
            parts = [p for p in head.split("\n") if p.strip()]
            rec["title_cn_draft"] = parts[0] if parts else ""
            rec["dek_cn_draft"] = "\n".join(parts[1:]) if e.get("dek") else None
            body = e.get("body_en") or ""
            chunks = chunk_body(body)
            rec["body_chunks"] = []
            for i, ch in enumerate(chunks):
                zh = t_translate(ch, sub)
                rec["body_chunks"].append({"en": ch, "zh": zh})
                print(f"  {fid} chunk {i+1}/{len(chunks)} ok", flush=True)
        rec["_done"] = True
        draft[fid] = rec
        save()
        print(f"{fid} DONE in {time.time()-t:.0f}s (terms {len(sub)}, missing {missing})", flush=True)
    except Exception as e2:
        draft[fid] = rec
        save()
        print(f"{fid} FAILED: {e2}", flush=True)

print("ALL DONE" if all(draft.get(f, {}).get("_done") for f in fids) else "SOME FAILED")
