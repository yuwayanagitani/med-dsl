#!/usr/bin/env python3
"""文書47の期待を手指定で展開する。runtimeはimportしない。"""
import base64
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import gen_temporal_measurement_fixtures as m
import gen_quantity_fixtures as q
ROOT=Path(os.environ.get('P2_REPO') or Path(__file__).resolve().parents[3]).resolve()
DIRECTORY=ROOT/'examples/p2-temporal-display'
PROFILE='p2-temporal-display-draft-1'
SPEC=hashlib.sha256((ROOT/'src/med_dsl/temporal_display_spec.json').read_bytes()).hexdigest()
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
    return {'schema_version':'p2-temporal-display-request-draft-1','operation':'project_temporal_measurement_displays',
            'consumer':{'profile':PROFILE,'profile_spec_sha256':SPEC,'operations':['project_temporal_measurement_displays'],
                        'temporal_measurement_profile':m.PROFILE,'temporal_measurement_profile_spec_sha256':m.SPEC,
                        'quantity_profile':m.QPROFILE,'quantity_profile_spec_sha256':m.QSPEC},
            'temporal_measurement_plan':child,'displays':deepcopy(displays if displays is not None else [display(p=p,questions=questions)]),
            'retention':retention,'budget':{'max_steps':budget}}


def seal(req):m.seal(req['temporal_measurement_plan']);return req


def artifact(k,text,p=1,unit='u_base',kind='k_a'):
    return {'schema_version':'p2-temporal-display-artifact-draft-1','profile':PROFILE,'profile_spec_sha256':SPEC,
            'quantity_profile':m.QPROFILE,'quantity_profile_spec_sha256':m.QSPEC,'quantity_kind_ref':kind,'unit_ref':unit,
            'rounding_policy':POLICY,'decimal_places':p,'coefficient':k,'text':text}


def checks_row(k=12,text='1.2',p=1,unit='u_base',kind='k_a',answers=None,sources=None,index=0,retention='none'):
    a=artifact(k,text,p,unit,kind);path=['results',index];raw=json.dumps(a,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
    checks=[m.check(path+['status'],'computed'),m.check(path+['assessment_complete'],True),m.check(path+['artifact'],a),
        m.check(path+['artifact_sha256'],digest(a)),m.check(path+['rounding_cell'],{'lower':ratio(2*k-1,2*10**p),'upper':ratio(2*k+1,2*10**p),'lower_closed':k%2==0,'upper_closed':k%2==0}),
        m.check(path+['projection_evidence','artifact_encoding'],{'kind':'canonical_json','bytes_base64':base64.b64encode(raw).decode(),'sha256':digest(a),'roundtrip_matches':True}),
        m.check(path+['projection_evidence','temporal_measurement_certificate','status'],'not_certified')]
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


def chain(n=2,k=8,at=5):
    child=m.chain(n,k,at)
    for literal,value in zip(child['source']['quantities'],[121,124,131]):
        literal['literal']['magnitude']=q.point(value,100);literal['literal']['unit_ref']='u_base'
    return m.seal(child)


def pair(questions=None,retention='none'):
    child=chain();child['queries']=[m.convert(ident='a',at=3),m.convert(ident='b',at=5)]
    return request(plan=child,displays=[display('a',questions=questions,query='a'),display('b',questions=questions,query='b')],retention=retention)


def all_questions():return [question(kind,str(i)) for i,kind in enumerate(['display_text','threshold','exact_value','selected_record','target_at','as_of','validity'])]


def main():
    DIRECTORY.mkdir(parents=True,exist_ok=True);entries=[]
    def emit(name,req,checks,normal=True):
        checks=list(checks)
        if normal:
            plan=deepcopy(req);plan.pop('budget')
            checks += [m.check(['meaning_mode'],'temporal_measurement_display_projection'),m.check(['clinical_confirmation'],'not_evaluated'),m.check(['review_verification'],'structural_only'),m.check(['uncertainty_propagated'],False),m.check(['converted_to_base'],False),m.check(['clinical_assertions_added'],[]),m.check(['source_bundle'],{'request_plan':plan} if req['retention']=='source_bundle' else None)]
        data={'schema_version':'p1-fixture-draft-1','fixture_version':1,'fixture_id':name,'condition':name[:3],'fictional':True,'review_state':'author_draft','request':deepcopy(req),'expected':{'comparison':'required_paths','checks':checks}}
        raw=(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode();filename=name.lower()+'.json';(DIRECTORY/filename).write_bytes(raw)
        entries.append({'fixture_id':name,'condition':name[:3],'path':filename,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
    def good(name,req=None,k=12,text='1.2',p=1,answers=None,sources=None,extra=(),rows=None):
        req=deepcopy(req if req is not None else request());rows=rows if rows is not None else [{'k':k,'text':text,'p':p,'answers':answers,'sources':sources}];checks=[m.check(['status'],'ok')];cert=True;used=False
        for i,row in enumerate(rows):
            checks+=checks_row(index=i,retention=req['retention'],**row)
            cert &= all(x is not None for x in (row.get('answers') if row.get('answers') is not None else [row['text']]))
            used |= any(x is not None for x in (row.get('sources') or []))
        emit(name,req,checks+[m.check(['certificate','status'],'certified' if cert else 'not_certified'),m.check(['additional_source_used'],used),*extra])
    def stop(name,req,reason,status='unassessed'):emit(name,req,[m.check(['status'],'ok'),*stopped(reason,status),m.check(['certificate','status'],'not_certified')])
    def bad(name,req,code,status='invalid_input'):emit(name,req,[m.check(['status'],status),m.check(['reason_codes'],[code])],False)
    good('J01')
    for n,d,k in [(5,4,12),(27,20,14),(-5,4,-12),(-27,20,-14)]:good('J02-'+str(n),request(n,d),k,('-' if k<0 else '')+str(abs(k)//10)+'.'+str(abs(k)%10))
    good('J03',request(2**53+1,1,p=0),2**53+1,str(2**53+1),0)
    good('J04',request(12501,10000),13,'1.3')
    for n in [-1,0,1]:good('J05-'+str(n),request(n,20),0,'0.0')
    for n,k in [(5,2),(-5,-2),(7,4),(-7,-4)]:good('J06-'+str(n),request(n,2,p=0),k,str(k),0)
    good('J07',request(1,1,p=2,unit='u_third'),67,'0.67',2)
    good('J08',request(2,4,p=2,questions=[question('exact_value')],retention='source_bundle'),50,'0.50',2,answers=[None],sources=[ratio(1,2)])
    stop('J09',request(plan=m.request([m.wrapper(magnitude=q.interval(1,2,False,True),unit='u_base')])),'unsupported_display_domain')
    good('J10',request(plan=m.request([m.wrapper(magnitude=q.interval(1,1),unit='u_base')])),10,'1.0')
    good('J11-precision',request(p=6),1210000,'1.210000',6)
    good('J11-unit',request(121,100,unit='u_ten'),121,'12.1')
    req=request();rec=req['temporal_measurement_plan']['source']['records'][0];rec['property_ref']='fiction:measurement:property:B@1';req['temporal_measurement_plan']['source']['quantities'][0]['literal']['quantity_kind_ref']='k_b';seal(req)
    good('J11-kind',req,rows=[{'k':12,'text':'1.2','kind':'k_b'}]);good('J12')
    for t in [3,6,4,5]:
        good(('J13-' if t in (3,6) else 'J14-')+str(t),request(plan=chain(at=t)),extra=[m.check(['results',0,'projection_evidence','selected',0,'record_ref'],'A' if t in (3,6) else 'B'),m.check(['steps_used'],33)])
    good('J15',request(plan=chain(3,9)),13,'1.3',extra=[m.check(['results',0,'projection_evidence','revision_evidence',0,'record_ref'],'B'),m.check(['results',0,'projection_evidence','revision_evidence',1,'record_ref'],'C')])
    child=chain();child['views']=[{'id':str(k),'as_of':m.day(k),'policy_ref':m.POLICY} for k in (6,7)]
    good('J16',request(plan=child,displays=[display(str(k),view=str(k)) for k in (6,7)]),rows=[{'k':12,'text':'1.2'},{'k':12,'text':'1.2'}],extra=[m.check(['steps_used'],59)])
    child=chain(3,9);child['source']['reviews']=[r for r in child['source']['reviews'] if r['record_ref']!='B'];stop('J17-missing',request(plan=child),'unresolved_measurement_conflict')
    child=chain();child['source']['records'][1]['revises']=[];child['source']['records'][1].pop('change_reason');child['source']['quantities'][1]['literal']['magnitude']=q.point(121,100);stop('J17-equal',request(plan=m.seal(child)),'unresolved_measurement_conflict')
    for name,child in [('pending',m.request(reviews=[])),('suspected',m.request())]:
        if name=='suspected':child['source']['records'][0]['certainty']='suspected';m.seal(child)
        stop('J18-'+name,request(plan=child),'no_adopted_measurement')
    for reviewed in [False,True]:
        req=request();s=req['temporal_measurement_plan']['source'];s['records'][0]['origin']={'kind':'ai_candidate','ref':'fiction:ai:r'};s['quantities'][0]['literal']['origin']={'kind':'ai_candidate','ref':'fiction:ai:q'}
        if not reviewed:s['reviews']=[]
        seal(req)
        if reviewed:good('J19-reviewed',req)
        else:stop('J19-pending',req,'no_adopted_measurement')
    for kind in ['unknown','unspecified']:
        for state in ['eligible','pending','suspected']:
            child=chain();b=child['source']['records'][1];b['revises']=[];b.pop('change_reason');b['validity']={'kind':kind}
            if state=='pending':child['source']['reviews']=child['source']['reviews'][:1]
            if state=='suspected':b['certainty']='suspected'
            req=request(plan=m.seal(child))
            if state=='eligible':stop('J20-'+kind+'-'+state,req,'validity_'+kind)
            else:good('J20-'+kind+'-'+state,req)
    for variant in ['pending','masked','outside','quantity','display']:
        child=chain(at=3 if variant=='outside' else 5)
        if variant=='pending':child['source']['reviews']=child['source']['reviews'][:1]
        if variant=='quantity':child['source']['quantities'][0]['literal']['required_capabilities'].append('future')
        elif variant!='display':child['source']['records'][0 if variant=='masked' else 1]['required_capabilities'].append('future')
        req=request(plan=m.seal(child))
        if variant=='display':req['displays'][0]['required_capabilities'].append('future')
        stop('J21-'+variant,req,'unknown_capability')
    for field in ['method','specimen']:
        for kind in ['unknown','unspecified']:
            req=request();req['temporal_measurement_plan']['source']['records'][0][field]={'kind':kind};stop('J22-'+field+'-'+kind,seal(req),field+'_'+kind)
    child=chain(at=3);child['source']['records'][1]['method']={'kind':'unknown'};good('J22-outside',request(plan=m.seal(child)))
    for variant in ['method','capability']:
        child=m.request([m.wrapper(magnitude=q.point(121,100),unit='u_base')],[m.record(),m.record('T','T',rec=2)],[m.review(),m.review('T',3)],slots=[{'id':s,'subject_ref':'u'} for s in ['S','T']],queries=[m.convert(),m.convert('T',ident='t')])
        if variant=='method':child['source']['records'][1]['method']={'kind':'unknown'}
        else:child['source']['records'][1]['required_capabilities'].append('future')
        good('J23-'+variant,request(plan=m.seal(child)),extra=[m.check(['steps_used'],42)])
    good('J24',request(questions=[question('threshold','a','ge',11,10),question('threshold','b','le',13,10),question('threshold','c','eq',13,10)]),answers=[True,True,False])
    # Explicit truth table for even closed [23/20,5/4] and odd open (5/4,27/20).
    for k,text,ends,expected in [(12,'1.2',[(23,20),(5,4)],[[False,None,None,True,None],[None,True,None,None,False]]),(13,'1.3',[(5,4),(27,20)],[[False,False,False,True,True],[True,True,False,False,False]])]:
        for j,(n,d) in enumerate(ends):
            for op,answer in zip(['lt','le','eq','ge','gt'],expected[j]):good('J24-'+str(k)+'-'+str(j)+'-'+op,request(k,10,questions=[question('threshold',op=op,n=n,d=d)]),k,text,answers=[answer])
    for retention in ['none','source_bundle']:
        good('J25-'+retention,pair([question('threshold')],retention),rows=[{'k':12,'text':'1.2','answers':[None],'sources':[False] if retention=='source_bundle' else None},{'k':12,'text':'1.2','answers':[None],'sources':[True] if retention=='source_bundle' else None}])
        good('J26-'+retention,pair([question('exact_value')],retention),rows=[{'k':12,'text':'1.2','answers':[None],'sources':[ratio(121,100)] if retention=='source_bundle' else None},{'k':12,'text':'1.2','answers':[None],'sources':[ratio(31,25)] if retention=='source_bundle' else None}])
        for ident in ['A','A2']:
            child=m.request([m.wrapper(magnitude=q.point(121,100),unit='u_base')],[m.record(ident,rec=2)],[m.review(ident,3)])
            source={'record_ref':ident,'record_sha256':m.record_hash(child['source'],child['source']['records'][0])}
            good('J27-'+ident+'-'+retention,request(plan=child,questions=[question('selected_record')],retention=retention),answers=[None],sources=[source] if retention=='source_bundle' else None)
        for k,t in [(8,3),(8,6),(9,3)]:
            child=m.request([m.wrapper(magnitude=q.point(121,100),unit='u_base')],queries=[m.convert(at=t)],k=k)
            good('J28-'+str(k)+'-'+str(t)+'-'+retention,request(plan=child,questions=[question('as_of','a'),question('target_at','b')],retention=retention),answers=[None,None],sources=[m.day(k),m.day(t)] if retention=='source_bundle' else None)
        for end in [9,10]:
            req=request(questions=[question('validity')],retention=retention);req['temporal_measurement_plan']['source']['records'][0]['validity']=m.span(1,end);seal(req)
            good('J29-'+str(end)+'-'+retention,req,answers=[None],sources=[m.span(1,end)] if retention=='source_bundle' else None)
    req=pair(retention='source_bundle')
    for key in ['slots','quantities','records','reviews']:req['temporal_measurement_plan']['source'][key].reverse()
    req['temporal_measurement_plan']['queries'].reverse();req['displays'].reverse();good('J30',req,rows=[{'k':12,'text':'1.2'},{'k':12,'text':'1.2'}])
    good('J31-snapshot');req=request();child=req['temporal_measurement_plan'];child['source']['records'].append(m.record('F',rec=12));child['source']['reviews'].append(m.review('F',13));good('J31-future',seal(req))
    for mode in ['none','source_bundle']:good('J32-'+mode,request(retention=mode))
    req=pair();req['temporal_measurement_plan']['queries'].append(m.convert(ident='unreferenced',at=6));req['displays']=req['displays'][:1];good('J33',req,extra=[m.check(['steps_used'],59)])
    child=m.request([m.wrapper(magnitude=q.point(121,100),unit='u_base')],[m.record('R'+str(i),rec=2) for i in range(20)],[m.review('R'+str(i),3) for i in range(20)])
    child['views']=[{'id':'v'+str(i),'as_of':m.day(8),'policy_ref':m.POLICY} for i in range(64)];child['queries']=[m.convert(ident='q'+str(i)) for i in range(64)]
    emit('J34',request(plan=child,displays=[display(view='v0',query='q0')]),[m.check(['status'],'resource_limit'),m.check(['steps_used'],100000),*stopped('step_limit',complete=False),m.check(['certificate','status'],'not_certified')])
    req=request(questions=all_questions(),retention='source_bundle');child=req['temporal_measurement_plan'];selected={'record_ref':'A','record_sha256':m.record_hash(child['source'],child['source']['records'][0])}
    for mode in ['none','source_bundle']:
        req['retention']=mode;good('J35-'+mode,req,answers=['1.2',None,None,None,None,None,None],sources=[None,False,ratio(121,100),selected,m.day(5),m.day(8),m.span()] if mode=='source_bundle' else None,extra=[m.check(['steps_used'],40)])
    good('J36')
    # Static failures are specified by code, not copied from runtime.
    for field in ['displays','retention','budget']:
        req=request();del req[field];bad('N01-missing-'+field,req,'missing_field')
    for field in ['request','display','question']:
        req=request();obj=req if field=='request' else req['displays'][0] if field=='display' else req['displays'][0]['questions'][0];obj['extra']=1;bad('N01-extra-'+field,req,'unknown_field')
    for field in ['displays','questions']:
        req=request();obj=req if field=='displays' else req['displays'][0];obj[field]*=2;bad('N01-duplicate-'+field,req,'duplicate_identifier')
        req=request();(req if field=='displays' else req['displays'][0])[field]=[];bad('N01-empty-'+field,req,'empty_collection')
    for key in ['view_ref','query_ref']:
        req=request();req['displays'][0][key]='absent';bad('N02-'+key,req,'unresolved_'+key)
    for key in ['quantity','validity','method']:
        req=request();s=req['temporal_measurement_plan']['source']
        if key=='quantity':s['quantities'][0]['literal']['magnitude']=q.point(8);code='quantity_reference_hash_mismatch'
        else:s['records'][0][key]=m.span(1,9) if key=='validity' else {'kind':'unknown'};code='review_record_hash_mismatch'
        bad('N03-'+key,req,code)
    req=request();req['temporal_measurement_plan']['source']['records'][0]['recorded_at']=m.day(12);seal(req);bad('N04-review',req,'review_precedes_record')
    for name,value in [('negative',-1),('bool',True),('string','1'),('limit',7)]:
        req=request();req['displays'][0]['decimal_places']=value;bad('N05-'+name,req,'unsupported_decimal_places' if name=='limit' else 'invalid_decimal_places','unsupported_profile' if name=='limit' else 'invalid_input')
    req=request();req['displays'][0]['rounding_policy']='future';bad('N05-policy',req,'unsupported_rounding_policy','unsupported_profile')
    for name,value in [('zero',{'numerator':1,'denominator':0}),('negative',{'numerator':1,'denominator':-1}),('bool',{'numerator':True,'denominator':1}),('text','0.1'),('bits',{'numerator':2**63,'denominator':1})]:
        req=request(questions=[question('threshold')]);req['displays'][0]['questions'][0]['threshold']=value;bad('N06-'+name,req,'rational_integer_limit' if name=='bits' else 'expected_object' if name=='text' else 'invalid_rational','resource_limit' if name=='bits' else 'invalid_input')
    for field in request()['consumer']:
        if field=='operations':continue
        req=request();req['consumer'][field]='0'*64 if field.endswith('sha256') else 'future';code='profile_spec_mismatch' if field=='profile_spec_sha256' else 'temporal_measurement_profile_mismatch' if field.startswith('temporal_measurement') else 'quantity_profile_mismatch' if field.startswith('quantity') else 'unsupported_profile';bad('N07-'+field,req,code,'unsupported_profile')
    for name,fn,code in [('schema',lambda r:r['temporal_measurement_plan'].update(schema_version='p2-measurement-request-draft-1'),'unsupported_temporal_measurement_schema'),('policy',lambda r:r['temporal_measurement_plan']['views'][0].update(policy_ref='future'),'unsupported_policy'),('compare',lambda r:r['temporal_measurement_plan']['queries'][0].update(kind='compare'),'unsupported_query_kind')]:
        req=request();fn(req);bad('N08-'+name,req,code,'unsupported_profile')
    for field in ['child_result','certificate','artifact']:
        req=request();req[field]={};bad('N09-'+field,req,'unknown_field')
    req=request();req['temporal_measurement_plan']['budget']={'max_steps':100000};bad('N09-child-budget',req,'unknown_field')
    for name,qs in [('kind',[{'id':'q','kind':'future'}]),('operator',[question('threshold',op='future')]),('metadata',[{'id':'q','kind':'target_at','answer':m.day(5)}])]:bad('N10-'+name,request(questions=qs),'unknown_field' if name=='metadata' else 'unsupported_question_'+name,'invalid_input' if name=='metadata' else 'unsupported_profile')
    bad('N11-displays',request(displays=[display(str(i)) for i in range(65)]),'item_limit','resource_limit');bad('N11-questions',request(questions=[question(ident=str(i)) for i in range(17)]),'item_limit','resource_limit')
    for name,value in [('negative',-1),('bool',True),('limit',100001)]:bad('N11-budget-'+name,request(budget=value),'step_budget_limit' if name=='limit' else 'invalid_step_budget','resource_limit' if name=='limit' else 'invalid_input')
    req=request();req['consumer']['profile_spec_sha256']='x';bad('N12-hash',req,'invalid_sha256')
    for prefix,req,total,thresholds in [('B01',request(),28,[0,16,17,26,27,28,29]),('B02',request(displays=[display('a'),display('b')]),38,[27,36,37,38]),('B03-pair',pair(),56,[44,45,54,55,56]),('B03-views',json.loads((DIRECTORY/'j16.json').read_text())['request'],59,[58,59]),('B03-seven',request(questions=all_questions()),40,[39,40])]:
        for b in thresholds:
            copy=deepcopy(req);copy['budget']['max_steps']=b;checks=[m.check(['status'],'ok' if b>=total else 'resource_limit'),m.check(['steps_used'],min(b,total)),m.check(['certificate','status'],'certified' if b>=total and prefix!='B03-seven' else 'not_certified')]
            cost={'B01':16,'B02':16,'B03-pair':34,'B03-views':37,'B03-seven':16}[prefix];paid=1+cost
            for index,d in enumerate(sorted(req['displays'],key=lambda x:x['id'])):
                paid+=8+2*len(d['questions']);complete=b>=paid;checks += [m.check(['results',index,'assessment_complete'],complete)]
                if not complete:checks+=stopped('step_limit',index=index,complete=False)
            if b==total-1:checks.append(m.check(['incomplete'],[{'stage':'completion','reason_codes':['step_limit']}]))
            emit(prefix+'-'+str(b),copy,checks)
    req=request();req['temporal_measurement_plan']['source']['records'][0]['method']={'kind':'unknown'};seal(req);req['budget']['max_steps']=27;emit('B04-stop',req,[m.check(['status'],'resource_limit'),*stopped('method_unknown'),m.check(['certificate','status'],'not_certified')])
    manifest={'schema_version':'p2-fixture-manifest-draft-1','suite':'p2-temporal-display','review_state':'author_draft','independent_review':False,'evaluation_frozen':False,'conditions':{'J':36,'N':12,'B':4},'files':entries}
    (DIRECTORY/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'files':len(entries),'checks':sum(len(json.loads((DIRECTORY/e['path']).read_text())['expected']['checks']) for e in entries)}))


if __name__=='__main__':main()
