# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-24

Initial release.

### Added

- Fully async `Api` client on httpx, usable as an async context manager;
  `follow_redirects` enabled by default. A client passed via `client=`
  stays open on close (httpx convention); the Api closes only clients
  it creates.
- NetBox v1 (`Token`) and v2 (`nbt_` / `Bearer`) token support, plus
  `Api.create_token()` provisioning that adopts the new token.
- App/endpoint attribute traversal (`nb.dcim.devices`), including
  `nb.plugins.<plugin>.<endpoint>`, `nb.plugins.installed_plugins()`,
  and `App.endpoint(name)` for slugs with literal underscores.
- `get()` / `filter()` / `all()` / `count()` / `create()` on endpoints;
  result sets are lazy async iterators with concurrent page fetching
  bounded by `max_concurrency`.
- Cursor-based pagination for NetBox 4.6+ via
  `aiopynetbox.api(..., pagination="cursor")`: constant-time pages
  using the `start` cursor (sequential). Offset mode with concurrent
  fan-out remains the default.
- Diff-based `Record.save()` (PATCHes only changed fields, with
  custom_fields merge semantics), `update()`, `delete()`, and explicit
  `full_details()` for brief nested records.
- Optimistic locking (NetBox 4.6+): detail fetches store the response
  `ETag`; `save()` sends `If-Match` (412 on concurrent modification)
  and repeat `full_details()` calls revalidate with `If-None-Match`
  (304 skips re-download and re-parsing).
- Automatic retries with exponential backoff and jitter: 429 for any
  method (honoring `Retry-After`), transient 502/503/504 and
  connection failures for GETs only. Configurable via `Api(retries=)`,
  default 3.
- Bulk operations: `RecordSet.update(**fields)` / `RecordSet.delete()`
  and `Endpoint.update(list)` / `Endpoint.delete(list)`.
- `Endpoint.choices()` from OPTIONS metadata and `Api.openapi()` with
  in-memory caching.
- IPAM allocation helpers: `prefix.available_ips` /
  `available_prefixes`, `ip_range.available_ips`,
  `vlan_group.available_vlans`; `AllocationError` raised on 409
  conflicts. `data_source.sync.create()` triggers a data source sync.
- `register_model(app, endpoint, record_class)` to map plugin or
  custom endpoints to Record subclasses.
- Record equality/hashing by NetBox identity (detail url + id).
- Full type hints with a `py.typed` marker, plus generated hints so
  IDEs autocomplete endpoint names and per-endpoint kwargs for
  `filter()` / `get()` / `count()` / `create()`. Hints never restrict
  runtime behavior; they regenerate weekly from the NetBox OpenAPI
  schema.
- A runnable FastAPI example (`examples/fastapi_app.py`) showing the
  app-state / lifespan usage pattern.

[0.1.0]: https://github.com/challey74/aiopynetbox/releases/tag/v0.1.0
