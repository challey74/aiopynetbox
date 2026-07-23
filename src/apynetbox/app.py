"""App: attribute access to a NetBox application's endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apynetbox.endpoint import Endpoint

if TYPE_CHECKING:
    from apynetbox.api import Api


class App:
    """Represents a NetBox app (dcim, ipam, ...); any attribute access
    returns an Endpoint, e.g. nb.dcim.devices."""

    def __init__(self, api: Api, name: str) -> None:
        self._api = api
        self.name = name

    def __getattr__(self, name: str) -> Endpoint:
        if name.startswith("_"):
            raise AttributeError(name)
        return Endpoint(self._api, self, name)

    def endpoint(self, name: str) -> Endpoint:
        """An Endpoint whose slug is used verbatim (no underscore-to-dash
        conversion), for plugin endpoints with literal underscores."""
        return Endpoint(self._api, self, name, literal_name=True)


class PluginsApp:
    """nb.plugins: attribute access routes into /api/plugins/<name>/...,
    e.g. nb.plugins.bgp.sessions -> /api/plugins/bgp/sessions/."""

    def __init__(self, api: Api) -> None:
        self._api = api

    def __getattr__(self, name: str) -> App:
        if name.startswith("_"):
            raise AttributeError(name)
        return App(self._api, "plugins/{}".format(name.replace("_", "-")))

    async def installed_plugins(self) -> list[dict[str, Any]]:
        """The plugins installed on the NetBox instance."""
        return await self._api._request(
            "GET", "{}/plugins/installed-plugins/".format(self._api.base_url)
        )
