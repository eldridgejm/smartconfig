"""Standard library of default functions for smartconfig."""

from .. import types as _types
from .list import LIST_FUNCTIONS
from .dict import DICT_FUNCTIONS
from .datetime import DATETIME_FUNCTIONS

STDLIB_FUNCTIONS: _types.FunctionMapping = {
    "datetime": DATETIME_FUNCTIONS,
    "dict": DICT_FUNCTIONS,
    "list": LIST_FUNCTIONS,
}

__all__ = [
    "STDLIB_FUNCTIONS",
]
