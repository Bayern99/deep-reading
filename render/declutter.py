"""OCR 双栏串扰清洗（declutter）。

检测正文中的 OCR/提取 artifact：
  1. dual_column_interleave — 双栏交错：相邻行分属左右栏，语义断裂
  2. abrupt_lang_switch   — 行内中英文突兀切换（非正常的术语/人名混排）
  3. truncated_para       — 段落截断（以小词/单字母结尾，非正常标点收尾）
  4. repeated_fragment    — 重复片段（提取重叠导致）

设计原则：
  - 只做检测 + 标记，不自动删除正文（铁律：内容一字不动）。
  - 清洗 = 标记问题段落，供人工确认；提供 `clean()` 仅用于生成
    待审稿副本，原数据不动。
  - 不为单篇写规则：所有阈值基于通用文本特征。

用法：
    from declutter import scan_article, declutter_report
    issues = scan_article(article_dict)   # article 需有 body_cn / body_en
"""
import re

# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------

CJK_RE = re.compile(r'[\u4e00-\u9fff]')
EN_WORD_RE = re.compile(r'[A-Za-z]{3,}')
# 正常收尾标点（中英）
CLOSE_PUNCT = set('.!?。！？…”)’"』」')


def _paras(text):
    return [p.strip() for p in (text or '').split('\n\n') if p.strip()]


def _has_cjk(s):
    return bool(CJK_RE.search(s))


def _has_en(s):
    return bool(EN_WORD_RE.search(s))


# ---------------------------------------------------------------------------
# 检测器
# ---------------------------------------------------------------------------

def detect_truncated_para(para):
    """段落截断：非正常标点结尾 + 尾词过短/异常。

    正常段落以标点或完整词结尾。截断常表现为：
      - 以单个字母/不完整词结尾（如 "...or even thin", "...Whe"）
      - 以小品词悬空结尾（如 "...for the"）
    返回 (is_issue, detail)。
    """
    p = para.strip()
    if not p or p[-1] in CLOSE_PUNCT:
        return False, ''
    words = p.split()
    if not words:
        return False, ''
    last = words[-1]
    # 尾词是单个字母（非 I/a/O 缩写场景）
    if len(last) == 1 and last.isalpha() and last not in 'Ia':
        # 排除 "Grade A" 这类合法单字母
        if len(words) < 2 or not words[-2][0].isupper():
            return True, f'truncated: ends with single letter "{last}"'
    # 尾词长度 <=2 且上一词也是短词（双栏切断常见）
    if len(last) <= 2 and len(words) >= 2 and len(words[-2]) <= 3:
        # 排除合法短结尾（"go to", "up to" 等）
        if last.lower() not in {'to', 'of', 'in', 'on', 'up', 'go', 'do', 'be'}:
            return True, f'truncated: ends with fragment "{words[-2]} {last}"'
    # 以悬空介词/冠词结尾
    if last.lower() in {'the', 'a', 'an', 'for', 'with', 'and', 'or', 'to', 'of'}:
        return True, f'truncated: ends with dangling "{last}"'
    return False, ''


def detect_abrupt_lang_switch(para):
    """行内中英文突兀切换。

    正常混排：中文段落含英文专名/术语（长度>3 的英文词成块出现）。
    异常：短段落内中英碎片交替（如 "the 公司 and 企业 said"），
    或英文段落突兀插入无上下文的中文短语。
    返回 (is_issue, detail)。
    """
    p = para.strip()
    if len(p) < 30:
        return False, ''
    # 切分为中英块
    blocks = []
    cur_lang, cur_len = None, 0
    for ch in p:
        if '\u4e00' <= ch <= '\u9fff':
            lang = 'cn'
        elif ch.isalpha():
            lang = 'en'
        else:
            continue
        if lang == cur_lang:
            cur_len += 1
        else:
            if cur_lang:
                blocks.append((cur_lang, cur_len))
            cur_lang, cur_len = lang, 1
    if cur_lang:
        blocks.append((cur_lang, cur_len))
    # 交替次数过多（>6 次语言切换）且块平均长度短 → 碎片交错
    switches = sum(1 for i in range(1, len(blocks)) if blocks[i][0] != blocks[i-1][0])
    if switches >= 6:
        avg = sum(l for _, l in blocks) / len(blocks)
        if avg < 8:
            return True, f'lang-switch: {switches} switches, avg block {avg:.1f} chars'
    return False, ''


def detect_dual_column_interleave(paras, idx):
    """双栏交错：本段与相邻段语义断裂 + 行长异常。

    双栏 OCR 把左右栏拼进同一行时，段落会出现：
      - 相邻段落主题突变（用词重叠度极低）
      - 段内句子长度方差极大
    这是启发式标记，需人工确认。返回 (is_issue, detail)。
    """
    if idx == 0 or idx >= len(paras):
        return False, ''
    cur = set(re.findall(r'[a-z]{4,}', paras[idx].lower()))
    prev = set(re.findall(r'[a-z]{4,}', paras[idx-1].lower()))
    if not cur or not prev:
        return False, ''
    # 内容词重叠度
    overlap = len(cur & prev) / max(len(cur), len(prev))
    # 句子长度方差
    sents = re.split(r'(?<=[.!?])\s+', paras[idx])
    lens = [len(s) for s in sents if len(s) > 10]
    if len(lens) >= 3:
        mean = sum(lens) / len(lens)
        var = sum((l - mean) ** 2 for l in lens) / len(lens)
        # 重叠极低 + 长度方差极大 → 疑似交错
        if overlap < 0.05 and var > 8000 and mean < 120:
            return True, (f'interleave-suspect: overlap={overlap:.2f}, '
                          f'sent-len-var={var:.0f}')
    return False, ''


def detect_repeated_fragment(para):
    """重复片段：同一 15+ 字符片段出现 2 次以上（提取重叠）。"""
    p = re.sub(r'\s+', ' ', para)
    m = re.search(r'(.{15,}?)\1', p)
    if m:
        return True, f'repeat: "{m.group(1)[:40]}..."'
    return False, ''


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

DETECTORS = {
    'truncated_para': detect_truncated_para,
    'abrupt_lang_switch': detect_abrupt_lang_switch,
    'repeated_fragment': detect_repeated_fragment,
}


def scan_article(article):
    """扫描单篇文章，返回 issues 列表。

    issue = {'article_id', 'field', 'para_idx', 'type', 'detail', 'excerpt'}
    """
    aid = article.get('id', '?')
    issues = []
    for field in ('body_cn', 'body_en'):
        text = article.get(field) or ''
        paras = _paras(text)
        for i, p in enumerate(paras):
            for dtype, fn in DETECTORS.items():
                hit, detail = fn(p)
                if hit:
                    issues.append({
                        'article_id': aid, 'field': field,
                        'para_idx': i, 'type': dtype,
                        'detail': detail, 'excerpt': p[:80],
                    })
            hit, detail = detect_dual_column_interleave(paras, i)
            if hit:
                issues.append({
                    'article_id': aid, 'field': field,
                    'para_idx': i, 'type': 'dual_column_interleave',
                    'detail': detail, 'excerpt': p[:80],
                })
    return issues


def scan_all(articles):
    """扫描全部文章，返回 {article_id: [issues]}（只含命中）。"""
    out = {}
    for a in articles:
        iss = scan_article(a)
        if iss:
            out[a.get('id', '?')] = iss
    return out


def declutter_report(issues_by_article):
    """生成人类可读的清洗报告（标记，不删文）。"""
    lines = [f'# Declutter 报告：{len(issues_by_article)} 篇命中']
    for aid, iss in sorted(issues_by_article.items()):
        lines.append(f'\n## {aid}（{len(iss)} 处）')
        for it in iss:
            lines.append(
                f"- [{it['field']} p{it['para_idx']}] {it['type']}: "
                f"{it['detail']}\n  摘录：{it['excerpt']}…")
    return '\n'.join(lines)


if __name__ == '__main__':
    import json, sys
    fj = sys.argv[1] if len(sys.argv) > 1 else \
        '/home/hatch/workspace/wsj-deep-read/2026-10-12/final.json'
    articles = json.load(open(fj, encoding='utf-8'))
    if len(sys.argv) > 2:  # 只扫指定篇
        articles = [a for a in articles if a['id'] == sys.argv[2]]
    hits = scan_all(articles)
    print(declutter_report(hits))
    # 退出码：有命中=1（供门禁调用），无=0
    sys.exit(1 if hits else 0)
