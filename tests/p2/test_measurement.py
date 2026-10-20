"""P2-g：実装前の期待、到着順の参照計算、内容の拘束、変数、未知・共有予算・再現。"""
from copy import deepcopy
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
from med_dsl import evaluate, host, measurement as native
from med_dsl.model import Problem
import gen_measurement_fixtures as make
import gen_quantity_fixtures as values
import measurement_oracle as oracle
import p2_checks

DIRECTORY=ROOT/'examples/p2-measurement'
FIELDS=('converted_domain','relation_set','certain_relation','binding_evidence','calculation_evidence')


def fixture(name):return json.loads((DIRECTORY/(name.lower()+'.json')).read_text())


def compare_reference(req):
    result=evaluate(req)
    if result['status']!='ok':raise AssertionError(result)
    views={v['id']:v for v in req['views']};queries={q['id']:q for q in req['queries']}
    for row in result['results']:
        expected=oracle.answer(req,views[row['view']],queries[row['query']])
        for key in ('status','reason_codes','converted_domain','relation_set','certain_relation'):
            if row[key]!=expected[key]:raise AssertionError((key,row,expected))
        for key in ('candidate_refs','masked_records'):
            if row['diagnostics'][key]!=expected[key]:raise AssertionError((key,row,expected))
        selected=sorted(item['record_ref'] for item in row['binding_evidence']['selected']) if row['binding_evidence'] else []
        if selected!=expected['selected']:raise AssertionError((row,expected))
    return len(result['results'])


class MeasurementTests(unittest.TestCase):
    def test_hand_expectations_api_cli_and_manifest(self):
        manifest=json.loads((DIRECTORY/'manifest.json').read_text())
        self.assertEqual(manifest['conditions'],{'M':36,'N':12,'B':4})
        self.assertEqual(len(manifest['files']),137)
        declaration=json.loads((ROOT/'extensions/p2-measurement-binding.json').read_text())
        self.assertEqual({o['id'] for o in declaration['obligations']},{'K-ID','K-STOP','K-INV','K-RES','R5-1','R5-2','R5-3'}|{f'MB-{i}' for i in range(1,13)})
        self.assertEqual({p.name for p in DIRECTORY.glob('*.json')},{e['path'] for e in manifest['files']}|{'manifest.json'})
        for entry in manifest['files']:
            path=DIRECTORY/entry['path'];raw=path.read_bytes();data=json.loads(raw)
            self.assertEqual((len(raw),hashlib.sha256(raw).hexdigest()),(entry['bytes'],entry['sha256']))
            self.assertEqual(p2_checks.failed_checks(evaluate(data['request']),data['expected']['checks']),[],entry['path'])
            done=subprocess.run([sys.executable,'-B','-m','med_dsl','--fixture',str(path)],cwd=ROOT,
                                env={**os.environ,'PYTHONPATH':str(ROOT/'src')},capture_output=True,text=True,timeout=30)
            result=json.loads(done.stdout)
            self.assertEqual(done.returncode,{'ok':0,'invalid_input':2,'unsupported_profile':3,'resource_limit':4}[result['status']],done.stderr)
            self.assertEqual(p2_checks.failed_checks(result,data['expected']['checks']),[],entry['path'])

    def test_all_small_revision_graphs_and_confirmation_arrivals(self):
        histories=rows=0
        for n in range(4):
            pairs=list(itertools.combinations(range(n),2))
            for mask in range(1<<len(pairs)):
                parents=[[] for _ in range(n)]
                for bit,(old,new) in enumerate(pairs):
                    if mask&(1<<bit):parents[new].append(chr(65+old))
                for confirmed in itertools.product((False,True),repeat=n):
                    for modes in itertools.product((0,1,2),repeat=n):
                        records=[];reviews=[]
                        for i in range(n):
                            ident=chr(65+i);rec=make.record(ident,revises=parents[i],rec=2*(i+1))
                            rec['certainty']='confirmed' if confirmed[i] else 'suspected';records.append(rec)
                            if modes[i]:reviews.append(make.review(ident,2*(i+1)+(2 if modes[i]==2 else 0)))
                        req=make.request(records=records,reviews=reviews)
                        req['views']=[{'id':f'v{k}','as_of':make.hour(k),'policy_ref':make.POLICY} for k in range(1,10)]
                        rows+=compare_reference(req);histories+=1
        self.assertEqual((histories,rows),(1807,16263))

    def test_two_slot_context_variable_and_unknown_cross_product(self):
        count=0
        for shared,alias,left_mode,right_mode in itertools.product((False,True),(False,True),range(6),range(6)):
            req=make.pair(shared)
            if alias:req['queries']=[make.compare('S','S')]
            for rec,mode in zip(req['source']['records'],(left_mode,right_mode)):
                if mode==1:rec['method']={'kind':'unknown'}
                elif mode==2:rec['specimen']['version']='2'
                elif mode==3:rec['required_capabilities'].append('fiction:unknown')
                elif mode==4:rec['certainty']='suspected'
                elif mode==5:rec['effective_at']={'kind':'unspecified'}
            count+=compare_reference(make.seal(req))
        self.assertEqual(count,144)

    def test_seeded_histories_with_forks_delays_and_incomplete_context(self):
        rng=random.Random(20261020);rows=0
        for _ in range(200):
            records=[];reviews=[]
            for i in range(rng.randrange(1,7)):
                ident='R'+str(i);slot=rng.choice(['S','T'])
                parents=[r['id'] for r in records if r['slot_ref']==slot and rng.random()<0.4]
                rec=make.record(ident,slot,revises=parents,rec=i+2)
                if rng.random()<0.2:rec['certainty']='suspected'
                if rng.random()<0.2:rec['method']={'kind':rng.choice(['unknown','unspecified'])}
                if rng.random()<0.1:rec['required_capabilities'].append('fiction:unknown')
                records.append(rec)
                if rng.random()<0.7:reviews.append(make.review(ident,min(i+3,9)))
            req=make.request(records=records,reviews=reviews,slots=[{'id':'S','subject_ref':'u'},{'id':'T','subject_ref':'u'}],queries=[make.convert(ident="convert"),make.compare(ident="compare")])
            req['views']=[{'id':str(k),'as_of':make.hour(k),'policy_ref':make.POLICY} for k in (1,5,9)]
            rows+=compare_reference(req)
        self.assertEqual(rows,1200)

    def test_hash_chain_binds_all_original_content_and_cannot_reuse_confirmation(self):
        base=make.request()
        def independent(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        result=evaluate(base);binding=result['results'][0]['binding_evidence']['selected'][0]
        self.assertEqual(binding['quantity_ref']['sha256'],independent(base['source']['quantities'][0]))
        self.assertEqual(binding['record_sha256'],independent({'binding_profile':make.PROFILE,'binding_spec_sha256':make.SPEC,'source_ref':base['source']['ref'],'record':base['source']['records'][0]}))
        self.assertEqual(result['source_sha256'],independent(base['source']))
        for name in ('N03-unit_ref','N03-magnitude','N03-origin','N03-required_capabilities','N04-method','N04-subject_ref'):
            req=fixture(name)['request'];self.assertEqual(evaluate(req)['status'],'invalid_input')
        req=make.request();req['source']['ref']='fiction:another-source'
        self.assertEqual(evaluate(req)['reason_codes'],['review_record_hash_mismatch'])
        req=make.pair();req['source']['records'][0]['required_capabilities'].append('future');make.seal(req)
        req['source']['records'][0]['required_capabilities'].reverse()
        self.assertEqual(evaluate(req)['reason_codes'],['review_record_hash_mismatch'])

    def test_record_identity_preserves_shared_domains_without_aliasing_distinct_measurements(self):
        for name,expected in [('M25',['less','equal','greater']),('M26',['equal'])]:
            result=evaluate(fixture(name)['request']);row=result['results'][0]
            self.assertEqual(row['relation_set'],expected)
            ids=[s['native_quantity_id'] for s in row['binding_evidence']['selected']]
            self.assertEqual(len(set(ids)),2 if name=='M25' else 1)
            self.assertEqual(row['calculation_evidence']['reserved_steps'],12)
            self.assertEqual(row['calculation_evidence']['steps_used'],12 if name=='M25' else 11)

    def test_budget_sweep_atomic_values_receipts_and_no_child_before_reservation(self):
        report=p2_checks.budget_report(p2_checks.load_requests(('p2-measurement',)),evaluate)
        self.assertEqual(report['violations'],[])
        for name in ('M01','M11','M22-pending-record','M25','B04-16'):
            req=fixture(name)['request'];unlimited=deepcopy(req);unlimited['budget']['max_steps']=100000;full=evaluate(unlimited)
            for maximum in range(full['steps_used']+2):
                copy=deepcopy(req);copy['budget']['max_steps']=maximum;result=evaluate(copy)
                self.assertLessEqual(result['steps_used'],maximum)
                for row in result['results']:
                    if not row['assessment_complete']:
                        for key in (*FIELDS,'diagnostics'):self.assertIsNone(row[key])
                    elif row['status']!='computed':
                        for key in FIELDS:self.assertIsNone(row[key])
        req=make.request(budget=15)
        with patch('med_dsl.measurement.run_quantities',side_effect=AssertionError('child called without funding')):
            self.assertEqual(evaluate(req)['status'],'resource_limit')
        from med_dsl.quantity import run_quantities as child
        budgets=[]
        def tracked(request):budgets.append(request['budget']['max_steps']);return child(request)
        with patch('med_dsl.measurement.run_quantities',side_effect=tracked):
            self.assertEqual(evaluate(fixture('B04-27')['request'])['status'],'ok')
            self.assertEqual(evaluate(fixture('M26')['request'])['status'],'ok')
        self.assertEqual(budgets,[8,8,12])

    def test_child_size_and_injected_resource_stop_have_no_partial_receipts(self):
        req=make.pair(True);req['source']['quantities'][0]['literal']['origin']['ref']='x'*530000;make.seal(req)
        result=evaluate(req)
        self.assertEqual(result['status'],'resource_limit');self.assertEqual(result['reason_codes'],['input_size_limit'])
        self.assertFalse(result['results'][0]['assessment_complete'])
        for key in (*FIELDS,'diagnostics'):self.assertIsNone(result['results'][0][key])
        req=fixture('B04-27')['request']
        from med_dsl.quantity import run_quantities as child
        def second_fails(request):
            if request['queries'][0]['target_unit_ref']=='u_ten':raise Problem('rational_intermediate_limit',status='resource_limit')
            return child(request)
        with patch('med_dsl.measurement.run_quantities',side_effect=second_fails):result=evaluate(req)
        self.assertEqual(result['results'][0]['status'],'computed')
        for key in (*FIELDS,'diagnostics'):self.assertIsNone(result['results'][1][key])

    def test_checker_detects_receipt_diagnostic_and_completion_leaks(self):
        for field,leak in [('binding_evidence',{'premature':True}),('diagnostics',{'premature':True}),('assessment_complete',True)]:
            def leaking(req):
                result=evaluate(req)
                if result['status']=='resource_limit' and result.get('results'):result['results'][0][field]=leak
                return result
            bad,_=p2_checks.budget_violations('measurement-leak',make.request(),leaking)
            self.assertTrue(bad,field)
        req=make.pair(True);req['source']['quantities'][0]['literal']['origin']['ref']='x'*530000;make.seal(req)
        def resource_leaks(request):
            result=evaluate(request)
            if result.get('results'):result['results'][0]['binding_evidence']={'premature':True}
            return result
        self.assertTrue(p2_checks.budget_violations('full-resource-leak',req,resource_leaks)[0])

    def test_input_retention_permutation_snapshot_pins_and_no_hidden_latest_state(self):
        req=fixture('M11')['request'];original=deepcopy(req);result=evaluate(req)
        self.assertEqual(req,original);self.assertEqual(result['retained_source'],original['source'])
        for key in ('slots','quantities','records','reviews'):req['source'][key].reverse()
        req['queries'].reverse();req['views'].reverse()
        def semantic(result):return {k:v for k,v in result.items() if k not in ('input_sha256','retained_source')}
        self.assertEqual(semantic(evaluate(req)),semantic(result))
        past=fixture('M36-past')['request'];old=fixture('M36-old')['request'];now=fixture('M36-now')['request']
        self.assertEqual(evaluate(past)['results'][0]['converted_domain'],evaluate(old)['results'][0]['converted_domain'])
        self.assertNotEqual(evaluate(now)['source_sha256'],evaluate(old)['source_sha256'])
        self.assertEqual(evaluate(now)['results'][0]['binding_evidence']['selected'][0]['record_ref'],'B')
        self.assertEqual(evaluate(old)['results'][0]['binding_evidence']['selected'][0]['record_ref'],'A')

    def test_native_dependency_pins_and_structural_refusals_precede_budget(self):
        self.assertEqual(hashlib.sha256((ROOT/'src/med_dsl/measurement_spec.json').read_bytes()).hexdigest(),native.SPEC_SHA256)
        with patch('med_dsl.measurement.SPEC_SHA256','0'*64):self.assertEqual(evaluate(make.request())['reason_codes'],['native_spec_mismatch'])
        with patch('med_dsl.measurement.QUANTITY_SPEC_SHA256','0'*64):self.assertEqual(evaluate(make.request())['reason_codes'],['quantity_profile_mismatch'])
        # 親の静的上限は予算前、子の複製上限は計算時（別テスト）に区別する。
        oversized=make.request();oversized['source']['ref']='x'*(1024*1024)
        nested=make.request();deep=[]
        for _ in range(66):deep=[deep]
        nested['source']['ref']=deep
        future=make.request();future['views'][0]['as_of']=make.hour(1)
        future['source']['records'][0]['quantity_ref']['sha256']='0'*64
        for req,code in [(oversized,'input_size_limit'),(nested,'nesting_limit'),(future,'quantity_reference_hash_mismatch')]:
            for maximum in (0,100000):
                req['budget']['max_steps']=maximum
                self.assertEqual(evaluate(req)['reason_codes'],[code])
        for literal in ('1.5','NaN','Infinity'):
            raw=json.dumps(make.request()).replace('100000',literal)
            done=subprocess.run([sys.executable,'-B','-m','med_dsl'],input=raw,capture_output=True,text=True,
                                cwd=ROOT,env={**os.environ,'PYTHONPATH':str(ROOT/'src')},timeout=30)
            self.assertEqual(done.returncode,2);self.assertEqual(json.loads(done.stdout)['reason_codes'],['unsupported_json_number'])
        for _,req in p2_checks.load_requests(('p2-measurement',)):
            full=evaluate(req)
            if full['status']=='ok' or req.get('budget')!={'max_steps':100000}:continue
            for maximum in (0,1,7):
                copy=deepcopy(req);copy['budget']['max_steps']=maximum
                self.assertEqual(p2_checks.without_input_hash(evaluate(copy)),p2_checks.without_input_hash(full))

    def test_ai_origin_and_confirmation_are_preserved_without_clinical_or_base_writes(self):
        result=evaluate(fixture('M08')['request']);selected=result['results'][0]['binding_evidence']['selected'][0]
        self.assertEqual(selected['record_origin']['kind'],'ai_candidate');self.assertEqual(selected['quantity_origin']['kind'],'ai_candidate')
        self.assertEqual(result['clinical_assertions_added'],[]);self.assertFalse(result['converted_to_base'])
        self.assertEqual(result['clinical_confirmation'],'not_evaluated');self.assertEqual(result['certificate']['status'],'not_certified')
        self.assertEqual(evaluate(fixture('M07')['request'])['results'][0]['reason_codes'],['no_adopted_measurement'])
        with patch('med_dsl.measurement.run_measurements',side_effect=AssertionError('new handler on old path')):
            # hostの束縛も差し替え、旧schemaだけを照合する。
            surface=host.SURFACES['p2-measurement-request-draft-1']._replace(run=lambda r: (_ for _ in ()).throw(AssertionError('new route')))
            with patch.dict(host.SURFACES,{'p2-measurement-request-draft-1':surface}):
                for _,req in p2_checks.load_requests(('p0','p1-a','p1-b','p1-c','p2-split','p2-splits','p2-temporal','p2-quantity')):evaluate(req)

    def test_schema_corruption_never_raises_and_never_changes_input(self):
        seed=make.request()
        def paths(value,path=()):
            yield path
            if type(value) is dict:
                for key,child in value.items():yield from paths(child,path+(key,))
            elif type(value) is list:
                for i,child in enumerate(value):yield from paths(child,path+(i,))
        count=0
        for path in paths(seed):
            for value in (None,True,False,[],{},0,-1,'future','',1.5):
                req=deepcopy(seed)
                if not path:req=deepcopy(value)
                else:
                    target=req
                    for key in path[:-1]:target=target[key]
                    target[path[-1]]=deepcopy(value)
                original=deepcopy(req);result=evaluate(req)
                self.assertEqual(req,original);self.assertIn(result['status'],('ok','invalid_input','unsupported_profile','resource_limit'));count+=1
        self.assertGreater(count,700)

    def test_targeted_semantic_mutants_are_detected_by_their_guards(self):
        path=ROOT/'src/med_dsl/measurement.py';source=path.read_text()
        mutants=[('quantity-hash',"if record['quantity_ref']['sha256'] != digest(quantities[ref]):","if False:",'N03-unit_ref'),
                 ('record-hash',"if review['record_sha256'] != hashes[ref]:","if False:",'N04-method'),
                 ('review-time',"and review['recorded_at'] <= as_of:","and True:",'M05-before'),
                 ('latest',"if reasons:\n        return {**result, 'reason_codes': sorted(reasons)}\n    selected", "if reasons:\n        candidates = {s: [max(ids, key=lambda k: visible[k]['recorded_at'])] for s,ids in candidates.items() if ids}\n        reasons.clear()\n    selected",'M13'),
                 ('masked-source',"for key in eligible for target in visible[key]['supersedes']","for key in eligible - {x for i in eligible for x in visible[i]['supersedes']} for target in visible[key]['supersedes']",'M11'),
                 ('context',"if selected[0][field] != selected[1][field]:","if False:",'M30'),
                 ('unknown',"if record[field]['kind'] in ('unknown', 'unspecified'):","if False:",'M16'),
                 ('alias',"    child_request = _quantity_request(literals, [operation], reserve)","    if query['kind']=='compare' and selected[0]['quantity_ref']==selected[1]['quantity_ref']:\n        literals = literals[:1]\n        operation['right_ref'] = operation['left_ref']\n    child_request = _quantity_request(literals, [operation], reserve)",'M25'),
                 ('child-budget',"_quantity_request(literals, [operation], reserve)","_quantity_request(literals, [operation], 100000)",'M26'),
                 ('clinical',"'converted_to_base': False","'converted_to_base': True",'M08')]
        for name,old,new,guard in mutants:
            self.assertEqual(source.count(old),1,name)
            namespace={'__name__':'med_dsl.measurement','__package__':'med_dsl','__file__':str(path)}
            exec(compile(source.replace(old,new),str(path),'exec'),namespace)
            surface=host.SURFACES['p2-measurement-request-draft-1']._replace(run=namespace['run_measurements']);data=fixture(guard)
            with patch.dict(host.SURFACES,{'p2-measurement-request-draft-1':surface}):
                result=evaluate(data['request'])
            if name=='child-budget':
                called=[]
                def capture(request):called.append(request['budget']['max_steps']);return native.run_quantities(request)
                with patch.dict(host.SURFACES,{'p2-measurement-request-draft-1':surface}),patch.dict(namespace,{'run_quantities':capture}):evaluate(data['request'])
                self.assertEqual(called,[100000]);self.assertNotEqual(called,[12]);continue
            self.assertTrue(p2_checks.failed_checks(result,data['expected']['checks']),name)


if __name__=='__main__':unittest.main()
