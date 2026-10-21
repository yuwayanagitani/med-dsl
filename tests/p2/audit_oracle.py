"""用語の版更新の監査の別計算。native の面ごとの差の計算を読まず、要求の snapshot から集合の演算で自前に求める（概念は (出典, id) の組の集合、
原子は id の集合、関係は (種類, 対象) の集合、属性は (原子, 名前, 値) の三つ組の集合）。料金も自前の式で数える。nativeは読まない。"""


def pairs(snapshot):
    return {(c['source'], c['id']): c for c in snapshot['concepts']}


def ids(snapshot):
    return {c['id'] for c in snapshot['concepts']}


def counts(concept):
    atoms = len(concept['atoms'])
    attributes = sum(len(a['attributes']) for a in concept['atoms'])
    return atoms + attributes + len(concept['relations'])


def cost(request):
    sources = set(request['scope']['sources'])
    old, new = pairs(request['from']), pairs(request['to'])
    total = 1+len(request['from']['concepts'])+len(request['to']['concepts'])+1
    by_id = {c['id']: c for c in request['from']['concepts']}
    for reference in request['references']:
        concept = by_id[reference]
        if concept['source'] not in sources:
            total += 1
            continue
        total += 1+counts(concept)
        twin = new.get((concept['source'], reference))
        if twin is not None:
            total += counts(twin)
    return total


def triples(concept):
    return {(a['id'], x['name'], x['value']) for a in concept['atoms'] for x in a['attributes']}


def row(request, reference):
    sources = set(request['scope']['sources'])
    classes = {p['name']: p['class'] for p in request['policy']['attributes']}
    old_snapshot, new_snapshot = request['from'], request['to']
    concept = next(c for c in old_snapshot['concepts'] if c['id'] == reference)
    if concept['source'] not in sources:
        return {'presence': 'not_compared', 'audit_state': 'not_compared', 'facets': None, 'requests': [], 'policy_assumptions': [], 'successor': None, 'concept_source': concept['source']}
    twin = pairs(new_snapshot).get((concept['source'], reference))
    if twin is None:
        return {'presence': 'not_found', 'audit_state': 'not_found', 'facets': None, 'requests': [{'element': 'history', 'action': 'provide_official_history', 'reference': reference, 'name': None}],
                'policy_assumptions': [], 'successor': 'not_determined', 'concept_source': concept['source']}
    old_ids, new_ids = ids(old_snapshot), ids(new_snapshot)
    # 名称
    old_atoms, new_atoms = {a['id']: (a['kind'], a['name']) for a in concept['atoms']}, {a['id']: (a['kind'], a['name']) for a in twin['atoms']}
    name_added = [dict(id=i, kind=new_atoms[i][0], name=new_atoms[i][1]) for i in sorted(new_atoms.keys()-old_atoms.keys())]
    name_removed = [dict(id=i, kind=old_atoms[i][0], name=old_atoms[i][1]) for i in sorted(old_atoms.keys()-new_atoms.keys())]
    name_modified = [{'id': i, 'from': {'kind': old_atoms[i][0], 'name': old_atoms[i][1]}, 'to': {'kind': new_atoms[i][0], 'name': new_atoms[i][1]}}
                     for i in sorted(old_atoms.keys() & new_atoms.keys()) if old_atoms[i] != new_atoms[i]]
    names = {'state': 'changed' if (name_added or name_removed or name_modified) else 'unchanged', 'added': name_added, 'removed': name_removed, 'modified': name_modified}
    # 関係
    old_relations, new_relations = {(r['kind'], r['target']) for r in concept['relations']}, {(r['kind'], r['target']) for r in twin['relations']}
    flag = lambda pair: {'kind': pair[0], 'target': pair[1], 'target_in_from': pair[1] in old_ids, 'target_in_to': pair[1] in new_ids}
    relation_added = [flag(p) for p in sorted(new_relations-old_relations)]
    relation_removed = [flag(p) for p in sorted(old_relations-new_relations)]
    unresolved = [{'target': t, 'in_from': t in old_ids} for t in sorted({t for _, t in new_relations if t not in new_ids})]
    relation_changed = bool(relation_added or relation_removed or [u for u in unresolved if u['in_from']])
    relations = {'state': 'changed' if relation_changed else 'unchanged', 'added': relation_added, 'removed': relation_removed, 'unresolved_in_to': unresolved}
    # 属性（両版にある原子の三つ組）
    common = old_atoms.keys() & new_atoms.keys()
    old_triples = {t for t in triples(concept) if t[0] in common}
    new_triples = {t for t in triples(twin) if t[0] in common}
    changed_keys = sorted({(t[0], t[1]) for t in old_triples ^ new_triples})
    groups = {'definitional': [], 'administrative': [], 'undeclared': []}
    for atom, name in changed_keys:
        groups[classes.get(name, 'undeclared')].append({'atom': atom, 'name': name, 'from': sorted(v for a, n, v in old_triples if (a, n) == (atom, name)),
                                                         'to': sorted(v for a, n, v in new_triples if (a, n) == (atom, name))})
    only_new = new_atoms.keys()-old_atoms.keys()
    only_old = old_atoms.keys()-new_atoms.keys()
    attributes = {'state': 'changed' if changed_keys else 'unchanged', **groups,
                  'with_atom_change': {'added': len([t for t in triples(twin) if t[0] in only_new]), 'removed': len([t for t in triples(concept) if t[0] in only_old])}}
    if names['state'] == 'changed' or relations['state'] == 'changed' or groups['definitional']:
        state = 'changed'
    elif groups['undeclared']:
        state = 'needs_information'
    elif groups['administrative']:
        state = 'changed_administrative_only'
    else:
        state = 'unchanged_in_scope'
    used = {g['name'] for g in groups['definitional']+groups['administrative']}
    return {'presence': 'continues', 'audit_state': state, 'facets': {'names': names, 'relations': relations, 'attributes': attributes},
            'requests': [{'element': 'attribute', 'action': 'declare_attribute_class', 'reference': reference, 'name': n} for n in sorted({g['name'] for g in groups['undeclared']})],
            'policy_assumptions': sorted(f'attribute_class:{n}:{classes[n]}' for n in used), 'successor': None, 'concept_source': concept['source']}


def summary(request, rows):
    sources = set(request['scope']['sources'])
    old, new = pairs(request['from']), pairs(request['to'])
    in_old = {p for p in old if p[0] in sources}
    in_new = {p for p in new if p[0] in sources}
    states = ('unchanged_in_scope', 'changed_administrative_only', 'changed', 'needs_information', 'not_found', 'not_compared')
    return {'references': len(rows), 'by_state': {s: sum(1 for r in rows if r['audit_state'] == s) for s in states}, 'from_concepts': len(old), 'to_concepts': len(new),
            'in_scope_from': len(in_old), 'in_scope_to': len(in_new), 'continuing': len(in_old & in_new), 'from_only': len(in_old-in_new), 'to_only': len(in_new-in_old)}
