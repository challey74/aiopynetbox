"""Api: the entry point to aiopynetbox."""

from __future__ import annotations

import asyncio
import random
from types import TracebackType
from typing import Any

import httpx

from aiopynetbox.app import PluginsApp
from aiopynetbox.apps import (
    CircuitsApp,
    CoreApp,
    DcimApp,
    ExtrasApp,
    IpamApp,
    TenancyApp,
    UsersApp,
    VirtualizationApp,
    VpnApp,
    WirelessApp,
)
from aiopynetbox.exceptions import AllocationError, ContentError, RequestError
from aiopynetbox.response import Record

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

        async with aiopynetbox.api("https://netbox", token="...") as nb:
            device = await nb.dcim.devices.get(name="sw-1")

    Pass `client` to supply a custom httpx.AsyncClient (SSL config, mock
    transports in tests, ...).

    `pagination` selects how result sets page through list views:
    "offset" (default) fetches pages concurrently once the first page
    reveals the count; "cursor" (NetBox 4.6+) pages with the `start`
    parameter in constant time per page, but sequentially, since each
    page's cursor comes from the previous response.

    `retries` bounds automatic retries with exponential backoff and
    jitter: 429 responses are retried for any method (honoring
    Retry-After); transient 502/503/504 and connection failures are
    retried for GETs only, since an ambiguous write may have been
    processed. `retries=0` disables.
    """

    def __init__(
        self,
        url: str,
        token: str | None = None,
        *,
        timeout: float = 30.0,
        max_concurrency: int = 4,
        pagination: str = "offset",
        retries: int = 3,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if pagination not in ("offset", "cursor"):
            raise ValueError("pagination must be 'offset' or 'cursor'")
        self.base_url = "{}/api".format(url.rstrip("/"))
        self.token = token
        self.max_concurrency = max_concurrency
        self.pagination = pagination
        self.retries = retries
        self._openapi: dict[str, Any] | None = None
        # follow_redirects matches requests/pynetbox behavior: NetBox's
        # hyperlinked `url` fields may redirect (e.g. http->https behind a
        # proxy) and record methods fetch those urls directly.
        self._client = (
            client
            if client is not None
            else httpx.AsyncClient(timeout=timeout, follow_redirects=True)
        )

        self.circuits = CircuitsApp(self, "circuits")
        self.core = CoreApp(self, "core")
        self.dcim = DcimApp(self, "dcim")
        self.extras = ExtrasApp(self, "extras")
        self.ipam = IpamApp(self, "ipam")
        self.plugins = PluginsApp(self)
        self.tenancy = TenancyApp(self, "tenancy")
        self.users = UsersApp(self, "users")
        self.virtualization = VirtualizationApp(self, "virtualization")
        self.vpn = VpnApp(self, "vpn")
        self.wireless = WirelessApp(self, "wireless")

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

    def _backoff(self, attempt: int, retry_after: str | None) -> float:
        """Delay in seconds before retry `attempt` (0-based)."""
        if retry_after is not None:
            try:
                # Honor Retry-After, capped so a broken proxy can't stall us.
                return min(float(retry_after), 60.0)
            except ValueError:
                pass  # HTTP-date form; fall through to exponential backoff
        delay = min(0.5 * 2**attempt, 8.0)
        return delay * (0.5 + random.random() / 2)

    async def _request_response(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        merged = {
            "Accept": "application/json",
            **self._auth_headers(),
            **(headers or {}),
        }
        attempt = 0
        while True:
            retry_after = None
            try:
                resp = await self._client.request(
                    method, url, params=params, json=json, headers=merged
                )
            except httpx.TransportError:
                # An ambiguous failure is only safely repeatable for GETs:
                # a timed-out write may have been processed server-side.
                if method != "GET" or attempt >= self.retries:
                    raise
            else:
                if resp.status_code == 429 and attempt < self.retries:
                    # Rejected without processing; safe to retry any method.
                    retry_after = resp.headers.get("Retry-After")
                elif (
                    resp.status_code in (502, 503, 504)
                    and method == "GET"
                    and attempt < self.retries
                ):
                    pass
                else:
                    if resp.status_code == 304 and "If-None-Match" in merged:
                        return resp
                    if not resp.is_success:
                        if method == "POST" and resp.status_code == 409:
                            raise AllocationError(resp)
                        raise RequestError(resp)
                    return resp
            await asyncio.sleep(self._backoff(attempt, retry_after))
            attempt += 1

    @staticmethod
    def _decode(resp: httpx.Response) -> Any:
        try:
            return resp.json()
        except ValueError:
            raise ContentError(resp) from None

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        resp = await self._request_response(
            method, url, params=params, json=json, headers=headers
        )
        if method == "DELETE":
            return True
        return self._decode(resp)

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

    async def openapi(self) -> dict[str, Any]:
        """The OpenAPI spec (NetBox 3.5+), cached after the first call."""
        if self._openapi is None:
            spec: dict[str, Any] = await self._request(
                "GET", "{}/schema/".format(self.base_url)
            )
            self._openapi = spec
        return self._openapi

    async def create_token(self, username: str, password: str) -> Record:
        """Provision an API token from NetBox credentials and adopt it for
        subsequent requests.

        For v2 tokens (NetBox 4.5+) `self.token` becomes the full
        `nbt_<key>.<token>` auth value, which differs from `token.key`.
        """
        data = await self._request(
            "POST",
            "{}/users/tokens/provision/".format(self.base_url),
            json={"username": username, "password": password},
        )
        if data.get("version") == 2:
            self.token = "{}{}.{}".format(TOKEN_PREFIX, data["key"], data["token"])
        else:
            self.token = data.get("token") or data["key"]
        return Record(data, self, full=True)
