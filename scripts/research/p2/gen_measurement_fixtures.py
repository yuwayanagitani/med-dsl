#!/usr/bin/env python3
"""文書38の手指定期待を展開。runtimeをimportせず、出力から期待を作らない。"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).parent))
import gen_quantity_fixtures as literals
ROOT=Path(os.environ.get('P2_REPO') or Path(__file__).resolve().parents[3]).resolve()
DIRECTORY=ROOT/'examples/p2-measurement'
PROFILE='p2-measurement-binding-draft-1'
SPEC=hashlib.sha256((ROOT/'src/med_dsl/measurement_spec.json').read_bytes()).hexdigest()
QPROFILE='p2-quantity-literal-draft-1'
QSPEC=hashlib.sha256((ROOT/'src/med_dsl/quantity_spec.json').read_bytes()).hexdigest()
POLICY='fiction:reviewed-measurement-record@1'


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def hour(n):return f'2026-10-20T{n:02}:00:00Z'


def wrapper(ref='Q',magnitude=None,unit='u_ten',kind='k_a'):
    return {'ref':ref,'profile':QPROFILE,'profile_spec_sha256':QSPEC,
            'literal':literals.quantity(ref,deepcopy(magnitude if magnitude is not None else literals.point(2)),unit,kind)}


def record(ident='A',slot='S',qref='Q',revises=(),rec=None):
    return {'id':ident,'kind':'measurement','slot_ref':slot,'subject_ref':'u',
            'property_ref':'fiction:measurement:property:A@1',
            'specimen':{'kind':'known','ref':'fiction:specimen:s','version':'1'},
            'method':{'kind':'known','ref':'fiction:method:m','version':'1'},
            'effective_at':{'kind':'instant','at':hour(1)},'quantity_ref':{'ref':qref,'sha256':'0'*64},
            'certainty':'confirmed','recorded_at':hour(rec if rec is not None else {'A':2,'B':4,'C':6}.get(ident,2)),
            'origin':{'kind':'observed','ref':'fiction:measurement:origin:'+ident},
            'required_capabilities':[PROFILE],'supersedes':list(revises),
            **({'change_reason':'架空の測定記録の明示訂正'} if revises else {})}


def review(ident='A',at=None):
    return {'id':'R'+ident,'record_ref':ident,'record_sha256':'0'*64,'reviewer_ref':'fiction:human:reviewer',
            'reviewer_kind':'human','recorded_at':hour(at if at is not None else {'A':3,'B':5,'C':7}.get(ident,3)),'outcome':'confirmed'}


def record_hash(source,rec):
    return digest({'binding_profile':PROFILE,'binding_spec_sha256':SPEC,'source_ref':source['ref'],'record':rec})


def seal(req):
    quantities={q['ref']:q for q in req['source']['quantities']};records={r['id']:r for r in req['source']['records']}
    for rec in records.values():
        rec['quantity_ref']['sha256']=digest(quantities[rec['quantity_ref']['ref']])
    for rev in req['source']['reviews']:rev['record_sha256']=record_hash(req['source'],records[rev['record_ref']])
    return req


def convert(slot='S',target='u_base',ident='q'):
    return {'id':ident,'kind':'convert','slot_ref':slot,'target_unit_ref':target}


def compare(left='S',right='T',ident='q'):
    return {'id':ident,'kind':'compare','left_slot_ref':left,'right_slot_ref':right,'comparison_scope':'matched_context'}


def request(quantities=None,records=None,reviews=None,slots=None,queries=None,k=5,budget=100000):
    req={'schema_version':'p2-measurement-request-draft-1','operation':'evaluate_measurements',
         'consumer':{'profile':PROFILE,'profile_spec_sha256':SPEC,'operations':['evaluate_measurements'],
                     'quantity_profile':QPROFILE,'quantity_profile_spec_sha256':QSPEC},
         'source':{'schema_version':'p2-measurement-ledger-draft-1','ref':'fiction:measurement:source@1',
                   'slots':deepcopy(slots if slots is not None else [{'id':'S','subject_ref':'u'}]),
                   'quantities':deepcopy(quantities if quantities is not None else [wrapper()]),
                   'records':deepcopy(records if records is not None else [record()]),
                   'reviews':deepcopy(reviews if reviews is not None else [review()])},
         'views':[{'id':'v','as_of':hour(k),'policy_ref':POLICY}],
         'queries':deepcopy(queries if queries is not None else [convert()]),'budget':{'max_steps':budget}}
    return seal(req)


def pair(shared=False):
    quantities=[wrapper('Q',literals.interval(1,2),'u_base')] if shared else [wrapper('Q',literals.point(1)),wrapper('QT',literals.point(10),'u_base')]
    return request(quantities,[record(),record('B','T','Q' if shared else 'QT')],[review(),review('B')],
                   [{'id':'S','subject_ref':'u'},{'id':'T','subject_ref':'u'}],[compare()])


def check(path,value):return {'path':path,'equals':value}


def row(status='computed',value=None,relations=None,reasons=(),index=0,complete=True):
    p=['results',index]
    result=[check(p+['status'],status),check(p+['assessment_complete'],complete),
            check(p+['converted_domain'],None if value is None else literals.domain(*value)),
            check(p+['relation_set'],relations),check(p+['certain_relation'],relations[0] if relations and len(relations)==1 else None),
            check(p+['reason_codes'],sorted(reasons))]
    if status!='computed':result += [check(p+['binding_evidence'],None),check(p+['calculation_evidence'],None)]
    if not complete:result += [check(p+['diagnostics'],None)]
    return result


def main():
    DIRECTORY.mkdir(parents=True,exist_ok=True);entries=[]
    def emit(name,condition,req,checks,normal=True):
        checks=deepcopy(checks)
        if normal:checks += [check(['meaning_mode'],'measurement_literal_projection'),check(['converted_to_base'],False),
            check(['clinical_assertions_added'],[]),check(['clinical_confirmation'],'not_evaluated'),check(['uncertainty_propagated'],False),
            check(['review_verification'],'structural_only'),check(['certificate','status'],'not_certified'),check(['retained_source'],req['source'])]
        data={'schema_version':'p1-fixture-draft-1','fixture_version':1,'fixture_id':name,'condition':condition,'fictional':True,
              'review_state':'author_draft','request':deepcopy(req),'expected':{'comparison':'required_paths','checks':checks}}
        raw=(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode();filename=name.lower()+'.json';(DIRECTORY/filename).write_bytes(raw)
        entries.append({'fixture_id':name,'condition':condition,'path':filename,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
    def good(name,req,selected=None,value=((20,1),),relations=None,status='computed',reasons=(),extra=()):
        checks=[check(['status'],'ok'),*row(status,value if status=='computed' else None,relations,reasons),*extra]
        if selected is not None:checks += [check(['results',0,'binding_evidence','selected',0,'record_ref'],selected)]
        emit(name,name[:3],req,checks)
    def stop(name,req,*reasons):good(name,req,value=None,status='unassessed',reasons=reasons)
    good('M01',request(),'A')
    stop('M02',request(reviews=[]),'no_adopted_measurement')
    stop('M03',request(quantities=[],records=[],reviews=[]),'no_adopted_measurement')
    stop('M04',request(records=[record(rec=6)],reviews=[review(at=7)]),'no_adopted_measurement')
    stop('M05-before',request(reviews=[review(at=6)]),'no_adopted_measurement');good('M05-at',request(reviews=[review(at=6)],k=6),'A')
    req=request();req['source']['records'][0]['certainty']='suspected';stop('M06',seal(req),'no_adopted_measurement')
    req=request(reviews=[]);req['source']['records'][0]['origin']['kind']='ai_candidate';req['source']['quantities'][0]['literal']['origin']['kind']='ai_candidate';seal(req)
    stop('M07',req,'no_adopted_measurement');req['source']['reviews']=[review()];good('M08',seal(req),'A')
    quantities=[wrapper(),wrapper('QB',literals.point(3)),wrapper('QC',literals.point(4))]
    records=[record(),record('B',qref='QB',revises=['A']),record('C',qref='QC',revises=['B'])]
    good('M09',request(quantities[:2],records[:2],[review()]),'A')
    good('M10-before',request(quantities[:2],records[:2],[review(),review('B')],k=4),'A')
    good('M10-at',request(quantities[:2],records[:2],[review(),review('B')]),'B',((30,1),))
    good('M11',request(quantities,records,[review(),review('B'),review('C')],k=8),'C',((40,1),))
    stop('M12-before',request(quantities,records,[review(),review('C')],k=8),'unresolved_measurement_conflict')
    good('M12-after',request(quantities,records,[review(),review('C'),review('B',9)],k=9),'C',((40,1),))
    fork=[record(),record('B',qref='QB')]
    stop('M13',request(quantities[:2],fork,[review(),review('B')]),'unresolved_measurement_conflict')
    stop('M14',request(records=[record(),record('B')],reviews=[review(),review('B')]),'unresolved_measurement_conflict')
    good('M15',request(quantities,[*fork,record('C',qref='QC',revises=['A','B'])],[review(),review('B'),review('C')],k=8),'C',((40,1),))
    for num,field,kind,reason in [(16,'method','unknown','method_unknown'),(17,'method','unspecified','method_unspecified'),
        (18,'specimen','unknown','specimen_unknown'),(19,'specimen','unspecified','specimen_unspecified'),
        (20,'effective_at','unknown','effective_time_unknown'),(21,'effective_at','unspecified','effective_time_unspecified')]:
        req=request();req['source']['records'][0][field]={'kind':kind};stop(f'M{num:02}',seal(req),reason)
        if num==16:req['queries']=[compare('S','S')];stop('M16-alias',req,reason)
    for state in ['pending','masked']:
        for place in ['record','quantity']:
            req=request(quantities[:2],records[:2],[review()] if state=='pending' else [review(),review('B')])
            index=1 if state=='pending' else 0
            item=req['source']['records'][index] if place=='record' else req['source']['quantities'][index]['literal']
            item['required_capabilities'].append('fiction:unknown');stop('M22-'+state+'-'+place,seal(req),'unknown_capability')
    req=pair();req['queries']=[convert()];req['source']['records'][1]['required_capabilities'].append('fiction:future');good('M23-other',seal(req),'A',((10,1),))
    req=request(quantities[:2],[record(),record('B',qref='QB',rec=6)],[review(),review('B',7)]);req['source']['records'][1]['required_capabilities'].append('fiction:future');good('M23-future',seal(req),'A')
    good('M24',pair(),value=None,relations=['equal'])
    good('M25',pair(True),value=None,relations=['less','equal','greater'])
    good('M26',request([wrapper('Q',literals.interval(1,2),'u_base')],queries=[compare('S','S')]),value=None,relations=['equal'])
    for num,field,reason in [(27,'subject_ref','different_subject'),(28,'property_ref','different_property'),
                              (29,'specimen','different_specimen'),(30,'method','different_method'),(31,'effective_at','different_effective_time')]:
        req=pair();r=req['source']['records'][1]
        if num==27:r[field]='v';req['source']['slots'][1]['subject_ref']='v'
        elif num==28:r[field]='fiction:measurement:property:A-other@1'
        elif num==31:r[field]={'kind':'instant','at':hour(2)}
        else:r[field]['ref']='fiction:other'
        good(f'M{num:02}',seal(req),status='not_comparable',reasons=[reason])
        if num in [29,30]:
            req=pair();req['source']['records'][1][field]['version']='2';good(f'M{num:02}-version',seal(req),status='not_comparable',reasons=[reason])
    for variant,reason in [('property','unknown_property'),('kind','unknown_quantity_kind'),('unit','unknown_unit'),('target','unknown_unit')]:
        req=request()
        if variant=='property':req['source']['records'][0]['property_ref']='fiction:future'
        elif variant=='target':req['queries'][0]['target_unit_ref']='future'
        else:req['source']['quantities'][0]['literal']['quantity_kind_ref' if variant=='kind' else 'unit_ref']='future'
        stop('M32-'+variant,seal(req),reason)
    req=request();req['source']['quantities'][0]['literal']['unit_ref']='future';req['queries']=[compare('S','S')];stop('M32-alias',seal(req),'unknown_unit')
    req=request();req['source']['records'][0]['property_ref']='future';q=req['source']['quantities'][0]['literal'];q['quantity_kind_ref']='future';q['unit_ref']='future';stop('M32-multiple',seal(req),'unknown_property','unknown_quantity_kind','unknown_unit')
    r0=record();r0['method']={'kind':'unknown'}
    stop('M33-before',request(records=[r0,record('B',revises=['A'])],reviews=[review()]),'method_unknown')
    good('M33-after',request(records=[r0,record('B',revises=['A'])],reviews=[review(),review('B')]),'B')
    for field in ['value','property_ref','specimen','method','effective_at']:
        req=request(quantities[:2],[record(),record('B',revises=['A'])],[review(),review('B')]);r=req['source']['records'][1]
        if field=='value':r['quantity_ref']['ref']='QB'
        elif field=='property_ref':r[field]='fiction:measurement:property:A-other@1'
        elif field=='effective_at':r[field]={'kind':'instant','at':hour(2)}
        else:r[field]['version']='2'
        seal(req);good('M34-'+field,req,'B',((30 if field=='value' else 20,1),));req['views'][0]['as_of']=hour(3);good('M34-'+field+'-past',req,'A')
    for suffix,mag,unit,out in [('negative',literals.point(-3),'u_half',((-3,2),)),('unreduced',literals.point(2,4),'u_ten',((5,1),)),
                               ('interval',literals.interval(1,2,False,True),'u_ten',((10,1),(20,1),False,True))]:
        good('M35-'+suffix,request([wrapper(magnitude=mag,unit=unit)]),'A',out)
    good('M36-old',request(),'A')
    req=request(quantities[:2],[record(),record('B',qref='QB',revises=['A'],rec=6)],[review(),review('B',7)])
    good('M36-past',req,'A');req['views'][0]['as_of']=hour(8);good('M36-now',req,'B',((30,1),))
    def bad(name,req,code,status='invalid_input'):emit(name,name[:3],req,[check(['status'],status),check(['reason_codes'],[code])],False)
    for field in ['source','consumer','budget']:
        req=request();del req[field];bad('N01-'+field,req,'missing_field')
    req=request();req['source']['records'][0]['method']=None;bad('N01-null',req,'expected_object')
    req=request();req['clinical_confirmation']=True;bad('N01-extra',req,'unknown_field')
    for table in ['slots','quantities','records','reviews']:
        req=request();req['source'][table].append(deepcopy(req['source'][table][0]));bad('N02-duplicate-'+table,req,'duplicate_identifier')
    req=request();req['queries'][0]['slot_ref']='missing';bad('N02-slot',req,'unresolved_slot')
    req=request();req['source']['records'][0]['quantity_ref']['ref']='missing';bad('N02-quantity',req,'unresolved_quantity')
    req=request();req['source']['quantities'][0]['literal']['id']='wrong';bad('N02-literal-id',req,'literal_identifier_mismatch')
    for field in ['unit_ref','magnitude','origin','required_capabilities']:
        req=request();q=req['source']['quantities'][0]['literal']
        if field=='unit_ref':q[field]='u_base'
        elif field=='magnitude':q[field]=literals.point(3)
        elif field=='origin':q[field]['kind']='imported_literal'
        else:q[field].append('future')
        bad('N03-'+field,req,'quantity_reference_hash_mismatch')
    for field in ['method','specimen','effective_at','property_ref','origin','certainty','recorded_at','subject_ref']:
        req=request();r=req['source']['records'][0]
        if field in ['method','specimen']:r[field]['version']='2'
        elif field=='effective_at':r[field]['at']=hour(2)
        elif field=='property_ref':r[field]='fiction:measurement:property:A-other@1'
        elif field=='origin':r[field]['kind']='imported'
        elif field=='certainty':r[field]='suspected'
        elif field=='recorded_at':r[field]=hour(1)
        else:r[field]='v';req['source']['slots'][0]['subject_ref']='v'
        bad('N04-'+field,req,'review_record_hash_mismatch')
    for field,value,code in [('reviewer_kind','ai','invalid_review'),('outcome','rejected','invalid_review'),('recorded_at',hour(1),'review_precedes_record')]:
        req=request();req['source']['reviews'][0][field]=value;bad('N05-'+field,req,code)
    req=request();req['source']['records'][0]['certainty']='future';bad('N05-certainty',req,'invalid_certainty')
    for suffix,target in [('self','A'),('unresolved','missing')]:
        req=request();r=req['source']['records'][0];r['supersedes']=[target];r['change_reason']='架空の訂正';seal(req);bad('N06-'+suffix,req,'invalid_revision' if suffix=='self' else 'unresolved_revision')
    req=request();req['source']['records'][0]['subject_ref']='other';seal(req);bad('N06-subject',req,'slot_subject_mismatch')
    req=pair();r=req['source']['records'][1];r['supersedes']=['A'];r['change_reason']='架空';seal(req);bad('N06-cross-slot',req,'invalid_revision')
    for suffix,mag,code,status in [('denominator',literals.point(1,0),'invalid_rational','invalid_input'),('bool',literals.point(True),'invalid_rational','invalid_input'),
        ('bits',literals.point(2**63),'rational_integer_limit','resource_limit'),('empty',literals.interval(1,1,False,True),'invalid_interval','invalid_input'),
        ('unsupported',{'kind':'statistical_interval'},'unsupported_magnitude','unsupported_profile')]:
        bad('N07-'+suffix,request([wrapper(magnitude=mag)]),code,status)
    req=request();req['source']['quantities'][0]['literal']['uncertainty']={'kind':'standard_deviation'};seal(req);bad('N07-uncertainty',req,'unsupported_uncertainty','unsupported_profile')
    req=request();req['source']['quantities'][0]['profile_spec_sha256']='0'*64;seal(req);bad('N07-dependency',req,'quantity_profile_mismatch','unsupported_profile')
    for suffix,value,code,status in [('missing',{'kind':'known','ref':'x'},'missing_field','invalid_input'),
        ('mixed',{'kind':'unknown','ref':'x'},'unknown_field','invalid_input'),('not-applicable',{'kind':'not_applicable'},'unsupported_context','unsupported_profile')]:
        req=request();req['source']['records'][0]['method']=value;seal(req);bad('N08-'+suffix,req,code,status)
    req=request();req['source']['records'][0]['effective_at']={'kind':'period','start':hour(1),'end':hour(2)};seal(req);bad('N08-period',req,'unsupported_context','unsupported_profile')
    req=request();req['source']['records'][0]['recorded_at']='2026-10-20';seal(req);bad('N08-time',req,'invalid_timestamp')
    for suffix,q,code in [('kind',wrapper(kind='k_b'),'property_quantity_kind_mismatch'),('dimension',wrapper(unit='v_base'),'input_dimension_mismatch')]:bad('N09-'+suffix,request([q]),code)
    for suffix,field,value,code in [('profile','profile','future','unsupported_profile'),('hash','profile_spec_sha256','0'*64,'profile_spec_mismatch'),
        ('qhash','quantity_profile_spec_sha256','0'*64,'quantity_profile_mismatch'),('operation','operations',['future'],'unsupported_operation')]:
        req=request();req['consumer'][field]=value;bad('N10-'+suffix,req,code,'unsupported_profile')
    req=request();req['views'][0]['policy_ref']='future';bad('N10-policy',req,'unsupported_policy','unsupported_profile')
    req=pair();req['queries'][0]['comparison_scope']='longitudinal';bad('N10-scope',req,'unsupported_comparison_scope','unsupported_profile')
    req=request();req['source']['schema_version']='future';bad('N10-schema',req,'unsupported_measurement_ledger','unsupported_profile')
    for kind in ['retraction','absence']:
        req=request();req['source']['records'][0]['kind']=kind;seal(req);bad('N10-'+kind,req,'unsupported_record_kind','unsupported_profile')
    for suffix,budget in [('negative',-1),('bool',True),('string','10')]:bad('N11-budget-'+suffix,request(budget=budget),'invalid_step_budget')
    bad('N11-budget-limit',request(budget=100001),'step_budget_limit','resource_limit')
    req=request();req['source']['slots']=[{'id':str(i),'subject_ref':'u'} for i in range(65)];bad('N11-count',req,'item_limit','resource_limit')
    # N12は旧経路・並べ替え・異なるsnapshot・変異の専用テストを受入条件とする。
    emit('B01','B01',request(budget=0),[check(['status'],'resource_limit'),check(['steps_used'],0),*row('unassessed',reasons=['step_limit'],complete=False)])
    for b in [15,16,17]:
        checks=[check(['status'],'ok' if b>=16 else 'resource_limit'),check(['steps_used'],min(b,16))]
        checks+=row(value=((20,1),)) if b>=16 else row('unassessed',reasons=['step_limit'],complete=False)
        emit('B02-'+str(b),'B02',request(budget=b),checks)
    for alias,cost in [(False,25),(True,20)]:
        for b in [cost-1,cost]:
            req=request([wrapper('Q',literals.interval(1,2),'u_base')],queries=[compare('S','S')],budget=b) if alias else pair();req['budget']['max_steps']=b
            checks=[check(['status'],'ok' if b==cost else 'resource_limit'),check(['steps_used'],b)]
            checks+=row(relations=['equal']) if b==cost else row('unassessed',reasons=['step_limit'],complete=False)
            emit(f'B03-{str(alias).lower()}-{b}','B03',req,checks)
    for b in [16,26,27,28]:
        req=request(queries=[convert(ident='a'),convert(target='u_ten',ident='b')],budget=b)
        checks=[check(['status'],'ok' if b>=27 else 'resource_limit'),check(['steps_used'],min(b,27)),*row(value=((20,1),))]
        checks+=row(value=((2,1),),index=1) if b>=27 else row('unassessed',reasons=['step_limit'],index=1,complete=False)
        emit('B04-'+str(b),'B04',req,checks)
    manifest={'schema_version':'p2-fixture-manifest-draft-1','suite':'p2-measurement','review_state':'author_draft',
              'independent_review':False,'evaluation_frozen':False,'conditions':{'M':36,'N':12,'B':4},'files':entries}
    (DIRECTORY/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'files':len(entries),'checks':sum(len(json.loads((DIRECTORY/e['path']).read_text())['expected']['checks']) for e in entries)}))


if __name__=='__main__':main()
