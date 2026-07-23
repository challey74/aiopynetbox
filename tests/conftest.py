import json
import re

import httpx
import pytest

import apynetbox

BASE = "http://netbox.test"


def make_device(i, name, serial="", site_id=1):
    return {
        "id": i,
        "url": f"{BASE}/api/dcim/devices/{i}/",
        "display": name,
        "name": name,
        "serial": serial,
        "status": {"value": "active", "label": "Active"},
        "site": {
            "id": site_id,
            "url": f"{BASE}/api/dcim/sites/{site_id}/",
            "display": "Main Campus",
            "name": "Main Campus",
            "slug": "main-campus",
        },
        "custom_fields": {"owner": None, "billing_code": "NET-1"},
        "config_context": {},
        "tags": [],
    }


SITE_FULL = {
    "id": 1,
    "url": f"{BASE}/api/dcim/sites/1/",
    "display": "Main Campus",
    "name": "Main Campus",
    "slug": "main-campus",
    "time_zone": "America/Phoenix",
    "description": "",
}

PREFIX_FULL = {
    "id": 1,
    "url": f"{BASE}/api/ipam/prefixes/1/",
    "display": "10.0.0.0/29",
    "prefix": "10.0.0.0/29",
    "status": {"value": "active", "label": "Active"},
    "custom_fields": {},
}

DEVICE_OPTIONS = {
    "actions": {
        "POST": {
            "name": {"type": "string"},
            "status": {
                "choices": [
                    {"value": "active", "display_name": "Active"},
                    {"value": "offline", "display_name": "Offline"},
                ]
            },
        }
    }
}


class FakeNetbox:
    """Minimal in-memory NetBox served through httpx.MockTransport."""

    def __init__(self, devices=None, page_size=50):
        self.devices = {d["id"]: d for d in (devices or [])}
        self.sites = {1: SITE_FULL}
        self.page_size = page_size
        self.requests = []
        self.next_id = max(self.devices, default=0) + 1

    def handler(self, request):
        self.requests.append(request)
        path = request.url.path
        params = request.url.params

        if path == "/api/" and request.method == "GET":
            return httpx.Response(200, json={}, headers={"API-Version": "4.5"})
        if path == "/api/status/":
            return httpx.Response(200, json={"netbox-version": "4.5.0"})
        if path == "/api/plugins/installed-plugins/":
            return httpx.Response(200, json=[{"name": "test_plugin", "version": "1.0"}])

        if path == "/api/ipam/prefixes/1/" and request.method == "GET":
            return httpx.Response(200, json=PREFIX_FULL)
        if path == "/api/ipam/prefixes/1/available-ips/":
            if request.method == "GET":
                return httpx.Response(
                    200,
                    json=[
                        {"family": 4, "address": f"10.0.0.{i}/29", "vrf": None}
                        for i in (1, 2, 3)
                    ],
                )
            body = json.loads(request.content)
            created = []
            for n, item in enumerate(body if isinstance(body, list) else [body], 1):
                ip = {
                    "id": n,
                    "url": f"{BASE}/api/ipam/ip-addresses/{n}/",
                    "address": f"10.0.0.{n}/29",
                }
                ip.update(item)
                created.append(ip)
            payload = created if isinstance(body, list) else created[0]
            return httpx.Response(201, json=payload)

        if m := re.fullmatch(r"/api/dcim/sites/(\d+)/", path):
            site = self.sites.get(int(m.group(1)))
            if not site:
                return httpx.Response(404, json={"detail": "Not found."})
            return httpx.Response(200, json=site)

        if m := re.fullmatch(r"/api/dcim/devices/(\d+)/", path):
            device = self.devices.get(int(m.group(1)))
            if not device:
                return httpx.Response(404, json={"detail": "Not found."})
            if request.method == "PATCH":
                device.update(json.loads(request.content))
                return httpx.Response(200, json=device)
            if request.method == "DELETE":
                del self.devices[device["id"]]
                return httpx.Response(204)
            return httpx.Response(200, json=device)

        if path == "/api/dcim/devices/":
            if request.method == "OPTIONS":
                return httpx.Response(200, json=DEVICE_OPTIONS)
            if request.method == "PATCH":
                body = json.loads(request.content)
                updated = []
                for item in body:
                    device = self.devices[item["id"]]
                    device.update({k: v for k, v in item.items() if k != "id"})
                    updated.append(device)
                return httpx.Response(200, json=updated)
            if request.method == "DELETE":
                body = json.loads(request.content)
                for item in body:
                    del self.devices[item["id"]]
                return httpx.Response(204)
            if request.method == "POST":
                body = json.loads(request.content)
                created = []
                for item in body if isinstance(body, list) else [body]:
                    device = make_device(self.next_id, item.get("name", ""))
                    device.update(item)
                    self.devices[self.next_id] = device
                    self.next_id += 1
                    created.append(device)
                payload = created if isinstance(body, list) else created[0]
                return httpx.Response(201, json=payload)
            matches = [
                d
                for d in self.devices.values()
                if all(
                    str(d.get(k)) == v
                    for k, v in params.items()
                    if k not in ("limit", "offset")
                )
            ]
            limit = int(params.get("limit", 0)) or self.page_size
            offset = int(params.get("offset", 0))
            page = matches[offset : offset + limit]
            has_next = offset + limit < len(matches)
            return httpx.Response(
                200,
                json={
                    "count": len(matches),
                    "next": f"{BASE}{path}?limit={limit}&offset={offset + limit}"
                    if has_next
                    else None,
                    "previous": None,
                    "results": page,
                },
            )

        return httpx.Response(500, json={"error": f"unhandled path {path}"})


@pytest.fixture
def fake():
    return FakeNetbox(
        devices=[
            make_device(1, "sw-1", serial="ABC123"),
            make_device(2, "sw-2"),
            make_device(3, "sw-3"),
            make_device(4, "sw-4"),
            make_device(5, "sw-5"),
        ]
    )


def make_api(fake, token="abc123"):
    client = httpx.AsyncClient(transport=httpx.MockTransport(fake.handler))
    return apynetbox.api(BASE, token=token, client=client)


@pytest.fixture
async def nb(fake):
    async with make_api(fake) as nb:
        yield nb
