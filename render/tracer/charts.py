"""Declarative Visual Primitive `<wsj-chart>` compiler.

Models express charts as compact declarative specs (~8 lines) with paragraph
anchors (``data-src="pK"``); the compiler verifies every substantive number in
labels/values against the referenced paragraphs and renders deterministic,
responsive, clip-free SVG (``viewBox`` + 100% width).  Four types:

- ``comparison`` — horizontal comparison bars with exact proportional widths.
- ``flow``       — multi-node mechanism/capital-flow topology (boxes + arrows).
- ``timeline``   — chronological milestone track (red dots per DESIGN.md).
- ``matrix``     — multi-column versus/comparison grid.

SVG internal text is emitted in both languages as ``.l-cn`` / ``.l-en`` pairs;
the reader shell shows exactly one language layer so text never collides.
"""
from __future__ import annotations

import html
from typing import Any

from .verify import TracerCompilationError, verify_element_numbers

INK = "#111111"
BODY = "#1f1f1f"
MUT = "#5f6462"
LINE = "#e5e2da"
ORANGE = "#fa9000"
RED = "#c31833"
PAPER = "#fdfbf8"

FONT_CN = "Noto Sans SC"
SERIF_CN = "Noto Serif SC"


def _t(x: float, y: float, text: str, cls: str = "l-cn", size: int = 13, weight: int = 400,
       fill: str = BODY, anchor: str = "start", family: str | None = None) -> str:
    fam = family or FONT_CN
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" font-family="{fam}" '
        f'font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{html.escape(text)}</text>'
    )


def _bilingual(x: float, y: float, cn: str, en: str, *, size: int = 13, weight: int = 400,
               fill: str = BODY, anchor: str = "start", dy_en: int = 13) -> str:
    return (
        _t(x, y, cn, "l-cn", size, weight, fill, anchor)
        + _t(x, y + dy_en, en, "l-en", size - 1, 400, MUT, anchor)
    )


def _svg(open_tag: str, body: str, w: int, h: int) -> str:
    return (
        f'<svg viewBox="0 0 {w} {h}" width="100%" '
        f'xmlns="http://www.w3.org/2000/svg" role="img">{body}</svg>'
    )


def _spec_numbers(spec: dict[str, Any]) -> str:
    """All human-facing strings of a chart spec, for number grounding.

    Numeric ``value``/``row``/``w`` fields are layout magnitudes (bar lengths,
    grid slots), not reader-facing text; their printable form lives in
    ``display``/labels, which is what gets verified.
    """
    parts: list[str] = [spec.get("title_cn", ""), spec.get("title_en", "")]
    layout_keys = {"value", "row", "w", "x", "y"}
    for group in ("items", "nodes", "rows", "cols"):
        for item in spec.get(group, []):
            parts.extend(str(v) for k, v in item.items() if k not in layout_keys and isinstance(v, (str, int, float)))
            for cell in item.get("cells", []) if isinstance(item, dict) else []:
                parts.extend(str(v) for v in cell.values() if isinstance(v, (str, int, float)))
    return "\n".join(parts)


def compile_wsj_chart(spec: dict[str, Any], paragraph_texts: dict[str, dict[str, str]]) -> str:
    """Compile a declarative chart spec into responsive SVG.

    ``paragraph_texts`` maps paragraph id -> {"en":..., "cn":...} for the
    paragraphs listed in the spec's ``data_src``.  Every substantive number in
    the spec must exist in the referenced paragraphs, else
    ``TracerCompilationError`` (zero silent fallback).
    """
    src_ids = [s for s in str(spec.get("data_src", "")).split() if s]
    sources = [paragraph_texts[s]["en"] for s in src_ids if s in paragraph_texts]
    sources += [paragraph_texts[s]["cn"] for s in src_ids if s in paragraph_texts]
    unknown = [s for s in src_ids if s not in paragraph_texts]
    if unknown:
        raise TracerCompilationError(f"wsj-chart data-src references unknown paragraphs: {unknown}")
    verify_element_numbers(f"wsj-chart[{spec.get('type')}:{spec.get('id', '?')}]", _spec_numbers(spec), sources)

    ctype = spec.get("type")
    if ctype == "comparison":
        body = _render_comparison(spec)
    elif ctype == "flow":
        body = _render_flow(spec)
    elif ctype == "timeline":
        body = _render_timeline(spec)
    elif ctype == "matrix":
        body = _render_matrix(spec)
    else:
        raise TracerCompilationError(f"unknown wsj-chart type: {ctype!r}")
    w, h = spec["_size"]
    return _svg("", body, w, h)


# --- comparison: exact proportional horizontal bars -------------------------

def _render_comparison(spec: dict[str, Any]) -> str:
    items = spec["items"]
    maxv = max(abs(float(i["value"])) for i in items) or 1.0
    label_w = max(max(len(str(i["label_cn"])) for i in items) * 13, 90) + 8
    bar_h, gap, top, right = 22, 14, 44, 70
    W = 640
    track = W - label_w - right
    H = top + len(items) * (bar_h + gap) + 26
    spec["_size"] = (W, H)
    out = [_bilingual(0, 20, spec["title_cn"], spec["title_en"], size=14, weight=700, fill=INK)]
    y = top
    for i, item in enumerate(items):
        frac = abs(float(item["value"])) / maxv
        bw = max(frac * track, 2)
        out.append(_bilingual(0, y + bar_h / 2 + 4, str(item["label_cn"]), str(item["label_en"]), size=12, anchor="start"))
        out.append(f'<rect x="{label_w}" y="{y}" width="{track}" height="{bar_h}" fill="{PAPER}" stroke="{LINE}"/>')
        color = ORANGE if item.get("emphasis") else INK
        out.append(f'<rect x="{label_w}" y="{y}" width="{bw:.1f}" height="{bar_h}" fill="{color}"/>')
        out.append(_t(label_w + bw + 6, y + bar_h / 2 + 4, str(item["display"]), "l-cn", 12, 700, INK))
        y += bar_h + gap
    return "".join(out)


# --- flow: mechanism / capital-flow topology --------------------------------

def _render_flow(spec: dict[str, Any]) -> str:
    nodes = spec["nodes"]
    edges = spec.get("edges", [])
    W = 640
    rows: list[list[dict[str, Any]]] = []
    for node in nodes:
        r = int(node.get("row", len(rows)))
        while len(rows) <= r:
            rows.append([])
        rows[r].append(node)
    box_h, v_gap, side = 54, 44, 18
    col_w = W / max(len(row) for row in rows)
    pos: dict[str, tuple[float, float, float, float]] = {}
    H = 44 + len(rows) * (box_h + v_gap) + 6
    spec["_size"] = (W, H)
    out = [_bilingual(0, 20, spec["title_cn"], spec["title_en"], size=14, weight=700, fill=INK)]
    for r, row in enumerate(rows):
        y = 36 + r * (box_h + v_gap)
        for c, node in enumerate(row):
            bw = float(node.get("w", col_w - side * 2))
            x = c * col_w + (col_w - bw) / 2
            fill = PAPER if node.get("kind") == "actor" else INK
            stroke = INK
            text_fill = INK if node.get("kind") == "actor" else PAPER
            out.append(f'<rect x="{x:.1f}" y="{y}" width="{bw:.1f}" height="{box_h}" fill="{fill}" stroke="{stroke}"/>')
            out.append(_t(x + bw / 2, y + 24, str(node["label_cn"]), "l-cn", 13, 700, text_fill, "middle"))
            out.append(_t(x + bw / 2, y + 40, str(node.get("label_en", "")), "l-en", 11, 400, text_fill if node.get("kind") != "actor" else MUT, "middle"))
            pos[node["id"]] = (x, y, bw, box_h)
    out.append(
        f'<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        f'markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{MUT}"/></marker></defs>'
    )
    for a, b in edges:
        ax, ay, aw, ah = pos[a]
        bx, by, bw, bh = pos[b]
        x1, y1 = ax + aw / 2, ay + ah
        x2, y2 = bx + bw / 2, by
        if abs(ay - by) < 1 and bx > ax:  # same-row left-to-right arrow
            x1, y1 = ax + aw, ay + ah / 2
            x2, y2 = bx, by + bh / 2
            d = f"M{x1},{y1} L{x2 - 8},{y2}"
        elif y2 < y1:  # upward edge (same row right-to-left)
            x1, y1 = ax + aw, ay + ah / 2
            x2, y2 = bx, by + bh / 2
            mid = (x1 + x2) / 2
            d = f"M{x1},{y1} C{mid},{y1} {mid},{y2} {x2 - 8},{y2}"
        else:
            d = f"M{x1},{y1} L{x1},{(y1 + y2) / 2} L{x2},{(y1 + y2) / 2} L{x2},{y2 - 2}"
        out.append(f'<path d="{d}" fill="none" stroke="{MUT}" stroke-width="1.4" marker-end="url(#arr)"/>')
        label = dict(spec.get("edge_labels", {})).get(f"{a}>{b}")
        if label:
            out.append(_t((x1 + x2) / 2 + 6, (y1 + y2) / 2 - 4, str(label), "l-cn", 11, 400, MUT))
    return "".join(out)


# --- timeline: chronological milestone track --------------------------------

def _render_timeline(spec: dict[str, Any]) -> str:
    items = spec["items"]
    W = 640
    top, rail_x = 52, 20
    row_h = 58  # stamp + CN text + EN text must not collide across rows
    H = top + len(items) * row_h + 8
    spec["_size"] = (W, H)
    out = [_bilingual(0, 20, spec["title_cn"], spec["title_en"], size=14, weight=700, fill=INK)]
    out.append(f'<line x1="{rail_x}" y1="{top - 14}" x2="{rail_x}" y2="{H - 24}" stroke="#d9d9d9" stroke-width="2"/>')
    y = top
    for item in items:
        out.append(f'<circle cx="{rail_x}" cy="{y - 4}" r="5" fill="{RED}"/>')
        stamp_cn, stamp_en = str(item.get("stamp_cn", "")), str(item.get("stamp_en", ""))
        out.append(_t(rail_x + 16, y, stamp_cn, "l-cn", 13, 700, INK))
        if stamp_en:
            out.append(_t(rail_x + 16, y, stamp_en, "l-en", 12, 700, INK))
        out.append(_t(rail_x + 16, y + 22, str(item["text_cn"]), "l-cn", 13, 400, BODY))
        out.append(_t(rail_x + 16, y + 38, str(item.get("text_en", "")), "l-en", 12, 400, MUT))
        y += row_h
    return "".join(out)


# --- matrix: multi-column versus grid ----------------------------------------

def _render_matrix(spec: dict[str, Any]) -> str:
    cols = spec["cols"]
    rows = spec["rows"]
    W = 640
    label_w = max(max(len(str(r["label_cn"])) for r in rows) * 13, 80) + 10
    col_w = (W - label_w) / len(cols)
    top, head_h, row_h = 52, 34, 40
    H = top + head_h + len(rows) * row_h + 6
    spec["_size"] = (W, H)
    out = [_bilingual(0, 20, spec["title_cn"], spec["title_en"], size=14, weight=700, fill=INK)]
    x = label_w
    for c, col in enumerate(cols):
        out.append(f'<rect x="{x:.1f}" y="{top}" width="{col_w:.1f}" height="{head_h}" fill="{INK}"/>')
        out.append(_t(x + col_w / 2, top + 22, str(col["label_cn"]), "l-cn", 12, 700, PAPER, "middle"))
        x += col_w
    y = top + head_h
    for r_i, row in enumerate(rows):
        bg = PAPER if r_i % 2 else "#f6f3ec"
        out.append(f'<rect x="0" y="{y}" width="{W}" height="{row_h}" fill="{bg}" stroke="{LINE}"/>')
        out.append(_t(0, y + row_h / 2 + 4, str(row["label_cn"]), "l-cn", 12, 700, INK))
        x = label_w
        for c, col in enumerate(cols):
            cell = row["cells"][c]
            emph = str(cell.get("emphasis", ""))
            val_cn, val_en = str(cell.get("cn", "")), str(cell.get("en", ""))
            if emph:
                out.append(f'<rect x="{x + 4:.1f}" y="{y + 6}" width="{col_w - 8:.1f}" height="{row_h - 12}" fill="{ORANGE}" fill-opacity="0.16"/>')
            out.append(_t(x + col_w / 2, y + row_h / 2 + 1, val_cn, "l-cn", 12, 700 if emph else 400, INK, "middle"))
            out.append(_t(x + col_w / 2, y + row_h / 2 + 14, val_en, "l-en", 10, 400, MUT, "middle"))
            x += col_w
        y += row_h
    return "".join(out)
