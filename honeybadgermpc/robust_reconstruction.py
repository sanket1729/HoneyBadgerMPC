import asyncio
from honeybadgermpc.wb_interpolate import makeEncoderDecoder
from honeybadgermpc.field import GF
from honeybadgermpc.polynomial import polynomialsOver

async def attempt_reconstruct(field_futures, field, n, t, nAvailable, point):
    # Wait for nAvailable of field_futures to be done
    async def waitFor(aws, to_wait):
        done, pending = set(), set(aws)
        while len(done) < to_wait:
            _d, pending = await asyncio.wait(pending,
                                             return_when=asyncio.FIRST_COMPLETED)
            done |= _d
        return done, pending

    #print("Attempting to reconstruct with points", nAvailable)
    #raise ValueError("Sentinel bug")
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
        if not field_futures[j].done():
            continue
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
    assert 2*t < n, "Robust reconstruct waits for at least n=2t+1 values"
    for nAvailable in range(2*t + 1, n+1):
        try:
            P, failures = await attempt_reconstruct(
                field_futures, field, n, t, nAvailable, point)
            return P, failures
        except ValueError as e:
            print('ValueError:', e)
            if str(e) in ("Wrong degree", "no divisors found"):
                continue
            else:
                raise e
    assert False, "shouldn't reach the end here"
