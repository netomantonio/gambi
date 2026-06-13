import httpx
import pytest
import respx

from gambi.adapters.stackspot.auth import StackSpotTokenProvider
from gambi.domain.models import UpstreamAuthError

TOKEN_URL = "https://idm.stackspot.com/stackspot/oidc/oauth/token"


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _provider(client: httpx.AsyncClient, clock: FakeClock | None = None) -> StackSpotTokenProvider:
    return StackSpotTokenProvider(
        client=client,
        realm="stackspot",
        client_id="id",
        client_secret="sec",
        clock=clock or FakeClock(),
    )


@respx.mock
async def test_obtains_and_caches_token():
    route = respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok-1", "expires_in": 3600})
    )
    async with httpx.AsyncClient() as client:
        provider = _provider(client)
        first = await provider.get_token()
        second = await provider.get_token()

    assert first == "tok-1"
    assert second == "tok-1"
    assert route.call_count == 1  # segunda chamada veio do cache


@respx.mock
async def test_refreshes_after_expiry():
    clock = FakeClock()
    route = respx.post(TOKEN_URL).mock(
        side_effect=[
            httpx.Response(200, json={"access_token": "tok-1", "expires_in": 100}),
            httpx.Response(200, json={"access_token": "tok-2", "expires_in": 100}),
        ]
    )
    async with httpx.AsyncClient() as client:
        provider = _provider(client, clock)
        assert await provider.get_token() == "tok-1"
        clock.now = 80.0  # além do expires_at (100 - margem 30 = 70)
        assert await provider.get_token() == "tok-2"

    assert route.call_count == 2


@respx.mock
async def test_auth_failure_raises():
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(401, json={}))
    async with httpx.AsyncClient() as client:
        provider = _provider(client)
        with pytest.raises(UpstreamAuthError):
            await provider.get_token()
