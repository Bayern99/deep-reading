#!/usr/bin/env python3
"""Editorial Intelligence 自主选择 Planner。

- 输入：文章（final.json 条目）
- 输出：六段式计划（Narrative Analysis / Editorial Opportunities / Text Treatment Plan /
  Layout Plan / Reading Aid Plan / Rejected Candidates）
- 原则：Planner 必须比较"维持原样 / 文字增强 / 布局调整 / 新增辅助"四种候选；
  不许按文章 ID 写规则；不许人工指定 Layout。
"""
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

# 决策规范（LAYOUT_DECISION_SPECS.md 的精简版，进 prompt）
LAYOUT_SPECS = """
## L02 正文与边注
叙事关系：主线的"旁白"，解释术语/身份/背景，不推进叙事。
适用：术语/人物首次出现且不解释影响理解；正文只给名称未给定义；边注事实可公开验证。
拒绝：正文已解释；需长篇解释(>80字)；与锚点段无直接关联；只出现一次。
证据：锚点段落ID + 来源；editorial_added=true。
手机：锚点段→边注inline→下一段。

## L03 平行双栏比较
叙事关系："天平的两端"，读者需逐项对照。
适用：原文明确给出两组在相同维度上的成对数据；维度2-4个；对照是原文论证结构。
拒绝：维度不对等；只是先后发生；数据缺失需脑补；单项>100字。
证据：成对维度列表 + 每项原文锚点；缺失标"原文未给"。
手机：维度1→A→B→维度2→A→B 交替纵排。
**必须验证真实的平行语义结构，禁止为凑双栏而配对。**

## L05 图文并置
叙事关系：图是"证据"，文是"解说"。
适用：照片/图表与紧邻段落讲同一事件；图注归属可靠。
拒绝：图与文无直接关联；归属存疑；纯装饰。
证据：asset_id + 图注 + credit + 锚点段落ID。
手机：图→图注(含credit)→解释文。

## L08 跨栏图形
叙事关系：图是"核心证据"，值得打破正文宽度。
适用：图表是原文论证核心；640px内标签挤压不可读；原图完整可验证。
拒绝：装饰大图；数据不完整；OCR残缺。
证据：原始asset + 来源 + 单位/时间范围。
手机：min-width 560px 横滑，不得压扁。
"""

PLANNER_PROMPT = """你是 WSJ 深读的 Editorial Planner。通读全文后，自主决定增强方案，只输出 JSON。

## 文章
类型：{atype}｜优先级：{prio}｜版面：{section} {page}

### 中文正文（段落 ID 稳定，p1=标题）
{cn_blocks}

### 英文正文（辅助理解；引语中英必须对齐同一片段）
{en_blocks}

## 可用模式

**Text Treatment**（snippet 逐字来自中文正文）：
- T01 语义加粗（block_id + snippet）：核心事实/转折短语，含限定词
- T03 数字强调（block_id + snippet）：承担论证的数字
- T06 引述归属（block_id + snippet）：易混淆的说话人
- T09 段落拆分（block_id + after_sentence_idx）：过长段落，不打断因果链
- T11 编辑小标题（before_block_id + title_cn/title_en）：新增文字，标 editorial_added
- T13 并列列表（block_id + items）：逐字条目，可逆

**Layout**（默认 L01；从下面四选一需满足其适用条件）：

### 本篇可用视觉资产
{assets_block}
（无资产时 L05/L08 不可选；有资产时必须评估是否使用，拒绝需给理由）
""" + LAYOUT_SPECS + """

**Reading Aid**（data 逐字来自正文；日期不加年份）：
- key_figures：数字同属一叙事问题且需比较；口径不一则拒绝
- timeline：≥4 可定日期事件，日期原文逐字出现；输出 events[] 每项含 date/event（中文逐字）+ t_en/text_en（英文）
- quote：具名人物直接引语，中英同一片段
- data_table：仅 data_table 类型

## 决策流程（必须执行）

1. **Narrative Analysis**：按段落标叙事功能（scene/background/claim/evidence/contrast/consequence），指出读者理解需求。
2. **Editorial Opportunities**：列出所有候选机会，每个机会比较四种方案：
   - A. 维持原样（T00/L01）
   - B. 文字增强（T01/T03/T06/T09/T11/T13）
   - C. 布局调整（L02/L03/L05/L08）
   - D. 新增辅助（key_figures/timeline/quote）
   写清每个方案的收益与成本，选择最优并给理由。
3. 输出六段式计划。同一信息不进两个组件。接受零处理。

## 铁律
1. snippet/引文/日期逐字来自正文；不编造。
2. L03 必须验证真实平行语义结构；L02 必须解决具体理解困难。
3. 布局变化不得破坏原文叙事顺序。
4. 不以组件数量衡量质量。

## 只输出 JSON（无 markdown fences）
{{
  "narrative_analysis": [{{"block_ids": ["p2","p3"], "function": "claim", "reader_need": "..."}}],
  "editorial_opportunities": [
    {{"id": "opp1", "location": "p5-p7", "need": "...",
      "candidates": [
        {{"option": "A", "desc": "维持原样", "benefit": "...", "cost": "..."}},
        {{"option": "B", "desc": "T11 小标题", "benefit": "...", "cost": "..."}}
      ],
      "chosen": "B", "reason": "..."}}
  ],
  "text_treatment_plan": [...],
  "layout_plan": [{{"pattern_id": "L02", "anchor_block": "p5", "reason": "...", "evidence": "..."}}],
  "reading_aid_plan": [...],
  "rejected_candidates": [{{"pattern_id": "L03", "reason_against": "..."}}]
}}
"""


def call_planner(aid, meta, cn_blocks, en_blocks, model=None, assets=None):
    """调用 oMLX 上的 planner 模型。返回解析后的 dict。

    assets: 该文章的可用视觉资产列表（来自 asset_registry.json），
            每项含 asset_id/asset_type/caption_cn/credit。None 或空表示无资产。
    """
    import urllib.request
    key = json.load(open(os.path.expanduser('~/.pi/agent/models.json')))['providers']['omlx']['apiKey']
    assets_block = _format_assets(assets)
    prompt = PLANNER_PROMPT.format(
        atype=meta['type'], prio=meta['priority'],
        section=meta['section'], page=meta['page'],
        cn_blocks=cn_blocks, en_blocks=en_blocks,
        assets_block=assets_block)
    body = json.dumps({
        'model': model or 'Qwen3.5-27B-Claude-4.6-Opus-Distilled-MLX-6bit',
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.2, 'max_tokens': 6000,
    }).encode()
    req = urllib.request.Request(
        'http://127.0.0.1:18800/v1/chat/completions', data=body,
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'})
    resp = urllib.request.urlopen(req, timeout=300)
    raw = json.load(resp)['choices'][0]['message']['content']
    # 去 markdown fences
    raw = raw.strip()
    if raw.startswith('```'):
        raw = '\n'.join(raw.split('\n')[1:])
        if raw.rstrip().endswith('```'):
            raw = raw.rstrip()[:-3]
    return json.loads(raw), prompt


def _format_assets(assets):
    """格式化资产列表供 prompt 注入。"""
    if not assets:
        return "（本篇无可用视觉资产）"
    lines = []
    for a in assets:
        if a.get('status') != 'extracted':
            continue
        lines.append(
            f"- {a['asset_id']}｜{a.get('asset_type','photo')}｜"
            f"图注：{(a.get('caption_cn') or '')[:60]}｜"
            f"来源：{a.get('credit') or '未注明'}"
        )
    return '\n'.join(lines) if lines else "（本篇无可用视觉资产）"


def load_assets_for_article(aid, registry_path=None):
    """从 asset_registry.json 取某文章的可用资产。"""
    import json as _json, os as _os
    rp = registry_path or _os.path.join(
        _os.path.dirname(_os.path.abspath(__file__)), 'asset_registry.json')
    try:
        reg = _json.load(open(rp, encoding='utf-8'))
    except FileNotFoundError:
        return []
    return [r for r in reg if r.get('article_id') == aid]
