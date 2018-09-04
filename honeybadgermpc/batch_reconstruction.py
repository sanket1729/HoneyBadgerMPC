# from honeybadgermpc.wb_interpolate import makeEncoderDecoder
from honeybadgermpc.wb_interpolate import decoding_message_with_none_elements
from honeybadgermpc.field import GF
from honeybadgermpc.polynomial import polynomialsOver
# from honeybadgermpc.test-asyncio-simplerouter import simple_router
# import asyncio

"""
batch_reconstruction function
input:
shared_secrets: an array of points representing shared secrets S1 - St+1
p: prime number used in the field
t: degree t polynomial
n: total number of nodes n=3t+1
id: id of the specific node running batch_reconstruction function
"""


async def batch_reconstruction(shared_secrets, p, t, n, myid, send, recv, debug):
    if debug:
        print("my id %d" % myid)
        print(shared_secrets)
    # construct the first polynomial f(x,i) = [S1]ti + [S2]ti x + … [St+1]ti xt
    Fp = GF(p)
    Poly = polynomialsOver(Fp)
    tmp_poly = Poly(shared_secrets)

    # Evaluate and send f(j,i) for each other participating party Pj
    for i in range(n):
        send(i, [Fp(myid+1), tmp_poly(Fp(i+1))])

    # Interpolate the polynomial, but we don't need to wait for getting all the values, we can start with 2t+1 values
    tmp_gathered_results = []
    for j in range(n):
        # TODO: can we assume that if received, the values are non-none?
        (i, o) = await recv()
        if debug:
            print("{} gets {} from {}".format(myid, o, i))
        tmp_gathered_results.append(o)
        """
        when t = 1, we should really use no-error-correction interpolation, but for now just decrease interpolation starting value by 1 to avoid running into infinite loop. WIP
        """
        if t == 1:
            start_interpolation = j
        else:
            start_interpolation = j + 1
        if start_interpolation >= (2*t + 1):
            if debug:
                print("{} is in first interpolation".format(myid))
                print(tmp_gathered_results)
            # interpolate with error correction to get f(j,y)
            Solved, P1, evil_nodes1 = decoding_message_with_none_elements(t, tmp_gathered_results, p)
            if Solved:
                if debug:
                    print("I am {} and evil nodes are{}".format(myid, evil_nodes1))
                break
    # what should we do if the first interpolation fails?
    #if not Solved:

    # Evaluate and send f(j,y) for each other participating party Pj
    for i in range(n):
        send(i, [myid + 1, P1.coeffs[0]])

    # Interpolate the polynomial to get f(x,0)
    tmp_gathered_results2 = []
    Solved = False
    for j in range(n):
        # TODO: can we assume that here the received values are non-none?
        (i, o) = await recv()
        if debug:
            print("{} gets {} from {}".format(myid, o, i))
        if i+1 not in evil_nodes1:
            tmp_gathered_results2.append(o)
            if t == 1:
                start_interpolation = len(tmp_gathered_results2) - 1
            else:
                start_interpolation = len(tmp_gathered_results2)
            if start_interpolation >= (2*t + 1):
                # interpolate with error correction to get f(x,0)
                if debug:
                    print("{} is in second interpolation".format(myid))
                    print(tmp_gathered_results2)
                Solved, P2, evil_nodes2 = decoding_message_with_none_elements(t, tmp_gathered_results2, p)
                if Solved:
                    break
    # what should we do if the first interpolation fails?
    #if not Solved:

    # return the result
    if Solved:
        if debug:
            print("I am {} and the secret polynomial is {}".format(myid, P2))
        return Solved, P2, evil_nodes1.extend(evil_nodes2)
    else:
        if debug:
            print("I am {} and I failed decoding the shared secrets".format(myid))
        return Solved, None, []
