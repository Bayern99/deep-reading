"""Full-issue print-signal routing: canonical sections, rubric kickers, tiers.

Deterministically classifies every one of the 86 raw inventory items of
2026-10-14 into the three editorial tiers of ADR 0001 and one of the seven
canonical sections, preserving the iconic WSJ rubric sub-columns as article
kickers.  Same-page recurring short fragments (Letters, Stock Spotlight,
U.S./World Watch, Corrections) are grouped into Composite Columns so the issue
compiles to ~70 cohesive reading units with zero one-paragraph orphan pages.

Routing is pure print-signal: page position, multi-page jumps, item type and
rubric — zero silent fallback; any inventory item that matches no route raises
``TracerCompilationError`` at build time.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .verify import TracerCompilationError

# --- Seven canonical sections ------------------------------------------------
# Every raw ``section`` string of inventory.json maps to exactly one canonical
# section; the remainder of the raw string becomes the rubric kicker.

SECTION_MAP: dict[str, str] = {
    # A1 front page
    "U.S. News": "us",
    "Business & Finance": "bt",
    "World News": "world",
    "What’s News": "a1",
    # rubric sub-columns (preserved as kickers)
    "U.S. News / Analysis": "us",
    "U.S. Watch": "us",
    "World Watch": "world",
    "Heard on the Street": "bt",
    "Money & Investing": "markets",
    "Money & Investing / Stock Spotlight": "markets",
    "Business & Tech": "bt",
    "Business News": "bt",
    "Corrections": "a1",
    "Personal Journal": "life",
    "The Property Report": "life",
    "Sports": "life",
    "Sports / Jason Gay": "life",
    "Arts in Review / Music": "life",
    "Arts in Review / Television": "life",
    "Opinion": "opinion",
    "Opinion / Letters": "opinion",
    "Opinion / Corrections": "opinion",
    "Opinion / Review & Outlook": "opinion",
    "Opinion / Business World": "opinion",
    "Opinion / Politics & Ideas": "opinion",
    "Opinion / Bookshelf": "opinion",
    "Opinion / Upward Mobility": "opinion",
    "Opinion / The Elder Influencer": "opinion",
}

# Canonical-section display order lives in shell.SECTIONS.

# --- Composite Columns ---------------------------------------------------------

COMPOSITES: dict[str, dict[str, object]] = {
    "COMPOSITE-A16-LETTERS": {
        "members": [
            "PILOT-A16-DIESEL-DOUG", "PILOT-A16-DIESEL-BOB", "PILOT-A16-DIESEL-STEVEN",
            "PILOT-A16-DIESEL-CHARLES", "PILOT-A16-DIESEL-DAN", "PILOT-A16-EDUCATION",
            "PILOT-A16-PERMITTING", "PILOT-A16-SHAPIRO", "PILOT-A16-NOBEL",
        ],
        "section": "opinion",
        "kicker": "来信 · LETTERS TO THE EDITOR · A16",
        "title_cn": "读者来信",
        "title_en": "Letters to the Editor",
        "dek_cn": "读者就柴油计划、教育创新、审批改革与和平奖评选发声。",
        "genre": "letters",
        "kind": "letters",  # group members by shared original title
    },
    "COMPOSITE-B13-SPOTLIGHT": {
        "members": [
            "PILOT-B13-SPOTLIGHT-UNITEDHEALTH", "PILOT-B13-SPOTLIGHT-BP",
            "PILOT-B13-SPOTLIGHT-VISA", "PILOT-B13-SPOTLIGHT-JNJ",
            "PILOT-B13-HISTORY",
        ],
        "section": "markets",
        "kicker": "个股聚焦 · STOCK SPOTLIGHT · B13",
        "title_cn": "个股聚焦",
        "title_en": "Stock Spotlight & Market History",
        "dek_cn": "联合健康、BP、Visa、强生个股快照，以及历史上的今天。",
        "genre": "spotlight",
        "kind": "briefs",
    },
    "COMPOSITE-A2-US-WATCH": {
        "members": ["PILOT-A2-ICE", "PILOT-A2-CORNELL", "PILOT-A2-OSSOFF"],
        "section": "us",
        "kicker": "美国简讯 · U.S. WATCH · A2",
        "title_cn": "美国简讯",
        "title_en": "U.S. Watch",
        "dek_cn": "移民执法、大学兄弟会派对与佐治亚州参议员动态。",
        "genre": "watch",
        "kind": "briefs",
    },
    "COMPOSITE-A8-WORLD-WATCH": {
        "members": ["PILOT-A8-SKOREA", "PILOT-A8-UKRAINE"],
        "section": "world",
        "kicker": "国际简讯 · WORLD WATCH · A8",
        "title_cn": "国际简讯",
        "title_en": "World Watch",
        "dek_cn": "韩国商场持刀伤人事件与乌克兰盟友预警之争。",
        "genre": "watch",
        "kind": "briefs",
    },
    "COMPOSITE-CORRECTIONS": {
        "members": ["PILOT-A2-CORRECTIONS", "PILOT-A16-CORRECTION"],
        "section": "opinion",
        "kicker": "更正 · CORRECTIONS & AMPLIFICATIONS",
        "title_cn": "更正与说明",
        "title_en": "Corrections & Amplifications",
        "dek_cn": "本报对前两日报道的更正与补充说明。",
        "genre": "corrections",
        "kind": "briefs",
    },
}

# --- Tier 1 flagships (print-signal derived) ----------------------------------
# ADR 0001 promises that print signals deterministically classify Tier 1. The
# rule below does that; the ids are no longer listed here.
#
# Measured on 2026-10-14 (86 items, 8 known flagships) and reproduced exactly on
# the held-out 2026-10-10 front page:
#
#   flagship = multi-page story AND (
#         starts on the paper's front page (folio A1)
#      OR starts on another section front (folio X1) AND body >= 850 words
#     )
#
# Why A1 is unconditional: on the reference issue every multi-page story that
# starts on A1 is a flagship (6 of 6), and the one A1 item that is not is the
# What's News digest, which is single-page. Position encodes hierarchy — the
# WSJ 2002 redesign fixed the front-page column roles (Poynter, "Behind the
# Redesign: WSJ").
#
# Why the B1 branch also needs a length test: the business front carried 6
# multi-page stories but only 2 flagships. Two independent signals agree on
# which 2 (left column + top half; and the two largest by body text), and
# length is the one computable from the inventory, so it is the one used.
#
# The word threshold is a DECLARED judgement, not a fitted constant: 830 fails
# and 911 passes on the reference issue, and every value in 850-900 gives the
# identical result, so it is not balanced on a single observation.
FLAGSHIP_MIN_BODY_WORDS = 850

#: Print identifier carried by every page, e.g. P2JW287000-5-A00100 -> stack A,
#: folio 001. Read rather than assumed: the reference issue has stacks A/B/S
#: across 36 pages, the held-out issue has A/B/C/D/R across 55, so any hardcoded
#: page boundary is wrong for one of them.
_PRINT_ID_RE = re.compile(r"P2JW\d+-\d+-([A-Z])(\d{3})\d{2}")


def _body_words(article: dict) -> int:
    return sum(len((p.get("text") or "").split()) for p in article.get("paragraphs") or [])


def _folio(page: int, natives: dict[int, dict] | None) -> tuple[str, int] | None:
    """(stack, folio) for a physical page, read from the paper's print id."""
    native = (natives or {}).get(page)
    if native:
        for line in native.get("lines", []):
            m = _PRINT_ID_RE.search(line.get("text", ""))
            if m:
                return m.group(1), int(m.group(2))
    return None


def is_front_page(page: int, natives: dict[int, dict] | None = None) -> bool:
    """Whether a printed page is the paper's front page (stack A, folio 1)."""
    pos = _folio(page, natives)
    if pos:
        return pos == ("A", 1)
    return page == 1


def is_section_front(page: int, natives: dict[int, dict] | None = None) -> bool:
    """Whether a printed page is any section front (folio 1), read from the paper.

    Falls back to the physical-page convention only when no native page is
    available, so a caller without the vector layer can still route.
    """
    pos = _folio(page, natives)
    if pos:
        return pos[1] == 1
    return page in (1, 19)


def is_flagship(article: dict, natives: dict[int, dict] | None = None) -> bool:
    """ADR 0001 Tier 1, from print signals alone.

    The non-front-page branch is decided by the story's printed lead position —
    it starts in the paper's leftmost column and in the top half of the front —
    when the inventory carries that signal. `lead_position` is what a derived
    issue map supplies; a hand-reviewed inventory may omit it, in which case the
    body-length test below is used. On the reference issue the two agree on all
    eight flagships, which is why the length test was originally preferred: it
    was the one computable from the inventory at the time.
    """
    pages = article.get("all_pages") or []
    if len(pages) < 2:
        return False
    start = int(article.get("start_page") or pages[0])
    if not is_section_front(start, natives):
        return False
    if is_front_page(start, natives):
        return True
    lead = article.get("lead_position")
    if lead is not None:
        return bool(lead)
    return _body_words(article) >= FLAGSHIP_MIN_BODY_WORDS

# Tier 3 standalone items (compact functional format) beyond the composites.
TIER3_STANDALONE = {
    "PILOT-A1-WHATSNEWS": {"section": "a1", "genre": "digest", "kicker": "要闻 · WHAT'S NEWS · A1"},
    "PILOT-A2-DINOSAUR": {"section": "us", "genre": "photo_caption", "kicker": "图片新闻 · A2"},
}

# View-only original print pages for dense market tables (machine numeric
# transcription of these pages is not approved; the reader sees the print).
VIEW_ONLY_TABLE_PAGES = [28, 29, 30, 31]

# Sidebar cross-links: sidebar -> same-page parent story.  The ticket named
# PILOT-A8-SUBS, which is not among the 86 verified inventory items; the
# shipbuilder brief's same-page defense-desk parent is the Taiwan story.
SIDEBAR_PARENT = {"PILOT-A8-SHIPBUILDER": "PILOT-A8-TAIWAN"}


@dataclass(frozen=True)
class Route:
    """Routing decision for one inventory item (or composite unit)."""

    unit_id: str
    tier: int
    genre: str
    section: str
    kicker: str
    article_ids: tuple[str, ...]


def canonical_section(raw_section: str) -> str:
    key = (raw_section or "").strip()
    if key in SECTION_MAP:
        return SECTION_MAP[key]
    raise TracerCompilationError(f"unmapped raw section string: {raw_section!r}")


def print_page_label(page: int) -> str:
    """WSJ folio: pages 1–18 are A1–A18; pages 19+ are B1–B13 etc."""
    return f"A{page}" if page <= 18 else f"B{page - 18}"


def rubric_kicker(article: dict) -> str:
    """Kicker: rubric sub-column (or section name) · print page.

    Iconic sub-columns survive as the kicker (Heard on the Street, Review &
    Outlook, Bookshelf, Jason Gay, …); plain sections keep their own label.
    """
    sec = article.get("section", "")
    page = article.get("start_page") or (article.get("all_pages") or [0])[0]
    label = sec.split(" / ")[-1] if " / " in sec else sec
    return f"{label} · {print_page_label(int(page))}"


def route_article(article: dict, natives: dict[int, dict] | None = None) -> Route:
    """Deterministic three-tier routing for one non-composite inventory item."""
    aid = article["id"]
    raw = article.get("section", "")
    section = canonical_section(raw)

    if aid in TIER3_STANDALONE:
        spec = TIER3_STANDALONE[aid]
        return Route(aid, 3, spec["genre"], spec["section"], spec["kicker"], (aid,))

    if is_flagship(article, natives):
        return Route(aid, 1, article["type"], section, rubric_kicker(article), (aid,))

    atype = article["type"]
    if atype in ("article", "analysis", "opinion", "editorial", "review", "sidebar"):
        return Route(aid, 2, atype, section, rubric_kicker(article), (aid,))
    if atype == "brief":
        return Route(aid, 3, "brief", section, rubric_kicker(article), (aid,))
    if atype == "photo_caption":
        return Route(aid, 3, "photo_caption", section, rubric_kicker(article), (aid,))
    if atype == "news_digest":
        # The front-page bullet roundup. On the reference issue it is named in
        # TIER3_STANDALONE; a derived map reaches it by type.
        return Route(aid, 3, "digest", section, rubric_kicker(article), (aid,))
    raise TracerCompilationError(f"{aid}: no route for inventory type {atype!r}")


def composite_route(unit_id: str) -> Route:
    spec = COMPOSITES[unit_id]
    return Route(
        unit_id=unit_id,
        tier=3,
        genre=str(spec["genre"]),
        section=str(spec["section"]),
        kicker=str(spec["kicker"]),
        article_ids=tuple(spec["members"]),
    )


def route_issue(articles: dict[str, dict],
                natives: dict[int, dict] | None = None,
                composites: dict[str, dict] | None = None) -> list[Route]:
    """Route the whole issue; every raw item lands in exactly one unit.

    ``composites`` lets a derived issue map supply its own Composite Columns
    (grouped by printed rubric) instead of the reference issue's hand-made table.
    Curation stays the single source of tiers either way.
    """
    table = COMPOSITES if composites is None else composites
    routes: list[Route] = []
    composite_members = {m for spec in table.values() for m in spec["members"]}
    for aid in sorted(articles):
        article = articles[aid]
        if aid in composite_members:
            continue
        routes.append(route_article(article, natives))
    for uid, spec in table.items():
        routes.append(Route(
            unit_id=uid,
            tier=3,
            genre=str(spec["genre"]),
            section=str(spec["section"]),
            kicker=str(spec["kicker"]),
            article_ids=tuple(spec["members"]),
        ))
    routed = {aid for r in routes for aid in r.article_ids}
    missing = set(articles) - routed
    if missing:
        raise TracerCompilationError(f"inventory items without a route: {sorted(missing)}")
    return routes
