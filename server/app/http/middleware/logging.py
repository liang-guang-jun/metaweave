"""Contextvar-safe ASGI request lifecycle logging."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import uuid4

from ....kernel.application.context import (
    ExecutionContext,
    MessageMetadata,
    execution_context,
)
from ....kernel.infrastructure.logging import bind_context, get_logger
from ...bootstrap.config import LoggingConfig

type Scope = dict[str, Any]
type Receive = Callable[[], Awaitable[dict[str, Any]]]
type Send = Callable[[dict[str, Any]], Awaitable[None]]
type AsgiApp = Callable[[Scope, Receive, Send], Awaitable[None]]


class HttpLoggingMiddleware:
    """Log one HTTP lifecycle while making request metadata available downstream."""

    def __init__(self, app: AsgiApp, config: LoggingConfig) -> None:
        """Store the ASGI application and its configured request logger."""
        self._app = app
        self._logger = get_logger("server.http")
        self._log_request_headers = config.log_request_headers

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Log HTTP completion without affecting non-HTTP ASGI scopes."""
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        headers = _headers(scope)
        request_id = headers.get("x-request-id", str(uuid4()))
        correlation_id = headers.get("x-correlation-id", request_id)
        status_code = 500

        async def send_with_status(message: dict[str, Any]) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
            await send(message)

        metadata = MessageMetadata(
            message_id=request_id,
            correlation_id=correlation_id,
            causation_id=None,
            user_id=None,
            tenant_id=None,
            occurred_at=datetime.now(UTC),
        )
        http_fields: dict[str, Any] = {
            "method": scope["method"],
            "path": scope["path"],
        }
        if self._log_request_headers:
            http_fields["request_headers"] = headers

        with bind_context(http_request_id=request_id, correlation_id=correlation_id):
            with execution_context(ExecutionContext(metadata)):
                started_at = perf_counter()
                self._logger.info("http.request.started", **http_fields)
                try:
                    await self._app(scope, receive, send_with_status)
                except Exception:
                    self._logger.exception(
                        "http.request.finished",
                        **http_fields,
                        status_code=status_code,
                        success=False,
                        duration_ms=_duration_ms(started_at),
                    )
                    raise
                self._logger.info(
                    "http.request.finished",
                    **http_fields,
                    status_code=status_code,
                    success=True,
                    duration_ms=_duration_ms(started_at),
                )


def _headers(scope: Scope) -> dict[str, str]:
    """Decode ASGI headers once for correlation extraction and optional logging."""
    return {
        name.decode("latin-1").lower(): value.decode("latin-1")
        for name, value in scope.get("headers", [])
    }


def _duration_ms(started_at: float) -> float:
    """Return elapsed monotonic time rounded for compact structured output."""
    return round((perf_counter() - started_at) * 1000, 3)
