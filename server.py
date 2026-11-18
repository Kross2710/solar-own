"""Solar dashboard FastAPI entrypoint.

Run directly with:
    python server.py

Or through an ASGI server with:
    uvicorn server:app
"""

from __future__ import annotations

import os

from backend.app import create_app
from backend.runtime import create_runtime


runtime = create_runtime()
app = create_app(runtime)


if __name__ == "__main__":
    import uvicorn

    config = runtime.config
    # HOST and PORT let the public port stay on the web server without editing config.json.
    host = os.environ.get("HOST") or config.get("host", "127.0.0.1")
    port = int(os.environ.get("PORT") or config.get("port", 8787))

    print(f"     Current live provider: {runtime.live_provider.__class__.__name__}")
    print(
        "     Current history provider: "
        f"{runtime.history_provider.__class__.__name__}"
    )
    print(f"     History source: {runtime.history_source}")
    print("\n  Solar dashboard")
    print(
        f"     Source : {config.get('source', 'mock')}  "
        f"(configuration: {config.get('_file', '-')})"
    )
    print(f"     Listening on    : http://{host}:{port}\n")

    uvicorn.run(app, host=host, port=port, log_level="warning")
