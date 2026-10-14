#!/usr/bin/env python3
"""R3.1 shell: v7 base + R3 vermilion system + new type system + adaptive."""
import re, sys

BASE = '/home/hatch/workspace/wsj-deep-read/2026-10-12'
v7 = open(f'{BASE}/wsj-2026-10-12-deepread-v7.html').read()
articles = open(f'{BASE}/cases/articles-r3-1.html').read()
base_css = re.search(r'<style>(.*?)</style>', v7, re.S).group(1)

fonts_link = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
 '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
 '<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@600;700;900'
 '&family=Noto+Sans+SC:wght@400;500;700;900'
 '&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400'
 '&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">')

r31_css = '''
/* ============ R3.1: type system + vermilion editorial + adaptive ============ */
:root{
  --bg:#ece5d3; --paper:#faf6ec;
  --ink:#211d15; --ink-2:#57503f; --ink-3:#948a73;
  --line:#211d15; --line-2:#d9d0b8;
  --verm:#cf421b; --verm-soft:#e88a6d;
  --petrol:#14616a; --petrol-soft:#7fb3b8;
  --serif-d:"Noto Serif SC","Songti SC","STSong",serif;
  --sans-b:"Noto Sans SC","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  --serif-e:"Newsreader",Georgia,serif;
  --sans-e:"Inter",-apple-system,"Segoe UI",sans-serif;
}
/* page chrome */
.page{max-width:1280px;margin:0 auto;padding:0 24px}
.r3-top{border-bottom:3px solid var(--ink);padding:26px 0 18px;margin-bottom:8px}
.r3-top .brand{font:700 11px/1.6 var(--mono);letter-spacing:.22em;color:var(--ink-3)}
.r3-top h1{font:900 clamp(26px,3.4vw,36px)/1.2 var(--serif-d);margin:8px 0 6px;letter-spacing:0}
.r3-top .sub{font:400 13px/1.6 var(--sans-b);color:var(--ink-2)}
.r3-toolbar{display:flex;align-items:center;gap:14px;padding:12px 0;border-bottom:1px solid var(--line-2);margin-bottom:26px}
.global-lang-toggle{font:700 12px/1 var(--mono);letter-spacing:.1em;border:1.5px solid var(--ink);background:var(--paper);color:var(--ink);padding:8px 14px;cursor:pointer}
.proto-note{font:400 12px/1.6 var(--mono);color:var(--ink-2);letter-spacing:.06em}
.colophon{font:400 12px/1.7 var(--mono);color:var(--ink-3);border-top:1px solid var(--line-2);margin-top:34px;padding:16px 0 30px;letter-spacing:.04em}
/* story frame */
.story{background:var(--paper);border:var(--bw) solid var(--line);padding:30px 34px;margin:26px auto;max-width:1040px}
.story-body{max-width:660px;margin:14px auto 0}
/* type: sans body, serif display */
.story-body p.b-cn{font:400 16.5px/1.95 var(--sans-b);margin:0 0 1em;color:var(--ink)}
.story-body p.b-en{font:400 16.5px/1.72 var(--sans-e);margin:0 0 1em;color:var(--ink)}
article.dir-a[data-priority="1"] h3{font:900 clamp(30px,4vw,42px)/1.28 var(--serif-d);letter-spacing:0}
article.dir-a[data-priority="2"] h3{font:900 clamp(24px,3vw,30px)/1.3 var(--serif-d)}
.dek-cn{font:400 15px/1.8 var(--sans-b);color:var(--ink-2)}
.dek-en{font:400 15px/1.7 var(--sans-e);color:var(--ink-2)}
.b-cn.b-lede::first-letter{font:700 3.1em/1 var(--serif-d);float:left;margin:6px 10px 0 0}
.beat{margin:0 0 26px}.beat:last-child{margin-bottom:0}
.num{font-weight:700;font-variant-numeric:tabular-nums}
.num.hot{color:var(--verm)}
/* figures */
.fig{margin:30px auto;max-width:660px}
.fig img{display:block;width:100%;height:auto;background:#fff}
.fig figcaption{font:400 12.5px/1.7 var(--sans-b);color:var(--ink-2);border-left:3px solid var(--verm);padding:2px 0 2px 12px;margin-top:10px}
.fig-chart{max-width:520px}
.fig-tesla{max-width:300px}
/* pullquote: serif display, vermilion mark, breakout on desktop */
.pullquote{margin:34px 0}
.pq-text{font:600 22px/1.6 var(--serif-d);letter-spacing:.005em}
.pq-text .k-en{font-family:var(--serif-e)}
.dir-a .pq-text::before{content:"\\201C";display:block;font:700 56px/1 var(--serif-d);color:var(--verm);margin-bottom:12px}
.pq-attr{font:600 12px/1.6 var(--mono);letter-spacing:.08em;color:var(--ink-3);margin-top:12px}
/* components (vermilion system) */
.cmp-label{font:600 11px/1.6 var(--mono);letter-spacing:.14em;color:var(--ink-3);margin:26px 0 12px;padding-top:12px;border-top:1px solid var(--line-2)}
.stat-strip{display:grid;grid-template-columns:1fr 1fr;gap:22px 28px;margin:8px 0;padding:20px 0;border-top:3px solid var(--ink);border-bottom:1px solid var(--line-2)}
.stat{min-width:0}
.stat .k{font:600 11px/1.5 var(--mono);letter-spacing:.1em;color:var(--ink-3);margin-bottom:8px}
.stat .v{font:600 34px/1.15 var(--serif-d);letter-spacing:0;font-variant-numeric:tabular-nums}
.stat .v.long{font-size:21px;white-space:nowrap}
.stat .v .k-en{font-family:var(--serif-e)}
.stat .v.hot{color:var(--verm)}
.stat .d{font:400 13px/1.6 var(--sans-b);color:var(--ink-2);margin-top:6px}
.timeline{margin:6px 0 8px}
.tl-item{display:grid;grid-template-columns:64px 20px 1fr;gap:0 10px;padding:9px 0;position:relative}
.tl-time{font:600 12px/1.75 var(--mono);text-align:right;letter-spacing:.04em;color:var(--petrol)}
.tl-rail{position:relative}
.tl-rail::before{content:"";position:absolute;left:9px;top:26px;bottom:-10px;width:1.5px;background:var(--ink)}
.tl-item:last-child .tl-rail::before{display:none}
.tl-dot{position:absolute;left:5px;top:7px;width:9px;height:9px;background:var(--verm)}
.tl-body{font:400 14.5px/1.7 var(--sans-b);color:var(--ink)}
.claimev{display:grid;grid-template-columns:1fr 1fr;gap:0;margin:8px 0;border:var(--bw) solid var(--ink)}
.ce-block{padding:18px 20px}
.ce-claim{background:var(--paper)}
.ce-ev{background:#fff;border-left:1px solid var(--line-2)}
.ce-tag{font:700 11px/1.6 var(--mono);letter-spacing:.14em;margin-bottom:10px;color:var(--ink-3)}
.ce-ev .ce-tag{color:var(--verm)}
.ce-text{font:600 16px/1.65 var(--serif-d)}
.ce-text .k-en{font-family:var(--serif-e)}
.ce-src{font:400 12px/1.6 var(--mono);color:var(--ink-3);margin-top:10px}
.bargraph{margin:8px 0;padding:18px 0;border-top:var(--bw) solid var(--ink);border-bottom:1px solid var(--line-2)}
.bar-row{display:grid;grid-template-columns:150px 1fr 76px;gap:14px;align-items:center;padding:9px 0}
.bar-label{font:600 12px/1.5 var(--mono);color:var(--ink-2)}
.bar-track{height:16px;background:var(--line-2);position:relative}
.bar-fill{height:100%}
.bar-fill.verm{background:var(--verm)}
.bar-fill.verm2{background:var(--verm-soft)}
.bar-val{font:700 15px/1.4 var(--mono);font-variant-numeric:tabular-nums;text-align:right;color:var(--verm)}
.bar-note{font:400 12px/1.6 var(--sans-b);color:var(--ink-3);margin-top:10px}
.compare-duel{margin:8px 0}
.compare-duel .crow{display:grid;grid-template-columns:1fr 1fr;gap:28px;padding:16px 0;border-top:1px solid var(--line-2)}
.compare-duel .crow.chead{padding:0 0 10px;border-top:0}
.compare-duel .crow.chead + .crow{border-top:var(--bw) solid var(--ink)}
.compare-duel .crow:last-child{border-bottom:var(--bw) solid var(--ink)}
.compare-duel .ccell{min-width:0}
.compare-duel .cwho{font:600 11px/1.6 var(--mono);letter-spacing:.12em;color:var(--ink-3)}
.compare-duel .cL .cwho{color:var(--verm)}
.compare-duel .cR .cwho{color:var(--petrol)}
.compare-duel .cwhat{font:400 15px/1.7 var(--sans-b)}
/* desktop: editorial composition with breakout */
@media(min-width:1024px){
  .fig-hero{max-width:920px;margin:30px -130px}
  .fig-chart{max-width:560px}
  .dir-a .pullquote{margin:36px -60px;padding:0 60px}
  .stat-strip{gap:24px 40px}
}
/* mobile: single column, protected measure */
@media(max-width:640px){
  .page{padding:0 14px}
  .story{padding:20px 18px}
  .story-body p.b-cn{font-size:16px;line-height:1.9}
  .pq-text{font-size:19px}
  .fig{margin:24px -18px;max-width:none}
  .fig figcaption{margin:10px 18px 0}
  .compare-duel .crow{grid-template-columns:1fr;gap:12px}
  .claimev{grid-template-columns:1fr}
  .ce-ev{border-left:0;border-top:1px solid var(--line-2)}
  .stat .v{font-size:27px}
  .tl-item{grid-template-columns:52px 20px 1fr}
  .bar-row{grid-template-columns:104px 1fr 64px}
}
'''

js = '''
<script>
(function(){
var root=document.documentElement;
function setLang(l){
  root.dataset.lang=l;
  var en=l==='en';
  document.querySelectorAll('.story h3').forEach(function(h){
    h.textContent=en?h.dataset.titleEn:h.dataset.titleZh;});
  document.querySelectorAll('.k-cn,.b-cn,.dek-cn').forEach(function(e){e.hidden=en;});
  document.querySelectorAll('.k-en,.b-en,.dek-en').forEach(function(e){e.hidden=!en;});
  var g=document.getElementById('globalLang');
  g.textContent=en?'\\u4e2d\\u6587':'EN';
  g.setAttribute('aria-pressed',en?'true':'false');
}
document.getElementById('globalLang').addEventListener('click',function(){
  setLang(root.dataset.lang==='en'?'cn':'en');});
})();
</script>
'''

art_map = {}
for mid in ['r3E1-005','r3E3-002']:
    mm = re.search(rf'<article class="story[^"]*" id="{mid}".*?</article>', articles, re.S)
    art_map[mid] = mm.group(0) if mm else f'<!-- missing {mid} -->'

body = ['<div class="page">',
 '<div class="r3-top"><div class="brand">WSJ 深读 · DEEP READ</div><h1>R3.1 · 编辑体验</h1>'
 '<div class="sub">方向 A（朱砂印刷风）· 新字体系统 · 真实视觉资产 · 自适应排版 · 内容逐字取自 2026-10-12 深读定稿</div></div>',
 '<div class="r3-toolbar"><button class="global-lang-toggle" id="globalLang" type="button" aria-pressed="false">EN</button>'
 '<span class="proto-note">R3.1 样稿 · 沙特长文 + 电动车报道</span></div>']
for mid in ['r3E1-005','r3E3-002']:
    body.append(art_map[mid])
body.append('<footer class="colophon">R3.1 样稿。图片：电动车充电站照片（Angus Mordant/彭博新闻）与月度充电桩图表（数据源：能源部）均取自《华尔街日报》2026年10月12日 B1 版原报；沙特报道在原报 A1 版无配图，未采用图片。12%→6% 柱状图为编辑绘制（数据来自正文第 9 段）。</footer>')
body.append('</div>')

html_doc = f'''<!DOCTYPE html>
<html lang="zh-CN" data-lang="cn">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>WSJ 深读 R3.1 · 编辑体验</title>
{fonts_link}
<style>{base_css}{r31_css}</style>
</head>
<body>
{chr(10).join(body)}
{js}
</body>
</html>'''

open(f'{BASE}/cases/wsj-r3-1.html', 'w').write(html_doc)
print('r3.1 shell bytes:', len(html_doc))
