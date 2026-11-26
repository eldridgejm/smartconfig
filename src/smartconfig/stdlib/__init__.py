"""Standard library of functions for smartconfig.

``DEFAULT_FUNCTIONS`` holds the stdlib functions that :func:`smartconfig.resolve`
uses by default, organized by namespace. A stdlib function left out of it must be
passed to ``resolve`` explicitly to be used.

"""

from .. import types as _types
from .list import LIST_FUNCTIONS
from .dict import DICT_FUNCTIONS
from .datetime import DATETIME_FUNCTIONS

DEFAULT_FUNCTIONS: _types.FunctionMapping = {
    "datetime": DATETIME_FUNCTIONS,
    "dict": DICT_FUNCTIONS,
    "list": LIST_FUNCTIONS,
}

__all__ = [
    "DEFAULT_FUNCTIONS",
]
