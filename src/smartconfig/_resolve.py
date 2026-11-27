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
import functools
import typing

from . import converters as _converters, types as _types
from ._core_functions import CORE_FUNCTIONS
from ._internals import make_node, reporting_recursion_errors
from ._prototypes import Prototype, _is_prototype, instantiate, schema_of
from ._schemas import validate_schema
from ._utils import jinja_reserved_name_problem
from . import stdlib as _stdlib


# defaults =============================================================================

# the default converters used by resolve()
DEFAULT_CONVERTERS: dict[str, Callable] = {
    "integer": _converters.integer,
    "float": _converters.float_,
    "string": str,
    "boolean": _converters.boolean,
    "date": _converters.date,
    "datetime": _converters.datetime,
}

# the default functions used by resolve()
DEFAULT_FUNCTIONS: _types.FunctionMapping = {
    **_stdlib.DEFAULT_FUNCTIONS,
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
            # name the other keys: a function call is a dict with exactly one key
            function_key = next(key for key in dct if _is_dunder(key))
            others = ", ".join(repr(key) for key in dct if key != function_key)
            raise ValueError(
                f"A function call must be a dict with exactly one key, but "
                f"{function_key!r} has the other key(s) {others}."
            )
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


def _preserve_types(
    original: Any,
    resolved: _types.Configuration,
    is_function_call: Callable[[_types.ConfigurationDict], bool],
) -> Any:
    """``resolved``, with each container replaced by ``original``'s where it has one.

    Used when preserve_type = True in resolve(). ``original`` is a copy of the
    input and is filled in place. The resolved output is walked, not the input,
    because their structures can differ: a function call in the input can produce
    a container, and defaults add keys the input doesn't have. Where the input has
    no container of the same kind (it has a function call, or nothing), the
    resolved value is used as is.

    """
    if isinstance(resolved, dict):
        # a function call is a dict in the input, but its result has nothing to do
        # with that dict, so there is no container to preserve
        if not isinstance(original, dict) or is_function_call(original):
            return resolved
        for key, value in resolved.items():
            # keys only in resolved (filled in by defaults) get original.get(key)
            # of None, so their resolved values are used
            original[key] = _preserve_types(original.get(key), value, is_function_call)
        return original

    if isinstance(resolved, list):
        # a list in the input resolves to one of the same length, so a different
        # length means the input has no matching list
        if not isinstance(original, list) or len(original) != len(resolved):
            return resolved
        for i, value in enumerate(resolved):
            original[i] = _preserve_types(original[i], value, is_function_call)
        return original

    # a leaf (a number, string, date, Template, ...) has no type to preserve
    return resolved


def _is_function_call(
    cfg: _types.ConfigurationDict, context: _types.ResolutionContext
) -> bool:
    """Whether ``cfg`` is a function call, by the same check that resolve() uses."""
    try:
        return context.check_for_function_call(cfg, context.functions) is not None
    except ValueError:
        # an invalid function call would already have failed to resolve
        return False


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


def _make_resolution_context(
    converters: Mapping[str, Callable] = DEFAULT_CONVERTERS,
    functions: _types.FunctionMapping | None = DEFAULT_FUNCTIONS,
    global_variables: Mapping[str, Any] | None = None,
    filters: Mapping[str, Callable] | None = None,
    inject_root_as: str | None = None,
    check_for_function_call: _types.FunctionCallChecker
    | None = _check_for_dunder_function_call,
) -> _types.ResolutionContext:
    """The resolution context for the options of :func:`resolve`.

    The defaults are those of :func:`resolve`. Also used by
    :meth:`Template.evaluate`.

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

    # a global or root named like a Jinja literal (true, none) or self could never
    # be referred to: ${ true } would be the literal, silently, not the variable
    for name in global_variables:
        problem = jinja_reserved_name_problem(name)
        if problem is not None:
            raise ValueError(f"Invalid global variable: {problem}")
    problem = jinja_reserved_name_problem(inject_root_as)
    if problem is not None:
        raise ValueError(f"Invalid inject_root_as: {problem}")

    if filters is None:
        filters = {}

    if check_for_function_call is None:
        # do not check for function calls
        def _no_check(*_):
            return None

        check_for_function_call = _no_check

    return _types.ResolutionContext(
        converters,
        converted_functions,
        global_variables,
        filters,
        inject_root_as,
        check_for_function_call,
    )


# overloads ----------------------------------------------------------------------------

# these overloads are provided so that type checkers can predict that the return
# type of resolve() is the same as the input type. This is useful for IDEs and
# static type checkers.


@typing.overload
def resolve[P: Prototype](
    cfg: _types.Configuration,
    spec: type[P],
    converters: Mapping[str, Callable] = ...,
    functions: _types.FunctionMapping | None = ...,
    global_variables: Mapping[str, Any] | None = ...,
    inject_root_as: str | None = ...,
    filters: Mapping[str, Callable] | None = ...,
    preserve_type: bool = ...,
    check_for_function_call: _types.FunctionCallChecker | None = ...,
) -> P:
    """Overloaded resolve() for a Prototype class: returns an instance of it."""


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
    converters: Mapping[str, Callable] = ...,
    functions: _types.FunctionMapping | None = ...,
    global_variables: Mapping[str, Any] | None = ...,
    inject_root_as: str | None = ...,
    filters: Mapping[str, Callable] | None = ...,
    preserve_type: bool = ...,
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
    spec : Union[:class:`types.Schema`, :class:`types.DynamicSchema`, type[:class:`Prototype`]]
        The schema describing the structure of the resolved configuration. If a
        :class:`types.DynamicSchema` is provided (which is a callable), it is called
        with the configuration and the keypath and should return a
        :class:`types.Schema`.
        If a :class:`Prototype` subclass is provided, the configuration is resolved
        against its schema (:func:`schema_of`), and the result is an instance of
        it (:func:`instantiate`).
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
        list. If this is True, `smartconfig` will attempt to return an object of the
        same type as the input ``cfg``, and the same for the containers inside it. This
        is most useful when the input is a custom mapping type (such as a ruamel
        round-trip dict) that should be preserved in the output. See
        :ref:`type-preservation`.
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
    ValueError
        If a global variable or ``inject_root_as`` has a name that Jinja reserves
        (``true``, ``false``, ``none``, ``True``, ``False``, ``None``, ``not`` or
        ``self``), since ``${...}`` could never refer to it.

    """
    if _is_prototype(spec):
        # resolved like the equivalent schema dict, so errors are the same
        # (cfg is cast so that mypy needn't match each part of its union to an
        # overload; the overload for a dict, as of a dict schema, gives a dict)
        resolved_dict = resolve(
            typing.cast(Any, cfg),
            schema_of(spec),
            converters,
            functions,
            global_variables,
            inject_root_as,
            filters,
            preserve_type,
            check_for_function_call,
        )
        return instantiate(spec, resolved_dict)

    resolution_context = _make_resolution_context(
        converters,
        functions,
        global_variables,
        filters,
        inject_root_as,
        check_for_function_call,
    )

    schema = typing.cast(_types.Schema, spec)

    # so that a schema or configuration too deep to handle is a ResolutionError, not
    # a RecursionError (each of the three steps below is recursive)
    with reporting_recursion_errors():
        # validate the schema first: an invalid one would otherwise fail later with
        # an unhelpful error (e.g. a KeyError), or be silently accepted. Dynamic
        # schemas are validated when they are called
        validate_schema(schema, converters=resolution_context.converters)

        root = make_node(cfg, schema, resolution_context)
        resolved = root.resolve()

    if not preserve_type or _is_leaf(resolved):
        # a leaf at the root (e.g. a Template) has no structure to preserve
        return resolved
    else:
        # pass _preserve_types only the check it needs, not the whole context
        is_function_call = functools.partial(
            _is_function_call, context=resolution_context
        )
        return _preserve_types(copy.deepcopy(cfg), resolved, is_function_call)
