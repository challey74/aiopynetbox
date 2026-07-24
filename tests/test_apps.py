from conftest import BASE

from aiopynetbox.apps import APP_CLASSES


async def test_every_generated_app_is_wired(nb):
    for name, cls in APP_CLASSES.items():
        assert isinstance(getattr(nb, name), cls)


async def test_annotated_endpoints_resolve_through_getattr(nb):
    """Every generated hint must reach a working Endpoint at runtime."""
    for name, cls in APP_CLASSES.items():
        app = getattr(nb, name)
        for attr in cls.__annotations__:
            endpoint = getattr(app, attr)
            slug = attr.replace("_", "-")
            assert endpoint.url == f"{BASE}/api/{name}/{slug}/"


def test_annotations_do_not_shadow_app_attributes():
    for cls in APP_CLASSES.values():
        assert "name" not in cls.__annotations__
        assert "endpoint" not in cls.__annotations__
