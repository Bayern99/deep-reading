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
