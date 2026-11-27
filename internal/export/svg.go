package export

import (
	"html"
	"math"
	"regexp"
	"strconv"
	"strings"
	"unicode"

	"deepread/internal/openuilang"
)

var (
	safeSVGPathRE   = regexp.MustCompile(`^[MmLlHhVvCcSsQqTtAaZz0-9eE.,+\-\s]*$`)
	safeSVGPointsRE = regexp.MustCompile(`^[-+0-9.eE\s,]*$`)
	svgTransformRE  = regexp.MustCompile(`(?i)(translate|rotate|scale|skewx|skewy|matrix)\(([^()]*)\)`)
)

func validExportViewBox(raw string) bool {
	parts := strings.FieldsFunc(raw, func(r rune) bool { return unicode.IsSpace(r) || r == ',' })
	if len(parts) != 4 {
		return false
	}
	for _, part := range parts {
		n, err := strconv.ParseFloat(part, 64)
		if err != nil || math.IsNaN(n) || math.IsInf(n, 0) {
			return false
		}
	}
	return true
}

var semanticSVGColors = map[string]string{
	"ink":            "var(--ink)",
	"muted":          "var(--muted)",
	"faint":          "var(--faint)",
	"canvas":         "var(--paper)",
	"paper":          "var(--paper)",
	"surface":        "var(--surface)",
	"surface-strong": "#e7e1d7",
	"border":         "var(--rule)",
	"rule":           "var(--rule)",
	"accent":         "var(--accent)",
	"info":           "#2f648e",
	"success":        "#2f7051",
	"warning":        "#9d661b",
	"danger":         "#a63d34",
	"purple":         "#6c4f8f",
	"pink":           "#a54a6c",
	"chart1":         "#866e5d",
	"chart2":         "#3b6978",
	"chart3":         "#a85a44",
	"chart4":         "#587a5b",
	"chart5":         "#8c6d99",
	"chart6":         "#b58b45",
}

func safeSVGColor(raw string) (string, bool) {
	value := strings.TrimSpace(raw)
	if value == "" {
		return "", false
	}
	lower := strings.ToLower(value)
	if strings.Contains(lower, "url(") || strings.Contains(lower, "expression(") || strings.Contains(lower, "javascript:") || strings.ContainsAny(value, ";<>\"'") {
		return "", false
	}
	if mapped, ok := semanticSVGColors[lower]; ok {
		return mapped, true
	}
	if safeHexColorRE.MatchString(value) || safeFunctionalColorRE.MatchString(value) {
		return value, true
	}
	if safeNamedColorRE.MatchString(value) {
		return value, true
	}
	return "", false
}

func safeSVGTransform(raw string) (string, bool) {
	value := strings.TrimSpace(raw)
	if value == "" {
		return "", false
	}
	matches := svgTransformRE.FindAllStringSubmatchIndex(value, -1)
	if len(matches) == 0 {
		return "", false
	}
	position := 0
	for _, match := range matches {
		if strings.TrimSpace(strings.Trim(matchSeparator(value[position:match[0]]), ",")) != "" {
			return "", false
		}
		position = match[1]
		name := strings.ToLower(value[match[2]:match[3]])
		args := strings.FieldsFunc(value[match[4]:match[5]], func(r rune) bool { return unicode.IsSpace(r) || r == ',' })
		validCount := 0
		switch name {
		case "translate", "scale":
			validCount = 12
		case "rotate":
			validCount = 13
		case "skewx", "skewy":
			validCount = 1
		case "matrix":
			validCount = 6
		}
		if len(args) == 0 || validCount == 12 && len(args) > 2 || validCount == 13 && len(args) != 1 && len(args) != 3 || validCount == 1 && len(args) != 1 || validCount == 6 && len(args) != 6 {
			return "", false
		}
		for _, arg := range args {
			n, err := strconv.ParseFloat(arg, 64)
			if err != nil || math.IsNaN(n) || math.IsInf(n, 0) {
				return "", false
			}
		}
	}
	if strings.TrimSpace(strings.Trim(value[position:], ",")) != "" {
		return "", false
	}
	return value, true
}

func matchSeparator(s string) string { return s }

func (r *genuiRenderer) renderSVG(el *openuilang.Element) (string, error) {
	viewBox := stringProperty(el.Props, "viewBox", "")
	if !validExportViewBox(viewBox) {
		return `<span class="dr-svg-invalid" role="img" aria-label="Invalid diagram"></span>`, nil
	}
	var out strings.Builder
	out.WriteString(`<svg class="dr-svg" xmlns="http://www.w3.org/2000/svg" viewBox="` + html.EscapeString(viewBox) + `" role="img" aria-label="` + html.EscapeString(stringProperty(el.Props, "label", "Diagram")) + `">`)
	if style := safeCSSLength("width", property(el.Props, "width")) + safeCSSLength("height", property(el.Props, "height")); style != "" {
		out.WriteString(` style="` + strings.TrimPrefix(style, ";") + `"`)
	}
	children, err := r.renderNodeList(property(el.Props, "children"), false)
	if err != nil {
		return "", err
	}
	out.WriteString(children)
	out.WriteString(`</svg>`)
	return out.String(), nil
}

func (r *genuiRenderer) renderSVGShape(el *openuilang.Element) (string, error) {
	kind := el.Type
	p := el.Props
	if kind == "G" {
		var out strings.Builder
		out.WriteString(`<g`)
		if transform, ok := safeSVGTransform(stringProperty(p, "transform", "")); ok {
			out.WriteString(` transform="` + html.EscapeString(transform) + `"`)
		}
		writeExportSVGPaint(&out, p, false, false, false)
		children, err := r.renderNodeList(property(p, "children"), false)
		if err != nil {
			return "", err
		}
		out.WriteString(`>` + children + `</g>`)
		return out.String(), nil
	}
	if kind == "SvgText" {
		var out strings.Builder
		out.WriteString(`<text x="` + exportSVGNumber(p, "x", 0) + `" y="` + exportSVGNumber(p, "y", 0) + `" font-size="` + exportSVGNumber(p, "size", 14) + `"`)
		if anchor := stringProperty(p, "anchor", ""); anchor == "start" || anchor == "middle" || anchor == "end" {
			out.WriteString(` text-anchor="` + anchor + `"`)
		}
		if weight := map[string]int{"normal": 400, "medium": 500, "semibold": 600}[stringProperty(p, "weight", "")]; weight != 0 {
			out.WriteString(` font-weight="` + strconv.Itoa(weight) + `"`)
		}
		writeExportSVGPaint(&out, p, false, false, true)
		out.WriteString(`>` + html.EscapeString(stringProperty(p, "text", "")) + `</text>`)
		return out.String(), nil
	}
	if kind == "Path" && !safeSVGPathRE.MatchString(stringProperty(p, "d", "")) {
		return "", nil
	}
	if (kind == "Polyline" || kind == "Polygon") && !safeSVGPointsRE.MatchString(stringProperty(p, "points", "")) {
		return "", nil
	}
	var out strings.Builder
	out.WriteString(`<` + strings.ToLower(kind))
	attributes := map[string][]string{
		"Circle": {"cx", "cy", "r"}, "Ellipse": {"cx", "cy", "rx", "ry"},
		"Rect": {"x", "y", "width", "height", "rx"}, "Line": {"x1", "y1", "x2", "y2"},
		"Polyline": {}, "Polygon": {}, "Path": {},
	}
	for _, name := range attributes[kind] {
		if kind == "Rect" && name == "rx" && property(p, name) == nil {
			continue
		}
		out.WriteString(` ` + name + `="` + exportSVGNumber(p, name, 0) + `"`)
	}
	if kind == "Polyline" || kind == "Polygon" {
		out.WriteString(` points="` + html.EscapeString(stringProperty(p, "points", "")) + `"`)
	} else if kind == "Path" {
		out.WriteString(` d="` + html.EscapeString(stringProperty(p, "d", "")) + `"`)
	}
	writeExportSVGPaint(&out, p, kind == "Circle" || kind == "Ellipse" || kind == "Rect" || kind == "Polygon", kind == "Line" || kind == "Path" || kind == "Polyline", false)
	out.WriteString(`/>`)
	return out.String(), nil
}

func writeExportSVGPaint(out *strings.Builder, p *openuilang.Object, defaultFill, defaultNoFill, text bool) {
	fill, fillOK := safeSVGColor(stringProperty(p, "fill", ""))
	stroke, strokeOK := safeSVGColor(stringProperty(p, "stroke", ""))
	if !fillOK {
		switch {
		case defaultNoFill || strokeOK:
			fill = "none"
		case defaultFill || text:
			fill = "currentColor"
		}
	}
	if fill != "" {
		out.WriteString(` fill="` + html.EscapeString(fill) + `"`)
	}
	if !strokeOK && defaultNoFill {
		stroke = "currentColor"
	}
	if stroke != "" && stringProperty(p, "stroke", "") != "none" || strokeOK {
		out.WriteString(` stroke="` + html.EscapeString(stroke) + `"`)
	}
	if width, ok := finiteNumber(property(p, "strokeWidth")); ok && width >= 0 {
		out.WriteString(` stroke-width="` + formatFloat(width) + `"`)
	} else if defaultNoFill && stroke != "" {
		out.WriteString(` stroke-width="2"`)
	}
	if opacity, ok := finiteNumber(property(p, "opacity")); ok && opacity >= 0 && opacity <= 1 {
		out.WriteString(` opacity="` + formatFloat(opacity) + `"`)
	}
}

func exportSVGNumber(p *openuilang.Object, name string, fallback float64) string {
	n, ok := finiteNumber(property(p, name))
	if !ok || n < -1_000_000 || n > 1_000_000 {
		n = fallback
	}
	return formatFloat(n)
}
