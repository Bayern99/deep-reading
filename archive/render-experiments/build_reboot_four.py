#!/usr/bin/env python3
"""Regenerate dist/reboot-four.html — the four-article reboot-proof strip.

Slices the freshly built dist/index.html: same shell/CSS/JS, only the four
proof articles kept, in reading order. Run after build.py.
"""
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(os.path.dirname(os.path.dirname(BASE)), '2026-10-12', 'dist')
ORDER = ['E2-002', 'E1-010', 'E3-004', 'E1-014']


def main():
    src = os.path.join(DIST, 'index.html')
    html = open(src, encoding='utf-8').read()

    body_start = html.index('<body')
    body_end = html.index('>', body_start) + 1
    pre = html[:body_end]

    arts = {}
    for m in re.finditer(
            r'<article class="story[^"]*" id="s-([A-Z0-9-]+)".*?</article>',
            html, re.S):
        arts[m.group(1)] = m.group(0)
    missing = [a for a in ORDER if a not in arts]
    assert not missing, f'articles missing from index.html: {missing}'

    tail = html[html.rindex('<script'):]

    out = pre + '\n' + '\n'.join(arts[a] for a in ORDER) + '\n' + tail
    dst = os.path.join(DIST, 'reboot-four.html')
    with open(dst, 'w', encoding='utf-8') as f:
        f.write(out)
    print(f'wrote {dst} ({len(out)//1024} KB, {len(ORDER)} articles)')


if __name__ == '__main__':
    main()
