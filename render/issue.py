#!/usr/bin/env python3
"""WSJ 深读 · 整期组装（头版选稿 / 目录 / 阅读顺序 / 导航）
读者表面不含流水线标签。每期选稿来自 <issue>/front.json。
"""
import json
import os
from components import esc, set_issue_meta
from article import render_article, article_nav
from enhanced_render import render_enhanced_article

GROUP_DEFS = [
    ('p1', 'P1 必读', 'P1 MUST READ'),
    ('p2', 'P2', 'P2'),
    ('p3', 'P3', 'P3'),
    ('data', '数据附录', 'DATA APPENDIX'),
]

SECTION_DEFS = [
    ('front', '要闻', 'FRONT PAGE',
     ('News',), ('A1',), False),
    ('us', '美国', 'U.S.',
     ('U.S. News',), (), False),
    ('world', '世界', 'WORLD',
     ('World News',), (), False),
    ('life', '生活', 'LIFE',
     ('Personal Journal', 'Arts in Review', 'Sports'), (), False),
    ('opinion', '观点', 'OPINION',
     ('Opinion',), (), False),
    ('business', '商业与金融', 'BUSINESS & FINANCE',
     ('Business & Finance', 'Technology', 'Business News', 'Heard on the Street', 'Money & Investing'), (), False),
    ('data', '数据', 'DATA',
     ('Data',), (), True),
]


def group_of(e):
    if e.get('type') == 'data_table':
        return 'data'
    return {'P1': 'p1', 'P2': 'p2', 'P3': 'p3'}.get(e.get('priority'), 'p3')


def section_of(e):
    if e.get('type') == 'data_table':
        return 'data'
    page = e.get('page') or ''
    sec = e.get('section') or ''
    if page == 'A1':
        return 'front'
    for sid, _cn, _en, secs, pages, _open in SECTION_DEFS:
        if sid == 'front':
            continue
        if pages and page in pages:
            return sid
        if sec in secs:
            return sid
    return 'life'

def load_front(issue_dir):
    p = os.path.join(issue_dir or '', 'front.json')
    if issue_dir and os.path.isfile(p):
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    return {}


def _story_weight(e, lead_id=None):
    t = e.get('type')
    if t in ('photo_caption', 'index_digest', 'data_table', 'correction'):
        return 9
    if lead_id and e.get('id') == lead_id:
        return -1
    pri = {'P1': 0, 'P2': 1, 'P3': 2}.get(e.get('priority'), 3)
    return pri


def reading_order(articles, front=None):
    """digest + A1 长文（front.lead_id 先）+ 其余按版块。"""
    front = front or {}
    lead_id = front.get('lead_id')
    used = set()
    order = []

    digest = next((e for e in articles if e.get('type') == 'index_digest'), None)
    if digest:
        order.append(digest)
        used.add(digest['id'])

    a1 = [e for e in articles
          if e.get('page') == 'A1' and e['id'] not in used
          and e.get('type') not in ('data_table', 'photo_caption', 'index_digest')]
    a1.sort(key=lambda e: _story_weight(e, lead_id))
    order.extend(a1)
    used.update(e['id'] for e in a1)

    for sid, *_rest in SECTION_DEFS:
        rest = [e for e in articles if e['id'] not in used and section_of(e) == sid]
        rest.sort(key=lambda e: _story_weight(e, lead_id))
        order.extend(rest)
        used.update(e['id'] for e in rest)
    leftover = [e for e in articles if e['id'] not in used]
    order.extend(leftover)
    return order



def render_front(order, front=None):
    """头版：1 主导 + 2 次条。优先 front.json；否则 A1 新闻。"""
    front = front or {}
    by_id = {e['id']: e for e in order}
    news = [e for e in order
            if e.get('page') == 'A1'
            and e.get('type') == 'article'
            and e.get('section') == 'News']
    hero = by_id.get(front.get('lead_id')) if front.get('lead_id') else None
    if hero is None:
        hero = news[0] if news else None
    if hero is None:
        return ''
    rest = []
    for aid in front.get('also_ids') or []:
        e = by_id.get(aid)
        if e and e['id'] != hero['id']:
            rest.append(e)
    if not rest:
        rest = [e for e in news if e['id'] != hero['id']][:2]
    else:
        rest = rest[:2]
    h = ['<section class="front-pack" aria-label="今日要闻">']
    h.append('<a class="front-hero" href="#s-%s">' % hero['id'])
    h.append('<div class="kicker"><span class="kbar"></span>'
             '<span class="k-cn">要闻</span><span class="k-en" hidden>FRONT</span></div>')
    h.append(f'<h2 class="front-title"><span class="k-cn">{esc(hero.get("title_cn"))}</span>'
             f'<span class="k-en" hidden>{esc(hero.get("title"))}</span></h2>')
    if hero.get('dek_cn') or hero.get('dek'):
        h.append(f'<p class="front-dek"><span class="k-cn">{esc(hero.get("dek_cn") or "")}</span>'
                 f'<span class="k-en" hidden>{esc(hero.get("dek") or "")}</span></p>')
    h.append('</a>')
    if rest:
        h.append('<ol class="front-also">')
        for e in rest:
            dek_cn = e.get('dek_cn') or ''
            dek_en = e.get('dek') or ''
            h.append(f'<li><a href="#s-{e["id"]}">'
                     f'<span class="toc-t"><span class="k-cn">{esc(e.get("title_cn"))}</span>'
                     f'<span class="k-en" hidden>{esc(e.get("title") or "")}</span></span>')
            if dek_cn:
                h.append(f'<span class="front-also-dek"><span class="k-cn">{esc(dek_cn)}</span>'
                         f'<span class="k-en" hidden>{esc(dek_en)}</span></span>')
            h.append('</a></li>')
        h.append('</ol>')
    h.append('</section>')
    return '\n'.join(h)


def render_toc(order):
    h2 = ['<nav id="toc" class="toc" aria-label="toc">']
    buckets = {sid: [] for sid, *_ in SECTION_DEFS}
    for e in order:
        if e.get('type') in ('index_digest', 'photo_caption', 'correction'):
            continue
        buckets[section_of(e)].append(e)
    h2.append('<ol class="toc-jump">')
    digest = next((e for e in order if e.get('type') == 'index_digest'), None)
    if digest:
        h2.append(
            f'<li><a href="#s-{digest["id"]}">'
            f'<span class="k-cn">最新消息</span><span class="k-en" hidden>WHAT\'S NEWS</span></a></li>')
    for sid, cn, en, *_rest in SECTION_DEFS:
        items = buckets[sid]
        if not items:
            continue
        h2.append(
            f'<li><a href="#sec-{sid}">'
            f'<span class="k-cn">{cn}</span><span class="k-en" hidden>{en}</span></a></li>')
    h2.append('</ol></nav>')
    return '\n'.join(h2)


def _section_break(sid, cn, en):
    return (
        f'<header class="sec-break" id="sec-{sid}">'
        f'<span class="k-cn">{esc(cn)}</span>'
        f'<span class="k-en" hidden>{esc(en)}</span></header>'
    )


def render_issue(articles, modules_all, images_all, img_cache, issue_date,
                 gate_status=None, plans_all=None, asset_loader=None,
                 curation=None, issue_dir=None, execution_receipts=None):
    """gate_status: {aid: ('pass'|'warn'|'block', issues)}。warn/block 不进正文，只进待审核区。
    plans_all: editorial-plans by article id → enhanced production path.
    curation: render/curation.json — exclude 与 data_treatment。
    issue_dir: 用于读取该期 front.json。
    """
    plans_all = plans_all or {}
    curation = curation or {}
    exclude = set(curation.get('exclude', {}))
    treatments = curation.get('data_treatment', {})
    if gate_status:
        pub_articles = [e for e in articles
                        if gate_status.get(e['id'], ('pass', []))[0] == 'pass'
                        and e['id'] not in exclude]
        review_articles = [e for e in articles
                           if gate_status.get(e['id'], ('pass', []))[0] in ('warn', 'block')]
    else:
        pub_articles, review_articles = articles, []
    if issue_dir is None and issue_date:
        issue_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), issue_date)
        if not os.path.isdir(issue_dir):
            issue_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', issue_date)
    front = load_front(issue_dir)
    order = reading_order(pub_articles, front)
    date_cn = front.get('date_cn') or issue_date or ''
    date_en = front.get('date_en') or issue_date or ''
    wd_cn = front.get('weekday_cn') or ''
    wd_en = front.get('weekday_en') or ''
    meta_cn = (date_cn + (' ' + wd_cn if wd_cn else '')).strip()
    meta_en = ((wd_en + ', ' if wd_en else '') + date_en).strip(', ')
    dek_cn = front.get('dek_cn') or ''
    dek_en = front.get('dek_en') or ''
    set_issue_meta(date_cn, date_en)
    parts = []

    parts.append(f'''
<header class="masthead">
  <a class="skip" href="#toc">跳到目录</a>
  <div class="mast-in">
    <div class="brand"><span class="sq"></span><span class="wm k-cn">WSJ 深读</span><span class="wm k-en" hidden>WSJ Deep Read</span></div>
    <div class="mast-meta"><span class="k-cn">{esc(meta_cn)}</span><span class="k-en" hidden>{esc(meta_en)}</span></div>
    <button id="langToggle" class="pill" aria-pressed="false" aria-label="切换中英文">
      <span class="k-cn">EN</span><span class="k-en" hidden>中文</span>
    </button>
  </div>
</header>
<div class="progress" aria-hidden="true"><span id="pbar"></span></div>
<div class="issue-hero">
  <div class="issue-kicker"><span class="kbar"></span><span class="k-cn">华尔街日报 · 每日深读</span><span class="k-en" hidden>THE WALL STREET JOURNAL · DAILY DEEP READ</span></div>
  <h1 class="issue-title"><span class="k-cn">{esc(date_cn)}</span><span class="k-en" hidden>{esc(date_en)}</span></h1>
  <p class="issue-dek"><span class="k-cn">{esc(dek_cn)}</span><span class="k-en" hidden>{esc(dek_en)}</span></p>
</div>''')

    parts.append('<main id="issue">')
    parts.append(render_front(order, front))
    parts.append(render_toc(order))

    last_sid = None
    sid_label = {sid: (cn, en) for sid, cn, en, *_ in SECTION_DEFS}
    for i, e in enumerate(order):
        uid = e['id']
        sid = section_of(e)
        if e.get('type') != 'index_digest' and sid != last_sid and sid in sid_label:
            cn, en = sid_label[sid]
            parts.append(_section_break(sid, cn, en))
            last_sid = sid
        elif e.get('type') == 'index_digest':
            last_sid = None
        plan = plans_all.get(uid)
        mods = modules_all.get(uid)
        imgs = images_all.get(uid)
        b64 = img_cache.get(uid)
        if plan is not None:
            parts.append(render_enhanced_article(
                e, plan, asset_loader=asset_loader, modules=mods,
                images=imgs, img_b64=b64, curated=treatments.get(uid),
                execution_receipts=execution_receipts))
        else:
            parts.append(render_article(
                e, mods, imgs, b64, curated=treatments.get(uid),
                execution_receipts=execution_receipts))
        prev_e = order[i - 1] if i > 0 else None
        next_e = order[i + 1] if i + 1 < len(order) else None
        parts.append(article_nav(
            prev_e['id'] if prev_e else None, prev_e.get('title_cn') if prev_e else None,
            next_e['id'] if next_e else None, next_e.get('title_cn') if next_e else None))

    if review_articles and gate_status:
        parts.append('<section class="review-queue" hidden aria-label="待审核">')
        for e in review_articles:
            parts.append(f'<div id="review-{e["id"]}"></div>')
        parts.append('</section>')
    parts.append('</main>')

    parts.append(f'''
<footer class="issue-foot">
  <div class="arule"></div>
  <p><span class="k-cn">《华尔街日报》 {esc(date_cn)}</span><span class="k-en" hidden>The Wall Street Journal, {esc(date_en)}</span></p>
  <button id="toTop" class="pill"><span class="k-cn">回顶部</span><span class="k-en" hidden>Back to top</span></button>
</footer>''')
    return '\n'.join(parts), order
