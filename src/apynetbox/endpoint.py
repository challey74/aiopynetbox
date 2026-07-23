"""Endpoint: actions available on a NetBox API endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apynetbox.exceptions import RequestError
from apynetbox.models import ENDPOINT_MODELS
from apynetbox.response import Record, RecordSet

if TYPE_CHECKING:
    from apynetbox.api import Api
    from apynetbox.app import App


class Endpoint:
    def __init__(self, api: Api, app: App, name: str) -> None:
        self.api = api
        self.name = name.replace("_", "-")
        self.url = "{}/{}/{}/".format(api.base_url, app.name, self.name)
        self.record_class = ENDPOINT_MODELS.get(
            "{}/{}".format(app.name, self.name), Record
        )
        self._choices: dict[str, list[dict[str, Any]]] | None = None

    async def get(self, *args: int | str, **kwargs: Any) -> Record | None:
        """Get a single Record by id or by filter kwargs.

        Returns None if nothing matches. Raises ValueError if kwargs match
        more than one object.
        """
        if args:
            try:
                data = await self.api._request("GET", "{}{}/".format(self.url, args[0]))
            except RequestError as e:
                if e.status_code == 404:
                    return None
                raise
            return self.record_class(data, self.api, full=True)
        it = aiter(self.filter(**kwargs))
        try:
            first = await anext(it, None)
            if first is None:
                return None
            if await anext(it, None) is not None:
                raise ValueError(
                    "get() returned more than one result. Check that the "
                    "kwarg(s) passed are valid for this endpoint or use "
                    "filter() or all() instead."
                )
        finally:
            await it.aclose()
        return first

    def filter(self, **kwargs: Any) -> RecordSet:
        """Query the endpoint with filters; returns a lazy RecordSet."""
        if not kwargs:
            raise ValueError("filter must be passed kwargs. Use all() instead.")
        return RecordSet(self, kwargs)

    def all(self, limit: int = 0, offset: int | None = None) -> RecordSet:
        """Return a RecordSet over every object on the endpoint."""
        if offset is not None and not limit:
            raise ValueError("offset requires a positive limit value")
        return RecordSet(self, limit=limit, offset=offset)

    async def count(self, **kwargs: Any) -> int:
        """Object count for the given filters (all objects if none)."""
        return await RecordSet(self, kwargs).count()

    async def create(
        self, *args: dict[str, Any] | list[dict[str, Any]], **kwargs: Any
    ) -> Record | list[Record]:
        """POST a new object (kwargs or a single dict) or a list of dicts."""
        data = args[0] if args else kwargs
        resp = await self.api._request("POST", self.url, json=data)
        if isinstance(resp, list):
            return [self.record_class(i, self.api, full=True) for i in resp]
        return self.record_class(resp, self.api, full=True)

    async def update(self, objects: list[dict[str, Any]]) -> list[Record]:
        """Bulk PATCH a list of dicts, each of which must contain "id"."""
        resp = await self.api._request("PATCH", self.url, json=objects)
        return [self.record_class(i, self.api, full=True) for i in resp]

    async def delete(self, objects: list[int | Record]) -> bool:
        """Bulk DELETE objects given as ids or Records."""
        ids = [o.id if isinstance(o, Record) else o for o in objects]
        return await self.api._request(
            "DELETE", self.url, json=[{"id": i} for i in ids]
        )

    async def choices(self) -> dict[str, list[dict[str, Any]]]:
        """Choices for the endpoint's choice fields, from an OPTIONS request.

        NetBox only includes writable-field metadata for actions the token
        may perform, so a read-only token raises ValueError here.
        """
        if self._choices is not None:
            return self._choices
        data = await self.api._request("OPTIONS", self.url)
        actions = data.get("actions", {})
        post = actions.get("POST") or actions.get("PUT")
        if post is None:
            raise ValueError(
                "Unexpected format in the OPTIONS response at {}".format(self.url)
            )
        self._choices = {
            field: meta["choices"] for field, meta in post.items() if "choices" in meta
        }
        return self._choices
