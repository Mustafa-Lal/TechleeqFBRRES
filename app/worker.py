"""Persistent pending-invoice worker, enabled only by operator configuration."""

import asyncio
from contextlib import asynccontextmanager, suppress
from app.province_adapters import *


async def run_worker():
    while True:
        try:
            await asyncio.to_thread(
                process_pending,
                {"id": 0, "role": "manager", "username": "fiscal-worker"},
            )
        except Exception:
            # Pending records remain durable; never turn unknown outcomes into retries.
            import logging

            logging.getLogger(__name__).exception("Fiscal queue processing failed")
        await asyncio.sleep(10)


@asynccontextmanager
async def lifespan(application):
    task = (
        asyncio.create_task(run_worker())
        if os.getenv("FISCAL_WORKER_ENABLED", "false").lower() == "true"
        else None
    )
    yield
    if task:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app.router.lifespan_context = lifespan
