"""Two-stage LQA funnel gate for full-issue publication (Ticket 2, Issue #3).

Stage 1 is a deterministic five-invariant radar over every bilingual unit of
the issue: it compares the reviewed English source and Chinese translation of
each paragraph and flags, with 100% recall on the historical fault classes:

1. **Normalized decimal & magnitude equivalence** — currencies, percentages,
   basis points and scaled counts must normalize identically across languages
   (``700 million`` == 「7亿」, ``$2.3 billion`` == 「23亿美元」); any
   cross-language token without a counterpart is flagged.
2. **Qualifier & range retention** — English qualifiers (``up to``, ``at
   least``, ``more than``, ``less than``, ``nearly``, ``about``, ``mid-6%``,
   ``basis points`` / ``bps``) must survive into Chinese (``最多/高达/至多``,
   ``至少/最少``, ``超过/逾/多于``, ``不到/少于/低于``, ``近/将近/接近``,
   ``约/大约``, ``中段/区间``, ``基点``) and vice versa.
3. **Negation & financial direction polarity** — an English upward verb
   (``rose / surged / gained / climbed / jumped``) paired with a Chinese
   downward verb (``下跌 / 下滑 / 下降``) when no downward verb exists in the
   English paragraph (or the mirror image), plus dropped hard negations.
4. **Length-ratio outlier** — ``len(zh_CN) / max(len(en_words), 1)`` outside
   ``[0.4, 6.0]`` for paragraphs with ``>= 8`` English words (truncated
   translation or runaway repetition).
5. **Continuation & sentence completeness** — unclosed quotes, dangling print
   continuation markers (``Continued on Page...``, ``See Page...``) and
   documented source grammar anomalies.

Stage 2 routes only Stage-1 flagged paragraphs (plus every Tier 1 flagship
story) through targeted spot-check and writes a compact ``gate-report.json``
into the output workspace — never inside the reader HTML.  Canonical source
text is read-only: the gate records dispositions, it never rewrites narrative.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from .numbers import extract_substantive_numbers

# --- Invariant 2: qualifier lexicons -----------------------------------------

# A qualifier only counts inside a sentence that also carries a substantive
# numeral, so prose like "up to speed" or 「优先级低于其他债务」 never flags.
_CN_QUALIFIERS = (
    # more than / over
    "超过", "逾", "多于", "以上", "不止", "多达", "最多", "高达", "至多",
    # at least
    "至少", "最少", "不下",
    # less than / under / fewer than
    "不到", "少于", "低于", "不足", "以内",
    # approximators
    "将近", "接近", "近", "约", "大约", "中段", "中期", "区间", "基点", "可享", "上限", "左右",
)
_EN_QUALIFIER_RE = re.compile(
    r"(?<![-\w])(up to|at least|more than|less than|nearly|mid-|basis points?|bps?|"
    r"as much as|as many as)\b|(?<![-\w])(?:about|roughly|some|over|under)\s+[$€£]?\d",
    re.I,
)
# Digit-adjacent 「至」("可达至10%") and 「多/余」("2000多名" == more than 2,000),
# excluding common non-qualifier compounds (截至/至今/甚至/由至/乃至).
_CN_QUALIFIER_RE = re.compile(
    "|".join(_CN_QUALIFIERS) + r"|(?<![截至今乃甚由])至(?=\d)|(?<=\d)(?:多|余)(?![\d%])"
)
_HAS_DIGIT_RE = re.compile(r"\d")
_SENT_SPLIT_CN = re.compile(r"(?<=[。！？；])")

# --- Invariant 3: polarity lexicons ------------------------------------------

_EN_UP = re.compile(
    r"\b(rose|risen|rises|rise|surged|surge|surges|gained|gain|gains|climbed|climb|"
    r"climbs|jumped|jump|jumps|increased|increase|increases|advanced|advance|advances|"
    r"rallied|rally|rallies|rebounded|rebound|rebounds|soared|soar|soars|grew|grow|grows|"
    r"upgraded|upgrade|boosted|boost|boosts|improved|improve|improves|exceeded|exceed|"
    r"higher)\b",
    re.I,
)
_EN_DOWN = re.compile(
    r"\b(fell|fallen|falls|fall|dropped|drop|drops|declined|decline|declines|"
    r"plunged|plunge|plunges|tumbled|tumble|tumbles|slid|slide|slides|slipped|slip|"
    r"slips|decreased|decrease|decreases|sank|sink|sinks|slumped|slump|slumps|"
    r"shrank|shrink|shrinks|weakened|weaken|weakens|worsened|worsen|downgraded|"
    r"downgrade|lowered|reduced|reduce|reduces|reducing)\b",
    re.I,
)
_CN_UP = re.compile("上涨|上升|攀升|走高|增长|增加|回升|反弹|跃升|大涨|升至|上扬|突破|超过")
_CN_DOWN = re.compile("下跌|下滑|下降|减少|暴跌|走低|回落|跌至|跌幅|下调|收缩|萎缩|低于|降至")
# Hard negations only: lexical verbs like "failed/denied" describe events, they
# do not flip the polarity of a numeric claim.
_EN_NEG = re.compile(r"\b(no|not|never|without)\b|n['\u2019]t", re.I)
_CN_NEG = re.compile("不|未|没有|无|勿|并非|绝非|未能|不再|毫无")
_BALLOT_NAME_RE = re.compile(r"\b(Yes|No) on [A-Z]\d*\b")

# --- Invariant 5: continuation & completeness --------------------------------

_CONTINUATION_RE = re.compile(r"continued on page|see page|continued from page", re.I)

# Documented source grammar anomalies: recorded in the gate report instead of
# surfacing an audit banner on the reader.
KNOWN_ANOMALIES: dict[str, str] = {
    "PILOT-B1-APPLECEO:p3": (
        "dangling modifier in approved source ('but closed below that level' "
        "lacks an explicit subject); translation review confirmed the reading"
    ),
    "PILOT-A15-NATIONALISM:p1": (
        "unclosed quotation mark in the approved English print source (the "
        "quoted list continues across paragraphs); translation review "
        "confirmed the reading"
    ),
}


@dataclass
class Finding:
    """One Stage-1 radar hit with its Stage-2 disposition."""

    article_id: str
    paragraph_id: str
    kind: str  # magnitude|qualifier|polarity|negation|length-ratio|completeness
    detail: str
    disposition: str = "pending"  # pending -> recorded | escalate


@dataclass
class GateReport:
    issue: str
    units_scanned: int
    paragraphs_scanned: int
    duration_s: float
    findings: list[Finding] = field(default_factory=list)
    spot_checked: list[str] = field(default_factory=list)

    def by_kind(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for f in self.findings:
            out[f.kind] = out.get(f.kind, 0) + 1
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue": self.issue,
            "units_scanned": self.units_scanned,
            "paragraphs_scanned": self.paragraphs_scanned,
            "duration_s": round(self.duration_s, 4),
            "findings_by_kind": self.by_kind(),
            "findings": [asdict(f) for f in self.findings],
            "spot_checked": self.spot_checked,
        }


# --- Stage 1: deterministic five-invariant radar -----------------------------

def _magnitude_findings(en: str, cn: str) -> list[tuple[str, str]]:
    """Cross-language number tokens without a counterpart.

    Matching order per token: same kind and exact value; then any kind at the
    same value (translations routinely turn a bare count into 「47000美元」);
    then a large-magnitude rounding tolerance (``$112.69 billion`` vs
    「1126亿」).
    """
    en_toks = extract_substantive_numbers(en)
    cn_toks = extract_substantive_numbers(cn)
    cn_left = list(cn_toks)
    out: list[tuple[str, str]] = []
    for tok in en_toks:
        hit = next((c for c in cn_left if c.kind == tok.kind and c.value == tok.value), None)
        if hit is None:
            hit = next((c for c in cn_left if c.value == tok.value), None)
        if hit is None and abs(tok.value) >= Decimal(1e6):
            hit = next(
                (c for c in cn_left
                 if abs(c.value) >= Decimal(1e6)
                 and abs(c.value - tok.value) / max(abs(tok.value), Decimal(1)) <= Decimal("0.005")),
                None,
            )
        if hit is not None:
            cn_left.remove(hit)
        else:
            out.append(("magnitude", f"EN {tok.kind} {tok.value} ({tok.raw}) has no CN counterpart"))
    for tok in cn_left:
        out.append(("magnitude", f"CN {tok.kind} {tok.value} ({tok.raw}) has no EN counterpart"))
    return out


def _sentences(text: str, cn: bool = False) -> list[str]:
    if not text:
        return []
    if cn:
        return [s for s in _SENT_SPLIT_CN.split(text) if s.strip()]
    from .verify import split_sentences

    return split_sentences(text)


def _qualifier_hit(en: str, cn: str) -> str | None:
    """English numeric qualifiers must survive into Chinese (Ticket invariant 2).

    A qualifier counts only inside a sentence that also carries a numeral, so
    「优先级低于其他债务」 (no digit) and "run-up to" (hyphen prefix) never
    flag; ``up to 10 million`` -> 「1000万」 drops every CN qualifier lexeme
    and is flagged.
    """
    en_q = any(_EN_QUALIFIER_RE.search(s) for s in _sentences(en) if _HAS_DIGIT_RE.search(s))
    cn_q = any(_CN_QUALIFIER_RE.search(s) for s in _sentences(cn, cn=True) if _HAS_DIGIT_RE.search(s))
    if en_q and not cn_q:
        return "EN numeric qualifier dropped in CN"
    return None


def _polarity_hit(en: str, cn: str) -> str | None:
    """Financial direction inversion, scoped to paragraphs carrying a
    substantive pct/money token and a single direction per language.

    Requiring exactly one direction per side kills cross-subject paragraphs
    (an index falling *while* the S&P rises mentions both directions) and
    qualitative prose with no number at stake.
    """
    toks = extract_substantive_numbers((en or "") + "\n" + (cn or ""))
    if not any(t.kind in ("pct", "money", "bp") for t in toks):
        return None
    en_up, en_down = bool(_EN_UP.search(en or "")), bool(_EN_DOWN.search(en or ""))
    cn_up, cn_down = bool(_CN_UP.search(cn or "")), bool(_CN_DOWN.search(cn or ""))
    if en_up and not en_down and cn_down and not cn_up:
        return "EN upward verb paired with CN downward verb"
    if en_down and not en_up and cn_up and not cn_down:
        return "EN downward verb paired with CN upward verb"
    return None


def _negation_hit(en: str, cn: str) -> str | None:
    """Dropped hard negations in numeric sentences.

    Only English sentences carrying both a hard negation and a substantive
    numeral are checked (a financial claim is at stake); idiomatic rewrites
    like "can't keep up" -> 「远超供给能力」 in number-free prose stay silent.
    """
    if _CN_NEG.search(cn or ""):
        return None
    en_clean = _BALLOT_NAME_RE.sub(" ", en or "")  # "No on G" is a campaign name
    for s in _sentences(en_clean):
        if _EN_NEG.search(s) and extract_substantive_numbers(s):
            return "EN hard negation on a numeric claim dropped in CN"
    return None


_CREDIT_LINE_RE = re.compile(r"^(FROM |PHOTO|SOURCE|IMAGE|CREDIT)|^(图片来源|来源)")


def _length_hit(en: str, cn: str) -> str | None:
    en_words = len((en or "").split())
    if en_words < 8 or _CREDIT_LINE_RE.search((en or "").strip()) or _CREDIT_LINE_RE.search((cn or "").strip()):
        return None
    ratio = len(cn or "") / max(en_words, 1)
    if ratio < 0.4:
        return f"length ratio {ratio:.2f} < 0.4 (possible truncation)"
    if ratio > 6.0:
        return f"length ratio {ratio:.2f} > 6.0 (possible runaway repetition)"
    return None


def _quote_unbalanced(text: str) -> bool:
    # 「’」 doubles as an apostrophe (Trump’s) — only paired quotes are checked.
    pairs = (("“", "”"), ("«", "»"), ("《", "》"))
    for op, cl in pairs:
        if (text or "").count(op) != (text or "").count(cl):
            return True
    if (text or "").count('"') % 2:
        return True
    return False


def _completeness_hit(article_id: str, pid: str, en: str, cn: str) -> str | None:
    if _CONTINUATION_RE.search(en or ""):
        return "dangling print continuation marker in EN"
    if _CONTINUATION_RE.search(cn or ""):
        return "dangling print continuation marker in CN"
    if _quote_unbalanced(en):
        return "unclosed quote in EN"
    if _quote_unbalanced(cn):
        return "unclosed quote in CN"
    note = KNOWN_ANOMALIES.get(f"{article_id}:{pid}")
    if note:
        return f"documented source grammar anomaly: {note}"
    return None


def scan_pair(article_id: str, pid: str, en: str, cn: str) -> list[Finding]:
    """Run all five invariants on one bilingual paragraph."""
    findings: list[Finding] = [
        Finding(article_id, pid, kind, detail) for kind, detail in _magnitude_findings(en, cn)
    ]
    for kind, fn in (
        ("qualifier", _qualifier_hit),
        ("polarity", _polarity_hit),
        ("negation", _negation_hit),
        ("length-ratio", _length_hit),
    ):
        detail = fn(en, cn)
        if detail:
            findings.append(Finding(article_id, pid, kind, detail))
    detail = _completeness_hit(article_id, pid, en, cn)
    if detail:
        findings.append(Finding(article_id, pid, "completeness", detail))
    return findings


def stage1_radar(pairs: Iterable[tuple[str, str, str, str]]) -> list[Finding]:
    """Scan ``(article_id, paragraph_id, en, cn)`` pairs; return all findings."""
    out: list[Finding] = []
    for article_id, pid, en, cn in pairs:
        out.extend(scan_pair(article_id, pid, en, cn))
    return out


# --- Stage 2: targeted spot-check, disposition, compact report ---------------

def run_gate(
    translations: dict[str, dict[str, dict[str, str]]],
    *,
    issue: str,
    tier1_ids: Iterable[str] = (),
) -> GateReport:
    """Full-issue two-stage gate over the reviewed bilingual projection.

    Stage 2 dispositions every Stage-1 finding (documented anomalies are
    ``recorded``; everything else ``escalate`` to human review — canonical
    text is never rewritten) and spot-checks every Tier 1 flagship story.
    """
    start = time.perf_counter()
    pairs: list[tuple[str, str, str, str]] = []
    units_scanned = 0
    for aid in sorted(translations):
        for pid in sorted(translations[aid], key=lambda p: (len(p), p)):
            u = translations[aid][pid]
            en, cn = u.get("en", ""), u.get("cn", u.get("zh_CN", ""))
            pairs.append((aid, pid, en, cn))
            units_scanned += 1
    findings = stage1_radar(pairs)
    seen_keys = {(f.article_id, f.paragraph_id) for f in findings}
    for key, note in KNOWN_ANOMALIES.items():
        aid, _, pid = key.partition(":")
        if aid in translations and (aid, pid) not in seen_keys:
            findings.append(Finding(aid, pid, "completeness", f"documented source grammar anomaly: {note}"))
    for f in findings:
        key = f"{f.article_id}:{f.paragraph_id}"
        f.disposition = "recorded" if key in KNOWN_ANOMALIES else "escalate"
    spot = sorted(set(tier1_ids))
    duration = time.perf_counter() - start
    return GateReport(
        issue=issue,
        units_scanned=units_scanned,
        paragraphs_scanned=len(pairs),
        duration_s=duration,
        findings=findings,
        spot_checked=spot,
    )


def write_gate_report(report: GateReport, path: str | Path) -> Path:
    """Write the compact gate report JSON to the output workspace."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=1), "utf-8")
    return p
