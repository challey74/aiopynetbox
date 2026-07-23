# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Cursor-based pagination for NetBox 4.6+: `apynetbox.api(..., pagination="cursor")`
  pages list views with the `start` cursor (constant-time per page,
  sequential). Offset mode with concurrent page fan-out remains the default.

## [0.1.0] - 2026-07-23

Initial release.

### Added

- Fully async `Api` client on httpx, usable as an async context manager;
  `follow_redirects` enabled by default.
- NetBox v1 (`Token`) and v2 (`nbt_` / `Bearer`) token support.
- App/endpoint attribute traversal (`nb.dcim.devices`), including
  `nb.plugins.<plugin>.<endpoint>` and `nb.plugins.installed_plugins()`.
- `get()` / `filter()` / `all()` / `count()` / `create()` on endpoints;
  result sets are lazy async iterators with concurrent page fetching
  bounded by `max_concurrency`.
- Diff-based `Record.save()` (PATCHes only changed fields, with
  custom_fields merge semantics), `update()`, `delete()`, and explicit
  `full_details()` for brief nested records.
- Bulk operations: `RecordSet.update(**fields)` / `RecordSet.delete()`
  and `Endpoint.update(list)` / `Endpoint.delete(list)`.
- `Endpoint.choices()` from OPTIONS metadata.
- IPAM allocation helpers: `prefix.available_ips` / `available_prefixes`,
  `ip_range.available_ips`, `vlan_group.available_vlans`.
- Record equality/hashing by NetBox identity (detail url + id).
- Full type hints and a `py.typed` marker.
