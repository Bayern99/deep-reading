#!/usr/bin/env python3
"""Rebuild today's WSJ deep-read page on the weekend edition's design system.
Content comes verbatim from final.json; only the shell/styling is rebuilt."""
import json, re, html

SRC = '/home/hatch/workspace/wsj-deep-read/2026-10-12/final.json'
OLD = '/home/hatch/workspace/ts-spaces/wsj-weekend-deep-read/index.html'
OUT = '/home/hatch/workspace/wsj-deep-read/2026-10-12/wsj-2026-10-12-deepread-v2.html'

def esc(s):
    return html.escape(s or '', quote=True)

fj = json.load(open(SRC))
old = open(OLD).read()
css = '\n'.join(re.findall(r'<style[^>]*>(.*?)</style>', old, re.S))

SECTIONS = [
    ('News', '新闻', 'NEWS'),
    ('World News', '国际新闻', 'WORLD NEWS'),
    ('U.S. News', '美国新闻', 'U.S. NEWS'),
    ('Technology', '科技', 'TECHNOLOGY'),
    ('Personal Journal', '个人生活', 'PERSONAL JOURNAL'),
    ('Sports', '体育', 'SPORTS'),
    ('Arts in Review', '艺术评论', 'ARTS IN REVIEW'),
    ('Opinion', '观点', 'OPINION'),
    ('Business & Finance', '商业与金融', 'BUSINESS & FINANCE'),
    ('Business News', '商业新闻', 'BUSINESS NEWS'),
    ('Money & Investing', '理财与投资', 'MONEY & INVESTING'),
    ('Heard on the Street', '街谈巷议', 'HEARD ON THE STREET'),
    ('Data', '数据附录', 'DATA APPENDIX'),
]

PRILABEL = {'P1': 'P1 · 必读', 'P2': 'P2 · 重点', 'P3': 'P3 · 延伸'}
PRINUM = {'P1': '1', 'P2': '2', 'P3': '3'}

by_sec = {}
for e in fj:
    by_sec.setdefault(e['section'], []).append(e)

def paras(text):
    return [p.strip() for p in (text or '').split('\n\n') if p.strip()]

def body_html(cn, en, cls='b'):
    parts = []
    for p in paras(cn):
        parts.append('<p class="%s-cn">%s</p>' % (cls, esc(p)))
    en_ps = ''.join('<p class="%s-en" hidden>%s</p>' % (cls, esc(p)) for p in paras(en))
    return '\n'.join(parts) + ('\n' + en_ps if en_ps else '')

def table_html(en_text, caption):
    blocks = [b.strip() for b in (en_text or '').split(' / ') if b.strip()]
    tbls = []
    for b in blocks:
        rows = [r.strip() for r in b.split('\n') if r.strip()]
        if not rows:
            continue
        if all('|' not in r for r in rows):
            cells = ''.join('<td>%s</td>' % esc(r) for r in rows)
            tbls.append('<table><tbody><tr>%s</tr></tbody></table>' % cells)
            continue
        head, body_rows = None, rows
        if '|' in rows[0]:
            head = [c.strip() for c in rows[0].split('|')]
            body_rows = rows[1:]
        t = ['<table>']
        if head:
            t.append('<thead><tr>' + ''.join('<th>%s</th>' % esc(c) for c in head) + '</tr></thead>')
        t.append('<tbody>')
        for r in body_rows:
            cells = [c.strip() for c in r.split('|')] if '|' in r else [r]
            t.append('<tr>' + ''.join('<td>%s</td>' % esc(c) for c in cells) + '</tr>')
        t.append('</tbody></table>')
        tbls.append('\n'.join(t))
    inner = '\n'.join(tbls)
    return '<div class="table-wrap"><p class="tbl-cap">%s</p>%s</div>' % (esc(caption), inner)

def story_html(e):
    pid = esc(e['id'])
    pri = e.get('priority', 'P3')
    pnum = PRINUM.get(pri, '3')
    page = esc(e.get('page') or '')
    tcn = e.get('title_cn') or e.get('title') or ''
    ten = e.get('title') or ''
    search = esc((tcn + ' ' + ten + ' ' + (e.get('body_cn') or '')[:300]).replace("'", ''))
    h = ['<article class="story" data-priority="%s" data-search="%s" id="s-%s">' % (pnum, search, pid)]
    h.append('<header class="story-head"><span class="page-ref">%s</span>'
             '<h3 data-title-zh="%s" data-title-en="%s">%s</h3>'
             '<button class="title-toggle" type="button" aria-pressed="false">EN · 英文标题</button></header>'
             % (page, esc(tcn), esc(ten), esc(tcn)))
    h.append('<span class="story-priority" data-level="%s">%s</span>' % (pnum, PRILABEL.get(pri, 'P3 · 延伸')))
    if e.get('byline'):
        h.append('<p class="byline">%s</p>' % esc(e['byline']))
    if e.get('dek_cn'):
        h.append('<p class="dek-cn">%s</p>' % esc(e['dek_cn']))
        if e.get('dek'):
            h.append('<p class="dek-en" hidden>%s</p>' % esc(e['dek']))
    h.append('<div class="story-body">')
    typ = e.get('type')
    if typ == 'data_table':
        en_text = e.get('body_en') or ''
        if en_text.strip().lower().startswith('chart embedded'):
            h.append('<div class="chart-note"><p class="b-cn">【图表说明】以下为该图表的文字描述，数据为原文摘录。</p>'
                     '<p class="b-en" hidden>Chart description; data excerpted from the original.</p>'
                     '<pre class="raw">%s</pre></div>' % esc(en_text))
        else:
            h.append(table_html(en_text, '%s · %s' % (tcn, page)))
    else:
        h.append(body_html(e.get('body_cn'), e.get('body_en')))
    h.append('</div>')
    if e.get('context_cn'):
        attr = esc(e.get('context_attr') or '')
        src = '<span class="context-source">%s</span>' % attr if attr else ''
        h.append('<details class="context"><summary>背景资料 · CONTEXT%s</summary>'
                 '<div class="context-body"><p class="ctx-cn">%s</p></div></details>' % (src, esc(e['context_cn'])))
    h.append('</article>')
    return '\n'.join(h)

n_articles = sum(1 for e in fj if e['type'] != 'data_table')
n_data = sum(1 for e in fj if e['type'] == 'data_table')

toc_links = []
sections_html = []
for idx, (en, zh, enup) in enumerate(SECTIONS, 1):
    items = by_sec.get(en, [])
    if not items:
        continue
    sid = 'sec-%02d' % idx
    pages = sorted(set(x.get('page', '') for x in items if x.get('page')))
    toc_links.append('<a data-target="%s" href="#%s"><strong>%02d</strong><span>%s %s</span></a>'
                     % (sid, sid, idx, zh, pages[0] if pages else ''))
    cnt = '%d stories' % len(items) if en != 'Data' else '%d tables' % len(items)
    sections_html.append(
        '<section class="paper-section" id="%s" aria-label="%s">'
        '<div class="section-head"><span class="section-no">%02d</span>'
        '<div><h2>%s</h2><p>%s · %s</p></div></div>'
        '%s</section>' % (sid, esc(zh), idx, esc(zh), enup, cnt,
                          '\n'.join(story_html(x) for x in items)))

EXTRA_CSS = """
.dek-cn{font-family:ui-serif,"Source Han Serif SC","Noto Serif CJK SC","Noto Serif SC","Songti SC",STSong,SimSun,serif;font-size:18px;line-height:1.5;color:var(--ink);margin:14px 0 4px;font-weight:600}
.dek-en{font-size:14px;color:var(--muted);margin:0 0 6px}
.tbl-cap{font:700 13px/1.4 ui-monospace,SFMono-Regular,Consolas,monospace;color:var(--ink);margin:0 0 10px}
.chart-note .raw{font:12.5px/1.6 ui-monospace,SFMono-Regular,Consolas,monospace;white-space:pre-wrap;background:var(--paper-2);border:1px solid var(--rule);border-radius:8px;padding:14px;overflow-x:auto}
.title-toggle{flex:none;font:700 10px/1 ui-monospace,SFMono-Regular,Consolas,monospace;letter-spacing:.08em;color:var(--accent);background:transparent;border:1px solid var(--rule);border-radius:999px;padding:7px 12px;cursor:pointer;margin-top:6px;align-self:start}
.title-toggle:hover{border-color:var(--accent)}
.story-head{grid-template-columns:58px 1fr auto !important}
footer.colophon{margin-top:64px;border-top:1px solid var(--rule);padding-top:18px;color:var(--muted);font-size:12.5px}
"""

JS = """(function(){
var root=document.documentElement;
function setLang(l){
  root.dataset.lang=l;
  var en=l==='en';
  document.querySelectorAll('.story').forEach(function(st){
    var h=st.querySelector('h3');
    h.textContent=en?h.dataset.titleEn:h.dataset.titleZh;
    var t=st.querySelector('.title-toggle');if(t)t.setAttribute('aria-pressed',en?'true':'false');
  });
  document.querySelectorAll('.dek-cn,.b-cn,.ctx-cn').forEach(function(e){e.hidden=en;});
  document.querySelectorAll('.dek-en,.b-en,.ctx-en').forEach(function(e){e.hidden=!en;});
  var g=document.getElementById('globalLang');
  g.textContent=en?'\\u4e2d\\u6587 \\u00b7 \\u5168\\u90e8\\u4e2d\\u6587':'EN \\u00b7 \\u5168\\u90e8\\u82f1\\u6587';
  g.setAttribute('aria-pressed',en?'true':'false');
}
document.getElementById('globalLang').addEventListener('click',function(){
  setLang(root.dataset.lang==='en'?'cn':'en');
});
document.querySelectorAll('.title-toggle').forEach(function(btn){
  btn.addEventListener('click',function(){
    var h=btn.closest('.story-head').querySelector('h3');
    var toEn=btn.getAttribute('aria-pressed')!=='true';
    h.textContent=toEn?h.dataset.titleEn:h.dataset.titleZh;
    btn.setAttribute('aria-pressed',toEn?'true':'false');
  });
});
var q=document.getElementById('search'),rc=document.getElementById('resultCount'),pf='all';
function apply(){
  var kw=q.value.trim().toLowerCase(),n=0;
  document.querySelectorAll('.story').forEach(function(st){
    var okP=(pf==='all'||st.dataset.priority===pf);
    var okK=!kw||(st.dataset.search||'').toLowerCase().indexOf(kw)>-1;
    var show=okP&&okK;st.hidden=!show;if(show)n++;
  });
  document.querySelectorAll('.paper-section').forEach(function(sec){
    sec.hidden=!sec.querySelector('.story:not([hidden])');
  });
  rc.textContent=(kw||pf!=='all')?('\\u5171 '+n+' \\u6761'):'';
}
q.addEventListener('input',apply);
document.querySelectorAll('.priority-filters button').forEach(function(b){
  b.addEventListener('click',function(){
    pf=b.dataset.priority;
    document.querySelectorAll('.priority-filters button').forEach(function(x){x.setAttribute('aria-pressed',x===b?'true':'false');});
    apply();
  });
});
var toc=document.getElementById('toc'),tb=document.getElementById('tocButton');
tb.addEventListener('click',function(){
  var open=toc.classList.toggle('open');tb.setAttribute('aria-expanded',open?'true':'false');
});
toc.querySelectorAll('a').forEach(function(a){
  a.addEventListener('click',function(){toc.classList.remove('open');tb.setAttribute('aria-expanded','false');});
});
var bar=document.getElementById('progressBar');
function prog(){
  var h=document.documentElement,max=h.scrollHeight-h.clientHeight;
  bar.style.width=(max>0?(h.scrollTop/max*100):0)+'%';
}
document.addEventListener('scroll',prog,{passive:true});prog();
})();"""

page = ('<!DOCTYPE html>\n<html lang="zh-CN" data-lang="cn">\n<head>\n<meta charset="utf-8">\n'
 '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
 '<title>WSJ 深读 · 2026年10月12日（周一）</title>\n<style>\n' + css + EXTRA_CSS + '\n</style>\n</head>\n<body>\n'
 '<a class="skip-link" href="#main-content">跳到正文</a>\n'
 '<div aria-hidden="true" class="progress"><i id="progressBar"></i></div>\n'
 '<div class="frame">\n'
 '<header class="cover">\n<div><p class="edition">周一版 · 逐版深读</p>'
 '<h1><span class="cover-weekend">星期一</span><span class="cover-date">2026年10月12日</span></h1>'
 '<p class="deck">逐版文章摘要。跨页内容合为一篇。新闻、评论、生活版与数据附录分区编排。</p></div>\n'
 '<aside class="issue-data"><dl><dt>报纸</dt><dd>《华尔街日报》</dd><dt>卷号</dt><dd>CCLXXXVIII</dd>'
 '<dt>期号</dt><dd>87</dd><dt>覆盖版块</dt><dd>13个版块</dd>'
 '<dt>精读条目</dt><dd>' + str(n_articles) + '篇文章 · ' + str(n_data) + '组数据</dd></dl></aside>\n</header>\n'
 '<section aria-label="阅读说明" class="reader-note">\n'
 '<div><b>01 · 阅读顺序</b><p>新闻主线在前，个人生活与艺术评论前置。汇率、股票和大宗商品等原始数据集中在文末附录。</p></div>\n'
 '<div><b>02 · 方法</b><p>本页为逐版摘要。先列事实，再说明报道为何重要。</p></div>\n'
 '<div><b>03 · 语言</b><p>中文正文采用机器辅助翻译，并按"短句、一句一事实"整理。点击右上角可切换全英文。</p></div>\n'
 '</section>\n'
 '<section aria-label="阅读优先级" class="priority-guide">\n'
 '<div><h2>优先级决定阅读顺序，不决定是否收录。</h2><p>' + str(n_articles) + '篇文章与' + str(n_data) + '组行情数据均纳入目录。P1条目另附多维深层上下文，默认折叠。</p></div>\n'
 '<div><b class="p1">P1 · 必读</b><p>影响政策、市场或重大制度变化。上下文补充时间线、机制、术语和争议焦点。</p></div>\n'
 '<div><b>P2 · 重点</b><p>补全当期主线，或提供重要行业与观点信息。</p></div>\n'
 '<div><b>P3 · 延伸</b><p>数据、文化、生活和书评。按兴趣继续深读。</p></div>\n'
 '</section>\n'
 '<div class="toolbar">\n'
 '<button class="toc-button" id="tocButton" type="button" aria-controls="toc" aria-expanded="false">目录</button>\n'
 '<label class="search"><svg aria-hidden="true" viewbox="0 0 24 24"><circle cx="11" cy="11" fill="none" r="7" stroke="currentColor" stroke-width="2"></circle><path d="m16 16 5 5" fill="none" stroke="currentColor" stroke-width="2"></path></svg><input aria-label="搜索本期深读" id="search" placeholder="搜索人物、公司、主题或数字" type="search"></label>\n'
 '<div aria-label="按优先级筛选" class="priority-filters" role="group"><button aria-pressed="true" data-priority="all" type="button">全部</button><button aria-pressed="false" data-priority="1" type="button">P1 必读</button><button aria-pressed="false" data-priority="2" type="button">P2 重点</button><button aria-pressed="false" data-priority="3" type="button">P3 延伸</button></div>\n'
 '<button class="global-lang-toggle" id="globalLang" type="button" aria-pressed="false">EN · 全部英文</button>\n'
 '<span class="result-count" id="resultCount"></span>\n'
 '</div>\n'
 '<div class="layout">\n'
 '<aside class="toc" id="toc"><h2>本期目录</h2><nav>' + ''.join(toc_links) + '</nav></aside>\n'
 '<main class="content" id="main-content">\n' + ''.join(sections_html) + '\n</main>\n</div>\n'
 '<footer class="colophon">本页为机器辅助翻译的逐期摘要，中文正文译自 2026 年 10 月 12 日（周一）版《华尔街日报》原文，仅供个人阅读参考。数据表为原文摘录。</footer>\n'
 '</div>\n<script>\n' + JS + '\n</script>\n</body></html>\n')

open(OUT, 'w').write(page)
print('written', OUT, len(page), 'chars')
