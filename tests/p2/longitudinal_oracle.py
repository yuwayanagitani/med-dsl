"""縦断比較の参照計算。P2-iの別計算（区間差引き）とP2-fの別計算（整数対と証人点）を再利用し、
文脈・時刻の順序・理由の和集合・料金・63bit境界は自前で持つ。nativeは読まない。
関係は二つの経路で求める：(1) 端点の換算領域から導いた値どうし（実装と同じ連鎖）、(2) 元のリテラルどうし（連鎖を使わない）。"""
import quantity_oracle as numbers
import temporal_measurement_oracle as measurements

PROFILE = 'p2-longitudinal-comparison-draft-1'
FIELDS = (('method', 'different_method'), ('property_ref', 'different_property'), ('specimen', 'different_specimen'))
INPUT_BITS = 63


def endpoint(request, comparison, which):
    plan = request['temporal_measurement_plan']
    views = {v['id']: v for v in plan['views']}
    queries = {q['id']: q for q in plan['queries']}
    query = queries[comparison[which + '_query_ref']]
    return query, measurements.answer(plan, views[comparison['view_ref']], query)


def derived(domain, unit):
    """換算領域を、目標単位の量にする（点または区間）。"""
    low, high = numbers.read(domain['lower']), numbers.read(domain['upper'])
    if low == high:
        magnitude = {'kind': 'point', 'value': domain['lower']}
    else:
        magnitude = {'kind': 'interval', 'lower': domain['lower'], 'upper': domain['upper'],
                     'lower_closed': domain['lower_closed'], 'upper_closed': domain['upper_closed']}
    return {'unit_ref': unit, 'magnitude': magnitude}


def beyond_input_limit(quantity):
    magnitude = quantity['magnitude']
    values = [magnitude['value']] if magnitude['kind'] == 'point' else [magnitude['lower'], magnitude['upper']]
    return any(abs(n).bit_length() > INPUT_BITS or d.bit_length() > INPUT_BITS for n, d in map(numbers.read, values))


def row(request, comparison):
    """比較1件の期待。endpoints：端点の行を公開するか。"""
    if set(comparison['required_capabilities']) - {PROFILE}:
        return {'status': 'unassessed', 'reason_codes': ['unknown_capability'], 'endpoints': False}
    plan = request['temporal_measurement_plan']
    (start_query, start), (end_query, end) = endpoint(request, comparison, 'from'), endpoint(request, comparison, 'to')
    if start['status'] != 'computed' or end['status'] != 'computed':
        return {'status': 'unassessed', 'reason_codes': sorted(set(start['reason_codes']) | set(end['reason_codes'])), 'endpoints': True}
    records = {r['id']: r for r in plan['source']['records']}
    first, second = records[start['selected'][0]], records[end['selected'][0]]
    differences = [(field, reason) for field, reason in FIELDS if first[field] != second[field]]
    if differences:
        return {'status': 'not_comparable', 'reason_codes': sorted(reason for _, reason in differences),
                'differences': [field for field, _ in differences], 'endpoints': True}
    left, right = derived(start['converted_domain'], start_query['target_unit_ref']), derived(end['converted_domain'], end_query['target_unit_ref'])
    if beyond_input_limit(left) or beyond_input_limit(right):
        return {'status': 'resource_limit', 'reason_codes': ['rational_integer_limit'], 'endpoints': True}
    quantities = {q['ref']: q['literal'] for q in plan['source']['quantities']}
    originals = [quantities[records[key]['quantity_ref']['ref']] for key in (start['selected'][0], end['selected'][0])]
    return {'status': 'computed', 'reason_codes': [], 'relation': numbers.relations(left, right),
            'original': numbers.relations(originals[0], originals[1]), 'endpoints': True, 'selected': [start['selected'][0], end['selected'][0]]}


def cost(request):
    return 2 + measurements.cost(request['temporal_measurement_plan']) + 18 * len(request['comparisons'])
