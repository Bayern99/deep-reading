#!/usr/bin/env python3
"""WSJ 深读 · 共享组件（AJ × WIRED v1.0）
样式类名与 reference/hybrid-v3 一致；内容逐字来自 final.json / modules.json / images.json。
铁律：绝不自动生成模块内容；"主张与现实"对照模块永不出现。
"""
import html
import re


def esc(s):
    return html.escape(s or '', quote=True).replace('&#x27;', "'")


def pair(cn, en, tag='p', cls=''):
    """中英 1:1 段落"""
    c = f' class="{cls}"' if cls else ''
    return (f'<{tag}{c}><span class="k-cn">{esc(cn)}</span>'
            f'<span class="k-en" hidden>{esc(en)}</span></{tag}>')


def paras(cn_text, en_text):
    """正文按 \n\n 分段，逐字返回 [(cn, en)]"""
    cps = (cn_text or '').split('\n\n')
    eps = (en_text or '').split('\n\n')
    out = []
    for i, cp in enumerate(cps):
        ep = eps[i] if i < len(eps) else ''
        out.append((cp, ep))
    return out


PRI_LABEL = {'P1': 'P1 必读', 'P2': 'P2', 'P3': 'P3'}


def kicker_text(e):
    bits = []
    if e.get('section'):
        bits.append(e['section'])
    if e.get('page'):
        bits.append(e['page'] + ' 版')
    bits.append(PRI_LABEL.get(e.get('priority'), e.get('priority') or ''))
    if e.get('type') == 'opinion':
        bits.append('观点')
    if e.get('type') == 'letter':
        bits.append('读者来信')
    return ' · '.join(b for b in bits if b)


def article_header(e):
    """完整文章头：kicker / h1 / deck / byline / rule"""
    h = [f'''<header class="ahead">
    <div class="kicker"><span class="kbar"></span><span class="k-cn">{esc(kicker_text(e))}</span><span class="k-en" hidden>{esc(kicker_text(e))}</span></div>
    <h2 class="art-title"><span class="k-cn">{esc(e.get('title_cn'))}</span><span class="k-en" hidden>{esc(e.get('title'))}</span></h2>''']
    if e.get('dek_cn') or e.get('dek'):
        h.append(f'''<p class="deck"><span class="k-cn">{esc(e.get('dek_cn'))}</span><span class="k-en" hidden>{esc(e.get('dek'))}</span></p>''')
    if e.get('byline'):
        h.append(f'''<div class="byline">
      <span class="who">{esc(e.get('byline'))}</span>
      <span class="meta k-cn">2026年10月12日 · 《华尔街日报》{esc(e.get('page') or '')} 版</span>
      <span class="meta k-en" hidden>Oct 12, 2026 · The Wall Street Journal, p.{esc(e.get('page') or '')}</span>
    </div>''')
    h.append('</header>\n  <div class="arule"></div>')
    return '\n'.join(h)


def body_paras(e):
    return [pair(cn, en) for cn, en in paras(e.get('body_cn'), e.get('body_en'))]


def key_figures(items, uid):
    """AJ ranked 条目；数值列固定宽度保证标签对齐"""
    kf = [f'<section id="keyfig-{uid}" class="mod keyfig" aria-label="关键数字">']
    kf.append('<div class="mtag"><span class="k-cn">关键数字</span><span class="k-en" hidden>KEY FIGURES</span></div>')
    for i, s in enumerate(items):
        kf.append(f'''<div class="krow">
      <div class="kidx">{i+1:02d}</div>
      <div class="kval"><span class="k-cn">{esc(s['value_cn'])}</span><span class="k-en" hidden>{esc(s['value_en'])}</span></div>
      <div class="kbody">
        <div class="klabel"><span class="k-cn">{esc(s['label_cn'])}</span><span class="k-en" hidden>{esc(s['label_en'])}</span></div>
        <div class="knote"><span class="k-cn">{esc(s['note_cn'])}</span><span class="k-en" hidden>{esc(s['note_en'])}</span></div>
      </div>
    </div>''')
    kf.append('</section>')
    return '\n'.join(kf)


def timeline(tl, uid):
    """AJ live 语言：红圆点 + 银灰竖轨 + mono 时间戳"""
    t = [f'<section id="timeline-{uid}" class="mod timeline" aria-label="时间线">']
    t.append(f'''<div class="mtag"><span class="kbar-sm"></span><span class="k-cn">{esc(tl.get('title_cn') or '时间线')}</span><span class="k-en" hidden>{esc(tl.get('title_en') or 'TIMELINE')}</span></div>''')
    t.append('<ol class="tl">')
    for e in tl.get('entries', []):
        t.append(f'''<li>
      <span class="dot" aria-hidden="true"></span>
      <div class="tt"><span class="k-cn">{esc(e['t_cn'])}</span><span class="k-en" hidden>{esc(e['t_en'])}</span></div>
      <div class="tx"><span class="k-cn">{esc(e['text_cn'])}</span><span class="k-en" hidden>{esc(e['text_en'])}</span></div>
    </li>''')
    t.append('</ol></section>')
    return '\n'.join(t)


def quote(q):
    """只取直接引语一句；人物介绍/叙述留在正文"""
    qt_cn = (q['text_cn'] or '').strip('“”"')
    qt_en = (q['text_en'] or '').strip('"“”')
    return f'''<aside class="mod quote" aria-label="引语">
    <div class="qt"><span class="k-cn">{esc(qt_cn)}</span><span class="k-en" hidden>{esc(qt_en)}</span></div>
    <div class="qa"><span class="k-cn">{esc(q['attr_cn'])}</span><span class="k-en" hidden>{esc(q['attr_en'])}</span></div>
  </aside>'''


def rail(uid, items):
    """per-article 右 rail（≥1200px）；items: [(anchor_id, cn, en)]"""
    if not items:
        return ''
    links = '\n'.join(
        f'<a href="#{aid}" data-spy="{aid}"><span class="k-cn">{esc(cn)}</span><span class="k-en" hidden>{esc(en)}</span></a>'
        for aid, cn, en in items)
    return f'''<aside class="rail" aria-label="rail">
    <div class="rail-in">
      <div class="rail-t"><span class="k-cn">\u672c\u7bc7</span><span class="k-en" hidden>IN THIS STORY</span></div>
      <nav>{links}</nav>
    </div>
  </aside>'''


def context_box(context_cn, uid):
    """底部折叠（AJ 原型式样），默认收起；无英文版时保留中文原文"""
    if not (context_cn or '').strip():
        return ''
    return f'''<details id="context-{uid}" class="mod ctx">
    <summary><span class="k-cn">背景资料</span><span class="k-en" hidden>BACKGROUND</span></summary>
    <div class="ctx-body"><p lang="zh-CN">{esc(context_cn)}</p></div>
  </details>'''


def figure(img_b64, caption_cn, caption_en, credit, uid):
    """已验证真实图片（base64 嵌入）+ 图注。credit 为空/unknown 时不渲染，不许编造。"""
    cr = (credit or '').strip()
    cr_cn = f'（{esc(cr)}）' if cr and cr.lower() not in ('unknown', '未知') else ''
    cr_en = f' ({esc(cr)})' if cr and cr.lower() not in ('unknown', '未知') else ''
    return f'''<figure id="fig-{uid}" class="mod fig">
    <img src="data:image/png;base64,{img_b64}" alt="{esc(caption_cn)}">
    <figcaption><span class="k-cn">{esc(caption_cn)}{cr_cn}</span><span class="k-en" hidden>{esc(caption_en)}{cr_en}</span></figcaption>
  </figure>'''


_NUM_RE = re.compile(r'^[\d\s.,$%▲▼↑↓+\-–()\'’/]+$')


def _is_header_row(cells):
    return cells and not any(_NUM_RE.match(c.strip()) for c in cells if c.strip())


def data_table(body_en):
    """真表格：按 | 切分行列；换行断裂的行标签自动合并；不编造列头"""
    blocks = (body_en or '').split('\n\n')
    out = []
    for block in blocks:
        lines = [ln.strip() for ln in block.split('\n') if ln.strip()]
        # 合并被换行断开的行标签（无 | 的行并入下一含 | 行）
        merged = []
        i = 0
        while i < len(lines):
            ln = lines[i]
            if '|' not in ln and i + 1 < len(lines) and '|' in lines[i + 1]:
                merged.append(ln + ' ' + lines[i + 1])
                i += 2
            else:
                merged.append(ln)
                i += 1
        rows = [ln for ln in merged if '|' in ln]
        titles = [ln for ln in merged if '|' not in ln]
        for tl in titles:
            out.append(f'<p class="tbl-title">{esc(tl)}</p>')
        if not rows:
            continue
        cells0 = [c.strip() for c in rows[0].split('|')]
        body_rows = rows[1:] if _is_header_row(cells0) else rows
        t = ['<div class="table-wrap"><table>']
        if body_rows is not rows:
            t.append('<thead><tr>' + ''.join(f'<th scope="col">{esc(c)}</th>' for c in cells0) + '</tr></thead>')
        t.append('<tbody>')
        for r in body_rows:
            cells = [c.strip() for c in r.split('|')]
            t.append('<tr><th scope="row">' + esc(cells[0]) + '</th>' +
                     ''.join(f'<td>{esc(c)}</td>' for c in cells[1:]) + '</tr>')
        t.append('</tbody></table></div>')
        out.append('\n'.join(t))
    return '\n'.join(out)


# ---------- 从 build_r3.py 移植的渲染原语（样式已适配 AJ×WIRED token） ----------

def bargraph(title_cn, title_en, bars, note_cn='', note_en='', uid=''):
    """横向柱状图：bars=[(label_cn,label_en,value_cn,value_en,pct)]。
    移植自 build_r3.py::bargraph；填充色改用 --ink（结构色），服从四色纪律。"""
    rows = []
    for lc, le, v_cn, v_en, pct in bars:
        rows.append(f'''<div class="bar-row">
      <div class="bar-label"><span class="k-cn">{esc(lc)}</span><span class="k-en" hidden>{esc(le)}</span></div>
      <div class="bar-track"><div class="bar-fill" style="width:{pct}%"></div></div>
      <div class="bar-val"><span class="k-cn">{esc(v_cn)}</span><span class="k-en" hidden>{esc(v_en)}</span></div>
    </div>''')
    note = (f'<div class="bar-note"><span class="k-cn">{esc(note_cn)}</span>'
            f'<span class="k-en" hidden>{esc(note_en)}</span></div>') if note_cn else ''
    return f'''<section id="bargraph-{uid}" class="mod bargraph" aria-label="图表">
    <div class="mtag"><span class="kbar-sm"></span><span class="k-cn">{esc(title_cn)}</span><span class="k-en" hidden>{esc(title_en)}</span></div>
    {chr(10).join(rows)}
    {note}
  </section>'''


def chart(img_b64, caption_cn, caption_en, source_note, uid):
    """图表：原报图表的高清裁图 + 图注 + 数据来源行。OCR 识别出的图表文字不等于图表本身——图必须保留。"""
    sn = (source_note or '').strip()
    sn_body = re.sub(r'(?i)^source\s*:\s*', '', sn)
    sn_cn = sn if sn.startswith('数据来源') else f'数据来源：{sn_body}'
    sn_en = sn if re.match(r'(?i)^source\s*:', sn) else f'Source: {sn}'
    return f'''<figure id="chart-{uid}" class="mod fig chart">
    <img src="data:image/png;base64,{img_b64}" alt="{esc(caption_cn)}">
    <figcaption><span class="k-cn">{esc(caption_cn)}</span><span class="k-en" hidden>{esc(caption_en)}</span></figcaption>
    <div class="fig-note"><span class="k-cn">{esc(sn_cn)}</span><span class="k-en" hidden>{esc(sn_en)}</span></div>
  </figure>'''


def infographic(img_b64, caption_cn, caption_en, data_note, uid):
    """信息图：原报信息图整体保留 + 说明文字 + 数据口径注。"""
    return f'''<figure id="infographic-{uid}" class="mod fig infographic">
    <img src="data:image/png;base64,{img_b64}" alt="{esc(caption_cn)}">
    <figcaption><span class="k-cn">{esc(caption_cn)}</span><span class="k-en" hidden>{esc(caption_en)}</span></figcaption>
    <div class="fig-note"><span class="k-cn">{esc(data_note)}</span><span class="k-en" hidden>{esc(data_note)}</span></div>
  </figure>'''


# ---------- 组件注册表 ----------
# 名称 → 需要的数据 / 用途。Plan 的 component 字段只能取这里的 key。
COMPONENT_REGISTRY = {
    'key_figures': {
        'needs': 'condensed 数据点列表（value/label/note，中英），来自 Plan data 或 data_ref',
        'purpose': '导语后的数据总览；只收 condensed 数据点，不复述正文句子',
        'fn': key_figures,
    },
    'timeline': {
        'needs': '时间线条目（t/text，中英），来自 Plan data 或 data_ref',
        'purpose': '提供叙事顺序之外的编年视角；单句 condensed',
        'fn': timeline,
    },
    'quote': {
        'needs': '直接引语一句 + 署名，来自 Plan data 或 data_ref',
        'purpose': '人物观点点题；人物介绍与叙述留在正文',
        'fn': quote,
    },
    'context_box': {
        'needs': 'context_cn（final.json）',
        'purpose': '背景资料，底部折叠，不打断叙事',
        'fn': context_box,
    },
    'figure': {
        'needs': '已验证真实图片（base64）+ 图注 + 来源',
        'purpose': '新闻照片及图注',
        'fn': figure,
    },
    'chart': {
        'needs': '原报图表裁图（base64）+ 图注 + 数据来源',
        'purpose': '金融图表等数据图形的原始视觉表达',
        'fn': chart,
    },
    'infographic': {
        'needs': '原报信息图裁图（base64）+ 说明 + 数据口径注',
        'purpose': '信息图的原始视觉表达整体保留',
        'fn': infographic,
    },
    'bargraph': {
        'needs': 'bars=[(label,value,pct)]，数据逐字来自正文',
        'purpose': '两组可比数据的等比横向对比',
        'fn': bargraph,
    },
    'data_table': {
        'needs': '| 分隔的源文本',
        'purpose': '真数据表格，移动端横滑',
        'fn': data_table,
    },
}
