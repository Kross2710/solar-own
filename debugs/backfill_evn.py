"""Run one EVN portal sync by hand (the server already does this on startup and every 12 h)."""

import asyncio
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from backend.runtime import create_runtime
from backend.services.sync import build_evn_portal, evn_sync_once


async def main() -> None:
    runtime = create_runtime()
    portal = build_evn_portal(runtime.config)
    if portal is None:
        print("  [evn] portal disabled or missing credentials in config.evn.portal")
        return
    try:
        result = await evn_sync_once(runtime, portal)
        print(f"  [evn] {result['days']} days + {result['bills']} bills; {runtime.store.evn_counts()} stored")
    finally:
        await portal.close()


if __name__ == "__main__":
    asyncio.run(main())
