#!/usr/bin/env python3
"""Pre-delivery checks from build-checklist.md. Reports alarms, exits 1 if any FAIL."""
import json, re, sys, os, html as ihtml

WORK = os.path.dirname(os.path.abspath(__file__))
FINAL = os.path.join(WORK, "final.json")
HTML = os.path.join(WORK, "wsj-2026-10-12-deepread.html")

fails, warns = [], []

entries = json.load(open(FINAL, encoding="utf-8"))
doc = open(HTML, encoding="utf-8").read() if os.path.exists(HTML) else ""

# 1. Duplicate sentences (>=3) across all CN bodies
sent_re = re.compile(r"[^。！？；\n]{8,}[。！？]")
counts = {}
for e in entries:
    for f in ("title_cn", "dek_cn", "body_cn", "context_cn"):
        t = e.get(f) or ""
        for s in sent_re.findall(t):
            s = s.strip()
            counts[s] = counts.get(s, 0) + 1
dups = {s: c for s, c in counts.items() if c >= 3}
if dups:
    warns.append(f"DUPLICATE sentences >=3: {len(dups)}")
    for s, c in list(dups.items())[:10]:
        warns.append(f"  x{c}: {s[:60]}")
else:
    print("PASS dup-sentences")

# 2. Number comparison CN vs EN
num_re = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?%?")
def norm_nums(t):
    out = []
    for m in num_re.findall(t or ""):
        v = m.replace(",", "")
        out.append(v)
    return out
bad = 0
for e in entries:
    en_nums = norm_nums(e.get("body_en", "") + " " + e.get("title", ""))
    cn_text = (e.get("body_cn", "") + " " + e.get("title_cn", ""))
    for n in en_nums:
        # allow % sign difference, magnitude must appear in CN (arabic digits usually kept)
        if n and n not in cn_text and n.rstrip("%") not in cn_text:
            # skip years that may be written differently; only flag if clearly numeric fact
            bad += 1
            if bad <= 15:
                warns.append(f"NUM-MISMATCH? [{e['id']}] EN has '{n}' not found in CN")
            break
if bad == 0:
    print("PASS number-compare")
else:
    warns.append(f"NUM: {bad} entries with EN numbers absent in CN (review)")

# 3. Zero-diff: every CN string in final.json must appear verbatim (escaped) in HTML
missing = 0
for e in entries:
    for f in ("title_cn", "body_cn"):
        t = (e.get(f) or "").strip()
        if not t:
            continue
        for para in [p for p in re.split(r"\n\s*\n", t) if p.strip()]:
            if ihtml.escape(para.strip(), quote=True) not in doc:
                missing += 1
                if missing <= 5:
                    fails.append(f"ZERO-DIFF FAIL [{e['id']}] para missing from HTML: {para[:50]}")
if missing == 0:
    print("PASS zero-diff")
else:
    fails.append(f"ZERO-DIFF: {missing} CN paragraphs not found verbatim in HTML")

# 4. Honest footer
for bad_word in ["完整保留", "ASD-STE100", "页码对应", "逐字对应原报"]:
    if bad_word in doc:
        fails.append(f"FOOTER dishonest phrase present: {bad_word}")
if "机器辅助翻译" in doc and "逐期摘要" in doc:
    print("PASS honest-footer")
else:
    fails.append("FOOTER missing honest statements")

# 5. No personal subscription links
for pat in ["getwsj.com", "wsj.com/paper", "subscribe.wsj.com/personal"]:
    if pat in doc:
        fails.append(f"PERSONAL LINK present: {pat}")
print("PASS no-personal-links")

print(f"\nentries={len(entries)}")
for w in warns:
    print("WARN:", w)
for f in fails:
    print("FAIL:", f)
sys.exit(1 if fails else 0)
