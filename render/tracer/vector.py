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


def union_chart_bbox(native: dict[str, Any], chart_norm: list[float]) -> tuple[list[float], list[dict[str, Any]]]:
    """Union of the chart bbox with adjacent `Retina*` title/source/axis lines.

    Walks upward from the chart top including contiguous `Retina*` lines whose
    horizontal center falls inside the chart column span (chart titles and
    top-axis labels such as ``$20billion``), and downward for the contiguous
    `Retina*` source line.  Returns (union_bbox_points, member_lines).
    """
    W, H = float(native["width"]), float(native["height"])
    cx0, cy0, cx1, cy1 = [float(v) for v in chart_norm]
    bx0, by0, bx1, by1 = cx0 * W, cy0 * H, cx1 * W, cy1 * H
    members: list[dict[str, Any]] = []

    retina = [l for l in native["lines"] if is_retina(l) and l.get("chars")]
    # Above: contiguous block, nearest-first, x-center inside the chart span.
    above = [
        l for l in retina
        if l["bbox"][3] <= by0 + _GAP_TOL_PT and bx0 <= (l["bbox"][0] + l["bbox"][2]) / 2 <= bx1
    ]
    above.sort(key=lambda l: -l["bbox"][3])
    anchor = by0
    for l in above:
        if anchor - l["bbox"][3] <= _GAP_TOL_PT:
            members.append(l)
            anchor = l["bbox"][1]
    # Below: contiguous Retina lines (the RetinaMPNarrowLt source line).
    below = [
        l for l in retina
        if l["bbox"][1] >= by1 - _GAP_TOL_PT and _x_overlap(l["bbox"][0], l["bbox"][2], bx0, bx1, _X_PAD_PT)
    ]
    below.sort(key=lambda l: l["bbox"][1])
    anchor = by1
    for l in below:
        if l["bbox"][1] - anchor <= _GAP_TOL_PT:
            members.append(l)
            anchor = l["bbox"][3]

    ux0 = min([bx0] + [l["bbox"][0] for l in members]) - _UNION_PAD_PT
    uy0 = min([by0] + [l["bbox"][1] for l in members]) - _UNION_PAD_PT
    ux1 = max([bx1] + [l["bbox"][2] for l in members]) + _UNION_PAD_PT
    uy1 = max([by1] + [l["bbox"][3] for l in members]) + _UNION_PAD_PT
    return [max(0.0, ux0), max(0.0, uy0), min(W, ux1), min(H, uy1)], members


def extract_chart_vectors(native: dict[str, Any], chart_id: str, page: int, chart_norm: list[float]) -> ChartVector:
    """Recover title / series labels / axis ticks / source for one chart.

    The union bbox (used for cropping) covers the chart plus adjacent
    title/source lines; the structured strings also read every ``Retina*`` line
    inside the chart region itself (series labels, axis ticks).
    """
    W, H = float(native["width"]), float(native["height"])
    union_pt, members = union_chart_bbox(native, chart_norm)
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
            if zone == "adjacent":
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


def reencode_image_file(path: str | Path, quality: int = 85) -> bytes:
    """Re-encode a verified asset file (e.g. inventory figure PNG) as WebP."""
    with open(path, "rb") as fh:
        return encode_webp(fh.read(), quality=quality)


def esc(text: str) -> str:
    return html.escape(text or "", quote=True)
