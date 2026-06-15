"""Monta o corpo do request da Agents API do StackSpot a partir das opções por agent.

Campos confirmados-reais (capturados da API em 2026-06-15): streaming, user_prompt,
stackspot_knowledge, deep_search_ks, return_ks_in_response, knowledge_source_ids,
agent_version_number.
"""

from __future__ import annotations

from gambi.domain.models import StackSpotAgentOptions


def build_payload(*, user_prompt: str, streaming: bool, options: StackSpotAgentOptions) -> dict:
    payload: dict = {
        "streaming": streaming,
        "user_prompt": user_prompt,
        "stackspot_knowledge": options.stackspot_knowledge,
        "deep_search_ks": options.deep_search_ks,
        "return_ks_in_response": options.return_ks_in_response,
    }
    if options.knowledge_source_ids:
        payload["knowledge_source_ids"] = list(options.knowledge_source_ids)
    if options.agent_version_number is not None:
        payload["agent_version_number"] = options.agent_version_number
    return payload
