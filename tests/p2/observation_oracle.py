"""Observation の status・code の写像と Provenance の別計算。基の行は構造への写像の可否の別計算（Decimal を使う）を再利用し、
どの記録が訂正か・どの確認が見えるか・確認者・時刻・出自は、台帳の結果でなく要求の操作の列から自前で読む。流れの表は文書71の§1.2の手書き。nativeは読まない。"""
import grounding_oracle as base_oracle
import library_oracle as library

STATUS = {'original': ['final'], 'correction': ['amended', 'corrected']}


def operations(request):
    return {op['id']: op for op in request['grounding_request']['library_request']['library']['operations']}


def visible_reviews(request, record_id, as_of):
    found = [op for op in operations(request).values() if op['kind'] == 'confirm' and op['record_ref'] == record_id and op['recorded_at'] <= as_of]
    return sorted(found, key=lambda op: (op['recorded_at'], op['id']))


def declaration_of(request, query):
    for item in request['observations']:
        if item['destination_ref'] == query['destination_ref']:
            return item
    return None


def cost(request):
    return 2+base_oracle.cost(request['grounding_request'])+3*len(request['grounding_request']['library_request']['queries'])


def grounding_cost(request):
    return base_oracle.cost(request['grounding_request'])


def row(request, query):
    grounded = base_oracle.row(request['grounding_request'], query)
    found = dict(grounded, observation_state=None, status_value=None, code_value=None, provenance=None)
    declaration = declaration_of(request, query)
    if declaration is None:
        found['observation_state'] = 'not_declared'
        return found
    if grounded['state'] != 'representable':
        found['observation_state'] = 'not_evaluated'
        return found
    libreq = request['grounding_request']['library_request']
    view = next(v for v in libreq['views'] if v['id'] == query['view_ref'])
    record_id = grounded['selection']['record_ref']
    record = operations(request)[record_id]
    property_ref = grounded['output']['context']['property_ref']
    state = 'correction' if record['kind'] == 'correct' else 'original'
    mapping = {entry['property_ref']: entry for entry in declaration['code_map']}
    needs = []
    observer = record.get('observer')
    if observer is not None and observer['kind'] == 'unknown':
        observer = None
    reviewer = declaration.get('provenance', {}).get('reviewer_type')
    observer_type = declaration.get('provenance', {}).get('observer_type')
    if reviewer is not None and observer is not None and observer['kind'] == 'human' and observer_type is None:
        needs.append({'element': 'provenance', 'action': 'declare_observer_type', 'record_ref': record_id, 'property_ref': None})
    if property_ref not in mapping:
        needs.append({'element': 'code', 'action': 'declare_code_mapping', 'record_ref': record_id, 'property_ref': property_ref})
    chosen = declaration['status'].get(state)
    if chosen is None:
        needs.append({'element': 'status', 'action': 'declare_correction_status', 'record_ref': record_id, 'property_ref': None})
    if needs:
        found.update(status='needs_information', reasons=['required_information_missing'], requests=sorted(needs, key=lambda r: (r['element'], r['record_ref'])),
                     output=None, flows=None, observation_state='needs_information')
        return found
    entries = []
    if reviewer is not None:
        agents = []
        if record['origin']['kind'] == 'ai_candidate':
            agents.append({'type': 'Device', 'identifier': record['origin']['ref']})
        if observer is not None:
            agents.append({'type': 'Device' if observer['kind'] == 'device' else observer_type, 'identifier': observer['ref']})
        if agents:
            entries.append({'activity': 'creation', 'record_ref': record_id, 'recorded': record['recorded_at'], 'agents': agents})
        for review in visible_reviews(request, record_id, view['as_of']):
            entries.append({'activity': 'confirmation', 'record_ref': record_id, 'recorded': review['recorded_at'], 'agents': [{'type': reviewer, 'identifier': review['reviewer_ref']}]})
    retained, lost, added = set(grounded['flows']['retained']), set(grounded['flows']['lost']), set(grounded['flows']['added'])
    retained.add('context:property')
    lost.discard('context:property')
    added |= {'assumption:code_mapping_declared', 'assumption:status_mapping:'+state+':'+chosen}
    if reviewer is not None:
        retained |= {'human_confirmed', 'record:identity'}
        lost -= {'human_confirmed', 'record:identity'}
        added.add('assumption:reviewer_type_declared')
        if record['origin']['kind'] == 'ai_candidate':
            retained.add('origin_kind')
            lost.discard('origin_kind')
        if observer is not None:
            retained.add('observer')
            if observer['kind'] == 'human':
                added.add('assumption:observer_type_declared')
    elif observer is not None:
        lost.add('observer')
    found.update(observation_state='projected', status_value={'state': state, 'code': chosen},
                 code_value={'system': mapping[property_ref]['system'], 'code': mapping[property_ref]['code']}, provenance=entries,
                 flows={'retained': sorted(retained), 'lost': sorted(lost), 'added': sorted(added)})
    return found
