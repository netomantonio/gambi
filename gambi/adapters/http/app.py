"""Construção do app FastAPI. As use cases são injetadas via app.state pelo composition root."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from fastapi import FastAPI

from gambi.adapters.http import routes_chat, routes_models
from gambi.adapters.http.errors import register_exception_handlers
from gambi.adapters.http.middleware import WideEventMiddleware
from gambi.application.ports import AgentCatalogPort
from gambi.application.use_cases import (
    CreateChatCompletion,
    CreateChatCompletionStream,
    ListModels,
)
from gambi.observability.config import ObservabilityConfig

Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


def create_app(
    *,
    catalog: AgentCatalogPort,
    list_models: ListModels,
    create_chat_completion: CreateChatCompletion,
    create_chat_completion_stream: CreateChatCompletionStream,
    lifespan: Lifespan | None = None,
    observability: ObservabilityConfig | None = None,
) -> FastAPI:
    app = FastAPI(title="GAMBI", version="0.1.0", lifespan=lifespan)
    # Wide event (CAP-6): barato por default (só metadados, console). Outermost user middleware.
    app.add_middleware(WideEventMiddleware, config=observability or ObservabilityConfig())
    app.state.catalog = catalog
    app.state.list_models = list_models
    app.state.create_chat_completion = create_chat_completion
    app.state.create_chat_completion_stream = create_chat_completion_stream

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(routes_models.router)
    app.include_router(routes_chat.router)
    register_exception_handlers(app)
    return app
