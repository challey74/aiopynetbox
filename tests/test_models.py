from apynetbox.models import Prefixes


async def test_prefixes_endpoint_returns_model_class(nb):
    prefix = await nb.ipam.prefixes.get(1)
    assert isinstance(prefix, Prefixes)


async def test_available_ips_list(nb):
    prefix = await nb.ipam.prefixes.get(1)
    ips = [ip.address async for ip in prefix.available_ips.list()]
    assert ips == ["10.0.0.1/29", "10.0.0.2/29", "10.0.0.3/29"]


async def test_available_ips_count(nb):
    prefix = await nb.ipam.prefixes.get(1)
    assert await prefix.available_ips.list().count() == 3


async def test_available_ips_create_single(nb):
    prefix = await nb.ipam.prefixes.get(1)
    ip = await prefix.available_ips.create()
    assert ip.id == 1
    assert ip.address == "10.0.0.1/29"


async def test_available_ips_create_bulk(nb):
    prefix = await nb.ipam.prefixes.get(1)
    ips = await prefix.available_ips.create([{}, {}])
    assert [ip.id for ip in ips] == [1, 2]
