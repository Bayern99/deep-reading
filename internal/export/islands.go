package export

import (
	"fmt"
	"math"
	"sort"
	"strconv"
	"strings"

	"deepread/internal/openuilang"
)

const (
	MaxIslandStates = 64
	MaxIslandBytes  = 128 * 1024
)

type islandDimension struct {
	target string
	values []any
	keys   []string
}

type islandState struct {
	key         string
	values      []any
	html        string
	transitions map[string]string
}

type islandResult struct {
	html     string
	warnings []string
	reactive bool
}

type islandEvaluator func(map[string]any) (*openuilang.Element, *openuilang.Session, error)

func bindingForControl(el *openuilang.Element) (*openuilang.Binding, bool) {
	if el == nil {
		return nil, false
	}
	name := ""
	switch el.Type {
	case "SegmentedControl", "RadioGroup", "Select", "Slider":
		name = "value"
	case "Checkbox":
		name = "checked"
	default:
		return nil, false
	}
	binding, ok := property(el.Props, name).(*openuilang.Binding)
	return binding, ok && binding != nil && binding.Target != ""
}

func reactiveAction(el *openuilang.Element) (*openuilang.ActionPlan, bool) {
	if el == nil || el.Type != "Button" && el.Type != "IconButton" && el.Type != "Pressable" {
		return nil, false
	}
	plan, ok := property(el.Props, "action").(*openuilang.ActionPlan)
	if !ok || plan == nil {
		return nil, false
	}
	reactive := false
	for _, step := range plan.Steps {
		if step.Type == "set" || step.Type == "reset" {
			reactive = true
		}
	}
	return plan, reactive
}

func isIslandControlElement(el *openuilang.Element) bool {
	if el == nil {
		return false
	}
	if _, ok := bindingForControl(el); ok {
		return true
	}
	_, ok := reactiveAction(el)
	return ok
}

func walkIslandElements(value any, visit func(*openuilang.Element)) {
	switch value := value.(type) {
	case []any:
		for _, item := range value {
			walkIslandElements(item, visit)
		}
	case *openuilang.Object:
		if value != nil {
			for _, key := range value.Keys {
				walkIslandElements(value.Values[key], visit)
			}
		}
	case *openuilang.Element:
		if value == nil {
			return
		}
		visit(value)
		if value.Props != nil {
			for _, key := range value.Props.Keys {
				walkIslandElements(value.Props.Values[key], visit)
			}
		}
	}
}

func islandValueKey(value any) string {
	switch value := value.(type) {
	case nil:
		return "null:"
	case string:
		return "string:" + value
	case float64:
		return "number:" + formatFloat(value)
	case bool:
		return "bool:" + strconv.FormatBool(value)
	default:
		return fmt.Sprintf("%T:%v", value, value)
	}
}

func unwrapIslandValue(value any) any {
	if object, ok := value.(*openuilang.Object); ok {
		if inner, exists := object.Get("value"); exists {
			return inner
		}
	}
	return value
}

func (d *islandDimension) add(value any) bool {
	value = unwrapIslandValue(value)
	key := islandValueKey(value)
	for _, existing := range d.keys {
		if existing == key {
			return false
		}
	}
	d.keys = append(d.keys, key)
	d.values = append(d.values, value)
	return true
}

func (d *islandDimension) index(value any) int {
	key := islandValueKey(unwrapIslandValue(value))
	for i, existing := range d.keys {
		if existing == key {
			return i
		}
	}
	return -1
}

func sliderDomain(el *openuilang.Element) ([]any, bool) {
	minimum, minOK := finiteNumber(property(el.Props, "min"))
	maximum, maxOK := finiteNumber(property(el.Props, "max"))
	step, stepOK := finiteNumber(property(el.Props, "step"))
	if !stepOK || step <= 0 {
		step = 1
	}
	if !minOK || !maxOK || maximum < minimum || step <= 0 {
		return nil, false
	}
	count := int(math.Floor((maximum-minimum)/step+1e-9)) + 1
	if count < 1 || count > 25 {
		return nil, false
	}
	precision := 0
	stepText := strconv.FormatFloat(step, 'f', -1, 64)
	if dot := strings.IndexByte(stepText, '.'); dot >= 0 {
		precision = len(stepText) - dot - 1
	}
	factor := math.Pow10(precision)
	values := make([]any, 0, count)
	for i := 0; i < count; i++ {
		value := minimum + float64(i)*step
		value = math.Round(value*factor) / factor
		if value > maximum+step*1e-9 {
			break
		}
		values = append(values, value)
	}
	return values, true
}

func buildReactiveIsland(id string, defaultSource *openuilang.Element, defaultSession *openuilang.Session, evaluate islandEvaluator, images *imageTransformer, noJS bool, popoverSeq *int) (islandResult, error) {
	var controls []*openuilang.Element
	var actions []*openuilang.Element
	walkIslandElements(defaultSource, func(el *openuilang.Element) {
		if _, ok := bindingForControl(el); ok {
			controls = append(controls, el)
		}
		if _, ok := reactiveAction(el); ok {
			actions = append(actions, el)
		}
	})
	if len(controls) == 0 && len(actions) == 0 {
		return islandResult{}, nil
	}
	result := islandResult{reactive: true}
	var dims []*islandDimension
	dimByTarget := map[string]int{}
	ensureDim := func(target string) *islandDimension {
		if index, ok := dimByTarget[target]; ok {
			return dims[index]
		}
		dim := &islandDimension{target: target}
		dimByTarget[target] = len(dims)
		dims = append(dims, dim)
		return dim
	}
	for _, control := range controls {
		binding, _ := bindingForControl(control)
		dim := ensureDim(binding.Target)
		switch control.Type {
		case "Slider":
			values, ok := sliderDomain(control)
			if !ok {
				return degradeIsland(id, defaultSource, defaultSession, controls, actions, dims, dimByTarget, images, popoverSeq, "slider exceeds 25 discrete values"), nil
			}
			for _, value := range values {
				dim.add(value)
			}
		case "Checkbox":
			dim.values, dim.keys = nil, nil
			dim.add(false)
			dim.add(true)
		default:
			for _, choice := range genChoices(property(control.Props, "options")) {
				dim.add(choice.value)
			}
		}
	}
	for _, action := range actions {
		plan, _ := reactiveAction(action)
		for _, step := range plan.Steps {
			if step.Type == "set" {
				ensureDim(step.Target)
			}
			for _, target := range step.Targets {
				ensureDim(target)
			}
		}
	}
	for _, dim := range dims {
		value, _ := defaultSession.Get(dim.target)
		dim.add(value)
	}

	product := func() int {
		total := 1
		for _, dim := range dims {
			if len(dim.values) == 0 {
				return 0
			}
			if total > MaxIslandStates/len(dim.values) {
				return MaxIslandStates + 1
			}
			total *= len(dim.values)
		}
		return total
	}
	degrade := func(reason string) (islandResult, error) {
		return degradeIsland(id, defaultSource, defaultSession, controls, actions, dims, dimByTarget, images, popoverSeq, reason), nil
	}
	if noJS {
		return staticIsland(id, defaultSource, defaultSession, controls, actions, dims, dimByTarget, images, false, popoverSeq), nil
	}
	if product() > MaxIslandStates {
		return degrade("state product exceeds 64")
	}

	actionIDs := make(map[*openuilang.Element]string, len(actions))
	for i, action := range actions {
		actionIDs[action] = "a" + strconv.Itoa(i)
	}
	var states []islandState
	for restart := 0; restart < MaxIslandStates+1; restart++ {
		if product() > MaxIslandStates {
			return degrade("action expansion exceeds 64")
		}
		states = states[:0]
		tuples := enumerateIslandTuples(dims, 0, nil)
		domainAdded := false
		for _, tuple := range tuples {
			state := islandState{values: append([]any(nil), tuple...), transitions: map[string]string{}}
			state.key = islandTupleKey(dims, tuple)
			values := islandValueMap(dims, tuple)
			source, _, err := evaluate(values)
			if err != nil || source == nil {
				return degrade("reactive evaluation failed")
			}
			var stateActions []*openuilang.Element
			walkIslandElements(source, func(el *openuilang.Element) {
				if _, ok := reactiveAction(el); ok {
					stateActions = append(stateActions, el)
				}
			})
			for i, action := range stateActions {
				if i >= len(actions) {
					break
				}
				plan, _ := reactiveAction(action)
				_, actionSession, err := evaluate(values)
				if err != nil || actionSession == nil {
					return degrade("reactive action evaluation failed")
				}
				actionSession.Trigger("", "", plan)
				next := make([]any, len(dims))
				for j, dim := range dims {
					value, _ := actionSession.Get(dim.target)
					next[j] = unwrapIslandValue(value)
					if dim.add(next[j]) {
						domainAdded = true
					}
				}
				if !domainAdded {
					state.transitions[actionIDs[actions[i]]] = islandTupleKey(dims, next)
				}
			}
			states = append(states, state)
		}
		if !domainAdded {
			break
		}
		if restart == MaxIslandStates {
			return degrade("action expansion did not converge")
		}
	}
	sort.SliceStable(states, func(i, j int) bool { return states[i].key < states[j].key })

	view := &islandView{id: id, enabled: true, controls: map[*openuilang.Element]islandControlInfo{}, actions: actionIDs}
	populateIslandControlInfo(view, controls, dims, dimByTarget, defaultSession)
	var templatesBuf strings.Builder
	for i := range states {
		values := islandValueMap(dims, states[i].values)
		source, session, err := evaluate(values)
		if err != nil || source == nil {
			return degrade("reactive rendering failed")
		}
		renderer := &genuiRenderer{images: images, session: session, island: view, skipControls: true, popoverSeq: popoverSeq}
		content, err := renderer.renderNodeList(property(source.Props, "children"), false)
		if err != nil {
			return islandResult{}, err
		}
		states[i].html = content
		templatesBuf.WriteString(`<template data-island="` + id + `" data-state="` + states[i].key + `">` + content + `</template>`)
		actionNames := make([]string, 0, len(states[i].transitions))
		for action := range states[i].transitions {
			actionNames = append(actionNames, action)
		}
		sort.Strings(actionNames)
		for _, action := range actionNames {
			target := states[i].transitions[action]
			templatesBuf.WriteString(`<span hidden data-island-transition="` + id + `" data-action="` + action + `" data-from="` + states[i].key + `" data-to="` + target + `"></span>`)
		}
		if templatesBuf.Len() > MaxIslandBytes {
			return degrade("serialized templates exceed 128 KiB")
		}
	}
	controlsHTML, err := renderIslandControls(defaultSource, defaultSession, controls, actions, view, images, popoverSeq)
	if err != nil {
		return islandResult{}, err
	}
	defaultTuple := make([]any, len(dims))
	for i, dim := range dims {
		value, _ := defaultSession.Get(dim.target)
		defaultTuple[i] = unwrapIslandValue(value)
	}
	defaultKey := islandTupleKey(dims, defaultTuple)
	defaultSourceState, defaultStateSession, err := evaluate(islandValueMap(dims, defaultTuple))
	if err != nil || defaultSourceState == nil {
		return degrade("default state evaluation failed")
	}
	defaultRenderer := &genuiRenderer{images: images, session: defaultStateSession, island: view, skipControls: true, popoverSeq: popoverSeq}
	defaultHTML, err := defaultRenderer.renderNodeList(property(defaultSourceState.Props, "children"), false)
	if err != nil {
		return islandResult{}, err
	}
	var out strings.Builder
	out.WriteString(`<div class="dr-island" data-island="` + id + `" data-state="` + defaultKey + `">`)
	out.WriteString(`<div class="dr-island-controls">` + controlsHTML + `</div>`)
	out.WriteString(`<div class="dr-island-output" data-island="` + id + `" data-state="` + defaultKey + `">` + defaultHTML + `</div>`)
	out.WriteString(templatesBuf.String())
	out.WriteString(`</div>`)
	result.html = out.String()
	return result, nil
}

func enumerateIslandTuples(dims []*islandDimension, index int, prefix []any) [][]any {
	if index == len(dims) {
		return [][]any{append([]any(nil), prefix...)}
	}
	var out [][]any
	for _, value := range dims[index].values {
		out = append(out, enumerateIslandTuples(dims, index+1, append(prefix, value))...)
	}
	return out
}

func islandTupleKey(dims []*islandDimension, values []any) string {
	parts := make([]string, len(dims))
	for i, dim := range dims {
		index := dim.index(values[i])
		if index < 0 {
			index = 0
		}
		parts[i] = strconv.Itoa(index)
	}
	return strings.Join(parts, ".")
}

func islandValueMap(dims []*islandDimension, values []any) map[string]any {
	out := make(map[string]any, len(dims))
	for i, dim := range dims {
		out[dim.target] = values[i]
	}
	return out
}

func populateIslandControlInfo(view *islandView, controls []*openuilang.Element, dims []*islandDimension, dimByTarget map[string]int, session *openuilang.Session) {
	for _, control := range controls {
		binding, _ := bindingForControl(control)
		dimension := dimByTarget[binding.Target]
		dim := dims[dimension]
		value, _ := session.Get(binding.Target)
		if len(dim.values) == 0 {
			dim.add(value)
		}
		info := islandControlInfo{dimension: dimension, selected: dim.index(value)}
		for _, value := range dim.values {
			info.values = append(info.values, showGenValue(value))
		}
		switch control.Type {
		case "Slider", "Checkbox":
		default:
			for _, choice := range genChoices(property(control.Props, "options")) {
				info.indices = append(info.indices, dim.index(choice.value))
			}
		}
		view.controls[control] = info
	}
}

func renderIslandControls(source *openuilang.Element, session *openuilang.Session, controls, actions []*openuilang.Element, view *islandView, images *imageTransformer, popoverSeq *int) (string, error) {
	renderer := &genuiRenderer{images: images, session: session, island: view, disableControls: !view.enabled, popoverSeq: popoverSeq}
	var out strings.Builder
	for _, control := range controls {
		rendered, err := renderer.renderNode(control, false)
		if err != nil {
			return "", err
		}
		out.WriteString(rendered)
	}
	for _, action := range actions {
		rendered, err := renderer.renderNode(action, false)
		if err != nil {
			return "", err
		}
		out.WriteString(rendered)
	}
	return out.String(), nil
}

func staticIsland(id string, source *openuilang.Element, session *openuilang.Session, controls, actions []*openuilang.Element, dims []*islandDimension, dimByTarget map[string]int, images *imageTransformer, enabled bool, popoverSeq *int) islandResult {
	view := &islandView{id: id, enabled: enabled, controls: map[*openuilang.Element]islandControlInfo{}, actions: map[*openuilang.Element]string{}}
	for i, action := range actions {
		view.actions[action] = "a" + strconv.Itoa(i)
	}
	populateIslandControlInfo(view, controls, dims, dimByTarget, session)
	controlsHTML, controlErr := renderIslandControls(source, session, controls, actions, view, images, popoverSeq)
	renderer := &genuiRenderer{images: images, session: session, island: view, skipControls: true, disableControls: !enabled, popoverSeq: popoverSeq}
	content, renderErr := renderer.renderNodeList(property(source.Props, "children"), false)
	if controlErr != nil || renderErr != nil {
		return islandResult{reactive: true, html: `<span class="dr-caption">Interactive view unavailable</span>`}
	}
	defaultValues := make([]any, len(dims))
	for i, dim := range dims {
		value, _ := session.Get(dim.target)
		defaultValues[i] = value
	}
	key := islandTupleKey(dims, defaultValues)
	return islandResult{reactive: true, html: `<div class="dr-island" data-island="` + id + `" data-state="` + key + `"><div class="dr-island-controls">` + controlsHTML + `</div><div class="dr-island-output" data-island="` + id + `" data-state="` + key + `">` + content + `</div></div>`}
}

func degradeIsland(id string, source *openuilang.Element, session *openuilang.Session, controls, actions []*openuilang.Element, dims []*islandDimension, dimByTarget map[string]int, images *imageTransformer, popoverSeq *int, reason string) islandResult {
	result := staticIsland(id, source, session, controls, actions, dims, dimByTarget, images, false, popoverSeq)
	result.reactive = true
	result.warnings = []string{fmt.Sprintf("REACTIVE_STATE_EXPLOSION: %s: %s", id, reason)}
	return result
}
