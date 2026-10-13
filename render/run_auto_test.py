#!/usr/bin/env python3
"""Editorial Intelligence 自主选择盲测：18 篇新文章。

流程/篇：
1. integrity_gate.check_article → block 级失败则 FAIL
2. autonomous_planner.call_planner → 六段式计划
3. plan_validate + validate_quote_bilingual → 失败则 FAIL
4. 渲染 article.html（ed-block 契约）
5. 截图 1440 + 390
输出：auto-test/<ID>/{plan.json, article.html, shot-1440.png, shot-390.png, validation.json}
"""
import base64
import json
import os
import re
import sys
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from source_model import SourceModel
from text_treatment import (
    TextOp, op_bold, op_number, op_attribution, op_subhead, op_group,
    op_list, render_block, TEXT_CSS,
)
from layout import (
    render_margin_note, render_compare, render_figure_text,
    render_wide_figure, LAYOUT_CSS, validate_mobile_order,
)
from components import esc, article_header
from autonomous_planner import call_planner, load_assets_for_article
from integrity_gate import check_article
from orchestrate import validate_quote_bilingual

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
FINAL = json.load(open(os.path.join(ROOT, '2026-10-12', 'final.json'), encoding='utf-8'))
OUT = os.path.join(ROOT, '2026-10-12', 'auto-test')
IDS = json.load(open('/tmp/blind18.json'))

PW = '/home/hatch/workspace/.tmp-chrome/shot-venv/bin/python'
SHOT = '/home/hatch/workspace/.tmp-chrome/shot.py'


def load_entry(aid):
    return next(x for x in FINAL if x['id'] == aid)


def make_source(aid):
    e = load_entry(aid)
    sm = SourceModel(aid)
    cn_paras = [p.strip() for p in (e.get('body_cn') or '').split('\n\n') if p.strip()]
    en_paras = [p.strip() for p in (e.get('body_en') or '').split('\n\n') if p.strip()]
    # p1 = 标题
    sm.add_block('p1', e.get('title') or '', e.get('title_cn') or '', role='title')
    n = max(len(cn_paras), len(en_paras))
    for i in range(n):
        cn = cn_paras[i] if i < len(cn_paras) else ''
        en = en_paras[i] if i < len(en_paras) else ''
        if cn or en:
            sm.add_block(f'p{i+2}', en, cn, role='body')
    return sm, e


def blocks_text(sm, locale):
    lines = []
    for b in sm.body_blocks():
        t = (b['cn'] if locale == 'cn' else b['en']) or ''
        if t.strip():
            lines.append(f"[{b['id']}] {t.strip()}")
    return '\n\n'.join(lines)


def build_treatments(sm, tplan):
    """planner 的 text_treatment_plan → TextOp 列表。失败的 op 跳过并记录。"""
    ops, skipped = [], []
    for item in (tplan or []):
        pid = item.get('pattern_id') or item.get('pattern') or ''
        try:
            if pid == 'T01':
                ops.append(op_bold(sm, item['block_id'], 'cn', item['snippet'],
                                   reason=item.get('reason', '')))
            elif pid == 'T03':
                ops.append(op_number(sm, item['block_id'], 'cn', item['snippet'],
                                     reason=item.get('reason', '')))
            elif pid == 'T06':
                ops.append(op_attribution(sm, item['block_id'], 'cn', item['snippet'],
                                          reason=item.get('reason', '')))
            elif pid == 'T09':
                ops.append(TextOp('T09', item['block_id'], 'cn', '',
                                  action='split',
                                  params={'after_sentence_idx': item.get('after_sentence_idx', 0)},
                                  reason=item.get('reason', '')))
            elif pid == 'T11':
                ops.append(op_subhead(item['before_block_id'],
                                      item.get('title_cn', ''),
                                      item.get('title_en', ''),
                                      reason=item.get('reason', '')))
            elif pid == 'T13':
                ops.append(op_list(sm, item['block_id'], 'cn',
                                   item.get('item_ranges', []),
                                   reason=item.get('reason', '')))
            else:
                skipped.append({'item': item, 'reason': f'未知 pattern {pid}'})
        except Exception as ex:
            skipped.append({'item': item, 'reason': str(ex)[:120]})
    return ops, skipped


def build_layouts(aid, sm, lplan):
    """planner 的 layout_plan → {anchor_wraps, after_blocks}。"""
    anchor_wraps, after_blocks, skipped = {}, {}, []
    for item in (lplan or []):
        pid = item.get('pattern_id') or ''
        try:
            if pid == 'L02':
                note = render_margin_note(
                    item['anchor_block'],
                    item.get('note_cn', ''), item.get('note_en', ''),
                    uid=f'{aid}-n1', editorial_added=True)
                anchor_wraps[item['anchor_block']] = note
            elif pid == 'L03':
                pairs = []
                for d in item.get('dims', []):
                    a = d.get('a', {})
                    b = d.get('b', {})
                    pairs.append(((a.get('cn', ''), a.get('en', '')),
                                  (b.get('cn', ''), b.get('en', ''))))
                html = ('<div class="ed-block">\n' +
                        render_compare(pairs, f'{aid}-c1',
                                       dim_labels=[d.get('label', '') for d in item.get('dims', [])]) +
                        '\n</div>')
                after_blocks.setdefault(item.get('after_block', item.get('anchor_block', '')), []).append(html)
            elif pid == 'L05':
                # 需要 asset；无 asset 则跳过
                skipped.append({'pattern': 'L05', 'reason': '无可用图片 asset，降级拒绝'})
            elif pid == 'L08':
                skipped.append({'pattern': 'L08', 'reason': '无可用图表 asset，降级拒绝'})
            elif pid == 'L01':
                pass  # 默认，无需操作
            else:
                skipped.append({'pattern': pid, 'reason': '未知 layout pattern'})
        except Exception as ex:
            skipped.append({'pattern': pid, 'reason': str(ex)[:120]})
    return {'anchor_wraps': anchor_wraps, 'after_blocks': after_blocks}, skipped


def build_aids(aid, sm, aplan):
    """planner 的 reading_aid_plan → component_plan 格式（供 plan_validate）。"""
    comps, skipped = [], []
    for item in (aplan or []):
        kind = item.get('type') or item.get('component') or ''
        try:
            if kind == 'quote':
                comps.append({'component': 'quote', 'data': {
                    'text_cn': item.get('text_cn', ''), 'text_en': item.get('text_en', ''),
                    'attr_cn': item.get('attr_cn', ''), 'attr_en': item.get('attr_en', '')}})
            elif kind == 'key_figures':
                comps.append({'component': 'key_figures', 'data': {
                    'items': item.get('items', [])}})
            elif kind == 'timeline':
                comps.append({'component': 'timeline', 'data': {
                    'timeline': {'title_cn': item.get('title_cn', '时间线'),
                                 'entries': item.get('entries', [])}}})
            elif kind == 'data_table':
                comps.append({'component': 'data_table', 'data': {}})
            else:
                skipped.append({'item': item, 'reason': f'未知 aid {kind}'})
        except Exception as ex:
            skipped.append({'item': item, 'reason': str(ex)[:120]})
    return comps, skipped


def render_body_flow(sm, treatments, layouts):
    ops_by_block, subheads, group_ranges = {}, {}, {}
    seen = set()
    for op in treatments:
        if op.action == 'subhead':
            subheads[op.block_id] = op
        elif op.action == 'group':
            key = tuple(op.params['blocks'])
            if key not in seen:
                seen.add(key)
                group_ranges[key[0]] = key
        else:
            ops_by_block.setdefault(op.block_id, []).append(op)
    anchor_wraps = layouts.get('anchor_wraps', {})
    after_blocks = layouts.get('after_blocks', {})
    h, in_group = [], None
    for b in sm.body_blocks():
        bid = b['id']
        if bid == 'p1':
            continue  # 标题由 article_header 渲染
        if bid in group_ranges and in_group is None:
            h.append('<div class="tt-group ed-block">')
            in_group = group_ranges[bid]
        if bid in subheads:
            op = subheads[bid]
            h.append(
                f'<h3 class="tt-subhead ed-block" data-editorial-added="true">'
                f'<span class="k-cn">{esc(op.params["title_cn"])}</span>'
                f'<span class="k-en" hidden>{esc(op.params.get("title_en", ""))}</span>'
                f'</h3>')
        cn_h, en_h = render_block(b, ops_by_block.get(bid, []))
        p_html = (f'<p class="ed-block" data-block="{bid}">'
                  f'<span class="k-cn">{cn_h}</span>'
                  f'<span class="k-en" hidden>{en_h}</span></p>')
        if bid in anchor_wraps:
            h.append(f'<div class="ed-block ly-anchor">\n{p_html}\n{anchor_wraps[bid]}\n</div>')
        else:
            h.append(p_html)
        for extra in after_blocks.get(bid, []):
            h.append(extra)
        if in_group and bid == in_group[-1]:
            h.append('</div>')
            in_group = None
    if in_group:
        h.append('</div>')
    return '\n'.join(h)


def extract_shell():
    src = os.path.join(ROOT, '2026-10-12', 'gen-test', 'E1-025', 'article.html')
    return open(src, encoding='utf-8').read()


def build_page(base_html, article_inner, aid):
    doc = re.sub(r'<title>.*?</title>',
                 f'<title>WSJ 深读 · {aid} 自主选择测试</title>', base_html, count=1)
    doc = doc.replace('</style>', TEXT_CSS + LAYOUT_CSS + '\n</style>', 1)
    doc = re.sub(r'<article.*?</article>', article_inner, doc, flags=re.S, count=1)
    return doc


def run_one(aid):
    d = os.path.join(OUT, aid)
    os.makedirs(d, exist_ok=True)
    val = {'article_id': aid, 'gates': {}, 'status': 'PENDING'}

    e = load_entry(aid)
    # Gate 1: 完整性
    passed, issues = check_article(e)
    val['gates']['integrity'] = {'passed': passed,
        'issues': issues}
    if not passed:
        val['status'] = 'FAIL'
        val['fail_reason'] = 'integrity_gate: ' + '; '.join(
            i['detail'] for i in issues if i['level'] == 'block')[:200]
        json.dump(val, open(os.path.join(d, 'validation.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        return val

    sm, _ = make_source(aid)
    meta = {'type': e.get('type'), 'priority': e.get('priority'),
            'section': e.get('section'), 'page': e.get('page')}
    # Planner
    try:
        assets = load_assets_for_article(aid)
        plan, _prompt = call_planner(aid, meta, blocks_text(sm, 'cn'), blocks_text(sm, 'en'), assets=assets)
    except Exception as ex:
        val['status'] = 'FAIL'
        val['fail_reason'] = f'planner 调用失败: {ex}'[:200]
        json.dump(val, open(os.path.join(d, 'validation.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        return val
    json.dump(plan, open(os.path.join(d, 'plan.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    treatments, t_skip = build_treatments(sm, plan.get('text_treatment_plan'))
    layouts, l_skip = build_layouts(aid, sm, plan.get('layout_plan'))
    aids, a_skip = build_aids(aid, sm, plan.get('reading_aid_plan'))
    val['skipped'] = {'treatments': t_skip, 'layouts': l_skip, 'aids': a_skip}

    # Gate 2: plan_validate（事实门禁）
    from plan_validate import validate as pv_validate
    import tempfile
    pv_plan = {'article_id': aid, 'component_plan': aids}
    src_text = (e.get('body_en') or '') + '\n' + (e.get('body_cn') or '')
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8') as tf:
        json.dump(pv_plan, tf, ensure_ascii=False)
        pv_path = tf.name
    pv_errors = pv_validate(pv_path, src_text)
    os.unlink(pv_path)
    val['gates']['plan_validate'] = {'passed': not pv_errors, 'errors': pv_errors}

    # Gate 3: 双语引语校验
    qb = validate_quote_bilingual({'component_plan': aids})
    qb_ok = all(ok for _, ok, _ in qb)
    val['gates']['quote_bilingual'] = {'passed': qb_ok,
        'results': [{'idx': i, 'ok': ok, 'msg': m} for i, ok, m in qb]}

    if pv_errors or not qb_ok:
        val['status'] = 'FAIL'
        val['fail_reason'] = ('plan_validate: ' + '; '.join(pv_errors[:3])[:200]
                              if pv_errors else 'quote_bilingual 未通过')
        json.dump(val, open(os.path.join(d, 'validation.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        return val

    # 渲染
    body_flow = render_body_flow(sm, treatments, layouts)
    # Aid 组件渲染（quote/key_figures/timeline）
    aid_htmls = []
    for comp in aids:
        name = comp['component']
        dd = comp['data']
        try:
            if name == 'quote':
                from components import quote as c_quote
                aid_htmls.append('<div class="ed-block">\n' + c_quote({
                    'text_cn': dd.get('text_cn', ''), 'text_en': dd.get('text_en', ''),
                    'attr_cn': dd.get('attr_cn', ''), 'attr_en': dd.get('attr_en', '')}) + '\n</div>')
            elif name == 'key_figures':
                from components import key_figures as c_kf
                items = dd.get('items', [])
                norm_items = []
                for it in items:
                    norm_items.append({
                        'value_cn': it.get('value_cn', it.get('value', '')),
                        'value_en': it.get('value_en', it.get('value', '')),
                        'label_cn': it.get('label_cn', it.get('label', '')),
                        'label_en': it.get('label_en', it.get('label', '')),
                        'note_cn': it.get('note_cn', it.get('note', '')),
                        'note_en': it.get('note_en', it.get('note', ''))})
                aid_htmls.append('<div class="ed-block">\n' + c_kf(norm_items, aid) + '\n</div>')
            elif name == 'timeline':
                from components import timeline as c_tl
                aid_htmls.append('<div class="ed-block">\n' + c_tl(dd.get('timeline', {}), aid) + '\n</div>')
        except Exception as ex:
            val.setdefault('render_warnings', []).append(f'{name}: {ex}'[:120])
    full_body = body_flow + ('\n' + '\n'.join(aid_htmls) if aid_htmls else '')
    article = (f'<article class="story story-plan" id="s-{aid}" aria-label="{aid}">\n'
               f'<div class="sheet">\n{article_header(e)}\n{full_body}\n</div>\n</article>')
    html = build_page(extract_shell(), article, aid)
    open(os.path.join(d, 'article.html'), 'w', encoding='utf-8').write(html)

    # 门禁：ed-tag / (pN) 不许进页面
    body = html.split('</style>')[-1]
    leak = []
    if 'ed-tag' in body:
        leak.append('ed-tag')
    if re.search(r'\(p\d+\)', body):
        leak.append('(pN)')
    mo_issues = validate_mobile_order(html)
    if mo_issues:
        leak.append(f'mobile_order: {mo_issues}')
    val['gates']['render_leak'] = {'passed': not leak, 'issues': leak}
    if leak:
        val['status'] = 'FAIL'
        val['fail_reason'] = '渲染泄漏: ' + '; '.join(leak)[:200]
        json.dump(val, open(os.path.join(d, 'validation.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        return val

    # 截图
    for vw, fn in [(1440, 'shot-1440.png'), (390, 'shot-390.png')]:
        r = subprocess.run([PW, SHOT, f'file://{d}/article.html', 'article',
                            f'auto-{aid}-{vw}.png'] +
                           (['mobile'] if vw == 390 else []),
                           capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            val.setdefault('render_warnings', []).append(f'截图 {vw} 失败: {r.stderr[:100]}')
    # 截图搬到输出目录
    import shutil
    shots_dir = '/home/hatch/workspace/wsj-deep-read/2026-10-12/cases/shots'
    for vw, fn in [(1440, 'shot-1440.png'), (390, 'shot-390.png')]:
        src = os.path.join(shots_dir, f'auto-{aid}-{vw}.png')
        if os.path.exists(src):
            shutil.move(src, os.path.join(d, fn))

    val['status'] = 'PASS'
    val['layout_chosen'] = [ (i.get('pattern_id'), i.get('anchor_block') or i.get('after_block'))
                             for i in (plan.get('layout_plan') or []) ]
    val['rejected'] = [ (i.get('pattern_id'), (i.get('reason_against') or '')[:80])
                        for i in (plan.get('rejected_candidates') or []) ]
    json.dump(val, open(os.path.join(d, 'validation.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    return val


if __name__ == '__main__':
    only = sys.argv[1:] or IDS
    results = []
    for aid in only:
        if aid not in IDS:
            print(f'{aid}: 不在盲测名单，跳过')
            continue
        try:
            v = run_one(aid)
        except Exception as ex:
            v = {'article_id': aid, 'status': 'FAIL', 'fail_reason': f'异常: {ex}'[:200]}
            import traceback; traceback.print_exc()
        results.append((v['article_id'], v['status'],
                        v.get('fail_reason', ''),
                        str(v.get('layout_chosen', ''))))
        print(f"{v['article_id']}: {v['status']} {v.get('fail_reason','')[:80]} "
              f"layout={v.get('layout_chosen','')}")
    print('\n=== 汇总 ===')
    for r in results:
        print(r)
