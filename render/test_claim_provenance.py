"""Consumer regressions for Experiment 0 at the compiler/publication boundary."""
import unittest
import copy
import json
import tempfile

from artifact_store import ArtifactStore
from canonical_builder import build_canonical_source
from claim_provenance import make_evidence_record
from editorial_publisher import import_raw_generation

from canonical_builder import load_canonical_for_issue
from editorial_compiler import EditorialCompilationError, compile_editorial_artifact
from pathlib import Path

ISSUE = str(Path(__file__).resolve().parents[1] / '2026-10-12')


def narrative(canonical, extra=''):
    return '<html><body><main>' + ''.join(
        f'<p data-ref="{b["id"]}"></p>' for b in canonical['blocks']
    ) + extra + '</main></body></html>'


class ClaimProvenanceTests(unittest.TestCase):
    def test_canonical_false_numbers_and_pseudo_quotes_cannot_pass(self):
        for aid, derive in [('E1-010', 'm1'), ('E1-010', 'q1'), ('E3-004', 'q1')]:
            with self.subTest(article=aid, derive=derive):
                canonical = load_canonical_for_issue(ISSUE, aid)
                bundle = compile_editorial_artifact(
                    narrative(canonical, f'<aside data-derive="{derive}"></aside>'),
                    canonical, strict=False,
                )
                self.assertFalse(bundle['audit_report']['passed'],
                                 'Unsupported canonical content was accepted as verified')
                self.assertEqual(bundle['audit_report']['source_integrity']['exact_match_en'],
                                 f'{len(canonical["blocks"])}/{len(canonical["blocks"])}')
                gate = bundle['audit_report']['claim_provenance']
                self.assertEqual(next(c['status'] for c in gate['claims']
                                      if c['target'] == f'derive:{derive}'), 'rejected')

    def test_supported_quote_calculation_interpretation_and_chart_deliver(self):
        entry = {'id': 'EXP-0', 'title': 'Survey', 'title_cn': '调查',
                 'body_en': 'The survey forecasts 5.1%, up from 4.4%. “Rates remain uncertain,” Lee said.',
                 'body_cn': '调查预测为5.1%，此前为4.4%。李说：“利率仍不确定。”'}
        canonical = build_canonical_source(entry)
        extra = ('<blockquote>“Rates remain uncertain,”</blockquote>'
                 '<aside>70 bps</aside>'
                 '<aside data-claim="analysis">Editorial analysis: a forecast is not a guarantee.</aside>'
                 '<svg viewBox="0 0 100 100"><rect x="0" y="0" width="44" height="10"/>'
                 '<rect x="0" y="20" width="51" height="10"/>'
                 '<text x="0" y="50">4.4% → 5.1%</text></svg>')
        raw = narrative(canonical, extra)
        inventory = compile_editorial_artifact(raw, canonical, strict=False)['audit_report']['claim_provenance']
        spans = [{'block': 'p1', 'locale': locale, 'text': canonical['blocks'][0]['text_' + locale]}
                 for locale in ('en', 'cn')]
        kinds = ['quote', 'calculation', 'interpretation', 'chart']
        records = []
        for claim, kind in zip([c for c in inventory['claims'] if c['target'].startswith('html:')], kinds):
            calculation = {'operation': 'basis_points_change',
                           'operands': [{'span': 0, 'token': 0}, {'span': 0, 'token': 1}],
                           'result': '70', 'unit': 'bps', 'decimal_places': 0} if kind == 'calculation' else None
            records.append(make_evidence_record(canonical, claim, kind=kind, spans=spans,
                review={'decision': 'supported', 'reviewer': 'fixture-editor',
                        'reason': 'Exact Lee quote; 70 bps forecast difference; labeled uncertainty interpretation; zero-based bars 44:51 encode 4.4:5.1.'},
                calculation=calculation))
        bundle = compile_editorial_artifact(raw, canonical, evidence_records=records)
        self.assertTrue(bundle['audit_report']['passed'])
        self.assertIn('<svg', bundle['compiled_html'])
        self.assertEqual(bundle['audit_report']['source_integrity']['exact_match_cn'], '1/1')
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'final.json').write_text(json.dumps([entry]), encoding='utf-8')
            # Match the issue binding used by the actual import seam.
            local = load_canonical_for_issue(tmp, entry['id'])
            local_inventory = compile_editorial_artifact(raw, local, strict=False)['audit_report']['claim_provenance']
            for record, claim in zip(records, [c for c in local_inventory['claims'] if c['target'].startswith('html:')]):
                record.update(make_evidence_record(local, claim, kind=record['kind'], spans=record['spans'],
                                                  review=record['review'], calculation=record.get('calculation')))
            saved = import_raw_generation(issue_dir=tmp, article_id=entry['id'], raw_html=raw,
                                          model_metadata={'provider': 'host', 'model_id': 'offline'}, evidence_records=records)
            self.assertEqual(saved['artifact_version'], 'v1')
            active = ArtifactStore(tmp).get_active_artifact(entry['id'])
            self.assertEqual(active['validation']['compiler_audit']['claim_provenance']['evidence_records'], records)
            local_bundle = compile_editorial_artifact(raw, local, evidence_records=records)
            with self.assertRaises(ValueError):
                ArtifactStore(tmp).save_verified_artifact(canonical=local, raw_html=raw,
                    compiled_html=local_bundle['compiled_html'] + '<p>Invented addition</p>',
                    shadow_bundle=local_bundle['shadow_bundle'], audit_report=local_bundle['audit_report'], model_metadata={})
            with self.assertRaisesRegex(ValueError, 'Reader bundle differs'):
                ArtifactStore(tmp).save_verified_artifact(canonical=local, raw_html=raw,
                    compiled_html=local_bundle['compiled_html'], shadow_bundle={'shadow_html': 'Invented', 'shadow_css': ''},
                    audit_report=local_bundle['audit_report'], model_metadata={})
            with self.assertRaises(EditorialCompilationError):
                import_raw_generation(issue_dir=tmp, article_id=entry['id'], raw_html=raw.replace('70 bps', '18 bps'),
                                      model_metadata={}, evidence_records=records)
            self.assertEqual(ArtifactStore(tmp).get_active_artifact(entry['id'])['artifact_version'], 'v1')

        for field, value in [('claim_digest', 'changed'), ('source_digest', 'changed')]:
            bad = copy.deepcopy(records)
            bad[0][field] = value
            self.assertFalse(compile_editorial_artifact(raw, local, strict=False, evidence_records=bad)['audit_report']['passed'])

    def test_supported_review_cannot_override_incorrect_calculation(self):
        canonical = build_canonical_source({'id': 'EXP-CALC', 'body_en': 'Forecast 5.1% versus 4.4%.',
                                            'body_cn': '预测5.1%，此前4.4%。'})
        raw = narrative(canonical, '<aside>18 bps</aside>')
        claim = next(c for c in compile_editorial_artifact(raw, canonical, strict=False)['audit_report']['claim_provenance']['claims'] if c['active'])
        record = make_evidence_record(canonical, claim, kind='calculation',
            spans=[{'block': 'p1', 'locale': 'en', 'text': '5.1%'}, {'block': 'p1', 'locale': 'en', 'text': '4.4%'}],
            calculation={'operation': 'basis_points_change', 'operands': [{'span': 0, 'token': 0}, {'span': 1, 'token': 0}],
                         'result': '18', 'unit': 'bps'},
            review={'decision': 'supported', 'reviewer': 'editor', 'reason': 'Deliberately incorrect arithmetic challenge'})
        result = compile_editorial_artifact(raw, canonical, strict=False, evidence_records=[record])
        self.assertIn('Incorrect calculation result', '; '.join(result['audit_report']['errors']))

    def test_unreviewed_content_and_uninjected_fields_are_not_trusted(self):
        canonical = build_canonical_source({'id': 'EXP-UNKNOWN', 'body_en': 'Reported evidence.', 'body_cn': '报道证据。'})
        for addition in ['<aside>Causes a recession.</aside>', '<p data-field="value">999%</p>',
                         '<svg viewBox="0 0 100 100"><path d="M0 0L10 10"/></svg>',
                         '<script>document.body.append("New factual claim")</script>',
                         '<style>aside::after {content:"999%"}</style>']:
            with self.subTest(addition=addition):
                result = compile_editorial_artifact(narrative(canonical, addition), canonical, strict=False)
                self.assertFalse(result['audit_report']['passed'])
                self.assertTrue(any(c['status'] == 'needs_review' and c['active']
                                    for c in result['audit_report']['claim_provenance']['claims']))

    def test_review_cannot_bypass_quote_or_numeric_evidence_and_geometry_binding(self):
        canonical = build_canonical_source({'id': 'EXP-CHART', 'body_en': 'Reported 5.1% versus 4.4%.',
                                            'body_cn': '报道5.1%，此前4.4%。'})
        span = [{'block': 'p1', 'locale': 'en', 'text': 'Reported 5.1% versus 4.4%.'}]
        review = {'decision': 'supported', 'reviewer': 'fixture-editor', 'reason': 'Deliberate invalid evidence challenge'}
        for addition, kind in [('<blockquote>“Invented quotation.”</blockquote>', 'interpretation'),
                               ('<svg viewBox="0 0 100 100"><text x="0" y="20">4.12%</text></svg>', 'chart'),
                               ('<aside>5.1 bps</aside>', 'number')]:
            with self.subTest(addition=addition):
                raw = narrative(canonical, addition)
                claim = next(c for c in compile_editorial_artifact(raw, canonical, strict=False)['audit_report']['claim_provenance']['claims'] if c['active'])
                record = make_evidence_record(canonical, claim, kind=kind, spans=span, review=review)
                result = compile_editorial_artifact(raw, canonical, strict=False, evidence_records=[record])
                self.assertEqual(next(c['status'] for c in result['audit_report']['claim_provenance']['claims'] if c['active']), 'rejected')
        raw = narrative(canonical, '<svg viewBox="0 0 100 100"><rect width="51" height="5"/><text x="0" y="50">5.1%</text></svg>')
        claim = next(c for c in compile_editorial_artifact(raw, canonical, strict=False)['audit_report']['claim_provenance']['claims'] if c['active'])
        record = make_evidence_record(canonical, claim, kind='chart', spans=span, review=review)
        self.assertTrue(compile_editorial_artifact(raw, canonical, evidence_records=[record])['audit_report']['passed'])
        changed = raw.replace('width="51"', 'width="91"')
        result = compile_editorial_artifact(changed, canonical, strict=False, evidence_records=[record])
        self.assertIn('Stale claim evidence', '; '.join(result['audit_report']['errors']))

    def test_host_semantic_rejection_and_invalid_span_prevent_publication(self):
        canonical = build_canonical_source({'id': 'EXP-SEMANTIC', 'body_en': 'Forecast for 2026: 5.1%.',
                                            'body_cn': '2026年预测：5.1%。'})
        raw = narrative(canonical, '<aside>Guaranteed yield: 5.1%</aside>')
        claim = next(c for c in compile_editorial_artifact(raw, canonical, strict=False)['audit_report']['claim_provenance']['claims'] if c['active'])
        record = make_evidence_record(canonical, claim, kind='fact',
            spans=[{'block': 'p1', 'locale': 'en', 'text': 'Forecast for 2026: 5.1%.'}],
            review={'decision': 'rejected', 'reviewer': 'fixture-editor', 'reason': 'Forecast is not a guaranteed return'})
        result = compile_editorial_artifact(raw, canonical, strict=False, evidence_records=[record])
        self.assertIn('Forecast is not a guaranteed return', '; '.join(result['audit_report']['errors']))
        record['spans'][0]['text'] = 'Invented evidence 5.1%'
        record['review']['decision'] = 'supported'
        result = compile_editorial_artifact(raw, canonical, strict=False, evidence_records=[record])
        self.assertIn('Evidence span absent', '; '.join(result['audit_report']['errors']))

    def test_canonical_context_requires_evidence_even_when_source_referenced(self):
        canonical = build_canonical_source({'id': 'EXP-CONTEXT', 'body_en': 'Source reporting.',
                                            'body_cn': '来源报道。', 'context_cn': '未经证实的解释。'})
        bundle = compile_editorial_artifact(narrative(canonical, '<aside data-ref="ctx1"></aside>'), canonical, strict=False)
        self.assertFalse(bundle['audit_report']['claim_provenance']['passed'])
        self.assertEqual(next(c['status'] for c in bundle['audit_report']['claim_provenance']['claims'] if c['target'] == 'context:ctx1'), 'needs_review')

    def test_corrected_experimental_metric_preserves_data_derive_protocol(self):
        canonical = copy.deepcopy(load_canonical_for_issue(ISSUE, 'E1-010'))
        metric = canonical['derived_metrics'][0]
        metric.update(value='5.1% vs 4.4%', value_cn='5.1% (7月预测4.4%)',
                      note_en='Revised up 70 bps.', note_cn='上调70个基点。')
        metric['label_en'] = '10-Yr Treasury Yield Forecast (End-2026: Oct vs July)'
        raw = narrative(canonical, '<aside data-derive="m1"><div data-field="value"></div><div data-field="note"></div></aside>')
        gate = compile_editorial_artifact(raw, canonical, strict=False)['audit_report']['claim_provenance']
        claim = next(c for c in gate['claims'] if c['target'] == 'derive:m1')
        block = canonical['blocks'][3]
        record = make_evidence_record(canonical, claim, kind='calculation',
            spans=[{'block': 'p4', 'locale': 'en', 'text': '5.1%'},
                   {'block': 'p4', 'locale': 'en', 'text': '4.4%'},
                   {'block': 'p4', 'locale': 'en', 'text': block['text_en']},
                   {'block': 'p4', 'locale': 'cn', 'text': block['text_cn']}],
            calculation={'operation': 'basis_points_change', 'operands': [{'span': 0, 'token': 0}, {'span': 1, 'token': 0}],
                         'result': '70', 'unit': 'bps'},
            review={'decision': 'supported', 'reviewer': 'fixture-editor',
                    'reason': 'p4 pairs end-2026 October 5.1% with July 4.4%; 70 bps difference. Both locales keep the forecast horizon and qualifier.'})
        bundle = compile_editorial_artifact(raw, canonical, evidence_records=[record])
        self.assertIn('上调70个基点', bundle['compiled_html'])
        self.assertEqual(bundle['audit_report']['source_integrity']['exact_match_en'], '20/20')
        changed = copy.deepcopy(canonical)
        changed['derived_metrics'][0]['value'] = '4.12% vs 3.94%'
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(ValueError, 'Derived publication input'):
            ArtifactStore(tmp).save_verified_artifact(canonical=changed, raw_html=raw,
                compiled_html=bundle['compiled_html'], shadow_bundle=bundle['shadow_bundle'],
                audit_report=bundle['audit_report'], model_metadata={})

    def test_chart_scale_ticks_do_not_require_fabricated_source_facts(self):
        canonical = build_canonical_source({'id': 'EXP-AXIS', 'body_en': 'Forecast 5.1% versus 4.4%.',
                                            'body_cn': '预测5.1%，此前4.4%。'})
        raw = narrative(canonical, '<svg viewBox="0 0 100 100"><text x="0" y="10">0%</text><text x="0" y="40">4.4%</text><text x="0" y="70">5.1%</text></svg>')
        claim = next(c for c in compile_editorial_artifact(raw, canonical, strict=False)['audit_report']['claim_provenance']['claims'] if c['active'])
        record = make_evidence_record(canonical, claim, kind='chart',
            spans=[{'block': 'p1', 'locale': 'en', 'text': 'Forecast 5.1% versus 4.4%.'}],
            review={'decision': 'supported', 'reviewer': 'fixture-editor', 'reason': '0% is a scale baseline; plotted observations remain 4.4% and 5.1% forecasts.'})
        record['presentation_numbers'] = [{'text_index': 1, 'role': 'axis_tick', 'text': '0%',
                                          'reason': 'Zero baseline tick, not a reported observation'}]
        self.assertTrue(compile_editorial_artifact(raw, canonical, evidence_records=[record])['audit_report']['passed'])
        changed = raw.replace('4.4%', '4.12%')
        changed_claim = next(c for c in compile_editorial_artifact(changed, canonical, strict=False)['audit_report']['claim_provenance']['claims'] if c['active'])
        record['claim_digest'] = changed_claim['claim_digest']
        result = compile_editorial_artifact(changed, canonical, strict=False, evidence_records=[record])
        self.assertIn('4.12 percent', '; '.join(result['audit_report']['errors']))
