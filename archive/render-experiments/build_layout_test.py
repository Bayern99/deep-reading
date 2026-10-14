#!/usr/bin/env python3
"""Layout Intelligence 真实验证：5 篇新文章的布局能力测试。

E1-007: L02 边注（预测市场解释）+ T01/T11
E2-031: L03 并列双栏（无人机对比）+ L05 图文并置（基辅照片）+ T01/T03/T11
E3-036: L08 跨栏图表（股价图）
E1-011: L02 边注（哈马克身份）+ T01/T11
E2-005: T10 分组 + T11 小标题 + T01

布局契约：所有正文流元素带 ed-block；.sheet>.ed-block 统一 640px。
L02 用 .ly-anchor wrapper（≥1200px 右栏，<1200px inline）。
"""
import base64
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from source_model import SourceModel
from text_treatment import (
    TextOp, op_bold, op_number, op_attribution, op_subhead, op_group,
    render_block, TEXT_CSS,
)
from layout import (
    render_margin_note, render_compare, render_figure_text,
    render_wide_figure, LAYOUT_CSS, validate_mobile_order,
)
from components import esc, article_header

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(BASE))
FINAL = json.load(open(os.path.join(ROOT, '2026-10-12', 'final.json'), encoding='utf-8'))
OUT = os.path.join(ROOT, '2026-10-12', 'archive', 'historical-outputs', 'layout-test')

# 素材
KYIV_IMG = '/tmp/kyiv/p17-000.png'
CHART_IMG = '/tmp/b7/chart-shareprice.png'


def load_entry(aid):
    return next(x for x in FINAL if x['id'] == aid)


def make_source(aid):
    """从 final.json 建 SourceModel（p1..pN）。"""
    e = load_entry(aid)
    sm = SourceModel(aid)
    cn_paras = [p.strip() for p in (e.get('body_cn') or '').split('\n\n') if p.strip()]
    en_paras = [p.strip() for p in (e.get('body_en') or '').split('\n\n') if p.strip()]
    n = max(len(cn_paras), len(en_paras))
    for i in range(n):
        cn = cn_paras[i] if i < len(cn_paras) else ''
        en = en_paras[i] if i < len(en_paras) else ''
        if cn or en:
            sm.add_block(f'p{i+1}', en, cn, role='body')
    return sm, e


def extract_shell():
    src = os.path.join(ROOT, '2026-10-12', 'archive', 'experiments', 'gen-test', 'E1-025', 'article.html')
    html = open(src, encoding='utf-8').read()
    return html


def build_page(base_html, article_inner, aid, title_suffix):
    doc = re.sub(r'<title>.*?</title>',
                 f'<title>WSJ 深读 · {aid} 布局测试 {title_suffix}</title>',
                 base_html, count=1)
    doc = doc.replace('</style>', TEXT_CSS + LAYOUT_CSS + '\n</style>', 1)
    doc = re.sub(r'<article.*?</article>', article_inner, doc, flags=re.S, count=1)
    doc = doc.replace('Editorial Plan 测试', '布局测试', 1)
    return doc


def render_body_flow(sm, treatments, layouts):
    """渲染正文流。layouts: {after_block_id: html} 插入；anchor 包裹由调用方处理。"""
    ops_by_block = {}
    subheads = {}
    groups = {}
    for op in treatments:
        if op.action == 'subhead':
            subheads[op.block_id] = op
        elif op.action == 'group':
            for bid in op.params['blocks']:
                groups[bid] = op.params['blocks']
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

    # L02 anchor 包装
    anchor_wraps = layouts.get('anchor_wraps', {})  # block_id -> note_html
    after_blocks = layouts.get('after_blocks', {})  # block_id -> [html]

    h = []
    in_group = None
    for b in sm.body_blocks():
        bid = b['id']
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


def wrap_aid(html):
    """Aid 组件包 ed-block（跨栏组件除外，由调用方决定）。"""
    return f'<div class="ed-block">\n{html}\n</div>'


def write_article(aid, body_flow_html, extra_head=''):
    e = load_entry(aid)
    base = extract_shell()
    article = (
        f'<article class="story story-plan" id="s-{aid}" aria-label="{aid}">\n'
        f'<div class="sheet">\n{article_header(e)}\n{extra_head}\n{body_flow_html}\n</div>\n</article>')
    return build_page(base, article, aid, '布局测试')


def save(aid, html, plan):
    d = os.path.join(OUT, aid)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, 'article.html'), 'w', encoding='utf-8').write(html)
    json.dump(plan, open(os.path.join(d, 'plan.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    # 门禁：ed-tag / (pN) 不许出现在页面 body
    body = html.split('</style>')[-1]
    assert 'ed-tag' not in body, f'{aid}: ed-tag 泄漏'
    assert not re.search(r'\(p\d+\)', body), f'{aid}: (pN) 泄漏'
    issues = validate_mobile_order(html)
    assert not issues, f'{aid}: mobile order {issues}'
    print(f'{aid}: OK ({len(html)//1024}KB)')
