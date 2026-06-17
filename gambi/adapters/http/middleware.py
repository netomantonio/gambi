"""WideEventMiddleware — ASGI puro (CAP-6 / AD-2).

Cria o wide event no início da request, captura status (do `http.response.start`) e
duração, e emite EXATAMENTE um evento no encerramento — inclusive em erro. Roda no mesmo
task do app downstream, então o `ContextVar` propaga para route/use case/adapter.
Emissão protegida: logar nunca derruba a request (núcleo sagrado).
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from gambi.observability.config import ObservabilityConfig
from gambi.observability.emit import emit
from gambi.observability.wide_event import new_event, reset_event

Send = Callable[[dict], Awaitable[None]]
Receive = Callable[[], Awaitable[dict]]


class WideEventMiddleware:
    def __init__(self, app, config: ObservabilityConfig) -> None:
        self.app = app
        self.config = config

    async def __call__(self, scope: dict, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        event, token = new_event(method=scope.get("method"), path=scope.get("path"))
        start = time.perf_counter()
        captured: dict[str, int | None] = {"status": None}

        async def send_wrapper(message: dict) -> None:
            if message.get("type") == "http.response.start":
                captured["status"] = message.get("status")
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            if event.outcome is None:
                event.outcome = "internal_error"
            raise
        finally:
            try:
                event.http_status = captured["status"]
                event.duration_ms = round((time.perf_counter() - start) * 1000, 3)
                if event.outcome is None:
                    status = event.http_status
                    event.outcome = (
                        "internal_error" if status is not None and status >= 400 else "success"
                    )
                emit(event, self.config)
            except Exception:  # noqa: BLE001 — observabilidade nunca derruba a request
                pass
            finally:
                reset_event(token)
