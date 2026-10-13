#!/usr/bin/env python3
"""WSJ 深读 · 泛化测试 pipeline（B 组：E2-017 / E2-024 / E3-032 / E3-034）。

复用 pipeline.py 的通用 helpers（chat / number_warnings / normalize_plan /
validate / extract_json），本文件只做：
  1. 文章配置（id -> OCR 页索引），无 per-ID 分支逻辑；
  2. find_anchor 支持 "## " 标题行；
  3. segment 清洗增强（By 署名续行、全大写版头、尾部 —署名/信件落款、
     图注行、Write to 脚注、连字符跨行合并）——全部通用规则；
  4. assets：OCR <img> 标记（阅读顺序归属）为主信号；get_images() 把标记
     解析为高清 raster；无 raster 重叠的标记按区域裁；向量图表
     （多部件 fill path）自动检测 + 扩边裁图。

用法：python3 pipeline_b.py --stage segment|translate|assets|plan|render|shots
"""
import argparse
import base64
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pipeline as P

BASE = P.BASE
ARTICLES = [
    {"id": "E2-017", "ocr": 14},  # opinion, How the AI Boom Ends -> p14(A15)
    {"id": "E2-024", "ocr": 15},  # letter, Massachusetts' Policies... -> p15(A16)
    {"id": "E3-032", "ocr": 24},  # opinion, Home Builders and Sellers... -> p24(B7)
    {"id": "E3-034", "ocr": 24},  # brief, Investors' No. 1 Worry -> p24(B7)
]

IMG_MARK = re.compile(r"images/(bbox_\d+_\d+_\d+_\d+)\.jpg")
HEAD_RE = re.compile(r"#{1,2}\s")


def load_ocr_lines(idx):
    d = json.load(open(os.path.join(P.PAGES, f"page-{idx}-ocr.json"), encoding="utf-8"))
    return d["choices"][0]["message"]["content"].split("\n")


def strip_head(l):
    return HEAD_RE.sub("", l, count=1).strip()


def find_anchor(lines, title):
    """标题锚点：先在 '# '/ '## ' 标题行里精确匹配，再退化为前后缀匹配。"""
    heads = [(i, l) for i, l in enumerate(lines) if HEAD_RE.match(l)]
    nt = P.norm(title)
    for i, l in heads:
        hl = P.norm(strip_head(l))
        if hl == nt or hl.startswith(nt) or nt.startswith(hl):
            return i, "headline", heads
    words = title.split()
    for k in range(len(words), 1, -1):
        pre = " ".join(words[:k]).lower()
        for i, l in enumerate(lines):
            if l.strip().lower().startswith(pre):
                return i, f"prefix{k}", heads
    for k in range(len(words), 1, -1):
        suf = " ".join(words[-k:]).lower()
        for i, l in enumerate(lines):
            if l.strip().lower().startswith(suf):
                return i, f"suffix{k}", heads
    raise RuntimeError(f"anchor not found for title: {title!r}")


def is_section_header(s):
    return (bool(s) and len(s) < 50 and s.upper() == s
            and not any(c.islower() for c in s) and bool(re.search(r"[A-Z]", s)))


def segment_article(lines, meta):
    """切分 + 清洗，返回 (paras, how, anchor_text, markers, captions)。
    markers: [{line, bbox, norm:(x1,y1,x2,y2), caps:[邻近图注]}]"""
    ai, how, heads = find_anchor(lines, meta["title"])
    nxt = next((i for i, _ in heads if i > ai), len(lines))
    drop = {ai}
    # 1) "By X" 署名 + 短续行（名字被 OCR 断行，跳过空行找续行）
    for k in range(ai + 1, min(ai + 9, nxt)):
        s = lines[k].strip()
        if s.startswith("By ") and len(s) < 30:
            drop.add(k)
            for j in range(k + 1, min(k + 4, nxt)):
                t = lines[j].strip()
                if not t:
                    continue
                if len(t) < 30 and not re.search(r"[.!?;:]", t):
                    drop.add(j)
                break
            break
    # 1b) 尾部信件落款姓氏（供 2) 豁免与 6) 整块删除）
    surname = None
    if meta.get("byline"):
        name = re.split(r"[,(\u2014]", meta["byline"])[0].strip()
        name = re.sub(r"^By\s+", "", name)
        parts = name.split()
        if parts:
            surname = parts[-1]
    # 2) 全大写版头行（INSIDE / VIEW / OPINION 等），落款行豁免
    for k in range(ai + 1, nxt):
        if k not in drop and is_section_header(lines[k].strip()):
            if not (surname and surname.lower() in lines[k].lower()):
                drop.add(k)
    # 3) dek（与 final.json dek 归一化相等）
    dek_n = P.norm(meta.get("dek"))
    if dek_n:
        for k in range(ai + 1, nxt):
            if k not in drop and lines[k].strip() and P.norm(lines[k]) == dek_n:
                drop.add(k)
                break
    # 4) <img> 标记 + 邻近图注行（3 行内、短、无句末标点）
    markers, captions_all = [], []
    for k in range(ai + 1, nxt):
        m = IMG_MARK.search(lines[k])
        if not m:
            continue
        drop.add(k)
        x1, y1, x2, y2 = (int(v) / 1000 for v in m.group(1).split("_")[1:])
        caps = []
        for j in range(max(ai + 1, k - 3), min(nxt, k + 4)):
            if j in drop:
                continue
            s = lines[j].strip()
            if not s or HEAD_RE.match(s) or s.startswith("By "):
                continue
            if len(s) < 160 and not re.search(r"[.!?;:]$", s):
                drop.add(j)
                caps.append(s)
                if len(caps) >= 2:
                    break
        markers.append({"line": k, "bbox": m.group(1),
                        "norm": (x1, y1, x2, y2), "caps": caps})
        captions_all.extend(caps)
    # 5) 尾部 "—姓名" 署名行
    nonempty = [k for k in range(ai + 1, nxt) if lines[k].strip() and k not in drop]
    if nonempty:
        last = lines[nonempty[-1]].strip()
        if last.startswith("—") and len(last) < 40:
            drop.add(nonempty[-1])
    # 6) 尾部信件落款：按 byline 姓氏定位（末尾 10 行内），整块删除
    if surname:
        for k in range(nxt - 1, max(ai, nxt - 11), -1):
            if k in drop:
                continue
            if surname.lower() in lines[k].lower():
                for k2 in range(k, nxt):
                    drop.add(k2)
                break
    # 7) "Write to xxx@xxx." 专栏脚注
    for k in range(max(ai + 1, nxt - 4), nxt):
        if k not in drop and re.match(r"^Write to \S+@\S+\.?$", lines[k].strip()):
            drop.add(k)
    # 组装段落
    paras, cur = [], []
    for k in range(ai + 1, nxt):
        if k in drop:
            continue
        s = lines[k].strip()
        if not s:
            if cur:
                paras.append(" ".join(cur))
                cur = []
            continue
        cur.append(s)
    if cur:
        paras.append(" ".join(cur))
    # 合并被 OCR 空行切断的句子 + 连字符跨行合并（通用）
    merged, i = [], 0
    while i < len(paras):
        chunk = paras[i]
        # 连字符跨行：本块以 "-" 结尾且下块小写开头 -> 去连字符直连
        while (i + 1 < len(paras) and chunk.rstrip().endswith("-")
               and paras[i + 1].lstrip()[:1].islower()):
            i += 1
            chunk = chunk.rstrip()[:-1] + paras[i].lstrip()
        while (i + 1 < len(paras) and chunk.rstrip()
               and chunk.rstrip()[-1] not in ".!?;:\"'\"''\u2026"):
            i += 1
            chunk = chunk.rstrip() + " " + paras[i].lstrip()
        merged.append(chunk)
        i += 1
    return merged, how, strip_head(lines[ai]), markers, captions_all


# ================= 阶段 1：segment -> ocr.json =================
def stage_segment():
    meta = P.load_meta()
    for spec in ARTICLES:
        aid = spec["id"]
        m = meta[aid]
        lines = load_ocr_lines(spec["ocr"])
        paras, how, anchor, markers, caps = segment_article(lines, m)
        full_ocr = "\n".join(lines)
        warns = P.number_warnings(P.PDF, full_ocr, spec["ocr"])
        out = {"article_id": aid, "page": m["page"],
               "text": "\n\n".join(paras), "paragraphs": paras,
               "anchor": anchor, "anchor_how": how,
               "markers": markers, "captions": caps,
               "number_warnings": warns}
        d = os.path.join(BASE, aid)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "ocr.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print(f"[{aid}] segment ok: {len(paras)} paragraphs, anchor={how}, "
              f"markers={len(markers)}, "
              f"ocr_only={len(warns['ocr_only'])}, pdf_only={len(warns['pdf_only'])}")


# ================= 阶段 2：translate -> translation.json =================
def stage_translate():
    meta = P.load_meta()
    for spec in ARTICLES:
        aid = spec["id"]
        m = meta[aid]
        ocr = json.load(open(os.path.join(BASE, aid, "ocr.json"), encoding="utf-8"))
        paras = [{"id": "title", "en": m["title"],
                  "cn": P.chat(P.MT_MODEL, P.MT_PROMPT, m["title"], 0).strip()}]
        if m.get("dek"):
            paras.append({"id": "dek", "en": m["dek"],
                          "cn": P.chat(P.MT_MODEL, P.MT_PROMPT, m["dek"], 0).strip()})
        for i, p in enumerate(ocr["paragraphs"], 1):
            cn = P.chat(P.MT_MODEL, P.MT_PROMPT, p, 0).strip()
            paras.append({"id": f"p{i}", "en": p, "cn": cn})
            print(f"[{aid}] translated p{i}/{len(ocr['paragraphs'])}")
        with open(os.path.join(BASE, aid, "translation.json"), "w", encoding="utf-8") as f:
            json.dump({"article_id": aid, "paragraphs": paras}, f, ensure_ascii=False, indent=1)
        print(f"[{aid}] translation.json ok ({len(paras)} entries)")


# ================= 阶段 3：assets =================
def _iou(a, b):
    ix1, iy1 = max(a.x0, b.x0), max(a.y0, b.y0)
    ix2, iy2 = min(a.x1, b.x1), min(a.y1, b.y1)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    union = (a.x1 - a.x0) * (a.y1 - a.y0) + (b.x1 - b.x0) * (b.y1 - b.y0) - inter
    return inter / union if union else 0.0


def _merge_rects(rects):
    out = []
    for r in sorted(rects, key=lambda r: r.x0):
        for o in out:
            if _iou(r, o) > 0.05:
                o.x0, o.y0 = min(o.x0, r.x0), min(o.y0, r.y0)
                o.x1, o.y1 = max(o.x1, r.x1), max(o.y1, r.y1)
                break
        else:
            out.append(r.__class__(r))
    return out


def chart_crop_rect(page, R, y_limit=None):
    """文本引导的图表裁图（通用）：标题按字号识别，注/来源行纳入，
    左右排除较远的正文栏文字。R = 向量图表 bbox。"""
    import fitz
    d = page.get_text("dict")
    spans = [s for b in d["blocks"] if b.get("type") == 0
             for l in b["lines"] for s in l["spans"] if s["text"].strip()]

    def x_overlap(s, pad=50):
        return s["bbox"][0] < R.x1 + pad and s["bbox"][2] > R.x0 - pad

    # top：R 上方 45pt 内、x 交叠的行，取字号最大者（图表标题）
    top_cands = [s for s in spans
                 if s["bbox"][3] <= R.y0 + 2 and s["bbox"][1] >= R.y0 - 45
                 and x_overlap(s)]
    top = R.y0 - 10
    if top_cands:
        by_size = {}
        for s in top_cands:
            by_size.setdefault(round(s["size"], 1), []).append(s)
        big = by_size[max(by_size)]
        top = min(s["bbox"][1] for s in big) - 6
    # bottom：R 下方 70pt 内的行 + 以 Source/Note 开头的行（110pt 内）
    bot_cands = [s for s in spans
                 if s["bbox"][1] >= R.y1 - 2 and s["bbox"][1] <= R.y1 + 70
                 and x_overlap(s, 40)]
    bottom = R.y1 + 10
    if bot_cands:
        bottom = max(s["bbox"][3] for s in bot_cands) + 6
    for s in spans:
        t = s["text"].strip()
        if (R.y1 < s["bbox"][1] <= R.y1 + 115 and x_overlap(s, 40)
                and re.match(r"^(Source|Note|来源|资料来源|注)[:：]", t)):
            bottom = max(bottom, s["bbox"][3] + 6)
    if y_limit:
        bottom = min(bottom, y_limit)
    # left：排除 R.x0 - 20 以左的远端正文（保留坐标轴标签等近端元素）
    words = page.get_text("words")
    left = R.x0 - 30
    far = [w for w in words
           if top < w[1] and w[3] < bottom and w[2] < R.x0 - 20 and w[0] > R.x0 - 250]
    if far:
        left = min(max(w[2] for w in far) + 10, R.x0 - 6)
    # right：排除 R.x1 + 8 以右的正文
    right = R.x1 + 15
    near = [w for w in words
            if top < w[1] and w[3] < bottom and w[0] > R.x1 + 8 and w[0] < R.x1 + 250]
    if near:
        right = max(min(w[0] for w in near) - 8, R.x1 + 4)
    q = fitz.Rect(left, top, right, bottom)
    q &= page.rect
    return q


def stage_assets():
    import fitz
    meta = P.load_meta()
    doc = fitz.open(P.PDF)
    for spec in ARTICLES:
        aid = spec["id"]
        m = meta[aid]
        lines = load_ocr_lines(spec["ocr"])
        ocr = json.load(open(os.path.join(BASE, aid, "ocr.json"), encoding="utf-8"))
        ai, how, heads = find_anchor(lines, m["title"])
        nxt = next((i for i, _ in heads if i > ai), len(lines))
        page = doc[spec["ocr"]]
        W, H = page.rect.width, page.rect.height

        def band_edge(q, default):
            for qq in (q, q.replace("'", "\u2019")):
                hits = page.search_for(" ".join(qq.split()[:6]))
                if hits:
                    return min(r.y0 for r in hits)
            return default

        top = band_edge(strip_head(lines[ai]), 0.0)
        bot = band_edge(strip_head(lines[nxt]), H) if nxt < len(lines) else H

        def norm_of(r):
            return {"x1": round(r.x0 / W * 1000), "y1": round(r.y0 / H * 1000),
                    "x2": round(r.x1 / W * 1000), "y2": round(r.y1 / H * 1000)}

        # 版面带内的内嵌 raster
        rasters = []
        for img in page.get_images(full=True):
            for rect in page.get_image_rects(img[0]):
                if rect.y1 <= top or rect.y0 >= bot:
                    continue
                if not any(_iou(rect, r) > 0.9 for r in rasters):
                    rasters.append(rect)
        # 向量图表候选：部件数 >= 40 的 fill path，位于带内，不与 raster 重叠
        charts = []
        for x in page.get_drawings():
            if len(x["items"]) < 40:
                continue
            r = x["rect"]
            if r.y1 <= top or r.y0 >= bot:
                continue
            if r.x1 - r.x0 < 30 or r.y1 - r.y0 < 30:
                continue
            if any(_iou(r, rr) > 0.05 for rr in rasters):
                continue
            charts.append(r)
        charts = _merge_rects(charts)

        adir = os.path.join(BASE, aid, "assets")
        os.makedirs(adir, exist_ok=True)
        manifest = []

        def save(rect, fname, pad=2):
            clip = rect + fitz.Rect(-pad, -pad, pad, pad)
            clip &= page.rect
            pix = page.get_pixmap(clip=clip, dpi=200)
            pix.save(os.path.join(adir, fname))
            return pix

        def expand(r, dl, dt, dr, db):
            q = fitz.Rect(r.x0 - dl, r.y0 - dt, r.x1 + dr, r.y1 + db)
            q &= page.rect
            return q

        used_r, used_c, n = set(), set(), 0
        for mk in ocr["markers"]:
            mr = fitz.Rect(mk["norm"][0] * W, mk["norm"][1] * H,
                           mk["norm"][2] * W, mk["norm"][3] * H)
            cap_txt = "; ".join(f"'{c}'" for c in mk["caps"]) or "no caption in OCR"
            n += 1
            hit = next((i for i, rr in enumerate(rasters)
                        if i not in used_r and _iou(mr, rr) > 0.3), None)
            if hit is not None:
                used_r.add(hit)
                fn = f"img-{n:02d}.png"
                save(rasters[hit], fn)
                manifest.append({
                    "file": fn, "page": m["page"], "region": norm_of(rasters[hit]),
                    "description": f"embedded raster illustration. OCR caption near marker: {cap_txt}",
                    "relation": "OCR illustration marker inside this article's segment overlaps this image (reading-order attribution)",
                })
                continue
            chits = [i for i, c in enumerate(charts)
                     if i not in used_c and _iou(mr, c) > 0.05]
            if chits:
                for i in chits:
                    used_c.add(i)
                vr = charts[chits[0]]
                for i in chits[1:]:
                    vr = fitz.Rect(min(vr.x0, charts[i].x0), min(vr.y0, charts[i].y0),
                                   max(vr.x1, charts[i].x1), max(vr.y1, charts[i].y1))
                cr = chart_crop_rect(page, vr, y_limit=bot - 8)
                ur = fitz.Rect(min(cr.x0, mr.x0), min(cr.y0, mr.y0),
                               max(cr.x1, mr.x1), max(cr.y1, mr.y1))
                ur &= page.rect
                fn = f"chart-{n:02d}.png"
                save(ur, fn, pad=0)
                manifest.append({
                    "file": fn, "page": m["page"], "region": norm_of(ur),
                    "description": f"vector chart/graphic. OCR caption near marker: {cap_txt}",
                    "relation": "OCR illustration marker inside this article's segment overlaps vector drawing(s) (reading-order attribution); planner must verify it belongs to this article",
                })
                continue
            mr2 = expand(mr, 10, 10, 10, 10)
            fn = f"region-{n:02d}.png"
            save(mr2, fn)
            manifest.append({
                "file": fn, "page": m["page"], "region": norm_of(mr2),
                "description": f"OCR illustration marker region (no embedded raster found). caption: {cap_txt}",
                "relation": "OCR illustration marker inside this article's segment; cropped marker region directly",
            })
        # 无标记归属的向量图表（仍在带内）：纳入，注明需核验
        for i, c in enumerate(charts):
            if i in used_c:
                continue
            n += 1
            ur = chart_crop_rect(page, c, y_limit=bot - 8)
            fn = f"chart-{n:02d}.png"
            save(ur, fn, pad=0)
            manifest.append({
                "file": fn, "page": m["page"], "region": norm_of(ur),
                "description": "vector chart/graphic detected in article band (no OCR marker)",
                "relation": "multi-part vector drawing inside this article's vertical band; planner must verify it belongs to this article",
            })
        with open(os.path.join(BASE, aid, "asset-manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=1)
        print(f"[{aid}] assets ok: {len(manifest)} files "
              f"({', '.join(x['file'] for x in manifest) or 'none'})")
    doc.close()


# ================= 阶段 4：plan =================
def stage_plan():
    tpl = open(P.PROMPT_TPL, encoding="utf-8").read()
    schema = json.load(open(P.SCHEMA, encoding="utf-8"))
    meta = P.load_meta()
    for spec in ARTICLES:
        aid = spec["id"]
        m = meta[aid]
        tr = json.load(open(os.path.join(BASE, aid, "translation.json"), encoding="utf-8"))
        manifest = json.load(open(os.path.join(BASE, aid, "asset-manifest.json"), encoding="utf-8"))
        tmap = {p["id"]: p for p in tr["paragraphs"]}
        body = [{"id": p["id"], "en": p["en"], "cn": p["cn"]}
                for p in tr["paragraphs"] if p["id"].startswith("p")]
        art = {"article_id": aid, "title": m["title"],
               "title_cn": tmap["title"]["cn"],
               "dek": m.get("dek"), "byline": m.get("byline"), "type": m["type"],
               "priority": m.get("priority"), "section": m.get("section"),
               "paragraphs": body,
               "assets": [{"file": x["file"], "description": x["description"],
                           "relation": x["relation"]} for x in manifest]}
        user_text = ("## Article input (JSON)\n" + json.dumps(art, ensure_ascii=False, indent=1)
                     + "\n\nProduce the Editorial Plan JSON now.")
        raw = P.chat(P.PLANNER_MODEL, tpl, user_text, 0, max_tokens=4000)
        plan = P.extract_json(raw)
        asset_kinds = {x["file"]: "photo" for x in manifest}
        plan["article_id"] = aid
        plan = P.normalize_plan(plan, asset_kinds)
        err = P.validate(schema, plan)
        if err:
            print(f"[{aid}] schema fail, retrying once: {err[:300]}")
            raw2 = P.chat(P.PLANNER_MODEL, tpl,
                          user_text + "\n\nYour previous output failed schema validation:\n"
                          + err + "\nReturn the corrected FULL JSON only.",
                          0, max_tokens=4000)
            plan = P.extract_json(raw2)
            plan["article_id"] = aid
            plan = P.normalize_plan(plan, asset_kinds)
            err = P.validate(schema, plan)
            if err:
                print(f"[{aid}] SCHEMA STILL FAILING: {err[:500]}")
        plan.setdefault("created", "2026-10-13")
        with open(os.path.join(BASE, aid, "plan.json"), "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=1)
        n_comp = len(plan.get("component_plan", []))
        comps = [c["component"] for c in plan.get("component_plan", [])]
        print(f"[{aid}] plan.json ok: {n_comp} components {comps}" +
              ("" if not err else " [SCHEMA-FAIL]"))


# ================= 阶段 5：render =================
def stage_render():
    sys.path.insert(0, P.RENDER_DIR)
    from plan_render import render_article_with_plan
    from build_test_pages import build_page
    modules_all = json.load(open(os.path.join(P.RENDER_DIR, "modules.json"), encoding="utf-8"))
    meta = P.load_meta()
    for spec in ARTICLES:
        aid = spec["id"]
        m = meta[aid]
        tr = json.load(open(os.path.join(BASE, aid, "translation.json"), encoding="utf-8"))
        plan = json.load(open(os.path.join(BASE, aid, "plan.json"), encoding="utf-8"))
        tmap = {p["id"]: p for p in tr["paragraphs"]}
        body_ps = [p for p in tr["paragraphs"] if p["id"].startswith("p")]
        adir = os.path.join(BASE, aid, "assets")

        def asset_loader(fname, _d=adir):
            with open(os.path.join(_d, fname), "rb") as f:
                return base64.b64encode(f.read()).decode("ascii")

        e = {"id": aid, "section": m.get("section"), "page": m.get("page"),
             "priority": m.get("priority"), "type": m.get("type"),
             "title_cn": tmap["title"]["cn"], "title": m.get("title"),
             "dek_cn": tmap["dek"]["cn"] if "dek" in tmap else None,
             "dek": m.get("dek"), "byline": m.get("byline"),
             "body_cn": "\n\n".join(p["cn"] for p in body_ps),
             "body_en": "\n\n".join(p["en"] for p in body_ps)}
        article_html = render_article_with_plan(e, plan, modules_all, asset_loader)
        html = build_page(e, article_html, "")
        out = os.path.join(BASE, aid, "article.html")
        with open(out, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[{aid}] article.html ok ({len(html)//1024} KB)")


# ================= 阶段 6：shots =================
def stage_shots():
    from playwright.sync_api import sync_playwright
    exe = "/home/hatch/workspace/.tmp-chrome/chrome-headless-shell-linux64/chrome-headless-shell"
    with sync_playwright() as pw:
        for spec in ARTICLES:
            aid = spec["id"]
            url = "file://" + os.path.join(BASE, aid, "article.html")
            b = pw.chromium.launch(executable_path=exe)
            for name, width in (("shot-d.png", 1440), ("shot-m.png", 390)):
                pg = b.new_page(viewport={"width": width, "height": 900})
                pg.goto(url, timeout=60000)
                pg.wait_for_timeout(1500)
                pg.screenshot(path=os.path.join(BASE, aid, name), full_page=True)
                pg.close()
                print(f"[{aid}] {name} ok")
            b.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True,
                    choices=["segment", "translate", "assets", "plan", "render", "shots"])
    args = ap.parse_args()
    {"segment": stage_segment, "translate": stage_translate, "assets": stage_assets,
     "plan": stage_plan, "render": stage_render, "shots": stage_shots}[args.stage]()
