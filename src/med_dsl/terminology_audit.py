"""R5：用語の版更新の監査。旧版の参照（概念の id）ごとに、新版で同じ (出典, id) が続くか、続くなら名称・関係・属性の三つの面に何の差があるかを、
宣言した属性の方針のもとで報告する。後継は決めず、未宣言の属性の差は依頼にして分類しない。一方向（旧→新）で、逆向きは推定しない。"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from .model import Budget, Problem
from .validation import fields, string, strings, values

AUDIT_PROFILE = 'p2-terminology-audit-draft-1'
SPEC_SHA256 = '8291f2df3ad0cb07d650d05aae9bce7a9f716b6ee43f4347742a54dfb12c2ea4'
OPERATION = 'run_terminology_audit'
ANSWER_KIND = 'terminology_version_audit'
VALUE_FIELDS = ('concept_source', 'presence', 'audit_state', 'facets', 'requests', 'policy_assumptions', 'successor')
STATES = ('unchanged_in_scope', 'changed_administrative_only', 'changed', 'needs_information', 'not_found', 'not_compared')


def _unsupported(code, path):
    raise Problem(code, path, 'unsupported_profile')


def _spec():
    try:
        raw = Path(__file__).with_name('terminology_audit_spec.json').read_bytes()
    except OSError as error:
        raise Problem('native_spec_unavailable', 'native_spec') from error
    if hashlib.sha256(raw).hexdigest() != SPEC_SHA256:
        raise Problem('native_spec_mismatch', 'native_spec')
    return json.loads(raw)


def _consumer(consumer):
    fields(consumer, ('profile', 'profile_spec_sha256', 'operations'), path='consumer')
    for key, expected, code in [('profile', AUDIT_PROFILE, 'unsupported_profile'), ('profile_spec_sha256', SPEC_SHA256, 'profile_spec_mismatch')]:
        string(consumer[key], 'consumer.' + key)
        if key.endswith('sha256') and (len(consumer[key]) != 64 or any(c not in '0123456789abcdef' for c in consumer[key])):
            raise Problem('invalid_sha256', 'consumer.' + key)
        if consumer[key] != expected:
            _unsupported(code, 'consumer.' + key)
    strings(consumer['operations'], 64, 'consumer.operations')
    if consumer['operations'] != [OPERATION]:
        _unsupported('unsupported_operation', 'consumer.operations')


def _snapshot(snapshot, path, spec):
    limits = spec['limits']
    fields(snapshot, ('ref', 'version', 'concepts'), ('source_sha256',), path)
    string(snapshot['ref'], path + '.ref')
    string(snapshot['version'], path + '.version')
    if 'source_sha256' in snapshot:
        string(snapshot['source_sha256'], path + '.source_sha256')
        if len(snapshot['source_sha256']) != 64 or any(c not in '0123456789abcdef' for c in snapshot['source_sha256']):
            raise Problem('invalid_sha256', path + '.source_sha256')
    concepts, atom_ids = {}, set()
    for concept in values(snapshot['concepts'], limits['concepts'], path + '.concepts'):
        fields(concept, ('id', 'source', 'atoms', 'relations'), path=path + '.concept')
        string(concept['id'], path + '.concept.id')
        string(concept['source'], path + '.concept.source')
        if concept['id'] in concepts:
            raise Problem('duplicate_identifier', path + '.concepts')
        for atom in values(concept['atoms'], limits['atoms'], path + '.atoms'):
            fields(atom, ('id', 'kind', 'name', 'attributes'), path=path + '.atom')
            for key in ('id', 'kind', 'name'):
                string(atom[key], path + '.atom.' + key)
            if atom['id'] in atom_ids:
                raise Problem('duplicate_identifier', path + '.atoms')
            atom_ids.add(atom['id'])
            seen = set()
            for attribute in values(atom['attributes'], limits['attributes'], path + '.attributes'):
                fields(attribute, ('name', 'value'), path=path + '.attribute')
                string(attribute['name'], path + '.attribute.name')
                if type(attribute['value']) is not str:
                    raise Problem('expected_string', path + '.attribute.value')
                if (attribute['name'], attribute['value']) in seen:
                    raise Problem('duplicate_attribute', path + '.attributes')
                seen.add((attribute['name'], attribute['value']))
        seen = set()
        for relation in values(concept['relations'], limits['relations'], path + '.relations'):
            fields(relation, ('kind', 'target'), path=path + '.relation')
            string(relation['kind'], path + '.relation.kind')
            string(relation['target'], path + '.relation.target')
            if (relation['kind'], relation['target']) in seen:
                raise Problem('duplicate_relation', path + '.relations')
            seen.add((relation['kind'], relation['target']))
        concepts[concept['id']] = concept
    return concepts


def _validate(request):
    fields(request, ('schema_version', 'operation', 'consumer', 'from', 'to', 'scope', 'policy', 'references', 'budget'))
    spec = _spec()
    if request['operation'] != OPERATION:
        _unsupported('unsupported_operation', 'operation')
    _consumer(request['consumer'])
    fields(request['budget'], ('max_steps',), path='budget')
    maximum = request['budget']['max_steps']
    if type(maximum) is not int or maximum < 0:
        raise Problem('invalid_step_budget', 'budget.max_steps')
    if maximum > spec['limits']['max_steps']:
        raise Problem('step_budget_limit', 'budget.max_steps', 'resource_limit')
    old, new = request['from'], request['to']
    if type(old) is not dict:
        raise Problem('expected_object', 'from')
    if type(new) is not dict:
        raise Problem('expected_object', 'to')
    old_concepts, new_concepts = _snapshot(old, 'from', spec), _snapshot(new, 'to', spec)
    if old['ref'] != new['ref']:
        _unsupported('system_mismatch', 'to.ref')
    if old['version'] == new['version']:
        raise Problem('same_version', 'to.version')
    fields(request['scope'], ('sources',), path='scope')
    sources = values(request['scope']['sources'], spec['limits']['sources'], 'scope.sources')
    if not sources:
        raise Problem('empty_collection', 'scope.sources')
    strings(sources, spec['limits']['sources'], 'scope.sources')
    fields(request['policy'], ('attributes',), path='policy')
    classes = {}
    for item in values(request['policy']['attributes'], spec['limits']['policy'], 'policy.attributes'):
        fields(item, ('name', 'class'), path='policy.attribute')
        string(item['name'], 'policy.attribute.name')
        string(item['class'], 'policy.attribute.class')
        if item['class'] not in spec['attribute_classes']:
            _unsupported('unsupported_attribute_class', 'policy.attribute.class')
        if item['name'] in classes:
            raise Problem('duplicate_policy', 'policy.attributes')
        classes[item['name']] = item['class']
    references = values(request['references'], spec['limits']['references'], 'references')
    if not references:
        raise Problem('empty_collection', 'references')
    strings(references, spec['limits']['references'], 'references')
    if any(reference not in old_concepts for reference in references):
        raise Problem('unresolved_reference', 'references')
    return {'spec': spec, 'from': old, 'to': new, 'from_concepts': old_concepts, 'to_concepts': new_concepts, 'sources': set(sources),
            'classes': classes, 'references': sorted(references)}


def _counts(concept):
    atoms = concept['atoms']
    return len(atoms), sum(len(atom['attributes']) for atom in atoms), len(concept['relations'])


def reference_fee(reference, old_concepts, new_concepts, sources):
    """参照ごとの料金（設計82の UD9）。"""
    concept = old_concepts[reference]
    if concept['source'] not in sources:
        return 1
    fee = 1 + sum(_counts(concept))
    twin = new_concepts.get(reference)
    if twin is not None and twin['source'] == concept['source']:
        fee += sum(_counts(twin))
    return fee


def _names(old, new):
    old_atoms, new_atoms = {a['id']: a for a in old['atoms']}, {a['id']: a for a in new['atoms']}
    shown = lambda a: {'id': a['id'], 'kind': a['kind'], 'name': a['name']}
    added = [shown(new_atoms[i]) for i in sorted(set(new_atoms) - set(old_atoms))]
    removed = [shown(old_atoms[i]) for i in sorted(set(old_atoms) - set(new_atoms))]
    modified = [{'id': i, 'from': {'kind': old_atoms[i]['kind'], 'name': old_atoms[i]['name']}, 'to': {'kind': new_atoms[i]['kind'], 'name': new_atoms[i]['name']}}
                for i in sorted(set(old_atoms) & set(new_atoms)) if (old_atoms[i]['kind'], old_atoms[i]['name']) != (new_atoms[i]['kind'], new_atoms[i]['name'])]
    return {'state': 'changed' if added or removed or modified else 'unchanged', 'added': added, 'removed': removed, 'modified': modified}, old_atoms, new_atoms


def _relations(old, new, old_ids, new_ids):
    old_set, new_set = {(r['kind'], r['target']) for r in old['relations']}, {(r['kind'], r['target']) for r in new['relations']}
    shown = lambda kind, target: {'kind': kind, 'target': target, 'target_in_from': target in old_ids, 'target_in_to': target in new_ids}
    added = [shown(*pair) for pair in sorted(new_set - old_set)]
    removed = [shown(*pair) for pair in sorted(old_set - new_set)]
    unresolved = [{'target': target, 'in_from': target in old_ids} for target in sorted({t for _, t in new_set if t not in new_ids})]
    changed = bool(added or removed or any(item['in_from'] for item in unresolved))
    return {'state': 'changed' if changed else 'unchanged', 'added': added, 'removed': removed, 'unresolved_in_to': unresolved}


def _attributes(old_atoms, new_atoms, classes):
    groups = {'definitional': [], 'administrative': [], 'undeclared': []}
    for atom_id in sorted(set(old_atoms) & set(new_atoms)):
        old_values, new_values = {}, {}
        for attribute in old_atoms[atom_id]['attributes']:
            old_values.setdefault(attribute['name'], set()).add(attribute['value'])
        for attribute in new_atoms[atom_id]['attributes']:
            new_values.setdefault(attribute['name'], set()).add(attribute['value'])
        for name in sorted(set(old_values) | set(new_values)):
            before, after = sorted(old_values.get(name, ())), sorted(new_values.get(name, ()))
            if before != after:
                groups[classes.get(name, 'undeclared')].append({'atom': atom_id, 'name': name, 'from': before, 'to': after})
    with_change = {'added': sum(len(new_atoms[i]['attributes']) for i in set(new_atoms) - set(old_atoms)),
                   'removed': sum(len(old_atoms[i]['attributes']) for i in set(old_atoms) - set(new_atoms))}
    return {'state': 'changed' if any(groups.values()) else 'unchanged', **groups, 'with_atom_change': with_change}


def audit_reference(reference, old_concepts, new_concepts, sources, classes, spec):
    """一つの参照の行（予算を使わない核）。"""
    concept = old_concepts[reference]
    row = {'reference': reference, 'assessment_complete': True, 'reason_codes': []}
    if concept['source'] not in sources:
        return {**row, 'concept_source': concept['source'], 'presence': 'not_compared', 'audit_state': 'not_compared', 'facets': None, 'requests': [], 'policy_assumptions': [], 'successor': None}
    twin = new_concepts.get(reference)
    if twin is None or twin['source'] != concept['source']:
        history = {'element': 'history', 'action': spec['requests']['history'], 'reference': reference, 'name': None}
        return {**row, 'concept_source': concept['source'], 'presence': 'not_found', 'audit_state': 'not_found', 'facets': None, 'requests': [history], 'policy_assumptions': [],
                'successor': 'not_determined'}
    names, old_atoms, new_atoms = _names(concept, twin)
    relations = _relations(concept, twin, old_concepts, new_concepts)
    attributes = _attributes(old_atoms, new_atoms, classes)
    if names['state'] == 'changed' or relations['state'] == 'changed' or attributes['definitional']:
        state = 'changed'
    elif attributes['undeclared']:
        state = 'needs_information'
    elif attributes['administrative']:
        state = 'changed_administrative_only'
    else:
        state = 'unchanged_in_scope'
    requests = [{'element': 'attribute', 'action': spec['requests']['attribute'], 'reference': reference, 'name': name}
                for name in sorted({entry['name'] for entry in attributes['undeclared']})]
    used = {entry['name'] for entry in attributes['definitional'] + attributes['administrative']}
    return {**row, 'concept_source': concept['source'], 'presence': 'continues', 'audit_state': state, 'facets': {'names': names, 'relations': relations, 'attributes': attributes},
            'requests': requests, 'policy_assumptions': sorted(f'attribute_class:{name}:{classes[name]}' for name in used), 'successor': None}


def summarize(rows, old_concepts, new_concepts, sources):
    in_old = {i for i, c in old_concepts.items() if c['source'] in sources}
    in_new = {i for i, c in new_concepts.items() if c['source'] in sources}
    continuing = {i for i in in_old & in_new if old_concepts[i]['source'] == new_concepts[i]['source']}
    by_state = {state: 0 for state in STATES}
    for row in rows:
        by_state[row['audit_state']] += 1
    return {'references': len(rows), 'by_state': by_state, 'from_concepts': len(old_concepts), 'to_concepts': len(new_concepts), 'in_scope_from': len(in_old),
            'in_scope_to': len(in_new), 'continuing': len(continuing), 'from_only': len(in_old) - len(continuing), 'to_only': len(in_new) - len(continuing)}


def run_audit(request):
    prepared = _validate(request)
    spec, classes, sources = prepared['spec'], prepared['classes'], prepared['sources']
    old_concepts, new_concepts = prepared['from_concepts'], prepared['to_concepts']
    rows = [{'reference': reference, 'assessment_complete': False, 'reason_codes': ['step_limit'], **dict.fromkeys(VALUE_FIELDS)} for reference in prepared['references']]
    version = lambda snapshot: {'ref': snapshot['ref'], 'version': snapshot['version'], 'source_sha256': snapshot.get('source_sha256')}
    result = {'status': 'ok', 'meaning_mode': ANSWER_KIND, 'direction': 'from_to', 'reverse_inferred': False,
              'versions': {'from': version(prepared['from']), 'to': version(prepared['to'])},
              'scope': {'sources': sorted(sources), 'facets': list(spec['facets']), 'not_compared': list(spec['not_compared'])},
              'policy': {'attributes': [{'name': name, 'class': classes[name]} for name in sorted(classes)]}, 'summary': None, 'results': rows, 'reason_codes': [],
              'clinical_confirmation': 'not_evaluated', 'review_verification': 'not_applicable', 'uncertainty_propagated': False, 'converted_to_base': False,
              'clinical_assertions_added': [], 'inferred_information': [],
              'certificate': {'status': 'not_certified', 'evidence_level': 'known_policy_change', 'reason_codes': ['terminology_audit_is_diagnostic'], 'scope': None}}
    budget = Budget(request['budget']['max_steps'])
    stage, current = 'index', None
    try:
        budget.tick()
        for _ in range(len(old_concepts) + len(new_concepts)):
            budget.tick()
        stage = 'references'
        for row in rows:
            current = row
            for _ in range(reference_fee(row['reference'], old_concepts, new_concepts, sources)):
                budget.tick()
            row.update(audit_reference(row['reference'], old_concepts, new_concepts, sources, classes, spec))
        current, stage = None, 'completion'
        budget.tick()
        result['summary'] = summarize(rows, old_concepts, new_concepts, sources)
    except Problem as problem:
        if problem.status != 'resource_limit':
            raise
        result.update(status='resource_limit', reason_codes=[problem.code])
        result['certificate']['reason_codes'] = [problem.code]
        for row in rows:
            if not row['assessment_complete'] and (stage == 'index' or row is current):
                row['reason_codes'] = [problem.code]
    result['steps_used'] = budget.used
    result['incomplete'] = [{'reference': r['reference'], 'reason_codes': r['reason_codes']} for r in rows if not r['assessment_complete']]
    if result['status'] == 'resource_limit' and stage == 'completion':
        result['incomplete'].append({'stage': 'completion', 'reason_codes': result['reason_codes']})
    return result
