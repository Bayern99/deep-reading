#!/usr/bin/env python3
"""T2 初译：031-059 条目，TranslateGemma 只做初译（不做判断），复核/修订另行手工做。"""
import json, importlib.util, time

spec = importlib.util.spec_from_file_location("tg", "/home/hatch/workspace/translate-gemma.py")
tg = importlib.util.module_from_spec(spec); spec.loader.exec_module(tg)

BASE = '/home/hatch/workspace/wsj-deep-read/2026-10-12'
merged = json.load(open(BASE + '/merged.json'))
glossary = json.load(open(BASE + '/glossary.json'))


def entry_glossary(terms):
    sub, missing = {}, []
    for t in terms or []:
        en = t.get('en')
        if not en:
            continue
        if en in glossary:
            sub[en] = glossary[en]
        elif t.get('zh_suggested'):
            sub[en] = t['zh_suggested']
            missing.append(en)
    return sub, missing


def chunk_paragraphs(body, max_words=1100, max_paras=10):
    paras = [p.strip() for p in body.split('\n\n') if p.strip()]
    chunks, cur, cw = [], [], 0
    for p in paras:
        w = len(p.split())
        if (cw + w > max_words or len(cur) >= max_paras) and cur:
            chunks.append(cur); cur, cw = [], 0
        cur.append(p); cw += w
    if cur:
        chunks.append(cur)
    return chunks


def safe_translate(text, gl, max_tokens=4000, label=''):
    for attempt in range(4):
        try:
            return tg.translate(text, src='en', tgt='zh', glossary=gl, max_tokens=max_tokens)
        except Exception as ex:
            print(f'  [{label}] attempt {attempt} failed: {str(ex)[:100]}', flush=True)
            time.sleep(30)
    raise RuntimeError(f'{label}: failed after retries')


ids = sorted([e for e in merged if e.get('final_id') and '031' <= e['final_id'] <= '059'],
             key=lambda x: x['final_id'])
results = {}
for e in ids:
    fid = e['final_id']
    print(f'== {fid} [{e.get("type")}/{e.get("priority")}] {(e.get("title") or "")[:50]}', flush=True)
    gl, missing = entry_glossary(e.get('terms'))
    title_cn = safe_translate(e['title'], gl, max_tokens=500, label=fid + '-title')
    dek = e.get('dek')
    dek_cn = safe_translate(dek, gl, max_tokens=600, label=fid + '-dek') if dek and dek != 'None' else None
    body_en = (e.get('body_en') or '').strip()
    if e.get('type') == 'data_table' or not body_en:
        body_cn = ''
        print(f'   data_table/empty -> body skipped', flush=True)
    else:
        chunks = chunk_paragraphs(body_en)
        print(f'   {len(chunks)} body chunk(s)', flush=True)
        parts = []
        for i, c in enumerate(chunks):
            parts.append(safe_translate('\n\n'.join(c), gl, max_tokens=4000, label=fid + f'-body{i}'))
        body_cn = '\n\n'.join(parts)
    results[fid] = {
        'type': e.get('type'), 'priority': e.get('priority'),
        'title_en': e.get('title'), 'dek_en': dek if dek != 'None' else None,
        'body_en': body_en,
        'title_cn': title_cn, 'dek_cn': dek_cn, 'body_cn': body_cn,
        'glossary_used': gl, 'glossary_missing': missing,
    }
    json.dump(results, open(BASE + '/trans-T2-draft.json', 'w'), ensure_ascii=False, indent=2)
print('DONE', len(results), flush=True)
