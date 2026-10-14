#!/usr/bin/env python3
"""源内容锚定层（Source Anchoring）。

原则：见仓库 FOUNDATION.md 的内容不变量与 ARCHITECTURE.md 的来源契约。
- OCR 原稿与 QA 译文是只读层，格式化流程不可修改原文。
- 每个段落有当前来源投影内的 ID（p1/p2…），原文/译文分别存字符 range；来源变更后需重新校验锚定计划。
- Text Treatment 只生成"操作"（operations），不改原文；操作必须过 source exact match。
- editorial_added 标记所有新增编辑文字，与记者原文明确区分。

caption_duplicate 检测：
- OCR 会把印刷图注也识别为正文段落（如 E1-025 p2）。
- 当某段文字与 figure/chart/infographic 的 caption 高度重合，且资产清单确认该图存在，
  标记 role='caption_duplicate'，渲染时正文流跳过该段（只在 figure 处渲染一次）。
- 绝不删除：原文块保留在 source model 中，可审计。
"""
import hashlib
import json
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))

_OVERRIDES = None


def _alignment_overrides():
    global _OVERRIDES
    if _OVERRIDES is None:
        with open(os.path.join(BASE, 'alignment_overrides.json'), encoding='utf-8') as f:
            _OVERRIDES = json.load(f)
    return _OVERRIDES


def _apply_en_repairs(aid, paragraphs):
    repairs = _alignment_overrides().get(aid) or {}
    en = list(paragraphs)
    for exact in repairs.get('drop_en', []):
        matches = [i for i, text in enumerate(en) if text == exact]
        if len(matches) != 1:
            raise ValueError(f'{aid}: drop_en must match once: {exact!r}')
        en.pop(matches[0])
    for spec in repairs.get('join_en', []):
        first = [i for i, text in enumerate(en) if text.startswith(spec['first_prefix'])]
        second = [i for i, text in enumerate(en) if text.startswith(spec['second_prefix'])]
        if len(first) != 1 or len(second) != 1 or first[0] == second[0]:
            raise ValueError(f'{aid}: join_en prefixes must match once: {spec!r}')
        en[first[0]] += spec.get('joiner', ' ') + en[second[0]]
        en.pop(second[0])
    return en


def content_digest(entry):
    """Pin original content plus this article's repair record for pN plan anchors."""
    payload = {'article': entry,
               'alignment_repair': _alignment_overrides().get(entry['id']) or {}}
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()


def source_from_final(entry):
    """Read-only repaired bilingual projection shared by every production path.

    pN anchors retain the existing enhanced-v1 numbering. An unmatched locale
    gets an empty counterpart, so an English tail can never be truncated.
    """
    sm = SourceModel(entry['id'])
    cn = [p.strip() for p in (entry.get('body_cn') or '').split('\n\n') if p.strip()]
    en = [p.strip() for p in (entry.get('body_en') or '').split('\n\n') if p.strip()]
    en = _apply_en_repairs(entry['id'], en)
    for i in range(max(len(cn), len(en))):
        c = cn[i] if i < len(cn) else ''
        raw_en = en[i] if i < len(en) else ''
        role = 'source_head' if c and len(c) <= 12 and not re.search(r'[。！？.!?]', c) else 'body'
        sm.add_block(f'p{i+1}', raw_en, c, role=role)
    return sm


def _norm(s):
    return re.sub(r'\s+', '', s or '')


def caption_similarity(a, b):
    """归一化后的字符重合率（去空白）。"""
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    short, long = (na, nb) if len(na) <= len(nb) else (nb, na)
    if short in long:
        return len(short) / len(long)
    # Jaccard on bigrams
    def bigrams(s):
        return {s[i:i+2] for i in range(len(s)-1)} or {s}
    ba, bb = bigrams(na), bigrams(nb)
    return len(ba & bb) / max(1, len(ba | bb))


class SourceModel:
    def __init__(self, article_id):
        self.article_id = article_id
        self.blocks = []          # [{id,en,cn,en_range,cn_range,role,duplicate_of}]
        self.by_id = {}
        self.captions = []        # [(component, caption_cn, caption_en)]

    def add_block(self, bid, en, cn, role='body'):
        b = {
            'id': bid,
            'en': en or '',
            'cn': cn or '',
            # range: (start_codepoint, end_codepoint)，段落内从 0 起
            'en_range': (0, len(en or '')),
            'cn_range': (0, len(cn or '')),
            'role': role,
            'duplicate_of': None,
        }
        self.blocks.append(b)
        self.by_id[bid] = b
        return b

    def register_caption(self, component, caption_cn, caption_en=''):
        self.captions.append((component, caption_cn or '', caption_en or ''))

    def detect_caption_duplicates(self, threshold=0.85):
        """标记与图注重复的正文段。返回标记列表（可审计）。"""
        marked = []
        for b in self.blocks:
            if b['role'] != 'body':
                continue
            for comp, ccn, cen in self.captions:
                sim = max(caption_similarity(b['cn'], ccn),
                          caption_similarity(b['en'], cen))
                if sim >= threshold and len(_norm(b['cn'])) > 10:
                    b['role'] = 'caption_duplicate'
                    b['duplicate_of'] = comp
                    marked.append({
                        'block_id': b['id'],
                        'duplicate_of': comp,
                        'similarity': round(sim, 3),
                    })
                    break
        return marked

    def get_text(self, bid, locale='cn'):
        b = self.by_id.get(bid)
        if not b:
            raise KeyError(f'unknown block {bid}')
        return b['en'] if locale == 'en' else b['cn']

    def check_exact(self, bid, locale, text_exact):
        """source exact match：操作引用的文字必须在源中逐字存在。"""
        src = self.get_text(bid, locale)
        return text_exact in src

    def body_blocks(self, include_caption_dup=False):
        if include_caption_dup:
            return list(self.blocks)
        return [b for b in self.blocks if b['role'] == 'body']

    def to_dict(self):
        return {
            'article_id': self.article_id,
            'blocks': self.blocks,
            'caption_sources': [
                {'component': c, 'caption_cn': ccn} for c, ccn, _ in self.captions
            ],
        }


def build_source(article_id, translation_path, plan=None, asset_manifest=None,
                 p1_is_title=True):
    """从 translation.json 构建源模型；plan 用于注册图注。

    p1_is_title：归档的 gen-test 适配器约定 translation.json 的 p1 是标题块（跳过正文流）；
    若 paragraphs 全为正文段（标题在 meta），传 False。
    """
    t = json.load(open(translation_path, encoding='utf-8'))
    sm = SourceModel(article_id)
    # plan 中的图注先注册（用于重复检测）
    if plan:
        for cp in plan.get('component_plan', []):
            if cp['component'] in ('figure', 'chart', 'infographic'):
                d = cp.get('data', {})
                sm.register_caption(cp['component'],
                                    d.get('caption_cn', ''),
                                    d.get('caption_en', ''))
    for p in t['paragraphs']:
        # p1 仅在 p1_is_title 约定时标为 title，不参与正文流
        role = 'title' if (p['id'] == 'p1' and p1_is_title) else 'body'
        sm.add_block(p['id'], p.get('en', ''), p.get('cn', ''), role=role)
    marked = sm.detect_caption_duplicates()
    return sm, marked
