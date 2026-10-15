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
    r"(?P<unit>%|percent|basis\s*points?|bps?|bp)?(?![\w-])"
)

_CN_TOKEN = re.compile(
    r"(?P<num>\d[\d.]*)\s*(?P<unit>亿|万|千)?\s*(?P<cur>美元|英镑|欧元|加元|澳元|港元|日元|韩元|人民币|卢布)?\s*(?P<pct>%|％)?"
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


def _en_tokens(text: str) -> list[NumberToken]:
    out: list[NumberToken] = []
    for m in _EN_TOKEN.finditer(text or ""):
        num = _dec(m.group("num"))
        if num is None:
            continue
        scale = m.group("scale")
        unit = (m.group("unit") or "").lower()
        cur = m.group("cur")
        if unit in ("%", "percent"):
            out.append(NumberToken(num, "pct", m.group(0).strip()))
        elif "basis" in unit or unit in ("bps", "bp"):
            out.append(NumberToken(num, "bp", m.group(0).strip()))
        elif cur or scale:
            mult = {"thousand": Decimal(1e3), "million": Decimal(1e6), "billion": Decimal(1e9), "trillion": Decimal(1e12)}.get(scale, Decimal(1))
            out.append(NumberToken(num * mult, "money", m.group(0).strip()))
        elif num >= Decimal(1000):
            out.append(NumberToken(num, "count", m.group(0).strip()))
        # bare small integers without unit are structural noise (list ordinals
        # 1. 2. 3., "10-year", quarter labels 3Q) and are ignored by design.
    return out


def _cn_tokens(text: str) -> list[NumberToken]:
    out: list[NumberToken] = []
    for m in _CN_TOKEN.finditer(text or ""):
        raw_num = m.group("num")
        # skip ordinals like 「1.」 and decimal fragments already consumed
        if raw_num.endswith("."):
            continue
        num = _dec(raw_num)
        if num is None:
            continue
        unit = m.group("unit")
        cur = m.group("cur")
        pct = m.group("pct")
        if pct:
            out.append(NumberToken(num, "pct", m.group(0).strip()))
        elif unit:
            mult = {"千": Decimal(1e3), "万": Decimal(1e4), "亿": Decimal(1e8)}[unit]
            out.append(NumberToken(num * mult, "money", m.group(0).strip()))
        elif cur:
            # bare Chinese currency: 9.99美元 / 32美元 / 5.57美元
            out.append(NumberToken(num, "money", m.group(0).strip()))
        elif num >= Decimal(1000):
            out.append(NumberToken(num, "count", m.group(0).strip()))
    return out


def extract_substantive_numbers(text: str) -> list[NumberToken]:
    """All substantive numbers in a bilingual string, normalized."""
    return _en_tokens(text) + _cn_tokens(text)


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
