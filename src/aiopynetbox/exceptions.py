"""Exception types raised by aiopynetbox."""

from __future__ import annotations

import httpx


class RequestError(Exception):
    """NetBox returned a non-success HTTP response."""

    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        self.status_code = response.status_code
        self.url = str(response.url)
        self.error = response.text
        if response.status_code == 404:
            self.message = f"The requested url: {response.url} could not be found."
        else:
            try:
                detail = response.json()
            except ValueError:
                detail = "(non-JSON response body)"
            self.message = f"The request failed with code {response.status_code} {response.reason_phrase}: {detail}"
        super().__init__(self.message)


class AllocationError(Exception):
    """NetBox returned 409 Conflict for an allocation request
    (e.g. available-ips with no room left)."""

    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        self.url = str(response.url)
        self.error = "The requested allocation could not be fulfilled."
        super().__init__(self.error)


class ContentError(Exception):
    """A successful response contained non-JSON content."""

    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        self.url = str(response.url)
        self.error = (
            "The server returned invalid (non-json) data. Maybe not a NetBox server?"
        )
        super().__init__(self.error)
