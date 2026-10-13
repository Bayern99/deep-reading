#!/usr/bin/env python3
"""WSJ 深读混合重设计原型：Al Jazeera 主干 + WIRED 字体气质.
内容唯一来源: ../wsj-design-exploration/article-e1005.json（24 段一字不改）
输出: index.html（单文件）
"""
import json, html, os

BASE = os.path.dirname(os.path.abspath(__file__))
A = json.load(open(os.path.join(BASE, '..', 'wsj-design-exploration', 'article-e1005.json')))

def esc(s):
    return html.escape(s, quote=True).replace('&#x27;', "'")

def pair(cn, en, tag='p', cls=''):
    """中英 1:1 段落"""
    c = f' class="{cls}"' if cls else ''
    return (f'<{tag}{c}><span class="k-cn">{esc(cn)}</span>'
            f'<span class="k-en" hidden>{esc(en)}</span></{tag}>')

def build():
    body = A['body']
    parts = []

    # ---------- masthead ----------
    parts.append('''
<header class="masthead">
  <a class="skip" href="#article">跳到正文</a>
  <div class="mast-in">
    <div class="brand"><span class="sq"></span><span class="wm k-cn">WSJ 深读</span><span class="wm k-en" hidden>WSJ Deep Read</span></div>
    <button id="langToggle" class="pill" aria-pressed="false" aria-label="切换中英文">
      <span class="k-cn">EN</span><span class="k-en" hidden>中文</span>
    </button>
  </div>
</header>
<div class="progress" aria-hidden="true"><span id="pbar"></span></div>''')

    # ---------- article head ----------
    parts.append(f'''
<main id="article">
<article class="sheet">
  <header class="ahead">
    <div class="kicker"><span class="kbar"></span><span class="k-cn">中东 · 沙特阿拉伯 · P1 必读</span><span class="k-en" hidden>MIDDLE EAST · SAUDI ARABIA · P1 MUST READ</span></div>
    <h1><span class="k-cn">{esc(A['title_cn'])}</span><span class="k-en" hidden>{esc(A['title_en'])}</span></h1>
    <p class="deck"><span class="k-cn">{esc(A['dek_cn'])}</span><span class="k-en" hidden>{esc(A['dek_en'])}</span></p>
    <div class="byline">
      <span class="who">{esc(A['byline'])}</span>
      <span class="meta k-cn">2026年10月12日 · 《华尔街日报》A1 版</span>
      <span class="meta k-en" hidden>Oct 12, 2026 · The Wall Street Journal, p.A1</span>
    </div>
  </header>
  <div class="arule"></div>''')

    # ---------- right rail ----------
    parts.append('''
  <aside class="rail" aria-label="本篇导航">
    <div class="rail-in">
      <div class="rail-t k-cn">本篇</div><div class="rail-t k-en" hidden>IN THIS STORY</div>
      <nav>
        <a href="#keyfig" data-spy="keyfig"><span class="k-cn">关键数字</span><span class="k-en" hidden>Key figures</span></a>
        <a href="#timeline" data-spy="timeline"><span class="k-cn">时间线</span><span class="k-en" hidden>Timeline</span></a>
        <a href="#context" data-spy="context"><span class="k-cn">背景资料</span><span class="k-en" hidden>Background</span></a>
        <a href="#end" data-spy="end"><span class="k-cn">文末</span><span class="k-en" hidden>End</span></a>
      </nav>
    </div>
  </aside>''')

    # ---------- key figures (after P2 = index 1) ----------
    kf = ['<section id="keyfig" class="mod keyfig" aria-label="关键数字">']
    kf.append('<div class="mtag"><span class="k-cn">关键数字</span><span class="k-en" hidden>KEY FIGURES</span></div>')
    for i, s in enumerate(A['stats']):
        kf.append(f'''<div class="krow">
      <div class="kidx">{i+1:02d}</div>
      <div class="kval"><span class="k-cn">{esc(s['value_cn'])}</span><span class="k-en" hidden>{esc(s['value_en'])}</span></div>
      <div class="kbody">
        <div class="klabel"><span class="k-cn">{esc(s['label_cn'])}</span><span class="k-en" hidden>{esc(s['label_en'])}</span></div>
        <div class="knote"><span class="k-cn">{esc(s['note_cn'])}</span><span class="k-en" hidden>{esc(s['note_en'])}</span></div>
      </div>
    </div>''')
    kf.append('</section>')
    KEYFIG = '\n'.join(kf)

    # ---------- timeline (after P7 = index 6) ----------
    tl = ['<section id="timeline" class="mod timeline" aria-label="时间线">']
    tl.append('<div class="mtag"><span class="kbar-sm"></span><span class="k-cn">时间线 · 冲突升级</span><span class="k-en" hidden>TIMELINE · ESCALATION</span></div>')
    tl.append('<ol class="tl">')
    for t in A['timeline']:
        tl.append(f'''<li>
      <span class="dot" aria-hidden="true"></span>
      <div class="tt"><span class="k-cn">{esc(t['t_cn'])}</span><span class="k-en" hidden>{esc(t['t_en'])}</span></div>
      <div class="tx"><span class="k-cn">{esc(t['text_cn'])}</span><span class="k-en" hidden>{esc(t['text_en'])}</span></div>
    </li>''')
    tl.append('</ol></section>')
    TIMELINE = '\n'.join(tl)

    # ---------- context: AJ bottom collapsible (after all body paragraphs) ----------
    CONTEXT = f'''<details id="context" class="mod ctx">
    <summary><span class="k-cn">背景资料</span><span class="k-en" hidden>BACKGROUND</span></summary>
    <div class="ctx-body"><p lang="zh-CN">{esc(A['context_cn'])}</p></div>
  </details>'''

    # ---------- quote module (after P14 = index 13; direct quote only, narration stays in body) ----------
    _q = A['pullquote']
    _qt_cn = _q['text_cn'].strip('“”"')
    _qt_en = _q['text_en'].strip('"“”')
    QUOTE = f'''<aside class="mod quote" aria-label="引语">
    <div class="qt"><span class="k-cn">{esc(_qt_cn)}</span><span class="k-en" hidden>{esc(_qt_en)}</span></div>
    <div class="qa"><span class="k-cn">{esc(_q['attr_cn'])}</span><span class="k-en" hidden>{esc(_q['attr_en'])}</span></div>
  </aside>'''

    # ---------- body paragraphs ----------
    for i, p in enumerate(body):
        parts.append(pair(p['cn'], p['en'], 'p'))
        if i == 1:
            parts.append(KEYFIG)
        if i == 6:
            parts.append(TIMELINE)
        if i == 13:
            parts.append(QUOTE)

    parts.append(CONTEXT)

    # ---------- footer ----------
    parts.append(f'''
  <footer id="end" class="fin">
    <div class="arule"></div>
    <p class="src"><span class="k-cn">{esc(A['source_note'])}</span><span class="k-en" hidden>{esc(A['source_note'])}</span></p>
    <div class="finrow"><span class="endmark" aria-hidden="true">■</span>
      <button id="toTop" class="pill"><span class="k-cn">回顶部</span><span class="k-en" hidden>Back to top</span></button>
    </div>
  </footer>
</article>
</main>''')

    return '\n'.join(parts)


CSS = '''
:root{
  --paper:#fdfbf8; --ink:#111111; --body:#1f1f1f; --mut:#5f6462;
  --line:#e5e2da; --orange:#fa9000; --red:#c31833;
  --serif:"Noto Serif SC","Playfair Display","Songti SC",serif;
  --sans:"Noto Sans SC","Inter","PingFang SC","Microsoft YaHei",sans-serif;
  --mono:"Noto Sans Mono","IBM Plex Mono",monospace;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--paper);color:var(--body);
  font-family:var(--sans);-webkit-font-smoothing:antialiased}
::selection{background:#111;color:#fdfbf8}

/* masthead */
.masthead{border-bottom:1px solid var(--ink)}
.mast-in{max-width:1080px;margin:0 auto;padding:10px 24px;display:flex;align-items:center;justify-content:space-between}
.brand{display:flex;align-items:center;gap:10px}
.sq{width:18px;height:18px;background:var(--orange);display:inline-block}
.wm{font-weight:700;font-size:15px;letter-spacing:.06em;color:var(--ink)}
.pill{background:#111;color:#fff;border:0;border-radius:9999px;padding:8px 20px;
  font-family:var(--sans);font-size:13px;font-weight:500;cursor:pointer;letter-spacing:.05em}
.pill:focus-visible,a:focus-visible{outline:2px solid var(--orange);outline-offset:2px}
.skip{position:absolute;left:-9999px;top:0;background:#111;color:#fff;padding:8px 16px;z-index:99}
.skip:focus{left:8px;top:8px}
.progress{position:sticky;top:0;height:2px;background:transparent;z-index:50}
.progress span{display:block;height:100%;width:0;background:#111}

/* article head */
#article{max-width:1080px;margin:0 auto;padding:0 24px}
.sheet{position:relative}
.ahead{max-width:760px;margin:0 auto;padding:40px 0 8px;text-align:left}
.kicker{display:flex;align-items:center;gap:10px;font-size:13px;font-weight:700;
  letter-spacing:.14em;color:var(--mut);margin-bottom:20px}
.kbar{width:8px;height:22px;background:var(--orange);display:inline-block;flex:none}
h1{font-family:var(--serif);font-weight:700;font-size:40px;line-height:1.3;
  color:var(--ink);margin:0 0 14px;text-wrap:balance;letter-spacing:.01em}
.deck{font-family:var(--serif);font-size:18px;line-height:1.7;color:var(--mut);margin:0 0 20px}
.byline{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:baseline;
  font-family:var(--sans);font-size:13px;margin-bottom:26px}
.byline .who{font-weight:700;letter-spacing:.04em;color:var(--ink)}
.byline .meta{color:var(--mut)}
.arule{border-top:1px solid var(--ink);margin:0 auto;max-width:760px}

/* right rail */
.rail{display:none}
@media(min-width:1200px){
  .rail{display:block;position:absolute;top:340px;right:0;width:180px}
  .rail-in{position:sticky;top:80px}
  .rail-t{font-size:11px;font-weight:700;letter-spacing:.18em;color:var(--mut);margin-bottom:10px}
  .rail nav a{display:block;padding:7px 0;font-size:13px;color:var(--mut);text-decoration:none;
    border-left:2px solid var(--line);padding-left:12px}
  .rail nav a.on{color:var(--ink);font-weight:700;border-left-color:#111}
}

/* body */
.sheet>p, .sheet .mod{max-width:640px;margin-left:auto;margin-right:auto}
.sheet>p{font-family:var(--serif);font-size:16px;line-height:1.8;color:var(--body);
  margin-top:0;margin-bottom:1.05em}
html[lang="en"] .sheet>p{font-family:"Lora",Georgia,serif}
.k-en{font-family:"Lora",Georgia,serif}
p .k-en{font-size:.96em}

/* quote module (AJ scale, WIRED serif): direct quote only, narration stays in body */
.quote{margin-top:2em;margin-bottom:2em;padding:2px 0 2px 18px;border-left:3px solid var(--ink)}
.quote .qt{font-family:var(--serif);font-weight:700;font-size:20px;line-height:1.7;color:var(--ink)}
html[lang="en"] .quote .qt{font-family:"Playfair Display","Noto Serif SC",serif}
.quote .qa{font-family:var(--sans);font-size:13px;color:var(--mut);margin-top:10px}

/* modules */
.mod{margin-top:2em;margin-bottom:2em}
.mtag{display:flex;align-items:center;gap:10px;font-family:var(--sans);
  font-size:13px;font-weight:700;letter-spacing:.16em;color:var(--ink);margin-bottom:8px}
.kbar-sm{width:8px;height:18px;background:var(--orange);display:inline-block;flex:none}

/* key figures: AJ ranked rows */
.keyfig .krow{display:flex;gap:16px;align-items:baseline;padding:14px 0;border-bottom:1px solid var(--line)}
.keyfig .krow:first-of-type{border-top:1px solid var(--line)}
.kidx{font-family:var(--mono);font-size:13px;color:var(--mut);flex:none;width:28px}
.kval{font-family:var(--serif);font-weight:700;font-size:28px;line-height:1.2;color:var(--ink);
  flex:none;width:200px}
.klabel{font-size:13px;font-weight:700;color:var(--ink);margin-bottom:4px}
.knote{font-size:13px;color:var(--mut);line-height:1.7}

/* timeline: AJ live language */
.timeline .tl{list-style:none;margin:18px 0 0;padding:0;position:relative}
.timeline .tl::before{content:"";position:absolute;left:5px;top:8px;bottom:8px;width:2px;background:#d9d9d9}
.timeline li{position:relative;padding:0 0 16px 28px}
.timeline .dot{position:absolute;left:0;top:7px;width:12px;height:12px;border-radius:50%;background:var(--red)}
.timeline .tt{font-family:var(--mono);font-size:13px;font-weight:700;color:var(--ink);margin-bottom:4px;letter-spacing:.04em}
.timeline .tx{font-family:var(--serif);font-size:15px;line-height:1.75;color:var(--body)}

/* context: AJ bottom collapsible */
.ctx{border:1px solid var(--line)}
.ctx summary{list-style:none;cursor:pointer;padding:14px 18px;font-family:var(--sans);
  font-weight:700;font-size:15px;color:var(--ink);display:flex;justify-content:space-between;
  align-items:center;gap:12px;min-height:44px}
.ctx summary::-webkit-details-marker{display:none}
.ctx summary::after{content:"+";font-weight:300;font-size:22px;color:var(--mut);flex:none}
.ctx[open] summary::after{content:"–"}
.ctx summary:focus-visible{outline:2px solid var(--orange);outline-offset:2px}
.ctx .ctx-body{padding:0 18px 18px;font-family:var(--serif);font-size:15px;line-height:1.8;
  color:var(--body);border-top:1px solid var(--line);padding-top:14px}
.ctx .ctx-body p{margin:0}

/* footer */
.fin{max-width:760px;margin:0 auto;padding:8px 0 60px}
.fin .arule{max-width:none;margin-bottom:18px}
.src{font-size:13px;color:var(--mut);line-height:1.8;margin:0 0 22px}
.finrow{display:flex;align-items:center;justify-content:space-between}
.endmark{font-size:14px;color:#111}

/* responsive */
@media(max-width:768px){
  h1{font-size:32px}
  .ahead{padding:32px 0 8px}
}
@media(max-width:430px){
  h1{font-size:30px;line-height:1.35}
  .deck{font-size:17px}
  .sheet>p{font-size:16px;line-height:1.75}
  .quote .qt{font-size:19px}
  .kval{font-size:22px;width:165px}
  .keyfig .krow{gap:12px}
  #article{padding:0 20px}
}
'''

JS = '''
(function(){
  var btn=document.getElementById('langToggle');
  function setLang(en){
    document.querySelectorAll('.k-cn').forEach(function(e){e.hidden=en});
    document.querySelectorAll('.k-en').forEach(function(e){e.hidden=!en});
    document.documentElement.lang=en?'en':'zh-CN';
    btn.setAttribute('aria-pressed',en?'true':'false');
  }
  btn.addEventListener('click',function(){
    setLang(btn.getAttribute('aria-pressed')!=='true');
  });
  document.getElementById('toTop').addEventListener('click',function(){
    window.scrollTo({top:0,behavior:'smooth'});
  });
  var bar=document.getElementById('pbar');
  function prog(){
    var h=document.documentElement;
    var m=h.scrollHeight-h.clientHeight;
    bar.style.width=(m>0?(h.scrollTop/m*100):0)+'%';
  }
  window.addEventListener('scroll',prog,{passive:true});prog();
  // rail scroll-spy
  var links=document.querySelectorAll('.rail nav a');
  if(links.length&&'IntersectionObserver' in window){
    var map={};
    links.forEach(function(a){map[a.getAttribute('data-spy')]=a});
    var io=new IntersectionObserver(function(es){
      es.forEach(function(e){
        if(e.isIntersecting){
          links.forEach(function(a){a.classList.remove('on')});
          var a=map[e.target.id];if(a)a.classList.add('on');
        }
      });
    },{rootMargin:'-30% 0px -60% 0px'});
    ['keyfig','timeline','context','end'].forEach(function(id){
      var el=document.getElementById(id);if(el)io.observe(el);
    });
  }
})();
'''

HTML = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>胡塞武装发动袭击，沙特王储重担加重 · WSJ 深读</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;700&family=Noto+Sans+SC:wght@400;500;700&family=Noto+Sans+Mono:wght@400;700&family=Playfair+Display:wght@700&family=Lora:ital,wght@0,400;0,700;1,400&family=Inter:wght@500;600&display=swap" rel="stylesheet">
<style>''' + CSS + '''</style>
</head>
<body>
''' + build() + '''
<script>''' + JS + '''</script>
</body>
</html>
'''

if __name__ == '__main__':
    out = os.path.join(BASE, 'index.html')
    open(out, 'w', encoding='utf-8').write(HTML)
    print('wrote', out, len(HTML), 'bytes')
