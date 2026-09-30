"""Run one history sync pass by hand (the server already does this on startup and every 12 h)."""

import asyncio
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from backend.runtime import create_runtime
from backend.services.collector import close_providers, snapshot
from backend.services.sync import sync_once


async def main() -> None:
    runtime = create_runtime()
    try:
        await snapshot(runtime)
        await sync_once(runtime)
    finally:
        await close_providers(runtime)


if __name__ == "__main__":
    asyncio.run(main())
