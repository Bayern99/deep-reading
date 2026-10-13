#!/usr/bin/env python3
"""WSJ 深读 · 整期组装（目录 / 阅读顺序 / 导航 / 进度条）
分组：P1 必读 → P2 → P3 → 数据附录（data_table 全部沉底）；组内按 final.json 原顺序。
"""
from components import esc
from article import render_article, article_nav


GROUP_DEFS = [
    ('p1', 'P1 \u5fc5\u8bfb', 'P1 MUST READ'),
    ('p2', 'P2', 'P2'),
    ('p3', 'P3', 'P3'),
    ('data', '\u6570\u636e\u9644\u5f55', 'DATA APPENDIX'),
]


def group_of(e):
    if e.get('type') == 'data_table':
        return 'data'
    return {'P1': 'p1', 'P2': 'p2', 'P3': 'p3'}.get(e.get('priority'), 'p3')


def reading_order(articles):
    order = []
    for gid, _, _ in GROUP_DEFS:
        order.extend([e for e in articles if group_of(e) == gid])
    return order


def render_toc(order):
    h2 = ['<nav id="toc" class="toc" aria-label="toc">']
    h2.append('<div class="toc-head"><span class="k-cn">\u672c\u671f\u76ee\u5f55</span><span class="k-en" hidden>IN THIS ISSUE</span></div>')
    cur = None
    for e in order:
        g = group_of(e)
        if g != cur:
            if cur is not None:
                h2.append('</ol>')
            cur = g
            label = dict((x[0], (x[1], x[2])) for x in GROUP_DEFS)[g]
            h2.append(f'<div class="toc-group"><span class="k-cn">{label[0]}</span><span class="k-en" hidden>{label[1]}</span></div>')
            h2.append('<ol class="toc-list">')
        meta = ' \u00b7 '.join(x for x in [e.get('section') or '', (e.get('page') or '') + ' \u7248'] if x)
        h2.append(f'''<li><a href="#s-{e["id"]}">
      <span class="toc-t"><span class="k-cn">{esc(e.get("title_cn") or e.get("title") or e["id"])}</span><span class="k-en" hidden>{esc(e.get("title") or "")}</span></span>
      <span class="toc-m">{esc(meta)}</span></a></li>''')
    h2.append('</ol>')
    h2.append('</nav>')
    return '\n'.join(h2)


def render_issue(articles, modules_all, images_all, img_cache, issue_date):
    order = reading_order(articles)
    parts = []

    # masthead
    parts.append('''
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
  <p class="issue-dek"><span class="k-cn">共 117 篇 · 机器辅助翻译 · 逐版摘要</span><span class="k-en" hidden>117 stories · machine-assisted translation · section-by-section digest</span></p>
</div>''')

    parts.append('<main id="issue">')
    parts.append(render_toc(order))

    for i, e in enumerate(order):
        uid = e['id']
        mods = modules_all.get(uid)
        imgs = images_all.get(uid)
        b64 = img_cache.get(uid)
        parts.append(render_article(e, mods, imgs, b64))
        prev_e = order[i - 1] if i > 0 else None
        next_e = order[i + 1] if i + 1 < len(order) else None
        parts.append(article_nav(
            prev_e['id'] if prev_e else None, prev_e.get('title_cn') if prev_e else None,
            next_e['id'] if next_e else None, next_e.get('title_cn') if next_e else None))
    parts.append('</main>')

    parts.append('''
<footer class="issue-foot">
  <div class="arule"></div>
  <p><span class="k-cn">《华尔街日报》2026年10月12日 · 机器辅助翻译 · 逐版摘要</span><span class="k-en" hidden>WSJ, Oct 12, 2026 · machine-assisted translation · section digest</span></p>
  <button id="toTop" class="pill"><span class="k-cn">回顶部</span><span class="k-en" hidden>Back to top</span></button>
</footer>''')
    return '\n'.join(parts), order
