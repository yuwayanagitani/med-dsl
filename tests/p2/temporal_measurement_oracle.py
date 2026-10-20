"""期間つき数量主張の別計算。区間差引きと確認の到着順、整数対の換算を使う。"""
import quantity_oracle as numbers

PROFILE='p2-temporal-measurement-draft-1'
QPROFILE='p2-quantity-literal-draft-1'
PROPERTIES={'fiction:measurement:property:A@1':'k_a','fiction:measurement:property:A-other@1':'k_a','fiction:measurement:property:B@1':'k_b'}
UNITS={'u_base':'u','u_ten':'u','u_third':'u','u_half':'u','v_base':'v','w_base':'w','w_hundredth':'w'}
KINDS={'k_a','k_b','k_c','k_ratio_a','k_ratio_b'}


def subtract(parts,cut):
    result=[]
    for start,end in parts:
        lo,hi=max(start,cut[0]),min(end,cut[1])
        if lo>=hi:result.append((start,end))
        else:
            if start<lo:result.append((start,lo))
            if hi<end:result.append((hi,end))
    return result


def selection(req,view,query):
    records={r['id']:r for r in req['source']['records'] if r['slot_ref']==query['slot_ref'] and r['recorded_at']<=view['as_of']}
    eligible=set();confirmations={}
    for review in sorted(req['source']['reviews'],key=lambda r:(r['recorded_at'],r['id'])):
        key=review['record_ref']
        if key in records and review['recorded_at']<=view['as_of']:
            confirmations.setdefault(key,[]).append(review['id'])
            if records[key]['certainty']=='confirmed':eligible.add(key)
    domains={key:[(r['validity']['start'],r['validity']['end'])] if r['validity']['kind']=='bounded' else [] for key,r in records.items()}
    remaining={key:list(domains[key]) for key in eligible};removed={key:[] for key in records}
    for key in sorted(eligible):
        record=records[key]
        for cut in domains[key]:
            for old in record['revises']:
                removed[old].append(cut)
                if old in remaining:remaining[old]=subtract(remaining[old],cut)
    target=query['target_at']
    inside=lambda parts:any(lo<=target<hi for lo,hi in parts)
    return records,eligible,confirmations,sorted(key for key,parts in remaining.items() if inside(parts)),sorted(key for key,parts in removed.items() if inside(parts))


def answer(req,view,query):
    records,eligible,confirmations,candidates,masked=selection(req,view,query)
    quantities={q['ref']:q['literal'] for q in req['source']['quantities']}
    result={'status':'unassessed','reason_codes':[],'converted_domain':None,'selected':[],
            'candidate_refs':{query['slot_ref']:candidates},'masked_records':masked}
    if any(set(r['required_capabilities'])-{PROFILE} or set(quantities[r['quantity_ref']['ref']]['required_capabilities'])-{QPROFILE} for r in records.values()):
        return {**result,'reason_codes':['unknown_capability']}
    reasons={'validity_'+records[key]['validity']['kind'] for key in eligible if records[key]['validity']['kind'] in ('unknown','unspecified')}
    if reasons:return {**result,'reason_codes':sorted(reasons)}
    if len(candidates)!=1:return {**result,'reason_codes':['no_adopted_measurement' if not candidates else 'unresolved_measurement_conflict']}
    key=candidates[0];record=records[key];literal=quantities[record['quantity_ref']['ref']]
    if record['property_ref'] not in PROPERTIES:reasons.add('unknown_property')
    for field in ('specimen','method'):
        if record[field]['kind']!='known':reasons.add(field+'_'+record[field]['kind'])
    if literal['quantity_kind_ref'] not in KINDS:reasons.add('unknown_quantity_kind')
    if literal['unit_ref'] not in UNITS or query['target_unit_ref'] not in UNITS:reasons.add('unknown_unit')
    if reasons:return {**result,'reason_codes':sorted(reasons)}
    if UNITS[literal['unit_ref']]!=UNITS[query['target_unit_ref']]:return {**result,'status':'not_comparable','reason_codes':['incompatible_dimension']}
    return {**result,'status':'computed','converted_domain':numbers.converted(literal,query['target_unit_ref']),'selected':[key]}


def cost(req):
    source=req['source'];total=1+len(source['slots'])+len(source['quantities'])
    for view in req['views']:
        total+=len(source['records'])+len(source['reviews'])
        for query in req['queries']:
            records,eligible,_,_,_=selection(req,view,query)
            total+=10+len(records)+sum(len(records[key]['revises']) for key in eligible)
    return total
