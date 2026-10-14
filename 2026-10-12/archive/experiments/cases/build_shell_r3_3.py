#!/usr/bin/env python3
"""R3.3 shell: v7 base + R3 vermilion system + new type system + adaptive."""
import re, sys

BASE = '/home/hatch/workspace/wsj-deep-read/2026-10-12'
v7 = open(f'{BASE}/wsj-2026-10-12-deepread-v7.html').read()
articles = open(f'{BASE}/cases/articles-r3-5.html').read()
base_css = re.search(r'<style>(.*?)</style>', v7, re.S).group(1)

fonts_link = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
 '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
 '<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@600;700;900'
 '&family=Noto+Sans+SC:wght@400;500;700;900'
 '&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400'
 '&display=swap" rel="stylesheet">')

r31_css = '''
/* ============ R3.3: Vercel guidelines pass ============ */
html{color-scheme:light}
.skip{position:absolute;left:-9999px;top:0;z-index:100;background:var(--ink);color:var(--paper);font:600 13px/1.5 var(--sans-b);padding:10px 18px;text-decoration:none}
.skip:focus-visible{left:12px;top:12px}
.k-pri{white-space:nowrap} /* R3.3: badge 不换行 */
.k-byline{text-transform:uppercase} /* R3.4 oil-ui: byline 全大写统一 */
.stat{display:flex;flex-direction:column} /* R3.4 oil-ui: 数字条底部对齐 */
.stat .d{margin-top:auto;padding-top:6px}
@media(max-width:640px){.k-byline{white-space:nowrap;font-size:10px;letter-spacing:.06em}} /* R3.4 oil-ui: 手机 byline 不折行 */
/* ============ R3.3: type system + vermilion editorial + adaptive ============ */
/* R3.5: 底色定稿为 D2（冷白70/宣纸30，Jerry 2026-10-13 定） */
:root{
  --bg:#eaeae5; --paper:#fdfbf8;
  --ink:#1d1f1f; --ink-2:#4f5353; --ink-3:#5f6462;
  --line:#1d1f1f; --line-2:#dbdad3;
  --verm:#cf421b; --verm-soft:#e88a6d;
  --petrol:#14616a; --petrol-soft:#7fb3b8;
  --serif-d:"Noto Serif SC","Songti SC","STSong",serif;
  --sans-b:"Noto Sans SC","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  --serif-e:"Newsreader",Georgia,serif;
}
/* page chrome */
.page{max-width:1280px;margin:0 auto;padding:0 24px}
.r3-top{border-bottom:3px solid var(--ink);padding:26px 0 18px;margin-bottom:8px}
.r3-top .brand{font:700 11px/1.6 var(--mono);letter-spacing:.22em;color:var(--ink-3)}
.r3-top h1{font:900 clamp(26px,3.4vw,36px)/1.2 var(--serif-d);margin:8px 0 6px;letter-spacing:-0.015em;text-wrap:balance}
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
.story-body p.b-en{font:400 16.5px/1.72 var(--sans-b);margin:0 0 1em;color:var(--ink)}
article.dir-a[data-priority="1"] h2{font:900 clamp(30px,4vw,42px)/1.28 var(--serif-d);letter-spacing:-0.015em;text-wrap:balance}
article.dir-a[data-priority="2"] h2{font:900 clamp(24px,3vw,30px)/1.3 var(--serif-d);letter-spacing:-0.01em;text-wrap:balance}
.dek-cn{font:400 15px/1.8 var(--sans-b);color:var(--ink-2)}
.dek-en{font:400 15px/1.7 var(--sans-b);color:var(--ink-2)}
.b-cn.b-lede::first-letter{font:700 3.1em/1 var(--serif-d);float:left;margin:6px 10px 0 0}
.beat{margin:0 0 26px}.beat:last-child{margin-bottom:0}
.num{font-weight:700;font-variant-numeric:tabular-nums}
.num.hot{color:var(--verm)}
/* figures */
.fig{margin:30px auto;max-width:660px}
.fig img{display:block;width:100%;height:auto;background:#fff}
.fig-hero img{aspect-ratio:485/314}
.fig-chart img{aspect-ratio:410/330}
.fig figcaption{font:400 12.5px/1.7 var(--sans-b);color:var(--ink-2);border-left:3px solid var(--verm);padding:2px 0 2px 12px;margin-top:10px}
.fig-chart{max-width:520px}
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
.compare-duel .cpair{display:grid;grid-template-columns:1fr 1fr;gap:28px;padding:18px 0;border-top:1px solid var(--line-2)}
.compare-duel .cpair:last-child{border-bottom:var(--bw) solid var(--ink)}
.compare-duel .cside{min-width:0}
.compare-duel .plab{font:700 11px/1.6 var(--mono);letter-spacing:.14em;color:var(--ink-3);margin-bottom:8px}
.compare-duel .ptext{font:400 15.5px/1.75 var(--sans-b);color:var(--ink)}
@media(max-width:768px){.compare-duel .cpair{grid-template-columns:1fr;gap:16px}}
/* ============ R3.5: 组件信息层级（题眼/主次/数据主角） ============ */
.cmp-label{font:700 13px/1.6 var(--mono);letter-spacing:.14em;color:var(--ink);margin:30px 0 14px;padding-top:12px;border-top:1px solid var(--line-2)}
.ce-block.ce-claim .ce-text{font:600 16px/1.7 var(--serif-d);color:var(--ink)}
.ce-block.ce-ev .ce-tag{font-size:12px}
.ce-block.ce-ev .ce-text{font:800 20px/1.62 var(--serif-d);color:var(--ink)}
.ce-block.ce-ev .ce-text .hot{font-weight:800}
.bar-row{grid-template-columns:132px 1fr 84px}
.bar-label .bl-t{color:var(--ink-2)}
.bar-label .bl-j{color:var(--ink);font-weight:800;margin-left:6px}
.bar-val{font:800 22px/1.2 var(--mono);font-variant-numeric:tabular-nums;text-align:right;color:var(--verm);white-space:nowrap}
/* desktop: editorial composition with breakout */
@media(min-width:1024px){
  .stat-strip{grid-template-columns:repeat(4,1fr);gap:20px}
  .stat .v{font-size:29px}
  .fig-hero{max-width:920px;margin:30px -130px}
  .fig-chart{max-width:560px}
  .dir-a .pullquote{margin:36px -60px;padding:0 60px}
  .stat-strip{gap:24px 40px}
}
/* motion: restrained editorial reveals (MOTION 4) */
html{scroll-behavior:smooth}
.global-lang-toggle{transition:background .25s cubic-bezier(.16,1,.3,1),color .25s cubic-bezier(.16,1,.3,1)}
.global-lang-toggle:hover{background:var(--ink);color:var(--paper)}
.global-lang-toggle:active{transform:scale(.97)}
.global-lang-toggle{touch-action:manipulation;-webkit-tap-highlight-color:rgba(33,29,21,.15);min-height:36px}
.global-lang-toggle:focus-visible{outline:2.5px solid var(--verm);outline-offset:3px}
@media(max-width:640px){.global-lang-toggle{min-height:44px;min-width:64px}}
a:focus-visible{outline:2.5px solid var(--verm);outline-offset:2px}
@media (prefers-reduced-motion: no-preference){
  .reveal{animation:r33-in .8s cubic-bezier(.16,1,.3,1) both;animation-timeline:view();animation-range:entry 8% entry 65%}
  @keyframes r33-in{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:none}}
}
/* paper grain: fixed, ultra-subtle (Editorial Luxury) */
body::after{content:"";position:fixed;inset:0;z-index:60;pointer-events:none;opacity:.03;
background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='160' height='160' filter='url(%23n)' opacity='0.55'/%3E%3C/svg%3E")}
/* mobile: single column, protected measure */
@media(max-width:640px){
  .page{padding:0 calc(14px + env(safe-area-inset-right)) 0 calc(14px + env(safe-area-inset-left))}
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
  document.querySelectorAll('.story h2').forEach(function(h){
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
 '<a class="skip" href="#main">跳到正文</a>',
 '<div class="r3-top"><div class="brand">WSJ 深读 · DEEP READ</div><h1>R3.5 · 组件层级重做</h1>'
 '<div class="sub">方向 A（朱砂印刷风）· 新字体系统 · 真实视觉资产 · 自适应排版 · 内容逐字取自 2026-10-12 深读定稿</div></div>',
 '<div class="r3-toolbar"><button class="global-lang-toggle" id="globalLang" type="button" aria-pressed="false">EN</button>'
 '<span class="proto-note">R3.5 样稿 · 沙特长文 + 电动车报道</span></div>']
for mid in ['r3E1-005','r3E3-002']:
    body.append(art_map[mid])
body.insert(1, '<main id="main">')
body.append('</main>')
body.append('<footer class="colophon">R3.5 样稿。图片：电动车充电站照片（Angus Mordant/彭博新闻）与月度充电桩图表（数据源：能源部）均取自《华尔街日报》2026年10月12日 B1 版原报；沙特报道在原报 A1 版无配图，未采用图片。12%→6% 柱状图为编辑绘制（数据来自正文第 10 段）。</footer>')
body.append('</div>')

html_doc = f'''<!DOCTYPE html>
<html lang="zh-CN" data-lang="cn">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#fdfbf8">
<title>WSJ 深读 R3.5 · 组件层级重做</title>
{fonts_link}
<style>{base_css}{r31_css}</style>
</head>
<body>
{chr(10).join(body)}
{js}
</body>
</html>'''

open(f'{BASE}/cases/wsj-r3-5.html', 'w').write(html_doc)
print('r3.3 shell bytes:', len(html_doc))
