"""Behavioral P0 regressions at article rendering and issue assembly seams.

Run from the repository root: PYTHONPATH=render python3 -m unittest tests.test_p0_render
Fixtures are the unchanged published final.json; no renderer-source assertions.
"""
import base64
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from html.parser import HTMLParser

from article import render_article
from enhanced_render import render_enhanced_article, source_from_final
from source_model import content_digest


ROOT = Path(__file__).resolve().parent.parent


class LocaleText(HTMLParser):
    def __init__(self, locale):
        super().__init__()
        self.locale = locale
        self.stack = []
        self.parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag not in ('area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
                        'link', 'meta', 'param', 'source', 'track', 'wbr'):
            active = self.locale in attrs.get('class', '').split()
            self.stack.append((tag, active or (self.stack[-1][1] if self.stack else False)))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if self.stack and self.stack[-1][1]:
            self.parts.append(data)


def locale_text(html, locale):
    parser = LocaleText('k-' + locale)
    parser.feed(html)
    return ''.join(parser.parts)


class RenderingConvergence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entries = {e['id']: e for e in json.loads(
            (ROOT / '2026-10-12/final.json').read_text())}

    def test_actual_english_tail_survives_ordinary_and_enhanced(self):
        entry = self.entries['E2-010']
        self.assertEqual(len(entry['body_cn'].split('\n\n')), 14)
        self.assertEqual(len(entry['body_en'].split('\n\n')), 16)
        self.assertEqual(len(source_from_final(entry).blocks), 14)
        unmatched = dict(entry, id='fixture', body_cn='一段中文。',
                         body_en='First English paragraph.\n\nUnmatched English tail.')
        self.assertIn('Unmatched English tail.', locale_text(render_article(unmatched, None, None), 'en'))
        tail = entry['body_en'].split('\n\n')[-2:]
        plan = {'text_treatments': [{
            'pattern_id': 'T01', 'action': 'wrap', 'block_id': 'p1',
            'locale': 'en', 'text_exact': entry['body_en'].split('\n\n')[0][:20]}]}
        for html in (render_article(entry, None, None),
                     render_enhanced_article(entry, {}),
                     render_enhanced_article(entry, plan)):
            english = locale_text(html, 'en')
            self.assertNotIn('[Continued on page A12.]', english)
            for paragraph in tail:
                self.assertIn(paragraph, english)
            self.assertLess(english.index(tail[0]), english.index(tail[1]))

    def test_preserve_keeps_actual_compact_metadata_and_all_type_markup(self):
        entry = self.entries['E1-014']
        plan = json.loads((ROOT / '2026-10-12/editorial-plans/E1-014.json').read_text())
        ordinary = render_article(entry, None, None)
        self.assertIn('佛罗里达州', ordinary)
        self.assertIn('—Associated Press', ordinary)
        self.assertEqual(render_enhanced_article(entry, plan), ordinary)
        for kind in ('article', 'opinion', 'brief', 'letter', 'index_digest',
                     'data_table', 'photo_caption', 'correction'):
            with self.subTest(kind=kind):
                example = dict(entry, id='fixture', type=kind)
                self.assertEqual(render_enhanced_article(example, {}),
                                 render_article(example, None, None))

    def test_repairs_are_independent_of_plan_and_do_not_mutate_final(self):
        for aid, expected_count in (('E1-005', 24), ('E2-002', 38), ('E2-010', 14)):
            entry = self.entries[aid]
            original = json.dumps(entry, ensure_ascii=False, sort_keys=True)
            expected_join = {
                'E1-005': 'conference scheduled for the end of the month',
                'E2-002': "helped the farmer harden the camera's security",
                'E2-010': 'workers say they experience the Sunday scaries, according',
            }[aid]
            source = source_from_final(entry)
            self.assertEqual(len(source.blocks), expected_count)
            plan = {'text_treatments': [{
                'pattern_id': 'T01', 'action': 'wrap', 'block_id': 'p1',
                'locale': 'cn', 'text_exact': source.blocks[0]['cn'][:10]}]}
            for html in (render_article(entry, None, None),
                         render_enhanced_article(entry, {}),
                         render_enhanced_article(entry, plan)):
                english = locale_text(html, 'en')
                self.assertIn(expected_join, english)
                for block in source.blocks:
                    if block['en']:
                        self.assertIn(block['en'], english)
                self.assertNotIn('[Continued on page A10.]', english)
            self.assertEqual(json.dumps(entry, ensure_ascii=False, sort_keys=True), original)


    def test_missing_and_unsupported_operations_fail_with_receipts(self):
        entry = dict(self.entries['E1-014'], id='fixture', type='article')
        good = {'pattern_id': 'T01', 'block_id': 'p1', 'locale': 'cn',
                'text_exact': entry['body_cn'].split('\n\n')[0][:8], 'action': 'wrap'}
        invalid = [
            {'text_treatments': [dict(good, block_id='p999')]},
            {'text_treatments': [dict(good, pattern_id='T99')]},
            {'text_treatments': [dict(good, action='teleport')]},
            {'text_treatments': [dict(good, text_exact='没有出现在源里的旧文字')]},
            {'text_treatments': [dict(good, pattern_id='T09', action='split', params={'cut': 8})]},
            {'text_treatments': [dict(good, pattern_id='T10', action='group',
                                      params={'blocks': ['p1', 'p999']})]},
            {'layout_decisions': [{'pattern_id': 'L02', 'action': 'apply',
                                   'params': {'anchor_block_id': 'p999', 'note_cn': '边注'}}]},
            {'layout_decisions': [{'pattern_id': 'L99', 'action': 'apply'}]},
            {'layout_decisions': [{'pattern_id': 'L03', 'action': 'teleport'}]},
            {'component_plan': [{'component': 'missing_component'}]},
            {'component_plan': [{'component': 'quote', 'slot': {'at': 'missing_slot'}}]},
            {'component_plan': [{'component': 'quote', 'slot': {'at': 'after_para', 'para': 999}}]},
        ]
        for plan in invalid:
            with self.subTest(plan=plan):
                receipts = []
                with self.assertRaises(ValueError):
                    render_enhanced_article(entry, plan, execution_receipts=receipts)
                self.assertEqual(receipts[-1]['status'], 'failed')
                self.assertIn('error', receipts[-1])
                self.assertFalse(any(op['status'] == 'applied' for op in receipts[-1]['operations']))
        receipts = []
        html = render_enhanced_article(entry, {'text_treatments': [good]}, execution_receipts=receipts)
        self.assertIn('class="tt-b"', html)
        self.assertEqual(receipts[-1]['status'], 'applied')
        render_enhanced_article(entry, {}, execution_receipts=receipts)
        self.assertEqual(receipts[-1]['status'], 'preserved')
        with self.assertRaises(ValueError):
            render_article(dict(entry, type='missing_type'), None, None, execution_receipts=receipts)
        self.assertEqual(receipts[-1]['status'], 'failed')

    def test_stale_full_content_pin_fails_even_when_exact_text_still_matches(self):
        entry = self.entries['E2-010']
        plan = {'content_digest': content_digest(entry), 'text_treatments': [{
            'pattern_id': 'T01', 'block_id': 'p1', 'locale': 'cn',
            'text_exact': entry['body_cn'].split('\n\n')[0][:8]}]}
        receipts = []
        render_enhanced_article(entry, plan, execution_receipts=receipts)
        changed = dict(entry, byline=(entry.get('byline') or '') + ' changed')
        with self.assertRaisesRegex(ValueError, 'stale plan content digest'):
            render_enhanced_article(changed, plan, execution_receipts=receipts)
        self.assertEqual(receipts[-1]['status'], 'failed')

    def test_real_cli_shares_repaired_bodies_assets_and_failure_sidecar(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            renderer = root / 'render'
            renderer.mkdir()
            for source in (ROOT / 'render').iterdir():
                if source.suffix in ('.py', '.css', '.json'):
                    shutil.copy2(source, renderer / source.name)
            issue = root / '2026-10-12'
            issue.mkdir()
            shutil.copy2(ROOT / '2026-10-12/final.json', issue / 'final.json')
            shutil.copy2(ROOT / '2026-10-12/front.json', issue / 'front.json')
            final_entries = json.loads((issue / 'final.json').read_text())

            def suppress_map(exclude=()):
                return json.dumps({'data_treatment': {
                    e['id']: {'suppress_body': 'fixture'} for e in final_entries
                    if e.get('type') in ('data_table', 'index_digest')
                    and e['id'] not in exclude}}, ensure_ascii=False)

            (renderer / 'curation.json').write_text(suppress_map())
            for filename in ('modules.json',):
                (renderer / filename).write_text('{}')
            (issue / 'assets').mkdir()
            image = ('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwC'
                     'AAAAC0lEQVR42mP8/x8AAwMCAO+aM5sAAAAASUVORK5CYII=')
            (issue / 'assets/evidence.png').write_bytes(base64.b64decode(image))
            (renderer / 'images.json').write_text(json.dumps({'E2-010': {
                'file': '../2026-10-12/assets/evidence.png', 'caption_cn': '原始图像',
                'caption_en': 'Original image', 'credit': 'WSJ'}}))
            plans = issue / 'editorial-plans'
            plans.mkdir()
            (plans / 'E1-014.json').write_text(json.dumps({
                'schema_version': 'enhanced-v1', 'article_id': 'E1-014'}))
            entry = self.entries['E2-010']
            plan = {'schema_version': 'enhanced-v1', 'article_id': 'E2-010',
                    'text_treatments': [{'pattern_id': 'T01', 'block_id': 'p1',
                                        'locale': 'cn', 'text_exact': entry['body_cn'].split('\n\n')[0][:8]}],
                    'component_plan': [{'component': 'figure', 'asset': 'assets/evidence.png',
                                        'slot': {'at': 'before_body'},
                                        'data': {'caption_cn': '原始图像', 'caption_en': 'Original image',
                                                 'credit': 'WSJ'}}]}
            plan_path = plans / 'E2-010.json'
            plan_path.write_text(json.dumps(plan))
            command = [sys.executable, str(renderer / 'build.py'), '--issue', '2026-10-12']
            result = subprocess.run(command, cwd=renderer, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            receipt_path = issue / 'dist/render-receipts.json'
            receipt = json.loads(receipt_path.read_text())
            self.assertEqual(receipt['status'], 'complete')
            statuses = {r['article_id']: r['status'] for r in receipt['articles']}
            self.assertEqual(statuses['E1-014'], 'preserved')
            self.assertEqual(statuses['E2-010'], 'applied')
            # suppressed body + insights where EN drops numbers CN kept fails loudly
            partial = json.loads((renderer / 'curation.json').read_text())
            partial['data_treatment']['E1-002'] = {
                'suppress_body': 'fixture',
                'insight_cn': '上周道指 51654.95（▲477.99 / +0.93%）',
                'insight_en': 'Last week: DJIA 51654.95 (+0.93%)'}
            (renderer / 'curation.json').write_text(json.dumps(partial, ensure_ascii=False))
            dropped = subprocess.run(command, cwd=renderer, capture_output=True, text=True)
            self.assertNotEqual(dropped.returncode, 0)
            self.assertIn('digest insight number parity broken: 477.99', dropped.stderr)
            self.assertEqual(json.loads(receipt_path.read_text())['status'], 'failed')
            partial['data_treatment']['E1-002'] = {'suppress_body': 'fixture'}
            (renderer / 'curation.json').write_text(json.dumps(partial, ensure_ascii=False))
            pages = [(issue / 'dist' / name).read_text() for name in ('index.html', 'baseline.html')]
            for html in pages:
                for paragraph in entry['body_en'].split('\n\n')[-2:]:
                    self.assertIn(paragraph, locale_text(html, 'en'))
                self.assertNotIn('[Continued on page A12.]', html)
                self.assertEqual(html.count(image), 1)
            plan['text_treatments'][0].update(pattern_id='T09', action='split', params={'cut': 8})
            plan_path.write_text(json.dumps(plan))
            failed = subprocess.run(command, cwd=renderer, capture_output=True, text=True)
            self.assertNotEqual(failed.returncode, 0)
            receipt = json.loads(receipt_path.read_text())
            self.assertEqual(receipt['status'], 'failed')
            self.assertEqual(receipt['articles'][-1]['status'], 'failed')
            self.assertIn('T09/split', receipt['articles'][-1]['error'])

if __name__ == '__main__':
    unittest.main()
