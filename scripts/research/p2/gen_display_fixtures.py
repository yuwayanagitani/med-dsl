#!/usr/bin/env python3
"""文書41の期待を手指定で展開する。runtimeはimportしない。"""
import base64
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import gen_measurement_fixtures as m
import gen_quantity_fixtures as q
ROOT=Path(os.environ.get('P2_REPO') or Path(__file__).resolve().parents[3]).resolve()
DIRECTORY=ROOT/'examples/p2-display'
PROFILE='p2-quantity-display-draft-1'
SPEC=hashlib.sha256((ROOT/'src/med_dsl/display_spec.json').read_bytes()).hexdigest()
POLICY='fiction:decimal-half-even@1'
digest=m.digest


def ratio(n,d=1):
    f=Fraction(n,d);return {'numerator':f.numerator,'denominator':f.denominator}


def question(kind='display_text',ident='q',op='ge',n=61,d=50):
    return {'id':ident,'kind':kind,**({'operator':op,'threshold':ratio(n,d)} if kind=='threshold' else {})}


def display(ident='d',p=1,questions=None,view='v',query='q'):
    return {'id':ident,'view_ref':view,'query_ref':query,'decimal_places':p,'rounding_policy':POLICY,
            'required_capabilities':[PROFILE],'questions':deepcopy(questions if questions is not None else [question()])}


def request(n=121,d=100,p=1,unit='u_base',plan=None,displays=None,questions=None,retention='none',budget=100000):
    child=deepcopy(plan if plan is not None else m.request([m.wrapper(magnitude=q.point(n,d),unit=unit)]));child.pop('budget',None)
    return {'schema_version':'p2-display-request-draft-1','operation':'project_measurement_displays',
            'consumer':{'profile':PROFILE,'profile_spec_sha256':SPEC,'operations':['project_measurement_displays'],
                        'measurement_profile':m.PROFILE,'measurement_profile_spec_sha256':m.SPEC,
                        'quantity_profile':m.QPROFILE,'quantity_profile_spec_sha256':m.QSPEC},
            'measurement_plan':child,'displays':deepcopy(displays if displays is not None else [display(p=p,questions=questions)]),
            'retention':retention,'budget':{'max_steps':budget}}


def pair(second=124):
    child=m.request([m.wrapper('Q',q.point(121,100),'u_base'),m.wrapper('QT',q.point(second,100),'u_base')],
        [m.record(),m.record('B','T','QT')],[m.review(),m.review('B')],
        [{'id':'S','subject_ref':'u'},{'id':'T','subject_ref':'u'}],[m.convert('S',ident='a'),m.convert('T',ident='b')])
    return request(plan=child,displays=[display('a',query='a'),display('b',query='b')])


def seal(req):m.seal(req['measurement_plan']);return req


def artifact(k,text,p=1,unit='u_base',kind='k_a'):
    return {'schema_version':'p2-display-artifact-draft-1','profile':PROFILE,'profile_spec_sha256':SPEC,
            'quantity_profile':m.QPROFILE,'quantity_profile_spec_sha256':m.QSPEC,'quantity_kind_ref':kind,'unit_ref':unit,
            'rounding_policy':POLICY,'decimal_places':p,'coefficient':k,'text':text}


def checks_row(k=12,text='1.2',p=1,unit='u_base',kind='k_a',answers=None,sources=None,index=0,retention='none'):
    a=artifact(k,text,p,unit,kind);path=['results',index];raw=json.dumps(a,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
    checks=[m.check(path+['status'],'computed'),m.check(path+['assessment_complete'],True),m.check(path+['artifact'],a),
        m.check(path+['artifact_sha256'],digest(a)),m.check(path+['rounding_cell'],{'lower':ratio(2*k-1,2*10**p),'upper':ratio(2*k+1,2*10**p),'lower_closed':k%2==0,'upper_closed':k%2==0}),
        m.check(path+['projection_evidence','artifact_encoding'],{'kind':'canonical_json','bytes_base64':base64.b64encode(raw).decode(),'sha256':digest(a),'roundtrip_matches':True}),
        m.check(path+['projection_evidence','measurement_certificate','status'],'not_certified')]
    if retention=='none':checks.append(m.check(path+['source_evidence'],None))
    answers=answers if answers is not None else [text];sources=sources if sources is not None else [None]*len(answers)
    for i,(answer,source) in enumerate(zip(answers,sources)):
        checks += [m.check(path+['question_results',i,'status'],'preserved' if answer is not None else 'out_of_scope'),
                   m.check(path+['question_results',i,'projection_answer'],answer),
                   m.check(path+['question_results',i,'source_answer'],None if source is None else {'mode':'source_replay','answer':source})]
    return checks


def stopped(reason,status='unassessed',index=0,complete=True):
    p=['results',index];checks=[m.check(p+['status'],status),m.check(p+['assessment_complete'],complete),m.check(p+['reason_codes'],[reason])]
    for key in ('artifact','artifact_sha256','rounding_cell','projection_evidence','source_evidence'):checks.append(m.check(p+[key],None))
    checks += [m.check(p+['question_results'],None)] if not complete else [m.check(p+['question_results',0,'status'],'unassessed'),m.check(p+['question_results',0,'projection_answer'],None),m.check(p+['question_results',0,'source_answer'],None)]
    return checks


def main():
    DIRECTORY.mkdir(parents=True,exist_ok=True);entries=[]
    def emit(name,req,checks,normal=True):
        if normal:
            plan=deepcopy(req);plan.pop('budget')
            checks=list(checks)+[m.check(['meaning_mode'],'measurement_display_projection'),m.check(['clinical_confirmation'],'not_evaluated'),m.check(['uncertainty_propagated'],False),m.check(['converted_to_base'],False),m.check(['clinical_assertions_added'],[]),m.check(['source_bundle'],{'request_plan':plan} if req['retention']=='source_bundle' else None)]
        data={'schema_version':'p1-fixture-draft-1','fixture_version':1,'fixture_id':name,'condition':name[:3],'fictional':True,'review_state':'author_draft','request':deepcopy(req),'expected':{'comparison':'required_paths','checks':checks}}
        raw=(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode();namepath=name.lower()+'.json';(DIRECTORY/namepath).write_bytes(raw)
        entries.append({'fixture_id':name,'condition':name[:3],'path':namepath,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
    def good(name,req=None,k=12,text='1.2',p=1,answers=None,sources=None,extra=(),rows=None):
        req=deepcopy(req if req is not None else request());rows=rows if rows is not None else [{'k':k,'text':text,'p':p,'answers':answers,'sources':sources}]
        checks=[m.check(['status'],'ok')];cert=True;used=False
        for i,row in enumerate(rows):
            checks += checks_row(index=i,retention=req['retention'],**row)
            cert &= all(x is not None for x in (row.get('answers') if row.get('answers') is not None else [row['text']]))
            used |= any(x is not None for x in (row.get('sources') or []))
        emit(name,req,checks+[m.check(['certificate','status'],'certified' if cert else 'not_certified'),m.check(['additional_source_used'],used),*extra])
    def stop(name,req,reason,status='unassessed'):emit(name,req,[m.check(['status'],'ok'),*stopped(reason,status),m.check(['certificate','status'],'not_certified')])
    good('P01');good('P02',request(124));good('P03',request(5,4));good('P04',request(27,20),14,'1.4');good('P05',request(-5,4),-12,'-1.2');good('P06',request(-27,20),-14,'-1.4')
    for suffix,n,d in [('positive',1,20),('negative',-1,20),('zero',0,1)]:good('P07-'+suffix,request(n,d),0,'0.0')
    good('P08',request(1,3,p=2),33,'0.33',2);good('P09',request(1,2,p=2),50,'0.50',2)
    for n,k in [(5,2),(-5,-2),(7,4),(-7,-4)]:good('P10-'+str(n),request(n,2,p=0),k,str(k),0)
    good('P11',request(9007199254740993,1,p=0),9007199254740993,'9007199254740993',0)
    good('P12',request(1,1,p=2,unit='u_third'),33,'0.33',2)
    req=pair();req['displays'].reverse()
    for key in ('slots','quantities','records','reviews'):req['measurement_plan']['source'][key].reverse()
    req['measurement_plan']['queries'].reverse();good('P13',req,rows=[{'k':12,'text':'1.2'},{'k':12,'text':'1.2'}])
    good('P14',request(2,4,p=2,questions=[question('exact_value')],retention='source_bundle'),50,'0.50',2,answers=[None],sources=[ratio(1,2)])
    stop('P15',request(plan=m.request([m.wrapper(magnitude=q.interval(1,2,False,True),unit='u_base')])),'unsupported_display_domain')
    good('P16',request(plan=m.request([m.wrapper(magnitude=q.interval(1,1),unit='u_base')])),10,'1.0')
    for mode in ['unknown','unspecified']:
        req=request();req['measurement_plan']['source']['records'][0]['method']={'kind':mode};stop('P17-'+mode,seal(req),'method_'+mode)
    req=request();req['measurement_plan']['source']['reviews']=[];stop('P18-no-review',req,'no_adopted_measurement')
    req=request();req['measurement_plan']['source']['records'][0]['certainty']='suspected';stop('P18-suspected',seal(req),'no_adopted_measurement')
    req=request(retention='source_bundle');req['measurement_plan']['source']['records'][0]['origin']['kind']='ai_candidate';req['measurement_plan']['source']['quantities'][0]['literal']['origin']['kind']='ai_candidate';seal(req);good('P19-reviewed',req,extra=[m.check(['results',0,'projection_evidence','selected',0,'record_origin','kind'],'ai_candidate'),m.check(['results',0,'projection_evidence','selected',0,'quantity_origin','kind'],'ai_candidate')]);req['measurement_plan']['source']['reviews']=[];stop('P19-pending',req,'no_adopted_measurement')
    child=m.request([m.wrapper(magnitude=q.point(121,100),unit='u_base')],[m.record(),m.record('B')],[m.review(),m.review('B')]);stop('P20',request(plan=child),'unresolved_measurement_conflict')
    for place in ['record','quantity','display']:
        req=request();target=req['displays'][0] if place=='display' else req['measurement_plan']['source']['records'][0] if place=='record' else req['measurement_plan']['source']['quantities'][0]['literal'];target['required_capabilities'].append('fiction:future');stop('P21-'+place,seal(req),'unknown_capability')
    for state in ['pending','masked']:
        for place in ['record','quantity']:
            child=m.request([m.wrapper(magnitude=q.point(121,100),unit='u_base'),m.wrapper('QB',q.point(124,100),'u_base')],[m.record(),m.record('B',qref='QB',revises=['A'])],[m.review()] if state=='pending' else [m.review(),m.review('B')]);req=request(plan=child);idx=1 if state=='pending' else 0;target=req['measurement_plan']['source']['records'][idx] if place=='record' else req['measurement_plan']['source']['quantities'][idx]['literal'];target['required_capabilities'].append('fiction:future');stop('P21-'+state+'-'+place,seal(req),'unknown_capability')
    qs=[question('threshold','a','ge',11,10),question('threshold','b','le',13,10),question('threshold','c','eq',13,10)];good('P22',request(questions=qs),answers=[True,True,False])
    closed={'lt':(False,None),'le':(None,True),'eq':(None,None),'ge':(True,None),'gt':(None,False)}
    opened={'lt':(False,True),'le':(False,True),'eq':(False,False),'ge':(True,False),'gt':(True,False)}
    for case,x,k,text,bounds,table in [('P23',(121,100),12,'1.2',[(23,20),(5,4)],closed),('P24',(13,10),13,'1.3',[(5,4),(27,20)],opened)]:
        for op,answers in table.items():
            for j,(n,d) in enumerate(bounds):good(case+'-'+op+'-'+str(j),request(*x,questions=[question('threshold',op=op,n=n,d=d)]),k,text,answers=[answers[j]])
    for retention in ['none','source_bundle']:
        good('P25-'+retention,request(questions=[question('exact_value')],retention=retention),answers=[None],sources=[ratio(121,100) if retention=='source_bundle' else None])
        good('P26-'+retention,request(questions=[question('threshold')],retention=retention),answers=[None],sources=[False if retention=='source_bundle' else None])
    good('P27',request(retention='source_bundle'))
    for case,kind,sources in [('P28','threshold',[False,True]),('P29','exact_value',[ratio(121,100),ratio(31,25)]),('P30','threshold',[False,True])]:
        req=pair();req['retention']='source_bundle'
        for d in req['displays']:d['questions']=[question(kind)]
        good(case,req,rows=[{'k':12,'text':'1.2','answers':[None],'sources':[s]} for s in sources])
    req=pair(121);req['measurement_plan']['source']['records'][1]['method']['version']='2';req['measurement_plan']['source']['records'][1]['origin']['kind']='judgment';good('P31',seal(req),rows=[{'k':12,'text':'1.2'},{'k':12,'text':'1.2'}])
    good('P32',request(1251,1000,displays=[display('a',2),display('b',1)]),rows=[{'k':125,'text':'1.25','p':2},{'k':13,'text':'1.3'}])
    good('P33-places',request(1,2,displays=[display('a',1),display('b',2)]),rows=[{'k':5,'text':'0.5'},{'k':50,'text':'0.50','p':2}])
    req=pair();src=req['measurement_plan']['source'];src['quantities'][0]['literal']['magnitude']=q.point(1);src['quantities'][1]['literal']['magnitude']=q.point(1);src['quantities'][1]['literal']['unit_ref']='u_ten';req['measurement_plan']['queries'][1]['target_unit_ref']='u_ten';good('P33-unit',seal(req),rows=[{'k':10,'text':'1.0'},{'k':10,'text':'1.0','unit':'u_ten'}])
    req=pair();src=req['measurement_plan']['source'];src['quantities'][0]['literal']['magnitude']=q.point(1);src['quantities'][1]['literal']['magnitude']=q.point(1);src['quantities'][1]['literal']['quantity_kind_ref']='k_b';src['records'][1]['property_ref']='fiction:measurement:property:B@1';good('P33-kind',seal(req),rows=[{'k':10,'text':'1.0'},{'k':10,'text':'1.0','kind':'k_b'}])
    child=m.request([m.wrapper(magnitude=q.point(121,100),unit='u_base'),m.wrapper('QB',q.point(131,100),'u_base')],[m.record(),m.record('B',qref='QB',revises=['A'],rec=6)],[m.review(),m.review('B',7)],k=8)
    good('P34-now',request(plan=child,retention='source_bundle'),13,'1.3',extra=[m.check(['results',0,'projection_evidence','selected',0,'record_ref'],'B')]);child['views'][0]['as_of']=m.hour(3);good('P34-past',request(plan=child),12,'1.2');good('P34-old',request())
    child['source']['records'][1]['required_capabilities'].append('fiction:future');m.seal(child);good('P35-future',request(plan=child))
    req=pair();req['displays']=[display(query='a')];req['measurement_plan']['queries']=[m.convert('S',ident='a')];req['measurement_plan']['source']['records'][1]['required_capabilities'].append('fiction:future');good('P35-other',seal(req));req['measurement_plan']['queries'].append(m.convert('T',ident='b'));good('P35-unused-query',req)
    req=request(p=6,retention='source_bundle');src=req['measurement_plan']['source'];src['records'][0]['origin']['kind']='ai_candidate';src['quantities'][0]['literal']['origin']['kind']='ai_candidate';good('P36',seal(req),1210000,'1.210000',6)
    def bad(name,req,reason,status='invalid_input'):emit(name,req,[m.check(['status'],status),m.check(['reason_codes'],[reason])],False)
    for field in ['consumer','measurement_plan','displays','retention','budget']:
        req=request();del req[field];bad('N01-missing-'+field,req,'missing_field')
    req=request();req['measurement_plan']['budget']={'max_steps':100000};bad('N01-inner-budget',req,'unknown_field')
    req=request();req['displays']=None;bad('N01-null',req,'expected_array')
    req=request();req['displays'].append(deepcopy(req['displays'][0]));bad('N02-display',req,'duplicate_identifier')
    req=request();req['displays'][0]['questions']*=2;bad('N02-question',req,'duplicate_identifier')
    for field in ['view_ref','query_ref']:
        req=request();req['displays'][0][field]='missing';bad('N02-'+field,req,'unresolved_'+field)
    for case,change,code in [('quantity',lambda r:r['measurement_plan']['source']['quantities'][0]['literal'].update(unit_ref='u_ten'),'quantity_reference_hash_mismatch'),('review',lambda r:r['measurement_plan']['source']['records'][0]['method'].update(version='2'),'review_record_hash_mismatch')]:
        req=request();change(req);bad('N03-'+case,req,code)
        req['measurement_plan']['views'][0]['as_of']=m.hour(1);bad('N03-future-'+case,req,code)
    for name,value,status,code in [('bool',True,'invalid_input','invalid_decimal_places'),('negative',-1,'invalid_input','invalid_decimal_places'),('string','2','invalid_input','invalid_decimal_places'),('seven',7,'unsupported_profile','unsupported_decimal_places'),('large',1000000,'unsupported_profile','unsupported_decimal_places')]:
        req=request();req['displays'][0]['decimal_places']=value;bad('N04-'+name,req,code,status)
    for name,n,d,status,code in [('zero',1,0,'invalid_input','invalid_rational'),('negative',1,-1,'invalid_input','invalid_rational'),('bool',True,1,'invalid_input','invalid_rational'),('bits',2**63,1,'resource_limit','rational_integer_limit')]:
        req=request(questions=[question('threshold')]);req['displays'][0]['questions'][0]['threshold']={'numerator':n,'denominator':d};bad('N05-'+name,req,code,status)
    for name,mag,unit,kind,code in [('denominator',q.point(1,0),'u_base','k_a','invalid_rational'),('empty',q.interval(1,1,False,True),'u_base','k_a','invalid_interval'),('kind',q.point(1),'u_base','k_b','property_quantity_kind_mismatch'),('dimension',q.point(1),'v_base','k_a','input_dimension_mismatch')]:bad('N06-'+name,request(plan=m.request([m.wrapper(magnitude=mag,unit=unit,kind=kind)])),code)
    for field,code in [('profile','unsupported_profile'),('profile_spec_sha256','profile_spec_mismatch'),('measurement_profile','measurement_profile_mismatch'),('measurement_profile_spec_sha256','measurement_profile_mismatch'),('quantity_profile','quantity_profile_mismatch'),('quantity_profile_spec_sha256','quantity_profile_mismatch')]:
        req=request();req['consumer'][field]='0'*64 if field.endswith('sha256') else 'future';bad('N07-'+field,req,code,'unsupported_profile')
    for name,change,code in [('policy',lambda r:r['displays'][0].update(rounding_policy='future'),'unsupported_rounding_policy'),('retention',lambda r:r.update(retention='future'),'unsupported_retention'),('kind',lambda r:r['displays'][0]['questions'][0].update(kind='future'),'unsupported_question_kind'),('operator',lambda r:r['displays'][0]['questions'][0].update(operator='future'),'unsupported_question_operator'),('schema',lambda r:r['measurement_plan'].update(schema_version='future'),'unsupported_measurement_schema')]:
        req=request(questions=[question('threshold')]);change(req);bad('N08-'+name,req,code,'unsupported_profile')
    req=request();req['measurement_plan']['queries']=[m.compare('S','S')];bad('N08-compare',req,'unsupported_measurement_query','unsupported_profile')
    for field in ['child_result','certificate','artifact']:
        req=request();req[field]={'status':'certified'};bad('N09-'+field,req,'unknown_field')
    for name,field,value in [('displays','displays',[]),('questions','questions',[])]:
        req=request()
        if field=='displays':req[field]=value
        else:req['displays'][0][field]=value
        bad('N10-empty-'+name,req,'empty_collection')
    req=request();req['displays']=[display(str(i)) for i in range(65)];bad('N10-displays',req,'item_limit','resource_limit')
    req=request();req['displays'][0]['questions']=[question(ident=str(i)) for i in range(17)];bad('N10-questions',req,'item_limit','resource_limit')
    for name,value in [('negative',-1),('bool',True),('string','0')]:bad('N11-budget-'+name,request(budget=value),'invalid_step_budget')
    bad('N11-budget-limit',request(budget=100001),'step_budget_limit','resource_limit')
    child=m.request([m.wrapper(magnitude=q.point(121,100),unit='u_base')],[m.record('R'+str(i),rec=2) for i in range(20)],[m.review('R'+str(i),3) for i in range(20)])
    child['views']=[{'id':'v'+str(i),'as_of':m.hour(5),'policy_ref':m.POLICY} for i in range(64)];child['queries']=[m.convert(ident='q'+str(i)) for i in range(64)]
    req=request(plan=child,displays=[display(view='v0',query='q0')]);emit('N11-large-plan',req,[m.check(['status'],'resource_limit'),m.check(['steps_used'],100000),*stopped('step_limit',complete=False),m.check(['certificate','status'],'not_certified')])
    for case,budgets in [('B01',[0,16,17]),('B02',[26,27,28,29])]:
        for b in budgets:
            req=request(budget=b);checks=[m.check(['status'],'ok' if b>=28 else 'resource_limit'),m.check(['steps_used'],min(b,28)),m.check(['certificate','status'],'certified' if b>=28 else 'not_certified')]
            checks+=checks_row() if b>=27 else stopped('step_limit',complete=False)
            if b==27:checks.append(m.check(['incomplete'],[{'stage':'completion','reason_codes':['step_limit']}]))
            emit(case+'-'+str(b),req,checks)
    for retention in ['none','source_bundle']:
        for b in [27,36,37,38]:
            req=request(displays=[display('a'),display('b')],budget=b,retention=retention);checks=[m.check(['status'],'ok' if b==38 else 'resource_limit'),m.check(['steps_used'],b),m.check(['certificate','status'],'certified' if b==38 else 'not_certified'),*checks_row(retention=retention)]
            checks+=checks_row(index=1,retention=retention) if b>=37 else stopped('step_limit',index=1,complete=False)
            emit('B03-'+retention+'-'+str(b),req,checks)
    for name,req,reason in [('method',request(),'method_unknown'),('interval',request(plan=m.request([m.wrapper(magnitude=q.interval(1,2),unit='u_base')])),'unsupported_display_domain')]:
        if name=='method':req['measurement_plan']['source']['records'][0]['method']={'kind':'unknown'};seal(req)
        req['budget']['max_steps']=27;emit('B04-'+name,req,[m.check(['status'],'resource_limit'),m.check(['certificate','status'],'not_certified'),*stopped(reason),m.check(['incomplete'],[{'stage':'completion','reason_codes':['step_limit']}])])
    manifest={'schema_version':'p2-fixture-manifest-draft-1','suite':'p2-display','review_state':'author_draft','independent_review':False,'evaluation_frozen':False,'conditions':{'P':36,'N':12,'B':4},'files':entries}
    (DIRECTORY/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'files':len(entries),'checks':sum(len(json.loads((DIRECTORY/e['path']).read_text())['expected']['checks']) for e in entries)}))


if __name__=='__main__':main()
