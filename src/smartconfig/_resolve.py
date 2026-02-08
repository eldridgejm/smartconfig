"""Public resolve() function, default converters, and default function definitions.

This module provides the :func:`resolve` entry point and the default values for its
parameters (:data:`DEFAULT_CONVERTERS`, :data:`DEFAULT_FUNCTIONS`). It is a thin wrapper
around the internal tree-building and resolution machinery defined in ``_internals.py``;
see that module's docstring for a detailed description of how resolution works.

"""

from typing import (
    Any,
    Callable,
    Mapping,
)
import copy
import typing

from . import converters as _converters, types as _types
from ._core_functions import CORE_FUNCTIONS
from ._internals import make_node
from ._prototypes import Prototype, is_prototype_class
from .stdlib import STDLIB_FUNCTIONS


# defaults =============================================================================

# the default converters used by resolve()
DEFAULT_CONVERTERS: dict[str, Callable] = {
    "integer": _converters.integer,
    "float": _converters.float_,
    "string": str,
    "boolean": _converters.boolean,
    "date": _converters.date,
    "datetime": _converters.datetime,
    "any": lambda x: x,
}

# the default functions used by resolve()
DEFAULT_FUNCTIONS: _types.FunctionMapping = {
    **STDLIB_FUNCTIONS,
    **CORE_FUNCTIONS,
}


def _check_for_dunder_function_call(
    dct: _types.ConfigurationDict, functions: Mapping[str, _types.Function]
) -> tuple[_types.Function, _types.Configuration] | None:
    """Checks if a ConfigurationDict represents a function call.

    In this case, a function call is a dictionary with a single key of the form
    "__<function_name>__".

    Parameters
    ----------
    dct : ConfigurationDict
        The dictionary to check.
    functions: Mapping[str, Function]
        The functions available.

    Returns
    -------
    Union[tuple[Function, Configuration], None]
        If this is a valid function call, a 2-tuple is returned with the function and
        the input to the function. Otherwise, None is returned.

    Raises
    ------
    ValueError
        If the dictionary has a key of the form "__<function_name>__" but there
        are other keys present, making this an invalid function call, or if the
        function being called is not known.

    """

    def _is_dunder(s: str) -> bool:
        """Checks if a string is of the form "__<something>__"."""
        return s.startswith("__") and s.endswith("__")

    is_potential_function_call = any(_is_dunder(key) for key in dct.keys())

    if is_potential_function_call:
        if len(dct) != 1:
            raise ValueError("Invalid function call.")
        else:
            key = next(iter(dct.keys()))
            function_name = key[2:-2]
    else:
        return None

    if function_name not in functions:
        raise ValueError(f"Unknown function: {function_name}")

    return functions[function_name], dct[key]


# helpers ------------------------------------------------------------------------------


def _is_leaf(x: _types.Configuration) -> bool:
    return not isinstance(x, dict) and not isinstance(x, list)


def _copy_into(dst, src):
    """Recursively copy the leaf values from src to dst.

    Used when preserve_type = True in resolve()

    """
    assert isinstance(dst, (dict, list))

    if isinstance(dst, dict):
        keys = dst.keys()
    else:
        # dst must be a list
        keys = range(len(dst))

    for key in keys:
        x = src[key]
        if _is_leaf(x):
            dst[key] = src[key]
        else:
            _copy_into(dst[key], src[key])


def _ensure_function(
    callable_or_function: _types.FunctionOrCallable,
) -> _types.Function:
    """Converts standard Python functions to _types.Function instances."""
    if isinstance(callable_or_function, _types.Function):
        return callable_or_function
    else:
        return _types.Function(callable_or_function)


def _flatten_functions(
    mapping: _types.FunctionMapping, prefix: str = ""
) -> dict[str, _types.Function]:
    """Flatten a possibly-nested function mapping into dot-separated keys.

    Raw callables are wrapped in :class:`Function` via :func:`_ensure_function`.

    Parameters
    ----------
    mapping : FunctionMapping
        A mapping of function names to functions or nested FunctionMapping
        instances.
    prefix : str
        The prefix to prepend to keys, used during recursion to build
        dot-separated names. Defaults to ``""``.

    Returns
    -------
    dict[str, Function]
        A flat dictionary mapping dot-separated names to Function instances.

    """
    result: dict[str, _types.Function] = {}
    for key, value in mapping.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, Mapping):
            result.update(_flatten_functions(value, full_key))
        else:
            result[full_key] = _ensure_function(value)
    return result


# overloads ----------------------------------------------------------------------------

# these overloads are provided so that type checkers can predict that the return
# type of resolve() is the same as the input type. This is useful for IDEs and
# static type checkers.


@typing.overload
def resolve[_P: Prototype](
    cfg: _types.Configuration,
    spec: type[_P],
    converters: Mapping[str, Callable] = ...,
    functions: _types.FunctionMapping | None = ...,
    global_variables: Mapping[str, Any] | None = ...,
    inject_root_as: str | None = ...,
    filters: Mapping[str, Callable] | None = ...,
    preserve_type: bool = ...,
    check_for_function_call: _types.FunctionCallChecker | None = ...,
) -> _P:
    """Overloaded resolve() for ConfigurationValue."""


@typing.overload
def resolve(
    cfg: _types.ConfigurationDict,
    spec: _types.Schema | _types.DynamicSchema,
    converters: Mapping[str, Callable] = ...,
    functions: _types.FunctionMapping | None = ...,
    global_variables: Mapping[str, Any] | None = ...,
    inject_root_as: str | None = ...,
    filters: Mapping[str, Callable] | None = ...,
    preserve_type: bool = ...,
    check_for_function_call: _types.FunctionCallChecker | None = ...,
) -> dict:
    """Overloaded resolve() for ConfigurationDict."""


@typing.overload
def resolve(
    cfg: _types.ConfigurationList,
    spec: _types.Schema | _types.DynamicSchema,
    converters: Mapping[str, Callable] = DEFAULT_CONVERTERS,
    functions: _types.FunctionMapping | None = DEFAULT_FUNCTIONS,
    global_variables: Mapping[str, Any] | None = None,
    inject_root_as: str | None = None,
    filters: Mapping[str, Callable] | None = None,
    preserve_type: bool = False,
    check_for_function_call: _types.FunctionCallChecker | None = ...,
) -> list:
    """Overloaded resolve() for ConfigurationList."""


@typing.overload
def resolve(
    cfg: _types.ConfigurationValue,
    spec: _types.Schema | _types.DynamicSchema,
    converters: Mapping[str, Callable] = ...,
    functions: _types.FunctionMapping | None = ...,
    global_variables: Mapping[str, Any] | None = ...,
    inject_root_as: str | None = ...,
    filters: Mapping[str, Callable] | None = ...,
    preserve_type: bool = ...,
    check_for_function_call: _types.FunctionCallChecker | None = ...,
) -> Any:
    """Overloaded resolve() for ConfigurationValue."""


# implementation -----------------------------------------------------------------------


def resolve(
    cfg: _types.Configuration,
    spec: _types.Schema | _types.DynamicSchema | type[Prototype],
    converters: Mapping[str, Callable] = DEFAULT_CONVERTERS,
    functions: _types.FunctionMapping | None = DEFAULT_FUNCTIONS,
    global_variables: Mapping[str, Any] | None = None,
    inject_root_as: str | None = None,
    filters: Mapping[str, Callable] | None = None,
    preserve_type: bool = False,
    check_for_function_call: _types.FunctionCallChecker
    | None = _check_for_dunder_function_call,
) -> _types.Configuration | Prototype:
    """Resolve a configuration by interpolating and parsing its entries.

    Parameters
    ----------
    cfg : :class:`types.Configuration`
        The "raw" configuration to resolve.
    spec : Union[:class:`types.Schema`, :class:`types.DynamicSchema`, :class:`Prototype`]
        The schema describing the structure of the resolved configuration, or a
        :class:`Prototype` subclass. If a :class:`Prototype` subclass is provided, the
        resolved configuration will be an instance of that :class:`Prototype` class. If
        a :class:`types.DynamicSchema` is provided (which is a callable), it is called
        with the configuration and the keypath and should return a
        :class:`types.Schema`.
    converters : Mapping[str, Callable]
        A dictionary mapping value types to converter functions. The converter functions
        should take the raw value (after interpolation) and convert it to the specified
        type. If this is not provided, the default converters in :data:`DEFAULT_CONVERTERS` are used.
    functions : Mapping[str, Union[Callable, :class:`types.Function`]] | None
        A mapping of function names to functions. The functions should either be basic
        Python functions accepting an instance of :class:`types.FunctionArgs` as input
        and returning a :class:`types.Configuration`, or they should be
        :class:`smartconfig.types.Function` instances. If ``None``, no
        functions are made available. Defaults to :data:`DEFAULT_FUNCTIONS`.
    global_variables : Mapping[str, Any] | None
        A dictionary of global variables to make available during string interpolation.
        If this is not provided, no global variables are available.
    inject_root_as : str | None
        If this is not None, the root of the configuration tree is made available to
        Jinja2 templates as an :class:`types.UnresolvedDict`,
        :class:`types.UnresolvedList`, or :class:`types.UnresolvedFunctionCall` by
        injecting it into the template variables as the value of this key. This allows
        the root to be referenced directly during string interpolation. Defaults to
        ``None``.
    filters : Mapping[str, Callable] | None
        A dictionary of Jinja2 filters to make available to templates. These will be
        added to Jinja2's set of default filters. If ``None``, no custom filters are
        provided. Defaults to ``None``.
    preserve_type : bool (default: False)
        If False, the return value of this function is a plain Python dictionary or
        list. If this is True, however, the return type will be the same as the type of
        cfg. See below for details.
    check_for_function_call : :class:`types.FunctionCallChecker`
        A function that checks if a :class:`types.ConfigurationDict` represents a
        function call. It is given the configuration and the available functions. If it
        is a function call, it returns a 2-tuple of the :class:`types.Function` and the
        input to the function. If not, it returns None. If it is an invalid function
        call, it should raise a ``ValueError``. If this is not provided, a default
        implementation is used that assumes function calls are dictionaries with a
        single key of the form ``__<function_name>__``. If set to None, function calls
        are effectively disabled.

    Raises
    ------
    InvalidSchemaError
        If the schema is not valid.
    ResolutionError
        If the configuration does not match the schema, if there is a circular
        reference, or there is some other issue with the configuration itself.

    """
    if functions is None:
        converted_functions: Mapping[str, _types.Function] = {}
    else:
        # convert standard Python functions to _types.Function instances,
        # flattening any nested mappings into dot-separated keys
        converted_functions = _flatten_functions(functions)

    if global_variables is None:
        global_variables = {}
    else:
        global_variables = dict(global_variables)

    if filters is None:
        filters = {}

    if check_for_function_call is None:
        # do not check for function calls
        def _no_check(*_):
            return None

        check_for_function_call = _no_check

    resolution_context = _types.ResolutionContext(
        converters,
        converted_functions,
        global_variables,
        filters,
        inject_root_as,
        check_for_function_call,
    )

    if is_prototype_class(spec):
        schema = spec._schema()
    else:
        schema = typing.cast(_types.Schema, spec)

    root = make_node(cfg, schema, resolution_context)

    resolved = root.resolve()

    if is_prototype_class(spec):
        # convert the resolved dict into a Prototype instance
        assert isinstance(resolved, dict)
        return spec._from_dict(resolved)
    elif not preserve_type:
        return resolved
    else:
        output = copy.deepcopy(cfg)
        _copy_into(output, resolved)
        return output
