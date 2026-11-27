package export

import "html"

const contentSecurityPolicy = "default-src 'none'; style-src 'unsafe-inline'; img-src data:;"
const externalContentSecurityPolicy = "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:;"

func exportContentSecurityPolicy(external, noJS bool) string {
	csp := "default-src 'none'; "
	if !noJS {
		csp += "script-src 'sha256-" + runtimeCSPHash() + "'; "
	}
	csp += "style-src 'unsafe-inline'; img-src "
	if external {
		csp += "'self' data:"
	} else {
		csp += "data:"
	}
	return csp + "; connect-src 'none'; base-uri 'none'; form-action 'none'"
}

const documentCSS = `
:root {
  color-scheme: light;
  --paper: #faf8f5;
  --surface: #f2eee8;
  --ink: #1c1b18;
  --muted: #716c63;
  --faint: #979086;
  --rule: #e5e2dc;
  --accent: #866e5d;
  --chart-1: #866e5d;
  --chart-2: #607d78;
  --chart-3: #a47767;
  --chart-4: #6d7891;
  --chart-5: #a18b56;
  --chart-6: #7d6b82;
  --serif: Georgia, "Songti SC", "Noto Serif CJK SC", "Times New Roman", serif;
  --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Noto Sans CJK SC", Arial, sans-serif;
}
* { box-sizing: border-box; }
html { background: var(--paper); scroll-behavior: smooth; scroll-padding-top: 5rem; }
body { margin: 0; background: var(--paper); color: var(--ink); font-family: var(--serif); font-size: 18px; line-height: 1.8; overflow-x: hidden; text-rendering: optimizeLegibility; -webkit-font-smoothing: antialiased; }
.dr-document { width: min(calc(100% - 2rem), 48rem); margin: 0 auto; padding: 1.25rem 0 7rem; }
h1, h2, h3, p, blockquote, figure { margin-top: 0; }
h1, h2, h3 { font-family: var(--serif); font-weight: 500; line-height: 1.25; }
h1 { margin-bottom: 1.5rem; font-size: clamp(2.05rem, 8vw, 3.6rem); letter-spacing: -0.035em; }
h2 { margin: 3.8rem 0 1.35rem; font-size: clamp(1.65rem, 6vw, 2.25rem); letter-spacing: -0.025em; }
h3 { margin-bottom: 1rem; font-size: 1.5rem; }
p { margin-bottom: 1.35rem; }
a { color: inherit; text-decoration-color: #b7a797; text-underline-offset: 0.2em; overflow-wrap: anywhere; }
button, input, select, textarea { font: inherit; }
button { color: inherit; }
button, a { -webkit-tap-highlight-color: transparent; }
svg { max-width: 100%; }
figure { margin: 1.5rem auto; }
img { display: block; max-width: 100%; height: auto; margin: 1.5rem auto; }
pre, code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
pre { max-width: 100%; overflow-x: auto; white-space: pre-wrap; overflow-wrap: anywhere; }
table, figure, .dr-module, .dr-chart, .dr-table-wrap { max-width: 100%; }
.dr-book-header { margin: 1.5rem 0 2rem; }
.dr-book-header > h1 { margin-bottom: 0; }
.dr-topbar { position: sticky; z-index: 20; top: 0; display: flex; min-height: 52px; align-items: center; justify-content: space-between; gap: .5rem; margin: 0 -0.25rem 1.25rem; padding: .25rem; background: color-mix(in srgb, var(--paper) 94%, transparent); backdrop-filter: blur(12px); border-bottom: 1px solid var(--rule); font-family: var(--sans); }
.dr-topbar:empty { display: none; }
.dr-topbar button, .dr-topbar summary, .dr-topbar a { min-height: 44px; min-width: 44px; padding: .55rem .8rem; border: 0; border-radius: 999px; background: transparent; cursor: pointer; text-decoration: none; line-height: 1.4; }
.dr-face-switch, .dr-language-switch { display: flex; gap: .2rem; align-items: center; }
.dr-face-switch { padding: .18rem; border-radius: 999px; background: var(--surface); }
.dr-face-switch button[aria-pressed="true"], .dr-language-switch button[aria-pressed="true"] { background: var(--ink); color: var(--paper); }
[data-face-target], [data-inline-view-target], [data-language], [data-chapter-step] { display: none; }
.dr-js [data-face-target], .dr-js [data-inline-view-target], .dr-js [data-language], .dr-js [data-chapter-step] { display: inline-flex; align-items: center; justify-content: center; }
.dr-face { display: block; }
.dr-js[data-face="genui"] [data-face-panel="read"], .dr-js[data-face="read"] [data-face-panel="genui"] { display: none; }
.dr-js[data-face="genui"] [data-face-panel="genui"], .dr-js[data-face="read"] [data-face-panel="read"] { display: block; }
.dr-inline-empty { display: none; margin: 2rem 0; color: var(--muted); font-family: var(--sans); font-size: .9375rem; }
.dr-js[data-face="inline"][data-inline-view="prose"] .dr-inline-module,
.dr-js[data-face="hybrid"][data-inline-view="prose"] .dr-inline-module,
.dr-js[data-face="hybrid"][data-inline-view="prose"] .dr-hybrid-hero { display: none; }
.dr-js[data-face="inline"][data-inline-view="genui"] .dr-sec-prose > .dr-translated > :not(h1),
.dr-js[data-face="inline"][data-inline-view="genui"] .dr-sec-prose > .dr-orig > .dr-orig-full > :not(h1),
.dr-js[data-face="inline"][data-inline-view="genui"] .dr-sec-prose > :not(h1):not(.dr-translated):not(.dr-orig),
.dr-js[data-face="hybrid"][data-inline-view="genui"] .dr-sec-prose > .dr-translated > :not(h1),
.dr-js[data-face="hybrid"][data-inline-view="genui"] .dr-sec-prose > .dr-orig > .dr-orig-full > :not(h1),
.dr-js[data-face="hybrid"][data-inline-view="genui"] .dr-sec-prose > :not(h1):not(.dr-translated):not(.dr-orig) { display: none; }
.dr-js[data-face="inline"][data-inline-view="genui"] .dr-inline-empty,
.dr-js[data-face="hybrid"][data-inline-view="genui"] .dr-inline-empty { display: block; }
.dr-hybrid-hero { margin: 1.5rem 0 2.5rem; padding: 1.35rem 1.35rem 1.15rem; border: 1px solid color-mix(in srgb, var(--accent) 32%, var(--rule)); border-top: 3px solid var(--accent); border-radius: 14px; background: color-mix(in srgb, var(--surface) 62%, var(--paper)); }
.dr-hybrid-hero-head { display: flex; align-items: center; justify-content: space-between; gap: .75rem; margin-bottom: .9rem; font-family: var(--sans); font-size: .78rem; letter-spacing: .08em; text-transform: uppercase; color: var(--accent); font-weight: 600; }
.dr-hybrid-hero-hint { color: var(--muted); font-weight: 400; letter-spacing: 0; text-transform: none; }
.dr-hybrid-hero > .dr-module { margin: 0; padding: 0; border-top: 0; }
.dr-hybrid-hero-framing { margin-bottom: 1rem; }
.dr-inline-module > .dr-module { margin: 2rem 0 2.5rem; padding: 1.35rem 1.3rem 1.1rem; border: 1px solid var(--rule); border-left: 3px solid var(--accent); border-radius: 12px; background: color-mix(in srgb, var(--surface) 48%, var(--paper)); }
.dr-js [data-chapter][hidden] { display: none; }
.dr-toc { position: relative; font-family: var(--sans); }
.dr-toc summary { cursor: pointer; list-style: none; }
.dr-toc-drawer { position: absolute; right: 0; top: 3rem; display: grid; width: min(20rem, 85vw); max-height: 32rem; overflow-y: auto; padding: .5rem; border: 1px solid var(--rule); border-radius: 12px; background: var(--paper); box-shadow: 0 12px 30px #1c1b1818; }
.dr-toc-drawer a { border-radius: 6px; }
.dr-toc-drawer a[aria-current="location"] { background: var(--surface); color: var(--accent); }
.dr-chapter-nav { display: flex; justify-content: space-between; margin: 3rem 0; gap: 1rem; font-family: var(--sans); }
.dr-chapter-nav button { min-height: 44px; padding: .6rem 1rem; border: 1px solid var(--rule); border-radius: 8px; background: var(--surface); }
.dr-sec-break { display: flex; align-items: center; gap: .85rem; margin: 4rem 0 1.75rem; color: var(--muted); font-family: var(--sans); font-size: .875rem; font-weight: 500; letter-spacing: .06em; line-height: 1.5; }
.dr-sec-break::before, .dr-sec-break::after { content: ""; height: 1px; background: var(--rule); flex: 1; }
.dr-module { margin: 2.75rem 0 3.5rem; padding: 1.5rem 0 0; border-top: 1px solid var(--rule); }
.dr-module-meta { display: flex; flex-wrap: wrap; align-items: baseline; gap: .45rem .75rem; margin-bottom: 1.6rem; color: var(--muted); font-family: var(--sans); font-size: .875rem; }
.dr-shortcode { display: inline; padding: 0; background: none; color: var(--accent); font-size: .8rem; font-weight: 600; user-select: text; -webkit-user-select: text; }
.dr-module-footer { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: .75rem; margin-top: 1.4rem; color: var(--muted); font-family: var(--sans); font-size: .875rem; }
.dr-source-chips { display: flex; flex-wrap: wrap; gap: .4rem; }
.dr-source-chip-wrap { position: relative; display: inline-flex; align-items: center; gap: .2rem; }
.dr-source-chip { display: inline-flex; min-height: 36px; align-items: center; padding: .3rem .65rem; border: 1px solid var(--rule); border-radius: 999px; background: var(--surface); color: var(--accent); text-decoration: none; }
.dr-preview-button { display: inline-flex; min-height: 36px; align-items: center; padding: .25rem .6rem; border: 1px solid transparent; border-radius: 999px; background: transparent; color: var(--muted); white-space: nowrap; cursor: pointer; }
.dr-source-popover, .dr-popover-content { width: min(28rem, calc(100vw - 2rem)); padding: 1rem; border: 1px solid var(--rule); border-radius: 10px; background: var(--paper); color: var(--ink); box-shadow: 0 16px 40px #1c1b1820; line-height: 1.7; }
.dr-feedback { color: var(--faint); }
.dr-feedback summary { cursor: pointer; }
.dr-feedback button { padding: 0; border: 0; background: transparent; cursor: pointer; }
.dr-citation-reverse { float: right; margin-left: .5rem; color: var(--accent); font-family: var(--sans); font-size: .75rem; text-decoration: none; }
.dr-highlight { animation: dr-flash 1.8s ease-out; }
@keyframes dr-flash { 0%, 35% { background: #eadcc6; } 100% { background: transparent; } }
.dr-back-genui { position: fixed; z-index: 30; right: 1rem; bottom: 1rem; min-height: 44px; padding: .6rem 1rem; border: 1px solid var(--rule); border-radius: 999px; background: var(--ink); color: var(--paper); box-shadow: 0 6px 20px #1c1b1825; cursor: pointer; }
.dr-back-genui[hidden] { display: none; }
.dr-col { display: flex; flex-direction: column; min-width: 0; }
.dr-row { display: flex; flex-direction: row; min-width: 0; align-items: flex-start; }
.dr-wrap { flex-wrap: wrap; }
.dr-col > *:last-child { margin-bottom: 0; }
.dr-grid { display: grid; grid-template-columns: repeat(var(--dr-grid-columns, 2), minmax(0, 1fr)); min-width: 0; }
.dr-card { padding: 1rem; border: 1px solid var(--rule); border-radius: 12px; background: var(--paper); }
.dr-card-soft { border-color: transparent; background: var(--surface); }
.dr-divider { margin: 1.5rem 0; border: 0; border-top: 1px solid var(--rule); }
.dr-spacer { flex: 1 1 auto; min-height: 1rem; }
.dr-title { margin: 0 0 1.15rem; color: var(--ink); }
.dr-title-sm { font-size: 1.05rem; } .dr-title-md { font-size: 1.35rem; } .dr-title-lg { font-size: 1.65rem; } .dr-title-xl { font-size: 1.9rem; } .dr-title-2xl { font-size: 2.15rem; } .dr-title-3xl { font-size: 2.4rem; }
.dr-text { margin: 0 0 1.25rem; }
.dr-text-xs { font-size: .875rem; } .dr-text-sm { font-size: .9375rem; } .dr-text-md { font-size: 1rem; } .dr-text-lg { font-size: 1.2rem; }
.dr-weight-medium { font-weight: 500; } .dr-weight-semibold { font-weight: 600; } .dr-italic { font-style: italic; } .dr-line-through { text-decoration: line-through; } .dr-tabular { font-variant-numeric: tabular-nums; }
.dr-caption { margin: .8rem 0 1.5rem; color: var(--muted); font-family: var(--sans); font-size: .875rem; line-height: 1.6; }
.dr-label { color: var(--muted); font-family: var(--sans); font-size: .875rem; font-weight: 500; }
.dr-badge { display: inline-flex; align-items: center; gap: .25rem; padding: .15rem .55rem; border: 1px solid var(--rule); border-radius: 999px; color: var(--muted); font-family: var(--sans); font-size: .8rem; line-height: 1.5; }
.dr-badge-success { color: #476b58; } .dr-badge-warning { color: #8a632e; } .dr-badge-danger { color: #944f49; } .dr-badge-info { color: #4f687d; }
.dr-icon { display: inline-block; flex: none; vertical-align: -.18em; }
.dr-quote { margin: 2.25rem 0; padding: 0 0 0 1.25rem; border-left: 2px solid #b8a391; }
.dr-quote blockquote { margin: 0; font-size: clamp(1.3rem, 5.5vw, 1.7rem); font-style: italic; line-height: 1.5; }
.dr-quote figcaption { margin-top: .8rem; color: var(--muted); font-family: var(--sans); font-size: .875rem; font-style: normal; }
.dr-code { padding: 1rem; border-radius: 8px; background: var(--surface); font-size: .875rem; line-height: 1.65; }
.dr-table-wrap { margin: 1.5rem 0; overflow-x: auto; overscroll-behavior-x: contain; -webkit-overflow-scrolling: touch; }
.dr-table { width: 100%; min-width: 0; table-layout: fixed; border-collapse: collapse; border-top: 1px solid var(--rule); border-bottom: 1px solid var(--rule); font-family: var(--sans); font-size: .875rem; line-height: 1.6; }
.dr-table-wide { min-width: 28rem; table-layout: auto; }
.dr-table th, .dr-table td { padding: .7rem .55rem; border-bottom: 1px solid var(--rule); text-align: left; vertical-align: top; overflow-wrap: anywhere; word-break: normal; }
.dr-table th { color: var(--muted); font-size: .875rem; font-weight: 600; }
.dr-table tr:last-child td { border-bottom: 0; }
.dr-table .dr-num { text-align: right; font-variant-numeric: tabular-nums; }
.dr-table td p { margin: 0; }
.dr-list { margin: 1.5rem 0; padding-left: 1.4rem; }
.dr-list > li { margin: .55rem 0; padding-left: .2rem; }
.dr-list-none { padding-left: 0; list-style: none; }
.dr-list-item { position: relative; }
.dr-list-none:not(.dr-timeline) > .dr-list-item { display: flex; align-items: baseline; gap: .75rem; margin: 0; padding: .7rem 0; border-bottom: 1px solid color-mix(in srgb, var(--rule) 65%, transparent); }
.dr-list-none:not(.dr-timeline) > .dr-list-item:last-child { border-bottom: 0; padding-bottom: .15rem; }
.dr-list-content { flex: 1; min-width: 0; }
.dr-list-title { font-family: var(--sans); font-size: 1rem; font-weight: 600; line-height: 1.5; color: var(--ink); }
.dr-list-description { margin-top: .28rem; color: color-mix(in srgb, var(--ink) 84%, var(--muted)); font-family: var(--sans); font-size: .95rem; line-height: 1.72; }
.dr-list-marker { display: inline-flex; flex: none; align-items: center; justify-content: center; margin-right: .15rem; padding: .1rem .5rem; border-radius: 999px; background: var(--surface); color: var(--accent); font-family: var(--sans); font-size: .78rem; font-weight: 600; white-space: nowrap; }
.dr-timeline > .dr-list-item .dr-list-marker { display: inline-block; padding: 0; background: none; margin-right: .55rem; font-size: .875rem; }
.dr-timeline > .dr-list-item .dr-list-description { color: var(--muted); font-size: .875rem; line-height: 1.6; }
.dr-timeline { position: relative; margin: 1.75rem 0; padding: 0; list-style: none; }
.dr-timeline::before { content: ""; position: absolute; top: .45rem; bottom: .55rem; left: .29rem; width: 1px; background: #cfc5ba; }
.dr-timeline > .dr-list-item { margin: 0; padding: 0 0 1.5rem 1.6rem; }
.dr-timeline > .dr-list-item::before { content: ""; position: absolute; top: .4rem; left: 0; width: .58rem; height: .58rem; border: 2px solid var(--paper); border-radius: 50%; background: var(--accent); }
.dr-chart { margin: 1.75rem 0 1.5rem; }
.dr-chart svg { display: block; width: 100%; height: auto; overflow: visible; }
.dr-chart-legend { display: flex; flex-wrap: wrap; gap: .5rem 1rem; color: var(--muted); font-family: var(--sans); font-size: .875rem; }
.dr-chart-legend span { display: inline-flex; align-items: center; gap: .3rem; }
.dr-chart-legend i { width: .7rem; height: .7rem; border-radius: 2px; }
.dr-svg { display: block; width: 100%; height: auto; margin: 1.5rem 0; }
.dr-carousel { display: flex; gap: 1rem; max-width: 100%; overflow-x: auto; scroll-snap-type: x mandatory; overscroll-behavior-x: contain; padding-bottom: .75rem; }
.dr-carousel > * { flex: 0 0 min(var(--dr-carousel-width, 82%), 32rem); scroll-snap-align: start; }
.dr-popover-trigger { padding: 0; border: 0; background: none; cursor: pointer; }
.dr-form fieldset, .dr-radio-group { min-width: 0; margin: 0; padding: 0; border: 0; }
.dr-control { display: flex; flex-direction: column; gap: .4rem; margin: .75rem 0; font-family: var(--sans); }
.dr-control input:not([type="range"]):not([type="checkbox"]):not([type="radio"]), .dr-control select, .dr-control textarea { width: 100%; min-height: 44px; padding: .55rem .7rem; border: 1px solid var(--rule); border-radius: 7px; background: var(--paper); color: var(--ink); }
.dr-control input:disabled, .dr-control select:disabled, .dr-control textarea:disabled, .dr-button:disabled, .dr-segment:disabled { opacity: .62; cursor: not-allowed; }
.dr-choice { display: flex; min-height: 44px; align-items: center; gap: .6rem; font-family: var(--sans); }
.dr-choice input { width: 1.15rem; height: 1.15rem; accent-color: var(--accent); }
.dr-choice small { display: block; color: var(--muted); }
.dr-checked-line { color: var(--muted); text-decoration: line-through; }
.dr-segments { display: flex; flex-wrap: wrap; gap: .25rem; margin: .75rem 0; padding: .25rem; border-radius: 9px; background: var(--surface); }
.dr-segment { flex: 1; min-height: 44px; padding: .45rem .7rem; border: 0; border-radius: 6px; background: transparent; cursor: pointer; font-family: var(--sans); }
.dr-segment[aria-pressed="true"] { background: var(--paper); color: var(--accent); box-shadow: 0 1px 4px #1c1b1810; }
.dr-slider-heading { display: flex; justify-content: space-between; gap: 1rem; }
.dr-slider output { font-variant-numeric: tabular-nums; }
.dr-slider input { width: 100%; min-height: 44px; accent-color: var(--accent); }
.dr-button { display: inline-flex; min-height: 44px; align-items: center; justify-content: center; gap: .4rem; padding: .55rem 1rem; border: 1px solid var(--rule); border-radius: 8px; background: var(--ink); color: var(--paper); text-decoration: none; cursor: pointer; font-family: var(--sans); }
.dr-button-outline, .dr-button-ghost, .dr-button-soft { background: var(--surface); color: var(--ink); }
.dr-block { width: 100%; }
.dr-pressable { display: block; width: 100%; padding: 0; border: 0; background: transparent; text-align: left; cursor: pointer; }
.dr-flashcard { margin: 1.25rem 0; padding: 1rem; border: 1px solid var(--rule); border-radius: 10px; background: var(--surface); }
.dr-flashcard summary { min-height: 44px; cursor: pointer; }
.dr-flash-label { color: var(--muted); font-family: var(--sans); font-size: .75rem; text-transform: uppercase; }
.dr-flash-back { margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--rule); }
.dr-celebration { color: var(--accent); font-size: 2rem; letter-spacing: .5em; }
.dr-island-controls { margin-bottom: 1rem; }
.dr-island-output { min-width: 0; }
.dr-sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
.dr-image-missing { display: block; padding: 1rem; background: var(--surface); color: var(--muted); font-family: var(--sans); }
.dr-js[data-lang-mode="translated"] .dr-orig, .dr-js[data-lang-mode="original"] .dr-translated { display: none; }
.dr-js[data-lang-mode="original"] .dr-orig-full { display: block; }
.dr-js[data-lang-mode="bilingual"] .dr-translated { display: block; }
[data-lang-mode="bilingual"] .dr-orig-full { display: none; }
.dr-orig { color: var(--muted); }
.dr-orig-inline { display: none; margin-top: .35rem; color: var(--muted); font-size: .9em; line-height: 1.65; }
[data-lang-mode="bilingual"] .dr-orig-inline { display: block; }
[data-lang-mode="bilingual"] .dr-reading-block { margin-bottom: 1.65rem; }
@media (max-width: 600px) {
  .dr-topbar { flex-wrap: wrap; }
  .dr-language-switch { order: 3; width: 100%; justify-content: flex-end; }
  .dr-grid { grid-template-columns: minmax(0, 1fr); }
  .dr-row { flex-wrap: wrap; }
}
@media (max-width: 480px) {
  body { font-size: 17px; line-height: 1.8; }
  .dr-document { width: calc(100% - 2rem); padding-top: .75rem; }
  .dr-module { margin-top: 2.25rem; }
  .dr-inline-module > .dr-module { padding: 1.15rem .95rem 1rem; }
  .dr-quote { padding-left: 1rem; }
  .dr-table { width: 100%; min-width: 0; }
  .dr-table-wide { min-width: 28rem; }
  .dr-table th, .dr-table td { padding: .6rem .4rem; }
  .dr-face-switch button, .dr-language-switch button { padding-inline: .65rem; }
}
@media print {
  :root, html, body { background: #fff; }
  .dr-document { width: 100%; max-width: none; padding: 0; }
  .dr-topbar, .dr-back-genui, .dr-chapter-nav, .dr-island-controls { display: none !important; }
  .dr-face, .dr-orig, .dr-translated, [data-chapter] { display: block !important; }
  .dr-module, .dr-quote, .dr-chart, .dr-table-wrap { break-inside: avoid; }
  .dr-table-wrap { overflow-x: visible; }
}
`

func renderDocument(title, body string) string {
	return renderDocumentWithCSP(title, body, contentSecurityPolicy)
}

func renderDocumentWithCSP(title, body, csp string) string {
	return "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n<meta http-equiv=\"Content-Security-Policy\" content=\"" + csp + "\">\n<title>" + html.EscapeString(title) + "</title>\n<style>" + documentCSS + "</style>\n</head>\n<body>\n<main class=\"dr-document\">\n" + body + "</main>\n</body>\n</html>\n"
}
