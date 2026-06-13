"""Composition root: monta adapters + use cases e expõe `app` para o uvicorn.

Uso: uv run uvicorn gambi.main:app --reload
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from gambi.adapters.catalog.config_catalog import ConfigAgentCatalog
from gambi.adapters.http.app import create_app
from gambi.adapters.stackspot.auth import StackSpotTokenProvider
from gambi.adapters.stackspot.client import StackSpotAgentInvoker
from gambi.adapters.stackspot.stream import StackSpotAgentStreamer
from gambi.application.use_cases import (
    CreateChatCompletion,
    CreateChatCompletionStream,
    ListModels,
)
from gambi.config import Settings


def build_app(settings: Settings | None = None):
    settings = settings or Settings.from_env()

    http_client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))

    token_provider = StackSpotTokenProvider(
        client=http_client,
        realm=settings.realm,
        client_id=settings.client_id,
        client_secret=settings.client_secret,
    )
    invoker = StackSpotAgentInvoker(
        client=http_client,
        token_provider=token_provider,
        stackspot_knowledge=settings.stackspot_knowledge,
    )
    streamer = StackSpotAgentStreamer(
        client=http_client,
        token_provider=token_provider,
        stackspot_knowledge=settings.stackspot_knowledge,
    )
    catalog = ConfigAgentCatalog(settings.agents)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await http_client.aclose()

    return create_app(
        list_models=ListModels(catalog),
        create_chat_completion=CreateChatCompletion(catalog, invoker),
        create_chat_completion_stream=CreateChatCompletionStream(catalog, streamer),
        lifespan=lifespan,
    )


app = build_app()
