# aiopynetbox

[![CI](https://github.com/challey74/aiopynetbox/actions/workflows/ci.yml/badge.svg)](https://github.com/challey74/aiopynetbox/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/aiopynetbox)](https://pypi.org/project/aiopynetbox/)
[![Python versions](https://img.shields.io/pypi/pyversions/aiopynetbox)](https://pypi.org/project/aiopynetbox/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

Fully async NetBox API client for Python, built on [httpx](https://www.python-httpx.org/).

Inspired by [pynetbox](https://github.com/netbox-community/pynetbox), redesigned
for asyncio. This is not a port: pynetbox's core ergonomics (lazy attribute
fetches, `len()` on result sets, sync generators) depend on Python protocols
that cannot be awaited, so the API surface here is deliberately different.
**All I/O is explicit and awaitable, and nothing does network I/O behind your
back.**

## Requirements

- Python 3.11+
- NetBox 3.x / 4.x (v1 and v2 `nbt_` API tokens both supported)

## Installation

```sh
uv add aiopynetbox   # or: pip install aiopynetbox
```

## Quick start

```python
import asyncio
import aiopynetbox


async def main():
    async with aiopynetbox.api("https://netbox.example.com", token="...") as nb:
        # single object
        device = await nb.dcim.devices.get(name="sw-1")
        print(device.name, device.status, device.site)

        # filtered query, pages are fetched concurrently
        async for iface in nb.dcim.interfaces.filter(device_id=device.id):
            print(iface.name)

        # diff-based save: only changed fields are PATCHed
        device.serial = "ABC123"
        await device.save()


asyncio.run(main())
```

## Coming from pynetbox

The traversal (`nb.dcim.devices`), diff-based `save()`, and exception taxonomy
all carry over. What changes is that implicit I/O becomes explicit:

| pynetbox (sync)                    | aiopynetbox (async)                       |
| ---------------------------------- | --------------------------------------- |
| `nb.dcim.devices.get(name="x")`    | `await nb.dcim.devices.get(name="x")`   |
| `for d in nb.dcim.devices.all()`   | `async for d in nb.dcim.devices.all()`  |
| `len(nb.dcim.devices.all())`       | `await nb.dcim.devices.count()`         |
| `device.site.region` (lazy fetch)  | `await device.site.full_details()` then `device.site.region` |
| `nb.version` (property does I/O)   | `await nb.version()`                    |
| `threading=True`                   | built in: concurrent page fan-out, bounded by `max_concurrency` |

Nested records come back *brief* (as NetBox sends them). Touching a field
that isn't loaded raises `AttributeError` telling you to
`await record.full_details()`. It never fires a hidden HTTP request.

## Features

- **Explicit async everywhere**: `httpx.AsyncClient` under the hood, used as
  an async context manager so the connection pool closes deterministically.
- **Concurrent pagination**: after the first page reveals the count, the
  remaining pages are fetched in parallel (bounded by `max_concurrency`,
  default 4) and yielded in order.
- **Cursor pagination (NetBox 4.6+)**: pass `pagination="cursor"` to the
  client to page with the `start` cursor instead, constant-time per page
  on very large tables (pages are sequential in this mode, since each
  cursor comes from the previous response).
- **Diff-based writes**: `save()` PATCHes only what you changed, with
  NetBox's custom_fields merge semantics handled correctly.
- **Bulk operations**:
  `await nb.dcim.devices.filter(status="offline").update(comments="audit")`,
  `await recordset.delete()`, and list forms on the endpoint
  (`endpoint.update([...])` / `endpoint.delete([...])`).
- **IPAM allocation**: `await prefix.available_ips.create()` /
  `.list()`, plus `available_prefixes` and `available_vlans`.
- **Plugins**: `nb.plugins.<plugin>.<endpoint>` and
  `await nb.plugins.installed_plugins()`.
- **Choices**: `await nb.dcim.devices.choices()` from OPTIONS metadata.
- **Retries with backoff**: 429 responses are retried automatically for
  any method (honoring `Retry-After`); transient 502/503/504 and
  connection failures are retried for GETs only, since an ambiguous
  write may already have been processed. Exponential backoff with
  jitter; tune with `retries=`, disable with `retries=0`.
- **Optimistic locking (NetBox 4.6+)**: records fetched from a detail
  endpoint remember their `ETag`; `save()` sends `If-Match`, so a
  concurrent modification fails with a 412 error instead of being
  silently overwritten. Repeat `full_details()` calls revalidate with
  `If-None-Match`, so unchanged objects aren't re-downloaded or
  re-parsed.
- **Data source sync**: `await data_source.sync.create()`.
- **Custom models**: `aiopynetbox.register_model("plugins/bgp", "sessions",
  BgpSession)` maps plugin endpoints to your own Record subclasses;
  `app.endpoint("literal_name")` reaches endpoint slugs that contain
  real underscores.
- **Typed**: full type hints and a `py.typed` marker, plus generated
  hints so IDEs autocomplete endpoint names (`nb.dcim.devices`) and
  per-endpoint kwargs (`filter(name=...)`, `create(device_type=...)`).
  Hints never restrict anything at runtime: unknown endpoints, lookup
  expressions, and custom-field filters keep working.

## API tour

```python
async with aiopynetbox.api(url, token=token) as nb:
    # read
    device = await nb.dcim.devices.get(123)  # by id (None if missing)
    device = await nb.dcim.devices.get(name="sw-1")  # by filter (ValueError if >1)
    total = await nb.dcim.devices.count(site="main")
    async for d in nb.dcim.devices.filter(status="active", tag=["prod", "core"]):
        ...
    async for d in nb.dcim.devices.all(limit=100, offset=200):  # single page
        ...

    # write
    new = await nb.dcim.devices.create(name="sw-9", device_type=12, site=1, role=3)
    device.serial = "XYZ"
    await device.save()  # PATCH {"serial": "XYZ"}
    await device.update({"serial": "XYZ", "comments": "..."})
    await device.delete()

    # bulk
    await nb.dcim.devices.filter(site="old").update(status="decommissioning")
    await nb.dcim.devices.filter(status="decommissioning").delete()

    # ipam allocation
    prefix = await nb.ipam.prefixes.get(prefix="10.0.0.0/24")
    ip = await prefix.available_ips.create()  # next free IP
    ips = await prefix.available_ips.create([{}, {}])  # next two

    # instance info
    print(await nb.version())  # "4.5"
    print(await nb.status())
```

### Long-lived apps (FastAPI, services)

Create the client once and share it; the async context manager is
one-shot, so enter it for the app's lifetime, not per request:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with aiopynetbox.api(url, token=token) as nb:
        app.state.nb = nb
        yield  # handlers use `await app.state.nb...`; pool closes on shutdown
```

One shared instance is safe under concurrent requests. See
[examples/fastapi_app.py](examples/fastapi_app.py) for a runnable app.

### Custom httpx client

Pass your own `httpx.AsyncClient` for custom SSL, proxies, event hooks, or
`MockTransport` in tests:

```python
client = httpx.AsyncClient(verify="/path/to/ca.pem", timeout=60)
async with aiopynetbox.api(url, token=token, client=client) as nb:
    ...
```

Per httpx convention, a client you pass in is yours to close: `aclose()`
and the context manager only close clients the Api created itself, so
one client can safely back several Api instances.

Response caching is deliberately not built in: NetBox is a source of
truth, and the library can't know your staleness tolerance. If you want
HTTP caching, pass a client using [hishel](https://hishel.com/)'s
`AsyncCacheTransport` and set the policy yourself.

## Development

Managed with [uv](https://docs.astral.sh/uv/):

```sh
uv sync              # install environment
uv run pytest        # tests (in-memory fake NetBox, no network)
uv run ruff check    # lint
uv run ruff format   # format
```

## License

Apache 2.0, see [LICENSE](LICENSE).
