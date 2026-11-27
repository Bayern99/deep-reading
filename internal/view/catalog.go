package view

import (
	"encoding/json"
	"fmt"
	"strings"

	"deepread/internal/bundle"
	"deepread/internal/genuikit"
)

// AllowedComponents is the deliberately narrowed v0.2 margin-reading whitelist.
// Canvas validation instead derives its whitelist from genuikit's full catalog.
var AllowedComponents = map[string]bool{
	"Col":      true,
	"Source":   true,
	"Title":    true,
	"Text":     true,
	"Caption":  true,
	"Quote":    true,
	"List":     true,
	"ListItem": true,
	"Table":    true,
	"Chart":    true,
}

var allowedComponentOrder = []string{
	"Col", "Source", "Title", "Text", "Caption", "Quote", "Table", "Chart", "List", "ListItem",
}

// AllowedChartTypes restricts the legacy margin profile to static bar and line charts.
var AllowedChartTypes = map[string]bool{
	"bar":  true,
	"line": true,
}

// CatalogText returns the default full reading-canvas contract.
func CatalogText() (string, error) {
	return CatalogTextFor(bundle.ProfileCanvas)
}

// CatalogTextFor builds either the full v0.3 canvas catalog or the byte-compatible
// v0.2 margin catalog. All component signatures come from genuikit's catalog.
func CatalogTextFor(profile string) (string, error) {
	if profile == "" {
		profile = bundle.ProfileCanvas
	}
	switch profile {
	case bundle.ProfileMargin:
		return marginCatalogText()
	case bundle.ProfileCanvas:
		return canvasCatalogText(), nil
	default:
		return "", fmt.Errorf("unknown view profile %q (expected canvas or margin)", profile)
	}
}

func canvasCatalogText() string {
	var b strings.Builder
	b.WriteString("# DeepRead OpenUI Lang Contract (Canvas Profile, Mark Go Go v3)\n\n")
	b.WriteString("Build a **full-information structured reading canvas** — eliminate dense walls of prose WITHOUT losing the article's concrete reporting, actors, figures, counterpoints, or quotes. Never write a thin 3-card executive summary, never dump raw paragraphs into `Card([Text(...)])`, and never emit generic two-column key-value tables (`指标|数值`, `项目|事实`, `metric|value`).\n\n")
	b.WriteString("How to structure an article Act-by-Act:\n")
	b.WriteString("1. Put the article title, concise thesis subtitle, and terminology `Popover` outside `Source` in `head`.\n")
	b.WriteString("2. Break the article into 3–6 sequential narrative Acts (`01 …`, `02 …`, …), preserving ~95%+ of the original facts, people, cases, numbers, and caveats.\n")
	b.WriteString("3. Replace dense narrative blocks with pill-tagged scannable `List([ListItem(\"Bold lead-in\", \"1–2 line fact-dense detail\", \"Tag\")], \"none\")`, punchy verbatim `Quote`, and original source artwork/charts via `Image(\"assets/...\", \"caption\")`.\n")
	b.WriteString("4. Weave bespoke `Svg` mechanism diagrams, comparative `Chart`s, multi-column `Table`s (real subject columns), dated `Timeline` lists, and bounded `$variable` + `Slider` / `SegmentedControl` reactive islands right at the Act where they clarify structure or math. Keep each interactive control in its own `Source` statement so the toggle/slider sits directly above its reactive chart/table.\n")
	b.WriteString("5. Bind `--cite <stmt>:<srcId>=<blockId,...>` on every `Source` so the reader can jump straight to the verbatim translated/bilingual/original paragraphs behind the `原文` face.\n\n")
	b.WriteString("## Three Full-Page Editorial Patterns\n\n")
	b.WriteString("### Example 1: Act with Quote + pill-tagged scannable List + causal SVG mechanism\n")
	b.WriteString("```openui\n")
	b.WriteString("root = Col([head, act1_mechanism, act2_chart])\n")
	b.WriteString("head = Col([Row([Title(\"Why grid queues delay electrification\", \"xl\"), Popover(Badge(\"Terms\", \"info\"), Text(\"Interconnection queue: projects waiting for grid hookup approval.\"))], 3), Text(\"Full-information structured read · every figure anchored to verbatim prose\", \"sm\")], 2)\n")
	b.WriteString("act1_mechanism = Source([\"s1\"], [Title(\"01 The bottleneck and how speculative filings jam the line\", \"md\"), Quote(\"\\\"Projects wait five years just to learn what upgrades cost.\\\"\", \"Grid operator\"), List([ListItem(\"Queue surge\", \"Waiting capacity jumped from 750 GW in 2020 to 2,600 GW in 2024.\", \"Scale\"), ListItem(\"First-come trap\", \"Low refundable deposits let developers submit speculative studies that clog reviews.\", \"Cause\")], \"none\"), Svg([Rect(5, 10, 30, 20, \"surface\"), Path(\"M 35 20 L 60 20\", null, \"info\", 2), Circle(70, 20, 10, \"warning\"), SvgText(\"Queue\", 15, 25)], \"0 0 100 50\", \"Applications enter a constrained interconnection queue\")])\n")
	b.WriteString("act2_chart = Source([\"s2\"], [Title(\"02 Queued capacity trajectory (GW)\", \"md\"), Chart(\"line\", queueData, \"year\", [\"gw\"], \"number\", false, 220, {gw: \"Queued capacity\"})])\n")
	b.WriteString("queueData = [{year: \"2020\", gw: 750}, {year: \"2024\", gw: 2600}]\n")
	b.WriteString("```\n\n")
	b.WriteString("### Example 2: Dedicated reactive Source with bounded $variable + Slider\n")
	b.WriteString("```openui\n")
	b.WriteString("root = Col([Title(\"Storage migration scenario\", \"xl\"), scenario])\n")
	b.WriteString("$months = 6\n")
	b.WriteString("scenario = Source([\"s1\", \"s2\"], [Slider($months, 6, 12, 1, \"Months\"), Text(@Format($months * 900, \"currency\", 0), \"lg\"), Chart(\"bar\", @Each(@Range(1, $months + 1), \"m\", {month: \"M\" + m, disk: m * 2300, object: m * 1400}), \"month\", [\"disk\", \"object\"], null, null, null, {disk: \"Disk\", object: \"Object storage\"})])\n")
	b.WriteString("```\n")
	b.WriteString("The report supplies the 6–12 month range, the 6-month default, and both monthly prices; do not invent any of them.\n\n")
	b.WriteString("### Example 3: Multi-subject Table + dated Timeline\n")
	b.WriteString("```openui\n")
	b.WriteString("root = Col([head, comparison, chronology])\n")
	b.WriteString("head = Row([Title(\"Two deployment models\", \"xl\"), Spacer(), Popover(Badge(\"Capex\", \"info\"), Text(\"Capital expenditure: the terminology used by the source.\"))])\n")
	b.WriteString("comparison = Source([\"s1\"], [Table([\"Subject\", \"Disclosure Basis\", \"Reported Figure\", \"Annualized Note\"], [[\"Firm A\", \"Single-year cash (2024)\", \"$18B\", \"One-year outlay\"], [\"Firm B\", \"3-year commitment (2024–2026)\", \"$42B\", \"~$14B/yr average\"]])])\n")
	b.WriteString("chronology = Source([\"s2\"], [List([ListItem(\"Readiness review\", \"Land and financing evidence required.\", \"2023\"), ListItem(\"Network upgrade\", \"Construction begins after approval.\", \"2024\")], \"none\", true)])\n")
	b.WriteString("```\n\n")
	b.WriteString("## Complete OpenUI v3 Language and Layout Guidance\n\n")
	b.WriteString(genuikit.Format())
	b.WriteString("\n")
	return b.String()
}

// marginCatalogText preserves the v0.2 ten-primitive output exactly.
func marginCatalogText() (string, error) {
	var raw struct {
		Components map[string]struct {
			Signature   string `json:"signature"`
			Description string `json:"description"`
		} `json:"components"`
	}
	if err := json.Unmarshal(genuikit.CatalogJSON(), &raw); err != nil {
		return "", err
	}

	var b strings.Builder
	b.WriteString("# DeepRead OpenUI Lang Contract (Mark Go Go v3 Static Subset)\n\n")
	b.WriteString("Write bare openui-lang statements (one statement per line, NO JSON escaping needed).\n")
	b.WriteString("Pass `--source <sourceId>=<Exact Heading>#<occurrence>` for each section cited.\n\n")

	b.WriteString("## Hard Rules (Enforced by `deepread write` & `deepread patch`)\n")
	b.WriteString("1. Prose-by-Reference: NEVER summarize or retell the article. Original Markdown prose is already rendered.\n")
	b.WriteString("2. Sparse Intervention: Emit 0 to 4 top-level Source modules (max 6 for very long texts; max 1 per section). 0 modules (`root = Col([])`) is valid and encouraged when prose is already clear.\n")
	b.WriteString("3. Topology: `root = Col([stmt1, stmt2, ...])` may ONLY reference named top-level `Source([\"srcId\"], [...])` statements. Each `Source` cites EXACTLY ONE non-H1 section. No nested `Source`. No root-level title/intro outside `Source`.\n")
	b.WriteString("4. Anti-Cliché: Every `Source` MUST contain at least one structural primitive (`Table`, `Chart`, `Quote`, or `List` with `timeline=true`). Pure text/bullet summaries and titles like \"Summary\" / \"Key Takeaways\" / \"要点\" / \"总结\" are rejected.\n")
	b.WriteString("5. Chart restriction: Only `type=\"bar\"` or `type=\"line\"`. Never compare mismatched units/periods as equal bars without explicit disclosure.\n")
	b.WriteString("6. Factuality: Every figure, date, entity, and quote must be grounded verbatim in the cited section.\n\n")

	b.WriteString("## Allowed Components (10 Static Reading Primitives)\n")
	for _, name := range allowedComponentOrder {
		comp, ok := raw.Components[name]
		if !ok {
			continue
		}
		fmt.Fprintf(&b, "- `%s` — %s\n", comp.Signature, comp.Description)
	}

	b.WriteString("\n## Sparse Non-Cliché Examples\n\n")
	b.WriteString("### Example 1: Disclosing a hidden metric mismatch (Table)\n")
	b.WriteString("```openui\n")
	b.WriteString("root = Col([capex_basis])\n")
	b.WriteString("capex_basis = Source([\"sec1\"], [Title(\"资本开支统计口径差异\", \"md\"), Table([\"主体\", \"披露口径\", \"原文数值\", \"为何不能直接横向相加\"], [[\"甲公司\", \"单年实付（2024）\", \"$18B\", \"仅含当年现金流出\"], [\"乙公司\", \"三年累计承诺（2024–2026）\", \"$42B\", \"含未来两年未实付承诺，年均约 $14B\"]]), Caption(\"依据原文 §1 财报口径注释\")])\n")
	b.WriteString("```\n\n")

	b.WriteString("### Example 2: Chronological inflection & trajectory (Chart + Timeline List)\n")
	b.WriteString("```openui\n")
	b.WriteString("root = Col([grid_trend, policy_shift])\n")
	b.WriteString("grid_trend = Source([\"sec2\"], [Title(\"并网排队容量变化（GW）\", \"md\"), Chart(\"line\", queue_data, \"year\", [\"queued\"], \"number\", false, 200, {queued: \"待并网容量 (GW)\"}), Caption(\"数据取自原文 §2 行业统计\")])\n")
	b.WriteString("queue_data = [{year: \"2020\", queued: 750}, {year: \"2022\", queued: 1350}, {year: \"2024\", queued: 2600}]\n")
	b.WriteString("policy_shift = Source([\"sec3\"], [Title(\"审批规则转折时间线\", \"md\"), List([ListItem(\"先到先得拥堵\", \"项目只需低门槛押金即可排队占位\", \"2020\"), ListItem(\"准备度审查\", \"要求土地与融资证明，淘汰投机队列\", \"2023\")], \"none\", true)])\n")
	b.WriteString("```\n")
	return b.String(), nil
}
