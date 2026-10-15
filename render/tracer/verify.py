"""Inline paragraph-scoped verification and AST surgical completion.

Everything the compiler needs to guarantee, per ADR 0001:

- ``data-ref="pK"`` / ``data-ref="pK.sM"`` verbatim anchors in both languages.
- ``data-hl`` phrase highlighting capped at <= 12% total character density.
- Every authored element carrying ``data-src="pK"`` has all of its substantive
  numbers grounded in the referenced paragraphs (or the chart's native
  ``Retina*`` vector lines).
- Missing / misordered ``pK`` narrative blocks are surgically inserted or
  reordered in the ``lxml`` AST — never silently dropped.
- Zero pipeline audit chrome: forbidden strings raise on the reader surface.

Failure modes that micro-repair cannot resolve raise ``TracerCompilationError``
— tiers are never silently downgraded.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

import lxml.html
import lxml.etree

from .numbers import NumberToken, extract_substantive_numbers, ground_numbers, norm_number

HL_CAP = 0.12
PROSE_CLASS = "prose-p"
HL_MARK = 'mark class="ed-hl"'

FORBIDDEN_STRINGS = ("待审译稿", "未经逐格核准", "Inspect source", "已核验")


class TracerCompilationError(ValueError):
    """Explicit compilation failure; carries an audit report."""


# --- data-src number grounding ---------------------------------------------

def verify_element_numbers(
    element_label: str,
    authored_text: str,
    source_texts: Iterable[str],
    extra_grounding: Iterable[str] = (),
) -> None:
    """Raise unless every substantive number in authored text is grounded."""
    ungrounded = ground_numbers(authored_text, source_texts, extra_grounding=extra_grounding)
    if ungrounded:
        raise TracerCompilationError(
            f"{element_label}: ungrounded numbers "
            + ", ".join(f"{t.raw} ({t.value} {t.kind})" for t in ungrounded)
        )


# --- data-ref sentence anchors ----------------------------------------------

_SENT_SPLIT = re.compile(r"(?<=[.!?;:\"”’])\s+(?=[“\"A-Z0-9])")


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []
    return [s for s in _SENT_SPLIT.split(text) if s.strip()]


def sentence_anchor(paragraph_en: str, m: int) -> str:
    """Verbatim sentence ``sM`` of a paragraph (1-based); raises if absent."""
    sentences = split_sentences(paragraph_en)
    if not (1 <= m <= len(sentences)):
        raise TracerCompilationError(
            f"data-ref sentence s{m} out of range: paragraph has {len(sentences)} sentences"
        )
    return sentences[m - 1]


def verify_quote_anchor(paragraph_en: str, m: int, quote_text: str) -> None:
    """A pull quote bound to ``pK.sM`` must be verbatim that sentence."""
    want = re.sub(r"\s+", " ", sentence_anchor(paragraph_en, m)).strip()
    got = re.sub(r"\s+", " ", (quote_text or "")).strip()
    if want != got:
        raise TracerCompilationError(
            f"pull quote is not verbatim p.s{m}:\n  want: {want!r}\n  got:  {got!r}"
        )


# --- data-hl density ---------------------------------------------------------

def _visible_text(el: lxml.html.HtmlElement) -> str:
    return re.sub(r"\s+", "", el.text_content() or "")


def check_highlight_density(article_el: lxml.html.HtmlElement, cap: float = HL_CAP) -> float:
    """Marked characters / total characters across the article narrative.

    Computes per ``.lang-cn`` and ``.lang-en`` stream when bilingual spans are
    present, else over the whole prose; returns the maximum density found.
    Raises ``TracerCompilationError`` when the cap is exceeded.
    """
    densities: list[float] = []
    lang_blocks = article_el.xpath(
        ".//*[contains(concat(' ', normalize-space(@class), ' '), ' lang-cn ')"
        " or contains(concat(' ', normalize-space(@class), ' '), ' lang-en ')]"
    )
    if lang_blocks:
        for block in lang_blocks:
            total = len(_visible_text(block))
            if total == 0:
                continue
            marked = 0
            for mark in block.iter("mark"):
                marked += len(_visible_text(mark))
            densities.append(marked / total)
    else:
        total = 0
        marked = 0
        for p in article_el.iter("p"):
            total += len(_visible_text(p))
            for mark in p.iter("mark"):
                marked += len(_visible_text(mark))
        if total:
            densities.append(marked / total)
    worst = max(densities, default=0.0)
    if worst > cap:
        raise TracerCompilationError(
            f"data-hl density {worst:.3f} exceeds cap {cap:.2f}"
        )
    return worst


# --- AST surgical completion -------------------------------------------------

def surgical_narrative_completion(
    article_el: lxml.html.HtmlElement,
    paragraph_ids: list[str],
    canonical_text: dict[str, tuple[str, str]] | None = None,
) -> list[str]:
    """Insert/reorder ``<p class="prose-p" data-ref="pK">`` blocks in the AST.

    Returns the list of repair operations performed.  Missing blocks are
    inserted at their canonical position (filled from ``canonical_text`` when
    provided); misordered blocks are reordered in place.  Never silent: every
    repair is reported.
    """
    repairs: list[str] = []
    prose = [
        p for p in article_el.iter("p")
        if PROSE_CLASS in (p.get("class") or "").split()
        and re.fullmatch(r"p\d+", p.get("data-ref") or "")
    ]

    wanted_index = {pid: i for i, pid in enumerate(paragraph_ids)}
    seen: dict[str, lxml.html.HtmlElement] = {}
    for p in prose:
        ref = p.get("data-ref")
        if ref in wanted_index and ref not in seen:
            seen[ref] = p

    # Relocate blocks that are missing or misordered: walk the canonical id
    # list, keep an "anchor" (last block placed in document order) and insert
    # each block right after the anchor when it is absent or out of place.
    anchor: lxml.html.HtmlElement | None = None
    for pid in paragraph_ids:
        el = seen.get(pid)
        if el is not None and anchor is not None and el.getparent() is not None:
            siblings = list(anchor.itersiblings())
            if el in siblings:
                anchor = el
                continue
            el.getparent().remove(el)
            anchor.addnext(el)
            repairs.append(f"reorder:{pid}")
            anchor = el
            continue
        if el is not None:
            anchor = el
            continue
        # missing: create and insert after anchor (or before first later prose)
        p = lxml.html.Element("p")
        p.set("class", PROSE_CLASS)
        p.set("data-ref", pid)
        cn, en = (canonical_text or {}).get(pid, ("", ""))
        if cn or en:
            span_cn = lxml.etree.SubElement(p, "span")
            span_cn.set("class", "lang-cn")
            span_cn.text = cn
            span_en = lxml.etree.SubElement(p, "span")
            span_en.set("class", "lang-en")
            span_en.text = en
        inserted = False
        if anchor is not None:
            anchor.addnext(p)
            inserted = True
        else:
            for later in paragraph_ids[wanted_index[pid] + 1:]:
                if later in seen and seen[later].getparent() is not None:
                    seen[later].addprevious(p)
                    inserted = True
                    break
        if not inserted:
            article_el.append(p)
        seen[pid] = p
        repairs.append(f"insert:{pid}")
        anchor = p

    return repairs


# --- pipeline chrome guard ---------------------------------------------------

def assert_no_forbidden_strings(html_text: str) -> None:
    hits = [s for s in FORBIDDEN_STRINGS if s in html_text]
    if hits:
        raise TracerCompilationError(
            "pipeline audit chrome on reader surface: " + ", ".join(hits)
        )
