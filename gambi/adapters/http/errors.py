"""Mapeamento de exceções de domínio → envelope de erro OpenAI (D8)."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from gambi.domain.models import (
    DomainError,
    EmptyConversationError,
    ModelNotFoundError,
    UpstreamAuthError,
    UpstreamError,
)
from gambi.observability import enrich


def _envelope(message: str, type_: str, code: str | None, status: int) -> JSONResponse:
    body: dict = {"error": {"message": message, "type": type_, "code": code}}
    return JSONResponse(status_code=status, content=body)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ModelNotFoundError)
    async def _model_not_found(_: Request, exc: ModelNotFoundError) -> JSONResponse:
        enrich(outcome="model_not_found", error_type="ModelNotFoundError")
        return _envelope(str(exc), "invalid_request_error", "model_not_found", 404)

    @app.exception_handler(EmptyConversationError)
    async def _empty_conversation(_: Request, exc: EmptyConversationError) -> JSONResponse:
        enrich(outcome="empty_conversation", error_type="EmptyConversationError")
        return _envelope(str(exc), "invalid_request_error", "empty_messages", 400)

    @app.exception_handler(UpstreamAuthError)
    async def _auth_error(_: Request, exc: UpstreamAuthError) -> JSONResponse:
        enrich(outcome="upstream_auth_error", error_type="UpstreamAuthError")
        return _envelope(str(exc), "api_error", "upstream_auth_error", 502)

    @app.exception_handler(UpstreamError)
    async def _upstream_error(_: Request, exc: UpstreamError) -> JSONResponse:
        # upstream_status já foi enriquecido pelo client; aqui marcamos o desfecho.
        enrich(outcome="upstream_error", error_type="UpstreamError")
        status = 404 if exc.status_code == 404 else 502
        return _envelope(str(exc), "api_error", "upstream_error", status)

    @app.exception_handler(DomainError)
    async def _domain_error(_: Request, exc: DomainError) -> JSONResponse:
        enrich(outcome="internal_error", error_type=type(exc).__name__)
        return _envelope(str(exc), "api_error", None, 500)
