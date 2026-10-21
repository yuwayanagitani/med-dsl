#!/usr/bin/env python3
"""文書64の手指定期待を展開する。runtimeはimportせず、出力から期待を作らない。"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
import gen_temporal_measurement_fixtures as m
import gen_quantity_fixtures as q
ROOT = Path(os.environ.get('P2_REPO') or Path(__file__).resolve().parents[3]).resolve()
DIRECTORY = ROOT/'examples/p2-library'
PROFILE = 'p2-clinical-library-draft-1'
SPEC = hashlib.sha256((ROOT/'src/med_dsl/clinical_library_spec.json').read_bytes()).hexdigest()
PROPERTY = 'fiction:measurement:property:A@1'
SPECIMEN = {'kind': 'known', 'ref': 'fiction:specimen:s', 'version': '1'}
METHOD = {'kind': 'known', 'ref': 'fiction:method:m', 'version': '1'}
METHOD2 = {'kind': 'known', 'ref': 'fiction:method:m', 'version': '2'}
UNKNOWN = {'kind': 'unknown'}
POLICY = 'fiction:decimal-half-even@1'
check = m.check
day = m.day
FLOWS = {
    'line': {'retained': ['value:rounded_text'], 'lost': ['value:exact', 'record:identity', 'validity', 'context:specimen', 'context:method', 'origin', 'confirmation'], 'added': ['rounding_policy']},
    'exchange': {'retained': ['value:exact_domain', 'unit', 'quantity_kind', 'context:property', 'context:specimen', 'context:method', 'origin_kind', 'human_confirmed'],
                 'lost': ['record:identity', 'validity', 'review:identity', 'revision_history'], 'added': []},
    'trend': {'retained': ['relation_set', 'direction'], 'lost': ['value:exact', 'record:identity', 'validity', 'context', 'origin', 'confirmation'], 'added': ['assumption:independent_time_variables']}}


def rec(ident='A', **change):
    op = {'id': ident, 'kind': 'record', 'slot_ref': 'S', 'property_ref': PROPERTY, 'specimen': deepcopy(SPECIMEN), 'method': deepcopy(METHOD),
          'validity': m.span(1, 10), 'value': {'magnitude': q.point(2), 'unit_ref': 'u_ten', 'quantity_kind_ref': 'k_a'}, 'certainty': 'confirmed',
          'recorded_at': day(2), 'origin': {'kind': 'observed', 'ref': 'fiction:library:origin:'+ident}, 'observer': {'kind': 'unknown'}}
    op.update(change)
    return op


def fix(ident, corrects, **change):
    change.setdefault('recorded_at', day(6))
    op = rec(ident, **change)
    op['kind'] = 'correct'
    op['corrects'] = list(corrects)
    op['reason'] = '架空の訂正'
    return op


def confirm(record, at=3, ident=None):
    return {'id': ident or 'R'+record, 'kind': 'confirm', 'record_ref': record, 'reviewer_ref': 'fiction:human:reviewer', 'recorded_at': day(at)}


def value(magnitude=None, unit='u_ten', kind='k_a'):
    return {'magnitude': deepcopy(magnitude if magnitude is not None else q.point(2)), 'unit_ref': unit, 'quantity_kind_ref': kind}


def line(version='1', unit='u_base', places=1, ident='dest:record-line', form='single_point'):
    return {'id': ident, 'version': version, 'output': {'kind': 'line'}, 'elements': [{'element': 'value', 'form': form, 'unit_ref': unit, 'decimal_places': places}]}


def exchange(version, contexts=('property',), unit='u_base', form='domain', ident='dest:numeric-exchange'):
    return {'id': ident, 'version': version, 'output': {'kind': 'exchange'},
            'elements': [{'element': 'value', 'form': form, 'unit_ref': unit}] + [{'element': 'context', 'field': f, 'requires': 'known'} for f in contexts]}


def trend(version='1', match=('method', 'property', 'specimen'), ident='dest:trend-summary'):
    return {'id': ident, 'version': version, 'output': {'kind': 'trend'}, 'elements': [{'element': 'trend', 'context_match': list(match)}]}


PB1, PB2, PB3 = exchange('1'), exchange('2', ('property', 'method')), exchange('3', ('property', 'method', 'specimen'))
PA1, PC1 = line(), trend()
PE1 = {'id': 'dest:registry-entry', 'version': '1', 'output': {'kind': 'exchange'},
       'elements': [{'element': 'value', 'form': 'domain', 'unit_ref': 'u_ten'}, {'element': 'context', 'field': 'specimen', 'requires': 'known'},
                    {'element': 'context', 'field': 'method', 'requires': 'known'}]}


def ref(profile):
    return {'id': profile['id'], 'version': profile['version']}


def single(ident, profile, at=5, view='v', slot='S'):
    return {'id': ident, 'view_ref': view, 'slot_ref': slot, 'destination_ref': ref(profile), 'target_at': day(at)}


def between(ident, profile, start=3, end=5, view='v', slot='S'):
    return {'id': ident, 'view_ref': view, 'slot_ref': slot, 'destination_ref': ref(profile), 'from_at': day(start), 'to_at': day(end)}


def std():
    return [rec(), confirm('A')]


def request(ops=None, queries=None, destinations=None, views=None, slots=None, budget=100000):
    return {'schema_version': 'p2-library-request-draft-1', 'operation': 'run_clinical_library',
            'consumer': {'profile': PROFILE, 'profile_spec_sha256': SPEC, 'operations': ['run_clinical_library'],
                         'temporal_measurement_profile': m.PROFILE, 'temporal_measurement_profile_spec_sha256': m.SPEC,
                         'quantity_profile': m.QPROFILE, 'quantity_profile_spec_sha256': m.QSPEC},
            'library': {'ref': 'fiction:library:session@1', 'slots': deepcopy(slots if slots is not None else [{'id': 'S', 'subject_ref': 'u'}]),
                        'operations': deepcopy(ops if ops is not None else std())},
            'destinations': deepcopy(destinations if destinations is not None else [PA1]),
            'views': deepcopy(views if views is not None else [{'id': 'v', 'as_of': day(8)}]),
            'queries': deepcopy(queries if queries is not None else [single('q1', PA1)]), 'budget': {'max_steps': budget}}


def req(element, action, record_ref=None, records=(), candidates=(), slot=None, at=None, ends=None):
    return {'element': element, 'action': action, 'record_ref': record_ref, 'records': list(records), 'candidates': list(candidates),
            'slot_ref': slot, 'target_at': None if at is None else day(at), 'ends': ends}


def dom(low, high=None, lc=True, uc=True):
    return q.domain(low, high, lc, uc)


def exchange_output(domain, unit='u_base', specimen=SPECIMEN, method=METHOD, origin=('observed', 'literal')):
    return {'converted_domain': domain, 'unit_ref': unit, 'quantity_kind_ref': 'k_a',
            'context': {'property_ref': PROPERTY, 'specimen': deepcopy(specimen), 'method': deepcopy(method)},
            'origin': {'record': origin[0], 'quantity': origin[1]}, 'human_confirmed': True}


def line_output(text, coefficient, places=1, unit='u_base'):
    return {'text': text, 'coefficient': coefficient, 'unit_ref': unit, 'decimal_places': places, 'rounding_policy': POLICY}


def trend_output(relation, certain, start=3, end=5):
    return {'relation_set': list(relation), 'certain_relation': certain, 'direction': 'from_relative_to_to', 'from_at': day(start), 'to_at': day(end),
            'assumptions': ['independent_time_variables']}


def row(index, status, reasons, states, selection=None, output=None, flows=None, requests=()):
    """問い合わせ一行の期待。states は要素の (名前, 状態) の列。selection は (記録の id, 確認の列, 対象時点) か、trend では None 以外の辞書。"""
    p = ['results', index]
    checks = [check(p+['status'], status), check(p+['assessment_complete'], True), check(p+['reason_codes'], list(reasons)),
              check(p+['requests'], list(requests)), check(p+['output'], output), check(p+['flows'], flows)]
    for j, (name, state) in enumerate(states):
        checks += [check(p+['elements', j, 'element'], name), check(p+['elements', j, 'state'], state)]
    if selection is None:
        checks.append(check(p+['selection'], None))
    elif type(selection) is tuple:
        record, reviews, at = selection
        checks += [check(p+['selection', 'record_ref'], record), check(p+['selection', 'review_refs'], list(reviews)),
                   check(p+['selection', 'as_of'], day(8)), check(p+['selection', 'target_at'], day(at))]
    else:
        for end, (record, reviews, at) in selection.items():
            checks += [check(p+['selection', end, 'record_ref'], record), check(p+['selection', end, 'review_refs'], list(reviews)),
                       check(p+['selection', end, 'target_at'], day(at))]
    return checks


def satisfied(index, kind, output, states, record='A', reviews=('RA',), at=5):
    return row(index, 'satisfied', [], states, (record, reviews, at), output, FLOWS[kind])


def waiting(index, reasons, states, requests, record=None, reviews=(), at=5):
    return row(index, 'needs_information', reasons, states, (record, reviews, at) if record else None, requests=requests)


def unfinished(index=0, reason='step_limit'):
    p = ['results', index]
    return [check(p+['status'], 'unassessed'), check(p+['assessment_complete'], False), check(p+['reason_codes'], [reason])] + \
           [check(p+[key], None) for key in ('selection', 'elements', 'requests', 'output', 'flows')]


def main():
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    entries = []

    def emit(name, request_, checks, normal=True):
        checks = list(checks)
        if normal:
            checks += [check(['meaning_mode'], 'clinical_library_projection'), check(['converted_to_base'], False), check(['clinical_assertions_added'], []),
                       check(['inferred_information'], []), check(['clinical_confirmation'], 'not_evaluated'), check(['review_verification'], 'structural_only'),
                       check(['uncertainty_propagated'], False), check(['certificate', 'status'], 'not_certified'),
                       check(['certificate', 'evidence_level'], 'known_policy_change'), check(['certificate', 'scope'], None)]
        data = {'schema_version': 'p1-fixture-draft-1', 'fixture_version': 1, 'fixture_id': name, 'condition': name[:3], 'fictional': True,
                'review_state': 'author_draft', 'request': deepcopy(request_), 'expected': {'comparison': 'required_paths', 'checks': checks}}
        raw = (json.dumps(data, ensure_ascii=False, indent=2)+'\n').encode()
        (DIRECTORY/(name.lower()+'.json')).write_bytes(raw)
        entries.append({'fixture_id': name, 'condition': name[:3], 'path': name.lower()+'.json', 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})

    def good(name, request_, rows, steps):
        emit(name, request_, [check(['status'], 'ok'), check(['steps_used'], steps), check(['incomplete'], []), *rows])

    def bad(name, request_, code, status='invalid_input'):
        emit(name, request_, [check(['status'], status), check(['reason_codes'], [code])], False)

    S0 = [('selection', 'met'), ('value', 'met')]
    S1, S2 = S0+[('context:property', 'met')], S0+[('context:property', 'met'), ('context:method', 'met')]
    S3 = S2+[('context:specimen', 'met')]
    missing = lambda field, record='A': req('context:'+field, 'observe_and_record', record)
    # ---- line（Y3） ----
    good('O01', request(), satisfied(0, 'line', line_output('20.0', 200), S0), 32)
    for name, magnitude, places, text, coefficient in [('O02-5-4', q.point(5, 4), 1, '1.2', 12), ('O02-27-20', q.point(27, 20), 1, '1.4', 14),
                                                       ('O02-m5-4', q.point(-5, 4), 1, '-1.2', -12), ('O02-m27-20', q.point(-27, 20), 1, '-1.4', -14),
                                                       ('O02-5-2', q.point(5, 2), 0, '2', 2), ('O02-7-2', q.point(7, 2), 0, '4', 4),
                                                       ('O02-m5-2', q.point(-5, 2), 0, '-2', -2), ('O02-m7-2', q.point(-7, 2), 0, '-4', -4),
                                                       ('O02-places6', q.point(121, 100), 6, '1.210000', 1210000)]:
        profile = line(places=places)
        good(name, request([rec(value=value(magnitude, 'u_base')), confirm('A')], destinations=[profile], queries=[single('q1', profile)]),
             satisfied(0, 'line', line_output(text, coefficient, places), S0), 32)
    profile = line(places=2)
    good('O02-third', request([rec(value=value(q.point(1), 'u_third')), confirm('A')], destinations=[profile], queries=[single('q1', profile)]),
         satisfied(0, 'line', line_output('0.67', 67, 2), S0), 32)
    good('O03', request([rec(value=value(q.interval(1, 2))), confirm('A')]),
         row(0, 'not_representable', ['value_not_a_single_point'], [('selection', 'met'), ('value', 'unrepresentable')], ('A', ('RA',), 5),
             flows={'retained': [], 'lost': ['interval_bounds'], 'added': []}), 32)
    good('O04', request([rec(value=value(q.interval(1, 1), 'u_base')), confirm('A')]), satisfied(0, 'line', line_output('1.0', 10), S0), 32)
    odd = line(version='v-base', unit='v_base')
    good('O05', request(destinations=[odd], queries=[single('q1', odd)]),
         row(0, 'not_representable', ['unit_not_convertible'], [('selection', 'met'), ('value', 'unrepresentable')], ('A', ('RA',), 5),
             flows={'retained': [], 'lost': ['value'], 'added': []}), 32)
    future = line(version='future-unit', unit='fiction:future-unit')
    good('O06', request(destinations=[future], queries=[single('q1', future)]),
         row(0, 'unassessed', ['unknown_unit'], [('selection', 'met'), ('value', 'unassessed')], ('A', ('RA',), 5)), 32)
    good('O07', request([rec(value=value(q.interval(1, 2, True, False))), confirm('A')], destinations=[PB1], queries=[single('q1', PB1)]),
         satisfied(0, 'exchange', exchange_output(dom((10, 1), (20, 1), True, False)), S1), 32)
    # 集約の優先（LD6）：一つの行に表せない要素と足りない要素が並ぶとき、状態の強い方が行を決め、足りない要素の依頼は出さない
    mixed = exchange('mixed', ('method',), unit='v_base')
    good('O08', request([rec(method=UNKNOWN), confirm('A')], destinations=[mixed], queries=[single('q1', mixed)]),
         row(0, 'not_representable', ['unit_not_convertible'], [('selection', 'met'), ('value', 'unrepresentable'), ('context:method', 'unmet')], ('A', ('RA',), 5),
             flows={'retained': [], 'lost': ['value'], 'added': []}), 32)
    unseen = exchange('unseen', ('method',), unit='fiction:future-unit')
    good('O09', request([rec(method=UNKNOWN), confirm('A')], destinations=[unseen], queries=[single('q1', unseen)]),
         row(0, 'unassessed', ['unknown_unit'], [('selection', 'met'), ('value', 'unassessed'), ('context:method', 'unmet')], ('A', ('RA',), 5)), 32)
    # ---- K14：要求の版の更新（Y1・Y2、V3・V4） ----
    triple = dict(destinations=[PB1, PB2, PB3], queries=[single('b1', PB1), single('b2', PB2), single('b3', PB3)])
    point = lambda **kw: exchange_output(dom((20, 1)), **kw)
    good('O10', request(**triple), satisfied(0, 'exchange', point(), S1)+satisfied(1, 'exchange', point(), S2)+satisfied(2, 'exchange', point(), S3), 82)
    incomplete = ['required_information_missing']
    good('O11', request([rec(method=UNKNOWN), confirm('A')], **triple),
         satisfied(0, 'exchange', point(method=UNKNOWN), S1)
         + waiting(1, incomplete, S1+[('context:method', 'unmet')], [missing('method')], 'A', ('RA',))
         + waiting(2, incomplete, S1+[('context:method', 'unmet'), ('context:specimen', 'met')], [missing('method')], 'A', ('RA',)), 82)
    good('O12', request([rec(method={'kind': 'unspecified'}, specimen=UNKNOWN), confirm('A')], **triple),
         satisfied(0, 'exchange', point(specimen=UNKNOWN, method={'kind': 'unspecified'}), S1)
         + waiting(1, incomplete, S1+[('context:method', 'unmet')], [missing('method')], 'A', ('RA',))
         + waiting(2, incomplete, S1+[('context:method', 'unmet'), ('context:specimen', 'unmet')], [missing('method'), missing('specimen')], 'A', ('RA',)), 82)
    second = dict(destinations=[PB2], queries=[single('b2', PB2)])
    candidate = {'record_ref': 'A2', 'origin_kind': 'ai_candidate', 'proposed': deepcopy(METHOD)}
    suggestion = [rec(method=UNKNOWN), confirm('A'), fix('A2', ['A'], origin={'kind': 'ai_candidate', 'ref': 'fiction:ai:A2'})]
    good('O13', request(suggestion, **second),
         waiting(0, incomplete, S1+[('context:method', 'unmet')], [req('context:method', 'confirm_candidate', 'A', candidates=[candidate])], 'A', ('RA',)), 35)
    good('O14', request(suggestion+[confirm('A2', 7)], **second),
         row(0, 'satisfied', [], S2, ('A2', ('RA2',), 5), exchange_output(dom((20, 1)), origin=('ai_candidate', 'ai_candidate')), FLOWS['exchange'])
         + [check(['results', 0, 'selection', 'record_origin', 'kind'], 'ai_candidate')], 37)
    answered = [rec(method=UNKNOWN), confirm('A'), fix('A3', ['A']), confirm('A3', 7)]
    good('O15', request(answered, **second), satisfied(0, 'exchange', point(), S2, 'A3', ('RA3',)), 37)
    # ---- 選択の段階の依頼（Y8） ----
    one = dict(destinations=[PB1])
    good('O20', request(queries=[single('q1', PB1, 11)], **one),
         waiting(0, ['no_adopted_measurement'], [('selection', 'unmet')], [req('selection', 'record_and_confirm', slot='S', at=11)], at=11), 32)
    good('O21', request([rec()], queries=[single('q1', PB1)], **one),
         waiting(0, ['no_adopted_measurement'], [('selection', 'unmet')], [req('selection', 'confirm_pending', records=['A'])]), 31)
    good('O22', request([rec(certainty='suspected'), confirm('A')], queries=[single('q1', PB1)], **one),
         waiting(0, ['no_adopted_measurement'], [('selection', 'unmet')], [req('selection', 'record_and_confirm', slot='S', at=5)]), 32)
    conflict = [rec(), confirm('A'), rec('D', validity=m.span(1, 4), value=value(q.point(5))), confirm('D')]
    good('O23', request(conflict, queries=[single('q1', PB1, 3)], **one),
         waiting(0, ['unresolved_measurement_conflict'], [('selection', 'unmet')], [req('selection', 'resolve_conflict', records=['A', 'D'])], at=3), 36)
    blocked = [rec(), confirm('A'), rec('U', validity={'kind': 'unknown'}, recorded_at=day(4)), confirm('U', 5)]
    good('O24', request(blocked, queries=[single('q1', PB1)], **one),
         waiting(0, ['validity_unknown'], [('selection', 'unmet')], [req('selection', 'refine_validity', records=['U'])]), 36)
    good('O25', request([rec(capabilities=['future:capability']), confirm('A')], queries=[single('q1', PB1)], **one),
         row(0, 'unassessed', ['unknown_capability'], [('selection', 'unassessed')]), 32)
    ai = {'kind': 'ai_candidate', 'ref': 'fiction:ai:A'}
    good('O26', request([rec(origin=ai), confirm('A')], queries=[single('q1', PB1)], **one),
         satisfied(0, 'exchange', exchange_output(dom((20, 1)), origin=('ai_candidate', 'ai_candidate')), S1), 32)
    good('O27', request([rec(origin=ai)], queries=[single('q1', PB1)], **one),
         waiting(0, ['no_adopted_measurement'], [('selection', 'unmet')], [req('selection', 'confirm_pending', records=['A'])]), 31)
    # ---- 部分訂正で選択が変わる（CL-4） ----
    revised = [rec(), confirm('A'), fix('B', ['A'], validity=m.span(4, 6), value=value(q.point(3)), method=deepcopy(METHOD2)), confirm('B', 7)]
    good('O30', request(revised, destinations=[PB2], queries=[single('q3', PB2, 3), single('q5', PB2, 5), single('q6', PB2, 6)]),
         satisfied(0, 'exchange', exchange_output(dom((20, 1))), S2, 'A', ('RA',), 3)
         + satisfied(1, 'exchange', exchange_output(dom((30, 1)), method=METHOD2), S2, 'B', ('RB',), 5)
         + satisfied(2, 'exchange', exchange_output(dom((20, 1))), S2, 'A', ('RA',), 6), 91)
    # ---- trend（Y4） ----
    pair = dict(destinations=[PC1], queries=[between('t1', PC1)])
    both = lambda a, b: {'from': (a, (f'R{a}',), 3), 'to': (b, (f'R{b}',), 5)}
    TS = [('selection', 'met'), ('trend', 'met')]
    good('O40', request(**pair), row(0, 'satisfied', [], TS, both('A', 'A'), trend_output(['equal'], 'equal'), FLOWS['trend']), 47)
    chain = [rec(), confirm('A'), fix('B', ['A'], validity=m.span(4, 6), value=value(q.point(3))), confirm('B', 7)]
    good('O41', request(chain, **pair), row(0, 'satisfied', [], TS, both('A', 'B'), trend_output(['less'], 'less'), FLOWS['trend']), 54)
    changed = [rec(), confirm('A'), fix('B', ['A'], validity=m.span(4, 6), value=value(q.point(3)), method=deepcopy(METHOD2)), confirm('B', 7)]
    good('O42', request(changed, **pair),
         row(0, 'not_representable', ['contexts_differ'], [('selection', 'met'), ('trend', 'unrepresentable')], both('A', 'B'),
             flows={'retained': [], 'lost': ['relation'], 'added': []})
         + [check(['results', 0, 'elements', 1, 'differences'], [{'field': 'method', 'from': METHOD, 'to': METHOD2}])], 54)
    good('O43', request([rec(method=UNKNOWN), confirm('A')], **pair),
         row(0, 'needs_information', incomplete, [('selection', 'met'), ('trend', 'unmet')], both('A', 'A'),
             requests=[req('context:method', 'observe_and_record', 'A', ends=['from', 'to'])]), 47)
    good('O44', request([rec(value=value(q.interval(1, 2))), confirm('A')], **pair),
         row(0, 'satisfied', [], TS, both('A', 'A'), trend_output(['less', 'equal', 'greater'], None), FLOWS['trend']), 47)
    good('O45', request(queries=[between('t1', PC1, 3, 11)], destinations=[PC1]),
         row(0, 'needs_information', ['no_adopted_measurement'], [('selection', 'unmet')], None,
             requests=[req('selection', 'record_and_confirm', slot='S', at=11, ends=['to'])]), 47)
    good('O46', request(conflict, queries=[between('t1', PC1, 3, 11)], destinations=[PC1]),
         row(0, 'needs_information', ['no_adopted_measurement', 'unresolved_measurement_conflict'], [('selection', 'unmet')], None,
             requests=[req('selection', 'record_and_confirm', slot='S', at=11, ends=['to']), req('selection', 'resolve_conflict', records=['A', 'D'], ends=['from'])]), 52)
    good('O47', request([rec(capabilities=['future:capability']), confirm('A')], **pair),
         row(0, 'unassessed', ['unknown_capability'], [('selection', 'unassessed')]), 47)
    good('O48', request([rec(value=value(q.point(2), 'fiction:future-unit')), confirm('A')], **pair),
         row(0, 'unassessed', ['unknown_unit'], [('selection', 'met'), ('trend', 'unassessed')], both('A', 'A')), 47)
    thirds = [rec(), confirm('A'), fix('B', ['A'], validity=m.span(4, 6), value=value(q.point(3)), specimen={'kind': 'known', 'ref': 'fiction:specimen:s', 'version': '2'}), confirm('B', 7)]
    good('O49', request(thirds, **pair),
         row(0, 'not_representable', ['contexts_differ'], [('selection', 'met'), ('trend', 'unrepresentable')], both('A', 'B'),
             flows={'retained': [], 'lost': ['relation'], 'added': []})
         + [check(['results', 0, 'elements', 1, 'differences', 0, 'field'], 'specimen')], 54)
    # ---- データだけで足す出力先・複数の出力先（V2・Y5・Y6・Y7） ----
    good('O50', request(destinations=[PE1], queries=[single('q1', PE1)]),
         satisfied(0, 'exchange', exchange_output(dom((2, 1)), unit='u_ten'), S0+[('context:specimen', 'met'), ('context:method', 'met')]), 32)
    for name, change, code in [('O51', lambda p: p['elements'].append({'element': 'laterality'}), 'unsupported_requirement_element'),
                               ('O52', lambda p: p['output'].update(kind='form_letter'), 'unsupported_output_kind'),
                               ('O53-field', lambda p: p['elements'].append({'element': 'context', 'field': 'laterality', 'requires': 'known'}), 'unsupported_context_field'),
                               ('O53-requires', lambda p: p['elements'].append({'element': 'context', 'field': 'method', 'requires': 'equal_to_previous'}), 'unsupported_context_requirement'),
                               ('O53-form', lambda p: p['elements'][0].update(form='range'), 'unsupported_value_form')]:
        profile = deepcopy(PB1)
        change(profile)
        bad(name, request(destinations=[profile], queries=[single('q1', profile)]), code, 'unsupported_profile')
    multi = dict(destinations=[PA1, PB2, PC1], queries=[single('q1', PA1), single('q2', PB2), between('q3', PC1)])
    expected = (satisfied(0, 'line', line_output('20.0', 200), S0) + satisfied(1, 'exchange', point(), S2)
                + row(2, 'satisfied', [], TS, both('A', 'A'), trend_output(['equal'], 'equal'), FLOWS['trend']))
    good('O60', request(**multi), expected, 97)
    reverse = request(**multi)
    reverse['library']['operations'].reverse()
    reverse['destinations'].reverse()
    reverse['queries'].reverse()
    good('O61', reverse, expected, 97)
    later = request(std()+[rec('F', recorded_at=day(12)), confirm('F', 13)], **multi)
    good('O62', later, expected, 100)
    # ---- 観察者（P2-r、文書74の§2）：記録・訂正の任意の項目 observer を台帳へ渡し、選択の根拠に出す ----
    human, device = {'kind': 'human', 'ref': 'fiction:human:observer'}, {'kind': 'device', 'ref': 'fiction:device:meter'}
    shown = lambda index, observer: [check(['results', index, 'selection', 'record_observer'], observer)]
    good('O70', request([rec(observer=human), confirm('A')]), satisfied(0, 'line', line_output('20.0', 200), S0) + shown(0, human), 32)
    good('O71', request([rec(observer=device), confirm('A')], destinations=[PB1], queries=[single('q1', PB1)]), satisfied(0, 'exchange', point(), S1) + shown(0, device), 32)
    watched = [rec(), confirm('A'), fix('B', ['A'], validity=m.span(4, 6), value=value(q.point(3)), method=METHOD2, observer=human), confirm('B', 7)]
    good('O72', request(watched, destinations=[PB1], queries=[single('q3', PB1, 3), single('q5', PB1, 5)]),
         satisfied(0, 'exchange', point(), S1, 'A', ('RA',), 3) + satisfied(1, 'exchange', exchange_output(dom((30, 1)), method=METHOD2), S1, 'B', ('RB',), 5) + shown(1, human), 64)
    # ---- 静的検査 ----
    for key in ('library', 'destinations', 'views', 'queries', 'consumer', 'budget'):
        broken = request()
        del broken[key]
        bad('N01-missing-'+key, broken, 'missing_field')
    for key in ('source', 'ledger', 'result', 'certificate'):
        broken = request()
        broken[key] = {}
        bad('N01-extra-'+key, broken, 'unknown_field')
    broken = request()
    broken['library'] = None
    bad('N01-null', broken, 'expected_object')
    for key in ('destinations', 'views', 'queries'):
        broken = request()
        broken[key] = []
        bad('N01-empty-'+key, broken, 'empty_collection')
    bad('N01-empty-slots', request(slots=[]), 'empty_collection')
    broken = request(slots=[{'id': 'S', 'subject_ref': 'u'}, {'id': 'S', 'subject_ref': 'u'}])
    bad('N01-duplicate-slots', broken, 'duplicate_identifier')
    bad('N01-duplicate-operations', request([rec(), rec()]), 'duplicate_identifier')
    bad('N01-duplicate-views', request(views=[{'id': 'v', 'as_of': day(8)}, {'id': 'v', 'as_of': day(9)}]), 'duplicate_identifier')
    bad('N01-duplicate-queries', request(queries=[single('q1', PA1), single('q1', PA1)]), 'duplicate_identifier')
    bad('N01-duplicate-destinations', request(destinations=[PA1, PA1]), 'duplicate_destination')
    for key, code in (('view_ref', 'unresolved_view_ref'), ('slot_ref', 'unresolved_slot')):
        broken = request()
        broken['queries'][0][key] = 'absent'
        bad('N02-'+key, broken, code)
    broken = request()
    broken['queries'][0]['destination_ref']['version'] = '99'
    bad('N02-destination', broken, 'unresolved_destination')
    bad('N02-confirm', request([rec(), confirm('absent')]), 'unresolved_record')
    bad('N02-corrects', request([rec(), fix('B', ['absent'])]), 'unresolved_record')
    broken = std()
    broken[0]['kind'] = 'retract'
    bad('N03-kind', request(broken), 'unsupported_operation_kind', 'unsupported_profile')
    broken = std()
    broken[0]['record_sha256'] = '0'*64
    bad('N03-hash', request(broken), 'unknown_field')
    broken = std()
    del broken[0]['property_ref']
    bad('N03-missing', request(broken), 'missing_field')
    bad('N03-validity', request([rec(validity=m.span(5, 4)), confirm('A')]), 'invalid_validity_interval')
    bad('N03-review-time', request([rec(recorded_at=day(2)), confirm('A', 1)]), 'review_precedes_record')
    bad('N03-correction-outside', request([rec(), confirm('A'), fix('B', ['A'], validity=m.span(1, 11))]), 'invalid_revision_interval')
    bad('N03-correction-unbounded', request([rec(validity={'kind': 'unknown'}), confirm('A'), fix('B', ['A'])]), 'unsupported_revision_scope', 'unsupported_profile')
    bad('N03-denominator', request([rec(value=value(q.point(1, 0))), confirm('A')]), 'invalid_rational')
    bad('N03-bits', request([rec(value=value(q.point(2**63))), confirm('A')]), 'rational_integer_limit', 'resource_limit')
    bad('N03-dimension', request([rec(value=value(q.point(1), 'v_base')), confirm('A')]), 'input_dimension_mismatch')
    unknown = {'kind': 'unknown'}
    good('O73', request([rec(observer=unknown), confirm('A')]), satisfied(0, 'line', line_output('20.0', 200), S0) + shown(0, unknown), 32)
    missing_observer = [rec(), confirm('A')]
    del missing_observer[0]['observer']
    bad('N03-observer-missing', request(missing_observer), 'missing_field')
    bad('N03-observer-unknown-ref', request([rec(observer={'kind': 'unknown', 'ref': 'x'}), confirm('A')]), 'unknown_field')
    bad('N03-observer-kind', request([rec(observer={'kind': 'robot', 'ref': 'x'}), confirm('A')]), 'invalid_observer')
    bad('N03-observer-ref', request([rec(observer={'kind': 'human', 'ref': ''}), confirm('A')]), 'expected_nonempty_string')
    watching = [rec(), confirm('A')]
    watching[1]['observer'] = {'kind': 'human', 'ref': 'x'}
    bad('N03-observer-confirm', request(watching), 'unknown_field')
    bad('N03-property-kind', request([rec(property_ref='fiction:measurement:property:B@1'), confirm('A')]), 'property_quantity_kind_mismatch')
    bad('N03-origin', request([rec(origin={'kind': 'guess', 'ref': 'x'}), confirm('A')]), 'invalid_origin')
    # 要求プロファイルの形
    for name, change, code, status in [
            ('N04-line-without-value', lambda p: p.update(elements=[]), 'invalid_destination_profile', 'invalid_input'),
            ('N04-line-domain', lambda p: p['elements'][0].update(form='domain'), 'invalid_destination_profile', 'invalid_input'),
            ('N04-places-negative', lambda p: p['elements'][0].update(decimal_places=-1), 'invalid_decimal_places', 'invalid_input'),
            ('N04-places-bool', lambda p: p['elements'][0].update(decimal_places=True), 'invalid_decimal_places', 'invalid_input'),
            ('N04-places-limit', lambda p: p['elements'][0].update(decimal_places=7), 'unsupported_decimal_places', 'unsupported_profile'),
            ('N04-missing-field', lambda p: p.pop('elements'), 'missing_field', 'invalid_input'),
            ('N04-extra-field', lambda p: p.update(extra=1), 'unknown_field', 'invalid_input')]:
        profile = deepcopy(PA1)
        change(profile)
        bad(name, request(destinations=[profile], queries=[single('q1', PA1)]), code, status)
    profile = deepcopy(PC1)
    profile['elements'].append({'element': 'value', 'form': 'domain', 'unit_ref': 'u_base'})
    bad('N04-trend-with-value', request(destinations=[profile], queries=[between('q1', PC1)]), 'invalid_destination_profile')
    profile = deepcopy(PC1)
    profile['elements'][0]['context_match'] = []
    bad('N04-trend-empty-match', request(destinations=[profile], queries=[between('q1', PC1)]), 'invalid_destination_profile')
    # 問い合わせの形
    bad('N05-order-equal', request(destinations=[PC1], queries=[between('q1', PC1, 5, 5)]), 'invalid_trend_order')
    bad('N05-order-reversed', request(destinations=[PC1], queries=[between('q1', PC1, 5, 3)]), 'invalid_trend_order')
    broken = request()
    broken['queries'][0]['from_at'] = day(3)
    bad('N05-single-with-from', broken, 'unknown_field')
    broken = request(destinations=[PC1], queries=[between('q1', PC1)])
    broken['queries'][0]['target_at'] = day(5)
    bad('N05-trend-with-target', broken, 'unknown_field')
    broken = request(destinations=[PC1], queries=[between('q1', PC1)])
    del broken['queries'][0]['to_at']
    bad('N05-trend-without-end', broken, 'missing_field')
    broken = request()
    del broken['queries'][0]['target_at']
    bad('N05-single-without-target', broken, 'missing_field')
    broken = request()
    broken['queries'][0]['target_at'] = '2026-10-05'
    bad('N05-timestamp', broken, 'invalid_timestamp')
    for field in request()['consumer']:
        if field == 'operations':
            continue
        broken = request()
        broken['consumer'][field] = '0'*64 if field.endswith('sha256') else 'future'
        code = ('profile_spec_mismatch' if field == 'profile_spec_sha256' else 'temporal_measurement_profile_mismatch' if field.startswith('temporal_measurement')
                else 'quantity_profile_mismatch' if field.startswith('quantity') else 'unsupported_profile')
        bad('N06-'+field, broken, code, 'unsupported_profile')
    broken = request()
    broken['consumer']['profile_spec_sha256'] = 'x'
    bad('N06-format', broken, 'invalid_sha256')
    for name, number in (('negative', -1), ('bool', True), ('limit', 100001)):
        bad('N07-budget-'+name, request(budget=number), 'step_budget_limit' if name == 'limit' else 'invalid_step_budget', 'resource_limit' if name == 'limit' else 'invalid_input')
    bad('N08-operations', request([confirm('A', 3, 'c'+str(i)) for i in range(257)]), 'item_limit', 'resource_limit')
    bad('N08-destinations', request(destinations=[line(str(i)) for i in range(17)]), 'item_limit', 'resource_limit')
    bad('N08-queries', request(queries=[single('q'+str(i), PA1) for i in range(33)]), 'item_limit', 'resource_limit')

    # ---- 資源 ----
    def sweep(prefix, request_, rows, total, thresholds, cost, fees):
        for budget in thresholds:
            copy = deepcopy(request_)
            copy['budget']['max_steps'] = budget
            checks = [check(['status'], 'ok' if budget >= total else 'resource_limit'), check(['steps_used'], min(budget, total))]
            paid, unfinished_ids = 1+cost, []
            names = sorted(qr['id'] for qr in request_['queries'])
            for index, (build, fee) in enumerate(zip(rows, fees)):
                paid += fee
                if budget >= paid:
                    checks += build(index)
                else:
                    checks += unfinished(index)
                    unfinished_ids.append(names[index])
            incomplete = [{'query': ident, 'reason_codes': ['step_limit']} for ident in unfinished_ids]
            if budget == total-1:
                incomplete.append({'stage': 'completion', 'reason_codes': ['step_limit']})
            checks.append(check(['incomplete'], incomplete))
            emit(prefix+'-'+str(budget), copy, checks)
    sweep('B01', request(), [lambda i: satisfied(i, 'line', line_output('20.0', 200), S0)], 32, [0, 1, 16, 17, 30, 31, 32, 33], 16, [14])
    sweep('B02', request(**pair), [lambda i: row(i, 'satisfied', [], TS, both('A', 'A'), trend_output(['equal'], 'equal'), FLOWS['trend'])], 47, [27, 28, 45, 46, 47], 27, [18])
    sweep('B03', request(**multi), [lambda i: satisfied(i, 'line', line_output('20.0', 200), S0), lambda i: satisfied(i, 'exchange', point(), S2),
                                    lambda i: row(i, 'satisfied', [], TS, both('A', 'A'), trend_output(['equal'], 'equal'), FLOWS['trend'])],
          97, [49, 50, 63, 64, 77, 78, 95, 96, 97], 49, [14, 14, 18])
    big_ops = [rec('R'+str(i)) for i in range(64)] + [confirm('R'+str(i), 3, 'C'+str(i)) for i in range(64)]
    emit('B04-plan', request(big_ops, queries=[single('q'+str(i), PA1, 5, 'v'+str(j)) for i, j in zip(range(32), range(32))],
                             views=[{'id': 'v'+str(i), 'as_of': day(8)} for i in range(64)]),
         [check(['status'], 'resource_limit'), check(['steps_used'], 100000), *unfinished(0), check(['certificate', 'status'], 'not_certified')])
    conditions = {letter: len({e['condition'] for e in entries if e['condition'][0] == letter}) for letter in 'ONB'}
    manifest = {'schema_version': 'p2-fixture-manifest-draft-1', 'suite': 'p2-library', 'review_state': 'author_draft', 'independent_review': False,
                'evaluation_frozen': False, 'conditions': conditions, 'files': entries}
    (DIRECTORY/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'files': len(entries), 'checks': sum(len(json.loads((DIRECTORY/e['path']).read_text())['expected']['checks']) for e in entries), 'conditions': conditions}))


if __name__ == '__main__':
    main()
