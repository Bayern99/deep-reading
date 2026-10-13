#!/usr/bin/env python3
"""gen-test 泛化 pipeline（第二批）：多篇文章走完整流程，零按 ID 分支。

输入：[(article_id, pdf_page)] —— 任务给定的输入表。
其余一切（分割、翻译、资产判定、Plan、渲染）全部走同一套通用规则，
不许出现任何按 article_id / 标题内容写分支的逻辑。

阶段（每篇）：
  1. ocr.json         整页 OCR 按标题锚点切出文章文本 + pdftotext 数字交叉检查
  2. translation.json Hy-MT2 逐段翻译（p1=标题 + 正文段；dek/byline 另存）
  3. assets/ + asset-manifest.json  pymupdf 按版面内嵌图裁图（通用"文章相关"判定）
  4. plan.json        planner 模板 + 文章 + 资产清单 -> Qwen -> jsonschema 校验 -> 失败回灌重试一次
  5. article.html     plan_render.render_article_with_plan + build_test_pages.build_page 页面壳
"""
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, '/home/hatch/workspace/wsj-deep-read/render')

BASE = '/home/hatch/workspace/wsj-deep-read/2026-10-12/gen-test'
PAGES_DIR = os.path.join(BASE, '_pages')
PDF = '/home/hatch/workspace/user/files/kg07NVrtUILyeNFZgUpK-WSJNewsPaper-10-12-2026.pdf'
FINAL = '/home/hatch/workspace/wsj-deep-read/2026-10-12/final.json'
TEMPLATE = os.path.join(PAGES_DIR, 'planner-prompt.md')
SCHEMA = '/home/hatch/workspace/wsj-deep-read/render/editorial-plan.schema.json'

# 任务输入表：(article_id, ocr_page)。这是输入，不是分支。
# 注：_pages/page-N.* ↔ 真实 PDF 第 N+1 页（已用 mean-diff 实测确认）。
ARTICLES = [('E1-014', 1), ('E1-025', 3), ('E1-034', 6)]


def pdf_page_of(ocr_page):
    return ocr_page + 1

API = 'http://127.0.0.1:18800/v1/chat/completions'
MT_MODEL = 'Hy-MT2-30B-A3B-oQ6-MLX'
PLAN_MODEL = 'Qwen3.8-27B-oQ4e-mtp'
MT_PROMPT = ('Translate the following English news text to Chinese. '
             'Keep all names, numbers, dates and quotes faithful. '
             'Output only the translation.')

STOPWORDS = set('''a an the and or of to in on for with at by from as is are was were be been
being it its this that these those he she they we you i his her their our your my me him
us them will would can could should may might must shall do does did have has had not no
but if then than so such into out up down over under about after before between
during said says say according new old big small more most less least very just only also
all any each every both few many much own same other another while who whom whose
what when where why how which there here their his her its our your my me him us them
s t d ll re ve don isn aren wasn weren hasn haven doesn didn won wouldn couldn shouldn
m'''.split())


def get_key():
    return json.load(open('/home/hatch/.pi/agent/models.json'))['providers']['omlx']['apiKey']


def norm_ws(s):
    return re.sub(r'\s+', ' ', s).strip()


def anchor_re(s):
    """把一段文本转成空白宽容（大小写不敏感）的正则锚点。"""
    return re.compile(r'\s+'.join(re.escape(w) for w in s.split()), re.IGNORECASE)


# ---------------------------------------------------------------- 分割
DATELINE_RE = r"[A-Z][A-Z .'\-]{1,28}"


def cut_span(full_text, title):
    """通用分割：标题锚点开始，到下一个 '# ' 标题或全大写 dateline 行结束。
    标题前若紧贴一行全大写 dateline（如 FLORIDA），一并纳入。
    返回 (span, dateline, next_heading)：next_heading 为下一个 '# ' 标题的文本
    （供 pdftotext 文本做同样的切割；dateline 边界时为 None）。"""
    m = find_anchor(full_text, title)
    if not m:
        raise ValueError(f'title anchor not found: {title!r}')
    start = m.start()
    dateline = None
    dm = re.search(r'\n\n(' + DATELINE_RE + r')\n\n$', full_text[:start])
    if dm:
        dateline = dm.group(1)
        start = dm.start() + 2
    tail = full_text[m.end():]
    bounds = []  # (offset, kind, text)
    for mm in re.finditer(r'(?m)^# (.+)$', tail):
        bounds.append((mm.start(), 'heading', mm.group(1).strip()))
    for mm in re.finditer(r'(?m)^' + DATELINE_RE + r'\s*$', tail):
        bounds.append((mm.start(), 'dateline', None))
    if bounds:
        bounds.sort()
        off, kind, htext = bounds[0]
        end = m.end() + off
    else:
        end = len(full_text)
    # next_heading 独立于 span 边界：pdftotext 文本无 '# ' 标记，需要标题文本做锚点
    next_heading = None
    for mm in re.finditer(r'(?m)^# (.+)$', tail):
        next_heading = mm.group(1).strip()
        break
    return full_text[start:end], dateline, next_heading


def _img_markers_with_caption(span):
    out = []
    for m in re.finditer(r'<img src="([^"]+)" />', span):
        rest = span[m.end():]
        cap = ''
        for chunk in re.split(r'\n\s*\n', rest):
            chunk = chunk.strip()
            if chunk:
                cap = chunk[:400]
                break
        out.append({'pos': m.start(), 'src': m.group(1), 'caption': cap})
    return out


def _relevant_marker(mk, kw):
    cap_words = set(re.findall(r"[A-Za-z']{4,}", mk['caption'].lower()))
    if cap_words & kw:
        return True
    if re.match(r'(?i)^\s*ads?\s*$', mk['caption']):
        return False
    if re.search(r'(?i)advertisement', mk['caption']):
        return False
    return False


def truncate_at_ads(span, kw):
    """通用广告截断：span 后 60% 区域内，第一个与主题词零交集的 <img> 标记
    视为广告版块开始，从此处截断（广告文案不进正文）。返回 (span, truncated)。"""
    markers = _img_markers_with_caption(span)
    n = max(len(span), 1)
    for mk in markers:
        if mk['pos'] / n > 0.4 and not _relevant_marker(mk, kw):
            return span[:mk['pos']], True
    return span, False


def strip_img_markers(s):
    return re.sub(r'<img src="[^"]+" />', '', s)


def remove_once(hay, needle):
    mm = anchor_re(needle).search(hay)
    if not mm:
        return hay, False
    return hay[:mm.start()] + hay[mm.end():], True


MERGE_END = set('.!?;:"\'""''\u2026')


def merge_broken_lines(paras):
    """通用阅读顺序重建：上一块未以终结标点收尾 → 与下一块是同一句被 OCR
    空行切断，合并。全大写 dateline 独立成段，不参与合并。"""
    merged, i = [], 0
    while i < len(paras):
        chunk = paras[i]
        if re.match(r'^' + DATELINE_RE + r'$', chunk):
            merged.append(chunk)
            i += 1
            continue
        while (i + 1 < len(paras)
               and chunk.rstrip() and chunk.rstrip()[-1] not in MERGE_END
               and not re.match(r'^' + DATELINE_RE + r'$', paras[i + 1])):
            i += 1
            chunk = chunk.rstrip() + ' ' + paras[i].lstrip()
        merged.append(chunk)
        i += 1
    return merged


def segment(full_text, meta):
    """返回 (span_raw, paragraphs_en, dek_en, byline_en, ad_truncated)。
    paragraphs_en：去掉标题/dek/byline/img标记、广告截断、断行合并后的正文段。"""
    span, dateline, next_heading = cut_span(full_text, meta['title'])
    kw = subject_keywords({'title': meta.get('title'), 'dek': meta.get('dek')}, [])
    span, ad_truncated = truncate_at_ads(span, kw)
    text = strip_img_markers(span)
    text, _ = remove_once(text, meta['title'])
    dek_en = meta.get('dek')
    if dek_en and not (dateline and norm_ws(dek_en) == norm_ws(dateline)):
        text, _ = remove_once(text, dek_en)
    byline_en = meta.get('byline')
    if byline_en:
        text, _ = remove_once(text, byline_en)
    paras = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    paras = merge_broken_lines(paras)
    return span, paras, dek_en, byline_en, ad_truncated, next_heading


# ---------------------------------------------------------------- 数字交叉检查
NUM_RE = re.compile(r'\$?\d[\d,]*(?:\.\d+)?%?')


def num_counter(s):
    c = Counter()
    for tok in NUM_RE.findall(s):
        t = tok.replace('$', '').replace(',', '').replace('%', '')
        if t and any(ch.isdigit() for ch in t):
            c[t] += 1
    return c


def find_anchor(text, title):
    """通用锚点：先试全标题；找不到则退化为最长可匹配前缀（≥2 词），
    应对 pdftotext -layout 把标题拆到多栏的情形。返回 match 或 None。"""
    words = title.split()
    for k in range(len(words), 1, -1):
        m = anchor_re(' '.join(words[:k])).search(text)
        if m:
            return m
    return None


def number_warnings(pdf_page, span, meta):
    """数字交叉检查：OCR 文章文本的数字集合 vs pdftotext 整页文本的数字集合。
    （pdftotext -layout 在多栏版面上混排，无法做可靠的 article 级对齐，
    故 pdf_only 含整页其他文章/广告数字，仅备查；ocr_only 为重点可疑项。）
    返回 {"ocr_only": [...], "pdf_only": [...], "note": ...}。"""
    ocr_nums = num_counter(strip_img_markers(span))
    try:
        pt = subprocess.run(['pdftotext', '-layout', '-f', str(pdf_page), '-l', str(pdf_page),
                             PDF, '-'], capture_output=True, text=True, timeout=60).stdout
    except Exception as e:
        return {'ocr_only': [], 'pdf_only': [],
                'note': f'pdftotext failed: {e}'}
    if not pt.strip():
        return {'ocr_only': [], 'pdf_only': [],
                'note': 'pdftotext 无文本层（扫描版 PDF），无法比对'}
    pdf_nums = num_counter(pt)
    so, sp = set(ocr_nums), set(pdf_nums)
    return {
        'ocr_only': sorted(so - sp, key=lambda t: (len(t), t)),
        'pdf_only': sorted(sp - so, key=lambda t: (len(t), t)),
        'note': ('pdftotext -layout 多栏混排：pdf_only 含整页其他文章/广告/版式家具数字，仅备查；'
                 'ocr_only（OCR 文章有、整页未见）为重点可疑项'),
    }


# ---------------------------------------------------------------- 翻译
def mt_call(text, key, retries=2):
    payload = {'model': MT_MODEL, 'temperature': 0,
               'messages': [{'role': 'user', 'content': MT_PROMPT + '\n\n' + text}]}
    last = None
    for _ in range(retries + 1):
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
            json.dump(payload, f, ensure_ascii=False)
            tmp = f.name
        try:
            r = subprocess.run(
                ['curl', '-s', '-m', '120', '-X', 'POST', API,
                 '-H', f'Authorization: Bearer {key}',
                 '-H', 'Content-Type: application/json',
                 '-d', '@' + tmp],
                capture_output=True, text=True, timeout=150)
            d = json.loads(r.stdout)
            return d['choices'][0]['message']['content'].strip()
        except Exception as e:
            last = e
        finally:
            os.unlink(tmp)
    raise RuntimeError(f'MT failed after retries: {last}')


def translate_article(meta, paras, key):
    jobs = [('p1', meta['title'])] + [(f'p{i + 2}', p) for i, p in enumerate(paras)]
    extra = []
    if meta.get('dek'):
        extra.append(('dek', meta['dek']))
    if meta.get('byline'):
        extra.append(('byline', meta['byline']))

    def one(job):
        jid, en = job
        return jid, en, mt_call(en, key)

    out = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        for jid, en, cn in ex.map(one, jobs + extra):
            out[jid] = (en, cn)
    paragraphs = [{'id': jid, 'en': out[jid][0], 'cn': out[jid][1]} for jid, _ in jobs]
    tr = {'article_id': meta['id'], 'paragraphs': paragraphs}
    if 'dek' in out:
        tr['dek'] = {'en': out['dek'][0], 'cn': out['dek'][1]}
    if 'byline' in out:
        tr['byline'] = {'en': out['byline'][0], 'cn': out['byline'][1]}
    return tr


# ---------------------------------------------------------------- 资产
def subject_keywords(meta, paras):
    seed = ' '.join([meta.get('title') or '', meta.get('dek') or '',
                     paras[0] if paras else ''])
    words = re.findall(r"[A-Za-z']{4,}", seed.lower())
    return {w for w in words if w not in STOPWORDS}


def article_img_markers(span):
    """span 内的 <img bbox_…> 标记：位置 + caption（紧随其后的第一个非空段）。"""
    out = []
    for m in re.finditer(r'<img src="([^"]+)" />', span):
        rest = span[m.end():]
        cap = ''
        for chunk in re.split(r'\n\s*\n', rest):
            chunk = chunk.strip()
            if chunk:
                cap = chunk[:400]
                break
        out.append({'pos': m.start(), 'src': m.group(1), 'caption': cap})
    return out


def is_ad_marker(marker):
    cap = marker['caption']
    if re.match(r'(?i)^\s*ads?\s*$', cap):
        return True
    if re.search(r'(?i)advertisement', cap):
        return True
    return False


def pick_assets(pdf_page, span, meta, paras, out_dir):
    """通用"文章相关"判定：
    1) 标记必须在文章 span 内；
    2) 排除广告标记（caption 为裸 'ad'/advertisement；或 caption 与文章主题词
       零交集且不在文首 lead-art 位置）；
    3) bbox 为千分比 -> PDF 坐标，与页面内嵌图做 IoU 最佳匹配
       （IoU>=0.05 用内嵌图精确 rect，否则直接裁 bbox 区域），200dpi PNG。
    没有合格标记 -> 空 manifest，不硬找。"""
    import pymupdf
    markers = article_img_markers(span)
    kw = subject_keywords(meta, paras)
    qual = []
    for mk in markers:
        if is_ad_marker(mk):
            continue
        cap_words = set(re.findall(r"[A-Za-z']{4,}", mk['caption'].lower()))
        overlap = bool(cap_words & kw)
        lead_art = mk['pos'] < 1200
        if overlap or lead_art:
            qual.append(mk)
    assets_dir = os.path.join(out_dir, 'assets')
    os.makedirs(assets_dir, exist_ok=True)
    manifest = []
    if not qual:
        return manifest
    doc = pymupdf.open(PDF)
    pg = doc[pdf_page - 1]
    W, H = pg.rect.width, pg.rect.height
    imgs = []
    for info in pg.get_images():
        for r in pg.get_image_rects(info[0]):
            if r.width >= 100 and r.height >= 80:  # 跳过小图标/logo
                imgs.append(r)
    for i, mk in enumerate(qual):
        mm = re.search(r'bbox_(\d+)_(\d+)_(\d+)_(\d+)', mk['src'])
        if not mm:
            continue
        x1, y1, x2, y2 = (int(v) / 1000 for v in mm.groups())
        target = pymupdf.Rect(x1 * W, y1 * H, x2 * W, y2 * H)
        best, best_iou = None, 0.0
        for r in imgs:
            inter = r & target
            ia = inter.get_area()
            if ia <= 0:
                continue
            iou = ia / (r.get_area() + target.get_area() - ia)
            if iou > best_iou:
                best, best_iou = r, iou
        crop = best if (best is not None and best_iou >= 0.05) else target
        crop = crop & pg.rect
        fname = f'img-{i + 1}.png'
        pg.get_pixmap(clip=crop, dpi=200).save(os.path.join(assets_dir, fname))
        manifest.append({
            'file': fname,
            'page': pdf_page,
            'region': [round(crop.x0, 1), round(crop.y0, 1),
                       round(crop.x1, 1), round(crop.y1, 1)],
            'description': mk['caption'] or '(no caption in OCR)',
            'relation': 'photo/graphic located within the article area on the printed page',
        })
    doc.close()
    return manifest


# ---------------------------------------------------------------- Planner
def qwen_call(prompt, key, max_tokens=4000):
    payload = {'model': PLAN_MODEL, 'temperature': 0, 'max_tokens': max_tokens,
               'messages': [{'role': 'user', 'content': prompt}]}
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
        json.dump(payload, f, ensure_ascii=False)
        tmp = f.name
    try:
        r = subprocess.run(
            ['curl', '-s', '-m', '300', '-X', 'POST', API,
             '-H', f'Authorization: Bearer {key}',
             '-H', 'Content-Type: application/json',
             '-d', '@' + tmp],
            capture_output=True, text=True, timeout=330)
        d = json.loads(r.stdout)
        return d['choices'][0]['message']['content']
    finally:
        os.unlink(tmp)


def extract_json(s):
    s = s.strip()
    if s.startswith('```'):
        s = re.sub(r'^```[a-zA-Z]*\n?', '', s)
        s = re.sub(r'\n?```$', '', s)
    return json.loads(s[s.index('{'):s.rindex('}') + 1])


def build_planner_prompt(meta, tr, manifest):
    template = open(TEMPLATE, encoding='utf-8').read()
    schema = open(SCHEMA, encoding='utf-8').read()
    article = {
        'article_id': meta['id'], 'type': meta.get('type'),
        'title': meta['title'], 'title_cn': tr['paragraphs'][0]['cn'],
        'dek': meta.get('dek'), 'dek_cn': tr.get('dek', {}).get('cn'),
        'byline': meta.get('byline'),
        'paragraphs': tr['paragraphs'],
        'visual_assets': manifest,
    }
    return (template
            + '\n\n## Article (JSON)\n' + json.dumps(article, ensure_ascii=False, indent=1)
            + '\n\n## Hard constraint\nYour output MUST validate against the following JSON Schema. '
              'Where the shape sketch in the template conflicts with the schema, '
              'the schema wins: analysis.structure is an ARRAY of strings; '
              'analysis.needs_background is an OBJECT {"needed": bool, "what": str}; '
              'analysis.quotes[].para and analysis.timeline_events[].para are INTEGERS '
              '(1-based paragraph numbers matching the paragraph ids p1..pn); '
              'slot with at="after_para" MUST include "para" (0-based paragraph index); '
              'reason is REQUIRED for every component.\n'
            + schema)


def make_plan(meta, tr, manifest, key, out_dir):
    import jsonschema
    schema = json.load(open(SCHEMA, encoding='utf-8'))
    prompt = build_planner_prompt(meta, tr, manifest)
    raw = qwen_call(prompt, key)
    open(os.path.join(out_dir, 'planner-raw-1.txt'), 'w', encoding='utf-8').write(raw)
    plan = extract_json(raw)

    def check(p):
        try:
            jsonschema.validate(p, schema)
            return None
        except Exception as e:
            return str(e)

    err = check(plan)
    if err:
        open(os.path.join(out_dir, 'planner-validate-error.txt'), 'w',
             encoding='utf-8').write(err)
        raw2 = qwen_call(
            prompt + '\n\n## Validation error on your previous output\n'
            + err + '\nFix ONLY what the error reports and output the full corrected JSON.',
            key)
        open(os.path.join(out_dir, 'planner-raw-2.txt'), 'w', encoding='utf-8').write(raw2)
        plan = extract_json(raw2)
        err = check(plan)
        if err:
            raise ValueError(f'plan schema still failing after retry: {err[:800]}')
    plan.setdefault('created_by', 'generic-planner-v1')
    plan.setdefault('version', '1.0')
    return plan


# ---------------------------------------------------------------- 渲染
def render_html(meta, tr, plan, out_dir):
    from plan_render import render_article_with_plan
    from build_test_pages import build_page  # 页面壳：照抄 build_test_pages.build_page
    paras = tr['paragraphs']
    e = {'id': meta['id'], 'section': meta.get('section'), 'page': meta.get('page'),
         'priority': meta.get('priority'), 'type': meta.get('type'),
         'title_cn': paras[0]['cn'], 'title': meta['title'],
         'dek_cn': tr.get('dek', {}).get('cn'), 'dek': meta.get('dek'),
         'byline': meta.get('byline'),
         'body_cn': '\n\n'.join(p['cn'] for p in paras[1:]),
         'body_en': '\n\n'.join(p['en'] for p in paras[1:])}

    def asset_loader(fname):
        with open(os.path.join(out_dir, 'assets', fname), 'rb') as f:
            return base64.b64encode(f.read()).decode('ascii')

    article_html = render_article_with_plan(e, plan, {}, asset_loader)
    html = build_page(e, article_html, '')
    out = os.path.join(out_dir, 'article.html')
    open(out, 'w', encoding='utf-8').write(html)
    return out


# ---------------------------------------------------------------- 主流程
def process(aid, ocr_page, key, final):
    out_dir = os.path.join(BASE, aid)
    os.makedirs(out_dir, exist_ok=True)
    pdf_page = pdf_page_of(ocr_page)
    meta = next(x for x in final if x['id'] == aid)
    print(f'[{aid}] ocr-p{ocr_page}/pdf-p{pdf_page}: {meta["title"]}', flush=True)

    full = json.load(open(os.path.join(PAGES_DIR, f'page-{ocr_page}-ocr.json'),
                          encoding='utf-8'))['choices'][0]['message']['content']
    span, paras, dek_en, byline_en, ad_truncated, next_heading = segment(full, meta)
    warns = number_warnings(pdf_page, span, meta)
    json.dump({'article_id': aid, 'page': pdf_page,
               'ocr_page': ocr_page,
               'text': strip_img_markers(span).strip(),
               'ad_truncated': ad_truncated,
               'number_warnings': warns},
              open(os.path.join(out_dir, 'ocr.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'[{aid}] ocr.json: {len(paras)} paras, ad_truncated={ad_truncated}, '
          f'ocr_only={warns["ocr_only"]}', flush=True)

    tr = translate_article(meta, paras, key)
    json.dump(tr, open(os.path.join(out_dir, 'translation.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'[{aid}] translation.json done', flush=True)

    manifest = pick_assets(pdf_page, span, meta, paras, out_dir)
    json.dump(manifest, open(os.path.join(out_dir, 'asset-manifest.json'), 'w',
                             encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'[{aid}] assets: {len(manifest)}', flush=True)

    plan = make_plan(meta, tr, manifest, key, out_dir)
    json.dump(plan, open(os.path.join(out_dir, 'plan.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    comps = [c['component'] for c in plan.get('component_plan', [])]
    print(f'[{aid}] plan.json: {len(comps)} components {comps}', flush=True)

    html_path = render_html(meta, tr, plan, out_dir)
    print(f'[{aid}] {html_path} ({os.path.getsize(html_path) // 1024} KB)', flush=True)
    return out_dir


def main():
    key = get_key()
    final = json.load(open(FINAL, encoding='utf-8'))
    for aid, p in ARTICLES:
        try:
            process(aid, p, key, final)
        except Exception:
            print(f'[{aid}] FAILED', flush=True)
            import traceback
            traceback.print_exc()


if __name__ == '__main__':
    main()
