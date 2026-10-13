#!/usr/bin/env python3
"""turn-to-page 跨页续文跟随。

WSJ 长文在首页放"Please turn to page X"，续文在目标页以
"Continued from page X"+ 重复标题出现。本模块：

1. wsj_page_to_pdf_idx: 版面页码(A8/B2) -> PDF 页索引
2. find_continuations: 找出续页上所有 (标题, Continued标记) 配对
3. extract_region: 按栏重建阅读顺序文本
4. merge_continuation: 主入口；用重叠检测避免重复合并（已合并正确的文章不动）

所有修改可逆：原始 body 保留在 result['original_body'] 中。
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import pymupdf
except ImportError:
    pymupdf = None

# 版面映射：PDF 页索引(0-based)。A1-A18 -> 0-17；B1-B8 -> 18-25
SECTION_OFFSET = {'A': 0, 'B': 18}


def wsj_page_to_pdf_idx(label):
    """'A8' -> 7, 'B2' -> 19。"""
    m = re.match(r'^([AB])(\d+)$', label.strip())
    if not m:
        raise ValueError(f'bad page label: {label}')
    return SECTION_OFFSET[m.group(1)] + int(m.group(2)) - 1


def _norm(s):
    return re.sub(r'\s+', ' ', (s or '')).strip().lower()


def find_continuations(pdf_path, pdf_idx):
    """找出续页上所有 Continued 标记及其上方标题。

    返回 [{headline, headline_rect, continued_rect}]。
    标题判定：在标记上方 300pt 内、字号显著大于正文(>11pt)的文本行。
    """
    if pymupdf is None:
        raise RuntimeError('pymupdf required')
    doc = pymupdf.open(pdf_path)
    page = doc[pdf_idx]
    results = []
    seen = set()
    for inst in page.search_for('Continued'):
        key = (round(inst[0]), round(inst[1]))
        if key in seen:
            continue
        seen.add(key)
        cx0, cy0, cx1, cy1 = inst
        cx = (cx0 + cx1) / 2
        # 收集标记上方的大字号标题行（多行合并）
        heads = []
        blocks = page.get_text('dict')['blocks']
        for b in blocks:
            if b.get('type', 0) != 0:
                continue
            for line in b['lines']:
                for span in line['spans']:
                    sx0, sy0, sx1, sy1 = span['bbox']
                    size = span['size']
                    if sy1 < cy0 and cy0 - sy1 < 400 and size > 11:
                        sx = (sx0 + sx1) / 2
                        if abs(sx - cx) < 180:
                            txt = span['text'].strip()
                            if txt and len(txt) > 2 and 'Continued' not in txt:
                                heads.append((sy0, txt, span['bbox']))
        heads.sort()
        headline = ' '.join(t for _, t, _ in heads)
        if heads:
            xs0 = min(b[0] for _, _, b in heads)
            ys0 = min(b[1] for _, _, b in heads)
            xs1 = max(b[2] for _, _, b in heads)
            ys1 = max(b[3] for _, _, b in heads)
            hrect = [xs0, ys0, xs1, ys1]
        else:
            hrect = None
        results.append({
            'headline': headline,
            'headline_rect': hrect,
            'continued_rect': [cx0, cy0, cx1, cy1],
        })
    doc.close()
    return results


def match_headline(headline, candidates):
    """标题模糊匹配到候选文章。candidates: [(article_id, title_en)]。
    返回 article_id 或 None。"""
    hn = _norm(headline)
    if not hn:
        return None
    hwords = set(hn.split()) - {'the', 'a', 'an', 'of', 'to', 'in', 'on', 'news', 'world'}
    best, best_score = None, 0
    for aid, title in candidates:
        twords = set(_norm(title).split()) - {'the', 'a', 'an', 'of', 'to', 'in', 'on'}
        score = len(hwords & twords)
        if score > best_score and score >= 2:
            best, best_score = aid, score
    return best


def pick_continuation(conts, article_id, title_en):
    """从多个 Continued 标记中选出目标文章的：标题匹配 + 距标题最近（正下方）。"""
    cands = []
    for c in conts:
        if match_headline(c['headline'], [(article_id, title_en)]) == article_id:
            hr = c['headline_rect']
            cr = c['continued_rect']
            # 标题底到标记顶的距离（越小越好）；标记必须在标题下方
            dist = cr[1] - hr[3] if hr and cr[1] >= hr[3] else 9999
            cands.append((dist, c))
    if not cands:
        return None
    cands.sort(key=lambda x: x[0])
    return cands[0][1]


def _words_with_size(page, x0, x1, y0, y1, min_size=8, max_size=12):
    """取指定区域、字号范围内的词（用于栏检测，排除图注/标题）。"""
    out = []
    for b in page.get_text('dict')['blocks']:
        if b.get('type', 0) != 0:
            continue
        for line in b['lines']:
            for span in line['spans']:
                sz = span['size']
                if not (min_size <= sz <= max_size):
                    continue
                words_in_span = span['text'].split()
                if not words_in_span:
                    continue
                sx0, sy0, sx1, _ = span['bbox']
                sw = (sx1 - sx0) / len(words_in_span)
                for i, w in enumerate(words_in_span):
                    out.append((sx0 + i * sw, sy0, w))
    return [(x, y, w) for x, y, w in out if x0 <= x <= x1 and y0 <= y <= y1]


def _detect_columns(words, x0, x1, y0, y1):
    """在区域内用 x 直方图低谷检测栏边界。返回 [(col_x0, col_x1), ...]。"""
    from collections import Counter
    bins = Counter()
    for w in words:
        wx0, wy0 = w[0], w[1]
        if x0 <= wx0 <= x1 and y0 <= wy0 <= y1:
            bins[int(wx0 / 10) * 10] += 1
    if not bins:
        return []
    lo, hi = int(x0 / 10) * 10, int(x1 / 10) * 10
    xs = list(range(lo, hi + 10, 10))
    counts = [bins.get(x, 0) for x in xs]
    # 低谷：原始计数显著低于左右各 20pt 邻域（不用平滑，栏缝窄）
    gutters = []
    for i in range(2, len(counts) - 2):
        neigh = max(counts[i-2], counts[i-1], counts[i+1], counts[i+2])
        if neigh >= 10 and counts[i] <= neigh * 0.3:
            gutters.append(xs[i])
    # 合并 20pt 内的相邻低谷
    merged = []
    for g in gutters:
        if merged and g - merged[-1] <= 20:
            continue  # 保留第一个（最左）
        merged.append(g)
    bounds = [x0] + merged + [x1]
    cols = [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]
    return [(a, b) for a, b in cols if b - a >= 50]


def _find_article_end(words, x0, x1, y0, y_max, gap_thresh=80):
    """找文章结尾：从 y0 向下，第一个 >gap_thresh 的无文本间隙处截断。"""
    # 20pt bins 统计
    from collections import Counter
    bins = Counter()
    for w in words:
        wx0, wy0 = w[0], w[1]
        if x0 <= wx0 <= x1 and y0 <= wy0 <= y_max:
            bins[int(wy0 / 20) * 20] += 1
    if not bins:
        return y_max
    ys = sorted(bins)
    prev = ys[0]
    for y in ys[1:]:
        if y - prev > gap_thresh and bins[prev] > 3:
            # 确认是真间隙（前后都有实质文本）
            return prev + 20
        prev = y
    return y_max


def extract_region(pdf_path, pdf_idx, x0, x1, y0, y1, ncols=3):
    """按栏提取区域文本，重建阅读顺序。返回清理后的连续文本。"""
    if pymupdf is None:
        raise RuntimeError('pymupdf required')
    doc = pymupdf.open(pdf_path)
    page = doc[pdf_idx]
    words = page.get_text('words')
    cols = _detect_columns(words, x0, x1, y0, y1)
    if not cols:
        w = (x1 - x0) / ncols
        cols = [(x0 + i * w, x0 + (i + 1) * w) for i in range(ncols)]
    parts = []
    for (cx0, cx1) in cols:
        cwords = [(w[1], w[0], w[4]) for w in words
                  if cx0 <= w[0] <= cx1 and y0 <= w[1] <= y1]
        cwords.sort()
        lines = {}
        for wy0, wx0, word in cwords:
            lines.setdefault(round(wy0), []).append((wx0, word))
        for k in sorted(lines):
            parts.append(' '.join(wd for _, wd in sorted(lines[k])))
    text = '\n'.join(parts)
    # 去连字符：行末 "word-" + 下行 "word"（join 后变成 "word- word"）
    text = re.sub(r'(\w)-\s+(\w)', r'\1\2', text)
    text = re.sub(r'[ \t]+', ' ', text.replace('\n', ' '))
    text = re.sub(r'\s+', ' ', text).strip()
    doc.close()
    return text


def overlap_ratio(body, continuation, n=8):
    """检测续文是否已在正文中：取续文前 n 个长句，用词袋 Jaccard 相似度。

    返回平均相似度。>0.5 视为已合并。
    """
    sents = re.split(r'(?<=[.!?])\s+', continuation)
    sents = [s.strip() for s in sents if len(s.strip()) > 40][:n]
    if not sents:
        return 0.0
    bwords = _norm(body).split()
    scores = []
    for s in sents:
        sw = set(_norm(s).split())
        if not sw:
            continue
        # 在 body 中找最匹配的窗口
        best = 0
        slen = len(sw)
        for i in range(0, len(bwords) - slen, 20):
            win = set(bwords[i:i + slen + 10])
            j = len(sw & win) / len(sw | win) if (sw | win) else 0
            if j > best:
                best = j
                if best > 0.7:
                    break
        scores.append(best)
    return sum(scores) / len(scores) if scores else 0.0


def merge_continuation(article_id, pdf_path, final_json_path=None,
                       dry_run=False):
    """主入口。返回 dict：
    {article_id, turn_to, pdf_page, status, original_paras, merged_paras,
     added_chars, original_body, merged_body, headline}
    status: merged | already_complete | not_found | no_new_content
    """
    if final_json_path is None:
        final_json_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..', '2026-10-12', 'final.json')
    data = json.load(open(final_json_path, encoding='utf-8'))
    art = next((e for e in data if e['id'] == article_id), None)
    if art is None:
        raise ValueError(f'article not found: {article_id}')
    turn_to = art.get('turn_to')
    result = {
        'article_id': article_id,
        'turn_to': turn_to,
        'original_body': art.get('body_en') or '',
        'original_paras': len([p for p in (art.get('body_en') or '').split('\n\n') if p.strip()]),
    }
    if not turn_to:
        result.update(status='no_turn_to', merged_paras=result['original_paras'],
                      added_chars=0, merged_body=result['original_body'])
        return result

    pdf_idx = wsj_page_to_pdf_idx(turn_to)

    # 主方法：用 body 末句在续页定位
    # 取 body 最后一个实质句子（去 [Photo:]/[caption:] 尾巴）
    body_clean = re.sub(r'\[\s*(Photo|caption)[^\]]*\]\s*$', '',
                        result['original_body'].strip())
    m_tail = re.search(r'([^.!?]{20,80}[.!?])\s*$', body_clean)
    if m_tail:
        tail_sent = m_tail.group(1).strip()
        # 取关键短语（去引号，取后 40 字符）
        key = re.sub(r'["\u201c\u201d]', '', tail_sent)[-45:].strip()
        # 归一化撇号（PDF 常用 ’，文本常用 '）
        key = key.replace('\u2019', "'").replace('\u2018', "'")
        doc3 = pymupdf.open(pdf_path)
        pg3 = doc3[pdf_idx]
        # 去掉首词（常含缩写/引号干扰），取核心短语
        key_parts = key.split()
        key_q = ' '.join(key_parts[1:]) if len(key_parts) > 4 else key
        insts = pg3.search_for(key_q[:38]) if len(key_q) >= 20 else []
        if insts:
            ix0, iy0, ix1, iy1 = insts[0]
            # 在该句下方、同栏（x±120）找后续正文（排除广告：字号 8-12pt）
            words_after = []
            for b in pg3.get_text('dict')['blocks']:
                if b.get('type', 0) != 0:
                    continue
                for line in b['lines']:
                    for span in line['spans']:
                        sz = span['size']
                        sx0, sy0 = span['bbox'][0], span['bbox'][1]
                        if sy0 > iy1 + 5 and abs((sx0) - ix0) < 150 and 7 <= sz <= 12:
                            # 排除广告关键词
                            txt = span['text']
                            if not re.search(r'ADVERTISEMENT|CLASS ACTION|LEGAL NOTICE|INDEX TO',
                                           txt, re.I):
                                words_after.append((sy0, sx0, txt))
            doc3.close()
            if words_after:
                words_after.sort()
                after_text = ' '.join(w for _, _, w in words_after[:200])
                # 若后续文本实质新内容 <200 字符 → 已完整
                bn = _norm(result['original_body'])
                an = _norm(after_text)
                # 找不在 body 中的连续片段
                max_new = 0
                for i in range(0, len(an) - 100, 50):
                    win = an[i:i+100]
                    if win not in bn:
                        max_new = max(max_new, 100)
                if max_new < 100:
                    result.update(status='already_complete',
                                  merged_paras=result['original_paras'],
                                  added_chars=0, merged_body=result['original_body'],
                                  headline='', pdf_page=pdf_idx + 1)
                    return result
                # 有新内容：用此方法提取（按行重建）
                lines = {}
                for sy0, sx0, txt in words_after:
                    lines.setdefault(round(sy0 / 6) * 6, []).append((sx0, txt))
                parts = [' '.join(t for _, t in sorted(lines[k]))
                         for k in sorted(lines)]
                cont_text2 = re.sub(r'\s+', ' ', ' '.join(parts)).strip()
                cont_text2 = re.sub(r'(\w)-\s+(\w)', r'\1\2', cont_text2)
                if len(cont_text2) > 300:
                    merged = body_clean.rstrip() + '\n\n' + cont_text2
                    result.update(
                        status='merged',
                        merged_body=merged,
                        merged_paras=len([p for p in merged.split('\n\n') if p.strip()]),
                        added_chars=len(cont_text2),
                        headline='', pdf_page=pdf_idx + 1)
                    if not dry_run:
                        art['body_en'] = merged
                        art['continuation_merged'] = {
                            'turn_to': turn_to, 'pdf_page': pdf_idx + 1,
                            'method': 'tail_anchor', 'added_chars': len(cont_text2)}
                        data = json.load(open(final_json_path, encoding='utf-8'))
                        a2 = next(e for e in data if e['id'] == article_id)
                        a2['body_en'] = merged
                        a2['continuation_merged'] = art['continuation_merged']
                        json.dump(data, open(final_json_path, 'w', encoding='utf-8'),
                                  ensure_ascii=False, indent=1)
                    return result
            else:
                # 末句找到但下方无正文 → 已完整
                result.update(status='already_complete',
                              merged_paras=result['original_paras'],
                              added_chars=0, merged_body=result['original_body'],
                              headline='', pdf_page=pdf_idx + 1)
                return result
        doc3.close()

    conts = find_continuations(pdf_path, pdf_idx)
    candidates = [(article_id, art.get('title') or '')]
    target = pick_continuation(conts, article_id, art.get('title') or '')
    if target is None:
        result.update(status='not_found', merged_paras=result['original_paras'],
                      added_chars=0, merged_body=result['original_body'],
                      headline='')
        return result

    cr = target['continued_rect']
    hr = target['headline_rect']
    cx = (cr[0] + cr[2]) / 2
    y0 = cr[3] + 5  # 正文从 Continued 标记下方开始
    doc_tmp = pymupdf.open(pdf_path)
    page_tmp = doc_tmp[pdf_idx]
    y1_tmp = page_tmp.rect.height - 40
    all_words = page_tmp.get_text('words')
    # 栏宽：取标记下方 5 个文本行的 x 范围（文章首栏宽度）
    line_ys = sorted(set(int(w[1] / 8) * 8 for w in all_words
                          if y0 <= w[1] <= y0 + 80))
    col_words = []
    for ly in line_ys[:5]:
        for w in all_words:
            if abs(w[1] - ly) < 6 and y0 <= w[1] <= y0 + 80:
                # 只取标记 x ±80 范围内的（紧约束，排除邻栏）
                if abs(w[0] - cx) < 80:
                    col_words.append(w[0])
    doc_tmp.close()
    if col_words:
        x0, x1 = max(0, min(col_words) - 10), max(col_words) + 10
    else:
        x0, x1 = max(0, cx - 70), cx + 70
    y1 = _find_article_end(all_words, x0, x1, y0, y1_tmp)
    cont_text = extract_region(pdf_path, pdf_idx, x0, x1, y0, y1)

    result['headline'] = target['headline']
    result['pdf_page'] = pdf_idx + 1
    if not cont_text or len(cont_text) < 200:
        result.update(status='not_found', merged_paras=result['original_paras'],
                      added_chars=0, merged_body=result['original_body'])
        return result

    # 判定1：body 结尾关键短语若出现在续页 → 续文已在正文中
    tail = result['original_body'].strip()
    # 取结尾最后一个完整分句（去标点，取 30-50 字符）
    m = re.search(r'([^.!?]{30,60}[.!?])\s*$', tail)
    if m:
        phrase = _norm(m.group(1))[:40]
        # 在续页全文搜
        doc2 = pymupdf.open(pdf_path)
        page_text = _norm(doc2[pdf_idx].get_text())
        doc2.close()
        if phrase and phrase in page_text:
            result.update(status='already_complete',
                          merged_paras=result['original_paras'],
                          added_chars=0, merged_body=result['original_body'])
            return result
    # 判定2：若续文实质新内容 <300 字符 → 已完整，不合并
    # （用滑动窗口找 body 中不存在的连续片段）
    bn = _norm(result['original_body'])
    cn = _norm(cont_text)
    # 取续文每 200 字符窗口，找不在 body 中的最长连续段
    max_new = 0
    for i in range(0, len(cn) - 200, 100):
        win = cn[i:i+200]
        if win not in bn:
            # 向后扩展找连续新内容
            j = i + 200
            while j < len(cn) and cn[j:j+200] not in bn:
                j += 100
            max_new = max(max_new, j - i)
            if max_new > 500:
                break
    if max_new < 300:
        result.update(status='already_complete',
                      merged_paras=result['original_paras'],
                      added_chars=0, merged_body=result['original_body'])
        return result
    # 判定3：重叠检测兜底
    if overlap_ratio(result['original_body'], cont_text) >= 0.5:
        result.update(status='already_complete',
                      merged_paras=result['original_paras'],
                      added_chars=0, merged_body=result['original_body'])
        return result

    # 合并：找 body 结尾与续文开头的衔接点，避免重复
    body = result['original_body']
    # 取续文前 200 字符，在 body 尾部找重叠
    head = cont_text[:300]
    join_at = 0
    for i in range(0, len(head) - 50, 10):
        probe = head[i:i + 60]
        idx = body.rfind(probe)
        if idx > len(body) * 0.7:  # 只在尾部找
            join_at = i + 60
            # 找到 probe 在续文中的结束位置
            break
    if join_at:
        # 从 body 结尾对齐处截断续文头部
        new_part = cont_text[join_at:].strip()
    else:
        new_part = cont_text

    merged = body.rstrip() + '\n\n' + new_part
    result.update(
        status='merged',
        merged_body=merged,
        merged_paras=len([p for p in merged.split('\n\n') if p.strip()]),
        added_chars=len(new_part),
    )
    if not dry_run:
        art['body_en'] = merged
        art['continuation_merged'] = {
            'turn_to': turn_to,
            'pdf_page': pdf_idx + 1,
            'headline': target['headline'],
            'added_chars': len(new_part),
        }
        json.dump(data, open(final_json_path, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
    return result


if __name__ == '__main__':
    pdf = '/home/hatch/workspace/user/files/kg07NVrtUILyeNFZgUpK-WSJNewsPaper-10-12-2026.pdf'
    fj = '/home/hatch/workspace/wsj-deep-read/2026-10-12/final.json'
    for aid in sys.argv[1:]:
        r = merge_continuation(aid, pdf, fj, dry_run=True)
        print(f"{r['article_id']}: {r['status']} | paras {r['original_paras']}->{r.get('merged_paras')} "
              f"| +{r.get('added_chars',0)} chars | headline={r.get('headline','')[:40]}")
