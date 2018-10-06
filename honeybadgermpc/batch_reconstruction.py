from honeybadgermpc.wb_interpolate import makeEncoderDecoder
from honeybadgermpc.field import GF
from honeybadgermpc.polynomial import polynomialsOver
import asyncio

async def attemptReconstruct(field_futures, field, n, t, nAvailable, point):
    # Wait for nAvailable of field_futures to be done
    async def waitFor(aws, to_wait):
        done, pending = set(), set(aws)
        while len(done) < to_wait:
            _d, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            done |= _d
        return done, pending

    # print("Attempting to reconstruct with points", nAvailable)
    await waitFor(field_futures, nAvailable)

    # interpolate with error correction to get f(j,y)
    _, decode, _ = makeEncoderDecoder(n, t+1, field.modulus)
    encoded = [x.result() if x.done() else None for x in field_futures]

    P = polynomialsOver(field)(decode(encoded))
    if P.degree() > t:
        raise ValueError("Wrong degree")

    # check for errors
    coincides = 0
    failures_detected = set()
    for j in range(n):
        if not field_futures[j].done(): continue
        if P(point(j)) == field_futures[j].result():
            coincides += 1
        else:
            failures_detected.add(j)

    if coincides >= 2 * t + 1:
        return P, failures_detected
    else:
        raise ValueError("Did not coincide")


async def robust_reconstruct(field_futures, field, n, t, point):
    # Wait for between 2t+1 values and N values,
    # trying to reconstruct each time
    for nAvailable in range(2*t + 1, n+1):
        try:
            P, failures = await attemptReconstruct(field_futures, field, n, t, nAvailable, point)
            return P, failures
        except ValueError as e:
            if str(e) in ("Wrong degree", "no divisors found"):
                continue

    assert False, "shouldn't reach the end here"

async def batch_reconstruction(shared_secrets, p, t, n, myid, send, recv, debug):
    """
    args:
      shared_secrets: an array of points representing shared secrets S1 - St+1
      p: prime number used in the field
      t: degree t polynomial
      n: total number of nodes n=3t+1
      myid: id of the specific node running batch_reconstruction function
    
    output:
      the reconstructed array of t+1 shares

    Communication takes place over two rounds,
      objects sent/received of the form ('R1', share) or ('R2', share)
      up to one of each for each party
"""

    if debug:
        print("my id %d" % myid)
        print(shared_secrets)

    Fp = GF.get(p)
    Poly = polynomialsOver(Fp)
    point = lambda i: Fp(i+1) # TODO: make it use omega

    # Reconstruct a batch of exactly t+1 secrets
    assert len(shared_secrets) == t+1

    # We'll wait to receive between 2t+1 shares
    round1_shares = [asyncio.Future() for _ in range(n)]
    round2_shares = [asyncio.Future() for _ in range(n)]

    async def _recvloop():
        while True:
            (j, (r, o)) = await recv()
            if r == 'R1':
                assert(not round1_shares[j].done())
                round1_shares[j].set_result(o)
            elif r == 'R2':
                assert(not round2_shares[j].done())
                round2_shares[j].set_result(o)
            else:
                assert False, f"invalid round tag: {r}"

    # Run receive loop as background task, until self.prog finishes
    loop = asyncio.get_event_loop()
    bgtask = loop.create_task(_recvloop())

    try:
        # Round 1:
        # construct the first polynomial f(x,i) = [S1]ti + [S2]ti x + … [St+1]ti xt
        f_poly = Poly(shared_secrets)

        #  Evaluate and send f(j,i) for each other participating party Pj
        for j in range(n):
            send(j, ('R1', f_poly(point(j))))        

        # Robustly reconstruct f(i,X)
        P1, failures_detected = await robust_reconstruct(round1_shares, Fp, n, t, point)
        if debug:
            print(f"I am {myid} and evil nodes are {failures_detected}")
        
        # Round 2:
        # Evaluate and send f(i,0) to each other party
        for j in range(n):
            send(j, ('R2', P1(Fp(0))))

        # Robustly reconstruct f(X,0)
        P2, failures_detected = await robust_reconstruct(round2_shares, Fp, n, t, point)

        #print(f"I am {myid} and the secret polynomial is {P2}")
        return P2.coeffs

    finally:
        bgtask.cancel()
