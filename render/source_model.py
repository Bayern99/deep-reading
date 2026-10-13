#!/usr/bin/env python3
"""源内容锚定层（Source Anchoring）。

原则（/tmp/kit/EDITORIAL_KNOWLEDGE.md §1, §8）：
- OCR 原稿与 QA 译文是只读层，格式化流程不可修改原文。
- 每个段落有稳定 ID（p1/p2…），原文/译文分别存字符 range。
- Text Treatment 只生成"操作"（operations），不改原文；操作必须过 source exact match。
- editorial_added 标记所有新增编辑文字，与记者原文明确区分。

caption_duplicate 检测：
- OCR 会把印刷图注也识别为正文段落（如 E1-025 p2）。
- 当某段文字与 figure/chart/infographic 的 caption 高度重合，且资产清单确认该图存在，
  标记 role='caption_duplicate'，渲染时正文流跳过该段（只在 figure 处渲染一次）。
- 绝不删除：原文块保留在 source model 中，可审计。
"""
import json
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))


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


def build_source(article_id, translation_path, plan=None, asset_manifest=None):
    """从 translation.json 构建源模型；plan 用于注册图注。"""
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
        # p1 通常是标题：role 标记为 title，不参与正文流
        role = 'title' if p['id'] == 'p1' else 'body'
        sm.add_block(p['id'], p.get('en', ''), p.get('cn', ''), role=role)
    marked = sm.detect_caption_duplicates()
    return sm, marked
