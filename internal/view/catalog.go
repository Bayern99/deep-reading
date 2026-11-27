package view

import (
	"encoding/json"
	"fmt"
	"strings"

	"deepread/internal/genuikit"
)

// AllowedComponents is the deliberately narrowed v1 reading-primitive whitelist.
// Dashboard/form components (Card, Grid, Badge, Box, Carousel, Input, etc.) are
// excluded at both catalog and validator layers while remaining 100% valid Mark Go Go v3.
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

// AllowedChartTypes restricts v1 Chart rendering to crisp static bar and line charts.
var AllowedChartTypes = map[string]bool{
	"bar":  true,
	"line": true,
}

// CatalogText builds the concise, anti-cliché OpenUI Lang specification shown to
// host Agents via `deepread catalog`. It derives signatures directly from
// genuikit's authoritative catalog.json and never exposes card/badge examples.
func CatalogText() (string, error) {
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
