"""smartconfig: interpolation, functions and schemas for configurations.

smartconfig resolves a configuration (dicts, lists and values, from any source:
JSON, YAML, TOML, Python, ...) against a schema: it interpolates ``${...}``
references with Jinja2, evaluates function calls written as one-key dicts like
``{"__list.loop__": {...}}``, and converts values to their types. The entry
point is ``resolve()``.

An agent cheat sheet covering the whole configuration language is
``docs/agent_cheatsheet.rst``, in the directory next to this file. The full
documentation is in that same ``docs/`` directory and at
https://eldridgejm.github.io/smartconfig/. (In a source checkout, such as an
editable install, the pages are in the repository's ``docs/source/`` instead.)

"""

from . import exceptions
from . import stdlib
from . import converters
from . import types
from . import prototypes
from ._resolve import resolve, DEFAULT_CONVERTERS, DEFAULT_FUNCTIONS
from ._schemas import validate_schema
from ._core_functions import CORE_FUNCTIONS
from .prototypes import Prototype

__all__ = [
    "exceptions",
    "converters",
    "stdlib",
    "types",
    "prototypes",
    "resolve",
    "Prototype",
    "validate_schema",
    "CORE_FUNCTIONS",
    "DEFAULT_FUNCTIONS",
    "DEFAULT_CONVERTERS",
]
