"""Custom APIRoute to auto-wrap responses."""
from typing import Callable

from fastapi import Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.requests import Request
from starlette.responses import Response as StarletteResponse

from app.core.response_codes import ResponseCode


class CustomAPIRoute(APIRoute):
    """Route that wraps handler returns into the unified ApiResponse shape."""

    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()
        default_status = self.status_code or 200

        async def custom_route_handler(request: Request) -> Response:
            response = await original_route_handler(request)

            # Pass through existing Response objects (file downloads, streams, etc.)
            if isinstance(response, StarletteResponse):
                return response

            # Return 204 when handler returns None
            if response is None:
                return Response(status_code=204)

            # Avoid double wrapping if already in unified shape
            if isinstance(response, dict) and all(
                key in response for key in ("code", "message", "data")
            ):
                return JSONResponse(content=response, status_code=default_status)

            wrapped_response = {
                "code": int(ResponseCode.SUCCESS),
                "message": "ok",
                "data": response,
            }
            return JSONResponse(content=wrapped_response, status_code=default_status)

        return custom_route_handler
