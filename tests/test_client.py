import httpx
import pytest
from conftest import BASE, FakeNetbox, make_api, make_device

import aiopynetbox


async def test_get_by_id(nb):
    device = await nb.dcim.devices.get(1)
    assert device.name == "sw-1"
    assert device.serial == "ABC123"
    assert device.id == 1


async def test_get_by_id_missing_returns_none(nb):
    assert await nb.dcim.devices.get(999) is None


async def test_get_by_kwargs(nb):
    device = await nb.dcim.devices.get(name="sw-2")
    assert device.id == 2


async def test_get_by_kwargs_no_match_returns_none(nb):
    assert await nb.dcim.devices.get(name="nope") is None


async def test_get_multiple_matches_raises(nb, fake):
    for d in fake.devices.values():
        d["serial"] = "DUP"
    with pytest.raises(ValueError, match="more than one result"):
        await nb.dcim.devices.get(serial="DUP")


async def test_filter_requires_kwargs(nb):
    with pytest.raises(ValueError, match="filter must be passed kwargs"):
        nb.dcim.devices.filter()


async def test_filter_matches(nb):
    names = [d.name async for d in nb.dcim.devices.filter(name="sw-1")]
    assert names == ["sw-1"]


async def test_all_paginates_in_order():
    fake = FakeNetbox(
        devices=[make_device(i, f"sw-{i}") for i in range(1, 6)], page_size=2
    )
    async with make_api(fake) as nb:
        names = [d.name async for d in nb.dcim.devices.all()]
    assert names == [f"sw-{i}" for i in range(1, 6)]
    offsets = [
        r.url.params.get("offset")
        for r in fake.requests
        if r.url.path == "/api/dcim/devices/"
    ]
    assert offsets == [None, "2", "4"]


async def test_all_with_offset_fetches_single_page(nb, fake):
    names = [d.name async for d in nb.dcim.devices.all(limit=2, offset=2)]
    assert names == ["sw-3", "sw-4"]
    assert len([r for r in fake.requests if r.url.path == "/api/dcim/devices/"]) == 1


async def test_offset_requires_limit(nb):
    with pytest.raises(ValueError, match="offset requires"):
        nb.dcim.devices.all(offset=2)


async def test_count(nb, fake):
    assert await nb.dcim.devices.count() == 5
    assert fake.requests[-1].url.params["limit"] == "1"


async def test_recordset_count(nb):
    assert await nb.dcim.devices.filter(name="sw-1").count() == 1


async def test_create_single(nb, fake):
    device = await nb.dcim.devices.create(name="sw-new", serial="XYZ")
    assert device.id == 6
    assert device.serial == "XYZ"
    assert 6 in fake.devices


async def test_create_bulk(nb):
    created = await nb.dcim.devices.create([{"name": "bulk-1"}, {"name": "bulk-2"}])
    assert [d.name for d in created] == ["bulk-1", "bulk-2"]


async def test_v1_token_header(nb, fake):
    await nb.dcim.devices.get(1)
    assert fake.requests[-1].headers["Authorization"] == "Token abc123"


async def test_v2_token_uses_bearer(fake):
    async with make_api(fake, token="nbt_abc.secret123") as nb:
        await nb.dcim.devices.get(1)
    assert fake.requests[-1].headers["Authorization"] == "Bearer nbt_abc.secret123"


async def test_version(nb):
    assert await nb.version() == "4.5"


async def test_status(nb):
    assert (await nb.status())["netbox-version"] == "4.5.0"


async def test_request_error_on_500(nb):
    with pytest.raises(aiopynetbox.RequestError, match="code 500"):
        await nb.dcim.nonexistent.count()


async def test_content_error_on_non_json():
    def handler(request):
        return httpx.Response(200, text="<html>not netbox</html>")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    async with aiopynetbox.api(BASE, client=client) as nb:
        with pytest.raises(aiopynetbox.ContentError):
            await nb.dcim.devices.get(1)


async def test_context_manager_closes_owned_client():
    nb = aiopynetbox.api(BASE)
    async with nb:
        pass
    assert nb._client.is_closed


async def test_context_manager_leaves_supplied_client_open(fake):
    client = httpx.AsyncClient(transport=httpx.MockTransport(fake.handler))
    async with aiopynetbox.api(BASE, token="abc123", client=client) as nb:
        await nb.dcim.devices.get(1)
    assert not client.is_closed
    await client.aclose()


async def test_endpoint_url_dashes(nb):
    assert nb.ipam.ip_addresses.url == f"{BASE}/api/ipam/ip-addresses/"


async def test_recordset_bulk_update(nb, fake):
    updated = await nb.dcim.devices.filter(name="sw-1").update(serial="BULK")
    assert [d.serial for d in updated] == ["BULK"]
    assert fake.devices[1]["serial"] == "BULK"


async def test_recordset_bulk_update_empty_sends_nothing(nb, fake):
    assert await nb.dcim.devices.filter(name="nope").update(serial="X") == []
    assert not [r for r in fake.requests if r.method == "PATCH"]


async def test_recordset_bulk_delete(nb, fake):
    assert await nb.dcim.devices.filter(name="sw-5").delete() is True
    assert 5 not in fake.devices


async def test_recordset_bulk_delete_empty_returns_false(nb, fake):
    assert await nb.dcim.devices.filter(name="nope").delete() is False
    assert not [r for r in fake.requests if r.method == "DELETE"]


async def test_endpoint_bulk_update(nb, fake):
    updated = await nb.dcim.devices.update(
        [{"id": 1, "serial": "E1"}, {"id": 2, "serial": "E2"}]
    )
    assert [d.serial for d in updated] == ["E1", "E2"]
    assert fake.devices[2]["serial"] == "E2"


async def test_endpoint_bulk_delete_ids_and_records(nb, fake):
    device = await nb.dcim.devices.get(4)
    assert await nb.dcim.devices.delete([device, 5]) is True
    assert 4 not in fake.devices
    assert 5 not in fake.devices


async def test_choices(nb):
    choices = await nb.dcim.devices.choices()
    assert choices["status"][0]["value"] == "active"
    assert "name" not in choices


async def test_choices_cached_on_endpoint(nb, fake):
    endpoint = nb.dcim.devices
    await endpoint.choices()
    await endpoint.choices()
    assert len([r for r in fake.requests if r.method == "OPTIONS"]) == 1


async def test_plugins_endpoint_url(nb):
    assert (
        nb.plugins.test_plugin.widgets.url == f"{BASE}/api/plugins/test-plugin/widgets/"
    )


async def test_installed_plugins(nb):
    plugins = await nb.plugins.installed_plugins()
    assert plugins[0]["name"] == "test_plugin"


def test_version_attribute():
    assert aiopynetbox.__version__


def test_invalid_pagination_raises():
    with pytest.raises(ValueError, match="pagination"):
        aiopynetbox.api(BASE, pagination="nope")


def test_backoff_honors_retry_after_with_cap():
    nb = aiopynetbox.api(BASE)
    assert nb._backoff(0, "2") == 2.0
    assert nb._backoff(0, "3600") == 60.0


def test_backoff_exponential_with_jitter():
    nb = aiopynetbox.api(BASE)
    # attempt 0: 0.5s base, jittered to 50-100%
    assert 0.25 <= nb._backoff(0, None) <= 0.5
    # capped at 8s base regardless of attempt
    assert nb._backoff(10, None) <= 8.0
    # non-numeric Retry-After (HTTP-date) falls back to backoff
    assert nb._backoff(0, "Wed, 21 Oct 2026 07:28:00 GMT") <= 0.5


async def test_cursor_pagination_follows_next_links():
    fake = FakeNetbox(
        devices=[make_device(i, f"sw-{i}") for i in range(1, 6)], page_size=2
    )
    async with make_api(fake, pagination="cursor") as nb:
        names = [d.name async for d in nb.dcim.devices.all()]
    assert names == [f"sw-{i}" for i in range(1, 6)]
    list_requests = [r for r in fake.requests if r.url.path == "/api/dcim/devices/"]
    starts = [r.url.params.get("start") for r in list_requests]
    assert starts == ["0", "3", "5"]
    assert all("offset" not in r.url.params for r in list_requests)


async def test_cursor_with_explicit_offset_uses_offset(fake):
    async with make_api(fake, pagination="cursor") as nb:
        names = [d.name async for d in nb.dcim.devices.all(limit=2, offset=2)]
    assert names == ["sw-3", "sw-4"]
    request = fake.requests[-1]
    assert request.url.params["offset"] == "2"
    assert "start" not in request.url.params


async def test_cursor_ordering_filter_warns(fake):
    async with make_api(fake, pagination="cursor") as nb:
        with pytest.warns(UserWarning, match="ordering has no effect"):
            [d async for d in nb.dcim.devices.filter(name="sw-1", ordering="name")]


async def test_cursor_count_still_works(fake):
    async with make_api(fake, pagination="cursor") as nb:
        assert await nb.dcim.devices.count() == 5
