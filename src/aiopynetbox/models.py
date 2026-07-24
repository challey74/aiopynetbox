"""Per-endpoint Record subclasses and NetBox detail (sub-)endpoints.

Endpoints listed in ENDPOINT_MODELS return these Record subclasses so
NetBox-specific helpers (e.g. available-ips allocation) hang off the record.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aiopynetbox.response import Record, RecordSet

if TYPE_CHECKING:
    from aiopynetbox.api import Api


class DetailEndpoint:
    """A sub-endpoint nested under a record's detail URL,
    e.g. /api/ipam/prefixes/<id>/available-ips/."""

    def __init__(self, record: Record, name: str) -> None:
        self.api: Api = record._api
        self.url = "{}/{}/".format(str(record.url).rstrip("/"), name)
        self.record_class: type[Record] = Record

    def list(self, **params: Any) -> RecordSet:
        """Lazy RecordSet over the detail endpoint."""
        return RecordSet(self, params)

    async def create(
        self, data: dict[str, Any] | list[dict[str, Any]] | None = None
    ) -> Record | list[Record]:
        """POST to the detail endpoint (e.g. allocate next available IPs).

        Args:
            data: A dict for one object, a list of dicts for several,
                or omitted to take the next single allocation. NetBox
                assigns the actual values (address, prefix, vid...).

        Returns:
            A Record, or a list of Records for list input.

        Raises:
            AllocationError: If the request cannot be fulfilled
                (e.g. not enough free IPs in the prefix).
        """
        resp = await self.api._request("POST", self.url, json=data or {})
        if isinstance(resp, list):
            return [Record(i, self.api, full=True) for i in resp]
        return Record(resp, self.api, full=True)


class Prefixes(Record):
    """ipam/prefixes record with available-ips/-prefixes allocation."""

    @property
    def available_ips(self) -> DetailEndpoint:
        return DetailEndpoint(self, "available-ips")

    @property
    def available_prefixes(self) -> DetailEndpoint:
        return DetailEndpoint(self, "available-prefixes")


class IpRanges(Record):
    """ipam/ip-ranges record with available-ips allocation."""

    @property
    def available_ips(self) -> DetailEndpoint:
        return DetailEndpoint(self, "available-ips")


class VlanGroups(Record):
    """ipam/vlan-groups record with available-vlans allocation."""

    @property
    def available_vlans(self) -> DetailEndpoint:
        return DetailEndpoint(self, "available-vlans")


class DataSources(Record):
    """core/data-sources record with a sync trigger."""

    @property
    def sync(self) -> DetailEndpoint:
        """POST with `await data_source.sync.create()` to trigger a sync."""
        return DetailEndpoint(self, "sync")


ENDPOINT_MODELS: dict[str, type[Record]] = {
    "core/data-sources": DataSources,
    "ipam/prefixes": Prefixes,
    "ipam/ip-ranges": IpRanges,
    "ipam/vlan-groups": VlanGroups,
}


def register_model(app: str, endpoint: str, record_class: type[Record]) -> None:
    """Register a Record subclass for an endpoint, e.g. a plugin's:

        register_model("plugins/bgp", "sessions", BgpSession)

    The endpoint name is converted like attribute access (`_` to `-`).
    """
    ENDPOINT_MODELS["{}/{}".format(app, endpoint.replace("_", "-"))] = record_class
