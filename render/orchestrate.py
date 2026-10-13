#!/usr/bin/env python3
"""联合编排（Orchestration）：narrative_outline → 三层候选 → rejected → 去重 → 校验。

流程（kit §2, §6, §8）：
1. narrative_outline：段落叙事功能标注（scene/background/claim/evidence/…）。
2. 三层候选：Text Treatment / Layout Grammar / Reading Aids，各自带理由。
3. rejected_opportunities：每项写拒绝理由（证据不足/重复成本/移动负担）。
4. 统一去重：caption_duplicate 跳过正文渲染；quote 与正文逐字重复时缩减为单句或拒绝。
5. plan_validate 兜底；输出增强版 plan JSON（兼容现有 schema，新增
   text_treatments / layout_decisions / narrative_outline / rejected_opportunities）。

评分启发式（kit §2）：阅读收益+证据清晰度+关联度−打断成本−重复成本−移动端负担。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from source_model import build_source
from text_treatment import (
    op_bold, op_number, op_attribution, op_subhead, op_group, op_mix_spans, TextOp,
)

BASE = os.path.dirname(os.path.abspath(__file__))


# ---------------- E1-025 的叙事大纲（Planner 分析结果，持久化） ----------------
E1025_OUTLINE = [
    {'block_ids': ['p3', 'p4', 'p5', 'p6', 'p7', 'p8'], 'function': 'scene',
     'reader_need': '建立事件场景：录音曝光的吹嘘内容与晚宴风波'},
    {'block_ids': ['p9', 'p10', 'p11', 'p12', 'p13'], 'function': 'evidence',
     'reader_need': '商人资助旅行的具体指控与金额链条'},
    {'block_ids': ['p14', 'p15'], 'function': 'contrast',
     'reader_need': '官方回应的对立面，避免单向叙事'},
    {'block_ids': ['p16', 'p17', 'p18'], 'function': 'consequence',
     'reader_need': '政府层面的后果：撤职讨论与监察调查'},
    {'block_ids': ['p19', 'p20'], 'function': 'claim',
     'reader_need': '核心新指控：十万美元短信请求'},
    {'block_ids': ['p21', 'p22', 'p23', 'p24', 'p25', 'p26', 'p27',
                   'p28', 'p29', 'p30', 'p31'], 'function': 'consequence',
     'reader_need': '各方回应：特朗普、鲁比奥、万斯及前官员'},
    {'block_ids': ['p32', 'p33', 'p34', 'p35'], 'function': 'consequence',
     'reader_need': '国会调查升级'},
]


def build_e1025_treatments(sm):
    """E1-025 的 Text Treatment 决策（每项有理由，可审计）。"""
    ops = []

    # T11：两个编辑小标题（editorial_added=true）
    ops.append(op_subhead(
        'p9', '奢华旅行谁买单', 'Who Paid for the Luxury Travel',
        reason='p9-p13 形成"商人资助旅行"的独立主题，与 p3-p8 的晚宴风波切换'))
    ops.append(op_subhead(
        'p19', '十万美元的请求', 'The $100,000 Ask',
        reason='p19-p20 是全文核心新指控，与前后回应段落主题切换'))

    # T01：两个语义加粗（含 T07 限定词保护）
    ops.append(op_bold(
        sm, 'p8', 'cn', '最终，吉尔福伊尔得以在最后一刻获得一个席位',
        reason='晚宴风波的转折句：从被拒到入场，T08 转折的文本落点'))
    ops.append(op_bold(
        sm, 'p19', 'cn',
        '吉尔福伊尔要求一位特朗普的捐赠者向她的美国运通账户汇入10万美元',
        reason='核心指控句；无限定词被截断（T07 检查通过）'))

    # T06：引述归属标识（p6 两处引语说话动词易混淆）
    ops.append(op_attribution(
        sm, 'p6', 'cn', '她这样说道',
        reason='同段两处引语，"她这样说道/她又说了这样一句话"需归属标识'))
    ops.append(op_attribution(
        sm, 'p6', 'cn', '她又说了这样一句话',
        reason='同上'))

    # T17：中英混排（拉丁/数字 run）
    for bid in ['p9', 'p12', 'p19']:
        text = sm.get_text(bid, 'cn')
        spans = op_mix_spans(text)
        if spans:
            ops.append(TextOp('T17', bid, 'cn', text, action='mix',
                              params={'spans': spans},
                              reason='英文专名/数字混排，加 tt-mix 保证不断行断裂'))

    # T10：分组留白（p14-p15 官方回应成组）
    ops.append(op_group(['p14', 'p15'], reason='官方回应两段成组，与前后指控段落视觉分隔'))
    return ops


def build_e1025_layouts():
    """E1-025 的 Layout 决策。"""
    layouts = [
        {'pattern_id': 'L05', 'action': 'apply',
         'blocks': ['figure'],
         'reason': 'Guilfoyle 照片已有 before_body figure；L05 图文并置语义已满足，保持现状',
         'mobile_strategy': '图→图注→正文，DOM 即此顺序'},
    ]
    rejected = [
        {'pattern_id': 'L02', 'action': 'decline',
         'reason_against': '无可信来源的附加信息可用；编造"Aktor Group 简介"类边注违反证据门禁',
         'fallback_pattern_id': 'L01'},
        {'pattern_id': 'L03', 'action': 'decline',
         'reason_against': '文中无结构对等的比较对象；硬做双栏会制造虚假对照',
         'fallback_pattern_id': 'L01'},
        {'pattern_id': 'L08', 'action': 'decline',
         'reason_against': '照片为示意性配图，非核心证据；跨栏放大增加视觉成本而无阅读收益',
         'fallback_pattern_id': 'L01'},
        {'pattern_id': 'T13', 'action': 'decline',
         'reason_against': '200万/20张/10万美元口径不同，非并列条目；已在 key_figures 中呈现',
         'fallback_pattern_id': 'T00'},
        {'pattern_id': 'T09', 'action': 'decline',
         'reason_against': '各段均为单一新闻论点，无可分两段且保持引语完整的安全拆分点',
         'fallback_pattern_id': 'T00'},
    ]
    return layouts, rejected


def _quoted_segments(text):
    """按引号对切分引语片段，返回 [(open_idx, segment_text)]（按出现顺序）。"""
    import re
    segs = []
    for pat in [r'“([^”]*)”', r'"([^"]*)"']:
        for m in re.finditer(pat, text or ''):
            segs.append((m.start(), m.group(0)))
    segs.sort()
    return segs


def _first_sentence(seg_text):
    """引语片段内取首个完整句子（含结尾标点）；无则返回 None。"""
    import re
    m = re.search(r'^[“"]?[^。！？.!?]*[。！？.!?]', (seg_text or '').strip())
    return m.group(0) if m else None


def dedup_quote(plan):
    """引语去重：quote 与正文逐字重复时，缩减为首个直接引语单句。

    中英必须取同一序号的引语片段（双语一致性），否则拒绝去重、
    保留原文并记录人工审核。
    返回 (modified: bool, note: str)。"""
    for cp in plan.get('component_plan', []):
        if cp['component'] != 'quote':
            continue
        d = cp.get('data', {})
        q = d.get('quote', {})
        cn_segs = _quoted_segments(q.get('text_cn', ''))
        en_segs = _quoted_segments(q.get('text_en', ''))
        cn_pick = en_pick = None
        for idx, (_, seg) in enumerate(cn_segs):
            s = _first_sentence(seg)
            if s:
                cn_pick = (idx, s)
                break
        for idx, (_, seg) in enumerate(en_segs):
            s = _first_sentence(seg)
            if s:
                en_pick = (idx, s)
                break
        if cn_pick and en_pick and cn_pick[0] == en_pick[0]:
            single_cn, single_en = cn_pick[1], en_pick[1]
            if single_cn != q['text_cn']:
                q['text_cn'] = single_cn
                q['text_en'] = single_en
                cp['dedup_note'] = ('引语与正文逐字重复；缩减为第%d个引语片段首句（中英对齐），'
                                    '保留导读功能，消除重复成本' % (cn_pick[0] + 1))
                return True, cp['dedup_note']
        elif cn_pick or en_pick:
            cp['dedup_note'] = ('中英引语片段序号不一致，去重中止，保留原文，需人工审核')
            return False, cp['dedup_note']
    return False, ''


def validate_quote_bilingual(plan):
    """双语引用一致性校验：所有 quote 组件的中英引语片段数必须一致。
    返回 [(component_idx, ok, msg)]。"""
    results = []
    for i, cp in enumerate(plan.get('component_plan', [])):
        if cp.get('component') != 'quote':
            continue
        q = cp.get('data', {}).get('quote', {})
        cn_n = len(_quoted_segments(q.get('text_cn', '')))
        en_n = len(_quoted_segments(q.get('text_en', '')))
        if cn_n != en_n:
            results.append((i, False, '中英引语片段数不一致 CN=%d EN=%d' % (cn_n, en_n)))
            continue
        # 语义合理性：去重后单句的中英长度比应在翻译常理内
        # 中文字符数 : 英文单词数 ≈ 1 : 0.6~2.5（超出则疑似错配）
        qcn = q.get('text_cn', '')
        qen = q.get('text_en', '')
        cn_len = len([c for c in qcn if '\u4e00' <= c <= '\u9fff'])
        en_words = len(qen.split())
        if cn_len > 5 and en_words > 0:
            ratio = en_words / cn_len
            if ratio < 0.3 or ratio > 3.0:
                results.append((i, False,
                    '中英长度比异常 (%.2f)，疑似错配：CN%d字 EN%d词' % (ratio, cn_len, en_words)))
                continue
        # attribution 泄漏检查：英文单句不应是"X said"结构
        import re as _re
        if _re.match(r'^[“"]?\s*\w+\s+said\b', qen, _re.I):
            results.append((i, False, '英文疑似 attribution 而非引语：%s' % qen[:40]))
            continue
        # source span 关联：中英引语在各自正文中的相对位置应接近
        # （不是序号对齐，而是位置对齐——同一引语在双语中位置相近）
        cn_segs = _quoted_segments(qcn)
        en_segs = _quoted_segments(qen)
        if cn_segs and en_segs and len(qcn) > 50 and len(qen) > 50:
            # 用首个片段的相对位置比
            cn_rel = cn_segs[0][0] / len(qcn)
            en_rel = en_segs[0][0] / len(qen)
            if abs(cn_rel - en_rel) > 0.5:
                results.append((i, False,
                    '中英引语位置偏差过大 (CN%.2f vs EN%.2f)，疑似非同一来源' % (cn_rel, en_rel)))
                continue
        results.append((i, True, '中英引语片段对齐 (%d 对)' % cn_n))
    return results


def orchestrate_e1025(gen_test_dir):
    aid = 'E1-025'
    tpath = os.path.join(gen_test_dir, aid, 'translation.json')
    plan = json.load(open(os.path.join(gen_test_dir, aid, 'plan.json'),
                          encoding='utf-8'))

    # 1. 源锚定
    sm, marked = build_source(aid, tpath, plan)
    print(f'源锚定：{len(sm.blocks)} 块；caption_duplicate 标记：{marked}')

    # 2. 三层候选
    treatments = build_e1025_treatments(sm)
    layouts, rejected = build_e1025_layouts()

    # exact match 全量校验
    for op in treatments:
        if op.action == 'wrap' and not sm.check_exact(op.block_id, op.locale, op.text_exact):
            raise ValueError(f' treatment exact match 失败: {op.pattern_id} {op.block_id}')

    # 3. 去重
    qmod, qnote = dedup_quote(plan)
    print(f'引语去重：{qmod}；{qnote}')

    # 4. 增强 plan（兼容现有 schema）
    plan['schema_version'] = '0.2-enh'
    plan['narrative_outline'] = E1025_OUTLINE
    plan['text_treatments'] = [op.to_dict() for op in treatments]
    plan['layout_decisions'] = layouts
    plan['rejected_opportunities'] = rejected
    plan['source_model'] = sm.to_dict()
    plan['dedup'] = {
        'caption_duplicates_skipped': marked,
        'quote_trimmed': qmod,
        'quote_note': qnote,
    }
    return plan, sm, treatments


if __name__ == '__main__':
    gen_test = os.path.join(os.path.dirname(BASE), '2026-10-12', 'gen-test')
    plan, sm, treatments = orchestrate_e1025(gen_test)
    out = os.path.join(gen_test, 'E1-025', 'plan-enhanced.json')
    json.dump(plan, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'增强 plan 写入：{out}')
    print(f'treatments: {len(treatments)} 项')
