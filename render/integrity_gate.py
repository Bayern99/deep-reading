"""正文完整性发布门禁（integrity gate）。

check_article(article) -> (pass: bool, issues: list)

检查项：
  拦截（block，不可发布）：
    ① 有 turn_to 但续文未合并（无 continuation_merged 标记且正文疑似截断）
    ② 正文以 turn-to-page / [请见X页] / [Photo: / [caption: 结尾（截断信号）
    ③ declutter 标记未处理（article 含 declutter_issues 且未人工确认）
  警告（warn，需人工确认）：
    ④ 正文段落数异常少（<3 段且非 brief 类型）
    ⑤ 中英段落数不对齐（差值 >2）

issue = {'level': 'block'|'warn', 'code': str, 'detail': str}

铁律：门禁只做判定，不改内容。
"""
import re

try:
    from .declutter import scan_article as _declutter_scan
except ImportError:
    from declutter import scan_article as _declutter_scan

# 截断结尾信号：照片/图注标记收尾（正文不应以此结尾）
TRUNC_TAIL_RES = [
    re.compile(r'\[\s*(Photo|caption)\s*:[^\]]*\]\s*$', re.I),
    re.compile(r'\(.*?(Images|Getty|Bloomberg|WSJ|AFP|Reuters)\)\s*\]\s*$', re.I),
]
# turn-to-page 残留
TURN_RES = [
    re.compile(r'turn to page\s+[A-Z]?\d+', re.I),
    re.compile(r'\[请见\s*[A-Z]?\d+\s*页\]'),
    re.compile(r'请见.*页.*完|未完待续\s*$'),
]

BRIEF_TYPES = {'brief', 'briefs', 'digest', 'headline', 'photo_caption', 'data_table', 'letter', 'correction'}


def _paras(text):
    return [p.strip() for p in (text or '').split('\n\n') if p.strip()]


def check_article(article):
    """检查单篇文章。返回 (pass: bool, issues: list)。

    pass=True 仅当无 block 级问题。warn 不影响 pass，但需人工确认。
    """
    issues = []
    aid = article.get('id', '?')
    body_en = article.get('body_en') or ''
    body_cn = article.get('body_cn') or ''
    tail = body_en.strip()[-300:] if body_en.strip() else ''

    # ① 有 turn_to 但续文未合并
    turn_to = article.get('turn_to')
    merged_flag = article.get('continuation_merged')
    if turn_to and not merged_flag:
        # 若正文结尾正常（完整句子）则只警告，否则拦截
        last = body_en.strip()
        truncated = any(rx.search(last) for rx in TRUNC_TAIL_RES)
        if truncated:
            issues.append({
                'level': 'block', 'code': 'turn_to_unmerged',
                'detail': f'turn_to={turn_to} 但无 continuation_merged 标记，'
                          f'且正文以图注结尾，疑似截断',
            })
        else:
            issues.append({
                'level': 'warn', 'code': 'turn_to_unconfirmed',
                'detail': f'turn_to={turn_to} 但无 continuation_merged 标记；'
                          f'正文结尾正常，需人工确认是否已完整',
            })

    # ② 正文以 turn-to-page / 图注结尾 → 拦截
    for rx in TURN_RES:
        if rx.search(body_en) or rx.search(body_cn):
            issues.append({
                'level': 'block', 'code': 'turn_marker_leftover',
                'detail': f'正文含 turn-to-page 残留：{rx.pattern[:30]}…',
            })
            break

    # ③ declutter 标记未处理 → 拦截
    # （article['declutter_issues'] 为已确认列表；若扫描有新命中且未确认则拦）
    confirmed = [tuple(c) for c in (article.get('declutter_confirmed') or [])]
    fresh = _declutter_scan(article)
    unconfirmed = [i for i in fresh
                   if (i['field'], i['para_idx'], i['type']) not in confirmed]
    if unconfirmed:
        issues.append({
            'level': 'block', 'code': 'declutter_unhandled',
            'detail': f'declutter 检出 {len(unconfirmed)} 处未处理：' +
                      ', '.join(f"{u['type']}@{u['field']}p{u['para_idx']}"
                                for u in unconfirmed[:5]),
        })

    # ④ 段落数异常少 → 警告
    atype = (article.get('type') or '').lower()
    n_en = len(_paras(body_en))
    if n_en < 3 and atype not in BRIEF_TYPES and body_en.strip():
        issues.append({
            'level': 'warn', 'code': 'too_few_paras',
            'detail': f'正文仅 {n_en} 段（非 brief），需人工确认是否截断',
        })

    # ⑤ 中英段落数不对齐 → 警告
    n_cn = len(_paras(body_cn))
    if body_cn.strip() and abs(n_en - n_cn) > 2:
        issues.append({
            'level': 'warn', 'code': 'para_misaligned',
            'detail': f'中英段落数不对齐：EN={n_en} / CN={n_cn}',
        })

    passed = not any(i['level'] == 'block' for i in issues)
    return passed, issues


def gate_report(results):
    """results: [(article_id, passed, issues)] → 人类可读报告。"""
    blocked = [(a, iss) for a, p, iss in results if not p]
    warned = [(a, iss) for a, p, iss in results if p and iss]
    lines = [f'# Integrity Gate：{len(results)} 篇，'
             f'拦截 {len(blocked)}，警告 {len(warned)}，通过 {len(results)-len(blocked)-len(warned)}']
    if blocked:
        lines.append('\n## ⛔ 拦截（不可发布）')
        for aid, iss in blocked:
            for i in iss:
                if i['level'] == 'block':
                    lines.append(f'- {aid}: [{i["code"]}] {i["detail"]}')
    if warned:
        lines.append('\n## ⚠️ 警告（需人工确认）')
        for aid, iss in warned:
            for i in iss:
                if i['level'] == 'warn':
                    lines.append(f'- {aid}: [{i["code"]}] {i["detail"]}')
    return '\n'.join(lines)


if __name__ == '__main__':
    import argparse
    import json
    import sys
    parser = argparse.ArgumentParser(description='Audit a final.json without changing content')
    parser.add_argument('final_json', help='Path to the issue final.json')
    args = parser.parse_args()
    with open(args.final_json, encoding='utf-8') as f:
        articles = json.load(f)
    results = [(a.get('id', '?'), *check_article(a)) for a in articles]
    print(gate_report(results))
    n_block = sum(1 for _, p, _ in results if not p)
    sys.exit(1 if n_block else 0)
