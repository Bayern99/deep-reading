#!/usr/bin/env python3
"""5 篇盲测：Editorial Enhancement 全流程（通用编排，无单篇硬编码）。

流程：source_model → LLM planner（三层决策）→ TextOp 转换（exact match）
      → plan_validate 门禁 → 增强 plan → full enhancement HTML → 截图。

铁律：不手工改 HTML；不为单篇加规则；plan_validate 必须通过；正文一字不改。
"""
import base64
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from source_model import build_source
from text_treatment import (
    op_bold, op_number, op_attribution, op_subhead, op_group,
    op_split, op_list, op_mix_spans, TextOp, TEXT_CSS, render_block,
)
from layout import LAYOUT_CSS
from components import esc, article_header
from plan_render import _render_component

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
BLIND5 = os.path.join(ROOT, '2026-10-12', 'blind5')
FINAL = json.load(open(os.path.join(ROOT, '2026-10-12', 'final.json'), encoding='utf-8'))
BYID = {e['id']: e for e in FINAL}
SHELL_SRC = os.path.join(ROOT, '2026-10-12', 'gen-test', 'E1-025', 'article.html')

OMLX = 'http://127.0.0.1:18800/v1/chat/completions'
PLANNER_MODEL = 'Qwen3.8-27B-oQ4e-mtp'


def api_key():
    return json.load(open(os.path.expanduser('~/.pi/agent/models.json')))['providers']['omlx']['apiKey']


PLANNER_PROMPT = """你是 WSJ 深读的编辑规划师。为给定文章生成增强计划，只输出 JSON。

## 文章
类型：{atype}｜优先级：{prio}｜版面：{section} {page}

### 中文正文（p1 为标题，不处理）
{cn_blocks}

### 英文正文（辅助理解，决策以中文为准）
{en_blocks}

## 可用模式

**Text Treatment**（snippet 必须逐字来自中文正文，一字不差）：
- T01 语义加粗：加粗承载核心事实/转折的短语。给 block_id + snippet。
- T03 数字强调：强调关键数字。给 block_id + snippet。
- T06 引述归属：标识易混淆的引语说话人。给 block_id + snippet。
- T09 段落拆分：拆分过长段落。给 block_id + after_sentence_idx（第几个句号后拆，从0数）。
- T11 编辑小标题：在某段前插入小标题（新增文字）。给 before_block_id + title_cn + title_en。
- T13 并列列表：段落转列表。给 block_id + items（每项逐字来自正文）。

**Layout**：默认 L01 单栏。L05 图文并置仅在有图时考虑。

**Reading Aid**（data 内容必须逐字来自正文，不许编造；日期不许加年份）：
- key_figures：3-6 个关键数字，slot 建议 after_para:1 或 after_body。
  data.items 每项：value_cn/value_en/label_cn/label_en/note_cn/note_en。
- timeline：仅当有 ≥4 个可定日期事件且日期在原文逐字出现时。
  data.timeline：title_cn/title_en + entries[{{t_cn/t_en/text_cn/text_en}}]。
- quote：仅当有具名人物直接引语时，取一句话逐字，带署名。
  data.quote：text_cn/text_en/attr_cn/attr_en。
- context_box：仅当原文自带背景信息需要折叠时（无需 data）。
- data_table：仅 data_table 类型文章。

## 铁律
1. snippet/items/引文/日期必须逐字来自正文；时间线日期不许添加原文没有的年份。
2. 同一信息不许同时进正文强调和 Aid 组件。
3. 无候选时 treatments/aids 可为空数组——接受零处理。
4. 每项写清 reason（中文）。

## 只输出 JSON（无 markdown fences）
{{
  "narrative_outline": [{{"block_ids": ["p2"], "function": "scene|background|claim|evidence|contrast|consequence", "reader_need": "..."}}],
  "treatments": [
    {{"pattern": "T01", "block_id": "p5", "locale": "cn", "snippet": "逐字片段", "reason": "..."}},
    {{"pattern": "T11", "before_block_id": "p9", "title_cn": "...", "title_en": "...", "reason": "..."}},
    {{"pattern": "T13", "block_id": "p7", "locale": "cn", "items": ["逐字条目"], "reason": "..."}},
    {{"pattern": "T09", "block_id": "p12", "locale": "cn", "after_sentence_idx": 1, "reason": "..."}}
  ],
  "layouts": [{{"pattern_id": "L01", "action": "apply", "reason": "..."}}],
  "aids": [
    {{"component": "key_figures", "slot": {{"at": "after_para", "para": 1}}, "reason": "...", "data": {{"items": [{{"value_cn": "...", "value_en": "...", "label_cn": "...", "label_en": "...", "note_cn": "...", "note_en": "..."}}]}}}},
    {{"component": "quote", "slot": {{"at": "after_para", "para": 5}}, "reason": "...", "data": {{"quote": {{"text_cn": "逐字", "text_en": "...", "attr_cn": "...", "attr_en": "..."}}}}}}
  ],
  "rejected_opportunities": [
    {{"pattern_id": "T09", "action": "decline", "reason_against": "...", "fallback_pattern_id": "T00"}}
  ]
}}
"""


def call_planner(aid, meta, cn_blocks, en_blocks):
    prompt = PLANNER_PROMPT.format(
        atype=meta['type'], prio=meta['priority'],
        section=meta['section'], page=meta['page'],
        cn_blocks=cn_blocks, en_blocks=en_blocks)
    payload = {
        'model': PLANNER_MODEL,
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0, 'max_tokens': 6000,
    }
    r = subprocess.run(
        ['curl', '-s', '--max-time', '300',
         '-H', f'Authorization: Bearer {api_key()}',
         '-H', 'Content-Type: application/json',
         OMLX, '-d', json.dumps(payload)],
        capture_output=True, text=True)
    d = json.loads(r.stdout)
    content = d['choices'][0]['message']['content']
    # 去 markdown fences
    content = re.sub(r'^```\w*\n?', '', content.strip())
    content = re.sub(r'\n?```$', '', content.strip())
    # 提取最外层 JSON
    m = re.search(r'\{.*\}', content, re.S)
    return json.loads(m.group(0))


def treatments_from_decisions(sm, decisions, rejected):
    """LLM 决策 → TextOp（exact match 失败的记入 rejected）。"""
    ops = []
    conv = {
        'T01': lambda t: op_bold(sm, t['block_id'], t.get('locale', 'cn'), t['snippet'], t.get('reason', '')),
        'T03': lambda t: op_number(sm, t['block_id'], t.get('locale', 'cn'), t['snippet'], t.get('reason', '')),
        'T06': lambda t: op_attribution(sm, t['block_id'], t.get('locale', 'cn'), t['snippet'], t.get('reason', '')),
        'T09': lambda t: op_split(sm, t['block_id'], t.get('locale', 'cn'), t.get('after_sentence_idx', 0), t.get('reason', '')),
        'T11': lambda t: op_subhead(t['before_block_id'], t['title_cn'], t.get('title_en', ''), t.get('reason', '')),
    }
    for t in decisions.get('treatments', []):
        pat = t.get('pattern')
        try:
            if pat == 'T13':
                text = sm.get_text(t['block_id'], t.get('locale', 'cn'))
                ranges = []
                for item in t['items']:
                    i = text.find(item)
                    if i < 0:
                        raise ValueError(f'T13 item exact match failed: {item[:30]}')
                    ranges.append((i, i + len(item)))
                ops.append(op_list(sm, t['block_id'], t.get('locale', 'cn'), ranges, t.get('reason', '')))
            elif pat in conv:
                ops.append(conv[pat](t))
            else:
                rejected.append({'pattern_id': pat, 'action': 'decline',
                                 'reason_against': f'未知 pattern，不执行：{pat}',
                                 'fallback_pattern_id': 'T00'})
        except (ValueError, KeyError) as ex:
            rejected.append({'pattern_id': pat, 'action': 'decline',
                             'reason_against': f'exact match 或参数失败，放弃执行：{ex}',
                             'fallback_pattern_id': 'T00'})
    # T17：通用混排（所有中文块自动处理）
    for b in sm.blocks:
        if b['role'] == 'body' and b['cn']:
            spans = op_mix_spans(b['cn'])
            if spans:
                ops.append(TextOp('T17', b['id'], 'cn', b['cn'], action='mix',
                                  params={'spans': spans},
                                  reason='英文专名/数字混排，加 tt-mix 保证不断行断裂'))
    return ops


def norm(s):
    return re.sub(r'\s+', ' ', s or '').strip().lower()


def prevalidate_aid(aid, comp, src_en, src_cn):
    """Aid 入 plan 前的事实门禁；返回 (ok, reason)。"""
    data = comp.get('data', {})
    name = comp.get('component')
    if name == 'timeline':
        for i, e in enumerate(data.get('timeline', {}).get('entries', [])):
            for key in ('t_en', 't_cn'):
                t = e.get(key, '')
                if not t:
                    continue
                hit = norm(t) in src_en or norm(t) in src_cn
                if not hit:
                    if re.search(r'20\d{2}', t) and not re.search(r'20\d{2}', src_en + src_cn):
                        return False, f'timeline[{i}].{key}="{t}" 编造了年份'
                    return False, f'timeline[{i}].{key}="{t}" 原文无逐字对应'
    if name == 'quote':
        q = data.get('quote', {})
        qt = q.get('text_cn', '')
        if qt and norm(qt) not in src_cn and norm(qt) not in src_en:
            return False, f'quote 引文非逐字："{qt[:40]}..."'
    if name == 'key_figures':
        for i, s in enumerate(data.get('items', [])):
            v = s.get('value_cn', '')
            if v and norm(v) not in src_cn and norm(v) not in src_en:
                return False, f'key_figures[{i}] value="{v}" 原文无逐字对应'
    return True, ''


def run_plan_validate(plan_path, source_text):
    with open('/tmp/blind5_src.txt', 'w', encoding='utf-8') as f:
        f.write(source_text)
    r = subprocess.run(
        [sys.executable, os.path.join(BASE, 'plan_validate.py'),
         plan_path, '/tmp/blind5_src.txt'],
        capture_output=True, text=True)
    return r.returncode == 0, r.stdout + r.stderr


# ---------------- 渲染 ----------------

def render_body_full(sm, treatments):
    """通用正文流渲染（含 T09 拆分、T13 列表、T11 小标题、T10 分组）。"""
    ops_by_block = {}
    subheads = {}
    for op in treatments:
        if op.action == 'subhead':
            subheads[op.block_id] = op
        elif op.action == 'group':
            pass  # 下方统一处理
        else:
            ops_by_block.setdefault(op.block_id, []).append(op)

    group_ranges = {}
    seen = set()
    for op in treatments:
        if op.action == 'group':
            key = tuple(op.params['blocks'])
            if key not in seen:
                seen.add(key)
                group_ranges[key[0]] = key

    # T09/T13 按 block 索引
    split_ops = {op.block_id: op for op in treatments if op.action == 'split'}
    list_ops = {op.block_id: op for op in treatments if op.action == 'list'}

    h = []
    in_group = None
    for b in sm.blocks:
        if b['role'] == 'title':
            continue
        if b['role'] == 'caption_duplicate':
            continue
        bid = b['id']
        if bid in group_ranges and in_group is None:
            h.append('<div class="tt-group">')
            in_group = group_ranges[bid]
        if bid in subheads:
            op = subheads[bid]
            h.append(
                f'<h3 class="tt-subhead" data-editorial-added="true">'
                f'<span class="k-cn">{esc(op.params["title_cn"])}</span>'
                f'<span class="k-en" hidden>{esc(op.params.get("title_en", ""))}</span>'
                f'</h3>')

        if bid in split_ops:
            op = split_ops[bid]
            cut = op.params['cut']
            loc = op.locale
            cn, en = b['cn'], b['en']
            # 同句序号切英文
            from text_treatment import SENT_END
            en_bounds = [m.end() for m in SENT_END.finditer(en)] if en else []
            idx = 0
            # 找到 cut 对应的句序号
            cn_bounds = [m.end() for m in SENT_END.finditer(cn)]
            try:
                sidx = cn_bounds.index(cut)
            except ValueError:
                sidx = 0
            ecut = en_bounds[sidx] if sidx < len(en_bounds) else len(en)
            c1, c2 = cn[:cut], cn[cut:]
            e1, e2 = en[:ecut], en[ecut:]
            # wrap ops 分别应用到两段
            w1 = [o for o in ops_by_block.get(bid, []) if o.action == 'wrap' or o.action == 'mix']
            cn_h1, _ = render_block({'id': bid, 'cn': c1, 'en': ''},
                                    [o for o in w1 if o.locale == 'cn'])
            cn_h2, _ = render_block({'id': bid, 'cn': c2, 'en': ''},
                                    [o for o in w1 if o.locale == 'cn'])
            h.append(f'<p data-block="{bid}-a"><span class="k-cn">{cn_h1}</span>'
                     f'<span class="k-en" hidden>{esc(e1)}</span></p>')
            h.append(f'<p data-block="{bid}-b"><span class="k-cn">{cn_h2}</span>'
                     f'<span class="k-en" hidden>{esc(e2)}</span></p>')
        elif bid in list_ops:
            op = list_ops[bid]
            items = op.params['items']
            lis = []
            for it in items:
                # item 内的 wrap ops
                ih, _ = render_block({'id': bid, 'cn': it, 'en': ''},
                                     [o for o in ops_by_block.get(bid, [])
                                      if o.action in ('wrap', 'mix') and o.locale == 'cn'])
                lis.append(f'<li><span class="k-cn">{ih}</span></li>')
            h.append(f'<ul class="tt-list" data-block="{bid}">' + ''.join(lis) +
                     f'<span class="k-en" hidden>{esc(b["en"])}</span></ul>')
        else:
            cn_h, en_h = render_block(b, ops_by_block.get(bid, []))
            h.append(f'<p data-block="{bid}"><span class="k-cn">{cn_h}</span>'
                     f'<span class="k-en" hidden>{en_h}</span></p>')

        if in_group and bid == in_group[-1]:
            h.append('</div>')
            in_group = None
    if in_group:
        h.append('</div>')
    return '\n'.join(h)


def render_aids(plan, e):
    h = []
    for cp in plan.get('component_plan', []):
        try:
            h.append(_render_component(cp, e, e['id'], {}, None))
        except Exception as ex:
            h.append(f'<!-- aid render failed: {cp.get("component")}: {ex} -->')
            cp['_render_error'] = str(ex)
    return h


def extract_shell():
    html = open(SHELL_SRC, encoding='utf-8').read()
    css = re.search(r'<style>(.*?)</style>', html, re.S).group(1)
    return css, html


def build_full_page(aid, e, sm, treatments, plan, css, base_html):
    body_html = render_body_full(sm, treatments)
    aids = render_aids(plan, e)
    aid_htmls = aids  # 与 component_plan 一一对应

    h = [f'<article class="story story-plan" id="s-{aid}" aria-label="{aid}">',
         '<div class="sheet">', article_header(e)]
    for cp, ah in zip(plan.get('component_plan', []), aid_htmls):
        if cp['slot']['at'] == 'before_body':
            h.append(ah)
    after_para = {}
    for cp, ah in zip(plan.get('component_plan', []), aid_htmls):
        if cp['slot']['at'] == 'after_para':
            after_para.setdefault(cp['slot']['para'], []).append(ah)
    id2n = {}
    n = 0
    for b in sm.blocks:
        if b['role'] in ('body',):
            n += 1
            id2n[b['id']] = n
    # data-block 可能是 pN / pN-a / pN-b
    parts = re.split(r'(?=<p data-block=|<ul class="tt-list"|<h3 class="tt-subhead|<div class="tt-group">)', body_html)
    for part in parts:
        if not part.strip():
            continue
        h.append(part)
        m = re.search(r'data-block="(p\d+)', part)
        if m:
            pn = id2n.get(m.group(1))
            if pn and pn in after_para:
                h.extend(after_para[pn])
    for cp, ah in zip(plan.get('component_plan', []), aid_htmls):
        if cp['slot']['at'] == 'after_body':
            h.append(ah)
    h.append('</div>\n</article>')
    article_inner = '\n'.join(h)

    doc = re.sub(r'<title>.*?</title>',
                 f'<title>WSJ 深读 · {aid} 增强版</title>', base_html, count=1)
    doc = doc.replace('</style>', TEXT_CSS + LAYOUT_CSS + '\n</style>', 1)
    doc = re.sub(r'<article.*?</article>', article_inner, doc, flags=re.S, count=1)
    doc = doc.replace('Editorial Plan 测试', f'{aid} · 增强版', 1)
    return doc


EXE = '/home/hatch/workspace/.tmp-chrome/chrome-headless-shell-linux64/chrome-headless-shell'


def screenshot(html_path, out_path, width):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=EXE)
        pg = b.new_page(viewport={'width': width, 'height': 900})
        pg.goto('file://' + html_path, wait_until='networkidle')
        pg.wait_for_timeout(1200)
        pg.screenshot(path=out_path, full_page=True)
        b.close()


# ---------------- 主流程 ----------------

ARTICLES = ['E2-002', 'E1-010', 'E2-018', 'E1-015', 'E2-012']


def process_one(aid):
    out_dir = os.path.join(BLIND5, aid)
    os.makedirs(out_dir, exist_ok=True)
    e = BYID[aid]
    meta = {'type': e['type'], 'priority': e['priority'],
            'section': e['section'], 'page': e['page']}
    report = {'article_id': aid, 'treatments_used': [], 'layouts_used': [],
              'aids_used': [], 'rejected': [], 'anomalies': []}

    # 1. 源模型
    sm, marked = build_source(aid, os.path.join(out_dir, 'translation.json'),
                             p1_is_title=False)
    print(f'[{aid}] 源模型：{len(sm.blocks)} 块')

    # 2. LLM planner（planner-raw.json 已存在则复用，避免重复调用）
    cn_blocks = '\n'.join(f'[{b["id"]}] {b["cn"]}' for b in sm.blocks if b['role'] != 'title')
    en_blocks = '\n'.join(f'[{b["id"]}] {b["en"]}' for b in sm.blocks if b['role'] != 'title')
    # 超长截断（E2-002 40 段）：保留全部中文，英文截断到 12000 字符
    if len(en_blocks) > 12000:
        en_blocks = en_blocks[:12000] + '\n...(truncated)'
    raw_path = os.path.join(out_dir, 'planner-raw.json')
    dec = None
    if os.path.exists(raw_path):
        try:
            d0 = json.load(open(raw_path, encoding='utf-8'))
            if isinstance(d0, dict) and 'treatments' in d0 and 'aids' in d0:
                dec = d0
                print(f'[{aid}] 复用已存 planner 决策')
        except Exception:
            pass
    if dec is None:
        try:
            dec = call_planner(aid, meta, cn_blocks, en_blocks)
        except Exception as ex:
            report['anomalies'].append(f'planner 调用失败：{ex}')
            dec = {'narrative_outline': [], 'treatments': [], 'layouts': [],
                   'aids': [], 'rejected_opportunities': []}
        json.dump(dec, open(raw_path, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)

    # 3. Treatment 转换
    rejected = list(dec.get('rejected_opportunities', []))
    treatments = treatments_from_decisions(sm, dec, rejected)
    # exact match 二次校验
    for op in treatments:
        if op.action in ('wrap',) and not sm.check_exact(op.block_id, op.locale, op.text_exact):
            rejected.append({'pattern_id': op.pattern_id, 'action': 'decline',
                             'reason_against': f'渲染前 exact match 失败：{op.block_id}',
                             'fallback_pattern_id': 'T00'})
    treatments = [op for op in treatments
                  if not any(r.get('reason_against', '').startswith('渲染前 exact match 失败') and op.pattern_id in r.get('pattern_id', '')
                             for r in rejected[-10:])]

    # 4. Aid 预校验（事实门禁）
    src_en = norm(' '.join(b['en'] for b in sm.blocks))
    src_cn = norm(' '.join(b['cn'] for b in sm.blocks))
    aids_ok = []
    for comp in dec.get('aids', []):
        ok, reason = prevalidate_aid(aid, comp, src_en, src_cn)
        if ok:
            aids_ok.append(comp)
        else:
            rejected.append({'pattern_id': comp.get('component'), 'action': 'decline',
                             'reason_against': f'事实门禁拦截：{reason}',
                             'fallback_pattern_id': 'none'})

    # 5. 增强 plan
    plan = {
        'article_id': aid, 'schema_version': '0.2-enh',
        'narrative_outline': dec.get('narrative_outline', []),
        'text_treatments': [op.to_dict() for op in treatments],
        'layout_decisions': dec.get('layouts', []),
        'component_plan': aids_ok,
        'rejected_opportunities': rejected,
        'dedup': {'caption_duplicates_skipped': marked},
    }
    plan_path = os.path.join(out_dir, 'plan.json')
    json.dump(plan, open(plan_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # 6. plan_validate 最终门禁
    src_text = '\n'.join(b['en'] + '\n' + b['cn'] for b in sm.blocks)
    ok, msg = run_plan_validate(plan_path, src_text)
    if not ok:
        report['anomalies'].append(f'plan_validate 未通过：{msg[:300]}')
        print(f'[{aid}] plan_validate FAILED:\n{msg[:500]}')
    else:
        print(f'[{aid}] plan_validate 通过')

    # 7. 渲染
    css, base_html = extract_shell()
    html = build_full_page(aid, e, sm, treatments, plan, css, base_html)
    html_path = os.path.join(out_dir, 'article.html')
    open(html_path, 'w', encoding='utf-8').write(html)

    # 8. 截图
    screenshot(html_path, os.path.join(out_dir, 'shot-d.png'), 1440)
    screenshot(html_path, os.path.join(out_dir, 'shot-m.png'), 390)
    print(f'[{aid}] 截图完成')

    # 报告
    report['treatments_used'] = sorted({op.pattern_id for op in treatments})
    report['layouts_used'] = [l.get('pattern_id') for l in dec.get('layouts', [])]
    report['aids_used'] = [(c.get('component'), c.get('slot')) for c in aids_ok]
    report['rejected'] = [(r.get('pattern_id'), r.get('reason_against', '')[:60]) for r in rejected]
    report['n_blocks'] = len(sm.blocks)
    report['n_treatments'] = len(treatments)
    report['plan_validate_ok'] = ok
    json.dump(report, open(os.path.join(out_dir, 'report.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    return report


if __name__ == '__main__':
    which = sys.argv[1:] or ARTICLES
    all_reports = {}
    for aid in which:
        if aid not in ARTICLES:
            print(f'跳过未知文章：{aid}')
            continue
        try:
            all_reports[aid] = process_one(aid)
        except Exception as ex:
            import traceback
            traceback.print_exc()
            all_reports[aid] = {'article_id': aid, 'error': str(ex)}
    print(json.dumps(all_reports, ensure_ascii=False, indent=1))
