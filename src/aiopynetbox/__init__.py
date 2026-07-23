"""aiopynetbox: async NetBox API client."""

from importlib.metadata import version as _version

from aiopynetbox.api import Api
from aiopynetbox.exceptions import AllocationError, ContentError, RequestError
from aiopynetbox.models import register_model
from aiopynetbox.response import Record, RecordSet

__version__ = _version("aiopynetbox")

api = Api

__all__ = [
    "AllocationError",
    "Api",
    "ContentError",
    "Record",
    "RecordSet",
    "RequestError",
    "__version__",
    "api",
    "register_model",
]
