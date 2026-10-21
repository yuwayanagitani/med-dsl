#!/usr/bin/env python3
"""文書68の手指定期待を展開する。runtimeはimportせず、出力から期待を作らない。"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
import gen_library_fixtures as lib

ROOT = Path(os.environ.get('P2_REPO') or Path(__file__).resolve().parents[3]).resolve()
DIRECTORY = ROOT/'examples/p2-grounding'
PROFILE = 'p2-structure-grounding-draft-1'
SPEC = hashlib.sha256((ROOT/'src/med_dsl/structure_grounding_spec.json').read_bytes()).hexdigest()
STRUCTURE = 'fhir-r5-observation'
check, q, m, day = lib.check, lib.q, lib.m, lib.day
KNOWN = {'method': {'ref': 'fiction:method:m', 'version': '1'}, 'specimen': {'ref': 'fiction:specimen:s', 'version': '1'}}
NOT_CARRIED = ['record:identity', 'review:identity', 'revision_history', 'quantity_kind', 'context:property', 'origin_kind', 'human_confirmed']
LOST = {'interval_not_representable_as_quantity': 'interval_width', 'open_boundary_not_representable': 'interval_bounds', 'not_decimal_representable': 'exact_value',
        'digits_exceed_limit': 'exact_value', 'period_end_convention_undeclared': 'validity_end'}
ASSUMPTIONS = ['assumption:end_convention:last_second', 'assumption:second_granularity']


def rational(n, d=1):
    return {'numerator': n, 'denominator': d}


def ivl(low, high, lower_closed=True, upper_closed=True):
    return {'kind': 'interval', 'lower': rational(*low), 'upper': rational(*high), 'lower_closed': lower_closed, 'upper_closed': upper_closed}


def target(profile, value='quantity', contexts=('method', 'specimen'), period=None, structure=STRUCTURE):
    found = {'destination_ref': lib.ref(profile), 'structure': structure, 'value': value, 'context_fields': list(contexts)}
    if period is not None:
        found['period'] = {'end_convention': period}
    return found


def grounding(library_request, targets, budget=100000):
    child = deepcopy(library_request)
    child['budget'] = {'max_steps': 0}
    return {'schema_version': 'p2-grounding-request-draft-1', 'operation': 'run_structure_grounding',
            'consumer': {'profile': PROFILE, 'profile_spec_sha256': SPEC, 'operations': ['run_structure_grounding'],
                         'library_profile': lib.PROFILE, 'library_profile_spec_sha256': lib.SPEC},
            'library_request': child, 'targets': deepcopy(targets), 'budget': {'max_steps': budget}}


def one(magnitude=None, unit='u_ten', ops=None, profile=None, query=None, **options):
    """記録A（標準：2 u_ten）の値を替えた、出力先P-B1（既定）の一問い合わせ。"""
    profile = profile or lib.PB1
    ops = ops if ops is not None else [lib.rec(value=lib.value(magnitude if magnitude is not None else q.point(2), unit)), lib.confirm('A')]
    return grounding(lib.request(ops, destinations=[profile], queries=[query or lib.single('q1', profile)]), [target(profile, **options)])


def flows_ok(listed=('method', 'specimen'), known=('method', 'specimen'), carried=False):
    absent = [f for f in listed if f not in known]
    kept = [f for f in listed if f in known]
    unlisted = [f for f in ('method', 'specimen') if f not in listed]
    return {'retained': sorted(['value:exact_domain', 'unit'] + ['context:'+f for f in kept] + (['validity'] if carried else [])),
            'lost': sorted(NOT_CARRIED + ([] if carried else ['validity']) + ['context:'+f for f in unlisted] + ['context_state_distinction:'+f for f in absent]),
            'added': list(ASSUMPTIONS) if carried else []}


def flows_no(reasons):
    return {'retained': [], 'lost': sorted({LOST[r] for r in reasons}), 'added': []}


def projection(value, period=None, absent=(), context=None):
    return {'value': value, 'unit_ref': 'u_base', 'period': period, 'absent': list(absent), 'context': deepcopy(KNOWN if context is None else context)}


def grow(index, status, reasons, state, projected, flows, base='satisfied', structure=STRUCTURE, record='A'):
    p = ['results', index]
    checks = [check(p+['status'], status), check(p+['assessment_complete'], True), check(p+['reason_codes'], list(reasons)), check(p+['base_status'], base),
              check(p+['grounding', 'structure'], structure), check(p+['grounding', 'state'], state),
              check(p+['grounding', 'reasons'], list(reasons) if state == 'not_representable' else []), check(p+['grounding', 'projection'], projected),
              check(p+['flows'], flows), check(p+['requests'], [])]
    if state == 'not_representable':
        checks.append(check(p+['output'], None))
    else:
        checks.append(check(p+['output', 'unit_ref'], 'u_base'))
    if record:
        checks.append(check(p+['selection', 'record_ref'], record))
    return checks


def rep(index, value, flows=None, **options):
    return grow(index, 'satisfied', [], 'representable', projection(value, **options), flows or flows_ok())


def nr(index, reasons):
    return grow(index, 'not_representable', reasons, 'not_representable', None, flows_no(reasons), record='A')


def passed(index, status, reasons, state, flows, requests, structure=STRUCTURE, record=None):
    p = ['results', index]
    checks = [check(p+['status'], status), check(p+['assessment_complete'], True), check(p+['reason_codes'], list(reasons)), check(p+['base_status'], status),
              check(p+['grounding', 'structure'], structure), check(p+['grounding', 'state'], state), check(p+['grounding', 'reasons'], []),
              check(p+['grounding', 'projection'], None), check(p+['flows'], flows), check(p+['requests'], requests)]
    if record:
        checks.append(check(p+['selection', 'record_ref'], record))
    return checks


def unfinished(index=0, reason='step_limit'):
    p = ['results', index]
    return [check(p+['status'], 'unassessed'), check(p+['assessment_complete'], False), check(p+['reason_codes'], [reason])] + \
           [check(p+[key], None) for key in ('selection', 'elements', 'requests', 'output', 'flows', 'grounding', 'base_status')]


def main():
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    entries = []

    def emit(name, request_, checks, normal=True):
        checks = list(checks)
        if normal:
            checks += [check(['meaning_mode'], 'structure_grounding_projection'), check(['converted_to_base'], False), check(['clinical_assertions_added'], []),
                       check(['inferred_information'], []), check(['clinical_confirmation'], 'not_evaluated'), check(['review_verification'], 'structural_only'),
                       check(['uncertainty_propagated'], False), check(['certificate', 'status'], 'not_certified'),
                       check(['certificate', 'evidence_level'], 'known_policy_change'), check(['certificate', 'scope'], None)]
        data = {'schema_version': 'p1-fixture-draft-1', 'fixture_version': 1, 'fixture_id': name, 'condition': name[:3], 'fictional': True,
                'review_state': 'author_draft', 'request': deepcopy(request_), 'expected': {'comparison': 'required_paths', 'checks': checks}}
        raw = (json.dumps(data, ensure_ascii=False, indent=2)+'\n').encode()
        (DIRECTORY/(name.lower()+'.json')).write_bytes(raw)
        entries.append({'fixture_id': name, 'condition': name[:3], 'path': name.lower()+'.json', 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})

    def good(name, request_, rows, steps, library_steps):
        emit(name, request_, [check(['status'], 'ok'), check(['steps_used'], steps), check(['incomplete'], []), check(['library', 'reserved_steps'], library_steps),
                              check(['library', 'steps_used'], library_steps), *rows])

    def bad(name, request_, code, status='invalid_input'):
        emit(name, request_, [check(['status'], status), check(['reason_codes'], [code])], False)

    # ---- 値（G）：M＝37（M_lib＝32） ----
    values = [
        ('G01', 'quantity', q.point(2), 'u_ten', ('rep', {'decimal': '20'})),
        ('G02', 'quantity', q.point(1), 'u_half', ('rep', {'decimal': '0.5'})),
        ('G03', 'quantity', q.point(1), 'u_third', ('nr', ['not_decimal_representable'])),
        ('G04', 'quantity', q.point(1, 8), 'u_base', ('rep', {'decimal': '0.125'})),
        ('G05', 'quantity', q.point(-1, 2), 'u_base', ('rep', {'decimal': '-0.5'})),
        ('G06', 'quantity', q.point(0), 'u_base', ('rep', {'decimal': '0'})),
        ('G07', 'quantity', q.point(7, 4), 'u_ten', ('rep', {'decimal': '17.5'})),
        ('G08', 'quantity', q.point(1, 3), 'u_base', ('nr', ['not_decimal_representable'])),
        ('G09', 'quantity', q.point(1, 50), 'u_base', ('rep', {'decimal': '0.02'})),
        ('G10', 'quantity', ivl((1, 1), (2, 1)), 'u_base', ('nr', ['interval_not_representable_as_quantity'])),
        ('G11', 'quantity', ivl((1, 1), (1, 1)), 'u_base', ('rep', {'decimal': '1'})),
        ('G12', 'quantity', ivl((1, 1), (2, 1), True, False), 'u_base', ('nr', ['interval_not_representable_as_quantity'])),
        ('G13', 'quantity', ivl((1, 1), (4, 3)), 'u_base', ('nr', ['interval_not_representable_as_quantity', 'not_decimal_representable'])),
        ('G20', 'range', ivl((1, 1), (2, 1)), 'u_base', ('rep', {'low': '1', 'high': '2'})),
        ('G21', 'range', q.point(2), 'u_ten', ('rep', {'low': '20', 'high': '20'})),
        ('G22', 'range', ivl((1, 1), (2, 1), True, False), 'u_base', ('nr', ['open_boundary_not_representable'])),
        ('G23', 'range', ivl((1, 1), (2, 1), False, True), 'u_base', ('nr', ['open_boundary_not_representable'])),
        ('G24', 'range', ivl((1, 1), (2, 1), False, False), 'u_base', ('nr', ['open_boundary_not_representable'])),
        ('G25', 'range', ivl((1, 1), (4, 3)), 'u_base', ('nr', ['not_decimal_representable'])),
        ('G26', 'range', ivl((0, 1), (1, 3), False, True), 'u_base', ('nr', ['not_decimal_representable', 'open_boundary_not_representable'])),
        ('G27', 'range', ivl((1, 8), (5, 4)), 'u_base', ('rep', {'low': '0.125', 'high': '1.25'})),
        ('G28', 'range', ivl((1, 1), (1, 1)), 'u_base', ('rep', {'low': '1', 'high': '1'})),
        ('G30', 'quantity', q.point(123456789012345678), 'u_base', ('rep', {'decimal': '123456789012345678'})),
        ('G31', 'quantity', q.point(1234567890123456789), 'u_base', ('nr', ['digits_exceed_limit'])),
        ('G32', 'quantity', q.point(-123456789012345678), 'u_base', ('rep', {'decimal': '-123456789012345678'})),
        ('G33', 'quantity', q.point(12345678901234567, 10**17), 'u_base', ('rep', {'decimal': '0.12345678901234567'})),
        ('G34', 'quantity', q.point(123456789012345678, 10**18), 'u_base', ('nr', ['digits_exceed_limit'])),
    ]
    for name, kind, magnitude, unit, (state, detail) in values:
        if state == 'rep':
            rows = rep(0, detail)
        else:
            rows = nr(0, detail)
        good(name, one(magnitude, unit, value=kind), rows, 37, 32)

    # ---- 期間（P） ----
    G03 = (q.point(1), 'u_third')
    good('P01', one(period='undeclared'), nr(0, ['period_end_convention_undeclared']), 37, 32)
    last = {'start': day(1), 'end': '2026-10-09T23:59:59Z'}
    good('P02', one(period='exclusive_end_as_last_second'), rep(0, {'decimal': '20'}, flows_ok(carried=True), period=last), 37, 32)
    good('P04', one(*G03, period='undeclared'), nr(0, ['not_decimal_representable', 'period_end_convention_undeclared']), 37, 32)
    good('P05', one(*G03, period='exclusive_end_as_last_second'), nr(0, ['not_decimal_representable']), 37, 32)
    corrected = [lib.rec(), lib.confirm('A'), lib.fix('B', ['A'], validity=m.span(4, 6), value=lib.value(q.point(3)), method=lib.METHOD2), lib.confirm('B', 7)]
    good('P06', one(ops=corrected, query=lib.single('q1', lib.PB1, 5), period='exclusive_end_as_last_second'),
         grow(0, 'satisfied', [], 'representable',
              projection({'decimal': '30'}, period={'start': day(4), 'end': '2026-10-05T23:59:59Z'}, context={'method': {'ref': 'fiction:method:m', 'version': '2'}, 'specimen': KNOWN['specimen']}),
              flows_ok(carried=True), record='B'), 42, 37)

    # ---- 文脈（C） ----
    ops_unknown_method = [lib.rec(method=lib.UNKNOWN), lib.confirm('A')]
    good('C01', one(ops=ops_unknown_method), rep(0, {'decimal': '20'}, flows_ok(known=('specimen',)), absent=['method'], context={'specimen': KNOWN['specimen']}), 37, 32)
    good('C02', one(ops=[lib.rec(method={'kind': 'unspecified'}, specimen=lib.UNKNOWN), lib.confirm('A')]),
         rep(0, {'decimal': '20'}, flows_ok(known=()), absent=['method', 'specimen'], context={}), 37, 32)
    good('C03', one(contexts=[]), rep(0, {'decimal': '20'}, flows_ok(listed=(), known=()), context={}), 37, 32)
    good('C04', one(contexts=['method']), rep(0, {'decimal': '20'}, flows_ok(listed=('method',), known=('method',)), context={'method': KNOWN['method']}), 37, 32)
    good('C05', one(ops=[lib.rec(method=lib.METHOD2), lib.confirm('A')]),
         rep(0, {'decimal': '20'}, context={'method': {'ref': 'fiction:method:m', 'version': '2'}, 'specimen': KNOWN['specimen']}), 37, 32)
    good('C06', one(ops=[lib.rec(method={'kind': 'unspecified'}, specimen=lib.UNKNOWN), lib.confirm('A')], contexts=['specimen', 'method']),
         rep(0, {'decimal': '20'}, flows_ok(known=()), absent=['method', 'specimen'], context={}), 37, 32)

    # ---- 通す行・対象のない行（R・D） ----
    triple = dict(destinations=[lib.PB1, lib.PB2, lib.PB3], queries=[lib.single('b1', lib.PB1), lib.single('b2', lib.PB2), lib.single('b3', lib.PB3)])
    missing_method = [lib.req('context:method', 'observe_and_record', record_ref='A')]
    good('R01', grounding(lib.request(ops_unknown_method, **triple), [target(lib.PB1), target(lib.PB2), target(lib.PB3)]),
         rep(0, {'decimal': '20'}, flows_ok(known=('specimen',)), absent=['method'], context={'specimen': KNOWN['specimen']})
         + passed(1, 'needs_information', ['required_information_missing'], 'not_evaluated', None, missing_method, record='A')
         + passed(2, 'needs_information', ['required_information_missing'], 'not_evaluated', None, missing_method, record='A'), 93, 82)
    unit_profile = lib.exchange('x', unit='v_base')
    good('R02', grounding(lib.request(destinations=[unit_profile], queries=[lib.single('q1', unit_profile)]), [target(unit_profile)]),
         passed(0, 'not_representable', ['unit_not_convertible'], 'not_evaluated', {'retained': [], 'lost': ['value'], 'added': []}, [], record='A'), 37, 32)
    good('R03', grounding(lib.request([lib.rec(capabilities=['future:capability']), lib.confirm('A')], destinations=[lib.PB1], queries=[lib.single('q1', lib.PB1)]),
                          [target(lib.PB1)]),
         passed(0, 'unassessed', ['unknown_capability'], 'not_evaluated', None, []), 37, 32)
    good('R04', grounding(lib.request(destinations=[lib.PB1], queries=[lib.single('q1', lib.PB1, 11)]), [target(lib.PB1)]),
         passed(0, 'needs_information', ['no_adopted_measurement'], 'not_evaluated', None, [lib.req('selection', 'record_and_confirm', slot='S', at=11)]), 37, 32)
    good('D01', grounding(lib.request(destinations=[lib.PB1, lib.PB2], queries=[lib.single('q1', lib.PB1), lib.single('q2', lib.PB2)]), [target(lib.PB2)]),
         passed(0, 'satisfied', [], 'not_declared', lib.FLOWS['exchange'], [], structure=None, record='A') + rep(1, {'decimal': '20'}), 65, 57)
    good('D02', grounding(lib.request(destinations=[lib.PA1, lib.PB1], queries=[lib.single('q1', lib.PA1), lib.single('q2', lib.PB1)]), [target(lib.PB1)]),
         passed(0, 'satisfied', [], 'not_declared', lib.FLOWS['line'], [], structure=None, record='A') + [check(['results', 0, 'output', 'text'], '20.0')]
         + rep(1, {'decimal': '20'}), 65, 57)
    multi = dict(destinations=[lib.PA1, lib.PB2, lib.PC1], queries=[lib.single('q1', lib.PA1), lib.single('q2', lib.PB2), lib.between('q3', lib.PC1)])
    good('D03', grounding(lib.request(**multi), [target(lib.PB2)]),
         passed(0, 'satisfied', [], 'not_declared', lib.FLOWS['line'], [], structure=None, record='A') + rep(1, {'decimal': '20'})
         + passed(2, 'satisfied', [], 'not_declared', lib.FLOWS['trend'], [], structure=None, record=None) + [check(['results', 2, 'output', 'relation_set'], ['equal'])], 108, 97)
    good('D04', grounding(lib.request(destinations=[lib.PB1, lib.PB2], queries=[lib.single('b1', lib.PB1), lib.single('b2', lib.PB2)]),
                          [target(lib.PB1, 'quantity'), target(lib.PB2, 'range')]),
         rep(0, {'decimal': '20'}) + rep(1, {'low': '20', 'high': '20'}), 65, 57)

    # ---- 静的検査（N） ----
    base = one()
    for key in ('schema_version', 'operation', 'consumer', 'library_request', 'targets', 'budget'):
        broken = deepcopy(base)
        del broken[key]
        if key == 'schema_version':
            continue                        # schema_version を欠くと P0 の入口に回る（この系列の対象外）
        bad('N01-missing-'+key, broken, 'missing_field')
    broken = deepcopy(base)
    broken['extra'] = 1
    bad('N01-extra', broken, 'unknown_field')
    broken = deepcopy(base)
    broken['library_request'] = []
    bad('N01-library-not-object', broken, 'expected_object')
    for name, path, value, code in [('profile', 'profile', 'p2-other-draft-1', 'unsupported_profile'), ('profile_spec_sha256', 'profile_spec_sha256', '0'*64, 'profile_spec_mismatch'),
                                    ('library_profile', 'library_profile', 'p2-other-draft-1', 'library_profile_mismatch'),
                                    ('library_profile_spec_sha256', 'library_profile_spec_sha256', '0'*64, 'library_profile_mismatch')]:
        broken = deepcopy(base)
        broken['consumer'][path] = value
        bad('N02-'+name, broken, code, 'unsupported_profile')
    broken = deepcopy(base)
    broken['operation'] = 'other_operation'
    bad('N03-operation', broken, 'unsupported_operation', 'unsupported_profile')
    broken = deepcopy(base)
    broken['consumer']['operations'] = ['other_operation']
    bad('N03-consumer-operations', broken, 'unsupported_operation', 'unsupported_profile')
    broken = deepcopy(base)
    broken['library_request']['schema_version'] = 'p2-library-request-draft-2'
    bad('N04-library-schema', broken, 'library_schema_mismatch', 'unsupported_profile')
    broken = deepcopy(base)
    broken['library_request']['budget'] = {'max_steps': 5}
    bad('N05-child-budget', broken, 'invalid_child_budget')
    hashed = [lib.rec(), lib.confirm('A')]
    hashed[1]['record_sha256'] = 'x'
    bad('N06-library-hash', grounding(lib.request(hashed, destinations=[lib.PB1], queries=[lib.single('q1', lib.PB1)]), [target(lib.PB1)]), 'unknown_field')
    unbounded = [lib.rec(validity={'kind': 'unknown'}), lib.confirm('A'), lib.fix('B', ['A'])]
    bad('N06-library-unbounded', grounding(lib.request(unbounded, destinations=[lib.PB1], queries=[lib.single('q1', lib.PB1)]), [target(lib.PB1)]),
        'unsupported_revision_scope', 'unsupported_profile')
    broken = deepcopy(base)
    broken['targets'] = []
    bad('N07-empty', broken, 'empty_collection')
    broken = deepcopy(base)
    broken['targets'] = [target(lib.PB1)]*17
    bad('N07-limit', broken, 'item_limit', 'resource_limit')
    for name, key, value, code in [('structure', 'structure', 'fhir-r4-observation', 'unsupported_structure'), ('value', 'value', 'ratio', 'unsupported_target_value')]:
        broken = deepcopy(base)
        broken['targets'][0][key] = value
        bad('N08-'+name, broken, code, 'unsupported_profile')
    broken = deepcopy(base)
    broken['targets'][0]['period'] = {'end_convention': 'inclusive_end'}
    bad('N08-end-convention', broken, 'unsupported_end_convention', 'unsupported_profile')
    broken = deepcopy(base)
    broken['targets'][0]['context_fields'] = ['property']
    bad('N08-context-field', broken, 'unsupported_context_field', 'unsupported_profile')
    broken = deepcopy(base)
    broken['targets'][0]['context_fields'] = ['method', 'method']
    bad('N09-duplicate-context', broken, 'duplicate_reference')
    broken = deepcopy(base)
    broken['targets'][0]['extra'] = 1
    bad('N09-extra-field', broken, 'unknown_field')
    broken = deepcopy(base)
    del broken['targets'][0]['value']
    bad('N09-missing-field', broken, 'missing_field')
    broken = deepcopy(base)
    broken['targets'] = [target(lib.PB1), target(lib.PB1, 'range')]
    bad('N10-duplicate-target', broken, 'duplicate_target')
    broken = deepcopy(base)
    broken['targets'][0]['destination_ref'] = {'id': 'dest:none', 'version': '1'}
    bad('N10-unresolved', broken, 'unresolved_destination')
    for name, profile, query in [('line', lib.PA1, lib.single('q1', lib.PA1)), ('trend', lib.PC1, lib.between('q1', lib.PC1))]:
        bad('N11-'+name, grounding(lib.request(destinations=[profile], queries=[query]), [target(profile)]), 'unsupported_grounding_output_kind', 'unsupported_profile')
    for name, number in [('bool', True), ('negative', -1), ('limit', 100001)]:
        broken = deepcopy(base)
        broken['budget']['max_steps'] = number
        bad('N12-budget-'+name, broken, 'step_budget_limit' if name == 'limit' else 'invalid_step_budget', 'resource_limit' if name == 'limit' else 'invalid_input')

    # ---- 資源（B） ----
    def sweep(prefix, request_, row_builders, total, thresholds, library_cost, fees):
        for budget in thresholds:
            copy = deepcopy(request_)
            copy['budget']['max_steps'] = budget
            checks = [check(['status'], 'ok' if budget >= total else 'resource_limit'), check(['steps_used'], min(budget, total))]
            paid, unfinished_ids = 1+library_cost, []
            names = sorted(qr['id'] for qr in request_['library_request']['queries'])
            for index, (build, fee) in enumerate(zip(row_builders, fees)):
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
    sweep('B01', one(), [lambda i: rep(i, {'decimal': '20'})], 37, [0, 1, 32, 33, 34, 35, 36, 37], 32, [3])
    sweep('B02', grounding(lib.request(ops_unknown_method, **triple), [target(lib.PB1), target(lib.PB2), target(lib.PB3)]),
          [lambda i: rep(i, {'decimal': '20'}, flows_ok(known=('specimen',)), absent=['method'], context={'specimen': KNOWN['specimen']}),
           lambda i: passed(i, 'needs_information', ['required_information_missing'], 'not_evaluated', None, missing_method, record='A'),
           lambda i: passed(i, 'needs_information', ['required_information_missing'], 'not_evaluated', None, missing_method, record='A')],
          93, [82, 83, 85, 86, 88, 89, 91, 92, 93], 82, [3, 3, 3])
    big_ops = [lib.rec('R'+str(i)) for i in range(64)] + [lib.confirm('R'+str(i), 3, 'C'+str(i)) for i in range(64)]
    big = lib.request(big_ops, destinations=[lib.PB1], queries=[lib.single('q'+str(i), lib.PB1, 5, 'v'+str(j)) for i, j in zip(range(32), range(32))],
                      views=[{'id': 'v'+str(i), 'as_of': day(8)} for i in range(64)])
    emit('B03-plan', grounding(big, [target(lib.PB1)]),
         [check(['status'], 'resource_limit'), check(['steps_used'], 100000), *unfinished(0), check(['certificate', 'status'], 'not_certified')])

    conditions = {letter: len({e['condition'] for e in entries if e['condition'][0] == letter}) for letter in 'GPCRDNB'}
    manifest = {'schema_version': 'p2-fixture-manifest-draft-1', 'suite': 'p2-grounding', 'review_state': 'author_draft', 'independent_review': False,
                'evaluation_frozen': False, 'conditions': conditions, 'files': entries}
    (DIRECTORY/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'files': len(entries), 'checks': sum(len(json.loads((DIRECTORY/e['path']).read_text())['expected']['checks']) for e in entries), 'conditions': conditions}))


if __name__ == '__main__':
    main()
