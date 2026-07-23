import json

import pytest
from conftest import BASE

import aiopynetbox
from aiopynetbox.models import ENDPOINT_MODELS, DataSources


async def test_openapi_cached(nb, fake):
    spec = await nb.openapi()
    assert spec["openapi"] == "3.0.3"
    await nb.openapi()
    assert len([r for r in fake.requests if r.url.path == "/api/schema/"]) == 1


async def test_create_token_v2_adopts_bearer_value(nb, fake):
    token = await nb.create_token("admin", "hunter2")
    assert token.key == "shortkey"
    assert nb.token == "nbt_shortkey.plaintext"
    await nb.dcim.devices.get(1)
    assert fake.requests[-1].headers["Authorization"] == "Bearer nbt_shortkey.plaintext"


async def test_create_token_v1_plain_value(nb):
    await nb.create_token("v1user", "hunter2")
    assert nb.token == "plainv1token"


async def test_allocation_error_on_conflict(nb):
    prefix = await nb.ipam.prefixes.get(1)
    with pytest.raises(aiopynetbox.AllocationError, match="could not be fulfilled"):
        await prefix.available_ips.create([{}, {}, {}, {}])


async def test_data_source_sync(nb, fake):
    source = await nb.core.data_sources.get(1)
    assert isinstance(source, DataSources)
    result = await source.sync.create()
    assert result.status.value == "syncing"
    assert fake.requests[-1].url.path == "/api/core/data-sources/1/sync/"
    assert fake.requests[-1].method == "POST"


async def test_literal_endpoint_keeps_underscores(nb):
    endpoint = nb.plugins.test_plugin.endpoint("under_scores")
    assert endpoint.url == f"{BASE}/api/plugins/test-plugin/under_scores/"


async def test_register_model(nb):
    class Widget(aiopynetbox.Record):
        pass

    aiopynetbox.register_model("plugins/test-plugin", "widgets", Widget)
    try:
        assert nb.plugins.test_plugin.widgets.record_class is Widget
    finally:
        del ENDPOINT_MODELS["plugins/test-plugin/widgets"]


async def test_etag_stored_and_sent_as_if_match(nb, fake):
    device = await nb.dcim.devices.get(1)
    assert device._etag == '"etag-1"'
    device.serial = "ETAG-1"
    await device.save()
    patch = [r for r in fake.requests if r.method == "PATCH"][-1]
    assert patch.headers["If-Match"] == '"etag-1"'
    assert device._etag == '"etag-1-v2"'


async def test_stale_etag_fails_with_412(nb):
    device = await nb.dcim.devices.get(1)
    device._etag = '"stale"'
    device.serial = "CLOBBER"
    with pytest.raises(aiopynetbox.RequestError) as excinfo:
        await device.save()
    assert excinfo.value.status_code == 412


async def test_list_records_save_without_if_match(nb, fake):
    device = await anext(aiter(nb.dcim.devices.filter(name="sw-1")))
    device.serial = "NO-ETAG"
    await device.save()
    patch = [r for r in fake.requests if r.method == "PATCH"][-1]
    assert "If-Match" not in patch.headers


async def test_full_details_captures_etag(nb):
    device = await anext(aiter(nb.dcim.devices.filter(name="sw-1")))
    assert device._etag is None
    await device.full_details()
    assert device._etag == '"etag-1"'


async def test_add_tags_write_only_field(nb, fake):
    device = await nb.dcim.devices.get(1)
    device.add_tags = ["prod"]
    await device.save()
    patch = [r for r in fake.requests if r.method == "PATCH"][-1]
    assert json.loads(patch.content) == {"add_tags": ["prod"]}
