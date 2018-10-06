import asyncio
from asyncio import Future
from .field import GF, GFElement
from .polynomial import polynomialsOver
from .jubjub import Point, Jubjub
from .router import simple_router
from .batch_reconstruction import batch_reconstruction
import random


class NotEnoughShares(Exception):
    pass


class BatchReconstructionFailed(Exception):
    pass

zeros_files_prefix = None # 'sharedata/test_zeros'
triples_files_prefix = None # 'sharedata/test_triples'
random_files_prefix = None #'sharedata/test_random'

class PassiveMpc(object):

    def __init__(self, sid, N, t, myid, send, recv, prog):
        # Parameters for passive secure MPC
        # Note: tolerates min(t,N-t) crash faults
        assert type(N) is int and type(t) is int
        assert t < N
        self.sid = sid
        self.N = N
        self.t = t
        self.myid = myid

        # send(j, o): sends object o to party j with (current sid)
        # recv(): returns (j, o) from party j
        self.send = send
        self.recv = recv

        # An Mpc program should only depend on common parameters,
        # and the values of opened shares. Opened shares will be
        # assigned an ID based on the order that share is encountered.
        # So the protocol must encounter the shares in the same order.
        self.prog = prog

        # Store deferreds representing SharedValues
        self._openings = []

        # Store opened shares until ready to reconstruct
        # shareid => { [playerid => share] }
        self._share_buffers = tuple([] for _ in range(N))

        self.Share, self.ShareArray = shareInContext(self)

        # Preprocessing elements
        filename = f'{zeros_files_prefix}-{self.myid}.share'
        self._zeros = iter(self.read_shares(open(filename)))

        filename = f'{random_files_prefix}-{self.myid}.share'
        self._rands = iter(self.read_shares(open(filename)))

        filename = f'{triples_files_prefix}-{self.myid}.share'
        self._triples = iter(self.read_shares(open(filename)))

    def _reconstruct(self, shareid):
        # Are there enough shares to reconstruct?
        shares = [(i+1, self._share_buffers[i][shareid])
                  for i in range(self.N)
                  if len(self._share_buffers[i]) > shareid]
        if len(shares) < self.t+1:
            raise NotEnoughShares

        # print('[%d] reconstruct %s' % (self.myid, shareid,))

        if not self._openings[shareid].done():
            s = Poly.interpolate_at(shares)
            # Set the result on the future representing this share
            self._openings[shareid].set_result(s)

    def open_share(self, share):
        opening = asyncio.Future()
        shareid = len(self._openings)
        self._openings.append(opening)

        # Broadcast share
        for j in range(self.N):
            self.send(j, (shareid, share.v))

        # Reconstruct if we already had enough shares
        try:
            self._reconstruct(shareid)
        except NotEnoughShares:
            pass

        # Return future
        return opening

    def get_triple(self):
        a = next(self._triples)
        b = next(self._triples)
        ab = next(self._triples)
        return a, b, ab

    def get_rand(self):
        return next(self._rands)

    def get_zero(self):
        return next(self._zeros)

    def get_bit(self):
        return next(self._bits)

    async def _run(self):
        # Run receive loop as background task, until self.prog finishes
        loop = asyncio.get_event_loop()
        bgtask = loop.create_task(self._recvloop())

        def handle_result(future):
            if not future.cancelled() and future.exception():
                # Stop the loop otherwise the loop continues to await for the prog to
                # finish which will never happen since the recvloop has terminated.
                loop.stop()
                future.result()
        bgtask.add_done_callback(handle_result)
        res = await self.prog(self)
        bgtask.cancel()
        return res

    async def _recvloop(self):
        while True:
            (j, (shareid, share)) = await self.recv()
            buf = self._share_buffers[j]

            # Shareid is redundant, but confirm it is one greater
            assert shareid == len(buf), "shareid: %d, len: %d" % (shareid, len(buf))
            buf.append(share)

            # Reconstruct if we now have enough shares,
            # and if the opening has been asked for
            if len(self._openings) > shareid:
                try:
                    self._reconstruct(shareid)
                except NotEnoughShares:
                    pass

        return True

    # File I/O
    def read_shares(self, f):
        # Read shares from a file object
        lines = iter(f)
        # first line: field modulus
        modulus = int(next(lines))
        assert Field.modulus == modulus
        # second line: share degree
        degree = int(next(lines))   # noqa
        # third line: id
        myid = int(next(lines))     # noqa
        shares = []
        # remaining lines: shared values
        for line in lines:
            shares.append(self.Share(int(line)))
        return shares

    def write_shares(self, f, shares):
        write_shares(f, Field.modulus, self.myid,
                     [share.v for share in shares])


def write_shares(f, modulus, degree, myid, shares):
    print(modulus, file=f)
    print(degree, file=f)
    print(myid, file=f)
    for share in shares:
        print(share.value, file=f)

###############
# Share class
###############


def shareInContext(context):

    def _binopField(fut, other, op):
        assert type(other) in [ShareFuture, GFElementFuture, Share, GFElement]
        if isinstance(other, ShareFuture) or isinstance(other, Share):
            res = ShareFuture()
        elif isinstance(other, GFElement) or isinstance(other, GFElementFuture):
            res = GFElementFuture()

        if isinstance(other, Future):
            def cb(_): return res.set_result(op(fut.result(), other.result()))
            asyncio.gather(fut, other).add_done_callback(cb)
        else:
            def cb(_): return res.set_result(op(fut.result(), other))
            fut.add_done_callback(cb)
        return res

    class GFElementFuture(Future):
        def __add__(self, other): return _binopField(
            self, other, lambda a, b: a + b)

        def __sub__(self, other): return _binopField(
            self, other, lambda a, b: a - b)

        def __mul__(self, other): return _binopField(
            self, other, lambda a, b: a * b)

    class Share(object):
        def __init__(self, v):
            # v is the local value of the share
            if type(v) is int:
                #for the purpose of calling batch reconstruction, might need to refactor in the future
                self.v_int = v
                v = Field(v)
            assert type(v) is GFElement
            self.v = v

        # Publicly reconstruct a shared value
        def open(self):
            res = GFElementFuture()

            def cb(f): return res.set_result(f.result())
            context.open_share(self).add_done_callback(cb)
            return res

        # Linear combinations of shares can be computed directly
        # TODO: add type checks for the operators
        # @typecheck(Share)
        def __add__(self, other):
            if isinstance(other, GFElement):
                return Share(self.v + other)
            elif isinstance(other, Share):
                return Share(self.v + other.v)

        def __sub__(self, other): return Share(self.v - other.v)
        __radd__ = __add__

        def __rsub__(self, other): return Share(-self.v + other.v)

        # @typecheck(int,field)
        def __rmul__(self, other): return Share(self.v * other)

        # @typecheck(Share)
        # TODO
        def __mul__(self, other):
            a, b, ab = context.get_triple()
            raise NotImplemented

        def __str__(self): return '{%d}' % (self.v)


    def _binopShare(fut, other, op):
        assert type(other) in [ShareFuture, GFElementFuture, Share, GFElement]
        res = ShareFuture()
        if isinstance(other, Future):
            def cb(_): return res.set_result(op(fut.result(), other.result()))
            asyncio.gather(fut, other).add_done_callback(cb)
        else:
            def cb(_): return res.set_result(op(fut.result(), other))
            fut.add_done_callback(cb)
        return res

    class ShareFuture(Future):
        def __add__(self, other): return _binopShare(
            self, other, lambda a, b: a + b)

        def __sub__(self, other): return _binopShare(
            self, other, lambda a, b: a - b)

        def __mul__(self, other): return _binopShare(
            self, other, lambda a, b: a * b)

        def open(self) -> GFElementFuture:
            res = GFElementFuture()

            def cb2(sh): return res.set_result(sh.result())

            def cb1(_): return self.result().open().add_done_callback(cb2)
            self.add_done_callback(cb1)
            return res

    class ShareArray(object):
        def __init__(self, shares):
            # Initialized with a list of share objects
            for share in shares:
                assert type(share) is Share
            self._shares = shares

        async def open(self):
            # Returns a list of field elements
            # TODO: replace with batch recpub
            # async def batch_reconstruction(shared_secrets, p, t, n, myid, send, recv, debug):
            length = len(self._shares)
            results = []
            if length < (context.t + 1):
                raise NotEnoughShares
            # shares_copy = [share for share in self._shares]
            tmp = length % (context.t + 1)
            if tmp != 0:
                for i in range((context.t + 1) - tmp):
                    self._shares.append(self._shares[length - 1])
            assert len(self._shares) % (context.t + 1) == 0
            for i in range(len(self._shares) // (context.t + 1)):
                # shared_secrets = []
                # for j in range(self.t + 1):
                #     shared_secrets.append(self._shares[i*(self.t + 1)+j].v_int)
                shared_secrets = [self._shares[i*(context.t + 1)+j].v_int for j in range(context.t + 1)]
                Solved, opened_poly, evil_ndoes = await batch_reconstruction(shared_secrets, p, context.N, context.t, context.myid, context.send, context.recv, True)
                #construct openpoly in to field elements
                if Solved:
                    # coeffs = opened_poly.coeffs
                    # for result in coeffs:
                    #     results.append([field(result)])
                    results.extend([Field(coeff) for coeff in opened_poly.coeffs])
                else:
                    raise BatchReconstructionFailed
                    # continue
                #record evil nodes
                #do another batch
                #return

            return results

        def __add__(self, other): raise NotImplemented

        def __sub__(self, other):
            assert len(self._shares) == len(other._shares)
            return ShareArray([(a-b) for (a, b) in zip(self._shares, other._shares)])

    return Share, ShareArray


# Share = shareInContext(None)


# Create a fake network with N instances of the program
async def runProgramAsTasks(program, N, t):
    loop = asyncio.get_event_loop()
    sends, recvs = simple_router(N)

    tasks = []
    # bgtasks = []
    for i in range(N):
        context = PassiveMpc('sid', N, t, i, sends[i], recvs[i], program)
        tasks.append(loop.create_task(context._run()))

    results = await asyncio.gather(*tasks)
    return results


#######################
# Generating test files
#######################

# p as an integer for calling batch_reconstruction
p = 0x73eda753299d7d483339d80809a1d80553bda402fffe5bfeffffffff00000001
# Fix the field for now
Field = GF.get(0x73eda753299d7d483339d80809a1d80553bda402fffe5bfeffffffff00000001)
Poly = polynomialsOver(Field)


def write_polys(prefix, modulus, N, t, polys):
    for i in range(N):
        shares = [f(i+1) for f in polys]
        with open('%s-%d.share' % (prefix, i), 'w') as f:
            write_shares(f, modulus, t, i, shares)


def generate_test_triples(prefix, k, N, t):
    # Generate k triples, store in files of form "prefix-%d.share"
    polys = []
    for j in range(k):
        a = Field(random.randint(0, Field.modulus-1))
        b = Field(random.randint(0, Field.modulus-1))
        c = a*b
        polys.append(Poly.random(t, a))
        polys.append(Poly.random(t, b))
        polys.append(Poly.random(t, c))
    write_polys(prefix, Field.modulus, N, t, polys)


def generate_test_zeros(prefix, k, N, t):
    polys = []
    for j in range(k):
        polys.append(Poly.random(t, 0))
    write_polys(prefix, Field.modulus, N, t, polys)


def generate_test_randoms(prefix, k, N, t):
    polys = []
    for j in range(k):
        polys.append(Poly.random(t))
    write_polys(prefix, Field.modulus, N, t, polys)


###############
# Test programs
###############
async def test_prog1(context):

    # Example of Beaver multiplication
    x = context.get_zero() + context.Share(10)
    # x = context.Share(10)
    y = context.get_zero() + context.Share(15)
    # y = context.Share(15)

    a, b, ab = context.get_triple()
    # assert await a.open() * await b.open() == await ab.open()

    D = (x - a).open()
    E = (y - b).open()

    # This is a random share of x*y
    print('type(D):', type(D))
    print('type(b):', type(b))
    xy = D*E + D*b + E*a + ab

    print('type(x):', type(x))
    print('type(y):', type(y))
    print('type(xy):', type(xy))
    X, Y, XY = await x.open(), await y.open(), await xy.open()
    assert X * Y == XY

    print("[%d] Finished" % (context.myid,), X, Y, XY)


async def test_batchbeaver(context):

    # Demonstrates use of ShareArray batch interface

    xs = [context.get_zero() + context.Share(i) for i in range(100)]
    ys = [context.get_zero() + context.Share(i+10) for i in range(100)]
    xs = context.ShareArray(xs)
    ys = context.ShareArray(ys)

    As, Bs, ABs = [], [], []
    for i in range(100):
        A, B, AB = context.get_triple()
        As.append(A)
        Bs.append(B)
        ABs.append(AB)
    As = context.ShareArray(As)
    Bs = context.ShareArray(Bs)
    ABs = context.ShareArray(ABs)

    Ds = await (xs - As).open()
    Es = await (ys - Bs).open()

    for i, (x, y, a, b, ab, D, E) in enumerate(
            zip(xs._shares, ys._shares,
                As._shares, Bs._shares, ABs._shares, Ds, Es)):
        xy = context.Share(D*E) + D*b + E*a + ab
        assert (await xy.open()) == i * (i + 10)

    print("[%d] Finished batch beaver" % (context.myid,))

# Read zeros from file, open them

async def test_batchjubjub(context):

    def mul(x, y):
        a, b, ab = context.get_triple()
        return beaver_mult(context, x, y, a, b, ab)

    # Stream of random numbers for taking inverses
    async def inverse(x):
        _r = context.get_rand()
        # return [r] / open([r * x])
        rx = await (await mul(_r, x)).open()
        return (1/rx) * _r

    # ShareArray batch addition of points on jubjub

    p1 = Point(0,1)
    p2 = Point(5, 6846412461894745224441235558443359243034138132682534265960483512729196124138)
    p3 = Point(10, 9069365299349881324022309154395348339753339814197599672892180073931980134853)
    p4 = Point(20, 19591689915777126424527574975649725331665833659101192930707046924393354292087)
    p5 = Point(21, 7077199607858622853608570958787827897736274549921838431359778037825087697958)
    p6 = Point(28, 6872713299796450981547816838430986612693130632041108310621050902354381807248)

    s1 = [p1, p2, p3]
    s2 = [p4, p5, p6]
    s3 = [] # for assertion with opened value

    for p, q in zip(s1, s2):
        s3.append(p + q)
    assert len(s1) == len(s3)

    x1s = [context.get_zero() + context.Share(i.x) for i in s1]
    y1s = [context.get_zero() + context.Share(i.y) for i in s1]
    x2s = [context.get_zero() + context.Share(i.x) for i in s2]
    y2s = [context.get_zero() + context.Share(i.y) for i in s2]

    x1s = context.ShareArray(x1s)
    y1s = context.ShareArray(y1s)
    x2s = context.ShareArray(x2s)
    y2s = context.ShareArray(y2s)
    x3s = []
    y3s = []

    for i, (x1, y1, x2, y2) in enumerate(
            zip(x1s._shares, y1s._shares, x2s._shares, y2s._shares)):

        dx1x2y1y2 = p.curve.d * await mul(await mul(x1, x2), await mul(y1, y2))
        x3num = (await mul(x1, y2) + await mul(y1, x2))
        x3den = (context.Share(1) + dx1x2y1y2)
        x3 = await mul(x3num, await inverse(x3den))
        y3num = (await mul(y1, y2) + await mul(x1, x2))
        y3den = (context.Share(1) - dx1x2y1y2)
        y3 = await mul(y3num, await inverse(y3den))

        x3s.append(x3)
        y3s.append(y3)

    x3s = context.ShareArray(x3s)
    y3s = context.ShareArray(y3s)

    X3s, Y3s = await x3s.open(), await y3s.open()

    # verify
    for i in range(len(s3)):
        assert s3[i].x == X3s[i] and s3[i].y == Y3s[i]


async def test_prog2(context):

    shares = [context.get_zero() for _ in range(1000)]
    for share in shares[:100]:
        s = await share.open()
        assert s == 0
    print('[%d] Finished' % (context.myid,))

    # Batch version
    arr = context.ShareArray(shares[:100])
    for s in await arr.open():
        assert s == 0
    print('[%d] Finished batch' % (context.myid,))


async def beaver_mult(context, x, y, a, b, ab):
    D = await (x - a).open()
    E = await (y - b).open()

    # This is a random share of x*y
    xy = context.Share(D*E) + D*b + E*a + ab

    return context.Share(await xy.open())


async def test_prog3(context):

    def mul(x, y):
        a, b, ab = context.get_triple()
        return beaver_mult(context, x, y, a, b, ab)

    # Stream of random numbers for taking inverses
    async def inverse(x):
        _r = context.get_rand()
        # return [r] / open([r * x])
        rx = await (await mul(_r, x)).open()
        return (1/rx) * _r


    P = Point(Field(0x18ea85ca00cb9d895cb7b8669baa263fd270848f90ebefabe95b38300e80bde1),
              Field(0x255fa75b6ef4d4e1349876df94ca8c9c3ec97778f89c0c3b2e4ccf25fdf9f7c1))
    Q = Point(Field(0x1624451837683b2c4d2694173df71c9174ffcc613788eef3a9c7a7d0011476fa),
              Field(0x6f76dbfd7c62860d59f5937fa66d0571158ff68f28ccd83a4cd41b9918ee8fe2))

    R = P + Q

    x1 = context.get_zero() + context.Share(P.x)
    y1 = context.get_zero() + context.Share(P.y)
    x2 = context.get_zero() + context.Share(Q.x)
    y2 = context.get_zero() + context.Share(Q.y)


    dx1x2y1y2 = P.curve.d * await mul(await mul(x1, x2), await mul(y1, y2))
    x3num = (await mul(x1, y2) + await mul(y1, x2))
    x3den = (context.Share(1) + dx1x2y1y2)
    x3 = await mul(x3num, await inverse(x3den))
    y3num = (await mul(y1, y2) + await mul(x1, x2))
    y3den = (context.Share(1) - dx1x2y1y2)
    y3 = await mul(y3num, await inverse(y3den))

    X3, Y3 = await x3.open(), await y3.open()

    assert X3 == R.x and Y3 == R.y


# Run some test cases
if __name__ == '__main__':
    print('Generating random shares of zero in sharedata/')
    generate_test_zeros('sharedata/test_zeros', 1000, 3, 2)
    print('Generating random shares in sharedata/')
    generate_test_randoms('sharedata/test_random', 1000, 3, 2)
    print('Generating random shares of triples in sharedata/')
    generate_test_triples('sharedata/test_triples', 1000, 3, 2)

    asyncio.set_event_loop(asyncio.new_event_loop())
    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    try:
        loop.run_until_complete(runProgramAsTasks(test_prog1, 3, 2))
        loop.run_until_complete(runProgramAsTasks(test_prog2, 3, 2))
        loop.run_until_complete(runProgramAsTasks(test_prog3, 3, 2))
        loop.run_until_complete(runProgramAsTasks(test_batchbeaver, 3, 2))
        loop.run_until_complete(runProgramAsTasks(test_batchjubjub, 3, 2))
    finally:
        loop.close()
