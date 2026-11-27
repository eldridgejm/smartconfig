"""Internal representation of configurations as trees, and the machinery for resolving them.

This module is the implementation core of smartconfig. It defines the node types
used to represent a configuration as a tree, the "unresolved container" wrappers
that allow Jinja2 to lazily access parts of the tree, and the ``make_node()``
factory that constructs the tree from raw configuration data.

The public entry point is :func:`smartconfig.resolve` (in ``_resolve.py``),
which is a thin wrapper around the machinery defined here.

Background
==========

In smartconfig, a *configuration* is either:

- a dictionary whose keys are strings and values are configurations,
- a list whose elements are configurations, or
- a simple value (string, integer, float, boolean, date, datetime, or None).

The purpose of `smartconfig` is to allow configurations to contain dynamic elements that
are resolved at runtime, such as references to other parts of the configuration,
arithmetic expressions, or function calls. The resolve() function takes in an unresolved
configuration and "resolves" it into a resolved configuration by following all
references, evaluating all expressions, and calling all functions.

Internal Representation of Configurations
=========================================

Because configurations are naturally hierarchical, it is useful to think of them as
*configuration trees*. The internal nodes of the tree are dictionaries and lists, and
the leaves are simple values.

Value nodes can contain references to other nodes in the configuration tree. If we
represent these references with directed "cross-edges" between nodes, our configuration
tree becomes a *configuration graph*. An edge in this graph captures a dependency: the
successor node must be resolved before the predecessor node.

This module represents the configuration internally as a configuration tree/graph. It
defines _DictNode, _ListNode, and _ValueNode types, as well as the _FunctionCallNode
type for representing dynamic function calls. The creation of the tree/graph is
orchestrated by the make_node() function, whose job is to take an arbitrary
configuration and determine which node class should be used to represent it. This
function is called with the whole configuration to create the root node, and is also
called by the container node classes to create their children.

Resolution
==========

Each of the node types listed above implements a `.resolve()` method that recursively
resolves the node into a resolved configuration; these methods do the actual work of
resolution. The resolve() function itself is a wrapper which:

    1. Constructs the root node using make_node(),
    2. Calls .resolve() on the root node, effectively performing a depth-first traversal
       of the graph, resolving it as it goes and returning the result.

Much of the real work happens when a _ValueNode is resolved. The resolution of a
_ValueNode involves two steps:

    1. String interpolation: If the value is a string, it is passed to Jinja2 for string
       interpolation, as discussed in the "String Interpolation with Jinja2" section
       below.

    2. Conversion: The resolved string is then converted to the expected type using the
       appropriate converter as determined by the schema.

There are a few details about resolution that deserve further explanation:

String Interpolation with Jinja2
--------------------------------

String interpolation (like of "${foo.bar}") is delegated to Jinja2.

During the resolution of a _ValueNode representing a string, the string is passed to
Jinja2 for interpolation. When Jinja encounters a reference of the form "${foo.bar}", it
looks for "foo" in a custom context object that searches three sources, in this order:

    1. Local variables. Each node in the configuration tree can have a dictionary of
    local variables. These variables are available when resolving any leaf node in its
    subtree. For more information, see the "Local Variables" section below.

    2. Root. If the reference is not found in the local variables, Jinja2 looks for it
    in the root of the configuration tree. For more information, see the "Root
    Container" section below.

    3. Global variables. If the reference is not found in the root of the configuration,
    Jinja2 looks for it in a dictionary of global variables that can be passed to the
    resolve() function.

If the name is found in none of these (nor among Jinja's own names, like ``range``), it
is an _UndefinedName, which knows the names that were available; using it raises an
UndefinedNameError that suggests a close name or lists them.

Local Variables
~~~~~~~~~~~~~~~

When Jinja2 encounters a reference like "${foo.bar}", it looks for "foo" in the custom
context; in turn, the custom context first searches for "foo" in the "local variables".

The local variables are attached to the nodes in the configuration tree. Each node in
the tree carries a `.local_variables` attribute; this is a dictionary of variables that
can be accessed during the resolution of any value node in the subtree rooted at that
node. This is useful for passing information down the tree. For example, a function node
might set a variable in its local variables that can be accessed by its children.

In addition, each node type provides a `.get_local_variable()` method to retrieve a
variable from the node or its ancestors. Calling `.get_local_variable(key)` on a value
node will search up the tree for the first occurrence of the key, returning its value or
raising a KeyError if the key is not found.

Root Container
~~~~~~~~~~~~~~

When Jinja2 encounters a reference like "${foo.bar}", it looks for "foo" using the
custom context. If the context does not find "foo" in the local variables, it then
searches for it in the root of the configuration tree. Assuming that "${foo.bar}" is a
valid reference to another part of the configuration tree, we expect the root node
to either be a dictionary containing a key "foo" or a function call that evaluates to a
dictionary containing a key "foo".

At the moment that Jinja2 is performing string interpolation, resolution of the
configuration is in-progress. For this reason, we do not have access to the
fully-resolved dictionary at the root of the configuration at that time, and so we can't
simply look up the value of "foo" within that dictionary. Instead, we represent the root
as an "unresolved" container: either an _UnresolvedDict, _UnresolvedList, or
_UnresolvedFunctionCall, depending on the type of the root node. When an element of one
of these containers is accessed, the resolution process is triggered for that element if
it is a function node or a value node. Otherwise, another unresolved collection is
returned. This prevents circular references from causing infinite loops.

Worked Example
==============

Consider the configuration:

    .. code:: python

        {
            "foo": "${bar.baz + 1}",
            "bar": {
                "baz": 42
            }
        }

With schema:

    .. code:: python

        {
            "type": "dict",
            "required_keys": {
                "foo": {"type": "integer"},
                "bar": {
                    "type": "dict",
                    "required_keys": {
                        "baz": {"type": "integer"}
                    }
                }
            }
        }

When resolve() is called on this configuration, the following major steps occur:

    1. resolve() calls make_node() to create the root node, which in this case is a
       _DictNode. The _DictNode's constructor also creates the children of the node,
       calling make_node() on each child. The process continues recursively,
       and at the end the root node will contain two children: a _ValueNode representing
       the "${bar.baz + 1}" string and a _DictNode representing the "bar" dictionary.
       This _DictNode has one child: a _ValueNode representing the number 42.

    2. resolve() calls .resolve() on the root node. Because the root node is a
       _DictNode, resolving it amounts to calling the .resolve() method on each of its
       children. Suppose the "foo" child is first.

    3. Because the "foo" child is a _ValueNode representing a string, its .resolve()
       method begins by interpolating the string using Jinja2. Before interpolation,
       a custom Jinja2 context is created which searches through local variables first,
       then the root, and then through the global variables. More precisely, because the
       root node is a _DictNode, an instance of _UnresolvedDict is created wrapping the
       root node, and this is passed to Jinja2 as part of the custom context.

    4. Jinja2 begins interpolating the string. It sees the expression ${bar.baz + 1}
       and looks up "bar" in the context. The context searches the local variables
       first, but seeing as there are none, it then looks up "bar" in the root of the
       configuration tree (which is an _UnresolvedDict wrapping the _DictNode
       representing the root). The _UnresolvedDict recognizes the key as a reference to
       a child node of type _DictNode, and so it returns a new _UnresolvedDict wrapping
       the child node. Jinja2 next looks up "baz" in this new _UnresolvedDict. This
       time, the _UnresolvedDict recognizes the key as a reference to a child
       _ValueNode, and so it triggers the resolution of the child node by calling its
       .resolve() method. Interpolation of the string pauses momentarily while the child
       node is resolved.

    5. When .resolve() is called on the _ValueNode representing the number 42,
       interpolation is skipped since the contained value is not a string. The schema
       expects this value to be an integer, so the integer converter is called on the
       value, and the result (42) is returned.

    6. Jinja resumes evaluating the expression, computing 42 + 1 = 43. The entire
       interpolation ${bar.baz + 1} is replaced with "43". The integer converter is
       then called on the string "43", and the result (43) is returned. This is the
       resolved value of the "foo" key.

    7. Now that "foo" has been resolved, the code backtracks to the _DictNode's
       .resolve() method, which then attempts to resolve the "bar" child. This is a
       _DictNode, so its .resolve() method is called. This call attempts to resolve its
       only child, the _ValueNode representing the number 42. This node was already
       resolved during the resolution of "foo", and the resolved value is returned.

    8. The _DictNode representing "bar" is now fully resolved, and the _DictNode
       representing the root of the configuration tree is also fully resolved. The
       resolved configuration is returned from resolve().

Template Fields
---------------

A field whose schema has ``"type": "template"`` is represented by a _TemplateNode.
When a configuration containing a template field is resolved, the field is not
resolved to an ordinary value (an int, a string, a dict, etc.). Rather, the node
resolves to a :class:`smartconfig.types.Template` holding the value as written.

The resolver does not unwrap a template field's value itself. make_node() builds an
ordinary _FunctionCallNode for it, whose function is given the template schema; the
value of a template field must be a function call (or a Template passed in). The core functions decide what to do with that schema:
``__template__`` returns a _TemplateNode of its input, and ``__use__`` returns a
_TemplateNode of the template it copies (see _core_functions.py). Any other function's
result is built under the template schema too, so ``__if__`` choosing between two
``__template__`` values works, and a result that isn't a template is an error.

Like a _ValueNode, a _TemplateNode is resolved lazily and the result cached.
Resolving it:

    1. replaces each ``__use__`` in the value with the value it stands for (as written).
       The target is looked up as a ``${...}`` reference would be (local variables,
       the document, then the global variables), so it is done here rather than
       when the node is built, since looking in the document needs the whole tree;
    2. builds a node tree of the value against the inner schema, which checks its
       structure, and walks that tree without resolving it (_TemplateNode._check).
       A template inside it is resolved, so its value is checked in the same way,
       at any depth;

    Steps 1 and 2 are the only places where the resolver must recognize a core
    function by identity (_is_use_function, _is_template_function): a template's
    value is not evaluated, so no function in it runs that could act for itself;
    3. returns a Template that remembers the resolution options and the parameters.

A ``__template__`` wrapper on a field of type ``any`` also gives a _TemplateNode (with
an ``any`` inner schema and no parameters); see ``_template()`` in _core_functions.py.
Template.evaluate() (in types.py) builds and resolves a new tree from the
template's source, with the given parameters in the resolution context's
``template_parameters``. Names are looked up there after the document and before the
global variables.

Templates nest. A template field inside a template's value is resolved while the
outer template is evaluated, so its _TemplateNode has the outer evaluation's context,
and the Template it makes carries the context's ``template_parameters`` as its
``outer_parameters``. When the inner template is evaluated, they are put in its
context with its own parameters. Nothing in the tree records which templates are
around a node: the values travel in the context. When the configuration is resolved,
step 2 puts the template's parameter names (with ``None`` values) in the context of
the tree it checks, so that an inner template can be checked against them.

"""

from __future__ import annotations

from typing import (
    Any,
    Callable,
    Iterable,
    Mapping,
)
import abc
import contextlib
import copy
import dataclasses
import difflib
import enum
import functools
import typing

import jinja2

from . import types as _types
from .exceptions import (
    Error,
    InvalidSchemaError,
    ResolutionError,
    TemplateRequiredError,
    UndefinedNameError,
    UnexpectedTemplateError,
)
from ._schemas import validate_schema as _validate_schema
from .types import Template
from ._utils import deep_update


# Exceptions that are not wrapped in a ResolutionError when raised by an expression,
# a filter or a function: smartconfig's own errors already say where they happened;
# an AssertionError is a bug in the code, not a mistake in the configuration; and a
# RecursionError is reported by reporting_recursion_errors, at the root.
_NOT_WRAPPED = (Error, AssertionError, RecursionError)


def _wrapped(exc: Exception, keypath: _types.KeyPath) -> ResolutionError:
    """A ResolutionError at ``keypath`` for an exception that isn't smartconfig's.

    The exception's type is kept in the message, since some messages (a KeyError's
    ``'x'``, say) mean little without it. Raise it ``from exc`` to keep the cause.

    """
    return ResolutionError(f"{type(exc).__name__}: {exc}", keypath)


def _call_dynamic_schema(
    schema: _types.DynamicSchema,
    cfg: _types.Configuration,
    keypath: _types.KeyPath,
    resolution_context: _types.ResolutionContext,
    allow_default: bool,
) -> _types.Schema:
    """Call a dynamic schema and validate the schema it returns.

    Every place that calls a dynamic schema goes through here, so that each reports
    its errors in the same way, at ``keypath``.

    Parameters
    ----------
    schema
        The dynamic schema.
    cfg
        The configuration it is called with (``None`` for a missing optional key).
    keypath
        The keypath of that configuration.
    resolution_context
        The resolution context; its converters are the valid value types.
    allow_default
        Whether the returned schema may have a "default".

    Returns
    -------
    Schema
        The validated schema.

    Raises
    ------
    ResolutionError
        If the dynamic schema raises an exception that isn't smartconfig's (other
        than an AssertionError or RecursionError), with the exception as its cause.
    InvalidSchemaError
        If the returned schema is another dynamic schema, or is invalid.

    """
    # an exception raised by the dynamic schema gets the keypath it was called for,
    # as one raised by a function gets the call's
    try:
        result = schema(cfg, keypath)
    except _NOT_WRAPPED:
        raise
    except Exception as exc:
        raise _wrapped(exc, keypath) from exc

    # _validate_schema accepts a callable without calling it (dynamic schemas nested
    # in the result are fine), so a callable result is rejected here, before it is
    # used as a schema dict
    if callable(result):
        raise InvalidSchemaError(
            "A dynamic schema must return a schema, not another dynamic schema.",
            keypath,
        )

    # the keypath makes an error read "a.0.type", not "type"; the converters make a
    # type defined by a custom converter valid here as it is in a static schema
    _validate_schema(
        result,
        keypath,
        allow_default=allow_default,
        allow_dynamic=True,
        converters=resolution_context.converters,
    )
    return result


class ResolutionMode(enum.Enum):
    """Controls the level of interpolation / function evaluation."""

    # no string interpolation at all; functions are not evaluated
    RAW = "raw"

    # single-pass string interpolation
    STANDARD = "standard"

    # multi-pass string interpolation until no ${...} references remain
    FULL = "full"


# unresolved containers ================================================================
#
# These containers are used to represent the configuration while it is being resolved.
# They are passed to Jinja as variables available during string interpolation, and they
# are provided to functions as part of their input so that they can reference other
# parts of the configuration as well. Accessing an element in a unresolved container
# triggers the resolution of that element if it is a function node or a value node.
# Otherwise, it returns another unresolved container.

# _UnresolvedDict ----------------------------------------------------------------------


def _did_you_mean(name: str, candidates: typing.Iterable[str]) -> str | None:
    """A ' Did you mean "x"?' suggestion of a close candidate, or None."""
    matches = difflib.get_close_matches(name, list(candidates), n=1)
    return f' Did you mean "{matches[0]}"?' if matches else None


def _describe_keys(keys: list[str], limit: int = 10) -> str:
    """A sentence listing a mapping's keys, for an undefined key's message."""
    if not keys:
        return " It is empty."
    listed = ", ".join(f'"{key}"' for key in keys[:limit])
    if len(keys) > limit:
        listed += f", and {len(keys) - limit} more"
    return f" Its keys are {listed}."


class StrictUndefined(jinja2.StrictUndefined):
    """A StrictUndefined whose messages say what is missing and suggest a fix.

    Without this, a reference like ``${ vars.nope }`` reports
    ``'smartconfig._internals._UnresolvedDict object' has no attribute 'nope'``,
    and one like ``${ meta.topc }`` reports ``'dict object' has no attribute
    'topc'``. With it, the message names the configuration key when there is
    one, and suggests a close key or attribute (or lists the keys).

    It is the ``undefined`` class of the environment used to resolve
    configurations. It is not part of the public API.

    """

    @property
    def _undefined_message(self) -> str:
        # this must never raise AttributeError: Python would then fall back to
        # Undefined.__getattr__, which asks for this message again, forever
        obj = self._undefined_obj
        name = self._undefined_name

        # before the check below, since a list's missing element is usually named
        # by an integer index, which would get Jinja's message naming the
        # internal container class
        if isinstance(obj, _UnresolvedList):
            keypath = obj.list_node.keypath
            where = ".".join(str(k) for k in keypath) or "The list"
            element = f'"{name}"' if isinstance(name, str) else str(name)
            return f'"{where}" has no element {element}.'

        if obj is jinja2.utils.missing or not isinstance(name, str):
            return super()._undefined_message

        # the root is a function call that evaluated to a plain value, such as the
        # string an __if__ returns; without this, the message names the internal class
        if isinstance(obj, _UnresolvedFunctionCall) and isinstance(
            obj.function_node.evaluate(), (_ValueNode, _TemplateNode)
        ):
            return f'The configuration is a single value, so it has no key "{name}".'

        if isinstance(obj, _UnresolvedDict):
            keypath = obj.dict_node.keypath
            where = ".".join(str(k) for k in keypath)
            message = (
                f'"{where}" has no key "{name}".'
                if where
                else f'The configuration has no key "{name}".'
            )
            keys = [str(k) for k in obj.dict_node.children]
            return message + (_did_you_mean(name, keys) or "")

        if isinstance(obj, typing.Mapping):
            keys = [str(k) for k in obj]
            message = f'The {type(obj).__name__} has no key "{name}".'
            return message + (_did_you_mean(name, keys) or _describe_keys(keys))

        attributes = [a for a in dir(obj) if not a.startswith("_")]
        message = f'The {type(obj).__name__} object has no attribute "{name}".'
        return message + (_did_you_mean(name, attributes) or "")


class _UndefinedNameJinjaError(jinja2.exceptions.UndefinedError):
    """Raised by Jinja for an undefined top-level name; see _UndefinedName."""

    def __init__(self, message: str, name: str, available: tuple[str, ...]):
        super().__init__(message)
        self.name = name
        self.available = available


class _UndefinedName(StrictUndefined):
    """An undefined top-level name, which knows the names that were available.

    Using it raises a _UndefinedNameJinjaError, which _interpolate turns into an
    UndefinedNameError.

    """

    def __init__(self, name: str, available: tuple[str, ...]):
        def exception(message: str) -> _UndefinedNameJinjaError:
            return _UndefinedNameJinjaError(message, name, available)

        # Jinja raises self._undefined_exception(message) whenever the value is used
        super().__init__(name=name, exc=typing.cast(type, exception))
        self._available = available

    @property
    def _undefined_message(self) -> str:
        name = str(self._undefined_name)
        hint = _did_you_mean(name, self._available)
        if hint is None and self._available:
            hint = f" Names available here: {', '.join(self._available)}."
        return f"'{name}' is undefined.{hint or ''}"


class _DeferredError(StrictUndefined):
    """A name whose value failed to resolve, standing in until the name is used.

    Jinja looks up every name in a string before evaluating any of it, so in
    ``${ y if debug else 'plain' }`` it asks for ``y`` even when ``debug`` is
    false. If resolving ``y`` fails (say, with a circular reference, because ``y``
    refers back to this string), the lookup gives this instead of raising. Using it
    in any way raises the original error; a branch that never uses it is unharmed.

    """

    def __init__(self, name: str, error: ResolutionError):
        def exception(message: str) -> ResolutionError:
            return error

        # Jinja raises self._undefined_exception(message) whenever the value is used
        # (overriding _fail_with_undefined_error wouldn't do: StrictUndefined binds
        # its dunder methods to the base class's)
        super().__init__(name=name, exc=typing.cast(type, exception))
        self.error = error


def _raise_if_deferred_error(value: typing.Any) -> None:
    """Raise the error a _DeferredError stands for; do nothing for other values."""
    if isinstance(value, _DeferredError):
        raise value.error


def _raising_deferred_errors(function: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap a Jinja test or filter so that a _DeferredError argument raises its error.

    Jinja's tests and filters treat any undefined value as missing: ``y is
    defined`` is false, ``y | default(1)`` is 1 and ``y is none`` is false. For a
    name that exists but failed to resolve, that would hide the error.

    """

    # wraps copies jinja_pass_arg, which tells Jinja what to pass the filter first
    @functools.wraps(function)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        for arg in (*args, *kwargs.values()):
            _raise_if_deferred_error(arg)
        return function(*args, **kwargs)

    return wrapper


_JINJA_FILTERS = {
    name: _raising_deferred_errors(f) for name, f in jinja2.filters.FILTERS.items()
}
# some of Jinja's tests are typed as plain functions, which mypy won't take as Callable
_JINJA_TESTS = {
    name: _raising_deferred_errors(typing.cast(Callable[..., Any], t))
    for name, t in jinja2.tests.TESTS.items()
}


class _Uninsertable(Exception):
    """A ``${...}`` gave a value that can't go into a string: a dict, a list or
    Jinja's ``self``."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class _InsertedNone(Exception):
    """A ``${...}`` in a string gave None.

    _interpolate writes the message, since it knows the string.

    """


def _key_reference(where: str, key: str) -> str:
    """A reference to *key* of the dict at *where*, as in ``${ where.key }``."""
    if key.isidentifier():
        return f"${{ {where}.{key} }}"
    return f'${{ {where}["{key}"] }}'


def _resolve_for_json(value: typing.Any) -> typing.Any:
    """Plain data for an unresolved container, for Jinja's ``tojson`` filter."""
    # a name that failed to resolve, inside a list or dict given to tojson
    _raise_if_deferred_error(value)
    if isinstance(value, (_UnresolvedDict, _UnresolvedList)):
        return value.resolve()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _refuse_uninsertable(value: typing.Any) -> typing.Any:
    """Raise if *value*, the value of a ``${...}``, is None, a dict or a list.

    Inserted into a string, None would become "None", and a dict or list its
    Python repr (or, for an unresolved one, the repr of an internal object),
    which is almost never what's meant. Used as the ``finalize`` of the Jinja
    environment.

    """
    # None would silently become the string "None", which a nullable field would
    # then keep (or fail to convert) instead of being null. __splice__ copies it
    if value is None:
        raise _InsertedNone()
    # Jinja reads self as the template itself, whatever the configuration holds,
    # and would insert "<TemplateReference None>"
    if isinstance(value, jinja2.runtime.TemplateReference):
        raise _Uninsertable(
            'In ${ ... }, Jinja reads "self" as the template itself, not a key or '
            "variable of that name. To use a key named self, give its container, as "
            "in ${ parent.self }, or use inject_root_as."
        )
    cant = "can't be inserted into a string"
    if isinstance(value, Template):
        where = ".".join(value.keypath)
        raise _Uninsertable(
            f'"{where}" is a template, which {cant}. Use it with __use__ instead.'
        )
    if isinstance(value, _UnresolvedDict):
        where = ".".join(str(k) for k in value.dict_node.keypath)
        keys = [str(k) for k in value.dict_node.children]
        example = f", as in {_key_reference(where, keys[0])}," if keys else ""
        raise _Uninsertable(
            f'"{where}" is a dict, which {cant}. Use one of its keys{example} or copy '
            f"the whole value with __splice__."
        )
    if isinstance(value, _UnresolvedList):
        where = ".".join(str(k) for k in value.list_node.keypath)
        raise _Uninsertable(
            f'"{where}" is a list, which {cant}. Use one of its elements, as in '
            f"${{ {where}[0] }}, or copy the whole value with __splice__."
        )
    if isinstance(value, typing.Mapping):
        described = _describe_value(dict(value))
        raise _Uninsertable(
            f"{described[0].upper()}{described[1:]} {cant}. Use one of its keys "
            f"instead."
        )
    if isinstance(value, (list, tuple)):
        raise _Uninsertable(
            f"A {type(value).__name__} {cant}. Use one of its elements instead."
        )
    return value


class _Environment(jinja2.Environment):
    """A Jinja environment in which ``${ a.b }`` on a configuration container is a["b"].

    Jinja tries Python attributes before items, so a key named like a method of an
    unresolved container (``keys``, ``values``, ``resolve``, ``get_keypath``) would
    give the method. Here a container's items come first; its methods are found
    only when no item has the name, so ``${ a.keys() }`` still works.

    """

    def getattr(self, obj: typing.Any, attribute: str) -> typing.Any:
        # Check that the item exists before looking it up, rather than catching
        # LookupError or TypeError from obj[attribute]: the lookup also resolves the
        # item, so catching would hide an error raised while resolving it.
        if _is_unresolved_container(obj) and _has_item(obj, attribute):
            return obj[attribute]
        return super().getattr(obj, attribute)

    def getitem(self, obj: typing.Any, argument: typing.Any) -> typing.Any:
        # Override Jinja's getitem for the same reason as getattr: it catches lookup
        # and type errors from obj[argument], hiding errors raised while resolving
        # the item.
        if _is_unresolved_container(obj) and _has_item(obj, argument):
            return obj[argument]
        return super().getitem(obj, argument)


def _is_unresolved_container(obj: typing.Any) -> bool:
    return isinstance(obj, (_UnresolvedDict, _UnresolvedList, _UnresolvedFunctionCall))


def _has_item(container: typing.Any, key: typing.Any) -> bool:
    """Whether the container has an item at key, found without resolving the item.

    ``container[key]`` resolves the item too, so catching a KeyError or IndexError
    from it can't tell a missing key from an error raised while resolving the
    value. Code that looks up a name checks with this first, then looks it up
    without catching anything, so errors in the value are reported as themselves.

    """
    if isinstance(container, _UnresolvedFunctionCall):
        # a function call (at the root) may evaluate to a plain value, such as the
        # string an __if__ returns; a value has no keys, so nothing is found in it
        node = container.function_node.evaluate()
        if not isinstance(node, (_DictNode, _ListNode)):
            return False
        container = _view(node)
    if isinstance(container, _UnresolvedDict):
        children = container.dict_node.children
    elif isinstance(container, _UnresolvedList):
        # mirrors _UnresolvedList.__getitem__: integer indices in range only
        return isinstance(key, int) and key in range(len(container))
    else:
        children = container
    try:
        return key in children
    except TypeError:  # an unhashable key
        return False


class _UnresolvedDict(_types.UnresolvedDict):
    """Implements UnresolvedDict using a _DictNode as the backing data structure."""

    def __init__(self, dict_node: _DictNode):
        self.dict_node = dict_node

    def __getitem__(
        self, key
    ) -> _UnresolvedDict | _UnresolvedList | _types.Configuration:
        """Access an element in the unresolved dictionary (see _view).

        If the key is not found, a KeyError is raised.

        """
        return _view(self.dict_node.children[key])

    def __len__(self):
        return len(self.dict_node.children)

    def __iter__(self):
        return iter(self.keys())

    def keys(self):
        return self.dict_node.children.keys()

    # Mapping's default `in` looks the value up, which would resolve it, and could
    # even report a circular reference. Checking the keys doesn't resolve anything
    def __contains__(self, key) -> bool:
        return key in self.dict_node.children

    # str() is what ${ d | string } and ${ 'x' ~ d } call; without this it fell
    # back to object's repr, inserting "<..._UnresolvedDict object at 0x...>".
    # Give the text of the plain dict, as for a dict written in the expression.
    # __repr__ is left alone: resolving there would run in debuggers and error
    # messages, where it could raise
    def __str__(self) -> str:
        return str(self.resolve())

    def resolve(self) -> _types.ConfigurationDict:
        """Resolve all values recursively, returning a ConfigurationDict."""
        return self.dict_node.resolve()

    def get_keypath(self, keypath: _types.KeyPath | str) -> _types.Configuration:
        """Resolve the value at the given keypath."""
        return self.dict_node.get_keypath(keypath).resolve()


# _UnresolvedList ----------------------------------------------------------------------


class _UnresolvedList(_types.UnresolvedList):
    """Implements UnresolvedList using a _ListNode as the backing data structure."""

    def __init__(self, list_node: _ListNode):
        self.list_node = list_node

    @typing.overload
    def __getitem__(
        self, ix: int
    ) -> _UnresolvedDict | _UnresolvedList | _types.Configuration: ...

    @typing.overload
    def __getitem__(
        self, ix: slice
    ) -> list[_types.UnresolvedDict | _types.UnresolvedList | _types.Configuration]: ...

    def __getitem__(self, ix):
        """Access an element in the unresolved list (see _view).

        If the index is out of range, an IndexError is raised. A negative index
        counts from the end, and a slice gives a plain list of the elements.

        """
        # a slice gives a list of the elements, each looked up as below (so a
        # container in it stays unresolved), as slicing a list would
        if isinstance(ix, slice):
            return [self[i] for i in range(len(self))[ix]]

        # a negative index counts from the end, as for a list
        if isinstance(ix, int) and -len(self) <= ix < 0:
            ix += len(self)

        if ix not in range(len(self)):
            raise IndexError(ix)

        return _view(self.list_node.children[ix])

    def __iter__(self):
        for i in range(len(self)):
            yield self[i]

    def __len__(self):
        return len(self.list_node.children)

    # Sequence defines no __eq__, so == compared identity and l == [1, 2] was always
    # False (as was a dict holding a list, since Mapping's == compares the values).
    # Compare element by element like a list; an element that is a container is
    # itself unresolved, so nesting works. Like a list, it equals only lists:
    # anything else (a tuple) gets NotImplemented, so Python gives False
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, (list, _types.UnresolvedList)):
            return NotImplemented
        return len(self) == len(other) and list(self) == list(other)

    # for the same reason as _UnresolvedDict.__str__: the text of the plain list,
    # not "<..._UnresolvedList object at 0x...>"
    def __str__(self) -> str:
        return str(self.resolve())

    def resolve(self) -> _types.ConfigurationList:
        """Resolve all values recursively, returning a ConfigurationList."""
        return self.list_node.resolve()

    def get_keypath(self, keypath: _types.KeyPath | str) -> _types.Configuration:
        """Resolve the value at the given keypath."""
        return self.list_node.get_keypath(keypath).resolve()


# _UnresolvedFunctionCall --------------------------------------------------------------


class _UnresolvedFunctionCall(_types.UnresolvedFunctionCall):
    """Implements UnresolvedFunctionCall using _FunctionCallNode."""

    def __init__(self, function_node: _FunctionCallNode):
        self.function_node = function_node

    def __getitem__(
        self, key
    ) -> _UnresolvedDict | _UnresolvedList | _types.Configuration:
        """Attempt to access an element in the result of the unresolved function call.

        This will trigger the evaluation of the function call if it has not already been
        resolved. If the result is a dictionary or list, the key is looked up in that
        collection. If the result is not a dictionary or list, a TypeError is raised.

        """
        # Jinja reads the TypeError as an undefined name
        node = self.function_node.evaluate()
        if isinstance(node, _DictNode):
            return _UnresolvedDict(node)[key]
        if isinstance(node, _ListNode):
            return _UnresolvedList(node)[key]
        raise TypeError("The function call evaluated to a value with no keys.")

    def get_keypath(self, keypath: _types.KeyPath | str) -> _types.Configuration:
        """Resolve the value at the given keypath."""
        return self.function_node.get_keypath(keypath).resolve()


# helpers ------------------------------------------------------------------------------


def _view(
    node: _ConcreteNode,
) -> _UnresolvedDict | _UnresolvedList | _types.Configuration:
    """A node's value as seen through an unresolved container.

    A function call is evaluated first. A dict or list node is wrapped in another
    unresolved container, so that its children are resolved only when accessed; a
    value or template node is resolved.

    """
    if isinstance(node, _FunctionCallNode):
        node = node.evaluate()
    if isinstance(node, _DictNode):
        return _UnresolvedDict(node)
    if isinstance(node, _ListNode):
        return _UnresolvedList(node)
    return node.resolve()


def _make_unresolved_container(
    node: _DictNode | _ListNode | _FunctionCallNode,
) -> _UnresolvedDict | _UnresolvedList | _UnresolvedFunctionCall:
    """Create the correct type of unresolved container to wrap a node."""
    if isinstance(node, _DictNode):
        return _UnresolvedDict(node)
    elif isinstance(node, _ListNode):
        return _UnresolvedList(node)
    else:
        return _UnresolvedFunctionCall(node)


def _get_node_at_keypath(
    node: _DictNode | _ListNode,
    keypath: _types.KeyPath | str,
    cast_key: Callable[[str], Any],
) -> _ConcreteNode:
    """Navigate the node tree and return the node at the given keypath.

    Walks the internal node tree and returns the raw ``_Node`` without resolving it.
    ``_FunctionCallNode`` instances encountered along the path are evaluated so that
    their children can be traversed.

    If there is no node at the keypath, a KeyError is raised.

    """
    if isinstance(keypath, str):
        keypath = tuple(keypath.split("."))

    head_key, *rest = keypath

    # A list index that is out of range or not an integer raises IndexError or
    # ValueError here. Raise KeyError instead, which is what callers such as
    # __splice__ catch to report that the keypath does not exist.
    try:
        child: _ConcreteNode = node.children[cast_key(head_key)]
    except (IndexError, ValueError):
        raise KeyError(head_key) from None

    # if the child is a function call, evaluate it to get the underlying node
    if isinstance(child, _FunctionCallNode):
        child = child.evaluate()

    if not rest:
        return child

    if not isinstance(child, (_DictNode, _ListNode)):
        raise KeyError(head_key)

    return child.get_keypath(tuple(rest))


# node types ===========================================================================
#
# A configuration tree is the internal representation of a configuration. The
# nodes of tree come in four types:
#
#   _ValueNode: a leaf node in the tree that can be resolved into a non-container value,
#       such as an integer. Can reference other ValueNodes.
#
#   _DictNode: an internal node that behaves like a dictionary, mapping keys to child
#       nodes.
#
#   _ListNode: an internal node that behaves like a list, mapping indices to child
#       nodes.
#
#   _FunctionCallNode: a node that represents a function call.
#
#   _TemplateNode: a leaf node representing a template field. Its value is kept as
#       written and resolves to a Template, which is evaluated later.

# _Node ABC ----------------------------------------------------------------------------

type _ConcreteNode = (
    _DictNode | _ListNode | _ValueNode | _FunctionCallNode | _TemplateNode
)


# computing a node's result once ----------------------------------------------------

# a node's result, while it is being computed
_IN_PROGRESS = object()


def _cache_and_detect_cycles[N: _Node, R](method: Callable[[N], R]) -> Callable[[N], R]:
    """Make a node's method compute its result once, and detect circular references.

    The first call runs the method and keeps its result, which later calls return.
    A call made while the method is still running (because computing the result
    needs the result itself) raises a ResolutionError, "Circular reference.", at
    the node's keypath. If the method raises, nothing is kept, so a later call
    runs it again and reports the same error rather than a circular reference.

    The result is kept in the node's ``_cache``, under the method's name. Use
    :func:`_is_in_progress` to ask whether it is running, and :func:`_set_result`
    to give a result without running it.

    """
    name = method.__name__

    @functools.wraps(method)
    def wrapper(node: N) -> R:
        if name in node._cache:
            if node._cache[name] is _IN_PROGRESS:
                raise ResolutionError("Circular reference.", node.keypath)
            return node._cache[name]

        node._cache[name] = _IN_PROGRESS
        try:
            result = method(node)
        except BaseException:
            del node._cache[name]
            raise
        node._cache[name] = result
        return result

    return wrapper


def _is_in_progress(method: Callable[[], object]) -> bool:
    """Whether a node's method, given bound, is running.

    The method must be decorated with :func:`_cache_and_detect_cycles`.

    """
    node = typing.cast(_Node, getattr(method, "__self__"))
    return node._cache.get(method.__name__) is _IN_PROGRESS


def _set_result(method: Callable[[], object], result: object) -> None:
    """Give a node's method, given bound, its result without running it.

    The method must be decorated with :func:`_cache_and_detect_cycles`.

    """
    node = typing.cast(_Node, getattr(method, "__self__"))
    node._cache[method.__name__] = result


def _names_after_the_document(context: _types.ResolutionContext) -> dict[str, Any]:
    """The names looked up after the document: the globals and template parameters.

    The parameters of the templates being evaluated win over the globals: whoever
    calls resolve() may pass globals that a template's author never saw, and the
    template should not break because one shares a parameter's name.

    """
    return {**context.global_variables, **context.template_parameters}


class _Node(abc.ABC):
    """Abstract base class for all nodes in a configuration tree.

    Attributes
    ----------
    keypath : KeyPath
        The keypath to this node in the configuration tree; used in error messages.
    resolution_context : ResolutionContext
        The resolution context (converters, functions, variables, filters, etc.).
    parent : _ConcreteNode | None
        The parent of this node. Can be `None`, in which case this is the root of the
        tree.
    local_variables : Mapping[str, Configuration | UnresolvedDict | UnresolvedList | UnresolvedFunctionCall] | None
        A dictionary of local variables that can be accessed during string
        interpolation. If None, this is made an empty dictionary.

    """

    def __init__(
        self,
        keypath: _types.KeyPath,
        resolution_context: _types.ResolutionContext,
        parent: _ConcreteNode | None = None,
        local_variables: Mapping[str, _types.Configuration] | None = None,
    ):
        self.keypath = keypath
        self.resolution_context = resolution_context
        self.parent = parent

        # the results of the node's _cache_and_detect_cycles methods, by method name
        self._cache: dict[str, Any] = {}

        if local_variables is None:
            self.local_variables: dict[
                str,
                _types.Configuration
                | _types.UnresolvedDict
                | _types.UnresolvedList
                | _types.UnresolvedFunctionCall,
            ] = {}
        else:
            self.local_variables = dict(local_variables)

        # cache the root of the tree
        self._root: _ConcreteNode | None = None

    @property
    def root(self) -> _ConcreteNode:
        """The root of the configuration tree."""
        assert isinstance(
            self, (_DictNode, _ListNode, _ValueNode, _FunctionCallNode, _TemplateNode)
        )
        if self._root is None:
            if self.parent is None:
                self._root = self
            else:
                # recurse up the tree
                self._root = self.parent.root
        return self._root

    @abc.abstractmethod
    def resolve(self) -> _types.Configuration:
        """Recursively resolve the node into a configuration."""

    # name lookup ----------------------------------------------------------------------
    #
    # ${...} references (see _ValueNode._make_custom_jinja_context) and __use__
    # targets (see _look_up_keypath) find names the same way, using these methods.

    def _root_container(
        self,
    ) -> _UnresolvedDict | _UnresolvedList | _UnresolvedFunctionCall | dict[str, Any]:
        """The root of the tree as an unresolved container, for looking up names.

        If the root is a value or template node, the tree is a single isolated node.
        It cannot have in-tree references, because they'd be circular, so an empty
        dict does the job.

        """
        if isinstance(self.root, (_DictNode, _ListNode, _FunctionCallNode)):
            return _make_unresolved_container(self.root)
        return {}

    def _look_up_name(
        self,
        key: str,
        root_container: _UnresolvedDict
        | _UnresolvedList
        | _UnresolvedFunctionCall
        | dict[str, Any],
        global_variables: Mapping[str, Any],
    ) -> Any:
        """Look up a name as seen from this node.

        The name is looked up in the local variables of this node and its ancestors,
        then in the root of the tree, then in ``global_variables`` (which holds the
        parameters of the templates being evaluated too; see
        _names_after_the_document).

        Raises
        ------
        KeyError
            If the name is in none of them.

        """
        try:
            return self.get_local_variable(key)
        except KeyError:
            pass

        # the root is skipped if it is a function call still being evaluated (we
        # are in its input): it has no keys yet, and looking one up would be circular
        root = self.root
        if not (isinstance(root, _FunctionCallNode) and _is_in_progress(root.evaluate)):
            # check before looking up, rather than catching KeyError or IndexError,
            # so that an error raised while resolving the value isn't mistaken for
            # a missing name (see _has_item)
            if _has_item(root_container, key):
                return root_container[key]  # type: ignore[index, call-overload]

        return global_variables[key]

    def get_local_variable(
        self, key: str
    ) -> (
        _types.Configuration
        | _types.UnresolvedDict
        | _types.UnresolvedList
        | _types.UnresolvedFunctionCall
    ):
        """Retrieves the local variable from the node or its ancestors.

        If the local variable is not found, a KeyError is raised. The first node to have
        the local variable is the one that provides the value, and the search is
        bottom-up.

        Parameters
        ----------
        key: str

        Returns
        -------
        The value of the local variable.

        """
        if key in self.local_variables:
            return self.local_variables[key]
        elif self.parent is not None:
            return self.parent.get_local_variable(key)
        else:
            raise KeyError(key)


# _DictNode ----------------------------------------------------------------------------


class _DictNode(_Node):
    """Represents an internal dictionary node in a configuration tree.

    Building the node builds its children, and checks the dictionary against the
    schema while doing so: a required key must be present, a missing optional key
    gets its default (if it has one), and an extra key is allowed only if the schema
    has an "extra_keys_schema". This is done here rather than in .resolve() because
    building the children already needs to know which keys are missing.

    Attributes
    ----------
    children : dict[str, _ConcreteNode]
        A dictionary of child nodes.

    """

    def __init__(
        self,
        dct: _types.ConfigurationDict,
        schema: _types.Schema,
        keypath: _types.KeyPath,
        resolution_context: _types.ResolutionContext,
        parent: _ConcreteNode | None = None,
        local_variables: Mapping[str, _types.Configuration] | None = None,
        mode: ResolutionMode = ResolutionMode.STANDARD,
    ):
        super().__init__(keypath, resolution_context, parent, local_variables)
        self.children: dict[str, _ConcreteNode] = {}

        def add_child(
            key: str,
            value: _types.Configuration,
            key_schema: _types.Schema | _types.DynamicSchema,
        ) -> None:
            self.children[key] = make_node(
                value, key_schema, resolution_context, self, keypath + (key,), mode=mode
            )

        required_keys = schema.get("required_keys", {})
        for key, key_schema in required_keys.items():
            if key not in dct:
                raise ResolutionError(
                    f'Dictionary is missing required key "{key}".', keypath + (key,)
                )

            # make_node validates a dynamic schema's result with defaults allowed, as
            # for an optional key. A required key is never missing, so a default for
            # it is a mistake, and is rejected here as it would be in a static schema
            if callable(key_schema):
                key_schema = _call_dynamic_schema(
                    key_schema,
                    dct[key],
                    keypath + (key,),
                    resolution_context,
                    allow_default=False,
                )
            add_child(key, dct[key], key_schema)

        optional_keys = schema.get("optional_keys", {})
        for key, key_schema in optional_keys.items():
            if key in dct:
                add_child(key, dct[key], key_schema)
                continue

            # the key is missing; resolve a dynamic schema before checking for a default
            if callable(key_schema):
                key_schema = _call_dynamic_schema(
                    key_schema,
                    None,
                    keypath + (key,),
                    resolution_context,
                    allow_default=True,
                )
            if "default" not in key_schema:
                continue

            default = key_schema["default"]
            if key_schema.get("type") == "template" and default is not None:
                # the default of a template field is the template's value as
                # written, without a __template__ wrapper
                self.children[key] = _TemplateNode(
                    default, key_schema, keypath + (key,), resolution_context, self
                )
            else:
                add_child(key, default, key_schema)

        # a list, not a set difference, so that extra keys keep their input order
        extra_keys = [
            key for key in dct if key not in required_keys and key not in optional_keys
        ]
        if extra_keys and "extra_keys_schema" not in schema:
            key = extra_keys[0]
            raise ResolutionError(
                f'Dictionary contains unexpected extra key "{key}".', keypath + (key,)
            )
        for key in extra_keys:
            add_child(key, dct[key], schema["extra_keys_schema"])

    def resolve(self) -> _types.ConfigurationDict:
        """Recursively resolve the _DictNode into a ConfigurationDict."""
        return {key: child_node.resolve() for key, child_node in self.children.items()}

    def get_keypath(self, keypath: _types.KeyPath | str) -> _ConcreteNode:
        """Return the node at the given keypath."""
        return _get_node_at_keypath(self, keypath, str)


# _ListNode ----------------------------------------------------------------------------


class _ListNode(_Node):
    """Represents an internal list node in a configuration tree.

    Attributes
    ----------
    children : list[_ConcreteNode]
        A list of the node's children.

    """

    def __init__(
        self,
        lst: _types.ConfigurationList,
        schema: _types.Schema,
        keypath: _types.KeyPath,
        resolution_context: _types.ResolutionContext,
        parent: _ConcreteNode | None = None,
        local_variables: Mapping[str, _types.Configuration] | None = None,
        mode: ResolutionMode = ResolutionMode.STANDARD,
    ):
        super().__init__(keypath, resolution_context, parent, local_variables)
        self.children: list[_ConcreteNode] = [
            make_node(
                value,
                schema["element_schema"],
                resolution_context,
                self,
                keypath + (str(i),),
                mode=mode,
            )
            for i, value in enumerate(lst)
        ]

    def resolve(self) -> _types.ConfigurationList:
        """Recursively resolve the _ListNode into a ConfigurationList."""
        return [child_node.resolve() for child_node in self.children]

    def get_keypath(self, keypath: _types.KeyPath | str) -> _ConcreteNode:
        """Return the node at the given keypath."""
        return _get_node_at_keypath(self, keypath, int)


# _ValueNode ---------------------------------------------------------------------------


class _ValueNode(_Node):
    """Represents a leaf of the configuration tree.

    Attributes
    ----------
    value : ConfigurationValue
        The "raw" value of the leaf node as it appeared in the configuration.
    type_ : str
        The type the value is converted to once interpolated: the schema's "type",
        which names a converter in the resolution context (or is "any").
    mode : ResolutionMode
        The resolution mode governing string interpolation for this node.

    """

    def __init__(
        self,
        value: _types.ConfigurationValue,
        type_: str,
        keypath: _types.KeyPath,
        resolution_context: _types.ResolutionContext,
        parent: _ConcreteNode | None = None,
        local_variables: Mapping[str, _types.Configuration] | None = None,
        mode: ResolutionMode = ResolutionMode.STANDARD,
    ):
        super().__init__(keypath, resolution_context, parent, local_variables)
        self.value = value
        self.type_ = type_
        self.mode = mode

    @_cache_and_detect_cycles
    def resolve(self) -> _types.ConfigurationValue:
        """Resolve the leaf's value by 1) interpolating and 2) converting.

        This node's ``mode`` attribute determines how string interpolation is performed:

        - ``RAW``: no interpolation; the value is passed directly to conversion.
        - ``STANDARD``: a single pass of ``${...}`` interpolation.
        - ``FULL``: repeated interpolation until no ``${...}`` references remain.

        After interpolation, the value is converted to the type specified by the
        schema (e.g., ``int``, ``date``).

        Returns
        -------
        The resolved value.

        """
        # a smartconfig error other than a ResolutionError (a converter's
        # ConversionError, say) is reported at this value's keypath
        try:
            # Step 1: interpolate the string (if it's a string and mode is not RAW)
            value: _types.ConfigurationValue = self.value
            if isinstance(value, str) and self.mode != ResolutionMode.RAW:
                value = self._interpolate(value, full=self.mode == ResolutionMode.FULL)

            # Step 2: convert the value to the expected type. None is never
            # converted: make_node gives a None value the "any" type, which _convert
            # passes through
            return self._convert(value)
        except ResolutionError:
            raise
        except Error as exc:
            raise ResolutionError(str(exc), self.keypath) from exc

    def _make_custom_jinja_context(self) -> type[jinja2.runtime.Context]:
        """This creates a custom Jinja2 context for string interpolation.

        We create this custom context to carefully control how Jinja2 resolves
        references. The typical way to provide template variables to Jinja2 is to pass a
        dictionary-like object to the .render() method. This object is used by Jinja to
        create a "context". However, in creating the context itself, Jinja immediately
        accesses the values in the top-level of the dictionary. This is problematic
        because the values in the dictionary may be references to other parts of the
        configuration. If Jinja2 accesses these values before the references are
        resolved, it can create circular dependencies.

        To avoid this, we create a custom context class that only resolves references
        when they are accessed during interpolation, and not during the creation of the
        context. The root of the configuration is stored in a _UnresolvedDict,
        _UnresolvedList, or _UnresolvedFunctionCall, which are "lazy" containers that
        resolve their contents only when accessed.

        This custom context also specifies the variable lookup order. First, a key is
        looked up in the local variables. If it is not found, it looked up in the
        unresolved container representing the root of the configuration tree. Following
        this, the key is looked up in the global variables. Finally, if a key was not
        found in any of these places, Jinja2 will fall back to the default behavior of
        looking up the key in the template variables.

        """
        root_container = self._root_container()

        # save a copy of self, because we shadow `self` in `resolve_or_missing` below
        this_node = self

        # the globals and template parameters, in a new dict so that the root node
        # can be inserted, if requested, without modifying them
        context = self.resolution_context
        global_variables = _names_after_the_document(context)
        if context.inject_root_as is not None:
            global_variables[context.inject_root_as] = root_container

        class CustomContext(jinja2.runtime.Context):
            def resolve_or_missing(self, key):
                # first try local variables, then the root, then the globals
                try:
                    return this_node._look_up_name(
                        key, root_container, global_variables
                    )
                except KeyError:
                    pass
                # Jinja looks up every name up front, even in untaken branches, so
                # the error (of any kind) is raised only if the name is used. An
                # unused name loses nothing: its value is resolved on its own anyway
                except ResolutionError as exc:
                    return _DeferredError(key, exc)

                # finally, try jinja's default behavior, including jinja builtins
                result = super().resolve_or_missing(key)
                if result is jinja2.utils.missing:
                    return _UndefinedName(key, available_names())
                return result

        def available_names() -> tuple[str, ...]:
            """The names a reference could use here, in lookup order."""
            names: list[str] = []
            node: _Node | None = this_node
            while node is not None:
                names += node.local_variables
                node = node.parent
            if isinstance(root_container, _UnresolvedDict):
                names += [str(k) for k in root_container.dict_node.children]
            names += global_variables
            return tuple(dict.fromkeys(names))

        return CustomContext

    def _interpolate(self, s: str, full=False) -> str:
        """Replace ``${...}`` references in the string with their resolved values.

        Uses the custom Jinja2 context built by ``_make_custom_jinja_context`` to
        control variable lookup order (local variables, then root, then globals).

        Parameters
        ----------
        s : str
            A configuration string with references to other values.
        full : bool
            If True, this will continue interpolating until the string no longer
            changes. Default: False.

        Returns
        -------
        The interpolated string.

        """
        # Jinja changes text even where there is nothing to interpolate (it
        # converts line endings to \n and drops a trailing newline), so a string
        # with no template syntax is returned exactly as written
        if not any(marker in s for marker in ("${", "{%", "{#")):
            return s

        environment = _Environment(
            variable_start_string="${",
            variable_end_string="}",
            # without this, Jinja drops a single trailing newline from the result
            keep_trailing_newline=True,
            # inserting None, a dict or a list into a string is an error
            finalize=_refuse_uninsertable,
        )

        # create a custom jinja context for resolving references. This will first look
        # up keys in the local variables, and then in the root of the configuration
        # tree, and finally in the global variables. See the
        # _make_custom_jinja_context() method for more information.
        environment.context_class = self._make_custom_jinja_context()

        # a name whose value failed to resolve is a _DeferredError, which tests and
        # filters would take for a missing name; these raise its error instead
        environment.tests.update(_JINJA_TESTS)
        environment.filters.update(_JINJA_FILTERS)

        # register the custom filters
        environment.filters.update(
            {
                name: _raising_deferred_errors(f)
                for name, f in self.resolution_context.filters.items()
            }
        )

        # json can't serialize the unresolved containers, so tojson resolves them to
        # plain data first (sort_keys is Jinja's default for tojson)
        environment.policies["json.dumps_kwargs"] = {
            "sort_keys": True,
            "default": _resolve_for_json,
        }

        # make undefined references raise an error
        environment.undefined = StrictUndefined

        try:
            template = environment.from_string(s)
        except jinja2.exceptions.TemplateSyntaxError as exc:
            raise ResolutionError(
                f'Invalid template "{s}": {exc.message}', self.keypath
            ) from None

        try:
            result = template.render()
        except _UndefinedNameJinjaError as exc:
            raise UndefinedNameError(
                exc.message or "", self.keypath, exc.name, exc.available
            ) from None
        except jinja2.exceptions.UndefinedError as exc:
            raise ResolutionError(str(exc), self.keypath)
        except _Uninsertable as exc:
            raise ResolutionError(exc.message, self.keypath) from None
        except _InsertedNone:
            raise ResolutionError(
                f'A ${{ ... }} in "{s}" is None, which can\'t be inserted into a '
                "string. To copy the None itself, use __splice__; to insert something "
                "else, give a default, as in ${ value or '' }.",
                self.keypath,
            ) from None
        # an exception raised by the expression or a filter in it gets this string's
        # keypath. One from a value it refers to was already wrapped where it was
        # raised, so it is a ResolutionError by now and passes through unchanged
        except _NOT_WRAPPED:
            raise
        except Exception as exc:
            raise _wrapped(exc, self.keypath) from exc

        if full and result != s:
            # if the string changed, we need to interpolate again
            return self._interpolate(result, full=True)
        else:
            return result

    def _convert(self, value: _types.ConfigurationValue) -> _types.ConfigurationValue:
        """Convert the configuration value into this node's type."""
        # "any" is a built-in type, like "dict": validate_schema accepts it whatever
        # the converters are, so it must not depend on one here either
        if self.type_ == "any":
            return value

        try:
            converter = self.resolution_context.converters[self.type_]
        except KeyError:
            raise ResolutionError(
                f'No converter provided for type: "{self.type_}".', self.keypath
            )

        return converter(value)


# _FunctionCallNode --------------------------------------------------------------------


class _FunctionCallNode(_Node):
    """Represents a function call in the configuration tree.

    Attributes
    ----------
    function : _types.Function
        The function being called.
    input : _types.Configuration
        The input to the function.
    schema : _types.Schema
        The schema for the function's output.
    mode : ResolutionMode
        The resolution mode propagated to child nodes built from the function's
        result.

    """

    def __init__(
        self,
        keypath: _types.KeyPath,
        resolution_context: _types.ResolutionContext,
        function: _types.Function,
        input: _types.Configuration,
        schema: _types.Schema,
        parent: _ConcreteNode | None = None,
        local_variables: Mapping[str, _types.Configuration] | None = None,
        mode: ResolutionMode = ResolutionMode.STANDARD,
    ):
        super().__init__(keypath, resolution_context, parent, local_variables)
        self.schema = schema
        self.function = function
        self.input = input
        self.mode = mode

    def _make_resolver(self) -> _types.Resolver:
        """Make a "resolver" function that can be used by functions to resolve configs.

        This enables advanced use cases like using a function to implement for-loops.
        This function satisfies the _types.Resolver protocol.

        """

        def resolver(
            configuration: _types.Configuration,
            schema: _types.Schema | None = None,
            local_variables: Mapping[str, _types.Configuration] | None = None,
            relative_keypath: _types.KeyPath = (),
        ) -> _types.Configuration:
            if schema is None:
                schema = self.schema
            node = make_node(
                configuration,
                schema,
                self.resolution_context,
                parent=self,
                # relative_keypath places it under the call, for error messages
                keypath=self.keypath + tuple(relative_keypath),
                local_variables=local_variables,
                mode=self.mode,
            )
            return node.resolve()

        return resolver

    @_cache_and_detect_cycles
    def evaluate(self) -> _DictNode | _ListNode | _ValueNode | _TemplateNode:
        """Evaluate the function, returning a _DictNode, _ListNode, or _ValueNode.

        This operates recursively, so that if the function returns a ConfigurationDict
        representing another function call, that child function call is also evaluated,
        and so on.

        """
        # NOTE: Although the public interface says functions return Configuration,
        # internal (core) functions are allowed to return node types directly
        # (_DictNode, _ListNode, _ValueNode, _FunctionCallNode). This bypasses
        # make_node and gives core functions precise control over how the result is
        # built (e.g., choosing the resolution mode).

        # if the function wants its input to be resolved, we resolve it by creating
        # a node out of its input configuration and resolving it
        if self.function.resolve_input:
            input_node = make_node(
                self.input,
                {"type": "any"},
                self.resolution_context,
                parent=self,
                keypath=self.keypath,
                mode=self.mode,
            )
            input = input_node.resolve()
        else:
            input = self.input

        # root can't be a value node, because we're calling this from a
        # function node that is either 1) the root, or 2) the successor of a root
        # that is a container node
        assert isinstance(self.root, (_DictNode, _ListNode, _FunctionCallNode))
        root = _make_unresolved_container(self.root)

        # create the resolver function that the function can use to resolve
        # configurations
        resolver = self._make_resolver()

        args = _types.FunctionArgs(
            input,
            root,
            self.keypath,
            self.resolution_context,
            resolver,
            self.schema,
            _root_node=self.root,
            _function_call_node=self,
        )

        # evaluate the function itself. An exception it raises that isn't
        # smartconfig's gets the call's keypath, so that it is reported where the
        # function was called, not wherever the call happened to be referenced from
        try:
            output = self.function(args)
        except _NOT_WRAPPED:
            raise
        except Exception as exc:
            raise _wrapped(exc, self.keypath) from exc

        # see the comment at the top of this method: privately, functions are allowed to
        # return node types directly, in which case we skip make_node and use the
        # returned node as the result directly; publicly, functions should return
        # Configuration, in which case we pass the output through make_node to
        # construct the appropriate node type
        if isinstance(
            output,
            (_DictNode, _ListNode, _ValueNode, _FunctionCallNode, _TemplateNode),
        ):
            result = output
        else:
            # By default the output is configuration, resolved in this call's mode.
            # With resolve_output=False it is finished data: RAW mode converts it to
            # the schema without interpolating it or evaluating function calls in it.
            if self.function.resolve_output:
                output_mode = self.mode
            else:
                output_mode = ResolutionMode.RAW
            result = make_node(
                output,
                self.schema,
                self.resolution_context,
                parent=self,
                keypath=self.keypath,
                mode=output_mode,
            )

        # the result may be a function call itself, in which case we need to evaluate it
        if isinstance(result, _FunctionCallNode):
            # this will evaluate the function call recursively
            result = result.evaluate()

        return result

    def resolve(self) -> _types.Configuration:
        """Evaluate the function node and return the resulting Configuration.

        This amounts to evaluating the function and resolving the resulting node.

        """
        return self.evaluate().resolve()

    def get_keypath(self, keypath: _types.KeyPath | str) -> _ConcreteNode:
        """Evaluate the function, then return the node at the given keypath."""
        node = self.evaluate()
        if isinstance(node, (_DictNode, _ListNode)):
            return node.get_keypath(keypath)
        raise KeyError(keypath)


# _TemplateNode ------------------------------------------------------------------------


@contextlib.contextmanager
def reporting_recursion_errors() -> typing.Iterator[None]:
    """Report a RecursionError raised inside the block as a ResolutionError.

    Checking the schema, building the tree and resolving it are all recursive: a
    node's children, and the values its references point to, are handled inside
    it. A configuration or schema nested deeply enough (a few hundred levels, with
    Python's default limit), or a long enough chain of references or of function
    calls that return function calls, exhausts the stack and raises a bare
    RecursionError, with no explanation.

    """
    try:
        yield
    except RecursionError as exc:
        # chained, so that if smartconfig itself recursed forever, the traceback
        # still shows where
        raise ResolutionError(
            "The configuration is nested too deeply to resolve, or has a chain of "
            "references or of function calls that is too long (or never ends).",
            (),
        ) from exc


def check_keys_are_not_parameters(
    tree: _ConcreteNode, parameters: Iterable[str], outer_parameters: Iterable[str]
) -> None:
    """Raise if a top-level key of a template's tree is named like a parameter.

    A template's top-level keys can be referenced by name, like its parameters and
    its outer parameters (those of the templates around it), so ``${ name }``
    would be ambiguous if both a key and a parameter were called ``name``. Nested
    keys are not names, so they are not checked.

    Raises
    ------
    ResolutionError
        At the keypath of the first key named like a parameter.

    """
    if not isinstance(tree, _DictNode):
        return
    for key, child in tree.children.items():
        if key in parameters:
            raise ResolutionError(
                f'"{key}" is both a key of this template and one of its '
                "parameters. A template's keys can be referenced by name, like its "
                "parameters, so the name is ambiguous. Rename the key or the "
                "parameter.",
                child.keypath,
            )
        if key in outer_parameters:
            raise ResolutionError(
                f'"{key}" is both a key of this template and a parameter of a '
                "template around it. A template's keys can be referenced by name, "
                "like the parameters it sees, so the name is ambiguous. Rename the "
                "key or the parameter.",
                child.keypath,
            )


def _is_template_function(function: _types.Function) -> bool:
    """Whether ``function`` is the core ``template`` function, whatever its name."""
    # imported here: _core_functions imports this module
    from ._core_functions import _template

    return function is _template


def _is_use_function(function: _types.Function) -> bool:
    """Whether ``function`` is the core ``use`` function, whatever its name."""
    from ._core_functions import _use

    return function is _use


def _is_raw_function(function: _types.Function) -> bool:
    """Whether ``function`` is the core ``raw`` function, whatever its name."""
    from ._core_functions import _raw

    return function is _raw


def _look_up_keypath(node: _ConcreteNode, keypath: str) -> Any:
    """The value at a dotted keypath, found as ``${...}`` would find it from ``node``.

    The first part of the keypath is looked up as a name in a ``${...}`` reference
    is: in the local variables, then the root of the tree, then the global variables
    (including the root, under ``inject_root_as``). Each later part is looked up as
    Jinja looks up ``.part``: a container's keys first, then Python attributes. A
    part that is a number is also tried as a list index. So ``__use__: "a.b.0"``
    finds whatever ``${ a.b.0 }`` would.

    Raises
    ------
    KeyError
        If no value is found.

    """
    first, *rest = keypath.split(".")

    context = node.resolution_context
    root_container = node._root_container()
    global_variables = _names_after_the_document(context)
    if context.inject_root_as is not None:
        global_variables[context.inject_root_as] = root_container

    value = node._look_up_name(first, root_container, global_variables)

    environment = _Environment()
    for part in rest:
        found = jinja2.Undefined()
        if part.isdigit():
            found = environment.getitem(value, int(part))
        if isinstance(found, jinja2.Undefined):
            found = environment.getattr(value, part)
        if isinstance(found, jinja2.Undefined):
            raise KeyError(keypath)
        value = found

    return value


def _expand_use(
    use_input: _types.Configuration, node: _ConcreteNode, keypath: _types.KeyPath
) -> _types.Configuration:
    """The value that a ``__use__`` stands for: its target's source, as written.

    ``use_input`` is the input of the ``__use__`` call. It takes one of two forms:

    - a keypath string naming the target, as in ``{"__use__": "a.b"}``;
    - a dict with a ``"template"`` key (the target's keypath) and an optional
      ``"overrides"`` key (a dict), as in
      ``{"__use__": {"template": "a.b", "overrides": {...}}}``.

    The target is looked up from ``node`` as a ``${...}`` reference would be (see
    _look_up_keypath), so it can be in the document or in a global variable. It
    must be a :class:`Template`. Its source is copied and the overrides, if any, are
    deep-merged on top of the copy. Nothing is interpolated: the source and the
    overrides are both used as written.

    Raises
    ------
    ResolutionError
        If the input is malformed, the target does not exist or is not a template,
        or overrides are given for a template that is not written as a dict (or is
        written as a function call).

    """
    # parse the input: a keypath string, or a dict with "template" and "overrides"
    if isinstance(use_input, str):
        target = use_input
        overrides = None
    elif isinstance(use_input, dict):
        if "template" not in use_input:
            raise ResolutionError(
                "Dict input to 'use' must contain a 'template' key.", keypath
            )
        target_ = use_input["template"]
        if not isinstance(target_, str):
            raise ResolutionError(
                "The 'template' value in 'use' must be a string.", keypath
            )
        target = target_
        overrides = use_input.get("overrides")
        if overrides is not None and not isinstance(overrides, dict):
            raise ResolutionError(
                "The 'overrides' value in 'use' must be a dictionary.", keypath
            )
        extra = set(use_input.keys()) - {"template", "overrides"}
        if extra:
            raise ResolutionError(f"Unexpected keys in 'use': {extra}.", keypath)
    else:
        raise ResolutionError(
            "Input to 'use' must be a string or a dictionary.", keypath
        )

    # look up the target, as a ${...} reference would be
    try:
        resolved = _look_up_keypath(node, target)
    except KeyError:
        raise ResolutionError(f"Keypath '{target}' does not exist.", keypath)

    if not isinstance(resolved, Template):
        raise ResolutionError(
            "The target of 'use' must be a template (written with __template__).",
            keypath,
        )

    # copy the template's source and merge the overrides on top of it
    value = copy.deepcopy(resolved.source)
    if overrides is not None:
        if not isinstance(value, dict):
            raise ResolutionError(
                "Overrides can only be applied when the template is written as a "
                "dictionary.",
                keypath,
            )

        # a template written as a function call is a dict too, but merging into it
        # would add keys to the call, not to the dict it makes. An invalid call
        # (ValueError) is call-shaped as well, so it is rejected the same way
        context = node.resolution_context
        try:
            is_call = (
                context.check_for_function_call(value, context.functions) is not None
            )
        except ValueError:
            is_call = True
        if is_call:
            raise ResolutionError(
                "Overrides can only be applied when the template is written as a "
                "dictionary, not a function call.",
                keypath,
            )

        assert isinstance(overrides, dict)  # checked when the input was parsed
        value = deep_update([value, overrides])

    return value


class _TemplateNode(_Node):
    """Represents a template field in the configuration tree.

    The value of a template field is not resolved; it is kept as written and the node
    resolves to a :class:`Template`. Like a _ValueNode, the node is resolved lazily
    (and the result cached).

    Attributes
    ----------
    value : Configuration
        The template's value as written (without the ``__template__`` wrapper).
    inner_schema : Schema | DynamicSchema
        The schema of the template's value once evaluated: the ``"schema"`` of the
        template schema (``{"type": "template", ...}``) it is built with.
    parameters : tuple[str, ...]
        The template field's parameters: the names given each time it is evaluated.
    outer_parameters : dict[str, Any]
        The outer parameters of a Template passed in, which it keeps when it is
        rebuilt here. The outer parameters of the evaluation the node is resolved
        in (if any) are added to them.

    """

    def __init__(
        self,
        value: _types.Configuration,
        template_schema: _types.Schema,
        keypath: _types.KeyPath,
        resolution_context: _types.ResolutionContext,
        parent: _ConcreteNode | None = None,
        local_variables: Mapping[str, _types.Configuration] | None = None,
        outer_parameters: Mapping[str, Any] | None = None,
    ):
        super().__init__(keypath, resolution_context, parent, local_variables)
        self.value = value
        self.outer_parameters = dict(outer_parameters or {})
        # every template schema was validated (by resolve(), Template, or when a
        # dynamic schema returned it), so it has both keys
        self.inner_schema = template_schema["schema"]
        self.parameters = tuple(template_schema["parameters"])

    @_cache_and_detect_cycles
    def resolve(self) -> Template:
        """Expand, check and build (once) the Template for this field.

        Raises
        ------
        ResolutionError
            If a parameter is named like a parameter of a template around this
            one, if the value's structure doesn't match the inner schema, or if a
            template inside it fails these checks.

        """
        context = self.resolution_context

        # the names this template sees from the templates around it: the
        # parameters of the evaluation it is made in, and those that a Template
        # passed in carries already
        outer = dict(context.template_parameters)
        for name, value in self.outer_parameters.items():
            if name in outer:
                raise ResolutionError(
                    f'"{name}" is a parameter of a template around this one, and '
                    "this template already carries a value for it. Rename one of "
                    "them.",
                    self.keypath,
                )
            outer[name] = value

        # an outer parameter is a name in this template too, so a parameter of the
        # same name would make ${ name } ambiguous
        for name in self.parameters:
            if name in outer:
                raise ResolutionError(
                    f'"{name}" is a parameter of this template and of a template '
                    "around it. A template inside a template sees the parameters of "
                    "the templates around it, so the name is ambiguous. Rename one "
                    "of them.",
                    self.keypath,
                )

        # replace every __use__ in the value with the value it stands for, so
        # that the template's source does not depend on the rest of the document
        expanded: set[_types.KeyPath] = set()
        self.value = self._expand_uses(self.value, self.keypath, expanded)

        # check the structure of the value as written: building the tree raises
        # structure errors; it is walked but never resolved, except for the
        # templates inside it, which are checked in turn. This template's
        # parameters are names in the tree, as when it is evaluated, so that a
        # template inside it is checked against them. Their values aren't known
        # yet, so they are None; the Templates made in the tree are discarded
        names = {**outer, **dict.fromkeys(self.parameters)}
        tree_context = dataclasses.replace(context, template_parameters=names)
        try:
            tree = make_node(
                self.value, self.inner_schema, tree_context, keypath=self.keypath
            )
            self._check(tree)
        except TemplateRequiredError as exc:
            # a __use__ that was the whole value of a template field inside this
            # template was replaced by the value it copies, without a wrapper. Say
            # so, rather than asking for a wrapper that the user did write
            if exc.keypath not in expanded:
                raise
            raise TemplateRequiredError(
                "This field is a template inside a template, so a __use__ here is "
                "replaced by the value it copies, which leaves the field without "
                'its wrapper. Write it as {"__template__": {"__use__": ...}}.',
                exc.keypath,
                exc.parameters,
            ) from None

        # report a key named like a parameter now, when the configuration is
        # resolved, rather than only when the program evaluates the template
        check_keys_are_not_parameters(tree, self.parameters, outer)

        # the context is handed over whole, so that the Template evaluates with
        # every option of this resolve() without listing them here
        return Template._from_context(
            self.value,
            self.inner_schema,
            self.parameters,
            self.keypath,
            context,
            outer,
        )

    def _expand_uses(
        self,
        value: _types.Configuration,
        keypath: _types.KeyPath,
        expanded: set[_types.KeyPath],
    ) -> _types.Configuration:
        """The value with each ``__use__`` replaced by the value it stands for.

        Every dict and list is visited, including the inputs of other function
        calls, except the input of ``__raw__``, which is kept as written. The
        target template's own ``__use__`` calls were already expanded
        when that template was resolved. The keypath of each ``__use__`` replaced
        is added to ``expanded``.

        """
        if isinstance(value, list):
            return [
                self._expand_uses(item, keypath + (str(i),), expanded)
                for i, item in enumerate(value)
            ]
        if not isinstance(value, dict):
            return value

        # at this point, value is a dict. It is either a function call (a __use__ or
        # some other function) or an ordinary dict configuration
        context = self.resolution_context
        try:
            call = context.check_for_function_call(value, context.functions)
        except ValueError:
            # an invalid call is reported when the tree is built
            call = None
        if call is not None and _is_use_function(call[0]):
            # a __use__ call: replace it with the value it stands for
            expanded.add(keypath)
            return _expand_use(call[1], self, keypath)
        if call is not None and _is_raw_function(call[0]):
            # everything under __raw__ is data, so a __use__ in it is kept as written
            return value

        # an ordinary dict, or a call to a function other than __use__ (whose input
        # is a dict too): expand the __use__ calls inside each value
        return {
            k: self._expand_uses(v, keypath + (k,), expanded) for k, v in value.items()
        }

    def _check(self, node: _ConcreteNode) -> None:
        """Check the templates inside a tree built from this template's value.

        The tree is walked without resolving it. Each template in it is resolved,
        which checks its value in turn: one written with ``__template__`` (whose
        function only wraps its input, so it is safe to call now), a default, or a
        Template passed in. Other function calls are not evaluated, and their
        inputs are not walked, so a template one makes is checked when this
        template is evaluated.

        Raises
        ------
        UnexpectedTemplateError
            If a ``__template__`` wrapper is on a field that is not a template
            (nor ``any``). Its ``enclosing`` is this template's keypath.

        """
        if isinstance(node, _DictNode):
            for child in node.children.values():
                self._check(child)
        elif isinstance(node, _ListNode):
            for child in node.children:
                self._check(child)
        elif isinstance(node, _TemplateNode):
            node.resolve()
        elif isinstance(node, _FunctionCallNode) and _is_template_function(
            node.function
        ):
            try:
                node.resolve()
            except UnexpectedTemplateError as exc:
                # the wrapper is on a field that is evaluated now. The error from a
                # template further in already names the template it is in
                if exc.enclosing is not None:
                    raise
                raise UnexpectedTemplateError(
                    exc.reason, exc.keypath, self.keypath
                ) from None


# make_node() ==========================================================================


def make_node(
    cfg: _types.Configuration,
    schema: _types.Schema | _types.DynamicSchema,
    resolution_context: _types.ResolutionContext,
    parent: _ConcreteNode | None = None,
    keypath: _types.KeyPath = tuple(),
    local_variables: Mapping[str, _types.Configuration] | None = None,
    mode: ResolutionMode = ResolutionMode.STANDARD,
) -> _ConcreteNode:
    """Recursively constructs a configuration tree from a configuration.

    The configuration can be a dictionary, list, or a non-container type. In any case,
    the provided schema must match the type of the configuration; for example, if the
    configuration is a dictionary, the schema must be a dict schema.

    A function call node is created if ``resolution_context.check_for_function_call``
    recognises the dictionary as a function call. In this case, the schema is used to
    validate the output of the function.

    Parameters
    ----------
    cfg
        A dictionary, list, or non-container type representing the "raw", unresolved
        configuration.
    schema
        A schema dictionary, or a dynamic schema function, describing the types of the
        configuration tree nodes.
    resolution_context
        The resolution context (converters, functions, variables, filters, etc.).
    parent
        The parent node of the node being built. Can be `None`.
    keypath
        The keypath to this node in the configuration tree.
    local_variables
        Local variables available during string interpolation within this
        node's subtree. Defaults to `None`.
    mode
        The resolution mode governing string interpolation for the resulting
        node and its children.

    Returns
    -------
    _ConcreteNode
        The root node of the configuration tree.

    """
    # In some instances, the provided configuration is an UnresolvedDict or
    # UnresolvedList; for example, when a function returns `args.root["a"]`. The code
    # below wouldn't recognize it as a dict or list, so it would be treated as a single
    # value, and the result would contain an _UnresolvedDict object instead of a dict.
    # Resolving it gives a plain dict or list. After that, its values are already
    # resolved, so the node is built in RAW mode, which converts the values without
    # interpolating them a second time.
    if isinstance(cfg, (_UnresolvedDict, _UnresolvedList)):
        cfg = cfg.resolve()
        mode = ResolutionMode.RAW

    if callable(schema):
        # dynamic schema: call the function to get the actual schema
        schema = _call_dynamic_schema(
            schema, cfg, keypath, resolution_context, allow_default=True
        )

    if cfg is None:
        # "any" accepts None unless the schema says explicitly that it isn't
        # nullable; other types accept it only if they are nullable
        if schema.get("nullable", schema.get("type") == "any"):
            return _ValueNode(
                None, "any", keypath, resolution_context, parent, local_variables, mode
            )
        else:
            raise ResolutionError("Unexpectedly null.", keypath)

    # keys must be strings: keypaths and ${...} references name keys, and checking
    # for a function call reads them as strings. YAML reads "2: y" as the key 2.
    # Checked here, before the function-call checks below, so every dict is covered
    if isinstance(cfg, dict):
        for key in cfg:
            if not isinstance(key, str):
                raise ResolutionError(
                    f"A key must be a string, but this key is {type(key).__name__} "
                    f"{key!r}.",
                    keypath + (str(key),),
                )

    # a dict may be a function call, except in RAW mode (under __raw__), where
    # everything is data. On a template field, the call's function is given the
    # template schema: __template__ and __use__ return a _TemplateNode for it, and
    # any other function's result is built under the template schema in turn
    if isinstance(cfg, dict) and mode != ResolutionMode.RAW:
        try:
            call = resolution_context.check_for_function_call(
                cfg, resolution_context.functions
            )
        except ValueError as exc:
            raise ResolutionError(f"Invalid function call: {exc}", keypath)
        if call is not None:
            function, input = call
            return _FunctionCallNode(
                keypath,
                resolution_context,
                function,
                input,
                schema,
                parent,
                local_variables,
                mode,
            )

    # any other value of a template field must be an existing Template
    if schema.get("type") == "template":
        if not isinstance(cfg, Template):
            names = ", ".join(schema["parameters"]) or "none"
            raise TemplateRequiredError(
                f"This field expects a template (parameters: {names}). "
                'Write it as {"__template__": ...}.',
                keypath,
                tuple(schema["parameters"]),
            )

        # like a __use__ copy, the Template's value is kept as written under this
        # field's schema and parameters. It keeps the values it carries from the
        # templates around it, which its source may use
        node = _TemplateNode(
            cfg.source,
            schema,
            keypath,
            resolution_context,
            parent,
            local_variables,
            outer_parameters=cfg.outer_parameters,
        )
        if (cfg.schema, cfg.parameters, cfg.keypath) == (
            node.inner_schema,
            node.parameters,
            keypath,
        ):
            # this field's own Template (as when a resolved configuration is
            # resolved again): passed through unchanged
            _set_result(node.resolve, cfg)
        return node

    # otherwise, build the configuration tree: a nested container whose leaves are
    # _ValueNodes, and whose internal nodes are dictionaries or lists
    _check_shape(cfg, schema, keypath)
    is_any = schema["type"] == "any"
    if isinstance(cfg, dict):
        if is_any:
            schema = {"type": "dict", "extra_keys_schema": {"type": "any"}}
        return _DictNode(
            cfg, schema, keypath, resolution_context, parent, local_variables, mode
        )
    if isinstance(cfg, list):
        if is_any:
            schema = {"type": "list", "element_schema": {"type": "any"}}
        return _ListNode(
            cfg, schema, keypath, resolution_context, parent, local_variables, mode
        )
    return _ValueNode(
        cfg, schema["type"], keypath, resolution_context, parent, local_variables, mode
    )


def _check_shape(
    cfg: _types.Configuration, schema: _types.Schema, keypath: _types.KeyPath
) -> None:
    """Raise a ResolutionError if a dict, list, or value doesn't match the schema.

    A dict must have a dict schema and a list a list schema; any other value must
    have a value schema. Schemas of type "any" accept every shape.

    """
    expected = schema.get("type")
    if expected == "any":
        return

    if isinstance(cfg, Template):
        # template fields are handled by make_node before shapes are checked
        matches = False
    elif isinstance(cfg, dict):
        matches = expected == "dict"
    elif isinstance(cfg, list):
        matches = expected == "list"
    else:
        matches = expected not in ("dict", "list")

    if not matches:
        hint = ""
        if isinstance(cfg, str) and "${" in cfg and expected in ("dict", "list"):
            hint = (
                " A ${ ... } always gives a string: to copy a dict or list, use "
                "__splice__ (or __use__ for a template)."
            )
        raise ResolutionError(
            f"Expected {_a(str(expected))}, but got {_describe_value(cfg)}.{hint}",
            keypath,
        )


def _a(noun: str) -> str:
    """The noun with an indefinite article: "a dict", "an integer"."""
    return f"an {noun}" if noun[:1] in "aeiou" else f"a {noun}"


def _describe_value(value: _types.Configuration) -> str:
    """A short description of a configuration value, for error messages."""
    if isinstance(value, Template):
        return "a template"
    if isinstance(value, dict):
        if not value:
            return "an empty dict"
        keys = [f'"{key}"' for key in list(value)[:3]]
        more = ", ..." if len(value) > 3 else ""
        label = "key" if len(value) == 1 else "keys"
        return f"a dict with {label} {', '.join(keys)}{more}"
    if isinstance(value, list):
        return "a list"
    if isinstance(value, bool):
        return f"the boolean {value}"
    if isinstance(value, (int, float)):
        return f"the number {value}"
    if isinstance(value, str):
        shown = value if len(value) <= 40 else value[:37] + "..."
        return f'the string "{shown}"'
    return _a(type(value).__name__)
