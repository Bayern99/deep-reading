#!/usr/bin/env python3
"""Build the WSJ deep-read HTML from final.json. Layout only.

IRON RULE: Chinese body text is inserted verbatim from final.json
(html-escaped only). This script never translates, polishes, or edits
Chinese text. Any fix goes into final.json, never into this builder.
"""
import json, html, re, sys, os

# Archived into 2026-10-12/archive/legacy-scripts/; WORK stays the issue directory.
WORK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FINAL = os.path.join(WORK, "final.json")
OUT = os.path.join(WORK, "archive", "pre-reboot-html", "wsj-2026-10-12-deepread.html")

SECTION_CN = {
    "News": "新闻", "World News": "国际新闻", "U.S. News": "美国新闻",
    "Technology": "科技", "Personal Journal": "个人生活", "Sports": "体育",
    "Arts in Review": "艺术评论", "Opinion": "观点", "Review": "评论",
    "Books": "图书", "Business & Finance": "商业与金融",
    "Business News": "商业新闻", "Money & Investing": "理财与投资",
    "Heard on the Street": "街谈巷议", "Markets": "市场", "Data": "数据附录",
}
SECTION_ORDER = ["News", "World News", "U.S. News", "Technology",
                 "Personal Journal", "Sports", "Arts in Review",
                 "Opinion", "Review", "Books",
                 "Business & Finance", "Business News", "Money & Investing",
                 "Heard on the Street", "Markets", "Data"]

PRI_STYLE = {
    "P1": ("1", "#1d4ed8", "要闻"),
    "P2": ("2", "#0f766e", "关注"),
    "P3": ("3", "#6b7280", "速览"),
}

def esc(s):
    return html.escape(s or "", quote=True)

def paras(text):
    """Split body into paragraphs, escape each. No text changes."""
    return [p for p in re.split(r"\n\s*\n", (text or "").strip()) if p.strip()]

def entry_card(e, lang_default="cn"):
    num, color, label = PRI_STYLE.get(e.get("priority", "P3"), PRI_STYLE["P3"])
    parts = []
    parts.append(f'<article class="entry pri-{num}" data-id="{esc(e.get("final_id", e["id"]))}">')
    parts.append(f'<div class="pri-tag" style="border-color:{color};color:{color}">'
                 f'P{num} · {label} · {esc(e.get("page",""))}</div>')
    # title: CN + EN (EN hidden unless lang=en)
    parts.append(f'<h3 class="t-cn">{esc(e.get("title_cn",""))}</h3>')
    parts.append(f'<h3 class="t-en" hidden>{esc(e.get("title",""))}</h3>')
    if e.get("dek_cn") or e.get("dek"):
        parts.append(f'<p class="dek-cn">{esc(e.get("dek_cn",""))}</p>')
        parts.append(f'<p class="dek-en" hidden>{esc(e.get("dek",""))}</p>')
    if e.get("byline"):
        parts.append(f'<p class="byline">{esc(e["byline"])}</p>')
    # body paragraphs
    for p in paras(e.get("body_cn")):
        parts.append(f'<p class="b-cn">{esc(p)}</p>')
    for p in paras(e.get("body_en")):
        parts.append(f'<p class="b-en" hidden>{esc(p)}</p>')
    # context (collapsed)
    ctx = e.get("context_cn") or e.get("context")
    if ctx:
        attr = e.get("context_attr", "")
        attr_html = f' <span class="attr">（{esc(attr)}）</span>' if attr else ""
        ctx_paras = "".join(f'<p>{esc(p)}</p>' for p in paras(ctx if isinstance(ctx, str) else "\n\n".join(ctx)))
        ctx_en = e.get("context_en")
        ctx_en_html = ""
        if ctx_en:
            ctx_en_html = '<div class="ctx-en" hidden>' + "".join(
                f'<p>{esc(p)}</p>' for p in paras(ctx_en if isinstance(ctx_en, str) else "\n\n".join(ctx_en))) + "</div>"
        parts.append(
            '<details class="ctx"><summary>背景资料' + attr_html + '</summary>'
            f'<div class="ctx-cn">{ctx_paras}</div>{ctx_en_html}</details>')
    parts.append('</article>')
    return "\n".join(parts)

def data_table_card(e):
    # appendix: real table when the source uses | or aligned columns, else pre
    body = e.get("body_en", "")
    cap = esc(e.get("title_cn") or e.get("title", "")) + f' · {esc(e.get("page",""))}'
    table = None
    lines = [l for l in body.split("\n") if l.strip()]
    pipe_lines = [l for l in lines if "|" in l]
    if len(pipe_lines) >= 2:
        rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in pipe_lines]
        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        thead = "<tr>" + "".join(f"<th>{esc(c)}</th>" for c in rows[0]) + "</tr>"
        tb = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>"
                     for r in rows[1:60])
        table = (f'<div class="tblwrap"><table><caption>{cap}</caption>'
                 f'<thead>{thead}</thead><tbody>{tb}</tbody></table></div>')
    elif len(pipe_lines) == 1:
        cells = [c.strip() for c in pipe_lines[0].split("|") if c.strip()]
        if len(cells) > 1:
            td = "".join(f"<td>{esc(c)}</td>" for c in cells)
            table = (f'<div class="tblwrap"><table><caption>{cap}</caption>'
                     f'<tbody><tr>{td}</tr></tbody></table></div>')
    if table is None:
        # heuristic: split on 2+ spaces
        rows = [re.split(r"\s{2,}", l.strip()) for l in lines if len(l.strip()) > 3]
        if rows and max(len(r) for r in rows) > 1:
            thead = rows[0]
            thead_html = "<tr>" + "".join(f"<th>{esc(c)}</th>" for c in thead) + "</tr>"
            tb = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>"
                         for r in rows[1:60])
            table = (f'<div class="tblwrap"><table><caption>{cap}</caption>'
                     f'<thead>{thead_html}</thead><tbody>{tb}</tbody></table></div>')
        else:
            table = f'<pre class="raw">{esc(body[:4000])}</pre>'
    return (f'<article class="entry data" data-id="{esc(e.get("final_id", e["id"]))}">'
            f'<h3 class="t-cn">{esc(e.get("title_cn") or e.get("title",""))}</h3>'
            f'<h3 class="t-en" hidden>{esc(e.get("title",""))}</h3>'
            + "".join(f'<p class="b-cn">{esc(p)}</p>' for p in paras(e.get("body_cn")))
            + table + '</article>')

CSS = """
:root{--ink:#111827;--mut:#6b7280;--line:#e5e7eb;--bg:#ffffff;--soft:#f9fafb}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font-family:-apple-system,"PingFang SC","Microsoft YaHei","Noto Sans SC",sans-serif;line-height:1.75}
.wrap{max-width:860px;margin:0 auto;padding:24px 20px 80px}
header.hero{border-bottom:2px solid var(--ink);padding:8px 0 20px;margin-bottom:28px}
header.hero h1{font-size:26px;margin:0 0 6px;letter-spacing:.02em}
header.hero .sub{color:var(--mut);font-size:13px}
.langbar{position:sticky;top:0;background:rgba(255,255,255,.94);backdrop-filter:blur(6px);
border-bottom:1px solid var(--line);padding:10px 0;z-index:50;display:flex;gap:8px;align-items:center}
.langbar button{border:1px solid var(--line);background:#fff;border-radius:999px;padding:6px 16px;
font-size:14px;cursor:pointer}.langbar button.on{background:var(--ink);color:#fff;border-color:var(--ink)}
h2.sec{font-size:20px;margin:40px 0 4px;padding-top:8px}
.sec-en{color:var(--mut);font-size:12px;letter-spacing:.08em;text-transform:uppercase;margin-bottom:14px}
.entry{background:#fff;border:1px solid var(--line);border-radius:10px;padding:18px 20px;margin:14px 0}
.entry.data{background:var(--soft)}
.pri-tag{display:inline-block;font-size:12px;border:1px solid;border-radius:999px;padding:2px 10px;margin-bottom:10px}
h3{font-size:17px;margin:0 0 6px;line-height:1.5}
.dek-cn,.dek-en{color:var(--mut);font-size:14px;margin:0 0 8px}
.byline{font-size:12px;color:var(--mut);letter-spacing:.04em;margin:0 0 10px}
.entry p{font-size:15px;margin:0 0 10px}
.entry p:last-child{margin-bottom:0}
details.ctx{margin-top:12px;border-top:1px dashed var(--line);padding-top:10px}
details.ctx summary{cursor:pointer;font-size:13px;color:var(--mut)}
details.ctx .ctx-cn,details.ctx .ctx-en{font-size:13.5px;color:#374151;background:var(--soft);
border-radius:8px;padding:10px 12px;margin-top:8px}
.attr{font-size:12px}
.tblwrap{overflow-x:auto;margin-top:10px}
table{border-collapse:collapse;font-size:13px;min-width:640px}
caption{text-align:left;font-weight:600;padding:6px 0;color:var(--ink)}
th,td{border:1px solid var(--line);padding:6px 10px;text-align:left;white-space:nowrap}
thead th{background:#f3f4f6}
pre.raw{font-size:12.5px;overflow-x:auto;background:#f3f4f6;padding:12px;border-radius:8px}
footer{margin-top:48px;border-top:1px solid var(--line);padding-top:16px;color:var(--mut);font-size:12.5px}
.toc a{color:var(--ink);text-decoration:none;font-size:14px}
.toc li{margin:4px 0}
"""

JS = """
function setLang(l){document.documentElement.dataset.lang=l;
document.querySelectorAll('.t-cn,.dek-cn,.b-cn,.ctx-cn').forEach(e=>e.hidden=(l!=='cn'));
document.querySelectorAll('.t-en,.dek-en,.b-en,.ctx-en').forEach(e=>e.hidden=(l!=='en'));
document.querySelectorAll('.langbar button').forEach(b=>b.classList.toggle('on',b.dataset.l===l));}
document.addEventListener('DOMContentLoaded',()=>setLang('cn'));
"""

FOOTER = ("本页为机器辅助翻译的逐期摘要，中文正文译自 2026 年 10 月 12 日（周一）版《华尔街日报》"
          "原文，仅供个人阅读参考。数据表为原文摘录。")

def main():
    entries = json.load(open(FINAL, encoding="utf-8"))
    # order: readable sections first, data appendix last
    def sec_key(e):
        s = e.get("section", "News")
        try: return SECTION_ORDER.index(s)
        except ValueError: return 90
    entries.sort(key=lambda e: (sec_key(e), e.get("page",""), e["id"]))
    # group
    groups = {}
    for e in entries:
        groups.setdefault(e.get("section","News"), []).append(e)
    ordered_secs = sorted(groups.keys(), key=lambda s: SECTION_ORDER.index(s) if s in SECTION_ORDER else 90)
    # data appendix: type=data_table entries grouped under Data
    toc = "".join(
        f'<li><a href="#sec-{i}">{esc(SECTION_CN.get(s,s))} <span style="color:#6b7280">{esc(s)}</span></a></li>'
        for i, s in enumerate(ordered_secs))
    body_parts = [f'<nav class="toc"><ul>{toc}</ul></nav>']
    for i, s in enumerate(ordered_secs):
        body_parts.append(f'<h2 class="sec" id="sec-{i}">{esc(SECTION_CN.get(s,s))}</h2>'
                          f'<div class="sec-en">{esc(s)}</div>')
        for e in groups[s]:
            if e.get("type") == "data_table":
                body_parts.append(data_table_card(e))
            else:
                body_parts.append(entry_card(e))
    n_p1 = sum(1 for e in entries if e.get("priority")=="P1")
    n_p2 = sum(1 for e in entries if e.get("priority")=="P2")
    n_p3 = sum(1 for e in entries if e.get("priority")=="P3")
    doc = f"""<!DOCTYPE html><html lang="zh-CN" data-lang="cn"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>WSJ 深读 · 2026-10-12（周一）</title><style>{CSS}</style></head>
<body><div class="langbar wrap" style="padding-top:10px;padding-bottom:10px;max-width:860px">
<span style="font-size:13px;color:#6b7280">语言 / Language</span>
<button data-l="cn" class="on" onclick="setLang('cn')">中文</button>
<button data-l="en" onclick="setLang('en')">English</button></div>
<div class="wrap"><header class="hero"><h1>WSJ 深读 · 2026 年 10 月 12 日（周一）</h1>
<div class="sub">The Wall Street Journal · 全版覆盖 {len(entries)} 条（P1 {n_p1} / P2 {n_p2} / P3 {n_p3}）· 中英双语</div></header>
{''.join(body_parts)}
<footer>{esc(FOOTER)}</footer></div><script>{JS}</script></body></html>"""
    open(OUT, "w", encoding="utf-8").write(doc)
    print(f"wrote {OUT} ({len(entries)} entries)")

if __name__ == "__main__":
    main()
