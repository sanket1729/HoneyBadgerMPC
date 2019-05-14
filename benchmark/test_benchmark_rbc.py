from honeybadgermpc.protocols.reliablebroadcast import reliablebroadcast
from contextlib import ExitStack
from random import randint
from pytest import mark
import asyncio
import cProfile
import os

@mark.parametrize("t, msglen", [(5, 200), (5, 10000), (10, 200), (10, 10000)])
def test_benchmark_rbc(test_router, benchmark, t, msglen):
    loop = asyncio.get_event_loop()
    n = 3*t + 1
    sends, recvs, _ = test_router(n)
    msg = os.urandom(msglen)
    params = (sends, recvs, t, n, msg)

    def _prog():
        loop.run_until_complete(rbc(params))
    benchmark(_prog)
    #cProfile.runctx("_prog()", None, locals())


@mark.parametrize("t, msglen", [(5, 200), (5, 10000), (10, 200), (10, 10000)])
def test_benchmark_rbc_dealer(test_router, benchmark, t, msglen):
    loop = asyncio.get_event_loop()
    n = 3*t + 1
    sends, recvs, _ = test_router(n)
    msg = ""
    for i in range(5000):
        msg = msg + "Pad."
    params = (sends, recvs, t, n, msg)

    def _prog():
        loop.run_until_complete(rbc_dealer(params))
    benchmark(_prog)
    #cProfile.runctx("_prog()", None, locals())


async def rbc(params):

    (sends, recvs, t, n, msg) = params
    rbc_tasks = [None]*n
    dealer_id = randint(0, n-1)
    tag = f"RBC"

    for i in range(n):
        if i == dealer_id:
            rbc_tasks[i] = asyncio.create_task(reliablebroadcast(tag, i, n, t, dealer_id, msg, recvs[i], sends[i]))
        else:
            rbc_tasks[i] = asyncio.create_task(reliablebroadcast(tag, i, n, t, dealer_id, None, recvs[i], sends[i]))
    msgs = await asyncio.gather(*rbc_tasks)
    for task in rbc_tasks:
        task.cancel()


async def rbc_dealer(params):

    (sends, recvs, t, n, msg) = params
    rbc_tasks = [None]*n
    dealer_id = 0
    tag = f"RBC"
    await reliablebroadcast(tag, 0, n, t, 0, msg, recvs[0], sends[0], client_mode=True)