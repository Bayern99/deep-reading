
"""各篇编辑配置（import 自 build_layout_test）。"""
import base64
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from text_treatment import op_bold, op_number, op_subhead, op_group
from layout import render_margin_note, render_compare, render_figure_text, render_wide_figure
from components import esc
from build_layout_test import (
    make_source, render_body_flow, write_article, save, OUT, KYIV_IMG, CHART_IMG,
)

# ---------------- E1-007：L02 边注（预测市场）+ T01/T11 ----------------
def build_E1_007():
    aid = 'E1-007'
    sm, e = make_source(aid)
    T = []
    # T11 小标题
    T.append(op_subhead('p4', '当法庭变成赌场', 'When the Court Becomes a Casino',
                        reason='p4-p8 转入伦理与陪审员风险，主题切换'))
    T.append(op_subhead('p9', '偏见如何渗入', 'How Bias Creeps In',
                        reason='p9-p14 学者与法庭程序视角'))
    T.append(op_subhead('p15', '离岸赌局', 'The Offshore Books',
                        reason='p15-p18 平台与监管套利'))
    T.append(op_subhead('p19', '法院的反制', 'Courts Push Back',
                        reason='p19-p21 法院政策回应'))
    # T01 语义加粗（exact match）
    T.append(op_bold(sm, 'p5', 'cn', '当公众将法庭视为赌场时，正当程序很容易受到腐败的影响',
                     reason='核心论点句'))
    T.append(op_bold(sm, 'p6', 'cn', '陪审员可能会对自己的审议过程进行赌博',
                     reason='最直接的风险点'))
    # L02 边注：锚定 p3（Polymarket 首次出现并解释）
    note_cn = ('预测市场（prediction market）：对未来事件结果进行交易的平台。'
               '参与者买卖与"谁获胜""是否发生"等挂钩的合约，合约价格即群体对结果概率的集体判断。'
               'Polymarket 是其中最知名的境外平台。')
    note_en = ('A prediction market lets people trade contracts tied to future events; '
               'prices reflect the crowd\u2019s collective judgment of probabilities. '
               'Polymarket is one of the best-known offshore platforms.')
    note_html = render_margin_note('p3', note_cn, note_en, 'e1007',
                                   editorial_added=True)
    layouts = {'anchor_wraps': {'p3': note_html}, 'after_blocks': {}}
    body = render_body_flow(sm, T, layouts)
    html = write_article(aid, body)
    plan = {
        'article_id': aid,
        'narrative_outline': '陪审团赌注案例(p1-p3) → 伦理风险(p4-p8) → 学者/法庭视角(p9-p14) → 离岸与平台(p15-p18) → 法院反制(p19-p21)',
        'decisions': [
            {'pattern': 'L02', 'anchor': 'p3', 'reason': 'Polymarket 首次出现，正文未解释何为预测市场；边注给一句话定义',
             'editorial_added': True},
            {'pattern': 'T11', 'count': 4, 'reason': '21 段长文，四个主题段需要路标'},
            {'pattern': 'T01', 'count': 2, 'reason': '核心论点与最直接风险点'},
        ],
        'rejected': [
            {'pattern': 'A04 timeline', 'reason': '日期零散（夏季/9月初/上个月/7月），无可靠年份链'},
            {'pattern': 'A03 key_figures', 'reason': '金额口径不一（10万/50万/30万/79.8万），拼凑无意义'},
            {'pattern': 'L03', 'reason': '无对等比较对象'},
        ],
    }
    save(aid, html, plan)


# ---------------- E2-031：L03 双栏 + L05 图文 + T01/T03/T11 ----------------
def build_E2_031():
    aid = 'E2-031'
    sm, e = make_source(aid)
    T = []
    T.append(op_subhead('p4', '不只是乌克兰的问题', 'Not Just Ukraine\u2019s Problem',
                        reason='p4-p6 转入北约与欧洲威胁'))
    T.append(op_subhead('p7', '乌克兰的应对', 'Ukraine\u2019s Response',
                        reason='p7-p10 防空体系与拦截武器'))
    T.append(op_subhead('p11', '坏消息', 'The Bad News',
                        reason='p11-p12 量产困境'))
    T.append(op_subhead('p14', '西方能做什么', 'What the West Can Do',
                        reason='p14-p15 政策建议'))
    T.append(op_bold(sm, 'p2', 'cn', '俄罗斯最新的突破是喷气动力无人机，而乌克兰缺乏有效的应对手段',
                     reason='全文核心判断'))
    T.append(op_number(sm, 'p3', 'cn', '375 英里', reason='关键性能参数'))
    T.append(op_number(sm, 'p3', 'cn', '55%', reason='拦截率对比核心'))
    # L03：俄喷气无人机 vs 乌方拦截（p3 数据 + p10/p11）
    pairs = [
        (('时速375英里、升限约5.5英里、射程近600英里、载荷近200磅',
          '375 mph, ~5.5 mi ceiling, ~600 mi range, ~200 lb payload'),
         ('乌方拦截无人机追不上这个速度，便携式防空系统够不着这个高度',
          'Too fast for Ukraine\u2019s interceptor drones, too high for man-portable air defenses')),
        (('拦截率仅55%', 'Only 55% intercepted'),
         ('老式"沙赫德"拦截率超90%', 'Over 90% for older Shaheds')),
        (('单架成本10万美元或更低，俄每天发射多达100架，扩产优先',
          'US$100,000 or less each; up to 100 launched daily; production ramp-up a priority'),
         ('乌方廉价拦截武器仍在测试，量产前"麻烦大了"',
          'Cheap interceptors still in testing; "we\u2019re in trouble" until mass production')),
    ]
    cmp_html = ('<div class="ed-block">\n' +
                render_compare(pairs, 'e2031',
                               dim_labels=['性能', '拦截率', '成本与规模']) +
                '\n</div>')
    # L05：基辅照片 + 图注并置（E2-032），放在 p12（基辅空袭）之后
    with open(KYIV_IMG, 'rb') as fh:
        img_b64 = base64.b64encode(fh.read()).decode('ascii')
    img_html = (f'<figure class="fig"><img src="data:image/png;base64,{img_b64}" '
                f'alt="基辅遭袭建筑"/>'
                f'<figcaption><span class="k-cn">9月28日，基辅一栋建筑遭到俄罗斯喷气式无人机袭击。'
                f'（图片来源：托马斯·彼得/路透社）</span>'
                f'<span class="k-en" hidden>A building hit by a Russian jet-powered drone strike '
                f'in Kyiv, Sept. 28. (Credit: Thomas Peter/Reuters.)</span></figcaption></figure>')
    figtext_html = ('<div class="ed-block">\n' + render_figure_text(
        img_html,
        '照片记录的正是文中所说的威胁：喷气式无人机对基辅市区的直接打击。',
        'The photo documents the threat described: a jet-drone strike on Kyiv itself.',
        'e2031') + '\n</div>')
    layouts = {'anchor_wraps': {},
               'after_blocks': {'p3': [cmp_html], 'p12': [figtext_html]}}
    body = render_body_flow(sm, T, layouts)
    html = write_article(aid, body)
    plan = {
        'article_id': aid,
        'narrative_outline': '威胁总览(p1-p3) → 北约/欧洲(p4-p6) → 乌方应对体系(p7-p10) → 困境(p11-p12) → 缓解与西方(p13-p15)',
        'decisions': [
            {'pattern': 'L03', 'anchor': 'p3', 'reason': 'p3 明确给出俄无人机性能与乌拦截率的成对数据，读者需逐项对照',
             'dims': ['性能', '拦截率', '成本与规模']},
            {'pattern': 'L05', 'anchor': 'p12', 'reason': 'E2-032 同话题照片，归属可靠（路透），与"基辅空袭猛烈"紧贴'},
            {'pattern': 'T11', 'count': 4, 'reason': '观点长文四段式结构'},
        ],
        'rejected': [
            {'pattern': 'A04 timeline', 'reason': '无历史事件链，多为现状与预警'},
            {'pattern': 'A12 数据图表', 'reason': '无连续数据，不自造曲线；用原始照片而非重绘'},
            {'pattern': 'L02', 'reason': '术语（喷气无人机/沙赫德）正文已解释，无需边注'},
        ],
    }
    save(aid, html, plan)


# ---------------- E3-036：L08 跨栏图表 ----------------
def build_E3_036():
    aid = 'E3-036'
    sm, e = make_source(aid)  # EN-only
    T = []
    T.append(op_bold(sm, 'p2', 'en',
                     'AT&T and Verizon suffered their biggest one-day declines in more than 24 years',
                     reason='核心事实句'))
    with open(CHART_IMG, 'rb') as fh:
        img_b64 = base64.b64encode(fh.read()).decode('ascii')
    chart_inner = (
        f'<img src="data:image/png;base64,{img_b64}" alt="Share-price performance chart"/>'
        f'<figcaption><span class="k-cn">盘中股价表现（上午10时至下午4时）：AT&T、威瑞森、T-Mobile US。数据来源：FactSet。</span>'
        f'<span class="k-en" hidden>Share-price performance chart (intraday, 10 a.m. to 4 p.m.): '
        f'AT&T, Verizon, T-Mobile US. Source: FactSet.</span></figcaption>')
    wide_html = render_wide_figure(chart_inner, 'e3036')
    layouts = {'anchor_wraps': {}, 'after_blocks': {'p1': [wide_html]}}
    body = render_body_flow(sm, T, layouts)
    html = write_article(aid, body)
    plan = {
        'article_id': aid,
        'narrative_outline': '图表说明(p1) → 事件背景(p2) → 数据来源(p3)',
        'decisions': [
            {'pattern': 'L08', 'reason': '原始股价走势图（FactSet），小栏挤压图例；桌面跨栏，手机横滑',
             'asset': 'chart-shareprice.png', 'credit': 'FactSet'},
            {'pattern': 'T01', 'count': 1, 'reason': '仅加粗核心事实句'},
        ],
        'rejected': [
            {'pattern': 'A12 数据图表', 'reason': '已有原始图表，不重绘'},
            {'pattern': 'T11', 'reason': '3 段短文，无需小标题'},
        ],
        'component_plan': [
            {'component': 'figure', 'data': {'credit': 'FactSet'},
             'slot': {'at': 'after_para', 'para': 1}},
        ],
    }
    save(aid, html, plan)
    # plan_validate：credit 必须在原文出现
    from plan_validate import validate
    src = (e.get('body_en') or '') + ' ' + (e.get('body_cn') or '')
    errs = validate(os.path.join(OUT, aid, 'plan.json'), src)
    print(f'{aid} plan_validate: {errs if errs else "通过"}')
    assert not errs


# ---------------- E1-011：L02 边注（哈马克）+ T01/T11 ----------------
def build_E1_011():
    aid = 'E1-011'
    sm, e = make_source(aid)
    T = []
    T.append(op_subhead('p5', '定价权的回归', 'The Return of Pricing Power',
                        reason='p5-p6 需求超供给的定价能力'))
    T.append(op_subhead('p7', '加息的理由', 'The Case for Hikes',
                        reason='p7-p10 哈马克的政策立场'))
    T.append(op_subhead('p11', '多快算快', 'How Fast',
                        reason='p11-p13 加息节奏之争'))
    T.append(op_subhead('p14', '中性利率之争', 'The Neutral-Rate Debate',
                        reason='p14-p16 技术性辩论'))
    T.append(op_subhead('p18', '与主席的分歧', 'Split With the Chair',
                        reason='p18-p19 哈马克 vs 沃什'))
    T.append(op_bold(sm, 'p5', 'cn', '这种定价能力让像哈马克这样的通胀控制者感到担忧',
                     reason='承上启下的关键判断'))
    T.append(op_bold(sm, 'p8', 'cn', '我认为，这时间太长了',
                     reason='哈马克对 2029 年目标的直接表态'))
    note_cn = ('贝丝·哈马克（Beth Hammack）：克利夫兰联邦储备银行行长，2024年上任；'
               '此前在高盛工作30余年。在美联储决策层中立场偏"鹰"，是主张更积极加息的主要官员之一。')
    note_en = ('Beth Hammack: president of the Cleveland Fed since 2024; '
               'previously 30+ years at Goldman Sachs. A leading hawk on the FOMC, '
               'pushing for more aggressive rate hikes.')
    note_html = render_margin_note('p1', note_cn, note_en, 'e1011',
                                   editorial_added=True)
    layouts = {'anchor_wraps': {'p1': note_html}, 'after_blocks': {}}
    body = render_body_flow(sm, T, layouts)
    html = write_article(aid, body)
    plan = {
        'article_id': aid,
        'narrative_outline': '工厂见闻(p1-p4) → 定价权(p5-p6) → 加息理由(p7-p10) → 节奏(p11-p13) → 中性利率(p14-p16) → 批评与分歧(p17-p19)',
        'decisions': [
            {'pattern': 'L02', 'anchor': 'p1', 'reason': '哈马克首次出现；读者需知其身份与政策立场才能理解后文',
             'editorial_added': True},
            {'pattern': 'T11', 'count': 5, 'reason': '19 段，五个议题段'},
            {'pattern': 'T01', 'count': 2, 'reason': '关键判断与直接表态'},
        ],
        'rejected': [
            {'pattern': 'A03 key_figures', 'reason': '数字分散（3.75%-4%/2%/2029年），无同口径比较价值'},
            {'pattern': 'L03', 'reason': '哈马克 vs 沃什只有立场差异，无对等维度数据'},
        ],
    }
    save(aid, html, plan)


# ---------------- E2-005：T10 分组 + T11 小标题 + T01 ----------------
def build_E2_005():
    aid = 'E2-005'
    sm, e = make_source(aid)
    T = []
    T.append(op_subhead('p1', '起跑线提前了', 'The Starting Line Moved Up',
                        reason='开场：招聘季提前'))
    T.append(op_group(['p1', 'p2'], reason='开场组：现状 + 人物引语'))
    T.append(op_subhead('p3', '万里挑一', 'One in a Hundred',
                        reason='竞争烈度与选拔标准'))
    T.append(op_group(['p3', 'p4'], reason='选拔组：录取率 + 要找的人'))
    T.append(op_subhead('p5', '为什么量化交易不一样', 'Why Quant Is Different',
                        reason='p5 独立议题：经验 vs 数学模型'))
    T.append(op_group(['p5'], reason='单段成组：议题独立'))
    T.append(op_subhead('p6', '为了实习，他们说谎', 'Lying for the Internship',
                        reason='p6-p8 造假与焦虑'))
    T.append(op_group(['p6', 'p7', 'p8'], reason='收尾组：虚报年级 + 焦虑'))
    T.append(op_bold(sm, 'p1', 'cn', '可能已经太晚了', reason='开场钩子'))
    T.append(op_bold(sm, 'p3', 'cn', '录取率甚至低于1%', reason='核心数据点'))
    layouts = {'anchor_wraps': {}, 'after_blocks': {}}
    body = render_body_flow(sm, T, layouts)
    html = write_article(aid, body)
    plan = {
        'article_id': aid,
        'narrative_outline': '开场(p1-p2) → 选拔(p3-p4) → 量化逻辑(p5) → 造假与焦虑(p6-p8)',
        'decisions': [
            {'pattern': 'T10+T11', 'reason': '8 段长段落，四组议题；分组留白 + 小标题给节奏'},
            {'pattern': 'T01', 'count': 2, 'reason': '开场钩子与核心数据'},
        ],
        'rejected': [
            {'pattern': 'L02', 'reason': '无需要解释的术语或人物'},
            {'pattern': 'A03 key_figures', 'reason': '5万美元/30万美元已在正文充分展开，重复无意义'},
            {'pattern': 'T09', 'reason': '长段落内部因果完整，拆分破坏节奏'},
        ],
    }
    save(aid, html, plan)


if __name__ == '__main__':
    build_E1_007()
    build_E2_031()
    build_E3_036()
    build_E1_011()
    build_E2_005()
    print('全部完成')
