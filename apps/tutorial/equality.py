import asyncio
from honeybadgermpc.mpc import TaskProgramRunner
from honeybadgermpc.progs.mixins.dataflow import Share
from honeybadgermpc.preprocessing import (
    PreProcessedElements as FakePreProcessedElements,
)
from honeybadgermpc.utils.typecheck import TypeCheck
from honeybadgermpc.progs.mixins.share_arithmetic import (
    MixinConstants,
    BeaverMultiply,
    BeaverMultiplyArrays,
)

from honeybadgermpc.progs.mixins.share_comparison import Equality

config = {
    MixinConstants.MultiplyShareArray: BeaverMultiplyArrays(),
    MixinConstants.MultiplyShare: BeaverMultiply(),
    MixinConstants.ShareEquality: Equality(),
}


async def prog(ctx):

    K1 = 700
    k1 = ctx.Share(K1) + ctx.preproc.get_zero(ctx)
    print(f"[{ctx.myid}] k1 = ", k1)

    K2 = 700
    k2 = ctx.Share(K2) + ctx.preproc.get_zero(ctx)
    print(f"[{ctx.myid}] k2 = ", k2)

    res = await (k1 == k2).open()

    print(f"[{ctx.myid}] Result = ", res)


async def tutorial_1():
    # Create a test network of 4 nodes (no sockets, just asyncio tasks)
    n, t = 4, 1
    pp = FakePreProcessedElements()
    pp.generate_zeros(10000, n, t)
    pp.generate_triples(10000, n, t)
    pp.generate_bits(10000, n, t)
    print("here2!")
    program_runner = TaskProgramRunner(n, t, config)
    program_runner.add(prog)
    results = await program_runner.join()
    return results


def main():
    # Run the tutorials
    asyncio.set_event_loop(asyncio.new_event_loop())
    loop = asyncio.get_event_loop()
    loop.run_until_complete(tutorial_1())
    # loop.run_until_complete(tutorial_2())


if __name__ == "__main__":
    main()
    print("Tutorial 1 ran successfully")
