#!/usr/bin/env python3
"""v3: restyle on answer-me-with-html paper-theme design language.
Content verbatim from final.json; HTML structure same as v2; CSS rewritten."""
import json, re, html

SRC = '/home/hatch/workspace/wsj-deep-read/2026-10-12/final.json'
OUT = '/home/hatch/workspace/wsj-deep-read/2026-10-12/wsj-2026-10-12-deepread-v5.html'

def esc(s):
    return html.escape(s or '', quote=True)

fj = json.load(open(SRC))

SECTIONS = [
    ('News', '新闻', 'NEWS'), ('World News', '国际新闻', 'WORLD NEWS'),
    ('U.S. News', '美国新闻', 'U.S. NEWS'), ('Technology', '科技', 'TECHNOLOGY'),
    ('Personal Journal', '个人生活', 'PERSONAL JOURNAL'), ('Sports', '体育', 'SPORTS'),
    ('Arts in Review', '艺术评论', 'ARTS IN REVIEW'), ('Opinion', '观点', 'OPINION'),
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
    parts = ['<p class="%s-cn">%s</p>' % (cls, esc(p)) for p in paras(cn)]
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
    return '<div class="table-wrap"><p class="tbl-cap">%s</p>%s</div>' % (esc(caption), '\n'.join(tbls))

def story_html(e):
    pid = esc(e['id'])
    pri = e.get('priority', 'P3')
    pnum = PRINUM.get(pri, '3')
    page = esc(e.get('page') or '')
    tcn = e.get('title_cn') or e.get('title') or ''
    ten = e.get('title') or ''
    search = esc((tcn + ' ' + ten + ' ' + (e.get('body_cn') or '')[:300]).replace("'", ''))
    h = ['<article class="story" data-priority="%s" data-search="%s" id="s-%s">' % (pnum, search, pid)]
    kicker = '<div class="kicker"><span class="k-left"><span class="k-page">%s</span>' % page
    kicker += '<span class="k-pri">%s</span></span>' % PRILABEL.get(pri, 'P3')
    if e.get('byline'):
        kicker += '<span class="k-byline">%s</span>' % esc(e['byline'])
    kicker += '</div>'
    h.append(kicker)
    h.append('<header class="story-head">'
             '<h3 data-title-zh="%s" data-title-en="%s">%s</h3>'
             '<button class="title-toggle" type="button" aria-pressed="false">EN</button></header>'
             % (esc(tcn), esc(ten), esc(tcn)))
    if e.get('dek_cn'):
        h.append('<p class="dek-cn">%s</p>' % esc(e['dek_cn']))
        if e.get('dek'):
            h.append('<p class="dek-en" hidden>%s</p>' % esc(e['dek']))
    h.append('<div class="story-body">')
    if e.get('type') == 'data_table':
        en_text = e.get('body_en') or ''
        if en_text.strip().lower().startswith('chart embedded'):
            h.append('<div class="chart-note"><p class="b-cn">以下为该图表的文字描述，数据为原文摘录。</p>'
                     '<p class="b-en" hidden>Chart description; data excerpted from the original.</p>'
                     '<pre class="raw">%s</pre></div>' % esc(en_text))
        else:
            h.append(table_html(en_text, '%s - %s' % (tcn, page)))
    else:
        h.append(body_html(e.get('body_cn'), e.get('body_en')))
    h.append('</div>')
    if e.get('context_cn'):
        attr = esc(e.get('context_attr') or '')
        s2 = '<span class="context-source">%s</span>' % attr if attr else ''
        h.append('<details class="context"><summary>背景资料 - CONTEXT%s</summary>'
                 '<div class="context-body"><p class="ctx-cn">%s</p></div></details>' % (s2, esc(e['context_cn'])))
    h.append('</article>')
    return '\n'.join(h)

CSS = """
:root{
  --bg:#f6f6f3; --paper:#ffffff;
  --ink:#16181d; --ink-2:#4b5260; --ink-3:#8b929e;
  --line:#1d2026; --line-2:#d6dae1; --fill:#f3f5f8;
  --bw:1.5px;
  --accent:#1d5fbf; --accent-bg:#e4ecf8;
  --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,"Songti SC","STSong","Noto Serif CJK SC","Source Han Serif SC",serif;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  --mono:ui-monospace,SFMono-Regular,"JetBrains Mono",Menlo,Consolas,monospace;
}
*{box-sizing:border-box;border-radius:0 !important}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:16.5px;line-height:1.7;-webkit-font-smoothing:antialiased}
.skip-link{position:absolute;left:-9999px}
.progress{position:fixed;top:0;left:0;right:0;height:3px;z-index:200;background:transparent}
.progress i{display:block;height:100%;width:0;background:var(--ink)}
.frame{max-width:1180px;margin:0 auto;padding:0 28px 90px}
/* masthead */
.cover{background:var(--ink);color:#fff;margin:0 -28px;padding:52px 40px 40px}
.edition{font:700 11px/1 var(--mono);letter-spacing:.22em;color:#fff;opacity:.65;margin:0 0 20px;text-transform:uppercase}
.cover h1{font-family:var(--serif);font-weight:700;font-size:clamp(38px,5.4vw,64px);line-height:1.12;letter-spacing:-.01em;margin:0;max-width:900px}
.cover-weekend,.cover-date{display:block}
.cover-date{margin-top:.12em}
.deck{margin:18px 0 0;max-width:62ch;font-size:15px;line-height:1.65;color:#d6dae1}
.issue-data{margin-top:28px;border-top:var(--bw) solid #fff;padding-top:16px;max-width:560px}
.issue-data dl{display:grid;grid-template-columns:1fr auto;gap:7px 24px;margin:0;font:12.5px/1.5 var(--mono)}
.issue-data dt{color:#8b929e}.issue-data dd{margin:0;text-align:right;color:#fff}
/* reader note + priority guide */
.reader-note{display:grid;grid-template-columns:repeat(3,1fr);gap:0;margin:34px 0 0;background:var(--paper);border:var(--bw) solid var(--line)}
.reader-note>div{padding:18px 20px;border-left:var(--bw) solid var(--line)}
.reader-note>div:first-child{border-left:0}
.reader-note b{font:700 11px/1.4 var(--mono);letter-spacing:.12em;display:block;margin-bottom:8px}
.reader-note p{margin:0;font-size:13.5px;line-height:1.65;color:var(--ink-2)}
.priority-guide{display:grid;grid-template-columns:1.4fr 1fr 1fr 1fr;gap:0;margin:22px 0 0;background:var(--paper);border:var(--bw) solid var(--line)}
.priority-guide>div{padding:18px 20px;border-left:var(--bw) solid var(--line)}
.priority-guide>div:first-child{border-left:0}
.priority-guide h2{font-family:var(--serif);font-size:19px;line-height:1.35;margin:0 0 8px;letter-spacing:-.01em}
.priority-guide p{margin:0;font-size:13px;line-height:1.6;color:var(--ink-2)}
.priority-guide b{font:700 11px/1.4 var(--mono);letter-spacing:.1em;display:block;margin-bottom:8px}
.priority-guide b.p1{background:var(--ink);color:#fff;display:inline-block;padding:4px 10px}
.priority-guide div:nth-child(3) b{color:var(--accent)}
.priority-guide div:nth-child(4) b{color:var(--ink-3)}
/* toolbar */
.toolbar{position:sticky;top:0;z-index:100;display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:12px 0;background:var(--bg);border-bottom:var(--bw) solid var(--line)}
.toc-button,.global-lang-toggle,.priority-filters button{font:700 12px/1 var(--mono);letter-spacing:.06em;background:var(--paper);border:var(--bw) solid var(--line);color:var(--ink);padding:10px 14px;cursor:pointer}
.toc-button:hover,.global-lang-toggle:hover,.priority-filters button:hover{background:var(--ink);color:#fff}
.priority-filters{display:flex;gap:0}
.priority-filters button{border-left:0}
.priority-filters button:first-child{border-left:var(--bw) solid var(--line)}
.priority-filters button[aria-pressed="true"]{background:var(--ink);color:#fff}
.search{display:flex;align-items:center;gap:8px;background:var(--paper);border:var(--bw) solid var(--line);padding:8px 12px;flex:1;min-width:200px}
.search svg{width:16px;height:16px;flex:none}
.search input{border:0;outline:0;background:transparent;font:14px var(--sans);width:100%;color:var(--ink)}
.result-count{font:700 12px var(--mono);color:var(--ink-3);margin-left:auto}
/* layout */
.layout{display:grid;grid-template-columns:230px minmax(0,1fr);gap:48px;margin-top:8px}
.toc{position:sticky;top:76px;align-self:start;max-height:calc(100vh - 96px);overflow:auto;padding:24px 0}
.toc h2{font:700 11px/1.2 var(--mono);letter-spacing:.18em;margin:0 0 12px;color:var(--ink-3)}
.toc nav{display:flex;flex-direction:column}
.toc a{display:flex;gap:10px;align-items:baseline;color:var(--ink-2);text-decoration:none;font-size:13.5px;padding:7px 0;border-bottom:1px solid var(--line-2)}
.toc a strong{font:700 11px var(--mono);color:var(--ink-3)}
.toc a:hover{color:var(--ink)}.toc a:hover strong{color:var(--accent)}
.content{min-width:0}
/* sections */
.paper-section{padding:44px 0 6px}
.section-head{display:grid;grid-template-columns:64px 1fr;gap:20px;align-items:end;padding-bottom:16px;border-bottom:3px solid var(--line);margin-bottom:6px}
.section-no{font:700 34px/1 var(--mono);color:var(--ink)}
.section-head h2{font-family:var(--serif);font-weight:700;font-size:clamp(28px,3.6vw,42px);line-height:1.1;letter-spacing:-.01em;margin:0}
.section-head p{font:11px/1.4 var(--mono);letter-spacing:.14em;color:var(--ink-3);margin:10px 0 0;text-transform:uppercase}
/* stories */
.story{background:var(--paper);border:var(--bw) solid var(--line);padding:26px 30px;margin:22px 0;max-width:860px}
.story[hidden],.paper-section[hidden]{display:none}
.story-head{display:grid;grid-template-columns:1fr auto;gap:18px;align-items:start}

.story h3{font-family:var(--serif);font-weight:700;letter-spacing:-.01em;margin:0;line-height:1.22}.story[data-priority="1"] h3{font-size:clamp(26px,3vw,34px)}.story[data-priority="2"] h3{font-size:23px}.story[data-priority="3"] h3{font-size:20px}
.title-toggle{font:700 10px/1 var(--mono);letter-spacing:.08em;color:var(--ink-2);background:transparent;border:var(--bw) solid var(--line-2);padding:8px 10px;cursor:pointer;margin-top:6px}
.title-toggle:hover{border-color:var(--ink);color:var(--ink)}
.kicker{display:flex;justify-content:space-between;align-items:center;gap:16px;font:700 11px/1.5 var(--mono);letter-spacing:.1em;margin:0 0 14px}.k-left{display:flex;align-items:center;gap:10px}.k-page{color:var(--ink)}
.story[data-priority="1"] .k-pri{background:var(--ink);color:#fff;padding:4px 9px}
.story[data-priority="2"] .k-pri{color:var(--accent);border:var(--bw) solid var(--accent);padding:3px 8px}
.story[data-priority="3"] .k-pri{color:var(--ink-3);border:1px solid var(--line-2);padding:3px 8px}.k-byline{color:var(--ink-3);font-weight:400;letter-spacing:.04em;text-align:right}

.dek-cn{font-family:var(--sans);font-weight:400;font-size:15.5px;line-height:1.7;color:var(--ink-2);margin:12px 0 0;max-width:62ch}
.dek-en{font-size:13.5px;color:var(--ink-3);margin:0 0 4px}
.story-body{margin-top:14px;max-width:68ch}
.story-body p{margin:0 0 12px;font-size:16px;line-height:1.75}
.story-body p:last-child{margin-bottom:0}
.story-body strong{font-weight:700}
/* context */
details.context{margin-top:20px;border:1px solid var(--line-2);background:transparent}
details.context summary{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:11px 14px;cursor:pointer;list-style:none;font:700 10.5px/1.4 var(--mono);letter-spacing:.12em;color:var(--ink-2)}
details.context summary::-webkit-details-marker{display:none}
details.context summary::after{content:"+";font-size:16px}
details.context[open] summary::after{content:"–"}
.context-source{color:var(--ink-3);letter-spacing:.04em}
.context-body{padding:2px 14px 16px;border-top:1px solid var(--line-2)}
.context-body p{font-size:14px;line-height:1.7;color:var(--ink-2);margin:12px 0 0}
/* data tables */
.table-wrap{margin:16px 0 6px;border:var(--bw) solid var(--line);overflow-x:auto}
.tbl-cap{font:700 12px/1.5 var(--mono);letter-spacing:.04em;padding:12px 14px;margin:0;border-bottom:var(--bw) solid var(--line);background:var(--paper)}
.table-wrap table{border-collapse:collapse;width:100%;font-size:13px}
.table-wrap th{background:var(--ink);color:#fff;font:700 11px/1.4 var(--mono);letter-spacing:.04em;text-align:left;padding:9px 12px;border:1px solid var(--line);white-space:nowrap}
.table-wrap td{border:1px solid var(--line-2);padding:8px 12px;text-align:left;vertical-align:top}
.table-wrap tbody tr:nth-child(even) td{background:var(--fill)}
.chart-note .raw{font:12.5px/1.65 var(--mono);white-space:pre-wrap;background:var(--fill);border:var(--bw) solid var(--line);padding:16px;overflow-x:auto;margin:12px 0 0}
/* footer */
footer.colophon{margin-top:60px;border-top:3px solid var(--line);padding-top:18px;color:var(--ink-2);font-size:12.5px;line-height:1.7;max-width:860px}
/* responsive */
@media(max-width:960px){
  .layout{grid-template-columns:1fr}
  .toc{position:fixed;top:0;left:0;bottom:0;width:280px;background:var(--paper);border-right:var(--bw) solid var(--line);z-index:300;padding:24px 20px;transform:translateX(-105%);transition:transform .25s}
  .toc.open{transform:none}
  .reader-note,.priority-guide{grid-template-columns:1fr}
  .reader-note>div,.priority-guide>div{border-left:0;border-top:var(--bw) solid var(--line)}
  .reader-note>div:first-child,.priority-guide>div:first-child{border-top:0}
  .cover{margin:0 -20px;padding:40px 24px 32px}
  .frame{padding:0 20px 70px}
  .story{padding:20px}
}
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
  g.textContent=en?'\\u4e2d\\u6587':'EN';
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

page = ('<!DOCTYPE html>\n<html lang="zh-CN" data-lang="cn">\n<head>\n<meta charset="utf-8">\n'
 '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
 '<title>WSJ 深读 · 2026年10月12日（周一）</title>\n<style>\n' + CSS + '\n</style>\n</head>\n<body>\n'
 '<a class="skip-link" href="#main-content">跳到正文</a>\n'
 '<div aria-hidden="true" class="progress"><i id="progressBar"></i></div>\n'
 '<div class="frame">\n'
 '<header class="cover">\n<p class="edition">The Wall Street Journal · Deep Read · Monday Edition</p>'
 '<h1><span class="cover-weekend">星期一</span><span class="cover-date">2026年10月12日</span></h1>'
 '<p class="deck">逐版文章摘要。跨页内容合为一篇。新闻、评论、生活版与数据附录分区编排。</p>\n'
 '<aside class="issue-data"><dl><dt>报纸</dt><dd>《华尔街日报》</dd><dt>卷号</dt><dd>CCLXXXVIII</dd>'
 '<dt>期号</dt><dd>87</dd><dt>覆盖版块</dt><dd>13个版块</dd>'
 '<dt>精读条目</dt><dd>' + str(n_articles) + '篇文章 · ' + str(n_data) + '组数据</dd></dl></aside>\n</header>\n'
 '<section aria-label="阅读说明" class="reader-note">\n'
 '<div><b>01 / 阅读顺序</b><p>新闻主线在前，个人生活与艺术评论前置。汇率、股票和大宗商品等原始数据集中在文末附录。</p></div>\n'
 '<div><b>02 / 方法</b><p>本页为逐版摘要。先列事实，再说明报道为何重要。</p></div>\n'
 '<div><b>03 / 语言</b><p>中文正文采用机器辅助翻译，并按"短句、一句一事实"整理。点击右上角可切换全英文。</p></div>\n'
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
 '<button class="global-lang-toggle" id="globalLang" type="button" aria-pressed="false">EN</button>\n'
 '<span class="result-count" id="resultCount"></span>\n'
 '</div>\n'
 '<div class="layout">\n'
 '<aside class="toc" id="toc"><h2>本期目录</h2><nav>' + ''.join(toc_links) + '</nav></aside>\n'
 '<main class="content" id="main-content">\n' + ''.join(sections_html) + '\n</main>\n</div>\n'
 '<footer class="colophon">本页为机器辅助翻译的逐期摘要，中文正文译自 2026 年 10 月 12 日（周一）版《华尔街日报》原文，仅供个人阅读参考。数据表为原文摘录。</footer>\n'
 '</div>\n<script>\n' + JS + '\n</script>\n</body></html>\n')

open(OUT, 'w').write(page)
print('written', OUT, len(page), 'chars')
