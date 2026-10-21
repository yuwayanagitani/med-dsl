"""P2-f：手指定期待、整数対と証人点による参照計算、停止・予算・原情報保存。"""
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
from med_dsl import evaluate, host, quantity as native
from med_dsl.model import Problem
from med_dsl.validation import decode_json
import gen_quantity_fixtures as make
import p2_checks
import quantity_oracle as oracle

DIRECTORY=ROOT/'examples/p2-quantity'
VALUE_FIELDS=('converted_domain','relation_set','certain_relation','calculation_evidence')


def fixture(name):
    return json.loads((DIRECTORY/(name.lower()+'.json')).read_text())


def domains():
    for a,b in itertools.combinations_with_replacement((-1,0,1),2):
        for lc,uc in itertools.product((False,True),repeat=2):
            if a<b or lc and uc:yield make.interval(a,b,lc,uc)


# draft-1 の単位表（版の記録の旧版）。native 仕様を読まず、文書54の§1 から独立に写した表
UNITS_DRAFT_1 = {'u_base': ((1, 0), (1, 1)), 'u_ten': ((1, 0), (10, 1)), 'u_third': ((1, 0), (1, 3)), 'u_half': ((1, 0), (1, 2)),
                 'v_base': ((0, 1), (1, 1)), 'w_base': ((0, 0), (1, 1)), 'w_hundredth': ((0, 0), (1, 100))}
# 宣言した改訂（文書54の§1）：u_third の倍率を改訂し、u_hundred を追加
DECLARED_REVISION = {'u_third': ((1, 0), (2, 3)), 'u_hundred': ((1, 0), (100, 1))}


class QuantityTests(unittest.TestCase):
    def test_the_unit_table_matches_the_declared_revision(self):
        """VR-1（単一の木の部分）：draft-2 の単位表は、draft-1 の表に、宣言した変更だけを加えたもの。"""
        spec = json.loads((ROOT / 'src/med_dsl/quantity_spec.json').read_text())
        table = {name: (tuple(unit['dimension']), (unit['scale']['numerator'], unit['scale']['denominator'])) for name, unit in spec['units'].items()}
        self.assertEqual(table, {**UNITS_DRAFT_1, **DECLARED_REVISION})
        self.assertEqual(set(table) - set(UNITS_DRAFT_1), {'u_hundred'})                              # 追加は1件だけ
        self.assertEqual({n for n in UNITS_DRAFT_1 if table[n] != UNITS_DRAFT_1[n]}, {'u_third'})   # 変更は1件だけ
        self.assertEqual({name: oracle.SCALES[name] for name in table}, {name: table[name][1] for name in table})   # 別計算の表と一致

    def test_hand_expectations_api_cli_and_manifest(self):
        manifest=json.loads((DIRECTORY/'manifest.json').read_text())
        self.assertEqual(len(manifest['files']),80)
        declaration=json.loads((ROOT/'extensions/p2-quantity-literal.json').read_text())
        self.assertEqual({o['id'] for o in declaration['obligations']},{'K-ID','K-STOP','K-INV','K-RES'}|{f'R2-{i}' for i in range(1,6)}|{f'QT-{i}' for i in range(1,9)}|{'VR-1'})
        self.assertFalse(manifest['independent_review']);self.assertFalse(manifest['evaluation_frozen'])
        self.assertEqual({p.name for p in DIRECTORY.glob('*.json')},{e['path'] for e in manifest['files']}|{'manifest.json'})
        for entry in manifest['files']:
            raw=(DIRECTORY/entry['path']).read_bytes();data=json.loads(raw)
            self.assertEqual((len(raw),hashlib.sha256(raw).hexdigest()),(entry['bytes'],entry['sha256']))
            self.assertEqual(p2_checks.failed_checks(evaluate(data['request']),data['expected']['checks']),[],entry['path'])
            done=subprocess.run([sys.executable,'-B','-m','med_dsl','--fixture',str(DIRECTORY/entry['path'])],
                                cwd=ROOT,env={**os.environ,'PYTHONPATH':str(ROOT/'src')},capture_output=True,text=True,timeout=30)
            result=json.loads(done.stdout)
            self.assertEqual(done.returncode,{'ok':0,'invalid_input':2,'unsupported_profile':3,'resource_limit':4}[result['status']],done.stderr)
            self.assertEqual(p2_checks.failed_checks(result,data['expected']['checks']),[],entry['path'])

    def test_finite_domain_relations_against_witness_points(self):
        variants=[make.quantity(magnitude=d,unit=u) for d in domains() for u in ('u_base','u_ten','u_third','u_half')]
        self.assertEqual(len(variants),60)
        rows=0
        for left,right in itertools.product(variants,repeat=2):
            right={**deepcopy(right),'id':'b'}
            result=evaluate(make.request([left,right],[make.compare()]))
            self.assertEqual(result['status'],'ok',result)
            self.assertEqual(result['results'][0]['relation_set'],oracle.relations(left,right))
            rows+=1
        for left in variants:
            row=evaluate(make.request([left],[make.compare('a','a')]))['results'][0]
            self.assertEqual(row['relation_set'],oracle.relations(left,left,True));rows+=1
        self.assertEqual(rows,3660)

    def test_exact_conversion_and_roundtrip_for_each_compatible_unit(self):
        rows=0
        for units,kind in [(('u_base','u_ten','u_third','u_half'),'k_a'),(('w_base','w_hundredth'),'k_ratio_a'),(('v_base',),'k_c')]:
            for source,target,mag in itertools.product(units,units,[*domains(),make.point(-7,11),make.point(2**63-1,2**63-2)]):
                item=make.quantity(magnitude=mag,unit=source,kind=kind)
                row=evaluate(make.request([item],[make.convert(target=target)]))['results'][0]
                self.assertEqual(row['converted_domain'],oracle.converted(item,target));rows+=1
                # 大きな正規化値は入力63bit上限を超え得る。往復は断片の入力範囲内だけを要求する。
                back={**deepcopy(item),'unit_ref':target,'magnitude':{'kind':'interval',**row['converted_domain']}}
                if all(abs(back['magnitude'][k]['numerator']).bit_length()<=63 and back['magnitude'][k]['denominator'].bit_length()<=63 for k in ('lower','upper')):
                    again=evaluate(make.request([back],[make.convert(target=source)]))['results'][0]
                    self.assertEqual(again['converted_domain'],oracle.converted(item,source))
        self.assertEqual(rows,357)

    def test_seeded_rational_intervals(self):
        rng=random.Random(20261020)
        for _ in range(500):
            items=[]
            for ident in ('a','b'):
                a,b=sorted([rng.randrange(-100000,100000),rng.randrange(-100000,100000)])
                m=make.interval(a,b,rng.choice([True,False]),rng.choice([True,False]))
                if a==b:m['lower_closed']=m['upper_closed']=True
                m['lower']['denominator']=m['upper']['denominator']=rng.randrange(1,1000)
                items.append(make.quantity(ident,m,rng.choice(['u_base','u_ten','u_third','u_half'])))
            req=make.request(items,[make.compare(),make.convert(target='u_third',ident='z')])
            rows=evaluate(req)['results']
            self.assertEqual(rows[0]['relation_set'],oracle.relations(*items))
            self.assertEqual(rows[1]['converted_domain'],oracle.converted(items[0],'u_third'))

    def test_unknowns_priority_unused_literals_and_same_reference(self):
        q=make.quantity(kind='future-kind',unit='future-unit')
        req=make.request([q],[make.compare('a','a')]);row=evaluate(req)['results'][0]
        self.assertEqual(row['reason_codes'],['unknown_quantity_kind','unknown_unit'])
        for key in VALUE_FIELDS:self.assertIsNone(row[key])
        req['quantities'][0]['required_capabilities'].append('future-cap')
        self.assertEqual(evaluate(req)['results'][0]['reason_codes'],['unknown_capability'])
        req=make.request([make.quantity(),{**q,'id':'unused'}]);req['quantities'][1]['required_capabilities'].append('future-cap')
        self.assertEqual(evaluate(req)['results'][0]['status'],'computed')
        self.assertEqual(len(evaluate(req)['retained_quantities']),2)
        req=make.request(queries=[make.convert(target='v_base')])
        self.assertEqual(evaluate(req)['results'][0]['reason_codes'],['incompatible_dimension'])
        req['queries'][0]['target_unit_ref']='U_BASE'
        self.assertEqual(evaluate(req)['results'][0]['reason_codes'],['unknown_unit'])

    def test_input_immutability_array_permutation_and_origin_retention(self):
        req=make.request([make.quantity('b',make.point(2,4),'u_ten'),make.quantity()],
                         [make.compare('a','b','z'),make.convert('b',ident='a')],budget=9)
        original=deepcopy(req);result=evaluate(req)
        self.assertEqual(req,original)
        for field in ('quantities','queries'):req[field].reverse()
        self.assertEqual(p2_checks.without_input_hash(result),p2_checks.without_input_hash(evaluate(req)))
        self.assertEqual(result['retained_quantities'][1]['magnitude']['value'],make.rational(2,4))
        for kind in ('literal','imported_literal','ai_candidate'):
            req=make.request();req['quantities'][0]['origin']['kind']=kind
            result=evaluate(req)
            self.assertEqual(result['results'][0]['calculation_evidence']['operands'][0]['origin'],req['quantities'][0]['origin'])
            self.assertEqual(result['retained_quantities'],req['quantities'])
            self.assertEqual(result['clinical_confirmation'],'not_evaluated')
            self.assertFalse(result['uncertainty_propagated'])

    def test_budget_sweep_atomic_rows_and_exact_costs(self):
        requests=p2_checks.load_requests(('p2-quantity',))
        self.assertEqual(p2_checks.budget_report(requests,evaluate)['violations'],[])
        for _,req in requests:
            full=evaluate(req)
            if 'steps_used' not in full:continue
            for maximum in range(full['steps_used']+2):
                copy=deepcopy(req);copy['budget']['max_steps']=maximum;result=evaluate(copy)
                self.assertLessEqual(result['steps_used'],maximum)
                for row in result['results']:
                    if row['status']!='computed':
                        for field in VALUE_FIELDS:self.assertIsNone(row[field])
        self.assertEqual(evaluate(make.request())['steps_used'],8)
        self.assertEqual(evaluate(make.request([make.quantity(),make.quantity('b')],[make.compare()]))['steps_used'],12)
        self.assertEqual(evaluate(make.request(queries=[make.compare('a','a')]))['steps_used'],11)

    def test_budget_checker_detects_each_quantity_value_leak(self):
        req=make.request()
        for field,leak in [('converted_domain',make.domain((0,1))),('relation_set',['equal']),
                           ('certain_relation','equal'),('calculation_evidence',{'premature':True})]:
            def leaking(request):
                result=evaluate(request)
                if result.get('status')=='resource_limit' and result.get('results'):
                    result['results'][0][field]=leak
                return result
            problems,_=p2_checks.budget_violations('quantity-leak',req,leaking)
            self.assertTrue(any(p[2]=='value_on_stopped_row' for p in problems),field)

    def test_collection_limits_and_semantic_stops_use_full_row_cost(self):
        req=make.request([make.quantity(str(i)) for i in range(64)],
                         [make.convert('0',ident=str(i)) for i in range(64)])
        result=evaluate(req)
        self.assertEqual(result['status'],'ok');self.assertEqual(result['steps_used'],449)
        req['queries'].append(make.convert('0',ident='extra'));req['budget']['max_steps']=0
        self.assertEqual(evaluate(req)['reason_codes'],['item_limit'])
        for req,cost in [(fixture('Q21')['request'],11),(fixture('Q23')['request'],11),(fixture('Q18')['request'],12)]:
            full=evaluate(req);self.assertEqual(full['steps_used'],cost)
            req['budget']['max_steps']=cost-1
            result=evaluate(req)
            self.assertEqual(result['status'],'resource_limit')
            self.assertEqual(result['results'][0]['reason_codes'],['step_limit'])
            for key in VALUE_FIELDS:self.assertIsNone(result['results'][0][key])

    def test_structural_refusals_precede_budget(self):
        for _,req in p2_checks.load_requests(('p2-quantity',)):
            full=evaluate(req)
            if 'results' in full:continue
            for maximum in (0,1,7):
                copy=deepcopy(req);copy['budget']={'max_steps':maximum}
                # 予算欄そのものを変える負例は別の入力になる。
                if req['budget']!={'max_steps':100000}:continue
                self.assertEqual(p2_checks.without_input_hash(evaluate(copy)),p2_checks.without_input_hash(full))
        req=make.request(budget=0);req['quantities'].append(make.quantity('unused',make.interval(2,1)))
        self.assertEqual(evaluate(req)['reason_codes'],['invalid_interval'])

    def test_non_json_numeric_types_and_raw_json_are_rejected(self):
        for value in (1.5,float('nan'),float('inf'),(1,2),None,True,'2.30'):
            req=make.request();req['quantities'][0]['magnitude']['value']['numerator']=value
            self.assertEqual(evaluate(req)['status'],'invalid_input')
        for number in ('2.3','NaN','Infinity','-Infinity'):
            raw=json.dumps(make.request()).replace('"numerator": 1','"numerator": '+number).encode()
            with self.assertRaises(Problem):decode_json(raw)
        for field in ('quantity_kind_ref','unit_ref'):
            for value in ([],{},None,True):
                req=make.request();req['quantities'][0][field]=value
                self.assertEqual(evaluate(req)['status'],'invalid_input')

    def test_native_identity_and_integer_bounds(self):
        self.assertEqual(hashlib.sha256((ROOT/'src/med_dsl/quantity_spec.json').read_bytes()).hexdigest(),native.SPEC_SHA256)
        with patch('med_dsl.quantity.SPEC_SHA256','0'*64):
            self.assertEqual(evaluate(make.request())['reason_codes'],['native_spec_mismatch'])
        scales=list(oracle.SCALES.values())
        for n,d,(sn,sd),(tn,td) in itertools.product((-(2**63-1),2**63-1),(1,2**63-1),scales,scales):
            self.assertLessEqual(abs(n*sn).bit_length(),70);self.assertLessEqual((d*sd).bit_length(),70)
            self.assertLessEqual(abs(n*sn*td).bit_length(),77);self.assertLessEqual((d*sd*tn).bit_length(),77)
            self.assertLessEqual(abs(n*sn*d*sd).bit_length(),140)
        self.assertEqual(native._bounded(native.Fraction(1<<255,1)),native.Fraction(1<<255,1))
        with self.assertRaises(Problem):native._bounded(native.Fraction(1<<256,1))
        with patch('med_dsl.quantity._bounded',side_effect=Problem('rational_intermediate_limit',status='resource_limit')):
            result=evaluate(make.request())
        self.assertEqual(result['status'],'resource_limit')
        for key in VALUE_FIELDS:self.assertIsNone(result['results'][0][key])

    def test_no_clinical_or_base_promotion_and_no_base_reads(self):
        with patch('med_dsl.ledger.select_view',side_effect=AssertionError('base read')):
            # 基底を参照しないR2。量の計算はAI候補でも可能だが、臨床採用は行わない。
            result=evaluate(fixture('Q24')['request'])
        self.assertFalse(result['converted_to_base']);self.assertEqual(result['clinical_assertions_added'],[])
        self.assertEqual(result['certificate']['status'],'not_certified')
        for field in ('source','ledger','clinical_confirmation'):
            req=make.request();req[field]={}
            self.assertEqual(evaluate(req)['reason_codes'],['unknown_field'])
        with patch('med_dsl.quantity._calculate',side_effect=AssertionError('new module on old route')):
            for _,req in p2_checks.load_requests(('p0','p1-a','p1-b','p1-c','p2-split','p2-splits','p2-temporal')):
                self.assertNotEqual(evaluate(req).get('reason_codes'),['extension_absent'])

    def test_each_targeted_semantic_mutant_is_detected(self):
        path=ROOT/'src/med_dsl/quantity.py';source=path.read_text()
        mutants=[('scale','1 / target_scale','target_scale','Q04'),
                 ('floating',"'numerator': value.numerator","'numerator': Fraction(float(value)).numerator",'N02-valid'),
                 ('midpoint',"_bounded(domain[0] * factor), _bounded(domain[1] * factor)","_bounded((domain[0]+domain[1])*factor/2), _bounded((domain[0]+domain[1])*factor/2)",'Q07'),
                 ('boundary','equal = lo < hi or','equal = lo <= hi or','Q12'),
                 ('alias','if alias:','if False:','Q16'),
                 ('kind',"if query['kind'] == 'compare' and operands[0]['quantity_kind_ref'] != operands[1]['quantity_kind_ref']:","if False:",'Q18'),
                 ('unknown',"    reasons = set()", "    if len(refs)==2 and refs[0]==refs[1]:\n        return {'status':'computed','reason_codes':[],'relation_set':['equal'],'certain_relation':'equal'}\n    reasons = set()",'Q21'),
                 ('clinical',"'converted_to_base': False","'converted_to_base': True",'Q24'),
                 ('partial',"range(6 if query['kind'] == 'convert' else 9)","range(5 if query['kind'] == 'convert' else 9)",'B02-7')]
        for name,old,new,guard in mutants:
            self.assertEqual(source.count(old),1,name)
            namespace={'__name__':'med_dsl.quantity','__package__':'med_dsl','__file__':str(path)}
            exec(compile(source.replace(old,new),str(path),'exec'),namespace)
            surface=host.SURFACES['p2-quantity-request-draft-1']._replace(run=namespace['run_quantities'])
            data=fixture(guard)
            if name=='floating':
                data['request']=make.request([make.quantity(magnitude=make.point(2**53+1))])
                data['expected']['checks']=[make.check(['results',0,'converted_domain'],make.domain((2**53+1,1)))]
            with patch.dict(host.SURFACES,{'p2-quantity-request-draft-1':surface}):result=evaluate(data['request'])
            self.assertTrue(p2_checks.failed_checks(result,data['expected']['checks']),name)


if __name__=='__main__':unittest.main()
