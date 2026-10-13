#!/usr/bin/env python3
"""WSJ 深读 · 文章渲染（按 type 分流）
铁律：正文逐字来自 final.json；模块只来自 modules.json / images.json / context_cn。
"""
from components import (esc, pair, paras, article_header, body_paras, key_figures,
                        timeline, quote, context_box, figure, data_table, rail)


def _quote_after_index(e, q):
    """引语模块放在包含直接引语的段落之后；找不到则放中部"""
    needle = (q.get('text_cn') or '').strip('“”"')[:12]
    cps = (e.get('body_cn') or '').split('\n\n')
    for i, p in enumerate(cps):
        if needle and needle in p:
            return i
    return max(0, len(cps) // 2)


def _compact_kicker(e):
    bits = []
    if e.get('section'):
        bits.append(e['section'])
    if e.get('page'):
        bits.append(e['page'] + ' 版')
    if e.get('type') == 'letter':
        bits.append('读者来信')
    return ' · '.join(b for b in bits if b)


def _compact_head(e, kicker_cn, kicker_en):
    h = ['<header class="ahead ahead-compact">']
    h.append(f'<div class="kicker"><span class="kbar"></span><span class="k-cn">{esc(kicker_cn)}</span>'
             f'<span class="k-en" hidden>{esc(kicker_en)}</span></div>')
    h.append(f'<h2 class="art-title art-compact"><span class="k-cn">{esc(e.get("title_cn"))}</span>'
             f'<span class="k-en" hidden>{esc(e.get("title"))}</span></h2>')
    if e.get('dek_cn') or e.get('dek'):
        h.append(f'<p class="deck deck-compact"><span class="k-cn">{esc(e.get("dek_cn"))}</span>'
                 f'<span class="k-en" hidden>{esc(e.get("dek"))}</span></p>')
    if e.get('byline'):
        h.append(f'<div class="byline"><span class="who">{esc(e.get("byline"))}</span></div>')
    h.append('</header>')
    return '\n'.join(h)


def render_article(e, modules, images, img_b64=None):
    """返回 article HTML。modules/images 为该文章的策展数据（可为 None）。"""
    uid = e['id']
    t = e.get('type')
    h = [f'<article class="story story-{t}" id="s-{uid}" aria-label="{esc(e.get("title_cn") or e.get("title") or uid)}">']
    h.append('<div class="sheet">')

    if t in ('article', 'opinion'):
        h.append(article_header(e))
        rail_items = []
        if modules and modules.get('key_figures'):
            rail_items.append((f'keyfig-{uid}', '关键数字', 'KEY FIGURES'))
        if modules and modules.get('timeline'):
            rail_items.append((f'timeline-{uid}', '时间线', 'TIMELINE'))
        if (e.get('context_cn') or '').strip():
            rail_items.append((f'context-{uid}', '背景资料', 'BACKGROUND'))
        h.append(rail(uid, rail_items))
        if images and img_b64:
            h.append(figure(img_b64, images['caption_cn'], images.get('caption_en', ''),
                            images.get('credit', ''), uid))
        ps = paras(e.get('body_cn'), e.get('body_en'))
        n = len(ps)
        kf_at = min(1, n - 1)
        tl_at = min(6, n - 1)
        q_at = _quote_after_index(e, modules['quote']) if modules and modules.get('quote') else None
        for i, (cn, en) in enumerate(ps):
            h.append(pair(cn, en))
            if modules and modules.get('key_figures') and i == kf_at:
                h.append(key_figures(modules['key_figures'], uid))
            if modules and modules.get('timeline') and i == tl_at:
                h.append(timeline(modules['timeline'], uid))
            if q_at is not None and i == q_at:
                h.append(quote(modules['quote']))
        h.append(context_box(e.get('context_cn'), uid))
        h.append('<div class="story-end"><span class="endmark" aria-hidden="true">■</span></div>')

    elif t in ('brief', 'letter'):
        h.append(_compact_head(e, _compact_kicker(e), _compact_kicker(e)))
        h.extend(body_paras(e))

    elif t == 'data_table':
        h.append(_compact_head(e, f'数据 · {e.get("page") or ""} 版', f'DATA · p.{e.get("page") or ""}'))
        h.append(f'<div class="tbl-cap"><span class="k-cn">{esc(e.get("title_cn"))}</span>'
                 f'<span class="k-en" hidden>{esc(e.get("title"))}</span></div>')
        h.append(data_table(e.get('body_en')))

    elif t == 'photo_caption':
        h.append(_compact_head(e, f'图片 · {e.get("page") or ""} 版', f'PHOTO · p.{e.get("page") or ""}'))
        if images and img_b64:
            h.append(figure(img_b64, e.get('title_cn'), e.get('title'), images.get('credit', ''), uid))
        else:
            h.append(pair(e.get('title_cn'), e.get('title'), 'p', 'cap-lede'))
        h.extend(body_paras(e))

    else:
        h.append(_compact_head(e, f'{e.get("section") or ""} · {e.get("page") or ""} 版',
                               f'{e.get("section") or ""} · p.{e.get("page") or ""}'))
        h.extend(body_paras(e))

    h.append('</div>')
    h.append('</article>')
    return '\n'.join(h)


def article_nav(prev_id, prev_title_cn, next_id, next_title_cn):
    """上一篇 / 目录 / 下一篇"""
    if prev_id:
        prev = (f'<a class="anav-prev" href="#s-{prev_id}"><span class="anav-dir"><span class="k-cn">← 上一篇</span>'
                f'<span class="k-en" hidden>← Prev</span></span>'
                f'<span class="anav-t"><span class="k-cn">{esc(prev_title_cn or "")}</span><span class="k-en" hidden></span></span></a>')
    else:
        prev = '<span class="anav-empty"></span>'
    if next_id:
        nxt = (f'<a class="anav-next" href="#s-{next_id}"><span class="anav-dir"><span class="k-cn">下一篇 →</span>'
               f'<span class="k-en" hidden>Next →</span></span>'
               f'<span class="anav-t"><span class="k-cn">{esc(next_title_cn or "")}</span><span class="k-en" hidden></span></span></a>')
    else:
        nxt = '<span class="anav-empty"></span>'
    toc = '<a class="anav-toc" href="#toc"><span class="k-cn">目录</span><span class="k-en" hidden>Contents</span></a>'
    return f'<nav class="anav" aria-label="article nav"><div class="anav-row">{prev}{toc}{nxt}</div></nav>'
