import ast
from pathlib import Path

from conftest import BASE

import aiopynetbox
from aiopynetbox.apps import APP_CLASSES

HINTS = Path(aiopynetbox.__file__).parent / "hints.pyi"


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


def test_every_annotation_has_a_hint_class():
    hint_classes = {
        node.name
        for node in ast.parse(HINTS.read_text()).body
        if isinstance(node, ast.ClassDef)
    }
    for cls in APP_CLASSES.values():
        for annotation in cls.__annotations__.values():
            assert annotation.startswith("hints.")
            assert annotation.removeprefix("hints.") in hint_classes


def test_hints_carry_known_params_and_model_returns():
    text = HINTS.read_text()
    assert "class DcimDevicesFilters(TypedDict, total=False):" in text
    assert "class DcimDevicesEndpoint(Endpoint):" in text
    # model subclasses flow through hint return types
    assert "Prefixes | None" in text


def test_hint_keys_exclude_lookups_and_custom_fields():
    for node in ast.parse(HINTS.read_text()).body:
        if not isinstance(node, ast.ClassDef):
            continue
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                key = stmt.target.id
                assert "__" not in key
                assert not key.startswith("cf_")
