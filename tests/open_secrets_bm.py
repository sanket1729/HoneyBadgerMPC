import cProfile, pstats, io
from pstats import SortKey
from honeybadgermpc.robust_reconstruction import attempt_reconstruct
from honeybadgermpc.batch_reconstruction import attempt_reconstruct_batch, toChunks
from honeybadgermpc.field import GF
from honeybadgermpc.polynomial import polynomialsOver
from honeybadgermpc.wb_interpolate import makeEncoderDecoder
from random import randint
import sys
# sys.stdout = open('tests/bench_marking_stats.txt', 'w')


# BLS12_381 order
p = 0x73eda753299d7d483339d80809a1d80553bda402fffe5bfeffffffff00000001

# def encode(message):
#     if not all(x < p for x in message):
#         raise Exception(
#             "Message is improperly encoded as integers < p. It was:\n%r" % message)
#     assert len(message) == t + 1

#     thePoly = Poly(message)
#     return [thePoly(point(i)) for i in range(n)]
# p = 73

def generate_test(n, t, p, k=10000):

    enc, _, _ = makeEncoderDecoder(n, t+1, p)
    Fp = GF.get(p)

    def point(i): return Fp(i+1)

    integerMessage = [randint(0, p-1) for i in range(k)]

    # In chunks:
    encoded = [[] for _ in range(n)]
    for chunk in toChunks(integerMessage, t + 1):
        for i in range(n):
            chunk += [0]*(t+1 - len(chunk))
            data = enc(chunk)
            encoded[i] += [data[i]]

    return encoded, Fp, point

# Test 1
def test1(n=16, k=1000):
    t = (n-1) // 3
    print('starting test1. k:', k, 'n:', n, 't:', t)
    encoded, field, point = generate_test(n, t, p)
    # cProfile.run('attempt_reconstruct()')
    # attempt_reconstruct(encoded, field, n, t, point):
    cp = cProfile.Profile()
    cp.enable()
    # attempt_reconstruct(encoded, field, n, t, point)
    # Attempt to reconstruct the fast way, with exactly 2t+ 1 points
    for i in range(2*t+1,n):
        encoded[i] = None
    attempt_reconstruct_batch(encoded, field, n, t, point)
    cp.disable()
    # cp.print_stats()
    print("Test n = {}, t = {}, field = {}".format(n, t, p))
    stats = pstats.Stats(cp)
    stats.strip_dirs().sort_stats(SortKey.CUMULATIVE, SortKey.TIME).print_stats(.5)

test1(n=4)
test1(n=8)
test1(n=16)
