#!/usr/bin/env python3
"""文書35の手指定期待。実装をimportせず、期待値を実行結果から作らない。"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(os.environ.get('P2_REPO') or Path(__file__).resolve().parents[3]).resolve()
PROFILE = 'p2-quantity-literal-draft-1'
SPEC = hashlib.sha256((ROOT/'src/med_dsl/quantity_spec.json').read_bytes()).hexdigest()
DIRECTORY = ROOT/'examples/p2-quantity'


def rational(n, d=1):
    return {'numerator': n, 'denominator': d}


def point(n, d=1):
    return {'kind': 'point', 'value': rational(n,d)}


def interval(a,b,lc=True,uc=True):
    return {'kind':'interval','lower':rational(a),'upper':rational(b),'lower_closed':lc,'upper_closed':uc}


def quantity(ident='a', magnitude=None, unit='u_base', kind='k_a'):
    return {'id':ident,'quantity_kind_ref':kind,'unit_ref':unit,'magnitude':deepcopy(magnitude if magnitude is not None else point(1)),
            'uncertainty':{'kind':'not_evaluated'},'origin':{'kind':'literal','ref':'fiction:quantity:'+ident},'required_capabilities':[PROFILE]}


def convert(ref='a', target='u_base', ident='q'):
    return {'id':ident,'kind':'convert','quantity_ref':ref,'target_unit_ref':target}


def compare(left='a', right='b', ident='q'):
    return {'id':ident,'kind':'compare','left_ref':left,'right_ref':right}


def request(quantities=None, queries=None, budget=100000):
    return {'schema_version':'p2-quantity-request-draft-1','operation':'evaluate_quantities',
            'consumer':{'profile':PROFILE,'profile_spec_sha256':SPEC,'operations':['evaluate_quantities']},
            'quantities':deepcopy(quantities if quantities is not None else [quantity()]),
            'queries':deepcopy(queries if queries is not None else [convert()]),'budget':{'max_steps':budget}}


def check(path,value):
    return {'path':path,'equals':value}


def domain(a,b=None,lc=True,uc=True):
    return {'lower':rational(*a),'upper':rational(*(a if b is None else b)),'lower_closed':lc,'upper_closed':uc}


def row(status='computed', converted=None, relations=None, reasons=(), index=0):
    prefix=['results',index]
    return [check(prefix+['status'],status),check(prefix+['converted_domain'],converted),
            check(prefix+['relation_set'],relations),check(prefix+['certain_relation'],relations[0] if relations and len(relations)==1 else None),
            check(prefix+['reason_codes'],list(reasons))] + ([] if status=='computed' else [check(prefix+['calculation_evidence'],None)])


def main():
    DIRECTORY.mkdir(parents=True,exist_ok=True)
    entries=[]
    def emit(name,condition,req,checks,normal=True):
        checks=deepcopy(checks)
        if normal:
            checks += [check(['meaning_mode'],'quantity_literal_result'),check(['converted_to_base'],False),
                       check(['clinical_assertions_added'],[]),check(['clinical_confirmation'],'not_evaluated'),
                       check(['uncertainty_propagated'],False),check(['certificate','status'],'not_certified'),
                       check(['retained_quantities'],sorted(deepcopy(req['quantities']),key=lambda x:x['id']))]
        value={'schema_version':'p1-fixture-draft-1','fixture_version':1,'fixture_id':name,'condition':condition,
               'fictional':True,'review_state':'author_draft','request':deepcopy(req),'expected':{'comparison':'required_paths','checks':checks}}
        raw=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode(); filename=name.lower()+'.json'
        (DIRECTORY/filename).write_bytes(raw)
        entries.append({'fixture_id':name,'condition':condition,'path':filename,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
    def good(name,req,converted=None,relations=None,status='computed',reasons=(),extra=()):
        emit(name,name[:3],req,[check(['status'],'ok'),*row(status,converted,relations,reasons),*extra])
    for n,mag,unit,target,out in [(1,point(2),'u_ten','u_base',domain((20,1))),
         (2,point(20),'u_base','u_ten',domain((2,1))),(3,point(1),'u_third','u_base',domain((2,3))),
         (4,point(1),'u_base','u_third',domain((3,2))),(5,point(2,4),'u_ten','u_base',domain((5,1))),
         (6,point(-3),'u_half','u_base',domain((-3,2))),(7,interval(1,2,False,True),'u_ten','u_base',domain((10,1),(20,1),False,True)),
         (8,interval(3,3),'u_third','u_base',domain((2,1))),
         (25,point(3),'u_hundred','u_base',domain((300,1)))]:
        good(f'Q{n:02}',request([quantity(magnitude=mag,unit=unit)],[convert(target=target)]),out)
    pairs=[(9,point(1),point(10),'u_ten',['equal']),(10,point(2),point(3),'u_base',['less']),
           (11,point(3),point(2),'u_base',['greater']),(12,interval(1,2,True,False),interval(2,3),'u_base',['less']),
           (13,interval(1,2),interval(2,3),'u_base',['less','equal']),
           (14,interval(1,3,False,False),interval(2,4),'u_base',['less','equal','greater']),
           (15,interval(1,2),interval(1,2),'u_base',['less','equal','greater'])]
    for n,left,right,unit,rels in pairs:
        good(f'Q{n:02}',request([quantity(magnitude=left,unit=unit),quantity('b',right)],[compare()]),relations=rels)
    good('Q16',request([quantity(magnitude=interval(1,2))],[compare('a','a')]),relations=['equal'])
    good('Q17',request([quantity(magnitude=point(25),unit='w_hundredth',kind='k_ratio_a')],[convert(target='w_base')]),domain((1,4)))
    for n,left,right,reason in [(18,quantity(),quantity('b',kind='k_b'),'incompatible_quantity_kind'),
         (19,quantity(),quantity('b',unit='v_base',kind='k_c'),'incompatible_dimension'),
         (20,quantity(unit='w_base',kind='k_ratio_a'),quantity('b',unit='w_base',kind='k_ratio_b'),'incompatible_quantity_kind')]:
        good(f'Q{n:02}',request([left,right],[compare()]),status='not_comparable',reasons=[reason])
    unknown=quantity(unit='u_base_future')
    good('Q21',request([unknown],[compare('a','a')]),status='unassessed',reasons=['unknown_unit'])
    good('Q22',request([quantity(kind='k_future')]),status='unassessed',reasons=['unknown_quantity_kind'])
    unknown['required_capabilities'].append('fiction:future')
    good('Q23',request([unknown],[compare('a','a')]),status='unassessed',reasons=['unknown_capability'])
    ai=quantity(magnitude=point(2),unit='u_ten');ai['origin']['kind']='ai_candidate'
    good('Q24',request([ai]),domain((20,1)))
    def bad(name,req,code,status='invalid_input'):
        emit(name,name[:3],req,[check(['status'],status),check(['reason_codes'],[code])],False)
    for suffix,num,den in [('zero',1,0),('negative',1,-1),('bool-n',True,1),('bool-d',1,True),('string','1',1)]:
        bad('N01-'+suffix,request([quantity(magnitude=point(num,den))]),'invalid_rational')
    req=request();del req['quantities'][0]['magnitude']['value']['denominator'];bad('N01-missing',req,'missing_field')
    good('N02-valid',request([quantity(magnitude=point(2**63-1,2**63-1))]),domain((1,1)))
    for suffix,num,den in [('n',2**63,1),('negative-n',-(2**63),1),('d',1,2**63)]:
        bad('N02-'+suffix,request([quantity(magnitude=point(num,den))]),'rational_integer_limit','resource_limit')
    for suffix,mag in [('inverted',interval(2,1)),('empty',interval(1,1,True,False)),('flags',interval(1,2,1,True))]:
        bad('N03-'+suffix,request([quantity(magnitude=mag)]),'invalid_interval')
    req=request([quantity(magnitude=interval(1,2))]);del req['quantities'][0]['magnitude']['upper'];bad('N03-missing',req,'missing_field')
    bad('N04',request([quantity(unit='v_base')]),'input_dimension_mismatch')
    for field in ['uncertainty','required_capabilities']:
        req=request();del req['quantities'][0][field];bad('N05-'+field,req,'missing_field')
    req=request();req['quantities'][0]['required_capabilities']=[];bad('N05-profile',req,'missing_quantity_capability')
    bad('N06-string',request([quantity(magnitude=point('2.3'))]),'invalid_rational')
    for field in ['units','scale','clinical_meaning']:
        req=request();req[field]={};bad('N07-'+field,req,'unknown_field')
    for kind in ['censored','unbounded','statistical_interval']:
        bad('N08-'+kind,request([quantity(magnitude={'kind':kind})]),'unsupported_magnitude','unsupported_profile')
    req=request();req['quantities'][0]['uncertainty']={'kind':'standard_deviation'};bad('N09-uncertainty',req,'unsupported_uncertainty','unsupported_profile')
    for kind in ['parse_external','round_display','convert_kind']:
        req=request();req['queries'][0]={'id':'q','kind':kind};bad('N09-'+kind,req,'unsupported_query_kind','unsupported_profile')
    for suffix,field,value,code in [('profile','profile','future','unsupported_profile'),('hash','profile_spec_sha256','0'*64,'profile_spec_mismatch'),('ops','operations',['future'],'unsupported_operation')]:
        req=request();req['consumer'][field]=value;bad('N10-'+suffix,req,code,'unsupported_profile')
    req=request();req['operation']='future';bad('N10-operation',req,'unsupported_operation','unsupported_profile')
    req=request();req['queries'][0]={'id':'q','kind':'future'};bad('N10-query',req,'unsupported_query_kind','unsupported_profile')
    bad('N11-ref',request(queries=[convert('missing')]),'unresolved_quantity')
    bad('N11-duplicate',request([quantity(),quantity()]),'duplicate_identifier')
    bad('N11-quantities',request([]),'empty_collection');bad('N11-queries',request(queries=[]),'empty_collection')
    for suffix,budget in [('negative',-1),('bool',True),('string','10')]:bad('N11-budget-'+suffix,request(budget=budget),'invalid_step_budget')
    bad('N11-budget-limit',request(budget=100001),'step_budget_limit','resource_limit')
    bad('N11-item-limit',request([quantity(str(i)) for i in range(65)]),'item_limit','resource_limit')
    # N12は既存例の前後比較・配列並べ替え・基底への昇格の変異を専用テストで検査する。
    emit('B01','B01',request(budget=0),[check(['status'],'resource_limit'),check(['steps_used'],0),*row('unassessed',reasons=['step_limit'])])
    for b in [7,8,9]:
        checks=[check(['status'],'ok' if b>=8 else 'resource_limit'),check(['steps_used'],min(b,8))]
        checks+=row(converted=domain((1,1))) if b>=8 else row('unassessed',reasons=['step_limit'])
        emit('B02-'+str(b),'B02',request(budget=b),checks)
    for alias,cost in [(False,12),(True,11)]:
        for b in [cost-1,cost]:
            req=request([quantity()] if alias else [quantity(),quantity('b')],[compare('a','a' if alias else 'b')],b)
            checks=[check(['status'],'ok' if b==cost else 'resource_limit'),check(['steps_used'],b)]
            checks+=row(relations=['equal']) if b==cost else row('unassessed',reasons=['step_limit'])
            emit(f'B03-{str(alias).lower()}-{b}','B03',req,checks)
    for b in [8,13,14,15]:
        req=request(queries=[convert(ident='a'),convert(target='u_ten',ident='b')],budget=b)
        checks=[check(['status'],'ok' if b>=14 else 'resource_limit'),check(['steps_used'],min(b,14)),*row(converted=domain((1,1)))]
        checks+=row(converted=domain((1,10)),index=1) if b>=14 else row('unassessed',reasons=['step_limit'],index=1)
        emit('B04-'+str(b),'B04',req,checks)
    manifest={'schema_version':'p2-fixture-manifest-draft-1','suite':'p2-quantity','review_state':'author_draft',
              'independent_review':False,'evaluation_frozen':False,'files':entries}
    (DIRECTORY/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'files':len(entries),'conditions':len({e['condition'] for e in entries})}))


if __name__=='__main__':main()
