"""表示の参照計算：近隣整数への距離と、閾値で分割したセル内の証人点。nativeは読まない。"""
from fractions import Fraction as F
import measurement_oracle as measurements


def rounded(x,p):
    scale=10**p;z=x*scale;a=z.numerator//z.denominator
    k=min(range(a-1,a+3),key=lambda j:(abs(z-j),j%2))
    integer,decimal=divmod(abs(k),scale)
    text=('-' if k<0 else '')+str(integer)+(('.'+str(decimal).rjust(p,'0')) if p else '')
    center=F(k,scale);lo=(center+F(k-1,scale))/2;hi=(center+F(k+1,scale))/2
    def assigned(t):
        z=t*scale;a=z.numerator//z.denominator
        return min(range(a-1,a+3),key=lambda j:(abs(z-j),j%2))==k
    return k,text,lo,hi,assigned(lo),assigned(hi)


def uniform(op,t,lo,hi,lc,uc):
    cuts=sorted({lo,hi,*([t] if lo<t<hi else [])})
    witnesses=[v for v in cuts if (v>lo or lc) and (v<hi or uc)]
    witnesses += [(a+b)/2 for a,b in zip(cuts,cuts[1:])]
    answers={compare(op,v,t) for v in witnesses}
    return answers.pop() if len(answers)==1 else None


def compare(op,x,y):
    if op=='lt':return x<y
    if op=='le':return x<=y
    if op=='eq':return x==y
    if op=='ge':return x>=y
    return x>y


def encode(x):return {'numerator':x.numerator,'denominator':x.denominator}


def row(request,display):
    plan=request['measurement_plan'];views={v['id']:v for v in plan['views']};queries={q['id']:q for q in plan['queries']}
    child=measurements.answer(plan,views[display['view_ref']],queries[display['query_ref']])
    reason=['unknown_capability'] if set(display['required_capabilities'])-{'p2-quantity-display-draft-1'} else child['reason_codes']
    status='unassessed' if reason==['unknown_capability'] else child['status']
    domain=child['converted_domain']
    if not reason and status=='computed' and domain['lower']!=domain['upper']:reason=['unsupported_display_domain'];status='unassessed'
    if reason or status!='computed':return {'status':status,'reason_codes':reason,'artifact':None,'questions':None}
    x=F(domain['lower']['numerator'],domain['lower']['denominator']);k,text,lo,hi,lc,uc=rounded(x,display['decimal_places']);answers=[]
    for q in sorted(display['questions'],key=lambda q:q['id']):
        source=None
        if q['kind']=='display_text':answer=text
        elif q['kind']=='exact_value':
            answer=None
            if request['retention']=='source_bundle':source={'mode':'source_replay','answer':encode(x)}
        else:
            t=F(q['threshold']['numerator'],q['threshold']['denominator']);answer=uniform(q['operator'],t,lo,hi,lc,uc)
            if request['retention']=='source_bundle':source={'mode':'source_replay','answer':compare(q['operator'],x,t)}
        answers.append({'id':q['id'],'status':'preserved' if answer is not None else 'out_of_scope','projection_answer':answer,'source_answer':source,'reason_codes':[] if answer is not None else ['query_out_of_scope']})
    return {'status':'computed','reason_codes':[],'coefficient':k,'text':text,'cell':{'lower':encode(lo),'upper':encode(hi),'lower_closed':lc,'upper_closed':uc},'questions':answers}


def cost(plan):
    source=plan['source'];base=1+len(source['slots'])+len(source['quantities'])
    for view in plan['views']:
        base+=len(source['records'])+len(source['reviews'])
        visible=[r for r in source['records'] if r['recorded_at']<=view['as_of']]
        confirmed={r['record_ref'] for r in source['reviews'] if r['recorded_at']<=view['as_of']}
        for query in plan['queries']:
            scope=[r for r in visible if r['slot_ref']==query['slot_ref']]
            base+=2+len(scope)+8
            for r in scope:
                if r['certainty']=='confirmed' and r['id'] in confirmed:base+=len(r['supersedes'])
    return base
