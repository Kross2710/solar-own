"""Diagnostic script cho GoodWe cloud connectivity.

Usage:
    ...
"""
import asyncio
import logging
import sys
import json

from pathlib import Path

# Point to base directory
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from server import load_config, build_provider, _snapshot

config = load_config()
live_provider = build_provider(config)
POLL = 20
state: dict = {"latest": None}

async def print_cloud():
    try:
        async with asyncio.timeout(10):
            m = await _snapshot()
            print(m)
            
    except TimeoutError:
        print("Out of time 10s")
    except Exception as e:
        print(f"Error: {type(e).__name__} - {e}")

if __name__ == "__main__":
    try:
        asyncio.run(print_cloud())
    except KeyboardInterrupt:
        print("\nCancelled by Ctrl+C.")