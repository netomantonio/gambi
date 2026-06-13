"""Construção do app FastAPI. As use cases são injetadas via app.state pelo composition root."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from fastapi import FastAPI

from gambi.adapters.http import routes_chat, routes_models
from gambi.adapters.http.errors import register_exception_handlers
from gambi.application.use_cases import (
    CreateChatCompletion,
    CreateChatCompletionStream,
    ListModels,
)

Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


def create_app(
    *,
    list_models: ListModels,
    create_chat_completion: CreateChatCompletion,
    create_chat_completion_stream: CreateChatCompletionStream,
    lifespan: Lifespan | None = None,
) -> FastAPI:
    app = FastAPI(title="GAMBI", version="0.1.0", lifespan=lifespan)
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
