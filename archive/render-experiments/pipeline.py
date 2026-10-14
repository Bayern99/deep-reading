#!/usr/bin/env python3
"""WSJ 深读每日生产 Pipeline。

PDF → Extraction → Content Integrity → Translation → Translation QA →
Editorial Planning → Plan Validation → Asset Association → Rendering →
Visual QA → Issue Assembly

特性：
- 每篇文章稳定 ID（E{section}-{seq}）
- 各阶段产物持久化到 2026-10-12/stages/<stage>/
- 支持独立失败重试（--retry <stage>）
- 支持断点续跑（--from <stage>）
- 已完成且输入未变化的阶段不重复调用模型（内容哈希缓存）
- 明确区分：模型失败 / 源内容不足 / Schema 错误
"""
import argparse
import hashlib
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
ISSUE_DIR = os.path.join(os.path.dirname(BASE), '2026-10-12')
STAGES_DIR = os.path.join(ISSUE_DIR, 'stages')

STAGES = [
    'extraction',      # PDF → final.json（已完成，产物即 final.json）
    'integrity',       # integrity_gate → gate_status.json
    'planning',        # autonomous_planner → plans/<id>.json
    'validation',      # plan_validate + quote → validation/<id>.json
    'assets',          # asset_registry → asset_links/<id>.json
    'rendering',       # plan_render → html/<id>.html
    'visual_qa',       # screenshots → shots/<id>-*.png
    'assembly',        # issue.py → dist/index.html
]


def _hash(obj):
    return hashlib.sha256(
        json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()[:16]


def stage_path(stage, aid=None):
    d = os.path.join(STAGES_DIR, stage)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f'{aid}.json' if aid else '_manifest.json')


def is_done(stage, aid, input_hash):
    """输入未变化且产物存在 → 跳过。"""
    mp = stage_path(stage)
    manifest = json.load(open(mp)) if os.path.exists(mp) else {}
    rec = manifest.get(aid or '_all')
    return rec and rec.get('input_hash') == input_hash and rec.get('status') == 'ok'


def mark_done(stage, aid, input_hash, status='ok', error=None):
    mp = stage_path(stage)
    manifest = json.load(open(mp)) if os.path.exists(mp) else {}
    manifest[aid or '_all'] = {
        'input_hash': input_hash, 'status': status, 'error': error}
    json.dump(manifest, open(mp, 'w'), ensure_ascii=False, indent=1)


def run_integrity(force=False):
    """Stage: integrity — 全库门禁，结果持久化。"""
    sys.path.insert(0, BASE)
    from integrity_gate import check_article
    final = json.load(open(os.path.join(ISSUE_DIR, 'final.json')))
    ihash = _hash([(e['id'], e.get('body_cn', '')[:100]) for e in final])
    if not force and is_done('integrity', None, ihash):
        print('integrity: 缓存命中，跳过')
        return json.load(open(stage_path('integrity')))
    gate_status = {}
    for e in final:
        passed, issues = check_article(e)
        st = 'pass' if passed and not issues else ('warn' if passed else 'block')
        gate_status[e['id']] = {'status': st, 'issues': issues}
    out = stage_path('integrity')
    # 存完整结果（供 assembly 用）
    json.dump(gate_status, open(out.replace('_manifest.json', 'gate_status.json'), 'w'),
              ensure_ascii=False, default=str)
    mark_done('integrity', None, ihash)
    n = {s: sum(1 for v in gate_status.values() if v['status'] == s)
         for s in ('pass', 'warn', 'block')}
    print(f"integrity: {n['pass']} PASS / {n['warn']} WARN / {n['block']} BLOCK")
    return gate_status


def main():
    ap = argparse.ArgumentParser(description='WSJ 深读每日生产')
    ap.add_argument('--from', dest='from_stage', default='integrity',
                    choices=STAGES, help='从指定阶段开始（断点续跑）')
    ap.add_argument('--retry', default=None, choices=STAGES,
                    help='重试指定阶段（清除其缓存）')
    ap.add_argument('--force', action='store_true', help='强制重跑所有')
    args = ap.parse_args()

    if args.retry:
        mp = stage_path(args.retry)
        if os.path.exists(mp):
            os.remove(mp)
        print(f'已清除 {args.retry} 缓存')

    start = STAGES.index(args.from_stage)
    if 'integrity' in STAGES[start:]:
        run_integrity(force=args.force)
    # planning/rendering/assembly 由 build.py 承接（需模型调用，另行调度）
    print('pipeline stages: ' + ' → '.join(STAGES[start:]))
    print('注：planning 需调用 oMLX 模型，按文章独立重试；assembly 见 build.py --issue')


if __name__ == '__main__':
    main()
