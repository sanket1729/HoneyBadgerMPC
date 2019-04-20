import asyncio
import eventsim
import importlib

# Minimal mockup for the MPC context
class MpcContext():
    async def open_share_array(self, xs):
        print('Opening a batch of shares:', xs)
        # print('open_share_array(): running loop:', asyncio.get_event_loop())
        # await asyncio.sleep(0.1)
        return xs

# Minimal mockup for the Share class, which just exposes Share.open,
# but supports implicitly batching them
def share_in_context(ctx, B=10):
    # B: maximum amount of shares to batch
    
    # Create a buffer of shares to open, and their futures,
    # to be accessed only through Share classmethods
    shares_to_open = []
    result_futures = []

    class Share(object):

        def __init__(self, v):
            self.v = v

        def open(self):
            # Add share and result future to buffer
            # print('opening:', self.v)
            shares_to_open.append(self.v)
            result_future = asyncio.Future()
            result_futures.append(result_future)

            # Stop the loop if the buffer reaches size
            # This indicates to the caller that more
            # shares should be delivered
            if len(result_futures) >= B:
                # print('buffer size reached, stopping')
                asyncio.get_event_loop().stop()

            return result_future

        #### Process a batch
        # Note: should be scheduled in main loop, not simloop
        @classmethod
        async def _open_batch(cls):
            results = await ctx.open_share_array(shares_to_open)
            for result, fut in zip(results, result_futures):
                fut.set_result(result)
            result_futures.clear()
            shares_to_open.clear()

    return Share


################
"""
Sample MPC operation that runs in 4 rounds, 32 ops
"""
async def singleOperation(ctx, a, b):
    a_, b_ = await asyncio.gather(a.open(), b.open())
    return a_ * b_

async def lotsOfOperations(ctx):
    # This MPC program creates several concurrent tasks
    # and awaits them all at once
    rs = list(range(1,17))
    while len(rs) > 1:
        layer = []
        # Reduce layer by layer
        for i in range(len(rs) // 2):
            a = ctx.Share(rs[2*i  ])
            b = ctx.Share(rs[2*i+1])
            layer.append( singleOperation(ctx, a, b) )
        rs = asyncio.gather(*layer)
        print('lotsOfOperations: running loop:', asyncio.get_event_loop())
        rs = await rs
    return rs[0]

########## 
async def run_with_share_batches(ctx, prog):
    """
    Runs `prog` in a simulated event loop until it returns a value.
    We repeatedly run the event loop until it stops, indicating more
    shares are needed. Then we open a batch of shares, then deliver them
    via `ctx._deliver_shares()` and run the simloop some more.
    """

    # Create a simplified "in a sandbox" event loop
    from eventsim import EventSimulator
    simloop = EventSimulator()

    # Schedule the coroutine `prog` as a task in simloop
    assert asyncio.iscoroutine(prog)
    result_future = simloop.create_task(prog)

    main_loop = asyncio.get_event_loop()
    print('main thread loop:', main_loop)
    print('result_future.get_loop():', result_future.get_loop())
    
    # Coroutine to await on the result in simloop
    async def _await_simloop():
        # print('_await_simloop():', asyncio.get_event_loop())
        assert asyncio.get_event_loop() == simloop
        await result_future
        return

    # Alternate between simloop and open_share_array
    i = 0
    while True:
        print()
        print('#### Beginning iteration ####')
        # 1) Run the simloop
        print('Step 1) Running the simloop once')
        simloop.create_task(_await_simloop())
        # print('simloop.run_forever() begin')
        simloop.run_forever()
        # print('simloop.run_forever() stop')
        
        if simloop._immediate:
            print('simloop stopped, but was not empty. resume in current round')
        else:
            print('#### Round Completed ####', i)
            print()
            i += 1
        
        # Quit if done
        if result_future.done():
            print('result_future.result():', result_future.result())
            break

        # 2) Open a batch of shares in the main event loop
        print('Step 2) await ctx.open_share_array()')
        assert asyncio.get_event_loop() == main_loop
        await ctx.Share._open_batch()
        
    return result_future.result()
    

if __name__ == "__main__":
    # Create a mock MPC context and install Share class
    ctx = MpcContext()
    ctx.Share = share_in_context(ctx)

    # Create a coroutine for the MPC program
    prog = lotsOfOperations(ctx)

    # Run with share batches
    loop = asyncio.new_event_loop()
    loop.run_until_complete(run_with_share_batches(ctx, prog))
