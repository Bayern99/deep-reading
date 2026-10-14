#!/usr/bin/env python3
"""WSJ Deep Read R3 — Editorial Design Exploration.
Two directions x two articles (E1-005 longform, E3-002 data).
A: Vermilion Editorial (print-expressive). B: Petrol System (digital-systematic).
Content verbatim from final.json."""
import json, re, html, sys

BASE = '/home/hatch/workspace/wsj-deep-read/2026-10-12'
fj = json.load(open(f'{BASE}/final.json'))
E = {e['id']: e for e in fj}

def esc(t): return html.escape(t or '', quote=False)
def cn_paras(eid): return [p for p in (E[eid].get('body_cn') or '').split('\n\n')]
def en_paras(eid): return [p for p in (E[eid].get('body_en') or '').split('\n\n')]
def cn_sents(p): return [s.strip() for s in re.split(r'(?<=[。！？])', p.strip()) if s.strip()]
def en_sents(p): return [s.strip() for s in re.split(r'(?<=[.!?])\s+', p.strip()) if s.strip()]
def ENP(eid, idx):
    ep = en_paras(eid); return ep[idx] if idx < len(ep) else ''
E1005_REMAP = {0:0,1:1,2:2,3:3,4:4,5:5,6:6,7:9,8:10,9:11,10:12,11:13,12:14,13:15,14:16,15:17,16:18,17:19,18:20,19:21,20:22,21:23,22:24,23:25}
def EN5(idx):
    ep = en_paras('E1-005')
    if idx == 6:
        # EN[6] 在页跳转处断句，EN[7] 是转页标记，EN[8] 是下半句——合并
        return (ep[6].rstrip() + ' ' + ep[8].strip()).replace('  ', ' ')
    j = E1005_REMAP.get(idx, idx); return ep[j] if j < len(ep) else ''

# ---------- primitives ----------
def P(cn, en='', cls=''):
    c = f' b-{cls}' if cls else ''
    return f'<p class="b-cn{c}">{esc(cn)}</p>\n<p class="b-en" hidden>{esc(en)}</p>'

def P_html(cn_html, en_html=''):
    return f'<p class="b-cn">{cn_html}</p>\n<p class="b-en" hidden>{en_html}</p>'

def em(cn, nums, hot=()):
    t = esc(cn)
    for n in nums:
        cls = 'num hot' if n in hot else 'num'
        t = t.replace(esc(n), f'<span class="{cls}">{esc(n)}</span>', 1)
    return t

def beat(items, mnote_cn='', mnote_en=''):
    inner = '\n'.join(items)
    if mnote_cn:
        return (f'<div class="beat3"><div class="mnote"><span class="k-cn">{esc(mnote_cn)}</span>'
                f'<span class="k-en" hidden>{esc(mnote_en)}</span></div>\n'
                f'<div class="beat3-body">\n{inner}\n</div></div>')
    return '<div class="beat">\n' + inner + '\n</div>'

def kicker(e):
    pr = {'P1': 'P1 必读', 'P2': 'P2 重点', 'P3': 'P3 浏览'}[e['priority']]
    by = e.get('byline') or ''
    return f'''<div class="kicker"><span class="k-left"><span class="k-page">{esc(e.get('page',''))}</span><span class="k-pri">{esc(pr)}</span></span><span class="k-byline">{esc(by)}</span></div>'''

def head(e):
    t = f'''<h2 data-title-zh="{esc(e.get('title_cn'))}" data-title-en="{esc(e.get('title'))}">{esc(e.get('title_cn'))}</h2>'''
    d = ''
    if e.get('dek_cn'):
        d = f'<p class="dek-cn">{esc(e["dek_cn"])}</p>\n<p class="dek-en" hidden>{esc(e.get("dek") or "")}</p>'
    return t + '\n' + d

def story_open(e, dirn):
    num = {'P1': '1', 'P2': '2', 'P3': '3'}[e['priority']]
    return f'<article class="story dir-{dirn}" id="r3{e["id"]}" data-priority="{num}">\n{kicker(e)}\n{head(e)}\n<div class="story-body">'

def story_close(): return '</div>\n</article>'

def cmp_label(cn, en):
    return f'<div class="cmp-label"><span class="k-cn">{esc(cn)}</span><span class="k-en" hidden>{esc(en)}</span></div>'

def pullquote(q_cn, q_en, attr_cn, attr_en):
    return f'''<div class="pullquote reveal">
<div class="pq-text"><span class="k-cn">{esc(q_cn)}</span><span class="k-en" hidden>{esc(q_en)}</span></div>
<div class="pq-attr"><span class="k-cn">— {esc(attr_cn)}</span><span class="k-en" hidden>— {esc(attr_en)}</span></div>
</div>'''

def stat_strip(stats):
    items = []
    for k_cn, k_en, v_cn, v_en, d_cn, d_en, hot in stats:
        hc = ' hot' if hot else ''
        lv = ' long' if len(v_cn) > 6 else ''
        items.append(f'''<div class="stat">
<div class="k"><span class="k-cn">{esc(k_cn)}</span><span class="k-en" hidden>{esc(k_en)}</span></div>
<div class="v{lv}{hc}"><span class="k-cn">{esc(v_cn)}</span><span class="k-en" hidden>{esc(v_en)}</span></div>
<div class="d"><span class="k-cn">{esc(d_cn)}</span><span class="k-en" hidden>{esc(d_en)}</span></div>
</div>''')
    return '<div class="stat-strip reveal">\n' + '\n'.join(items) + '\n</div>'

def timeline(nodes):
    items = []
    for t_cn, t_en, b_cn, b_en in nodes:
        items.append(f'''<div class="tl-item">
<div class="tl-time"><span class="k-cn">{esc(t_cn)}</span><span class="k-en" hidden>{esc(t_en)}</span></div>
<div class="tl-rail"><span class="tl-dot"></span></div>
<div class="tl-body"><span class="k-cn">{esc(b_cn)}</span><span class="k-en" hidden>{esc(b_en)}</span></div>
</div>''')
    return '<div class="timeline reveal">\n' + '\n'.join(items) + '\n</div>'

def claimevidence(claim_cn, claim_en, claim_src_cn, claim_src_en,
                  ev_cn, ev_en, ev_src_cn, ev_src_en,
                  label_cn='主张与现实', label_en='CLAIM VS REALITY',
                  ev_hot_cn=(), ev_hot_en=()):
    ev_c = esc(ev_cn)
    for h in ev_hot_cn:
        ev_c = ev_c.replace(esc(h), f'<span class="hot">{esc(h)}</span>', 1)
    ev_e = esc(ev_en)
    for h in ev_hot_en:
        ev_e = ev_e.replace(esc(h), f'<span class="hot">{esc(h)}</span>', 1)
    return f'''{cmp_label(label_cn, label_en)}
<div class="claimev reveal">
<div class="ce-block ce-claim">
<div class="ce-tag"><span class="k-cn">此前称</span><span class="k-en" hidden>CLAIMED</span></div>
<div class="ce-text"><span class="k-cn">{esc(claim_cn)}</span><span class="k-en" hidden>{esc(claim_en)}</span></div>
<div class="ce-src"><span class="k-cn">{esc(claim_src_cn)}</span><span class="k-en" hidden>{esc(claim_src_en)}</span></div>
</div>
<div class="ce-block ce-ev">
<div class="ce-tag"><span class="k-cn">随后发生</span><span class="k-en" hidden>WHAT HAPPENED</span></div>
<div class="ce-text"><span class="k-cn">{ev_c}</span><span class="k-en" hidden>{ev_e}</span></div>
<div class="ce-src"><span class="k-cn">{esc(ev_src_cn)}</span><span class="k-en" hidden>{esc(ev_src_en)}</span></div>
</div>
</div>'''

def _bar_label(cn, en):
    def split(t):
        return [x.strip() for x in t.split('·', 1)] if '·' in t else [t.strip(), '']
    tc, jc = split(cn); te, je = split(en)
    j = f'<span class="bl-j"><span class="k-cn">{esc(jc)}</span><span class="k-en" hidden>{esc(je)}</span></span>' if jc else ''
    return f'<span class="bl-t"><span class="k-cn">{esc(tc)}</span><span class="k-en" hidden>{esc(te)}</span></span>{j}'

def bargraph(title_cn, title_en, bars, note_cn='', note_en=''):
    # bars: [(label_cn,label_en,value,pct,color_class)]
    rows = []
    for lc, le, v_cn, v_en, pct, cc in bars:
        rows.append(f'''<div class="bar-row">
<div class="bar-label">{_bar_label(lc, le)}</div>
<div class="bar-track"><div class="bar-fill {cc}" style="width:{pct}%"></div></div>
<div class="bar-val"><span class="k-cn">{esc(v_cn)}</span><span class="k-en" hidden>{esc(v_en)}</span></div>
</div>''')
    note = f'<div class="bar-note"><span class="k-cn">{esc(note_cn)}</span><span class="k-en" hidden>{esc(note_en)}</span></div>' if note_cn else ''
    return f'''{cmp_label(title_cn, title_en)}
<div class="bargraph reveal">\n{chr(10).join(rows)}\n{note}\n</div>'''

def compare_duel(headL, headR, pairs, label_cn, label_en):
    # R3.5-fix: 配对块结构——标签贴着内容，手机堆叠不断裂；不用颜色编码
    blocks = []
    for tl, tr in pairs:
        blocks.append(f'''<div class="cpair">
<div class="cside"><div class="plab"><span class="k-cn">{esc(headL[0])}</span><span class="k-en" hidden>{esc(headL[1])}</span></div>
<div class="ptext"><span class="k-cn">{esc(tl[0])}</span><span class="k-en" hidden>{esc(tl[1])}</span></div></div>
<div class="cside"><div class="plab"><span class="k-cn">{esc(headR[0])}</span><span class="k-en" hidden>{esc(headR[1])}</span></div>
<div class="ptext"><span class="k-cn">{esc(tr[0])}</span><span class="k-en" hidden>{esc(tr[1])}</span></div></div>
</div>''')
    return f'{cmp_label(label_cn, label_en)}\n<div class="compare-duel reveal">\n' + '\n'.join(blocks) + '\n</div>'

def photo_cap(cn, en=''):
    return f'<div class="photo-cap"><span class="k-cn">{esc(cn)}</span><span class="k-en" hidden>{esc(en)}</span></div>'

# ============ E1-005 ============
def build_e1005(dirn):
    e = E['E1-005']; cp = cn_paras('E1-005'); h = [story_open(e, dirn)]
    A = (dirn == 'a')
    hot12 = ('至少12人',) if True else ()
    h.append(beat([P(cp[0], EN5(0), cls='lede'), P(cp[1], EN5(1))],
                  mnote_cn='' if A else '开篇', mnote_en='' if A else 'LEDE'))
    h.append(cmp_label('关键数字', 'KEY FIGURES'))
    h.append(stat_strip([
        ('利雅得机场袭击 · 死亡','AIRPORT STRIKE · KILLED','至少12人','at least 12','另有数百人受伤，许多人伤势严重','hundreds more injured, many severely', True),
        ('利雅得距胡塞控制区','RIYADH TO HOUTHI AREAS','约500英里','about 500 miles','首都部分地区已成战场','parts of the capital a battle zone', False),
        ('沙特年度预算','ANNUAL BUDGET','约3500亿美元','about $350 billion','未来项目总成本高达数万亿美元','giga-project costs run to trillions', False),
        ('2026 年 GDP 预期','2026 GDP FORECAST','下降3.6%','shrink 3.6%','沙特财政部最新预计','per the Saudi Finance Ministry', not A),
    ]))
    h.append(beat([P_html(em(cp[2], ['至少12人','数百人'], hot=('至少12人',)), em(EN5(2), ['12','hundreds'])),
                   P(cp[3], EN5(3)), P(cp[4], EN5(4))],
                  mnote_cn='' if A else '袭击', mnote_en='' if A else 'ATTACK'))
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
    h.append(beat([P(cp[i], EN5(i)) for i in [5,6,7]],
                  mnote_cn='' if A else '升级', mnote_en='' if A else 'ESCALATION'))
    h.append(claimevidence(
        '胡塞武装的情况已经得到控制。', 'the Houthi situation was under control.',
        '今年夏天 · 沙特官员向记者表示', 'This summer · Saudi officials briefed journalists',
        '周六，一枚胡塞导弹击中了沙特首都的国际机场，造成至少12人死亡，数百人受伤。',
        'On Saturday, a Houthi missile slammed into the Saudi capital\u2019s international airport, killing at least 12 people and injuring hundreds more.',
        '周六 · 利雅得', 'Saturday · Riyadh'))
    h.append(beat([P(cp[i], EN5(i)) for i in [8,9,10]] +
                  [P_html(em(cp[11], ['500英里']), em(EN5(11), ['500 miles'])),
                   P(cp[12], EN5(12))],
                  mnote_cn='' if A else '代价', mnote_en='' if A else 'COST'))
    h.append(pullquote('任何军事行动都有可能使沙特更深入地卷入一场不对称的冲突。',
                       '"Any military response risks getting drawn in deeper to an asymmetric conflict."',
                       '克里斯蒂安·库茨·乌尔里克森 / 莱斯大学贝克研究所',
                       'Kristian Coates Ulrichsen / Baker Institute, Rice University'))
    h.append(beat([P(cp[13], EN5(13)), P(cp[14], EN5(14))],
                  mnote_cn='' if A else '困境', mnote_en='' if A else 'DILEMMA'))
    h.append(beat([P_html(em(cp[15], ['数万亿美元','3500亿美元']), em(EN5(15), ['trillions','$350 billion'])),
                   P(cp[16], EN5(16))],
                  mnote_cn='' if A else '经济账', mnote_en='' if A else 'ECONOMY'))
    h.append(beat([P(cp[17], EN5(17)), P(cp[18], EN5(18)),
                   P_html(em(cp[19], ['3.6%'], hot=('3.6%',) if A else ()), em(EN5(19), ['3.6%']))],
                  mnote_cn='' if A else '经济账', mnote_en='' if A else 'ECONOMY'))
    h.append(beat([P(cp[20], EN5(20)), P(cp[21], EN5(21))],
                  mnote_cn='' if A else '历史', mnote_en='' if A else 'HISTORY'))
    h.append(beat([P(cp[22], EN5(22)), P(cp[23], EN5(23))],
                  mnote_cn='' if A else '外交', mnote_en='' if A else 'DIPLOMACY'))
    h.append(story_close()); return '\n'.join(h)

# ============ E3-002 ============
def build_e3002(dirn):
    e = E['E3-002']; cp = cn_paras('E3-002'); h = [story_open(e, dirn)]
    A = (dirn == 'a')
    h.append(beat([P(cp[0], ENP('E3-002',0))], mnote_cn='' if A else '开篇', mnote_en='' if A else 'LEDE'))
    h.append(bargraph('新车销量份额 · 电动汽车', 'EV SHARE OF NEW-CAR SALES',
        [('2025 年第三季度 · 峰值','Q3 2025 · PEAK','约12%','about 12%',100 if A else 80,'verm' if A else 'petrol'),
         ('目前 · 徘徊','NOW · HOVERING','6%左右','about 6%',50 if A else 40,'verm2' if A else 'petrol2')],
        '约占新车市场份额。来源：第 10 段。', 'Share of new-car market. Source: paragraph 10.'))
    h.append(compare_duel(('电动汽车销量','EV SALES'), ('充电基础设施','CHARGING BUILDOUT'), [
        (('美国电动汽车的销量与去年相比下降了一半','U.S. EV sales fell by half from last year'),
         ('今年公共充电桩安装量预计与2025年持平，达历史最高','public charger installations set to match 2025, an all-time high')),
        (('2025年第三季度达峰值（约占新车12%），此后徘徊在6%左右','peaked in Q3 2025 at ~12% of new cars, since hovering around 6%'),
         ('美国目前拥有超过8万个公共快速充电桩','the U.S. now has 80,000+ public fast chargers')),
    ], '反差 · 销量与充电', 'CONTRAST · SALES VS CHARGING'))
    h.append(beat([P(cp[i], ENP('E3-002',i)) for i in [1,2,3]],
                  mnote_cn='' if A else '现状', mnote_en='' if A else 'NOW'))
    h.append(pullquote('我仍觉得大家都还在惊慌失措（往纸袋里喘气）。但增长是真实的。',
                       '"I still think people are breathing into paper bags," said Rick Wilmer, chief executive of ChargePoint. "But the growth is real."',
                       '里克·威尔默 / ChargePoint 首席执行官', 'Rick Wilmer, CEO, ChargePoint'))
    h.append(beat([P_html(em(cp[4], ['近2000个','超过12000个','3885个','19839个','8万']), em(ENP('E3-002',4), ['2,000','12,000','3,885','19,839','80,000'])),
                   P(cp[5], ENP('E3-002',5)), P(cp[6], ENP('E3-002',6))],
                  mnote_cn='' if A else '8万+ 快充桩', mnote_en='' if A else '80,000+ CHARGERS'))
    h.append(pullquote('我开始称之为"伟大的美国充电站建设"。',
                       '"I\'ve started calling it the Great American Build-Out," Ferro said.',
                       '比尔·费罗 / Paren 联合创始人兼首席技术官', 'Bill Ferro, co-founder & CTO, Paren'))
    h.append(beat([P(cp[7], ENP('E3-002',7)), P(cp[8], ENP('E3-002',8)),
                   P_html(em(cp[9], ['12%','6%'], hot=('12%','6%')), em(ENP('E3-002',9), ['12%','6%']))],
                  mnote_cn='' if A else '12% → 6%', mnote_en='' if A else '12% TO 6%'))
    h.append(beat([P(cp[i], ENP('E3-002',i)) for i in [10,11,12,13,14]],
                  mnote_cn='' if A else '行业', mnote_en='' if A else 'INDUSTRY'))
    h.append(beat([P(cp[15], ENP('E3-002',15)), P(cp[16], ENP('E3-002',16))]))
    h.append(beat([P_html(em(cp[17], ['超过3500个','约4万个','46亿美元']), em(ENP('E3-002',17), ['3,500','40,000','$4.6 billion'])),
                   P(cp[18], ENP('E3-002',18))],
                  mnote_cn='' if A else '特斯拉', mnote_en='' if A else 'TESLA'))
    h.append(photo_cap('[图表：自2021年1月以来，美国公共电动汽车快速充电桩数量按月统计。注：数据截至2026年9月。来源：能源部。]', ENP('E3-002',19)))
    h.append(photo_cap('[照片说明：新的充电站拥有更多的充电桩和更强大的充电器，以缩短等待时间。（Angus Mordant/彭博新闻）]', ENP('E3-002',20)))
    h.append(photo_cap('[照片说明：埃隆·马斯克的特斯拉公司今年增加了超过3500个快速充电桩。]', ENP('E3-002',21)))
    h.append(story_close()); return '\n'.join(h)

if __name__ == '__main__':
    import sys as _s
    dirn = _s.argv[2] if len(_s.argv) > 2 else 'a'
    out = _s.argv[1] if len(_s.argv) > 1 else '/dev/stdout'
    parts = [build_e1005(dirn), build_e3002(dirn)]
    open(out, 'w').write('\n\n'.join(parts))
    print('r3 bytes:', sum(len(p) for p in parts), 'dir:', dirn)
