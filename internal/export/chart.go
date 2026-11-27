package export

import (
	"fmt"
	"html"
	"math"
	"strconv"
	"strings"

	"deepread/internal/openuilang"
)

var chartPalette = []string{"#866e5d", "#607d78", "#a47767", "#6d7891", "#a18b56", "#7d6b82"}

type chartFrame struct {
	kind         string
	format       string
	stacked      bool
	height       int
	xKey         string
	series       []string
	labels       []string
	rows         []*openuilang.Object
	values       [][]float64
	seriesLabels map[string]string
}

func renderChart(el *openuilang.Element) (string, error) {
	frame, err := readChartFrame(el)
	if err != nil {
		return "", err
	}
	if frame.kind != "bar" && frame.kind != "line" {
		return "", fmt.Errorf("Chart type %q is not supported", frame.kind)
	}

	const width = 600.0
	height := float64(frame.height)
	legendRows := 0
	if len(frame.series) > 0 {
		legendRows = (len(frame.series) + 2) / 3
	}
	left, right := 58.0, 20.0
	top := 26.0 + float64(legendRows)*20
	bottom := 48.0
	plotWidth := width - left - right
	plotHeight := math.Max(40, height-top-bottom)
	baseY := top + plotHeight

	var out strings.Builder
	out.WriteString(`<figure class="dr-chart dr-chart-` + frame.kind + `">`)
	out.WriteString(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 ` + strconv.Itoa(frame.height) + `" role="img" aria-label="` + html.EscapeString(frame.kind) + ` chart">`)
	out.WriteString(`<title>` + html.EscapeString(frame.kind) + ` chart</title>`)
	out.WriteString(`<g font-family="-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif">`)
	renderChartLegend(&out, frame, left)

	if len(frame.rows) == 0 || len(frame.series) == 0 {
		out.WriteString(`<text x="300" y="` + chartNumber(top+plotHeight/2) + `" text-anchor="middle" fill="#716c63" font-size="12">No data</text>`)
		out.WriteString(`</g></svg></figure>` + "\n")
		return out.String(), nil
	}

	minValue, maxValue := chartDomain(frame)
	ticks := chartTicks(minValue, maxValue)
	minValue, maxValue = ticks[0], ticks[len(ticks)-1]
	y := func(value float64) float64 {
		return top + (maxValue-value)/(maxValue-minValue)*plotHeight
	}

	out.WriteString(`<g class="dr-chart-axes">`)
	for _, tick := range ticks {
		tickY := y(tick)
		out.WriteString(`<line x1="` + chartNumber(left) + `" y1="` + chartNumber(tickY) + `" x2="` + chartNumber(width-right) + `" y2="` + chartNumber(tickY) + `" stroke="#e5e2dc" stroke-width="1"/>`)
		out.WriteString(`<text x="` + chartNumber(left-9) + `" y="` + chartNumber(tickY+4) + `" text-anchor="end" fill="#716c63" font-size="11">` + html.EscapeString(formatChartValue(tick, frame.format)) + `</text>`)
	}
	out.WriteString(`<line x1="` + chartNumber(left) + `" y1="` + chartNumber(baseY) + `" x2="` + chartNumber(width-right) + `" y2="` + chartNumber(baseY) + `" stroke="#b8b1a8" stroke-width="1"/>`)
	out.WriteString(`</g>`)

	groupWidth := plotWidth / float64(len(frame.rows))
	if frame.kind == "bar" {
		renderBars(&out, frame, left, groupWidth, y)
	} else {
		renderLines(&out, frame, left, groupWidth, y)
	}

	out.WriteString(`<g class="dr-chart-x-labels">`)
	for i, label := range frame.labels {
		x := left + (float64(i)+0.5)*groupWidth
		out.WriteString(`<text x="` + chartNumber(x) + `" y="` + chartNumber(baseY+22) + `" text-anchor="middle" fill="#716c63" font-size="11">` + html.EscapeString(label) + `</text>`)
	}
	out.WriteString(`</g></g></svg></figure>` + "\n")
	return out.String(), nil
}

func readChartFrame(el *openuilang.Element) (*chartFrame, error) {
	props := el.Props
	frame := &chartFrame{
		kind:         stringProperty(props, "type", ""),
		format:       stringProperty(props, "format", "number"),
		stacked:      boolProperty(props, "stacked"),
		height:       240,
		xKey:         stringProperty(props, "x", "x"),
		seriesLabels: map[string]string{},
	}
	if value, ok := props.Values["height"].(float64); ok && !math.IsNaN(value) && !math.IsInf(value, 0) {
		frame.height = int(math.Round(value))
		if frame.height < 160 {
			frame.height = 160
		}
		if frame.height > 800 {
			frame.height = 800
		}
	}
	rawRows, _ := props.Values["data"].([]any)
	for i, rawRow := range rawRows {
		row, ok := rawRow.(*openuilang.Object)
		if !ok || row == nil {
			return nil, fmt.Errorf("Chart data row %d must be an object", i)
		}
		frame.rows = append(frame.rows, row)
		label := ""
		switch value := row.Values[frame.xKey].(type) {
		case string:
			label = value
		case float64:
			label = strconv.FormatFloat(value, 'f', -1, 64)
		default:
			label = fmt.Sprint(value)
		}
		frame.labels = append(frame.labels, label)
	}
	if rawSeries, ok := props.Values["series"].([]any); ok {
		for _, rawName := range rawSeries {
			name, ok := rawName.(string)
			if !ok || name == "" {
				return nil, fmt.Errorf("Chart series names must be non-empty strings")
			}
			frame.series = append(frame.series, name)
		}
	} else {
		seen := map[string]bool{}
		for _, row := range frame.rows {
			for _, key := range row.Keys {
				if key == frame.xKey || seen[key] {
					continue
				}
				if _, ok := row.Values[key].(float64); ok {
					seen[key] = true
					frame.series = append(frame.series, key)
				}
			}
		}
	}
	if labels, ok := props.Values["seriesLabels"].(*openuilang.Object); ok {
		for _, key := range labels.Keys {
			if label, ok := labels.Values[key].(string); ok {
				frame.seriesLabels[key] = label
			}
		}
	}
	frame.values = make([][]float64, len(frame.series))
	for seriesIndex, name := range frame.series {
		frame.values[seriesIndex] = make([]float64, len(frame.rows))
		for rowIndex, row := range frame.rows {
			value, ok := row.Values[name].(float64)
			if !ok || math.IsNaN(value) || math.IsInf(value, 0) {
				return nil, fmt.Errorf("Chart data row %d series %q must be a finite number", rowIndex, name)
			}
			frame.values[seriesIndex][rowIndex] = value
		}
	}
	return frame, nil
}

func chartDomain(frame *chartFrame) (float64, float64) {
	minValue, maxValue := 0.0, 0.0
	if frame.kind == "bar" && frame.stacked {
		for row := range frame.rows {
			positive, negative := 0.0, 0.0
			for series := range frame.series {
				value := frame.values[series][row]
				if value >= 0 {
					positive += value
				} else {
					negative += value
				}
			}
			minValue = math.Min(minValue, negative)
			maxValue = math.Max(maxValue, positive)
		}
		return minValue, maxValue
	}
	for series := range frame.series {
		for _, value := range frame.values[series] {
			minValue = math.Min(minValue, value)
			maxValue = math.Max(maxValue, value)
		}
	}
	return minValue, maxValue
}

func chartTicks(minValue, maxValue float64) []float64 {
	if maxValue == minValue {
		if maxValue == 0 {
			maxValue = 1
		} else {
			padding := math.Abs(maxValue) * 0.2
			minValue -= padding
			maxValue += padding
		}
	}
	roughStep := (maxValue - minValue) / 4
	magnitude := math.Pow(10, math.Floor(math.Log10(roughStep)))
	normalized := roughStep / magnitude
	step := 10 * magnitude
	switch {
	case normalized <= 1:
		step = magnitude
	case normalized <= 2:
		step = 2 * magnitude
	case normalized <= 2.5:
		step = 2.5 * magnitude
	case normalized <= 5:
		step = 5 * magnitude
	}
	niceMin := math.Floor(minValue/step) * step
	niceMax := math.Ceil(maxValue/step) * step
	var ticks []float64
	for value := niceMin; value <= niceMax+step*0.001 && len(ticks) < 20; value += step {
		if math.Abs(value) < step*1e-9 {
			value = 0
		}
		ticks = append(ticks, value)
	}
	if len(ticks) < 2 {
		return []float64{niceMin, niceMax}
	}
	return ticks
}

func renderChartLegend(out *strings.Builder, frame *chartFrame, left float64) {
	if len(frame.series) == 0 {
		return
	}
	out.WriteString(`<g class="dr-chart-legend">`)
	for i, name := range frame.series {
		x := left + float64(i%3)*172
		y := 13.0 + float64(i/3)*20
		color := chartPalette[i%len(chartPalette)]
		if frame.kind == "line" {
			out.WriteString(`<line x1="` + chartNumber(x) + `" y1="` + chartNumber(y) + `" x2="` + chartNumber(x+15) + `" y2="` + chartNumber(y) + `" stroke="` + color + `" stroke-width="2.5"/>`)
		} else {
			out.WriteString(`<rect x="` + chartNumber(x) + `" y="` + chartNumber(y-5) + `" width="12" height="10" rx="1" fill="` + color + `"/>`)
		}
		label := frame.seriesLabels[name]
		if label == "" {
			label = name
		}
		out.WriteString(`<text x="` + chartNumber(x+21) + `" y="` + chartNumber(y+4) + `" fill="#716c63" font-size="11">` + html.EscapeString(label) + `</text>`)
	}
	out.WriteString(`</g>`)
}

func renderBars(out *strings.Builder, frame *chartFrame, left, groupWidth float64, y func(float64) float64) {
	zeroY := y(0)
	out.WriteString(`<g class="dr-chart-bars">`)
	if frame.stacked {
		barWidth := math.Min(54, groupWidth*0.56)
		for row := range frame.rows {
			x := left + (float64(row)+0.5)*groupWidth - barWidth/2
			positiveBase, negativeBase := 0.0, 0.0
			for series := range frame.series {
				value := frame.values[series][row]
				start, end := positiveBase, positiveBase+value
				if value < 0 {
					start, end = negativeBase, negativeBase+value
					negativeBase = end
				} else {
					positiveBase = end
				}
				y1, y2 := y(start), y(end)
				rectY, rectHeight := math.Min(y1, y2), math.Abs(y1-y2)
				out.WriteString(`<rect class="dr-chart-data" x="` + chartNumber(x) + `" y="` + chartNumber(rectY) + `" width="` + chartNumber(barWidth) + `" height="` + chartNumber(rectHeight) + `" fill="` + chartPalette[series%len(chartPalette)] + `"/>`)
				labelY := y2 - 6
				if value < 0 {
					labelY = y2 + 13
				}
				writeChartDataLabel(out, x+barWidth/2, labelY, value, frame.format)
			}
		}
	} else {
		barGroupWidth := groupWidth * 0.72
		barWidth := math.Max(2, barGroupWidth/float64(len(frame.series))-3)
		for row := range frame.rows {
			groupStart := left + float64(row)*groupWidth + (groupWidth-barGroupWidth)/2
			for series := range frame.series {
				value := frame.values[series][row]
				x := groupStart + float64(series)*(barWidth+3)
				valueY := y(value)
				rectY, rectHeight := math.Min(zeroY, valueY), math.Abs(zeroY-valueY)
				out.WriteString(`<rect class="dr-chart-data" x="` + chartNumber(x) + `" y="` + chartNumber(rectY) + `" width="` + chartNumber(barWidth) + `" height="` + chartNumber(rectHeight) + `" fill="` + chartPalette[series%len(chartPalette)] + `"/>`)
				labelY := valueY - 6
				if value < 0 {
					labelY = valueY + 13
				}
				writeChartDataLabel(out, x+barWidth/2, labelY, value, frame.format)
			}
		}
	}
	out.WriteString(`</g>`)
}

func renderLines(out *strings.Builder, frame *chartFrame, left, groupWidth float64, y func(float64) float64) {
	out.WriteString(`<g class="dr-chart-lines">`)
	for series := range frame.series {
		color := chartPalette[series%len(chartPalette)]
		var path strings.Builder
		for row, value := range frame.values[series] {
			x := left + (float64(row)+0.5)*groupWidth
			pointY := y(value)
			if row == 0 {
				path.WriteString("M ")
			} else {
				path.WriteString(" L ")
			}
			path.WriteString(chartNumber(x) + " " + chartNumber(pointY))
		}
		out.WriteString(`<path d="` + path.String() + `" fill="none" stroke="` + color + `" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>`)
		for row, value := range frame.values[series] {
			x := left + (float64(row)+0.5)*groupWidth
			pointY := y(value)
			out.WriteString(`<circle class="dr-chart-data" cx="` + chartNumber(x) + `" cy="` + chartNumber(pointY) + `" r="3.5" fill="` + color + `" stroke="#faf8f5" stroke-width="1.5"/>`)
			writeChartDataLabel(out, x, pointY-9-float64(series%3)*12, value, frame.format)
		}
	}
	out.WriteString(`</g>`)
}

func writeChartDataLabel(out *strings.Builder, x, y, value float64, format string) {
	out.WriteString(`<text class="dr-chart-data-label" x="` + chartNumber(x) + `" y="` + chartNumber(y) + `" text-anchor="middle" fill="#716c63" font-size="10">` + html.EscapeString(formatChartValue(value, format)) + `</text>`)
}

func formatChartValue(value float64, format string) string {
	if format == "percent" {
		return strconv.FormatFloat(value, 'f', -1, 64) + "%"
	}
	abs := math.Abs(value)
	decimals := 2
	if abs >= 100 || math.Abs(value-math.Round(value)) < 1e-9 {
		decimals = 0
	} else if abs >= 10 {
		decimals = 1
	}
	plain := strconv.FormatFloat(value, 'f', decimals, 64)
	parts := strings.Split(plain, ".")
	integer := parts[0]
	sign := ""
	if strings.HasPrefix(integer, "-") {
		sign = "-"
		integer = strings.TrimPrefix(integer, "-")
	}
	for i := len(integer) - 3; i > 0; i -= 3 {
		integer = integer[:i] + "," + integer[i:]
	}
	result := sign + integer
	if len(parts) == 2 {
		result += "." + parts[1]
	}
	return result
}

func chartNumber(value float64) string {
	return strconv.FormatFloat(value, 'f', 2, 64)
}
