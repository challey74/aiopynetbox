"""Per-endpoint Record subclasses and NetBox detail (sub-)endpoints.

Endpoints listed in ENDPOINT_MODELS return these Record subclasses so
NetBox-specific helpers (e.g. available-ips allocation) hang off the record.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apynetbox.response import Record, RecordSet

if TYPE_CHECKING:
    from apynetbox.api import Api


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

        Pass a dict for one object, a list of dicts for several; NetBox
        assigns the actual values (address, prefix, vid...).
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


ENDPOINT_MODELS: dict[str, type[Record]] = {
    "ipam/prefixes": Prefixes,
    "ipam/ip-ranges": IpRanges,
    "ipam/vlan-groups": VlanGroups,
}
