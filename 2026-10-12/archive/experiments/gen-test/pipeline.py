#!/usr/bin/env python3
"""WSJ 深读 · 泛化测试 pipeline（通用驱动，不许按文章 ID 写分支）。

用法：python3 pipeline.py --stage segment|translate|assets|plan|render|shots
阶段按序运行；每篇文章走完全相同的代码路径。
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import tempfile

# ---------------- 固定输入（任务给定的 4 篇文章，无分支逻辑） ----------------
ARTICLES = [
    {"id": "E1-004", "pdf_page": 0},  # Trump's Russia Energy Deal Gets Pushback
    {"id": "E2-010", "pdf_page": 0},  # The Sunday Scaries Are Real
    {"id": "E1-002", "pdf_page": 0},  # Market Snapshot: Last Week
    {"id": "E1-003", "pdf_page": 0},  # Kenyan, Ethiopian Win Chicago Marathon
]

BASE = "/home/hatch/workspace/wsj-deep-read/2026-10-12/gen-test"
PAGES = os.path.join(BASE, "_pages")
PDF = "/home/hatch/workspace/user/files/kg07NVrtUILyeNFZgUpK-WSJNewsPaper-10-12-2026.pdf"
FINAL_JSON = "/home/hatch/workspace/wsj-deep-read/2026-10-12/final.json"
PROMPT_TPL = os.path.join(PAGES, "planner-prompt.md")
SCHEMA = "/home/hatch/workspace/wsj-deep-read/render/editorial-plan.schema.json"
RENDER_DIR = "/home/hatch/workspace/wsj-deep-read/render"

ENDPOINT = "http://127.0.0.1:18800/v1/chat/completions"
MT_MODEL = "Hy-MT2-30B-A3B-oQ6-MLX"
PLANNER_MODEL = "Qwen3.8-27B-oQ4e-mtp"
MT_PROMPT = ("Translate the following English news text to Chinese. "
             "Keep all names, numbers, dates and quotes faithful. "
             "Output only the translation.")

KEY = subprocess.run(
    ["python3", "-c",
     "import json;print(json.load(open('/home/hatch/.pi/agent/models.json'))['providers']['omlx']['apiKey'])"],
    capture_output=True, text=True).stdout.strip()


def load_meta():
    final = json.load(open(FINAL_JSON, encoding="utf-8"))
    return {a["id"]: a for a in final}


def load_ocr_lines():
    d = json.load(open(os.path.join(PAGES, "page-0-ocr.json"), encoding="utf-8"))
    return d["choices"][0]["message"]["content"].split("\n")


def norm(s):
    return re.sub(r"[^\w\s]", "", s or "").lower().strip()


# ---------------- 通用：按标题锚点从整页 OCR 切出文章 ----------------
def find_anchor(lines, title):
    """返回 (anchor_line_idx, how)。通用逻辑：标题行精确匹配 → 前缀渐短 → 后缀渐短。"""
    headlines = [(i, l) for i, l in enumerate(lines) if l.startswith("# ")]
    nt = norm(title)
    for i, l in headlines:
        hl = norm(l[2:])
        if hl == nt or hl.startswith(nt) or nt.startswith(hl):
            return i, "headline", headlines
    words = title.split()
    for k in range(len(words), 1, -1):
        pre = " ".join(words[:k]).lower()
        for i, l in enumerate(lines):
            if l.strip().lower().startswith(pre):
                return i, f"prefix{k}", headlines
    for k in range(len(words), 1, -1):
        suf = " ".join(words[-k:]).lower()
        for i, l in enumerate(lines):
            if l.strip().lower().startswith(suf):
                return i, f"suffix{k}", headlines
    raise RuntimeError(f"anchor not found for title: {title!r}")


TURN_RE = re.compile(r"^Please turn to page \S+$")
IMG_RE = re.compile(r"^<img\s")


def is_byline_line(l):
    s = l.strip()
    return len(s) < 70 and (s.startswith("By ") or s.startswith("AND "))


def segment_article(lines, meta):
    """从整页 OCR 切出单篇文章正文（阅读顺序），去版式家具。"""
    ai, how, headlines = find_anchor(lines, meta["title"])
    nxt = next((i for i, _ in headlines if i > ai), len(lines))
    raw = lines[ai:nxt]
    # 非标题行命中的锚点（如 E1-002 的 "Last week:" 行）本身就是正文，保留；
    # "# " 标题行则跳过（标题另存为元数据）。
    start = 1 if raw and raw[0].startswith("# ") else 0
    paras, cur = [], []
    dek_n = norm(meta.get("dek"))
    for l in raw[start:]:
        s = l.strip()
        if not s:
            if cur:
                paras.append(" ".join(cur)); cur = []
            continue
        if IMG_RE.match(s):
            continue
        if TURN_RE.match(s):
            continue
        if dek_n and norm(s) == dek_n:
            continue
        if is_byline_line(s):
            continue
        cur.append(s)
    if cur:
        paras.append(" ".join(cur))
    # 阅读顺序重建：上一块未以终结标点收尾 → 与下一块是同一句被 OCR 空行切断，合并。
    # 通用规则，不针对任何文章。
    merged, i = [], 0
    while i < len(paras):
        chunk = paras[i]
        while (i + 1 < len(paras)
               and chunk.rstrip() and chunk.rstrip()[-1] not in ".!?;:\"'\"''\u2026"):
            i += 1
            chunk = chunk.rstrip() + " " + paras[i].lstrip()
        merged.append(chunk)
        i += 1
    return merged, how, lines[ai].strip()


# ---------------- 通用：数字交叉核验 ----------------
NUM_RE = re.compile(r"\$?\d[\d,]*(?:\.\d+)?%?|\d{1,2}:\d{2}(?::\d{2})?")


def number_set(text):
    out = set()
    for m in NUM_RE.finditer(text):
        t = m.group(0).replace("$", "").replace(",", "").replace("%", "")
        if t and any(ch.isdigit() for ch in t):
            out.add(t)
    return out


def number_warnings(pdf_path, ocr_text, pdf_page_idx):
    """pdftotext 整页文本的数字集合 vs OCR 整页文本的数字集合。
    OCR 文本先去掉 <img> 标签（bbox 文件名里的数字不是正文数字）。"""
    ocr_text = IMG_RE.sub("", ocr_text)
    ocr_text = re.sub(r"<img[^>]*>", "", ocr_text)
    r = subprocess.run(
        ["pdftotext", "-layout", "-f", str(pdf_page_idx + 1), "-l", str(pdf_page_idx + 1),
         pdf_path, "-"],
        capture_output=True, text=True)
    pdf_nums = number_set(r.stdout)
    ocr_nums = number_set(ocr_text)
    return {"ocr_only": sorted(ocr_nums - pdf_nums),
            "pdf_only": sorted(pdf_nums - ocr_nums)}


# ---------------- 通用：模型调用 ----------------
def chat(model, system_prompt, user_text, temperature, max_tokens=None, tries=3):
    payload = {"model": model,
               "messages": [{"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_text}],
               "temperature": temperature}
    if max_tokens:
        payload["max_tokens"] = max_tokens
    last_err = None
    for _ in range(tries):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(payload, f, ensure_ascii=False)
            tmp = f.name
        try:
            r = subprocess.run(
                ["curl", "-s", "-m", "180", ENDPOINT,
                 "-H", f"Authorization: Bearer {KEY}",
                 "-H", "Content-Type: application/json",
                 "-d", "@" + tmp],
                capture_output=True, text=True)
            d = json.loads(r.stdout)
            return d["choices"][0]["message"]["content"]
        except Exception as e:  # noqa: BLE001
            last_err = f"{e} | stdout={r.stdout[:200] if 'r' in dir() else ''}"
        finally:
            os.unlink(tmp)
    raise RuntimeError(f"chat failed after {tries} tries: {last_err}")


# ================= 阶段 1：segment → ocr.json =================
def stage_segment():
    lines = load_ocr_lines()
    meta = load_meta()
    full_ocr = "\n".join(lines)
    for spec in ARTICLES:
        aid = spec["id"]
        m = meta[aid]
        paras, how, anchor = segment_article(lines, m)
        warns = number_warnings(PDF, full_ocr, spec["pdf_page"])
        out = {"article_id": aid, "page": f"p{spec['pdf_page']}",
               "text": "\n\n".join(paras), "paragraphs": paras,
               "anchor": anchor, "anchor_how": how,
               "number_warnings": warns}
        d = os.path.join(BASE, aid)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "ocr.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print(f"[{aid}] segment ok: {len(paras)} paragraphs, anchor={how}, "
              f"ocr_only={len(warns['ocr_only'])}, pdf_only={len(warns['pdf_only'])}")


# ================= 阶段 2：translate → translation.json =================
def translate_en(text):
    return chat(MT_MODEL, MT_PROMPT, text, temperature=0).strip()


def stage_translate():
    meta = load_meta()
    for spec in ARTICLES:
        aid = spec["id"]
        m = meta[aid]
        ocr = json.load(open(os.path.join(BASE, aid, "ocr.json"), encoding="utf-8"))
        paras = []
        # 标题也翻译
        t_en = m["title"]
        t_cn = translate_en(t_en) if m["type"] != "data_table" else t_en
        paras.append({"id": "title", "en": t_en, "cn": t_cn})
        for i, p in enumerate(ocr["paragraphs"], 1):
            cn = p if m["type"] == "data_table" else translate_en(p)
            paras.append({"id": f"p{i}", "en": p, "cn": cn})
            print(f"[{aid}] translated p{i}/{len(ocr['paragraphs'])}")
        with open(os.path.join(BASE, aid, "translation.json"), "w", encoding="utf-8") as f:
            json.dump({"article_id": aid, "paragraphs": paras}, f, ensure_ascii=False, indent=1)
        print(f"[{aid}] translation.json ok ({len(paras)} entries)")


# ================= 阶段 3：assets =================
BBOX_RE = re.compile(r"bbox_(\d+)_(\d+)_(\d+)_(\d+)")


def stage_assets():
    """通用：OCR 在文章区域内标注的 <img bbox_…> → 按千分比换算为 PDF 坐标 →
    找 IoU 最大的内嵌图（或直接裁该区域），200dpi PNG。没有标注 = 空 manifest，不硬找。"""
    import fitz  # noqa: PLC0415
    lines = load_ocr_lines()
    meta = load_meta()
    doc = fitz.open(PDF)
    for spec in ARTICLES:
        aid = spec["id"]
        m = meta[aid]
        ai, how, headlines = find_anchor(lines, m["title"])
        nxt = next((i for i, _ in headlines if i > ai), len(lines))
        seg_lines = lines[ai:nxt]
        page = doc[spec["pdf_page"]]
        W, H = page.rect.width, page.rect.height
        adir = os.path.join(BASE, aid, "assets")
        os.makedirs(adir, exist_ok=True)
        manifest = []
        for l in seg_lines:
            s = l.strip()
            if not IMG_RE.match(s):
                continue
            mm = BBOX_RE.search(s)
            if not mm:
                continue
            x1, y1, x2, y2 = (int(v) / 1000 for v in mm.groups())
            target = fitz.Rect(x1 * W, y1 * H, x2 * W, y2 * H)
            best, best_iou = None, 0.0
            for img in page.get_images(full=True):
                for r in page.get_image_rects(img[0]):
                    inter = r & target
                    iarea = inter.get_area()
                    if iarea <= 0:
                        continue
                    iou = iarea / (r.get_area() + target.get_area() - iarea)
                    if iou > best_iou:
                        best, best_iou = r, iou
            crop = best if best is not None and best_iou >= 0.3 else target
            pix = page.get_pixmap(clip=crop & page.rect, dpi=200)
            fname = f"img-{len(manifest)+1:02d}.png"
            pix.save(os.path.join(adir, fname))
            manifest.append({
                "file": fname,
                "page": f"p{spec['pdf_page']}",
                "region": [round(crop.x0, 1), round(crop.y0, 1),
                           round(crop.x1, 1), round(crop.y1, 1)],
                "description": ("OCR 标注的文章配图（bbox 千分比还原），"
                                f"与 PDF 内嵌图 IoU={best_iou:.2f}"),
                "relation": "位于该文章在版面上的区域内，为其配图",
            })
        with open(os.path.join(BASE, aid, "asset-manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=1)
        print(f"[{aid}] assets ok: {len(manifest)} images")
    doc.close()


# ================= 阶段 4：plan =================
def para_int(p):
    if isinstance(p, int):
        return p
    mm = re.match(r"p(\d+)", str(p))
    return int(mm.group(1)) if mm else 0


def normalize_plan(plan, asset_kinds):
    a = plan.get("analysis", {})
    if isinstance(a.get("structure"), str):
        a["structure"] = [a["structure"]]
    nb = a.get("needs_background")
    if isinstance(nb, bool):
        a["needs_background"] = {"needed": nb, "what": ""}
    for q in a.get("quotes", []):
        if isinstance(q, str):
            q = {"text": q, "speaker": "", "para": 0, "why": ""}
        q["para"] = para_int(q.get("para"))
        q["why"] = q.pop("use", q.get("why", ""))
        q.setdefault("speaker", "")
    kns = []
    for kn in a.get("key_numbers", []):
        if isinstance(kn, str):
            kns.append(kn)
        else:
            v = kn.get("value", "")
            p = para_int(kn.get("para"))
            kns.append(f"{v} (p{p})" if p else str(v))
    a["key_numbers"] = kns
    tes = []
    for te in a.get("timeline_events", []):
        if isinstance(te, str):
            te = {"t": "", "text": te, "para": 0}
        tes.append(te)
    a["timeline_events"] = tes
    for te in a["timeline_events"]:
        te["para"] = para_int(te.get("para"))
        if "text" in te and "event" not in te:
            te["event"] = te.pop("text")
        te.setdefault("t", "")
    comp_asset_kind = {}
    for cp in plan.get("component_plan", []):
        if cp.get("asset"):
            comp = cp["component"]
            comp_asset_kind[cp["asset"]] = {"figure": "photo", "chart": "chart",
                                           "infographic": "infographic"}.get(comp, "other")
    for va in a.get("visual_assets", []):
        va["kind"] = comp_asset_kind.get(va.get("file"), asset_kinds.get(va.get("file"), "other"))
        va.setdefault("caption", "")
        va.setdefault("value", va.pop("relevance", ""))
    plan["analysis"] = a
    plan.setdefault("created_by", "generic-planner-v1")
    plan.setdefault("version", "1.0")
    return plan


def stage_plan():
    tpl = open(PROMPT_TPL, encoding="utf-8").read()
    schema = json.load(open(SCHEMA, encoding="utf-8"))
    import jsonschema  # noqa: PLC0415
    meta = load_meta()
    for spec in ARTICLES:
        aid = spec["id"]
        m = meta[aid]
        tr = json.load(open(os.path.join(BASE, aid, "translation.json"), encoding="utf-8"))
        manifest = json.load(open(os.path.join(BASE, aid, "asset-manifest.json"), encoding="utf-8"))
        body = [{"id": p["id"], "en": p["en"], "cn": p["cn"]}
                for p in tr["paragraphs"] if p["id"] != "title"]
        art = {"article_id": aid, "title": m["title"], "title_cn": m.get("title_cn"),
               "dek": m.get("dek"), "byline": m.get("byline"), "type": m["type"],
               "priority": m.get("priority"), "section": m.get("section"),
               "paragraphs": body,
               "assets": [{"file": x["file"], "description": x["description"],
                           "relation": x["relation"]} for x in manifest]}
        user_text = ("## Article input (JSON)\n" + json.dumps(art, ensure_ascii=False, indent=1)
                     + "\n\nProduce the Editorial Plan JSON now.")
        raw = chat(PLANNER_MODEL, tpl, user_text, temperature=0, max_tokens=4000)
        with open(os.path.join(BASE, aid, "plan-raw.txt"), "w", encoding="utf-8") as f:
            f.write(raw)
        plan = extract_json(raw)
        asset_kinds = {x["file"]: "photo" for x in manifest}
        plan["article_id"] = aid
        plan = normalize_plan(plan, asset_kinds)
        err = validate(schema, plan)
        if err:
            print(f"[{aid}] schema fail, retrying once: {err[:300]}")
            raw2 = chat(PLANNER_MODEL, tpl,
                        user_text + "\n\nYour previous output failed schema validation:\n"
                        + err + "\nReturn the corrected FULL JSON only.",
                        temperature=0, max_tokens=4000)
            with open(os.path.join(BASE, aid, "plan-raw-retry.txt"), "w", encoding="utf-8") as f:
                f.write(raw2)
            plan = extract_json(raw2)
            plan["article_id"] = aid
            plan = normalize_plan(plan, asset_kinds)
            err = validate(schema, plan)
            if err:
                print(f"[{aid}] SCHEMA STILL FAILING: {err[:500]}")
        plan.setdefault("created", "2026-10-13")
        with open(os.path.join(BASE, aid, "plan.json"), "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=1)
        n_comp = len(plan.get("component_plan", []))
        comps = [c["component"] for c in plan.get("component_plan", [])]
        print(f"[{aid}] plan.json ok: {n_comp} components {comps}" +
              ("" if not err else " [SCHEMA-FAIL]"))


def extract_json(raw):
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```\w*\n?", "", s)
        s = re.sub(r"\n?```$", "", s)
    return json.loads(s[s.index("{"):s.rindex("}") + 1])


def validate(schema, plan):
    import jsonschema  # noqa: PLC0415
    try:
        jsonschema.validate(plan, schema)
        return None
    except Exception as e:  # noqa: BLE001
        return str(e)


# ================= 阶段 5：render =================
def build_page(e, article_html, tag):
    """照抄 render/build_test_pages.py 的 build_page。"""
    sys.path.insert(0, RENDER_DIR)
    import build as B  # noqa: PLC0415
    tokens = open(os.path.join(RENDER_DIR, "tokens.css"), encoding="utf-8").read()
    doc = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WSJ 深读 · 测试页 {e["id"]}{' · 无Plan降级' if tag else ''}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{B.FONTS}" rel="stylesheet">
<style>
{tokens}
{B.CSS}
</style>
</head>
<body>
<div class="progress" aria-hidden="true"><span id="pbar"></span></div>
<header class="masthead">
  <div class="mast-in">
    <div class="mast-left"><span class="mast-sq" aria-hidden="true"></span><span class="mast-wm">WSJ 深读</span></div>
    <div class="mast-meta"><span class="k-cn">2026年10月12日 · Editorial Plan 测试</span><span class="k-en" hidden>Oct 12, 2026 · Editorial Plan test</span></div>
    <button id="langToggle" class="pill" aria-pressed="false" aria-label="切换中英文"><span class="k-cn">EN</span><span class="k-en" hidden>中文</span></button>
  </div>
</header>
<main id="testpage">
{article_html}
</main>
<footer class="issue-foot">
  <div class="arule"></div>
  <p><span class="k-cn">测试页 · Editorial Plan 驱动渲染验证。正文逐字来自内容定稿。</span><span class="k-en" hidden>Test page · Editorial-Plan-driven rendering. Body text verbatim from the proofed draft.</span></p>
</footer>
<script>{B.JS}</script>
</body>
</html>
'''
    return doc


def sanitize_plan_for_render(plan):
    """渲染器 data_table 按 '|' 切分行列（见 components.py）；planner 若用了制表符，
    在此统一归一化为 ' | '。通用规则，不针对任何文章。"""
    import copy  # noqa: PLC0415
    plan = copy.deepcopy(plan)
    for cp in plan.get("component_plan", []):
        if cp.get("component") == "data_table":
            body = (cp.get("data") or {}).get("body_en", "")
            if "\t" in body and "|" not in body:
                cp["data"]["body_en"] = body.replace("\t", " | ")
    return plan


def stage_render():
    sys.path.insert(0, RENDER_DIR)
    from plan_render import render_article_with_plan  # noqa: PLC0415
    modules_all = json.load(open(os.path.join(RENDER_DIR, "modules.json"), encoding="utf-8"))
    meta = load_meta()
    for spec in ARTICLES:
        aid = spec["id"]
        m = meta[aid]
        tr = json.load(open(os.path.join(BASE, aid, "translation.json"), encoding="utf-8"))
        plan = json.load(open(os.path.join(BASE, aid, "plan.json"), encoding="utf-8"))
        plan = sanitize_plan_for_render(plan)
        body_ps = [p for p in tr["paragraphs"] if p["id"] != "title"]
        adir = os.path.join(BASE, aid, "assets")

        def asset_loader(fname, _d=adir):
            with open(os.path.join(_d, fname), "rb") as f:
                return base64.b64encode(f.read()).decode("ascii")

        e = {"id": aid, "section": m.get("section"), "page": m.get("page"),
             "priority": m.get("priority"), "type": m.get("type"),
             "title_cn": m.get("title_cn"), "title": m.get("title"),
             "dek_cn": m.get("dek_cn"), "dek": m.get("dek"),
             "byline": m.get("byline"),
             "body_cn": "\n\n".join(p["cn"] for p in body_ps),
             "body_en": "\n\n".join(p["en"] for p in body_ps)}
        article_html = render_article_with_plan(e, plan, modules_all, asset_loader)
        html = build_page(e, article_html, None)
        out = os.path.join(BASE, aid, "article.html")
        with open(out, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[{aid}] article.html ok ({len(html)//1024} KB)")


# ================= 阶段 6：screenshots =================
def stage_shots():
    from playwright.sync_api import sync_playwright  # noqa: PLC0415
    for spec in ARTICLES:
        aid = spec["id"]
        url = "file://" + os.path.join(BASE, aid, "article.html")
        with sync_playwright() as pw:
            for name, width in (("shot-d.png", 1440), ("shot-m.png", 390)):
                b = pw.chromium.launch(
                    executable_path="/home/hatch/workspace/.tmp-chrome/chrome-headless-shell-linux64/chrome-headless-shell")
                pg = b.new_page(viewport={"width": width, "height": 900})
                pg.goto(url, wait_until="networkidle", timeout=60000)
                pg.wait_for_timeout(1200)
                pg.screenshot(path=os.path.join(BASE, aid, name), full_page=True)
                b.close()
                print(f"[{aid}] {name} ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True,
                    choices=["segment", "translate", "assets", "plan", "render", "shots"])
    args = ap.parse_args()
    {"segment": stage_segment, "translate": stage_translate, "assets": stage_assets,
     "plan": stage_plan, "render": stage_render, "shots": stage_shots}[args.stage]()
