#!/usr/bin/env python3
import json, os
# Archived into 2026-10-12/archive/legacy-scripts/; WORK stays the issue directory.
WORK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
g = json.load(open(f"{WORK}/glossary.json", encoding="utf-8"))
lines = []
lines.append("# Living Glossary（跨期术语库）\n")
lines.append("WSJ 深读各期共享。每次翻译后，复核发现的新实体/别名/冲突经确认后合并入库；QA 修正回流。")
lines.append("播种：2026-10-12 版（511 条）。\n")
lines.append("## 冻结裁定（跨期有效，勿改）\n")
frozen = [
    "Polymarket → Polymarket（预测市场）",
    "Shawn Fain → 肖恩·费恩",
    "Dutch Bros → Dutch Bros（美国咖啡连锁）",
    "JD Vance → J·D·万斯",
    "Pope Leo XIV → 教宗良十四世（不是“利奥十四世”）",
    "Truth Social → 真相社交",
    "Mohammed bin Salman → 穆罕默德·本·萨勒曼",
    "Pete Hegseth → 皮特·赫格塞斯",
    "Gavin Newsom → 加文·纽森",
    "nicotine pouches → 尼古丁袋（不是薄荷糖）",
    "Isaias（飓风）→ 伊萨亚斯",
    ".500 team → 胜率五成的球队",
    "Sunday Scaries → 周日恐慌",
    "fusionism → 融合主义",
    "Neom → Neom（沙特未来新城）",
]
lines += ["- " + x for x in frozen]
lines.append("\n## 未决（下期遇到时核验）\n")
pending = [
    "《Other Mommy》《Verity》电影官方中文译名待查",
    "Chloé Spo：姓氏被版面栏位截断，待查",
    "Cockroach Janta Party：按原文照录，未臆测",
    "Service Employees International Union / Solano County / county supervisor 译法待定",
]
lines += ["- " + x for x in pending]
lines.append("\n## 全表\n")
lines.append("| 英文 | 中文 |")
lines.append("|---|---|")
for en, zh in g.items():
    lines.append(f"| {en} | {zh} |")
open("/home/hatch/workspace/deep-read/glossary-db.md", "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("living glossary seeded:", len(g), "terms")
