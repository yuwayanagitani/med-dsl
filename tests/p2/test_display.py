"""P2-h：手指定期待、別計算、射影の反例、版・原情報・共有予算の境界。"""
import base64
from copy import deepcopy
from fractions import Fraction as F
import hashlib
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
from med_dsl import evaluate,host,display as native
from med_dsl.model import Problem
from med_dsl.measurement import run_measurements as measurement_runner
import gen_display_fixtures as make
import display_oracle as oracle
import p2_checks
DIRECTORY=ROOT/'examples/p2-display'
FIELDS=native.VALUE_FIELDS


def fixture(name):return json.loads((DIRECTORY/(name.lower()+'.json')).read_text())


def reference(req):
    result=evaluate(req)
    if result['status']!='ok':raise AssertionError(result)
    displays={d['id']:d for d in req['displays']}
    for row in result['results']:
        expected=oracle.row(req,displays[row['id']])
        if (row['status'],row['reason_codes'])!=(expected['status'],expected['reason_codes']):raise AssertionError((row,expected))
        if row['status']=='computed':
            for key in ('coefficient','text'):
                if row['artifact'][key]!=expected[key]:raise AssertionError((row,expected))
            if row['rounding_cell']!=expected['cell'] or row['question_results']!=expected['questions']:raise AssertionError((row,expected))
        elif row['artifact'] is not None:raise AssertionError(row)
    certified=all(r['status']=='computed' and all(q['status']=='preserved' for q in r['question_results']) for r in result['results'])
    if (result['certificate']['status']=='certified')!=certified:raise AssertionError(result)
    return result


class DisplayTests(unittest.TestCase):
    def test_hand_expectations_api_cli_manifest_and_obligations(self):
        manifest=json.loads((DIRECTORY/'manifest.json').read_text());self.assertEqual(manifest['conditions'],{'P':36,'N':12,'B':4});self.assertEqual(len(manifest['files']),145)
        declaration=json.loads((ROOT/'extensions/p2-quantity-display.json').read_text())
        self.assertEqual({o['id'] for o in declaration['obligations']},{'K-ID','K-STOP','K-INV','K-RES','R4-1','R4-2','R4-3'}|{f'DP-{i}' for i in range(1,13)})
        self.assertEqual({p.name for p in DIRECTORY.glob('*.json')},{e['path'] for e in manifest['files']}|{'manifest.json'})
        for entry in manifest['files']:
            path=DIRECTORY/entry['path'];raw=path.read_bytes();data=json.loads(raw)
            self.assertEqual((len(raw),hashlib.sha256(raw).hexdigest()),(entry['bytes'],entry['sha256']))
            self.assertEqual(p2_checks.failed_checks(evaluate(data['request']),data['expected']['checks']),[],entry['path'])
            done=subprocess.run([sys.executable,'-B','-m','med_dsl','--fixture',str(path)],cwd=ROOT,env={**os.environ,'PYTHONPATH':str(ROOT/'src')},capture_output=True,text=True,timeout=30)
            out=json.loads(done.stdout);self.assertEqual(done.returncode,{'ok':0,'invalid_input':2,'unsupported_profile':3,'resource_limit':4}[out['status']],done.stderr)
            self.assertEqual(p2_checks.failed_checks(out,data['expected']['checks']),[],entry['path'])

    def test_finite_rounding_and_formatting_against_nearest_distance(self):
        count=0
        for n in range(-200,201):
            for d in range(1,21):
                req=make.request(n,d,displays=[make.display(str(p),p) for p in range(4)])
                count+=len(reference(req)['results'])
        self.assertEqual(count,32080)

    def test_finite_threshold_questions_against_cell_witnesses(self):
        questions=rows=0
        for k in range(-20,21):
            for p in range(4):
                lo,hi,c=(F(2*k-1,2*10**p),F(2*k+1,2*10**p),k%2==0);width=hi-lo;qs=[]
                for t in (lo-width,lo,lo+width/4,(lo+hi)/2,hi-width/4,hi,hi+width):
                    for op in ('lt','le','eq','ge','gt'):qs.append(make.question('threshold',str(len(qs)).zfill(2),op,t.numerator,t.denominator))
                ds=[make.display(str(i//16),p,questions=qs[i:i+16]) for i in range(0,len(qs),16)]
                result=reference(make.request(k,10**p,displays=ds));rows+=len(result['results']);questions+=sum(len(r['question_results']) for r in result['results'])
        self.assertEqual((rows,questions),(492,5740))

    def test_seeded_fractions_and_units_keep_source_answers_separate(self):
        rng=random.Random(20261020);rows=0
        for _ in range(300):
            n=rng.choice([rng.randrange(-100000,100001),2**53+1,-2**53-1]);d=rng.randrange(1,1000)
            qs=[make.question('display_text','a'),make.question('exact_value','b'),make.question('threshold','c',rng.choice(['lt','le','eq','ge','gt']),rng.randrange(-20,21),rng.randrange(1,100))]
            req=make.request(n,d,unit=rng.choice(['u_base','u_ten','u_third','u_half']),displays=[make.display(str(i),rng.randrange(7),questions=qs) for i in range(3)],retention=rng.choice(['none','source_bundle']))
            rows+=len(reference(req)['results'])
        self.assertEqual(rows,900)

    def test_collision_encoding_typed_artifacts_and_scope(self):
        for name in ('P28','P29','P30'):
            result=evaluate(fixture(name)['request']);a,b=result['results'];self.assertEqual(a['artifact'],b['artifact']);self.assertEqual(a['artifact_sha256'],b['artifact_sha256'])
            self.assertNotEqual(a['question_results'][0]['source_answer'],b['question_results'][0]['source_answer']);self.assertTrue(result['additional_source_used']);self.assertEqual(result['certificate']['status'],'not_certified')
            for row in (a,b):
                enc=row['projection_evidence']['artifact_encoding'];self.assertEqual(json.loads(base64.b64decode(enc['bytes_base64'])),row['artifact']);self.assertTrue(enc['roundtrip_matches'])
        for name in ('P33-unit','P33-kind'):
            a,b=evaluate(fixture(name)['request'])['results'];self.assertEqual(a['artifact']['text'],b['artifact']['text']);self.assertNotEqual(a['artifact'],b['artifact'])
        result=evaluate(make.request());scope=result['certificate']['scope'];self.assertEqual(scope['kind'],'display_questions_only');self.assertIn('clinical_truth',scope['excludes']);self.assertIn('source_exact_value',scope['excludes'])
        self.assertEqual(set(result['results'][0]['artifact']),set(json.loads((ROOT/'src/med_dsl/display_spec.json').read_text())['artifact_fields']))
        self.assertEqual(evaluate(fixture('P27')['request'])['additional_source_used'],False)

    def test_cost_planning_with_histories_matches_paid_child_execution(self):
        rng=random.Random(640216);cases=0
        for _ in range(200):
            records=[];reviews=[]
            for i in range(rng.randrange(1,7)):
                ident='R'+str(i);slot=rng.choice(['S','T']);parents=[r['id'] for r in records if r['slot_ref']==slot and rng.random()<.5]
                rec=make.m.record(ident,slot,revises=parents,rec=i+2)
                if rng.random()<.2:rec['certainty']='suspected'
                if rng.random()<.2:rec['method']={'kind':'unknown'}
                records.append(rec)
                if rng.random()<.7:reviews.append(make.m.review(ident,i+2+rng.randrange(3)))
            child=make.m.request(records=records,reviews=reviews,slots=[{'id':'S','subject_ref':'u'},{'id':'T','subject_ref':'u'}],queries=[make.m.convert('S',ident='a'),make.m.convert('T',ident='b')])
            child['views']=[{'id':str(k),'as_of':make.m.hour(k),'policy_ref':make.m.POLICY} for k in (1,5,9)]
            req=make.request(plan=child,displays=[make.display(view='9',query='a')]);cost=oracle.cost(req['measurement_plan']);seen=[]
            def tracked(request):
                seen.append(request['budget']['max_steps']);answer=measurement_runner(request);self.assertEqual(answer['steps_used'],cost);return answer
            with patch('med_dsl.display.run_measurements',side_effect=tracked):result=reference(req)
            self.assertEqual(seen,[cost]);self.assertEqual(result['steps_used'],cost+12);cases+=1
        self.assertEqual(cases,200)

    def test_budget_prepaid_child_rows_completion_and_exact_values(self):
        report=p2_checks.budget_report(p2_checks.load_requests(('p2-display',)),evaluate);self.assertEqual(report['violations'],[])
        for b,expected in [(16,[]),(17,[16]),(27,[16]),(28,[16])]:
            seen=[]
            def tracked(req):seen.append(req['budget']['max_steps']);return measurement_runner(req)
            with patch('med_dsl.display.run_measurements',side_effect=tracked):r=evaluate(make.request(budget=b))
            self.assertEqual(seen,expected)
            if b==27:self.assertEqual(r['incomplete'],[{'stage':'completion','reason_codes':['step_limit']}]);self.assertTrue(r['results'][0]['assessment_complete']);self.assertEqual(r['certificate']['status'],'not_certified')
        with patch('med_dsl.display.run_measurements',side_effect=AssertionError('unfunded child')):self.assertEqual(evaluate(fixture('N11-large-plan')['request'])['status'],'resource_limit')
        for _,req in p2_checks.load_requests(('p2-display',)):
            copy=deepcopy(req);copy['budget']={'max_steps':100000};full=evaluate(copy)
            if full['status']!='ok':continue
            for maximum in range(full['steps_used']+2):
                copy['budget']['max_steps']=maximum;r=evaluate(copy);self.assertLessEqual(r['steps_used'],maximum)
                for row in r['results']:
                    if not row['assessment_complete']:
                        for key in FIELDS:self.assertIsNone(row[key])
                if r['status']=='resource_limit':self.assertNotEqual(r['certificate']['status'],'certified')

    def test_child_and_row_resource_stops_do_not_salvage_partial_values(self):
        req=make.request(retention='source_bundle')
        def child_stops(request):
            result=measurement_runner(request);result.update(status='resource_limit',reason_codes=['injected_child_limit']);return result
        with patch('med_dsl.display.run_measurements',side_effect=child_stops):result=evaluate(req)
        self.assertEqual(result['status'],'resource_limit');self.assertEqual(result['steps_used'],17)
        for key in FIELDS:self.assertIsNone(result['results'][0][key])
        req=fixture('P32')['request'];original=native._rounded
        def fail_second(point,places):
            if places==1:raise Problem('injected_row_limit',status='resource_limit')
            return original(point,places)
        with patch('med_dsl.display._rounded',side_effect=fail_second):result=evaluate(req)
        self.assertEqual(result['results'][0]['artifact']['text'],'1.25')
        for key in FIELDS:self.assertIsNone(result['results'][1][key])
        self.assertEqual(result['certificate']['status'],'not_certified')

    def test_checker_detects_early_values_empty_containers_and_certificate(self):
        for field,value in [(k,{'premature':True}) for k in FIELDS]+[('artifact',{}),('question_results',[]),('question_results',[{'projection_answer':False}])]:
            def leaky(req):
                out=evaluate(req)
                for row in out.get('results',[]):
                    if not row['assessment_complete']:row[field]=deepcopy(value);break
                return out
            self.assertTrue(p2_checks.budget_violations('display-leak',make.request(),leaky)[0],(field,value))
        def certified(req):
            result=evaluate(req)
            if result['status']=='resource_limit':result['certificate']['status']='certified'
            return result
        self.assertTrue(p2_checks.budget_violations('completion-cert',make.request(),certified)[0])

    def test_retention_hashes_order_snapshot_and_precision_are_separate(self):
        req=fixture('P28')['request'];req['measurement_plan']['views'].append({'id':'past','as_of':make.m.hour(1),'policy_ref':make.m.POLICY})
        for d in req['displays']:d['questions'] += [make.question('display_text','text')]
        before=deepcopy(req);out=evaluate(req);self.assertEqual(req,before)
        retained=deepcopy(req);retained.pop('budget');self.assertEqual(out['source_bundle']['request_plan'],retained)
        def verify_child_hash(request,out):
            child={**deepcopy(request['measurement_plan']),'budget':{'max_steps':oracle.cost(request['measurement_plan'])}}
            for row in out['results']:self.assertEqual(row['projection_evidence']['measurement_input_sha256'],make.digest(child))
        verify_child_hash(req,out)
        for field in ('slots','quantities','records','reviews'):req['measurement_plan']['source'][field].reverse()
        for field in ('views','queries'):req['measurement_plan'][field].reverse()
        req['displays'].reverse()
        for d in req['displays']:d['questions'].reverse()
        changed=evaluate(req);verify_child_hash(req,changed)
        def meaning(result):
            result=deepcopy(result);result.pop('input_sha256');result.pop('source_bundle')
            for row in result['results']:
                row['projection_evidence'].pop('measurement_input_sha256')
                row['source_evidence'].pop('measurement_input_sha256')
            return result
        self.assertEqual(meaning(out),meaning(changed))
        old=evaluate(fixture('P34-old')['request']);past=evaluate(fixture('P34-past')['request']);now=evaluate(fixture('P34-now')['request'])
        self.assertEqual(old['results'][0]['artifact'],past['results'][0]['artifact']);self.assertNotEqual(old['results'][0]['artifact'],now['results'][0]['artifact'])
        req=make.request();first=evaluate(req);req['displays'][0]['decimal_places']=2;second=evaluate(req)
        self.assertEqual(first['results'][0]['projection_evidence']['selected'],second['results'][0]['projection_evidence']['selected'])
        self.assertNotEqual(first['results'][0]['artifact'],second['results'][0]['artifact'])

    def test_native_pins_static_limits_and_refusals_precede_budget(self):
        self.assertEqual(hashlib.sha256((ROOT/'src/med_dsl/display_spec.json').read_bytes()).hexdigest(),native.SPEC_SHA256)
        for field,code in [('SPEC_SHA256','native_spec_mismatch'),('MEASUREMENT_SPEC_SHA256','measurement_profile_mismatch'),('QUANTITY_SPEC_SHA256','quantity_profile_mismatch')]:
            with patch.object(native,field,'0'*64):self.assertEqual(evaluate(make.request())['reason_codes'],[code])
        huge=make.request();huge['measurement_plan']['source']['ref']='x'*(1024*1024)
        deep=[]
        for _ in range(66):deep=[deep]
        nested=make.request();nested['measurement_plan']['source']['ref']=deep
        for req,code in [(huge,'input_size_limit'),(nested,'nesting_limit')]:
            for maximum in (0,100000):req['budget']['max_steps']=maximum;self.assertEqual(evaluate(req)['reason_codes'],[code])
        for _,req in p2_checks.load_requests(('p2-display',)):
            full=evaluate(req)
            if full['status'] not in ('invalid_input','unsupported_profile') or req.get('budget')!={'max_steps':100000}:continue
            for maximum in (0,1,7):
                copy=deepcopy(req);copy['budget']['max_steps']=maximum;self.assertEqual(p2_checks.without_input_hash(evaluate(copy)),p2_checks.without_input_hash(full))
        for number in ('1.5','NaN','Infinity'):
            raw=json.dumps(make.request()).replace('100000',number);done=subprocess.run([sys.executable,'-B','-m','med_dsl'],input=raw,capture_output=True,text=True,cwd=ROOT,env={**os.environ,'PYTHONPATH':str(ROOT/'src')},timeout=30)
            self.assertEqual(done.returncode,2);self.assertEqual(json.loads(done.stdout)['reason_codes'],['unsupported_json_number'])

    def test_arithmetic_guards_and_large_valid_inputs(self):
        for n,d,p in [(2**63-1,1,6),(-(2**63-1),2**63-1,6),(1,2**63-1,6),(2**63-1,2,0)]:reference(make.request(n,d,p,unit='u_ten'))
        with self.assertRaises(Problem):native._rounded(F(2**257),0)
        with patch('med_dsl.display.bounded',side_effect=lambda x:x):
            with self.assertRaises(Problem) as caught:native._rounded(F(10**65),0)
        self.assertEqual(caught.exception.code,'display_text_limit')

    def test_ai_origin_confirmation_and_no_clinical_writes(self):
        r=evaluate(fixture('P19-reviewed')['request']);row=r['results'][0]
        for key in ('record_origin','quantity_origin'):self.assertEqual(row['projection_evidence']['selected'][0][key]['kind'],'ai_candidate')
        self.assertEqual(row['projection_evidence']['measurement_certificate']['status'],'not_certified');self.assertEqual(r['clinical_confirmation'],'not_evaluated');self.assertEqual(r['review_verification'],'structural_only');self.assertFalse(r['uncertainty_propagated']);self.assertFalse(r['converted_to_base']);self.assertEqual(r['clinical_assertions_added'],[])
        self.assertEqual(evaluate(fixture('P19-pending')['request'])['results'][0]['artifact'],None)
        surface=host.SURFACES['p2-display-request-draft-1']._replace(run=lambda r:(_ for _ in ()).throw(AssertionError('new handler on old route')))
        with patch.dict(host.SURFACES,{'p2-display-request-draft-1':surface}):
            for _,req in p2_checks.load_requests(tuple(s for s in p2_checks.SUITES if s!='p2-display')):evaluate(req)

    def test_schema_corruption_never_raises_or_mutates_input(self):
        def paths(value,path=()):
            yield path
            if type(value) is dict:
                for key,v in value.items():yield from paths(v,path+(key,))
            elif type(value) is list:
                for i,v in enumerate(value):yield from paths(v,path+(i,))
        seed=make.request(questions=[make.question('threshold')]);count=0
        for path in paths(seed):
            for value in (None,True,False,[],{},0,-1,'future','',1.5):
                req=deepcopy(seed)
                if not path:req=deepcopy(value)
                else:
                    node=req
                    for key in path[:-1]:node=node[key]
                    node[path[-1]]=deepcopy(value)
                before=deepcopy(req);out=evaluate(req);self.assertEqual(req,before);self.assertIn(out['status'],('ok','invalid_input','unsupported_profile','resource_limit'));count+=1
        self.assertGreater(count,1000)

    def test_selected_semantic_mutants_and_child_budget_reset_are_detected(self):
        path=ROOT/'src/med_dsl/display.py';source=path.read_text()
        mutants=[('ties','quotient % 2 != 0','True','P03'),
                 ('float','scaled = bounded(point * scale)','scaled = bounded(F(float(point)) * scale)','P11'),
                 ('closed','closed = coefficient % 2 == 0','closed = True','P08'),
                 ('artifact','    raw = canonical_bytes(artifact)',"    artifact['source_exact_value'] = encode_rational(point)\n    raw = canonical_bytes(artifact)",'P28'),
                 ('source-answer',"answer = _constant(question['operator'], threshold, lower, upper, closed)","answer = _compare(question['operator'], point, threshold)",'P26-none'),
                 ('sidecar-cert',"all(q['status'] == 'preserved' for q in r['question_results'])","all(q['status'] == 'preserved' or q['source_answer'] is not None for q in r['question_results'])",'P25-source_bundle'),
                 ('double-round',"    k, text, lower, upper, closed = _rounded(point, display['decimal_places'])","    if display['decimal_places'] == 1:\n        point = Fraction(_rounded(point, 2)[0], 100)\n    k, text, lower, upper, closed = _rounded(point, display['decimal_places'])",'P32'),
                 ('child-budget',"child_request['budget']['max_steps'] = cost","child_request['budget']['max_steps'] = 100000",'P01'),
                 ('final',"        current, stage = None, 'completion'\n        budget.tick()","        current, stage = None, 'completion'",'B02-27'),
                 ('clinical',"'clinical_confirmation': 'not_evaluated'","'clinical_confirmation': 'confirmed'",'P19-reviewed')]
        for name,old,new,guard in mutants:
            self.assertEqual(source.count(old),1,name);namespace={'__name__':'med_dsl.display','__package__':'med_dsl','__file__':str(path),'F':F};exec(compile(source.replace(old,new),str(path),'exec'),namespace)
            surface=host.SURFACES['p2-display-request-draft-1']._replace(run=namespace['run_displays']);data=fixture(guard)
            if name=='child-budget':
                called=[]
                def capture(req):called.append(req['budget']['max_steps']);return measurement_runner(req)
                with patch.dict(host.SURFACES,{'p2-display-request-draft-1':surface}),patch.dict(namespace,{'run_measurements':capture}):evaluate(data['request'])
                self.assertEqual(called,[100000]);self.assertNotEqual(called,[16]);continue
            with patch.dict(host.SURFACES,{'p2-display-request-draft-1':surface}):result=evaluate(data['request'])
            self.assertTrue(p2_checks.failed_checks(result,data['expected']['checks']),name)


if __name__=='__main__':unittest.main()
