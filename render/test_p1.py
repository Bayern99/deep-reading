"""turn_page / declutter / integrity_gate 单元测试。

运行：python3 -m pytest test_p1.py -v  或  python3 test_p1.py
不依赖 PDF（用合成数据）；PDF 相关测试标记为 slow，需真实文件。
"""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from declutter import (
    detect_truncated_para, detect_abrupt_lang_switch,
    detect_repeated_fragment, scan_article,
)
from integrity_gate import check_article

PASS = 0
FAIL = 0


def ok(cond, name):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f'  ✓ {name}')
    else:
        FAIL += 1
        print(f'  ✗ {name}')


def test_declutter_truncated():
    print('declutter.detect_truncated_para')
    hit, d = detect_truncated_para(
        'The conflict is jeopardizing Saudi efforts to build travel and tourism into a pi '
        'for')
    ok(hit, 'dangling "for" detected')
    hit, _ = detect_truncated_para('This is a complete sentence.')
    ok(not hit, 'normal sentence clean')
    hit, _ = detect_truncated_para('She bought a $30 hourglass to rein them in. It takes an hour')
    # "hour" 是完整词，不应误报（保守）
    ok(not hit, 'no false positive on valid word')


def test_declutter_lang_switch():
    print('declutter.detect_abrupt_lang_switch')
    hit, d = detect_abrupt_lang_switch(
        'the 公司 said and 企业 announced but 市场 fell while 股票 rose and 投资 dropped')
    ok(hit, 'fragmented cn-en mix detected')
    hit, _ = detect_abrupt_lang_switch(
        '苹果公司（Apple Inc.）发布了新款 iPhone，这是正常的术语混排。')
    ok(not hit, 'normal term mix clean')


def test_declutter_repeat():
    print('declutter.detect_repeated_fragment')
    hit, _ = detect_repeated_fragment(
        'Sales rose 5% in the quarter. Sales rose 5% in the quarter. Done.')
    ok(hit, 'repeated fragment detected')
    hit, _ = detect_repeated_fragment('Sales rose. Then profits rose. Different.')
    ok(not hit, 'no false positive')


def test_declutter_scan():
    print('declutter.scan_article')
    art = {'id': 'T1', 'body_en': 'Good para one.\n\nBad para ends with for',
           'body_cn': '正常中文段落。'}
    iss = scan_article(art)
    ok(any(i['type'] == 'truncated_para' for i in iss), 'scan finds truncated')


def test_gate_turn_to():
    print('integrity_gate.check_article turn_to')
    # 有 turn_to 无标记 + 图注结尾 → block
    a = {'id': 'T2', 'turn_to': 'A8', 'type': 'news',
         'body_en': 'Some text.\n\n[Photo: Someone (WSJ)]', 'body_cn': '正文。'}
    passed, iss = check_article(a)
    ok(not passed and any(i['code'] == 'turn_to_unmerged' for i in iss),
       'unmerged turn_to blocked')
    # 有 turn_to 有标记 → 不因此 block
    a2 = dict(a, continuation_merged={'status': 'verified_complete'})
    passed2, iss2 = check_article(a2)
    ok(all(i['code'] != 'turn_to_unmerged' for i in iss2),
       'verified turn_to not blocked for this code')


def test_gate_turn_marker():
    print('integrity_gate.check_article turn marker')
    a = {'id': 'T3', 'type': 'news',
         'body_en': 'Text here. Please turn to page A8 for more.',
         'body_cn': ''}
    passed, iss = check_article(a)
    ok(not passed and any(i['code'] == 'turn_marker_leftover' for i in iss),
       'turn marker leftover blocked')
    a_cn = {'id': 'T3b', 'type': 'news', 'body_en': 'Text.',
            'body_cn': '正文。[请见A10页]'}
    passed, iss = check_article(a_cn)
    ok(not passed, 'CN turn marker blocked')


def test_gate_few_paras():
    print('integrity_gate.check_article few paras')
    a = {'id': 'T4', 'type': 'news', 'body_en': 'Only one para.', 'body_cn': ''}
    passed, iss = check_article(a)
    ok(passed and any(i['code'] == 'too_few_paras' and i['level'] == 'warn'
                      for i in iss),
       'few paras warns (not blocks)')
    # brief 类型不警告
    b = dict(a, type='brief')
    _, issb = check_article(b)
    ok(not any(i['code'] == 'too_few_paras' for i in issb),
       'brief exempt')


def test_gate_misaligned():
    print('integrity_gate.check_article para alignment')
    a = {'id': 'T5', 'type': 'news',
         'body_en': '\n\n'.join(f'en para {i}.' for i in range(10)),
         'body_cn': '\n\n'.join(f'中文段 {i}。' for i in range(4))}
    passed, iss = check_article(a)
    ok(passed and any(i['code'] == 'para_misaligned' for i in iss),
       'misaligned paras warn')


def test_gate_clean():
    print('integrity_gate.check_article clean')
    a = {'id': 'T6', 'type': 'news',
         'body_en': '\n\n'.join(f'English paragraph {i} with content.' for i in range(5)),
         'body_cn': '\n\n'.join(f'中文段落{i}内容。' for i in range(5))}
    passed, iss = check_article(a)
    ok(passed and not iss, 'clean article passes')


if __name__ == '__main__':
    for fn in [test_declutter_truncated, test_declutter_lang_switch,
               test_declutter_repeat, test_declutter_scan,
               test_gate_turn_to, test_gate_turn_marker,
               test_gate_few_paras, test_gate_misaligned, test_gate_clean]:
        fn()
    print(f'\n{PASS} passed, {FAIL} failed')
    sys.exit(1 if FAIL else 0)
