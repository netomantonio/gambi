"""BufferedAgentStreamInvoker — AgentInvokerPort via STREAMING + acumulação.

Motivo (confirmado por wide event, 2026-06-17): o StackSpot tem um teto de ~120s para uma
resposta **não-streaming** — o gateway derruba a conexão com `RemoteProtocolError: Server
disconnected without sending a response`. Turnos agênticos longos (prompt grande, muitas
tools) passam disso e sempre falham com 502. Aumentar o timeout do nosso cliente não ajuda:
só troca o `ReadTimeout` nosso pelo disconnect do gateway.

Solução: chamar o StackSpot em `streaming:True` (a conexão fica viva enquanto os tokens
fluem) e **acumular** os deltas aqui, devolvendo o `AgentReply` inteiro — exatamente o que o
use case espera. Assim o parsing do structured output (tool_calls/conteúdo) segue idêntico.
"""

from __future__ import annotations

from gambi.application.ports import AgentStreamPort
from gambi.domain.models import AgentReply, StackSpotAgentOptions, Usage


class BufferedAgentStreamInvoker:
    def __init__(self, streamer: AgentStreamPort) -> None:
        self._streamer = streamer

    async def invoke(
        self, agent_id: str, user_prompt: str, options: StackSpotAgentOptions
    ) -> AgentReply:
        parts: list[str] = []
        stop_reason: str | None = None
        usage = Usage(0, 0)
        sources: tuple[str, ...] = ()
        async for event in self._streamer.stream(agent_id, user_prompt, options):
            if event.delta:
                parts.append(event.delta)
            if event.final:
                stop_reason = event.stop_reason
                if event.usage is not None:
                    usage = event.usage
                if event.sources:
                    sources = event.sources
        return AgentReply(
            message="".join(parts), stop_reason=stop_reason, usage=usage, sources=sources
        )
