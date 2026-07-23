# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`aiopynetbox` - a fully async NetBox API client, built from scratch with httpx. It is inspired by [pynetbox](https://github.com/netbox-community/pynetbox) (the popular sync client) but is **not a port**: pynetbox's core ergonomics depend on sync-only Python protocols that cannot be awaited, so the API surface here is deliberately different (see Design constraints below).

Package layout: `src/aiopynetbox/`, tests in `tests/`. Managed with `uv`.

## Commands

- `uv sync` - install/update the environment (Python 3.11+)
- `uv run pytest` - run tests (`uv run pytest tests/test_foo.py::test_bar` for one test)
- `uv run ruff check` / `uv run ruff format` - lint and format (line length 88, isort + ASYNC lint rules enabled)

pytest-asyncio runs in `asyncio_mode = "auto"` - async test functions need no decorator.

## Design constraints (why this isn't just "pynetbox with await")

These pynetbox behaviors are impossible or wrong in async and must NOT be replicated:

1. **Lazy attribute fetch** - pynetbox's `Record.__getattr__` transparently GETs the full object when you touch a missing attribute (`device.site.region` may fire HTTP). `__getattr__` cannot be async. Here, fetching full details must be explicit: `await record.full_details()`.
2. **`len()` on result sets** - pynetbox's `RecordSet.__len__` can trigger an HTTP call. `__len__` cannot be async; expose `await recordset.count()` instead.
3. **Sync generators / `next()`** - pynetbox paginates inside a sync generator and `Endpoint.get()` calls `next()` on it. Result sets here are async iterators (`__aiter__`/`__anext__`, consumed with `async for`).
4. **Properties that do I/O** - pynetbox's `Api.version` is a property that makes a request. Properties can't await; use methods (`await nb.version()`).
5. **Threading** - pynetbox bolts on `threading=True` + ThreadPoolExecutor for concurrent page fetches. Not needed: use `asyncio.gather` for page fan-out after the first page reveals the count.

pynetbox ideas worth keeping (they're pure Python, no I/O): app/endpoint attribute traversal (`nb.dcim.devices`), diff-based `save()` (snapshot at parse + `serialize()` diff -> PATCH only changed fields), endpoint-name-to-Record-subclass mapping, and its exception taxonomy (RequestError/ContentError/AllocationError).

## Architecture

All HTTP funnels through `Api._request_response()` ([api.py](src/aiopynetbox/api.py)) - auth headers (v1 `Token`/v2 `nbt_` `Bearer`) and error raising (POST 409 -> `AllocationError`, everything else non-success -> `RequestError`) live there and nowhere else; `Api._request()` adds JSON decoding (`_decode` -> `ContentError`). Detail-path callers (`Endpoint.get(id)`, `full_details()`, `save()`) use `_request_response` directly to capture the `ETag` header: records store it as `_etag` and `save()` sends `If-Match` (NetBox 4.6+ optimistic locking; stale ETag -> 412 `RequestError`). `App.__getattr__` ([app.py](src/aiopynetbox/app.py)) turns any attribute into an `Endpoint` ([endpoint.py](src/aiopynetbox/endpoint.py)), which builds URLs (`_`->`-`) and returns `Record`/`RecordSet` ([response.py](src/aiopynetbox/response.py)). `PluginsApp` (also app.py) routes `nb.plugins.<plugin>` into `/api/plugins/<plugin>/`.

`Endpoint.__init__` resolves its Record subclass from `ENDPOINT_MODELS` in [models.py](src/aiopynetbox/models.py) (`"<app>/<endpoint>"` keys, e.g. `ipam/prefixes` -> `Prefixes` with `available_ips`/`available_prefixes` properties returning a `DetailEndpoint`; `core/data-sources` -> `DataSources` with a `sync` trigger). `register_model()` is the public way to add entries (plugin endpoints use the `"plugins/<plugin>"` app key). `DetailEndpoint.list()` reuses `RecordSet` - its plain-list branch handles non-paginated detail routes. `App.endpoint(name)` bypasses the `_` -> `-` slug conversion for literal-underscore endpoints. Import order matters: api -> app -> endpoint -> models -> response; response only TYPE_CHECKING-imports the others.

Key mechanics in `response.py`:

- `Record` snapshots `serialize()` (deep-copied) after every parse; `updates()` diffs current vs snapshot, with pynetbox's custom_fields merge semantics (only keys present now are compared). `save()` PATCHes only the diff to `record.url`.
- `serialize()` collapses nested Records to `id`, falling back to `value` (choice fields); `RAW_JSON_FIELDS` (custom_fields, local_context_data, config_context) stay plain dicts.
- Records created by endpoint methods are `full=True`; nested ones are brief - missing attrs on brief records raise AttributeError pointing at `full_details()`.
- `RecordSet._iter()` fetches page 1, then `asyncio.gather`-style fans out remaining offsets via tasks bounded by `Api.max_concurrency` (default 4), yielding in offset order; the `finally` cancels pending tasks if iteration is abandoned.
- Cursor mode (`Api(pagination="cursor")`, NetBox 4.6+): `_iter()` sends `start=0` and follows the server's `next` links sequentially (each carries the next cursor, last pk + 1; count comes back null so fan-out is impossible). An explicit offset always uses offset mode ('start'/'offset' are mutually exclusive server-side); an `ordering` filter warns because NetBox ignores it under cursor pagination.
- Bulk ops: `RecordSet.update(**fields)`/`delete()` iterate the set for ids then send one list-body PATCH/DELETE to the endpoint URL; `Endpoint.update(list)`/`delete(list)` are the explicit-id forms.
- `Record.__eq__`/`__hash__` key on `(url, id)`; records lacking either (choice fields) fall back to identity.

The package is fully type-annotated (`from __future__ import annotations` everywhere) and ships `py.typed`. `__version__` comes from package metadata via `importlib.metadata`.

Tests run entirely against `FakeNetbox` in [tests/conftest.py](tests/conftest.py) - an in-memory NetBox behind `httpx.MockTransport` (no network, no mocking library). Extend it when adding endpoints/behaviors.

Not implemented yet (deliberately, add only when needed): napalm helpers (NetBox dropped built-in napalm in 3.5), cable trace helpers, file uploads (multipart), OpenAPI filter validation.

## Conventions

- httpx `AsyncClient` is the only HTTP transport; the client should be usable as an async context manager (`async with aiopynetbox.api(...) as nb:`) so the connection pool is closed deterministically.
- No sync wrapper/facade unless explicitly requested.
- A local reference clone of pynetbox may exist in the session scratchpad, not in this repo - never vendor pynetbox code without noting its Apache 2.0 license.
