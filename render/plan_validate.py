#!/usr/bin/env python3
"""Plan 校验器：自动拦截 Planner 的事实层编造。

泛化测试发现（2026-10-13）：
- E1-034 timeline 把原文 "February" 写成 "2024年2月"（编造年份，P0）
- E1-034 quote 把直引号改成弯引号+句号（非逐字，P2）
- E1-003 figure credit 编造 "AJ Photo"（P2）

规则（通用，不针对单篇）：
1. timeline 每个条目的日期必须在原文中逐字出现（大小写不敏感，允许中英对应）
2. quote 的引文必须在原文中逐字出现（标点也算）
3. credit 为空时允许，不许编造（由 registry 配合）
"""
import json, re, sys


def norm(s):
    return re.sub(r'\s+', ' ', s or '').strip().lower()


def validate(plan_path, source_text):
    plan = json.load(open(plan_path))
    src = norm(source_text)
    errors = []
    aid = plan.get('article_id', '?')

    for comp in plan.get('component_plan', []):
        name = comp.get('component')
        data = comp.get('data', {})

        if name == 'timeline':
            entries = data.get('timeline', {}).get('entries', [])
            for i, e in enumerate(entries):
                for key in ('t_en', 't_cn'):
                    t = e.get(key, '')
                    if t and norm(t) not in src:
                        # 中文日期允许数字对应（如 2月 vs February 不算编造，只查年份）
                        if re.search(r'20\d{2}', t) and not re.search(r'20\d{2}', src):
                            errors.append(f'{aid} timeline[{i}].{key}="{t}" 编造了年份，原文无此年份')
                        elif key == 't_en':
                            errors.append(f'{aid} timeline[{i}].{key}="{t}" 在原文中找不到逐字对应')

        if name == 'quote':
            q = data.get('text_en') or data.get('text_cn') or data.get('text', '')
            if q and norm(q) not in src:
                errors.append(f'{aid} quote 引文非逐字（标点被改或内容不符）: "{q[:60]}..."')

        if name == 'figure':
            credit = data.get('credit', '')
            if credit and credit.strip().lower() not in ('', 'unknown', '未知'):
                if norm(credit) not in src:
                    errors.append(f'{aid} figure credit="{credit}" 在原文/OCR 中无依据（疑似编造）')

    return errors


if __name__ == '__main__':
    plan_path, source_path = sys.argv[1], sys.argv[2]
    errs = validate(plan_path, open(source_path, encoding='utf-8').read())
    if errs:
        print('PLAN VALIDATION FAILED:')
        for e in errs:
            print(' -', e)
        sys.exit(1)
    print('PLAN OK:', plan_path)
