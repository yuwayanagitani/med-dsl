"""測定選択の参照計算。確認の到着順で状態を更新し、値は整数対の既存参照計算へ渡す。"""
import quantity_oracle as numbers

PROFILE='p2-measurement-binding-draft-1'
QPROFILE='p2-quantity-literal-draft-1'
PROPERTIES={'fiction:measurement:property:A@1':'k_a','fiction:measurement:property:A-other@1':'k_a','fiction:measurement:property:B@1':'k_b'}
DIMENSIONS={'u_base':'u','u_ten':'u','u_third':'u','u_hundred':'u','u_half':'u','v_base':'v','w_base':'w','w_hundredth':'w'}
KINDS={'k_a','k_b','k_c','k_ratio_a','k_ratio_b'}


def answer(req,view,query):
    slots=[query['slot_ref']] if query['kind']=='convert' else [query['left_slot_ref'],query['right_slot_ref']]
    records={r['id']:r for r in req['source']['records'] if r['recorded_at']<=view['as_of'] and r['slot_ref'] in slots}
    quantities={q['ref']:q['literal'] for q in req['source']['quantities']}
    reviewed={key:[r for r in req['source']['reviews'] if r['record_ref']==key and r['recorded_at']<=view['as_of']] for key in records}
    events=[]
    for key,record in records.items():
        if record['certainty']=='confirmed' and reviewed[key]:events.append((min(r['recorded_at'] for r in reviewed[key]),key))
    active=set();masked=set()
    for _,key in sorted(events):
        removed=set(records[key]['supersedes']);masked|=removed;active-=removed
        if key not in masked:active.add(key)
    candidates={s:sorted(key for key in active if records[key]['slot_ref']==s) for s in set(slots)}
    result={'status':'unassessed','reason_codes':[],'converted_domain':None,'relation_set':None,'certain_relation':None,
            'candidate_refs':candidates,'masked_records':sorted(masked),'selected':[]}
    if any(set(r['required_capabilities'])-{PROFILE} or set(quantities[r['quantity_ref']['ref']]['required_capabilities'])-{QPROFILE} for r in records.values()):
        return {**result,'reason_codes':['unknown_capability']}
    reasons={('no_adopted_measurement' if not ids else 'unresolved_measurement_conflict') for ids in candidates.values() if len(ids)!=1}
    if reasons:return {**result,'reason_codes':sorted(reasons)}
    chosen=[records[candidates[s][0]] for s in slots]
    for rec in chosen:
        if rec['property_ref'] not in PROPERTIES:reasons.add('unknown_property')
        for field,prefix in [('specimen','specimen'),('method','method'),('effective_at','effective_time')]:
            if rec[field]['kind'] in ('unknown','unspecified'):reasons.add(prefix+'_'+rec[field]['kind'])
        q=quantities[rec['quantity_ref']['ref']]
        if q['quantity_kind_ref'] not in KINDS:reasons.add('unknown_quantity_kind')
        if q['unit_ref'] not in DIMENSIONS:reasons.add('unknown_unit')
    if query['kind']=='convert' and query['target_unit_ref'] not in DIMENSIONS:reasons.add('unknown_unit')
    if reasons:return {**result,'reason_codes':sorted(reasons)}
    if query['kind']=='compare':
        for field,name in [('subject_ref','different_subject'),('property_ref','different_property'),('specimen','different_specimen'),('method','different_method'),('effective_at','different_effective_time')]:
            if chosen[0][field]!=chosen[1][field]:reasons.add(name)
        if reasons:return {**result,'status':'not_comparable','reason_codes':sorted(reasons)}
    qs=[quantities[r['quantity_ref']['ref']] for r in chosen]
    if query['kind']=='convert':
        if DIMENSIONS[qs[0]['unit_ref']]!=DIMENSIONS[query['target_unit_ref']]:return {**result,'status':'not_comparable','reason_codes':['incompatible_dimension']}
        value={'converted_domain':numbers.converted(qs[0],query['target_unit_ref'])}
    else:
        rels=numbers.relations(qs[0],qs[1],chosen[0]['id']==chosen[1]['id'])
        value={'relation_set':rels,'certain_relation':rels[0] if len(rels)==1 else None}
    return {**result,**value,'status':'computed','selected':sorted({r['id'] for r in chosen})}
