from gambi.domain.mapping import FinishReasonMapper, ResponseMapper
from gambi.domain.models import AgentReply, FinishReason, Usage


def test_finish_reason_known():
    m = FinishReasonMapper()
    assert m.map("stop") == FinishReason.STOP
    assert m.map("max_tokens") == FinishReason.LENGTH
    assert m.map("content_filter") == FinishReason.CONTENT_FILTER


def test_finish_reason_unknown_defaults_to_stop():
    # OQ-6: valor desconhecido não inventa — cai em STOP seguro.
    assert FinishReasonMapper().map("alienígena") == FinishReason.STOP
    assert FinishReasonMapper().map(None) == FinishReason.STOP


def test_response_mapper_passes_through_usage_and_content():
    reply = AgentReply(
        message="resposta do agent",
        stop_reason="stop",
        usage=Usage(prompt_tokens=5, completion_tokens=5),
    )
    result = ResponseMapper().to_chat_result(reply, model_id="m1")
    assert result.content == "resposta do agent"
    assert result.model_id == "m1"
    assert result.finish_reason == FinishReason.STOP
    assert result.usage.prompt_tokens == 5
    assert result.usage.completion_tokens == 5
    assert result.usage.total_tokens == 10
