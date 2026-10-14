#!/usr/bin/env python3
"""WSJ Deep Read — Article Interior Design Prototype (5 articles).
Content: verbatim from final.json (CN + EN). Only presentation changes."""
import json, re, html, sys

BASE = '/home/hatch/workspace/wsj-deep-read/2026-10-12'
fj = json.load(open(f'{BASE}/final.json'))
E = {e['id']: e for e in fj}
WARN = []

def esc(t):
    return html.escape(t or '', quote=False)

def cn_paras(eid):
    return [p for p in (E[eid].get('body_cn') or '').split('\n\n')]

def en_paras(eid):
    return [p for p in (E[eid].get('body_en') or '').split('\n\n')]

def cn_sents(p):
    return [s.strip() for s in re.split(r'(?<=[。！？])', p.strip()) if s.strip()]

def en_sents(p):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', p.strip()) if s.strip()]

def find_en(eid, *kws):
    for p in en_paras(eid):
        if all(k.lower() in p.lower() for k in kws):
            return p
    return None

def ENP(eid, idx):
    ep = en_paras(eid)
    return ep[idx] if idx < len(ep) else ''


E1005_REMAP = {0:0,1:1,2:2,3:3,4:4,5:5,6:6,7:9,8:10,9:11,10:12,11:13,12:14,13:15,14:16,15:17,16:18,17:19,18:20,19:21,20:22,21:23,22:24,23:25}
def EN5(idx):
    ep = en_paras('E1-005')
    j = E1005_REMAP.get(idx, idx)
    return ep[j] if j < len(ep) else ''

def P(cn, en=''):
    return f'<p class="b-cn">{esc(cn)}</p>\n<p class="b-en" hidden>{esc(en)}</p>'

def kicker(e):
    pr = {'P1': 'P1 必读', 'P2': 'P2 重点', 'P3': 'P3 浏览'}[e['priority']]
    pr_en = {'P1': 'P1 MUST-READ', 'P2': 'P2 KEY', 'P3': 'P3 SCAN'}[e['priority']]
    by = e.get('byline') or ''
    k_cn = f"{e.get('page','')} · {pr}" + (f' · {by}' if by else '')
    k_en = f"{e.get('page','')} · {pr_en}" + (f' · {by}' if by else '')
    return f'<div class="kicker"><span class="k-cn">{esc(k_cn)}</span><span class="k-en" hidden>{esc(k_en)}</span></div>'

def head(e):
    t = f'''<h3 data-title-zh="{esc(e.get('title_cn'))}" data-title-en="{esc(e.get('title'))}">{esc(e.get('title_cn'))}</h3>'''
    d = ''
    if e.get('dek_cn'):
        d = f'<p class="dek-cn">{esc(e["dek_cn"])}</p>\n<p class="dek-en" hidden>{esc(e.get("dek") or "")}</p>'
    return t + '\n' + d

def story_open(e):
    return f'<article class="story proto" id="p-{e["id"]}" data-priority="{e["priority"]}">\n{kicker(e)}\n{head(e)}'

def cmp_label(cn, en):
    return f'<div class="cmp-label"><span class="k-cn">{esc(cn)}</span><span class="k-en" hidden>{esc(en)}</span></div>'

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

def keyfacts(rows):
    items = []
    for k_cn, k_en, v_cn, v_en in rows:
        items.append(f'''<div class="kf-row">
<div class="kf-k"><span class="k-cn">{esc(k_cn)}</span><span class="k-en" hidden>{esc(k_en)}</span></div>
<div class="kf-v"><span class="k-cn">{esc(v_cn)}</span><span class="k-en" hidden>{esc(v_en)}</span></div>
</div>''')
    return '<div class="keyfacts">\n' + '\n'.join(items) + '\n</div>'

def timeline(nodes):
    items = []
    for t_cn, t_en, b_cn, b_en in nodes:
        items.append(f'''<div class="tl-item">
<div class="tl-time"><span class="k-cn">{esc(t_cn)}</span><span class="k-en" hidden>{esc(t_en)}</span></div>
<div class="tl-rail"><span class="tl-dot"></span></div>
<div class="tl-body"><span class="k-cn">{esc(b_cn)}</span><span class="k-en" hidden>{esc(b_en)}</span></div>
</div>''')
    return '<div class="timeline">\n' + '\n'.join(items) + '\n</div>'

def compare(cols):
    items = []
    for who_cn, who_en, whats in cols:
        ws = '\n'.join(f'<div class="what"><span class="k-cn">{esc(c)}</span><span class="k-en" hidden>{esc(en)}</span></div>' for c, en in whats)
        items.append(f'''<div class="cmp-col">
<div class="who"><span class="k-cn">{esc(who_cn)}</span><span class="k-en" hidden>{esc(who_en)}</span></div>
{ws}
</div>''')
    return '<div class="compare">\n' + '\n'.join(items) + '\n</div>'

def xref(cn, en=''):
    return f'<div class="xref"><span class="k-cn">{esc(cn)}</span><span class="k-en" hidden>{esc(en)}</span></div>'

def qa_pair(q_cn, q_en, a_cn, a_en):
    return f'''<div class="qa">
<div class="qa-q"><div class="qa-tag"><span class="k-cn">问</span><span class="k-en" hidden>Q</span></div>
<div class="qa-qtext"><span class="k-cn">{esc(q_cn)}</span><span class="k-en" hidden>{esc(q_en)}</span></div></div>
<div class="qa-a"><p class="b-cn">{esc(a_cn)}</p><p class="b-en" hidden>{esc(a_en)}</p></div>
</div>'''

def photo_cap(cn, en=''):
    return f'<div class="photo-cap"><span class="k-cn">{esc(cn)}</span><span class="k-en" hidden>{esc(en)}</span></div>'

# ============ E1-001 What's News ============
def build_e1001():
    e = E['E1-001']
    h = [story_open(e)]
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
        gh = [f'<div class="digest-lang-{suffix}"{hidden}>']
        for gname, items in groups:
            gh.append(f'''<div class="digest-group">
<div class="digest-head"><span class="t">{esc(gname)}</span><span class="n"><span class="k-cn">{len(items)} 条</span><span class="k-en" hidden>{len(items)} items</span></span></div>''')
            for page, item in items:
                gh.append(f'''<div class="digest-item"><div class="page-chip">{esc(page)}</div><div class="digest-text">{esc(item)}</div></div>''')
            gh.append('</div>')
        gh.append('</div>')
        h.append('\n'.join(gh))
    h.append('</article>')
    return '\n'.join(h)

# ============ E1-004 Trump-Russia ============
def build_e1004():
    e = E['E1-004']; cp = cn_paras('E1-004')
    h = [story_open(e)]
    h.append(P(cp[0], ENP('E1-004',0)))
    h.append(P(cp[3], ENP('E1-004',3)))
    h.append(cmp_label('时间线 · 过去三天', 'TIMELINE · LAST THREE DAYS'))
    h.append(timeline([
        ('周五', 'FRI', cn_sents(cp[14])[0], ENP('E1-004',14)),
        ('周六', 'SAT', cn_sents(cp[13])[0], ENP('E1-004',13)),
        ('周日', 'SUN', cn_sents(cp[1])[0], ENP('E1-004',1)),
        ('周日', 'SUN', cn_sents(cp[2])[1], (lambda p: next((s for s in en_sents(p) if 'joint statement' in s.lower()), p))(ENP('E1-004',2))),
    ]))
    h.append(P(cn_sents(cp[2])[0], (lambda p: en_sents(p)[0])(ENP('E1-004',2))))
    h.append(xref('请参见 A8 页"俄罗斯石油协议面临阻力"', 'See page A8, "Russia Oil Deal Faces Pushback"'))
    for i, kws in [(5,('Putin','rejected')), (6,('reiterated','refineries')), (7,('White House','senators')), (8,('Sunday','Kyiv')), (9,('Ukraine wants peace',)), (10,('2022','full-scale invasion'))]:
        h.append(P(cp[i], ENP('E1-004', i)))
    h.append(P(''.join(cn_sents(cp[11])[:2]), (lambda p: ''.join(en_sents(p)[:2]))(ENP('E1-004',11))))
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
    h.append(P(cp[12], ENP('E1-004',12)))
    h.append(cmp_label('各方表述对照', 'STATEMENTS AT A GLANCE'))
    h.append(compare([
        ('特朗普称', 'TRUMP SAYS', [
            ('乌克兰和俄罗斯之间立即达成"能源停火"协议', 'an immediate "ENERGY CEASEFIRE" between Ukraine and Russia'),
            ('俄罗斯柴油供应是解决方案的一部分，可压低油价', 'Russian diesel supply is part of the solution to lower fuel prices'),
            ('泽连斯基应对战争持续和全球油价上涨负责', 'Zelensky is responsible for the continued war and higher global fuel prices'),
        ]),
        ('各方回应', 'RESPONSES', [
            ('莫斯科迄今拒绝；无协议迹象；普京已拒绝提议', 'Moscow has refused so far; no sign of a deal; Putin rejected the proposal'),
            ('分析人士：影响可能微乎其微，"中东地区更为重要"', 'Analysts: impact likely minimal; "the Middle East matters more"'),
            ('泽连斯基：若莫斯科停炸能源网络，愿停袭俄炼油厂', 'Zelensky: will halt refinery strikes if Moscow stops bombing energy networks'),
        ]),
    ]))
    for i, kws in [(15,('revenue','Kremlin')), (16,('Emmer',)), (17,('deal with the devil',)), (18,('Kluge','concessions')), (19,('Middle East matters more',)), (20,('Europe','Kyiv')), (21,('drones','domestic production')), (22,('refineries','powerful')), (23,('196',))]:
        h.append(P(cp[i], ENP('E1-004', i)))
    h.append(cmp_label('关键数字', 'KEY FIGURES'))
    h.append(stat_row([
        ('过去一周 · 电力系统', 'PAST WEEK · POWER GRID', '196次', '196', '俄罗斯对乌克兰电力系统的袭击', 'Russian strikes on Ukraine\u2019s power grid'),
        ('过去一周 · 油气设施', 'PAST WEEK · OIL & GAS', '20次', '20', '对乌克兰石油和天然气基础设施的袭击', 'strikes on oil and gas infrastructure'),
    ]))
    h.append('</article>')
    return '\n'.join(h)

# ============ E1-005 Saudi-Houthi ============
def build_e1005():
    e = E['E1-005']; cp = cn_paras('E1-005')
    h = [story_open(e)]
    h.append(P(cp[0], EN5(0)))
    h.append(P(cp[1], EN5(1)))
    h.append(cmp_label('关键数字', 'KEY FIGURES'))
    h.append(stat_row([
        ('利雅得机场袭击 · 死亡', 'AIRPORT STRIKE · KILLED', '至少12人', 'at least 12', '另有数百人受伤，许多人伤势严重', 'hundreds more injured, many severely'),
        ('利雅得距胡塞控制区', 'RIYADH TO HOUTHI AREA', '约500英里', 'about 500 miles', '首都部分地区已成战场', 'parts of the capital a battle zone'),
        ('沙特年度预算', 'ANNUAL BUDGET', '约3500亿美元', 'about $350 billion', '未来项目总成本高达数万亿美元', 'giga-project costs run to trillions'),
        ('2026 年 GDP 预期', '2026 GDP FORECAST', '下降3.6%', 'shrink 3.6%', '沙特财政部最新预计', 'per the Saudi Finance Ministry'),
    ]))
    for i, kws in [(2,('missile slammed','airport')), (3,('flight attendant',)), (4,('terminals','collapsed'))]:
        h.append(P(cp[i], EN5(i)))
    h.append(cmp_label('时间线 · 冲突升级', 'TIMELINE · ESCALATION'))
    h.append(timeline([
        ('2015 年', '2015', cn_sents(cp[21])[0], (lambda p: next((s for s in en_sents(p) if '2015' in s), '') if p else '')(find_en('E1-005','2015','Yemen'))),
        ('2022 年', '2022', cn_sents(cp[21])[2], (lambda p: next((s for s in en_sents(p) if '2022' in s), '') if p else '')(find_en('E1-005','2015','Yemen'))),
        ('7 月', 'JUL', cn_sents(cp[20])[1], (lambda p: next((s for s in en_sents(p) if 'July' in s or 'blockade' in s.lower()), '') if p else '')(find_en('E1-005','blockade'))),
        ('9 月', 'SEP', cn_sents(cp[20])[2], (lambda p: next((s for s in en_sents(p) if 'September' in s or 'pipeline' in s.lower()), '') if p else '')(find_en('E1-005','pipeline','September'))),
        ('周四', 'THU', cn_sents(cp[11])[1], (lambda p: next((s for s in en_sents(p) if 'Thursday' in s or 'kindergarten' in s.lower()), '') if p else '')(find_en('E1-005','kindergarten'))),
        ('周六', 'SAT', ' '.join(cn_sents(cp[2])[:2]), (lambda p: ' '.join(en_sents(p)[:2]) if p else '')(find_en('E1-005','missile slammed'))),
        ('周日', 'SUN', cn_sents(cp[10])[0], (lambda p: en_sents(p)[0] if p else '')(find_en('E1-005','spokesman','airports'))),
    ]))
    for i, kws in [(5,('under control',)), (6,('tourism',)), (7,('deficit',)), (8,('tech industry',)), (9,('weekend','Houthis')), (10,('spokesman','airports')), (11,('500 miles',)), (12,('41-year-old',)), (13,('Ulrichsen',)), (14,('declined to comment',))]:
        h.append(P(cp[i], EN5(i)))
    h.append(cmp_label('要点', 'KEY FACTS'))
    h.append(keyfacts([
        ('袭击伤亡', 'CASUALTIES', '至少12人死亡，数百人受伤', 'at least 12 killed, hundreds injured'),
        ('打击距离', 'STRIKE RANGE', '利雅得距胡塞控制区约500英里', 'Riyadh about 500 miles from Houthi-held areas'),
        ('年度预算', 'ANNUAL BUDGET', '约3500亿美元', 'about $350 billion'),
        ('项目总成本', 'PROJECT COSTS', '高达数万亿美元', 'trillions of dollars'),
        ('2026 年 GDP', '2026 GDP', '预计下降3.6%', 'expected to shrink 3.6%'),
    ]))
    for i, kws in [(15,('Neom',)), (16,('unattainable',)), (17,('foreign investment',)), (18,('stalled',)), (19,('3.6%',)), (20,('Red Sea','pipeline')), (21,('2015','Yemen')), (22,('air defenses',)), (23,('Pakistan',))]:
        h.append(P(cp[i], EN5(i)))
    h.append('</article>')
    return '\n'.join(h)

# ============ E3-002 EV charging ============
def build_e3002():
    e = E['E3-002']; cp = cn_paras('E3-002')
    h = [story_open(e)]
    h.append(cmp_label('反差 · 销量与充电', 'CONTRAST · SALES VS CHARGING'))
    h.append(compare([
        ('电动汽车销量', 'EV SALES', [
            ('美国电动汽车的销量与去年相比下降了一半', 'U.S. EV sales fell by half from last year'),
            ('2025 年第三季度达峰值（约占新车 12%），此后徘徊在 6% 左右', 'peaked in Q3 2025 at ~12% of new cars, since hovering around 6%'),
        ]),
        ('充电基础设施', 'CHARGING BUILDOUT', [
            ('今年公共充电桩安装量预计与 2025 年持平，达历史最高', 'public charger installations set to match 2025, an all-time high'),
            ('美国目前拥有超过 8 万个公共快速充电桩', 'the U.S. now has 80,000+ public fast chargers'),
        ]),
    ]))
    for i, kws in [(0,('fell by half',)), (1,('all-time high',)), (2,('paper bag',)), (3,('tax credits',))]:
        h.append(P(cp[i], ENP('E3-002', i)))
    h.append(cmp_label('关键数字', 'KEY FIGURES'))
    h.append(stat_row([
        ('销量同比', 'SALES YOY', '下降一半', 'down by half', '美国电动汽车销量', 'U.S. EV sales vs last year'),
        ('市场份额', 'MARKET SHARE', '12%→6%', '12% → 6%', '2025Q3 峰值 → 目前', 'Q3 2025 peak → now'),
        ('公共快充桩', 'PUBLIC FAST CHARGERS', '8万+', '80,000+', '全美现有总量', 'nationwide total'),
        ('特斯拉年新增', "TESLA ADDED", '3500+', '3,500+', '今年新增快充桩，全美总数约 4 万', 'added this year; ~40,000 total in U.S.'),
    ]))
    for i, kws in [(4,('Paren','2,000')), (5,('Ferro',)), (6,('wait times',)), (7,('chicken-and-egg',)), (8,('12%',)), (9,('more affordable',)), (10,('capital costs',)), (11,('losses are narrowing',)), (12,('autonomous',)), (13,('not enough chargers',)), (14,('California',)), (15,('Ionna',)), (16,('leader',)), (17,('leader',)), (18,('gas prices',))]:
        if i < len(cp): h.append(P(cp[i], ENP('E3-002', i)))
    h.append(photo_cap('[图表：自2021年1月以来，美国公共电动汽车快速充电桩数量按月统计。注：数据截至2026年9月。来源：能源部。]', '[Chart: U.S. public EV fast chargers by month since Jan 2021. Data through Sep 2026. Source: DOE.]'))
    h.append(photo_cap('[照片说明：新的充电站拥有更多的充电桩和更强大的充电器，以缩短等待时间。（Angus Mordant/彭博新闻）]', ENP('E3-002',20)))
    h.append(photo_cap('[照片说明：埃隆·马斯克的特斯拉公司今年增加了超过3500个快速充电桩。]', ENP('E3-002',21)))
    h.append('</article>')
    return '\n'.join(h)

# ============ E3-003 Delta CEO interview ============
def build_e3003():
    e = E['E3-003']; cp = cn_paras('E3-003')
    h = [story_open(e)]
    h.append(cmp_label('要点', 'KEY FACTS'))
    h.append(keyfacts([
        ('燃油成本增加', 'FUEL COST HIT', '60亿美元', '$6 billion'),
        ('全年预期', 'FULL-YEAR OUTLOOK', '大幅下调', 'sharply lowered'),
        ('第四季度收入预期', 'Q4 REVENUE', '增长20%', 'up 20%'),
    ]))
    for i, kws in [(0,('$6 billion',)), (1,('most profitable',)), (2,('demand remains strong',)), (3,('conversation',))]:
        h.append(P(cp[i], ENP('E3-003', i)))
    qa_kws = [(4,5,('fuel prices',),('60%',)), (6,7,('pushback',),('sensitive',)), (8,9,('premium','ceiling'),('15 years',)), (10,11,('Starlink',),('pioneer',))]
    for qi, ai, qk, ak in qa_kws:
        h.append(qa_pair(cp[qi], ENP('E3-003', qi), cp[ai], ENP('E3-003', ai)))
    h.append(photo_cap('[照片：埃德·巴斯蒂安。（Anindito Mukherjee/彭博社）]', '[Photo: Ed Bastian. (Anindito Mukherjee/Bloomberg)]'))
    h.append('</article>')
    return '\n'.join(h)

if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else '/dev/stdout'
    parts = [build_e1001(), build_e1004(), build_e1005(), build_e3002(), build_e3003()]
    open(out, 'w').write('\n\n'.join(parts))
    print('articles bytes:', sum(len(p) for p in parts))
    for w in WARN: print('WARN:', w)
