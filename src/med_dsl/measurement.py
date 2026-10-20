"""内容を特定した確認と測定版の選択を、数量計算へ結ぶR5診断。"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from .model import Budget, Problem
from .quantity import (QUANTITY_PROFILE, SPEC_SHA256 as QUANTITY_SPEC_SHA256,
                       _spec as quantity_spec, _validate as validate_quantities, run_quantities)
from .validation import check_json, digest, fields, indexed, string, strings, timestamp

MEASUREMENT_PROFILE = 'p2-measurement-binding-draft-1'
SPEC_SHA256 = '7c2f731f2e24423f552bef8fb61efd5bdb74fac326279c7d7800639bb301a454'
OPERATION = 'evaluate_measurements'
POLICY = 'fiction:reviewed-measurement-record@1'
ANSWER_KIND = 'measurement_literal_projection'


def _unsupported(code, path):
    raise Problem(code, path, 'unsupported_profile')


def _sha(value, path):
    if type(value) is not str or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise Problem('invalid_sha256', path)


def _spec():
    try:
        raw = Path(__file__).with_name('measurement_spec.json').read_bytes()
    except OSError as error:
        raise Problem('native_spec_unavailable', 'native_spec') from error
    if hashlib.sha256(raw).hexdigest() != SPEC_SHA256:
        raise Problem('native_spec_mismatch', 'native_spec')
    return json.loads(raw)


def _record_hash(source, record):
    return digest({'binding_profile': MEASUREMENT_PROFILE, 'binding_spec_sha256': SPEC_SHA256,
                   'source_ref': source['ref'], 'record': record})


def _snapshot_hash(source):
    normalized = deepcopy(source)
    for key in ('slots', 'quantities', 'records', 'reviews'):
        normalized[key].sort(key=lambda item: item['ref' if key == 'quantities' else 'id'])
    return digest(normalized)


def _context(value, path, temporal=False):
    if type(value) is not dict or 'kind' not in value:
        fields(value, ('kind',), path=path)
    string(value['kind'], path + '.kind')
    if value['kind'] in ('unknown', 'unspecified'):
        fields(value, ('kind',), path=path)
    elif value['kind'] == ('instant' if temporal else 'known'):
        if temporal:
            fields(value, ('kind', 'at'), path=path)
            timestamp(value['at'], path + '.at')
        else:
            fields(value, ('kind', 'ref', 'version'), path=path)
            string(value['ref'], path + '.ref')
            string(value['version'], path + '.version')
    else:
        _unsupported('unsupported_context', path)


def _quantity_request(quantities, queries, reserve):
    return {'schema_version': 'p2-quantity-request-draft-1', 'operation': 'evaluate_quantities',
            'consumer': {'profile': QUANTITY_PROFILE, 'profile_spec_sha256': QUANTITY_SPEC_SHA256,
                         'operations': ['evaluate_quantities']},
            'quantities': quantities, 'queries': queries, 'budget': {'max_steps': reserve}}


def _validate(request):
    fields(request, ('schema_version', 'operation', 'consumer', 'source', 'views', 'queries', 'budget'))
    if request['operation'] != OPERATION:
        _unsupported('unsupported_operation', 'operation')
    spec = _spec()
    qspec = quantity_spec()
    if spec['quantity_profile'] != QUANTITY_PROFILE or spec['quantity_spec_sha256'] != QUANTITY_SPEC_SHA256:
        _unsupported('quantity_profile_mismatch', 'native_spec.quantity_dependency')
    consumer = request['consumer']
    fields(consumer, ('profile', 'profile_spec_sha256', 'operations', 'quantity_profile', 'quantity_profile_spec_sha256'), path='consumer')
    if consumer['profile'] != MEASUREMENT_PROFILE:
        _unsupported('unsupported_profile', 'consumer.profile')
    _sha(consumer['profile_spec_sha256'], 'consumer.profile_spec_sha256')
    if consumer['profile_spec_sha256'] != SPEC_SHA256:
        _unsupported('profile_spec_mismatch', 'consumer.profile_spec_sha256')
    _sha(consumer['quantity_profile_spec_sha256'], 'consumer.quantity_profile_spec_sha256')
    if consumer['quantity_profile'] != QUANTITY_PROFILE or consumer['quantity_profile_spec_sha256'] != QUANTITY_SPEC_SHA256:
        _unsupported('quantity_profile_mismatch', 'consumer.quantity_profile')
    strings(consumer['operations'], 64, 'consumer.operations')
    if consumer['operations'] != [OPERATION]:
        _unsupported('unsupported_operation', 'consumer.operations')
    fields(request['budget'], ('max_steps',), path='budget')
    maximum = request['budget']['max_steps']
    if type(maximum) is not int or maximum < 0:
        raise Problem('invalid_step_budget', 'budget.max_steps')
    if maximum > 100000:
        raise Problem('step_budget_limit', 'budget.max_steps', 'resource_limit')
    source = request['source']
    fields(source, ('schema_version', 'ref', 'slots', 'quantities', 'records', 'reviews'), path='source')
    if source['schema_version'] != 'p2-measurement-ledger-draft-1':
        _unsupported('unsupported_measurement_ledger', 'source.schema_version')
    string(source['ref'], 'source.ref')
    slots = indexed(source['slots'], 'id', 64, 'slots')
    quantities = indexed(source['quantities'], 'ref', 64, 'quantities')
    records = indexed(source['records'], 'id', 64, 'records')
    reviews = indexed(source['reviews'], 'id', 128, 'reviews')
    views = indexed(request['views'], 'id', 64, 'views')
    queries = indexed(request['queries'], 'id', 64, 'queries')
    if not slots or not views or not queries:
        raise Problem('empty_collection', 'slots/views/queries')
    for slot in slots.values():
        fields(slot, ('id', 'subject_ref'), path='slot')
        string(slot['subject_ref'], 'slot.subject_ref')
    for q in quantities.values():
        fields(q, ('ref', 'profile', 'profile_spec_sha256', 'literal'), path='quantity_wrapper')
        _sha(q['profile_spec_sha256'], 'quantity_wrapper.profile_spec_sha256')
        if q['profile'] != QUANTITY_PROFILE or q['profile_spec_sha256'] != QUANTITY_SPEC_SHA256:
            _unsupported('quantity_profile_mismatch', 'quantity_wrapper.profile')
        if type(q['literal']) is not dict or q['literal'].get('id') != q['ref']:
            raise Problem('literal_identifier_mismatch', 'quantity_wrapper.literal.id')
    if quantities:
        literals = [quantities[key]['literal'] for key in sorted(quantities)]
        # 型・静的上限だけを検証する。ここで計算や採用をしない。
        validate_quantities(_quantity_request(literals, [{'id': 'validation', 'kind': 'convert',
            'quantity_ref': literals[0]['id'], 'target_unit_ref': literals[0].get('unit_ref')}], 0))
    for record in records.values():
        fields(record, ('id', 'kind', 'slot_ref', 'subject_ref', 'property_ref', 'specimen', 'method', 'effective_at',
                        'quantity_ref', 'certainty', 'recorded_at', 'origin', 'required_capabilities', 'supersedes'), ('change_reason',), 'record')
        string(record['kind'], 'record.kind')
        if record['kind'] != 'measurement':
            _unsupported('unsupported_record_kind', 'record.kind')
        for field in ('slot_ref', 'subject_ref', 'property_ref'):
            string(record[field], 'record.' + field)
        if record['slot_ref'] not in slots:
            raise Problem('unresolved_slot', 'record.slot_ref')
        if record['subject_ref'] != slots[record['slot_ref']]['subject_ref']:
            raise Problem('slot_subject_mismatch', 'record.subject_ref')
        for field in ('method', 'specimen', 'effective_at'):
            _context(record[field], 'record.' + field, field == 'effective_at')
        fields(record['quantity_ref'], ('ref', 'sha256'), path='record.quantity_ref')
        ref = record['quantity_ref']['ref']
        string(ref, 'record.quantity_ref.ref')
        if ref not in quantities:
            raise Problem('unresolved_quantity', 'record.quantity_ref.ref')
        _sha(record['quantity_ref']['sha256'], 'record.quantity_ref.sha256')
        if record['quantity_ref']['sha256'] != digest(quantities[ref]):
            raise Problem('quantity_reference_hash_mismatch', 'record.quantity_ref.sha256')
        prop, kind = record['property_ref'], quantities[ref]['literal']['quantity_kind_ref']
        if prop in spec['properties'] and kind in qspec['quantity_kinds'] and spec['properties'][prop] != kind:
            raise Problem('property_quantity_kind_mismatch', 'record.property_ref')
        if record['certainty'] not in ('confirmed', 'suspected'):
            raise Problem('invalid_certainty', 'record.certainty')
        timestamp(record['recorded_at'], 'record.recorded_at')
        fields(record['origin'], ('kind', 'ref'), path='record.origin')
        if record['origin']['kind'] not in ('observed', 'judgment', 'imported', 'ai_candidate'):
            raise Problem('invalid_origin', 'record.origin.kind')
        string(record['origin']['ref'], 'record.origin.ref')
        strings(record['required_capabilities'], 64, 'record.required_capabilities')
        if MEASUREMENT_PROFILE not in record['required_capabilities']:
            raise Problem('missing_measurement_capability', 'record.required_capabilities')
        strings(record['supersedes'], 64, 'record.supersedes')
        if record['supersedes']:
            string(record.get('change_reason'), 'record.change_reason')
        elif 'change_reason' in record:
            raise Problem('unexpected_change_reason', 'record.change_reason')
    for record in records.values():
        for target in record['supersedes']:
            if target not in records:
                raise Problem('unresolved_revision', 'record.supersedes')
            old = records[target]
            if old['slot_ref'] != record['slot_ref'] or old['recorded_at'] >= record['recorded_at']:
                raise Problem('invalid_revision', 'record.supersedes')
    hashes = {key: _record_hash(source, record) for key, record in records.items()}
    for review in reviews.values():
        fields(review, ('id', 'record_ref', 'record_sha256', 'reviewer_ref', 'reviewer_kind', 'recorded_at', 'outcome'), path='review')
        ref = review['record_ref']
        string(ref, 'review.record_ref')
        if ref not in records:
            raise Problem('unresolved_record', 'review.record_ref')
        _sha(review['record_sha256'], 'review.record_sha256')
        if review['record_sha256'] != hashes[ref]:
            raise Problem('review_record_hash_mismatch', 'review.record_sha256')
        if review['reviewer_kind'] != 'human' or review['outcome'] != 'confirmed':
            raise Problem('invalid_review', 'review')
        string(review['reviewer_ref'], 'review.reviewer_ref')
        timestamp(review['recorded_at'], 'review.recorded_at')
        if review['recorded_at'] < records[ref]['recorded_at']:
            raise Problem('review_precedes_record', 'review.recorded_at')
    for view in views.values():
        fields(view, ('id', 'as_of', 'policy_ref'), path='view')
        timestamp(view['as_of'], 'view.as_of')
        if view['policy_ref'] != POLICY:
            _unsupported('unsupported_policy', 'view.policy_ref')
    for query in queries.values():
        if 'kind' not in query:
            raise Problem('missing_field', 'query.kind')
        string(query['kind'], 'query.kind')
        if query['kind'] == 'convert':
            fields(query, ('id', 'kind', 'slot_ref', 'target_unit_ref'), path='query')
            string(query['target_unit_ref'], 'query.target_unit_ref')
        elif query['kind'] == 'compare':
            fields(query, ('id', 'kind', 'left_slot_ref', 'right_slot_ref', 'comparison_scope'), path='query')
            if query['comparison_scope'] != 'matched_context':
                _unsupported('unsupported_comparison_scope', 'query.comparison_scope')
        else:
            _unsupported('unsupported_query_kind', 'query.kind')
        for ref in _slot_refs(query):
            string(ref, 'query.slot_ref')
            if ref not in slots:
                raise Problem('unresolved_slot', 'query.slot_ref')
    return spec, qspec, slots, quantities, records, reviews, views, queries, hashes


def _slot_refs(query):
    return [query['slot_ref']] if query['kind'] == 'convert' else [query['left_slot_ref'], query['right_slot_ref']]


def _visible(records, reviews, as_of):
    visible = {key: r for key, r in records.items() if r['recorded_at'] <= as_of}
    confirmations = {}
    for review in reviews.values():
        if review['record_ref'] in visible and review['recorded_at'] <= as_of:
            confirmations.setdefault(review['record_ref'], []).append(review['id'])
    eligible = {key for key, r in visible.items() if r['certainty'] == 'confirmed' and key in confirmations}
    return visible, {key: sorted(ids) for key, ids in confirmations.items()}, eligible


def _assess(query, view, visible, eligible, confirmations, quantities, hashes, source_hash, spec, qspec):
    masked = {target for key in eligible for target in visible[key]['supersedes']}
    slots = _slot_refs(query)
    candidates = {s: sorted(key for key in eligible - masked if visible[key]['slot_ref'] == s) for s in sorted(set(slots))}
    diagnostics = {'visible_records': sorted(visible), 'eligible_records': sorted(eligible), 'masked_records': sorted(masked),
                   'pending_records': sorted(set(visible) - eligible), 'candidate_refs': candidates}
    result = {'status': 'unassessed', 'reason_codes': [], 'diagnostics': diagnostics}
    missing, blockers = set(), []
    for key, r in visible.items():
        caps = set(r['required_capabilities']) - {MEASUREMENT_PROFILE}
        caps |= set(quantities[r['quantity_ref']['ref']]['literal']['required_capabilities']) - {QUANTITY_PROFILE}
        if caps:
            missing.update(caps)
            blockers.append(key)
    if missing:
        diagnostics.update(missing_capabilities=sorted(missing), blocking_records=sorted(blockers))
        return {**result, 'reason_codes': ['unknown_capability']}
    reasons = set()
    for refs in candidates.values():
        if len(refs) != 1:
            reasons.add('no_adopted_measurement' if not refs else 'unresolved_measurement_conflict')
    if reasons:
        return {**result, 'reason_codes': sorted(reasons)}
    selected = [visible[candidates[s][0]] for s in slots]
    for record in selected:
        if record['property_ref'] not in spec['properties']:
            reasons.add('unknown_property')
        for field, prefix in [('specimen', 'specimen'), ('method', 'method'), ('effective_at', 'effective_time')]:
            if record[field]['kind'] in ('unknown', 'unspecified'):
                reasons.add(prefix + '_' + record[field]['kind'])
        literal = quantities[record['quantity_ref']['ref']]['literal']
        if literal['quantity_kind_ref'] not in qspec['quantity_kinds']:
            reasons.add('unknown_quantity_kind')
        if literal['unit_ref'] not in qspec['units']:
            reasons.add('unknown_unit')
    if query['kind'] == 'convert' and query['target_unit_ref'] not in qspec['units']:
        reasons.add('unknown_unit')
    if reasons:
        return {**result, 'reason_codes': sorted(reasons)}
    if query['kind'] == 'compare':
        for field, reason in [('subject_ref', 'different_subject'), ('property_ref', 'different_property'),
                              ('specimen', 'different_specimen'), ('method', 'different_method'), ('effective_at', 'different_effective_time')]:
            if selected[0][field] != selected[1][field]:
                reasons.add(reason)
        if reasons:
            return {**result, 'status': 'not_comparable', 'reason_codes': sorted(reasons)}
    unique = {record['id']: record for record in selected}
    ids = {key: 'operand:' + str(i) for i, key in enumerate(sorted(unique))}
    literals, bindings = [], []
    for key in sorted(unique):
        record = unique[key]
        wrapper = quantities[record['quantity_ref']['ref']]
        literals.append({**deepcopy(wrapper['literal']), 'id': ids[key]})
        bindings.append({'slot_ref': record['slot_ref'], 'record_ref': key, 'record_sha256': hashes[key],
                         'quantity_ref': deepcopy(record['quantity_ref']), 'native_quantity_id': ids[key],
                         'review_refs': confirmations[key], 'record_origin': deepcopy(record['origin']),
                         'quantity_origin': deepcopy(wrapper['literal']['origin'])})
    if query['kind'] == 'convert':
        operation = {'id': 'value', 'kind': 'convert', 'quantity_ref': ids[selected[0]['id']], 'target_unit_ref': query['target_unit_ref']}
        reserve = 8
    else:
        operation = {'id': 'value', 'kind': 'compare', 'left_ref': ids[selected[0]['id']], 'right_ref': ids[selected[1]['id']]}
        reserve = 12
    child_request = _quantity_request(literals, [operation], reserve)
    child_input_hash = check_json(child_request)
    child = run_quantities(child_request)
    if child['status'] == 'resource_limit':
        raise Problem(child['reason_codes'][0], 'quantity_child', 'resource_limit')
    value = child['results'][0]
    if value['status'] != 'computed':
        return {**result, 'status': value['status'], 'reason_codes': value['reason_codes']}
    return {**result, 'status': 'computed', 'reason_codes': [],
            **{field: value[field] for field in ('converted_domain', 'relation_set', 'certain_relation')},
            'binding_evidence': {'source_sha256': source_hash, 'profile_spec_sha256': SPEC_SHA256,
                                 'quantity_spec_sha256': QUANTITY_SPEC_SHA256, 'policy_ref': POLICY,
                                 'as_of': view['as_of'], 'query': deepcopy(query), 'selected': bindings},
            'calculation_evidence': {'input_sha256': child_input_hash, 'profile': QUANTITY_PROFILE,
                                     'reserved_steps': reserve, 'steps_used': child['steps_used'], 'evidence': value['calculation_evidence']}}


def run_measurements(request):
    spec, qspec, slots, quantities, records, reviews, views, queries, hashes = _validate(request)
    source_hash = _snapshot_hash(request['source'])
    budget = Budget(request['budget']['max_steps'])
    rows = [{'view': v, 'query': q, 'kind': queries[q]['kind'], 'status': 'unassessed', 'assessment_complete': False,
             'converted_domain': None, 'relation_set': None, 'certain_relation': None, 'binding_evidence': None,
             'calculation_evidence': None, 'diagnostics': None, 'reason_codes': ['step_limit']}
            for v in sorted(views) for q in sorted(queries)]
    result = {'status': 'ok', 'meaning_mode': ANSWER_KIND, 'converted_to_base': False, 'clinical_assertions_added': [],
              'clinical_confirmation': 'not_evaluated', 'uncertainty_propagated': False, 'review_verification': 'structural_only',
              'certificate': {'status': 'not_certified', 'evidence_level': 'known_policy_change',
                              'reason_codes': ['typed_measurement_selection'], 'scope': None},
              'source_sha256': source_hash, 'retained_source': deepcopy(request['source']), 'results': rows, 'reason_codes': []}
    current = None
    try:
        budget.tick()
        for _ in range(len(slots) + len(quantities)):
            budget.tick()
        for view_id in sorted(views):
            current = None
            for _ in range(len(records) + len(reviews)):
                budget.tick()
            visible, confirmations, eligible = _visible(records, reviews, views[view_id]['as_of'])
            for row in (r for r in rows if r['view'] == view_id):
                current = row
                query = queries[row['query']]
                scope = set(_slot_refs(query))
                scoped = {key: r for key, r in visible.items() if r['slot_ref'] in scope}
                scoped_eligible = eligible & set(scoped)
                charge = 2 + len(scoped) + sum(len(scoped[key]['supersedes']) for key in scoped_eligible)
                charge += 8 if query['kind'] == 'convert' else 12
                for _ in range(charge):
                    budget.tick()
                value = _assess(query, views[view_id], scoped, scoped_eligible, confirmations, quantities, hashes, source_hash, spec, qspec)
                row.update(value, assessment_complete=True)
    except Problem as problem:
        if problem.status != 'resource_limit':
            raise
        result.update(status='resource_limit', reason_codes=[problem.code])
        if current is not None:
            current['reason_codes'] = [problem.code]
        if problem.code != 'step_limit':
            for pending in rows:
                if not pending['assessment_complete'] and pending is not current:
                    pending['reason_codes'] = ['not_started_after_resource_limit']
    result['steps_used'] = budget.used
    result['incomplete'] = [{'view': row['view'], 'query': row['query'], 'reason_codes': row['reason_codes']}
                            for row in rows if not row['assessment_complete']]
    return result
