"""Provenance の activity の符号と revision の entity の別計算。基の行（Observation の status・code と Provenance の項目）は P2-q の別計算を再利用し、
訂正された記録・項目の種類・状態・符号・流れ・料金・ハッシュは、要求の操作の列と宣言から自前で求める。ハッシュは、結果の台帳の記録を JSON で正規化して独立に計算する。nativeは読まない。"""
import hashlib
import json
from pathlib import Path

import observation_oracle as base

ROOT = Path(__file__).resolve().parents[2]
TM_SPEC = hashlib.sha256((ROOT/'src/med_dsl/temporal_measurement_spec.json').read_bytes()).hexdigest()


def record_hash(ledger, record):
    payload = {'binding_profile': 'p2-temporal-measurement-draft-1', 'binding_spec_sha256': TM_SPEC, 'source_ref': ledger['ref'], 'record': record}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def operations(request):
    return base.operations(request['observation_request'])


def coding_of(request, query):
    for item in request['coding']:
        if item['destination_ref'] == query['destination_ref']:
            return item
    return None


def observation_cost(request):
    return base.cost(request['observation_request'])


def cost(request):
    return 2+observation_cost(request)+2*len(request['observation_request']['grounding_request']['library_request']['queries'])


def row(request, query, ledger):
    child = request['observation_request']
    found = dict(base.row(child, query), coding=None)
    if found['observation_state'] != 'projected':
        found['coding'] = {'state': 'not_evaluated', 'entries': None, 'revision': None}
        return found
    declaration = coding_of(request, query)
    if declaration is None:
        found['coding'] = {'state': 'not_declared', 'entries': None, 'revision': None}
        return found
    activities = declaration.get('activities', {})
    record_id = found['selection']['record_ref']
    record = operations(request)[record_id]
    correction = record['kind'] == 'correct'
    if correction != (found['status_value']['state'] == 'correction'):
        raise AssertionError('status and operation disagree')
    predecessors = sorted(record['corrects']) if correction else []
    entries = []
    for index, item in enumerate(found['provenance']):
        kind = 'confirmation' if item['activity'] == 'confirmation' else ('correction' if correction else 'creation')
        entries.append({'index': index, 'kind': kind, 'activity': activities.get(kind), 'entities': []})
    reviewer = base.declaration_of(child, query).get('provenance', {}).get('reviewer_type')
    generating = [index for index, item in enumerate(found['provenance']) if item['activity'] == 'creation']
    if not correction:
        state = 'not_applicable'
    elif not declaration.get('revision', False):
        state = 'not_requested'
    elif reviewer is None:
        state = 'no_provenance'
    elif not generating:
        state = 'no_agent'
    else:
        state = 'carried'
        by_id = {r['id']: r for r in ledger['records']}
        for predecessor in predecessors:
            entries[generating[0]]['entities'].append({'role': 'revision', 'what': {'type': 'Observation', 'record_ref': predecessor,
                                                                                    'record_sha256': record_hash(ledger, by_id[predecessor])}})
    retained, lost, added = set(found['flows']['retained']), set(found['flows']['lost']), set(found['flows']['added'])
    if any(entry['activity'] is not None for entry in entries):
        added.add('assumption:activity_coding_declared')
    lost |= {'activity:'+entry['kind'] for entry in entries if entry['activity'] is None}
    if correction:
        if state == 'carried':
            retained.add('revision:predecessor_identity')
            added.add('assumption:revision_role_declared')
        else:
            lost.add('revision:predecessor_identity')
    found['flows'] = {'retained': sorted(retained), 'lost': sorted(lost), 'added': sorted(added)}
    found['coding'] = {'state': 'coded', 'entries': entries, 'revision': {'state': state, 'predecessors': predecessors}}
    return found
