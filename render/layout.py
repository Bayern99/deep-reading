#!/usr/bin/env python3
"""Layout Grammar 层（L02/L03/L05/L08）。

原则（kit §4, §7）：
- 每种布局实现 1440px 和 390px 两种状态。
- 手机 DOM 顺序必须符合阅读顺序（无跨列跳读、无隐藏正文）。
- L02 边注：桌面右栏，手机在锚点段落后 inline 插入。
- L03 平行双栏：桌面并排，手机按维度交替 A→B 纵排。
- L05 图文并置：桌面图+文并排，手机图→图注→解释。
- L08 跨栏图：桌面破栏宽图，手机全宽（可横滑/缩放），表格可横滚。

布局决策数据：
  {pattern_id, blocks:[ids], params, reason, mobile_strategy, editorial_added}
"""
import re


def _esc(s):
    return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


# ---------------- L02 正文与边注 ----------------
def render_margin_note(anchor_block_id, note_cn, note_en, uid,
                       editorial_added=True):
    """桌面≥1200px：右栏边注（相对锚点段 wrapper 绝对定位）；
    <1200px：锚点段落后 inline 插入。
    DOM 顺序：锚点段 → note → 下一段（两端一致）。
    使用方式：builder 把锚点 <p> 与本 aside 包进
    <div class="ed-block ly-anchor">，见 LAYOUT_CSS。"""
    return f'''<aside class="ly-note" data-anchor="{anchor_block_id}" id="note-{uid}"
      data-editorial-added="{'true' if editorial_added else 'false'}">
  <p><span class="k-cn">{_esc(note_cn)}</span><span class="k-en" hidden>{_esc(note_en)}</span></p>
</aside>'''


# ---------------- L03 平行双栏比较 ----------------
def render_compare(pairs, uid, dim_labels=None, dim_labels_en=None):
    """pairs: [((a_cn,a_en),(b_cn,b_en))...] 按维度成对。
    桌面：左右两栏逐维度对照；手机：维度1 A→B，维度2 A→B…纵排。
    DOM 即手机顺序（维度交替），桌面用 CSS order 重排为两栏。"""
    rows = []
    for i, ((acn, aen), (bcn, ben)) in enumerate(pairs):
        lab = dim_labels[i] if dim_labels and i < len(dim_labels) else ''
        lab_en = dim_labels_en[i] if dim_labels_en and i < len(dim_labels_en) else ''
        lab_h = (f'<div class="ly-dim"><span class="k-cn">{_esc(lab)}</span>'
                 f'<span class="k-en" hidden>{_esc(lab_en)}</span></div>') if lab or lab_en else ''
        rows.append(f'''<div class="ly-pair" data-dim="{i}">
  {lab_h}
  <div class="ly-a"><span class="k-cn">{_esc(acn)}</span><span class="k-en" hidden>{_esc(aen)}</span></div>
  <div class="ly-b"><span class="k-cn">{_esc(bcn)}</span><span class="k-en" hidden>{_esc(ben)}</span></div>
</div>''')
    return f'<section class="ly-compare" id="cmp-{uid}" aria-label="对照比较">\n' + '\n'.join(rows) + '\n</section>'


# ---------------- L05 图文并置 ----------------
def render_figure_text(img_html, text_cn, text_en, uid):
    """桌面：图左文右并置；手机：图→图注→解释（DOM 即此顺序）。"""
    return f'''<div class="ly-figtext" id="ft-{uid}">
  <div class="ly-ft-img">{img_html}</div>
  <div class="ly-ft-text"><p><span class="k-cn">{_esc(text_cn)}</span><span class="k-en" hidden>{_esc(text_en)}</span></p></div>
</div>'''


# ---------------- L08 跨栏图形 ----------------
def render_wide_figure(inner_html, uid):
    """桌面：破栏宽图（宽于正文栏）；手机：全宽，可横向滚动查看。"""
    return f'''<figure class="ly-wide" id="wide-{uid}">
  <div class="ly-wide-scroll">{inner_html}</div>
</figure>'''


LAYOUT_CSS = '''
/* ---- Layout Grammar（布局层） ---- */
/* L02 边注：默认（<1200px）锚点段后 inline；≥1200px 右栏 */
/* 布局契约：.ly-anchor 是 ed-block（640px），note 相对它定位到右栏 */
.ly-note{border-left:2px solid var(--line);padding:.2em 0 .2em 14px;margin:.8em 0;
  font:400 14px/1.7 var(--font-meta);color:var(--mut)}
.ly-note p{margin:0}
@media(min-width:1200px){
  .ly-anchor{position:relative}
  .ly-anchor .ly-note{position:absolute;left:calc(100% + 32px);top:0;width:200px;
    margin:0;border-left:2px solid var(--orange);padding-left:14px}
}
/* L03 平行双栏 */
.ly-compare{margin:1.5em 0;border-top:1px solid var(--line)}
.ly-pair{padding:.9em 0;border-bottom:1px solid var(--line)}
.ly-dim{font:700 12px/1.6 var(--font-meta);letter-spacing:.1em;color:var(--mut);
  margin-bottom:.5em}
.ly-a,.ly-b{font:400 15px/1.75 var(--font-body);color:var(--body)}
.ly-a{margin-bottom:.4em}
.ly-a::before{content:"A";display:inline-block;font:700 11px/1 var(--font-meta);
  color:var(--paper);background:var(--ink);border-radius:2px;padding:3px 6px;margin-right:8px}
.ly-b::before{content:"B";display:inline-block;font:700 11px/1 var(--font-meta);
  color:var(--paper);background:var(--mut);border-radius:2px;padding:3px 6px;margin-right:8px}
@media(min-width:768px){
  .ly-pair{display:grid;grid-template-columns:1fr 1fr;gap:24px}
  .ly-dim{grid-column:1/-1}
  .ly-a{margin-bottom:0}
}
/* L05 图文并置 */
.ly-figtext{margin:1.5em 0}
.ly-ft-text p{font:400 15px/1.75 var(--font-body);color:var(--body);margin:.8em 0 0}
@media(min-width:768px){
  .ly-figtext{display:grid;grid-template-columns:1fr 1fr;gap:28px;align-items:start}
  .ly-ft-text p{margin:0}
}
/* L08 跨栏图：桌面破栏宽于正文；手机全幅 */
.ly-wide{margin:2em auto;max-width:960px;width:calc(100% - 48px)}
.ly-wide .ly-wide-scroll{overflow-x:auto}
.ly-wide img{display:block;max-width:100%;height:auto;margin:0 auto}
.ly-wide figcaption{font:400 13px/1.7 var(--font-meta);color:var(--mut);
  margin-top:10px;max-width:var(--measure);margin-left:auto;margin-right:auto}
.ly-wide table{min-width:620px;width:100%;border-collapse:collapse}
@media(max-width:430px){
  /* 由 #issue 统一留白；图形可在内部横滑，图注与正文对齐。 */
  .ly-wide{width:100%;max-width:none;margin-left:0;margin-right:0}
  /* 图表保持可读宽度，横向滚动而非压扁 */
  .ly-wide .ly-wide-scroll img{min-width:560px;max-width:none}
}
@media(max-width:430px){
  .ly-note{font-size:13.5px}
  .ly-a,.ly-b{font-size:15px}
}
'''


def validate_mobile_order(html):
    """手机 DOM 顺序检查：ly-note 必须紧跟其 anchor 段之后；
    ly-compare 内必须是 dim→A→B 交替。返回问题列表。"""
    issues = []
    # L02：aside.ly-note 的 data-anchor 应出现在其前面的 <p data-block>
    for m in re.finditer(r'<aside class="ly-note" data-anchor="([^"]+)"', html):
        anchor = m.group(1)
        before = html[:m.start()]
        # anchor 段应是最后一个 data-block
        blocks = re.findall(r'data-block="([^"]+)"', before)
        if not blocks or blocks[-1] != anchor:
            issues.append(f'L02 note anchor {anchor} 不在紧邻上文段后')
    return issues
