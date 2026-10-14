#!/usr/bin/env python3
"""WSJ Deep Read R3.1 — Editorial Experience.
Direction A (vermilion) + new type system (sans body / serif display)
+ real visual assets + adaptive desktop/mobile.
Articles: E1-005, E3-002. Content verbatim from final.json."""
import json, re, html, base64, sys

BASE = '/home/hatch/workspace/wsj-deep-read/2026-10-12'
ASSETS = f'{BASE}/cases/assets'
fj = json.load(open(f'{BASE}/final.json'))
E = {e['id']: e for e in fj}

def esc(t): return html.escape(t or '', quote=False)
def b64(f):
    return 'data:image/png;base64,' + base64.b64encode(open(f'{ASSETS}/{f}', 'rb').read()).decode()

PHOTO_EV = b64('b1-000.png')
PHOTO_TESLA = b64('tesla-ev.png')
PHOTO_SAUDI = b64('saudi-airport.png')
CHART_EV = b64('chart-ev-ports.png')

# reuse R3 primitives (direction A)
ns = {}
exec(open(f'{BASE}/cases/build_r3.py').read().split("if __name__")[0], ns)
for k in ['esc','cn_paras','en_paras','cn_sents','en_sents','ENP','EN5','P','P_html','em',
          'beat','kicker','head','story_open','story_close','cmp_label','pullquote',
          'stat_strip','timeline','claimevidence','bargraph','compare_duel','photo_cap']:
    globals()[k] = ns[k]

def figure(src, alt, cap_cn, cap_en, cls=''):
    return f'''<figure class="fig reveal {cls}">
<img src="{src}" alt="{esc(alt)}">
<figcaption><span class="k-cn">{esc(cap_cn)}</span><span class="k-en" hidden>{esc(cap_en)}</span></figcaption>
</figure>'''

# ============ E1-005 (no original photo in A1 edition) ============
def build_e1005():
    e = E['E1-005']; cp = cn_paras('E1-005'); h = [story_open(e, 'a')]
    h.append(beat([P(cp[0], EN5(0), cls='lede'), P(cp[1], EN5(1))]))
    h.append(cmp_label('关键数字', 'KEY FIGURES'))
    h.append(stat_strip([
        ('利雅得机场袭击 · 死亡','AIRPORT STRIKE · KILLED','至少12人','at least&nbsp;12','另有数百人受伤，许多人伤势严重','hundreds more injured, many severely', True),
        ('利雅得距胡塞控制区','RIYADH TO HOUTHI AREAS','约500英里','about&nbsp;500&nbsp;miles','首都部分地区已成战场','parts of the capital a battle zone', False),
        ('沙特年度预算','ANNUAL BUDGET','约3500亿美元','about&nbsp;$350&nbsp;billion','未来项目总成本高达数万亿美元','giga-project costs run to trillions', False),
        ('2026 年 GDP 预期','2026 GDP FORECAST','下降3.6%','shrink&nbsp;3.6%','沙特财政部最新预计','per the Saudi Finance Ministry', False),
    ]))
    h.append(beat([P_html(em(cp[2], ['至少12人','数百人'], hot=('至少12人',)), em(EN5(2), ['12','hundreds'])),
                   P(cp[3], EN5(3)), P(cp[4], EN5(4))]))
    h.append(cmp_label('时间线 · 冲突升级', 'TIMELINE · ESCALATION'))
    h.append(timeline([
        ('2015 年','2015', cn_sents(cp[21])[0], EN5(21)),
        ('2022 年','2022', cn_sents(cp[21])[2], EN5(21)),
        ('7 月','JUL', cn_sents(cp[20])[1], EN5(20)),
        ('9 月','SEP', cn_sents(cp[20])[2], EN5(20)),
        ('周四','THU', cn_sents(cp[11])[1], EN5(11)),
        ('周六','SAT', ' '.join(cn_sents(cp[2])[:2]), EN5(2)),
        ('周日','SUN', cn_sents(cp[10])[0], EN5(10)),
    ]))
    h.append(beat([P(cp[i], EN5(i)) for i in [5,6,7]]))
    h.append(claimevidence(
        '胡塞武装的情况已经得到控制。', 'the Houthi situation was under control.',
        '今年夏天 · 沙特官员向记者表示', 'This summer · Saudi officials briefed journalists',
        '周六，一枚胡塞导弹击中了沙特首都的国际机场，造成至少12人死亡，数百人受伤。',
        'On Saturday, a Houthi missile slammed into the Saudi capital\u2019s international airport, killing at least&nbsp;12 people and injuring hundreds more.',
        '周六 · 利雅得', 'Saturday · Riyadh',
        ev_hot_cn=('至少12人死亡',), ev_hot_en=('at least&nbsp;12 people',)))
    h.append(beat([P(cp[i], EN5(i)) for i in [8,9,10]] +
                  [P_html(em(cp[11], ['500英里']), em(EN5(11), ['500 miles'])),
                   P(cp[12], EN5(12))]))
    h.append(pullquote('任何军事行动都有可能使沙特更深入地卷入一场不对称的冲突。',
                       '"Any military response risks getting drawn in deeper to an asymmetric conflict."',
                       '克里斯蒂安·库茨·乌尔里克森 / 莱斯大学贝克研究所',
                       'Kristian Coates Ulrichsen / Baker Institute, Rice University'))
    h.append(beat([P(cp[13], EN5(13)), P(cp[14], EN5(14))]))
    h.append(beat([P_html(em(cp[15], ['数万亿美元','3500亿美元']), em(EN5(15), ['trillions','$350 billion'])),
                   P(cp[16], EN5(16))]))
    h.append(beat([P(cp[17], EN5(17)), P(cp[18], EN5(18)),
                   P_html(em(cp[19], ['3.6%'], hot=('3.6%',)), em(EN5(19), ['3.6%']))]))
    h.append(beat([P(cp[20], EN5(20)), P(cp[21], EN5(21))]))
    h.append(beat([P(cp[22], EN5(22)), P(cp[23], EN5(23))]))
    h.append(story_close()); return '\n'.join(h)

# ============ E3-002 (photo + original chart restored) ============
def build_e3002():
    e = E['E3-002']; cp = cn_paras('E3-002'); h = [story_open(e, 'a')]
    h.append(figure(PHOTO_EV,
        '一辆绿色电动汽车正在公共充电站充电，背景是一排带黄色防撞柱的充电桩',
        '新的充电站拥有更多的充电桩和更强大的充电器，以缩短等待时间。（Angus Mordant/彭博新闻，原图取自《华尔街日报》2026年10月12日 B1 版）',
        'New stations have more plugs and powerful chargers to cut down on wait time. (Angus Mordant/Bloomberg News, via WSJ Oct 12, 2026, p.B1)',
        cls='fig-hero'))
    h.append(beat([P(cp[0], ENP('E3-002',0))]))
    h.append(bargraph('新车销量份额 · 电动汽车', 'EV SHARE OF NEW-CAR SALES',
        [('2025 年第三季度 · 峰值','Q3 2025 · PEAK','约12%','about 12%',100,'verm'),
         ('目前 · 徘徊','NOW · HOVERING','6%左右','about 6%',50,'verm2')],
        '约占新车市场份额。来源：第 10 段。（编辑绘制）', 'Share of new-car market. Source: paragraph 9. (Editorial graphic)'))
    h.append(compare_duel(('电动汽车销量','EV SALES'), ('充电基础设施','CHARGING BUILDOUT'), [
        (('美国电动汽车的销量与去年相比下降了一半','U.S. EV sales fell by half from last year'),
         ('今年公共充电桩安装量预计与2025年持平，达历史最高','public charger installations set to match 2025, an all-time high')),
        (('2025年第三季度达峰值（约占新车12%），此后徘徊在6%左右','peaked in Q3 2025 at ~12% of new cars, since hovering around 6%'),
         ('美国目前拥有超过8万个公共快速充电桩','the U.S. now has 80,000+ public fast chargers')),
    ], '反差 · 销量与充电', 'CONTRAST · SALES VS CHARGING'))
    h.append(beat([P(cp[i], ENP('E3-002',i)) for i in [1,2,3]]))
    h.append(pullquote('我仍觉得大家都还在惊慌失措（往纸袋里喘气）。但增长是真实的。',
                       '"I still think people are breathing into paper bags," said Rick Wilmer, chief executive of ChargePoint. "But the growth is real."',
                       '里克·威尔默 / ChargePoint 首席执行官', 'Rick Wilmer, CEO, ChargePoint'))
    h.append(beat([P_html(em(cp[4], ['近2000个','超过12000个','3885个','19839个','8万']), em(ENP('E3-002',4), ['2,000','12,000','3,885','19,839','80,000'])),
                   P(cp[5], ENP('E3-002',5)), P(cp[6], ENP('E3-002',6))]))
    h.append(figure(CHART_EV,
        '2021年1月以来美国公共电动汽车快速充电桩数量按月统计面积图，持续增长至8万以上',
        '自2021年1月以来，美国公共电动汽车快速充电桩数量按月统计。注：数据截至2026年9月。来源：能源部。（原图取自《华尔街日报》2026年10月12日 B1 版）',
        'U.S. public EV fast-charging ports by month since January 2021. Note: Data through September 2026. Source: Energy Department. (Original chart, WSJ Oct 12, 2026, p.B1)',
        cls='fig-chart'))
    h.append(pullquote('我开始称之为"伟大的美国充电站建设"。',
                       '"I\'ve started calling it the Great American Build-Out," Ferro said.',
                       '比尔·费罗 / Paren 联合创始人兼首席技术官', 'Bill Ferro, co-founder & CTO, Paren'))
    h.append(beat([P(cp[7], ENP('E3-002',7)), P(cp[8], ENP('E3-002',8)),
                   P_html(em(cp[9], ['12%','6%'], hot=('12%','6%')), em(ENP('E3-002',9), ['12%','6%']))]))
    h.append(beat([P(cp[i], ENP('E3-002',i)) for i in [10,11,12,13,14]]))
    h.append(beat([P(cp[15], ENP('E3-002',15)), P(cp[16], ENP('E3-002',16))]))
    h.append(beat([P_html(em(cp[17], ['超过3500个','约4万个','46亿美元']), em(ENP('E3-002',17), ['3,500','40,000','$4.6 billion'])),
                   P(cp[18], ENP('E3-002',18))]))
    h.append(story_close()); return '\n'.join(h)

if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else '/dev/stdout'
    parts = [build_e1005(), build_e3002()]
    open(out, 'w').write('\n\n'.join(parts))
    print('r3.1 bytes:', sum(len(p) for p in parts))
