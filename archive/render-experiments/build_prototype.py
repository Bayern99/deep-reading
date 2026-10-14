#!/usr/bin/env python3
"""E1-025 三版原型：baseline / text-only / full-enhancement。

- baseline.html：现有 article.html 原样复制（当前 plan_render 效果）。
- text-only.html：仅 Text Treatment（无 Aid 组件；caption_duplicate 跳过；T11/T10/T01/T03/T06/T17）。
- full.html：Text Treatment + Layout + Aids（quote 已去重缩减为单句；p2 跳过）。

视觉 token 沿用既有 CSS（从 article.html 提取 <style>），不新增色板。
"""
import base64
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from source_model import build_source
from text_treatment import render_block, TEXT_CSS
from layout import LAYOUT_CSS
from components import esc, article_header
from plan_render import _render_component

BASE = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(os.path.dirname(BASE), '2026-10-12', 'gen-test', 'E1-025')
OUT = os.path.join(os.path.dirname(BASE), '2026-10-12', 'gen-test', 'E1-025', 'prototype')
ASSET_DIR = os.path.join(os.path.dirname(BASE), '2026-10-12', 'gen-test', 'E1-025', 'assets')


def load_assets():
    out = {}
    for f in os.listdir(ASSET_DIR):
        with open(os.path.join(ASSET_DIR, f), 'rb') as fh:
            out[f] = base64.b64encode(fh.read()).decode('ascii')
    return out


def extract_shell():
    """从现有 article.html 提取 <style> 与页面壳。"""
    html = open(os.path.join(GEN, 'article.html'), encoding='utf-8').read()
    css = re.search(r'<style>(.*?)</style>', html, re.S).group(1)
    # article 内容起止
    m = re.search(r'(<article.*?</article>)', html, re.S)
    return css, html, m


def build_page(css, base_html, article_inner, title_suffix):
    doc = re.sub(r'<title>.*?</title>',
                 f'<title>WSJ 深读 · E1-025 原型 {title_suffix}</title>', base_html, count=1)
    # 注入新增 CSS
    doc = doc.replace('</style>', TEXT_CSS + LAYOUT_CSS + '\n</style>', 1)
    # 替换 article
    doc = re.sub(r'<article.*?</article>', article_inner, doc, flags=re.S, count=1)
    # masthead 标注版本
    doc = doc.replace('Editorial Plan 测试', f'原型 {title_suffix}', 1)
    return doc


def render_body(sm, treatments, skip_caption_dup=True):
    """渲染正文流（含 T 操作、T11 小标题、T10 分组）。返回 HTML。"""
    ops_by_block = {}
    subheads = {}   # before_block_id -> op
    groups = {}     # frozenset -> True（组内首段标记）
    for op in treatments:
        if op.action == 'subhead':
            subheads[op.block_id] = op
        elif op.action == 'group':
            for bid in op.params['blocks']:
                groups[bid] = op.params['blocks']
        else:
            ops_by_block.setdefault(op.block_id, []).append(op)

    # T10 分组：记录每组起止
    group_ranges = {}
    seen_groups = set()
    for op in treatments:
        if op.action == 'group':
            key = tuple(op.params['blocks'])
            if key not in seen_groups:
                seen_groups.add(key)
                group_ranges[key[0]] = key

    h = []
    in_group = None
    for b in sm.blocks:
        if b['role'] == 'title':
            continue
        if b['role'] == 'caption_duplicate' and skip_caption_dup:
            continue
        bid = b['id']

        # T10 组开始
        if bid in group_ranges and in_group is None:
            h.append('<div class="tt-group ed-block">')
            in_group = group_ranges[bid]

        # T11 小标题
        if bid in subheads:
            op = subheads[bid]
            h.append(
                f'<h3 class="tt-subhead ed-block" data-editorial-added="true">'
                f'<span class="k-cn">{esc(op.params["title_cn"])}</span>'
                f'<span class="k-en" hidden>{esc(op.params.get("title_en",""))}</span>'
                f'</h3>')

        cn_h, en_h = render_block(b, ops_by_block.get(bid, []))
        h.append(
            f'<p data-block="{bid}"><span class="k-cn">{cn_h}</span>'
            f'<span class="k-en" hidden>{en_h}</span></p>')

        # T10 组结束
        if in_group and bid == in_group[-1]:
            h.append('</div>')
            in_group = None

    if in_group:
        h.append('</div>')
    return '\n'.join(h)


def render_aids(plan, e, assets):
    """渲染 Aid 组件（沿用 plan_render 分发；quote 已在 plan 中去重）。"""
    from plan_render import _render_component as rc
    h = []
    for cp in plan.get('component_plan', []):
        asset_b64 = None
        if cp.get('asset'):
            # asset 名映射到 gen-test assets 目录
            amap = {'img-1.png': 'img-1.png'}
            fn = amap.get(cp['asset'], cp['asset'])
            asset_b64 = assets.get(fn)
        try:
            h.append(rc(cp, e, e['id'], {}, asset_b64))
        except Exception as ex:
            h.append(f'<!-- aid render failed: {cp["component"]}: {ex} -->')
    return h


def main():
    os.makedirs(OUT, exist_ok=True)

    # baseline：原样复制
    shutil.copy(os.path.join(GEN, 'article.html'),
                os.path.join(OUT, 'baseline.html'))
    print('baseline.html ← 现有 article.html 原样复制')

    css, base_html, _ = extract_shell()
    plan = json.load(open(os.path.join(GEN, 'plan-enhanced.json'), encoding='utf-8'))
    sm, marked = build_source('E1-025', os.path.join(GEN, 'translation.json'), plan)
    treatments = []
    from text_treatment import TextOp
    for td in plan.get('text_treatments', []):
        treatments.append(TextOp(
            td['pattern_id'], td['block_id'], td['locale'], td['text_exact'],
            action=td['action'], params=td['params'],
            editorial_added=td['editorial_added'], reason=td['reason']))

    final = json.load(open(os.path.join(os.path.dirname(BASE), '2026-10-12',
                                        'final.json'), encoding='utf-8'))
    e = next(x for x in final if x['id'] == 'E1-025')
    assets = load_assets()

    body_html = render_body(sm, treatments)

    # text-only：只有正文流
    article_text = (
        f'<article class="story story-plan" id="s-E1-025" aria-label="E1-025">\n'
        f'<div class="sheet">\n{article_header(e)}\n{body_html}\n</div>\n</article>')
    open(os.path.join(OUT, 'text-only.html'), 'w', encoding='utf-8').write(
        build_page(css, base_html, article_text, 'text-only'))
    print('text-only.html ← 仅 Text Treatment（无 Aid 组件）')

    # full：正文流 + Aid 组件（按 plan slot 位置插入）
    # 简化：将 aids 按原 plan 的 slot 插入正文流
    aids = render_aids(plan, e, assets)
    # slot 映射：before_body / after_para:N / after_body
    slot_map = {}
    aid_idx = 0
    aid_htmls = []
    for cp in plan.get('component_plan', []):
        aid_htmls.append(aids[aid_idx] if aid_idx < len(aids) else '')
        aid_idx += 1
    # 重建带 slot 的流
    h = [f'<article class="story story-plan" id="s-E1-025" aria-label="E1-025">',
         '<div class="sheet">', article_header(e)]
    # before_body
    for cp, ah in zip(plan['component_plan'], aid_htmls):
        if cp['slot']['at'] == 'before_body':
            h.append(ah)
    # body + after_para
    after_para = {}
    for cp, ah in zip(plan['component_plan'], aid_htmls):
        if cp['slot']['at'] == 'after_para':
            after_para.setdefault(cp['slot']['para'], []).append(ah)
    # body_blocks 按 pN 顺序；slot para 是 1-based 索引（gen-test 约定）
    body_ids = [b['id'] for b in sm.body_blocks()]
    # render_body 已生成；这里按段重组以便插入
    # 为简化：用 render_body 的段落 HTML，按 data-block 切分
    seg = {}
    for part in re.findall(r'<p data-block="([^"]+)">.*?</p>', body_html, re.S):
        seg[part] = True
    # 逐段输出（复用 render_body 的顺序）
    parts = re.split(r'(?=<p data-block=|<h3 class="tt-subhead ed-block|<div class="tt-group ed-block">)', body_html)
    # 映射 data-block -> para 序号
    id2n = {b['id']: int(b['id'][1:]) for b in sm.body_blocks()}
    for part in parts:
        if not part.strip():
            continue
        h.append(part)
        m = re.search(r'data-block="(p\d+)"', part)
        if m:
            n = id2n.get(m.group(1))
            if n and n in after_para:
                h.extend(after_para[n])
    # after_body
    for cp, ah in zip(plan['component_plan'], aid_htmls):
        if cp['slot']['at'] == 'after_body':
            h.append(ah)
    h.append('</div>\n</article>')
    open(os.path.join(OUT, 'full.html'), 'w', encoding='utf-8').write(
        build_page(css, base_html, '\n'.join(h), 'full'))
    print('full.html ← Text + Layout + Aids（quote 已去重，p2 跳过）')
    print(f'输出目录：{OUT}')


if __name__ == '__main__':
    main()
