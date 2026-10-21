#!/usr/bin/env python3
"""文書44の手指定期待を展開。runtimeをimportせず、出力から期待を作らない。"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).parent))
import gen_quantity_fixtures as literals
ROOT=Path(os.environ.get('P2_REPO') or Path(__file__).resolve().parents[3]).resolve()
DIRECTORY=ROOT/'examples/p2-temporal-measurement'
PROFILE='p2-temporal-measurement-draft-1'
SPEC=hashlib.sha256((ROOT/'src/med_dsl/temporal_measurement_spec.json').read_bytes()).hexdigest()
QPROFILE='p2-quantity-literal-draft-1'
GSPEC=hashlib.sha256((ROOT/'src/med_dsl/measurement_spec.json').read_bytes()).hexdigest()   # 他の拡張（P2-g）の確認を流用する対照用
QSPEC=hashlib.sha256((ROOT/'src/med_dsl/quantity_spec.json').read_bytes()).hexdigest()
POLICY='fiction:reviewed-scoped-measurement@1'


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def day(n):return f'2026-10-{n:02}T00:00:00Z'


def span(start=1,end=10):return {'kind':'bounded','start':day(start),'end':day(end)}


def wrapper(ref='Q',magnitude=None,unit='u_ten',kind='k_a'):
    return {'ref':ref,'profile':QPROFILE,'profile_spec_sha256':QSPEC,
            'literal':literals.quantity(ref,deepcopy(magnitude if magnitude is not None else literals.point(2)),unit,kind)}


def record(ident='A',slot='S',qref='Q',revises=(),rec=None):
    return {'id':ident,'kind':'period_quantity','slot_ref':slot,'subject_ref':'u',
            'property_ref':'fiction:measurement:property:A@1',
            'specimen':{'kind':'known','ref':'fiction:specimen:s','version':'1'},
            'method':{'kind':'known','ref':'fiction:method:m','version':'1'},
            'validity':span(),'quantity_ref':{'ref':qref,'sha256':'0'*64},
            'certainty':'confirmed','recorded_at':day(rec if rec is not None else {'A':2,'B':6,'C':8}.get(ident,2)),
            'origin':{'kind':'observed','ref':'fiction:measurement:origin:'+ident},'observer':{'kind':'unknown'},
            'required_capabilities':[PROFILE],'revises':list(revises),
            **({'change_reason':'架空の測定記録の明示訂正'} if revises else {})}


def review(ident='A',at=None):
    return {'id':'R'+ident,'record_ref':ident,'record_sha256':'0'*64,'reviewer_ref':'fiction:human:reviewer',
            'reviewer_kind':'human','recorded_at':day(at if at is not None else {'A':3,'B':7,'C':9}.get(ident,3)),'outcome':'confirmed'}


def record_hash(source,rec):
    return digest({'binding_profile':PROFILE,'binding_spec_sha256':SPEC,'source_ref':source['ref'],'record':rec})


def seal(req):
    quantities={q['ref']:q for q in req['source']['quantities']};records={r['id']:r for r in req['source']['records']}
    for rec in records.values():
        rec['quantity_ref']['sha256']=digest(quantities[rec['quantity_ref']['ref']])
    for rev in req['source']['reviews']:rev['record_sha256']=record_hash(req['source'],records[rev['record_ref']])
    return req


def convert(slot='S',target='u_base',ident='q',at=5):
    return {'id':ident,'kind':'convert','slot_ref':slot,'target_unit_ref':target,'target_at':day(at)}


def request(quantities=None,records=None,reviews=None,slots=None,queries=None,k=8,budget=100000):
    req={'schema_version':'p2-temporal-measurement-request-draft-1','operation':'evaluate_temporal_measurements',
         'consumer':{'profile':PROFILE,'profile_spec_sha256':SPEC,'operations':['evaluate_temporal_measurements'],
                     'quantity_profile':QPROFILE,'quantity_profile_spec_sha256':QSPEC},
         'source':{'schema_version':'p2-temporal-measurement-ledger-draft-1','ref':'fiction:period:source@1',
                   'slots':deepcopy(slots if slots is not None else [{'id':'S','subject_ref':'u'}]),
                   'quantities':deepcopy(quantities if quantities is not None else [wrapper()]),
                   'records':deepcopy(records if records is not None else [record()]),
                   'reviews':deepcopy(reviews if reviews is not None else [review()])},
         'views':[{'id':'v','as_of':day(k),'policy_ref':POLICY}],
         'queries':deepcopy(queries if queries is not None else [convert()]),'budget':{'max_steps':budget}}
    return seal(req)



def chain(n=2,k=8,at=5,budget=100000):
    qs=[wrapper(),wrapper('QB',literals.point(3)),wrapper('QC',literals.point(4))]
    rs=[record(),record('B',qref='QB',revises=['A']),record('C',qref='QC',revises=['B'])]
    rs[1]['validity']=span(4,6);rs[2]['validity']=span(5,6)
    return request(qs[:n],rs[:n],[review(x) for x in ['A','B','C'][:n]],queries=[convert(at=at)],k=k,budget=budget)


def check(path,value):return {'path':path,'equals':value}


def row(status='computed',value=((20,1),),reasons=(),index=0,complete=True):
    p=['results',index]
    checks=[check(p+['status'],status),check(p+['assessment_complete'],complete),check(p+['reason_codes'],sorted(reasons)),
            check(p+['converted_domain'],literals.domain(*value) if status=='computed' else None),
            check(p+['relation_set'],None),check(p+['certain_relation'],None)]
    if status!='computed':checks += [check(p+[key],None) for key in ('binding_evidence','calculation_evidence')]
    if not complete:checks.append(check(p+['diagnostics'],None))
    return checks


def main():
    DIRECTORY.mkdir(parents=True,exist_ok=True);entries=[]
    def emit(name,req,checks,normal=True):
        checks=deepcopy(checks)
        if normal:checks += [check(['meaning_mode'],'temporal_measurement_projection'),check(['converted_to_base'],False),
            check(['clinical_assertions_added'],[]),check(['clinical_confirmation'],'not_evaluated'),check(['uncertainty_propagated'],False),
            check(['review_verification'],'structural_only'),check(['certificate','status'],'not_certified'),check(['retained_source'],req['source'])]
        data={'schema_version':'p1-fixture-draft-1','fixture_version':1,'fixture_id':name,'condition':name[:3],'fictional':True,
              'review_state':'author_draft','request':deepcopy(req),'expected':{'comparison':'required_paths','checks':checks}}
        raw=(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode();filename=name.lower()+'.json';(DIRECTORY/filename).write_bytes(raw)
        entries.append({'fixture_id':name,'condition':name[:3],'path':filename,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
    def good(name,req,selected='A',value=((20,1),),extra=()):
        emit(name,req,[check(['status'],'ok'),*row(value=value),check(['results',0,'binding_evidence','selected',0,'record_ref'],selected),*extra])
    def stop(name,req,*reasons):emit(name,req,[check(['status'],'ok'),*row('unassessed',reasons=reasons)])
    def bad(name,req,code,status='invalid_input'):emit(name,req,[check(['status'],status),check(['reason_codes'],[code])],False)
    good('C01',request(),extra=[check(['results',0,'binding_evidence','target_at'],day(5)),check(['results',0,'binding_evidence','assumptions'],['explicit_period_quantity_domain','scoped_revision'])])
    stop('C02',request(records=[record(rec=8)],reviews=[review(at=9)],k=7),'no_adopted_measurement')
    stop('C03-before',request(records=[record(rec=8)],reviews=[review(at=9)],k=8),'no_adopted_measurement')
    good('C03-at',request(records=[record(rec=8)],reviews=[review(at=9)],k=9))
    for t in (1,10,11):
        req=request(queries=[convert(at=t)])
        if t==1:good('C04-start',req)
        else:stop('C04-'+str(t),req,'no_adopted_measurement')
    req=request();req['source']['records'][0]['certainty']='suspected';stop('C04-suspected',seal(req),'no_adopted_measurement')
    good('C05',chain(at=3),extra=[check(['results',0,'diagnostics','masked_records'],[])])
    for t in (4,5,6):good('C06-'+str(t),chain(at=t),'B' if t<6 else 'A',((30 if t<6 else 20,1),))
    for t in (1,9,10):
        req=chain(at=t);req['source']['records'][1]['validity']=span();seal(req)
        if t<10:good('C07-'+str(t),req,'B',((30,1),))
        else:stop('C07-10',req,'no_adopted_measurement')
    for t,chosen,value in [(4,'B',30),(5,'C',40),(6,'A',20)]:
        extra=[check(['results',0,'diagnostics','masked_records'],['A','B'])] if t==5 else []
        good('C08-'+str(t),chain(3,9,t),chosen,((value,1),),extra)
    for suffix,late,k in [('missing',None,9),('before',11,9),('after',11,11)]:
        req=chain(3,k);req['source']['reviews']=[r for r in req['source']['reviews'] if r['record_ref']!='B']
        if late:req['source']['reviews'].append(review('B',late))
        seal(req)
        if k==11:good('C09-'+suffix,req,'C',((40,1),))
        else:stop('C09-'+suffix,req,'unresolved_measurement_conflict')
    for suffix,k,ra in [('missing',8,None),('late',9,9)]:
        req=chain(k=k);req['source']['reviews']=[review('B')]+([review('A',ra)] if ra else []);seal(req)
        good('C10-'+suffix,req,'B',((30,1),),[check(['results',0,'diagnostics','masked_records'],['A'])])
    for shared in (False,True):
        req=chain();r=req['source']['records'][1];r['revises']=[];del r['change_reason']
        if shared:r['quantity_ref']['ref']='Q'
        stop('C11-'+str(shared).lower(),seal(req),'unresolved_measurement_conflict')
    for t in (4,5):
        req=chain(3,9,t);b,c=req['source']['records'][1:];b['revises']=[];del b['change_reason'];c['revises']=['A','B'];seal(req)
        if t==5:good('C12-at',req,'C',((40,1),),[check(['results',0,'diagnostics','masked_records'],['A','B'])])
        else:stop('C12-outside',req,'unresolved_measurement_conflict')
    for kind in ('unknown','unspecified'):
        req=request();req['source']['records'][0]['validity']={'kind':kind};stop('C13-'+kind,seal(req),'validity_'+kind)
    for state in ('reviewed','pending','suspected'):
        u=record('U',rec=4);u['validity']={'kind':'unknown'}
        if state=='suspected':u['certainty']='suspected'
        req=request(records=[record(),u],reviews=[review()]+([] if state=='pending' else [review('U',5)]))
        if state=='reviewed':stop('C14-'+state,req,'validity_unknown')
        else:good('C14-'+state,req)
    for field in ('record','quantity'):
        for state in ('outside','pending','masked'):
            req=chain(3,9) if state=='masked' else chain(at=3 if state=='outside' else 5)
            if state=='pending':req['source']['reviews']=[review()]
            item=req['source']['records'][1] if field=='record' else req['source']['quantities'][1]['literal']
            item['required_capabilities'].append('future:capability');stop('C15-'+field+'-'+state,seal(req),'unknown_capability')
    for field in ('record','quantity'):
        for state in ('future','other'):
            req=chain();b=req['source']['records'][1]
            if state=='future':b['recorded_at']=day(9);req['source']['reviews'][1]['recorded_at']=day(10)
            else:
                req['source']['slots'].append({'id':'T','subject_ref':'u'});b['slot_ref']='T';b['revises']=[];del b['change_reason']
            item=b if field=='record' else req['source']['quantities'][1]['literal'];item['required_capabilities'].append('future:capability')
            good('C16-'+field+'-'+state,seal(req))
    for field in ('method','specimen'):
        for kind in ('unknown','unspecified'):
            req=request();req['source']['records'][0][field]={'kind':kind};stop('C17-'+field+'-'+kind,seal(req),field+'_'+kind)
    for t in (3,5):
        req=chain(at=t);req['source']['records'][1]['method']={'kind':'unknown'};seal(req)
        if t==3:good('C18-outside',req)
        else:stop('C18-inside',req,'method_unknown')
    for field,reason in [('property_ref','unknown_property'),('quantity_kind_ref','unknown_quantity_kind'),('unit_ref','unknown_unit')]:
        req=request();item=req['source']['records'][0] if field=='property_ref' else req['source']['quantities'][0]['literal'];item[field]='fiction:future'
        stop('C19-'+field,seal(req),reason)
    for t in (3,5,6):
        req=chain(at=t);b=req['source']['records'][1];b['method']['version']='2';b['specimen']['ref']='fiction:specimen:new';b['property_ref']='fiction:measurement:property:A-other@1';seal(req)
        good('C20-'+str(t),req,'B' if t==5 else 'A',((30 if t==5 else 20,1),))
    for reviewed in (False,True):
        req=request(reviews=[review()] if reviewed else []);req['source']['records'][0]['origin']['kind']='ai_candidate';req['source']['quantities'][0]['literal']['origin']['kind']='ai_candidate';seal(req)
        if reviewed:good('C21-reviewed',req)
        else:stop('C21-pending',req,'no_adopted_measurement')
    good('C22-third',request([wrapper(magnitude=literals.point(1),unit='u_third')]),value=((2,3),))
    good('C22-negative',request([wrapper(magnitude=literals.point(-3,2))]),value=((-15,1),))
    for k in (6,7):good('C23-'+str(k),chain(k=k),'A' if k==6 else 'B',((20 if k==6 else 30,1),))
    good('C24',request([wrapper(magnitude=literals.interval(1,2))]),value=((10,1),(20,1),True,True))
    req=request([wrapper(magnitude=literals.interval(1,2))],queries=[convert(ident='a',at=3),convert(ident='b',at=5)])
    good('C25',req,value=((10,1),(20,1),True,True),extra=row(value=((10,1),(20,1),True,True),index=1))
    req=chain();[req['source'][key].reverse() for key in ('slots','quantities','records','reviews')];good('C26',req,'B',((30,1),))
    good('C27-past',chain(k=6),'A');good('C27-now',chain(),'B',((30,1),))
    req=request();req['source']['records'][0]['validity']={'kind':'instant','at':day(1)};seal(req);bad('C28-instant',req,'unsupported_validity','unsupported_profile')
    req=request();req['source']['reviews'][0]['record_sha256']=digest({'binding_profile':'p2-measurement-binding-draft-1','binding_spec_sha256':GSPEC,'source_ref':req['source']['ref'],'record':req['source']['records'][0]});bad('C29-old-hash',req,'review_record_hash_mismatch')
    for case,shared in [('C30',False),('C31',True)]:
        req=chain();req['source']['quantities'][0]['literal'].update(magnitude=literals.point(121,100),unit_ref='u_base');req['source']['quantities'][1]['literal'].update(magnitude=literals.point(121 if shared else 124,100),unit_ref='u_base')
        req['queries']=[convert(ident='a',at=3),convert(ident='b',at=5)];seal(req)
        good(case,req,value=((121,100),),extra=[*row(value=((121,100) if shared else (31,25),),index=1),check(['results',1,'binding_evidence','selected',0,'record_ref'],'B')])
    good('C32',chain(),'B',((30,1),),[check(['certificate','scope'],None)])
    for key in ('source','consumer','budget','queries'):
        req=request();del req[key];bad('N01-missing-'+key,req,'missing_field')
    req=request();req['source']=None;bad('N01-null',req,'expected_object')
    req=request();req['artifact']={};bad('N01-extra',req,'unknown_field')
    for key in ('slots','quantities','records','reviews','views','queries'):
        req=request();target=req['source'][key] if key in req['source'] else req[key];target.append(deepcopy(target[0]));bad('N01-duplicate-'+key,req,'duplicate_identifier')
    for suffix,mutate,code in [
        ('slot',lambda r:r['queries'][0].update(slot_ref='missing'),'unresolved_slot'),
        ('quantity',lambda r:r['source']['records'][0]['quantity_ref'].update(ref='missing'),'unresolved_quantity'),
        ('record',lambda r:r['source']['reviews'][0].update(record_ref='missing'),'unresolved_record'),
        ('subject',lambda r:r['source']['records'][0].update(subject_ref='other'),'slot_subject_mismatch'),
        ('review-time',lambda r:r['source']['reviews'][0].update(recorded_at=day(1)),'review_precedes_record')]:
        req=request();mutate(req);bad('N02-'+suffix,req,code)
    for field in ('magnitude','origin','unit_ref','required_capabilities'):
        req=request();q=req['source']['quantities'][0]['literal']
        if field=='magnitude':q[field]=literals.point(3)
        elif field=='origin':q[field]['kind']='ai_candidate'
        elif field=='unit_ref':q[field]='u_base'
        else:q[field].append('future')
        bad('N03-quantity-'+field,req,'quantity_reference_hash_mismatch')
    for field in ('validity','method','revises'):
        req=chain()
        if field=='validity':req['source']['records'][1][field]=span(4,5)
        elif field=='method':req['source']['records'][1][field]['version']='2'
        else:req['source']['records'][1][field]=[];del req['source']['records'][1]['change_reason']
        bad('N03-record-'+field,req,'review_record_hash_mismatch')
    for suffix in ('self','future','same-time','cross-slot','reason'):
        req=chain();a,b=req['source']['records']
        if suffix=='self':b['revises']=['B']
        elif suffix=='future':a['revises']=['B'];a['change_reason']='架空'
        elif suffix=='same-time':b['recorded_at']=a['recorded_at']
        elif suffix=='cross-slot':req['source']['slots'].append({'id':'T','subject_ref':'u'});b['slot_ref']='T'
        else:del b['change_reason']
        seal(req);bad('N04-'+suffix,req,'expected_nonempty_string' if suffix=='reason' else 'invalid_revision')
    for suffix,validity in [('empty',span(4,4)),('reversed',span(5,4)),('missing',{'kind':'bounded','start':day(1)}),('outside',span(1,11))]:
        req=chain();req['source']['records'][1]['validity']=validity;seal(req)
        bad('N05-'+suffix,req,'missing_field' if suffix=='missing' else 'invalid_revision_interval' if suffix=='outside' else 'invalid_validity_interval')
    for target in (0,1):
        req=chain();req['source']['records'][target]['validity']={'kind':'unknown'};seal(req);bad('N06-'+str(target),req,'unsupported_revision_scope','unsupported_profile')
    for suffix,validity in [('open',{'kind':'open_end','start':day(1)}),('future',{'kind':'future'})]:
        req=request();req['source']['records'][0]['validity']=validity;seal(req);bad('N07-'+suffix,req,'unsupported_validity','unsupported_profile')
    for suffix,time in [('date','2026-10-01'),('offset','2026-10-01T00:00:00+00:00'),('fraction','2026-10-01T00:00:00.1Z')]:
        req=request();req['queries'][0]['target_at']=time;bad('N07-'+suffix,req,'invalid_timestamp')
    for suffix in ('compare','display','policy','schema','supersedes','effective_at','aggregate'):
        req=request();code='unsupported_query_kind'
        if suffix in ('compare','display'):req['queries'][0]['kind']=suffix
        elif suffix=='policy':req['views'][0]['policy_ref']='fiction:reviewed-measurement-record@1';code='unsupported_policy'
        elif suffix=='schema':req['source']['schema_version']='p2-measurement-ledger-draft-1';code='unsupported_temporal_measurement_ledger'
        elif suffix=='aggregate':req['source']['records'][0]['validity']={'kind':'aggregate'};seal(req);code='unsupported_validity'
        else:req['source']['records'][0][suffix]=[] if suffix=='supersedes' else {'kind':'instant','at':day(1)};seal(req);code='unknown_field'
        bad('N08-'+suffix,req,code,'invalid_input' if code=='unknown_field' else 'unsupported_profile')
    for key,value,code,status in [('profile','future','unsupported_profile','unsupported_profile'),('profile_spec_sha256','0'*64,'profile_spec_mismatch','unsupported_profile'),('quantity_profile','future','quantity_profile_mismatch','unsupported_profile'),('quantity_profile_spec_sha256','0'*64,'quantity_profile_mismatch','unsupported_profile'),('profile_spec_sha256','x','invalid_sha256','invalid_input')]:
        req=request();req['consumer'][key]=value;bad('N09-'+key+('-format' if value=='x' else ''),req,code,status)
    for suffix,q,code,status in [('kind',wrapper(kind='k_b'),'property_quantity_kind_mismatch','invalid_input'),('dimension',wrapper(unit='v_base'),'input_dimension_mismatch','invalid_input'),('zero',wrapper(magnitude=literals.point(1,0)),'invalid_rational','invalid_input'),('bool',wrapper(magnitude=literals.point(True)),'invalid_rational','invalid_input'),('bits',wrapper(magnitude=literals.point(2**63)),'rational_integer_limit','resource_limit')]:bad('N10-'+suffix,request([q]),code,status)
    for suffix,budget in [('negative',-1),('bool',True),('string','16')]:bad('N11-budget-'+suffix,request(budget=budget),'invalid_step_budget')
    bad('N11-budget-limit',request(budget=100001),'step_budget_limit','resource_limit')
    req=request();req['source']['slots']=[{'id':str(i),'subject_ref':'u'} for i in range(65)];bad('N11-count',req,'item_limit','resource_limit')
    # N12の旧経路・schema fuzz・順序、C32の旧表示拒否は専用テスト。
    for budget in (0,1,7,15,16,17):
        req=request(budget=budget);done=budget>=16
        emit('B01-'+str(budget),req,[check(['status'],'ok' if done else 'resource_limit'),check(['steps_used'],min(budget,16)),*(row() if done else row('unassessed',reasons=['step_limit'],complete=False))])
    for budget in (15,16,26,27,28):
        req=request(queries=[convert(ident='a',at=3),convert(ident='b',at=5)],budget=budget)
        checks=[check(['status'],'ok' if budget>=27 else 'resource_limit'),check(['steps_used'],min(budget,27))]
        checks += row() if budget>=16 else row('unassessed',reasons=['step_limit'],complete=False)
        checks += row(index=1) if budget>=27 else row('unassessed',reasons=['step_limit'],index=1,complete=False)
        emit('B02-'+str(budget),req,checks)
    for two in (False,True):
        for budget in ((20,21,22) if not two else (20,21,33,34,35)):
            req=chain(budget=budget,at=3)
            if two:req['queries']=[convert(ident='a',at=3),convert(ident='b',at=5)]
            cost=34 if two else 21;checks=[check(['status'],'ok' if budget>=cost else 'resource_limit'),check(['steps_used'],min(budget,cost))]
            checks += row() if budget>=21 else row('unassessed',reasons=['step_limit'],complete=False)
            if two:checks += row(value=((30,1),),index=1) if budget>=34 else row('unassessed',reasons=['step_limit'],index=1,complete=False)
            emit('B03-'+str(two).lower()+'-'+str(budget),req,checks)
    # B04の下位資源停止・部分結果の注入は専用テスト。
    # ---- 観察者（P2-r、文書74の§1）：記録の任意の項目 observer ----
    human={'kind':'human','ref':'fiction:human:observer'};device={'kind':'device','ref':'fiction:device:meter'}
    def observed(req,index,observer):
        req['source']['records'][index]['observer']=deepcopy(observer);return seal(req)
    shown=lambda observer:[check(['results',0,'binding_evidence','selected',0,'record_observer'],observer)]
    good('O01',observed(request(),0,human),extra=shown(human))
    good('O02',observed(request(),0,device),extra=shown(device))
    good('O03',observed(chain(at=5),1,human),'B',((30,1),),shown(human))
    good('O04',observed(chain(at=5),0,human),'B',((30,1),),shown({'kind':'unknown'}))          # 訂正は元の観察者を継がない：B は明示の unknown
    req=observed(request(),0,human);req['source']['records'][0]['observer']['ref']='fiction:human:other';bad('O05',req,'review_record_hash_mismatch')
    for name,change,code in [('O10',lambda o:o.update(kind='robot'),'invalid_observer'),('O11',lambda o:o.update(ref=''),'expected_nonempty_string'),
                             ('O12',lambda o:o.pop('ref'),'missing_field'),('O13',lambda o:o.update(extra=1),'unknown_field')]:
        req=observed(request(),0,human);change(req['source']['records'][0]['observer']);seal(req);bad(name,req,code)
    for suffix,value in [('null',None),('string','fiction:human:observer')]:
        req=request();req['source']['records'][0]['observer']=value;seal(req);bad('O14-'+suffix,req,'expected_object')
    # ---- 観察者を必須にする（P2-s、文書77の§1）：欠落は拒否し、不明は明示の unknown ----
    req=request();del req['source']['records'][0]['observer'];seal(req);bad('O20',req,'missing_field')
    unknown={'kind':'unknown'}
    good('O21',observed(request(),0,unknown),extra=shown(unknown))
    req=observed(request(),0,{'kind':'unknown','ref':'fiction:x'});bad('O22',req,'unknown_field')
    good('O23',request(),extra=shown(unknown))
    manifest={'schema_version':'p2-fixture-manifest-draft-1','suite':'p2-temporal-measurement','review_state':'author_draft','independent_review':False,'evaluation_frozen':False,'conditions':{'C':32,'N':12,'B':4,'O':14},'files':entries}
    (DIRECTORY/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'files':len(entries),'checks':sum(len(json.loads((DIRECTORY/e['path']).read_text())['expected']['checks']) for e in entries)}))


if __name__=='__main__':main()
