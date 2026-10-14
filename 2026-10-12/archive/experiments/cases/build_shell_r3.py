#!/usr/bin/env python3
"""R3 shell: v7 base CSS + R3 editorial palette + direction A/B systems."""
import re, sys

BASE = '/home/hatch/workspace/wsj-deep-read/2026-10-12'
v7 = open(f'{BASE}/wsj-2026-10-12-deepread-v7.html').read()
dirn = sys.argv[2] if len(sys.argv) > 2 else 'a'
articles = open(f'{BASE}/cases/articles-r3{dirn}.html').read()
base_css = re.search(r'<style>(.*?)</style>', v7, re.S).group(1)

palette = '''
:root{
  --bg:#ece5d3;
  --paper:#faf6ec;
  --ink:#211d15;
  --ink-2:#57503f;
  --ink-3:#948a73;
  --line:#211d15;
  --line-2:#d9d0b8;
  --verm:#cf421b; --verm-soft:#e88a6d;
  --petrol:#14616a; --petrol-soft:#7fb3b8;
}
'''

r3_shared = '''
/* ---- R3 shared: R2 typography assets ---- */
.beat{margin:0 0 26px}
.beat:last-child{margin-bottom:0}
.b-cn.b-lede::first-letter{font:700 3.1em/1 var(--serif);float:left;margin:6px 10px 0 0}
.num{font-weight:600;font-variant-numeric:tabular-nums}
.num.hot{color:var(--verm)}
.cmp-label{font:600 11px/1.6 var(--mono);letter-spacing:.14em;color:var(--ink-3);margin:26px 0 12px;padding-top:12px;border-top:1px solid var(--line-2)}
.photo-cap{font:400 13px/1.7 var(--sans);color:var(--ink-2);border-left:3px solid var(--line-2);padding:2px 0 2px 12px;margin:14px 0}
article.dir-a[data-priority="1"] h3,article.dir-b[data-priority="1"] h3{font-size:clamp(30px,4vw,42px);line-height:1.28;letter-spacing:-.01em}
article.dir-a[data-priority="2"] h3,article.dir-b[data-priority="2"] h3{font-size:clamp(24px,3vw,30px)}
/* stat strip */
.stat-strip{display:grid;grid-template-columns:1fr 1fr;gap:22px 28px;margin:8px 0;padding:20px 0;border-top:3px solid var(--ink);border-bottom:1px solid var(--line-2)}
.stat{min-width:0}
.stat .k{font:600 11px/1.5 var(--mono);letter-spacing:.1em;color:var(--ink-3);margin-bottom:8px}
.stat .v{font:600 34px/1.15 var(--serif);letter-spacing:-.01em;font-variant-numeric:tabular-nums}
.stat .v.long{font-size:22px;letter-spacing:0;white-space:nowrap}
.stat .d{font:400 13px/1.6 var(--sans);color:var(--ink-2);margin-top:6px}
/* timeline */
.timeline{margin:6px 0 8px}
.tl-item{display:grid;grid-template-columns:64px 20px 1fr;gap:0 10px;padding:9px 0;position:relative}
.tl-time{font:600 12px/1.75 var(--mono);text-align:right;letter-spacing:.04em;color:var(--ink-3)}
.tl-rail{position:relative}
.tl-rail::before{content:"";position:absolute;left:9px;top:26px;bottom:-10px;width:1.5px;background:var(--ink)}
.tl-item:last-child .tl-rail::before{display:none}
.tl-dot{position:absolute;left:5px;top:7px;width:9px;height:9px;background:var(--ink)}
.tl-body{font:400 14.5px/1.7 var(--sans);color:var(--ink)}
/* claim vs reality */
.claimev{display:grid;grid-template-columns:1fr 1fr;gap:0;margin:8px 0;border:var(--bw) solid var(--ink)}
.ce-block{padding:18px 20px}
.ce-claim{background:var(--paper)}
.ce-ev{background:#fff;border-left:1px solid var(--line-2)}
.ce-tag{font:700 11px/1.6 var(--mono);letter-spacing:.14em;margin-bottom:10px;color:var(--ink-3)}
.ce-text{font:600 16px/1.65 var(--serif)}
.ce-src{font:400 12px/1.6 var(--mono);color:var(--ink-3);margin-top:10px}
/* bar graphic */
.bargraph{margin:8px 0;padding:18px 0;border-top:var(--bw) solid var(--ink);border-bottom:1px solid var(--line-2)}
.bar-row{display:grid;grid-template-columns:150px 1fr 76px;gap:14px;align-items:center;padding:9px 0}
.bar-label{font:600 12px/1.5 var(--mono);color:var(--ink-2)}
.bar-track{height:16px;background:var(--line-2);position:relative}
.bar-fill{height:100%}
.bar-fill.verm{background:var(--verm)}
.bar-fill.verm2{background:var(--verm-soft)}
.bar-fill.petrol{background:var(--petrol)}
.bar-fill.petrol2{background:var(--petrol-soft)}
.bar-val{font:700 15px/1.4 var(--mono);font-variant-numeric:tabular-nums;text-align:right}
.bar-note{font:400 12px/1.6 var(--sans);color:var(--ink-3);margin-top:10px}
/* compare duel */
.compare-duel{margin:8px 0}
.compare-duel .crow{display:grid;grid-template-columns:1fr 1fr;gap:28px;padding:16px 0;border-top:1px solid var(--line-2)}
.compare-duel .crow.chead{padding:0 0 10px;border-top:0}
.compare-duel .crow.chead + .crow{border-top:var(--bw) solid var(--ink)}
.compare-duel .crow:last-child{border-bottom:var(--bw) solid var(--ink)}
.compare-duel .ccell{min-width:0}
.compare-duel .cwho{font:600 11px/1.6 var(--mono);letter-spacing:.12em;color:var(--ink-3)}
.compare-duel .cwhat{font:400 15px/1.7 var(--sans)}
/* pullquote base */
.pullquote{margin:30px 0}
.pq-text{font:600 21px/1.65 var(--serif);letter-spacing:.005em}
.pq-attr{font:600 12px/1.6 var(--mono);letter-spacing:.08em;color:var(--ink-3);margin-top:12px}
.proto-note{font:400 12px/1.6 var(--mono);color:var(--ink-2);letter-spacing:.06em}
/* R3 page chrome */
.r3-top{border-bottom:3px solid var(--ink);padding:26px 0 18px;margin-bottom:8px}
.r3-top .brand{font:700 11px/1.6 var(--mono);letter-spacing:.22em;color:var(--ink-3)}
.r3-top h1{font:700 clamp(26px,3.4vw,36px)/1.2 var(--serif);margin:8px 0 6px;letter-spacing:-.01em}
.r3-top .sub{font:400 13px/1.6 var(--sans);color:var(--ink-2)}
.r3-toolbar{display:flex;align-items:center;gap:14px;padding:12px 0;border-bottom:1px solid var(--line-2);margin-bottom:26px}
.global-lang-toggle{font:700 12px/1 var(--mono);letter-spacing:.1em;border:1.5px solid var(--ink);background:var(--paper);color:var(--ink);padding:8px 14px;cursor:pointer}
.colophon{font:400 12px/1.7 var(--mono);color:var(--ink-3);border-top:1px solid var(--line-2);margin-top:34px;padding:16px 0 30px;letter-spacing:.04em}
.page{max-width:1180px;margin:0 auto;padding:0 24px}
.story{background:var(--paper);border:var(--bw) solid var(--line);padding:26px 30px;margin:26px 0;max-width:880px}
'''

css_a = '''
/* ============ Direction A: Vermilion Editorial ============ */
.dir-a .pq-text::before{content:"\\201C";display:block;font:700 56px/1 var(--serif);color:var(--verm);margin-bottom:12px}
.dir-a .pullquote{margin:36px -24px;padding:0 24px}
.dir-a .pq-text{font-size:22px}
.dir-a .tl-dot{background:var(--verm)}
.dir-a .tl-time{color:var(--petrol)}
.dir-a .stat .v.hot{color:var(--verm)}
.dir-a .compare-duel .cL .cwho{color:var(--verm)}
.dir-a .compare-duel .cR .cwho{color:var(--petrol)}
.dir-a .ce-ev .ce-tag{color:var(--verm)}
.dir-a .bar-val{color:var(--verm)}
'''

css_b = '''
/* ============ Direction B: Petrol System ============ */
.dir-b .beat3{display:grid;grid-template-columns:104px 1fr;gap:20px;margin:0 0 26px}
.dir-b .beat3:last-child{margin-bottom:0}
.dir-b .mnote{font:600 11px/1.7 var(--mono);letter-spacing:.1em;color:var(--petrol);text-align:right;padding-top:5px}
.dir-b .beat3-body{min-width:0}
.dir-b .pullquote{margin:30px 0;padding:8px 0 8px 24px;border-left:4px solid var(--petrol)}
.dir-b .pq-text{font-size:19px}
.dir-b .tl-dot{background:var(--petrol)}
.dir-b .tl-time{color:var(--petrol)}
.dir-b .cmp-label{color:var(--petrol)}
.dir-b .ce-claim .ce-tag{color:var(--petrol)}
.dir-b .ce-ev .ce-tag{color:var(--verm)}
.dir-b .bar-track{background:repeating-linear-gradient(to right,var(--line-2) 0 1px,transparent 1px 25%)}
.dir-b .bar-val{color:var(--ink)}
.dir-b .compare-duel .cwho{color:var(--petrol)}
.dir-b .stat .v.hot{color:var(--verm)}
@media(max-width:760px){
  .dir-b .beat3{display:block}
  .dir-b .mnote{text-align:left;margin-bottom:8px;padding-top:0}
}
'''

r3_mobile = '''
@media(max-width:640px){
  .compare-duel .crow{grid-template-columns:1fr;gap:12px}
  .claimev{grid-template-columns:1fr}
  .ce-ev{border-left:0;border-top:1px solid var(--line-2)}
  .stat .v{font-size:28px}
  .tl-item{grid-template-columns:52px 20px 1fr}
  .dir-a .pullquote{margin:30px 0;padding:0}
  .bar-row{grid-template-columns:110px 1fr 64px}
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

dir_css = css_a if dirn == 'a' else css_b
dir_name = 'A · 朱砂印刷风 Vermilion Editorial' if dirn == 'a' else 'B · 石油青系统风 Petrol System'

art_map = {}
for mid in ['r3E1-005','r3E3-002']:
    mm = re.search(rf'<article class="story[^"]*" id="{mid}".*?</article>', articles, re.S)
    art_map[mid] = mm.group(0) if mm else f'<!-- missing {mid} -->'

body = ['<div class="page">',
 '<div class="r3-top"><div class="brand">WSJ 深读 · DEEP READ</div><h1>R3 · 编辑设计探索</h1>'
 f'<div class="sub">方向 {dir_name} · 两篇完整文章 · 内容逐字取自 2026-10-12 深读定稿</div></div>',
 '<div class="r3-toolbar"><button class="global-lang-toggle" id="globalLang" type="button" aria-pressed="false">EN</button>'
 f'<span class="proto-note">R3 样稿 · 方向 {dir_name}</span></div>']
for mid in ['r3E1-005','r3E3-002']:
    body.append(art_map[mid])
body.append('<footer class="colophon">R3 样稿：内容逐字取自 2026-10-12 深读定稿（final.json）。信息图形仅使用原文已有数据。</footer>')
body.append('</div>')

html_doc = f'''<!DOCTYPE html>
<html lang="zh-CN" data-lang="cn">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>WSJ 深读 R3 · 方向{dirn.upper()}</title>
<style>{base_css}{palette}{r3_shared}{dir_css}{r3_mobile}</style>
</head>
<body>
{chr(10).join(body)}
{js}
</body>
</html>'''

open(f'{BASE}/cases/wsj-r3-{dirn}.html', 'w').write(html_doc)
print('r3 shell bytes:', len(html_doc), 'dir:', dirn)
