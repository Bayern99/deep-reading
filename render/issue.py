#!/usr/bin/env python3
"""WSJ 深读 · 整期组装（目录 / 阅读顺序 / 导航 / 进度条）
分组：P1 必读 → P2 → P3 → 数据附录（data_table 全部沉底）；组内按 final.json 原顺序。
"""
from components import esc
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


def reading_order(articles):
    order = []
    for sid, *_rest in SECTION_DEFS:
        order.extend([e for e in articles if section_of(e) == sid])
    return order


def render_toc(order):
    h2 = ['<nav id="toc" class="toc" aria-label="toc">']
    h2.append('<div class="toc-head"><span class="k-cn">本期目录</span><span class="k-en" hidden>IN THIS ISSUE</span></div>')
    buckets = {sid: [] for sid, *_ in SECTION_DEFS}
    for e in order:
        buckets[section_of(e)].append(e)
    for sid, cn, en, _secs, _pages, default_open in SECTION_DEFS:
        items = buckets[sid]
        if not items:
            continue
        open_attr = ' open' if default_open or sid == 'front' else ''
        h2.append(f'<details class="toc-sec"{open_attr}>')
        h2.append(
            f'<summary class="toc-group"><span class="k-cn">{cn}</span>'
            f'<span class="k-en" hidden>{en}</span>'
            f'<span class="toc-n">{len(items)}</span></summary>')
        h2.append('<ol class="toc-list">')
        for e in items:
            meta = ' · '.join(x for x in [e.get('section') or '', (e.get('page') or '') + ' 版'] if x)
            h2.append(f'''<li><a href="#s-{e["id"]}">
      <span class="toc-t"><span class="k-cn">{esc(e.get("title_cn") or e.get("title") or e["id"])}</span><span class="k-en" hidden>{esc(e.get("title") or "")}</span></span>
      <span class="toc-m">{esc(meta)}</span></a></li>''')
        h2.append('</ol>')
        h2.append('</details>')
    h2.append('</nav>')
    return '\n'.join(h2)


def render_issue(articles, modules_all, images_all, img_cache, issue_date,
                 gate_status=None, plans_all=None, asset_loader=None,
                 curation=None):
    """gate_status: {aid: ('pass'|'warn'|'block', issues)}。warn/block 不进正文，只进待审核区。
    plans_all: editorial-plans by article id → enhanced production path.
    curation: render/curation.json — exclude（撤下死内容）与 data_treatment（数据稿编辑处理）。
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
    order = reading_order(pub_articles)
    n_pub = len(order)
    n_review = len(review_articles)
    parts = []

    # masthead
    masthead = '''
<header class="masthead">
  <a class="skip" href="#toc">跳到目录</a>
  <div class="mast-in">
    <div class="brand"><span class="sq"></span><span class="wm k-cn">WSJ 深读</span><span class="wm k-en" hidden>WSJ Deep Read</span></div>
    <div class="mast-meta"><span class="k-cn">2026年10月12日 星期一</span><span class="k-en" hidden>Mon, Oct 12, 2026</span></div>
    <button id="langToggle" class="pill" aria-pressed="false" aria-label="切换中英文">
      <span class="k-cn">EN</span><span class="k-en" hidden>中文</span>
    </button>
  </div>
</header>
<div class="progress" aria-hidden="true"><span id="pbar"></span></div>
<div class="issue-hero">
  <div class="issue-kicker"><span class="kbar"></span><span class="k-cn">华尔街日报 · 每日深读</span><span class="k-en" hidden>THE WALL STREET JOURNAL · DAILY DEEP READ</span></div>
  <h1 class="issue-title"><span class="k-cn">2026年10月12日</span><span class="k-en" hidden>October 12, 2026</span></h1>
  <p class="issue-dek"><span class="k-cn">共 {n_pub} 篇 · 机器辅助翻译 · 逐版摘要</span><span class="k-en" hidden>{n_pub} stories · machine-assisted translation · section-by-section digest</span></p>
</div>'''.format(n_pub=n_pub)
    parts.append(masthead)

    parts.append('<main id="issue">')
    parts.append(render_toc(order))

    for i, e in enumerate(order):
        uid = e['id']
        plan = plans_all.get(uid)
        if plan is not None:
            parts.append(render_enhanced_article(e, plan, asset_loader=asset_loader))
        else:
            mods = modules_all.get(uid)
            imgs = images_all.get(uid)
            b64 = img_cache.get(uid)
            parts.append(render_article(e, mods, imgs, b64,
                                        curated=treatments.get(uid)))
        prev_e = order[i - 1] if i > 0 else None
        next_e = order[i + 1] if i + 1 < len(order) else None
        parts.append(article_nav(
            prev_e['id'] if prev_e else None, prev_e.get('title_cn') if prev_e else None,
            next_e['id'] if next_e else None, next_e.get('title_cn') if next_e else None))
    # 待审核区：WARN/BLOCK 文章只列元数据，不渲染正文
    if review_articles and gate_status:
        parts.append('<section class="review-queue" aria-label="待审核">')
        parts.append('<h2><span class="k-cn">待审核（%d 篇）</span>'
                     '<span class="k-en" hidden>Under Review (%d)</span></h2>' % (n_review, n_review))
        parts.append('<p class="review-note"><span class="k-cn">以下文章尚未通过完整性确认，暂不发布正文。</span>'
                     '<span class="k-en" hidden>These articles are pending integrity review.</span></p>')
        for e in review_articles:
            status, issues = gate_status.get(e['id'], ('warn', []))
            reason = '; '.join(i.get('detail', '')[:80] for i in issues[:2] if isinstance(i, dict))
            parts.append(
                f'<article class="review-item" id="review-{e["id"]}">'
                f'<h3>{e.get("title_cn") or e["id"]}</h3>'
                f'<p class="review-meta">{e["id"]} · {e.get("type","")} · 状态：{status}</p>'
                f'<p class="review-reason">{reason}</p>'
                '</article>')
        parts.append('</section>')
    parts.append('</main>')

    parts.append('''
<footer class="issue-foot">
  <div class="arule"></div>
  <p><span class="k-cn">《华尔街日报》2026年10月12日 · 机器辅助翻译 · 逐版摘要</span><span class="k-en" hidden>WSJ, Oct 12, 2026 · machine-assisted translation · section digest</span></p>
  <button id="toTop" class="pill"><span class="k-cn">回顶部</span><span class="k-en" hidden>Back to top</span></button>
</footer>''')
    return '\n'.join(parts), order
