"""Reader shell: single-file Issue Artifact.

Assembles composed reading units into a self-contained HTML publication with
the seven canonical sections, rubric kickers, an Edition Overview plus
Immersive Article Reader, and global ``中文 / EN / 双语`` switching.

Language rules (ADR 0001):
- narrative elements (title, dek, takeaways, prose, pull quotes, captions)
  carry ``.lang-cn`` + ``.lang-en`` pairs; in ``双语`` mode they stack
  (Chinese above, English below in secondary serif);
- SVG internal text and UI controls stay single-language (中文 in ``双语``
  mode, switching to ``EN`` in ``EN`` mode) so geometry never collides.
"""
from __future__ import annotations

import base64
import html
from dataclasses import dataclass, field
from typing import Any

from .verify import assert_no_forbidden_strings

SECTIONS = [
    ("a1", "A1 头版要闻", "Front Page"),
    ("us", "U.S. 美国", "U.S."),
    ("world", "World 世界", "World"),
    ("bt", "Business & Tech 商业与科技", "Business & Tech"),
    ("markets", "Markets 市场与金融", "Markets"),
    ("opinion", "Opinion 社论与观点", "Opinion"),
    ("life", "Life & Arts 文化与生活", "Life & Arts"),
]

CSS = """
:root{--paper:#faf8f4;--paper-card:#f3efe6;--paper-deep:#ebe5d8;--ink:#141413;--body:#242220;--mut:#646059;--line:#dcd6c8;--accent:#b85d19;--accent-soft:rgba(184,93,25,0.14);--navy-bg:#0f1d2b;--navy-card:#16283b;--gold:#c99738;--orange:#b85d19;--red:#9e2a2b;--font-display:'Playfair Display','Noto Serif SC',Georgia,serif;--font-serif-cn:'Noto Serif SC','Songti SC',serif;--font-serif-en:'Lora','Noto Serif SC',Georgia,serif;--font-sans:'Inter','Noto Sans SC',-apple-system,sans-serif;--font-mono:'JetBrains Mono',monospace}
*{box-sizing:border-box}html{scroll-behavior:smooth}
html,body{overflow-x:clip}
body{margin:0;background:var(--paper);color:var(--body);font-family:var(--font-serif-cn);font-size:17px;line-height:1.85}
html[lang="en"] body{font-family:var(--font-serif-en)}
.wrap{max-width:1120px;margin:0 auto;padding:0 20px}
.masthead{position:sticky;top:0;background:var(--paper);border-bottom:2px solid var(--ink);z-index:9}
.masthead .wrap{display:flex;align-items:center;gap:12px;padding:10px 20px}
.masthead .block{width:14px;height:14px;background:var(--accent);flex:none}
.wordmark{font-family:var(--font-display);font-weight:800;letter-spacing:.04em;color:var(--ink);font-size:18px;white-space:nowrap}
.masthead .date{font-family:var(--font-mono);font-size:11.5px;color:var(--mut);margin-left:2px}
.lang-switch{margin-left:auto;display:flex;gap:6px}
.pill{font-family:var(--font-sans);font-size:12px;font-weight:500;padding:5px 13px;border-radius:9999px;border:1px solid var(--ink);background:transparent;color:var(--ink);cursor:pointer}
.pill.on{background:var(--ink);color:var(--paper)}
nav.sections{border-bottom:1px solid var(--line);background:var(--paper)}
nav.sections .wrap{display:flex;gap:4px;flex-wrap:wrap;padding:6px 20px}
nav.sections a{font-family:var(--font-sans);font-size:13px;font-weight:500;color:var(--mut);text-decoration:none;padding:4px 8px}
nav.sections a:hover{color:var(--ink)}
.view-toggle{display:flex;gap:6px;margin:18px 0 0}
h1.page-title{font-family:var(--font-display);font-weight:800;font-size:32px;line-height:1.3;color:var(--ink);margin:14px 0 4px}
.front-dek{font-size:18px;color:var(--mut);margin:0 0 8px}
.overview{display:grid;grid-template-columns:1fr;gap:0;max-width:1120px;border-top:2px solid var(--ink);margin-top:14px}
.ov-item{display:block;text-decoration:none;color:inherit;padding:18px 4px;border-bottom:1px solid var(--line)}
.ov-item:hover{background:var(--paper-card)}
.ov-item .kicker,.kicker{font-family:var(--font-sans);font-size:13px;font-weight:700;letter-spacing:.14em;color:var(--mut);margin:0 0 6px}
.ov-item .kicker::before,.kicker::before{content:"";display:inline-block;width:8px;height:8px;background:var(--accent);margin-right:8px;vertical-align:baseline}
.ov-item h2{font-size:23px;line-height:1.35;margin:0 0 4px;color:var(--ink)}
.ov-item .dek{font-size:15px;color:var(--mut);margin:0;line-height:1.6}
.unit{display:none;padding:34px 0 10px;border-top:1px solid var(--ink);margin-top:34px}
body[data-view="read"] .unit{display:block}
body[data-view="overview"] .unit{display:none!important}
body[data-view="read"] .overview,body[data-view="read"] .view-toggle .pill.ov{display:none}
.unit-head{max-width:1120px;margin:0 auto}
.unit-head h1{font-family:var(--font-display);font-size:42px;font-weight:800;line-height:1.25;color:var(--ink);margin:6px 0 8px;letter-spacing:-.01em}
.unit-head h1,.sec-h,.ov-item h2,.section-head h2{text-wrap:balance}
.dek{font-size:18px;line-height:1.7;color:var(--mut);margin:0 0 10px}
.byline{font-family:var(--font-sans);font-size:13px;font-weight:700;letter-spacing:.04em;color:var(--ink);margin:0 0 6px}
.hero-meta-grid{display:grid;grid-template-columns:1fr 1.35fr;gap:32px;border-top:2px solid var(--ink);padding-top:24px;margin-top:18px;align-items:start}
.byline-block{font-family:var(--font-sans)}
.date-line{font-family:var(--font-mono);font-size:12px;color:var(--mut);margin:2px 0 16px}
.key-ledger-strip{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;padding-top:12px;border-top:1px solid var(--line)}
.mini-stat-val{font-family:var(--font-mono);font-size:1.15rem;font-weight:700;color:var(--ink)}
.mini-stat-lbl{font-family:var(--font-sans);font-size:.72rem;color:var(--mut);line-height:1.35;margin-top:2px}
.dossier-card{background:var(--paper-card);border:1px solid var(--line);border-left:4px solid var(--accent);padding:18px 22px}
.dossier-header{font-family:var(--font-sans);font-size:.74rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:var(--accent);margin-bottom:10px}
.dossier-card ul.takeaways{max-width:none;margin:0;padding:0 0 0 22px;border:none}
.dossier-card .thesis-box{max-width:none;margin:0;border-left:none;padding:0;background:transparent;font-size:16.5px}
.unit-body{max-width:1120px;margin:0 auto}
.unit-tier3 .unit-head,.unit-tier3 .unit-body{max-width:680px}
.prose-p{margin:0 0 1.05em}
.lang-en{display:none}
html[lang="en"] .lang-cn{display:none}
html[lang="en"] .lang-en{display:block}
html[lang="bi"] .lang-en{display:block;color:var(--mut);font-size:.94em;line-height:1.7;margin-top:.2em}
.lang-en-block{display:none;font-size:.88em;color:var(--mut);line-height:1.6}
html[lang="en"] .lang-en-block{display:block}
html[lang="bi"] .lang-en-block{display:block;margin-top:.2em}
svg .l-en{display:none}
html[lang="en"] svg .l-cn{display:none}
html[lang="en"] svg .l-en{display:block}
.editorial-section{padding:44px 0 8px;border-bottom:1px solid var(--line)}
.editorial-section:last-of-type{border-bottom:none}
.section-banner{display:flex;align-items:baseline;gap:16px;margin-bottom:30px;padding-bottom:12px;border-bottom:1px solid var(--line)}
.section-num{font-family:var(--font-mono);font-size:.82rem;font-weight:700;color:var(--accent);letter-spacing:.08em;text-transform:uppercase;white-space:nowrap}
.section-banner .sec-h,.section-banner .chapter-kicker{margin:0;font-family:var(--font-display);font-size:clamp(1.3rem,2.2vw,1.85rem);font-weight:700;color:var(--ink);line-height:1.25}
.grid-asymmetric{display:grid;grid-template-columns:minmax(0,650px) minmax(280px,380px);justify-content:space-between;gap:48px;align-items:start}
.prose-column{min-width:0}
.rail-column{min-width:0;display:flex;flex-direction:column;gap:26px;position:sticky;top:76px}
.lead-paragraph{font-size:1.22rem;font-weight:600;line-height:1.75;color:var(--ink);padding-left:18px;border-left:3px solid var(--accent);margin-bottom:1.3em}
.metric-card{background:var(--paper-card);border:1px solid var(--line);border-top:3px solid var(--ink);padding:18px 20px}
.metric-card.accent-top{border-top-color:var(--accent)}
.metric-val{font-family:var(--font-mono);font-size:1.9rem;font-weight:700;color:var(--ink);line-height:1.15;margin-bottom:8px;letter-spacing:-.02em}
.metric-card.accent-top .metric-val{color:var(--accent)}
.metric-lbl{font-family:var(--font-sans);font-size:.86rem;font-weight:700;color:var(--ink);margin-bottom:6px;line-height:1.4}
.metric-note{font-family:var(--font-sans);font-size:.78rem;color:var(--mut);line-height:1.5}
.takeaways{max-width:640px;margin:18px auto;padding:14px 0 14px 22px;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.takeaway{margin:0 0 8px;font-size:15.5px;line-height:1.7}
.takeaway::marker{font-family:var(--font-sans);font-weight:700;color:var(--mut)}
.thesis-box{max-width:640px;margin:20px auto;border-left:3px solid var(--ink);padding:10px 18px;font-size:18px;font-weight:700;line-height:1.7;color:var(--ink);background:#f6f3ec}
.sec-h{font-size:21px;line-height:1.4;color:var(--ink);margin:1.6em 0 .6em;font-weight:700}
.sec-h-en{display:none;font-family:var(--font-sans);font-size:13px;font-weight:400;color:var(--mut);margin-left:10px}
html[lang="en"] .sec-h .lang-cn{display:none}
html[lang="en"] .sec-h .sec-h-en,html[lang="bi"] .sec-h .sec-h-en{display:inline}
.pull-quote{background:var(--paper-card);border-left:4px solid var(--ink);padding:20px 22px;margin:0;font-size:19px;font-weight:700;line-height:1.6;color:var(--ink)}
.book-details{background:var(--paper-card);border:1px solid var(--line);padding:14px 18px;margin:0}
.book-details .bd-title_cn{font-size:17px;font-weight:700;color:var(--ink)}
.book-details .bd-title_en{font-family:var(--font-sans);font-size:13px;color:var(--mut)}
.book-details .bd-author,.book-details .bd-imprint{font-family:var(--font-sans);font-size:13px;color:var(--body)}
.inline-adviser-callout{background:var(--paper-card);border:1px solid var(--line);border-left:4px solid var(--accent);padding:20px 24px;margin:26px 0}
.callout-kicker{font-family:var(--font-mono);font-size:.74rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:var(--accent);margin-bottom:10px}
.exhibit-box{background:#fff;border:1px solid var(--line);padding:24px;margin:30px 0;box-shadow:0 4px 20px rgba(20,20,19,.03)}
.exhibit-kicker{font-family:var(--font-mono);font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.09em;color:var(--accent);margin-bottom:10px}
.exhibit-box figure.wsj-fig{margin:0 auto;max-width:100%}
.exhibit-box .companion{margin:16px 0 0;max-width:100%}
.exhibit-box .wsj-chart{margin:0 auto;max-width:100%}
.defense-dossier{background:var(--navy-bg);color:#f2efe9;padding:28px;margin:30px 0;border-radius:3px;border-top:4px solid var(--gold)}
.defense-kicker{font-family:var(--font-mono);font-size:.74rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--gold);margin-bottom:14px;display:flex;gap:10px;flex-wrap:wrap}
.defense-dossier .prose-p{color:#eae6df;font-size:1.03rem;margin-bottom:1.1em}
.defense-dossier .prose-p:last-child{margin-bottom:0}
html[lang="bi"] .defense-dossier p .lang-en{color:#9fb3c8}
.defense-dossier mark.ed-hl{background:rgba(201,151,56,.25);color:#fff}
.verdict-box{background:var(--ink);color:var(--paper);padding:30px 32px;margin-top:24px;border-left:5px solid var(--accent)}
.verdict-kicker{font-family:var(--font-mono);font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.12em;color:var(--accent);margin-bottom:12px}
.verdict-prose{color:#eae6df;font-size:1.05rem;margin:0}
html[lang="bi"] .verdict-box .lang-en{color:#b9b4a9}
figure.wsj-fig{max-width:640px;margin:26px auto}
figure.wsj-fig img{width:100%;display:block;border:1px solid var(--line)}
figcaption{font-family:var(--font-sans);font-size:13px;color:var(--mut);line-height:1.6;margin-top:8px}
.companion{max-width:640px;margin:0 auto 26px;border:1px solid var(--line);border-top:2px solid var(--ink);padding:14px 18px;background:#fff}
.companion h3{font-size:15px;font-weight:700;color:var(--ink);margin:0 0 8px;font-family:var(--font-sans)}
.companion .co-title{font-size:14px;font-weight:700;color:var(--ink);margin:0 0 6px}
.companion .co-en{display:none;font-size:12px;color:var(--mut)}
html[lang="en"] .companion .co-en{display:block}
html[lang="bi"] .companion .co-en{display:block}
.companion ul{margin:6px 0;padding-left:18px;font-size:13.5px;line-height:1.7}
.companion .co-term{font-weight:700;color:var(--ink)}
.companion .co-cn{color:var(--body)}
html[lang="en"] .companion .co-cn{display:none}
.companion .co-src{font-size:12px;color:var(--mut);border-top:1px solid var(--line);margin-top:8px;padding-top:6px}
.wsj-chart{max-width:640px;margin:26px auto;border:1px solid var(--line);padding:16px;background:#fff}
.wsj-chart h3{font-size:15px;font-weight:700;color:var(--ink);margin:0 0 6px;font-family:var(--font-sans)}
.wsj-chart .ch-caption{font-family:var(--font-sans);font-size:12.5px;color:var(--mut);margin-top:8px}
.letter-group-title{font-size:20px;line-height:1.4;color:var(--ink);margin:1.4em 0 .4em;font-weight:700}
.letter{border-bottom:1px solid var(--line);padding-bottom:10px;margin-bottom:14px}
.letter-title{font-size:18px;margin:0 0 6px;color:var(--ink)}
.letter-title-en{display:none;font-family:var(--font-sans);font-size:13px;font-weight:400;color:var(--mut);margin-left:8px}
html[lang="en"] .letter-title .letter-title-en,html[lang="bi"] .letter-title .letter-title-en{display:inline}
.letter-sig{font-family:var(--font-sans);font-size:13px;font-weight:700;color:var(--mut);text-align:right;margin:4px 0 0}
.wn-link{margin:-0.6em 0 1.2em;text-align:right}
.wn-link a{font-family:var(--font-sans);font-size:13px;font-weight:700;color:var(--orange);text-decoration:none}
.wn-link a:hover{text-decoration:underline}
.wn-en{color:var(--mut);font-weight:400}
.sidebar-link{max-width:640px;margin:18px auto;border:1px solid var(--line);border-left:3px solid var(--orange);padding:10px 16px;font-size:14px;font-family:var(--font-sans);color:var(--body)}
.sidebar-link a{color:var(--ink);font-weight:700;text-decoration:none}
.sidebar-link a:hover{text-decoration:underline}
figure.wsj-fig.view-only img{border:1px solid var(--line);background:#fff}
mark.ed-hl{background:var(--accent-soft);color:inherit;padding:.06em .28em;border-bottom:1.5px solid rgba(184,93,25,.55);border-radius:2px;font-weight:600}
.section-head{max-width:1120px;margin:44px auto 0;border-bottom:2px solid var(--ink);padding-bottom:6px}
.section-head h2{font-size:24px;color:var(--ink);margin:0}
.section-head .en{font-family:var(--font-sans);font-size:13px;color:var(--mut);margin-left:8px}
@media(max-width:980px){.hero-meta-grid{grid-template-columns:1fr;gap:24px}.grid-asymmetric{grid-template-columns:1fr;gap:32px}.rail-column{position:static}}
@media(max-width:768px){.unit-head h1{font-size:30px}.pull-quote{font-size:18px}}
@media(max-width:430px){body{font-size:17px}.unit-head h1{font-size:28px}h1.page-title{font-size:26px}.masthead .date{display:none}.editorial-section{padding:30px 0}.section-banner{margin-bottom:22px}.key-ledger-strip{gap:8px}.exhibit-box{padding:16px 12px;margin:24px 0}.defense-dossier{padding:20px 16px}.verdict-box{padding:22px 18px}}
"""

JS = """
function setLang(l){document.documentElement.setAttribute('lang',l===undefined?(document.documentElement.getAttribute('lang')||'zh'):l);
document.querySelectorAll('.lang-switch .pill').forEach(function(b){b.classList.toggle('on',b.dataset.lang===document.documentElement.getAttribute('lang'))});}
function setView(v){document.body.setAttribute('data-view',v);
document.querySelectorAll('.view-toggle .pill').forEach(function(b){b.classList.toggle('on',b.dataset.view===v)});}
document.addEventListener('DOMContentLoaded',function(){
setLang('zh');setView(location.hash&&document.querySelector(location.hash)?'read':'overview');
document.querySelectorAll('.lang-switch .pill').forEach(function(b){b.addEventListener('click',function(){setLang(b.dataset.lang)})});
document.querySelectorAll('.view-toggle .pill').forEach(function(b){b.addEventListener('click',function(){setView(b.dataset.view);if(b.dataset.view==='overview')history.replaceState(null,'',' ')})});
document.querySelectorAll('a.ov-item').forEach(function(a){a.addEventListener('click',function(){setView('read')})});
window.addEventListener('hashchange',function(){if(location.hash)setView('read')});});
"""


@dataclass
class UnitEntry:
    unit_id: str
    section: str  # SECTIONS key
    kicker: str
    title_cn: str
    dek_cn: str
    element_html: str
    tier: int
    genre: str
    article_ids: list[str] = field(default_factory=list)


def data_uri(webp_bytes: bytes) -> str:
    return "data:image/webp;base64," + base64.b64encode(webp_bytes).decode("ascii")


# Group C Forensic Dossier type system (Issue #5): display serif for headlines,
# Lora for English narrative, Noto Serif/Sans SC for Chinese, Inter for UI,
# JetBrains Mono for ledger/stat values.  Offline readers fall back to the
# system serif/sans stacks declared in CSS.
FONTS_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?'
    'family=Playfair+Display:wght@700;800'
    '&family=Lora:ital,wght@0,400;0,600;1,400'
    '&family=Noto+Serif+SC:wght@400;600;700'
    '&family=Noto+Sans+SC:wght@400;500;700'
    '&family=Inter:wght@400;500;600;700'
    '&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">'
)


def build_issue_artifact(
    *,
    date_cn: str,
    date_en: str,
    units: list[UnitEntry],
    front_dek_cn: str = "",
    extra_head_html: str = "",
) -> str:
    """Assemble the self-contained single-file Issue Artifact HTML string."""
    by_section: dict[str, list[UnitEntry]] = {key: [] for key, _, _ in SECTIONS}
    for u in units:
        by_section[u.section].append(u)
    populated = [(key, cn, en) for key, cn, en in SECTIONS if by_section[key]]

    nav = "".join(
        f'<a href="#sec-{key}">{html.escape(cn)}</a>' for key, cn, _ in populated
    )
    overview_items = "".join(
        f'<a class="ov-item" href="#u-{html.escape(u.unit_id)}" data-tier="{u.tier}">'
        f'<p class="kicker">{html.escape(u.kicker)}</p>'
        f'<h2><span class="lang-cn">{html.escape(u.title_cn)}</span></h2>'
        f'<p class="dek"><span class="lang-cn">{html.escape(u.dek_cn)}</span></p></a>'
        for u in units
    )

    section_blocks = []
    for key, cn, en in populated:
        members = by_section[key]
        head = (
            f'<div class="section-head" id="sec-{key}"><h2>{html.escape(cn)}'
            f'<span class="en">{html.escape(en)}</span></h2></div>'
        )
        body = "".join(
            f'<div class="unit" id="u-{html.escape(m.unit_id)}" data-unit="{html.escape(m.unit_id)}" '
            f'data-tier="{m.tier}" data-genre="{html.escape(m.genre)}">{m.element_html}</div>'
            for m in members
        )
        section_blocks.append(head + body)

    doc = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WSJ 深读 · {html.escape(date_cn)}</title>
{FONTS_LINK}
<style>{CSS}</style>
{extra_head_html}
</head>
<body data-view="overview">
<header class="masthead"><div class="wrap">
<span class="block"></span><span class="wordmark">WSJ 深读</span>
<span class="date">{html.escape(date_cn)} · {html.escape(date_en)}</span>
<span class="lang-switch">
<button class="pill" data-lang="zh">中文</button>
<button class="pill" data-lang="en">EN</button>
<button class="pill" data-lang="bi">双语</button>
</span></div></header>
<nav class="sections"><div class="wrap">{nav}</div></nav>
<main><div class="wrap">
<div class="view-toggle">
<button class="pill ov" data-view="overview" onclick="setView('overview')">本期概览</button>
<button class="pill" data-view="read">沉浸阅读</button>
</div>
<h1 class="page-title">本期概览 <span style="font-family:'Noto Sans SC';font-size:14px;color:var(--mut)">Edition Overview</span></h1>
<p class="front-dek">{html.escape(front_dek_cn)}</p>
<div class="overview">{overview_items}</div>
{''.join(section_blocks)}
</div></main>
<script>{JS}</script>
</body>
</html>"""
    assert_no_forbidden_strings(doc)
    return doc
