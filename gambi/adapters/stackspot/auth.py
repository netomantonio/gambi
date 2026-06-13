"""StackSpotTokenProvider (D6) — OAuth client_credentials com cache + refresh.

Endpoint: POST https://idm.stackspot.com/{realm}/oidc/oauth/token (form-urlencoded).
Ver docs/stackspot/01-autenticacao.md.

OQ-5: a doc confirma TTL de 20 min (1200s) e não enumera os campos da resposta.
Usamos `expires_in` quando presente; caso ausente, caímos no TTL default de 1200s.
Margem de segurança evita usar um token a ponto de expirar.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import httpx

from gambi.domain.models import UpstreamAuthError

# TTL oficial do token StackSpot = 20 min (docs.stackspot.com .../access-token).
_DEFAULT_TTL_SECONDS = 1200.0
_REFRESH_MARGIN_SECONDS = 60.0


class StackSpotTokenProvider:
    """Implementa TokenProviderPort."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        realm: str,
        client_id: str,
        client_secret: str,
        idm_base_url: str = "https://idm.stackspot.com",
        default_ttl: float = _DEFAULT_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client
        self._token_url = f"{idm_base_url.rstrip('/')}/{realm}/oidc/oauth/token"
        self._client_id = client_id
        self._client_secret = client_secret
        self._default_ttl = default_ttl
        self._clock = clock
        self._cached_token: str | None = None
        self._expires_at: float = 0.0

    async def get_token(self) -> str:
        if self._cached_token is not None and self._clock() < self._expires_at:
            return self._cached_token
        return await self._refresh()

    async def _refresh(self) -> str:
        try:
            response = await self._client.post(
                self._token_url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
            )
        except httpx.HTTPError as exc:  # rede/timeout
            raise UpstreamAuthError(f"falha ao contatar o IDM do StackSpot: {exc}") from exc

        if response.status_code != 200:
            raise UpstreamAuthError(
                f"IDM do StackSpot retornou {response.status_code} ao emitir token"
            )

        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise UpstreamAuthError("resposta de token sem 'access_token'")

        ttl = float(payload.get("expires_in", self._default_ttl))
        self._cached_token = token
        self._expires_at = self._clock() + max(0.0, ttl - _REFRESH_MARGIN_SECONDS)
        return token
