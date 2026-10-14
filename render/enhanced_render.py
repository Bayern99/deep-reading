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
from source_model import source_from_final, content_digest
from text_treatment import TextOp, render_block, validate_text_op
from article import render_article, _compact_head



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


def _validate_plan(plan, sm):
    if plan.get('article_id') not in (None, sm.article_id):
        raise ValueError(f'plan article mismatch: {plan.get("article_id")}')
    occupied_groups, subheads, margin_anchors = set(), set(), set()
    for op in _ops_from_plan(plan):
        if op.block_id not in sm.by_id:
            raise ValueError(f'missing text anchor: {op.block_id}')
        validate_text_op(sm.by_id[op.block_id], op)
        if op.action == 'group':
            blocks = op.params.get('blocks') or []
            if not blocks or blocks[0] != op.block_id or any(b not in sm.by_id for b in blocks):
                raise ValueError(f'missing group anchor: {blocks}')
            indices = [sm.blocks.index(sm.by_id[b]) for b in blocks]
            if indices != list(range(indices[0], indices[0] + len(indices))):
                raise ValueError(f'group must be contiguous and ordered: {blocks}')
            if occupied_groups.intersection(blocks):
                raise ValueError(f'overlapping groups: {blocks}')
            occupied_groups.update(blocks)
        elif op.action == 'subhead':
            if op.block_id in subheads:
                raise ValueError(f'duplicate subhead anchor: {op.block_id}')
            subheads.add(op.block_id)
    for ld in plan.get('layout_decisions') or []:
        action = ld.get('action', 'apply')
        if action == 'decline':
            continue
        pid = ld.get('pattern_id')
        if action != 'apply' or pid not in ('L02', 'L03', 'L05', 'L08'):
            raise ValueError(f'unsupported layout operation: {pid}/{action}')
        params = ld.get('params') or {}
        anchor = params.get('anchor_block_id') if pid == 'L02' else params.get('after_block_id')
        if (pid == 'L02' or anchor is not None) and anchor not in sm.by_id:
            raise ValueError(f'missing layout anchor: {anchor}')
        for block in ld.get('blocks') or []:
            if block not in sm.by_id:
                raise ValueError(f'missing layout block: {block}')
        if pid == 'L02':
            if anchor in margin_anchors:
                raise ValueError(f'duplicate margin-note anchor: {anchor}')
            margin_anchors.add(anchor)
    supported_components = {'key_figures', 'timeline', 'quote', 'context_box',
                            'figure', 'chart', 'infographic', 'bargraph', 'data_table'}
    for cp in plan.get('component_plan') or []:
        if cp.get('component') not in supported_components:
            raise ValueError(f'unknown component: {cp.get("component")}')
        if cp.get('action', 'apply') != 'apply':
            raise ValueError(f'unsupported component action: {cp.get("action")}')
        slot = cp.get('slot') or {'at': 'after_body'}
        if slot.get('at') not in ('before_body', 'after_body', 'after_para'):
            raise ValueError(f'unknown component slot: {slot}')
        if slot['at'] == 'after_para':
            n = slot.get('para')
            if type(n) is not int or f'p{n}' not in sm.by_id:
                raise ValueError(f'missing component slot: {slot}')


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
                                  dim_labels=params.get('dim_labels'),
                                  dim_labels_en=params.get('dim_labels_en'))
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
        else:
            raise ValueError(f'unsupported layout: {pid}')
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
        if cp['component'] in ('figure', 'chart', 'infographic') and not asset_b64:
            raise ValueError(f'missing component asset: {cp.get("asset")}')
        if cp['component'] == 'context_box' and not (e.get('context_cn') or '').strip():
            raise ValueError('empty context component')
        html = _render_aid(cp, e, uid, asset_b64)
        slot = cp.get('slot') or {'at': 'after_body'}
        if slot['at'] == 'before_body':
            before.append(html)
        elif slot['at'] == 'after_body':
            after_body.append(html)
        elif slot['at'] == 'after_para':
            # plan paras are 1-based body indices matching pN
            after_para.setdefault(int(slot['para']), []).append(html)
        else:
            raise ValueError(f'unknown component slot: {slot}')
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


def _reading_roles(plan, sm):
    """Resolve explicit per-language rhythm without changing copy or order."""
    treatment = plan.get('reading_treatment')
    if treatment is None:
        return '', {}
    if not isinstance(treatment, dict) or treatment.get('profile') not in ('narrative', 'analysis', 'evidence'):
        raise ValueError('unsupported reading treatment')
    if not treatment.get('reason') or not treatment.get('evidence'):
        raise ValueError('reading treatment requires reason and source evidence')
    roles = treatment.get('roles') or {}
    if set(roles) - {'cn', 'en'}:
        raise ValueError('unsupported reading treatment locale')
    attrs = {}
    for locale, assignments in roles.items():
        if not isinstance(assignments, dict) or set(assignments) - {'lead', 'break', 'closing'}:
            raise ValueError('unsupported reading role')
        seen = set()
        for role, block_ids in assignments.items():
            if not isinstance(block_ids, list):
                raise ValueError('reading role targets must be a list')
            for bid in block_ids:
                if bid not in sm.by_id or not sm.by_id[bid][locale] or bid in seen:
                    raise ValueError(f'missing or conflicting reading target: {locale}/{bid}')
                seen.add(bid)
                attrs[bid] = attrs.get(bid, '') + f' data-reading-{locale}="{role}"'
    return treatment['profile'], attrs


def _render_enhanced_article(e, plan, asset_loader=None, modules=None, images=None,
                             img_b64=None, curated=None):
    """Execute only validated production operations over the shared source."""
    uid = e['id']
    sm = source_from_final(e)
    _validate_plan(plan, sm)
    reading_profile, reading_attrs = _reading_roles(plan, sm)
    treatments = _ops_from_plan(plan)
    applied_layouts = [ld for ld in (plan.get('layout_decisions') or [])
                       if ld.get('action') != 'decline']
    has_ops = bool(treatments or applied_layouts or (plan.get('component_plan') or [])
                   or plan.get('headline_phrases_cn') or reading_profile)
    if not has_ops:
        return render_article(e, modules, images, img_b64=img_b64, curated=curated)
    if e.get('type') not in ('article', 'opinion', 'brief', 'letter'):
        raise ValueError(f'unsupported enhanced article type: {e.get("type")}')
    if plan.get('headline_phrases_cn') and e.get('type') in ('brief', 'letter'):
        raise ValueError('headline phrases require a full article header')
    if asset_loader is None:
        def asset_loader(path):
            raise ValueError(f'asset loader required: {path}')
    layouts = _layout_slots(plan, uid)
    aid_before, aid_after_body, aid_after_para = _aid_maps(plan, e, uid, asset_loader)

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


    reading_attr = f' data-reading-profile="{reading_profile}"' if reading_profile else ''
    h = [f'<article class="story story-enhanced" id="s-{uid}"{reading_attr} '
         f'data-enhanced="{"true" if has_ops else "reviewed"}" '
         f'aria-label="{esc(e.get("title_cn") or e.get("title") or uid)}">']
    h.append('<div class="sheet">')
    if e.get('type') in ('brief', 'letter'):
        h.append(_compact_head(e, *kicker_pair(e)))
    else:
        h.append(article_header(e, plan.get('headline_phrases_cn') or ()))
    h.append(rail(uid, _rail_from_plan(plan, e, uid)))
    if images and img_b64 and not any(
            cp.get('asset') and os.path.basename(cp['asset']) == os.path.basename(images.get('file', ''))
            for cp in plan.get('component_plan') or []):
        h.append(figure(img_b64, images['caption_cn'], images.get('caption_en', ''),
                        images.get('credit', ''), uid))

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

        cn_h, en_h = render_block(b, ops_by_block.get(bid, []))
        is_heading = (b['role'] == 'source_head' and len(b['en']) <= 60
                      and not re.search(r'[.!?。！？]', b['en']))
        tag = 'h3' if is_heading else 'p'
        cls = 'tt-subhead ed-block' if is_heading else 'ed-block'
        source_attr = ' data-source-head="true"' if is_heading else ''
        p_html = (f'<{tag} class="{cls}" data-block="{bid}"{source_attr}{reading_attrs.get(bid, "")}>'
                  f'<span class="k-cn">{cn_h}</span>'
                  f'<span class="k-en" hidden>{en_h}</span></{tag}>')
        if bid in layouts['anchor_wraps']:
            h.append(f'<div class="ed-block ly-anchor">\n{p_html}\n'
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


_PLAN_KEYS = {'schema_version', 'version', 'article_id', 'created', 'created_by',
              'content_digest', 'analysis', 'narrative_outline', 'rejected_opportunities',
              'text_treatments', 'layout_decisions', 'component_plan',
              'headline_phrases_cn', 'reading_treatment'}
_OP_KEYS = {'pattern_id', 'action', 'block_id', 'slot', 'reason', 'editorial_added',
            'locale', 'text_exact', 'params'}
_COMPONENT_KEYS = {'component', 'asset', 'data', 'slot', 'reason'}
_PARAM_KEYS = {'anchor_block_id', 'after_block_id', 'blocks', 'pairs', 'dim_labels',
               'dim_labels_en', 'title_cn', 'title_en', 'note_cn', 'note_en',
               'img_html', 'inner_html', 'text_cn', 'text_en', 'cut'}


def _strict_plan_keys(plan):
    bad = set(plan) - _PLAN_KEYS
    if bad:
        raise ValueError(f'unknown plan keys: {sorted(bad)}')
    for field in ('text_treatments', 'layout_decisions'):
        for index, entry in enumerate(plan.get(field) or []):
            if isinstance(entry, dict):
                bad = set(entry) - _OP_KEYS
                if bad:
                    raise ValueError(f'unknown {field}[{index}] keys: {sorted(bad)}')
                bad = set(entry.get('params') or {}) - _PARAM_KEYS
                if bad:
                    raise ValueError(f'unknown {field}[{index}] params keys: {sorted(bad)}')
    for index, entry in enumerate(plan.get('component_plan') or []):
        if isinstance(entry, dict):
            bad = set(entry) - _COMPONENT_KEYS
            if bad:
                raise ValueError(f'unknown component_plan[{index}] keys: {sorted(bad)}')


def render_enhanced_article(e, plan, asset_loader=None, modules=None, images=None,
                            img_b64=None, curated=None, execution_receipts=None):
    """Return HTML; optionally append one execution receipt, including failures."""
    operations = []
    receipt = {'article_id': e['id'], 'status': 'preserved', 'operations': operations}
    try:
        if not isinstance(plan, dict):
            raise ValueError('unsupported plan type: expected an object')
        _strict_plan_keys(plan)
        if plan.get('content_digest') is not None:
            if plan['content_digest'] != content_digest(e):
                raise ValueError(f'stale plan content digest: {e["id"]}')
        for field, kind, name in (('text_treatments', 'text', 'pattern_id'),
                                  ('layout_decisions', 'layout', 'pattern_id'),
                                  ('component_plan', 'component', 'component')):
            for index, entry in enumerate(plan.get(field) or []):
                if not isinstance(entry, dict):
                    raise ValueError(f'unsupported {kind} operation type: expected an object')
                params = entry.get('params') or {}
                target = entry.get('block_id') or params.get('anchor_block_id') or params.get('after_block_id') or entry.get('slot')
                operations.append({'operation_id': f'{kind}:{index}', 'kind': kind,
                                   'operation': entry.get(name), 'target': target,
                                   'status': 'declined' if entry.get('action') == 'decline' else 'requested'})
        if plan.get('headline_phrases_cn'):
            operations.append({'kind': 'headline', 'operation': 'headline_phrases_cn', 'status': 'requested'})
        if plan.get('reading_treatment') is not None:
            operations.append({'operation_id': 'reading:0', 'kind': 'composition',
                               'operation': 'reading_treatment',
                               'target': plan['reading_treatment'].get('roles') if isinstance(plan['reading_treatment'], dict) else None,
                               'status': 'requested'})
        html = _render_enhanced_article(e, plan, asset_loader, modules, images, img_b64, curated)
    except Exception as error:
        receipt.update(status='failed', error=f'{type(error).__name__}: {error}')
        if execution_receipts is not None:
            execution_receipts.append(receipt)
        raise
    for operation in operations:
        if operation['status'] == 'requested':
            operation['status'] = 'applied'
            receipt['status'] = 'applied'
    if execution_receipts is not None:
        execution_receipts.append(receipt)
    return html
