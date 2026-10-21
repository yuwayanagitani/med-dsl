"""薄い臨床ライブラリの別計算。P2-iの別計算（区間差引き）、P2-fの別計算（整数対と証人点）、表示の別計算（最近接偶数への距離）を再利用し、
選択の段階の読み取り・要素の判定・集約・依頼・流れ・料金は自前で持つ。nativeは読まない。"""
from fractions import Fraction as F
import quantity_oracle as numbers
import temporal_display_oracle as display
import temporal_measurement_oracle as measurements

PROFILE = 'p2-temporal-measurement-draft-1'
QPROFILE = 'p2-quantity-literal-draft-1'
ORIGIN = {'observed': 'literal', 'judgment': 'literal', 'imported': 'imported_literal', 'ai_candidate': 'ai_candidate'}
STOPS = ('validity_unknown', 'validity_unspecified', 'no_adopted_measurement', 'unresolved_measurement_conflict')
FLOWS = {
    'line': {'retained': ['value:rounded_text'], 'lost': ['value:exact', 'record:identity', 'validity', 'context:specimen', 'context:method', 'origin', 'confirmation'], 'added': ['rounding_policy']},
    'exchange': {'retained': ['value:exact_domain', 'unit', 'quantity_kind', 'context:property', 'context:specimen', 'context:method', 'origin_kind', 'human_confirmed'],
                 'lost': ['record:identity', 'validity', 'review:identity', 'revision_history'], 'added': []},
    'trend': {'retained': ['relation_set', 'direction'], 'lost': ['value:exact', 'record:identity', 'validity', 'context', 'origin', 'confirmation'], 'added': ['assumption:independent_time_variables']}}
LOST = {'value_not_a_single_point': ['interval_bounds'], 'unit_not_convertible': ['value'], 'contexts_differ': ['relation'],
        'incompatible_dimension': ['relation'], 'incompatible_quantity_kind': ['relation']}


def build(request):
    """操作から、P2-iの別計算が読む形（hashなし）の台帳と、その問い合わせを作る。"""
    library = request['library']
    source = {'slots': library['slots'], 'quantities': [], 'records': [], 'reviews': []}
    for op in library['operations']:
        if op['kind'] == 'confirm':
            source['reviews'].append({'id': op['id'], 'record_ref': op['record_ref'], 'recorded_at': op['recorded_at']})
            continue
        ref = 'quantity:'+op['id']
        source['quantities'].append({'ref': ref, 'literal': {'id': ref, 'quantity_kind_ref': op['value']['quantity_kind_ref'], 'unit_ref': op['value']['unit_ref'],
                                                             'magnitude': op['value']['magnitude'], 'origin': {'kind': ORIGIN[op['origin']['kind']], 'ref': op['origin']['ref']},
                                                             'required_capabilities': [QPROFILE]}})
        source['records'].append({'id': op['id'], 'slot_ref': op['slot_ref'], 'property_ref': op['property_ref'], 'specimen': op['specimen'], 'method': op['method'],
                                  'validity': op['validity'], 'quantity_ref': {'ref': ref}, 'certainty': op['certainty'], 'recorded_at': op['recorded_at'],
                                  'origin': op['origin'], 'required_capabilities': [PROFILE, *op.get('capabilities', [])],
                                  'revises': list(op['corrects']) if op['kind'] == 'correct' else []})
    plan_queries = []
    profiles = {(p['id'], p['version']): p for p in request['destinations']}
    for query in request['queries']:
        profile = profiles[(query['destination_ref']['id'], query['destination_ref']['version'])]
        for end, at in ([('from', query['from_at']), ('to', query['to_at'])] if profile['output']['kind'] == 'trend' else [('at', query['target_at'])]):
            plan_queries.append({'id': f"{query['id']}:{end}", 'slot_ref': query['slot_ref'], 'target_at': at})
    return {'source': source, 'views': request['views'], 'queries': plan_queries}


def cost(request):
    profiles = {(p['id'], p['version']): p for p in request['destinations']}
    total = 2+measurements.cost(build(request))
    for query in request['queries']:
        total += 6+(12 if profiles[(query['destination_ref']['id'], query['destination_ref']['version'])]['output']['kind'] == 'trend' else 8)
    return total


def covers(record, at):
    return record['validity']['kind'] == 'bounded' and record['validity']['start'] <= at < record['validity']['end']


def request_of(element, action, record_ref=None, records=(), candidates=(), slot=None, at=None, ends=None):
    return {'element': element, 'action': action, 'record_ref': record_ref, 'records': list(records), 'candidates': list(candidates), 'slot_ref': slot, 'target_at': at, 'ends': ends}


def select(plan, view, slot, at):
    records, eligible, _, candidates, _ = measurements.selection(plan, view, {'slot_ref': slot, 'target_at': at})
    quantities = {q['ref']: q['literal'] for q in plan['source']['quantities']}
    if any(set(r['required_capabilities'])-{PROFILE} or set(quantities[r['quantity_ref']['ref']]['required_capabilities'])-{QPROFILE} for r in records.values()):
        return {'state': 'unassessed', 'reasons': ['unknown_capability'], 'record': None, 'requests': [], 'records': records, 'eligible': eligible}
    blocking = sorted(k for k in eligible if records[k]['validity']['kind'] in ('unknown', 'unspecified'))
    if blocking:
        return {'state': 'unmet', 'reasons': sorted({'validity_'+records[k]['validity']['kind'] for k in blocking}), 'record': None,
                'requests': [request_of('selection', 'refine_validity', records=blocking)], 'records': records, 'eligible': eligible}
    if len(candidates) == 0:
        pending = sorted(k for k in records if k not in eligible and records[k]['certainty'] == 'confirmed' and covers(records[k], at))
        ask = request_of('selection', 'confirm_pending', records=pending) if pending else request_of('selection', 'record_and_confirm', slot=slot, at=at)
        return {'state': 'unmet', 'reasons': ['no_adopted_measurement'], 'record': None, 'requests': [ask], 'records': records, 'eligible': eligible}
    if len(candidates) > 1:
        return {'state': 'unmet', 'reasons': ['unresolved_measurement_conflict'], 'record': None,
                'requests': [request_of('selection', 'resolve_conflict', records=candidates)], 'records': records, 'eligible': eligible}
    return {'state': 'met', 'reasons': [], 'record': candidates[0], 'requests': [], 'records': records, 'eligible': eligible}


def candidates_for(picked, field, at):
    return [{'record_ref': k, 'origin_kind': r['origin']['kind'], 'proposed': r[field]} for k, r in sorted(picked['records'].items())
            if k not in picked['eligible'] and r['certainty'] == 'confirmed' and covers(r, at) and r[field]['kind'] == 'known']


def literal_of(plan, record):
    return {q['ref']: q['literal'] for q in plan['source']['quantities']}[record['quantity_ref']['ref']]


def convert(literal, unit):
    kinds, units = measurements.KINDS, measurements.UNITS
    reasons = set()
    if literal['quantity_kind_ref'] not in kinds:
        reasons.add('unknown_quantity_kind')
    if literal['unit_ref'] not in units or unit not in units:
        reasons.add('unknown_unit')
    if reasons:
        return 'unassessed', sorted(reasons), None
    if units[literal['unit_ref']] != units[unit]:
        return 'not_comparable', ['incompatible_dimension'], None
    return 'computed', [], numbers.converted(literal, unit)


def value_element(element, record, plan):
    literal = literal_of(plan, record)
    entry = {'element': 'value', 'form': element['form'], 'unit_ref': element['unit_ref'], 'converted_domain': None}
    status, reasons, domain = convert(literal, element['unit_ref'])
    if status == 'unassessed':
        return {**entry, 'state': 'unassessed', 'reasons': reasons}, None
    if status == 'not_comparable':
        return {**entry, 'state': 'unrepresentable', 'reasons': ['unit_not_convertible']}, None
    entry['converted_domain'] = domain
    single = domain['lower'] == domain['upper'] and domain['lower_closed'] and domain['upper_closed']
    if element['form'] == 'single_point' and not single:
        return {**entry, 'state': 'unrepresentable', 'reasons': ['value_not_a_single_point']}, None
    return {**entry, 'state': 'met', 'reasons': []}, domain


def aggregate(elements):
    for state, status in (('unassessed', 'unassessed'), ('unrepresentable', 'not_representable'), ('unmet', 'needs_information')):
        found = [e for e in elements if e['state'] == state]
        if found:
            return status, sorted({r for e in found for r in e['reasons']})
    return 'satisfied', []


def flows(status, kind, reasons):
    if status == 'satisfied':
        return FLOWS[kind]
    if status == 'not_representable':
        return {'retained': [], 'lost': sorted({x for r in reasons for x in LOST[r]}), 'added': []}
    return None


def row(request, query):
    plan = build(request)
    profile = {(p['id'], p['version']): p for p in request['destinations']}[(query['destination_ref']['id'], query['destination_ref']['version'])]
    view = {v['id']: v for v in request['views']}[query['view_ref']]
    kind = profile['output']['kind']
    if kind == 'trend':
        return trend_row(plan, profile, view, query)
    at = query['target_at']
    picked = select(plan, view, query['slot_ref'], at)
    elements = [{'element': 'selection', 'state': picked['state'], 'reasons': picked['reasons'], 'record_refs': {'at': picked['record']}}]
    if picked['state'] != 'met':
        return {'status': {'unassessed': 'unassessed', 'unmet': 'needs_information'}[picked['state']], 'reasons': picked['reasons'], 'selection': None,
                'elements': elements, 'requests': picked['requests'], 'output': None, 'flows': None}
    record = picked['records'][picked['record']]
    requests, domain = [], None
    for element in profile['elements']:
        if element['element'] == 'context':
            field = element['field']
            if field == 'property':
                known = record['property_ref'] in measurements.PROPERTIES
                elements.append({'element': 'context:property', 'state': 'met' if known else 'unassessed', 'reasons': [] if known else ['unknown_property']})
            else:
                met = record[field]['kind'] == 'known'
                elements.append({'element': 'context:'+field, 'state': 'met' if met else 'unmet', 'reasons': [] if met else ['required_information_missing']})
                if not met:
                    found = candidates_for(picked, field, at)
                    requests.append(request_of('context:'+field, 'confirm_candidate' if found else 'observe_and_record', picked['record'], candidates=found))
        else:
            entry, domain = value_element(element, record, plan)
            elements.append(entry)
            value = element
    status, reasons = aggregate(elements)
    output = None
    if status == 'satisfied':
        if kind == 'line':
            x = F(domain['lower']['numerator'], domain['lower']['denominator'])
            coefficient, text, *_ = display.rounded(x, value['decimal_places'])
            output = {'text': text, 'coefficient': coefficient, 'unit_ref': value['unit_ref'], 'decimal_places': value['decimal_places'], 'rounding_policy': 'fiction:decimal-half-even@1'}
        else:
            literal = literal_of(plan, record)
            output = {'converted_domain': domain, 'unit_ref': value['unit_ref'], 'quantity_kind_ref': literal['quantity_kind_ref'],
                      'context': {'property_ref': record['property_ref'], 'specimen': record['specimen'], 'method': record['method']},
                      'origin': {'record': record['origin']['kind'], 'quantity': literal['origin']['kind']}, 'human_confirmed': True}
    if status == 'needs_information':
        reasons = ['required_information_missing']
    return {'status': status, 'reasons': reasons, 'selection': {'record_ref': picked['record'], 'target_at': at}, 'elements': elements,
            'requests': requests if status == 'needs_information' else [], 'output': output, 'flows': flows(status, kind, reasons)}


def trend_row(plan, profile, view, query):
    times = {'from': query['from_at'], 'to': query['to_at']}
    picked = {end: select(plan, view, query['slot_ref'], times[end]) for end in times}
    if any(p['state'] != 'met' for p in picked.values()):
        capability = any(p['state'] == 'unassessed' for p in picked.values())
        reasons = sorted({r for p in picked.values() for r in p['reasons']})
        groups = {}
        for end in times:
            for request in picked[end]['requests']:
                shape = repr(sorted(request.items(), key=lambda item: item[0]))
                groups.setdefault(shape, [request, []])[1].append(end)
        merged = sorted(({**request, 'ends': ends} for request, ends in groups.values()), key=lambda r: (r['element'], r['record_ref'] or '', r['action'], r['ends']))
        return {'status': 'unassessed' if capability else 'needs_information', 'reasons': reasons, 'selection': None,
                'elements': [{'element': 'selection', 'state': 'unassessed' if capability else 'unmet', 'reasons': reasons}],
                'requests': [] if capability else merged, 'output': None, 'flows': None}
    records = {end: picked[end]['records'][picked[end]['record']] for end in times}
    match = sorted(profile['elements'][0]['context_match'])
    needs, unassessed = {}, False
    for field in match:
        for end in times:
            if field == 'property':
                unassessed = unassessed or records[end]['property_ref'] not in measurements.PROPERTIES
            elif records[end][field]['kind'] != 'known':
                needs.setdefault(('context:'+field, picked[end]['record']), [candidates_for(picked[end], field, times[end]), []])[1].append(end)
    state, reasons, differences, relation = 'met', [], [], None
    if unassessed:
        state, reasons = 'unassessed', ['unknown_property']
    elif needs:
        state, reasons = 'unmet', ['required_information_missing']
    else:
        for field in match:
            name = 'property_ref' if field == 'property' else field
            if records['from'][name] != records['to'][name]:
                differences.append({'field': field, 'from': records['from'][name], 'to': records['to'][name]})
        if differences:
            state, reasons = 'unrepresentable', ['contexts_differ']
    if state == 'met':
        left, right = (literal_of(plan, records[end]) for end in ('from', 'to'))
        kinds, units = measurements.KINDS, measurements.UNITS
        problems = set()
        for literal in (left, right):
            if literal['quantity_kind_ref'] not in kinds:
                problems.add('unknown_quantity_kind')
            if literal['unit_ref'] not in units:
                problems.add('unknown_unit')
        if problems:
            state, reasons = 'unassessed', sorted(problems)
        elif units[left['unit_ref']] != units[right['unit_ref']]:
            state, reasons = 'unrepresentable', ['incompatible_dimension']
        elif left['quantity_kind_ref'] != right['quantity_kind_ref']:
            state, reasons = 'unrepresentable', ['incompatible_quantity_kind']
        else:
            relation = numbers.relations(left, right)
    elements = [{'element': 'selection', 'state': 'met', 'reasons': []}, {'element': 'trend', 'state': state, 'reasons': reasons, 'differences': differences}]
    status, reasons = aggregate(elements)
    requests = []
    if status == 'needs_information':
        reasons = ['required_information_missing']
        requests = [request_of(name, 'confirm_candidate' if found else 'observe_and_record', record, candidates=found, ends=sorted(ends))
                    for (name, record), (found, ends) in sorted(needs.items(), key=lambda item: item[0])]
    output = None
    if status == 'satisfied':
        output = {'relation_set': relation, 'certain_relation': relation[0] if len(relation) == 1 else None, 'direction': 'from_relative_to_to',
                  'from_at': times['from'], 'to_at': times['to'], 'assumptions': ['independent_time_variables']}
    return {'status': status, 'reasons': reasons, 'selection': {end: {'record_ref': picked[end]['record'], 'target_at': times[end]} for end in times}, 'elements': elements,
            'requests': requests, 'output': output, 'flows': flows(status, 'trend', reasons)}
