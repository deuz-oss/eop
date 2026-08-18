import asyncio
import sys
from collections.abc import Generator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base

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


async def _create_schema() -> None:
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


@pytest.fixture(scope="session")
def _schema_ready() -> None:
    """Ensures every table exists -- once per test session, not once per
    test. Every affected file's old local fixture repeated
    `Base.metadata.create_all` (idempotent, but not free: a full
    `create_async_engine`/`dispose()` cycle) before every single test.
    Measured directly: making `clean_database` below additionally open a
    *third* engine per test for this (on top of the two truncate cycles)
    increased a full-suite run from ~40-55 minutes to 64 minutes and the
    `ConnectionResetError` failure count roughly fivefold -- confirming
    engine-creation frequency, not test logic, drives the connection
    pressure this suite exhibits at ~2800-test scale. Session-scoping this
    removes ~2800 redundant engine cycles down to exactly one.
    """
    asyncio.run(_create_schema())


async def _reset_tables() -> None:
    """Truncates every table registered on `Base.metadata`, CASCADE, in a
    single statement -- Postgres resolves FK ordering itself, so no
    manually curated per-file table list (and its staleness risk as new
    models are added) is needed.
    """
    table_names = ", ".join(Base.metadata.tables.keys())
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE TABLE {table_names} CASCADE"))
    await engine.dispose()


def clean_database(_schema_ready: None) -> Generator[None]:
    """Shared isolation fixture body for every API-style test file (each
    file wraps this in its own `@pytest.fixture(autouse=True) def
    _tables()`, not applied globally here -- repository tests use their own
    transaction-rollback isolation and don't need this).

    Every test using this must start from a guaranteed-clean database,
    regardless of whether the *previous* test's teardown succeeded --
    reset runs before the test body, not only after it. Previously, each
    test file's local `_tables` fixture only truncated after the test
    (`_create()` then `yield` then `_truncate()`), with no defensive
    mechanism protecting the next test from a failed cleanup -- a failed
    teardown (e.g. from a transient connection drop under load) could
    silently leave stale rows that a later, unrelated test file would
    collide with. Reset failures here are not swallowed: `asyncio.run`
    propagates them as ordinary pytest setup/teardown errors.

    Depends on `_schema_ready` (session-scoped) purely to guarantee it has
    run first, at least once -- not to repeat schema creation per test.
    """
    asyncio.run(_reset_tables())
    yield
    asyncio.run(_reset_tables())
