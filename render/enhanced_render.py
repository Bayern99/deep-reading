#!/usr/bin/env python3
"""Plan-aware article render for the production issue path.

Reuses text_treatment + layout + components. No separate prototype shell.
"""
import json
import os
import re

from components import (
    esc, article_header, key_figures, timeline, quote, context_box,
    figure, chart, infographic, bargraph, data_table, rail, kicker_pair,
)
from layout import (
    render_margin_note, render_compare, render_figure_text,
    render_wide_figure,
)
from source_model import SourceModel
from text_treatment import TextOp, render_block

BASE = os.path.dirname(os.path.abspath(__file__))


def load_plans(plans_dir):
    """Load production-ready enhanced plans only.

    Old Phase-4 plans (E1-005/E1-033/E3-014) use modules.json data_ref and lack
    schema_version=enhanced-v1 — keep them as archive, not silent inputs.
    """
    out = {}
    if not os.path.isdir(plans_dir):
        return out
    for fn in os.listdir(plans_dir):
        if not fn.endswith('.json') or fn.startswith('_'):
            continue
        with open(os.path.join(plans_dir, fn), encoding='utf-8') as f:
            plan = json.load(f)
        if plan.get('schema_version') != 'enhanced-v1':
            continue
        aid = plan.get('article_id') or fn[:-5]
        out[aid] = plan
    return out


_OVERRIDES = None


def _alignment_overrides():
    """Per-article CN<->EN pairing repairs for extraction debt (markers,
    column-break fragments). Content text stays verbatim; only pairing
    and obvious non-content markers are affected."""
    global _OVERRIDES
    if _OVERRIDES is None:
        path = os.path.join(BASE, 'alignment_overrides.json')
        _OVERRIDES = {}
        if os.path.isfile(path):
            with open(path, encoding='utf-8') as f:
                _OVERRIDES = json.load(f)
    return _OVERRIDES


def _apply_en_repairs(aid, en):
    ov = _alignment_overrides().get(aid)
    if not ov:
        return en
    en = list(en)
    for exact in ov.get('drop_en', []):
        matches = [i for i, p in enumerate(en) if p.strip() == exact]
        assert len(matches) == 1, f'{aid}: drop_en not found once: {exact!r}'
        en.pop(matches[0])
    for spec in ov.get('join_en', []):
        fi = next((i for i, p in enumerate(en)
                   if p.startswith(spec['first_prefix'])), None)
        si = next((i for i, p in enumerate(en)
                   if p.startswith(spec['second_prefix'])), None)
        assert fi is not None and si is not None and fi != si, \
            f'{aid}: join_en prefix not found: {spec}'
        en[fi] = en[fi] + spec.get('joiner', ' ') + en[si]
        en.pop(si)
    return en


def source_from_final(e):
    sm = SourceModel(e['id'])
    cn = [p.strip() for p in (e.get('body_cn') or '').split('\n\n') if p.strip()]
    en = [p.strip() for p in (e.get('body_en') or '').split('\n\n') if p.strip()]
    en = _apply_en_repairs(e['id'], en)
    if len(cn) != len(en):
        print(f'warn: {e["id"]} cn/en para mismatch '
              f'({len(cn)} vs {len(en)}), index pairing may desync')
    n = max(len(cn), len(en))
    for i in range(n):
        c = cn[i] if i < len(cn) else ''
        g = en[i] if i < len(en) else ''
        role = 'body'
        # Source section heads: short, no sentence end — typography, not invented copy.
        if c and len(c) <= 12 and not re.search(r'[。！？.!?]', c):
            role = 'source_head'
        sm.add_block(f'p{i+1}', g, c, role=role)
    return sm


def _ops_from_plan(plan):
    ops = []
    for td in plan.get('text_treatments') or []:
        ops.append(TextOp(
            td['pattern_id'], td['block_id'], td.get('locale', 'cn'),
            td.get('text_exact', ''),
            action=td.get('action', 'wrap'),
            params=td.get('params') or {},
            editorial_added=bool(td.get('editorial_added')),
            reason=td.get('reason', ''),
        ))
    return ops


def _layout_slots(plan, uid):
    """Build layout insertion maps from plan.layout_decisions."""
    anchor_wraps = {}
    after_blocks = {}
    before_body = []
    after_body = []
    for ld in plan.get('layout_decisions') or []:
        if ld.get('action') == 'decline':
            continue
        pid = ld.get('pattern_id')
        params = ld.get('params') or {}
        if pid == 'L02':
            bid = params['anchor_block_id']
            note = render_margin_note(
                bid, params['note_cn'], params.get('note_en', ''),
                f'{uid}-{bid}', editorial_added=True)
            anchor_wraps[bid] = note
        elif pid == 'L03':
            pairs = [((a['cn'], a.get('en', '')), (b['cn'], b.get('en', '')))
                     for a, b in params['pairs']]
            html = render_compare(pairs, f'{uid}-cmp',
                                  dim_labels=params.get('dim_labels'))
            after = params.get('after_block_id')
            if after:
                after_blocks.setdefault(after, []).append(
                    f'<div class="ed-block">{html}</div>')
            else:
                before_body.append(f'<div class="ed-block">{html}</div>')
        elif pid == 'L05':
            # caller supplies image html in params['img_html']
            html = render_figure_text(
                params['img_html'], params['text_cn'], params.get('text_en', ''),
                f'{uid}-ft')
            after = params.get('after_block_id')
            if after:
                after_blocks.setdefault(after, []).append(
                    f'<div class="ed-block">{html}</div>')
            else:
                before_body.append(f'<div class="ed-block">{html}</div>')
        elif pid == 'L08':
            html = render_wide_figure(params['inner_html'], f'{uid}-wide')
            after = params.get('after_block_id')
            if after:
                after_blocks.setdefault(after, []).append(html)
            else:
                before_body.append(html)
    return {
        'anchor_wraps': anchor_wraps,
        'after_blocks': after_blocks,
        'before_body': before_body,
        'after_body': after_body,
    }


def _render_aid(entry, e, uid, asset_b64):
    name = entry['component']
    data = dict(entry.get('data') or {})
    if name == 'key_figures':
        return f'<div class="ed-block">{key_figures(data["items"], uid)}</div>'
    if name == 'timeline':
        return f'<div class="ed-block">{timeline(data.get("timeline") or data, uid)}</div>'
    if name == 'quote':
        return f'<div class="ed-block">{quote(data.get("quote") or data)}</div>'
    if name == 'context_box':
        return f'<div class="ed-block">{context_box(e.get("context_cn", ""), uid)}</div>'
    if name == 'figure':
        return f'<div class="ed-block">{figure(asset_b64, data["caption_cn"], data.get("caption_en", ""), data.get("credit", ""), uid)}</div>'
    if name == 'chart':
        return chart(asset_b64, data['caption_cn'], data.get('caption_en', ''),
                     data.get('source_note', ''), uid)
    if name == 'infographic':
        return infographic(asset_b64, data['caption_cn'], data.get('caption_en', ''),
                           data.get('data_note', ''), uid)
    if name == 'bargraph':
        return f'<div class="ed-block">{bargraph(data["title_cn"], data.get("title_en", ""), data["bars"], data.get("note_cn", ""), data.get("note_en", ""), uid)}</div>'
    if name == 'data_table':
        return f'<div class="ed-block">{data_table(data.get("body_en", ""))}</div>'
    raise ValueError(f'unknown component: {name}')


def _aid_maps(plan, e, uid, asset_loader):
    before, after_body, after_para = [], [], {}
    for cp in plan.get('component_plan') or []:
        asset_b64 = asset_loader(cp['asset']) if cp.get('asset') else None
        html = _render_aid(cp, e, uid, asset_b64)
        slot = cp.get('slot') or {'at': 'after_body'}
        if slot['at'] == 'before_body':
            before.append(html)
        elif slot['at'] == 'after_body':
            after_body.append(html)
        elif slot['at'] == 'after_para':
            # plan paras are 1-based body indices matching pN
            after_para.setdefault(int(slot['para']), []).append(html)
    return before, after_body, after_para


def _rail_from_plan(plan, e, uid):
    items = []
    for cp in plan.get('component_plan') or []:
        c = cp['component']
        if c == 'key_figures':
            items.append((f'keyfig-{uid}', '关键数字', 'KEY FIGURES'))
        elif c == 'timeline':
            items.append((f'timeline-{uid}', '时间线', 'TIMELINE'))
        elif c == 'context_box':
            items.append((f'context-{uid}', '背景资料', 'BACKGROUND'))
    if (e.get('context_cn') or '').strip() and not any(i[0].startswith('context-') for i in items):
        if any(cp.get('component') == 'context_box' for cp in (plan.get('component_plan') or [])):
            pass
        else:
            # context still available at bottom via default fold if plan asks
            pass
    seen, out = set(), []
    for it in items:
        if it[0] not in seen:
            seen.add(it[0])
            out.append(it)
    return out


def render_enhanced_article(e, plan, asset_loader=None):
    """Full enhanced article HTML for production issue."""
    uid = e['id']
    asset_loader = asset_loader or (lambda _p: None)
    sm = source_from_final(e)
    treatments = _ops_from_plan(plan)
    layouts = _layout_slots(plan, uid)
    aid_before, aid_after_body, aid_after_para = _aid_maps(
        plan, e, uid, asset_loader)

    ops_by_block = {}
    subheads = {}
    group_ranges = {}
    seen_groups = set()
    for op in treatments:
        if op.action == 'subhead':
            subheads[op.block_id] = op
        elif op.action == 'group':
            key = tuple(op.params['blocks'])
            if key not in seen_groups:
                seen_groups.add(key)
                group_ranges[key[0]] = key
        else:
            ops_by_block.setdefault(op.block_id, []).append(op)

    applied_layouts = [ld for ld in (plan.get('layout_decisions') or [])
                       if ld.get('action') != 'decline']
    has_ops = bool(treatments or applied_layouts or (plan.get('component_plan') or []))

    h = [f'<article class="story story-enhanced" id="s-{uid}" '
         f'data-enhanced="{"true" if has_ops else "reviewed"}" '
         f'aria-label="{esc(e.get("title_cn") or e.get("title") or uid)}">']
    h.append('<div class="sheet">')
    if e.get('type') in ('brief', 'letter'):
        kick_cn, kick_en = kicker_pair(e)
        h.append(
            '<header class="ahead ahead-compact">'
            f'<div class="kicker"><span class="kbar"></span>'
            f'<span class="k-cn">{esc(kick_cn)}</span>'
            f'<span class="k-en" hidden>{esc(kick_en)}</span></div>'
            f'<h2 class="art-title art-compact"><span class="k-cn">{esc(e.get("title_cn"))}</span>'
            f'<span class="k-en" hidden>{esc(e.get("title"))}</span></h2>'
            '</header>')
    else:
        h.append(article_header(e))
    h.append(rail(uid, _rail_from_plan(plan, e, uid)))

    for x in layouts['before_body'] + aid_before:
        h.append(x)

    in_group = None
    for b in sm.blocks:
        bid = b['id']
        n = int(bid[1:])

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

        if b['role'] == 'source_head':
            en_head = b['en']
            if len(en_head) > 60 or re.search(r'[.!?。！？]', en_head):
                en_head = ''  # not a real parallel head — never show prose as a heading
            en_span = (f'<span class="k-en" hidden>{esc(en_head)}</span>'
                       if en_head else '')
            h.append(
                f'<h3 class="tt-subhead ed-block" data-source-head="true" data-block="{bid}">'
                f'<span class="k-cn">{esc(b["cn"])}</span>'
                f'{en_span}'
                f'</h3>')
        else:
            cn_h, en_h = render_block(b, ops_by_block.get(bid, []))
            p_html = (f'<p class="ed-block" data-block="{bid}">'
                      f'<span class="k-cn">{cn_h}</span>'
                      f'<span class="k-en" hidden>{en_h}</span></p>')
            if bid in layouts['anchor_wraps']:
                h.append(
                    f'<div class="ed-block ly-anchor">\n{p_html}\n'
                    f'{layouts["anchor_wraps"][bid]}\n</div>')
            else:
                h.append(p_html)

        for extra in layouts['after_blocks'].get(bid, []):
            h.append(extra)
        for extra in aid_after_para.get(n, []):
            h.append(extra)

        if in_group and bid == in_group[-1]:
            h.append('</div>')
            in_group = None

    if in_group:
        h.append('</div>')

    for x in layouts['after_body'] + aid_after_body:
        h.append(x)

    # Default: fold context if present and not already planned
    if (e.get('context_cn') or '').strip():
        planned_ctx = any(
            cp.get('component') == 'context_box'
            for cp in (plan.get('component_plan') or []))
        if not planned_ctx:
            h.append(f'<div class="ed-block">{context_box(e.get("context_cn"), uid)}</div>')

    h.append('<div class="story-end ed-block">'
             '<span class="endmark" aria-hidden="true">■</span></div>')
    h.append('</div></article>')
    return '\n'.join(h)
