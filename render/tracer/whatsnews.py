"""What's News deep links: bullet -> full-article resolution (ADR 0001).

Each of the 16 bullet paragraphs of ``PILOT-A1-WHATSNEWS`` (``p2..p9`` under
*Business&Finance*, ``p11..p18`` under *Worldwide*) is automatically matched
to its full article in the issue by entity/keyword/number overlap against the
inventory titles and lead paragraphs.  The reader renders an interactive
deep-link badge (``→ 详见 B1 / Read Full Story``) jumping straight to that
article's reading unit, while the ``p1..p18`` narrative spans stay byte-for-
byte intact for SHA256 narrative conservation — the badge is a sibling
element, never an edit of the bullet text.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass

from .numbers import extract_substantive_numbers
from .verify import TracerCompilationError

DIGEST_ID = "PILOT-A1-WHATSNEWS"
HEADER_PARAGRAPHS = ("p1", "p10")  # Business&Finance / Worldwide column heads

_STOPWORDS = set(
    "the a an and of to in on for as at by it its he she his her their they we "
    "you i not no are was were is be has have had said say more other from with "
    "without after before that this which who whom will would could should can "
    "may might also into over under".split()
)

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’\-]+")


def _keywords(text: str) -> set[str]:
    toks = {w.strip("’").strip("'s,.:;\"“”()").lower() for w in _WORD_RE.findall(text or "")}
    return {k for k in toks if k not in _STOPWORDS and len(k) > 2}


def _bullet_ids(units: dict[str, dict[str, str]]) -> list[str]:
    return sorted(
        (u for u in units if re.fullmatch(r"p\d+", u) and u not in HEADER_PARAGRAPHS),
        key=lambda p: int(p[1:]),
    )


@dataclass(frozen=True)
class DeepLink:
    paragraph_id: str
    target_id: str
    target_page_label: str
    score: int


def resolve_whatsnews(data, composite_members: set[str] | None = None) -> dict[str, DeepLink]:
    """Entity/keyword/number overlap resolver for all 16 digest bullets.

    Candidate corpus: every full narrative item of the issue (composite
    members, corrections, captions and the digest itself are excluded — deep
    links always jump to a full article).  Score: 2 per shared keyword,
    6 per shared substantive number; ties and empty candidates are
    compilation errors, never silent skips.
    """
    composite_members = composite_members or set()
    digest = data.articles[DIGEST_ID]
    units = data.units(DIGEST_ID)
    pids = _bullet_ids(units)

    candidates: dict[str, tuple[set[str], set[tuple]]] = {}
    for aid, article in data.articles.items():
        if aid == DIGEST_ID or aid in composite_members:
            continue
        if article["type"] in ("news_digest", "correction", "photo_caption", "letter"):
            continue
        text = article["original_title"] + " " + " ".join(
            (p.get("text") or "")[:200] for p in article["paragraphs"][:3]
        )
        candidates[aid] = (
            _keywords(text),
            {(t.value, t.kind) for t in extract_substantive_numbers(text)},
        )
    if not candidates:
        raise TracerCompilationError("What's News resolver: empty candidate corpus")

    links: dict[str, DeepLink] = {}
    for pid in pids:
        bullet = units[pid]["en"].lstrip("• ")
        kw = _keywords(bullet)
        nums = {(t.value, t.kind) for t in extract_substantive_numbers(bullet)}
        best: tuple[int, str] | None = None
        for aid, (ckw, cnums) in candidates.items():
            score = len(kw & ckw) * 2 + len(nums & cnums) * 6
            if best is None or score > best[0]:
                best = (score, aid)
        assert best is not None
        score, aid = best
        if score <= 0:
            raise TracerCompilationError(f"{DIGEST_ID} {pid}: no overlapping candidate article")
        page = data.articles[aid].get("start_page") or data.articles[aid]["all_pages"][0]
        from .routing import print_page_label

        links[pid] = DeepLink(pid, aid, print_page_label(int(page)), score)
    return links


def deep_link_badge(link: DeepLink) -> str:
    """Interactive deep-link badge appended after the bullet paragraph."""
    target = html.escape(link.target_id, quote=True)
    label = html.escape(link.target_page_label)
    return (
        f'<p class="wn-link"><a href="#u-{target}">'
        f"→ 详见 {label} <span class=\"wn-en\">/ Read Full Story</span></a></p>"
    )
