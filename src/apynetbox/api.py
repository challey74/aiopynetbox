"""Api: the entry point to apynetbox."""

from __future__ import annotations

from types import TracebackType
from typing import Any

import httpx

from apynetbox.app import App, PluginsApp
from apynetbox.exceptions import ContentError, RequestError

# NetBox v2 token prefix (introduced in NetBox 4.5.0)
TOKEN_PREFIX = "nbt_"


def _is_v2_token(token: str | None) -> bool:
    """V2 tokens (NetBox 4.5+) look like nbt_<id>.<token> and use Bearer auth."""
    if not token or not token.startswith(TOKEN_PREFIX):
        return False
    return "." in token[len(TOKEN_PREFIX) :]


class Api:
    """Async NetBox API client.

    Use as an async context manager so the connection pool is closed:

        async with apynetbox.api("https://netbox", token="...") as nb:
            device = await nb.dcim.devices.get(name="sw-1")

    Pass `client` to supply a custom httpx.AsyncClient (SSL config, mock
    transports in tests, ...).
    """

    def __init__(
        self,
        url: str,
        token: str | None = None,
        *,
        timeout: float = 30.0,
        max_concurrency: int = 4,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = "{}/api".format(url.rstrip("/"))
        self.token = token
        self.max_concurrency = max_concurrency
        # follow_redirects matches requests/pynetbox behavior: NetBox's
        # hyperlinked `url` fields may redirect (e.g. http->https behind a
        # proxy) and record methods fetch those urls directly.
        self._client = (
            client
            if client is not None
            else httpx.AsyncClient(timeout=timeout, follow_redirects=True)
        )

        self.circuits = App(self, "circuits")
        self.core = App(self, "core")
        self.dcim = App(self, "dcim")
        self.extras = App(self, "extras")
        self.ipam = App(self, "ipam")
        self.plugins = PluginsApp(self)
        self.tenancy = App(self, "tenancy")
        self.users = App(self, "users")
        self.virtualization = App(self, "virtualization")
        self.vpn = App(self, "vpn")
        self.wireless = App(self, "wireless")

    async def __aenter__(self) -> Api:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    def _auth_headers(self) -> dict[str, str]:
        if not self.token:
            return {}
        scheme = "Bearer" if _is_v2_token(self.token) else "Token"
        return {"Authorization": "{} {}".format(scheme, self.token)}

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
    ) -> Any:
        headers = {"Accept": "application/json", **self._auth_headers()}
        resp = await self._client.request(
            method, url, params=params, json=json, headers=headers
        )
        if method == "DELETE":
            if resp.is_success:
                return True
            raise RequestError(resp)
        if not resp.is_success:
            raise RequestError(resp)
        try:
            return resp.json()
        except ValueError:
            raise ContentError(resp) from None

    async def version(self) -> str:
        """The NetBox API version string, read from response headers."""
        resp = await self._client.get(
            "{}/".format(self.base_url), headers=self._auth_headers()
        )
        if resp.is_success or resp.status_code == 403:
            return resp.headers.get("API-Version", "")
        raise RequestError(resp)

    async def status(self) -> dict[str, Any]:
        """The /api/status/ payload (NetBox version, plugins, workers...)."""
        return await self._request("GET", "{}/status/".format(self.base_url))
