#!/usr/bin/env python3
"""Wrap prototype articles in the v7 page shell + component CSS."""
import re

BASE = '/home/hatch/workspace/wsj-deep-read/2026-10-12'
v7 = open(f'{BASE}/wsj-2026-10-12-deepread-v7.html').read()
articles = open(f'{BASE}/cases/articles.html').read()

m = re.search(r'<style>(.*?)</style>', v7, re.S)
base_css = m.group(1)

component_css = '''
/* ============ Article interior components (prototype) ============ */
.proto .b-cn,.proto .b-en{font:400 16px/1.85 var(--sans);margin:0 0 14px;max-width:68ch}
.cmp-label{font:600 11px/1.6 var(--mono);letter-spacing:.14em;color:var(--ink-3);margin:26px 0 12px;
  padding-top:12px;border-top:1px solid var(--line-2)}
.cmp-label:first-child{margin-top:0}
/* stat row — ChatKit big-number pattern */
.stat-row{display:flex;gap:28px;flex-wrap:wrap;margin:6px 0 8px;padding:18px 0;
  border-top:var(--bw) solid var(--ink);border-bottom:1px solid var(--line-2)}
.stat{flex:1 1 150px;min-width:130px}
.stat .k{font:600 11px/1.5 var(--mono);letter-spacing:.1em;color:var(--ink-3);margin-bottom:8px}
.stat .v{font:600 32px/1.15 var(--serif);letter-spacing:-.01em;font-variant-numeric:tabular-nums}
.stat .v.long{font-size:22px;letter-spacing:0;white-space:nowrap}
.stat .d{font:400 13px/1.6 var(--sans);color:var(--ink-2);margin-top:6px}
/* key facts — spec-sheet pattern */
.keyfacts{margin:6px 0 8px;border:var(--bw) solid var(--ink);background:#fff;padding:2px 18px}
.kf-row{display:flex;gap:16px;padding:11px 0;border-top:1px solid var(--line-2);align-items:baseline}
.kf-row:first-child{border-top:0}
.kf-k{font:600 12px/1.6 var(--mono);letter-spacing:.08em;color:var(--ink-3);flex:0 0 auto;min-width:96px}
.kf-v{font:400 15px/1.65 var(--sans);margin-left:auto;text-align:right;font-variant-numeric:tabular-nums}
/* timeline — assistant-ui pattern, squared to fit the system */
.timeline{margin:6px 0 8px}
.tl-item{display:grid;grid-template-columns:64px 20px 1fr;gap:0 10px;padding:9px 0;position:relative}
.tl-time{font:600 12px/1.75 var(--mono);color:var(--ink-3);text-align:right;letter-spacing:.04em}
.tl-rail{position:relative}
.tl-rail::before{content:"";position:absolute;left:9px;top:26px;bottom:-10px;width:1.5px;background:var(--ink)}
.tl-item:last-child .tl-rail::before{display:none}
.tl-dot{position:absolute;left:5px;top:7px;width:9px;height:9px;background:var(--ink)}
.tl-body{font:400 14.5px/1.7 var(--sans);color:var(--ink);max-width:64ch}
/* comparison — neutral two-column */
.compare{display:grid;grid-template-columns:1fr 1fr;margin:6px 0 8px;border:var(--bw) solid var(--ink);background:#fff}
.cmp-col{padding:16px 18px}
.cmp-col + .cmp-col{border-left:1px solid var(--line-2)}
.cmp-col .who{font:600 11px/1.6 var(--mono);letter-spacing:.14em;color:var(--ink-3);margin-bottom:10px}
.cmp-col .what{font:400 14.5px/1.7 var(--sans)}
.cmp-col .what + .what{margin-top:10px;padding-top:10px;border-top:1px solid var(--line-2)}
/* digest list — ChatKit ListView pattern */
.digest-group{margin:4px 0 18px}
.digest-head{display:flex;align-items:baseline;gap:12px;border-bottom:var(--bw) solid var(--ink);padding-bottom:8px;margin-bottom:2px}
.digest-head .t{font:600 18px/1.4 var(--serif)}
.digest-head .n{font:600 11px/1 var(--mono);letter-spacing:.1em;color:var(--ink-3)}
.digest-item{display:grid;grid-template-columns:46px 1fr;gap:14px;padding:12px 0;border-bottom:1px solid var(--line-2);align-items:start}
.digest-item:last-child{border-bottom:0}
.page-chip{font:700 11px/1 var(--mono);letter-spacing:.06em;border:1px solid var(--ink);padding:6px 0;text-align:center}
.digest-text{font:400 15px/1.75 var(--sans)}
/* signers */
.signer-groups{display:grid;grid-template-columns:1fr 1fr;gap:0;margin:6px 0 8px;border:var(--bw) solid var(--ink);background:#fff}
.signer-group{padding:14px 18px}
.signer-group + .signer-group{border-left:1px solid var(--line-2)}
.sg-party{font:600 11px/1.6 var(--mono);letter-spacing:.14em;color:var(--ink-3);margin-bottom:8px}
.sg-name{font:400 14.5px/1.7 var(--sans);padding:3px 0}
/* Q&A */
.qa{margin:20px 0}
.qa-q{display:grid;grid-template-columns:44px 1fr;gap:14px;align-items:start;margin-bottom:10px}
.qa-tag{font:700 12px/1 var(--mono);letter-spacing:.08em;color:#fff;background:var(--ink);text-align:center;padding:8px 0}
.qa-qtext{font:600 17px/1.6 var(--serif)}
.qa-a{padding-left:58px}
.qa-a p{font:400 16px/1.85 var(--sans);margin:0 0 12px;max-width:68ch}
/* cross-ref + photo */
.xref{font:400 13px/1.7 var(--mono);color:var(--ink-2);border:1px dashed var(--line-2);padding:9px 14px;margin:16px 0}
.photo-cap{font:400 13px/1.7 var(--sans);color:var(--ink-2);border-left:3px solid var(--line-2);padding:2px 0 2px 12px;margin:14px 0}
.proto-note{font:400 12px/1.6 var(--mono);color:var(--ink-2);letter-spacing:.06em}
@media(max-width:640px){
  .compare{grid-template-columns:1fr}
  .cmp-col + .cmp-col{border-left:0;border-top:1px solid var(--line-2)}
  .signer-groups{grid-template-columns:1fr}
  .signer-group + .signer-group{border-left:0;border-top:1px solid var(--line-2)}
  .stat .v{font-size:27px}
  .qa-a{padding-left:0}
  .tl-item{grid-template-columns:52px 20px 1fr}
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
  document.querySelectorAll('.k-cn,.b-cn,.dek-cn,.digest-lang-cn').forEach(function(e){e.hidden=en;});
  document.querySelectorAll('.k-en,.b-en,.dek-en,.digest-lang-en').forEach(function(e){e.hidden=!en;});
  var g=document.getElementById('globalLang');
  g.textContent=en?'\\u4e2d\\u6587':'EN';
  g.setAttribute('aria-pressed',en?'true':'false');
}
document.getElementById('globalLang').addEventListener('click',function(){
  setLang(root.dataset.lang==='en'?'cn':'en');});
})();
</script>
'''

secs = [
    ('新闻 · NEWS', 'p-E1-001', ['p-E1-001', 'p-E1-004', 'p-E1-005']),
    ('商业 · BUSINESS', 'p-E3-002', ['p-E3-002', 'p-E3-003']),
]
# split articles by id
art_map = {}
for mid in ['p-E1-001','p-E1-004','p-E1-005','p-E3-002','p-E3-003']:
    mm = re.search(rf'<article class="story proto" id="{mid}".*?</article>', articles, re.S)
    art_map[mid] = mm.group(0) if mm else f'<!-- missing {mid} -->'

body = ['<div class="page">',
 '<header class="masthead"><div><h1>WSJ 深读</h1><p>文章内部设计样稿 · ARTICLE INTERIOR PROTOTYPE · 5 篇</p></div></header>',
 '<div class="toolbar"><button class="global-lang-toggle" id="globalLang" type="button" aria-pressed="false">EN</button>'
 '<span class="proto-note">样稿范围：条目内部排版 · 外层结构沿用 v7</span></div>',
 '<aside class="toc"><h2>样稿目录</h2><nav>' +
 ''.join(f'<a href="#{mid}"><strong>{i+1:02d}</strong><span>{mid[2:]}</span></a>' for i, mid in enumerate(['p-E1-001','p-E1-004','p-E1-005','p-E3-002','p-E3-003'])) +
 '</nav></aside>']
for si, (title, first, mids) in enumerate(secs):
    body.append(f'<section class="paper-section" id="sec-p{si+1}"><div class="section-head"><span class="section-no">P{si+1}</span><div><h2>{title}</h2></div></div>')
    body.extend(art_map[m] for m in mids)
    body.append('</section>')
body.append('<footer class="colophon">样稿：内容逐字取自 2026-10-12 深读定稿（final.json），仅调整呈现结构。双语 1:1。</footer>')
body.append('</div>')

html_doc = f'''<!DOCTYPE html>
<html lang="zh-CN" data-lang="cn">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>WSJ 深读 · 文章内部设计样稿</title>
<style>{base_css}{component_css}</style>
</head>
<body>
{chr(10).join(body)}
{js}
</body>
</html>'''

open(f'{BASE}/cases/wsj-interior-prototype.html', 'w').write(html_doc)
print('prototype bytes:', len(html_doc))
