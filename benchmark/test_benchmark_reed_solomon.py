from honeybadgermpc.field import GF
from honeybadgermpc.elliptic_curve import Subgroup
from honeybadgermpc.reed_solomon import GaoRobustDecoder
from honeybadgermpc.polynomial import EvalPoint, polynomials_over
from random import randint
from pytest import mark

 
@mark.parametrize("t", [1,3,5,10,25,50,100,256])
def test_benchmark_gao_robust_decode(benchmark, t, galois_field):
# if __name__ == "__main__":
    n = 3*t+1
    galois_field = GF(Subgroup.BLS12_381)
    point = EvalPoint(galois_field, n)
    dec = GaoRobustDecoder(t, point)
    parties = [_ for _ in range(n)]
    poly = polynomials_over(galois_field)
    truepoly = poly.random(degree=t)
    faults = []
    while len(faults) < t:
        r = randint(0, n-1)
        if r not in faults:
            faults.append(r)
    shares_with_faults = []
    for i in parties:
        if i in faults:
            shares_with_faults.append(int(galois_field.random()))
        else:
            shares_with_faults.append(int(truepoly(i+1)))
    benchmark(dec.robust_decode, parties, shares_with_faults)
    # decoded, decoded_faults = dec.robust_decode(parties, shares_with_faults)
    # assert truepoly == poly(decoded)
    # assert set(faults) == set(decoded_faults)
    
    
