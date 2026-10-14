#!/usr/bin/env python3
"""WSJ Deep Read R2 — Editorial Typography & Integrated Composition.
5 articles. Content verbatim from final.json. v7 shell/CSS reused verbatim
(numeric data-priority, .story-body wrapper, no base overrides)."""
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
    ep = en_paras('E1-005'); j = E1005_REMAP.get(idx, idx); return ep[j] if j < len(ep) else ''

# ---------- primitives ----------
def P(cn, en='', cls=''):
    c = f' b-{cls}' if cls else ''
    return f'<p class="b-cn{c}">{esc(cn)}</p>\n<p class="b-en" hidden>{esc(en)}</p>'

def P_html(cn_html, en_html=''):
    """Pre-marked HTML (already escaped + spans)."""
    return f'<p class="b-cn">{cn_html}</p>\n<p class="b-en" hidden>{en_html}</p>'

def em(cn, nums):
    """Escape then wrap numbers in .num spans."""
    t = esc(cn)
    for n in nums:
        t = t.replace(esc(n), f'<span class="num">{esc(n)}</span>', 1)
    return t

def beat(items):
    return '<div class="beat">\n' + '\n'.join(items) + '\n</div>'

def kicker(e):
    pr = {'P1': 'P1 必读', 'P2': 'P2 重点', 'P3': 'P3 浏览'}[e['priority']]
    by = e.get('byline') or ''
    return f'''<div class="kicker"><span class="k-left"><span class="k-page">{esc(e.get('page',''))}</span><span class="k-pri">{esc(pr)}</span></span><span class="k-byline">{esc(by)}</span></div>'''

def head(e):
    t = f'''<h3 data-title-zh="{esc(e.get('title_cn'))}" data-title-en="{esc(e.get('title'))}">{esc(e.get('title_cn'))}</h3>'''
    d = ''
    if e.get('dek_cn'):
        d = f'<p class="dek-cn">{esc(e["dek_cn"])}</p>\n<p class="dek-en" hidden>{esc(e.get("dek") or "")}</p>'
    return t + '\n' + d

def story_open(e):
    num = {'P1': '1', 'P2': '2', 'P3': '3'}[e['priority']]
    return f'<article class="story" id="r-{e["id"]}" data-priority="{num}">\n{kicker(e)}\n{head(e)}\n<div class="story-body">'

def story_close(): return '</div>\n</article>'

def cmp_label(cn, en):
    return f'<div class="cmp-label"><span class="k-cn">{esc(cn)}</span><span class="k-en" hidden>{esc(en)}</span></div>'

def pullquote(q_cn, q_en, attr_cn, attr_en, scheme='a'):
    return f'''<div class="pullquote {scheme}">
<div class="pq-text"><span class="k-cn">{esc(q_cn)}</span><span class="k-en" hidden>{esc(q_en)}</span></div>
<div class="pq-attr"><span class="k-cn">— {esc(attr_cn)}</span><span class="k-en" hidden>— {esc(attr_en)}</span></div>
</div>'''

def stat_row(stats):
    items = []
    for k_cn, k_en, v_cn, v_en, d_cn, d_en in stats:
        lv = ' long' if len(v_cn) > 6 else ''
        items.append(f'''<div class="stat">
<div class="k"><span class="k-cn">{esc(k_cn)}</span><span class="k-en" hidden>{esc(k_en)}</span></div>
<div class="v{lv}"><span class="k-cn">{esc(v_cn)}</span><span class="k-en" hidden>{esc(v_en)}</span></div>
<div class="d"><span class="k-cn">{esc(d_cn)}</span><span class="k-en" hidden>{esc(d_en)}</span></div>
</div>''')
    return '<div class="stat-row">\n' + '\n'.join(items) + '\n</div>'

def keyfacts2(rows):
    items = []
    for k_cn, k_en, v_cn, v_en in rows:
        items.append(f'''<div class="kf2-row">
<div class="kf2-k"><span class="k-cn">{esc(k_cn)}</span><span class="k-en" hidden>{esc(k_en)}</span></div>
<div class="kf2-v"><span class="k-cn">{esc(v_cn)}</span><span class="k-en" hidden>{esc(v_en)}</span></div>
</div>''')
    return '<div class="keyfacts2">\n' + '\n'.join(items) + '\n</div>'

def timeline(nodes):
    items = []
    for t_cn, t_en, b_cn, b_en in nodes:
        items.append(f'''<div class="tl-item">
<div class="tl-time"><span class="k-cn">{esc(t_cn)}</span><span class="k-en" hidden>{esc(t_en)}</span></div>
<div class="tl-rail"><span class="tl-dot"></span></div>
<div class="tl-body"><span class="k-cn">{esc(b_cn)}</span><span class="k-en" hidden>{esc(b_en)}</span></div>
</div>''')
    return '<div class="timeline">\n' + '\n'.join(items) + '\n</div>'

def compare2(headL, headR, pairs, label_cn='对照', label_en='AT A GLANCE'):
    # pairs: [ ((txtL_cn,txtL_en),(txtR_cn,txtR_en)) ]; column headers shown once
    rows = [f'''<div class="crow chead">
<div class="ccell"><div class="cwho"><span class="k-cn">{esc(headL[0])}</span><span class="k-en" hidden>{esc(headL[1])}</span></div></div>
<div class="ccell"><div class="cwho"><span class="k-cn">{esc(headR[0])}</span><span class="k-en" hidden>{esc(headR[1])}</span></div></div>
</div>''']
    for tl, tr in pairs:
        rows.append(f'''<div class="crow">
<div class="ccell"><div class="cwhat"><span class="k-cn">{esc(tl[0])}</span><span class="k-en" hidden>{esc(tl[1])}</span></div></div>
<div class="ccell"><div class="cwhat"><span class="k-cn">{esc(tr[0])}</span><span class="k-en" hidden>{esc(tr[1])}</span></div></div>
</div>''')
    return f'{cmp_label(label_cn, label_en)}\n<div class="compare2">\n' + '\n'.join(rows) + '\n</div>'

def xref(cn, en=''):
    return f'<div class="xref"><span class="k-cn">{esc(cn)}</span><span class="k-en" hidden>{esc(en)}</span></div>'

def photo_cap(cn, en=''):
    return f'<div class="photo-cap"><span class="k-cn">{esc(cn)}</span><span class="k-en" hidden>{esc(en)}</span></div>'

def qa2(q_cn, q_en, a_cn_html, a_en_html):
    # answers are pre-escaped/marked HTML
    return f'''<div class="qa2">
<div class="qa2-q"><span class="qmark"><span class="k-cn">问</span><span class="k-en" hidden>Q</span></span><span class="k-cn">{esc(q_cn)}</span><span class="k-en" hidden>{esc(q_en)}</span></div>
<div class="qa2-a"><p class="b-cn">{a_cn_html}</p><p class="b-en" hidden>{a_en_html}</p></div>
</div>'''

# ============ E1-001 What's News (refined list) ============
def build_e1001():
    e = E['E1-001']; h = [story_open(e)]
    for lang_body, suffix in [(e.get('body_cn',''), 'cn'), (e.get('body_en',''), 'en')]:
        hidden = ' hidden' if suffix == 'en' else ''
        groups, cur = [], None
        for line in lang_body.split('\n'):
            s = line.strip()
            if not s: continue
            if s.startswith('-'):
                item = s[1:].strip()
                m = re.search(r'（([A-Z]\d+)）\s*$', item) or re.search(r'\(([A-Z]\d+)\)\s*$', item)
                page = m.group(1) if m else ''
                if m: item = item[:m.start()].strip()
                cur[1].append((page, item))
            else:
                cur = (s, []); groups.append(cur)
        gh = [f'<div class="digest2-lang-{suffix}"{hidden}>']
        for gname, items in groups:
            unit = '条' if suffix == 'cn' else 'items'
            gh.append(f'''<div class="digest2-group">
<div class="digest2-head"><span class="t">{esc(gname)}</span><span class="n">{len(items)} {unit}</span></div>''')
            for page, item in items:
                gh.append(f'''<div class="digest2-item"><div class="page-ref">{esc(page)}</div><div class="digest2-text">{esc(item)}</div></div>''')
            gh.append('</div>')
        gh.append('</div>')
        h.append('\n'.join(gh))
    h.append(story_close()); return '\n'.join(h)

# ============ E1-004 ============
def build_e1004():
    e = E['E1-004']; cp = cn_paras('E1-004'); h = [story_open(e)]
    h.append(beat([P(cp[0], ENP('E1-004',0), cls='lede'),
                   P(cp[3], ENP('E1-004',3))]))
    h.append(cmp_label('时间线 · 过去三天', 'TIMELINE · LAST THREE DAYS'))
    h.append(timeline([
        ('周五','FRI', cn_sents(cp[14])[0], ENP('E1-004',14)),
        ('周六','SAT', cn_sents(cp[13])[0], ENP('E1-004',13)),
        ('周日','SUN', cn_sents(cp[1])[0], ENP('E1-004',1)),
        ('周日','SUN', cn_sents(cp[2])[1], ''.join(en_sents(ENP('E1-004',2))[1:])),
    ]))
    h.append(beat([P(cn_sents(cp[2])[0], en_sents(ENP('E1-004',2))[0]),
                   xref('[请参见A8页，标题为“俄罗斯石油协议面临阻力”:]', 'See page A8, "Russia Oil Deal Faces Pushback"')]))
    h.append(beat([P(cp[i], ENP('E1-004',i)) for i in [5,6,7,8]]))
    h.append(pullquote('乌克兰想要和平。问题是俄罗斯是否也想要。',
                       '"Ukraine wants peace. The question is whether Russia does," Zelensky said in a social-media post.',
                       '弗拉基米尔·泽连斯基', 'Volodymyr Zelensky'))
    h.append(beat([P(cp[9], ENP('E1-004',9)), P(cp[10], ENP('E1-004',10)),
                   P(cp[11], ENP('E1-004',11))]))
    h.append(cmp_label('联署参议员 · 7 人', 'SIGNATORIES · 7'))
    h.append('''<div class="signer-groups">
<div class="signer-group"><div class="sg-party"><span class="k-cn">共和党 · 4</span><span class="k-en" hidden>REPUBLICANS · 4</span></div>
<div class="sg-name"><span class="k-cn">苏珊·柯林斯（缅因州）</span><span class="k-en" hidden>Susan Collins (Maine)</span></div>
<div class="sg-name"><span class="k-cn">丽莎·穆尔科斯基（阿拉斯加州）</span><span class="k-en" hidden>Lisa Murkowski (Alaska)</span></div>
<div class="sg-name"><span class="k-cn">约翰·柯蒂斯（犹他州）</span><span class="k-en" hidden>John Curtis (Utah)</span></div>
<div class="sg-name"><span class="k-cn">汤姆·蒂利斯（北卡罗来纳州）</span><span class="k-en" hidden>Thom Tillis (North Carolina)</span></div></div>
<div class="signer-group"><div class="sg-party"><span class="k-cn">民主党 · 3</span><span class="k-en" hidden>DEMOCRATS · 3</span></div>
<div class="sg-name"><span class="k-cn">珍妮·沙欣（新罕布什尔州）</span><span class="k-en" hidden>Jeanne Shaheen (New Hampshire)</span></div>
<div class="sg-name"><span class="k-cn">罗恩·怀登（俄勒冈州）</span><span class="k-en" hidden>Ron Wyden (Oregon)</span></div>
<div class="sg-name"><span class="k-cn">理查德·布卢门撒尔（康涅狄格州）</span><span class="k-en" hidden>Richard Blumenthal (Connecticut)</span></div></div>
</div>''')
    h.append(beat([P(cp[12], ENP('E1-004',12))]))
    h.append(compare2(('特朗普称','TRUMP SAYS'), ('各方回应','RESPONSES'), [
        (('乌克兰和俄罗斯之间立即达成"能源停火"协议','an immediate "ENERGY CEASEFIRE" between Ukraine and Russia'),
         ('莫斯科迄今拒绝；无协议迹象；普京已拒绝提议','Moscow has refused so far; no sign of a deal; Putin rejected the proposal')),
        (('俄罗斯柴油供应是解决方案的一部分，可压低油价','Russian diesel supply is part of the solution to lower fuel prices'),
         ('分析人士：影响可能微乎其微，"中东地区更为重要"','Analysts: impact likely minimal; "the Middle East matters more"')),
        (('泽连斯基应对战争持续和全球油价上涨负责','Zelensky is responsible for the continued war and higher global fuel prices'),
         ('泽连斯基：若莫斯科停炸能源网络，愿停袭俄炼油厂','Zelensky: will halt refinery strikes if Moscow stops bombing energy networks')),
    ], '各方表述对照', 'STATEMENTS AT A GLANCE'))
    h.append(beat([P(cp[i], ENP('E1-004',i)) for i in [15,16,17]]))
    h.append(pullquote('从字面上看，特朗普与魔鬼达成了协议。',
                       '"Literally, Trump has made a deal with the devil," said Rep. Donald Norcross (D., N.J.).',
                       '唐纳德·诺克罗斯 / 民主党，新泽西州', 'Rep. Donald Norcross (D., N.J.)'))
    h.append(beat([P(cp[i], ENP('E1-004',i)) for i in [18,19,20,21,22]]))
    h.append(beat([P_html(em(cp[23], ['196次','20次']),
                          em(ENP('E1-004',23), ['196','20']))]))
    h.append(cmp_label('关键数字', 'KEY FIGURES'))
    h.append(stat_row([
        ('过去一周 · 电力系统','PAST WEEK · POWER GRID','196次','196','俄罗斯对乌克兰电力系统的袭击','Russian strikes on Ukraine\u2019s power grid'),
        ('过去一周 · 油气设施','PAST WEEK · OIL & GAS','20次','20','对乌克兰石油和天然气基础设施的袭击','strikes on oil and gas infrastructure'),
    ]))
    h.append(story_close()); return '\n'.join(h)



# ============ E1-005 Saudi (scheme a/b) ============
def build_e1005(scheme='a'):
    e = E['E1-005']; cp = cn_paras('E1-005'); h = [story_open(e)]
    lede_cls = 'lede' if scheme == 'a' else ''
    h.append(beat([P(cp[0], EN5(0), cls=lede_cls), P(cp[1], EN5(1))]))
    if scheme == 'a':
        h.append(cmp_label('关键数字', 'KEY FIGURES'))
        h.append(stat_row([
            ('利雅得机场袭击 · 死亡','AIRPORT STRIKE · KILLED','至少12人','at least 12','另有数百人受伤，许多人伤势严重','hundreds more injured, many severely'),
            ('利雅得距胡塞控制区','RIYADH TO HOUTHI AREAS','约500英里','about 500 miles','首都部分地区已成战场','parts of the capital a battle zone'),
            ('沙特年度预算','ANNUAL BUDGET','约3500亿美元','about $350 billion','未来项目总成本高达数万亿美元','giga-project costs run to trillions'),
            ('2026 年 GDP 预期','2026 GDP FORECAST','下降3.6%','shrink 3.6%','沙特财政部最新预计','per the Saudi Finance Ministry'),
        ]))
    h.append(beat([P_html(em(cp[2], ['至少12人','数百人']), em(EN5(2), ['12','hundreds'])),
                   P(cp[3], EN5(3)), P(cp[4], EN5(4))]))
    h.append(cmp_label('时间线 · 冲突升级', 'TIMELINE · ESCALATION'))
    tl = [('2015 年','2015', cn_sents(cp[21])[0], EN5(21)),
          ('2022 年','2022', cn_sents(cp[21])[2], EN5(21)),
          ('7 月','JUL', cn_sents(cp[20])[1], EN5(20)),
          ('9 月','SEP', cn_sents(cp[20])[2], EN5(20)),
          ('周四','THU', cn_sents(cp[11])[1], EN5(11)),
          ('周六','SAT', ' '.join(cn_sents(cp[2])[:2]), EN5(2)),
          ('周日','SUN', cn_sents(cp[10])[0], EN5(10))]
    h.append(timeline(tl if scheme == 'a' else [(t[0],t[1],t[2][:60],t[3]) for t in tl]))
    h.append(beat([P(cp[i], EN5(i)) for i in [5,6,7]]))
    h.append(beat([P(cp[i], EN5(i)) for i in [8,9,10]] +
                  [P_html(em(cp[11], ['500英里']), em(EN5(11), ['500 miles'])),
                   P(cp[12], EN5(12))]))
    h.append(pullquote('任何军事行动都有可能使沙特更深入地卷入一场不对称的冲突。',
                       '"Any military response risks getting drawn in deeper to an asymmetric conflict."',
                       '克里斯蒂安·库茨·乌尔里克森 / 莱斯大学贝克研究所',
                       'Kristian Coates Ulrichsen / Baker Institute, Rice University', scheme=scheme))
    h.append(beat([P(cp[13], EN5(13)), P(cp[14], EN5(14))]))
    if scheme == 'b':
        h.append(cmp_label('经济代价', 'ECONOMIC TOLL'))
    h.append(beat([P_html(em(cp[15], ['数万亿美元','3500亿美元']), em(EN5(15), ['trillions','$350 billion'])),
                   P(cp[16], EN5(16))]))
    h.append(beat([P(cp[17], EN5(17)), P(cp[18], EN5(18)),
                   P_html(em(cp[19], ['3.6%']), em(EN5(19), ['3.6%']))]))
    h.append(beat([P(cp[20], EN5(20)), P(cp[21], EN5(21))]))
    h.append(beat([P(cp[22], EN5(22)), P(cp[23], EN5(23))]))
    h.append(story_close()); return '\n'.join(h)

# ============ E3-002 EV ============
def build_e3002():
    e = E['E3-002']; cp = cn_paras('E3-002'); h = [story_open(e)]
    h.append(beat([P(cp[0], ENP('E3-002',0))]))
    h.append(compare2(('电动汽车销量','EV SALES'), ('充电基础设施','CHARGING BUILDOUT'), [
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
    h.append(pullquote('我开始称之为"伟大的美国充电站建设"。',
                       '"I\'ve started calling it the Great American Build-Out," Ferro said.',
                       '比尔·费罗 / Paren 联合创始人兼首席技术官', 'Bill Ferro, co-founder & CTO, Paren'))
    h.append(beat([P(cp[7], ENP('E3-002',7)), P(cp[8], ENP('E3-002',8)),
                   P_html(em(cp[9], ['12%','6%']), em(ENP('E3-002',9), ['12%','6%']))]))
    h.append(beat([P(cp[i], ENP('E3-002',i)) for i in [10,11,12,13,14]]))
    h.append(beat([P(cp[15], ENP('E3-002',15)), P(cp[16], ENP('E3-002',16))]))
    h.append(beat([P_html(em(cp[17], ['超过3500个','约4万个','46亿美元']), em(ENP('E3-002',17), ['3,500','40,000','$4.6 billion'])),
                   P(cp[18], ENP('E3-002',18))]))
    h.append(photo_cap('[图表：自2021年1月以来，美国公共电动汽车快速充电桩数量按月统计。注：数据截至2026年9月。来源：能源部。]', ENP('E3-002',19)))
    h.append(photo_cap('[照片说明：新的充电站拥有更多的充电桩和更强大的充电器，以缩短等待时间。（Angus Mordant/彭博新闻）]', ENP('E3-002',20)))
    h.append(photo_cap('[照片说明：埃隆·马斯克的特斯拉公司今年增加了超过3500个快速充电桩。]', ENP('E3-002',21)))
    h.append(story_close()); return '\n'.join(h)

# ============ E3-003 Delta ============
def build_e3003():
    e = E['E3-003']; cp = cn_paras('E3-003'); h = [story_open(e)]
    h.append(cmp_label('要点', 'KEY FACTS'))
    h.append(keyfacts2([
        ('燃油成本增加','FUEL COST HIT','60亿美元','$6 billion'),
        ('全年预期','FULL-YEAR OUTLOOK','大幅下调','sharply lowered'),
        ('第四季度收入预期','Q4 REVENUE','增长20%','up 20%'),
    ]))
    h.append(beat([P_html(em(cp[0], ['60亿美元']), em(ENP('E3-003',0), ['$6 billion'])),
                   P(cp[1], ENP('E3-003',1)), P(cp[2], ENP('E3-003',2)), P(cp[3], ENP('E3-003',3))]))
    h.append(qa2(cp[4], ENP('E3-003',4), esc(cp[5]), esc(ENP('E3-003',5))))
    h.append(qa2(cp[6], ENP('E3-003',6),
                 em(cp[7], ['20%']), em(ENP('E3-003',7), ['20%'])))
    h.append(qa2(cp[8], ENP('E3-003',8), esc(cp[9]), esc(ENP('E3-003',9))))
    h.append(pullquote('我们已经在这方面努力了15年。', '"We\'ve been at it for 15 years," Bastian said.',
                       '埃德·巴斯蒂安 / 达美航空首席执行官', 'Ed Bastian, CEO, Delta Air Lines'))
    h.append(qa2(cp[10], ENP('E3-003',10), esc(cp[11]), esc(ENP('E3-003',11))))
    h.append(photo_cap('[照片：埃德·巴斯蒂安。（Anindito Mukherjee/彭博社）]', ENP('E3-003',12)))
    h.append(story_close()); return '\n'.join(h)

if __name__ == '__main__':
    scheme = sys.argv[2] if len(sys.argv) > 2 else 'a'
    out = sys.argv[1] if len(sys.argv) > 1 else '/dev/stdout'
    parts = [build_e1001(), build_e1004(), build_e1005(scheme), build_e3002(), build_e3003()]
    open(out, 'w').write('\n\n'.join(parts))
    print('r2 bytes:', sum(len(p) for p in parts), 'scheme:', scheme)
