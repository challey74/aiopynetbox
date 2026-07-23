"""apynetbox: async NetBox API client."""

from importlib.metadata import version as _version

from apynetbox.api import Api
from apynetbox.exceptions import AllocationError, ContentError, RequestError
from apynetbox.models import register_model
from apynetbox.response import Record, RecordSet

__version__ = _version("apynetbox")

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
