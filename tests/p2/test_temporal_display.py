"""P2-j：手指定期待、別計算、実際の衝突、二時点・訂正根拠と共通予算。"""
import base64
from copy import deepcopy
from fractions import Fraction as F
import hashlib
from itertools import product
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
from med_dsl import evaluate,temporal_display as native
from med_dsl.model import Problem
from med_dsl.temporal_measurement import run_temporal_measurements as child_runner
import gen_temporal_display_fixtures as make
import temporal_display_oracle as oracle
import p2_checks
DIRECTORY=ROOT/'examples/p2-temporal-display'
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


class TemporalDisplayTests(unittest.TestCase):
    def test_hand_expectations_api_cli_manifest_and_obligations(self):
        manifest=json.loads((DIRECTORY/'manifest.json').read_text());self.assertEqual(manifest['conditions'],{'J':36,'N':12,'B':4});self.assertEqual(len(manifest['files']),170)
        declaration=json.loads((ROOT/'extensions/p2-temporal-display.json').read_text())
        self.assertEqual({o['id'] for o in declaration['obligations']},{'K-ID','K-STOP','K-INV','K-RES','R4-1','R4-2','R4-3'}|{f'TD-{i}' for i in range(1,13)})
        self.assertEqual({p.name for p in DIRECTORY.glob('*.json')},{e['path'] for e in manifest['files']}|{'manifest.json'})
        for entry in manifest['files']:
            path=DIRECTORY/entry['path'];raw=path.read_bytes();data=json.loads(raw)
            self.assertEqual((len(raw),hashlib.sha256(raw).hexdigest()),(entry['bytes'],entry['sha256']))
            self.assertEqual(p2_checks.failed_checks(evaluate(data['request']),data['expected']['checks']),[],entry['path'])
            done=subprocess.run([sys.executable,'-B','-m','med_dsl','--fixture',str(path)],cwd=ROOT,env={**os.environ,'PYTHONPATH':str(ROOT/'src')},capture_output=True,text=True,timeout=30)
            out=json.loads(done.stdout);self.assertEqual(done.returncode,{'ok':0,'invalid_input':2,'unsupported_profile':3,'resource_limit':4}[out['status']],done.stderr)
            self.assertEqual(p2_checks.failed_checks(out,data['expected']['checks']),[],entry['path'])

    def test_finite_rounding_against_nearest_distance(self):
        rows=0
        for n in range(-100,101):
            for d in range(1,11):rows+=len(reference(make.request(n,d,displays=[make.display(str(p),p) for p in range(7)]))['results'])
        self.assertEqual(rows,14070)
        self.assertEqual(evaluate(fixture('J04')['request'])['results'][0]['artifact']['text'],'1.3')
        self.assertEqual(native._rounded(F(125,100),1)[1],'1.2')

    def test_finite_thresholds_against_witnesses(self):
        questions=0
        for k,p in product(range(-10,11),range(4)):
            lo,hi=F(2*k-1,2*10**p),F(2*k+1,2*10**p);width=hi-lo;qs=[]
            for t in [lo-width,lo,lo+width/4,(lo+hi)/2,hi-width/4,hi,hi+width]:
                for op in ['lt','le','eq','ge','gt']:qs.append(make.question('threshold',str(len(qs)).zfill(2),op,t.numerator,t.denominator))
            ds=[make.display(str(i//16),p,questions=qs[i:i+16]) for i in range(0,len(qs),16)]
            result=reference(make.request(k,10**p,displays=ds));questions+=sum(len(r['question_results']) for r in result['results'])
        self.assertEqual(questions,2940)

    def test_confirmation_delays_revisions_and_context_against_subtraction(self):
        contexts=0
        for states in product(range(4),repeat=3):
            child=make.chain(3,9);reviews=[]
            for rec,state in zip(child['source']['records'],states):
                if state==3:rec['certainty']='suspected'
                if state in (1,2,3):reviews.append(make.m.review(rec['id'],11 if state==2 else None))
            child['source']['reviews']=reviews
            child['views']=[{'id':str(k),'as_of':make.m.day(k),'policy_ref':make.m.POLICY} for k in [2,3,6,7,8,9,11]]
            child['queries']=[make.m.convert(ident=str(t),at=t) for t in [1,3,4,5,6,10]];make.m.seal(child)
            ds=[make.display(str(k)+'-'+str(t),view=str(k),query=str(t),questions=make.all_questions()) for k in [2,3,6,7,8,9,11] for t in [1,3,4,5,6,10]]
            req=make.request(plan=child,displays=ds,retention='source_bundle');contexts+=len(reference(req)['results'])
        self.assertEqual(contexts,2688)

    def test_seeded_quantities_units_unknowns_and_intervals(self):
        rng=random.Random(20261020)
        for _ in range(200):
            child=make.chain(rng.randrange(1,4),9,rng.randrange(1,11))
            for q in child['source']['quantities']:
                q['literal']['magnitude']=make.q.point(rng.randrange(-10000,10001),rng.randrange(1,1000));q['literal']['unit_ref']=rng.choice(['u_base','u_ten','u_third','u_half'])
            for r in child['source']['records']:
                if rng.random()<.2:r['method']={'kind':rng.choice(['unknown','unspecified'])}
                if rng.random()<.1:r['required_capabilities'].append('future')
            req=make.request(plan=make.m.seal(child),displays=[make.display(p=rng.randrange(7),questions=make.all_questions())],retention=rng.choice(['none','source_bundle']));reference(req)
        for name in ['J09','J10','J20-unknown-eligible','J20-unspecified-pending','J21-masked','J22-outside','J23-method','J23-capability']:reference(fixture(name)['request'])

    def test_actual_artifact_collisions_do_not_restore_source(self):
        for name in ['J25-source_bundle','J26-source_bundle']:
            result=reference(fixture(name)['request']);a,b=result['results'];self.assertEqual(a['artifact'],b['artifact']);self.assertEqual(a['artifact_sha256'],b['artifact_sha256']);self.assertNotEqual(a['question_results'][0]['source_answer'],b['question_results'][0]['source_answer']);self.assertEqual(result['certificate']['status'],'not_certified')
        for left,right in [('J27-A-source_bundle','J27-A2-source_bundle'),('J28-8-3-source_bundle','J28-8-6-source_bundle'),('J28-8-3-source_bundle','J28-9-3-source_bundle'),('J29-9-source_bundle','J29-10-source_bundle')]:
            a=reference(fixture(left)['request'])['results'][0];b=reference(fixture(right)['request'])['results'][0]
            self.assertEqual(a['artifact'],b['artifact']);self.assertEqual(a['artifact_sha256'],b['artifact_sha256']);self.assertNotEqual(a['question_results'],b['question_results'])
        # Context changes over the input family; no universal loss theorem for fixed k/t.
        result=reference(make.request());self.assertEqual(result['certificate']['scope']['kind'],'temporal_display_questions_only')
        self.assertTrue({'as_of','target_at','validity','temporal_selection','clinical_truth'}<=set(result['certificate']['scope']['excludes']))

    def test_provenance_retention_encoding_and_seven_questions(self):
        for mode in ['none','source_bundle']:
            req=fixture('J35-'+mode)['request'];before=deepcopy(req);result=reference(req);self.assertEqual(req,before);row=result['results'][0];ev=row['projection_evidence'];self.assertEqual(ev['as_of'],make.m.day(8));self.assertEqual(ev['target_at'],make.m.day(5));self.assertEqual(ev['selected'][0]['validity'],make.m.span());self.assertEqual(ev['temporal_measurement_certificate']['status'],'not_certified')
            raw=base64.b64decode(ev['artifact_encoding']['bytes_base64']);self.assertEqual(json.loads(raw),row['artifact']);self.assertEqual(hashlib.sha256(raw).hexdigest(),row['artifact_sha256']);self.assertEqual(set(row['artifact']),set(json.loads((ROOT/'src/med_dsl/temporal_display_spec.json').read_text())['artifact_fields']))
            self.assertEqual(result['additional_source_used'],mode=='source_bundle');self.assertEqual(result['certificate']['status'],'not_certified')
            self.assertFalse({'converted_domain','exact_value','delta','temporal_measurement_row'}&set(ev))
            if mode=='none':self.assertIsNone(result['source_bundle']);self.assertIsNone(row['source_evidence'])
            else:
                plan=deepcopy(req);plan.pop('budget');self.assertEqual(result['source_bundle']['request_plan'],plan);self.assertEqual(set(row['source_evidence']),{'mode','temporal_measurement_input_sha256','temporal_measurement_row','temporal_measurement_certificate'})
        self.assertFalse(evaluate(make.request(retention='source_bundle'))['additional_source_used'])
        req=fixture('J15')['request'];row=reference(req)['results'][0];self.assertEqual([e['record_ref'] for e in row['projection_evidence']['revision_evidence']],['B','C']);self.assertEqual(row['projection_evidence']['revision_evidence'][0]['review_refs'],['RB'])

    def test_order_hashes_snapshot_future_and_precision(self):
        req=make.pair(make.all_questions(),'source_bundle');child=req['temporal_measurement_plan'];child['views'].append({'id':'past','as_of':make.m.day(2),'policy_ref':make.m.POLICY});base=reference(req)
        self.assertEqual(reference(req),base)
        for field in ['slots','quantities','records','reviews']:child['source'][field].reverse()
        for field in ['views','queries']:child[field].reverse()
        req['displays'].reverse()
        for d in req['displays']:d['questions'].reverse()
        out=reference(req);self.assertNotEqual(base['input_sha256'],out['input_sha256'])
        for a,b in zip(base['results'],out['results']):
            self.assertEqual(a['artifact'],b['artifact']);self.assertEqual(a['question_results'],b['question_results']);self.assertEqual(a['projection_evidence']['source_sha256'],b['projection_evidence']['source_sha256']);self.assertEqual(a['projection_evidence']['selected'],b['projection_evidence']['selected']);self.assertNotEqual(a['projection_evidence']['temporal_measurement_input_sha256'],b['projection_evidence']['temporal_measurement_input_sha256'])
        for request,result in [(req,out)]:
            child={**deepcopy(request['temporal_measurement_plan']),'budget':{'max_steps':oracle.cost(request['temporal_measurement_plan'])}}
            for row in result['results']:self.assertEqual(row['projection_evidence']['temporal_measurement_input_sha256'],make.digest(child))
        a=reference(make.request())['results'][0];b=reference(fixture('J31-future')['request'])['results'][0];self.assertEqual(a['artifact'],b['artifact']);self.assertNotEqual(a['projection_evidence']['source_sha256'],b['projection_evidence']['source_sha256'])
        b=reference(make.request(p=6))['results'][0];self.assertNotEqual(a['artifact'],b['artifact']);self.assertEqual(a['projection_evidence']['selected'],b['projection_evidence']['selected'])

    def test_full_plan_cost_funded_once_without_unreferenced_row_leak(self):
        for name,cost,total in [('J01',16,28),('J14-5',21,33),('J16',37,59),('J23-method',30,42),('J33',47,59),('J35-none',16,40)]:
            req=fixture(name)['request'];self.assertEqual(oracle.cost(req['temporal_measurement_plan']),cost);seen=[]
            def tracked(child):
                seen.append(child['budget']['max_steps']);out=child_runner(child);self.assertEqual(out['steps_used'],cost);return out
            with patch('med_dsl.temporal_display.run_temporal_measurements',side_effect=tracked):result=reference(req)
            self.assertEqual(seen,[cost]);self.assertEqual(result['steps_used'],total)
        req=fixture('J23-method')['request'];req['retention']='source_bundle';out=reference(req);e=out['results'][0]['source_evidence'];self.assertNotIn('results',e);self.assertEqual(e['temporal_measurement_row']['query'],'q');self.assertEqual(out['certificate']['status'],'certified')
        self.assertEqual(oracle.cost(fixture('J34')['request']['temporal_measurement_plan']),125443)
        with patch('med_dsl.temporal_display.run_temporal_measurements',side_effect=AssertionError('unfunded child')):self.assertEqual(evaluate(fixture('J34')['request'])['status'],'resource_limit')

    def test_budget_child_rows_and_final_fee(self):
        for b,called in [(0,[]),(16,[]),(17,[16]),(26,[16]),(27,[16]),(28,[16])]:
            seen=[]
            def tracked(req):seen.append(req['budget']['max_steps']);return child_runner(req)
            with patch('med_dsl.temporal_display.run_temporal_measurements',side_effect=tracked):out=evaluate(make.request(budget=b))
            self.assertEqual(seen,called);self.assertLessEqual(out['steps_used'],b)
            if b==27:self.assertEqual(out['incomplete'],[{'stage':'completion','reason_codes':['step_limit']}]);self.assertTrue(out['results'][0]['assessment_complete']);self.assertEqual(out['certificate']['status'],'not_certified')
        report=p2_checks.budget_report(p2_checks.load_requests(('p2-temporal-display',)),evaluate);self.assertEqual(report['violations'],[])
        for _,req in p2_checks.load_requests(('p2-temporal-display',)):
            if 'budget' not in req:continue
            req=deepcopy(req);req['budget']={'max_steps':100000};full=evaluate(req)
            if full['status']!='ok':continue
            for maximum in range(full['steps_used']+2):
                req['budget']['max_steps']=maximum;out=evaluate(req);self.assertLessEqual(out['steps_used'],maximum)
                for row in out['results']:
                    if not row['assessment_complete']:
                        for field in FIELDS:self.assertIsNone(row[field])
                if out['status']=='resource_limit':self.assertNotEqual(out['certificate']['status'],'certified')

    def test_child_partial_and_later_row_resource_failure_are_atomic(self):
        req=make.pair(retention='source_bundle')
        def stopped(child):
            out=child_runner(child);out.update(status='resource_limit',reason_codes=['injected_child_limit']);return out
        with patch('med_dsl.temporal_display.run_temporal_measurements',side_effect=stopped):out=evaluate(req)
        self.assertEqual(out['status'],'resource_limit');self.assertEqual(out['steps_used'],35)
        for row in out['results']:
            for key in FIELDS:self.assertIsNone(row[key])
        original=native._rounded;calls=[]
        def second(x,p):
            calls.append(x)
            if len(calls)==2:raise Problem('injected_row_limit',status='resource_limit')
            return original(x,p)
        with patch('med_dsl.temporal_display._rounded',side_effect=second):out=evaluate(req)
        self.assertEqual(out['results'][0]['artifact']['text'],'1.2')
        for key in FIELDS:self.assertIsNone(out['results'][1][key])
        self.assertEqual(out['certificate']['status'],'not_certified')

    def test_semantic_stops_do_not_answer_metadata_or_expose_values(self):
        for name in ['J18-pending','J21-display','J22-method-unknown','J09']:
            req=fixture(name)['request'];req['displays'][0]['questions']=make.all_questions();req['retention']='source_bundle';out=reference(req);row=out['results'][0]
            for key in FIELDS:
                if key!='question_results':self.assertIsNone(row[key])
            for q in row['question_results']:self.assertEqual((q['status'],q['projection_answer'],q['source_answer']),('unassessed',None,None))
            self.assertFalse(out['additional_source_used'])
        req=make.request();req['temporal_measurement_plan']['queries'][0]['target_unit_ref']='v_base';out=reference(req);self.assertEqual(out['results'][0]['status'],'not_comparable')

    def test_static_validation_hashes_pins_limits_and_native_refusals(self):
        for path in DIRECTORY.glob('n*.json'):
            req=json.loads(path.read_text())['request'];original=deepcopy(req);before=evaluate(req)
            if path.name.startswith('n11-budget') or 'budget' not in req:continue
            for b in [0,1,7]:
                req['budget']={'max_steps':b};out=evaluate(req);self.assertEqual((out['status'],out['reason_codes']),(before['status'],before['reason_codes']),path.name)
            req['budget']=original['budget'];self.assertEqual(req,original)
        for field in ['decimal_places']:
            req=make.request();req['displays'][0][field]=None;self.assertEqual(evaluate(req)['status'],'invalid_input')
        original=Path.read_bytes
        for filename in ['temporal_display_spec.json','temporal_measurement_spec.json','quantity_spec.json']:
            def corrupt(path):return b'{}' if path.name==filename else original(path)
            with patch.object(Path,'read_bytes',corrupt):self.assertEqual(evaluate(make.request())['reason_codes'],['native_spec_mismatch'])
        # Guard injection checks native limits, not naturally reachable fixture counts.
        with self.assertRaises(Problem):native._rounded(F(2**257),0)
        with self.assertRaises(Problem) as caught:native._rounded(F(10**64),0)
        self.assertEqual(caught.exception.code,'display_text_limit')
        req=make.request();req['padding']='x'*1048576;self.assertEqual(evaluate(req)['status'],'resource_limit')
        req=make.request();nested=None
        for _ in range(65):nested=[nested]
        req['padding']=nested;self.assertEqual(evaluate(req)['status'],'resource_limit')

    def test_all_nodes_type_fuzz_is_total_before_budget(self):
        req=fixture('J35-source_bundle')['request'];paths=[]
        def walk(v,path):
            paths.append(path)
            if type(v) is dict:
                for k,x in v.items():walk(x,path+[k])
            elif type(v) is list:
                for k,x in enumerate(v):walk(x,path+[k])
        walk(req,[])
        for path in paths:
            for value in [None,False,0,'',[],{}]:
                copy=deepcopy(req)
                if path:
                    obj=copy
                    for key in path[:-1]:obj=obj[key]
                    obj[path[-1]]=value
                else:copy=value
                out=evaluate(copy);self.assertIn(out['status'],['ok','invalid_input','unsupported_profile','resource_limit'])

    def test_checker_detects_early_values_false_empty_and_certificates(self):
        for key,value in [(key,{'early':True}) for key in FIELDS]+[('artifact',{}),('question_results',[]),('question_results',[{'projection_answer':False}])]:
            def leak(req):
                out=evaluate(req)
                for row in out.get('results',[]):
                    if not row['assessment_complete']:row[key]=value;break
                return out
            self.assertTrue(p2_checks.budget_violations('temporal-display',make.request(),leak)[0],(key,value))
        def early(req):
            out=evaluate(req)
            if out['status']=='resource_limit':out['certificate']['status']='certified'
            return out
        self.assertTrue(p2_checks.budget_violations('early-cert',make.request(),early)[0])

    def test_ai_origin_and_old_profiles_are_separate(self):
        out=reference(fixture('J19-reviewed')['request']);selected=out['results'][0]['projection_evidence']['selected'][0]
        self.assertEqual(selected['record_origin']['kind'],'ai_candidate');self.assertEqual(selected['quantity_origin']['kind'],'ai_candidate');self.assertEqual(out['clinical_confirmation'],'not_evaluated');self.assertEqual(out['clinical_assertions_added'],[])
        import gen_display_fixtures as h
        old=h.request();old['measurement_plan']=make.request()['temporal_measurement_plan'];self.assertEqual(evaluate(old)['status'],'unsupported_profile')
        req=make.request();req['temporal_measurement_plan']=h.request()['measurement_plan'];self.assertEqual(evaluate(req)['status'],'unsupported_profile')
        a=evaluate(h.request())['results'][0];b=reference(make.request())['results'][0];self.assertEqual((a['artifact']['text'],a['artifact']['coefficient']),('1.2',12));self.assertEqual(a['artifact']['text'],b['artifact']['text']);self.assertNotEqual(a['artifact_sha256'],b['artifact_sha256'])

    def test_upstream_static_negatives_and_old_confirmation_are_never_repaired(self):
        # Reuse I's fixed negative corpus through the new boundary; preserve the
        # complete original plan, including invalid future/unreferenced content.
        manifest=json.loads((ROOT/'examples/p2-temporal-measurement/manifest.json').read_text())
        checked=0
        for entry in manifest['files']:
            if not entry['path'].startswith('n'):continue
            child=json.loads((ROOT/'examples/p2-temporal-measurement'/entry['path']).read_text())['request']
            if 'budget' not in child:continue
            child=deepcopy(child);child['budget']={'max_steps':0};expected=evaluate(child)
            if expected['status'] not in ('invalid_input','unsupported_profile'):continue
            req=make.request(plan=child,budget=0)
            with patch('med_dsl.temporal_display.run_temporal_measurements',side_effect=AssertionError('invalid plan executed')):out=evaluate(req)
            self.assertEqual(out['status'],expected['status'],entry['path']);self.assertNotIn('results',out);checked+=1
        self.assertGreater(checked,40)
        req=make.request();plan=req['temporal_measurement_plan'];record=plan['source']['records'][0]
        import gen_measurement_fixtures as old
        plan['source']['reviews'][0]['record_sha256']=old.record_hash(plan['source'],record)
        self.assertEqual(evaluate(req)['reason_codes'],['review_record_hash_mismatch'])
        req=make.request(questions=[make.question('threshold')]);req['displays'][0]['questions'][0]['threshold']=0.1
        self.assertEqual(evaluate(req)['reason_codes'],['unsupported_json_type'])
        raw=json.dumps(req)
        done=subprocess.run([sys.executable,'-B','-m','med_dsl'],input=raw,text=True,capture_output=True,cwd=ROOT,env={**os.environ,'PYTHONPATH':str(ROOT/'src')})
        self.assertEqual(done.returncode,2);self.assertEqual(json.loads(done.stdout)['reason_codes'],['unsupported_json_number'])

    def test_seeded_whole_plan_cost_includes_eligible_outside_edges(self):
        rng=random.Random(470033)
        for _ in range(100):
            child=make.chain(rng.randrange(1,4),9,rng.choice([3,4,5,6]));child['views']=[{'id':str(k),'as_of':make.m.day(k),'policy_ref':make.m.POLICY} for k in [2,6,7,9]]
            child['queries']=[make.m.convert(ident=str(t),at=t) for t in [3,4,5,6]]
            for review in child['source']['reviews']:
                if rng.random()<.3:review['recorded_at']=make.m.day(11)
            cost=oracle.cost(child);req=make.request(plan=child,displays=[make.display(view='9',query='3')]);seen=[]
            def tracked(plan):
                seen.append(plan['budget']['max_steps']);out=child_runner(plan);self.assertEqual(out['steps_used'],cost);return out
            with patch('med_dsl.temporal_display.run_temporal_measurements',side_effect=tracked):out=reference(req)
            self.assertEqual(seen,[cost]);self.assertEqual(out['steps_used'],cost+12)

    def test_selected_mutants_are_detected_by_reference(self):
        req=make.request(questions=make.all_questions(),retention='source_bundle')
        mutations=[('_constant',lambda *a:True),('_rounded',lambda *a:(13,'1.3',F(5,4),F(27,20),False))]
        for name,mutant in mutations:
            with patch.object(native,name,side_effect=mutant):
                with self.assertRaises(AssertionError):reference(req)
        original=native._assess
        def forged(*args,**kwargs):
            out=original(*args,**kwargs)
            if out['status']=='computed':out['question_results'][-1].update(status='preserved',projection_answer=make.m.span(),reason_codes=[])
            return out
        with patch.object(native,'_assess',side_effect=forged):
            with self.assertRaises(AssertionError):reference(req)


if __name__=='__main__':unittest.main()
