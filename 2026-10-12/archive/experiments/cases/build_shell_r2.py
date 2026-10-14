#!/usr/bin/env python3
"""R2 shell: v7 CSS verbatim + R2 editorial typography."""
import re, sys

BASE = '/home/hatch/workspace/wsj-deep-read/2026-10-12'
v7 = open(f'{BASE}/wsj-2026-10-12-deepread-v7.html').read()
scheme = sys.argv[2] if len(sys.argv) > 2 else 'a'
articles = open(f'{BASE}/cases/articles-r2{scheme}.html').read()

base_css = re.search(r'<style>(.*?)</style>', v7, re.S).group(1)

r2_css = '''
/* ============ R2 editorial typography (on v7 base, no base overrides) ============ */
.beat{margin:0 0 26px}
.beat:last-child{margin-bottom:0}
.b-cn.b-lede::first-letter{font:700 3.1em/1 var(--serif);float:left;margin:6px 10px 0 0}
.pullquote{margin:30px 0}
.pullquote.a .pq-text{font:600 21px/1.65 var(--serif);letter-spacing:.005em}
.pullquote.a .pq-text::before{content:"\\201C";display:block;font:700 42px/1 var(--serif);color:var(--ink-3);margin-bottom:10px}
.pullquote.a .pq-attr{font:600 12px/1.6 var(--mono);letter-spacing:.08em;color:var(--ink-3);margin-top:12px}
.pullquote.b .pq-text{font:600 17px/1.7 var(--serif);border-left:3px solid var(--ink);padding-left:16px}
.pullquote.b .pq-attr{font:600 12px/1.6 var(--mono);letter-spacing:.08em;color:var(--ink-3);margin-top:10px;padding-left:19px}
.num{font-weight:600;font-variant-numeric:tabular-nums}
.cmp-label{font:600 11px/1.6 var(--mono);letter-spacing:.14em;color:var(--ink-3);margin:26px 0 12px;padding-top:12px;border-top:1px solid var(--line-2)}
.stat-row{display:grid;grid-template-columns:1fr 1fr;gap:20px 28px;margin:6px 0 8px;padding:18px 0;border-top:var(--bw) solid var(--ink);border-bottom:1px solid var(--line-2)}
.stat{min-width:0}
.stat .k{font:600 11px/1.5 var(--mono);letter-spacing:.1em;color:var(--ink-3);margin-bottom:8px}
.stat .v{font:600 32px/1.15 var(--serif);letter-spacing:-.01em;font-variant-numeric:tabular-nums}
.stat .v.long{font-size:22px;letter-spacing:0;white-space:nowrap}
.stat .d{font:400 13px/1.6 var(--sans);color:var(--ink-2);margin-top:6px}
.timeline{margin:6px 0 8px}
.tl-item{display:grid;grid-template-columns:64px 20px 1fr;gap:0 10px;padding:9px 0;position:relative}
.tl-time{font:600 12px/1.75 var(--mono);color:var(--ink-3);text-align:right;letter-spacing:.04em}
.tl-rail{position:relative}
.tl-rail::before{content:"";position:absolute;left:9px;top:26px;bottom:-10px;width:1.5px;background:var(--ink)}
.tl-item:last-child .tl-rail::before{display:none}
.tl-dot{position:absolute;left:5px;top:7px;width:9px;height:9px;background:var(--ink)}
.tl-body{font:400 14.5px/1.7 var(--sans);color:var(--ink)}
.compare2{margin:8px 0 8px}
.compare2 .crow{display:grid;grid-template-columns:1fr 1fr;gap:28px;padding:16px 0;border-top:1px solid var(--line-2)}
.compare2 .crow:first-of-type{border-top:var(--bw) solid var(--ink)}
.compare2 .crow:last-child{border-bottom:var(--bw) solid var(--ink)}
.compare2 .crow.chead{padding:0 0 10px;border-top:0}
.compare2 .crow.chead + .crow{border-top:var(--bw) solid var(--ink)}
.compare2 .crow.chead .cwho{margin-bottom:0}
.cwho{font:600 11px/1.6 var(--mono);letter-spacing:.12em;color:var(--ink-3);margin-bottom:8px}
.cwhat{font:400 15px/1.7 var(--sans)}
.keyfacts2{margin:8px 0;border-top:var(--bw) solid var(--ink);border-bottom:var(--bw) solid var(--ink)}
.kf2-row{display:flex;gap:16px;padding:11px 0;border-top:1px solid var(--line-2);align-items:baseline}
.kf2-row:first-child{border-top:0}
.kf2-k{font:600 12px/1.6 var(--mono);letter-spacing:.08em;color:var(--ink-3);flex:0 0 auto;min-width:96px}
.kf2-v{font:400 15px/1.65 var(--sans);margin-left:auto;text-align:right;font-variant-numeric:tabular-nums}
.digest2-group{margin:4px 0 18px}
.digest2-head{display:flex;align-items:baseline;gap:12px;border-bottom:var(--bw) solid var(--ink);padding-bottom:8px;margin-bottom:2px}
.digest2-head .t{font:600 18px/1.4 var(--serif)}
.digest2-head .n{font:600 11px/1 var(--mono);letter-spacing:.1em;color:var(--ink-3)}
.digest2-item{display:grid;grid-template-columns:38px 1fr;gap:14px;padding:11px 0;border-bottom:1px solid var(--line-2);align-items:start}
.digest2-item:last-child{border-bottom:0}
.page-ref{font:700 12px/1.75 var(--mono);letter-spacing:.04em;color:var(--ink-3)}
.digest2-text{font:400 15px/1.75 var(--sans)}
.signer-groups{display:grid;grid-template-columns:1fr 1fr;gap:0;margin:6px 0 8px;border:var(--bw) solid var(--ink);background:#fff}
.signer-group{padding:14px 18px}
.signer-group + .signer-group{border-left:1px solid var(--line-2)}
.sg-party{font:600 11px/1.6 var(--mono);letter-spacing:.14em;color:var(--ink-3);margin-bottom:8px}
.sg-name{font:400 14.5px/1.7 var(--sans);padding:3px 0}
.qa2{margin:0}
.qa2-q{font:600 16.5px/1.65 var(--serif);margin:26px 0 10px}
.qa2-q .qmark{font:700 12px/1.6 var(--mono);color:var(--ink-3);letter-spacing:.14em;margin-right:12px}
.xref{font:400 13px/1.7 var(--mono);color:var(--ink-2);border:1px dashed var(--line-2);padding:9px 14px;margin:16px 0}
.photo-cap{font:400 13px/1.7 var(--sans);color:var(--ink-2);border-left:3px solid var(--line-2);padding:2px 0 2px 12px;margin:14px 0}
.proto-note{font:400 12px/1.6 var(--mono);color:var(--ink-2);letter-spacing:.06em}
@media(max-width:640px){
  .compare2 .crow{grid-template-columns:1fr;gap:12px}
  .signer-groups{grid-template-columns:1fr}
  .signer-group + .signer-group{border-left:0;border-top:1px solid var(--line-2)}
  .stat .v{font-size:27px}
  .tl-item{grid-template-columns:52px 20px 1fr}
  .pullquote.a .pq-text{font-size:19px}
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
  document.querySelectorAll('.k-cn,.b-cn,.dek-cn,.digest2-lang-cn').forEach(function(e){e.hidden=en;});
  document.querySelectorAll('.k-en,.b-en,.dek-en,.digest2-lang-en').forEach(function(e){e.hidden=!en;});
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
for mid in ['r-E1-001','r-E1-004','r-E1-005','r-E3-002','r-E3-003']:
    mm = re.search(rf'<article class="story" id="{mid}".*?</article>', articles, re.S)
    art_map[mid] = mm.group(0) if mm else f'<!-- missing {mid} -->'

body = ['<div class="page">',
 '<header class="masthead"><div><h1>WSJ 深读</h1><p>R2 · 文章内部排印样稿</p></div></header>',
 '<div class="toolbar"><button class="global-lang-toggle" id="globalLang" type="button" aria-pressed="false">EN</button>'
 f'<span class="proto-note">R2 样稿 · scheme {scheme.upper()} · 外层沿用 v7（同版面条件）</span></div>',
 '<aside class="toc"><h2>样稿目录</h2><nav>' +
 ''.join(f'<a href="#{mid}"><strong>{i+1:02d}</strong><span>{mid[2:]}</span></a>' for i, mid in enumerate(art_map)) +
 '</nav></aside>']
for si, (title, mids) in enumerate([('新闻 · NEWS', ['r-E1-001','r-E1-004','r-E1-005']), ('商业 · BUSINESS', ['r-E3-002','r-E3-003'])]):
    body.append(f'<section class="paper-section" id="sec-r{si+1}"><div class="section-head"><span class="section-no">R{si+1}</span><div><h2>{title}</h2></div></div>')
    body.extend(art_map[m] for m in mids)
    body.append('</section>')
body.append('<footer class="colophon">R2 样稿：内容逐字取自 2026-10-12 深读定稿（final.json）。data-priority 采用 v7 数字制式；正文基样式沿用 v7。</footer>')
body.append('</div>')

html_doc = f'''<!DOCTYPE html>
<html lang="zh-CN" data-lang="cn">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>WSJ 深读 R2 · 文章内部排印样稿</title>
<style>{base_css}{r2_css}</style>
</head>
<body>
{chr(10).join(body)}
{js}
</body>
</html>'''

open(f'{BASE}/cases/wsj-r2-{scheme}.html', 'w').write(html_doc)
print('r2 shell bytes:', len(html_doc), 'scheme:', scheme)
