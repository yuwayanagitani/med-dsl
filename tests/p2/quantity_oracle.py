"""量の参照計算。native表や関数を読まず、整数対の演算と区間内の証人点で検査する。

各隣接端点間から2点を選び、同一区間内の大小も検出する。有限区間の順序関係に限る。
"""
from math import gcd

SCALES = {'u_base':(1,1),'u_ten':(10,1),'u_third':(1,3),'u_half':(1,2),
          'v_base':(1,1),'w_base':(1,1),'w_hundredth':(1,100)}


def rat(n,d=1):
    divisor=gcd(n,d)
    return n//divisor,d//divisor


def read(value):
    return rat(value['numerator'],value['denominator'])


def mul(a,b):
    return rat(a[0]*b[0],a[1]*b[1])


def cmp(a,b):
    cross=a[0]*b[1]-b[0]*a[1]
    return (cross>0)-(cross<0)


def mix(a,b,p,q):
    return rat((q-p)*a[0]*b[1]+p*b[0]*a[1],q*a[1]*b[1])


def bounds(quantity):
    m=quantity['magnitude'];scale=SCALES[quantity['unit_ref']]
    if m['kind']=='point':
        v=mul(read(m['value']),scale)
        return v,v,True,True
    return mul(read(m['lower']),scale),mul(read(m['upper']),scale),m['lower_closed'],m['upper_closed']


def converted(quantity,target):
    lo,hi,lc,uc=bounds(quantity);n,d=SCALES[target]
    lo,hi=mul(lo,(d,n)),mul(hi,(d,n))
    def encode(value):return dict(zip(('numerator','denominator'),value))
    return {'lower':encode(lo),'upper':encode(hi),'lower_closed':lc,'upper_closed':uc}


def relations(left,right,alias=False):
    from functools import cmp_to_key
    a,b=bounds(left),bounds(right)
    endpoints=sorted(set([a[0],a[1],b[0],b[1]]),key=cmp_to_key(cmp))
    points=list(endpoints)
    for x,y in zip(endpoints,endpoints[1:]):
        points.extend([mix(x,y,1,3),mix(x,y,2,3)])
    def inside(v,domain):
        lower,upper=cmp(v,domain[0]),cmp(v,domain[1])
        return (lower>0 or lower==0 and domain[2]) and (upper<0 or upper==0 and domain[3])
    l=[v for v in points if inside(v,a)];r=[v for v in points if inside(v,b)]
    signs={cmp(x,y) for x in l for y in r if not alias or cmp(x,y)==0}
    return [name for sign,name in [(-1,'less'),(0,'equal'),(1,'greater')] if sign in signs]
