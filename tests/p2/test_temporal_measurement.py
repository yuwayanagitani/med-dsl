"""P2-i：手指定期待・区間差引き・内容確認・共有予算・旧経路を別々に検査。"""
from copy import deepcopy
from fractions import Fraction
import hashlib
import itertools
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts/research'),str(ROOT/'scripts/research/p2'),str(Path(__file__).parent)]
from med_dsl import evaluate,host,temporal_measurement as native
from med_dsl.model import Problem
from med_dsl.quantity import run_quantities as quantity_runner
from med_dsl.validation import check_json,digest
import gen_temporal_measurement_fixtures as make
import gen_quantity_fixtures as values
import temporal_measurement_oracle as oracle
import p2_checks

DIRECTORY=ROOT/'examples/p2-temporal-measurement'
FIELDS=('converted_domain','binding_evidence','calculation_evidence','diagnostics')


def fixture(name):return json.loads((DIRECTORY/(name.lower()+'.json')).read_text())


def reference(req):
    result=evaluate(req)
    if result['status']!='ok':raise AssertionError(result)
    views={v['id']:v for v in req['views']};queries={q['id']:q for q in req['queries']}
    for row in result['results']:
        expected=oracle.answer(req,views[row['view']],queries[row['query']])
        for key in ('status','reason_codes','converted_domain'):
            if row[key]!=expected[key]:raise AssertionError((key,row,expected))
        for key in ('candidate_refs','masked_records'):
            if row['diagnostics'][key]!=expected[key]:raise AssertionError((key,row,expected))
        selected=[item['record_ref'] for item in row['binding_evidence']['selected']] if row['binding_evidence'] else []
        if selected!=expected['selected']:raise AssertionError((row,expected))
    if result['steps_used']!=oracle.cost(req):raise AssertionError(('cost',result['steps_used'],oracle.cost(req)))
    return result


class TemporalMeasurementTests(unittest.TestCase):
    def test_hand_expectations_api_cli_and_manifest(self):
        manifest=json.loads((DIRECTORY/'manifest.json').read_text())
        self.assertEqual(manifest['conditions'],{'C':32,'N':12,'B':4,'O':10});self.assertEqual(len(manifest['files']),162)
        self.assertFalse(manifest['independent_review']);self.assertFalse(manifest['evaluation_frozen'])
        decl=json.loads((ROOT/'extensions/p2-temporal-measurement.json').read_text())
        self.assertEqual({o['id'] for o in decl['obligations']},{'K-ID','K-STOP','K-INV','K-RES','R5-1','R5-2','R5-3'}|{f'TM-{i}' for i in range(1,14)})
        self.assertEqual({p.name for p in DIRECTORY.glob('*.json')},{e['path'] for e in manifest['files']}|{'manifest.json'})
        count=0
        for entry in manifest['files']:
            path=DIRECTORY/entry['path'];raw=path.read_bytes();data=json.loads(raw);count+=len(data['expected']['checks'])
            self.assertEqual((len(raw),hashlib.sha256(raw).hexdigest()),(entry['bytes'],entry['sha256']))
            self.assertEqual(p2_checks.failed_checks(evaluate(data['request']),data['expected']['checks']),[],entry['path'])
            done=subprocess.run([sys.executable,'-B','-m','med_dsl','--fixture',str(path)],cwd=ROOT,env={**os.environ,'PYTHONPATH':str(ROOT/'src')},capture_output=True,text=True,timeout=30)
            result=json.loads(done.stdout);self.assertEqual(done.returncode,{'ok':0,'invalid_input':2,'unsupported_profile':3,'resource_limit':4}[result['status']]);self.assertEqual(p2_checks.failed_checks(result,data['expected']['checks']),[],entry['path'])
        self.assertEqual(count,1757)
        self.assertEqual(json.loads((ROOT/'src/med_dsl/measurement_spec.json').read_text())['properties'],native._spec()['properties'])

    def test_optional_observer_is_content_bound_and_shown_only_when_present(self):
        """P2-r：観察者は任意の項目で、記録の内容の一部。選ばれた記録に観察者があるときだけ根拠に出し、訂正は元の観察者を継がない。"""
        human={'kind':'human','ref':'fiction:human:observer'};device={'kind':'device','ref':'fiction:device:meter'}
        hashes=set()
        for first,second in itertools.product([None,human,device],[None,human,device]):
            req=make.chain(at=5)
            for index,observer in enumerate((first,second)):
                if observer:req['source']['records'][index]['observer']=deepcopy(observer)
            make.seal(req);result=reference(req);selected=result['results'][0]['binding_evidence']['selected'][0]
            self.assertEqual(selected['record_ref'],'B')
            if second:self.assertEqual(selected['record_observer'],second)
            else:self.assertNotIn('record_observer',selected)
            self.assertEqual(selected['record_sha256'],make.record_hash(req['source'],req['source']['records'][1]))
            hashes.add(selected['record_sha256'])
        self.assertEqual(len(hashes),3)                                   # 観察者の有無と値で、記録の内容の hash が変わる
        req=make.request();bare=req['source']['records'][0]
        self.assertNotIn('observer',bare);self.assertNotIn('record_observer',reference(req)['results'][0]['binding_evidence']['selected'][0])
        for value in (None,[],'x',{},{'kind':'human'},{'ref':'x'},{'kind':'robot','ref':'x'},{'kind':'human','ref':''},{'kind':'human','ref':'x','extra':1}):
            req=make.request();req['source']['records'][0]['observer']=value;make.seal(req)
            self.assertEqual(evaluate(req)['status'],'invalid_input',value)
        req=make.request();req['source']['records'][0]['observer']=deepcopy(human);make.seal(req)
        req['source']['records'][0]['observer']['kind']='device'                                    # 確認の後に観察者を替えると、確認の内容が合わない
        self.assertEqual(evaluate(req)['reason_codes'],['review_record_hash_mismatch'])

    def test_finite_contained_dags_against_interval_subtraction(self):
        histories=rows=0
        spans=[make.span(1,10),make.span(4,6),make.span(5,6)]
        for domains in itertools.product(spans,repeat=3):
            possible=[(i,j) for i in range(3) for j in range(i) if domains[j]['start']<=domains[i]['start'] and domains[i]['end']<=domains[j]['end']]
            for bits in itertools.product((False,True),repeat=len(possible)):
                for confirmed in itertools.product((False,True),repeat=3):
                    records=[];reviews=[]
                    for i,key in enumerate(('A','B','C')):
                        parents=[('A','B','C')[j] for (a,j),enabled in zip(possible,bits) if a==i and enabled]
                        record=make.record(key,revises=parents);record['validity']=deepcopy(domains[i]);records.append(record)
                        if confirmed[i]:reviews.append(make.review(key))
                    req=make.request(records=records,reviews=reviews,queries=[make.convert(ident=str(t),at=t) for t in (3,4,5,6,10)])
                    req['views']=[{'id':str(k),'as_of':make.day(k),'policy_ref':make.POLICY} for k in (3,7,9)]
                    rows+=len(reference(req)['results']);histories+=1
        self.assertEqual((histories,rows),(1032,15480))

    def test_all_confirmation_delays_and_suspected_states(self):
        rows=0
        for states in itertools.product(range(4),repeat=3):
            req=make.chain(3,9);req['source']['reviews']=[]
            for i,key in enumerate(('A','B','C')):
                if states[i]:req['source']['reviews'].append(make.review(key,11 if states[i]==2 else (3,7,9)[i]))
                if states[i]==3:req['source']['records'][i]['certainty']='suspected'
            req['views']=[{'id':str(k),'as_of':make.day(k),'policy_ref':make.POLICY} for k in (1,2,3,6,7,8,9,11)]
            req['queries']=[make.convert(ident=str(t),at=t) for t in (1,3,4,5,6,10)]
            rows+=len(reference(make.seal(req))['results'])
        self.assertEqual(rows,3072)

    def test_seeded_histories_unknowns_and_slot_scope(self):
        rng=random.Random(441207);rows=0
        for _ in range(300):
            records=[];reviews=[]
            for i in range(rng.randrange(1,7)):
                ident='r'+str(i);slot=rng.choice(['S','T']);validity=rng.choice([make.span(1,10),make.span(4,6),make.span(5,6),{'kind':'unknown'},{'kind':'unspecified'}]);parents=[]
                if validity['kind']=='bounded':parents=[r['id'] for r in records if r['slot_ref']==slot and r['validity']['kind']=='bounded' and r['validity']['start']<=validity['start'] and validity['end']<=r['validity']['end'] and rng.random()<.4]
                r=make.record(ident,slot,revises=parents,rec=i+2);r['validity']=deepcopy(validity)
                if rng.random()<.2:r['certainty']='suspected'
                if rng.random()<.2:r['method']={'kind':rng.choice(['unknown','unspecified'])}
                if rng.random()<.15:r['required_capabilities'].append('future:capability')
                records.append(r)
                if rng.random()<.7:reviews.append(make.review(ident,i+2+rng.randrange(4)))
            req=make.request(records=records,reviews=reviews,slots=[{'id':'S','subject_ref':'u'},{'id':'T','subject_ref':'u'}],queries=[make.convert(s,ident=s+str(t),at=t) for s in ('S','T') for t in (3,5,6)])
            req['views']=[{'id':str(k),'as_of':make.day(k),'policy_ref':make.POLICY} for k in (3,7,10)]
            rows+=len(reference(req)['results'])
        self.assertEqual(rows,5400)

    def test_content_hashes_bind_period_context_quantity_and_dependency(self):
        req=make.chain();baseline=reference(req);self.assertEqual(baseline['results'][0]['binding_evidence']['selected'][0]['record_ref'],'B')
        for field in ('validity','method','specimen','origin','revises'):
            copy=deepcopy(req);record=copy['source']['records'][1]
            if field=='validity':record[field]['start']=make.day(5)
            elif field in ('method','specimen'):record[field]['version']='new'
            elif field=='origin':record[field]['kind']='ai_candidate'
            else:record[field]=[];del record['change_reason']
            self.assertEqual(evaluate(copy)['reason_codes'],['review_record_hash_mismatch'])
            reference(make.seal(copy))
        for name in ('N03-quantity-origin','N03-quantity-magnitude','N03-record-validity','C29-old-hash'):
            self.assertEqual(evaluate(fixture(name)['request'])['status'],'invalid_input')
        for row in baseline['results']:
            binding=row['binding_evidence'];self.assertEqual(binding['source_sha256'],baseline['source_sha256']);selected=binding['selected'][0]
            record=next(r for r in req['source']['records'] if r['id']==selected['record_ref']);self.assertEqual(selected['record_sha256'],make.record_hash(req['source'],record))
            wrapper=next(q for q in req['source']['quantities'] if q['ref']==record['quantity_ref']['ref']);self.assertEqual(selected['quantity_ref']['sha256'],make.digest(wrapper))

    def test_budget_atomic_rows_and_funded_child_once(self):
        report=p2_checks.budget_report(p2_checks.load_requests(('p2-temporal-measurement',)),evaluate);self.assertEqual(report['violations'],[])
        for name in ('C01','C05','C06-5','C08-5','C25','C30','C13-unknown','C15-record-outside'):
            req=fixture(name)['request'];full=reference(req)
            for b in range(full['steps_used']+2):
                copy=deepcopy(req);copy['budget']['max_steps']=b;seen=[]
                def tracked(child):seen.append(child['budget']['max_steps']);self.assertEqual(check_json(child),digest(child));return quantity_runner(child)
                with patch.object(native,'run_quantities',side_effect=tracked):result=evaluate(copy)
                self.assertTrue(all(n==8 for n in seen));self.assertEqual(len(seen),sum(r['status']=='computed' for r in result['results']))
                self.assertLessEqual(result['steps_used'],b)
                for row in result['results']:
                    if not row['assessment_complete']:self.assertTrue(all(row[key] is None for key in FIELDS))
        with patch.object(native,'run_quantities',side_effect=AssertionError('unfunded')):
            self.assertEqual(evaluate(make.request(budget=15))['status'],'resource_limit')

    def test_child_resource_stop_discards_partial_values_and_receipts(self):
        req=make.request(queries=[make.convert(ident='a',at=3),make.convert(ident='b',at=5)]);calls=[]
        def stopped(child):
            calls.append(child['budget']['max_steps']);result=quantity_runner(child)
            if len(calls)==2:result.update(status='resource_limit',reason_codes=['injected_limit'])
            return result
        with patch.object(native,'run_quantities',side_effect=stopped):result=evaluate(req)
        self.assertEqual(calls,[8,8]);self.assertEqual(result['status'],'resource_limit');self.assertTrue(result['results'][0]['assessment_complete'])
        self.assertFalse(result['results'][1]['assessment_complete']);self.assertTrue(all(result['results'][1][key] is None for key in FIELDS))
        self.assertEqual(result['results'][0],reference(req)['results'][0]);self.assertEqual(result['certificate']['status'],'not_certified')
        with patch.object(native,'check_json',side_effect=Problem('child_size_limit',status='resource_limit')):stopped=evaluate(req)
        self.assertEqual(stopped['status'],'resource_limit');self.assertTrue(all(stopped['results'][0][key] is None for key in FIELDS))

    def test_unknown_period_and_capability_priority_is_not_context_inference(self):
        cases=0
        for field in ('method','specimen','validity'):
            for kind in ('unknown','unspecified'):
                for certainty in ('confirmed','suspected'):
                    req=make.request();req['source']['records'][0][field]={'kind':kind};req['source']['records'][0]['certainty']=certainty
                    reference(make.seal(req));req['source']['records'][0]['required_capabilities'].append('future')
                    result=reference(make.seal(req));self.assertEqual(result['results'][0]['reason_codes'],['unknown_capability']);cases+=1
        self.assertEqual(cases,12)
        for name in ('C16-record-future','C16-quantity-future','C16-record-other','C16-quantity-other'):self.assertEqual(reference(fixture(name)['request'])['results'][0]['status'],'computed')

    def test_revision_evidence_contains_masked_revisers_and_visible_reviews(self):
        req=make.chain(3,9);result=reference(req);row=result['results'][0];edges=row['binding_evidence']['revision_evidence']
        self.assertEqual([(e['record_ref'],e['target_ref'],e['review_refs']) for e in edges],[('B','A',['RB']),('C','B',['RC'])])
        self.assertEqual(row['diagnostics']['masked_records'],['A','B']);self.assertEqual(row['binding_evidence']['selected'][0]['record_ref'],'C')
        req['source']['reviews'].append(make.review('C',11));req['source']['reviews'][-1]['id']='RC-late';make.seal(req)
        self.assertNotIn('RC-late',json.dumps(reference(req)['results']))

    def test_seeded_exact_quantities_and_interval_domains(self):
        rng=random.Random(440722);rows=0
        for _ in range(300):
            n=rng.choice([rng.randrange(-10000,10001),2**53+1,-2**53-1]);d=rng.randrange(1,1000);unit=rng.choice(['u_base','u_ten','u_third','u_half'])
            magnitude=values.point(n,d) if rng.random()<.5 else {'kind':'interval','lower':{'numerator':n,'denominator':d},'upper':{'numerator':n+d,'denominator':d},'lower_closed':rng.choice([True,False]),'upper_closed':rng.choice([True,False])}
            req=make.request([make.wrapper(magnitude=magnitude,unit=unit)],queries=[make.convert(ident='a',at=3),make.convert(target='u_third',ident='b',at=5)]);rows+=len(reference(req)['results'])
        self.assertEqual(rows,600)

    def test_old_routes_instant_display_boundary_and_ai_origin(self):
        req=fixture('C21-reviewed')['request'];result=reference(req)
        self.assertEqual(result['clinical_confirmation'],'not_evaluated');self.assertEqual(result['review_verification'],'structural_only');self.assertEqual(result['clinical_assertions_added'],[]);self.assertFalse(result['uncertainty_propagated']);self.assertFalse(result['converted_to_base'])
        selected=result['results'][0]['binding_evidence']['selected'][0];self.assertEqual(selected['record_origin']['kind'],'ai_candidate');self.assertEqual(selected['quantity_origin']['kind'],'ai_candidate')
        import gen_display_fixtures as displays
        req=displays.request();req['measurement_plan']=make.request();del req['measurement_plan']['budget']
        self.assertEqual(evaluate(req)['reason_codes'],['unsupported_measurement_schema'])
        with patch.dict(host.SURFACES,{native_schema:surface._replace(run=lambda _:(_ for _ in ()).throw(AssertionError('old route used new handler'))) for native_schema,surface in host.SURFACES.items() if surface.profile==native.TEMPORAL_MEASUREMENT_PROFILE}):
            old=json.loads((ROOT/'examples/p2-measurement/m01.json').read_text())['request'];self.assertEqual(evaluate(old)['status'],'ok')
        for name in ('C30','C31'):
            result=reference(fixture(name)['request']);a,b=result['results'];left=Fraction(a['converted_domain']['lower']['numerator'],a['converted_domain']['lower']['denominator']);right=Fraction(b['converted_domain']['lower']['numerator'],b['converted_domain']['lower']['denominator'])
            self.assertEqual(round(left*10),round(right*10));self.assertNotEqual(a['binding_evidence']['selected'][0]['record_ref'],b['binding_evidence']['selected'][0]['record_ref']);self.assertEqual(result['certificate']['status'],'not_certified')
            if name=='C30':self.assertNotEqual(left>=Fraction(61,50),right>=Fraction(61,50))

    def test_static_limits_native_pins_and_schema_fuzz_before_budget(self):
        for _,data in p2_checks.load_suite('p2-temporal-measurement'):
            req=data['request'];full=evaluate(req)
            if full['status'] not in ('invalid_input','unsupported_profile'):continue
            if 'budget' not in req or req['budget']!={'max_steps':100000}:continue
            for b in (0,1,7):
                copy=deepcopy(req);copy['budget']['max_steps']=b;actual=evaluate(copy);self.assertEqual(p2_checks.without_input_hash(actual),p2_checks.without_input_hash(full))
        with patch.object(native,'SPEC_SHA256','0'*64):self.assertEqual(evaluate(make.request())['reason_codes'],['native_spec_mismatch'])
        for payload in ('x'*1048576,):
            req=make.request();req['source']['records'][0]['origin']['ref']=payload;self.assertEqual(evaluate(req)['reason_codes'],['input_size_limit'])
        req=make.request();v='x'
        for _ in range(70):v=[v]
        req['extra']=v;self.assertEqual(evaluate(req)['reason_codes'],['nesting_limit'])
        for value in (1.5,float('nan'),float('inf')):
            req=make.request();req['source']['quantities'][0]['literal']['magnitude']['value']['numerator']=value
            self.assertEqual(evaluate(req)['reason_codes'],['unsupported_json_type'])
        for token in ('1.5','NaN','Infinity'):
            raw=json.dumps(make.request()).replace('"max_steps": 100000','"max_steps": '+token)
            done=subprocess.run([sys.executable,'-B','-m','med_dsl'],input=raw,capture_output=True,text=True,
                cwd=ROOT,env={**os.environ,'PYTHONPATH':str(ROOT/'src')})
            self.assertEqual(done.returncode,2);self.assertEqual(json.loads(done.stdout)['reason_codes'],['unsupported_json_number'])
        base=make.chain();paths=[]
        def walk(value,path):
            paths.append(path)
            if isinstance(value,dict):
                for k,v in value.items():walk(v,path+[k])
            elif isinstance(value,list):
                for i,v in enumerate(value):walk(v,path+[i])
        walk(base,[]);count=0
        for path in paths:
            for value in (None,True,False,0,-1,'',[],{},[None],{'kind':'future'}):
                req=deepcopy(base)
                if not path:req=deepcopy(value)
                else:
                    target=req
                    for key in path[:-1]:target=target[key]
                    target[path[-1]]=deepcopy(value)
                saved=deepcopy(req);result=evaluate(req);self.assertEqual(req,saved);self.assertIn(result['status'],('ok','invalid_input','unsupported_profile','resource_limit'));count+=1
        self.assertGreater(count,1000)

    def test_permutations_raw_retention_and_snapshot_replay(self):
        req=make.chain(3,9);req['views'].append({'id':'past','as_of':make.day(6),'policy_ref':make.POLICY});req['queries'].append(make.convert(ident='outside',at=3));baseline=reference(req)
        copy=deepcopy(req)
        for key in ('slots','quantities','records','reviews'):copy['source'][key].reverse()
        copy['views'].reverse();copy['queries'].reverse();permuted=reference(copy)
        self.assertEqual(baseline['results'],permuted['results']);self.assertEqual(baseline['source_sha256'],permuted['source_sha256']);self.assertNotEqual(baseline['input_sha256'],permuted['input_sha256']);self.assertEqual(permuted['retained_source'],copy['source'])
        req=make.request();before=reference(req);after=make.chain(3,9);after['views']=deepcopy(req['views']);later=reference(after)
        # k=8ではBが見えるため、元のsnapshotを保存して再生する場合だけAを再現する。
        self.assertEqual(reference(req)['results'],before['results']);self.assertNotEqual(later['source_sha256'],before['source_sha256'])
        req=make.chain(k=6);base=reference(req);req['source']['records'].append(make.record('F',rec=12));make.seal(req);future=reference(req)
        self.assertEqual(base['results'][0]['converted_domain'],future['results'][0]['converted_domain']);self.assertEqual(base['results'][0]['binding_evidence']['selected'],future['results'][0]['binding_evidence']['selected']);self.assertNotEqual(base['source_sha256'],future['source_sha256'])

    def test_checker_rejects_unfinished_empty_values_and_false_receipts(self):
        req=make.request();real=evaluate
        for field in FIELDS:
            for injected in ({},[],False,{'value':20}):
                def broken(request):
                    result=real(request)
                    if result.get('results') and not result['results'][0]['assessment_complete']:result['results'][0][field]=deepcopy(injected)
                    return result
                violations,_=p2_checks.budget_violations('temporal',req,broken);self.assertTrue(violations,(field,injected))

    def test_selected_semantic_mutants_are_detected(self):
        source=(ROOT/'src/med_dsl/temporal_measurement.py').read_text()
        cases=[
            ('closed-end',"<= target < visible[key]['validity']['end']","<= target <= visible[key]['validity']['end']",'C06-6'),
            ('whole-record',"covering = {key for key in eligible if visible[key]['validity']['kind'] == 'bounded'\n                and visible[key]['validity']['start'] <= target < visible[key]['validity']['end']}",'covering = set(eligible)','C05'),
            ('only-final-revisers',"masked = {old for key in covering for old in visible[key]['revises']}","masked = {old for key in covering if not any(key in visible[other]['revises'] for other in covering) for old in visible[key]['revises']}",'C08-5'),
            ('latest-wins','candidates = sorted(covering - masked)',"candidates = sorted(covering - masked, key=lambda key: visible[key]['recorded_at'])[-1:]",'C11-false'),
            ('equal-merging','candidates = sorted(covering - masked)',"candidates = sorted(covering - masked)\n    if candidates and len({visible[key]['quantity_ref']['ref'] for key in candidates}) == 1: candidates = candidates[:1]",'C11-true'),
            ('future-review',"if review['record_ref'] in visible and review['recorded_at'] <= as_of:","if review['record_ref'] in visible:",'C03-before'),
            ('outside-capability',"for key, record in visible.items():","for key, record in ((key, record) for key, record in visible.items() if key in covering):",'C15-record-outside'),
            ('unknown-period-ignored','if unknown:','if False:','C14-reviewed'),
            ('old-review-reused',"if review['record_sha256'] != hashes[ref]:",'if False:','C29-old-hash'),
            ('unfunded-child','charge += 8','charge += 0','B01-15'),
            ('clinical-promotion',"'certificate': {'status': 'not_certified'","'certificate': {'status': 'certified'",'C01'),
            ('observer-kind-unchecked',"if record['observer']['kind'] not in ('human', 'device'):",'if False:','O10'),
            ('observer-not-shown',"        binding['record_observer'] = deepcopy(record['observer'])",'        pass','O01')]
        for name,old,new,ident in cases:
            self.assertEqual(source.count(old),1,name);namespace=dict(vars(native));exec(compile(source.replace(old,new),str(native.__file__),'exec'),namespace)
            surface=host.SURFACES[make.request()['schema_version']]
            with patch.dict(host.SURFACES,{surface.request_schema:surface._replace(run=namespace['run_temporal_measurements'])}):result=evaluate(fixture(ident)['request'])
            self.assertTrue(p2_checks.failed_checks(result,fixture(ident)['expected']['checks']),name)
        # 正常な数値だけでは子予算リセットを検出できないので、引数を別に観測する。
        old="child_request = _quantity_request([{**deepcopy(literal), 'id': 'operand:0'}], [operation], 8)";self.assertEqual(source.count(old),1)
        namespace=dict(vars(native));exec(compile(source.replace(old,old[:-2]+'100000)'),str(native.__file__),'exec'),namespace);seen=[]
        def spy(request):seen.append(request['budget']['max_steps']);return quantity_runner(request)
        namespace['run_quantities']=spy;namespace['run_temporal_measurements'](make.request());self.assertEqual(seen,[100000]);self.assertNotEqual(seen,[8])


if __name__=='__main__':unittest.main()
