"""Article map derivation: deterministic print facts + reader item assembly.

Architecture (ADR 0003 / ticket #7):
  native.json -> line_table + print_facts (deterministic)
  reader cache -> per-page reading items (start line, kind, first line, rubric)
  assemble(items, natives) -> ownership records (id, start_page, section, all_pages, …)
"""
from __future__ import annotations

import hashlib
import json
import re
from itertools import permutations
from pathlib import Path
from typing import Any

from .routing import SECTION_MAP, _folio, canonical_section, print_page_label
from .verify import TracerCompilationError

READER_KINDS = frozenset(
    {
        "analysis",
        "article",
        "brief",
        "correction",
        "editorial",
        "letter",
        "news_digest",
        "opinion",
        "photo_caption",
        "review",
        "sidebar",
    }
)
#: The extractor emits two naming schemes for the same paper: `DJ5EscrowCond-Roman`
#: on some pages and `EscrowBannerCondensed-Bo` on others, depending on the embedded
#: font names. Both are Dow Jones faces; anything else (PalatinoLinotype, Abolition,
#: TradeGothic, Didot) is advertising or stock imagery. Measured on the reference
#: issue: pages 4 and 16 differ in scheme while both being editorial pages.
_DJ_FONT_PREFIX = ("DJ5", "DJ4", "Retina", "Escrow", "Exchange")

#: A page carrying no article text is an image-only advertisement. Derived, not
#: listed: measured on the reference issue the eight advertisement pages carry
#: 31–1,824 extracted characters while the lightest editorial page carries 5,147,
#: so the gap is wide and no per-issue table is needed (FOUNDATION 12).
_AD_PAGE_MAX_CHARS = 4000

_SECTION_HEAD_MIN = 18.0
#: Faces the paper uses for a rubric sub-column heading above a story, measured
#: against every golden story that carries one. `EscrowBannerCompressed` is the
#: same face as a section banner, so it only counts as a rubric when it is small.
_RUBRIC_FONTS = (
    "DJ5EscrowWide",
    "EscrowWide",
    "DJ5EscrowOutline",
    "EscrowOutline",
    "DJ5Escrow-Bold",
    "Escrow-Bold",
    "DJ5EscrowComp",
    "EscrowComp",
    "RetinaCondensedBold",
    "DJ5EscrowCond-BoldItalic",
    "EscrowCond-BoldItalic",
)
#: `EscrowBannerCompressed` sets both section banners (36–98pt) and small
#: rubric heads such as `CORRECTIONS & AMPLIFICATIONS` (18pt).
_BANNER_FONT = "EscrowBannerCompressed"
_RUBRIC_BANNER_MAX = 24.0
#: Drop caps reuse the rubric faces at 40pt+; nothing that large is a rubric.
_RUBRIC_MAX_SIZE = 30.0

_BASE_FROM_PRINT = {
    "usnews": "U.S. News",
    "businessfinance": "Business & Finance",
    "worldnews": "World News",
    "opinion": "Opinion",
    "personaljournal": "Personal Journal",
    "thepropertyreport": "The Property Report",
    "sports": "Sports",
    "moneyinvesting": "Money & Investing",
    "businessnews": "Business News",
    "businesstech": "Business & Tech",
    "heardonthestreet": "Heard on the Street",
    "corrections": "Corrections",
    "artsinreview": "Arts in Review",
    "whatsnews": "What's News",
}
def _norm_rubric(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


_RUBRIC_TO_SECTION: dict[str, str] = {}
for _raw in SECTION_MAP:
    if " / " in _raw:
        _base, _rub = _raw.split(" / ", 1)
        # A rubric that is also a top-level section keeps its own meaning:
        # `Corrections` is a section, not only `Opinion / Corrections`.
        _RUBRIC_TO_SECTION.setdefault(_norm_rubric(_rub), _raw)
    else:
        _RUBRIC_TO_SECTION[_norm_rubric(_raw)] = _raw

def _norm_title(text: str) -> str:
    text = (text or "").replace("\u2019", "'").replace("\u2014", "-")
    return re.sub(r"[^a-z0-9]+", "", text.lower())




def _dominant_char(line: dict[str, Any]) -> tuple[str, float]:
    chars = line.get("chars") or []
    if not chars:
        return "", 0.0
    counts: dict[str, int] = {}
    for ch in chars:
        font = str(ch.get("font") or "")
        counts[font] = counts.get(font, 0) + 1
    font = max(counts, key=counts.get)
    size = max(float(ch.get("size") or 0.0) for ch in chars)
    return font, size


def _is_dj_font(font: str) -> bool:
    return any(font.startswith(p) for p in _DJ_FONT_PREFIX)


def line_table(page_native: dict[str, Any]) -> list[dict[str, Any]]:
    """Deterministic export of every line for the strong-model reader."""
    rows: list[dict[str, Any]] = []
    for line in page_native.get("lines") or []:
        font, size = _dominant_char(line)
        bbox = line.get("bbox") or [0, 0, 0, 0]
        rows.append(
            {
                "id": line.get("id"),
                "y": float(bbox[1]),
                "x": float(bbox[0]),
                "size": round(size, 2),
                "font": font,
                "text": line.get("text") or "",
                "bbox": bbox,
            }
        )
    return rows


def column_grid(page_native: dict[str, Any]) -> list[float]:
    buckets: dict[int, int] = {}
    for line in page_native.get("lines") or []:
        font, size = _dominant_char(line)
        # Body text is set at 8.4pt on the reference issue; a 8.5pt floor
        # silently emptied the grid on most pages.
        if not _is_dj_font(font) or size < 8.0:
            continue
        text = (line.get("text") or "").strip()
        if len(text) < 10:
            continue
        x0 = float((line.get("bbox") or [0])[0])
        key = int(round(x0 / 4.0) * 4)
        buckets[key] = buckets.get(key, 0) + 1
    xs = sorted(k for k, c in buckets.items() if c >= 5)
    # Body lines in one column do not share an exact left edge — different faces
    # carry different left bearings, and indented lines sit further right. Group
    # by the printed column pitch (about 123pt) and keep the leftmost edge, which
    # is the column origin the golden regions record.
    cols: list[float] = []
    for x in xs:
        if cols and x - cols[-1] < 100:
            continue
        cols.append(float(x))
    return cols


def _section_head_text(page_native: dict[str, Any]) -> str | None:
    """The section banner printed at the top of the page, if any.

    A banner can be extracted as several lines in a scrambled order — page 32
    yields `HEARD`, `THESTREET`, `ON` — so the printed tokens are concatenated in
    every order and matched against the canonical section vocabulary. A page that
    prints no banner (the front page) returns ``None``.
    """
    tokens: list[str] = []
    for line in page_native.get("lines") or []:
        y = float((line.get("bbox") or [0, 9999])[1])
        if y > 120:
            continue
        font, size = _dominant_char(line)
        if size < 14 and "Escrow" not in font:
            continue
        text = (line.get("text") or "").strip()
        if not text or len(text) > 80:
            continue
        key = _norm_rubric(text)
        if not key or key in tokens:
            continue
        tokens.append(key)
    if not tokens:
        return None
    for r in range(1, min(len(tokens), 4) + 1):
        for combo in permutations(tokens, r):
            key = "".join(combo)
            if key in _BASE_FROM_PRINT:
                return _BASE_FROM_PRINT[key]
    return None


def _continuation_markers(page_native: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    forward: list[dict[str, Any]] = []
    backward: list[dict[str, Any]] = []
    for line in page_native.get("lines") or []:
        raw = re.sub(r"\s+", "", (line.get("text") or "").lower())
        m = re.search(r"pleaseturntopage([a-z]\d+|one)", raw)
        if m:
            forward.append({"line": line, "folio": m.group(1)})
            continue
        m = re.search(r"continuedfrompage([a-z]\d+|one)", raw)
        if m:
            backward.append({"line": line, "folio": m.group(1)})
    return {"forward": forward, "backward": backward}


def _parse_folio_token(token: str) -> tuple[str, int] | None:
    token = (token or "").lower()
    if token == "one":
        return ("A", 1)
    m = re.match(r"([a-z])(\d+)", token)
    if not m:
        return None
    return m.group(1).upper(), int(m.group(2))


def _is_ad_page(page_native: dict[str, Any]) -> bool:
    """Whether a page carries no article text (an image-only advertisement)."""
    chars = sum(len(line.get("chars") or ()) for line in page_native.get("lines") or ())
    return chars < _AD_PAGE_MAX_CHARS


def print_facts(page_native: dict[str, Any], natives: dict[int, dict] | None = None) -> dict[str, Any]:
    """Deterministic print facts bundled for the reader."""
    page = int(page_native.get("page") or 0)
    folio = _folio(page, natives)
    return {
        "page": page,
        "width": page_native.get("width"),
        "height": page_native.get("height"),
        "folio": {"stack": folio[0], "number": folio[1]} if folio else None,
        "section_head": _section_head_text(page_native),
        "column_grid": column_grid(page_native),
        "continuation": _continuation_markers(page_native),
        "ad_page": _is_ad_page(page_native),
        "lines": line_table(page_native),
    }


def _line_by_id(page_native: dict[str, Any], line_id: str) -> dict[str, Any] | None:
    for line in page_native.get("lines") or []:
        if line.get("id") == line_id:
            return line
    return None


def _x_overlap(a: list[float], b: list[float], pad: float = 12.0) -> bool:
    return a[0] - pad <= b[2] and b[0] - pad <= a[2]


def _is_rubric_line(font: str, size: float) -> bool:
    if any(font.startswith(p) for p in _RUBRIC_FONTS):
        return True
    return font.startswith(_BANNER_FONT) and size <= _RUBRIC_BANNER_MAX


def _canonical_text(raw: str, base: str | None) -> str:
    """Map a printed label to the section vocabulary, else keep it verbatim."""
    key = _norm_rubric(raw)
    if key in _BASE_FROM_PRINT:
        return _BASE_FROM_PRINT[key]
    if key in _RUBRIC_TO_SECTION:
        mapped = _RUBRIC_TO_SECTION[key]
        if " / " in mapped:
            return mapped.split(" / ", 1)[1]
        if mapped != base:
            return mapped
    # A rubric may carry a suffix the paper adds: `CORRECTIONS & AMPLIFICATIONS`.
    for known in sorted(_RUBRIC_TO_SECTION, key=len, reverse=True):
        if len(known) >= 6 and key.startswith(known):
            mapped = _RUBRIC_TO_SECTION[known]
            if " / " in mapped:
                return mapped.split(" / ", 1)[1]
            if mapped != base:
                return mapped
    return raw.strip()


#: Arts reviews name their rubric inside the kicker: `MUSIC REVIEW | MARK RICHARDSON`
#: and `TELEVISION REVIEW | JOHN ANDERSON` on the Arts in Review page.
_REVIEW_KICKER_RE = re.compile(r"^([A-Z][A-Z &'\-]{2,}?)\s+REVIEW\b")


def _detect_rubric(
    page_native: dict[str, Any],
    start_line: dict[str, Any],
    page_base: str | None,
) -> str | None:
    own_text = (start_line.get("text") or "").strip()
    own_key = _norm_rubric(own_text)
    if own_key in _BASE_FROM_PRINT or own_key in _RUBRIC_TO_SECTION:
        return _canonical_text(own_text, page_base)
    # `CORRECTIONS & AMPLIFICATIONS` starts with a known rubric and adds a suffix.
    if any(
        len(k) >= 6 and (own_key.startswith(k) or k.startswith(own_key))
        for k in _RUBRIC_TO_SECTION
    ):
        return _canonical_text(own_text, page_base)
    start_y = float(start_line["bbox"][1])
    bottom = float(start_line["bbox"][3])
    best: tuple[float, str] | None = None
    known_best: tuple[float, str] | None = None
    kicker: tuple[float, str] | None = None
    below: tuple[float, str] | None = None
    for line in page_native.get("lines") or []:
        y = float(line["bbox"][1])
        if y < 40 or (start_y - 2 <= y <= bottom):
            continue
        is_below = y > bottom
        if is_below and y - bottom > 260:
            continue
        if not _x_overlap(line["bbox"], start_line["bbox"]):
            continue
        text = (line.get("text") or "").strip()
        if not text or len(text) > 80:
            continue
        m = _REVIEW_KICKER_RE.match(text)
        if m and (kicker is None or y > kicker[0]):
            kicker = (y, m.group(1).strip().title())
        known = _norm_rubric(text)
        # A rubric equal to the page's own banner is the base, not a sub-column.
        if _canonical_text(text, page_base).strip() == (page_base or "").strip():
            continue
        if known in _RUBRIC_TO_SECTION or known in _BASE_FROM_PRINT or any(
            len(k) >= 6 and known.startswith(k) for k in _RUBRIC_TO_SECTION
        ):
            if is_below:
                if below is None or y < below[0]:
                    below = (y, text)
            elif known_best is None or y > known_best[0]:
                known_best = (y, text)
            continue
        font, size = _dominant_char(line)
        if not _is_rubric_line(font, size) or size > _RUBRIC_MAX_SIZE:
            continue
        # Drop caps share the rubric faces at 40pt+ and are one or two letters.
        if len(text) < 4:
            continue
        if is_below:
            # A kicker such as `ANALYSIS` is sometimes set just under the headline.
            if below is None or y < below[0]:
                below = (y, text)
            continue
        if best is None or y > best[0]:
            best = (y, text)
    if known_best:
        return _canonical_text(known_best[1], page_base)
    if kicker and (best is None or kicker[0] > best[0]):
        return _canonical_text(kicker[1], page_base)
    if best:
        return _canonical_text(best[1], page_base)
    if below:
        return _canonical_text(below[1], page_base)
    return None


def _compose_section(
    page_native: dict[str, Any],
    start_line: dict[str, Any],
    rubric_hint: str | None,
) -> str:
    """The story's raw section string, from the page banner and its own rubric.

    The front page prints no section banner; each story there carries its own
    small italic label instead, so the rubric alone is the base.
    """
    base = _section_head_text(page_native)
    hint = _canonical_text(rubric_hint, base) if (rubric_hint or "").strip() else ""
    rubric = hint or _detect_rubric(page_native, start_line, base)

    if rubric:
        full = _RUBRIC_TO_SECTION.get(_norm_rubric(rubric))
        if full and " / " in full:
            return full
    if rubric and rubric in SECTION_MAP:
        if " / " in rubric:
            return rubric
        if base and base != rubric:
            combo = f"{base} / {rubric}"
            if combo in SECTION_MAP:
                return combo
        return rubric
    if rubric and base:
        combo = f"{base} / {rubric}"
        if combo in SECTION_MAP:
            return combo
    if base:
        return base
    if rubric:
        return rubric
    raise TracerCompilationError(
        f"page {page_native.get('page')}: no section head for line {start_line.get('id')}"
    )


def _folio_index(natives: dict[int, dict[str, Any]]) -> dict[tuple[str, int], int]:
    """(stack, folio) -> physical page, read from each page's printed id.

    This replaces any per-issue page boundary: the reference issue carries
    stacks A/B/S and the second issue A/B/C/D/R, so a hardcoded offset is wrong
    for one of them.
    """
    index: dict[tuple[str, int], int] = {}
    for page in natives:
        pos = _folio(page, natives)
        if pos:
            index[pos] = page
    return index


def _resolve_folio(token: str, index: dict[tuple[str, int], int]) -> int | None:
    parsed = _parse_folio_token(token)
    if not parsed:
        return None
    return index.get(parsed)


def _continuation_evidence(
    page: int,
    page_native: dict[str, Any],
    start_line: dict[str, Any],
    index: dict[tuple[str, int], int],
    natives: dict[int, dict[str, Any]],
) -> tuple[int | None, list[dict[str, Any]]]:
    """The story's continuation page and the printed markers that prove it.

    Both directions are printed: the start page carries `Pleaseturn...`, the
    continuation page carries `Continued...`. The evidence keeps each marker's
    line id and bbox so the link is auditable. A marker naming a folio that is
    not in the issue raises rather than silently dropping the page.
    """
    sb = start_line["bbox"]
    forward: list[tuple[dict[str, Any], int]] = []
    for entry in _continuation_markers(page_native)["forward"]:
        target = _resolve_folio(entry["folio"], index)
        if target is None:
            raise TracerCompilationError(
                f"page {page}: continuation marker names an unreachable folio "
                f"{entry['folio']!r} (line {entry['line'].get('id')})"
            )
        forward.append((entry["line"], target))
    if not forward:
        return None, []

    overlaps = [entry for entry in forward if _x_overlap(sb, entry[0]["bbox"])]
    line, target = max(overlaps or forward, key=lambda entry: entry[0]["bbox"][1])

    evidence = [
        {
            "page": page,
            "line_id": line.get("id"),
            "raw": line.get("text", "").strip(),
            "bbox_points": [round(float(v), 2) for v in line["bbox"]],
        }
    ]
    target_native = natives.get(target)
    if target_native is not None:
        for entry in _continuation_markers(target_native)["backward"]:
            origin = _resolve_folio(entry["folio"], index)
            if origin == page:
                back = entry["line"]
                evidence.append(
                    {
                        "page": target,
                        "line_id": back.get("id"),
                        "raw": back.get("text", "").strip(),
                        "bbox_points": [round(float(v), 2) for v in back["bbox"]],
                    }
                )
                break
    return target, evidence


def _assign_markers(
    items: list[dict[str, Any]],
    markers: list[tuple[dict[str, Any], int]],
) -> dict[str, tuple[int, dict[str, Any]]]:
    """Pair jump markers with the stories they end, one marker per story.

    A marker sits at the end of a story's text, so its column is the story's
    *last* column, not its first — nearest-per-marker therefore misassigns once a
    page carries several jumps. What works is a global one-to-one assignment.

    Not every story continues and not every marker is usable, so an item may stay
    unassigned at a fixed cost; the optimum decides. Verified on the reference
    front page: seven items, six markers, and the optimum reproduces all six
    targets while leaving the single-page digest unassigned.
    """
    import itertools

    if not items or not markers:
        return {}
    # A marker above a story's start cannot belong to it.
    usable = [
        pair
        for pair in markers
        if any(float(pair[0]["bbox"][1]) > float(it["bbox"][1]) for it in items)
    ]
    if not usable:
        return {}

    #: Cost of leaving one story without a marker, in points of horizontal
    #: distance. A story that truly continues sits close to its marker; a
    #: single-page item is far from every one.
    unassigned_cost = 120.0

    def cost(item: dict[str, Any], marker: dict[str, Any]) -> float:
        if float(marker["bbox"][1]) <= float(item["bbox"][1]):
            return 1e6
        return abs(float(marker["bbox"][0]) - float(item["bbox"][0]))

    best_total: float | None = None
    best_pairs: dict[str, tuple[int, dict[str, Any]]] = {}
    size = min(len(items), len(usable))
    for subset in itertools.combinations(range(len(items)), size):
        chosen = [items[i] for i in subset]
        for perm in itertools.permutations(range(len(usable)), size):
            total = (len(items) - size) * unassigned_cost
            pairs: dict[str, tuple[int, dict[str, Any]]] = {}
            for item, marker_index in zip(chosen, perm):
                marker, target = usable[marker_index]
                total += cost(item, marker)
                pairs[str(item.get("start_line_id") or item.get("id"))] = (target, marker)
            if best_total is None or total < best_total:
                best_total, best_pairs = total, pairs
    return best_pairs


#: A rubric whose items are short briefs by editorial convention. `Stock
#: Spotlight` is a recurring WSJ column of one-paragraph company notes; the
#: reader calls them sidebars because they sit beside a longer story, which
#: moves them from Tier 3 to Tier 2. Measured on the reference issue: five of the
#: six tier misclassifications came from exactly this.
_TYPE_FROM_RUBRIC = {
    "stockspotlight": "brief",
}


#: Recurring WSJ columns whose short items form one Composite Column (ADR 0001).
#: Grouping is by the printed rubric, which is also what the reference issue's
#: hand-made table encodes: nine letters, five Spotlight notes, three U.S. Watch
#: briefs, two World Watch briefs, two corrections. Derived here instead of listed
#: by id, so a new issue groups its own items.
COMPOSITE_RUBRICS: dict[str, dict[str, str]] = {
    "letters": {"genre": "letters", "section": "opinion"},
    "stockspotlight": {"genre": "spotlight", "section": "markets"},
    "uswatch": {"genre": "watch", "section": "us"},
    "worldwatch": {"genre": "watch", "section": "world"},
    "corrections": {"genre": "corrections", "section": "opinion"},
}


def derive_composites(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group records into Composite Columns by their printed rubric."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        section = str(record.get("section") or "")
        rubric = section.split(" / ")[-1] if " / " in section else section
        key = _norm_rubric(rubric)
        if key in COMPOSITE_RUBRICS:
            groups.setdefault(key, []).append(record)

    units: list[dict[str, Any]] = []
    for key in sorted(groups):
        members = sorted(groups[key], key=lambda r: (r["start_page"], r["start_line_id"]))
        if len(members) < 2:
            # A lone item is not a column; it routes on its own.
            continue
        spec = COMPOSITE_RUBRICS[key]
        unit_id = f"COMPOSITE-{key.upper()}"
        units.append(
            {
                "unit_id": unit_id,
                "members": [r["id"] for r in members],
                "section": spec["section"],
                "genre": spec["genre"],
                "kicker": f"{members[0]['section']} · {print_page_label(members[0]['start_page'])}",
                "all_pages": sorted({p for r in members for p in r["all_pages"]}),
            }
        )
    return units


def _type_from_section(section: str, judged: str) -> str:
    rubric = section.split(" / ")[-1] if " / " in section else section
    return _TYPE_FROM_RUBRIC.get(_norm_rubric(rubric), judged)


#: A story's text on one page is a run of columns sharing one vertical band. The
#: band ends at the next story start in the same column, or where the printed
#: text stops — measured against the reference issue's hand-drawn regions, a
#: 28pt inter-line gap gives the best agreement (IoU median 0.82, 74 of 83
#: rectangles above 0.5). See the reconciliation note in docs/history.
_REGION_LINE_GAP = 28.0
#: Left edges within this many points are the same printed column; indented first
#: lines sit about 15pt right of the column origin.
_COLUMN_EDGE_GAP = 40.0


def _body_lines(page_native: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for line in page_native.get("lines") or []:
        if not (line.get("chars") or ()):
            continue
        _font, size = _dominant_char(line)
        if size < 15.0:
            out.append(line)
    return out


def _headline_block_bottom(page_native: dict[str, Any], start_line: dict[str, Any]) -> float:
    """Bottom of the whole headline, not just its first line.

    A headline is set over several lines at display size; starting the body scan
    under the first line makes the remaining headline lines look like a gap and
    cuts the story to a single line.
    """
    top = float(start_line["bbox"][1])
    bottom = float(start_line["bbox"][3])
    for line in page_native.get("lines") or ():
        if not (line.get("chars") or ()):
            continue
        y = float(line["bbox"][1])
        if y <= top:
            continue
        _font, size = _dominant_char(line)
        if size < 15.0:
            break
        if y - bottom > 20.0:
            break
        bottom = max(bottom, float(line["bbox"][3]))
    return bottom


def story_regions(
    page_native: dict[str, Any],
    start_line: dict[str, Any],
    marker_line: dict[str, Any] | None,
    other_starts: list[tuple[dict[str, Any], int | None]],
) -> list[dict[str, Any]]:
    """The story's rectangles on its start page: one per column it occupies.

    A story fills its column and spills into the next one. The spill is detected
    from the printed text: when a column's run reaches the end of that column's
    text, the story continues rightwards; when it stops at another story's start,
    it ends. A jump marker, when present, caps the last column.

    Measured against the reference issue's hand-drawn regions this reproduces
    about 39% of rectangles above IoU 0.5 (median 0.38 per story); an
    all-columns-band variant reaches 51% (median 0.44). Neither is exact, and the
    reason is structural: which columns a story occupies is not printed. A photo
    or a headline block can leave a column almost empty while the story still
    owns it. Exact regions need the story's own line set from the reader — see
    the reconciliation note in docs/history.
    """
    grid = column_grid(page_native)
    if not grid:
        return []
    start_column = _column_index(grid, start_line["bbox"][0])
    if start_column is None:
        return []
    marker_column = None
    if marker_line is not None:
        marker_column = _column_index(grid, marker_line["bbox"][0])
    pitch = (grid[1] - grid[0]) if len(grid) > 1 else 120.0
    body = _body_lines(page_native)
    page_bottom = max((float(l["bbox"][3]) for l in body), default=0.0)

    regions: list[dict[str, Any]] = []
    top = _headline_block_bottom(page_native, start_line)
    column = start_column
    while column < len(grid):
        stop = float("inf")
        for other, other_column in other_starts:
            if other_column == column and float(other["bbox"][1]) > top:
                stop = min(stop, float(other["bbox"][1]))
        capped = marker_column == column and marker_line is not None
        if capped:
            stop = min(stop, float(marker_line["bbox"][3]) + 10.0)

        candidates = sorted(
            (
                line
                for line in body
                if _column_index(grid, line["bbox"][0]) == column
                and top <= float(line["bbox"][1]) < stop
            ),
            key=lambda line: float(line["bbox"][1]),
        )
        if not candidates:
            break
        kept = [candidates[0]]
        for line in candidates[1:]:
            if float(line["bbox"][1]) - float(kept[-1]["bbox"][3]) > _REGION_LINE_GAP:
                break
            kept.append(line)

        regions.append(
            {
                "page": int(page_native.get("page") or 0),
                "bbox": [
                    round(grid[column], 2),
                    round(min(float(l["bbox"][1]) for l in kept), 2),
                    round(grid[column] + pitch, 2),
                    round(max(float(l["bbox"][3]) for l in kept), 2),
                ],
                "column_origin": round(grid[column], 2),
            }
        )
        if capped:
            break
        # Continue rightwards only when this column was filled to its end.
        reached_end = float(kept[-1]["bbox"][3]) >= page_bottom - 40.0 or stop == float("inf")
        if not reached_end:
            break
        top = float(grid and 0.0)
        next_column = column + 1
        first = next(
            (
                line
                for line in body
                if _column_index(grid, line["bbox"][0]) == next_column
                and not any(
                    other_column == next_column and float(other["bbox"][1]) <= float(line["bbox"][1])
                    for other, other_column in other_starts
                )
            ),
            None,
        )
        if first is None:
            break
        top = float(first["bbox"][1])
        column = next_column
    return regions


def _line_index(
    natives: dict[int, dict[str, Any]],
) -> dict[str, tuple[int, dict[str, Any], dict[str, Any]]]:
    index: dict[str, tuple[int, dict[str, Any], dict[str, Any]]] = {}
    for page_no, native in natives.items():
        number = int(native.get("page") or page_no)
        for line in native.get("lines") or ():
            if line.get("id"):
                index[str(line["id"])] = (number, native, line)
    return index


def regions_from_lines(
    natives: dict[int, dict[str, Any]],
    line_ids: list[str],
    *,
    line_index: dict[str, tuple[int, dict[str, Any], dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    """Exact rectangles from the reader's line set.

    When the reader answers which lines belong to a story, the rectangle follows
    from the column grid and those lines' own extents — nothing has to be inferred
    from where the printed text happens to stop. This covers every page the lines
    sit on, so continuation pages need no separate band construction.
    """
    index = line_index if line_index is not None else _line_index(natives)

    per_page: dict[int, tuple[dict[str, Any], list[dict[str, Any]]]] = {}
    for line_id in line_ids:
        hit = index.get(str(line_id))
        if hit is None:
            continue
        per_page.setdefault(hit[0], (hit[1], []))[1].append(hit[2])

    regions: list[dict[str, Any]] = []
    for page in sorted(per_page):
        native, page_lines = per_page[page]
        lines = [line for line in page_lines if (line.get("text") or "").strip()]
        if not lines:
            continue
        # The grid comes from the lines inside this story's band, not from the page:
        # one page can carry two column systems (page 12 has a five-column story and
        # a three-column one), and a page-wide grid merges them.
        band_top = min(float(line["bbox"][1]) for line in lines)
        band_bottom = max(float(line["bbox"][3]) for line in lines)
        in_band = {
            "page": page,
            "width": native.get("width"),
            "height": native.get("height"),
            "lines": [
                line
                for line in (native.get("lines") or ())
                if band_top - 2 <= float(line["bbox"][1]) <= band_bottom + 2
            ],
        }
        # A short story's band may hold too few lines for the grid to recover; the
        # page grid is the right answer there, because the band has only one layout.
        columns = column_grid(in_band) or column_grid(native)
        if not columns:
            continue
        by_column: list[list[dict[str, Any]]] = [[] for _ in columns]
        for line in lines:
            x0 = float(line["bbox"][0])
            best = min(range(len(columns)), key=lambda i: abs(x0 - columns[i]))
            # Only lines set at a column edge define that column's box. A justified
            # line split into style runs yields fragments starting mid-measure
            # ("woman added. Shares fell"), and snapping one of those to the next
            # column produces an inverted, empty rectangle.
            if abs(x0 - columns[best]) > _COLUMN_EDGE_GAP / 5:
                continue
            by_column[best].append(line)
        origins = list(columns)
        pitch = (
            min(b - a for a, b in zip(origins, origins[1:]))
            if len(origins) > 1
            else 150.0
        )
        for column in sorted((i for i in range(len(columns)) if by_column[i]), key=lambda i: origins[i]):
            members = by_column[column]
            # The column origin is its own printed edge, not the leftmost member:
            # a caption inset mid-measure joins this column without moving it.
            left = origins[column]
            right = max(float(line["bbox"][2]) for line in members)
            if column < len(columns) - 1:
                # A line spanning several columns is a rule or a caption; letting it
                # set the right edge would swallow the next column.
                right = min(right, left + pitch + 12.0)
            regions.append(
                {
                    "page": page,
                    "bbox": [round(left, 2), round(band_top, 2), round(right, 2), round(band_bottom, 2)],
                    "column_origin": round(origins[column], 2),
                }
            )
    return regions


# --- paragraphs from printed indents (ADR 0004) ------------------------------

#: A paragraph's first line is indented about 10pt from the body edge; a larger
#: offset is a figure wrap or a nested column, not a paragraph start.
_PARAGRAPH_INDENT_PT = (6.0, 20.0)
#: Subheads are set above body size (8.4pt on the reference issue) and below
#: display size.
_SUBHEAD_SIZE_PT = (10.0, 16.0)
#: A single display-size letter is a drop cap, and it starts its paragraph.
_DROP_CAP_MIN_SIZE = 20.0
#: A wrapped column moves its body edge mid-column, so the local edge has to come
#: from the lines themselves rather than from the page grid.
_PARAGRAPH_EDGE_WINDOW = 5


def _column_spans(grid: list[float], width: float | None) -> list[tuple[float, float]]:
    """Printed content span per column.

    The gutter is about 10pt; the last column ends at the page's right margin.
    """
    spans: list[tuple[float, float]] = []
    for i, left in enumerate(grid):
        right = grid[i + 1] - 10.0 if i + 1 < len(grid) else (width or left + 124.0) - 40.0
        spans.append((left, right))
    return spans


def _span_column(x: float, grid: list[float], width: float | None) -> int:
    """The column whose printed content contains ``x``.

    Nearest-origin snaps a word fragment near the measure's right edge into the
    next column — a 114pt measure on a 124pt pitch puts the measure's last 30pt
    closer to the next origin — which turns one justified line into two.
    """
    if not grid:
        return 0
    for i, (left, right) in enumerate(_column_spans(grid, width)):
        if left - 2.0 <= x <= right + 4.0:
            return i
    return min(range(len(grid)), key=lambda i: abs(x - grid[i]))


def _story_page_grids(
    natives: dict[int, dict[str, Any]],
    lines_by_page: dict[int, list[dict[str, Any]]],
) -> dict[int, list[float]]:
    """Column grid per page from the story's own lines, falling back to the page.

    One page can carry two column systems (page 12 has a five-column story and a
    three-column one), and a page-wide grid merges them.
    """
    grids: dict[int, list[float]] = {}
    for page, lines in lines_by_page.items():
        band = {
            "page": page,
            "width": natives[page].get("width"),
            "height": natives[page].get("height"),
            "lines": lines,
        }
        grids[page] = column_grid(band) or column_grid(natives[page])
    return grids


def _printed_lines(
    natives: dict[int, dict[str, Any]],
    grids: dict[int, list[float]],
    lines_by_page: dict[int, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """The story's vector lines merged into printed lines, in reading order.

    A justified line is split into style runs and word fragments; a paragraph is
    made of printed lines, not fragments. Fragments sharing a baseline belong to
    one printed line when they sit in the same printed column.
    """
    by_baseline: dict[tuple[int, float], list[dict[str, Any]]] = {}
    for page, lines in lines_by_page.items():
        for line in lines:
            by_baseline.setdefault((page, round(float(line["bbox"][1]), 1)), []).append(line)

    printed: list[dict[str, Any]] = []
    for (page, _y), lines in by_baseline.items():
        grid = grids.get(page) or []
        width = natives[page].get("width")
        lines.sort(key=lambda line: float(line["bbox"][0]))
        run = [lines[0]]
        for line in lines[1:]:
            if _span_column(float(run[-1]["bbox"][0]), grid, width) != _span_column(
                float(line["bbox"][0]), grid, width
            ):
                printed.append(_printed_line(page, grid, width, run))
                run = [line]
            else:
                run.append(line)
        printed.append(_printed_line(page, grid, width, run))
    printed.sort(key=lambda r: (r["page"], r["column"], r["y"], r["x0"]))
    return printed


def _printed_line(
    page: int, grid: list[float], width: float | None, lines: list[dict[str, Any]]
) -> dict[str, Any]:
    x0 = float(lines[0]["bbox"][0])
    column = _span_column(x0, grid, width)
    return {
        "page": page,
        "column": column,
        "origin": grid[column] if column < len(grid) else x0,
        "x0": x0,
        "x1": max(float(line["bbox"][2]) for line in lines),
        "y": round(float(lines[0]["bbox"][1]), 1),
        "lines": lines,
    }


def _body_edge(printed: list[dict[str, Any]], k: int) -> float:
    """Local unindented edge of the current column run."""
    line = printed[k]
    previous = [
        p["x0"]
        for p in printed[max(0, k - _PARAGRAPH_EDGE_WINDOW):k]
        if p["page"] == line["page"] and p["column"] == line["column"]
    ]
    return min(previous) if previous else float(line["origin"])


def paragraphs_from_lines(
    natives: dict[int, dict[str, Any]],
    line_ids: list[str],
    *,
    line_index: dict[str, tuple[int, dict[str, Any], dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    """Split a story's reader-named lines into paragraphs.

    The boundaries are printed facts: a first-line indent, a subhead's type size,
    or a drop cap (ADR 0004). Each paragraph carries its page, column and bbox, so
    the composer can order paragraphs and anchor figures without the hand-made
    inventory. Returns ``[]`` when the line set binds to nothing.

    A figure wrap and a nested column move the body edge mid-column; measuring the
    indent against the local edge keeps those lines in their paragraph instead of
    splitting them. A paragraph runs longer than the edge window is the limit of
    that local view.
    """
    index = line_index if line_index is not None else _line_index(natives)
    lines_by_page: dict[int, list[dict[str, Any]]] = {}
    for line_id in line_ids:
        hit = index.get(str(line_id))
        if hit is not None:
            lines_by_page.setdefault(hit[0], []).append(hit[2])
    if not lines_by_page:
        return []

    grids = _story_page_grids(natives, lines_by_page)
    printed = _printed_lines(natives, grids, lines_by_page)

    groups: list[list[dict[str, Any]]] = []
    for k, line in enumerate(printed):
        text = "".join(
            (part.get("text") or "").strip() for part in line["lines"]
        ).strip()
        size = _dominant_char(line["lines"][0])[1]
        is_subhead = _SUBHEAD_SIZE_PT[0] <= size <= _SUBHEAD_SIZE_PT[1]
        drop_cap = (
            len(text) == 1 and text.isupper() and size > _DROP_CAP_MIN_SIZE
        )
        starts = k == 0
        if k and not starts:
            previous = printed[k - 1]
            previous_size = _dominant_char(previous["lines"][0])[1]
            previous_subhead = (
                _SUBHEAD_SIZE_PT[0] <= previous_size <= _SUBHEAD_SIZE_PT[1]
            )
            # A subhead is its own block; the paragraph after it starts fresh
            # even when that first line is not indented.
            if is_subhead != previous_subhead:
                starts = True
            elif drop_cap:
                starts = True
            else:
                indent = line["x0"] - _body_edge(printed, k)
                starts = _PARAGRAPH_INDENT_PT[0] <= indent <= _PARAGRAPH_INDENT_PT[1]
        if starts:
            groups.append([])
        groups[-1].append(line)

    paragraphs: list[dict[str, Any]] = []
    for n, group in enumerate(groups, 1):
        size = _dominant_char(group[0]["lines"][0])[1]
        is_subhead = _SUBHEAD_SIZE_PT[0] <= size <= _SUBHEAD_SIZE_PT[1]
        boxes: dict[tuple[int, int], dict[str, Any]] = {}
        native_regions: list[dict[str, Any]] = []
        for line in group:
            left = round(min(float(part["bbox"][0]) for part in line["lines"]), 2)
            top = round(min(float(part["bbox"][1]) for part in line["lines"]), 2)
            right = round(max(float(part["bbox"][2]) for part in line["lines"]), 2)
            bottom = round(max(float(part["bbox"][3]) for part in line["lines"]), 2)
            native_regions.append(
                {
                    "line_id": line["lines"][0].get("id"),
                    "page": line["page"],
                    "bbox_points_top_left": [left, top, right, bottom],
                }
            )
            key = (line["page"], line["column"])
            box = boxes.get(key)
            if box is None:
                boxes[key] = {
                    "page": line["page"],
                    "column_origin": round(float(line["origin"]), 2),
                    "bbox": [left, top, right, bottom],
                }
            else:
                box["bbox"] = [
                    min(box["bbox"][0], left),
                    min(box["bbox"][1], top),
                    max(box["bbox"][2], right),
                    max(box["bbox"][3], bottom),
                ]
        paragraphs.append(
            {
                "id": f"p{n}",
                "type": "subheading" if is_subhead else "paragraph",
                "text": " ".join(
                    (part.get("text") or "").strip()
                    for line in group
                    for part in line["lines"]
                    if (part.get("text") or "").strip()
                ),
                "native_line_ids": [
                    part.get("id") for line in group for part in line["lines"]
                ],
                "native_regions": native_regions,
                "regions": sorted(
                    boxes.values(),
                    key=lambda box: (box["page"], box["bbox"][1], box["bbox"][0]),
                ),
            }
        )
    return paragraphs



TYPE_CONFIDENCE_PRINTED = 1.0
TYPE_CONFIDENCE_JUDGED = 0.9
TYPE_CONFIDENCE_FLAGGED = 0.5
#: A story typed `article` whose printed extent on its pages is under this many
#: points is contradicting its own type; the reference issue has three.
_TINY_ARTICLE_POINTS = 120.0


def _type_evidence(
    section: str,
    kind: str,
    regions: list[dict[str, Any]],
    all_pages: list[int],
) -> tuple[float, list[str]]:
    """Judge agreement between an item's type and what the page prints.

    The Reading Pass answers `kind`; this does not re-ask it. It checks the answer
    against printed structure, so a host reviews the items whose type contradicts
    the page rather than the whole issue.
    """
    rubric = section.split(" / ")[-1] if " / " in section else section
    printed = _TYPE_FROM_RUBRIC.get(_norm_rubric(rubric))
    extent = sum(float(r["bbox"][3]) - float(r["bbox"][1]) for r in regions)
    reasons: list[str] = []
    if printed is not None and printed != kind:
        reasons.append("rubric-disagrees")
    if kind == "brief" and len(all_pages) > 1:
        reasons.append("brief-but-multi-page")
    if kind == "article" and extent < _TINY_ARTICLE_POINTS:
        reasons.append("article-but-tiny")
    if reasons:
        return TYPE_CONFIDENCE_FLAGGED, reasons
    if printed is not None:
        return TYPE_CONFIDENCE_PRINTED, []
    return TYPE_CONFIDENCE_JUDGED, []


def default_mineru_dir(pilot_root: str | Path) -> Path:
    """Where the MinerU middle-json pages sit beside an issue's other inputs."""
    return Path(pilot_root) / "evidence"


def load_mineru_blocks(root: str | Path) -> dict[int, list[tuple[int, str, list[float]]]]:
    """Per page, MinerU's blocks in reading order: (index, type, bbox in points).

    Optional input. The Reading Pass may answer `blocks` instead of `lines` when
    these exist, which asks it for paragraphs rather than for every line.
    """
    out: dict[int, list[tuple[int, str, list[float]]]] = {}
    for path in sorted(Path(root).glob("p*-mineru.json")):
        match = re.search(r"(\d+)", path.stem)
        if not match:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        layout = (data.get("extensions") or {}).get("docvortex_layout") or {}
        size = (layout.get("pages") or [{}])[0]
        width = float(size.get("width_pt") or 0.0)
        height = float(size.get("height_pt") or 0.0)
        if not width or not height:
            continue
        blocks = []
        for block in (data.get("pages") or [{}])[0].get("blocks") or ():
            bbox = block.get("bbox") or []
            if len(bbox) != 4:
                continue
            blocks.append(
                (
                    int(block.get("index") or 0),
                    str(block.get("type") or ""),
                    [bbox[0] * width, bbox[1] * height, bbox[2] * width, bbox[3] * height],
                )
            )
        out[int(match.group(1))] = sorted(blocks)
    return out


def lines_from_blocks(
    page_native: dict[str, Any],
    blocks: list[tuple[int, str, list[float]]],
    indices: list[int],
) -> list[str]:
    """The native lines inside the named blocks, by containment.

    Measured on the reference issue: block boxes contain 97% of a page's text
    lines, so this is how a Reading Pass answer in blocks becomes a line set.
    """
    wanted = [bbox for index, _type, bbox in blocks if index in set(indices)]
    if not wanted:
        return []
    out: list[str] = []
    for line in page_native.get("lines") or ():
        if not (line.get("text") or "").strip():
            continue
        cx = (float(line["bbox"][0]) + float(line["bbox"][2])) / 2
        cy = (float(line["bbox"][1]) + float(line["bbox"][3])) / 2
        for x0, y0, x1, y1 in wanted:
            if x0 - 1 <= cx <= x1 + 1 and y0 - 2 <= cy <= y1 + 2:
                out.append(str(line.get("id")))
                break
    return out


def continuation_regions(page_native: dict[str, Any], headline: dict[str, Any],
                         next_top: float | None) -> list[dict[str, Any]]:
    """The story's rectangles on a page it continues onto.

    A jump page stacks the continued stories in horizontal bands, each running
    across every column of the page; the band runs from the reprinted headline to
    the next reprinted headline. Verified on page 4: two bands, 806–1182 and
    1199–1505, each spanning all six columns.
    """
    grid = column_grid(page_native)
    if not grid:
        return []
    pitch = (grid[1] - grid[0]) if len(grid) > 1 else 120.0
    # The band includes the reprinted headline: the golden regions start at its top.
    top = float(headline["bbox"][1])
    bottom = next_top if next_top is not None else float(page_native.get("height") or 0.0)
    if bottom <= top:
        return []
    return [
        {
            "page": int(page_native.get("page") or 0),
            "bbox": [round(x, 2), round(top, 2), round(x + pitch, 2), round(bottom, 2)],
            "column_origin": round(x, 2),
        }
        for x in grid
    ]


def _column_index(grid: list[float], x: float) -> int | None:
    if not grid:
        return None
    index = min(range(len(grid)), key=lambda i: abs(grid[i] - x))
    return index if abs(grid[index] - x) < 70 else None


def _jump_headline_blocks(page_native: dict[str, Any]) -> list[dict[str, Any]]:
    """Jump-page headlines merged into blocks.

    A reprinted headline is set as several lines (`Guilfoyle` / `Resigns as` /
    `Ambassador`), each carrying the italic display face, so they must be joined
    before they can bound a band.
    """
    lines = sorted(
        (
            line
            for line in page_native.get("lines") or ()
            if (line.get("chars") or ()) and _is_jump_headline(page_native, line)
        ),
        key=lambda line: (float(line["bbox"][1]), float(line["bbox"][0])),
    )
    blocks: list[list[dict[str, Any]]] = []
    for line in lines:
        if blocks and float(line["bbox"][1]) - float(blocks[-1][-1]["bbox"][3]) < 8.0:
            blocks[-1].append(line)
        else:
            blocks.append([line])
    return [
        {
            "text": " ".join(l["text"].strip() for l in block),
            "bbox": [
                min(float(l["bbox"][0]) for l in block),
                min(float(l["bbox"][1]) for l in block),
                max(float(l["bbox"][2]) for l in block),
                max(float(l["bbox"][3]) for l in block),
            ],
        }
        for block in blocks
    ]


def _answer_lines(
    page_native: dict[str, Any],
    item: dict[str, Any],
    mineru_pages: dict[int, list[tuple[int, str, list[float]]]] | None,
) -> list[str]:
    """The lines a Reading Pass answer names, whether it answered lines or blocks."""
    named = [str(x).strip() for x in (item.get("lines") or ()) if str(x).strip()]
    if named:
        return named
    blocks = [int(x) for x in (item.get("blocks") or ())]
    if blocks and mineru_pages:
        page = int(page_native.get("page") or 0)
        return lines_from_blocks(page_native, mineru_pages.get(page) or [], blocks)
    return []


def _attach_continuation_regions(records: list[dict[str, Any]],
                                 natives: dict[int, dict[str, Any]],
                                 skip: set[str] | None = None) -> None:
    """Give each continued story its rectangles on the page it continues onto.

    Bands are paired with stories in start order. That holds wherever a jump page
    carries one continuation, and on page 4 where it carries two in the same order
    as the front page. Where a jump page reorders them (page 10) the pairing needs
    a signal the paper does not print: the reprinted headline is a rewrite, so
    matching it to the original would be the headline-similarity join that
    `delivery-report.json` forbids.
    """
    by_target: dict[int, list[tuple[float, dict[str, Any]]]] = {}
    for record in records:
        if record["id"] in (skip or set()):
            continue
        if record.get("regions_source") == "reader_lines":
            continue
        for page in record["all_pages"][1:]:
            forward = next(
                (e for e in record["continuation_evidence"] if e["page"] != page), None
            )
            by_target.setdefault(page, []).append(
                (float(forward["bbox_points"][1]) if forward else 0.0, record)
            )
    for page, entries in by_target.items():
        native = natives.get(page)
        if native is None:
            continue
        blocks = _jump_headline_blocks(native)
        if not blocks:
            continue
        for index, (_y, record) in enumerate(sorted(entries, key=lambda e: e[0])):
            if index >= len(blocks):
                break
            nxt = blocks[index + 1]["bbox"][1] if index + 1 < len(blocks) else None
            record["regions"].extend(continuation_regions(native, blocks[index], nxt))
        for record in [r for _y, r in entries]:
            record["regions"].sort(key=lambda r: (r["page"], r["bbox"][1], r["bbox"][0]))


def _lead_position(page_native: dict[str, Any], start_line: dict[str, Any]) -> bool:
    """Whether a story occupies the paper's lead position on its page.

    A section front leads with the story in the leftmost column of the top half.
    Measured on the reference issue: on the business front this selects exactly
    the two flagships out of six multi-page stories, and agrees with the
    body-length test on all eight. Unlike body length it needs no reconstructed
    paragraphs, so it survives a derived inventory.
    """
    grid = column_grid(page_native)
    if not grid:
        return False
    column = min(range(len(grid)), key=lambda i: abs(grid[i] - float(start_line["bbox"][0])))
    if abs(grid[column] - float(start_line["bbox"][0])) > 70 or column != 0:
        return False
    height = float(page_native.get("height") or 0.0)
    return height > 0 and float(start_line["bbox"][1]) < height * 0.55


def _stable_topic_slug(first_line: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", first_line or "")
    if not words:
        return "ITEM"
    slug = "-".join(w.upper() for w in words[:4])
    return slug[:40] or "ITEM"


def _make_id(
    start_page: int,
    first_line: str,
    kind: str,
    used: set[str],
) -> str:
    folio = print_page_label(start_page)
    topic = _stable_topic_slug(first_line)
    prefix = "CASE" if folio in {"A11", "B1"} and kind == "brief" else "PILOT"
    base = f"{prefix}-{folio}-{topic}"
    if base not in used:
        used.add(base)
        return base
    for i in range(2, 50):
        cand = f"{base}-{i}"
        if cand not in used:
            used.add(cand)
            return cand
    raise TracerCompilationError(f"could not allocate stable id for {first_line!r}")


def _is_jump_headline(page_native: dict[str, Any], start_line: dict[str, Any]) -> bool:
    """Whether a line is a jump-page continuation headline.

    Printed fact, measured on the reference issue: WSJ sets a story's reprinted
    headline on its continuation page in a large *italic* display face, while a
    story that starts on that page is set in bold. Page 4 carries two
    `ContinuedfromPageOne` markers and exactly two large italic banner headlines
    (`Guilfoyle Resigns as Ambassador`, `Condo Borrows From Buyers`), while its
    one genuine start (`Paxton, on Dubai Trip,`) is bold. The italic-block count
    equals the marker count on six of the seven pages that have markers.

    Requires both signals to agree — an italic display headline *and* a backward
    continuation marker on the page — so an italic headline on a page that
    continues nothing is still treated as a start.
    """
    if not _continuation_markers(page_native)["backward"]:
        return False
    font, size = _dominant_char(start_line)
    if size < 20.0:
        return False
    return "EscrowBanner" in font and "-It" in font


#: A standalone photo caption carries a printed all-caps label (`STANDING TALL`).
#: A caption without one belongs to the story beside it and is not its own item.
_CAPTION_LABEL_RE = re.compile(r"^[A-Z][A-Z0-9'’\- ]{2,}:")


def _is_standalone_caption(first_line: str) -> bool:
    text = (first_line or "").strip()
    if _CAPTION_LABEL_RE.match(text):
        return True
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 4:
        return False
    return sum(1 for c in letters if c.isupper()) / len(letters) >= 0.8


def assemble(
    reader_items_by_page: dict[int, list[dict[str, Any]]],
    natives: dict[int, dict[str, Any]],
    mineru_pages: dict[int, list[tuple[int, str, list[float]]]] | None = None,
) -> list[dict[str, Any]]:
    """Bind reader items to vector lines and emit map records.

    The reader enumerates what it sees on the page. Printed facts then decide
    whether an enumerated item is a *new* reading item, so the reader is never
    asked to know a newspaper convention it cannot see from one page:

    - a jump-page continuation headline is not a new story (`_is_jump_headline`);
    - a photo caption only stands alone with a printed label (`_is_standalone_caption`);
    - an image-only page is not editorial (`_is_ad_page`);
    - a jump marker belongs to exactly one story (`_assign_markers`).
    """
    records: list[dict[str, Any]] = []
    continuations: dict[str, list[str]] = {}
    line_ids_by_record: dict[str, list[str]] = {}
    used_ids: set[str] = set()
    folio_index = _folio_index(natives)
    line_index = _line_index(natives)

    for page in sorted(reader_items_by_page):
        page_native = natives.get(page)
        if page_native is None:
            raise TracerCompilationError(f"missing native page {page}")
        if _is_ad_page(page_native):
            if reader_items_by_page[page]:
                raise TracerCompilationError(f"ad page {page} has reader items")
            continue

        # Pass 1: validate, then drop what a printed rule says is not an item.
        kept: list[tuple[dict[str, Any], dict[str, Any], str, str]] = []
        for item in reader_items_by_page[page]:
            kind = str(item.get("kind") or "").strip()
            if kind not in READER_KINDS:
                raise TracerCompilationError(f"page {page}: invalid reader kind {kind!r}")
            line_id = str(item.get("start_line") or "").strip()
            start_line = _line_by_id(page_native, line_id)
            if start_line is None:
                raise TracerCompilationError(f"page {page}: unbindable start_line {line_id!r}")
            first_line = str(item.get("first_line") or start_line.get("text") or "").strip()
            if not first_line:
                raise TracerCompilationError(f"page {page}: empty first_line for {line_id}")
            if _is_jump_headline(page_native, start_line):
                # A reprinted headline may say which story it continues. The pass
                # can answer that because the candidate stories are printed in the
                # start page's jump markers, not because it guessed from the text.
                origin = str(item.get("continues") or "").strip()
                if origin:
                    continuations.setdefault(origin, []).extend(
                        _answer_lines(page_native, item, mineru_pages)
                    )
                continue
            if kind == "photo_caption" and not _is_standalone_caption(first_line):
                continue
            kept.append((item, start_line, first_line, kind))

        # Jump markers on this page, resolved through the issue's folio index.
        markers: list[tuple[dict[str, Any], int]] = []
        for entry in _continuation_markers(page_native)["forward"]:
            target = _resolve_folio(entry["folio"], folio_index)
            if target is None:
                raise TracerCompilationError(
                    f"page {page}: continuation marker names an unreachable folio "
                    f"{entry['folio']!r} (line {entry['line'].get('id')})"
                )
            markers.append((entry["line"], target))
        assignment = _assign_markers(
            [
                {"id": start_line.get("id"), "start_line_id": start_line.get("id"), "bbox": start_line["bbox"]}
                for _item, start_line, _first, _kind in kept
            ],
            markers,
        )

        # Pass 2: emit records. The column grid and each item's column are needed
        # by every item on the page, so they are computed once here.
        page_grid = column_grid(page_native)
        page_starts = [
            (line, _column_index(page_grid, float(line["bbox"][0])))
            for _item, line, _first, _kind in kept
        ]
        for item, start_line, first_line, kind in kept:
            base = _section_head_text(page_native)
            supplied = str(item.get("section") or "").strip()
            if supplied:
                # The reader reads the page, including split rubric heads and
                # running section changes the derivation cannot resolve. Its
                # answer wins; the derivation below is the fallback.
                canonical_section(supplied)
                section = supplied
                rubric = ""
            else:
                rubric = _detect_rubric(page_native, start_line, base)
                section = ""
            try:
                if not section:
                    section = _compose_section(page_native, start_line, rubric)
            except TracerCompilationError:
                # The front page prints no section banner, and one story there can
                # share a continuation page with a story from another section, so
                # the section is not derivable from print. The reader supplies it —
                # the FOUNDATION 12 carve-out, same as `type`.
                judged = str(item.get("section") or "").strip()
                if not judged:
                    raise
                section = judged
            canonical_section(section)

            target, marker = assignment.get(str(start_line.get("id")), (None, None))
            evidence: list[dict[str, Any]] = []
            if marker is not None:
                evidence.append(
                    {
                        "page": page,
                        "line_id": marker.get("id"),
                        "raw": (marker.get("text") or "").strip(),
                        "bbox_points": [round(float(v), 2) for v in marker["bbox"]],
                    }
                )
                target_native = natives.get(target)
                if target_native is not None:
                    for entry in _continuation_markers(target_native)["backward"]:
                        if _resolve_folio(entry["folio"], folio_index) == page:
                            back = entry["line"]
                            evidence.append(
                                {
                                    "page": target,
                                    "line_id": back.get("id"),
                                    "raw": (back.get("text") or "").strip(),
                                    "bbox_points": [round(float(v), 2) for v in back["bbox"]],
                                }
                            )
                            break
            all_pages = sorted({page, *([target] if target else [])})

            kind = _type_from_section(section, kind)
            rec_id = _make_id(page, first_line, kind, used_ids)
            reader_lines = _answer_lines(page_native, item, mineru_pages)
            from_blocks = bool(reader_lines) and not any(
                str(x).strip() for x in (item.get("lines") or ())
            )
            if reader_lines:
                regions = regions_from_lines(natives, reader_lines, line_index=line_index)
                line_ids_by_record[rec_id] = list(dict.fromkeys(reader_lines))
                source = "reading_pass_blocks" if from_blocks else "reading_pass"
            else:
                regions = story_regions(
                    page_native,
                    start_line,
                    marker,
                    [entry for entry in page_starts if entry[0] is not start_line],
                )
                source = "geometry"
            confidence, review = _type_evidence(section, kind, regions, all_pages)
            records.append(
                {
                    "id": rec_id,
                    "original_title": first_line,
                    "start_page": page,
                    "section": section,
                    "type": kind,
                    "type_confidence": confidence,
                    "needs_review": review,
                    "all_pages": all_pages,
                    "lead_position": _lead_position(page_native, start_line),
                    "regions": regions,
                    "regions_source": source,
                    "continuation_evidence": evidence,
                    "start_line_id": start_line.get("id"),
                }
            )

    for record in records:
        named = continuations.get(str(record["start_line_id"]))
        if not named:
            continue
        record["regions"] = sorted(
            record["regions"]
            + regions_from_lines(natives, named, line_index=line_index),
            key=lambda r: (r["page"], r["bbox"][1], r["bbox"][0]),
        )
        line_ids_by_record[record["id"]] = list(
            dict.fromkeys([*line_ids_by_record.get(record["id"], []), *named])
        )
        record["regions_source"] = "reading_pass"
    _attach_continuation_regions(records, natives, skip={r["id"] for r in records if r["regions_source"] != "geometry" and len({g["page"] for g in r["regions"]}) >= len(r["all_pages"])})
    for record in records:
        line_ids = line_ids_by_record.get(record["id"])
        if line_ids:
            record["paragraphs"] = paragraphs_from_lines(
                natives, line_ids, line_index=line_index
            )
    return records


def load_reader_cache(path: str | Path) -> dict[int, list[dict[str, Any]]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    pages = data.get("pages") or {}
    out: dict[int, list[dict[str, Any]]] = {}
    for key, items in pages.items():
        out[int(key)] = list(items)
    return out


def default_reader_cache_path(pilot_root: str | Path) -> Path:
    return Path(pilot_root) / "evidence" / "reader-items.json"


def derive_article_map(
    natives: dict[int, dict[str, Any]],
    reader_cache: str | Path | None = None,
    *,
    pilot_root: str | Path | None = None,
    mineru_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Public seam: vector pages + cached reading-pass items -> ownership records.

    ``mineru_dir`` lets a Reading Pass answer in blocks instead of lines; the
    blocks are mapped back onto native lines by containment. It is optional
    input, and its absence changes nothing but which unit the pass is asked for.

    ``regions`` are a draft record (ADR 0004), never a compile input, so the
    deriver does not gate on how exact they are.
    """
    if reader_cache is None:
        if pilot_root is None:
            raise TracerCompilationError("reader cache path required")
        reader_cache = default_reader_cache_path(pilot_root)
    if mineru_dir is None and pilot_root is not None:
        candidate = default_mineru_dir(pilot_root)
        mineru_dir = candidate if any(candidate.glob("p*-mineru.json")) else None
    if not Path(reader_cache).exists():
        # A missing pass is a missing input, not an empty issue: deriving from
        # nothing would produce a zero-item map that looks like a real answer.
        raise TracerCompilationError(f"no Reading Pass cache at {reader_cache}")
    items = load_reader_cache(reader_cache)
    mineru_pages = load_mineru_blocks(mineru_dir) if mineru_dir else {}
    return assemble(items, natives, mineru_pages)


def load_natives_from_pilot(pilot_root: str | Path) -> dict[int, dict[str, Any]]:
    root = Path(pilot_root)
    out: dict[int, dict[str, Any]] = {}
    for path in sorted((root / "evidence").glob("p*-native.json")):
        native = json.loads(path.read_text(encoding="utf-8"))
        out[int(native["page"])] = native
    return out


def export_line_tables(natives: dict[int, dict[str, Any]], dest: str | Path) -> Path:
    """Write all content-page line tables for reader orchestration."""
    payload: dict[str, Any] = {"pages": {}}
    for page, native in sorted(natives.items()):
        if _is_ad_page(native):
            continue
        payload["pages"][str(page)] = {
            "print_facts": print_facts(native, natives),
        }
    path = Path(dest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def match_key(record: dict[str, Any]) -> tuple[int, str]:
    title = record.get("original_title") or record.get("first_line") or ""
    return int(record["start_page"]), _norm_title(title)


def stable_run_fingerprint(records: list[dict[str, Any]]) -> str:
    rows = sorted((r["id"], r["start_page"], r["section"], match_key(r)[1]) for r in records)
    return hashlib.sha256(json.dumps(rows).encode("utf-8")).hexdigest()
