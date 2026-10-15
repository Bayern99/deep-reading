"""Substantive-number extraction and cross-language numeric grounding.

Inline paragraph-scoped verification (`data-src="pK"`) requires comparing the
numbers an editor authored (takeaways, subheadings, callouts, Chart Companions,
`<wsj-chart>` labels) against the referenced paragraph text — in either
language.  "$10 billion" and 「100亿美元」 must normalize to the same magnitude;
``700 million`` vs 「7000万」 must not.

Only substantive tokens are considered: currencies, percentages, basis points
and numbers carrying a scale/unit word.  Structural list ordinals (``1.``,
``2.`` …) and bare layout attributes are ignored by construction (this module
never sees SVG geometry).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable

# --- Token extraction -------------------------------------------------------

# One capture pattern: currency mark, number, scale word, unit — all optional
# beyond the number itself; classification happens in code.  The trailing
# lookahead blocks mid-token matches ("10-year", "3Q", "1.4" in "1.45").
_EN_TOKEN = re.compile(
    r"(?<![\d.])(?P<cur>[$€£])?\s*(?P<num>\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<scale>billion|million|trillion|thousand)?\s*"
    r"(?P<unit>%|percent|basis\s*points?|bps?|bp)?(?![\w]|-(?=\d)|\.\d)",
    re.I,
)

# Verbal fractions: "half a million" == 500,000 == 「50万」.
_EN_VERBAL_FRACTION = re.compile(r"\bhalf a (million|billion|trillion)\b", re.I)
_VERBAL_FRACTION_VALUE = {"million": Decimal(5e5), "billion": Decimal(5e8), "trillion": Decimal(5e11)}

# Spelled-out English cardinals with a scale word (PILOT-A16-CORRECTION p1):
# "Four hundred thousand dollars" == 400,000 USD == 「40万美元」;
# "seven hundred million" == 700,000,000 == 「7亿」.  Only expressions
# carrying thousand/million/billion are substantive money by construction.
_SPELL_UNITS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_SPELL_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_EN_SPELL = re.compile(
    r"\b(?P<w1>one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|"
    r"thirty|forty|fifty|sixty|seventy|eighty|ninety)"
    r"(?P<hundred>\s+hundred)?"
    r"\s+(?P<scale>thousand|million|billion)(?P<dollars>\s+dollars)?\b",
    re.I,
)
_SPELL_SCALE_MULT = {"thousand": Decimal(1e3), "million": Decimal(1e6), "billion": Decimal(1e9)}

# Calendar years / decades are structural time references, not substantive
# counts: Chinese routinely renders "1980s" as 「上世纪80年代」 or "in 1890" as
# 「19世纪90年代」, which must not flag as magnitude errors (Reviewer-G).
def _is_calendar_year(num: Decimal) -> bool:
    return num == num.to_integral_value() and Decimal(1700) <= num <= Decimal(2099)

# Chinese range endpoints sharing one trailing unit: 「约20至50美元」 carries
# both 20美元 and 50美元; without this only the second endpoint is seen.
_CN_RANGE = re.compile(
    r"(?P<n1>\d[\d,.]*)\s*(?:至|到|—|–|-|~)\s*(?P<n2>\d[\d,.]*)\s*"
    r"(?P<unit>万亿美元|亿美元|万美元|美元|万亿|亿|万|个百分点|个基点|基点|%|％)"
)
_CN_RANGE_UNIT = {
    "美元": ("money", Decimal(1)), "万美元": ("money", Decimal(1e4)), "亿": ("money", Decimal(1e8)),
    "亿美元": ("money", Decimal(1e8)), "万亿": ("money", Decimal(1e12)),
    "万亿美元": ("money", Decimal(1e12)), "万": ("money", Decimal(1e4)),
    "%": ("pct", Decimal(1)), "％": ("pct", Decimal(1)), "个百分点": ("pct", Decimal(1)),
    "基点": ("bp", Decimal(1)), "个基点": ("bp", Decimal(1)),
}

# Chinese numeral words that scale 万/亿 directly: 「两万」 == 20,000.
_CN_WORD_DIGITS = {"两": Decimal(2)}


def _word_scaled_num(text: str) -> Decimal | None:
    m = re.match(r"(两)(?=[万亿])", text or "")
    if m:
        return _CN_WORD_DIGITS[m.group(1)]
    return None


_CN_TOKEN = re.compile(
    r"(?P<num>\d[\d,.]*|两)(?=[\s万亿个基点%％])?\s*(?P<unit>亿|万|千)?\s*"
    r"(?P<cur>美元|英镑|欧元|加元|澳元|港元|日元|韩元|人民币|卢布)?\s*(?P<bp>个基点?|基点)?\s*(?P<pct>%|％)?"
)

# Currency names normalize to the same "money" kind as $ / £ / € so that
# 「9.99美元」 and "$9.99" are the same token and "$5.57" vs 「9.99美元」 mismatches.
_CN_CURRENCY = ("美元", "英镑", "欧元", "加元", "澳元", "港元", "日元", "韩元", "人民币", "卢布")


@dataclass(frozen=True)
class NumberToken:
    """A normalized substantive number.

    ``value`` is the absolute magnitude as a Decimal in base units
    (percent kept as the printed number, e.g. 5.1 for 5.1%; basis points kept
    as printed).  ``kind`` is one of money|pct|bp|count|year.
    """

    value: Decimal
    kind: str
    raw: str


def _dec(s: str) -> Decimal | None:
    try:
        return Decimal(s.replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def _en_tokens_spanned(text: str) -> list[tuple[int, int, NumberToken]]:
    out: list[tuple[int, int, NumberToken]] = []
    for m in _EN_VERBAL_FRACTION.finditer(text or ""):
        scale = m.group(1).lower()
        out.append((m.start(), m.end(), NumberToken(_VERBAL_FRACTION_VALUE[scale], "money", m.group(0).strip())))
    for m in _EN_SPELL.finditer(text or ""):
        w1 = m.group("w1").lower()
        base = Decimal(_SPELL_UNITS.get(w1) or _SPELL_TENS[w1])
        if m.group("hundred"):
            base *= Decimal(100)
        value = base * _SPELL_SCALE_MULT[m.group("scale").lower()]
        out.append((m.start(), m.end(), NumberToken(value, "money", m.group(0).strip())))
    for m in _EN_TOKEN.finditer(text or ""):
        num = _dec(m.group("num"))
        if num is None:
            continue
        scale = m.group("scale")
        unit = (m.group("unit") or "").lower()
        cur = m.group("cur")
        if unit in ("%", "percent"):
            out.append((m.start(), m.end(), NumberToken(num, "pct", m.group(0).strip())))
        elif "basis" in unit or unit in ("bps", "bp"):
            out.append((m.start(), m.end(), NumberToken(num, "bp", m.group(0).strip())))
        elif cur or scale:
            mult = {"thousand": Decimal(1e3), "million": Decimal(1e6), "billion": Decimal(1e9), "trillion": Decimal(1e12)}.get((scale or "").lower(), Decimal(1))
            out.append((m.start(), m.end(), NumberToken(num * mult, "money", m.group(0).strip())))
        elif num >= Decimal(1000) and not _is_calendar_year(num):
            out.append((m.start(), m.end(), NumberToken(num, "count", m.group(0).strip())))
        # bare small integers without unit are structural noise (list ordinals
        # 1. 2. 3., "10-year", quarter labels 3Q) and are ignored by design;
        # 4-digit calendar years/decades are structural time references.
    return out


def _en_tokens(text: str) -> list[NumberToken]:
    return [tok for _, _, tok in _en_tokens_spanned(text)]


def _cn_tokens(
    text: str,
    en_spans: list[tuple[int, int]] | None = None,
) -> list[NumberToken]:
    """Chinese-context tokens; skips spans already claimed by the EN stream.

    Without span exclusion the CN regex re-extracts every ASCII ``6.8%``
    (Reviewer-G duplicate-percent note) and the same value is grounded twice.
    """
    out: list[NumberToken] = []
    # Range endpoints sharing one trailing unit: 「约20至50美元」 -> both
    # 20美元 and 50美元 (Reviewer-G: OIL p2 "about $20 to $50").
    for m in _CN_RANGE.finditer(text or ""):
        if en_spans and any(m.start() < e and s < m.end() for s, e in en_spans):
            continue
        kind, mult = _CN_RANGE_UNIT[m.group("unit")]
        for key in ("n1", "n2"):
            num = _dec(m.group(key))
            if num is not None:
                out.append(NumberToken(num * mult, kind, m.group(0).strip()))
    for m in _CN_TOKEN.finditer(text or ""):
        if en_spans and any(m.start() < e and s < m.end() for s, e in en_spans):
            continue
        raw_num = m.group("num")
        # skip ordinals like 「1.」 and decimal fragments already consumed
        if raw_num.endswith(".") or raw_num.endswith(","):
            continue
        if raw_num == "两":
            num = _word_scaled_num(text[m.start():])
        else:
            num = _dec(raw_num)
        if num is None:
            continue
        unit = m.group("unit")
        cur = m.group("cur")
        bp = m.group("bp")
        pct = m.group("pct")
        if pct:
            out.append(NumberToken(num, "pct", m.group(0).strip()))
        elif bp:
            out.append(NumberToken(num, "bp", m.group(0).strip()))
        elif unit:
            if unit == "万" and m.group(0).strip().startswith(raw_num) and "万亿" in (text or "")[m.start():m.end() + 1]:
                mult = Decimal(1e12)  # 「5万亿」 == five trillion
            else:
                mult = {"千": Decimal(1e3), "万": Decimal(1e4), "亿": Decimal(1e8)}[unit]
            out.append(NumberToken(num * mult, "money", m.group(0).strip()))
        elif cur:
            # bare Chinese currency: 9.99美元 / 32美元 / 5.57美元
            out.append(NumberToken(num, "money", m.group(0).strip()))
        elif num >= Decimal(1000) and not _is_calendar_year(num):
            out.append(NumberToken(num, "count", m.group(0).strip()))
    return out


def extract_substantive_numbers(text: str) -> list[NumberToken]:
    """All substantive numbers in a bilingual string, normalized, deduplicated.

    The EN stream claims its spans first (ASCII ``6.8%``), the CN stream keeps
    full-width ``％`` and Chinese-context amounts; overlapping duplicates are
    emitted once.  Only spans of *substantive* EN tokens are claimed, so a
    bare structural match (``mid-6%``) never shadows the CN token.
    """
    en = _en_tokens_spanned(text)
    en_spans = [(s, e) for s, e, _ in en]
    seen: set[tuple[Decimal, str]] = set()
    out: list[NumberToken] = []
    for tok in [t for _, _, t in en] + _cn_tokens(text, en_spans):
        key = norm_number(tok)
        if key in seen:
            continue
        seen.add(key)
        out.append(tok)
    return out


def norm_number(tok: NumberToken) -> tuple[Decimal, str]:
    return (tok.value, tok.kind)


def ground_numbers(
    authored_text: str,
    source_texts: Iterable[str],
    *,
    extra_grounding: Iterable[str] = (),
) -> list[NumberToken]:
    """Numbers in ``authored_text`` not found in the source grounding set.

    A number is grounded when a token with equal ``(value, kind)`` exists in
    any source text.  ``kind`` mismatch (e.g. authored ``5.1%`` vs source
    ``5.1`` count) is a mismatch.  Returns the ungrounded tokens (empty list =
    fully grounded).
    """
    available: set[tuple[Decimal, str]] = set()
    for t in list(source_texts) + list(extra_grounding):
        for tok in extract_substantive_numbers(t):
            available.add(norm_number(tok))
    return [tok for tok in extract_substantive_numbers(authored_text) if norm_number(tok) not in available]
