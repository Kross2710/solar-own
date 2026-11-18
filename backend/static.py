"""Static-file compatibility for the legacy dashboard."""

from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
from starlette.types import Scope


class NoCacheStaticFiles(StaticFiles):
    async def get_response(
        self,
        path: str,
        scope: Scope,
    ) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response
