#!/usr/bin/env python3
"""WSJ 深读 · Plan 驱动渲染。
Editorial Plan 决定组件与位置；渲染器只执行，不做编辑判断。
无 Plan 时降级为干净文章页（header + 正文 + 结束符）。
"""
import base64
import json
import os

from components import (esc, pair, paras, article_header, key_figures, timeline,
                        quote, context_box, figure, chart, infographic, bargraph,
                        data_table, rail, COMPONENT_REGISTRY)

BASE = os.path.dirname(os.path.abspath(__file__))


def load_plan(plans_dir, article_id):
    p = os.path.join(plans_dir, f'{article_id}.json')
    if not os.path.exists(p):
        return None
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def _resolve_ref(data_ref, modules_all):
    # "modules.json#E1-005.key_figures"
    _, rest = data_ref.split('#', 1)
    aid, key = rest.split('.', 1)
    return modules_all[aid][key]


def _render_component(entry, e, uid, modules_all, asset_b64):
    """按 COMPONENT_REGISTRY 分发；返回 HTML。未知组件抛错（不静默吞掉）。"""
    name = entry['component']
    if name not in COMPONENT_REGISTRY:
        raise ValueError(f'unknown component: {name}')
    data = dict(entry.get('data') or {})
    if entry.get('data_ref'):
        ref = _resolve_ref(entry['data_ref'], modules_all)
        data['_ref'] = ref
    if name == 'key_figures':
        items = data.get('items') or data['_ref']
        return key_figures(items, uid)
    if name == 'timeline':
        tl = data.get('timeline') or data['_ref']
        return timeline(tl, uid)
    if name == 'quote':
        q = data.get('quote') or data['_ref']
        return quote(q)
    if name == 'context_box':
        return context_box(e.get('context_cn', ''), uid)
    if name == 'figure':
        return figure(asset_b64, data['caption_cn'], data.get('caption_en', ''),
                      data.get('credit', ''), uid)
    if name == 'chart':
        return chart(asset_b64, data['caption_cn'], data.get('caption_en', ''),
                     data.get('source_note', ''), uid)
    if name == 'infographic':
        return infographic(asset_b64, data['caption_cn'], data.get('caption_en', ''),
                           data.get('data_note', ''), uid)
    if name == 'bargraph':
        return bargraph(data['title_cn'], data.get('title_en', ''), data['bars'],
                        data.get('note_cn', ''), data.get('note_en', ''), uid)
    if name == 'data_table':
        return data_table(data.get('body_en', ''))
    raise ValueError(f'no dispatcher for {name}')


def body_pairs(e):
    """正文配对：取较长一侧，保证 EN-only 的 data 页不丢段落。"""
    cps = (e.get('body_cn') or '').split('\n\n')
    eps = (e.get('body_en') or '').split('\n\n')
    n = max(len(cps), len(eps))
    out = []
    for i in range(n):
        cn = cps[i] if i < len(cps) else ''
        en = eps[i] if i < len(eps) else ''
        if cn.strip() or en.strip():
            out.append((cn, en))
    return out


def _rail_items(plan, e, uid):
    items = []
    for cp in plan.get('component_plan', []):
        c = cp['component']
        if c == 'key_figures':
            items.append((f'keyfig-{uid}', '关键数字', 'KEY FIGURES'))
        elif c == 'timeline':
            items.append((f'timeline-{uid}', '时间线', 'TIMELINE'))
        elif c == 'context_box':
            items.append((f'context-{uid}', '背景资料', 'BACKGROUND'))
    # 去重保序
    seen, out = set(), []
    for it in items:
        if it[0] not in seen:
            seen.add(it[0])
            out.append(it)
    return out


def render_article_with_plan(e, plan, modules_all, asset_loader):
    """Plan 驱动：组件与位置完全来自 plan['component_plan']。"""
    uid = e['id']
    h = [f'<article class="story story-plan" id="s-{uid}" '
         f'aria-label="{esc(e.get("title_cn") or e.get("title") or uid)}">']
    h.append('<div class="sheet">')
    h.append(article_header(e))

    cps = plan.get('component_plan', [])
    # 按 slot 分组（同 slot 按数组顺序）
    before = [c for c in cps if c['slot']['at'] == 'before_body']
    after_body = [c for c in cps if c['slot']['at'] == 'after_body']
    after_para = {}
    for c in cps:
        if c['slot']['at'] == 'after_para':
            after_para.setdefault(c['slot']['para'], []).append(c)

    h.append(rail(uid, _rail_items(plan, e, uid)))

    # 预加载本页用到的视觉资产
    asset_cache = {}
    for c in cps:
        if c.get('asset') and c['asset'] not in asset_cache:
            asset_cache[c['asset']] = asset_loader(c['asset'])

    for c in before:
        h.append(_render_component(c, e, uid, modules_all,
                                  asset_cache.get(c.get('asset'))))

    ps = body_pairs(e)
    for i, (cn, en) in enumerate(ps):
        h.append(pair(cn, en))
        for c in after_para.get(i, []):
            h.append(_render_component(c, e, uid, modules_all,
                                      asset_cache.get(c.get('asset'))))

    for c in after_body:
        h.append(_render_component(c, e, uid, modules_all,
                                  asset_cache.get(c.get('asset'))))

    h.append('<div class="story-end"><span class="endmark" aria-hidden="true">■</span></div>')
    h.append('</div>')
    h.append('</article>')
    return '\n'.join(h)


def render_clean(e):
    """降级：无 Plan 时的干净文章页。证明 Plan 在驱动渲染。"""
    uid = e['id']
    h = [f'<article class="story story-clean" id="s-{uid}" '
         f'aria-label="{esc(e.get("title_cn") or e.get("title") or uid)}">']
    h.append('<div class="sheet">')
    h.append(article_header(e))
    for cn, en in body_pairs(e):
        h.append(pair(cn, en))
    h.append('<div class="story-end"><span class="endmark" aria-hidden="true">■</span></div>')
    h.append('</div>')
    h.append('</article>')
    return '\n'.join(h)
