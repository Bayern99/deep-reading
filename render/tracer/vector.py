"""Primary PDF vector signals: Dow Jones `Retina*` line taxonomy and union chart crops.

Reads the primary vector character stream (`pXX-native.json`) and extracts the
printed-chart text layers:

- ``RetinaMedium``      — chart titles
- ``RetinaBook``/``RetinaLight`` — series labels
- ``RetinaNarrowLight`` — axis ticks
- ``RetinaMPNarrowLt``  — source lines

The union cropper repairs normalized inventory bboxes that chopped chart
headers/sources: it scans the chart's horizontal column span for adjacent
``Retina*`` lines above and below, computes the union bounding box with clean
padding, and crops the region directly from the original print PDF at high
DPI, encoded once as reading-grade WebP.

`fitz` (PyMuPDF) and `PIL` are imported lazily so the module stays importable
without them.
"""
from __future__ import annotations

import html
import io
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

RETINA_TITLE_FONT = "RetinaMedium"
RETINA_SOURCE_FONT = "RetinaMPNarrowLt"
RETINA_FONTS = ("RetinaMedium", "RetinaBook", "RetinaLight", "RetinaNarrowLight", "RetinaMPNarrowLt")

# Vertical gap tolerance (PDF points) when walking adjacent Retina lines.
_GAP_TOL_PT = 16.0
# Horizontal padding when testing line/column overlap (PDF points).
_X_PAD_PT = 6.0
# Clean padding around the union bbox (PDF points).
_UNION_PAD_PT = 4.0
# Render DPI for reading-grade chart crops.
CROP_DPI = 220
# Horizontal column lock: the union bbox never extends beyond the chart's own
# column plus this pad, so a 1-column chart can never balloon into a
# multi-column crop (Reviewer-G: p10-b59/63/68, p20-b72).
_LOCK_PAD_PT = 10.0
# A Retina line only joins the union when substantially contained in the
# chart column widened by this pad (excludes multi-column photo captions).
_CONTAIN_PAD_PT = 15.0
# Multi-column source lines keep only this slice of the chart's column.
_SRC_CLAMP_PT = 6.0
# Body prose families that must never be crossed or cropped into a chart.
_BODY_FONTS = ("Exchange", "DJ5Exchange", "Escrow", "Dispatch", "Archer", "Steed", "Bell")


def line_font(line: dict[str, Any]) -> str:
    chars = line.get("chars") or []
    return chars[0].get("font", "") if chars else ""


def is_retina(line: dict[str, Any]) -> bool:
    return any(line_font(line).startswith(f) for f in RETINA_FONTS)


def load_native(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _x_overlap(a0: float, a1: float, b0: float, b1: float, pad: float = 0.0) -> bool:
    return a0 - pad <= b1 and b0 - pad <= a1


@dataclass
class ChartVector:
    """Structured `Retina*` strings recovered for one printed chart."""

    chart_id: str
    page: int
    page_width: float
    page_height: float
    # Normalized (top-left origin) union bbox of chart + adjacent Retina lines.
    union_bbox_norm: list[float]
    title_en: str = ""
    series_labels_en: list[str] = field(default_factory=list)
    axis_ticks_en: list[str] = field(default_factory=list)
    source_en: str = ""
    # Every Retina line captured in the union, for grounding/verification.
    retina_lines: list[str] = field(default_factory=list)

    @property
    def union_bbox_points(self) -> list[float]:
        W, H = self.page_width, self.page_height
        n = self.union_bbox_norm
        return [n[0] * W, n[1] * H, n[2] * W, n[3] * H]

    def grounding_text(self) -> str:
        parts = [self.title_en, self.source_en, *self.series_labels_en, *self.axis_ticks_en]
        return "\n".join(p for p in parts if p)


def _line_in_bbox(l: dict[str, Any], bb: list[float], pad: float = 1.0) -> bool:
    return (bb[0] - pad <= l["bbox"][0] and l["bbox"][2] <= bb[2] + pad
            and bb[1] - pad <= l["bbox"][1] and l["bbox"][3] <= bb[3] + pad)


def union_chart_bbox(
    native: dict[str, Any],
    chart_norm: list[float],
    sibling_bboxes: list[list[float]] | None = None,
) -> tuple[list[float], list[dict[str, Any]]]:
    """Union of the chart bbox with adjacent `Retina*` title/source lines,
    locked to the chart's own column.

    Rules (Reviewer-G, Ticket 2 round 1):

    - **Column lock** — the union never extends horizontally beyond
      ``[orig_x0 - 10pt, orig_x1 + 10pt]``; only lines substantially
      contained in ``[orig_x0 - 15pt, orig_x1 + 15pt]`` join.  A shared
      multi-column ``RetinaMPNarrowLt`` source line is clamped to the
      chart's own column slice.
    - **Sibling barrier** — the vertical walk stops at any other media
      item's bbox on the page and never absorbs a sibling's title (a line
      sitting directly above a sibling, centered in its span).
    - **Prose barrier** — the walk never crosses an ``ExchangeBook`` /
      ``DJ5Exchange*`` body line, so prose can never enter the crop.
    """
    W, H = float(native["width"]), float(native["height"])
    cx0, cy0, cx1, cy1 = [float(v) for v in chart_norm]
    bx0, by0, bx1, by1 = cx0 * W, cy0 * H, cx1 * W, cy1 * H
    lock = (bx0 - _LOCK_PAD_PT, bx1 + _LOCK_PAD_PT)
    contain = (bx0 - _CONTAIN_PAD_PT, bx1 + _CONTAIN_PAD_PT)
    src_clamp = (bx0 - _SRC_CLAMP_PT, bx1 + _SRC_CLAMP_PT)
    siblings = list(sibling_bboxes or [])
    members: list[dict[str, Any]] = []
    clamps: dict[int, tuple[float, float]] = {}  # id(line) -> x clamp for source lines

    retina = [l for l in native["lines"] if is_retina(l) and l.get("chars")]

    def blocked(l: dict[str, Any]) -> bool:
        """True when the walk must stop at this line."""
        if line_font(l).startswith(_BODY_FONTS):
            return True
        if any(_line_in_bbox(l, s) for s in siblings):
            return True
        # A line sitting directly above a sibling chart is the sibling's title.
        cx = (l["bbox"][0] + l["bbox"][2]) / 2
        for s in siblings:
            if s[1] - _GAP_TOL_PT <= l["bbox"][3] <= s[1] + 1.0 and s[0] <= cx <= s[2]:
                return True
        return False

    def include(l: dict[str, Any]) -> bool:
        """True when the line may join the union (clamping multi-column sources)."""
        if contain[0] <= l["bbox"][0] and l["bbox"][2] <= contain[1]:
            return True
        if line_font(l).startswith(RETINA_SOURCE_FONT):
            clamps[id(l)] = src_clamp  # contribute only this chart's column slice
            return True
        return False

    def _inside_own(l: dict[str, Any]) -> bool:
        return (bx0 <= l["bbox"][0] and l["bbox"][2] <= bx1
                and by0 <= l["bbox"][1] and l["bbox"][3] <= by1)

    # Above: contiguous block, nearest-first, x-center inside the chart span.
    # Lines inside the chart's own bbox are read by the inside scan, not the
    # walk, so they never consume the adjacency gap budget.
    above = [
        l for l in retina
        if not _inside_own(l)
        and l["bbox"][3] <= by0 + _GAP_TOL_PT and bx0 <= (l["bbox"][0] + l["bbox"][2]) / 2 <= bx1
    ]
    above.sort(key=lambda l: -l["bbox"][3])
    anchor = by0
    for l in above:
        if anchor - l["bbox"][3] > _GAP_TOL_PT:
            break
        if blocked(l):
            break
        if include(l):
            members.append(l)
            anchor = l["bbox"][1]
    # Below: contiguous Retina lines (the RetinaMPNarrowLt source line).
    below = [
        l for l in retina
        if not _inside_own(l)
        and l["bbox"][1] >= by1 - _GAP_TOL_PT and _x_overlap(l["bbox"][0], l["bbox"][2], bx0, bx1, _X_PAD_PT)
    ]
    below.sort(key=lambda l: l["bbox"][1])
    anchor = by1
    for l in below:
        if l["bbox"][1] - anchor > _GAP_TOL_PT:
            break
        if blocked(l):
            break
        if include(l):
            members.append(l)
            anchor = l["bbox"][3]

    xs0: list[float] = []
    xs1: list[float] = []
    for l in members:
        clamp = clamps.get(id(l))
        if clamp:
            xs0.append(max(l["bbox"][0], clamp[0]))
            xs1.append(min(l["bbox"][2], clamp[1]))
        else:
            xs0.append(l["bbox"][0])
            xs1.append(l["bbox"][2])
    ux0 = min([bx0] + xs0) - _UNION_PAD_PT
    uy0 = min([by0] + [l["bbox"][1] for l in members]) - _UNION_PAD_PT
    ux1 = max([bx1] + xs1) + _UNION_PAD_PT
    uy1 = max([by1] + [l["bbox"][3] for l in members]) + _UNION_PAD_PT
    # Hard column lock: never crop outside the chart's own column.
    ux0 = max(0.0, ux0, lock[0])
    ux1 = min(W, ux1, lock[1])
    return [ux0, max(0.0, uy0), ux1, min(H, uy1)], members


def media_sibling_bboxes(
    media: list[dict[str, Any]],
    page: int,
    self_id: str,
    page_width: float,
    page_height: float,
) -> list[list[float]]:
    """Same-page sibling media bboxes in PDF points (union-walk barriers)."""
    out = []
    for m in media:
        if m.get("id") == self_id or int(m.get("page", -1)) != page:
            continue
        box = m.get("bbox_normalized_top_left")
        if not box:
            continue
        x0, y0, x1, y1 = [float(v) for v in box]
        out.append([x0 * page_width, y0 * page_height, x1 * page_width, y1 * page_height])
    return out


def extract_chart_vectors(
    native: dict[str, Any],
    chart_id: str,
    page: int,
    chart_norm: list[float],
    sibling_bboxes: list[list[float]] | None = None,
) -> ChartVector:
    """Recover title / series labels / axis ticks / source for one chart.

    The union bbox (used for cropping) covers the chart plus adjacent
    title/source lines, locked to the chart's own column; the structured
    strings also read every ``Retina*`` line inside the chart region itself
    (series labels, axis ticks).  ``sibling_bboxes`` (points, same page)
    fence the vertical walk so one chart never absorbs a sibling's title or
    a multi-column caption.
    """
    W, H = float(native["width"]), float(native["height"])
    union_pt, members = union_chart_bbox(native, chart_norm, sibling_bboxes)
    cx0, cy0, cx1, cy1 = [float(v) for v in chart_norm]
    bx0, by0, bx1, by1 = cx0 * W, cy0 * H, cx1 * W, cy1 * H

    cv = ChartVector(
        chart_id=chart_id,
        page=page,
        page_width=W,
        page_height=H,
        union_bbox_norm=[union_pt[0] / W, union_pt[1] / H, union_pt[2] / W, union_pt[3] / H],
    )
    member_ids = {id(l) for l in members}
    inside = [
        l for l in native["lines"]
        if id(l) not in member_ids and is_retina(l) and l.get("chars")
        and l["bbox"][3] >= by0 - 1.0 and l["bbox"][1] <= by1 + 1.0
        and _x_overlap(l["bbox"][0], l["bbox"][2], bx0, bx1, _X_PAD_PT)
    ]
    member_set = list(members)
    member_set.sort(key=lambda l: (l["bbox"][1], l["bbox"][0]))
    inside.sort(key=lambda l: (l["bbox"][1], l["bbox"][0]))

    series_raw: list[list] = []  # [x0_pt, text, last_y0_pt]
    for zone, lines in (("adjacent", member_set), ("inside", inside)):
        for l in lines:
            font = line_font(l)
            text = re.sub(r"\s+", " ", l.get("text", "")).strip()
            if not text:
                continue
            if zone == "adjacent" or font.startswith(RETINA_TITLE_FONT):
                cv.retina_lines.append(text)
            y0, y1 = l["bbox"][1], l["bbox"][3]
            if font.startswith(RETINA_TITLE_FONT):
                cv.title_en = (cv.title_en + " " + text).strip()
            elif font.startswith(RETINA_SOURCE_FONT) and y0 >= by1 - _GAP_TOL_PT:
                cv.source_en = (cv.source_en + " " + text).strip()
            elif y1 <= by0 + _GAP_TOL_PT:
                cv.axis_ticks_en.append(text)  # top-of-chart axis header, e.g. "$20billion"
            elif font.startswith("RetinaBook"):
                if series_raw and abs(series_raw[-1][0] - l["bbox"][0]) <= 1.5 and y0 - series_raw[-1][2] <= 12.0:
                    series_raw[-1][1] += " " + text
                    series_raw[-1][2] = y0
                else:
                    series_raw.append([l["bbox"][0], text, y0])
            else:
                cv.axis_ticks_en.append(text)
    cv.series_labels_en = [m[1] for m in series_raw]
    return cv


def crop_pdf_region(pdf_path: str | Path, page: int, bbox_points: list[float], dpi: int = CROP_DPI) -> bytes:
    """Crop a PDF region (points, top-left origin) and return PPM raster bytes.

    PyMuPDF's user-space coordinates are already top-left origin (y downward),
    matching the native character stream, so no axis flip is needed.
    """
    import fitz  # lazy: keep module importable without PyMuPDF

    doc = fitz.open(str(pdf_path))
    try:
        pg = doc[page - 1]
        x0, y0, x1, y1 = [float(v) for v in bbox_points]
        rect = fitz.Rect(x0, y0, x1, y1)
        pix = pg.get_pixmap(dpi=dpi, clip=rect, colorspace=fitz.csRGB)
        return pix.tobytes("ppm")
    finally:
        doc.close()


def encode_webp(image_bytes: bytes, quality: int = 88) -> bytes:
    """Encode a raster image (PPM/PNG/JPEG bytes) once as reading-grade WebP."""
    from PIL import Image  # lazy

    with Image.open(io.BytesIO(image_bytes)) as im:
        im = im.convert("RGB")
        out = io.BytesIO()
        im.save(out, format="WEBP", quality=quality, method=6)
        return out.getvalue()


def chart_webp(pdf_path: str | Path, cv: ChartVector, dpi: int = CROP_DPI) -> bytes:
    """Full primary-signal path: union bbox -> PDF crop -> WebP."""
    return encode_webp(crop_pdf_region(pdf_path, cv.page, cv.union_bbox_points, dpi=dpi))


def reencode_image_file(path: str | Path, quality: int = 85, max_dim: int | None = None) -> bytes:
    """Re-encode a verified asset file (e.g. inventory figure PNG) as WebP.

    ``max_dim`` bounds the longest edge (preserving aspect) so full-issue
    photo weaving stays inside the lightweight artifact budget.
    """
    with open(path, "rb") as fh:
        data = fh.read()
    if not max_dim:
        return encode_webp(data, quality=quality)
    from PIL import Image  # lazy

    with Image.open(io.BytesIO(data)) as im:
        im = im.convert("RGB")
        w, h = im.size
        scale = min(1.0, max_dim / max(w, h))
        if scale < 1.0:
            im = im.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
        out = io.BytesIO()
        im.save(out, format="WEBP", quality=quality, method=6)
        return out.getvalue()


def esc(text: str) -> str:
    return html.escape(text or "", quote=True)
