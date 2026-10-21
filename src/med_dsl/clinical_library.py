"""R5：医療者の操作（記録・確認・訂正）から台帳を組み立て、出力先の要求（宣言）を満たせるかを診断する薄い臨床ライブラリ。"""
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
from pathlib import Path

from .model import Budget, Problem
from .quantity import _bounded, _encode, run_quantities
from .temporal_measurement import (TEMPORAL_MEASUREMENT_PROFILE, SPEC_SHA256 as TEMPORAL_MEASUREMENT_SPEC_SHA256, POLICY as TEMPORAL_MEASUREMENT_POLICY,
                                   QUANTITY_PROFILE, QUANTITY_SPEC_SHA256, _record_hash, _validate as validate_temporal_measurements,
                                   _visible as visible_temporal_measurements, run_temporal_measurements)
from .validation import check_json, digest, fields, indexed, string, strings, timestamp, values

LIBRARY_PROFILE = 'p2-clinical-library-draft-1'
SPEC_SHA256 = '58abe63fca0b964120e88fd3773ef2226c6d516e7d7eed745fce126e9bcfd9c2'
OPERATION = 'run_clinical_library'
ANSWER_KIND = 'clinical_library_projection'
VALUE_FIELDS = ('selection', 'elements', 'requests', 'output', 'flows')
POLICY = 'fiction:decimal-half-even@1'
PROBE_UNIT = 'u_base'
ORIGIN_OF_QUANTITY = {'observed': 'literal', 'judgment': 'literal', 'imported': 'imported_literal', 'ai_candidate': 'ai_candidate'}
SELECTION_STOPS = ('validity_unknown', 'validity_unspecified', 'no_adopted_measurement', 'unresolved_measurement_conflict')
CONTEXT_FIELDS = ('method', 'property', 'specimen')
OWN_FEE, CONVERT_RESERVE, COMPARE_RESERVE = 6, 8, 12
RECORD_FIELDS = ('id', 'kind', 'slot_ref', 'property_ref', 'specimen', 'method', 'validity', 'value', 'certainty', 'recorded_at', 'origin', 'observer')
CORRECT_FIELDS = RECORD_FIELDS + ('corrects', 'reason')
CONFIRM_FIELDS = ('id', 'kind', 'record_ref', 'reviewer_ref', 'recorded_at')


def _unsupported(code, path):
    raise Problem(code, path, 'unsupported_profile')


def _invalid(code, path):
    raise Problem(code, path)


def _spec():
    try:
        raw = Path(__file__).with_name('clinical_library_spec.json').read_bytes()
    except OSError as error:
        raise Problem('native_spec_unavailable', 'native_spec') from error
    if hashlib.sha256(raw).hexdigest() != SPEC_SHA256:
        raise Problem('native_spec_mismatch', 'native_spec')
    spec = json.loads(raw)
    if spec['temporal_measurement_profile'] != TEMPORAL_MEASUREMENT_PROFILE or spec['temporal_measurement_spec_sha256'] != TEMPORAL_MEASUREMENT_SPEC_SHA256:
        _unsupported('temporal_measurement_profile_mismatch', 'native_spec')
    if spec['quantity_profile'] != QUANTITY_PROFILE or spec['quantity_spec_sha256'] != QUANTITY_SPEC_SHA256:
        _unsupported('quantity_profile_mismatch', 'native_spec')
    return spec


def _consumer(consumer):
    fields(consumer, ('profile', 'profile_spec_sha256', 'operations', 'temporal_measurement_profile', 'temporal_measurement_profile_spec_sha256',
                      'quantity_profile', 'quantity_profile_spec_sha256'), path='consumer')
    for key, expected, code in [('profile', LIBRARY_PROFILE, 'unsupported_profile'),
                                ('profile_spec_sha256', SPEC_SHA256, 'profile_spec_mismatch'),
                                ('temporal_measurement_profile', TEMPORAL_MEASUREMENT_PROFILE, 'temporal_measurement_profile_mismatch'),
                                ('temporal_measurement_profile_spec_sha256', TEMPORAL_MEASUREMENT_SPEC_SHA256, 'temporal_measurement_profile_mismatch'),
                                ('quantity_profile', QUANTITY_PROFILE, 'quantity_profile_mismatch'),
                                ('quantity_profile_spec_sha256', QUANTITY_SPEC_SHA256, 'quantity_profile_mismatch')]:
        string(consumer[key], 'consumer.' + key)
        if key.endswith('sha256') and (len(consumer[key]) != 64 or any(c not in '0123456789abcdef' for c in consumer[key])):
            raise Problem('invalid_sha256', 'consumer.' + key)
        if consumer[key] != expected:
            _unsupported(code, 'consumer.' + key)
    strings(consumer['operations'], 64, 'consumer.operations')
    if consumer['operations'] != [OPERATION]:
        _unsupported('unsupported_operation', 'consumer.operations')


def _operations(library):
    slots = indexed(library['slots'], 'id', 64, 'slots')
    if not slots:
        raise Problem('empty_collection', 'slots')
    for slot in slots.values():
        fields(slot, ('id', 'subject_ref'), path='slot')
        string(slot['subject_ref'], 'slot.subject_ref')
    operations = indexed(library['operations'], 'id', 256, 'operations')
    for op in operations.values():
        if 'kind' not in op:
            raise Problem('missing_field', 'operation.kind')
        string(op['kind'], 'operation.kind')
        if op['kind'] not in ('record', 'correct', 'confirm'):
            _unsupported('unsupported_operation_kind', 'operation.kind')
    records = {key for key, op in operations.items() if op['kind'] != 'confirm'}
    for op in operations.values():
        if op['kind'] == 'confirm':
            fields(op, CONFIRM_FIELDS, path='operation')
            string(op['reviewer_ref'], 'operation.reviewer_ref')
            string(op['record_ref'], 'operation.record_ref')
            if op['record_ref'] not in records:
                raise Problem('unresolved_record', 'operation.record_ref')
            continue
        fields(op, CORRECT_FIELDS if op['kind'] == 'correct' else RECORD_FIELDS, ('capabilities',), 'operation')
        for key in ('slot_ref', 'property_ref'):
            string(op[key], 'operation.' + key)
        if op['slot_ref'] not in slots:
            raise Problem('unresolved_slot', 'operation.slot_ref')
        fields(op['value'], ('magnitude', 'unit_ref', 'quantity_kind_ref'), path='operation.value')
        string(op['value']['unit_ref'], 'operation.value.unit_ref')
        string(op['value']['quantity_kind_ref'], 'operation.value.quantity_kind_ref')
        fields(op['origin'], ('kind', 'ref'), path='operation.origin')
        string(op['origin']['ref'], 'operation.origin.ref')
        string(op['origin']['kind'], 'operation.origin.kind')
        if op['origin']['kind'] not in ORIGIN_OF_QUANTITY:
            raise Problem('invalid_origin', 'operation.origin.kind')
        if 'capabilities' in op:
            strings(op['capabilities'], 64, 'operation.capabilities')
        if op['kind'] == 'correct':
            strings(op['corrects'], 64, 'operation.corrects')
            if not op['corrects']:
                raise Problem('empty_collection', 'operation.corrects')
            if any(target not in records for target in op['corrects']):
                raise Problem('unresolved_record', 'operation.corrects')
            string(op['reason'], 'operation.reason')
    return slots, operations


def _ledger(library, slots, operations):
    """操作から P2-i の台帳（slots・quantities・records・reviews）を組み立てる。内容 hash はここで計算する。"""
    quantities, records, reviews = [], [], []
    for op in operations.values():
        if op['kind'] == 'confirm':
            continue
        ref = 'quantity:' + op['id']
        value = op['value']
        wrapper = {'ref': ref, 'profile': QUANTITY_PROFILE, 'profile_spec_sha256': QUANTITY_SPEC_SHA256,
                   'literal': {'id': ref, 'quantity_kind_ref': value['quantity_kind_ref'], 'unit_ref': value['unit_ref'],
                               'magnitude': deepcopy(value['magnitude']), 'uncertainty': {'kind': 'not_evaluated'},
                               'origin': {'kind': ORIGIN_OF_QUANTITY[op['origin']['kind']], 'ref': op['origin']['ref']},
                               'required_capabilities': [QUANTITY_PROFILE]}}
        quantities.append(wrapper)
        record = {'id': op['id'], 'kind': 'period_quantity', 'slot_ref': op['slot_ref'], 'subject_ref': slots[op['slot_ref']]['subject_ref'],
                  'property_ref': op['property_ref'], 'specimen': deepcopy(op['specimen']), 'method': deepcopy(op['method']),
                  'validity': deepcopy(op['validity']), 'quantity_ref': {'ref': ref, 'sha256': digest(wrapper)},
                  'certainty': op['certainty'], 'recorded_at': op['recorded_at'], 'origin': deepcopy(op['origin']),
                  'required_capabilities': [TEMPORAL_MEASUREMENT_PROFILE, *op.get('capabilities', [])],
                  'revises': list(op['corrects']) if op['kind'] == 'correct' else []}
        record['observer'] = deepcopy(op['observer'])
        if op['kind'] == 'correct':
            record['change_reason'] = op['reason']
        records.append(record)
    source = {'schema_version': 'p2-temporal-measurement-ledger-draft-1', 'ref': library['ref'], 'slots': [deepcopy(s) for s in slots.values()],
              'quantities': quantities, 'records': records, 'reviews': reviews}
    by_id = {record['id']: record for record in records}
    for op in operations.values():
        if op['kind'] == 'confirm':
            reviews.append({'id': op['id'], 'record_ref': op['record_ref'], 'record_sha256': _record_hash(source, by_id[op['record_ref']]),
                            'reviewer_ref': op['reviewer_ref'], 'reviewer_kind': 'human', 'recorded_at': op['recorded_at'], 'outcome': 'confirmed'})
    return source


def _profile(profile, spec):
    fields(profile, ('id', 'version', 'output', 'elements'), path='destination')
    string(profile['id'], 'destination.id')
    string(profile['version'], 'destination.version')
    fields(profile['output'], ('kind',), path='destination.output')
    kind = profile['output']['kind']
    string(kind, 'destination.output.kind')
    rules = spec['requirements']['output_kinds']
    if kind not in rules:
        _unsupported('unsupported_output_kind', 'destination.output.kind')
    elements = values(profile['elements'], 16, 'destination.elements')
    counts = {'value': 0, 'context': 0, 'trend': 0}
    for element in elements:
        if type(element) is not dict or 'element' not in element:
            fields(element, ('element',), path='element')
        string(element['element'], 'element.element')
        if element['element'] not in counts:
            _unsupported('unsupported_requirement_element', 'element.element')
        counts[element['element']] += 1
        if element['element'] == 'value':
            fields(element, ('element', 'form', 'unit_ref') + (('decimal_places',) if rules[kind].get('decimal_places') else ()), path='element')
            string(element['form'], 'element.form')
            if element['form'] not in ('single_point', 'domain'):
                _unsupported('unsupported_value_form', 'element.form')
            string(element['unit_ref'], 'element.unit_ref')
            if 'decimal_places' in element:
                places = element['decimal_places']
                if type(places) is not int or places < 0:
                    raise Problem('invalid_decimal_places', 'element.decimal_places')
                if places > spec['requirements']['max_decimal_places']:
                    _unsupported('unsupported_decimal_places', 'element.decimal_places')
        elif element['element'] == 'context':
            fields(element, ('element', 'field', 'requires'), path='element')
            string(element['field'], 'element.field')
            if element['field'] not in spec['requirements']['context_fields']:
                _unsupported('unsupported_context_field', 'element.field')
            string(element['requires'], 'element.requires')
            if element['requires'] not in spec['requirements']['context_requires']:
                _unsupported('unsupported_context_requirement', 'element.requires')
        else:
            fields(element, ('element', 'context_match'), path='element')
            strings(element['context_match'], 8, 'element.context_match')
            if not element['context_match']:
                raise Problem('invalid_destination_profile', 'element.context_match')
            if any(field not in spec['requirements']['context_fields'] for field in element['context_match']):
                _unsupported('unsupported_context_field', 'element.context_match')
    allowed = set(rules[kind]['elements'])
    if any(counts[name] and name not in allowed for name in counts):
        raise Problem('invalid_destination_profile', 'destination.elements')
    if kind == 'trend':
        if counts['trend'] != 1:
            raise Problem('invalid_destination_profile', 'destination.elements')
    else:
        value = [e for e in elements if e['element'] == 'value']
        if len(value) != 1 or (kind == 'line' and value[0]['form'] != 'single_point'):
            raise Problem('invalid_destination_profile', 'destination.elements')


def _validate(request):
    fields(request, ('schema_version', 'operation', 'consumer', 'library', 'destinations', 'views', 'queries', 'budget'))
    spec = _spec()
    if request['operation'] != OPERATION:
        _unsupported('unsupported_operation', 'operation')
    _consumer(request['consumer'])
    fields(request['budget'], ('max_steps',), path='budget')
    maximum = request['budget']['max_steps']
    if type(maximum) is not int or maximum < 0:
        raise Problem('invalid_step_budget', 'budget.max_steps')
    if maximum > 100000:
        raise Problem('step_budget_limit', 'budget.max_steps', 'resource_limit')
    library = request['library']
    fields(library, ('ref', 'slots', 'operations'), path='library')
    string(library['ref'], 'library.ref')
    slots, operations = _operations(library)
    destinations = {}
    for profile in values(request['destinations'], 16, 'destinations'):
        _profile(profile, spec)
        if (profile['id'], profile['version']) in destinations:
            raise Problem('duplicate_destination', 'destinations')
        destinations[(profile['id'], profile['version'])] = profile
    if not destinations:
        raise Problem('empty_collection', 'destinations')
    views = indexed(request['views'], 'id', 64, 'views')
    if not views:
        raise Problem('empty_collection', 'views')
    for view in views.values():
        fields(view, ('id', 'as_of'), path='view')
        timestamp(view['as_of'], 'view.as_of')
    queries = indexed(request['queries'], 'id', 32, 'queries')
    if not queries:
        raise Problem('empty_collection', 'queries')
    plan_queries = []
    for query in queries.values():
        fields(query, ('id', 'view_ref', 'slot_ref', 'destination_ref'), ('target_at', 'from_at', 'to_at'), 'query')
        for key, table, code in [('view_ref', views, 'unresolved_view_ref'), ('slot_ref', slots, 'unresolved_slot')]:
            string(query[key], 'query.' + key)
            if query[key] not in table:
                raise Problem(code, 'query.' + key)
        fields(query['destination_ref'], ('id', 'version'), path='query.destination_ref')
        string(query['destination_ref']['id'], 'query.destination_ref.id')
        string(query['destination_ref']['version'], 'query.destination_ref.version')
        profile = destinations.get((query['destination_ref']['id'], query['destination_ref']['version']))
        if profile is None:
            raise Problem('unresolved_destination', 'query.destination_ref')
        if profile['output']['kind'] == 'trend':
            if 'target_at' in query:
                raise Problem('unknown_field', 'query')
            if 'from_at' not in query or 'to_at' not in query:
                raise Problem('missing_field', 'query')
            timestamp(query['from_at'], 'query.from_at')
            timestamp(query['to_at'], 'query.to_at')
            if not query['from_at'] < query['to_at']:
                raise Problem('invalid_trend_order', 'query')
            times = [('from', query['from_at']), ('to', query['to_at'])]
        else:
            if 'from_at' in query or 'to_at' in query:
                raise Problem('unknown_field', 'query')
            if 'target_at' not in query:
                raise Problem('missing_field', 'query')
            timestamp(query['target_at'], 'query.target_at')
            times = [('at', query['target_at'])]
        for end, at in times:
            plan_queries.append({'id': f"{query['id']}:{end}", 'kind': 'convert', 'slot_ref': query['slot_ref'], 'target_at': at, 'target_unit_ref': PROBE_UNIT})
    source = _ledger(library, slots, operations)
    plan = {'schema_version': 'p2-temporal-measurement-request-draft-1', 'operation': 'evaluate_temporal_measurements',
            'consumer': {'profile': TEMPORAL_MEASUREMENT_PROFILE, 'profile_spec_sha256': TEMPORAL_MEASUREMENT_SPEC_SHA256,
                         'operations': ['evaluate_temporal_measurements'], 'quantity_profile': QUANTITY_PROFILE, 'quantity_profile_spec_sha256': QUANTITY_SPEC_SHA256},
            'source': source, 'views': [{'id': v['id'], 'as_of': v['as_of'], 'policy_ref': TEMPORAL_MEASUREMENT_POLICY} for v in views.values()],
            'queries': plan_queries, 'budget': {'max_steps': 0}}
    check_json(plan)
    _, _, p_slots, p_quantities, p_records, p_reviews, p_views, p_queries, hashes = validate_temporal_measurements(plan)
    return {'spec': spec, 'plan': plan, 'destinations': destinations, 'views': views, 'queries': queries, 'records': p_records, 'reviews': p_reviews,
            'quantities': p_quantities, 'hashes': hashes, 'cost': _plan_cost(p_slots, p_quantities, p_records, p_reviews, p_views, p_queries)}


def _plan_cost(slots, quantities, records, reviews, views, queries):
    total = 1 + len(slots) + len(quantities)
    for view in views.values():
        total += len(records) + len(reviews)
        visible, _, eligible = visible_temporal_measurements(records, reviews, view['as_of'])
        for query in queries.values():
            scoped = {k: r for k, r in visible.items() if r['slot_ref'] == query['slot_ref']}
            total += 10 + len(scoped) + sum(len(scoped[k]['revises']) for k in eligible & set(scoped))
    return total


def _fee(profile):
    return OWN_FEE + (COMPARE_RESERVE if profile['output']['kind'] == 'trend' else CONVERT_RESERVE)


def _round(point, places):
    scaled = _bounded(point * 10**places)
    quotient, remainder = divmod(scaled.numerator, scaled.denominator)
    twice = 2 * remainder
    coefficient = quotient + int(twice > scaled.denominator or (twice == scaled.denominator and quotient % 2 != 0))
    _bounded(Fraction(coefficient))
    digits = str(abs(coefficient)).zfill(places + 1)
    text = digits if places == 0 else digits[:-places] + '.' + digits[-places:]
    if coefficient < 0:
        text = '-' + text
    if len(text) > 64:
        raise Problem('display_text_limit', status='resource_limit')
    return coefficient, text


def _request(element, action, record_ref=None, records=None, candidates=None, slot_ref=None, target_at=None, ends=None):
    return {'element': element, 'action': action, 'record_ref': record_ref, 'records': list(records or []), 'candidates': list(candidates or []),
            'slot_ref': slot_ref, 'target_at': target_at, 'ends': ends}


def _covers(record, at):
    validity = record['validity']
    return validity['kind'] == 'bounded' and validity['start'] <= at < validity['end']


def _select(row, state, slot, at):
    """P2-i の行から選択の段階の結果を読む。state は台帳の記録・確認。"""
    reasons = row['reason_codes']
    if 'unknown_capability' in reasons:
        return {'state': 'unassessed', 'reasons': ['unknown_capability'], 'record': None, 'requests': []}
    stops = sorted(set(reasons) & set(SELECTION_STOPS))
    if not stops:
        return {'state': 'met', 'reasons': [], 'record': row['diagnostics']['candidate_refs'][slot][0], 'requests': []}
    diagnostics = row['diagnostics']
    if 'no_adopted_measurement' in stops:
        pending = sorted(key for key in diagnostics['pending_records'] if state['records'][key]['certainty'] == 'confirmed' and _covers(state['records'][key], at))
        request = _request('selection', 'confirm_pending', records=pending) if pending else _request('selection', 'record_and_confirm', slot_ref=slot, target_at=at)
    elif 'unresolved_measurement_conflict' in stops:
        request = _request('selection', 'resolve_conflict', records=diagnostics['candidate_refs'][slot])
    else:
        request = _request('selection', 'refine_validity', records=diagnostics['blocking_records'])
    return {'state': 'unmet', 'reasons': stops, 'record': None, 'requests': [request]}


def _evidence(state, key, view, at):
    record = state['records'][key]
    literal = state['quantities'][record['quantity_ref']['ref']]['literal']
    reviews = sorted(r['id'] for r in state['reviews'].values() if r['record_ref'] == key and r['recorded_at'] <= view['as_of'])
    evidence = {'record_ref': key, 'record_sha256': state['hashes'][key], 'review_refs': reviews, 'as_of': view['as_of'], 'target_at': at,
                'record_origin': deepcopy(record['origin']), 'quantity_origin': deepcopy(literal['origin']), 'validity': deepcopy(record['validity'])}
    evidence['record_observer'] = deepcopy(record['observer'])
    return evidence


def _candidates(state, row, field, at):
    found = []
    for key in sorted(row['diagnostics']['pending_records']):
        record = state['records'][key]
        if record['certainty'] == 'confirmed' and _covers(record, at) and record[field]['kind'] == 'known':
            found.append({'record_ref': key, 'origin_kind': record['origin']['kind'], 'proposed': deepcopy(record[field])})
    return found


def _context(element, key, row, state, at):
    field = element['field']
    entry = {'element': 'context:' + field, 'requires': element['requires'], 'record_ref': key}
    record = state['records'][key]
    if field == 'property':
        entry.update(observed=record['property_ref'], state='unassessed' if 'unknown_property' in row['reason_codes'] else 'met',
                     reasons=['unknown_property'] if 'unknown_property' in row['reason_codes'] else [])
        return entry, None
    met = record[field]['kind'] == 'known'
    entry.update(observed=deepcopy(record[field]), state='met' if met else 'unmet', reasons=[] if met else ['required_information_missing'])
    if met:
        return entry, None
    candidates = _candidates(state, row, field, at)
    return entry, _request('context:' + field, 'confirm_candidate' if candidates else 'observe_and_record', record_ref=key, candidates=candidates)


def _convert(literal, unit):
    request = {'schema_version': 'p2-quantity-request-draft-1', 'operation': 'evaluate_quantities',
               'consumer': {'profile': QUANTITY_PROFILE, 'profile_spec_sha256': QUANTITY_SPEC_SHA256, 'operations': ['evaluate_quantities']},
               'quantities': [{**deepcopy(literal), 'id': 'operand:0'}],
               'queries': [{'id': 'value', 'kind': 'convert', 'quantity_ref': 'operand:0', 'target_unit_ref': unit}], 'budget': {'max_steps': CONVERT_RESERVE}}
    check_json(request)
    out = run_quantities(request)
    if out['status'] == 'resource_limit':
        raise Problem(out['reason_codes'][0], 'quantity_child', 'resource_limit')
    if out['steps_used'] != CONVERT_RESERVE:
        raise Problem('quantity_convert_cost_mismatch', 'quantity_child')
    return out['results'][0]


def _value(element, key, kind, state):
    literal = state['quantities'][state['records'][key]['quantity_ref']['ref']]['literal']
    entry = {'element': 'value', 'form': element['form'], 'unit_ref': element['unit_ref'], 'record_ref': key, 'converted_domain': None}
    if 'decimal_places' in element:
        entry['decimal_places'] = element['decimal_places']
    result = _convert(literal, element['unit_ref'])
    if result['status'] == 'unassessed':
        entry.update(state='unassessed', reasons=list(result['reason_codes']))
        return entry, None
    if result['status'] == 'not_comparable':
        entry.update(state='unrepresentable', reasons=['unit_not_convertible'])
        return entry, None
    domain = result['converted_domain']
    entry['converted_domain'] = deepcopy(domain)
    single = domain['lower'] == domain['upper'] and domain['lower_closed'] and domain['upper_closed']
    if element['form'] == 'single_point' and not single:
        entry.update(state='unrepresentable', reasons=['value_not_a_single_point'])
        return entry, None
    entry.update(state='met', reasons=[])
    return entry, domain


def _aggregate(elements):
    states = {e['state'] for e in elements}
    for state, status in (('unassessed', 'unassessed'), ('unrepresentable', 'not_representable'), ('unmet', 'needs_information')):
        if state in states:
            reasons = sorted({r for e in elements if e['state'] == state for r in e['reasons']})
            return status, reasons
    return 'satisfied', []


def _flows(spec, status, kind, reasons):
    table = spec['flows']
    if status == 'satisfied':
        return deepcopy(table[kind])
    if status == 'not_representable':
        return {'retained': [], 'lost': sorted({item for r in reasons for item in table['not_representable_lost'][r]}), 'added': []}
    return None


def _single(query, profile, row, state, spec):
    view = state['views'][query['view_ref']]
    at = query['target_at']
    selection = _select(row, state, query['slot_ref'], at)
    elements = [{'element': 'selection', 'state': selection['state'], 'reasons': selection['reasons'], 'record_refs': {'at': selection['record']}}]
    if selection['state'] != 'met':
        status = {'unassessed': 'unassessed', 'unmet': 'needs_information'}[selection['state']]
        return {'status': status, 'reason_codes': selection['reasons'], 'selection': None, 'elements': elements,
                'requests': selection['requests'], 'output': None, 'flows': None}
    key = selection['record']
    requests, domain, kind = [], None, profile['output']['kind']
    for element in profile['elements']:
        if element['element'] == 'context':
            entry, request = _context(element, key, row, state, at)
            if request:
                requests.append(request)
        else:
            entry, domain = _value(element, key, kind, state)
            value_element = element
        elements.append(entry)
    status, reasons = _aggregate(elements)
    output = None
    if status == 'satisfied':
        record = state['records'][key]
        literal = state['quantities'][record['quantity_ref']['ref']]['literal']
        if kind == 'line':
            point = Fraction(domain['lower']['numerator'], domain['lower']['denominator'])
            coefficient, text = _round(point, value_element['decimal_places'])
            output = {'text': text, 'coefficient': coefficient, 'unit_ref': value_element['unit_ref'], 'decimal_places': value_element['decimal_places'], 'rounding_policy': POLICY}
        else:
            output = {'converted_domain': deepcopy(domain), 'unit_ref': value_element['unit_ref'], 'quantity_kind_ref': literal['quantity_kind_ref'],
                      'context': {'property_ref': record['property_ref'], 'specimen': deepcopy(record['specimen']), 'method': deepcopy(record['method'])},
                      'origin': {'record': record['origin']['kind'], 'quantity': literal['origin']['kind']}, 'human_confirmed': True}
    elif status == 'needs_information':
        reasons = ['required_information_missing']
    requests = requests if status == 'needs_information' else []                    # 依頼は要素の順（要求プロファイルの順）
    return {'status': status, 'reason_codes': reasons, 'selection': _evidence(state, key, view, at), 'elements': elements,
            'requests': requests, 'output': output, 'flows': _flows(spec, status, kind, reasons)}


def _trend(query, profile, rows, state, spec):
    view = state['views'][query['view_ref']]
    times = {'from': query['from_at'], 'to': query['to_at']}
    picked = {end: _select(rows[end], state, query['slot_ref'], times[end]) for end in times}
    refs = {end: picked[end]['record'] for end in times}
    elements = [{'element': 'selection', 'state': 'met', 'reasons': [], 'record_refs': refs}]
    if any(p['state'] != 'met' for p in picked.values()):
        capability = any(p['state'] == 'unassessed' for p in picked.values())
        elements[0].update(state='unassessed' if capability else 'unmet', reasons=sorted({r for p in picked.values() for r in p['reasons']}))
        requests = {}
        for end in times:
            for request in picked[end]['requests']:
                shape = json.dumps({k: v for k, v in request.items() if k != 'ends'}, sort_keys=True)
                requests.setdefault(shape, [request, []])[1].append(end)
        merged = sorted(({**request, 'ends': ends} for request, ends in requests.values()),
                        key=lambda r: (r['element'], r['record_ref'] or '', r['action'], r['ends']))
        return {'status': 'unassessed' if capability else 'needs_information', 'reason_codes': elements[0]['reasons'], 'selection': None, 'elements': elements,
                'requests': [] if capability else merged, 'output': None, 'flows': None}
    element = profile['elements'][0]
    trend = {'element': 'trend', 'context_match': list(element['context_match']), 'differences': [], 'state': 'met', 'reasons': []}
    needs, unassessed = {}, False
    for field in sorted(element['context_match']):
        for end in times:
            record = state['records'][refs[end]]
            if field == 'property':
                if 'unknown_property' in rows[end]['reason_codes']:
                    unassessed = True
            elif record[field]['kind'] != 'known':
                candidates = _candidates(state, rows[end], field, times[end])
                need = needs.setdefault(('context:' + field, refs[end]), [candidates, []])
                need[1].append(end)
    if unassessed:
        trend.update(state='unassessed', reasons=['unknown_property'])
    elif needs:
        trend.update(state='unmet', reasons=['required_information_missing'])
    else:
        for field in sorted(element['context_match']):
            first, second = state['records'][refs['from']], state['records'][refs['to']]
            name = 'property_ref' if field == 'property' else field
            if first[name] != second[name]:
                trend['differences'].append({'field': field, 'from': deepcopy(first[name]), 'to': deepcopy(second[name])})
        if trend['differences']:
            trend.update(state='unrepresentable', reasons=['contexts_differ'])
    relation = None
    if trend['state'] == 'met':
        literals = {end: state['quantities'][state['records'][refs[end]]['quantity_ref']['ref']]['literal'] for end in times}
        request = {'schema_version': 'p2-quantity-request-draft-1', 'operation': 'evaluate_quantities',
                   'consumer': {'profile': QUANTITY_PROFILE, 'profile_spec_sha256': QUANTITY_SPEC_SHA256, 'operations': ['evaluate_quantities']},
                   'quantities': [{**deepcopy(literals['from']), 'id': 'endpoint:from'}, {**deepcopy(literals['to']), 'id': 'endpoint:to'}],
                   'queries': [{'id': 'relation', 'kind': 'compare', 'left_ref': 'endpoint:from', 'right_ref': 'endpoint:to'}], 'budget': {'max_steps': COMPARE_RESERVE}}
        check_json(request)
        out = run_quantities(request)
        if out['status'] == 'resource_limit':
            raise Problem(out['reason_codes'][0], 'quantity_child', 'resource_limit')
        if out['steps_used'] != COMPARE_RESERVE:
            raise Problem('quantity_compare_cost_mismatch', 'quantity_child')
        value = out['results'][0]
        if value['status'] == 'unassessed':
            trend.update(state='unassessed', reasons=list(value['reason_codes']))
        elif value['status'] == 'not_comparable':
            trend.update(state='unrepresentable', reasons=list(value['reason_codes']))
        else:
            relation = value
    elements.append(trend)
    status, reasons = _aggregate(elements)
    requests, output = [], None
    if status == 'needs_information':
        reasons = ['required_information_missing']
        for (name, record_ref), (candidates, ends) in sorted(needs.items()):
            requests.append(_request(name, 'confirm_candidate' if candidates else 'observe_and_record', record_ref=record_ref, candidates=candidates, ends=sorted(ends)))
    if status == 'satisfied':
        output = {'relation_set': list(relation['relation_set']), 'certain_relation': relation['certain_relation'], 'direction': 'from_relative_to_to',
                  'from_at': times['from'], 'to_at': times['to'], 'assumptions': ['independent_time_variables']}
    selection = {end: _evidence(state, refs[end], view, times[end]) for end in times}
    return {'status': status, 'reason_codes': reasons, 'selection': selection, 'elements': elements, 'requests': requests, 'output': output,
            'flows': _flows(spec, status, 'trend', reasons)}


def run_library(request):
    prepared = _validate(request)
    spec, plan, cost = prepared['spec'], prepared['plan'], prepared['cost']
    state = {'records': prepared['records'], 'quantities': prepared['quantities'], 'hashes': prepared['hashes'], 'views': prepared['views'],
             'reviews': prepared['reviews']}
    queries = sorted(prepared['queries'].values(), key=lambda q: q['id'])
    rows = [{'id': q['id'], 'view_ref': q['view_ref'], 'slot_ref': q['slot_ref'], 'destination_ref': deepcopy(q['destination_ref']),
             'status': 'unassessed', 'assessment_complete': False, 'reason_codes': ['step_limit'], **dict.fromkeys(VALUE_FIELDS)} for q in queries]
    result = {'status': 'ok', 'meaning_mode': ANSWER_KIND, 'results': rows, 'reason_codes': [], 'ledger': deepcopy(plan['source']), 'temporal_measurement': None,
              'clinical_confirmation': 'not_evaluated', 'review_verification': 'structural_only', 'uncertainty_propagated': False, 'converted_to_base': False,
              'clinical_assertions_added': [], 'inferred_information': [],
              'certificate': {'status': 'not_certified', 'evidence_level': 'known_policy_change', 'reason_codes': ['requirement_evaluation_is_diagnostic'], 'scope': None}}
    budget = Budget(request['budget']['max_steps'])
    stage, current = 'temporal_measurement', None
    try:
        budget.tick()
        for _ in range(cost):
            budget.tick()
        plan['budget']['max_steps'] = cost
        plan_hash = check_json(plan)
        child = run_temporal_measurements(plan)
        if child['status'] != 'ok':
            raise Problem(child['reason_codes'][0], 'temporal_measurement', child['status'])
        if child['steps_used'] != cost:
            raise Problem('temporal_measurement_cost_mismatch', 'temporal_measurement')
        result['temporal_measurement'] = {'input_sha256': plan_hash, 'reserved_steps': cost, 'steps_used': child['steps_used'], 'source_sha256': child['source_sha256']}
        found = {(r['view'], r['query']): r for r in child['results']}
        stage = 'queries'
        for row in rows:
            current = row
            query = prepared['queries'][row['id']]
            profile = prepared['destinations'][(query['destination_ref']['id'], query['destination_ref']['version'])]
            for _ in range(_fee(profile)):
                budget.tick()
            if profile['output']['kind'] == 'trend':
                value = _trend(query, profile, {'from': found[(query['view_ref'], query['id'] + ':from')], 'to': found[(query['view_ref'], query['id'] + ':to')]}, state, spec)
            else:
                value = _single(query, profile, found[(query['view_ref'], query['id'] + ':at')], state, spec)
            row.update(value, assessment_complete=True)
        current, stage = None, 'completion'
        budget.tick()
    except Problem as problem:
        if problem.status != 'resource_limit':
            raise
        result.update(status='resource_limit', reason_codes=[problem.code])
        result['certificate']['reason_codes'] = [problem.code]
        for row in rows:
            if not row['assessment_complete'] and (stage == 'temporal_measurement' or row is current):
                row['reason_codes'] = [problem.code]
    result['steps_used'] = budget.used
    result['incomplete'] = [{'query': r['id'], 'reason_codes': r['reason_codes']} for r in rows if not r['assessment_complete']]
    if result['status'] == 'resource_limit' and stage == 'completion':
        result['incomplete'].append({'stage': 'completion', 'reason_codes': result['reason_codes']})
    return result
