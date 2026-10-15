"""Authored editorial layer for the 2026-10-14 vertical tracer.

Every intervention below carries a ``data_src`` binding; the composer verifies
all of its substantive numbers against the referenced paragraphs before
assembly.  Chinese renderings of printed chart labels are editorial
translations of the lossless ``Retina*`` vector strings (not OCR).
"""

# --- PILOT-A1-BANKS (Tier 1, printed charts p02-b78 / p02-b83) ---------------

BANKS = {
    "kicker": "Business & Finance · A1",
    "takeaways": [
        {
            "cn": "四大行三季度利润齐增，但上月债券市场动荡正在侵蚀增长前景。",
            "en": "All four major banks posted higher third-quarter profits, but last month's bond-market turbulence is clouding the outlook.",
            "data_src": "p2 p3",
        },
        {
            "cn": "摩根大通季度利润达153.1亿美元，合每股5.57美元。",
            "en": "JPMorgan reported a quarterly profit of $15.31 billion, or $5.57 a share.",
            "data_src": "p4",
        },
        {
            "cn": "富国银行利润增长6%至59.5亿美元；花旗集团利润大增40%至52.5亿美元。",
            "en": "Wells Fargo's profit rose 6% to $5.95 billion; Citigroup's jumped 40% to $5.25 billion.",
            "data_src": "p13 p23",
        },
        {
            "cn": "KBW纳斯达克银行指数当日下跌1.4%，自6月以来累计下跌6.8%。",
            "en": "The KBW Nasdaq Bank Index fell 1.4% on the day and is down 6.8% since June.",
            "data_src": "p8",
        },
    ],
    "highlights": {
        "p8": {"cn": "6.8%", "en": "6.8%"},
        "p15": {"cn": "72%", "en": "72%"},
        "p23": {"cn": "40%", "en": "40%"},
    },
    # Chinese renderings of the printed series labels, in extracted print order.
    "chart_series_cn": {
        "p02-b78": ["富国银行", "花旗集团", "高盛", "摩根大通"],
        "p02-b83": ["摩根大通", "富国银行", "高盛", "花旗集团"],
    },
    "chart_title_cn": {
        "p02-b78": "固定收益、外汇及大宗商品收入（按银行）",
        "p02-b83": "第三季度净利润",
    },
    "companions": [
        {
            "chart_id": "p02-b78",
            "anchor": None,  # computed from print order at build time
            "takeaway_cn": "固定收益、外汇与大宗商品业务成为本轮增长引擎：高盛该项收入同比跳升72%，为花旗与富国同项收入增幅的两倍以上。",
            "takeaway_en": "FICC revenue powered the quarter: Goldman's jumped 72% year over year, more than double Citigroup's and Wells Fargo's gains.",
            "data_src": "p14 p15",
        },
        {
            "chart_id": "p02-b83",
            "anchor": None,
            "takeaway_cn": "净利润对比：摩根大通153.1亿美元；富国银行59.5亿美元（同比增6%）；花旗集团52.5亿美元（同比增40%）。",
            "takeaway_en": "Net profit: JPMorgan $15.31 billion; Wells Fargo $5.95 billion (up 6%); Citigroup $5.25 billion (up 40%).",
            "data_src": "p4 p13 p23",
        },
    ],
}

# --- PILOT-A1-CONDO (Tier 1, <wsj-chart> mechanism story) ---------------------

CONDO = {
    "kicker": "U.S. News · A1",
    "takeaways": [
        {
            "cn": "公寓买家以“创始债券”为Cain的100亿美元One Beverly Hills项目提供贷款。",
            "en": "Condo buyers are lending to Cain's $10 billion One Beverly Hills project through \"Founder Bonds.\"",
            "data_src": "p2",
        },
        {
            "cn": "买家可获得5%的回报，但债券受偿顺序次于28亿美元优先贷款与15亿美元夹层贷款。",
            "en": "Buyers receive a 5% return, but the bonds are junior to a $2.8 billion senior loan and a $1.5 billion mezzanine loan.",
            "data_src": "p5 p9",
        },
        {
            "cn": "Cain已通过这一方式募集约3.5亿美元，目标超过16亿美元。",
            "en": "Cain has raised about $350 million this way and aims to top $1.6 billion.",
            "data_src": "p14",
        },
    ],
    "subheadings": {
        "p9": {"cn": "买家借贷的风险结构", "en": "The Risk Borne by Buyers", "data_src": "p9"},
        "p16": {"cn": "史无前例的定价", "en": "Unprecedented Pricing", "data_src": "p16 p17"},
        "p20": {"cn": "洛杉矶豪宅市场的逆风", "en": "Headwinds in Los Angeles", "data_src": "p20 p23"},
    },
    "highlights": {
        "p5": {"cn": "5%", "en": "5%"},
        "p7": {"cn": "5.3%", "en": "5.3%"},
        "p17": {"cn": "2亿美元", "en": "$200 million"},
    },
    "wsj_charts": [
        {
            "id": "condo-flow",
            "type": "flow",
            "title_cn": "买家借贷机制",
            "title_en": "How Buyer Lending Works",
            "data_src": "p2 p5 p6 p9",
            "nodes": [
                {"id": "buyers", "label_cn": "公寓买家（约150套）", "label_en": "Condo buyers (~150 units)", "kind": "actor", "row": 0, "w": 250},
                {"id": "bonds", "label_cn": "创始债券 · 5%回报", "label_en": "Founder Bonds · 5% return", "kind": "instrument", "row": 0, "w": 250},
                {"id": "cain", "label_cn": "Cain（伦敦投资公司）", "label_en": "Cain (London investment firm)", "kind": "actor", "row": 1, "w": 250},
                {"id": "project", "label_cn": "One Beverly Hills · 100亿美元项目", "label_en": "One Beverly Hills · $10 billion project", "kind": "project", "row": 2, "w": 320},
            ],
            "edges": [["buyers", "bonds"], ["bonds", "cain"], ["cain", "project"]],
            "edge_labels": {"buyers>bonds": "购买债券 lend", "bonds>cain": "募集资金 pool", "cain>project": "投入建设 deploy"},
            "caption_cn": "买家购买“创始债券”向Cain提供贷款，资金进入100亿美元的项目开发；债券偿付顺序次于优先与夹层贷款。",
            "caption_en": "Buyers purchase Founder Bonds to lend to Cain, funding the $10 billion development; the bonds are junior to senior and mezzanine debt.",
        },
        {
            "id": "condo-progress",
            "type": "comparison",
            "title_cn": "创始债券募资进度",
            "title_en": "Founder Bond Fundraising",
            "data_src": "p14",
            "items": [
                {"label_cn": "已募集", "label_en": "Raised so far", "value": 350000000,
                 "display_cn": "约3.5亿美元", "display_en": "~$350 million", "emphasis": False},
                {"label_cn": "目标规模", "label_en": "Target", "value": 1600000000,
                 "display_cn": "超16亿美元", "display_en": "over $1.6 billion", "emphasis": True},
            ],
            "caption_cn": "Cain已通过创始债券募集约3.5亿美元，并计划将规模提升至16亿美元以上。",
            "caption_en": "Cain has raised about $350 million through Founder Bonds and aims to push the total above $1.6 billion.",
        },
        {
            "id": "condo-timeline",
            "type": "timeline",
            "title_cn": "项目与融资时间线",
            "title_en": "Project and Financing Timeline",
            "data_src": "p3 p7 p19",
            "items": [
                {"stamp_cn": "去年初", "stamp_en": "Early last year", "text_cn": "创始债券计划推出，当时10年期国债收益率不足5%", "text_en": "Founder Bond program launched when 10-year Treasuries yielded less than 5%"},
                {"stamp_cn": "今夏", "stamp_en": "Over the summer", "text_cn": "通过2亿美元公寓销售募集7000万美元创始债券", "text_en": "$70 million in Founder Bonds raised across $200 million in condo sales"},
                {"stamp_cn": "近几周", "stamp_en": "Recent weeks", "text_cn": "10年期国债收益率升破5%，本月一度超过5.3%", "text_en": "The 10-year yield exceeded 5%, rising above 5.3% at one point this month"},
                {"stamp_cn": "2029年", "stamp_en": "2029", "text_cn": "One Beverly Hills预计竣工", "text_en": "One Beverly Hills is set to be completed"},
            ],
            "caption_cn": "债券推出时10年期国债收益率不足5%，如今已超过5.3%，创始债券的吸引力随之下降。",
            "caption_en": "Treasuries yielded under 5% at launch and now top 5.3%, eroding the Founder Bonds' appeal.",
        },
        {
            "id": "condo-matrix",
            "type": "matrix",
            "title_cn": "创始债券 vs 10年期国债",
            "title_en": "Founder Bonds vs 10-Year Treasuries",
            "data_src": "p5 p7 p9",
            "cols": [
                {"label_cn": "创始债券", "label_en": "Founder Bonds"},
                {"label_cn": "10年期国债", "label_en": "10-year Treasury"},
            ],
            "rows": [
                {"label_cn": "收益率", "label_en": "Return", "cells": [
                    {"cn": "5%", "en": "5%", "emphasis": True},
                    {"cn": "一度升破5.3%", "en": "Rose above 5.3%", "emphasis": False},
                ]},
                {"label_cn": "风险", "label_en": "Risk", "cells": [
                    {"cn": "项目次级债务", "en": "Junior project debt", "emphasis": False},
                    {"cn": "被视为“无风险”", "en": "Considered risk-free", "emphasis": False},
                ]},
                {"label_cn": "受偿顺序", "label_en": "Priority", "cells": [
                    {"cn": "次于28亿美元优先贷款", "en": "Behind the $2.8 billion senior loan", "emphasis": False},
                    {"cn": "主权债务优先受偿", "en": "Sovereign senior claims", "emphasis": False},
                ]},
            ],
            "caption_cn": "创始人债券收益率5%，在偿付上次于28亿美元优先贷款与15亿美元夹层贷款；10年期国债一度升破5.3%。",
            "caption_en": "Founder Bonds pay 5% and rank behind a $2.8 billion senior loan and $1.5 billion mezzanine loan; 10-year Treasuries rose above 5.3%.",
        },
    ],
}

# --- PILOT-A1-NAVY (Tier 1, photo documentary feature) ------------------------

NAVY = {
    "kicker": "U.S. News · A1",
    "figure_caption_cn": "刊载于印刷版的图示与照片",
    "figure_caption_en": "Graphics and photographs from the printed edition",
}

# --- PILOT-A15-EDGEWORTH (Tier 2, review) -------------------------------------

EDGEWORTH = {
    "kicker": "Bookshelf · A15",
    "book_details": {
        "title_cn": "《玛丽亚·埃奇沃思的看不见的手》",
        "title_en": "The Invisible Hand of Maria Edgeworth",
        "author": "Jeanna Smialek（珍娜·斯米亚莱克） 著",
        "imprint": "Knopf，304页，$32",
    },
    "figure_caption_cn": "《玛丽亚·埃奇沃思的看不见的手》书封",
    "figure_caption_en": "Cover of 'The Invisible Hand of Maria Edgeworth'",
    "subheadings": {
        "p6": {"cn": "父亲、庄园与经济学启蒙", "en": "The Father, the Estate and an Education in Economics", "data_src": "p6"},
        "p8": {"cn": "小说里的济贫之争", "en": "The Poverty Debate in Her Fiction", "data_src": "p8"},
        "p13": {"cn": "愿意修正自我的胸怀", "en": "A Receptiveness to Self-Correction", "data_src": "p13"},
    },
    "highlights": {
        "p3": {"cn": "1847", "en": "1847"},
        "p5": {"cn": "170万美元", "en": "$1.7 million"},
        "p10": {"cn": "紧急情势需要例外", "en": "exigencies require exceptions"},
    },
}

# --- PILOT-A16-WEALTH (Tier 2, editorial) --------------------------------------

WEALTH = {
    "kicker": "Review & Outlook · A16",
    "thesis": {
        "cn": "加州是进步派政策的最大试验场，如今又成为下一场社会主义运动——财富税——的政治试验地；第40号提案将对净资产超过10亿美元的居民征收5%的税。",
        "en": "California is the nation's biggest laboratory for progressive policies and now the testing ground for the next socialist crusade — a wealth tax; Prop. 40 would levy a 5% tax on residents with more than $1 billion in net worth.",
        "data_src": "p1",
    },
    "subheadings": {
        "p5": {"cn": "覆盖全球资产的征税网", "en": "A Tax Net Over Worldwide Assets", "data_src": "p5"},
        "p7": {"cn": "居住认定的陷阱", "en": "The Residency Trap", "data_src": "p7"},
        "p11": {"cn": "从“一次性”到常态化", "en": "From \"One-Time\" to Permanent", "data_src": "p11"},
        "p14": {"cn": "欧洲的前车之鉴", "en": "Europe's Repealed Experiments", "data_src": "p14"},
    },
    "pull_quote": {"paragraph": "p2", "sentence": 1},
    "highlights": {
        "p1": {"cn": "财富税", "en": "wealth tax"},
        "p3": {"cn": "7770亿美元", "en": "$777 billion"},
        "p9": {"cn": "7.5%", "en": "7.5%"},
        "p10": {"cn": "14%", "en": "14%"},
    },
}

# --- Tier 1 additions for the full 2026-10-14 issue (Ticket 2, Issue #3) ------

GREECE = {
    # Documentary sub-mode: one original photo woven at its after-pK position.
    "takeaways": [
        {
            "cn": "金伯莉·吉尔福伊尔辞去美国驻希腊大使一职，此前白宫要求其辞职。",
            "en": "Kimberly Guilfoyle resigned as U.S. ambassador to Greece after the White House asked her to step down.",
            "data_src": "p1",
        },
        {
            "cn": "此前《华尔街日报》报道称，吉尔福伊尔曾于确认任命听证会前夕向一位特朗普的捐赠者索要10万美元。",
            "en": "The Journal reported that Guilfoyle had sought $100,000 from a Trump donor in the run-up to her confirmation hearing last year.",
            "data_src": "p1 p7",
        },
        {
            "cn": "特朗普表示，他不喜欢读到的有关吉尔福伊尔的内容，也尚未与她交谈。",
            "en": "Trump said he didn't like what he had read about Guilfoyle and hadn't spoken with her.",
            "data_src": "p5",
        },
    ],
    "highlights": {
        "p1": {"cn": "10万美元", "en": "$100,000"},
        "p7": {"cn": "10万美元", "en": "$100,000"},
    },
}

CHINA_YOUTH = {
    # Documentary sub-mode (original photos) + four printed-chart companions.
    "takeaways": [
        {
            "cn": "27岁的马永健在计算机科学硕士学业中途停止上课；软件工程这一曾经稳妥的选择，在AI崛起与中国科技行业裁员潮下不再保险。",
            "en": "The 27-year-old stopped attending his computer-science master's program; software engineering, once a safe career, no longer is amid the AI rise and tech layoffs.",
            "data_src": "p2",
        },
        {
            "cn": "“以前大家都觉得生活会越来越好，收入也会不断增加。如今情况却不同了，”马永健说道。",
            "en": "\"Before, everyone expected life would keep getting better, your income would keep growing. Now, it's different,\" said Ma.",
            "data_src": "p5",
        },
        {
            "cn": "技术甚至开始威胁年轻人转向的零工工作，如网约车、外卖配送和直播。",
            "en": "Technology is even starting to threaten the part-time gigs young people have turned to, such as ride hailing, food delivery and livestreaming.",
            "data_src": "p34",
        },
    ],
    # Inventory subheading paragraphs rendered verbatim as section heads.
    "subheading_paragraphs": ["p14", "p20", "p30", "p39"],
    "pull_quote": {
        "paragraph": "p5",
        "sentence": 3,
        "cn": "“放眼未来，实在看不到多少希望。”",
    },
}

CARFREE = {
    # Mechanism/quantitative sub-mode: campaign-money comparison primitive.
    "takeaways": [
        {
            "cn": "旧金山选民永久封闭上大公路大部分路段、建成“日落沙丘公园”后，每天多达20,000辆车被迫改道，西区民怨沸腾。",
            "en": "After voters permanently closed most of Upper Great Highway for Sunset Dunes park, as many as 20,000 cars a day were diverted, inflaming the West Side.",
            "data_src": "p3",
        },
        {
            "cn": "G提案将于11月3日付诸表决：若获通过，该路段平日将重新对车辆开放。",
            "en": "Proposition G is on the Nov. 3 ballot; if passed, the stretch would reopen to cars on weekdays.",
            "data_src": "p5",
        },
        {
            "cn": "Yelp首席执行官为“反对G提案”阵营捐款约80万美元筹款额的一半；支持方仅筹集约13万美元。",
            "en": "Yelp's CEO bankrolled about half of the $800,000 raised for No on G; the Yes side has raised about $130,000.",
            "data_src": "p6",
        },
    ],
    "highlights": {
        "p3": {"cn": "20,000", "en": "20,000"},
        "p6": {"cn": "80万美元", "en": "$800,000"},
    },
    "wsj_charts": [
        {
            "id": "carfree-money",
            "type": "comparison",
            "title_cn": "G提案竞选资金对比",
            "title_en": "Campaign Money on Proposition G",
            "data_src": "p6",
            "items": [
                {"label_cn": "反对G提案（No on G）", "label_en": "No on G", "value": 800000,
                 "display_cn": "约80万美元", "display_en": "about $800,000", "emphasis": True},
                {"label_cn": "支持G提案（Yes on G）", "label_en": "Yes on G", "value": 130000,
                 "display_cn": "约13万美元", "display_en": "about $130,000", "emphasis": False},
            ],
            "caption_cn": "Yelp首席执行官为反对阵营提供了约80万美元筹款额的一半；支持方筹集约13万美元。",
            "caption_en": "Yelp's CEO bankrolled about half of the $800,000 raised for No on G; supporters have raised about $130,000.",
        },
    ],
}

PRIVATE_EQUITY = {
    # Mechanism/quantitative sub-mode: fundraising comparison primitive.
    "takeaways": [
        {
            "cn": "过去一年，New State Capital Partners约三分之一的员工离职，获得高额报酬的前景变得黯淡。",
            "en": "About one-third of New State Capital Partners' employees have left over the past year as prospects for big payouts dimmed.",
            "data_src": "p1",
        },
        {
            "cn": "风险最大的是管理规模不足约150亿美元、缺乏其他业务对冲困境的小型公司；阿波罗、黑石与KKR等巨头则建立了多条盈利业务线。",
            "en": "The firms most at risk manage less than around $15 billion and lack other businesses to offset trouble; giants like Apollo, Blackstone and KKR have built multiple lucrative arms.",
            "data_src": "p6",
        },
        {
            "cn": "今年截至9月30日私募股权募资2220亿美元，去年全年为3300亿美元，按此进度将创下至少2020年以来最差年份。",
            "en": "Firms have raised $222 billion this year through Sept. 30, compared with $330 billion for all of last year — on pace for the worst year since at least 2020.",
            "data_src": "p14",
        },
    ],
    "subheading_paragraphs": ["p13", "p19"],
    "highlights": {
        "p14": {"cn": "2220亿美元", "en": "$222 billion"},
    },
    "wsj_charts": [
        {
            "id": "pe-fundraising",
            "type": "comparison",
            "title_cn": "私募股权募资额",
            "title_en": "Private-Equity Fundraising",
            "data_src": "p14",
            "items": [
                {"label_cn": "今年（截至9月30日）", "label_en": "This year through Sept. 30", "value": 222000000000,
                 "display_cn": "2220亿美元", "display_en": "$222 billion", "emphasis": False},
                {"label_cn": "去年全年", "label_en": "All of last year", "value": 330000000000,
                 "display_cn": "3300亿美元", "display_en": "$330 billion", "emphasis": True},
            ],
            "caption_cn": "据PitchBook统计，今年截至9月30日私募股权募资2220亿美元，低于去年全年的3300亿美元。",
            "caption_en": "Firms have raised $222 billion this year through Sept. 30, below $330 billion for all of last year, per PitchBook.",
        },
    ],
}

FACTORIES = {
    # Documentary sub-mode: four original photos woven across the story.
    "takeaways": [
        {
            "cn": "特朗普声称能吸引数十亿美元投资让制造业重返美国，但项目落地仍面临劳动力稀缺、工资偏高与产品价格缺乏竞争力等老障碍。",
            "en": "Trump touts billions in investment to revive U.S. manufacturing, but the projects face the same old hurdles: scarce workers, high wages and uncompetitive prices.",
            "data_src": "p1 p2",
        },
        {
            "cn": "费城一项50亿美元的造船厂项目急需更多造船空间，且难以吸引业主韩国韩华海运以外的客户。",
            "en": "A $5 billion Philadelphia shipyard project needs more shipbuilding space and struggles to attract customers beyond owner Hanwha Ocean.",
            "data_src": "p3",
        },
        {
            "cn": "爱荷华州钢厂重启动用了2000多名承包商；现有250多名全职员工，竣工后预计雇佣约1700人。",
            "en": "Restarting the Iowa mill took over 2,000 contractors; it now has well over 250 full-time employees and will employ about 1,700 when completed.",
            "data_src": "p23",
        },
    ],
    "highlights": {
        "p3": {"cn": "50亿美元", "en": "$5 billion"},
        "p23": {"cn": "2000多名", "en": "over 2,000"},
    },
}

# --- Bilingual Chart Companions for all 21 printed charts (Ticket 2) ---------
# title_cn is the editorial Chinese rendering of the lossless Retina* title;
# takeaways are grounded in the chart's data-src paragraphs (verified).  Charts
# without printed series labels carry an empty series list.

CHART_COMPANIONS: dict[str, dict[str, object]] = {
    "p02-b78": {  # BANKS FICC — authored layer above (content.BANKS)
        "use_authored": "BANKS",
    },
    "p02-b83": {
        "use_authored": "BANKS",
    },
    "p10-b57": {
        "title_cn": "就业人数年度变化、城镇失业率、人均可支配收入增速与消费者信心指数",
        "data_src": "p30 p33",
        "takeaway_cn": "上海科技大学的一项研究分析了2022年至2026年间中国五大招聘平台上的7亿条招聘信息：人工智能对拥有1至3年工作经验的初级至中级从业者的招聘需求削减最为明显。",
        "takeaway_en": "A ShanghaiTech study of 700 million job postings from 2022 to 2026 found AI has cut hiring demand most for entry- to midlevel workers with one to three years of experience.",
    },
    "p10-b59": {
        "title_cn": "城镇青年失业率（16—24岁与25—29岁，不含在校生）",
        "data_src": "p12",
        "takeaway_cn": "截至8月，中国16至24岁且非在校群体的城市失业率约为19%，25至29岁群体为7.5%，均明显高于美国同年龄段水平。",
        "takeaway_en": "As of August, China's urban jobless rate among 16- to 24-year-olds, excluding students, stands at roughly 19%; for those aged 25 to 29 it is 7.5% — both well above U.S. levels.",
    },
    "p10-b63": {
        "title_cn": "城镇居民人均可支配收入同比变化",
        "data_src": "p30 p33",
        "takeaway_cn": "城镇居民人均可支配收入的增速持续放缓，与青年就业市场的困境相互映照。",
        "takeaway_en": "Growth in urban disposable income per capita keeps slowing, mirroring the youth jobs malaise.",
    },
    "p10-b68": {
        "title_cn": "消费者信心指数",
        "data_src": "p33",
        "takeaway_cn": "消费者信心指数长期处于低位，年轻人对“努力就有回报”的信念正在动摇。",
        "takeaway_en": "The consumer confidence index remains depressed as young people lose faith in the promise of hard work.",
    },
    "p02-b21": {
        "title_cn": "美国成房中位价同比变化",
        "takeaway_cn": "9月份全美现有住房中位价同比上涨1.3%，达到417,500美元。",
        "takeaway_en": "The national median existing-home price rose 1.3% from a year earlier to $417,500 in September.",
    },
    "p09-b48": {
        "title_cn": "2025年人均国民总收入",
        "data_src": "p6",
        "takeaway_cn": "2025年中国人均国民总收入为14,230美元，略低于14,375美元的高收入门槛。",
        "takeaway_en": "The World Bank measured China's 2025 GNI per capita at $14,230, just below the $14,375 high-income threshold.",
    },
    "p09-b50": {
        "title_cn": "中国人均国民总收入与高收入门槛",
        "data_src": "p6 p7",
        "takeaway_cn": "2026年高收入门槛可能升至14,554美元，中国人均国民总收入需增长2.3%才能跨越。",
        "takeaway_en": "The high-income threshold is likely to rise to $14,554 for 2026; China's GNI per capita would need to grow 2.3% to cross it.",
    },
    "p11-b45": {
        "title_cn": "美国国债收益率：年初至今",
        "data_src": "p2",
        "takeaway_cn": "利率高位波动之下，买入高收益率债券仍需防范收益率进一步上行的风险。",
        "takeaway_en": "With yields volatile at elevated levels, buying high-yield bonds still carries the risk of further rises.",
    },
    "p19-b17": {
        "title_cn": "美国私募股权募资活动",
        "data_src": "p14",
        "takeaway_cn": "今年截至9月30日私募股权募资2220亿美元，去年全年为3300亿美元，按此进度将创下至少2020年以来最差年份。",
        "takeaway_en": "Firms raised $222 billion through Sept. 30 versus $330 billion for all of last year, on pace for the worst year since at least 2020.",
    },
    "p19-b82": {
        "title_cn": "数据中心总装机容量",
        "data_src": "p2 p19",
        "takeaway_cn": "AI电力需求激增推动装机容量预测屡创新高；一些州已要求大型用电客户按每兆瓦5万美元缴纳保证金，以筛除“幽灵”项目。",
        "takeaway_en": "AI demand keeps lifting capacity projections, while some states now require a $50,000-a-megawatt deposit to weed out phantom projects.",
    },
    "p20-b45": {
        "title_cn": "联合健康季度营收及同比变化",
        "data_src": "p6",
        "takeaway_cn": "第三季度公司营收为1126.9亿美元，略低于去年同期的1131.6亿美元。",
        "takeaway_en": "Revenue for the third quarter was $112.69 billion, compared with $113.16 billion a year earlier.",
    },
    "p20-b72": {
        "title_cn": "强生季度营收",
        "takeaway_cn": "强生7月宣布投入55亿美元解决相关诉讼，收购与合伙交易也在本季度带来额外支出。",
        "takeaway_en": "J&J said in July it would commit $5.5 billion to resolve lawsuits; acquisitions and partnerships also added charges.",
    },
    "p21-b9": {
        "title_cn": "Stellantis第三季度分区域交付量同比变化",
        "takeaway_cn": "零跑品牌车辆为欧洲增长作出贡献：出货量增加3.4万辆，达到约4.4万辆。",
        "takeaway_en": "Leapmotor vehicles added 34,000 units of European volume, reaching around 44,000 vehicles.",
    },
    "p21-b43": {
        "title_cn": "达美乐美国同店销售同比变化",
        "data_src": "p4",
        "takeaway_cn": "美国市场的同店销售额增速由去年同期的5.2%大幅放缓至0.3%。",
        "takeaway_en": "Same-store sales growth in the U.S. slowed to 0.3% from 5.2% a year earlier.",
    },
    "p22-b22": {
        "title_cn": "艾伯森同店销售同比变化",
        "takeaway_cn": "艾伯森旗下拥有Safeway、Jewel-Osco及ACME等品牌，共计约2200家门店。",
        "takeaway_en": "Albertsons owns banners including Safeway, Jewel-Osco and ACME, about 2,200 stores in all.",
    },
    "p24-b6": {
        "title_cn": "2019至2025年房屋翻售数量变化",
        "takeaway_cn": "巴尔的摩空置街区的新式30年期贷款吸引投机者涌入，部分贷款随后违约。",
        "takeaway_en": "The new 30-year loan type drew speculators to Baltimore's vacant blocks, and many mortgages later defaulted.",
    },
    "p31-b8": {
        "title_cn": "美国小市值高盈利股票相对市场的超额收益",
        "data_src": "p3",
        "takeaway_cn": "小盘股、低相对价格、高盈利三因子组合自1963年7月以来年化收益达17.1%，同期美股整体为10.9%。",
        "takeaway_en": "The small-value-high-profitability combo returned 17.1% annualized since July 1963, versus 10.9% for U.S. stocks overall.",
    },
    "p31-b68": {
        "title_cn": "个股与指数近两日表现",
        "takeaway_cn": "长鑫存储总裁透露公司计划推出新型DRAM芯片，存储板块股价应声波动。",
        "takeaway_en": "CXMT's president said the company plans a new type of DRAM chip, moving memory-chip stocks.",
    },
    "p32-b26": {
        "title_cn": "全球自然灾害上半年保险损失（按年份）",
        "takeaway_cn": "若伊萨亚斯风力不足以致触发巨灾债券损失，部分保险相关证券投资者反而可能受益。",
        "takeaway_en": "If Isaias isn't large enough to trigger catastrophe-bond losses, some insurance-linked securities investors may benefit.",
    },
}

# article id -> authored editorial layer (Tier 1 full composition, Tier 2 specials)
CONTENT_BY_ID = {
    "PILOT-A1-BANKS": BANKS,
    "PILOT-A1-CONDO": CONDO,
    "PILOT-A1-NAVY": NAVY,
    "PILOT-A15-EDGEWORTH": EDGEWORTH,
    "PILOT-A16-WEALTH": WEALTH,
    "PILOT-A1-GREECE": GREECE,
    "PILOT-A1-CHINA-YOUTH": CHINA_YOUTH,
    "PILOT-A1-CARFREE": CARFREE,
    "CASE-B1B2-PRIVATE-EQUITY": PRIVATE_EQUITY,
    "PILOT-B1-FACTORIES": FACTORIES,
}
