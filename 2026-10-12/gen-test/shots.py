#!/usr/bin/env python3
"""gen-test 截图：每篇 article.html 渲染 1440 宽（桌面）与 390 宽（手机）整页截图。"""
import os

BASE = '/home/hatch/workspace/wsj-deep-read/2026-10-12/gen-test'
ARTICLES = ['E1-014', 'E1-025', 'E1-034']  # 任务输入表
CHROME = '/home/hatch/workspace/.tmp-chrome/chrome-headless-shell-linux64/chrome-headless-shell'


def main():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        for aid in ARTICLES:
            url = 'file://' + os.path.join(BASE, aid, 'article.html')
            for name, width in (('shot-d.png', 1440), ('shot-m.png', 390)):
                b = pw.chromium.launch(executable_path=CHROME)
                pg = b.new_page(viewport={'width': width, 'height': 900})
                pg.goto(url, wait_until='networkidle', timeout=60000)
                pg.wait_for_timeout(1500)
                out = os.path.join(BASE, aid, name)
                pg.screenshot(path=out, full_page=True)
                b.close()
                print(f'[{aid}] {name} ok ({os.path.getsize(out)//1024} KB)')


if __name__ == '__main__':
    main()
