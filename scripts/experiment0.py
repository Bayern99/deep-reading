#!/usr/bin/env python3
"""Offline Experiment 0 replay. Writes new evidence only; never starts a live queue.

Runs pinned Golden versions, then compiles/imports source-backed interventions in
an isolated issue. The explicit review records below are narrow reference cases,
not an automatic approver for arbitrary generated content.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import urllib.request

import lxml.html

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'render'))
from artifact_store import ArtifactStore
from canonical_builder import load_canonical_for_issue
from claim_provenance import make_evidence_record
from editorial_compiler import EditorialCompilationError, compile_editorial_artifact
from editorial_publisher import import_raw_generation
from editorial_studio import create_studio_http_server

PANEL = [('E2-001', 'v1'), ('E2-001', 'v2'), ('E2-001', 'v3'),
         ('E2-002', 'v2'), ('E1-010', 'v1'), ('E3-004', 'v1'),
         ('E2-010', 'v1'), ('E1-024', 'v1'), ('E3-001', 'v2')]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protected(issue):
    return {str(p.relative_to(issue)): sha(p) for p in
            [issue / 'final.json', *(issue / 'editorial-artifacts').rglob('*')] if p.is_file()}


def raw_article(canonical, additions):
    return '<!DOCTYPE html><html lang="zh-CN"><head><style>html[lang="zh-CN"] .lang-en{display:none} html[lang="en"] .lang-cn{display:none}</style></head><body><main><h1 data-ref="title"></h1>' + ''.join(
        f'<p data-ref="{b["id"]}"></p>' for b in canonical['blocks']) + additions + '</main></body></html>'


def positive_case(issue, aid):
    canonical = load_canonical_for_issue(str(issue), aid)
    by_id = {b['id']: b for b in canonical['blocks']}
    specs = []
    if aid == 'E1-010':
        additions = []
        # Independently worked reference results from p4/p5: 70, 66, 52 bps.
        for horizon, new, old, delta, block in [
            ('End 2026', '5.1', '4.4', '70', 'p4'),
            ('Mid 2027', '4.96', '4.3', '66', 'p5'),
            ('End 2027', '4.78', '4.26', '52', 'p5'),
        ]:
            additions.append(f'<aside data-claim="{horizon}">{horizon}: {new}% versus {old}%; revision +{delta} bps.</aside>')
            specs.append(('calculation', [
                {'block': block, 'locale': 'en', 'text': new + '%'},
                {'block': block, 'locale': 'en', 'text': old + '%'},
                {'block': block, 'locale': 'en', 'text': by_id[block]['text_en']},
            ], {'operation': 'basis_points_change',
                'operands': [{'span': 0, 'token': 0}, {'span': 1, 'token': 0}],
                'result': delta, 'unit': 'bps', 'decimal_places': 0},
                'p4/p5 explicitly pair these July/October survey forecasts with these horizons; difference in percentage points multiplied by 100. Forecasts, not guaranteed yields.'))
        additions.append('<svg viewBox="0 0 600 160" width="100%"><rect x="0" y="0" width="440" height="20"/><rect x="0" y="30" width="510" height="20"/><text x="0" y="90">July: 4.4%</text><text x="0" y="120">October: 5.1%</text><text x="0" y="150">End 2026 forecast; zero baseline</text></svg>')
        specs.append(('chart', [{'block': 'p4', 'locale': 'en', 'text': by_id['p4']['text_en']}], None,
                      'End-2026 survey forecast bars start at zero. Widths 440 and 510 use the same 100 pixels per percentage point; July 4.4%, October 5.1%. No causal arrow or guaranteed outcome.'))
        raw = raw_article(canonical, ''.join(additions))
    else:
        raw = raw_article(canonical,
            '<blockquote>“AI wants to be God,”</blockquote>'
            '<blockquote>“人工智能想要成为上帝。”</blockquote>'
            '<aside data-claim="attribution">Joseph Hutchinson / 约瑟夫·哈钦森</aside>'
            '<aside data-claim="analysis">Editorial analysis / 编辑解读: The opening presents a pastor\'s concern, rather than establishing that AI has religious intentions. / 开篇呈现牧师的担忧，并非断言人工智能具有宗教意图。</aside>'
            '<svg viewBox="0 0 600 140" width="100%"><text x="10" y="30">Pastor / 牧师</text><path d="M100 40 L100 70" stroke="black"/><text x="10" y="90">Reported concern about AI / 对人工智能的担忧</text></svg>')
        spans = [{'block': b, 'locale': locale, 'text': by_id[b]['text_' + locale]}
                 for b in ('p1', 'p2') for locale in ('en', 'cn')]
        reason = 'p1 identifies Joseph Hutchinson; p2 reports his warning. These exact quoted fragments occur in the respective locales. The interpretation distinguishes the pastor\'s statement from authorial fact; the conceptual diagram depicts attribution, without quantitative or causal claims.'
        specs = [(kind, spans, None, reason) for kind in ('quote', 'quote', 'fact', 'interpretation', 'chart')]
    diagnosis = compile_editorial_artifact(raw, canonical, strict=False)
    claims = [c for c in diagnosis['audit_report']['claim_provenance']['claims'] if c['target'].startswith('html:')]
    if len(claims) != len(specs):
        raise AssertionError('Reference intervention inventory drift')
    records = [make_evidence_record(canonical, claim, kind=kind, spans=spans, calculation=calc,
               review={'decision': 'supported', 'reviewer': 'experiment0-source-review', 'reason': reason})
               for claim, (kind, spans, calc, reason) in zip(claims, specs)]
    bundle = compile_editorial_artifact(raw, canonical, evidence_records=records)
    record = import_raw_generation(issue_dir=str(issue), article_id=aid, raw_html=raw,
                                   model_metadata={'provider': 'host-reference', 'model_id': 'no-model-call'},
                                   evidence_records=records, notes='Isolated Experiment 0 reference; not a replacement Golden design')
    # Reopen the actual store and fetch the actual standalone compiled artifact.
    active = ArtifactStore(str(issue)).get_active_artifact(aid)
    assert active['artifact_version'] == record['artifact_version']
    return raw, records, bundle, record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--issue', default='2026-10-12')
    parser.add_argument('--output', required=True, help='New evidence directory outside the protected issue')
    args = parser.parse_args()
    issue = (ROOT / args.issue).resolve()
    out = Path(args.output).resolve()
    if out.is_relative_to(issue) or out.exists():
        raise ValueError('Use a new evidence directory outside the protected issue')
    before = protected(issue)
    result = {'schema_version': 'experiment0-results-v1', 'historical': [], 'positive': [],
              'model_calls': 0, 'reference_review_limit': 'Bounded source review, not independent human validation or design comparison'}
    outputs = {}
    result['implementation_sha256'] = {name: sha(ROOT / 'render' / name) for name in
        ('claim_provenance.py', 'canonical_builder.py', 'editorial_compiler.py', 'editorial_publisher.py', 'artifact_store.py')}
    with tempfile.TemporaryDirectory(prefix='wsj-experiment0-') as temp:
        isolated = Path(temp) / issue.name
        isolated.mkdir()
        shutil.copy2(issue / 'final.json', isolated / 'final.json')
        for aid, version in PANEL:
            canonical = load_canonical_for_issue(str(isolated), aid)
            path = issue / 'editorial-artifacts' / aid / version / 'raw.html'
            bundle = compile_editorial_artifact(path.read_text(), canonical, strict=False)
            audit = bundle['audit_report']
            gate = audit['claim_provenance']
            result['historical'].append({'article_id': aid, 'version': version, 'raw_sha256': sha(path),
                'narrative': audit['source_integrity'], 'publishable': audit['passed'],
                'active_status_counts': dict(Counter(c['status'] for c in gate['claims'] if c['active'])),
                'canonical_candidates': [{k: c[k] for k in ('target', 'status', 'active', 'errors')}
                                         for c in gate['claims'] if not c['target'].startswith('html:')],
                'authored_review_targets': [{k: c[k] for k in ('target', 'kind', 'claim_digest', 'review_needed')}
                                          for c in gate['claims'] if c['target'].startswith('html:')]})
            # Faithful narrative-only production remains valid for every panel story.
            assert compile_editorial_artifact(raw_article(canonical, ''), canonical)['audit_report']['passed']
            if aid == 'E1-010':
                chart_records = [make_evidence_record(canonical, claim, kind='chart',
                    spans=[{'block': b['id'], 'locale': locale, 'text': b['text_' + locale]}
                           for b in canonical['blocks'] for locale in ('en', 'cn')],
                    review={'decision': 'supported', 'reviewer': 'negative-challenge',
                            'reason': 'Deliberately permissive disposition: literal checks must still reject unsupported chart numbers.'})
                    for claim in gate['claims'] if claim['kind'] == 'chart']
                chart_by_target = {c['target']: c for c in gate['claims'] if c['kind'] == 'chart'}
                for chart_record in chart_records:
                    nodes = lxml.html.fromstring(chart_by_target[chart_record['target']]['payload']).xpath('.//text')
                    chart_record['presentation_numbers'] = [
                        {'text_index': i, 'role': 'axis_tick', 'text': node.text_content(),
                         'reason': 'Pinned comparison-chart y-axis tick at x=65, distinct from plotted forecast labels.'}
                        for i, node in enumerate(nodes, 1)
                        if node.get('x') == '65' and node.get('text-anchor') == 'end'
                        and node.text_content() in ('3.60%', '3.80%', '4.00%', '4.20%', '4.40%')]
                challenged = compile_editorial_artifact(path.read_text(), canonical, strict=False, evidence_records=chart_records)
                result['false_svg_challenge'] = [{k: c[k] for k in ('target', 'status', 'errors')}
                    for c in challenged['audit_report']['claim_provenance']['claims'] if c['kind'] == 'chart']
                assert any(c['status'] == 'rejected' and any('4.12' in e for e in c['errors'])
                           for c in result['false_svg_challenge'])
        for aid in ('E1-010', 'E3-004'):
            raw, records, bundle, record = positive_case(isolated, aid)
            outputs[aid + '-raw.html'] = raw
            outputs[aid + '-compiled.html'] = bundle['compiled_html']
            outputs[aid + '-evidence.json'] = json.dumps(records, ensure_ascii=False, indent=2)
            result['positive'].append({'article_id': aid, 'version': record['artifact_version'],
                'exact_match_cn': bundle['audit_report']['source_integrity']['exact_match_cn'],
                'exact_match_en': bundle['audit_report']['source_integrity']['exact_match_en'],
                'claim_status_counts': dict(Counter(c['status'] for c in bundle['audit_report']['claim_provenance']['claims'] if c['active'])),
                'compiled_digest': bundle['audit_report']['claim_provenance']['compiled_digest'],
                'shadow_digest': bundle['audit_report']['claim_provenance']['shadow_digest'],
                'svg_preserved': '<svg' in bundle['compiled_html']})
            # Unsupported attempt cannot replace the supported version.
            bad = raw.replace('5.1%', '4.12%') if aid == 'E1-010' else raw.replace('AI wants to be God,', 'AI is already God,')
            try:
                import_raw_generation(issue_dir=str(isolated), article_id=aid, raw_html=bad,
                                      model_metadata={}, evidence_records=records)
            except EditorialCompilationError:
                pass
            else:
                raise AssertionError('Unsupported modification was published')
            assert ArtifactStore(str(isolated)).get_active_artifact(aid)['artifact_version'] == record['artifact_version']
        server = create_studio_http_server(str(isolated), port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f'http://127.0.0.1:{server.server_port}'
            for positive in result['positive']:
                url = f'{base}/editorial-artifacts/{positive["article_id"]}/v1/compiled.html'
                with urllib.request.urlopen(url, timeout=10) as response:
                    delivered = response.read()
                assert hashlib.sha256(delivered).hexdigest() == positive['compiled_digest']
                positive['http_delivery'] = 'passed'
            with urllib.request.urlopen(base + '/reader', timeout=10) as response:
                assert response.status == 200
            result['reader_http'] = 'passed'
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
    after = protected(issue)
    if before != after:
        raise AssertionError('Protected issue changed during experiment; inspect concurrent writer')
    result['preservation'] = {'protected_files': len(before), 'hashes_unchanged': True,
                              'final_sha256': before['final.json']}
    out.mkdir(parents=True)
    for name, content in outputs.items():
        (out / name).write_text(content, encoding='utf-8')
    (out / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'historical'}, ensure_ascii=False, indent=2))
    print('Historical versions inspected:', len(result['historical']))
    print('Evidence:', out)


if __name__ == '__main__':
    main()
