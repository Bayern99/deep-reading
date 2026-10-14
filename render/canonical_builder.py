#!/usr/bin/env python3
"""WSJ 深读 · Phase 5 Canonical Content Builder (`canonical_builder.py`).

Bridges the existing WSJ extraction/translation/QA pipeline (`final.json` +
`render/source_model.py` + `render/alignment_overrides.json` + `render/asset_registry.json` +
`render/integrity_gate.py`) into the unified `CanonicalSource` structure (`canonical-v1`)
used by the Source-referenced Generative Editorial Publishing compiler.

Key invariants:
- Reuses `source_from_final(entry)` and `content_digest(entry)` so `drop_en` and `join_en`
  alignment repairs from `alignment_overrides.json` are applied identically.
- Preserves bilingual identity per block (`p1`..`pN`) with aligned sentence sub-units (`pK.sM`)
  when CN and EN sentence counts match or can be deterministically paired, without assuming
  naive 1:1 sentence counts when translation merges/splits sentences.
- Automatically extracts traceable quotes (`q1`..) and numeric metrics (`m1`..) from the
  canonical paragraphs, while supporting curated overrides.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
from typing import Any

from integrity_gate import check_article
from source_model import content_digest, source_from_final
from claim_provenance import validate_claim_provenance

BASE = os.path.dirname(os.path.abspath(__file__))

# Curated editorial candidates; factual support is checked by Claim Provenance Gate.
CURATED_DERIVATIONS: dict[str, dict[str, Any]] = {
    "E2-001": {
        "kicker_cn": "头版深度调查 · 华尔街与退休金",
        "kicker_en": "WSJ INVESTIGATION · A1 FRONT PAGE",
        "context_en": (
            "Indexed annuities lock up consumer capital for approximately 12 years with promises of "
            "equity-linked returns and zero downside risk. However, insurers hold unilateral discretion "
            "to lower participation rates, caps, and spreads. Lucrative 5%–7% agent commissions drive "
            "sales outside SEC fiduciary oversight, channeling sticky consumer float directly into "
            "illiquid private debt (CLOs, asset-backed securities)."
        ),
        "sentence_overrides": {
            "p4": [
                {
                    "id": "p4.s1",
                    "text_cn": "“这是指数型年金的一个缺点，”埃利奥特的女婿、位于佛罗里达州奥兰多市的理财顾问小卡洛斯·迪亚斯说道，",
                    "text_en": "\"That's one of the downfalls of the indexed annuities,\" said Carlos Dias Jr., Elliott's son-in-law and a financial adviser outside Orlando, Fla.",
                },
                {
                    "id": "p4.s2",
                    "text_cn": "“保险公司可以每年或每两年更改从特定指数中获得的收益金额。”",
                    "text_en": "\"Insurance companies can change the amount that's received from the particular index every year, every two years.\"",
                },
            ],
            "p20": [
                {
                    "id": "p20.s1",
                    "text_cn": "Valmark金融集团首席执行官拉里·里布卡表示，该公司销售人寿保险、年金和投资产品。他说，如果投资表现不佳，保险公司可以通过降低保单持有者收益上限来减少损失；如果投资表现良好，它们也可以通过同样的方式增加利润。",
                    "text_en": "If their investments do poorly, the insurer can cushion against loss by lowering the caps on policyholder gains, and if their investments do well they can fatten their profits the same way, said Larry Rybka, chief executive of Valmark Financial Group, which sells life insurance, annuities and investment products.",
                },
                {
                    "id": "p20.s2",
                    "text_cn": "“这就是私募股权公司喜欢这种方式的原因，因为它们可以改变与消费者的协议。”",
                    "text_en": "“That's why private equity likes this, because they can change the deal on the consumer,” Rybka said.",
                },
            ],
        },
        "derived_quotes": [
            {
                "id": "q1",
                "source_block": "p4",
                "quote_cn": "“这是指数型年金的一个缺点。保险公司可以每年或每两年更改从特定指数中获得的收益金额。”",
                "quote_en": "“That's one of the downfalls of the indexed annuities. Insurance companies can change the amount that's received from the particular index every year, every two years.”",
                "speaker_cn": "小卡洛斯·迪亚斯 (Carlos Dias Jr.)",
                "role_cn": "佛罗里达州奥兰多市理财顾问、埃利奥特的女婿",
                "speaker_en": "Carlos Dias Jr.",
                "role_en": "Financial adviser outside Orlando, Fla. & Sabrina Elliott's son-in-law",
            },
            {
                "id": "q2",
                "source_block": "p13",
                "quote_cn": "“表现出色，收益远高于类似的安全收益替代品，保证100%的本金保护，并提供可选的额外死亡赔偿和保证终身收入。”",
                "quote_en": "“performed exceptionally well, earning returns well in excess of similar safe yield alternatives, guaranteeing 100% principal protection, and providing optional enhanced death benefits and guaranteed lifetime income.”",
                "speaker_cn": "Athene (阿波罗全球管理旗下保险公司)",
                "role_cn": "公司官方声明",
                "speaker_en": "Athene (Apollo Global Management)",
                "role_en": "Company official statement",
            },
            {
                "id": "q3",
                "source_block": "p14",
                "quote_cn": "“使用一种将历史低利率与强劲的牛市相结合的情景来衡量固定指数型年金的表现，具有高度误导性。”",
                "quote_en": "“it is highly misleading to measure the performance of fixed indexed annuities using a scenario that pairs historically low rates with a strong bull equity market.”",
                "speaker_cn": "Athene (阿波罗全球管理旗下保险公司)",
                "role_cn": "关于评估情景的回应声明",
                "speaker_en": "Athene (Apollo Global Management)",
                "role_en": "Statement on benchmark scenario",
            },
            {
                "id": "q4",
                "source_block": "p20",
                "quote_cn": "“这就是私募股权公司喜欢这种方式的原因，因为它们可以改变与消费者的协议。”",
                "quote_en": "“That's why private equity likes this, because they can change the deal on the consumer.”",
                "speaker_cn": "拉里·里布卡 (Larry Rybka)",
                "role_cn": "Valmark金融集团首席执行官",
                "speaker_en": "Larry Rybka",
                "role_en": "Chief Executive, Valmark Financial Group",
            },
        ],
        "derived_metrics": [
            {
                "id": "m1",
                "source_block": "p1",
                "value": "$40,000",
                "value_cn": "4万美元",
                "label_cn": "埃利奥特初始投资本金",
                "label_en": "Sabrina Elliott's initial principal",
                "note_cn": "继承遗产后投入英杰华指数型年金",
                "note_en": "Inherited savings invested in Aviva indexed annuity",
            },
            {
                "id": "m2",
                "source_block": "p2",
                "value": "12 yrs",
                "value_cn": "12年",
                "label_cn": "保单资金锁定期限",
                "label_en": "Policy lockup period",
                "note_cn": "至2023年底保单到期",
                "note_en": "Ended in late 2023",
            },
            {
                "id": "m3",
                "source_block": "p3,p12",
                "value": "3.7%",
                "value_cn": "3.7%",
                "label_cn": "埃利奥特12年实际年化收益率",
                "label_en": "Elliott's actual annualized return",
                "note_cn": "经历两次收益比例下调及附加险扣除约2个百分点后",
                "note_en": "After two participation cuts and ~2pp rider cost",
            },
            {
                "id": "m4",
                "source_block": "p12",
                "value": "13%",
                "value_cn": "13%",
                "label_cn": "同期标普500指数年化收益率",
                "label_en": "S&P 500 annualized return over same period",
                "note_cn": "同期的美股强劲牛市基准",
                "note_en": "Concurrent strong bull equity market benchmark",
            },
            {
                "id": "m5",
                "source_block": "p12",
                "value": "1.9%",
                "value_cn": "1.9%",
                "label_cn": "同期美国国债年化收益率",
                "label_en": "Treasurys annualized return over same period",
                "note_cn": "无风险国债替代收益基准",
                "note_en": "Safe government bond alternative",
            },
            {
                "id": "m6",
                "source_block": "p10",
                "value": "60% → 55% → 45%",
                "value_cn": "60% → 55% → 45%",
                "label_cn": "与标普500挂钩的资金比例下调轨迹",
                "label_en": "Share of money tied to S&P 500 (Yr 1 → Yr 7 → Yr 11)",
                "note_cn": "扣除2.9个百分点差额；其余资金按1%固定利率增长",
                "note_en": "Minus 2.9pp spread; remainder grew at 1% fixed rate",
            },
            {
                "id": "m7",
                "source_block": "p16",
                "value": "5% – 7%",
                "value_cn": "5%至7%",
                "label_cn": "美国公平人寿10年期指数型年金代理佣金",
                "label_en": "American Equity 10-yr indexed annuity agent commission",
                "note_cn": "对比博枫旗下简单固定利率年金佣金约为3%",
                "note_en": "Compared with ~3% for simpler fixed-rate annuities (Brookfield)",
            },
            {
                "id": "m8",
                "source_block": "p18",
                "value": "$100K → $2.7M",
                "value_cn": "10万美元 → 270万美元",
                "label_cn": "特拉华人寿“动量增长”年金宣传册21年假设增长",
                "label_en": "Delaware Life 'Momentum Growth' 21-yr hypothetical pitch",
                "note_cn": "挂钩去年才成立的股票与加密货币指数，基于过去15年含11年双位数牛市的假设回测",
                "note_en": "Tied to year-old stock-and-crypto index using 15-yr hypothetical backtest",
            },
        ],
    },
    "E1-010": {
        "kicker_cn": "宏观经济展望 · 美债与利率结构",
        "kicker_en": "THE OUTLOOK · U.S. TREASURY YIELDS",
        "derived_quotes": [
            {
                "id": "q1",
                "source_block": "p9",
                "quote_cn": "“债券市场正在适应一个更高的中性利率世界，财政赤字和更强劲的生产率增长共同推高了长期借贷成本。”",
                "quote_en": "“The bond market is adjusting to a world of higher neutral rates, where fiscal deficits and firmer productivity growth keep long-term borrowing costs elevated.”",
                "speaker_cn": "华尔街日报经济学家调查共识",
                "role_cn": "2026年10月季度预测",
                "speaker_en": "WSJ Economists Survey Consensus",
                "role_en": "October 2026 Quarterly Forecast",
            }
        ],
        "derived_metrics": [
            {
                "id": "m1",
                "source_block": "p4",
                "value": "4.12% vs 3.94%",
                "value_cn": "4.12% (7月预测 3.94%)",
                "label_cn": "2026年底10年期美债收益率预期",
                "label_en": "10-Yr Treasury Yield Forecast (End of 2026: Oct vs July)",
                "note_cn": "10月调查较7月上调 18 个基点",
                "note_en": "Revised up 18 bps in October survey vs. July",
            },
            {
                "id": "m2",
                "source_block": "p5",
                "value": "4.09% vs 3.87%",
                "value_cn": "4.09% (7月预测 3.87%)",
                "label_cn": "2027年底10年期美债收益率预期",
                "label_en": "10-Yr Treasury Yield Forecast (End of 2027: Oct vs July)",
                "note_cn": "10月调查较7月上调 22 个基点",
                "note_en": "Revised up 22 bps in October survey vs. July",
            },
            {
                "id": "m3",
                "source_block": "p5",
                "value": "4.16% vs 3.92%",
                "value_cn": "4.16% (7月预测 3.92%)",
                "label_cn": "2028年底10年期美债收益率预期",
                "label_en": "10-Yr Treasury Yield Forecast (End of 2028: Oct vs July)",
                "note_cn": "10月调查较7月上调 24 个基点",
                "note_en": "Revised up 24 bps in October survey vs. July",
            },
        ],
    },
    "E3-004": {
        "kicker_cn": "科技与信仰 · 硅谷深度观察",
        "kicker_en": "TECHNOLOGY & FAITH · SILICON VALLEY ESSAY",
        "derived_quotes": [
            {
                "id": "q1",
                "source_block": "p12",
                "quote_cn": "“在历史上的每一次重大技术变革中，人类都会面临同样的诱惑：把我们自己造出的工具当成神。”",
                "quote_en": "“In every major technological shift in history, humanity faces the same temptation: mistaking the tools of our own making for God.”",
                "speaker_cn": "宗教与科技伦理学者观察",
                "role_cn": "关于巴别塔隐喻与生成式AI的讨论",
                "speaker_en": "Theological Ethics Commentary",
                "role_en": "On the Tower of Babel and Generative AI",
            }
        ],
        "derived_metrics": [],
    },
}


def split_sentences_cn(text: str) -> list[str]:
    """Split Chinese paragraph into sentences while preserving opening quotes with their sentence."""
    if not text:
        return []
    # Match sentence-ending punctuation plus optional closing quotes
    parts = re.split(r"(?<=[。！？])[”」』]?", text)
    # Re-split carefully preserving exact characters
    tokens: list[str] = []
    pos = 0
    for m in re.finditer(r"[。！？][”」』]?", text):
        end = m.end()
        tokens.append(text[pos:end])
        pos = end
    if pos < len(text):
        tokens.append(text[pos:])

    # Clean up any trailing opening quote attached to previous sentence
    fixed: list[str] = []
    for s in tokens:
        if not s:
            continue
        if fixed and re.search(r"[。！？][“「『]$", fixed[-1]):
            open_q = fixed[-1][-1]
            fixed[-1] = fixed[-1][:-1]
            s = open_q + s
        fixed.append(s)

    if "".join(fixed) != text:
        return [text]
    return fixed


def split_sentences_en(text: str) -> list[str]:
    """Split English paragraph into sentences while avoiding common abbreviations (U.S., Fla., Jr., Inc., Mr., Dr.)."""
    if not text:
        return []
    abbr_pattern = r"(?<!\bU\.S)(?<!\bFla)(?<!\bJr)(?<!\bSr)(?<!\bInc)(?<!\bLtd)(?<!\bMr)(?<!\bMs)(?<!\bDr)(?<!\bvs)(?<!\bSept)(?<!\bOct)(?<!\bNov)(?<!\bDec)"
    splits = re.split(abbr_pattern + r'(?<=[.!?]["”\'])\s+|' + abbr_pattern + r"(?<=[.!?])\s+(?=[A-Z“\"])", text)
    splits = [s.strip() for s in splits if s and s.strip()]
    if " ".join(splits) != re.sub(r"\s+", " ", text.strip()):
        return [text]
    return splits


def _build_aligned_sentences(pid: str, cn: str, en: str, overrides: dict[str, Any]) -> list[dict[str, str]]:
    if pid in overrides:
        sents = overrides[pid]
        if "".join(s["text_cn"] for s in sents) == cn and " ".join(s["text_en"] for s in sents) == en:
            return sents

    s_cn = split_sentences_cn(cn)
    s_en = split_sentences_en(en)
    if len(s_cn) > 1 and len(s_cn) == len(s_en):
        joined_cn = "".join(s_cn)
        joined_en = " ".join(s_en)
        if joined_cn == cn and joined_en == en:
            return [
                {"id": f"{pid}.s{idx + 1}", "text_cn": sc, "text_en": se}
                for idx, (sc, se) in enumerate(zip(s_cn, s_en))
            ]
    # Fallback when CN and EN sentence counts differ due to translation restructuring:
    # Keep a single atomic sentence unit pK.s1 so bilingual alignment is never corrupted.
    return [{"id": f"{pid}.s1", "text_cn": cn, "text_en": en}]


def _auto_extract_quotes(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract direct quotes that appear in both CN (“...”) and EN (“...” or "...") of the same paragraph."""
    quotes: list[dict[str, Any]] = []
    for b in blocks:
        cn_matches = re.findall(r"“([^”]{12,180})”", b["text_cn"])
        en_matches = re.findall(r'[“"]([^”"]{20,260})[”"]', b["text_en"])
        if cn_matches and en_matches:
            qid = f"q{len(quotes) + 1}"
            quotes.append({
                "id": qid,
                "source_block": b["id"],
                "quote_cn": f"“{cn_matches[-1]}”",
                "quote_en": f"“{en_matches[-1]}”",
                "speaker_cn": f"原文第 {b['index']} 段直接引述",
                "role_cn": f"Source Block {b['id']}",
                "speaker_en": f"Direct Quote ({b['id']})",
                "role_en": "Reported in article text",
            })
        if len(quotes) >= 5:
            break
    return quotes


def _auto_extract_metrics(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract salient financial/statistical figures from paragraphs for optional callout derivation."""
    metrics: list[dict[str, Any]] = []
    seen_vals: set[str] = set()
    for b in blocks:
        en_nums = re.findall(r"\$\d+(?:\.\d+)?\s*(?:billion|million|trillion)?|\d+(?:\.\d+)?%", b["text_en"], re.I)
        cn_nums = re.findall(r"\d+(?:\.\d+)?\s*(?:亿美元|万美元|万亿|%|个百分点)", b["text_cn"])
        if en_nums and cn_nums:
            val_en = en_nums[0].strip()
            val_cn = cn_nums[0].strip()
            if val_en.lower() in seen_vals:
                continue
            seen_vals.add(val_en.lower())
            mid = f"m{len(metrics) + 1}"
            metrics.append({
                "id": mid,
                "source_block": b["id"],
                "value": val_en,
                "value_cn": val_cn,
                "label_cn": b["text_cn"][:36] + ("…" if len(b["text_cn"]) > 36 else ""),
                "label_en": b["text_en"][:60] + ("…" if len(b["text_en"]) > 60 else ""),
                "note_cn": f"源自正文 [{b['id']}]",
                "note_en": f"From paragraph [{b['id']}]",
            })
        if len(metrics) >= 6:
            break
    return metrics


def build_canonical_source(
    entry: dict[str, Any],
    *,
    issue_date: str = "2026-10-12",
    asset_registry: list[dict[str, Any]] | None = None,
    images_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a complete, traceable `canonical-source-v1` object from a `final.json` article entry."""
    aid = entry["id"]
    sm = source_from_final(entry)
    digest = content_digest(entry)
    gate_passed, gate_issues = check_article(entry)

    curated = CURATED_DERIVATIONS.get(aid) or {}
    sent_overrides = curated.get("sentence_overrides") or {}

    blocks: list[dict[str, Any]] = []
    for idx, b in enumerate(sm.blocks):
        pid = b["id"]
        cn = b["cn"]
        en = b["en"]
        sentences = _build_aligned_sentences(pid, cn, en, sent_overrides)
        blocks.append({
            "id": pid,
            "index": idx + 1,
            "type": "subheading" if b["role"] == "source_head" else "paragraph",
            "role": b["role"],
            "text_cn": cn,
            "text_en": en,
            "sentences": sentences,
        })

    derived_quotes = curated.get("derived_quotes")
    if derived_quotes is None:
        derived_quotes = _auto_extract_quotes(blocks)

    derived_metrics = curated.get("derived_metrics")
    if derived_metrics is None:
        derived_metrics = _auto_extract_metrics(blocks)

    # Collect verified media assets from images.json or asset_registry.json
    media: list[dict[str, Any]] = []
    if images_manifest and aid in images_manifest:
        im = images_manifest[aid]
        media.append({
            "id": "img1",
            "file": im.get("file", ""),
            "caption_cn": im.get("caption_cn", ""),
            "caption_en": im.get("caption_en", ""),
            "credit": im.get("credit", ""),
        })
    elif asset_registry:
        art_assets = [a for a in asset_registry if a.get("article_id") == aid and a.get("status") == "extracted"]
        for i, a in enumerate(art_assets):
            # Only include assets whose caption does not look like OCR crosstalk
            cap_cn = a.get("caption_cn") or ""
            if cap_cn and not re.search(r"[\u4e00-\u9fff]", cap_cn):
                continue
            media.append({
                "id": f"img{i + 1}",
                "asset_id": a.get("asset_id", ""),
                "file": a.get("file", ""),
                "caption_cn": cap_cn,
                "caption_en": a.get("caption_en") or "",
                "credit": a.get("credit") or "",
            })

    context_dossier = None
    if entry.get("context_cn"):
        context_dossier = {
            "id": "ctx1",
            "source_attr": entry.get("context_attr") or "原文背景",
            "text_cn": entry["context_cn"],
            "text_en": curated.get("context_en") or entry.get("context_en") or entry["context_cn"],
        }

    section_name = entry.get("section") or "News"
    page_code = entry.get("page") or "A1"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", issue_date):
        day = datetime.date.fromisoformat(issue_date)
        date_cn = f"{day.year}年{day.month}月{day.day}日"
        date_en = f"{day.strftime('%B')} {day.day}, {day.year}"
    else:
        date_cn = date_en = issue_date

    canonical = {
        "schema_version": "canonical-source-v1",
        "article_id": aid,
        "final_id": entry.get("final_id"),
        "issue_date": issue_date,
        "content_digest": digest,
        "integrity_gate": {
            "passed": gate_passed,
            "status": "pass" if gate_passed and not gate_issues else ("warn" if gate_passed else "block"),
            "issues": gate_issues,
        },
        "metadata": {
            "page": page_code,
            "section": section_name,
            "type": entry.get("type") or "article",
            "priority": entry.get("priority") or "P2",
            "kicker_cn": curated.get("kicker_cn") or f"{section_name} · {page_code} 版",
            "kicker_en": curated.get("kicker_en") or f"WSJ · {section_name.upper()} · {page_code}",
            "title_cn": entry.get("title_cn") or "",
            "title_en": entry.get("title") or "",
            "dek_cn": entry.get("dek_cn") or "",
            "dek_en": entry.get("dek") or "",
            "byline": entry.get("byline") or "Wall Street Journal Staff",
            "date_cn": date_cn,
            "date_en": date_en,
        },
        "blocks": blocks,
        "derived_quotes": derived_quotes,
        "derived_metrics": derived_metrics,
        "context_dossier": context_dossier,
        "media": media,
        "terms": entry.get("terms") or [],
    }
    canonical['claim_provenance'] = validate_claim_provenance(canonical)
    return canonical


def load_canonical_for_issue(issue_dir: str, article_id: str | None = None) -> dict[str, Any] | list[dict[str, Any]]:
    final_path = os.path.join(issue_dir, "final.json")
    with open(final_path, encoding="utf-8") as f:
        final_entries = json.load(f)
    images_path = os.path.join(BASE, "images.json")
    images_manifest = {}
    if os.path.isfile(images_path):
        with open(images_path, encoding="utf-8") as f:
            images_manifest = json.load(f)

    reg_path = os.path.join(BASE, "asset_registry.json")
    asset_registry = []
    if os.path.isfile(reg_path):
        with open(reg_path, encoding="utf-8") as f:
            asset_registry = json.load(f)

    issue_date = os.path.basename(os.path.normpath(issue_dir))

    if article_id:
        entry = next((e for e in final_entries if e.get("id") == article_id), None)
        if entry is None:
            raise KeyError(f"Article '{article_id}' not found in {final_path}")
        return build_canonical_source(
            entry, issue_date=issue_date, asset_registry=asset_registry, images_manifest=images_manifest
        )

    return [
        build_canonical_source(
            e, issue_date=issue_date, asset_registry=asset_registry, images_manifest=images_manifest
        )
        for e in final_entries
    ]
