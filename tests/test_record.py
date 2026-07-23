import json

import pytest


async def test_nested_record_access(nb):
    device = await nb.dcim.devices.get(1)
    assert device.site.name == "Main Campus"
    assert device.status.value == "active"


async def test_missing_attr_on_brief_record_hints_full_details(nb):
    device = await nb.dcim.devices.get(1)
    with pytest.raises(AttributeError, match="full_details"):
        device.site.time_zone


async def test_full_details_loads_missing_fields(nb):
    device = await nb.dcim.devices.get(1)
    assert await device.site.full_details() is True
    assert device.site.time_zone == "America/Phoenix"


async def test_missing_attr_on_full_record_plain_error(nb):
    device = await nb.dcim.devices.get(1)
    with pytest.raises(AttributeError, match="has no attribute"):
        device.not_a_field


async def test_save_sends_only_changed_fields(nb, fake):
    device = await nb.dcim.devices.get(1)
    device.serial = "NEW-SERIAL"
    assert await device.save() is True
    patch = [r for r in fake.requests if r.method == "PATCH"]
    assert len(patch) == 1
    assert json.loads(patch[0].content) == {"serial": "NEW-SERIAL"}
    assert fake.devices[1]["serial"] == "NEW-SERIAL"


async def test_save_without_changes_sends_nothing(nb, fake):
    device = await nb.dcim.devices.get(1)
    assert await device.save() is False
    assert not [r for r in fake.requests if r.method == "PATCH"]


async def test_save_fk_by_id(nb, fake):
    device = await nb.dcim.devices.get(1)
    device.site = 2
    await device.save()
    patch = [r for r in fake.requests if r.method == "PATCH"]
    assert json.loads(patch[0].content) == {"site": 2}


async def test_custom_fields_subset_change(nb, fake):
    device = await nb.dcim.devices.get(1)
    device.custom_fields["owner"] = "cody"
    await device.save()
    patch = [r for r in fake.requests if r.method == "PATCH"]
    body = json.loads(patch[0].content)
    assert body == {"custom_fields": {"owner": "cody", "billing_code": "NET-1"}}


async def test_update_dict(nb, fake):
    device = await nb.dcim.devices.get(1)
    assert await device.update({"serial": "U1", "name": "sw-1-new"}) is True
    assert fake.devices[1]["serial"] == "U1"
    assert fake.devices[1]["name"] == "sw-1-new"


async def test_delete(nb, fake):
    device = await nb.dcim.devices.get(1)
    assert await device.delete() is True
    assert 1 not in fake.devices


async def test_serialize_collapses_nested(nb):
    device = await nb.dcim.devices.get(1)
    data = device.serialize()
    assert data["site"] == 1
    assert data["status"] == "active"
    assert data["custom_fields"] == {"owner": None, "billing_code": "NET-1"}


async def test_dict_cast(nb):
    device = await nb.dcim.devices.get(1)
    data = dict(device)
    assert data["name"] == "sw-1"
    assert data["site"]["slug"] == "main-campus"
    assert device["serial"] == "ABC123"


async def test_str_uses_name(nb):
    device = await nb.dcim.devices.get(1)
    assert str(device) == "sw-1"
    assert str(device.status) == "Active"


async def test_records_equal_when_same_object(nb):
    a = await nb.dcim.devices.get(1)
    b = await nb.dcim.devices.get(1)
    assert a == b
    assert len({a, b}) == 1


async def test_records_unequal_when_different_objects(nb):
    a = await nb.dcim.devices.get(1)
    b = await nb.dcim.devices.get(2)
    assert a != b
    assert len({a, b}) == 2


async def test_brief_nested_record_equals_full_record(nb):
    device = await nb.dcim.devices.get(1)
    site = await nb.dcim.sites.get(1)
    assert device.site == site


async def test_records_without_id_compare_by_identity(nb):
    a = await nb.dcim.devices.get(1)
    b = await nb.dcim.devices.get(2)
    assert a.status == a.status
    assert a.status != b.status
