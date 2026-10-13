#!/usr/bin/env python3
"""Planner → Renderer schema 适配器。

autonomous_planner 输出的六段式 → plan_render/orchestrate 期望的 component_plan 格式。
解决 E1-023 盲测发现的 timeline 空渲染 bug。
"""
import re


def adapt_plan(auto_plan, article):
    """输入 autonomous planner 的六段式 dict，输出 renderer 可用的 plan dict。"""
    out = {
        'component_plan': [],
        'treatments': auto_plan.get('text_treatment_plan', []),
        'layouts': auto_plan.get('layout_plan', []),
    }

    for aid in auto_plan.get('reading_aid_plan', []):
        atype = aid.get('type') or aid.get('component')
        if atype == 'timeline':
            out['component_plan'].append({
                'component': 'timeline',
                'data': {'timeline': _adapt_timeline(aid)},
                'slot': aid.get('slot', {'at': 'after_body'}),
            })
        elif atype == 'quote':
            out['component_plan'].append({
                'component': 'quote',
                'data': {'quote': _adapt_quote(aid)},
                'slot': aid.get('slot', {'at': 'after_para', 'para': 3}),
            })
        elif atype == 'key_figures':
            out['component_plan'].append({
                'component': 'key_figures',
                'data': {'key_figures': _adapt_key_figures(aid)},
                'slot': aid.get('slot', {'at': 'after_para', 'para': 1}),
            })
        elif atype == 'data_table':
            out['component_plan'].append({
                'component': 'data_table',
                'data': aid.get('data', {}),
                'slot': aid.get('slot', {'at': 'after_body'}),
            })
    _validate_output(out)
    return out


def _validate_output(out):
    """结构验证：任何会导致空白渲染的问题直接抛异常，不许静默通过。"""
    for cp in out.get('component_plan', []):
        comp = cp.get('component')
        data = cp.get('data', {})
        if comp == 'timeline':
            tl = data.get('timeline', {})
            entries = tl.get('entries', [])
            if not entries:
                raise ValueError('timeline 无 entries，会空白渲染')
            for e in entries:
                if not e.get('text_cn'):
                    raise ValueError(f'timeline entry 缺 text_cn: {e}')
                # 双语同源检查：有英文则中英长度比应在合理范围
                if e.get('text_en'):
                    cn_len = len(e['text_cn'])
                    en_len = len(e['text_en'].split())
                    if cn_len > 10 and (en_len / cn_len < 0.2 or en_len / cn_len > 4):
                        raise ValueError(
                            f'timeline 中英疑似不同源: CN{cn_len}字 EN{en_len}词')
        elif comp == 'quote':
            q = data.get('quote', {})
            if not q.get('text_cn') or not q.get('text_en'):
                raise ValueError('quote 缺中英文本，会空白渲染')
        elif comp == 'key_figures':
            items = data.get('key_figures', {}).get('items', [])
            if not items:
                raise ValueError('key_figures 无 items，会空白渲染')
            for it in items:
                if not it.get('value_cn'):
                    raise ValueError(f'key_figures 缺 value_cn: {it}')


def _adapt_timeline(aid):
    entries = []
    for ev in aid.get('events', []) or aid.get('entries', []):
        date = ev.get('date') or ev.get('t_cn') or ''
        text = ev.get('event') or ev.get('text_cn') or ''
        # 日期不许加年份（铁律）；英文日期尽量从原文找，找不到留空
        entries.append({
            't_cn': date, 't_en': ev.get('t_en') or '',
            'text_cn': text, 'text_en': ev.get('text_en') or '',
        })
    return {
        'title_cn': aid.get('title_cn') or '时间线',
        'title_en': aid.get('title_en') or 'Timeline',
        'entries': entries,
    }


def _adapt_quote(aid):
    # 兼容两种格式：{quote: {text_cn...}} 或 {quote_cn/quote_en/speaker_cn...}
    q = aid.get('quote') or aid.get('data', {}).get('quote', {}) or aid
    return {
        'text_cn': q.get('text_cn') or aid.get('quote_cn') or '',
        'text_en': q.get('text_en') or aid.get('quote_en') or '',
        'attr_cn': q.get('attr_cn') or aid.get('speaker_cn') or '',
        'attr_en': q.get('attr_en') or aid.get('speaker_en') or '',
    }


def _adapt_key_figures(aid):
    items = []
    for it in aid.get('items', []):
        items.append({
            'value_cn': it.get('value_cn') or it.get('value') or '',
            'value_en': it.get('value_en') or '',
            'label_cn': it.get('label_cn') or it.get('label') or '',
            'label_en': it.get('label_en') or '',
            'note_cn': it.get('note_cn') or '',
            'note_en': it.get('note_en') or '',
        })
    return {'items': items}
