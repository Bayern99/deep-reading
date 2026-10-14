#!/usr/bin/env python3
"""WSJ 深读 · Editorial Plan 测试页构建器。
为指定文章生成独立 HTML 页（Plan 驱动），用于端到端验证。
用法：python3 build_test_pages.py [--no-plan]  (输出 2026-10-12/archive/historical-outputs/test-pages/)
"""
import argparse
import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build as B
from plan_render import load_plan, render_article_with_plan, render_clean

BASE = os.path.dirname(os.path.abspath(__file__))
ISSUE_DIR = os.path.join(os.path.dirname(os.path.dirname(BASE)), '2026-10-12')
TEST_IDS = ['E1-005', 'E3-014', 'E1-033']
ASSET_DIR = os.path.join(ISSUE_DIR, 'assets')


def asset_loader(fname):
    with open(os.path.join(ASSET_DIR, fname), 'rb') as f:
        return base64.b64encode(f.read()).decode('ascii')


def build_page(e, article_html, tag):
    tokens = open(os.path.join(B.BASE, 'tokens.css'), encoding='utf-8').read()
    doc = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WSJ 深读 · 测试页 {e["id"]}{' · 无Plan降级' if tag else ''}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{B.FONTS}" rel="stylesheet">
<style>
{tokens}
{B.CSS}
</style>
</head>
<body>
<div class="progress" aria-hidden="true"><span id="pbar"></span></div>
<header class="masthead">
  <div class="mast-in">
    <div class="mast-left"><span class="mast-sq" aria-hidden="true"></span><span class="mast-wm">WSJ 深读</span></div>
    <div class="mast-meta"><span class="k-cn">2026年10月12日 · Editorial Plan 测试</span><span class="k-en" hidden>Oct 12, 2026 · Editorial Plan test</span></div>
    <button id="langToggle" class="pill" aria-pressed="false" aria-label="切换中英文"><span class="k-cn">EN</span><span class="k-en" hidden>中文</span></button>
  </div>
</header>
<main id="testpage">
{article_html}
</main>
<footer class="issue-foot">
  <div class="arule"></div>
  <p><span class="k-cn">测试页 · Editorial Plan 驱动渲染验证。正文逐字来自内容定稿。</span><span class="k-en" hidden>Test page · Editorial-Plan-driven rendering. Body text verbatim from the proofed draft.</span></p>
</footer>
<script>{B.JS}</script>
</body>
</html>
'''
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-plan', action='store_true', help='降级测试：不用 Plan 渲染')
    args = ap.parse_args()

    final = B.load_json(os.path.join(ISSUE_DIR, 'final.json'))
    modules_all = B.load_json(os.path.join(B.BASE, 'modules.json'))
    plans_dir = os.path.join(ISSUE_DIR, 'editorial-plans')
    out_dir = os.path.join(ISSUE_DIR, 'archive', 'historical-outputs', 'test-pages')
    os.makedirs(out_dir, exist_ok=True)

    for aid in TEST_IDS:
        e = next(x for x in final if x['id'] == aid)
        if args.no_plan:
            article_html = render_clean(e)
            suffix = '-noplan'
        else:
            plan = load_plan(plans_dir, aid)
            assert plan is not None, f'missing plan for {aid}'
            # schema 轻校验
            assert plan['article_id'] == aid
            for cp in plan['component_plan']:
                assert cp['component'] in __import__('components').COMPONENT_REGISTRY, cp['component']
                assert cp['reason'].strip(), f'{aid}: empty reason'
            article_html = render_article_with_plan(e, plan, modules_all, asset_loader)
            suffix = ''
        html = build_page(e, article_html, args.no_plan)
        out = os.path.join(out_dir, f'{aid}{suffix}.html')
        with open(out, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f'wrote {out} ({len(html)//1024} KB)')


if __name__ == '__main__':
    main()
