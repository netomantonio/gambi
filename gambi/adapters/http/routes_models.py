"""Rota GET /v1/models (CAP-1)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from gambi.adapters.http.schemas_openai import Model, ModelList
from gambi.application.use_cases import ListModels

router = APIRouter()


@router.get("/v1/models", response_model=ModelList)
async def list_models(request: Request) -> ModelList:
    use_case: ListModels = request.app.state.list_models
    entries = use_case.execute()
    return ModelList(data=[Model(id=e.model_id) for e in entries])
