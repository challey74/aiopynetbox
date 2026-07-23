import httpx
import pytest
from conftest import make_api

import aiopynetbox


@pytest.fixture(autouse=True)
def instant_backoff(monkeypatch):
    monkeypatch.setattr(
        aiopynetbox.Api, "_backoff", lambda self, attempt, retry_after: 0
    )


async def test_429_retried_until_success(nb, fake):
    fake.fail_next = [429, 429]
    device = await nb.dcim.devices.get(1)
    assert device.name == "sw-1"
    assert len(fake.requests) == 3


async def test_429_retried_for_writes(nb, fake):
    fake.fail_next = [429]
    device = await nb.dcim.devices.create(name="sw-new")
    assert device.name == "sw-new"


async def test_429_exhausted_raises(fake):
    fake.fail_next = [429, 429]
    async with make_api(fake, retries=1) as nb:
        with pytest.raises(aiopynetbox.RequestError) as excinfo:
            await nb.dcim.devices.get(1)
    assert excinfo.value.status_code == 429
    assert len(fake.requests) == 2


async def test_retries_zero_disables(fake):
    fake.fail_next = [429]
    async with make_api(fake, retries=0) as nb:
        with pytest.raises(aiopynetbox.RequestError):
            await nb.dcim.devices.get(1)
    assert len(fake.requests) == 1


async def test_transport_error_retried_for_get(nb, fake):
    fake.fail_next = ["transport"]
    device = await nb.dcim.devices.get(1)
    assert device.name == "sw-1"


async def test_transport_error_not_retried_for_post(nb, fake):
    fake.fail_next = ["transport"]
    with pytest.raises(httpx.ConnectError):
        await nb.dcim.devices.create(name="sw-new")
    assert len(fake.requests) == 1


async def test_503_retried_for_get(nb, fake):
    fake.fail_next = [503]
    assert (await nb.dcim.devices.get(1)).name == "sw-1"


async def test_503_not_retried_for_post(nb, fake):
    fake.fail_next = [503]
    with pytest.raises(aiopynetbox.RequestError) as excinfo:
        await nb.dcim.devices.create(name="sw-new")
    assert excinfo.value.status_code == 503
    assert len(fake.requests) == 1
