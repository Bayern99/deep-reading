package export

import (
	"fmt"
	"html"
	"math"
	"net/url"
	"regexp"
	"strconv"
	"strings"

	"deepread/internal/openuilang"
)

type islandControlInfo struct {
	dimension int
	indices   []int
	values    []string
	selected  int
}

type islandView struct {
	id       string
	enabled  bool
	controls map[*openuilang.Element]islandControlInfo
	actions  map[*openuilang.Element]string
}

type genuiRenderer struct {
	images          *imageTransformer
	session         *openuilang.Session
	island          *islandView
	skipControls    bool
	disableControls bool
	popoverSeq      *int
	sourceHandler   func(*openuilang.Element) (string, error)
	seen            map[*openuilang.Element]bool
}

func property(props *openuilang.Object, name string) any {
	if props == nil {
		return nil
	}
	return props.Values[name]
}

func stringProperty(props *openuilang.Object, name, fallback string) string {
	if value, ok := property(props, name).(string); ok {
		return value
	}
	return fallback
}

func boolProperty(props *openuilang.Object, name string) bool {
	value, _ := property(props, name).(bool)
	return value
}

func finiteNumber(value any) (float64, bool) {
	var n float64
	switch value := value.(type) {
	case float64:
		n = value
	case int:
		n = float64(value)
	case string:
		parsed, err := strconv.ParseFloat(strings.TrimSpace(value), 64)
		if err != nil {
			return 0, false
		}
		n = parsed
	default:
		return 0, false
	}
	return n, !math.IsNaN(n) && !math.IsInf(n, 0)
}

func formatFloat(value float64) string {
	if value == 0 {
		value = 0 // normalize negative zero
	}
	return strconv.FormatFloat(value, 'f', -1, 64)
}

func showGenValue(value any) string {
	switch value := value.(type) {
	case nil:
		return ""
	case string:
		return value
	case float64:
		return formatFloat(value)
	case bool:
		return strconv.FormatBool(value)
	case *openuilang.Object:
		if inner, ok := value.Get("value"); ok {
			return showGenValue(inner)
		}
	}
	return fmt.Sprint(value)
}

func flattenGen(value any) []any {
	switch value := value.(type) {
	case nil:
		return nil
	case []any:
		var out []any
		for _, item := range value {
			out = append(out, flattenGen(item)...)
		}
		return out
	default:
		return []any{value}
	}
}

func (r *genuiRenderer) bound(value any) any {
	binding, ok := value.(*openuilang.Binding)
	if !ok || r.session == nil {
		return value
	}
	resolved, _ := r.session.Get(binding.Target)
	if object, ok := resolved.(*openuilang.Object); ok {
		if inner, exists := object.Get("value"); exists {
			return inner
		}
	}
	return resolved
}

func renderNodeList(value any, inline bool) (string, error) {
	return (&genuiRenderer{}).renderNodeList(value, inline)
}

func renderNode(value any, inline bool) (string, error) {
	return (&genuiRenderer{}).renderNode(value, inline)
}

func renderElement(el *openuilang.Element, inline bool) (string, error) {
	return (&genuiRenderer{}).renderElement(el, inline)
}

func (r *genuiRenderer) renderNodeList(value any, inline bool) (string, error) {
	items, ok := value.([]any)
	if !ok {
		return "", nil
	}
	var out strings.Builder
	for _, item := range items {
		rendered, err := r.renderNodeDepth(item, inline, 1)
		if err != nil {
			return "", err
		}
		out.WriteString(rendered)
	}
	return out.String(), nil
}

func (r *genuiRenderer) renderNode(value any, inline bool) (string, error) {
	return r.renderNodeDepth(value, inline, 0)
}

func (r *genuiRenderer) renderNodeDepth(value any, inline bool, depth int) (string, error) {
	if depth > 128 {
		return `<span class="dr-caption">Component nesting limit reached</span>`, nil
	}
	switch value := value.(type) {
	case nil:
		return "", nil
	case string:
		return html.EscapeString(value), nil
	case float64:
		return formatFloat(value), nil
	case bool:
		return strconv.FormatBool(value), nil
	case []any:
		var out strings.Builder
		for _, item := range value {
			rendered, err := r.renderNodeDepth(item, inline, depth+1)
			if err != nil {
				return "", err
			}
			out.WriteString(rendered)
		}
		return out.String(), nil
	case *openuilang.Element:
		return r.renderElementDepth(value, inline, depth)
	case *openuilang.Object:
		return html.EscapeString(showGenValue(value)), nil
	default:
		return "", fmt.Errorf("unsupported OpenUI value %T", value)
	}
}

func (r *genuiRenderer) renderElement(el *openuilang.Element, inline bool) (string, error) {
	return r.renderElementDepth(el, inline, 0)
}

func (r *genuiRenderer) renderElementDepth(el *openuilang.Element, inline bool, depth int) (string, error) {
	if el == nil {
		return "", nil
	}
	if r.seen == nil {
		r.seen = map[*openuilang.Element]bool{}
	}
	if r.seen[el] {
		return "", nil
	}
	r.seen[el] = true
	defer delete(r.seen, el)
	if r.skipControls && r.island != nil && isIslandControlElement(el) {
		return "", nil
	}
	p := el.Props
	switch el.Type {
	case "Col", "Row", "Box", "Grid", "Card":
		return r.renderContainer(el)
	case "Divider":
		return `<hr class="dr-divider">` + "\n", nil
	case "Spacer":
		return `<span class="dr-spacer" aria-hidden="true"></span>`, nil
	case "Title":
		size := stringProperty(p, "size", "md")
		switch size {
		case "sm", "md", "lg", "xl", "2xl", "3xl":
		default:
			size = "md"
		}
		return `<h3 class="dr-title dr-title-` + size + `"` + colorStyle(stringProperty(p, "color", "")) + `>` + html.EscapeString(stringProperty(p, "text", "")) + `</h3>` + "\n", nil
	case "Text":
		return r.renderText(el, inline)
	case "Caption":
		return `<p class="dr-caption"` + colorStyle(stringProperty(p, "color", "")) + `>` + html.EscapeString(stringProperty(p, "text", "")) + `</p>` + "\n", nil
	case "Label":
		return `<div class="dr-label">` + html.EscapeString(stringProperty(p, "text", "")) + `</div>`, nil
	case "Badge":
		icon := ""
		if name := stringProperty(p, "icon", ""); name != "" {
			icon = renderGenIcon(name, "sm", stringProperty(p, "color", ""))
		}
		return `<span class="dr-badge dr-badge-` + safeClassToken(stringProperty(p, "color", "neutral"), "neutral") + `">` + icon + html.EscapeString(stringProperty(p, "text", "")) + `</span>`, nil
	case "Link":
		text := html.EscapeString(stringProperty(p, "text", ""))
		if href, ok := safeOpenUIURL(stringProperty(p, "url", "")); ok {
			return `<a class="dr-link" href="` + html.EscapeString(href) + `">` + text + `</a>`, nil
		}
		return text, nil
	case "ListItem":
		return r.renderStandaloneListItem(el)
	case "List":
		return r.renderList(el)
	case "Markdown":
		fragment, err := renderMarkdownWithImages(stringProperty(p, "text", ""), r.images)
		if err != nil {
			return "", err
		}
		return `<div class="dr-markdown">` + fragment + `</div>`, nil
	case "Quote":
		out := `<figure class="dr-quote"><blockquote>` + html.EscapeString(stringProperty(p, "text", "")) + `</blockquote>`
		if cite := stringProperty(p, "cite", ""); cite != "" {
			out += `<figcaption>` + html.EscapeString(cite) + `</figcaption>`
		}
		return out + `</figure>` + "\n", nil
	case "Code":
		if inline {
			return `<code class="dr-inline-code">` + html.EscapeString(stringProperty(p, "code", "")) + `</code>`, nil
		}
		language := safeClassToken(stringProperty(p, "language", ""), "")
		class := ""
		if language != "" {
			class = ` class="language-` + language + `"`
		}
		return `<pre class="dr-code"><code` + class + `>` + html.EscapeString(stringProperty(p, "code", "")) + `</code></pre>` + "\n", nil
	case "Source":
		if r.sourceHandler != nil {
			return r.sourceHandler(el)
		}
		children, err := r.renderNodeList(property(p, "children"), false)
		if err != nil {
			return "", err
		}
		var sources strings.Builder
		for _, raw := range flattenGen(property(p, "sources")) {
			sources.WriteString(`<span class="dr-source-id">§ ` + html.EscapeString(showGenValue(raw)) + `</span>`)
		}
		return `<div class="dr-source">` + children + `<div class="dr-sources">` + sources.String() + `</div></div>`, nil
	case "Table":
		return r.renderTable(el)
	case "Chart":
		return renderChart(el)
	case "Icon":
		return renderGenIcon(stringProperty(p, "name", ""), stringProperty(p, "size", "md"), stringProperty(p, "color", "")), nil
	case "Image":
		return r.renderImage(el)
	case "Svg":
		return r.renderSVG(el)
	case "G", "Circle", "Ellipse", "Rect", "Line", "Path", "Polyline", "Polygon", "SvgText":
		return r.renderSVGShape(el)
	case "Carousel":
		children, err := r.renderNodeList(property(p, "children"), false)
		style := ""
		if width, ok := finiteNumber(property(p, "itemWidth")); ok && width > 0 {
			style = ` style="--dr-carousel-width:` + formatFloat(math.Min(width, 1000)) + `px"`
		}
		return `<div class="dr-carousel"` + style + `>` + children + `</div>`, err
	case "Popover":
		return r.renderPopover(el)
	case "Button":
		return r.renderButton(el, false)
	case "IconButton":
		return r.renderButton(el, true)
	case "Pressable":
		return r.renderPressable(el)
	case "Form":
		children, err := r.renderNodeList(property(p, "children"), false)
		return `<form class="dr-form"><fieldset>` + children + `</fieldset></form>`, err
	case "Input":
		return r.renderInput(el, false)
	case "TextArea":
		return r.renderInput(el, true)
	case "Select":
		return r.renderSelect(el)
	case "Checkbox":
		return r.renderCheckbox(el)
	case "RadioGroup":
		return r.renderRadioGroup(el)
	case "SegmentedControl":
		return r.renderSegmented(el)
	case "Slider":
		return r.renderSlider(el)
	case "DatePicker":
		return r.renderDatePicker(el)
	case "Timer":
		return r.renderTimer(el)
	case "Flashcard":
		front, err := r.renderNodeDepth(property(p, "front"), true, depth+1)
		if err != nil {
			return "", err
		}
		back, err := r.renderNodeDepth(property(p, "back"), false, depth+1)
		if err != nil {
			return "", err
		}
		hint := ""
		if text := stringProperty(p, "hint", ""); text != "" {
			hint = `<span class="dr-caption">` + html.EscapeString(text) + `</span>`
		}
		return `<details class="dr-flashcard"><summary><span class="dr-flash-label">Front</span> ` + front + hint + `</summary><div class="dr-flash-back"><span class="dr-flash-label">Back</span>` + back + `</div></details>`, nil
	case "Celebration":
		if boolProperty(p, "when") {
			return `<span class="dr-celebration" role="img" aria-label="Celebration">✦ ✧ ✦</span>`, nil
		}
		return `<span class="dr-celebration" hidden aria-hidden="true">✦</span>`, nil
	default:
		return "", fmt.Errorf("unsupported component %q", el.Type)
	}
}

func safeClassToken(value, fallback string) string {
	if value == "" {
		return fallback
	}
	for _, r := range value {
		if !(r >= 'a' && r <= 'z' || r >= 'A' && r <= 'Z' || r >= '0' && r <= '9' || r == '-' || r == '_') {
			return fallback
		}
	}
	return value
}

func safeCSSLength(name string, value any) string {
	if n, ok := finiteNumber(value); ok && n >= 0 {
		return ";" + name + ":" + formatFloat(math.Min(n, 4096)) + "px"
	}
	if text, ok := value.(string); ok {
		for _, unit := range []string{"px", "%"} {
			if strings.HasSuffix(text, unit) {
				n, err := strconv.ParseFloat(strings.TrimSuffix(text, unit), 64)
				limit := 4096.0
				if unit == "%" {
					limit = 100
				}
				if err == nil && n >= 0 && n <= limit {
					return ";" + name + ":" + formatFloat(n) + unit
				}
			}
		}
	}
	return ""
}

func safeCSSRadius(value any) string {
	if name, ok := value.(string); ok {
		if n, exists := map[string]float64{"sm": 6, "md": 10, "lg": 14, "xl": 20, "full": 999}[name]; exists {
			return ";border-radius:" + formatFloat(n) + "px"
		}
	}
	if n, ok := finiteNumber(value); ok && n >= 0 {
		return ";border-radius:" + formatFloat(math.Min(n, 100)) + "px"
	}
	return ""
}

func safeFlexAlign(value string) string {
	switch value {
	case "start", "end":
		return "flex-" + value
	case "center", "stretch", "baseline":
		return value
	}
	return ""
}

func safeFlexJustify(value string) string {
	switch value {
	case "start", "end":
		return "flex-" + value
	case "center":
		return value
	case "between", "around", "evenly":
		return "space-" + value
	}
	return ""
}

func (r *genuiRenderer) renderContainer(el *openuilang.Element) (string, error) {
	p := el.Props
	class := "dr-col"
	switch el.Type {
	case "Row":
		class = "dr-row"
	case "Box":
		if stringProperty(p, "direction", "col") == "row" {
			class = "dr-row"
		}
	case "Grid":
		class = "dr-grid"
	case "Card":
		class = "dr-col dr-card"
		if stringProperty(p, "variant", "") == "soft" {
			class += " dr-card-soft"
		}
	}
	if boolProperty(p, "wrap") {
		class += " dr-wrap"
	}
	gap, _ := finiteNumber(property(p, "gap"))
	style := ";gap:" + formatFloat(math.Max(0, math.Min(gap, 64))*4) + "px"
	if padding, ok := finiteNumber(property(p, "padding")); ok && padding >= 0 {
		style += ";padding:" + formatFloat(math.Min(padding, 64)*4) + "px"
	}
	if align := safeFlexAlign(stringProperty(p, "align", "")); align != "" {
		style += ";align-items:" + align
	}
	if justify := safeFlexJustify(stringProperty(p, "justify", "")); justify != "" {
		style += ";justify-content:" + justify
	}
	if el.Type == "Grid" {
		columns, _ := finiteNumber(property(p, "columns"))
		if columns < 1 {
			columns = 2
		}
		style += ";--dr-grid-columns:" + strconv.Itoa(int(math.Min(columns, 12)+0.5))
		if minimum, ok := finiteNumber(property(p, "minChildWidth")); ok && minimum > 0 {
			style += ";grid-template-columns:repeat(auto-fit,minmax(min(100%," + formatFloat(math.Min(minimum, 1000)) + "px),1fr))"
		}
	}
	if background := stringProperty(p, "background", ""); background != "" {
		if color, ok := safeSVGColor(background); ok {
			style += ";background:" + color
		}
	}
	if boolProperty(p, "border") {
		style += ";border:1px solid var(--rule)"
	}
	style += safeCSSRadius(property(p, "radius"))
	style += safeCSSLength("width", property(p, "width")) + safeCSSLength("height", property(p, "height"))
	if flex, ok := finiteNumber(property(p, "flex")); ok && flex > 0 {
		style += ";flex:" + formatFloat(math.Min(flex, 100))
	}
	children, err := r.renderNodeList(property(p, "children"), false)
	return `<div class="` + class + `" style="` + strings.TrimPrefix(style, ";") + `">` + children + `</div>` + "\n", err
}

func (r *genuiRenderer) renderText(el *openuilang.Element, inline bool) (string, error) {
	p := el.Props
	classes := []string{"dr-text"}
	size := stringProperty(p, "size", "md")
	switch size {
	case "xs", "sm", "md", "lg":
	default:
		size = "md"
	}
	classes = append(classes, "dr-text-"+size)
	if weight := stringProperty(p, "weight", ""); weight == "medium" || weight == "semibold" {
		classes = append(classes, "dr-weight-"+weight)
	}
	if boolProperty(p, "italic") {
		classes = append(classes, "dr-italic")
	}
	if boolProperty(p, "lineThrough") {
		classes = append(classes, "dr-line-through")
	}
	if boolProperty(p, "tabularNums") {
		classes = append(classes, "dr-tabular")
	}
	style := colorStyle(stringProperty(p, "color", ""))
	if maxLines, ok := finiteNumber(property(p, "maxLines")); ok && maxLines > 0 {
		if style == "" {
			style = ` style="`
		} else {
			style = strings.TrimSuffix(style, `"`)
		}
		style += ";display:-webkit-box;-webkit-line-clamp:" + strconv.Itoa(int(math.Min(maxLines, 100))) + ";-webkit-box-orient:vertical;overflow:hidden\""
	}
	content := ""
	switch text := property(p, "text").(type) {
	case string:
		content = html.EscapeString(text)
	case []any:
		var err error
		content, err = r.renderNodeDepth(text, true, 1)
		if err != nil {
			return "", err
		}
	default:
		content = html.EscapeString(showGenValue(r.bound(text)))
	}
	tag, suffix := "p", "\n"
	if inline || len(classes) > 0 && property(p, "text") != nil {
		if _, isString := property(p, "text").(string); !isString {
			tag, suffix = "span", ""
		}
	}
	return `<` + tag + ` class="` + strings.Join(classes, " ") + `"` + style + `>` + content + `</` + tag + `>` + suffix, nil
}

func (r *genuiRenderer) renderList(el *openuilang.Element) (string, error) {
	p := el.Props
	marker := stringProperty(p, "marker", "bullet")
	tag, class := "ul", "dr-list"
	if marker == "number" {
		tag = "ol"
	}
	if marker == "none" {
		class += " dr-list-none"
	}
	if boolProperty(p, "timeline") {
		class += " dr-timeline"
		tag = "ol"
	}
	var out strings.Builder
	out.WriteString(`<` + tag + ` class="` + class + `">`)
	for _, item := range flattenGen(property(p, "items")) {
		if child, ok := item.(*openuilang.Element); ok && child != nil && child.Type == "ListItem" {
			rendered, err := r.renderListItem(child)
			if err != nil {
				return "", err
			}
			out.WriteString(rendered)
			continue
		}
		rendered, err := r.renderNodeDepth(item, true, 1)
		if err != nil {
			return "", err
		}
		out.WriteString(`<li>` + rendered + `</li>`)
	}
	out.WriteString(`</` + tag + `>` + "\n")
	return out.String(), nil
}

func (r *genuiRenderer) renderListItem(el *openuilang.Element) (string, error) {
	p := el.Props
	var out strings.Builder
	out.WriteString(`<li class="dr-list-item">`)
	if marker := stringProperty(p, "marker", ""); marker != "" {
		out.WriteString(`<span class="dr-list-marker">` + html.EscapeString(marker) + `</span>`)
	}
	out.WriteString(`<div class="dr-list-content"><div class="dr-list-title">` + html.EscapeString(stringProperty(p, "title", "")) + `</div>`)
	if description := stringProperty(p, "description", ""); description != "" {
		out.WriteString(`<div class="dr-list-description">` + html.EscapeString(description) + `</div>`)
	}
	children, err := r.renderNodeList(property(p, "children"), false)
	if err != nil {
		return "", err
	}
	out.WriteString(children + `</div></li>`)
	return out.String(), nil
}

func (r *genuiRenderer) renderStandaloneListItem(el *openuilang.Element) (string, error) {
	item, err := r.renderListItem(el)
	return `<ul class="dr-list dr-list-none">` + item + `</ul>` + "\n", err
}

func (r *genuiRenderer) renderTable(el *openuilang.Element) (string, error) {
	p := el.Props
	columns, _ := property(p, "columns").([]any)
	rows, _ := property(p, "rows").([]any)
	numeric := make([]bool, len(columns))
	for col := range columns {
		numeric[col] = true
		hasValue := false
		for _, rawRow := range rows {
			row, _ := rawRow.([]any)
			if col >= len(row) || row[col] == nil {
				continue
			}
			if _, ok := row[col].(float64); !ok {
				numeric[col] = false
				break
			}
			hasValue = true
		}
		numeric[col] = numeric[col] && hasValue
	}
	wide := ""
	if len(columns) >= 4 {
		wide = " dr-table-wide"
	}
	var out strings.Builder
	out.WriteString(`<div class="dr-table-wrap" role="region" tabindex="0"><table class="dr-table` + wide + `"><thead><tr>`)
	for i, column := range columns {
		class := ""
		if i < len(numeric) && numeric[i] {
			class = ` class="dr-num"`
		}
		out.WriteString(`<th scope="col"` + class + `>` + html.EscapeString(showGenValue(column)) + `</th>`)
	}
	out.WriteString(`</tr></thead><tbody>`)
	for _, rawRow := range rows {
		row, ok := rawRow.([]any)
		if !ok {
			return "", fmt.Errorf("Table row must be an array, got %T", rawRow)
		}
		out.WriteString(`<tr>`)
		for i := range columns {
			var cell any
			if i < len(row) {
				cell = row[i]
			}
			class := ""
			if i < len(numeric) && numeric[i] {
				class = ` class="dr-num"`
			}
			out.WriteString(`<td` + class + `>`)
			rendered, err := r.renderNodeDepth(cell, true, 1)
			if err != nil {
				return "", err
			}
			out.WriteString(rendered + `</td>`)
		}
		out.WriteString(`</tr>`)
	}
	out.WriteString(`</tbody></table></div>` + "\n")
	return out.String(), nil
}

func safeOpenUIURL(raw string) (string, bool) {
	parsed, err := url.Parse(strings.TrimSpace(raw))
	if err != nil {
		return "", false
	}
	switch strings.ToLower(parsed.Scheme) {
	case "http", "https", "mailto":
		return raw, true
	default:
		return "", false
	}
}

func (r *genuiRenderer) renderImage(el *openuilang.Element) (string, error) {
	p := el.Props
	src := stringProperty(p, "src", "")
	if r.images != nil {
		resolved, err := r.images.resolveDestination(src)
		if err != nil {
			return "", err
		}
		src = resolved
	} else if _, ok := safeOpenUIURL(src); !ok && strings.HasPrefix(strings.ToLower(src), "data:") {
		return `<span class="dr-image-missing" role="img">Image unavailable</span>`, nil
	}
	style := safeCSSRadius(property(p, "radius"))
	if ratio, ok := finiteNumber(property(p, "aspectRatio")); ok && ratio >= 0.2 && ratio <= 8 {
		style += ";aspect-ratio:" + formatFloat(ratio)
	}
	fit := "cover"
	if stringProperty(p, "fit", "") == "contain" {
		fit = "contain"
	}
	style += ";object-fit:" + fit
	return `<img class="dr-image" src="` + html.EscapeString(src) + `" alt="` + html.EscapeString(stringProperty(p, "alt", "")) + `" style="` + strings.TrimPrefix(style, ";") + `">`, nil
}

var iconPaths = map[string]string{
	"calendar": "M7 3v3M17 3v3M4 9h16M5 5h14a1 1 0 0 1 1 1v13H4V6a1 1 0 0 1 1-1Z",
	"check":    "m5 12 4 4L19 6", "check-circle": "m8 12 3 3 5-6M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z",
	"arrow-right": "M4 12h15m-5-5 5 5-5 5", "info": "M12 11v6m0-10v1M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z",
	"warning": "M12 3 2.5 20h19L12 3Zm0 6v5m0 3v1", "chart-bar": "M4 20V10h4v10m4 0V4h4v16m4 0v-7h-4",
	"book-open": "M3 5c4-1 7 0 9 2 2-2 5-3 9-2v14c-4-1-7 0-9 2-2-2-5-3-9-2V5Zm9 2v14",
	"sparkle":   "m12 2 2.2 6.8L21 11l-6.8 2.2L12 20l-2.2-6.8L3 11l6.8-2.2L12 2Z",
	"globe":     "M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-18 0h18M12 3c3 3 3 15 0 18-3-3-3-15 0-18Z",
}

func renderGenIcon(name, size, color string) string {
	path, ok := iconPaths[strings.ToLower(strings.TrimSpace(name))]
	if !ok {
		path = "M12 4v16M4 12h16M6 6l12 12M18 6 6 18"
	}
	pixels := map[string]int{"sm": 16, "md": 20, "lg": 24, "xl": 32}[size]
	if pixels == 0 {
		pixels = 20
	}
	style := ""
	if paint, ok := safeSVGColor(color); ok {
		style = ` style="color:` + html.EscapeString(paint) + `"`
	}
	return `<svg class="dr-icon" width="` + strconv.Itoa(pixels) + `" height="` + strconv.Itoa(pixels) + `" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"` + style + `><path d="` + path + `"/></svg>`
}

func (r *genuiRenderer) nextPopoverID() string {
	if r.popoverSeq == nil {
		n := 0
		r.popoverSeq = &n
	}
	*r.popoverSeq = *r.popoverSeq + 1
	return fmt.Sprintf("dr-popover-%d", *r.popoverSeq)
}

func (r *genuiRenderer) renderPopover(el *openuilang.Element) (string, error) {
	id := r.nextPopoverID()
	trigger, err := r.renderNodeDepth(property(el.Props, "trigger"), true, 1)
	if err != nil {
		return "", err
	}
	content, err := r.renderNodeDepth(property(el.Props, "content"), false, 1)
	if err != nil {
		return "", err
	}
	return `<span class="dr-popover"><span class="dr-popover-trigger-content">` + trigger + `</span><button type="button" class="dr-popover-trigger" popovertarget="` + id + `" aria-label="Show details">详情</button><aside class="dr-popover-content" popover id="` + id + `">` + content + `</aside></span>`, nil
}

func (r *genuiRenderer) control(el *openuilang.Element) (islandControlInfo, bool) {
	if r.island == nil {
		return islandControlInfo{}, false
	}
	info, ok := r.island.controls[el]
	return info, ok
}

func (r *genuiRenderer) controlAttrs(el *openuilang.Element) string {
	info, ok := r.control(el)
	if !ok || r.island == nil {
		return ""
	}
	return ` data-island="` + r.island.id + `" data-control="` + strconv.Itoa(info.dimension) + `"`
}

func (r *genuiRenderer) controlsDisabled() bool {
	return r.disableControls || r.island != nil && !r.island.enabled
}

func disabledAttr(disabled bool) string {
	if disabled {
		return ` disabled aria-disabled="true"`
	}
	return ""
}

type genChoice struct{ value, label, description string }

func genChoices(value any) []genChoice {
	var out []genChoice
	for _, item := range flattenGen(value) {
		switch item := item.(type) {
		case *openuilang.Object:
			if item == nil {
				continue
			}
			label := showGenValue(item.Values["label"])
			value := showGenValue(item.Values["value"])
			if label == "" {
				label = value
			}
			if value == "" {
				value = label
			}
			out = append(out, genChoice{value: value, label: label, description: showGenValue(item.Values["description"])})
		default:
			text := showGenValue(item)
			if text != "" {
				out = append(out, genChoice{value: text, label: text})
			}
		}
	}
	return out
}

func fieldLabel(label string) string {
	if label == "" {
		return ""
	}
	return `<span class="dr-label">` + html.EscapeString(label) + `</span>`
}

func (r *genuiRenderer) actionFor(el *openuilang.Element) (string, bool) {
	if r.island == nil {
		return "", false
	}
	id, ok := r.island.actions[el]
	return id, ok
}

func (r *genuiRenderer) renderButton(el *openuilang.Element, iconOnly bool) (string, error) {
	p := el.Props
	label := stringProperty(p, "label", "")
	content := html.EscapeString(label)
	if icon := stringProperty(p, "icon", ""); icon != "" {
		content = renderGenIcon(icon, "sm", "") + `<span` + func() string {
			if iconOnly {
				return ` class="dr-sr-only"`
			}
			return ""
		}() + `>` + content + `</span>`
	}
	class := "dr-button dr-button-" + safeClassToken(stringProperty(p, "variant", "solid"), "solid")
	if boolProperty(p, "block") {
		class += " dr-block"
	}
	action := property(p, "action")
	if href, ok := action.(*openuilang.ActionPlan); ok && len(href.Steps) == 1 && href.Steps[0].Type == "open_url" {
		if target, safe := safeOpenUIURL(href.Steps[0].URL); safe {
			return `<a class="` + class + `" href="` + html.EscapeString(target) + `">` + content + `</a>`, nil
		}
	}
	attrs := ""
	if id, ok := r.actionFor(el); ok {
		attrs = ` data-island="` + r.island.id + `" data-action="` + id + `"`
	}
	disabled := r.controlsDisabled() || boolProperty(p, "disabled") || action == nil || attrs == ""
	return `<button type="button" class="` + class + `"` + attrs + disabledAttr(disabled) + ` aria-label="` + html.EscapeString(label) + `">` + content + `</button>`, nil
}

func (r *genuiRenderer) renderPressable(el *openuilang.Element) (string, error) {
	children, err := r.renderNodeDepth(property(el.Props, "children"), false, 1)
	if err != nil {
		return "", err
	}
	attrs := ""
	if id, ok := r.actionFor(el); ok {
		attrs = ` data-island="` + r.island.id + `" data-action="` + id + `"`
	}
	style := ""
	if padding, ok := finiteNumber(property(el.Props, "padding")); ok && padding >= 0 {
		style = ` style="padding:` + formatFloat(math.Min(padding, 32)*4) + `px"`
	}
	disabled := r.controlsDisabled() || attrs == ""
	return `<button type="button" class="dr-pressable" aria-pressed="` + strconv.FormatBool(boolProperty(el.Props, "selected")) + `"` + attrs + style + disabledAttr(disabled) + `>` + children + `</button>`, nil
}

func (r *genuiRenderer) renderInput(el *openuilang.Element, multiline bool) (string, error) {
	p := el.Props
	value := showGenValue(r.bound(property(p, "value")))
	label := fieldLabel(stringProperty(p, "label", ""))
	placeholder := stringProperty(p, "placeholder", "")
	if multiline {
		rows := 4
		if n, ok := finiteNumber(property(p, "rows")); ok {
			rows = int(math.Max(2, math.Min(n, 20)))
		}
		return `<label class="dr-control">` + label + `<textarea rows="` + strconv.Itoa(rows) + `" placeholder="` + html.EscapeString(placeholder) + `"` + disabledAttr(true) + `>` + html.EscapeString(value) + `</textarea></label>`, nil
	}
	typeName := "text"
	if stringProperty(p, "type", "") == "number" {
		typeName = "number"
	}
	return `<label class="dr-control">` + label + `<input type="` + typeName + `" value="` + html.EscapeString(value) + `" placeholder="` + html.EscapeString(placeholder) + `"` + disabledAttr(true) + `></label>`, nil
}

func (r *genuiRenderer) choiceIndices(info islandControlInfo, choices []genChoice) []int {
	if len(info.indices) == len(choices) {
		return info.indices
	}
	indices := make([]int, len(choices))
	for i := range indices {
		indices[i] = i
	}
	return indices
}

func (r *genuiRenderer) renderSelect(el *openuilang.Element) (string, error) {
	p := el.Props
	selected := showGenValue(r.bound(property(p, "value")))
	choices := genChoices(property(p, "options"))
	info, reactive := r.control(el)
	indices := r.choiceIndices(info, choices)
	var out strings.Builder
	out.WriteString(`<label class="dr-control">` + fieldLabel(stringProperty(p, "label", "")) + `<select` + r.controlAttrs(el) + disabledAttr(!reactive || r.controlsDisabled()) + `>`)
	if placeholder := stringProperty(p, "placeholder", ""); placeholder != "" {
		out.WriteString(`<option value="" disabled>` + html.EscapeString(placeholder) + `</option>`)
	}
	for i, choice := range choices {
		value := strconv.Itoa(i)
		if reactive {
			value = strconv.Itoa(indices[i])
		}
		selectedAttr := ""
		if choice.value == selected {
			selectedAttr = ` selected`
		}
		out.WriteString(`<option value="` + value + `"` + selectedAttr + `>` + html.EscapeString(choice.label) + `</option>`)
	}
	out.WriteString(`</select></label>`)
	return out.String(), nil
}

func (r *genuiRenderer) renderCheckbox(el *openuilang.Element) (string, error) {
	checked, _ := r.bound(property(el.Props, "checked")).(bool)
	_, reactive := r.control(el)
	class := ""
	if checked && boolProperty(el.Props, "lineThrough") {
		class = ` class="dr-checked-line"`
	}
	return `<label class="dr-choice"><input type="checkbox"` + r.controlAttrs(el) + func() string {
		if checked {
			return ` checked`
		}
		return ""
	}() + disabledAttr(!reactive || r.controlsDisabled()) + `><span` + class + `>` + html.EscapeString(stringProperty(el.Props, "label", "")) + `</span></label>`, nil
}

func (r *genuiRenderer) renderRadioGroup(el *openuilang.Element) (string, error) {
	p := el.Props
	selected := showGenValue(r.bound(property(p, "value")))
	choices := genChoices(property(p, "options"))
	info, reactive := r.control(el)
	indices := r.choiceIndices(info, choices)
	var out strings.Builder
	out.WriteString(`<fieldset class="dr-control dr-radio-group"><legend>` + html.EscapeString(stringProperty(p, "label", "")) + `</legend>`)
	for i, choice := range choices {
		value := strconv.Itoa(i)
		if reactive {
			value = strconv.Itoa(indices[i])
		}
		checked := ""
		if choice.value == selected {
			checked = ` checked`
		}
		description := ""
		if choice.description != "" {
			description = `<small>` + html.EscapeString(choice.description) + `</small>`
		}
		out.WriteString(`<label class="dr-choice"><input type="radio" name="` + r.islandID() + `-` + strconv.Itoa(info.dimension) + `" value="` + value + `"` + r.controlAttrs(el) + checked + disabledAttr(!reactive || r.controlsDisabled()) + `><span>` + html.EscapeString(choice.label) + description + `</span></label>`)
	}
	out.WriteString(`</fieldset>`)
	return out.String(), nil
}

func (r *genuiRenderer) islandID() string {
	if r.island == nil {
		return "dr-static"
	}
	return r.island.id
}

func (r *genuiRenderer) renderSegmented(el *openuilang.Element) (string, error) {
	selected := showGenValue(r.bound(property(el.Props, "value")))
	choices := genChoices(property(el.Props, "options"))
	info, reactive := r.control(el)
	indices := r.choiceIndices(info, choices)
	var out strings.Builder
	out.WriteString(`<div class="dr-segments" role="group">`)
	for i, choice := range choices {
		index := i
		if reactive {
			index = indices[i]
		}
		pressed := choice.value == selected
		out.WriteString(`<button type="button" class="dr-segment" data-value-index="` + strconv.Itoa(index) + `" value="` + strconv.Itoa(index) + `" aria-pressed="` + strconv.FormatBool(pressed) + `"` + r.controlAttrs(el) + disabledAttr(!reactive || r.controlsDisabled()) + `>` + html.EscapeString(choice.label) + `</button>`)
	}
	out.WriteString(`</div>`)
	return out.String(), nil
}

func (r *genuiRenderer) renderSlider(el *openuilang.Element) (string, error) {
	p := el.Props
	minimum, _ := finiteNumber(property(p, "min"))
	maximum, _ := finiteNumber(property(p, "max"))
	step, ok := finiteNumber(property(p, "step"))
	if !ok || step <= 0 {
		step = 1
	}
	if maximum <= minimum {
		maximum = minimum + step
	}
	current, ok := finiteNumber(r.bound(property(p, "value")))
	if !ok {
		current = minimum
	}
	info, reactive := r.control(el)
	inputMin, inputMax, inputStep, inputValue := formatFloat(minimum), formatFloat(maximum), formatFloat(step), formatFloat(current)
	if reactive {
		inputMin, inputMax, inputStep, inputValue = "0", strconv.Itoa(len(info.values)-1), "1", strconv.Itoa(info.selected)
	}
	unit := stringProperty(p, "unit", "")
	valueLabel := formatFloat(current)
	if unit == "%" {
		valueLabel += "%"
	} else if unit != "" {
		valueLabel = unit + valueLabel
	}
	return `<label class="dr-control dr-slider"><span class="dr-slider-heading">` + fieldLabel(stringProperty(p, "label", "")) + `<output>` + html.EscapeString(valueLabel) + `</output></span><input type="range" min="` + inputMin + `" max="` + inputMax + `" step="` + inputStep + `" value="` + inputValue + `" aria-valuetext="` + html.EscapeString(valueLabel) + `"` + r.controlAttrs(el) + disabledAttr(!reactive || r.controlsDisabled()) + `></label>`, nil
}

func (r *genuiRenderer) renderDatePicker(el *openuilang.Element) (string, error) {
	value := showGenValue(r.bound(property(el.Props, "value")))
	return `<label class="dr-control">` + fieldLabel(stringProperty(el.Props, "label", "")) + `<input type="date" value="` + html.EscapeString(value) + `" min="` + html.EscapeString(stringProperty(el.Props, "min", "")) + `" max="` + html.EscapeString(stringProperty(el.Props, "max", "")) + `"` + disabledAttr(true) + `></label>`, nil
}

func (r *genuiRenderer) renderTimer(el *openuilang.Element) (string, error) {
	seconds, _ := finiteNumber(r.bound(property(el.Props, "seconds")))
	seconds = math.Max(0, seconds)
	whole := int(seconds)
	clock := fmt.Sprintf("%02d:%02d", whole/60, whole%60)
	if whole >= 3600 {
		clock = fmt.Sprintf("%d:%02d:%02d", whole/3600, whole/60%60, whole%60)
	}
	return `<div class="dr-control">` + fieldLabel(stringProperty(el.Props, "label", "")) + `<time class="dr-timer">` + clock + `</time></div>`, nil
}

var safeHexColorRE = regexp.MustCompile(`^#[0-9A-Fa-f]{3,8}$`)
var safeNamedColorRE = regexp.MustCompile(`^[A-Za-z]+$`)
var safeFunctionalColorRE = regexp.MustCompile(`^(?i:(?:rgb|rgba|hsl|hsla))\([0-9.,%+\- /]+\)$`)

func colorStyle(color string) string {
	color = strings.TrimSpace(color)
	if color == "" {
		return ""
	}
	if paint, ok := safeSVGColor(color); ok {
		return ` style="color:` + html.EscapeString(paint) + `"`
	}
	return ""
}
