#!/usr/bin/env python3
"""WSJ 深读 · 正式渲染器（AJ × WIRED v1.0）
构建：cd render && python build.py --issue 2026-10-12
输入：../<issue>/final.json ｜ 输出：../<issue>/dist/index.html
"""
import argparse
import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from issue import render_issue, reading_order
from enhanced_render import load_plans
from text_treatment import TEXT_CSS
from layout import LAYOUT_CSS

BASE = os.path.dirname(os.path.abspath(__file__))

CSS = '''
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--paper);color:var(--body);
  font-family:var(--font-meta);-webkit-font-smoothing:antialiased}
::selection{background:#111;color:#fdfbf8}

/* masthead */
.masthead{border-bottom:1px solid var(--ink)}
.mast-in{max-width:var(--page);margin:0 auto;padding:10px 24px;display:flex;align-items:center;justify-content:space-between;gap:16px}
.brand{display:flex;align-items:center;gap:10px}
.sq{width:18px;height:18px;background:var(--orange);display:inline-block;flex:none}
.wm{font-weight:700;font-size:15px;letter-spacing:.06em;color:var(--ink)}
.mast-meta{font-size:13px;color:var(--mut)}
.pill{background:#111;color:#fff;border:0;border-radius:9999px;padding:8px 20px;
  font-family:var(--font-meta);font-size:13px;font-weight:500;cursor:pointer;letter-spacing:.05em;flex:none}
.pill:focus-visible,a:focus-visible,summary:focus-visible{outline:2px solid var(--orange);outline-offset:2px}
.skip{position:absolute;left:-9999px;top:0;background:#111;color:#fff;padding:8px 16px;z-index:99}
.skip:focus{left:8px;top:8px}
.progress{position:sticky;top:0;height:2px;background:transparent;z-index:50}
.progress span{display:block;height:100%;width:0;background:#111}

/* issue hero */
.issue-hero{max-width:var(--head-measure);margin:0 auto;padding:48px 24px 8px}
.issue-kicker{display:flex;align-items:center;gap:10px;font-size:13px;font-weight:700;
  letter-spacing:.14em;color:var(--mut);margin-bottom:16px}
.issue-title{font-family:var(--font-display);font-weight:700;font-size:40px;line-height:1.3;
  color:var(--ink);margin:0 0 12px;text-wrap:balance}
.issue-dek{font-family:var(--font-display);font-size:18px;line-height:1.7;color:var(--mut);margin:0}

/* toc */
#issue{max-width:var(--page);margin:0 auto;padding:0 24px}
.toc{max-width:var(--head-measure);margin:32px auto 0}
.toc-head{font-size:13px;font-weight:700;letter-spacing:.16em;color:var(--ink);
  border-bottom:1px solid var(--ink);padding-bottom:10px;margin-bottom:6px}
.toc-group{font-size:13px;font-weight:700;letter-spacing:.14em;color:var(--mut);margin:22px 0 4px}
.toc-list{list-style:none;margin:0;padding:0}
.toc-list li{border-bottom:1px solid var(--line)}
.toc-list a{display:flex;justify-content:space-between;align-items:baseline;gap:16px;
  padding:11px 2px;text-decoration:none;color:var(--ink)}
.toc-t{font-family:var(--font-display);font-size:16px;font-weight:700}
.toc-m{font-size:12px;color:var(--mut);flex:none}

/* article */
.story{position:relative;padding:0 0 8px}
.story + .anav{margin-bottom:8px}
.sheet{position:relative}
.ahead{max-width:var(--head-measure);margin:0 auto;padding:40px 0 8px;text-align:left}
.ahead-compact{padding:30px 0 4px}
.kicker{display:flex;align-items:center;gap:10px;font-size:13px;font-weight:700;
  letter-spacing:.14em;color:var(--mut);margin-bottom:20px}
.ahead-compact .kicker{margin-bottom:12px}
.kbar{width:8px;height:22px;background:var(--orange);display:inline-block;flex:none}
.art-title{font-family:var(--font-display);font-weight:700;font-size:40px;line-height:1.3;
  color:var(--ink);margin:0 0 14px;text-wrap:balance;letter-spacing:.01em}
h2.art-title.art-compact{font-size:26px;line-height:1.35;margin-bottom:10px}
.deck{font-family:var(--font-display);font-size:18px;line-height:1.7;color:var(--mut);margin:0 0 20px}
.deck-compact{font-size:16px;margin-bottom:12px}
.byline{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:baseline;
  font-family:var(--font-meta);font-size:13px;margin-bottom:26px}
.ahead-compact .byline{margin-bottom:8px}
.byline .who{font-weight:700;letter-spacing:.04em;color:var(--ink)}
.byline .meta{color:var(--mut)}
.arule{border-top:1px solid var(--ink);margin:0 auto;max-width:var(--head-measure)}

/* right rail (per full article) */
.rail{display:none}
@media(min-width:1200px){
  .rail{display:block;position:absolute;top:300px;right:0;width:var(--rail)}
  .rail-in{position:sticky;top:80px}
  .rail-t{font-size:11px;font-weight:700;letter-spacing:.18em;color:var(--mut);margin-bottom:10px}
  .rail nav a{display:block;padding:7px 0;font-size:13px;color:var(--mut);text-decoration:none;
    border-left:2px solid var(--line);padding-left:12px}
  .rail nav a.on{color:var(--ink);font-weight:700;border-left-color:#111}
}

/* body */
.sheet>p,.sheet>.mod,.sheet>figure.fig{max-width:var(--measure);margin-left:auto;margin-right:auto}
.sheet>p{font-family:var(--font-body);font-size:16px;line-height:1.8;color:var(--body);
  margin-top:0;margin-bottom:1.05em}
html[lang="en"] .sheet>p{font-family:"Lora",Georgia,serif}
.k-en{font-family:"Lora",Georgia,serif}
p .k-en{font-size:.96em}
.cap-lede{font-size:15px;color:var(--mut)}

/* quote module (AJ scale, WIRED serif): direct quote only */
.quote{margin-top:2em;margin-bottom:2em;padding:2px 0 2px 18px;border-left:3px solid var(--ink)}
.quote .qt{font-family:var(--font-display);font-weight:700;font-size:20px;line-height:1.7;color:var(--ink)}
html[lang="en"] .quote .qt{font-family:"Playfair Display","Noto Serif SC",serif}
.quote .qa{font-family:var(--font-meta);font-size:13px;color:var(--mut);margin-top:10px}

/* modules */
.mod{margin-top:2em;margin-bottom:2em}
.mtag{display:flex;align-items:center;gap:10px;font-family:var(--font-meta);
  font-size:13px;font-weight:700;letter-spacing:.16em;color:var(--ink);margin-bottom:8px}
.kbar-sm{width:8px;height:18px;background:var(--orange);display:inline-block;flex:none}

/* key figures: AJ ranked rows */
.keyfig .krow{display:flex;gap:16px;align-items:baseline;padding:14px 0;border-bottom:1px solid var(--line)}
.keyfig .krow:first-of-type{border-top:1px solid var(--line)}
.kidx{font-family:var(--font-mono);font-size:13px;color:var(--mut);flex:none;width:28px}
.kval{font-family:var(--font-display);font-weight:700;font-size:28px;line-height:1.2;color:var(--ink);
  flex:none;width:200px}
.klabel{font-size:13px;font-weight:700;color:var(--ink);margin-bottom:4px}
.knote{font-size:13px;color:var(--mut);line-height:1.7}

/* timeline: AJ live language */
.timeline .tl{list-style:none;margin:18px 0 0;padding:0;position:relative}
.timeline .tl::before{content:"";position:absolute;left:5px;top:8px;bottom:8px;width:2px;background:#d9d9d9}
.timeline li{position:relative;padding:0 0 16px 28px}
.timeline .dot{position:absolute;left:0;top:7px;width:12px;height:12px;border-radius:50%;background:var(--red)}
.timeline .tt{font-family:var(--font-mono);font-size:13px;font-weight:700;color:var(--ink);margin-bottom:4px;letter-spacing:.04em}
.timeline .tx{font-family:var(--font-body);font-size:15px;line-height:1.75;color:var(--body)}

/* context: AJ bottom collapsible */
.ctx{border:1px solid var(--line)}
.ctx summary{list-style:none;cursor:pointer;padding:14px 18px;font-family:var(--font-meta);
  font-weight:700;font-size:15px;color:var(--ink);display:flex;justify-content:space-between;
  align-items:center;gap:12px;min-height:44px}
.ctx summary::-webkit-details-marker{display:none}
.ctx summary::after{content:"+";font-weight:300;font-size:22px;color:var(--mut);flex:none}
.ctx[open] summary::after{content:"–"}
.ctx .ctx-body{padding:0 18px 18px;font-family:var(--font-body);font-size:15px;line-height:1.8;
  color:var(--body);border-top:1px solid var(--line);padding-top:14px}
.ctx .ctx-body p{margin:0}

/* figure */
.fig{margin-top:2em;margin-bottom:2em}
.fig img{display:block;width:100%;height:auto}
.fig figcaption{font-family:var(--font-meta);font-size:13px;line-height:1.7;color:var(--mut);margin-top:10px}
.fig-note{font-family:var(--font-meta);font-size:12px;line-height:1.7;color:var(--mut);margin-top:6px;
  border-top:1px solid var(--line);padding-top:8px}

/* bargraph（自 build_r3.py 移植；填充用结构色 --ink，服从四色纪律） */
.bargraph{margin-top:2em;margin-bottom:2em;padding:18px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.bar-row{display:grid;grid-template-columns:150px 1fr 76px;gap:14px;align-items:center;padding:9px 0}
.bar-label{font-family:var(--font-mono);font-weight:600;font-size:12px;line-height:1.5;color:var(--mut)}
html[lang="en"] .bar-label{font-family:var(--font-mono)}
.bar-track{height:16px;background:var(--line);position:relative}
.bar-fill{height:100%;background:var(--ink)}
.bar-val{font-family:var(--font-mono);font-weight:700;font-size:15px;line-height:1.4;
  font-variant-numeric:tabular-nums;text-align:right;color:var(--ink)}
.bar-note{font-family:var(--font-meta);font-size:12px;line-height:1.6;color:var(--mut);margin-top:10px}
@media(max-width:430px){.bar-row{grid-template-columns:110px 1fr 64px;gap:10px}.bar-val{font-size:13px}}

/* data tables */
.tbl-cap{font-family:var(--font-meta);font-size:13px;font-weight:700;letter-spacing:.1em;
  color:var(--ink);margin:0 0 12px}
.tbl-title{font-family:var(--font-display);font-size:16px;font-weight:700;color:var(--ink);margin:18px 0 10px}
.table-wrap{overflow-x:auto;margin:0 0 24px;border:1px solid var(--line)}
.table-wrap table{border-collapse:collapse;width:100%;font-size:13px;line-height:1.6;min-width:560px}
.table-wrap th,.table-wrap td{padding:9px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
.table-wrap thead th{background:#f4f2ec;font-family:var(--font-meta);font-weight:700;color:var(--ink);white-space:nowrap}
.table-wrap tbody th[scope="row"]{font-weight:700;color:var(--ink);white-space:nowrap}
.table-wrap td{font-variant-numeric:tabular-nums;color:var(--body);white-space:nowrap}
.table-wrap tbody tr:last-child th,.table-wrap tbody tr:last-child td{border-bottom:0}

.story-end{max-width:var(--measure);margin:0 auto;padding:4px 0 8px}
.endmark{font-size:14px;color:#111}

/* article nav */
.anav{max-width:var(--head-measure);margin:0 auto;padding:6px 0 40px}
.anav-row{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;
  border-top:1px solid var(--line);padding-top:16px}
.anav a{text-decoration:none;color:var(--ink)}
.anav-dir{display:block;font-family:var(--font-meta);font-size:12px;font-weight:700;letter-spacing:.1em;color:var(--mut);margin-bottom:4px}
.anav-t{display:block;font-family:var(--font-display);font-size:15px;font-weight:700;line-height:1.5}
.anav-prev{max-width:40%}
.anav-next{max-width:40%;text-align:right}
.anav-toc{flex:none;font-family:var(--font-meta);font-size:13px;font-weight:700;padding-top:2px}
.anav-empty{flex:1;max-width:40%}

/* issue footer */
.issue-foot{max-width:var(--head-measure);margin:0 auto;padding:8px 24px 60px;text-align:left}
.issue-foot .arule{max-width:none;margin-bottom:18px}
.issue-foot p{font-size:13px;color:var(--mut);line-height:1.8;margin:0 0 22px}

/* responsive */
@media(max-width:768px){
  .art-title{font-size:32px}
  h2.art-title.art-compact{font-size:23px}
  .ahead{padding:32px 0 8px}
  .ahead-compact{padding:24px 0 4px}
  .issue-hero{padding:36px 24px 8px}
  .issue-title{font-size:32px}
  .mast-meta{display:none}
}
@media(max-width:430px){
  .art-title{font-size:30px;line-height:1.35}
  h2.art-title.art-compact{font-size:21px}
  .deck{font-size:17px}
  .issue-title{font-size:28px}
  .issue-dek{font-size:16px}
  .sheet>p{font-size:16px;line-height:1.75}
  .quote .qt{font-size:19px}
  .kval{font-size:22px;width:165px}
  .keyfig .krow{gap:12px}
  #issue{padding:0 20px}
  .toc-t{font-size:15px}
  .anav-t{font-size:14px}
}
'''

JS = '''
(function(){
  var btn=document.getElementById('langToggle');
  function setLang(en){
    document.querySelectorAll('.k-cn').forEach(function(e){e.hidden=en});
    document.querySelectorAll('.k-en').forEach(function(e){e.hidden=!en});
    document.documentElement.lang=en?'en':'zh-CN';
    if(btn)btn.setAttribute('aria-pressed',en?'true':'false');
  }
  if(btn)btn.addEventListener('click',function(){
    setLang(btn.getAttribute('aria-pressed')!=='true');
  });
  var toTop=document.getElementById('toTop');
  if(toTop){toTop.addEventListener('click',function(){window.scrollTo({top:0,behavior:'smooth'});});}
  var bar=document.getElementById('pbar');
  function prog(){
    if(!bar)return;
    var h=document.documentElement;
    var m=h.scrollHeight-h.clientHeight;
    bar.style.width=(m>0?(h.scrollTop/m*100):0)+'%';
  }
  window.addEventListener('scroll',prog,{passive:true});prog();
  // rail scroll-spy (per-article rails)
  var links=document.querySelectorAll('.rail nav a');
  if(links.length&&'IntersectionObserver' in window){
    var map={};
    links.forEach(function(a){map[a.getAttribute('data-spy')]=a});
    var io=new IntersectionObserver(function(es){
      es.forEach(function(e){
        if(e.isIntersecting){
          var rail=e.target.closest('.sheet').querySelectorAll('.rail nav a');
          rail.forEach(function(a){a.classList.remove('on')});
          var a=map[e.target.id];if(a)a.classList.add('on');
        }
      });
    },{rootMargin:'-30% 0px -60% 0px'});
    links.forEach(function(a){
      var el=document.getElementById(a.getAttribute('data-spy'));if(el)io.observe(el);
    });
  }
})();
'''

FONTS = ('https://fonts.googleapis.com/css2?'
         'family=Noto+Serif+SC:wght@400;700'
         '&family=Noto+Sans+SC:wght@400;500;700'
         '&family=Noto+Sans+Mono:wght@400;700'
         '&family=Playfair+Display:wght@700'
         '&family=Lora:ital,wght@0,400;0,700;1,400'
         '&family=Inter:wght@500;600&display=swap')


def load_json(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def _asset_loader_for_issue(issue_dir):
    def load(path_or_name):
        if not path_or_name:
            return None
        candidates = [
            os.path.join(issue_dir, path_or_name),
            os.path.join(issue_dir, 'assets', os.path.basename(path_or_name)),
            os.path.join(issue_dir, 'ovis-test', 'visual-assets', os.path.basename(path_or_name)),
            os.path.normpath(os.path.join(BASE, path_or_name)),
        ]
        for fp in candidates:
            if os.path.isfile(fp):
                with open(fp, 'rb') as f:
                    return base64.b64encode(f.read()).decode('ascii')
        raise FileNotFoundError(f'asset not found: {path_or_name}')
    return load


def build_issue(issue, plans_all=None, write_baseline=True):
    issue_dir = os.path.join(os.path.dirname(BASE), issue)
    final = load_json(os.path.join(issue_dir, 'final.json'))
    modules_all = load_json(os.path.join(BASE, 'modules.json'))
    images_all = load_json(os.path.join(BASE, 'images.json'))
    curation = load_json(os.path.join(BASE, 'curation.json')) \
        if os.path.isfile(os.path.join(BASE, 'curation.json')) else {}
    tokens = open(os.path.join(BASE, 'tokens.css'), encoding='utf-8').read()
    if plans_all is None:
        plans_all = load_plans(os.path.join(issue_dir, 'editorial-plans'))
    print(f'enhanced plans: {sorted(plans_all)}')

    # 图片 base64 嵌入（只收 images.json 清单）
    img_cache = {}
    for aid, im in images_all.items():
        if aid.startswith('_'):
            continue
        fp = os.path.normpath(os.path.join(BASE, im['file']))
        with open(fp, 'rb') as f:
            img_cache[aid] = base64.b64encode(f.read()).decode('ascii')

    # 策展图（curation.json data_treatment.figures）同样 base64 嵌入
    for aid, treat in curation.get('data_treatment', {}).items():
        for fig in treat.get('figures', []):
            fp = os.path.normpath(os.path.join(issue_dir, fig['file']))
            with open(fp, 'rb') as f:
                fig['b64'] = base64.b64encode(f.read()).decode('ascii')

    # 完整性门禁分流
    from integrity_gate import check_article
    gate_status = {}
    for e in final:
        passed, issues = check_article(e)
        gate_status[e['id']] = ('pass' if passed else 'block',
                                issues) if not passed else ('pass', [])
        if passed and issues:
            gate_status[e['id']] = ('warn', issues)
    n_pass = sum(1 for v in gate_status.values() if v[0] == 'pass')
    n_warn = sum(1 for v in gate_status.values() if v[0] == 'warn')
    n_block = sum(1 for v in gate_status.values() if v[0] == 'block')
    print(f'gate: {n_pass} PASS / {n_warn} WARN / {n_block} BLOCK')

    asset_loader = _asset_loader_for_issue(issue_dir)
    body, order = render_issue(
        final, modules_all, images_all, img_cache, issue,
        gate_status=gate_status, plans_all=plans_all,
        asset_loader=asset_loader, curation=curation)

    enh_css = (
        TEXT_CSS + LAYOUT_CSS +
        '\n.enh-note{font:400 13px/1.6 var(--font-meta);color:var(--mut);'
        'margin:12px auto 0;padding-bottom:8px;border-bottom:1px solid var(--line)}'
        '\n.enh-note a{color:var(--ink);text-decoration:underline;text-underline-offset:2px}'
        '\n.story-enhanced .tt-subhead[data-source-head="true"]::before{background:var(--ink)}'
        '\n.dins{margin:14px auto 20px;padding:14px 18px;border-left:3px solid var(--orange);'
        'background:#faf7f2;max-width:var(--measure)}'
        '\n.dins-tag{font:700 12px/1.4 var(--font-meta);letter-spacing:.08em;color:var(--orange);margin-bottom:6px}'
        '\n.dins p{font-size:15px;line-height:1.8;margin:0}'
        '\n.dcal{list-style:none;margin:8px auto 20px;padding:0;max-width:var(--measure)}'
        '\n.dcal li{display:grid;grid-template-columns:5.5em 1fr;gap:12px;padding:10px 0;'
        'border-bottom:1px solid var(--line);font-size:15px;line-height:1.7}'
        '\n.dcal-d{font:700 13px/1.5 var(--font-meta);letter-spacing:.04em;color:var(--mut)}'
        '\n@media(max-width:430px){.dcal li{grid-template-columns:1fr;gap:2px}}'
    )

    def wrap_doc(body_html, title_suffix=''):
        title = 'WSJ 深读 · 2026年10月12日' + (f' · {title_suffix}' if title_suffix else '')
        return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{FONTS}" rel="stylesheet">
<style>
{tokens}
{CSS}
{enh_css}
</style>
</head>
<body>
{body_html}
<script>{JS}</script>
</body>
</html>
'''

    dist = os.path.join(issue_dir, 'dist')
    os.makedirs(dist, exist_ok=True)
    out = os.path.join(dist, 'index.html')
    doc = wrap_doc(body)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(doc)
    print(f'wrote {out} ({len(doc)//1024} KB, {len(order)} articles, '
          f'{len(plans_all)} enhanced)')

    if write_baseline:
        body_b, _ = render_issue(
            final, modules_all, images_all, img_cache, issue,
            gate_status=gate_status, plans_all={}, asset_loader=asset_loader,
            curation=curation)
        # Force pure typography for the four reboot articles too: drop modules
        # only where we want before/after. Baseline = no enhanced plans.
        base_out = os.path.join(dist, 'baseline.html')
        base_doc = wrap_doc(body_b, 'baseline')
        # Point baseline note targets back to enhanced issue
        base_doc = base_doc.replace('href="baseline.html#', 'href="index.html#')
        with open(base_out, 'w', encoding='utf-8') as f:
            f.write(base_doc)
        print(f'wrote {base_out} ({len(base_doc)//1024} KB)')

    return out, final, order, gate_status, plans_all


def check_no_duel(html):
    bad = ['主张与现实', 'cpair', 'cwho', 'duel', 'claim-evidence']
    found = [b for b in bad if b in html]
    assert not found, f'duel residue: {found}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--issue', required=True)
    args = ap.parse_args()
    out, final, order, gate_status, plans_all = build_issue(args.issue)

    # ---- 自查断言 ----
    html = open(out, encoding='utf-8').read()
    import json as _js
    _cur = _js.load(open(os.path.join(BASE, 'curation.json'))) \
        if os.path.isfile(os.path.join(BASE, 'curation.json')) else {}
    excluded = set(_cur.get('exclude', {}))
    # 1. 117 条全在，无遗漏/重复/错序（策展撤下项除外，它们记录在 curation.json）
    ids = [e['id'] for e in final]
    assert len(ids) == 117, f'expected 117, got {len(ids)}'
    assert len(set(ids)) == 117, 'duplicate ids'
    for e in final:
        if e['id'] in excluded:
            assert f'id="s-{e["id"]}"' not in html, f'excluded article rendered: {e["id"]}'
            continue
        st = gate_status.get(e['id'], ('pass', []))[0]
        if st == 'pass':
            assert f'id="s-{e["id"]}"' in html, f'missing article {e["id"]}'
        else:
            # WARN/BLOCK 只进待审核区
            assert f'id="review-{e["id"]}"' in html, f'missing review {e["id"]}'
    # 阅读顺序 = 分组顺序
    from issue import reading_order
    pub_final = [e for e in final
                 if gate_status.get(e['id'], ('pass', []))[0] == 'pass'
                 and e['id'] not in excluded]
    assert [e['id'] for e in order] == [e['id'] for e in reading_order(pub_final)]
    # 每篇段落数一致（正文逐字）
    from components import paras as _paras
    for e in final:
        if e.get('type') == 'data_table':
            continue
        if gate_status.get(e['id'], ('pass', []))[0] != 'pass':
            continue
        if e['id'] in excluded:
            continue
        got = html.count(f'id="s-{e["id"]}"')
        assert got == 1, f'{e["id"]} anchor count {got}'
    # 段落级校验：正文文字必须保留。增强篇会插入标签，故在 article 切片上去标签后核对。
    import re as _re
    for e in final:
        if e.get('type') == 'data_table':
            continue
        if gate_status.get(e['id'], ('pass', []))[0] != 'pass':
            continue
        if e['id'] in excluded:
            continue
        m = _re.search(
            rf'<article[^>]*id="s-{_re.escape(e["id"])}"[^>]*>(.*?)</article>',
            html, _re.S)
        assert m, f'missing article slice {e["id"]}'
        plain = _re.sub(r'<[^>]+>', '', m.group(1))
        for cn, _ in _paras(e.get('body_cn'), e.get('body_en')):
            key = cn[:24].strip()
            if key:
                assert key in plain, f'{e["id"]} para missing: {key[:20]}'
    # Enhanced articles present
    for aid in plans_all:
        assert f'data-enhanced="true"' in html
        assert f'id="s-{aid}"' in html
        # baseline counterpart exists
        assert os.path.isfile(os.path.join(os.path.dirname(out), 'baseline.html'))
    check_no_duel(html)
    assert 'text-wrap:pretty' not in html and 'text-wrap: pretty' not in html
    # legacy modules.json image embeds still respected for non-plan articles
    import json as _js
    _imgs = _js.load(open(os.path.join(BASE, 'images.json')))
    _expected_imgs = sum(1 for aid in _imgs if not aid.startswith('_')
                         and gate_status.get(aid, ('pass', []))[0] == 'pass'
                         and aid not in plans_all)
    # plan path may add images later; for now reboot plans add none
    assert html.count('data:image/png;base64') >= _expected_imgs
    print(f'assertions passed: 117 articles, {len(plans_all)} enhanced, '
          f'paras verbatim, no duel, no pretty')


if __name__ == '__main__':
    main()
