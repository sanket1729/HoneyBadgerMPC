import asyncio

# EventSimulator from
# https://stackoverflow.com/questions/40329421/how-can-i-learn-how-to-implement-a-custom-python-asyncio-event-loop
# https://gist.github.com/damonjw/35aac361ca5d313ee9bf79e00261f4ea

class EventSimulator(asyncio.AbstractEventLoop):
    '''A simple event-driven simulator, using async/await'''

    def __init__(self):
        self._time = 0
        self._running = False
        self._immediate = []
        self._exc = None
        
    def get_debug(self):
        # A silly hangover from the way asyncio is written
        return False
    
    # Methods for running the event loop.
    # For a real asyncio system you need to worry a lot more about running+closed.
    # For a simple simulator, we completely control the passage of time, so most of
    # these functions are trivial.
    #
    # I've split the pending events into _immediate and _scheduled.
    # I could put them all in _scheduled; but if there are lots of
    # _immediate calls there's no need for them to clutter up the heap.
    
    def run_forever(self):
        # Run until stopped or out of tasks
        self._running = True
        try:
            # Set the event loop
            orig_loop = asyncio._get_running_loop()
            asyncio.events._set_running_loop(self)

            # Process one task at a time
            while (self._immediate) and self._running:
                h = self._immediate[0]
                self._immediate = self._immediate[1:]
                if not h._cancelled:
                    h._run()
                if self._exc is not None:
                    raise self._exc
        finally:
            # Restore the event loop
            asyncio.events._set_running_loop(orig_loop)

    def is_running(self):
        return self._running
    def is_closed(self):
        return not self._running
    def stop(self):
        self._running = False
    def close(self):
        self._running = False
    def shutdown_asyncgens(self):
        pass

    def call_exception_handler(self, context):
        # If there is any exception in a callback, this method gets called.
        # I'll store the exception in self._exc, so that the main simulation loop picks it up.
        self._exc = context.get('exception', None)


    # Methods for scheduling jobs.
    #
    # If the job is a coroutine, the end-user should call asyncio.ensure_future(coro()).
    # The asyncio machinery will invoke loop.create_task(). Asyncio will then
    # run the coroutine in pieces, breaking it apart at async/await points, and every time it
    # will construct an appropriate callback and call loop.call_soon(cb).
    #
    # If the job is a plain function, the end-user should call one of the loop.call_*()
    # methods directly.
    
    def call_soon(self, callback, *args, context=None):
        h = asyncio.Handle(callback, args, self, context)
        self._immediate.append(h)
        return h
        
    def create_task(self, coro):
        # Since this is a simulator, I'll run a plain simulated-time event loop, and
        # if there are any exceptions inside any coroutine I'll pass them on to the
        # event loop, so it can halt and print them out. To achieve this, I need the
        # exception to be caught in "async mode" i.e. by a coroutine, and then
        # use self._exc to pass it on to "regular execution mode".
        async def wrapper():
            try:
                return await coro
            except Exception as e:
                print("Wrapped exception")
                self._exc = e
        #return asyncio.Task(wrapper(), loop=self)
        return asyncio.Task(coro, loop=self)
        
    def create_future(self):
        # Not sure why this is here rather than in AbstractEventLoop.
        return asyncio.Future(loop=self)
