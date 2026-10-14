"""Source-bound factual checks, separate from narrative exactness and visual approval.

Evidence is supplied by the host caller, never accepted from generated HTML.
Literal checks establish necessary conditions; host review establishes meaning.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
import re
from typing import Any

import lxml.html

SCHEMA = 'claim-evidence-v1'
NUMBER = re.compile(
    r'(?<![\d.])(?P<currency>\$)?(?P<value>(?:(?<![A-Za-z0-9])[-+])?\d+(?:,\d{3})*(?:\.\d+)?)'
    r'\s*(?P<unit>万美元|亿美元|万亿美元|美元|billion|million|trillion|bps\b|basis points?\b|(?:个)?基点|个百分点|%|[KM]\b)?',
    re.I,
)
SCALES = {'k': '1000', 'm': '1000000', 'million': '1000000',
          'billion': '1000000000', 'trillion': '1000000000000',
          '万美元': '10000', '亿美元': '100000000', '万亿美元': '1000000000000'}


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def evidence_source_digest(canonical: dict[str, Any]) -> str:
    """Bind actual publication source; narrative digest alone excludes curated inputs."""
    return _hash({k: canonical.get(k) for k in
                  ('issue_date', 'article_id', 'content_digest', 'blocks', 'metadata', 'context_dossier')})


def numeric_tokens(text: str) -> list[tuple[Decimal, str]]:
    out = []
    for m in NUMBER.finditer(text):
        value = Decimal(m['value'].replace(',', ''))
        unit = (m['unit'] or '').lower()
        if unit in SCALES:
            value *= Decimal(SCALES[unit])
        if unit in ('%', '个百分点'):
            normalized = 'percent'
        elif unit in ('bps', '基点', '个基点') or unit.startswith('basis point'):
            normalized = 'bps'
        elif m['currency'] or unit.endswith('美元'):
            normalized = 'USD'
        else:
            normalized = 'number'
        out.append((value, normalized))
    return out


def _quote_text(text: str) -> str:
    # Typography/outer delimiters only: no word, punctuation or clause rewriting.
    return re.sub(r'\s+', ' ', text.strip().strip('“”"「」')).strip()


def _claim(target: str, kind: str, payload: Any, **extra: Any) -> dict[str, Any]:
    return {'target': target, 'kind': kind, 'payload': payload,
            'claim_digest': _hash(payload), **extra}


def canonical_claims(canonical: dict[str, Any]) -> list[dict[str, Any]]:
    claims = []
    for collection, kind in [('derived_quotes', 'quote'), ('derived_metrics', 'metric')]:
        for item in canonical.get(collection, []):
            claims.append(_claim(f'derive:{item["id"]}', kind, item,
                                 source_blocks=item.get('source_block', '').split(',')))
    context = canonical.get('context_dossier')
    if context:
        claims.append(_claim('context:ctx1', 'context', context,
                             text=context.get('text_cn', '') + ' ' + context.get('text_en', '')))
    return claims


def editorial_claims(doc: lxml.html.HtmlElement) -> list[dict[str, Any]]:
    """Inventory all authored body text and SVG geometry, including tails and attributes.

    Only compiler-injected refs/derives and fixed language controls are exempt.
    Optional data-claim groups a complete intervention, not a trustedness flag.
    """
    claims = []
    tree = doc.getroottree()
    skipped = {'head'}
    controls = {'中文', 'EN', 'English', '中', '返回顶部', 'Back to top'}

    def walk(el):
        if not isinstance(el.tag, str):
            return
        path = tree.getpath(el)
        if el.tag.lower() in ('script', 'style'):
            if el.tag.lower() == 'script' or re.search(r'\bcontent\s*:', el.text_content(), re.I):
                claims.append(_claim('html:' + path, 'presentation_code',
                                     lxml.html.tostring(el, encoding='unicode', with_tail=False), text=''))
            return
        if el.tag.lower() in skipped:
            for child in el:
                walk(child)
            return
        if el.get('data-ref') or (el.get('data-field') and el.xpath('ancestor::*[@data-derive]')):
            return
        if el.get('data-derive') and not el.xpath('.//*[@data-field]'):
            return
        if el.tag.lower() == 'svg' or el.get('data-claim'):
            payload = lxml.html.tostring(el, encoding='unicode', with_tail=False)
            claims.append(_claim('html:' + path, 'chart' if el.tag.lower() == 'svg' or el.xpath('.//svg') else 'direct_quote' if el.tag.lower() in ('blockquote', 'q') else 'editorial',
                                 payload, text=el.text_content()))
            return
        if el.text and el.text.strip():
            text = el.text.strip()
            if not (el.tag.lower() == 'button' and text in controls):
                claims.append(_claim('html:' + path + '/text()', 'direct_quote' if el.tag.lower() in ('blockquote', 'q') else 'editorial', text, text=text))
        for attr in ('title', 'alt', 'aria-label'):
            text = el.get(attr)
            if text and not (el.tag.lower() == 'button' and text in controls):
                claims.append(_claim('html:' + path + '/@' + attr, 'editorial', text, text=text))
        for child in el:
            walk(child)
            if child.tail and child.tail.strip():
                claims.append(_claim('html:' + tree.getpath(child) + '/tail()', 'editorial',
                                     child.tail.strip(), text=child.tail.strip()))
    walk(doc)
    return claims


def make_evidence_record(canonical: dict[str, Any], claim: dict[str, Any], *,
                         kind: str, spans: list[dict[str, str]],
                         review: dict[str, str] | None = None,
                         calculation: dict[str, Any] | None = None) -> dict[str, Any]:
    """Bind caller-authored evidence to an inventoried claim; does not approve it."""
    record = {'schema_version': SCHEMA, 'target': claim['target'], 'kind': kind,
              'source_digest': evidence_source_digest(canonical),
              'claim_digest': claim['claim_digest'], 'spans': spans}
    if review is not None:
        record['review'] = review
    if calculation is not None:
        record['calculation'] = calculation
    return record


def _span_texts(record, canonical):
    blocks = {b['id']: b for b in canonical['blocks']}
    texts = []
    errors = []
    spans = record.get('spans')
    if not isinstance(spans, list) or not spans:
        return [], ['Evidence requires nonempty source spans']
    for span in spans:
        if not isinstance(span, dict) or not all(isinstance(span.get(k), str) for k in ('block', 'locale', 'text')):
            errors.append('Malformed evidence span')
            continue
        block = blocks.get(span.get('block'))
        locale = span.get('locale')
        text = span.get('text')
        if not block or locale not in ('en', 'cn') or not isinstance(text, str) or not text.strip():
            errors.append('Invalid evidence block, locale or text')
        elif text not in block['text_' + locale]:
            errors.append(f'Evidence span absent from {span["block"]} ({locale})')
        else:
            texts.append(text)
    return texts, errors


def _calculated_token(calc, texts):
    """Finite Decimal arithmetic; no eval, tolerances, or arbitrary executable formulas."""
    operands = []
    for operand in calc['operands']:
        si, ti = operand['span'], operand['token']
        if not isinstance(si, int) or not isinstance(ti, int) or si < 0 or ti < 0:
            raise ValueError('Invalid calculation operand index')
        operands.append(numeric_tokens(texts[si])[ti])
    if len(operands) != 2:
        raise ValueError('Calculation requires exactly two operands')
    (a, au), (b, bu) = operands
    op = calc['operation']
    if op == 'basis_points_change' and au == bu == 'percent':
        value, unit = (a - b) * 100, 'bps'
    elif op in ('difference', 'sum') and au == bu:
        value, unit = (a - b if op == 'difference' else a + b), au
    elif op == 'ratio' and au == bu:
        value, unit = a / b, 'number'
    else:
        raise ValueError('Unsupported calculation or incompatible units')
    places = calc.get('decimal_places', 0)
    if type(places) is not int or not 0 <= places <= 8:
        raise ValueError('Invalid decimal_places')
    value = value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    if Decimal(str(calc['result'])) != value or calc['unit'] != unit:
        raise ValueError('Incorrect calculation result or unit')
    return value, unit


def _check_claim(claim, canonical, record):
    errors = []
    pending = []
    payload = claim['payload']
    blocks = {b['id']: b for b in canonical['blocks']}
    # Historical candidate data is evidence, not an automatic approval record.
    cited = [blocks[b] for b in claim.get('source_blocks', []) if b in blocks]
    if record is None:
        texts = [b['text_en'] for b in cited] + [b['text_cn'] for b in cited]
        if claim['kind'] == 'quote':
            for locale in ('cn', 'en'):
                quoted = _quote_text(payload.get('quote_' + locale, ''))
                if not quoted or not any(quoted in _quote_text(b['text_' + locale]) for b in cited):
                    errors.append(f'Quote is not verbatim in cited source ({locale})')
        if claim['kind'] == 'metric':
            supported = {t for text in texts for t in numeric_tokens(text)}
            for field in ('value', 'value_cn'):
                missing = [str(v) + ' ' + u for v, u in numeric_tokens(payload.get(field, '')) if (v, u) not in supported]
                if missing:
                    errors.append(f'Unsupported {field}: {", ".join(missing)}')
        if claim['kind'] in ('editorial', 'chart', 'direct_quote'):
            pending.append('Authored numbers require scoped evidence or a calculation: ' +
                           ', '.join(str(v) + ' ' + u for v, u in numeric_tokens(claim.get('text', ''))))
        pending.append('Missing host evidence record')
    else:
        if not isinstance(record, dict) or record.get('schema_version') != SCHEMA:
            errors.append('Invalid evidence record schema')
            return errors, pending
        if record.get('source_digest') != evidence_source_digest(canonical):
            errors.append('Stale source evidence')
        if record.get('claim_digest') != claim['claim_digest']:
            errors.append('Stale claim evidence')
        texts, span_errors = _span_texts(record, canonical)
        errors.extend(span_errors)
        if span_errors:
            return errors, pending
        kind = record.get('kind')
        if kind not in ('quote', 'number', 'calculation', 'fact', 'interpretation', 'chart', 'nonfactual'):
            errors.append('Unknown evidence kind')
        if claim['kind'] in ('quote', 'direct_quote') and kind != 'quote':
            errors.append('A direct quotation cannot be relabeled as interpretation')
        if claim['kind'] == 'chart' and kind != 'chart':
            errors.append('SVG/visual intervention requires chart review')
        if kind == 'quote':
            if claim['kind'] == 'quote':
                for locale in ('cn', 'en'):
                    quoted = _quote_text(payload.get('quote_' + locale, ''))
                    localized = [s['text'] for s in (record.get('spans') or []) if isinstance(s, dict) and s.get('locale') == locale and isinstance(s.get('text'), str)]
                    if not quoted or not any(quoted in _quote_text(t) for t in localized):
                        errors.append(f'Quote does not match evidence ({locale})')
            elif not _quote_text(claim.get('text', '')) or not any(_quote_text(claim.get('text', '')) in _quote_text(t) for t in texts):
                errors.append('Quotation does not match evidence')
        supported = {t for text in texts for t in numeric_tokens(text)}
        numeric_text = _numeric_text(claim)
        if record.get('presentation_numbers'):
            try:
                numeric_text = _chart_numeric_text(claim, record['presentation_numbers'])
            except (TypeError, ValueError, KeyError, IndexError) as exc:
                errors.append(f'Invalid chart presentation annotation: {exc}')
        calc = record.get('calculation')
        if calc is not None:
            try:
                token = _calculated_token(calc, texts)
                supported.add(token)
                if token not in numeric_tokens(numeric_text):
                    errors.append('Calculation result is not displayed in the claim')
            except (KeyError, IndexError, TypeError, ValueError, InvalidOperation, ZeroDivisionError) as exc:
                errors.append(f'Invalid calculation: {exc}')
        elif kind == 'calculation':
            errors.append('Calculation record is missing operands and operation')
        # Interpretations are not exempt from factual numeric checks.
        if kind != 'quote':
            missing = [str(v) + ' ' + u for v, u in numeric_tokens(numeric_text) if (v, u) not in supported]
            if missing:
                errors.append('Numbers absent from evidence/calculation: ' + ', '.join(missing))
        review = record.get('review') or {}
        if not isinstance(review, dict):
            errors.append('Malformed host review')
            review = {}
        if review.get('decision') == 'rejected':
            errors.append('Host semantic review rejected claim: ' + str(review.get('reason', '')))
        elif not (review.get('decision') == 'supported' and
                  all(isinstance(review.get(k), str) and review[k].strip() for k in ('reviewer', 'reason'))):
            pending.append('Host must review attribution, meaning, bilingual alignment and visual encoding')
        if kind == 'interpretation':
            text = claim.get('text', '')
            if not re.search(r'\b(?:interpretation|editorial analysis)\b|编辑解读|编者解读', text, re.I):
                errors.append('Interpretation requires a visible interpretation label')
    return errors, pending


def _numeric_text(claim):
    if claim['kind'] == 'metric':
        p = claim['payload']
        return ' '.join(str(p.get(k, '')) for k in ('value', 'value_cn', 'label_cn', 'label_en', 'note_cn', 'note_en'))
    return claim.get('text', '')


def _chart_numeric_text(claim, annotations):
    """Exclude only specific host-reviewed SVG axis labels, never all equal values."""
    if claim['kind'] != 'chart' or not isinstance(annotations, list):
        raise ValueError('Presentation annotations require a chart and a list')
    root = lxml.html.fromstring(claim['payload'])
    text_nodes = root.xpath('.//text')
    excluded = set()
    for annotation in annotations:
        if not isinstance(annotation, dict):
            raise ValueError('Malformed axis annotation')
        index = annotation.get('text_index')
        if type(index) is not int or not 1 <= index <= len(text_nodes):
            raise ValueError('Invalid SVG text_index')
        node = text_nodes[index - 1]
        if annotation.get('role') != 'axis_tick' or annotation.get('text') != node.text_content():
            raise ValueError('Axis role/text does not match the bound SVG node')
        if not isinstance(annotation.get('reason'), str) or not annotation['reason'].strip():
            raise ValueError('Axis annotation needs a review reason')
        excluded.add(node)
    parts = []
    for text in root.xpath('.//text()'):
        owner = text.getparent().getparent() if text.is_tail else text.getparent()
        if owner is not None and not any(n in excluded for n in [owner, *owner.iterancestors()]):
            parts.append(str(text))
    return ' '.join(parts)


def validate_claim_provenance(canonical: dict[str, Any], doc: lxml.html.HtmlElement | None = None, *,
                              evidence_records: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    candidates = canonical_claims(canonical)
    active_derives = {el.get('data-derive') for el in doc.xpath('//*[@data-derive]')} if doc is not None else None
    active_context = doc is None or any(t.strip() in ('ctx1', 'context') for el in doc.xpath('//*[@data-ref]') for t in el.get('data-ref', '').split(','))
    authored = editorial_claims(doc) if doc is not None else []
    claims = candidates + authored
    records = {}
    errors = []
    if evidence_records is not None and not isinstance(evidence_records, list):
        errors.append('Evidence records must be a list')
        evidence_records = []
    for record in evidence_records or []:
        if not isinstance(record, dict) or not isinstance(record.get('target'), str):
            errors.append('Malformed evidence record')
            continue
        target = record['target']
        if target in records:
            errors.append(f'Duplicate evidence target: {target}')
        records[target] = record
    targets = {c['target'] for c in claims}
    for target in records.keys() - targets:
        errors.append(f'Evidence target not present: {target}')
    if len(targets) != len(claims):
        errors.append('Duplicate canonical claim identifiers')
    results = []
    for claim in claims:
        failures, pending = _check_claim(claim, canonical, records.get(claim['target']))
        active = active_context if claim['target'] == 'context:ctx1' else active_derives is None or claim['target'].startswith('html:') or claim['target'].removeprefix('derive:') in active_derives
        results.append({**claim, 'active': active,
                        'status': 'rejected' if failures else 'needs_review' if pending else 'supported',
                        'errors': failures, 'review_needed': pending})
    active_results = [r for r in results if r['active']]
    for r in active_results:
        if r['status'] != 'supported':
            errors.append(f'{r["target"]}: {r["status"]}: ' + '; '.join(r['errors'] + r['review_needed']))
    return {'schema_version': SCHEMA, 'passed': not errors, 'source_digest': evidence_source_digest(canonical),
            'compiled_digest': hashlib.sha256(lxml.html.tostring(doc, encoding='unicode', doctype='<!DOCTYPE html>').encode()).hexdigest() if doc is not None else None,
            'claims': results, 'evidence_records': evidence_records or [], 'errors': errors}
