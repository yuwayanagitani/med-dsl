#!/usr/bin/env python3
"""文書57の手指定期待を展開する。runtimeはimportせず、出力から期待を作らない。"""
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
DIRECTORY = ROOT/'examples/p2-longitudinal'
PROFILE = 'p2-longitudinal-comparison-draft-1'
SPEC = hashlib.sha256((ROOT/'src/med_dsl/longitudinal_spec.json').read_bytes()).hexdigest()
POLICY = 'fiction:independent-time-variables@1'
ASSUMPTIONS = ['independent_time_variables', 'explicit_period_quantity_domain', 'scoped_revision']
METHOD = {'kind': 'known', 'ref': 'fiction:method:m', 'version': '1'}
SPECIMEN = {'kind': 'known', 'ref': 'fiction:specimen:s', 'version': '1'}
PROPERTY = 'fiction:measurement:property:A@1'
OTHER_PROPERTY = 'fiction:measurement:property:A-other@1'
digest = m.digest
check = m.check


def comparison(ident='c', view='v', start='a', end='b', policy=POLICY, caps=None):
    return {'id': ident, 'view_ref': view, 'from_query_ref': start, 'to_query_ref': end, 'comparison_policy': policy,
            'required_capabilities': list(caps if caps is not None else [PROFILE])}


def pair(times=(3, 5), targets=('u_base', 'u_base'), magnitude=None, unit='u_ten'):
    """一つの記録Aだけの計画。query a・b が二つの時点を問う。"""
    return m.request([m.wrapper(magnitude=magnitude, unit=unit)],
                     queries=[m.convert(ident=name, target=target, at=t) for name, target, t in zip('ab', targets, times)])


def chain(n=2, k=8, times=(3, 5), targets=('u_base', 'u_base')):
    plan = m.chain(n, k)
    plan['queries'] = [m.convert(ident=name, target=target, at=t) for name, target, t in zip('abcd', targets, times)]
    return m.seal(plan)


def quantity(plan, index, magnitude):
    plan['source']['quantities'][index]['literal']['magnitude'] = deepcopy(magnitude)
    return m.seal(plan)


def request(plan=None, comparisons=None, budget=100000):
    child = deepcopy(plan if plan is not None else pair())
    child.pop('budget', None)
    return {'schema_version': 'p2-longitudinal-request-draft-1', 'operation': 'compare_longitudinal_measurements',
            'consumer': {'profile': PROFILE, 'profile_spec_sha256': SPEC, 'operations': ['compare_longitudinal_measurements'],
                         'temporal_measurement_profile': m.PROFILE, 'temporal_measurement_profile_spec_sha256': m.SPEC,
                         'quantity_profile': m.QPROFILE, 'quantity_profile_spec_sha256': m.QSPEC},
            'temporal_measurement_plan': child, 'comparisons': deepcopy(comparisons if comparisons is not None else [comparison()]),
            'budget': {'max_steps': budget}}


def seal(req):
    m.seal(req['temporal_measurement_plan'])
    return req


def domain(low, high=None, lc=True, uc=True):
    return q.domain(low, high, lc, uc)


def computed(relation, cost, index=0, start=None, end=None, selected=('A', 'A')):
    """computed の行の期待。start・end は端点の換算領域（q.domain の値）。"""
    p = ['results', index]
    checks = [check(p+['status'], 'computed'), check(p+['assessment_complete'], True), check(p+['reason_codes'], []),
              check(p+['relation_set'], relation), check(p+['certain_relation'], relation[0] if len(relation) == 1 else None),
              check(p+['context_differences'], []),
              check(p+['comparison_evidence', 'assumptions'], ASSUMPTIONS), check(p+['comparison_evidence', 'direction'], 'from_relative_to_to'),
              check(p+['comparison_evidence', 'comparison_policy'], POLICY),
              check(p+['comparison_evidence', 'temporal_measurement_reserved_steps'], cost),
              check(p+['comparison_evidence', 'temporal_measurement_steps_used'], cost),
              check(p+['comparison_evidence', 'quantity_compare', 'reserved_steps'], 12),
              check(p+['comparison_evidence', 'quantity_compare', 'steps_used'], 12),
              check(p+['endpoints', 'from', 'status'], 'computed'), check(p+['endpoints', 'to', 'status'], 'computed'),
              check(p+['endpoints', 'from', 'binding_evidence', 'selected', 0, 'record_ref'], selected[0]),
              check(p+['endpoints', 'to', 'binding_evidence', 'selected', 0, 'record_ref'], selected[1])]
    if start is not None:
        checks.append(check(p+['endpoints', 'from', 'converted_domain'], start))
    if end is not None:
        checks.append(check(p+['endpoints', 'to', 'converted_domain'], end))
    return checks


def not_comparable(reasons, differences, index=0):
    p = ['results', index]
    return [check(p+['status'], 'not_comparable'), check(p+['assessment_complete'], True), check(p+['reason_codes'], reasons),
            check(p+['relation_set'], None), check(p+['certain_relation'], None), check(p+['context_differences'], differences),
            check(p+['comparison_evidence'], None), check(p+['endpoints', 'from', 'status'], 'computed'), check(p+['endpoints', 'to', 'status'], 'computed')]


def unassessed(reasons, index=0, ends=None, endpoints=True):
    """端点が止まった行（endpoints あり）か、比較の未知能力の行（endpoints なし）。"""
    p = ['results', index]
    checks = [check(p+['status'], 'unassessed'), check(p+['assessment_complete'], True), check(p+['reason_codes'], reasons),
              check(p+['relation_set'], None), check(p+['certain_relation'], None), check(p+['context_differences'], None),
              check(p+['comparison_evidence'], None)]
    if endpoints:
        checks += [check(p+['endpoints', side, 'status'], status) for side, status in zip(('from', 'to'), ends)]
    else:
        checks.append(check(p+['endpoints'], None))
    return checks


def unfinished(reason='step_limit', index=0):
    p = ['results', index]
    return [check(p+['status'], 'unassessed'), check(p+['assessment_complete'], False), check(p+['reason_codes'], [reason])] + \
           [check(p+[key], None) for key in ('relation_set', 'certain_relation', 'context_differences', 'endpoints', 'comparison_evidence')]


def difference(field, start, end):
    return {'field': field, 'from': start, 'to': end}


def main():
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    entries = []

    def emit(name, req, checks, normal=True):
        checks = list(checks)
        if normal:
            checks += [check(['meaning_mode'], 'longitudinal_measurement_comparison'), check(['converted_to_base'], False),
                       check(['clinical_assertions_added'], []), check(['clinical_confirmation'], 'not_evaluated'),
                       check(['review_verification'], 'structural_only'), check(['uncertainty_propagated'], False),
                       check(['time_correlation_assumed'], False), check(['clinical_significance'], 'not_evaluated'),
                       check(['certificate', 'status'], 'not_certified'), check(['certificate', 'evidence_level'], 'known_policy_change'),
                       check(['certificate', 'scope'], None)]
        data = {'schema_version': 'p1-fixture-draft-1', 'fixture_version': 1, 'fixture_id': name, 'condition': name[:3], 'fictional': True,
                'review_state': 'author_draft', 'request': deepcopy(req), 'expected': {'comparison': 'required_paths', 'checks': checks}}
        raw = (json.dumps(data, ensure_ascii=False, indent=2)+'\n').encode()
        filename = name.lower()+'.json'
        (DIRECTORY/filename).write_bytes(raw)
        entries.append({'fixture_id': name, 'condition': name[:3], 'path': filename, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})

    def good(name, req, rows, steps, ok=True):
        checks = [check(['status'], 'ok'), check(['steps_used'], steps), check(['incomplete'], []), *rows]
        emit(name, req, checks)

    def bad(name, req, code, status='invalid_input'):
        emit(name, req, [check(['status'], status), check(['reason_codes'], [code])], False)

    twenty, thirty, ten, forty = domain((20, 1)), domain((30, 1)), domain((10, 1)), domain((40, 1))
    # 関係（X1・X9・W2・W7）
    good('L01', request(), computed(['equal'], 27, start=twenty, end=twenty), 47)
    for name, magnitude, shape in [('L02', q.interval(1, 2), domain((10, 1), (20, 1))), ('L03', q.interval(1, 2, True, False), domain((10, 1), (20, 1), True, False))]:
        good(name, request(pair(magnitude=magnitude)), computed(['less', 'equal', 'greater'], 27, start=shape, end=shape), 47)
    for name, values, relation, start, end in [
            ('L04', (None, q.point(3)), ['less'], twenty, thirty), ('L05', (None, q.point(1)), ['greater'], twenty, ten),
            ('L06', (None, q.point(2)), ['equal'], twenty, twenty),
            ('L07', (q.interval(1, 2), q.interval(2, 3)), ['less', 'equal'], domain((10, 1), (20, 1)), domain((20, 1), (30, 1))),
            ('L08', (q.interval(1, 2, True, False), q.interval(2, 3, False, True)), ['less'], domain((10, 1), (20, 1), True, False), domain((20, 1), (30, 1), False, True)),
            ('L09', (q.point(3, 2), q.interval(1, 2)), ['less', 'equal', 'greater'], domain((15, 1)), domain((10, 1), (20, 1))),
            ('L10', (q.point(1, 2), q.interval(1, 2)), ['less'], domain((5, 1)), domain((10, 1), (20, 1))),
            ('L11', (q.point(-3, 2), q.point(-2)), ['greater'], domain((-15, 1)), domain((-20, 1)))]:
        plan = chain()
        for index, magnitude in enumerate(values):
            if magnitude is not None:
                quantity(plan, index, magnitude)
        good(name, request(plan), computed(relation, 34, start=start, end=end, selected=('A', 'B')), 54)
    good('L12', request(pair(targets=('u_base', 'u_ten'))), computed(['equal'], 27, start=twenty, end=domain((2, 1))), 47)
    good('L13', request(pair(targets=('u_base', 'u_half'))), computed(['equal'], 27, start=twenty, end=domain((40, 1))), 47)
    # 比較可能性（X2・W4）
    def context(name, change, reasons, differences):
        plan = chain()
        change(plan['source']['records'][1])
        good(name, request(m.seal(plan)), not_comparable(reasons, differences), 54)
    new_method = {'kind': 'known', 'ref': 'fiction:method:m', 'version': '2'}
    context('L20', lambda r: r.update(method=new_method), ['different_method'], [difference('method', METHOD, new_method)])
    other_method = {'kind': 'known', 'ref': 'fiction:method:new', 'version': '1'}
    context('L21', lambda r: r.update(method=other_method), ['different_method'], [difference('method', METHOD, other_method)])
    other_specimen = {'kind': 'known', 'ref': 'fiction:specimen:new', 'version': '1'}
    context('L22', lambda r: r.update(specimen=other_specimen), ['different_specimen'], [difference('specimen', SPECIMEN, other_specimen)])
    new_specimen = {'kind': 'known', 'ref': 'fiction:specimen:s', 'version': '2'}
    context('L23', lambda r: r.update(specimen=new_specimen), ['different_specimen'], [difference('specimen', SPECIMEN, new_specimen)])
    context('L24', lambda r: r.update(property_ref=OTHER_PROPERTY), ['different_property'], [difference('property_ref', PROPERTY, OTHER_PROPERTY)])
    context('L25', lambda r: r.update(method=new_method, specimen=other_specimen, property_ref=OTHER_PROPERTY),
            ['different_method', 'different_property', 'different_specimen'],
            [difference('method', METHOD, new_method), difference('property_ref', PROPERTY, OTHER_PROPERTY), difference('specimen', SPECIMEN, other_specimen)])
    plan = chain()
    plan['source']['records'][1]['origin'] = {'kind': 'judgment', 'ref': 'fiction:measurement:origin:judged'}
    good('L26', request(m.seal(plan)), computed(['less'], 34, start=twenty, end=thirty, selected=('A', 'B')), 54)
    plan = chain(times=(3, 7))
    plan['source']['records'][1]['method'] = new_method
    good('L27', request(m.seal(plan)), computed(['equal'], 34, start=twenty, end=twenty, selected=('A', 'A')), 54)
    plan = chain(times=(5, 6))
    plan['source']['records'][1]['method'] = new_method
    good('L28', request(m.seal(plan)), not_comparable(['different_method'], [difference('method', new_method, METHOD)]), 54)
    # 端点が止まる場合（X3・W5）
    good('L30', request(pair(times=(3, 11))), unassessed(['no_adopted_measurement'], ends=('computed', 'unassessed')), 47)
    good('L31', request(pair(times=(11, 12))), unassessed(['no_adopted_measurement'], ends=('unassessed', 'unassessed')), 47)
    plan = m.request([m.wrapper(), m.wrapper('QD', q.point(5))], [m.record(), m.record('D', 'S', 'QD')], [m.review(), m.review('D')],
                     queries=[m.convert(ident='a', at=3), m.convert(ident='b', at=11)])
    plan['source']['records'][1]['validity'] = m.span(1, 4)
    good('L32', request(m.seal(plan)), unassessed(['no_adopted_measurement', 'unresolved_measurement_conflict'], ends=('unassessed', 'unassessed')), 52)
    unknown = m.record('U', rec=4)
    unknown['validity'] = {'kind': 'unknown'}
    plan = m.request(records=[m.record(), unknown], reviews=[m.review(), m.review('U', 5)], queries=[m.convert(ident='a', at=3), m.convert(ident='b', at=5)])
    good('L33', request(plan), unassessed(['validity_unknown'], ends=('unassessed', 'unassessed')), 51)
    plan = pair()
    plan['source']['records'][0]['required_capabilities'].append('future:capability')
    good('L34', request(m.seal(plan)), unassessed(['unknown_capability'], ends=('unassessed', 'unassessed')), 47)
    good('L35', request(comparisons=[comparison(caps=[PROFILE, 'future:capability'])]), unassessed(['unknown_capability'], endpoints=False), 47)
    good('L36', request(comparisons=[comparison('c1', caps=[PROFILE, 'future:capability']), comparison('c2')]),
         unassessed(['unknown_capability'], endpoints=False) + computed(['equal'], 27, index=1, start=twenty, end=twenty), 65)
    good('L37', request(pair(targets=('u_base', 'v_base'))), unassessed(['incompatible_dimension'], ends=('computed', 'not_comparable')), 47)
    plan = chain()
    plan['source']['records'][1]['certainty'] = 'suspected'
    good('L38', request(m.seal(plan)), computed(['equal'], 32, start=twenty, end=twenty) + [check(['results', 0, 'endpoints', 'to', 'diagnostics', 'pending_records'], ['B'])], 52)
    # 参照時点・再現（C・G）
    plan = pair()
    plan['source']['records'].append(m.record('F', rec=12))
    plan['source']['reviews'].append(m.review('F', 13))
    good('L40', request(m.seal(plan)), computed(['equal'], 29, start=twenty, end=twenty), 49)
    plan = chain()
    plan['views'] = [{'id': 'v6', 'as_of': m.day(6), 'policy_ref': m.POLICY}, {'id': 'v8', 'as_of': m.day(8), 'policy_ref': m.POLICY}]
    good('L41', request(plan, [comparison('c6', 'v6'), comparison('c8', 'v8')]),
         computed(['equal'], 62, 0, twenty, twenty, ('A', 'A')) + computed(['less'], 62, 1, twenty, thirty, ('A', 'B')), 100)
    req = request()
    plan = req['temporal_measurement_plan']
    for key in ('slots', 'quantities', 'records', 'reviews', 'views', 'queries'):
        (plan['source'] if key in plan['source'] else plan)[key].reverse()
    good('L42', req, computed(['equal'], 27, start=twenty, end=twenty), 47)
    good('L43', request(comparisons=[comparison('c1'), comparison('c2')]),
         computed(['equal'], 27, 0, twenty, twenty) + computed(['equal'], 27, 1, twenty, twenty), 65)
    plan = m.chain(3, 9)
    plan['queries'] = [m.convert(ident=name, at=t) for name, t in zip('abcd', (3, 4, 5, 6))]
    good('L44', request(m.seal(plan), [comparison('ab', start='a', end='b'), comparison('bc', start='b', end='c'), comparison('cd', start='c', end='d')]),
         computed(['less'], 71, 0, twenty, thirty, ('A', 'B')) + computed(['less'], 71, 1, thirty, forty, ('B', 'C')) + computed(['greater'], 71, 2, forty, twenty, ('C', 'A')), 127)
    plan = pair()
    plan['source']['records'][0]['origin'] = {'kind': 'ai_candidate', 'ref': 'fiction:ai:r'}
    plan['source']['quantities'][0]['literal']['origin'] = {'kind': 'ai_candidate', 'ref': 'fiction:ai:q'}
    good('L45', request(m.seal(plan)), computed(['equal'], 27, start=twenty, end=twenty) + [
        check(['results', 0, 'endpoints', 'from', 'binding_evidence', 'selected', 0, 'record_origin', 'kind'], 'ai_candidate'),
        check(['results', 0, 'endpoints', 'from', 'binding_evidence', 'selected', 0, 'quantity_origin', 'kind'], 'ai_candidate')], 47)
    # 接続面の閉包（X6・W6）
    big = 2**62
    for name, req in [('L50', request(pair(magnitude=q.point(big)))), ('L53', request(pair(magnitude=q.point(big), targets=('u_ten', 'u_base'))))]:
        emit(name, req, [check(['status'], 'resource_limit'), check(['reason_codes'], ['rational_integer_limit']), check(['steps_used'], 46),
                         *unfinished('rational_integer_limit'),
                         check(['incomplete'], [{'comparison': 'c', 'reason_codes': ['rational_integer_limit']}])])
    good('L51', request(pair(magnitude=q.point(big), targets=('u_ten', 'u_ten'))), computed(['equal'], 27, start=domain((big, 1)), end=domain((big, 1))), 47)
    good('L52', request(pair(magnitude=q.point(big), unit='u_base')), computed(['equal'], 27, start=domain((big, 1)), end=domain((big, 1))), 47)
    # 静的検査
    for key in ('comparisons', 'temporal_measurement_plan', 'consumer', 'budget'):
        req = request()
        del req[key]
        bad('N01-missing-'+key, req, 'missing_field')
    req = request()
    req['temporal_measurement_plan'] = None
    bad('N01-null', req, 'expected_object')
    req = request()
    req['artifact'] = {}
    bad('N01-extra-request', req, 'unknown_field')
    req = request()
    req['comparisons'][0]['extra'] = 1
    bad('N01-extra-comparison', req, 'unknown_field')
    for field in ('child_result', 'certificate'):
        req = request()
        req[field] = {}
        bad('N09-'+field, req, 'unknown_field')
    req = request()
    req['temporal_measurement_plan']['budget'] = {'max_steps': 100000}
    bad('N09-budget', req, 'unknown_field')
    req = request()
    req['comparisons'] *= 2
    bad('N01-duplicate', req, 'duplicate_identifier')
    bad('N01-empty', request(comparisons=[]), 'empty_collection')
    bad('N01-count', request(comparisons=[comparison(str(i)) for i in range(65)]), 'item_limit', 'resource_limit')
    for key in ('view_ref', 'from_query_ref', 'to_query_ref'):
        req = request()
        req['comparisons'][0][key] = 'absent'
        bad('N02-'+key, req, 'unresolved_'+key)
    bad('N03-same', request(comparisons=[comparison(start='a', end='a')]), 'invalid_comparison_order')
    bad('N03-reversed', request(comparisons=[comparison(start='b', end='a')]), 'invalid_comparison_order')
    bad('N03-equal-time', request(pair(times=(3, 3))), 'invalid_comparison_order')
    plan = m.request(slots=[{'id': 'S', 'subject_ref': 'u'}, {'id': 'T', 'subject_ref': 'u'}],
                     queries=[m.convert('S', ident='a', at=3), m.convert('T', ident='b', at=5)])
    bad('N04', request(plan), 'unsupported_cross_slot_comparison', 'unsupported_profile')
    bad('N05-policy', request(comparisons=[comparison(policy='fiction:same-variable-within-record@1')]), 'unsupported_comparison_policy', 'unsupported_profile')
    bad('N05-type', request(comparisons=[comparison(policy=5)]), 'expected_nonempty_string')
    bad('N06-missing', request(comparisons=[comparison(caps=['future'])]), 'missing_comparison_capability')
    req = request()
    req['comparisons'][0]['required_capabilities'] = 'x'
    bad('N06-type', req, 'expected_array')
    for field in request()['consumer']:
        if field == 'operations':
            continue
        req = request()
        req['consumer'][field] = '0'*64 if field.endswith('sha256') else 'future'
        code = ('profile_spec_mismatch' if field == 'profile_spec_sha256' else 'temporal_measurement_profile_mismatch' if field.startswith('temporal_measurement')
                else 'quantity_profile_mismatch' if field.startswith('quantity') else 'unsupported_profile')
        bad('N07-'+field, req, code, 'unsupported_profile')
    req = request()
    req['consumer']['profile_spec_sha256'] = 'x'
    bad('N07-format', req, 'invalid_sha256')
    for name, change, code in [('schema', lambda r: r['temporal_measurement_plan'].update(schema_version='p2-measurement-request-draft-1'), 'unsupported_temporal_measurement_schema'),
                               ('policy', lambda r: r['temporal_measurement_plan']['views'][0].update(policy_ref='future'), 'unsupported_policy'),
                               ('compare', lambda r: r['temporal_measurement_plan']['queries'][0].update(kind='compare'), 'unsupported_query_kind')]:
        req = request()
        change(req)
        bad('N08-'+name, req, code, 'unsupported_profile')
    for key in ('quantity', 'validity', 'review'):
        req = request()
        source = req['temporal_measurement_plan']['source']
        if key == 'quantity':
            source['quantities'][0]['literal']['magnitude'] = q.point(8)
            code = 'quantity_reference_hash_mismatch'
        elif key == 'validity':
            source['records'][0]['validity'] = m.span(1, 9)
            code = 'review_record_hash_mismatch'
        else:
            source['records'][0]['recorded_at'] = m.day(12)
            seal(req)
            code = 'review_precedes_record'
        bad('N10-'+key, req, code)
    for name, value in [('negative', -1), ('bool', True), ('limit', 100001)]:
        bad('N11-budget-'+name, request(budget=value), 'step_budget_limit' if name == 'limit' else 'invalid_step_budget', 'resource_limit' if name == 'limit' else 'invalid_input')
    # 資源
    def sweep(prefix, req, rows, total, thresholds, cost):
        for budget in thresholds:
            copy = deepcopy(req)
            copy['budget']['max_steps'] = budget
            checks = [check(['status'], 'ok' if budget >= total else 'resource_limit'), check(['steps_used'], min(budget, total))]
            paid = 1 + cost
            unfinished_ids = []
            for index, (kind, args) in enumerate(rows):
                paid += 18
                if budget >= paid:
                    checks += kind(index=index, **args)
                else:
                    checks += unfinished(index=index)
                    unfinished_ids.append(sorted(c['id'] for c in req['comparisons'])[index])
            incomplete = [{'comparison': ident, 'reason_codes': ['step_limit']} for ident in unfinished_ids]
            if budget == total-1:
                incomplete.append({'stage': 'completion', 'reason_codes': ['step_limit']})
            checks.append(check(['incomplete'], incomplete))
            emit(prefix+'-'+str(budget), copy, checks)
    relation = lambda **a: computed(**a)
    sweep('B01', request(), [(relation, dict(relation=['equal'], cost=27, start=twenty, end=twenty))], 47, [0, 1, 27, 28, 45, 46, 47, 48], 27)
    sweep('B02', request(comparisons=[comparison('c1'), comparison('c2')]),
          [(relation, dict(relation=['equal'], cost=27, start=twenty, end=twenty))]*2, 65, [27, 28, 45, 46, 63, 64, 65], 27)
    sweep('B03', request(chain()), [(relation, dict(relation=['less'], cost=34, start=twenty, end=thirty, selected=('A', 'B')))], 54, [34, 35, 52, 53, 54], 34)
    req = request(pair(times=(3, 11)))
    req['budget']['max_steps'] = 47
    emit('B04-stop', req, [check(['status'], 'ok'), check(['steps_used'], 47), *unassessed(['no_adopted_measurement'], ends=('computed', 'unassessed'))])
    big_plan = m.request([m.wrapper(magnitude=q.point(121, 100), unit='u_base')], [m.record('R'+str(i), rec=2) for i in range(20)], [m.review('R'+str(i), 3) for i in range(20)])
    big_plan['views'] = [{'id': 'v'+str(i), 'as_of': m.day(8), 'policy_ref': m.POLICY} for i in range(64)]
    big_plan['queries'] = [m.convert(ident='q'+str(i), at=3+i % 2) for i in range(64)]
    emit('B05-plan', request(big_plan, [comparison('c', 'v0', 'q0', 'q1')]),
         [check(['status'], 'resource_limit'), check(['steps_used'], 100000), *unfinished(), check(['certificate', 'status'], 'not_certified')])
    manifest = {'schema_version': 'p2-fixture-manifest-draft-1', 'suite': 'p2-longitudinal', 'review_state': 'author_draft', 'independent_review': False,
                'evaluation_frozen': False, 'conditions': {'L': len({e['condition'] for e in entries if e['condition'][0] == 'L'}),
                                                              'N': len({e['condition'] for e in entries if e['condition'][0] == 'N'}),
                                                              'B': len({e['condition'] for e in entries if e['condition'][0] == 'B'})}, 'files': entries}
    (DIRECTORY/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'files': len(entries), 'checks': sum(len(json.loads((DIRECTORY/e['path']).read_text())['expected']['checks']) for e in entries)}))


if __name__ == '__main__':
    main()
