#!/usr/bin/env python3
"""Text Treatment 层（T01/T03/T06/T07/T09/T10/T11/T13/T17）。

原则（kit §3, §8）：
- 只读源：所有操作引用 (block_id, locale, start, end, text_exact)，渲染前过 source exact match。
- T07 限定词保护：T01 加粗不得丢"可能/据称/预计/大约"等限定词——自动扩展 range。
- T09/T13 可逆：拆分/列表化后拼回原文必须逐字一致（含标点引号数字）。
- T11/T18 类新增文字标 editorial_added=true。
- 接受零处理输出：无候选时返回空操作列表。

操作渲染为行内 HTML：
- T01: <strong class="tt-b"> | T03: <span class="tt-num"> | T06: <span class="tt-attr">
- T09: 段落拆分为两个 <p>（可逆） | T10: <div class="tt-group"> 包裹
- T11: <h3 class="tt-subhead" data-editorial-added="true">
- T13: <ul class="tt-list"><li>（可逆） | T17: <span class="tt-mix"> 包裹拉丁/数字 run
"""
import re

# T07 限定词表（加粗时必须包含，不得截断丢弃）
QUALIFIERS = ['可能', '据称', '预计', '大约', '或许', '似乎', '有望', '声称',
              '表示', '认为', '估计', '大概', '将近', '接近', 'allegedly',
              'reportedly', 'likely', 'expected', 'about', 'around', 'may',
              'might', 'could']

# 中文句边界（T09 拆分用）
SENT_END = re.compile(r'([。！？…]+[""」』]?)\s*')


def _find_range(text, snippet):
    i = text.find(snippet)
    return (i, i + len(snippet)) if i >= 0 else None


class TextOp:
    def __init__(self, pattern_id, block_id, locale, text_exact,
                 action='wrap', params=None, editorial_added=False,
                 reason=''):
        self.pattern_id = pattern_id
        self.block_id = block_id
        self.locale = locale
        self.text_exact = text_exact
        self.action = action            # wrap | split | group | subhead | list | mix
        self.params = params or {}
        self.editorial_added = editorial_added
        self.reason = reason

    def to_dict(self):
        return {
            'pattern_id': self.pattern_id,
            'block_id': self.block_id,
            'locale': self.locale,
            'text_exact': self.text_exact,
            'action': self.action,
            'params': self.params,
            'editorial_added': self.editorial_added,
            'reason': self.reason,
        }


def _expand_qualifiers(text, start, end):
    """T07：向左右扩展，把紧贴的限定词纳入 range。"""
    # 向左找限定词（限定词+标点紧贴选中区开头）
    left = text[:start]
    for q in QUALIFIERS:
        if left.endswith(q) or left.rstrip('，。、：； ').endswith(q):
            ns = left.rfind(q)
            if ns >= 0 and start - (ns + len(q)) <= 2:
                start = ns
    return start, end


def op_bold(sm, block_id, locale, snippet, reason=''):
    """T01 语义加粗（含 T07 限定词保护）。"""
    text = sm.get_text(block_id, locale)
    rng = _find_range(text, snippet)
    if not rng:
        raise ValueError(f'T01 exact match failed: {snippet[:40]}')
    s, e = _expand_qualifiers(text, *rng)
    return TextOp('T01', block_id, locale, text[s:e], reason=reason)


def op_number(sm, block_id, locale, snippet, reason=''):
    """T03 数值内联强调：数字+单位整体。"""
    text = sm.get_text(block_id, locale)
    rng = _find_range(text, snippet)
    if not rng:
        raise ValueError(f'T03 exact match failed: {snippet[:40]}')
    return TextOp('T03', block_id, locale, snippet, reason=reason)


def op_attribution(sm, block_id, locale, snippet, reason=''):
    """T06 引述归属标识：标记说话者/说话动词。"""
    text = sm.get_text(block_id, locale)
    rng = _find_range(text, snippet)
    if not rng:
        raise ValueError(f'T06 exact match failed: {snippet[:40]}')
    return TextOp('T06', block_id, locale, snippet, reason=reason)


def op_split(sm, block_id, locale, after_sentence_idx=0, reason=''):
    """T09 段落拆分：在第 N 个句边界处拆分；返回 op，可逆验证由渲染器执行。"""
    text = sm.get_text(block_id, locale)
    bounds = [m.end() for m in SENT_END.finditer(text)]
    if after_sentence_idx >= len(bounds):
        raise ValueError('T09: 句边界不足')
    cut = bounds[after_sentence_idx]
    return TextOp('T09', block_id, locale, text,
                  action='split', params={'cut': cut}, reason=reason)


def op_group(block_ids, reason=''):
    """T10 段落分组留白：一组连续段落。"""
    return TextOp('T10', block_ids[0], 'cn', '',
                  action='group', params={'blocks': block_ids}, reason=reason)


def op_subhead(before_block_id, title_cn, title_en='', reason=''):
    """T11 增补编辑小标题：editorial_added=true。"""
    return TextOp('T11', before_block_id, 'cn', title_cn,
                  action='subhead',
                  params={'title_cn': title_cn, 'title_en': title_en},
                  editorial_added=True, reason=reason)


def op_list(sm, block_id, locale, item_ranges, reason=''):
    """T13 并列列表：item_ranges 为 [(start,end)]；可逆验证由渲染器执行。"""
    text = sm.get_text(block_id, locale)
    items = []
    for s, e in item_ranges:
        items.append(text[s:e])
        if text[s:e] not in text:
            raise ValueError('T13 exact match failed')
    return TextOp('T13', block_id, locale, text,
                  action='list', params={'items': items}, reason=reason)


def op_mix_spans(text):
    """T17：找出需要混排处理的拉丁/数字 run。返回 [(start,end)]。"""
    return [(m.start(), m.end())
            for m in re.finditer(r'[A-Za-z0-9][A-Za-z0-9\s.,$%€¥\-–—/()]*[A-Za-z0-9$%]', text)
            if len(m.group(0).strip()) >= 2]


# ---------------- 渲染 ----------------

def _esc(s):
    return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _apply_wraps(text, wraps):
    """Escape source slices after indexing; entities never shift source ranges."""
    events = {}
    for index, (start, end, opening, closing) in enumerate(wraps):
        events.setdefault(start, []).append((True, end, index, opening))
        events.setdefault(end, []).append((False, start, index, closing))
    out, cursor = [], 0
    for position in sorted(events):
        out.append(_esc(text[cursor:position]))
        # Close inner spans first, then open outer spans first.
        for opening, other, index, markup in sorted(
                events[position], key=lambda e: (e[0], -e[1], e[2] if e[0] else -e[2])):
            out.append(markup)
        cursor = position
    out.append(_esc(text[cursor:]))
    return ''.join(out)


def validate_text_op(block, op):
    """Reject operations this renderer cannot execute instead of silently dropping them."""
    supported = {'T01': 'wrap', 'T03': 'wrap', 'T06': 'wrap',
                 'T10': 'group', 'T11': 'subhead', 'T17': 'mix'}
    if supported.get(op.pattern_id) != op.action:
        raise ValueError(f'unsupported text operation: {op.pattern_id}/{op.action}')
    if op.block_id != block['id']:
        raise ValueError(f'missing text anchor: {op.block_id}')
    if op.locale not in ('cn', 'en'):
        raise ValueError(f'unsupported text locale: {op.locale}')
    text = block[op.locale]
    if op.action in ('wrap', 'mix'):
        if not op.text_exact or op.text_exact not in text:
            raise ValueError(f'stale exact text: {op.pattern_id} {op.block_id}')
    if op.action == 'mix':
        spans = op.params.get('spans')
        if not spans or any(not isinstance(s, int) or not isinstance(e, int)
                            or not 0 <= s < e <= len(text) for s, e in spans):
            raise ValueError(f'invalid mix spans: {op.block_id}')
    if op.action == 'subhead':
        if not op.editorial_added or not op.params.get('title_cn'):
            raise ValueError(f'subhead must be explicit editorial addition: {op.block_id}')
        if op.text_exact != op.params['title_cn']:
            raise ValueError(f'stale editorial subhead text: {op.block_id}')


def render_block(block, ops, css_classes=True):
    """渲染单个块（含 T 操作）。返回 (cn_html, en_html)。"""
    cn, en = block['cn'], block['en']
    cn_wraps, en_wraps = [], []

    for op in ops:
        validate_text_op(block, op)
        loc = op.locale
        text = cn if loc == 'cn' else en
        if op.action == 'wrap':
            rng = _find_range(text, op.text_exact)
            if not rng:
                raise ValueError(f'render exact match failed: {op.pattern_id} {op.text_exact[:30]}')
            s, e = rng
            if op.pattern_id == 'T01':
                tag = ('<strong class="tt-b">', '</strong>')
            elif op.pattern_id == 'T03':
                tag = ('<span class="tt-num">', '</span>')
            elif op.pattern_id == 'T06':
                tag = ('<span class="tt-attr">', '</span>')
            else:
                raise ValueError(f'unsupported wrap: {op.pattern_id}')
            (cn_wraps if loc == 'cn' else en_wraps).append((s, e, tag[0], tag[1]))
        elif op.action in ('group', 'subhead'):
            raise ValueError(f'block renderer cannot execute {op.action}')
        elif op.action == 'mix':
            for s, e in op.params['spans']:
                (cn_wraps if loc == 'cn' else en_wraps).append(
                    (s, e, '<span class="tt-mix">', '</span>'))

    for wraps in (cn_wraps, en_wraps):
        ordered = sorted(wraps, key=lambda w: (w[0], -w[1]))
        for i, (start, end, *_rest) in enumerate(ordered):
            for other_start, other_end, *_ in ordered[i+1:]:
                if start < other_start < end < other_end:
                    raise ValueError(f'crossing text treatments: {block["id"]}')
    cn_h = _apply_wraps(cn, cn_wraps)
    en_h = _apply_wraps(en, en_wraps)
    return cn_h, en_h


def verify_reversible(original, rendered_parts):
    """T09/T13 可逆验证：去掉 HTML 标签后拼回原文必须逐字一致。"""
    joined = ''.join(re.sub(r'<[^>]+>', '', p) for p in rendered_parts)
    return _norm_ws(joined) == _norm_ws(original)


def _norm_ws(s):
    return re.sub(r'\s+', '', s or '')


# ---------------- Text Treatment CSS（AJ×WIRED token，不新增色板） ----------------
# 布局契约：所有正文流子元素通过 .ed-block 统一宽度，不再依赖元素类型子选择器。
# Text Treatment 只改变文字样式，不得改变正文宽度/字体体系/响应式行为。
TEXT_CSS = '''
/* ---- Editorial Content Container 契约 ---- */
.sheet>.ed-block{max-width:var(--measure);margin-left:auto;margin-right:auto}
/* ---- Text Treatment（阅读增强文字层） ---- */
.tt-b{font-weight:700;color:var(--ink)}                 /* T01 语义加粗：只加重点，不变色 */
.tt-num{font-weight:700;color:var(--ink);               /* T03 数值内联强调 */
  font-variant-numeric:tabular-nums;white-space:nowrap}
.tt-attr{border-bottom:1px dotted var(--mut)}            /* T06 引述归属：点线下划线 */
.tt-mix{font-family:var(--font-mix,inherit)}            /* T17 中英混排 */
.tt-subhead{font:700 17px/1.5 var(--font-meta);color:var(--ink); /* T11 编辑小标题 */
  margin:1.8em 0 .7em;padding-left:12px;position:relative}
.tt-subhead::before{content:"";position:absolute;left:0;top:.25em;bottom:.25em;
  width:3px;background:var(--orange)}
.tt-group{margin:0 0 1.6em}                              /* T10 分组：组间留白 */
.tt-group p:last-child{margin-bottom:0}
ul.tt-list{margin:0 0 1em;padding:0;list-style:none}     /* T13 并列列表 */
ul.tt-list li{position:relative;padding-left:1.2em;margin:0 0 .5em;
  font:400 var(--body-size)/var(--body-leading) var(--font-body);color:var(--body)}
ul.tt-list li::before{content:"·";position:absolute;left:.2em;color:var(--ink);
  font-weight:700}
@media(max-width:430px){
  .tt-subhead{font-size:16px}
}
'''
