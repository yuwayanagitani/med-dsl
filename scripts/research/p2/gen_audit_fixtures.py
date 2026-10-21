#!/usr/bin/env python3
"""文書83の手指定期待を展開する。runtimeはimportせず、出力から期待を作らない。"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(os.environ.get('P2_REPO') or Path(__file__).resolve().parents[3]).resolve()
DIRECTORY = ROOT/'examples/p2-audit'
PROFILE = 'p2-terminology-audit-draft-1'
SPEC = hashlib.sha256((ROOT/'src/med_dsl/terminology_audit_spec.json').read_bytes()).hexdigest()
REF = 'fiction:terminology:drugs'
OLD_VERSION, NEW_VERSION = '2026-09', '2026-10'
POL = [{'name': 'code_list', 'class': 'administrative'}, {'name': 'strength', 'class': 'definitional'}]
VALUE_FIELDS = ('concept_source', 'presence', 'audit_state', 'facets', 'requests', 'policy_assumptions', 'successor')
STATES = ('unchanged_in_scope', 'changed_administrative_only', 'changed', 'needs_information', 'not_found', 'not_compared')


def check(path, value):
    return {'path': path, 'equals': value}


def atom(ident, kind, name, attributes=()):
    return {'id': ident, 'kind': kind, 'name': name, 'attributes': [{'name': n, 'value': v} for n, v in attributes]}


def concept(ident, source, atoms, relations=()):
    return {'id': ident, 'source': source, 'atoms': deepcopy(list(atoms)), 'relations': [{'kind': k, 'target': t} for k, t in relations]}


def world():
    """標準の世界 W（文書83の§0）。"""
    return {'c1': concept('c1', 'S', [atom('a1', 'full', 'alpha 5 mg tablet', [('code_list', 'N1'), ('strength', '5 mg')]), atom('a2', 'syn', 'alpha tab 5')],
                          [('has_ingredient', 'c9'), ('has_form', 'c8')]),
            'c2': concept('c2', 'S', [atom('a3', 'full', 'beta 10 mg tablet', [('strength', '10 mg')])], [('has_ingredient', 'c9')]),
            'c8': concept('c8', 'S', [atom('a8', 'form', 'tablet')]),
            'c9': concept('c9', 'S', [atom('a9', 'ingredient', 'alpha')])}


def find_atom(w, concept_id, atom_id):
    return next(a for a in w[concept_id]['atoms'] if a['id'] == atom_id)


def snapshot(concepts, version, sha=None):
    found = {'ref': REF, 'version': version, 'concepts': deepcopy(list(concepts.values()))}
    if sha is not None:
        found['source_sha256'] = sha
    return found


def request(old, new, refs, policy=POL, sources=('S',), budget=100000, old_sha=None, new_sha=None):
    return {'schema_version': 'p2-audit-request-draft-1', 'operation': 'run_terminology_audit',
            'consumer': {'profile': PROFILE, 'profile_spec_sha256': SPEC, 'operations': ['run_terminology_audit']},
            'from': snapshot(old, OLD_VERSION, old_sha), 'to': snapshot(new, NEW_VERSION, new_sha), 'scope': {'sources': list(sources)},
            'policy': {'attributes': deepcopy(policy)}, 'references': list(refs), 'budget': {'max_steps': budget}}


# ---- 期待の部品 ----
def names(state='unchanged', added=(), removed=(), modified=()):
    return {'state': state, 'added': list(added), 'removed': list(removed), 'modified': list(modified)}


def relations(state='unchanged', added=(), removed=(), unresolved=()):
    return {'state': state, 'added': list(added), 'removed': list(removed), 'unresolved_in_to': list(unresolved)}


def attributes(state='unchanged', definitional=(), administrative=(), undeclared=(), added=0, removed=0):
    return {'state': state, 'definitional': list(definitional), 'administrative': list(administrative), 'undeclared': list(undeclared),
            'with_atom_change': {'added': added, 'removed': removed}}


def facets(n=None, r=None, a=None):
    return {'names': n or names(), 'relations': r or relations(), 'attributes': a or attributes()}


def shown(ident, kind, name):
    return {'id': ident, 'kind': kind, 'name': name}


def rel(kind, target, in_from, in_to):
    return {'kind': kind, 'target': target, 'target_in_from': in_from, 'target_in_to': in_to}


def diff(atom_id, name, before, after):
    return {'atom': atom_id, 'name': name, 'from': list(before), 'to': list(after)}


def attribute_request(ref, name):
    return {'element': 'attribute', 'action': 'declare_attribute_class', 'reference': ref, 'name': name}


def history_request(ref):
    return {'element': 'history', 'action': 'provide_official_history', 'reference': ref, 'name': None}


def row(index, ref, state, presence='continues', face=None, requests=(), assumptions=(), successor=None, source='S'):
    p = ['results', index]
    return [check(p+['reference'], ref), check(p+['concept_source'], source), check(p+['presence'], presence), check(p+['audit_state'], state), check(p+['facets'], face),
            check(p+['requests'], list(requests)), check(p+['policy_assumptions'], list(assumptions)), check(p+['successor'], successor),
            check(p+['assessment_complete'], True), check(p+['reason_codes'], [])]


def unchanged(index, ref):
    return row(index, ref, 'unchanged_in_scope', face=facets())


def missing(index, ref, source='S'):
    return row(index, ref, 'not_found', 'not_found', None, [history_request(ref)], (), 'not_determined', source)


def summary(references, by_state, old, new, in_old, in_new, continuing):
    counts = {state: 0 for state in STATES}
    counts.update(by_state)
    return {'references': references, 'by_state': counts, 'from_concepts': old, 'to_concepts': new, 'in_scope_from': in_old, 'in_scope_to': in_new,
            'continuing': continuing, 'from_only': in_old-continuing, 'to_only': in_new-continuing}


def unfinished(index, ref):
    p = ['results', index]
    return [check(p+['reference'], ref), check(p+['assessment_complete'], False), check(p+['reason_codes'], ['step_limit'])] + [check(p+[key], None) for key in VALUE_FIELDS]


def main():
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    entries = []

    def emit(name, request_, checks, normal=True):
        checks = list(checks)
        if normal:
            checks += [check(['meaning_mode'], 'terminology_version_audit'), check(['direction'], 'from_to'), check(['reverse_inferred'], False),
                       check(['converted_to_base'], False), check(['clinical_assertions_added'], []), check(['inferred_information'], []),
                       check(['clinical_confirmation'], 'not_evaluated'), check(['uncertainty_propagated'], False), check(['certificate', 'status'], 'not_certified'),
                       check(['certificate', 'evidence_level'], 'known_policy_change'), check(['certificate', 'scope'], None)]
        data = {'schema_version': 'p1-fixture-draft-1', 'fixture_version': 1, 'fixture_id': name, 'condition': name[:3], 'fictional': True,
                'review_state': 'author_draft', 'request': deepcopy(request_), 'expected': {'comparison': 'required_paths', 'checks': checks}}
        raw = (json.dumps(data, ensure_ascii=False, indent=2)+'\n').encode()
        (DIRECTORY/(name.lower()+'.json')).write_bytes(raw)
        entries.append({'fixture_id': name, 'condition': name[:3], 'path': name.lower()+'.json', 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})

    def good(name, request_, rows, steps, total_summary, extra=()):
        emit(name, request_, [check(['status'], 'ok'), check(['steps_used'], steps), check(['incomplete'], []), check(['summary'], total_summary), *rows, *extra])

    def bad(name, request_, code, status='invalid_input'):
        emit(name, request_, [check(['status'], status), check(['reason_codes'], [code])], False)

    # ---- 例（U） ----
    w = world()
    s4 = lambda **by: summary(1, by, 4, 4, 4, 4, 4)
    base_summary = summary(2, {'unchanged_in_scope': 2}, 4, 4, 4, 4, 4)
    u01 = request(w, world(), ['c1', 'c2'])
    good('U01', u01, unchanged(0, 'c1') + unchanged(1, 'c2'), 30, base_summary)

    n = world()
    find_atom(n, 'c1', 'a1')['attributes'][0]['value'] = 'N2'
    good('U02', request(w, n, ['c1']), row(0, 'c1', 'changed_administrative_only', face=facets(a=attributes('changed', administrative=[diff('a1', 'code_list', ['N1'], ['N2'])])),
                                          assumptions=['attribute_class:code_list:administrative']), 23, s4(changed_administrative_only=1))

    n = world()
    find_atom(n, 'c2', 'a3')['attributes'][0]['value'] = '20 mg'
    good('U03', request(w, n, ['c2']), row(0, 'c2', 'changed', face=facets(a=attributes('changed', definitional=[diff('a3', 'strength', ['10 mg'], ['20 mg'])])),
                                          assumptions=['attribute_class:strength:definitional']), 17, s4(changed=1))

    n = world()
    find_atom(n, 'c1', 'a2')['attributes'].append({'name': 'flag', 'value': 'x'})
    good('U04', request(w, n, ['c1']), row(0, 'c1', 'needs_information', face=facets(a=attributes('changed', undeclared=[diff('a2', 'flag', [], ['x'])])),
                                          requests=[attribute_request('c1', 'flag')]), 24, s4(needs_information=1))

    n = world()
    n['c1']['atoms'].append(atom('a5', 'syn', 'alpha tab'))
    good('U05', request(w, n, ['c1']), row(0, 'c1', 'changed', face=facets(n=names('changed', added=[shown('a5', 'syn', 'alpha tab')]))), 24, s4(changed=1))

    n = world()
    find_atom(n, 'c1', 'a2')['name'] = 'alpha tablet 5'
    good('U06', request(w, n, ['c1']), row(0, 'c1', 'changed', face=facets(n=names('changed', modified=[{'id': 'a2', 'from': {'kind': 'syn', 'name': 'alpha tab 5'},
                                                                                                         'to': {'kind': 'syn', 'name': 'alpha tablet 5'}}]))), 23, s4(changed=1))

    n = world()
    del n['c9']
    n['c1']['relations'] = [r for r in n['c1']['relations'] if r['target'] != 'c9']
    n['c2']['relations'] = []
    gone = relations('changed', removed=[rel('has_ingredient', 'c9', True, False)])
    good('U07', request(w, n, ['c1', 'c2', 'c9']),
         row(0, 'c1', 'changed', face=facets(r=gone)) + row(1, 'c2', 'changed', face=facets(r=gone)) + missing(2, 'c9'),
         29, summary(3, {'changed': 2, 'not_found': 1}, 4, 3, 4, 3, 3))

    n = world()
    n['c2']['relations'] = []
    good('U08', request(w, n, ['c2']), row(0, 'c2', 'changed', face=facets(r=relations('changed', removed=[rel('has_ingredient', 'c9', True, True)]))), 16, s4(changed=1))

    n = world()
    n['c10'] = concept('c10', 'S', [atom('a10', 'full', 'delta')])
    n['c1']['relations'].append({'kind': 'has_ingredient', 'target': 'c10'})
    good('U09', request(w, n, ['c1']), row(0, 'c1', 'changed', face=facets(r=relations('changed', added=[rel('has_ingredient', 'c10', False, True)]))), 25,
         summary(1, {'changed': 1}, 4, 5, 4, 5, 4))

    n = world()
    del n['c2']
    n['c11'] = concept('c11', 'S', [atom('a11', 'full', 'beta 10 mg tablet', [('strength', '10 mg')])], [('has_ingredient', 'c9')])
    good('U10', request(w, n, ['c2']), missing(0, 'c2'), 14, summary(1, {'not_found': 1}, 4, 4, 4, 4, 3))

    old = world()
    old['c7'] = concept('c7', 'X', [atom('a7', 'full', 'omega')])
    new = world()
    new['c7'] = concept('c7', 'X', [atom('a7', 'full', 'omega2')])
    good('U11', request(old, new, ['c7']), row(0, 'c7', 'not_compared', 'not_compared', None, source='X'), 13, summary(1, {'not_compared': 1}, 5, 5, 4, 4, 4))

    old = world()
    old['c1']['relations'].append({'kind': 'has_part', 'target': 'c99'})
    new = deepcopy(old)
    good('U12', request(old, new, ['c1']), row(0, 'c1', 'unchanged_in_scope', face=facets(r=relations('unchanged', unresolved=[{'target': 'c99', 'in_from': False}]))), 25, s4(unchanged_in_scope=1))

    n = world()
    del n['c9']
    good('U13', request(w, n, ['c2']), row(0, 'c2', 'changed', face=facets(r=relations('changed', unresolved=[{'target': 'c9', 'in_from': True}]))), 16,
         summary(1, {'changed': 1}, 4, 3, 4, 3, 3))

    old = world()
    find_atom(old, 'c2', 'a3')['attributes'][0]['value'] = '20 mg'
    good('U14', request(old, world(), ['c2']), row(0, 'c2', 'changed', face=facets(a=attributes('changed', definitional=[diff('a3', 'strength', ['20 mg'], ['10 mg'])])),
                                                 assumptions=['attribute_class:strength:definitional']), 17, s4(changed=1))

    old = world()
    find_atom(old, 'c1', 'a1')['attributes'].insert(1, {'name': 'code_list', 'value': 'N2'})
    new = world()
    find_atom(new, 'c1', 'a1')['attributes'].insert(1, {'name': 'code_list', 'value': 'N3'})
    good('U15', request(old, new, ['c1']), row(0, 'c1', 'changed_administrative_only', face=facets(a=attributes('changed', administrative=[diff('a1', 'code_list', ['N1', 'N2'], ['N1', 'N3'])])),
                                              assumptions=['attribute_class:code_list:administrative']), 25, s4(changed_administrative_only=1))

    old = world()
    find_atom(old, 'c1', 'a2')['attributes'].append({'name': 'flag', 'value': 'x'})
    new = world()
    new['c1']['atoms'] = [a for a in new['c1']['atoms'] if a['id'] != 'a2']
    good('U16', request(old, new, ['c1']), row(0, 'c1', 'changed', face=facets(n=names('changed', removed=[shown('a2', 'syn', 'alpha tab 5')]), a=attributes('unchanged', removed=1))), 23, s4(changed=1))

    n = world()
    find_atom(n, 'c1', 'a1')['attributes'][0]['value'] = 'N2'
    n['c1']['atoms'].append(atom('a5', 'syn', 'alpha tab'))
    good('U17', request(w, n, ['c1']), row(0, 'c1', 'changed', face=facets(n=names('changed', added=[shown('a5', 'syn', 'alpha tab')]),
                                                                         a=attributes('changed', administrative=[diff('a1', 'code_list', ['N1'], ['N2'])])),
                                          assumptions=['attribute_class:code_list:administrative']), 24, s4(changed=1))

    n = world()
    find_atom(n, 'c1', 'a1')['attributes'][0]['value'] = 'N2'
    find_atom(n, 'c1', 'a2')['attributes'].append({'name': 'flag', 'value': 'x'})
    good('U18', request(w, n, ['c1']), row(0, 'c1', 'needs_information', face=facets(a=attributes('changed', administrative=[diff('a1', 'code_list', ['N1'], ['N2'])],
                                                                                                undeclared=[diff('a2', 'flag', [], ['x'])])),
                                          requests=[attribute_request('c1', 'flag')], assumptions=['attribute_class:code_list:administrative']), 24, s4(needs_information=1))

    good('U19', request(w, world(), ['c1', 'c2'], policy=POL+[{'name': 'extra', 'class': 'definitional'}]), unchanged(0, 'c1') + unchanged(1, 'c2'), 30, base_summary,
         [check(['policy', 'attributes'], [{'name': 'code_list', 'class': 'administrative'}, {'name': 'extra', 'class': 'definitional'}, {'name': 'strength', 'class': 'definitional'}])])

    n = world()
    find_atom(n, 'c2', 'a3')['attributes'][0]['value'] = '20 mg'
    good('U20', request(w, n, ['c2'], policy=[]), row(0, 'c2', 'needs_information', face=facets(a=attributes('changed', undeclared=[diff('a3', 'strength', ['10 mg'], ['20 mg'])])),
                                                     requests=[attribute_request('c2', 'strength')]), 17, s4(needs_information=1))

    n = world()
    n = {k: n[k] for k in ['c9', 'c8', 'c2', 'c1']}
    n['c1']['atoms'].reverse()
    n['c1']['relations'].reverse()
    for a in n['c1']['atoms']:
        a['attributes'].reverse()
    good('U21', request(w, n, ['c1']), unchanged(0, 'c1'), 23, s4(unchanged_in_scope=1))

    old = world()
    old['c7'] = concept('c7', 'X', [atom('a7', 'full', 'omega')])
    new = world()
    new['c7'] = concept('c7', 'X', [atom('a7', 'full', 'omega2')])
    good('U22', request(old, new, ['c7'], sources=('S', 'X')),
         row(0, 'c7', 'changed', face=facets(n=names('changed', modified=[{'id': 'a7', 'from': {'kind': 'full', 'name': 'omega'}, 'to': {'kind': 'full', 'name': 'omega2'}}])), source='X'),
         15, summary(1, {'changed': 1}, 5, 5, 5, 5, 5))

    n = world()
    n['c2']['source'] = 'X'
    good('U23', request(w, n, ['c2']), missing(0, 'c2'), 14, summary(1, {'not_found': 1}, 4, 4, 4, 3, 3))

    old = world()
    del old['c9']
    old['c1']['relations'] = [r for r in old['c1']['relations'] if r['target'] != 'c9']
    old['c2']['relations'] = []
    arrived = relations('changed', added=[rel('has_ingredient', 'c9', False, True)])
    good('U24', request(old, world(), ['c1', 'c2']), row(0, 'c1', 'changed', face=facets(r=arrived)) + row(1, 'c2', 'changed', face=facets(r=arrived)), 27,
         summary(2, {'changed': 2}, 3, 4, 3, 4, 3))

    old = world()
    old['c3'] = concept('c3', 'S', [atom('a4', 'full', 'gamma 1 mg', [('strength', '1 mg')])])
    old['c7'] = concept('c7', 'X', [atom('a7', 'full', 'omega')])
    new = world()
    new['c7'] = concept('c7', 'X', [atom('a7', 'full', 'omega')])
    find_atom(new, 'c1', 'a2')['attributes'].append({'name': 'flag', 'value': 'x'})
    find_atom(new, 'c2', 'a3')['attributes'][0]['value'] = '20 mg'
    new['c9']['atoms'][0]['attributes'].append({'name': 'code_list', 'value': 'N9'})
    good('U25', request(old, new, ['c1', 'c2', 'c3', 'c7', 'c8', 'c9']),
         row(0, 'c1', 'needs_information', face=facets(a=attributes('changed', undeclared=[diff('a2', 'flag', [], ['x'])])), requests=[attribute_request('c1', 'flag')])
         + row(1, 'c2', 'changed', face=facets(a=attributes('changed', definitional=[diff('a3', 'strength', ['10 mg'], ['20 mg'])])), assumptions=['attribute_class:strength:definitional'])
         + missing(2, 'c3') + row(3, 'c7', 'not_compared', 'not_compared', None, source='X') + unchanged(4, 'c8')
         + row(5, 'c9', 'changed_administrative_only', face=facets(a=attributes('changed', administrative=[diff('a9', 'code_list', [], ['N9'])])),
               assumptions=['attribute_class:code_list:administrative']),
         45, summary(6, {'needs_information': 1, 'changed': 1, 'not_found': 1, 'not_compared': 1, 'unchanged_in_scope': 1, 'changed_administrative_only': 1}, 6, 5, 5, 4, 4))

    sha_old, sha_new = 'a'*64, 'b'*64
    good('U26', request(w, world(), ['c1', 'c2'], old_sha=sha_old, new_sha=sha_new), unchanged(0, 'c1') + unchanged(1, 'c2'), 30, base_summary,
         [check(['versions'], {'from': {'ref': REF, 'version': OLD_VERSION, 'source_sha256': sha_old}, 'to': {'ref': REF, 'version': NEW_VERSION, 'source_sha256': sha_new}})])

    n = world()
    n['c2']['source'] = 'X'
    good('U27', request(w, n, ['c2'], sources=('S', 'X')), missing(0, 'c2'), 14, summary(1, {'not_found': 1}, 4, 4, 4, 4, 3))

    # ---- 静的検査（N） ----
    base = u01
    for key in ('operation', 'consumer', 'from', 'to', 'scope', 'policy', 'references', 'budget'):
        broken = deepcopy(base)
        del broken[key]
        bad('N01-missing-'+key, broken, 'missing_field')
    broken = deepcopy(base)
    broken['extra'] = 1
    bad('N01-extra', broken, 'unknown_field')
    broken = deepcopy(base)
    broken['from'] = []
    bad('N01-from-not-object', broken, 'expected_object')
    for name, path, value, code in [('profile', 'profile', 'p2-other-draft-1', 'unsupported_profile'), ('profile_spec_sha256', 'profile_spec_sha256', '0'*64, 'profile_spec_mismatch')]:
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
    del broken['from']['concepts']
    bad('N04-concepts-missing', broken, 'missing_field')
    broken = deepcopy(base)
    broken['from']['concepts'] = {}
    bad('N04-concepts-not-array', broken, 'expected_array')
    broken = deepcopy(base)
    broken['to']['ref'] = 'fiction:terminology:other'
    bad('N05-system-mismatch', broken, 'system_mismatch', 'unsupported_profile')
    broken = deepcopy(base)
    broken['to']['version'] = OLD_VERSION
    bad('N06-same-version', broken, 'same_version')
    broken = deepcopy(base)
    broken['from']['concepts'].append(deepcopy(broken['from']['concepts'][0]))
    bad('N07-duplicate-concept', broken, 'duplicate_identifier')
    broken = deepcopy(base)
    broken['from']['concepts'][1]['atoms'][0]['id'] = 'a1'
    bad('N07-duplicate-atom', broken, 'duplicate_identifier')
    broken = deepcopy(base)
    broken['from']['concepts'][0]['relations'].append(deepcopy(broken['from']['concepts'][0]['relations'][0]))
    bad('N07-duplicate-relation', broken, 'duplicate_relation')
    broken = deepcopy(base)
    broken['from']['concepts'][0]['atoms'][0]['attributes'].append(deepcopy(broken['from']['concepts'][0]['atoms'][0]['attributes'][0]))
    bad('N07-duplicate-attribute', broken, 'duplicate_attribute')
    broken = deepcopy(base)
    broken['policy']['attributes'].append(deepcopy(broken['policy']['attributes'][0]))
    bad('N07-duplicate-policy', broken, 'duplicate_policy')
    broken = deepcopy(base)
    broken['references'] = ['c1', 'c1']
    bad('N07-duplicate-reference', broken, 'duplicate_reference')
    broken = deepcopy(base)
    broken['policy']['attributes'][0]['class'] = 'clinical'
    bad('N08-class', broken, 'unsupported_attribute_class', 'unsupported_profile')
    broken = deepcopy(base)
    broken['references'] = ['c1', 'c404']
    bad('N09-unresolved-reference', broken, 'unresolved_reference')
    broken = deepcopy(base)
    broken['references'] = []
    bad('N10-references-empty', broken, 'empty_collection')
    broken = deepcopy(base)
    broken['scope']['sources'] = []
    bad('N10-sources-empty', broken, 'empty_collection')
    broken = deepcopy(base)
    broken['references'] = ['c1']*257
    bad('N10-references-limit', broken, 'item_limit', 'resource_limit')
    broken = deepcopy(base)
    broken['from']['concepts'] = [concept('x'+str(i), 'S', []) for i in range(513)]
    bad('N10-concepts-limit', broken, 'item_limit', 'resource_limit')
    broken = deepcopy(base)
    broken['from']['concepts'][0]['atoms'] = [atom('z'+str(i), 'k', 'n') for i in range(33)]
    bad('N10-atoms-limit', broken, 'item_limit', 'resource_limit')
    broken = deepcopy(base)
    broken['policy']['attributes'] = [{'name': 'p'+str(i), 'class': 'definitional'} for i in range(65)]
    bad('N10-policy-limit', broken, 'item_limit', 'resource_limit')
    broken = deepcopy(base)
    broken['from']['concepts'][0]['atoms'][0]['kind'] = ''
    bad('N11-atom-kind-empty', broken, 'expected_nonempty_string')
    broken = deepcopy(base)
    broken['from']['concepts'][0]['source'] = 7
    bad('N11-concept-source-number', broken, 'expected_nonempty_string')
    broken = deepcopy(base)
    del broken['from']['concepts'][0]['relations'][0]['target']
    bad('N11-relation-target-missing', broken, 'missing_field')
    broken = deepcopy(base)
    broken['from']['concepts'][0]['atoms'][0]['attributes'][0]['extra'] = 1
    bad('N11-attribute-extra', broken, 'unknown_field')
    broken = deepcopy(base)
    broken['from']['concepts'][0]['atoms'][0]['attributes'][0]['value'] = 5
    bad('N11-attribute-value-not-string', broken, 'expected_string')
    broken = deepcopy(base)
    broken['from']['source_sha256'] = 'x'
    bad('N11-source-sha256', broken, 'invalid_sha256')
    for name, number in [('bool', True), ('negative', -1), ('limit', 100001)]:
        broken = deepcopy(base)
        broken['budget']['max_steps'] = number
        bad('N12-budget-'+name, broken, 'step_budget_limit' if name == 'limit' else 'invalid_step_budget', 'resource_limit' if name == 'limit' else 'invalid_input')

    # ---- 資源（B） ----
    def sweep(prefix, request_, refs, fees, builders, full_summary, base_paid, total, thresholds):
        for budget in thresholds:
            copy = deepcopy(request_)
            copy['budget']['max_steps'] = budget
            checks = [check(['status'], 'ok' if budget >= total else 'resource_limit'), check(['steps_used'], min(budget, total))]
            paid, left = base_paid, []
            for index, (ref, fee, build) in enumerate(zip(refs, fees, builders)):
                paid += fee
                if budget >= paid:
                    checks += build(index)
                else:
                    checks += unfinished(index, ref)
                    left.append(ref)
            incomplete = [{'reference': ref, 'reason_codes': ['step_limit']} for ref in left]
            if budget == total-1:
                incomplete.append({'stage': 'completion', 'reason_codes': ['step_limit']})
            checks += [check(['incomplete'], incomplete), check(['summary'], full_summary if budget >= total else None)]
            emit(prefix+'-'+str(budget), copy, checks)
    sweep('B01', u01, ['c1', 'c2'], [13, 7], [lambda i: unchanged(i, 'c1'), lambda i: unchanged(i, 'c2')], base_summary, 9, 30, [0, 1, 8, 9, 21, 22, 28, 29, 30])
    n = world()
    del n['c9']
    n['c1']['relations'] = [r for r in n['c1']['relations'] if r['target'] != 'c9']
    n['c2']['relations'] = []
    sweep('B02', request(w, n, ['c1', 'c2', 'c9']), ['c1', 'c2', 'c9'], [12, 6, 2],
          [lambda i: row(i, 'c1', 'changed', face=facets(r=gone)), lambda i: row(i, 'c2', 'changed', face=facets(r=gone)), lambda i: missing(i, 'c9')],
          summary(3, {'changed': 2, 'not_found': 1}, 4, 3, 4, 3, 3), 8, 29, [0, 1, 7, 8, 19, 20, 25, 26, 27, 28, 29])

    conditions = {letter: len({e['condition'] for e in entries if e['condition'][0] == letter}) for letter in 'UNB'}
    manifest = {'schema_version': 'p2-fixture-manifest-draft-1', 'suite': 'p2-audit', 'review_state': 'author_draft', 'independent_review': False,
                'evaluation_frozen': False, 'conditions': conditions, 'files': entries}
    (DIRECTORY/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'files': len(entries), 'checks': sum(len(json.loads((DIRECTORY/e['path']).read_text())['expected']['checks']) for e in entries), 'conditions': conditions}))


if __name__ == '__main__':
    main()
