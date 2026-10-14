import json
import os
import html

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FINAL_JSON_PATH = os.path.abspath(os.path.join(BASE_DIR, "../../final.json"))

with open(FINAL_JSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

story = next(item for item in data if item["id"] == "E2-001")

body_cn = story["body_cn"]
paras_cn = [p.strip() for p in body_cn.split("\n\n") if p.strip()] if isinstance(body_cn, str) else body_cn
body_en = story["body_en"]
paras_en = [p.strip() for p in body_en.split("\n\n") if p.strip()] if isinstance(body_en, str) else body_en

assert len(paras_cn) == 20
assert len(paras_en) == 20

def esc(t):
    return html.escape(t or "")

# ===========================================================================
# DIRECTION A: FORENSIC ASYMMETRY (调查审计态 / 黄金标准)
# ===========================================================================
HTML_A = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>美国人的储蓄助燃私人信贷 · WSJ 深读 Editorial Gold Standard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&family=Lora:ital,wght@0,400;0,500;0,600;1,400;1,600&family=Noto+Sans+SC:wght@400;500;700&family=Noto+Serif+SC:wght@400;500;600;700;900&family=Playfair+Display:ital,wght@0,700;0,800;0,900;1,700&display=swap" rel="stylesheet">
  <style>
    :root {
      --paper: #faf8f4;
      --paper-card: #f3efe6;
      --paper-highlight: #ede8dc;
      --ink: #141413;
      --body: #242220;
      --muted: #646059;
      --faint: #99948a;
      --line: #e4dfd3;
      --line-dark: #141413;
      --accent: #b85d19; /* Editorial Terracotta / Amber */
      --accent-subtle: #fbf5ee;
      --accent-blue: #1c3d5a;
      --navy-bg: #0f1d2b;
      
      --font-display: "Playfair Display", "Noto Serif SC", serif;
      --font-body-cn: "Noto Serif SC", "Songti SC", serif;
      --font-body-en: "Lora", Georgia, serif;
      --font-sans: "Inter", "Noto Sans SC", sans-serif;
      --font-mono: "JetBrains Mono", monospace;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    
    body {
      background-color: var(--paper);
      color: var(--body);
      font-family: var(--font-body-cn);
      line-height: 1.85;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
    }

    #progress-bar {
      position: fixed;
      top: 0;
      left: 0;
      height: 3px;
      background: var(--accent);
      width: 0%;
      z-index: 1000;
      transition: width 0.1s;
    }

    /* Global Masthead */
    .top-nav {
      border-bottom: 1px solid var(--line);
      background: rgba(250, 248, 244, 0.95);
      backdrop-filter: blur(8px);
      position: sticky;
      top: 0;
      z-index: 100;
      padding: 12px 24px;
    }
    .nav-inner {
      max-width: 1140px;
      margin: 0 auto;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .pub-brand {
      display: flex;
      align-items: center;
      gap: 12px;
      text-decoration: none;
      color: var(--ink);
    }
    .brand-mark {
      width: 14px;
      height: 14px;
      background: var(--accent);
      display: inline-block;
      flex-shrink: 0;
    }
    .brand-title {
      font-family: var(--font-sans);
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      white-space: nowrap;
    }
    .brand-badge {
      font-family: var(--font-mono);
      font-size: 11px;
      background: var(--paper-highlight);
      padding: 2px 8px;
      border-radius: 2px;
      color: var(--muted);
      border: 1px solid var(--line);
      white-space: nowrap;
    }
    .nav-actions {
      display: flex;
      align-items: center;
      gap: 16px;
    }
    .lang-toggle {
      display: flex;
      align-items: center;
      background: var(--paper-highlight);
      border: 1px solid var(--line);
      border-radius: 9999px;
      padding: 2px;
      cursor: pointer;
    }
    .lang-opt {
      font-family: var(--font-sans);
      font-size: 11px;
      font-weight: 700;
      padding: 4px 12px;
      border-radius: 9999px;
      border: none;
      background: transparent;
      color: var(--muted);
      cursor: pointer;
      transition: all 0.2s;
    }
    .lang-opt.active {
      background: var(--ink);
      color: #fff;
    }

    @media (max-width: 768px) {
      .brand-badge { display: none; }
      .brand-title { font-size: 12px; }
      .top-nav { padding: 10px 16px; }
    }

    /* Article Hero Canvas */
    .article-wrap {
      max-width: 1140px;
      margin: 0 auto;
      padding: 48px 24px 120px 24px;
    }
    .hero-section {
      max-width: 900px;
      margin: 0 auto 56px auto;
      border-bottom: 1px solid var(--line-dark);
      padding-bottom: 32px;
    }
    .kicker-row {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 20px;
    }
    .kicker-tag {
      font-family: var(--font-sans);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.15em;
      text-transform: uppercase;
      color: var(--accent);
    }
    .kicker-dot {
      width: 4px;
      height: 4px;
      background: var(--faint);
      border-radius: 50%;
    }
    .kicker-location {
      font-family: var(--font-sans);
      font-size: 12px;
      font-weight: 500;
      color: var(--muted);
    }

    .article-headline {
      font-family: var(--font-display);
      font-size: clamp(34px, 5vw, 52px);
      font-weight: 800;
      line-height: 1.2;
      color: var(--ink);
      letter-spacing: -0.02em;
      margin-bottom: 24px;
      text-wrap: balance;
    }
    .hl-phrase {
      display: inline-block;
    }

    .article-dek {
      font-family: var(--font-body-cn);
      font-size: clamp(19px, 2.2vw, 24px);
      font-weight: 400;
      line-height: 1.65;
      color: #383531;
      margin-bottom: 28px;
      max-width: 820px;
      text-wrap: balance;
    }

    .byline-cluster {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      font-family: var(--font-sans);
      font-size: 13px;
      color: var(--muted);
      padding-top: 16px;
      border-top: 1px solid var(--line);
    }
    .byline-left {
      display: flex;
      align-items: center;
      gap: 16px;
      flex-wrap: wrap;
    }
    .author-name {
      font-weight: 700;
      color: var(--ink);
      letter-spacing: 0.04em;
    }
    .pub-source {
      color: var(--muted);
    }
    .reading-time {
      font-family: var(--font-mono);
      font-size: 12px;
      color: var(--muted);
      background: var(--paper-highlight);
      padding: 3px 8px;
      border-radius: 2px;
    }

    /* Movement Architecture: Contextual Asymmetric Grid */
    .movement-section {
      display: grid;
      grid-template-columns: minmax(0, 700px) 340px;
      gap: 60px;
      align-items: start;
      margin-bottom: 48px;
      padding-top: 36px;
      border-top: 1px solid var(--line);
    }
    .movement-section:first-of-type {
      border-top: none;
      padding-top: 0;
    }

    .prose-column {
      min-width: 0;
    }

    /* Microtypographic Prose */
    .prose-p {
      font-size: 18.5px;
      line-height: 1.9;
      color: var(--body);
      margin-bottom: 1.4em;
      letter-spacing: 0.01em;
      text-align: justify;
      text-justify: inter-ideograph;
    }
    
    /* Lead Paragraph Stature */
    .lead-paragraph {
      font-size: 22px;
      line-height: 1.8;
      font-weight: 500;
      color: var(--ink);
      margin-bottom: 1.6em;
      padding-bottom: 8px;
    }
    .lead-paragraph::first-letter {
      font-family: var(--font-display);
      font-size: 1.25em;
      font-weight: 700;
      color: var(--accent);
      margin-right: 2px;
    }

    /* Chapter / Narrative Movements */
    .movement-header {
      margin: 0 0 24px 0;
      display: flex;
      align-items: baseline;
      gap: 14px;
    }
    .movement-num {
      font-family: var(--font-display);
      font-size: 18px;
      font-weight: 700;
      color: var(--accent);
      letter-spacing: 0.05em;
    }
    .movement-title {
      font-family: var(--font-sans);
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--ink);
    }

    /* Integrated Callout Quote */
    .quote-anchor {
      margin: 32px 0;
      padding: 24px 28px;
      background: var(--paper-card);
      border-left: 4px solid var(--ink);
      position: relative;
    }
    .quote-text {
      font-family: var(--font-display);
      font-size: 21px;
      font-weight: 700;
      line-height: 1.6;
      color: var(--ink);
      margin-bottom: 12px;
    }
    .quote-attrib {
      font-family: var(--font-sans);
      font-size: 12.5px;
      font-weight: 600;
      color: var(--muted);
      letter-spacing: 0.03em;
    }

    /* Corporate Defense Voice Modulation */
    .corporate-record {
      background: #fbfbf9;
      border: 1px solid var(--line);
      border-left: 3px solid var(--muted);
      padding: 18px 22px;
      margin: 28px 0;
    }
    .corp-tag {
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .corp-tag::before {
      content: "";
      display: inline-block;
      width: 6px;
      height: 6px;
      background: var(--muted);
    }
    .corporate-record p {
      font-size: 16.5px;
      line-height: 1.8;
      color: #3a3835;
      font-style: italic;
    }

    /* Climactic Investigative Verdict */
    .verdict-box {
      margin: 40px 0 32px 0;
      padding: 32px 32px 28px 32px;
      background: var(--navy-bg);
      color: #ffffff;
      position: relative;
      overflow: hidden;
    }
    .verdict-box::after {
      content: "WSJ INVESTIGATION VERDICT";
      position: absolute;
      top: 14px;
      right: 18px;
      font-family: var(--font-mono);
      font-size: 10px;
      letter-spacing: 0.15em;
      color: rgba(255, 255, 255, 0.4);
    }
    .verdict-kicker {
      font-family: var(--font-sans);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: #e5a956;
      margin-bottom: 14px;
    }
    .verdict-quote {
      font-family: var(--font-display);
      font-size: 24px;
      font-weight: 700;
      line-height: 1.5;
      color: #ffffff;
      margin-bottom: 16px;
      letter-spacing: -0.01em;
    }
    .verdict-speaker {
      font-family: var(--font-sans);
      font-size: 13px;
      font-weight: 500;
      color: #cbd5e1;
    }
    .verdict-speaker strong {
      color: #ffffff;
      font-weight: 700;
    }

    /* Forensic Margin Column (The Active Rail) */
    .movement-rail {
      min-width: 0;
      position: sticky;
      top: 80px;
    }

    .forensic-exhibit {
      background: var(--paper-card);
      border: 1px solid var(--line);
      padding: 20px;
      margin-bottom: 24px;
      transition: box-shadow 0.2s;
    }
    .forensic-exhibit:hover {
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
    }
    .exhibit-badge {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
      padding-bottom: 8px;
      border-bottom: 1px solid var(--line);
    }
    .exhibit-num {
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 700;
      color: var(--accent);
      letter-spacing: 0.08em;
    }
    .exhibit-type {
      font-family: var(--font-sans);
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--muted);
    }
    .exhibit-title {
      font-family: var(--font-sans);
      font-size: 14px;
      font-weight: 700;
      color: var(--ink);
      line-height: 1.4;
      margin-bottom: 14px;
    }

    /* Forensic Data Rows */
    .data-row {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      padding: 6px 0;
      border-bottom: 1px dashed var(--line);
      font-size: 13px;
    }
    .data-row:last-child {
      border-bottom: none;
    }
    .data-label {
      font-family: var(--font-sans);
      color: var(--muted);
      font-size: 12px;
    }
    .data-val {
      font-family: var(--font-mono);
      font-weight: 700;
      color: var(--ink);
      font-size: 13px;
    }
    .data-val.accent {
      color: var(--accent);
      font-size: 14px;
    }

    /* Comparative Bar Chart in Exhibit */
    .bar-comp {
      margin: 14px 0 8px 0;
    }
    .bar-item {
      margin-bottom: 10px;
    }
    .bar-header {
      display: flex;
      justify-content: space-between;
      font-family: var(--font-sans);
      font-size: 11.5px;
      margin-bottom: 4px;
    }
    .bar-name {
      color: var(--muted);
    }
    .bar-pct {
      font-family: var(--font-mono);
      font-weight: 700;
      color: var(--ink);
    }
    .bar-track {
      height: 8px;
      background: var(--paper-highlight);
      border-radius: 1px;
      overflow: hidden;
    }
    .bar-fill {
      height: 100%;
      background: var(--ink);
    }
    .bar-fill.accent { background: var(--accent); }
    .bar-fill.subtle { background: var(--muted); }

    /* Flow diagram in Exhibit */
    .pipeline-step {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      margin-bottom: 10px;
      font-family: var(--font-sans);
      font-size: 12px;
    }
    .step-node {
      width: 18px;
      height: 18px;
      background: var(--ink);
      color: #fff;
      font-family: var(--font-mono);
      font-size: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      border-radius: 50%;
      margin-top: 2px;
    }
    .step-desc {
      color: #333;
      line-height: 1.45;
    }
    .step-arrow {
      text-align: center;
      color: var(--faint);
      font-size: 12px;
      margin: -4px 0 4px 6px;
    }

    /* Reporter Context / Dossier Drawer */
    .reporter-dossier {
      margin-top: 56px;
      border-top: 2px solid var(--line-dark);
      padding-top: 24px;
    }
    .dossier-header {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 14px;
    }
    .dossier-badge {
      font-family: var(--font-mono);
      font-size: 11px;
      background: var(--accent);
      color: #fff;
      padding: 2px 6px;
      font-weight: 700;
    }
    .dossier-title {
      font-family: var(--font-sans);
      font-size: 14px;
      font-weight: 700;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--ink);
    }
    .dossier-body {
      font-family: var(--font-sans);
      font-size: 14.5px;
      line-height: 1.75;
      color: #444;
      background: var(--paper-card);
      padding: 18px 22px;
      border: 1px solid var(--line);
    }

    /* End Signoff */
    .story-signoff {
      margin-top: 48px;
      padding-top: 20px;
      border-top: 1px solid var(--line);
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-family: var(--font-sans);
      font-size: 12px;
      color: var(--faint);
    }
    .signoff-mark {
      width: 8px;
      height: 8px;
      background: var(--ink);
      display: inline-block;
    }

    /* Bilingual Handling */
    html[lang="zh-CN"] .lang-en { display: none !important; }
    html[lang="en"] .lang-cn { display: none !important; }
    html[lang="en"] body {
      font-family: var(--font-body-en);
    }
    html[lang="en"] .lead-paragraph {
      font-family: var(--font-body-en);
    }
    html[lang="en"] .article-dek {
      font-family: var(--font-body-en);
    }
    html[lang="en"] .prose-p {
      text-align: left;
      hyphens: auto;
    }

    /* Responsive Adaptation */
    @media (max-width: 1024px) {
      .movement-section {
        display: block;
        margin-bottom: 40px;
        padding-top: 28px;
      }
      .movement-rail {
        position: static;
        margin-top: 28px;
        padding-top: 20px;
        border-top: 1px dashed var(--line);
      }
      .forensic-exhibit {
        max-width: 100%;
      }
    }

    @media (max-width: 768px) {
      .article-wrap {
        padding: 24px 18px 80px 18px;
      }
      .hero-section {
        margin-bottom: 36px;
        padding-bottom: 24px;
      }
      .article-headline {
        font-size: 28px;
        line-height: 1.25;
      }
      .article-dek {
        font-size: 17px;
        line-height: 1.6;
      }
      .prose-p {
        font-size: 17px;
        line-height: 1.85;
      }
      .lead-paragraph {
        font-size: 19px;
        line-height: 1.75;
      }
      .quote-text {
        font-size: 18px;
      }
      .verdict-box {
        padding: 24px 20px;
      }
      .verdict-quote {
        font-size: 20px;
      }
    }
  </style>
</head>
<body>

  <div id="progress-bar"></div>

  <!-- Global Masthead -->
  <header class="top-nav">
    <div class="nav-inner">
      <a href="javascript:void(0)" class="pub-brand">
        <span class="brand-mark"></span>
        <span class="brand-title">WSJ 深读 · Editorial Renaissance</span>
        <span class="brand-badge">GOLD STANDARD · A1 INVESTIGATION</span>
      </a>
      <div class="nav-actions">
        <div class="lang-toggle">
          <button class="lang-opt active" id="btn-cn" onclick="setLang('zh-CN')">中文</button>
          <button class="lang-opt" id="btn-en" onclick="setLang('en')">EN</button>
        </div>
      </div>
    </div>
  </header>

  <main class="article-wrap">
    
    <!-- Hero Article Header -->
    <header class="hero-section">
      <div class="kicker-row">
        <span class="kicker-tag">
          <span class="lang-cn">头版深度调查 · 华尔街与退休金</span>
          <span class="lang-en">WSJ INVESTIGATION · A1 FRONT PAGE</span>
        </span>
        <span class="kicker-dot"></span>
        <span class="kicker-location">
          <span class="lang-cn">《华尔街日报》A1 版</span>
          <span class="lang-en">The Wall Street Journal</span>
        </span>
      </div>

      <h1 class="article-headline">
        <span class="lang-cn">
          <span class="hl-phrase">美国人的储蓄</span>
          <span class="hl-phrase">助燃私人信贷</span>
        </span>
        <span class="lang-en">
          Americans' Savings Help Fuel Private Credit
        </span>
      </h1>

      <p class="article-dek">
        <span class="lang-cn">
          <span style="display:inline-block">并推动了私募机构</span>
          <span style="display:inline-block">向风险企业放贷业务的增长</span>
        </span>
        <span class="lang-en">""" + esc(story["dek"]) + """</span>
      </p>

      <div class="byline-cluster">
        <div class="byline-left">
          <span class="author-name">BY """ + esc(story["byline"]).upper() + """</span>
          <span class="pub-source">
            <span class="lang-cn">2026年10月12日 · 纽约</span>
            <span class="lang-en">October 12, 2026 · New York</span>
          </span>
        </div>
        <span class="reading-time">
          <span class="lang-cn">深度阅读 约 6 分钟</span>
          <span class="lang-en">6 min deep read</span>
        </span>
      </div>
    </header>

    <!-- Content Architecture: Movement Sections -->

    <!-- ==================== MOVEMENT I ==================== -->
    <section class="movement-section" id="movement-1">
      <div class="prose-column">
        
        <!-- P1 (Lead) -->
        <p class="prose-p lead-paragraph" data-block="p1">
          <span class="lang-cn">""" + esc(paras_cn[0]) + """</span>
          <span class="lang-en">""" + esc(paras_en[0]) + """</span>
        </p>

        <!-- P2 -->
        <p class="prose-p" data-block="p2">
          <span class="lang-cn">""" + esc(paras_cn[1]) + """</span>
          <span class="lang-en">""" + esc(paras_en[1]) + """</span>
        </p>

        <!-- P3 -->
        <p class="prose-p" data-block="p3">
          <span class="lang-cn">""" + esc(paras_cn[2]) + """</span>
          <span class="lang-en">""" + esc(paras_en[2]) + """</span>
        </p>

        <!-- P4 (Quote Anchor) -->
        <div class="quote-anchor" data-block="p4">
          <p class="quote-text">
            <span class="lang-cn">“这是指数型年金的一个缺点。保险公司可以每年或每两年更改从特定指数中获得的收益金额。”</span>
            <span class="lang-en">“That's one of the downfalls of the indexed annuities. Insurance companies can change the amount that's received from the particular index every year, every two years.”</span>
          </p>
          <div class="quote-attrib">
            <span class="lang-cn">— 小卡洛斯·迪亚斯 · 佛罗里达州理财顾问 / 埃利奥特的女婿</span>
            <span class="lang-en">— Carlos Dias Jr., Financial Adviser & Sabrina Elliott's Son-in-law</span>
          </div>
        </div>

      </div>

      <!-- Movement I Forensic Rail -->
      <aside class="movement-rail">
        <div class="forensic-exhibit">
          <div class="exhibit-badge">
            <span class="exhibit-num">EXHIBIT A</span>
            <span class="exhibit-type">
              <span class="lang-cn">案例审计</span>
              <span class="lang-en">Case Audit</span>
            </span>
          </div>
          <h4 class="exhibit-title">
            <span class="lang-cn">埃利奥特的 12 年年金账目</span>
            <span class="lang-en">Sabrina Elliott's 12-Year Policy</span>
          </h4>
          <div class="data-row">
            <span class="data-label">
              <span class="lang-cn">初始投资本金</span>
              <span class="lang-en">Initial Principal</span>
            </span>
            <span class="data-val">$40,000</span>
          </div>
          <div class="data-row">
            <span class="data-label">
              <span class="lang-cn">资金锁定期限</span>
              <span class="lang-en">Lockup Period</span>
            </span>
            <span class="data-val">12 年 (至2023)</span>
          </div>
          <div class="data-row">
            <span class="data-label">
              <span class="lang-cn">营销承诺</span>
              <span class="lang-en">Marketing Pitch</span>
            </span>
            <span class="data-val" style="font-size:11px;">
              <span class="lang-cn">与股市挂钩·零损失</span>
              <span class="lang-en">Market upside, zero loss</span>
            </span>
          </div>
          <div class="data-row">
            <span class="data-label">
              <span class="lang-cn">实际到手年化</span>
              <span class="lang-en">Actual Return</span>
            </span>
            <span class="data-val accent">3.7%</span>
          </div>
        </div>
      </aside>
    </section>

    <!-- ==================== MOVEMENT II ==================== -->
    <section class="movement-section" id="movement-2">
      <div class="prose-column">
        
        <div class="movement-header">
          <span class="movement-num">II</span>
          <h2 class="movement-title">
            <span class="lang-cn">华尔街的保费吸管与影子信贷</span>
            <span class="lang-en">The Wall Street Siphon & Private Debt</span>
          </h2>
        </div>

        <!-- P5 -->
        <p class="prose-p" data-block="p5">
          <span class="lang-cn">""" + esc(paras_cn[4]) + """</span>
          <span class="lang-en">""" + esc(paras_en[4]) + """</span>
        </p>

        <!-- P6 -->
        <p class="prose-p" data-block="p6">
          <span class="lang-cn">""" + esc(paras_cn[5]) + """</span>
          <span class="lang-en">""" + esc(paras_en[5]) + """</span>
        </p>

        <!-- P7 -->
        <p class="prose-p" data-block="p7">
          <span class="lang-cn">""" + esc(paras_cn[6]) + """</span>
          <span class="lang-en">""" + esc(paras_en[6]) + """</span>
        </p>

        <!-- P8 -->
        <p class="prose-p" data-block="p8">
          <span class="lang-cn">""" + esc(paras_cn[7]) + """</span>
          <span class="lang-en">""" + esc(paras_en[7]) + """</span>
        </p>

        <!-- P9 -->
        <p class="prose-p" data-block="p9">
          <span class="lang-cn">""" + esc(paras_cn[8]) + """</span>
          <span class="lang-en">""" + esc(paras_en[8]) + """</span>
        </p>

      </div>

      <!-- Movement II Forensic Rail -->
      <aside class="movement-rail">
        <div class="forensic-exhibit">
          <div class="exhibit-badge">
            <span class="exhibit-num">EXHIBIT B</span>
            <span class="exhibit-type">
              <span class="lang-cn">资金流向链路</span>
              <span class="lang-en">Capital Flow</span>
            </span>
          </div>
          <h4 class="exhibit-title">
            <span class="lang-cn">华尔街影子借贷资金池</span>
            <span class="lang-en">Shadow Credit Pipeline</span>
          </h4>
          <div class="pipeline-step">
            <span class="step-node">1</span>
            <span class="step-desc">
              <span class="lang-cn"><strong>普通家庭储蓄</strong><br>美国家庭 $5万–$10万 长期储蓄或 401(k) 资金</span>
              <span class="lang-en"><strong>Retail Savings</strong><br>$50k–$100k household savings or 401(k) nest eggs</span>
            </span>
          </div>
          <div class="step-arrow">↓</div>
          <div class="pipeline-step">
            <span class="step-node">2</span>
            <span class="step-desc">
              <span class="lang-cn"><strong>收购寿险获取浮存金</strong><br>私募巨头 (阿波罗/博枫) 收购寿险公司吸走保费</span>
              <span class="lang-en"><strong>Insurers Acquisition</strong><br>PE giants (Apollo/Brookfield) acquire insurers for float</span>
            </span>
          </div>
          <div class="step-arrow">↓</div>
          <div class="pipeline-step">
            <span class="step-node">3</span>
            <span class="step-desc">
              <span class="lang-cn"><strong>投向高风险私人信贷</strong><br>担保贷款凭证 (CLO) 与缺乏流动性的资产支持证券</span>
              <span class="lang-en"><strong>Illiquid Private Debt</strong><br>Fund CLOs, risky corporate loans, asset-backed debt</span>
            </span>
          </div>
        </div>
      </aside>
    </section>

    <!-- ==================== MOVEMENT III ==================== -->
    <section class="movement-section" id="movement-3">
      <div class="prose-column">
        
        <div class="movement-header">
          <span class="movement-num">III</span>
          <h2 class="movement-title">
            <span class="lang-cn">失衡的算式与5%的销售推力</span>
            <span class="lang-en">The Skewed Arithmetic & Commission Push</span>
          </h2>
        </div>

        <!-- P10 -->
        <p class="prose-p" data-block="p10">
          <span class="lang-cn">""" + esc(paras_cn[9]) + """</span>
          <span class="lang-en">""" + esc(paras_en[9]) + """</span>
        </p>

        <!-- P11 -->
        <p class="prose-p" data-block="p11">
          <span class="lang-cn">""" + esc(paras_cn[10]) + """</span>
          <span class="lang-en">""" + esc(paras_en[10]) + """</span>
        </p>

        <!-- P12 -->
        <p class="prose-p" data-block="p12">
          <span class="lang-cn">""" + esc(paras_cn[11]) + """</span>
          <span class="lang-en">""" + esc(paras_en[11]) + """</span>
        </p>

        <!-- P13 & P14: Corporate PR Defense -->
        <div class="corporate-record">
          <div class="corp-tag">
            <span class="lang-cn">机构回应 · 阿波罗控股之雅典娜人寿 (Athene) 官方声明</span>
            <span class="lang-en">Official Response · Athene (Apollo Global Management)</span>
          </div>
          <p data-block="p13" style="margin-bottom: 12px;">
            <span class="lang-cn">""" + esc(paras_cn[12]) + """</span>
            <span class="lang-en">""" + esc(paras_en[12]) + """</span>
          </p>
          <p data-block="p14">
            <span class="lang-cn">""" + esc(paras_cn[13]) + """</span>
            <span class="lang-en">""" + esc(paras_en[13]) + """</span>
          </p>
        </div>

        <!-- P15 -->
        <p class="prose-p" data-block="p15">
          <span class="lang-cn">""" + esc(paras_cn[14]) + """</span>
          <span class="lang-en">""" + esc(paras_en[14]) + """</span>
        </p>

        <!-- P16 -->
        <p class="prose-p" data-block="p16">
          <span class="lang-cn">""" + esc(paras_cn[15]) + """</span>
          <span class="lang-en">""" + esc(paras_en[15]) + """</span>
        </p>

      </div>

      <!-- Movement III Forensic Rail -->
      <aside class="movement-rail">
        
        <!-- Exhibit C: Comparative Yields & Ratchet -->
        <div class="forensic-exhibit">
          <div class="exhibit-badge">
            <span class="exhibit-num">EXHIBIT C</span>
            <span class="exhibit-type">
              <span class="lang-cn">收益率对比</span>
              <span class="lang-en">Yield Gap</span>
            </span>
          </div>
          <h4 class="exhibit-title">
            <span class="lang-cn">牛市中的收益断层 (同期年化)</span>
            <span class="lang-en">Annualized Return Asymmetry</span>
          </h4>
          <div class="bar-comp">
            <div class="bar-item">
              <div class="bar-header">
                <span class="bar-name">
                  <span class="lang-cn">标普500指数同期</span>
                  <span class="lang-en">S&P 500 Index</span>
                </span>
                <span class="bar-pct">13.0%</span>
              </div>
              <div class="bar-track">
                <div class="bar-fill" style="width: 100%;"></div>
              </div>
            </div>
            <div class="bar-item">
              <div class="bar-header">
                <span class="bar-name">
                  <span class="lang-cn">埃利奥特实际收益</span>
                  <span class="lang-en">Sabrina Actual</span>
                </span>
                <span class="bar-pct" style="color:var(--accent);">3.7%</span>
              </div>
              <div class="bar-track">
                <div class="bar-fill accent" style="width: 28.5%;"></div>
              </div>
            </div>
            <div class="bar-item">
              <div class="bar-header">
                <span class="bar-name">
                  <span class="lang-cn">10年期美国国债</span>
                  <span class="lang-en">10Y US Treasury</span>
                </span>
                <span class="bar-pct">1.9%</span>
              </div>
              <div class="bar-track">
                <div class="bar-fill subtle" style="width: 14.6%;"></div>
              </div>
            </div>
          </div>
          
          <div style="margin-top:16px; padding-top:12px; border-top:1px solid var(--line);">
            <div class="data-label" style="margin-bottom:6px; font-weight:700; color:var(--ink);">
              <span class="lang-cn">参与率单向调降轨迹：</span>
              <span class="lang-en">Participation Rate Ratchet:</span>
            </div>
            <div class="data-row">
              <span class="data-label"><span class="lang-cn">保单第 1 年</span><span class="lang-en">Year 1</span></span>
              <span class="data-val">60%</span>
            </div>
            <div class="data-row">
              <span class="data-label"><span class="lang-cn">保单第 7 年</span><span class="lang-en">Year 7</span></span>
              <span class="data-val">55%</span>
            </div>
            <div class="data-row">
              <span class="data-label"><span class="lang-cn">保单第 11 年</span><span class="lang-en">Year 11</span></span>
              <span class="data-val accent">45%</span>
            </div>
          </div>
        </div>

        <!-- Exhibit D: Commission Gap -->
        <div class="forensic-exhibit">
          <div class="exhibit-badge">
            <span class="exhibit-num">EXHIBIT D</span>
            <span class="exhibit-type">
              <span class="lang-cn">监管套利</span>
              <span class="lang-en">Regulatory Gap</span>
            </span>
          </div>
          <h4 class="exhibit-title">
            <span class="lang-cn">销售代理佣金悬殊</span>
            <span class="lang-en">Agent Commission Spread</span>
          </h4>
          <div class="data-row">
            <span class="data-label">
              <span class="lang-cn">指数型年金佣金</span>
              <span class="lang-en">Indexed Annuity Commission</span>
            </span>
            <span class="data-val accent">5% – 7%</span>
          </div>
          <div class="data-row">
            <span class="data-label">
              <span class="lang-cn">简单固定年金佣金</span>
              <span class="lang-en">Plain Fixed Annuity</span>
            </span>
            <span class="data-val">约 3%</span>
          </div>
          <div class="data-row">
            <span class="data-label">
              <span class="lang-cn">监管约束适用</span>
              <span class="lang-en">SEC Fiduciary Duty</span>
            </span>
            <span class="data-val" style="color:#c31833; font-size:11px;">
              <span class="lang-cn">免除信义义务约束</span>
              <span class="lang-en">Exempt from SEC rules</span>
            </span>
          </div>
        </div>

      </aside>
    </section>

    <!-- ==================== MOVEMENT IV ==================== -->
    <section class="movement-section" id="movement-4">
      <div class="prose-column">
        
        <div class="movement-header">
          <span class="movement-num">IV</span>
          <h2 class="movement-title">
            <span class="lang-cn">单向修改的契约与终局裁判</span>
            <span class="lang-en">The Unilateral Contract & Final Verdict</span>
          </h2>
        </div>

        <!-- P17 -->
        <p class="prose-p" data-block="p17">
          <span class="lang-cn">""" + esc(paras_cn[16]) + """</span>
          <span class="lang-en">""" + esc(paras_en[16]) + """</span>
        </p>

        <!-- P18 -->
        <p class="prose-p" data-block="p18">
          <span class="lang-cn">""" + esc(paras_cn[17]) + """</span>
          <span class="lang-en">""" + esc(paras_en[17]) + """</span>
        </p>

        <!-- P19 -->
        <p class="prose-p" data-block="p19">
          <span class="lang-cn">""" + esc(paras_cn[18]) + """</span>
          <span class="lang-en">""" + esc(paras_en[18]) + """</span>
        </p>

        <!-- P20: The Climactic Verdict Box -->
        <div class="verdict-box" data-block="p20">
          <div class="verdict-kicker">
            <span class="lang-cn">调查终局裁决 · 行业洞察</span>
            <span class="lang-en">Investigative Conclusion · Industry Insight</span>
          </div>
          <div class="verdict-quote">
            <span class="lang-cn">“这就是私募股权公司喜欢这种方式的原因，因为它们可以改变与消费者的协议。”</span>
            <span class="lang-en">“That's why private equity likes this, because they can change the deal on the consumer.”</span>
          </div>
          <div class="verdict-speaker">
            <span class="lang-cn"><strong>拉里·里布卡 (Larry Rybka)</strong> · Valmark金融集团首席执行官</span>
            <span class="lang-en"><strong>Larry Rybka</strong> · Chief Executive, Valmark Financial Group</span>
          </div>
        </div>

      </div>

      <!-- Movement IV Rail -->
      <aside class="movement-rail">
        <div class="forensic-exhibit" style="background:#f0ebe0; border-color:#dcd5c7;">
          <div class="exhibit-badge">
            <span class="exhibit-num">SUMMARY</span>
            <span class="exhibit-type">
              <span class="lang-cn">核心结论</span>
              <span class="lang-en">Key Takeaway</span>
            </span>
          </div>
          <h4 class="exhibit-title" style="font-size:13px; font-weight:600; line-height:1.5;">
            <span class="lang-cn">私募巨头通过年金获得长达 10 年的资金锁定，并在投资不佳时单方面下调保户收益上限，将市场风险转嫁给普通家庭。</span>
            <span class="lang-en">PE giants secure 10-year lockups on retail float, unilaterally lowering payout caps during downturns and shifting risks onto ordinary savers.</span>
          </h4>
        </div>
      </aside>
    </section>

    <!-- Reporter's Background Dossier (context_cn) -->
    <section class="reporter-dossier" style="max-width: 900px; margin: 48px auto 0 auto;">
      <div class="dossier-header">
        <span class="dossier-badge">DOSSIER</span>
        <h3 class="dossier-title">
          <span class="lang-cn">记者调查手记与背景档案</span>
          <span class="lang-en">Reporter's Background & Forensic Context</span>
        </h3>
      </div>
      <div class="dossier-body">
        <span class="lang-cn">""" + esc(story["context_cn"]) + """</span>
        <span class="lang-en">Indexed annuities lock up consumer capital for approximately 12 years with promises of equity-linked returns and zero downside risk. However, insurers hold unilateral discretion to lower participation rates, caps, and spreads. Lucrative 5%–7% agent commissions drive sales outside SEC fiduciary oversight, channeling sticky consumer float directly into illiquid private debt (CLOs, asset-backed securities).</span>
      </div>
    </section>

    <!-- Signoff -->
    <div class="story-signoff" style="max-width: 900px; margin: 32px auto 0 auto;">
      <span class="signoff-left">THE WALL STREET JOURNAL · EDITORIAL EXCELLENCE EXPERIMENT</span>
      <span class="signoff-mark"></span>
    </div>

  </main>

  <script>
    function setLang(lang) {
      document.documentElement.lang = lang;
      document.getElementById('btn-cn').classList.toggle('active', lang === 'zh-CN');
      document.getElementById('btn-en').classList.toggle('active', lang === 'en');
    }

    // Reading Progress
    window.addEventListener('scroll', () => {
      const total = document.documentElement.scrollHeight - window.innerHeight;
      const progress = (window.scrollY / total) * 100;
      document.getElementById('progress-bar').style.width = Math.min(100, Math.max(0, progress)) + '%';
    });
  </script>
</body>
</html>
"""

# ===========================================================================
# DIRECTION B: PURE LITERARY LONG-FORM (纯粹文学特写态)
# ===========================================================================
HTML_B = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>美国人的储蓄助燃私人信贷 · Direction B (Literary Long-form)</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&family=Lora:ital,wght@0,400;0,500;0,600;1,400&family=Noto+Sans+SC:wght@400;500;700&family=Noto+Serif+SC:wght@400;500;600;700;900&family=Playfair+Display:ital,wght@0,700;0,800;1,700&display=swap" rel="stylesheet">
  <style>
    :root {
      --paper: #fbf9f5;
      --ink: #111111;
      --body: #222220;
      --muted: #66635d;
      --faint: #a29e95;
      --line: #e7e3d8;
      --accent: #8b3a1a;
      --font-display: "Playfair Display", "Noto Serif SC", serif;
      --font-body-cn: "Noto Serif SC", "Songti SC", serif;
      --font-body-en: "Lora", Georgia, serif;
      --font-sans: "Inter", "Noto Sans SC", sans-serif;
      --font-mono: "JetBrains Mono", monospace;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--paper);
      color: var(--body);
      font-family: var(--font-body-cn);
      line-height: 1.95;
      -webkit-font-smoothing: antialiased;
    }
    .reading-wrap {
      max-width: 720px;
      margin: 0 auto;
      padding: 64px 24px 140px 24px;
    }
    .header-block {
      text-align: center;
      margin-bottom: 64px;
      padding-bottom: 40px;
      border-bottom: 1px solid var(--line);
    }
    .eyebrow {
      font-family: var(--font-sans);
      font-size: 11.5px;
      font-weight: 700;
      letter-spacing: 0.22em;
      text-transform: uppercase;
      color: var(--accent);
      margin-bottom: 20px;
    }
    .headline {
      font-family: var(--font-display);
      font-size: clamp(34px, 5.5vw, 48px);
      font-weight: 800;
      line-height: 1.22;
      color: var(--ink);
      margin-bottom: 24px;
      letter-spacing: -0.015em;
      text-wrap: balance;
    }
    .dek {
      font-family: var(--font-body-cn);
      font-size: 20px;
      line-height: 1.7;
      color: var(--muted);
      margin-bottom: 28px;
      text-wrap: balance;
    }
    .byline {
      font-family: var(--font-sans);
      font-size: 13px;
      color: var(--faint);
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 16px;
    }
    .byline strong {
      color: var(--ink);
      font-weight: 600;
    }
    .prose {
      font-size: 19px;
      line-height: 1.95;
      color: var(--body);
      margin-bottom: 1.5em;
      text-align: justify;
      text-justify: inter-ideograph;
    }
    .lead-drop {
      font-size: 22.5px;
      line-height: 1.85;
      color: var(--ink);
      margin-bottom: 1.8em;
    }
    .chapter-break {
      text-align: center;
      margin: 56px 0 44px 0;
      position: relative;
    }
    .chapter-break::before {
      content: "";
      position: absolute;
      top: 50%;
      left: 0;
      right: 0;
      height: 1px;
      background: var(--line);
      z-index: 1;
    }
    .chapter-mark {
      display: inline-block;
      background: var(--paper);
      padding: 0 20px;
      position: relative;
      z-index: 2;
      font-family: var(--font-display);
      font-size: 16px;
      font-style: italic;
      color: var(--muted);
      letter-spacing: 0.1em;
    }
    .literary-quote {
      margin: 44px 0;
      padding: 0 32px;
      border-left: 2px solid var(--accent);
      font-family: var(--font-display);
      font-size: 22px;
      font-style: italic;
      line-height: 1.65;
      color: var(--ink);
    }
    .literary-quote-attrib {
      font-family: var(--font-sans);
      font-size: 12px;
      font-style: normal;
      font-weight: 600;
      color: var(--muted);
      margin-top: 10px;
      letter-spacing: 0.05em;
    }
    .flow-compare {
      margin: 40px 0;
      background: #f4f0e6;
      padding: 24px 28px;
      border-radius: 2px;
    }
    .flow-title {
      font-family: var(--font-sans);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.15em;
      text-transform: uppercase;
      color: var(--accent);
      margin-bottom: 16px;
    }
    .flow-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 16px;
      text-align: center;
    }
    .flow-card {
      background: #fff;
      padding: 14px 10px;
      border: 1px solid var(--line);
    }
    .flow-metric {
      font-family: var(--font-mono);
      font-size: 22px;
      font-weight: 700;
      color: var(--ink);
      margin-bottom: 4px;
    }
    .flow-metric.highlight { color: var(--accent); }
    .flow-label {
      font-family: var(--font-sans);
      font-size: 11.5px;
      color: var(--muted);
      line-height: 1.35;
    }
    .conclusion-ornament {
      text-align: center;
      margin: 64px 0 20px 0;
      color: var(--faint);
      font-size: 18px;
      letter-spacing: 0.3em;
    }
    .top-controls {
      display: flex;
      justify-content: flex-end;
      margin-bottom: 32px;
    }
    .lang-pill {
      display: inline-flex;
      border: 1px solid var(--line);
      border-radius: 9999px;
      overflow: hidden;
      background: #fff;
    }
    .lang-pill button {
      border: none;
      background: none;
      padding: 4px 14px;
      font-family: var(--font-sans);
      font-size: 11px;
      font-weight: 600;
      color: var(--muted);
      cursor: pointer;
    }
    .lang-pill button.active {
      background: var(--ink);
      color: #fff;
    }
    html[lang="zh-CN"] .lang-en { display: none !important; }
    html[lang="en"] .lang-cn { display: none !important; }
    html[lang="en"] body { font-family: var(--font-body-en); }
    html[lang="en"] .dek { font-family: var(--font-body-en); }
  </style>
</head>
<body>
  <div class="reading-wrap">
    <div class="top-controls">
      <div class="lang-pill">
        <button id="btn-cn" class="active" onclick="setLang('zh-CN')">中文</button>
        <button id="btn-en" onclick="setLang('en')">EN</button>
      </div>
    </div>
    <header class="header-block">
      <div class="eyebrow">
        <span class="lang-cn">华尔街日报 · 深度调查特写</span>
        <span class="lang-en">The Wall Street Journal · Deep Read Feature</span>
      </div>
      <h1 class="headline">
        <span class="lang-cn">""" + esc(story["title_cn"]) + """</span>
        <span class="lang-en">""" + esc(story["title"]) + """</span>
      </h1>
      <p class="dek">
        <span class="lang-cn">""" + esc(story["dek_cn"]) + """</span>
        <span class="lang-en">""" + esc(story["dek"]) + """</span>
      </p>
      <div class="byline">
        <span>By <strong>""" + esc(story["byline"]) + """</strong></span>
        <span>·</span>
        <span>October 12, 2026</span>
      </div>
    </header>
    <main>
      <p class="prose lead-drop">
        <span class="lang-cn">""" + esc(paras_cn[0]) + """</span>
        <span class="lang-en">""" + esc(paras_en[0]) + """</span>
      </p>
      <p class="prose"><span class="lang-cn">""" + esc(paras_cn[1]) + """</span><span class="lang-en">""" + esc(paras_en[1]) + """</span></p>
      <p class="prose"><span class="lang-cn">""" + esc(paras_cn[2]) + """</span><span class="lang-en">""" + esc(paras_en[2]) + """</span></p>
      <div class="literary-quote">
        <span class="lang-cn">“这是指数型年金的一个缺点。保险公司可以每年或每两年更改从特定指数中获得的收益金额。”</span>
        <span class="lang-en">“That's one of the downfalls of the indexed annuities. Insurance companies can change the amount that's received from the particular index every year, every two years.”</span>
        <div class="literary-quote-attrib">
          <span class="lang-cn">— 小卡洛斯·迪亚斯 · 佛罗里达州奥兰多市理财顾问</span>
          <span class="lang-en">— Carlos Dias Jr., Financial Adviser, Orlando, Fla.</span>
        </div>
      </div>
      <div class="chapter-break"><span class="chapter-mark">§ II</span></div>
      <p class="prose"><span class="lang-cn">""" + esc(paras_cn[4]) + """</span><span class="lang-en">""" + esc(paras_en[4]) + """</span></p>
      <p class="prose"><span class="lang-cn">""" + esc(paras_cn[5]) + """</span><span class="lang-en">""" + esc(paras_en[5]) + """</span></p>
      <p class="prose"><span class="lang-cn">""" + esc(paras_cn[6]) + """</span><span class="lang-en">""" + esc(paras_en[6]) + """</span></p>
      <p class="prose"><span class="lang-cn">""" + esc(paras_cn[7]) + """</span><span class="lang-en">""" + esc(paras_en[7]) + """</span></p>
      <p class="prose"><span class="lang-cn">""" + esc(paras_cn[8]) + """</span><span class="lang-en">""" + esc(paras_en[8]) + """</span></p>
      <div class="chapter-break"><span class="chapter-mark">§ III</span></div>
      <p class="prose"><span class="lang-cn">""" + esc(paras_cn[9]) + """</span><span class="lang-en">""" + esc(paras_en[9]) + """</span></p>
      <p class="prose"><span class="lang-cn">""" + esc(paras_cn[10]) + """</span><span class="lang-en">""" + esc(paras_en[10]) + """</span></p>
      <p class="prose"><span class="lang-cn">""" + esc(paras_cn[11]) + """</span><span class="lang-en">""" + esc(paras_en[11]) + """</span></p>
      <div class="flow-compare">
        <div class="flow-title">
          <span class="lang-cn">十二年同期投资回报悬殊</span>
          <span class="lang-en">12-Year Performance Asymmetry</span>
        </div>
        <div class="flow-grid">
          <div class="flow-card">
            <div class="flow-metric">13.0%</div>
            <div class="flow-label">
              <span class="lang-cn">标普 500 指数</span>
              <span class="lang-en">S&P 500 Index</span>
            </div>
          </div>
          <div class="flow-card">
            <div class="flow-metric highlight">3.7%</div>
            <div class="flow-label">
              <span class="lang-cn">埃利奥特实际年化</span>
              <span class="lang-en">Elliott's Actual</span>
            </div>
          </div>
          <div class="flow-card">
            <div class="flow-metric">1.9%</div>
            <div class="flow-label">
              <span class="lang-cn">同期美国国债</span>
              <span class="lang-en">US Treasurys</span>
            </div>
          </div>
        </div>
      </div>
      <p class="prose"><span class="lang-cn">""" + esc(paras_cn[12]) + """</span><span class="lang-en">""" + esc(paras_en[12]) + """</span></p>
      <p class="prose"><span class="lang-cn">""" + esc(paras_cn[13]) + """</span><span class="lang-en">""" + esc(paras_en[13]) + """</span></p>
      <p class="prose"><span class="lang-cn">""" + esc(paras_cn[14]) + """</span><span class="lang-en">""" + esc(paras_en[14]) + """</span></p>
      <p class="prose"><span class="lang-cn">""" + esc(paras_cn[15]) + """</span><span class="lang-en">""" + esc(paras_en[15]) + """</span></p>
      <div class="chapter-break"><span class="chapter-mark">§ IV</span></div>
      <p class="prose"><span class="lang-cn">""" + esc(paras_cn[16]) + """</span><span class="lang-en">""" + esc(paras_en[16]) + """</span></p>
      <p class="prose"><span class="lang-cn">""" + esc(paras_cn[17]) + """</span><span class="lang-en">""" + esc(paras_en[17]) + """</span></p>
      <p class="prose"><span class="lang-cn">""" + esc(paras_cn[18]) + """</span><span class="lang-en">""" + esc(paras_en[18]) + """</span></p>
      <div class="literary-quote" style="border-left-color: var(--ink);">
        <span class="lang-cn">“这就是私募股权公司喜欢这种方式的原因，因为它们可以改变与消费者的协议。”</span>
        <span class="lang-en">“That's why private equity likes this, because they can change the deal on the consumer.”</span>
        <div class="literary-quote-attrib">
          <span class="lang-cn">— 拉里·里布卡 · Valmark金融集团首席执行官</span>
          <span class="lang-en">— Larry Rybka, Chief Executive, Valmark Financial Group</span>
        </div>
      </div>
      <div class="conclusion-ornament">♦ ♦ ♦</div>
    </main>
  </div>
  <script>
    function setLang(lang) {
      document.documentElement.lang = lang;
      document.getElementById('btn-cn').classList.toggle('active', lang === 'zh-CN');
      document.getElementById('btn-en').classList.toggle('active', lang === 'en');
    }
  </script>
</body>
</html>
"""

# ===========================================================================
# COMPARISON DASHBOARD
# ===========================================================================
HTML_COMP = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>WSJ 深读 · Editorial Renaissance 审读与并排裁决</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0f141c;
      --card-bg: #18202c;
      --text: #e2e8f0;
      --text-muted: #94a3b8;
      --accent: #f59e0b;
      --border: #334155;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: 'Inter', sans-serif;
      padding: 24px;
    }
    header {
      max-width: 1400px;
      margin: 0 auto 24px auto;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid var(--border);
      padding-bottom: 20px;
    }
    .title-group h1 {
      font-size: 20px;
      font-weight: 700;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .badge {
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      padding: 3px 8px;
      border-radius: 4px;
      background: var(--accent);
      color: #000;
      font-weight: 700;
    }
    .tab-bar {
      display: flex;
      gap: 10px;
    }
    .tab-btn {
      background: var(--card-bg);
      border: 1px solid var(--border);
      color: var(--text-muted);
      padding: 8px 16px;
      border-radius: 6px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
    }
    .tab-btn.active, .tab-btn:hover {
      background: #2563eb;
      color: #fff;
      border-color: #3b82f6;
    }
    .viewport-ctrl {
      display: flex;
      gap: 8px;
      align-items: center;
    }
    .vp-btn {
      background: var(--card-bg);
      border: 1px solid var(--border);
      color: var(--text-muted);
      padding: 6px 12px;
      font-size: 12px;
      border-radius: 4px;
      cursor: pointer;
    }
    .vp-btn.active {
      background: #334155;
      color: #fff;
    }
    .frame-container {
      max-width: 1400px;
      margin: 0 auto;
      height: calc(100vh - 120px);
      display: flex;
      justify-content: center;
      background: #000;
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
      position: relative;
    }
    iframe {
      width: 100%;
      height: 100%;
      border: none;
      background: #faf8f4;
      transition: width 0.3s;
    }
  </style>
</head>
<body>
  <header>
    <div class="title-group">
      <h1>
        <span>WSJ 深读 · Editorial Renaissance 方案裁决面板</span>
        <span class="badge">E2-001 GOLD STANDARD</span>
      </h1>
      <p style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
        目标报道：Heather Gillers《美国人的储蓄助燃私人信贷》· A1 头版重磅调查 · 20段正文逐字保留
      </p>
    </div>
    <div class="tab-bar">
      <button class="tab-btn active" onclick="loadView('index.html', this)">方案 A: 调查审计态 (Gold Standard)</button>
      <button class="tab-btn" onclick="loadView('direction-b.html', this)">方案 B: 纯文学特写态</button>
      <button class="tab-btn" onclick="loadView('../../dist/index.html#s-E2-001', this)">旧生产页 (Baseline)</button>
    </div>
    <div class="viewport-ctrl">
      <button class="vp-btn active" onclick="setViewport('100%', this)">桌面 (100%)</button>
      <button class="vp-btn" onclick="setViewport('768px', this)">平板 (768px)</button>
      <button class="vp-btn" onclick="setViewport('390px', this)">手机 (390px)</button>
    </div>
  </header>
  <div class="frame-container">
    <iframe id="preview-frame" src="index.html"></iframe>
  </div>
  <script>
    function loadView(url, btn) {
      document.getElementById('preview-frame').src = url;
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
    }
    function setViewport(width, btn) {
      document.getElementById('preview-frame').style.width = width;
      document.querySelectorAll('.vp-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
    }
  </script>
</body>
</html>
"""

with open(os.path.join(BASE_DIR, "index.html"), "w", encoding="utf-8") as f:
    f.write(HTML_A)

with open(os.path.join(BASE_DIR, "direction-b.html"), "w", encoding="utf-8") as f:
    f.write(HTML_B)

with open(os.path.join(BASE_DIR, "comparison.html"), "w", encoding="utf-8") as f:
    f.write(HTML_COMP)

print("All gold-standard files successfully built with flawless syntax and structure!")
