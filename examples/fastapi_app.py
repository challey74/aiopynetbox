"""Minimal FastAPI app sharing one aiopynetbox client as app state.

The Api enters its async context once for the app's lifetime: the
connection pool is shared by every request and closes cleanly on
shutdown. Handlers use it bare (`await app.state.nb...`). Don't
`async with app.state.nb` per request - the context manager is
one-shot and exiting it closes the pool for good.

Run with:

    NETBOX_URL=https://netbox.example.com NETBOX_TOKEN=... \
    uv run --with fastapi --with uvicorn \
        uvicorn examples.fastapi_app:app --reload
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request

import aiopynetbox


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with aiopynetbox.api(
        os.environ["NETBOX_URL"], token=os.environ["NETBOX_TOKEN"]
    ) as nb:
        app.state.nb = nb
        yield


app = FastAPI(lifespan=lifespan)


@app.get("/devices/{name}")
async def get_device(name: str, request: Request):
    device = await request.app.state.nb.dcim.devices.get(name=name)
    if device is None:
        raise HTTPException(404, f"device {name!r} not found")
    return dict(device)


@app.get("/sites/{slug}/devices")
async def site_devices(slug: str, request: Request):
    nb = request.app.state.nb
    return [
        {"name": d.name, "status": d.status.value}
        async for d in nb.dcim.devices.filter(site=slug)
    ]
