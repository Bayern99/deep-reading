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
	xValues      []float64
	seriesLabels map[string]string
}

func renderChart(el *openuilang.Element) (string, error) {
	frame, err := readChartFrame(el)
	if err != nil {
		return "", err
	}
	switch frame.kind {
	case "bar", "line", "area", "pie", "donut", "scatter":
	default:
		return "", fmt.Errorf("Chart type %q is not supported", frame.kind)
	}
	if frame.kind == "pie" || frame.kind == "donut" {
		return renderPieChart(frame)
	}
	if frame.kind == "scatter" {
		return renderScatterChart(frame)
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
		xValue, ok := row.Values[frame.xKey].(float64)
		if !ok || math.IsNaN(xValue) || math.IsInf(xValue, 0) {
			xValue = float64(i)
		}
		frame.xValues = append(frame.xValues, xValue)
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
		if frame.kind == "line" || frame.kind == "area" {
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
		var areaPoints strings.Builder
		for row, value := range frame.values[series] {
			x := left + (float64(row)+0.5)*groupWidth
			pointY := y(value)
			if row == 0 {
				path.WriteString("M ")
			} else {
				path.WriteString(" L ")
			}
			path.WriteString(chartNumber(x) + " " + chartNumber(pointY))
			areaPoints.WriteString(chartNumber(x) + "," + chartNumber(pointY) + " ")
		}
		if frame.kind == "area" && len(frame.values[series]) > 0 {
			firstX := left + 0.5*groupWidth
			lastX := left + (float64(len(frame.values[series]))-0.5)*groupWidth
			out.WriteString(`<polygon points="` + areaPoints.String() + chartNumber(lastX) + "," + chartNumber(y(0)) + " " + chartNumber(firstX) + "," + chartNumber(y(0)) + `" fill="` + color + `" opacity=".16"/>`)
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

func renderPieChart(frame *chartFrame) (string, error) {
	height := float64(frame.height)
	var out strings.Builder
	out.WriteString(`<figure class="dr-chart dr-chart-` + frame.kind + `"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 ` + strconv.Itoa(frame.height) + `" role="img" aria-label="` + frame.kind + ` chart"><title>` + frame.kind + ` chart</title>`)
	if len(frame.series) == 0 || len(frame.values) == 0 {
		out.WriteString(`<text x="300" y="100" text-anchor="middle" fill="#716c63">No data</text></svg></figure>`)
		return out.String(), nil
	}
	values := frame.values[0]
	total := 0.0
	for _, value := range values {
		total += math.Max(0, value)
	}
	cx, cy, radius := 300.0, height/2, math.Min(100, height/2-20)
	start := -math.Pi / 2
	for i, value := range values {
		if value <= 0 || total <= 0 {
			continue
		}
		angle := value / total * 2 * math.Pi
		color := chartPalette[i%len(chartPalette)]
		label := ""
		if i < len(frame.labels) {
			label = frame.labels[i]
		}
		formatted := formatChartValue(value, frame.format)
		if frame.format == "percent" {
			formatted = formatChartValue(value/total*100, frame.format)
		}
		if angle >= 2*math.Pi-1e-9 {
			out.WriteString(`<circle cx="` + chartNumber(cx) + `" cy="` + chartNumber(cy) + `" r="` + chartNumber(radius) + `" fill="` + color + `"><title>` + html.EscapeString(label+": "+formatted) + `</title></circle>`)
			continue
		}
		end := start + angle
		x1, y1 := cx+radius*math.Cos(start), cy+radius*math.Sin(start)
		x2, y2 := cx+radius*math.Cos(end), cy+radius*math.Sin(end)
		large := 0
		if angle > math.Pi {
			large = 1
		}
		out.WriteString(`<path d="M ` + chartNumber(cx) + " " + chartNumber(cy) + " L " + chartNumber(x1) + " " + chartNumber(y1) + " A " + chartNumber(radius) + " " + chartNumber(radius) + " 0 " + strconv.Itoa(large) + " 1 " + chartNumber(x2) + " " + chartNumber(y2) + ` Z" fill="` + color + `"><title>` + html.EscapeString(label+": "+formatted) + `</title></path>`)
		start = end
	}
	if frame.kind == "donut" {
		out.WriteString(`<circle cx="` + chartNumber(cx) + `" cy="` + chartNumber(cy) + `" r="` + chartNumber(radius*0.56) + `" fill="#faf8f5"/>`)
	}
	out.WriteString(`</svg><figcaption class="dr-chart-legend">`)
	for i, label := range frame.labels {
		out.WriteString(`<span><i style="background:` + chartPalette[i%len(chartPalette)] + `"></i>` + html.EscapeString(label) + `</span>`)
	}
	out.WriteString(`</figcaption></figure>`)
	return out.String(), nil
}

func renderScatterChart(frame *chartFrame) (string, error) {
	const width = 600.0
	height := float64(frame.height)
	left, right, top, bottom := 58.0, 20.0, 46.0, 48.0
	plotWidth, plotHeight := width-left-right, height-top-bottom
	minY, maxY := chartDomain(frame)
	ticks := chartTicks(minY, maxY)
	minY, maxY = ticks[0], ticks[len(ticks)-1]
	minX, maxX := 0.0, 1.0
	if len(frame.xValues) > 0 {
		minX, maxX = frame.xValues[0], frame.xValues[0]
		for _, value := range frame.xValues {
			minX, maxX = math.Min(minX, value), math.Max(maxX, value)
		}
	}
	if minX == maxX {
		maxX = minX + 1
	}
	x := func(value float64) float64 { return left + (value-minX)/(maxX-minX)*plotWidth }
	y := func(value float64) float64 { return top + (maxY-value)/(maxY-minY)*plotHeight }
	var out strings.Builder
	out.WriteString(`<figure class="dr-chart dr-chart-scatter"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 ` + strconv.Itoa(frame.height) + `" role="img" aria-label="scatter chart"><title>scatter chart</title>`)
	renderChartLegend(&out, frame, left)
	for _, tick := range ticks {
		out.WriteString(`<line x1="` + chartNumber(left) + `" y1="` + chartNumber(y(tick)) + `" x2="` + chartNumber(width-right) + `" y2="` + chartNumber(y(tick)) + `" stroke="#e5e2dc"/><text x="` + chartNumber(left-8) + `" y="` + chartNumber(y(tick)+4) + `" text-anchor="end" fill="#716c63" font-size="11">` + html.EscapeString(formatChartValue(tick, frame.format)) + `</text>`)
	}
	for series := range frame.series {
		for row, value := range frame.values[series] {
			label := frame.series[series] + ": " + formatChartValue(value, frame.format)
			out.WriteString(`<circle class="dr-chart-data" cx="` + chartNumber(x(frame.xValues[row])) + `" cy="` + chartNumber(y(value)) + `" r="4" fill="` + chartPalette[series%len(chartPalette)] + `" opacity=".85"><title>` + html.EscapeString(label) + `</title></circle>`)
		}
	}
	for _, value := range []float64{minX, (minX + maxX) / 2, maxX} {
		out.WriteString(`<text x="` + chartNumber(x(value)) + `" y="` + chartNumber(top+plotHeight+22) + `" text-anchor="middle" fill="#716c63" font-size="11">` + html.EscapeString(formatChartValue(value, "number")) + `</text>`)
	}
	out.WriteString(`</svg></figure>`)
	return out.String(), nil
}
