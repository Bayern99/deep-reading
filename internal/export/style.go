package export

import "html"

const contentSecurityPolicy = "default-src 'none'; style-src 'unsafe-inline'; img-src data:;"
const externalContentSecurityPolicy = "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:;"

const documentCSS = `
:root {
  color-scheme: light;
  --paper: #faf8f5;
  --ink: #1c1b18;
  --muted: #716c63;
  --faint: #979086;
  --rule: #e5e2dc;
  --accent: #866e5d;
  --serif: Georgia, "Songti SC", "Noto Serif CJK SC", "Times New Roman", serif;
  --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Noto Sans CJK SC", Arial, sans-serif;
}
* { box-sizing: border-box; }
html { background: var(--paper); }
body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: var(--serif);
  font-size: 18px;
  line-height: 1.72;
  overflow-x: hidden;
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
}
.dr-document {
  width: min(calc(100% - 2rem), 46rem);
  margin: 0 auto;
  padding: 3.5rem 0 6rem;
}
h1, h2, h3, p, blockquote, figure { margin-top: 0; }
h1, h2, h3 { font-family: var(--serif); font-weight: 500; line-height: 1.18; }
h1 { margin-bottom: 1.5rem; font-size: clamp(2.15rem, 8vw, 3.6rem); letter-spacing: -0.035em; }
h2 { margin: 4.25rem 0 1.35rem; font-size: clamp(1.65rem, 6vw, 2.25rem); letter-spacing: -0.025em; }
h3 { margin-bottom: 1rem; font-size: 1.5rem; }
p { margin-bottom: 1.35rem; }
a { color: inherit; text-decoration-color: #b7a797; text-underline-offset: 0.2em; overflow-wrap: anywhere; }
svg { max-width: 100%; }
figure { margin: 1.5rem auto; }
img { display: block; max-width: 100%; height: auto; margin: 1.5rem auto; }
pre, code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
pre { max-width: 100%; overflow-x: auto; white-space: pre-wrap; overflow-wrap: anywhere; }
table, figure, .dr-module, .dr-chart, .dr-table-wrap { max-width: 100%; }
.dr-sec-break {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  margin: 4rem 0 1.75rem;
  color: var(--muted);
  font-family: var(--sans);
  font-size: 0.72rem;
  font-weight: 500;
  letter-spacing: 0.09em;
  line-height: 1.4;
  text-transform: uppercase;
}
.dr-sec-break::before, .dr-sec-break::after { content: ""; height: 1px; background: var(--rule); flex: 1; }
.dr-module { margin: 2.75rem 0 3.25rem; padding: 1.5rem 0 0; border-top: 1px solid var(--rule); }
.dr-module-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.45rem 0.75rem;
  margin-bottom: 1.6rem;
  color: var(--muted);
  font-family: var(--sans);
  font-size: 0.74rem;
  line-height: 1.45;
}
.dr-shortcode {
  display: inline;
  padding: 0;
  background: none;
  color: var(--accent);
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  user-select: text;
  -webkit-user-select: text;
}
.dr-module-source { overflow-wrap: anywhere; }
.dr-col > *:last-child { margin-bottom: 0; }
.dr-title { margin: 0 0 1.15rem; color: var(--ink); }
.dr-title-sm { font-size: 1.05rem; }
.dr-title-md { font-size: 1.35rem; }
.dr-title-lg { font-size: 1.65rem; }
.dr-title-xl { font-size: 1.9rem; }
.dr-title-2xl { font-size: 2.15rem; }
.dr-title-3xl { font-size: 2.4rem; }
.dr-text { margin: 0 0 1.25rem; }
.dr-text-xs { font-size: 0.75rem; }
.dr-text-sm { font-size: 0.875rem; }
.dr-text-md { font-size: 1rem; }
.dr-text-lg { font-size: 1.2rem; }
.dr-weight-medium { font-weight: 500; }
.dr-weight-semibold { font-weight: 600; }
.dr-italic { font-style: italic; }
.dr-line-through { text-decoration: line-through; }
.dr-tabular { font-variant-numeric: tabular-nums; }
.dr-caption { margin: 0.8rem 0 1.5rem; color: var(--muted); font-family: var(--sans); font-size: 0.75rem; line-height: 1.55; }
.dr-quote { margin: 2.25rem 0; padding: 0 0 0 1.25rem; border-left: 2px solid #b8a391; }
.dr-quote blockquote { margin: 0; font-size: clamp(1.3rem, 5.5vw, 1.7rem); font-style: italic; line-height: 1.4; }
.dr-quote figcaption { margin-top: 0.8rem; color: var(--muted); font-family: var(--sans); font-size: 0.75rem; font-style: normal; }
.dr-table-wrap { margin: 1.5rem 0; overflow-x: auto; overscroll-behavior-x: contain; -webkit-overflow-scrolling: touch; }
.dr-table { width: 100%; min-width: 30rem; border-collapse: collapse; border-top: 1px solid var(--rule); border-bottom: 1px solid var(--rule); font-family: var(--sans); font-size: 0.82rem; line-height: 1.5; }
.dr-table th, .dr-table td { padding: 0.7rem 0.8rem; border-bottom: 1px solid var(--rule); text-align: left; vertical-align: top; overflow-wrap: break-word; word-break: normal; }
.dr-table th { color: var(--muted); font-size: 0.7rem; font-weight: 600; letter-spacing: 0.04em; white-space: nowrap; }
.dr-table tr:last-child td { border-bottom: 0; }
.dr-table td:first-child { min-width: 6.5rem; }
.dr-table .dr-num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.dr-table td p { margin: 0; }
.dr-list { margin: 1.5rem 0; padding-left: 1.4rem; }
.dr-list > li { margin: 0.55rem 0; padding-left: 0.2rem; }
.dr-list-none { padding-left: 0; list-style: none; }
.dr-list-item { position: relative; }
.dr-list-title { font-weight: 600; line-height: 1.4; }
.dr-list-description { margin-top: 0.3rem; color: var(--muted); font-family: var(--sans); font-size: 0.85rem; line-height: 1.55; }
.dr-list-marker { display: inline-block; margin-right: 0.55rem; color: var(--accent); font-family: var(--sans); font-size: 0.72rem; font-variant-numeric: tabular-nums; font-weight: 600; }
.dr-timeline { position: relative; margin: 1.75rem 0; padding: 0; list-style: none; }
.dr-timeline::before { content: ""; position: absolute; top: 0.45rem; bottom: 0.55rem; left: 0.29rem; width: 1px; background: #cfc5ba; }
.dr-timeline > .dr-list-item { margin: 0; padding: 0 0 1.5rem 1.6rem; }
.dr-timeline > .dr-list-item:last-child { padding-bottom: 0; }
.dr-timeline > .dr-list-item::before { content: ""; position: absolute; top: 0.4rem; left: 0; width: 0.58rem; height: 0.58rem; border: 2px solid var(--paper); border-radius: 50%; background: var(--accent); }
.dr-timeline .dr-list-marker { display: block; margin: 0 0 0.2rem; }
.dr-chart { margin: 1.75rem 0 1.5rem; }
.dr-chart svg { display: block; width: 100%; height: auto; overflow: visible; }
@media (max-width: 480px) {
  body { font-size: 17px; }
  .dr-document { width: min(calc(100% - 2rem), 46rem); padding-top: 2.5rem; }
  .dr-module { margin-top: 2.25rem; }
  .dr-quote { padding-left: 1rem; }
  .dr-table { min-width: 30rem; }
}
@media print {
  :root, html, body { background: #fff; }
  .dr-document { width: 100%; max-width: none; padding: 0; }
  .dr-module, .dr-quote, .dr-chart, .dr-table-wrap { break-inside: avoid; }
  .dr-table-wrap { overflow-x: visible; }
}
`

func renderDocument(title, body string) string {
	return renderDocumentWithCSP(title, body, contentSecurityPolicy)
}

func renderDocumentWithCSP(title, body, csp string) string {
	return "<!doctype html>\n<html lang=\"en\">\n<head>\n" +
		"<meta charset=\"utf-8\">\n" +
		"<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n" +
		"<meta http-equiv=\"Content-Security-Policy\" content=\"" + csp + "\">\n" +
		"<title>" + html.EscapeString(title) + "</title>\n" +
		"<style>" + documentCSS + "</style>\n" +
		"</head>\n<body>\n<main class=\"dr-document\">\n" + body + "</main>\n</body>\n</html>\n"
}
