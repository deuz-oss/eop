import asyncio
import sys

if sys.platform == "win32":
    # Windows' default ProactorEventLoopPolicy can hang inside `loop.close()`
    # (blocked in `_poll()`) once many event loops are created and torn down
    # within one process. This suite does exactly that at scale: every API
    # test spins up a fresh Starlette `TestClient` (and therefore a fresh
    # anyio blocking portal + event loop), and every repository/service test
    # opens its own asyncpg-backed engine bound to its own event loop --
    # thousands of loop create/close cycles across a full run. Under
    # Proactor's IOCP-based polling, a loop's `close()` can block
    # indefinitely waiting on a completion that never arrives. `Selector`
    # event loops don't use IOCP and don't exhibit this hang; the only
    # capability traded away (subprocess I/O) is unused anywhere in this
    # suite or the application it tests.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
