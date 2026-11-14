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
       _DictNode. make_node() delegates the creation of this node to
       _DictNode.from_configuration(). This class method also creates the children of
       the node, calling make_node() on each child. The process continues recursively,
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

A field whose schema has ``"type": "template"`` is represented by a _TemplateNode
(built by _make_template_node(), called from make_node()). Its value is written in a
``__template__`` wrapper or given by a ``__use__``. When a configuration containing a
template field is resolved, the field is not resolved to an ordinary value (an int, a
string, a dict, etc.). Rather, the node resolves to a :class:`smartconfig.Template`
holding the value as written. Like a _ValueNode, it is resolved lazily and the result
cached. Resolving it:

    1. replaces each ``__use__`` in the value with the value it stands for (as written).
       The target is looked up as a ``${...}`` reference would be (local variables,
       the document, then the global variables), so it is done here rather than
       when the node is built, since looking in the document needs the whole tree;
    2. builds a node tree of the value against the inner schema, which checks its
       structure, and walks that tree without resolving it, rejecting template
       fields and ``__template__`` wrappers (templates do not nest). The tree is
       marked with the template's keypath, so a template field in it raises when
       resolved;
    3. returns a Template that remembers the resolution options and the available
       variables.

A ``__template__`` wrapper on a field of type ``any`` also gives a _TemplateNode (with
an ``any`` inner schema and no available variables); see ``_template()`` in _core_functions.py.
Template.evaluate() (in _templates.py) builds and resolves a new tree from the
template's source, with the given names as the global variables. It marks the root
with the template's keypath, so that a template field produced while evaluating (by a
function call, say) is rejected too.

"""

from __future__ import annotations

from typing import (
    Any,
    Callable,
    Mapping,
    TypedDict,
)
import abc
import copy
import difflib
import enum
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
from ._templates import Template
from ._utils import deep_update


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

    It is used when resolving configurations, and can be used as the
    ``undefined`` class of other Jinja environments.

    """

    @property
    def _undefined_message(self) -> str:
        # this must never raise AttributeError: Python would then fall back to
        # Undefined.__getattr__, which asks for this message again, forever
        obj = self._undefined_obj
        name = self._undefined_name
        if obj is jinja2.utils.missing or not isinstance(name, str):
            return super()._undefined_message

        if isinstance(obj, _UnresolvedDict):
            keypath = getattr(obj.dict_node, "keypath", ())
            where = ".".join(str(k) for k in keypath)
            message = (
                f'"{where}" has no key "{name}".'
                if where
                else f'The configuration has no key "{name}".'
            )
            keys = [str(k) for k in getattr(obj.dict_node, "children", {})]
            return message + (_did_you_mean(name, keys) or "")

        if isinstance(obj, _UnresolvedList):
            keypath = getattr(obj.list_node, "keypath", ())
            where = ".".join(str(k) for k in keypath) or "The list"
            return f'"{where}" has no element "{name}".'

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


class _InsertedContainer(Exception):
    """A dict or list was inserted into a string with ``${...}``."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _key_reference(where: str, key: str) -> str:
    """A reference to *key* of the dict at *where*, as in ``${ where.key }``."""
    if key.isidentifier():
        return f"${{ {where}.{key} }}"
    return f'${{ {where}["{key}"] }}'


def _refuse_containers(value: typing.Any) -> typing.Any:
    """Raise if *value*, the value of a ``${...}``, is a dict or a list.

    Inserted into a string, a dict or list would become its Python repr (or, for
    an unresolved one, the repr of an internal object), which is almost never
    what's meant. Used as the ``finalize`` of the Jinja environment.

    """
    cant = "can't be inserted into a string"
    if isinstance(value, Template):
        where = ".".join(value.keypath)
        raise _InsertedContainer(
            f'"{where}" is a template, which {cant}. Use it with __use__ instead.'
        )
    if isinstance(value, _UnresolvedDict):
        where = ".".join(str(k) for k in getattr(value.dict_node, "keypath", ()))
        keys = [str(k) for k in getattr(value.dict_node, "children", {})]
        example = f", as in {_key_reference(where, keys[0])}," if keys else ""
        raise _InsertedContainer(
            f'"{where}" is a dict, which {cant}. Use one of its keys{example} or copy '
            f"the whole value with __splice__."
        )
    if isinstance(value, _UnresolvedList):
        where = ".".join(str(k) for k in getattr(value.list_node, "keypath", ()))
        raise _InsertedContainer(
            f'"{where}" is a list, which {cant}. Use one of its elements, as in '
            f"${{ {where}[0] }}, or copy the whole value with __splice__."
        )
    if isinstance(value, typing.Mapping):
        described = _describe_value(dict(value))
        raise _InsertedContainer(
            f"{described[0].upper()}{described[1:]} {cant}. Use one of its keys "
            f"instead."
        )
    if isinstance(value, (list, tuple)):
        raise _InsertedContainer(
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
        if isinstance(obj, (_UnresolvedDict, _UnresolvedList, _UnresolvedFunctionCall)):
            try:
                return obj[attribute]
            except (LookupError, TypeError):
                pass
        return super().getattr(obj, attribute)


class _UnresolvedDict(_types.UnresolvedDict):
    """Implements UnresolvedDict using a _DictNode as the backing data structure."""

    def __init__(self, dict_node: _DictNode):
        self.dict_node = dict_node

    def __getitem__(
        self, key
    ) -> _UnresolvedDict | _UnresolvedList | _types.Configuration:
        """Access an element in the unresolved dictionary.

        If the element is a _ValueNode, this resolves it. If the element is a _DictNode
        or _ListNode, this returns another unresolved container. If the element is a
        _FunctionCallNode, this evaluates the function and returns an unresolved
        container if the result is a collection, or the resolved value otherwise.

        If the key is not found, a KeyError is raised.

        """
        child = self.dict_node.children[key]

        if isinstance(child, _FunctionCallNode):
            # evaluate the function to turn it into a Dict, List, or Value node
            child = child.evaluate()

        if isinstance(child, _DictNode):
            return _UnresolvedDict(child)
        elif isinstance(child, _ListNode):
            return _UnresolvedList(child)
        elif isinstance(child, (_ValueNode, _TemplateNode)):
            return child.resolve()

    def __len__(self):
        return len(self.dict_node.children)

    def __iter__(self):
        return iter(self.keys())

    def keys(self):
        return self.dict_node.children.keys()

    def values(self):
        for key in self.keys():
            yield self[key]

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

    def __getitem__(
        self, ix
    ) -> _UnresolvedDict | _UnresolvedList | _types.Configuration:
        """Access an element in the unresolved list.

        If the element is a _ValueNode, this resolves it. If the element is a _DictNode
        or _ListNode, this returns another unresolved container. If the element is a
        _FunctionCallNode, this evaluates the function and returns an unresolved
        container if the result is a collection, or the resolved value otherwise.

        If the index is out of range, an IndexError is raised.

        """
        if ix not in range(len(self)):
            raise IndexError(ix)

        child = self.list_node.children[ix]

        if isinstance(child, _FunctionCallNode):
            # evaluate the function to turn it into a Dict, List, or Value node
            child = child.evaluate()

        if isinstance(child, _DictNode):
            return _UnresolvedDict(child)
        elif isinstance(child, _ListNode):
            return _UnresolvedList(child)
        elif isinstance(child, (_ValueNode, _TemplateNode)):
            return child.resolve()
        else:
            raise TypeError(f"Unexpected node type: {type(child)}")  # pragma: no cover

    def __iter__(self):
        for i in range(len(self)):
            yield self[i]

    def __len__(self):
        return len(self.list_node.children)

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

    def _evaluate_to_unresolved_container(
        self,
    ) -> _UnresolvedDict | _UnresolvedList:
        """Evaluate the function call and return a unresolved container."""
        node = self.function_node.evaluate()
        assert not isinstance(node, (_ValueNode, _TemplateNode))
        if isinstance(node, _DictNode):
            return _UnresolvedDict(node)
        else:
            # must be a _ListNode
            return _UnresolvedList(node)

    def __getitem__(
        self, key
    ) -> _UnresolvedDict | _UnresolvedList | _types.Configuration:
        """Attempt to access an element in the result of the unresolved function call.

        This will trigger the evaluation of the function call if it has not already been
        resolved. If the result is a dictionary or list, the key is looked up in that
        collection. If the result is not a dictionary or list, a TypeError is raised.

        """
        return self._evaluate_to_unresolved_container()[key]

    def get_keypath(self, keypath: _types.KeyPath | str) -> _types.Configuration:
        """Resolve the value at the given keypath."""
        return self.function_node.get_keypath(keypath).resolve()


# helpers ------------------------------------------------------------------------------


def _make_unresolved_container(
    node: _DictNode | _ListNode | _FunctionCallNode,
) -> _UnresolvedDict | _UnresolvedList | _UnresolvedFunctionCall:
    """Create the correct type of unresolved container to wrap a node."""
    if isinstance(node, _DictNode):
        return _UnresolvedDict(node)
    elif isinstance(node, _ListNode):
        return _UnresolvedList(node)
    elif isinstance(node, _FunctionCallNode):
        return _UnresolvedFunctionCall(node)
    raise TypeError(f"Cannot create unresolved container for {type(node).__name__}.")


def _get_node_at_keypath(
    node: _DictNode | _ListNode,
    keypath: _types.KeyPath | str,
    cast_key: Callable[[str], Any],
) -> _ConcreteNode:
    """Navigate the node tree and return the node at the given keypath.

    Walks the internal node tree and returns the raw ``_Node`` without resolving it.
    ``_FunctionCallNode`` instances encountered along the path are evaluated so that
    their children can be traversed.

    """
    if isinstance(keypath, str):
        keypath = tuple(keypath.split("."))

    head_key, *rest = keypath

    child: _ConcreteNode = node.children[cast_key(head_key)]

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


class _Node(abc.ABC):
    """Abstract base class for all nodes in a configuration tree.

    Attributes
    ----------
    parent : _ConcreteNode | None
        The parent of this node. Can be `None`, in which case this is the root of the
        tree.
    local_variables : Mapping[str, Configuration | UnresolvedDict | UnresolvedList | UnresolvedFunctionCall] | None
        A dictionary of local variables that can be accessed during string
        interpolation. If None, this is made an empty dictionary.
    template_keypath : KeyPath | None
        Used to detect a template inside a template, which is not allowed. It is set
        on the root of a tree built from a template's value (by
        :meth:`Template.evaluate`, and by _TemplateNode.resolve to check the
        structure), and it is the keypath of that template. A _TemplateNode checks
        its root's ``template_keypath`` when it is resolved: if it is set, the node
        is a template inside a template, and the error message uses the keypath to
        name the enclosing template. ``None`` on any other root.

    """

    template_keypath: _types.KeyPath | None = None

    def __init__(
        self,
        parent: _ConcreteNode | None = None,
        local_variables: Mapping[str, _types.Configuration] | None = None,
    ):
        self.parent = parent

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
        then in the root of the tree, then in the global variables.

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
        if not (
            isinstance(root, _FunctionCallNode)
            and root._evaluated is _FunctionCallNode.PENDING
        ):
            try:
                return root_container[key]  # type: ignore[index]
            except (KeyError, IndexError):
                pass

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


def _populate_required_children(
    existing_children: dict[str, _ConcreteNode],
    dct: _types.ConfigurationDict,
    dict_schema: _types.Schema,
    resolution_context: _types.ResolutionContext,
    parent: _ConcreteNode,
    keypath: _types.KeyPath,
    mode: ResolutionMode = ResolutionMode.STANDARD,
) -> None:
    """Validates/populates required children of a _DictNode from a ConfigurationDict.

    This uses the schema to determine which keys are required and then creates the child
    nodes for those keys. If a required key is missing, a ResolutionError is raised.

    Modifications are made to the node's .children dictionary in place.

    """
    required_keys = dict_schema.get("required_keys", {})

    for key, key_schema in required_keys.items():
        if key not in dct:
            raise ResolutionError(
                f'Dictionary is missing required key "{key}".', (keypath + (key,))
            )

        existing_children[key] = make_node(
            dct[key],
            key_schema,
            resolution_context,
            parent,
            keypath + (key,),
            mode=mode,
        )


def _populate_optional_children(
    existing_children: dict[str, _ConcreteNode],
    dct: _types.ConfigurationDict,
    dict_schema: _types.Schema,
    resolution_context: _types.ResolutionContext,
    parent: _ConcreteNode,
    keypath: _types.KeyPath,
    mode: ResolutionMode = ResolutionMode.STANDARD,
) -> None:
    """Validates/populates optional children of a _DictNode from a ConfigurationDict.

    This uses the schema to determine which keys are optional and then creates the child
    nodes for those keys. If an optional key is missing and a default is provided, the
    default is used. If an optional key is missing and no default is provided, the key
    is simply not added to the children.

    Modifications are made to the .children dictionary in place.

    """
    optional_keys = dict_schema.get("optional_keys", {})

    for key, key_schema in optional_keys.items():
        if key in dct:
            # key is not missing
            value = dct[key]
        else:
            # key is missing; resolve dynamic schema before checking for default
            if callable(key_schema):
                key_schema = key_schema(None, keypath + (key,))
                _validate_schema(
                    key_schema, keypath + (key,), allow_default=True, allow_dynamic=True
                )
            if "default" in key_schema:
                # default was provided
                value = key_schema["default"]
            else:
                # no default was provided
                continue

            if key_schema.get("type") == "template" and value is not None:
                # the default of a template field is the template's value as
                # written, without a __template__ wrapper
                existing_children[key] = _TemplateNode(
                    value,
                    key_schema,
                    keypath + (key,),
                    resolution_context,
                    parent=parent,
                )
                continue

        existing_children[key] = make_node(
            value,
            key_schema,
            resolution_context,
            parent,
            keypath + (key,),
            mode=mode,
        )


def _populate_extra_children(
    children: dict[str, _ConcreteNode],
    dct: _types.ConfigurationDict,
    dict_schema: _types.Schema,
    resolution_context: _types.ResolutionContext,
    parent: _ConcreteNode,
    keypath: _types.KeyPath,
    mode: ResolutionMode = ResolutionMode.STANDARD,
) -> None:
    """Validates/populates extra children of a _DictNode from a ConfigurationDict.

    This uses the schema to determine how to handle extra keys in the configuration
    dictionary. If extra keys are not allowed, a ResolutionError is raised. If extra
    keys are allowed, the schema for the extra keys is used to create the child nodes.

    Modifications are made to the .children dictionary in place.

    """
    required_keys = dict_schema.get("required_keys", {})

    optional_keys = dict_schema.get("optional_keys", {})
    expected_keys = set(required_keys) | set(optional_keys)
    # a list, not a set difference, so that extra keys keep their input order
    extra_keys = [key for key in dct if key not in expected_keys]

    if extra_keys and "extra_keys_schema" not in dict_schema:
        key = extra_keys[0]
        raise ResolutionError(
            f'Dictionary contains unexpected extra key "{key}".', keypath + (key,)
        )

    for key in extra_keys:
        children[key] = make_node(
            dct[key],
            dict_schema["extra_keys_schema"],
            resolution_context,
            parent,
            keypath + (key,),
            mode=mode,
        )


class _DictNode(_Node):
    """Represents an internal dictionary node in a configuration tree.

    Attributes
    ----------
    resolution_context : _types.ResolutionContext
        The resolution context (converters, functions, variables, filters, etc.).
    children : dict[str, _ConcreteNode]
        A dictionary of child nodes.
    parent : _ConcreteNode | None
        The parent of this node. Can be `None`, in which case this is the root of the
        tree.
    local_variables : Mapping[str, Configuration | UnresolvedDict | UnresolvedList | UnresolvedFunctionCall] | None
        A dictionary of local variables that can be accessed during string
        interpolation.

    """

    def __init__(
        self,
        resolution_context: _types.ResolutionContext,
        children: dict[str, _ConcreteNode] | None = None,
        parent: _ConcreteNode | None = None,
        local_variables: Mapping[str, _types.Configuration] | None = None,
    ):
        super().__init__(parent, local_variables)
        self.resolution_context = resolution_context
        self.children: dict[str, _ConcreteNode] = {} if children is None else children
        # set by from_configuration; used in error messages
        self.keypath: _types.KeyPath = ()

    @classmethod
    def from_configuration(
        cls,
        dct: _types.ConfigurationDict,
        schema: _types.Schema,
        keypath: _types.KeyPath,
        resolution_context: _types.ResolutionContext,
        parent: _ConcreteNode | None = None,
        local_variables: Mapping[str, _types.Configuration] | None = None,
        mode: ResolutionMode = ResolutionMode.STANDARD,
    ) -> _DictNode:
        """Construct a _DictNode from a configuration dictionary and its schema.

        Parameters
        ----------
        dct : ConfigurationDict
            The configuration dictionary.
        schema : Schema
            The schema to enforce on the configuration dictionary.
        keypath : _types.KeyPath
            The keypath to this node in the configuration tree.
        resolution_context : ResolutionContext
            The resolution context (converters, functions, variables, filters, etc.).
        parent : _ConcreteNode | None
            The parent of this node. Can be `None`.
        local_variables : Mapping[str, Configuration] | None
            Local variables available during string interpolation within this
            node's subtree. Defaults to `None`.
        mode : ResolutionMode
            The resolution mode to use for children of this node.

        """
        node = cls(resolution_context, parent=parent, local_variables=local_variables)
        node.keypath = keypath

        if schema["type"] == "any":
            schema = {
                "type": "dict",
                "extra_keys_schema": {"type": "any", "nullable": True},
            }

        children: dict[str, _ConcreteNode] = {}

        # these private functions are used to populate the children of the node. they
        # also enforce the schema by checking that all required keys are present and
        # that no extra keys are present. It is most natural to do this validation here
        # and not in .resolve() because the process of populating children already
        # requires us to check if children are missing; for example, to fill in default
        # values.

        _populate_required_children(
            children,
            dct,
            schema,
            resolution_context,
            node,
            keypath,
            mode=mode,
        )
        _populate_optional_children(
            children,
            dct,
            schema,
            resolution_context,
            node,
            keypath,
            mode=mode,
        )
        _populate_extra_children(
            children,
            dct,
            schema,
            resolution_context,
            node,
            keypath,
            mode=mode,
        )

        node.children = children
        return node

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
    resolution_context : ResolutionContext
        The resolution context (converters, functions, variables, filters, etc.).
    children : list[_ConcreteNode]
        A list of the node's children.
    parent : _ConcreteNode | None
        The parent of this node. Can be `None`, in which case this is the root of the
        tree.
    local_variables : Mapping[str, Configuration] | None
        A dictionary of local variables that can be accessed during string
        interpolation

    """

    def __init__(
        self,
        resolution_context: _types.ResolutionContext,
        children: list[_ConcreteNode] | None = None,
        parent: _ConcreteNode | None = None,
        local_variables: Mapping[str, _types.Configuration] | None = None,
    ):
        super().__init__(parent, local_variables)
        self.resolution_context = resolution_context
        self.children: list[_ConcreteNode] = [] if children is None else children
        # set by from_configuration; used in error messages
        self.keypath: _types.KeyPath = ()

    @classmethod
    def from_configuration(
        cls,
        lst: _types.ConfigurationList,
        schema: _types.Schema,
        keypath: _types.KeyPath,
        resolution_context: _types.ResolutionContext,
        parent: _ConcreteNode | None = None,
        local_variables: Mapping[str, _types.Configuration] | None = None,
        mode: ResolutionMode = ResolutionMode.STANDARD,
    ) -> _ListNode:
        """Construct a _ListNode from a configuration list and its schema.

        Parameters
        ----------
        lst : ConfigurationList
            The configuration list.
        schema : Schema
            The schema to enforce on the configuration list.
        keypath : KeyPath
            The keypath to this node in the configuration tree.
        resolution_context : ResolutionContext
            The resolution context (converters, functions, variables, filters, etc.).
        parent : _ConcreteNode | None
            The parent of this node. Can be `None`.
        local_variables : Mapping[str, Configuration] | None
            Local variables available during string interpolation within this
            node's subtree. Defaults to `None`.
        mode : ResolutionMode
            The resolution mode to use for children of this node.

        """
        node = cls(resolution_context, parent=parent, local_variables=local_variables)
        node.keypath = keypath

        if schema["type"] == "any":
            schema = {
                "type": "list",
                "element_schema": {"type": "any", "nullable": True},
            }

        child_schema = schema["element_schema"]

        children = []
        for i, lst_value in enumerate(lst):
            r = make_node(
                lst_value,
                child_schema,
                resolution_context,
                node,
                keypath + (str(i),),
                mode=mode,
            )
            children.append(r)

        node.children = children
        return node

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
        A string describing the expected type of this leaf once resolved. Used
        to determined which converter to use from the resolution options.
    keypath : _types.KeyPath
        The keypath to this node in the configuration tree.
    resolution_context : ResolutionContext
        The resolution context (converters, functions, variables, filters, etc.).
    nullable : bool
        Whether the value can be None or not. If `raw` is None this is True, it
        is not converted (no matter what type_ is). Default: False.
    parent : _ConcreteNode | None
        The parent of this node. Can be `None`, in which case this is the root.
    local_variables : Mapping[str, Configuration | UnresolvedDict | UnresolvedList | UnresolvedFunctionCall] | None
        A dictionary of local variables that can be accessed during string
        interpolation.
    mode : ResolutionMode
        The resolution mode governing string interpolation for this node.

    """

    # sentinel object denoting that a node is currently being resolved
    _PENDING = object()

    # sentinel object denoting that the resolution of this node has not yet started
    _UNDISCOVERED = object()

    def __init__(
        self,
        value: _types.ConfigurationValue,
        type_,
        keypath: _types.KeyPath,
        resolution_context: _types.ResolutionContext,
        nullable: bool = False,
        parent: _ConcreteNode | None = None,
        local_variables: Mapping[str, _types.Configuration] | None = None,
        mode: ResolutionMode = ResolutionMode.STANDARD,
    ):
        super().__init__(parent, local_variables)
        self.value = value
        self.type_ = type_
        self.keypath = keypath
        self.resolution_context = resolution_context
        self.nullable = nullable
        self.mode = mode

        # The resolved value of the leaf node. There are two special values. If this is
        # _UNDISCOVERED, the resolution process has not yet discovered the leaf node
        # (this is the default value). If this is _PENDING, a step in the resolution
        # process has started to resolve the leaf. Otherwise, this contains the resolved
        # value. Necessary in order to detect circular references.
        self._resolved = _ValueNode._UNDISCOVERED

    @classmethod
    def from_configuration(
        cls,
        value: _types.ConfigurationValue,
        schema: _types.Schema,
        keypath: _types.KeyPath,
        resolution_context: _types.ResolutionContext,
        parent: _ConcreteNode | None = None,
        local_variables: Mapping[str, _types.Configuration] | None = None,
        mode: ResolutionMode = ResolutionMode.STANDARD,
    ) -> _ValueNode:
        """Construct a _ValueNode from a configuration value and its schema.

        Parameters
        ----------
        value : ConfigurationValue
            The raw configuration value.
        schema : Schema
            The schema describing the expected type and constraints.
        keypath : KeyPath
            The keypath to this node in the configuration tree.
        resolution_context : ResolutionContext
            The resolution context (converters, functions, variables, filters, etc.).
        parent : _ConcreteNode | None
            The parent of this node. Can be `None`.
        local_variables : Mapping[str, Configuration] | None
            Local variables available during string interpolation within this
            node's subtree. Defaults to `None`.
        mode : ResolutionMode
            The resolution mode governing string interpolation for this node.

        """
        if schema["type"] == "any":
            schema = {"type": "any", "nullable": True}

        return cls(
            value,
            schema["type"],
            keypath,
            resolution_context,
            nullable=schema["nullable"] if "nullable" in schema else False,
            parent=parent,
            local_variables=local_variables,
            mode=mode,
        )

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
        # check for circular references
        if self._resolved is _ValueNode._PENDING:
            raise ResolutionError("Circular reference.", self.keypath)

        # if the value is already resolved, return it
        if self._resolved is not _ValueNode._UNDISCOVERED:
            self._resolved = typing.cast(_types.ConfigurationValue, self._resolved)
            return self._resolved

        # if we've reached this point, we're resolving this node for the first time
        self._resolved = _ValueNode._PENDING

        # Step 1: interpolate the string (if its a string and mode is not RAW)
        value: _types.ConfigurationValue
        if isinstance(self.value, str) and self.mode != ResolutionMode.RAW:
            value = self._safely_evaluate(
                self._interpolate,
                self.value,
                full=(self.mode == ResolutionMode.FULL),
            )
        else:
            value = self.value

        # Step 2: convert the value to the expected type (if it's not None) and cache
        # the result
        if self.nullable and self.value is None:
            self._resolved = None
        else:
            self._resolved = self._safely_evaluate(self._convert, value, self.type_)

        return typing.cast(_types.ConfigurationValue, self._resolved)

    def _make_custom_jinja_context(
        self, global_variables: Mapping[str, Any], inject_root_as: str | None = None
    ) -> type[jinja2.runtime.Context]:
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

        # copy the globals to prevent modification, then insert the root node if
        # requested
        global_variables = dict(global_variables)
        if inject_root_as is not None:
            global_variables[inject_root_as] = root_container

        class CustomContext(jinja2.runtime.Context):
            def resolve_or_missing(self, key):
                # first try local variables, then the root, then the globals
                try:
                    return this_node._look_up_name(
                        key, root_container, global_variables
                    )
                except KeyError:
                    pass

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
        environment = _Environment(
            variable_start_string="${",
            variable_end_string="}",
            # inserting a dict or list into a string is an error
            finalize=_refuse_containers,
        )

        # create a custom jinja context for resolving references. This will first look
        # up keys in the local variables, and then in the root of the configuration
        # tree, and finally in the global variables. See the
        # _make_custom_jinja_context() method for more information.
        environment.context_class = self._make_custom_jinja_context(
            self.resolution_context.global_variables,
            inject_root_as=self.resolution_context.inject_root_as,
        )

        # register the custom filters
        environment.filters.update(self.resolution_context.filters)

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
        except _InsertedContainer as exc:
            raise ResolutionError(exc.message, self.keypath) from None

        if full and result != s:
            # if the string changed, we need to interpolate again
            return self._interpolate(result, full=True)
        else:
            return result

    def _convert(
        self, value: _types.ConfigurationValue, type_: str
    ) -> _types.ConfigurationValue:
        """convert the configuration value into its final type.

        Parameters
        ----------
        value : ConfigurationValue
            The value to convert.

        type_ : str
            The expected type of the value. Should be one of the valid value types.

        Returns
        -------
        ConfigurationValue
            The converted value.

        """
        converters = self.resolution_context.converters

        try:
            converter = converters[type_]
        except KeyError:
            raise ResolutionError(
                f'No converter provided for type: "{type_}".', self.keypath
            )

        return converter(value)

    def _safely_evaluate[T, **P](
        self, fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs
    ) -> T:
        """Apply the function and catch any exceptions, raising a ResolutionError."""
        try:
            return fn(*args, **kwargs)
        except ResolutionError as exc:
            raise exc
        except Error as exc:
            raise ResolutionError(str(exc), self.keypath) from exc


# _FunctionCallNode --------------------------------------------------------------------


class _FunctionCallNode(_Node):
    """Represents a function call in the configuration tree.

    Attributes
    ----------
    keypath : _types.KeyPath
        The keypath to this node in the configuration tree.
    resolution_context : _types.ResolutionContext
        The resolution context (converters, functions, variables, filters, etc.).
    function : _types.Function
        The function being called.
    input : _types.Configuration
        The input to the function.
    schema : _types.Schema
        The schema for the function's output.
    parent : _ConcreteNode | None
        The parent of this node. Can be `None`, in which case this is the root
    local_variables : Mapping[str, Configuration | UnresolvedDict | UnresolvedList | UnresolvedFunctionCall] | None
        A dictionary of local variables that can be accessed during string
        interpolation.
    mode : ResolutionMode
        The resolution mode propagated to child nodes built from the function's
        result.

    """

    # sentinel object denoting that a node is currently being evaluated
    PENDING = object()

    # sentinel object denoting that the evaluation of this node has not yet started
    UNDISCOVERED = object()

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
        super().__init__(parent, local_variables)
        self.keypath = keypath
        self.resolution_context = resolution_context
        self.schema = schema
        self.function = function
        self.input = input
        self.mode = mode

        # The evaluated value of the function node. There are two special
        # values. If this is _UNDISCOVERED, the evaluation process has not yet
        # discovered the function node (this is the default value). If this is
        # _PENDING, a step in the resolution process has started to evaluate
        # the function. Otherwise, this contains the evaluated value. Necessary
        # in order to detect circular references.
        self._evaluated = _FunctionCallNode.UNDISCOVERED

    def _make_resolver(self) -> _types.Resolver:
        """Make a "resolver" function that can be used by functions to resolve configs.

        This enables advanced use cases like using a function to implement for-loops.
        This function satisfies the _types.Resolver protocol.

        """

        def resolver(
            configuration: _types.Configuration,
            schema: _types.Schema | None = None,
            local_variables: Mapping[str, _types.Configuration] | None = None,
        ) -> _types.Configuration:
            if schema is None:
                schema = self.schema
            node = make_node(
                configuration,
                schema,
                self.resolution_context,
                parent=self,
                keypath=self.keypath,
                local_variables=local_variables,
                mode=self.mode,
            )
            return node.resolve()

        return resolver

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

        if self._evaluated is _FunctionCallNode.PENDING:
            raise ResolutionError("Circular reference", self.keypath)

        # if the function has already been evaluated, return the cached result
        if self._evaluated is not _FunctionCallNode.UNDISCOVERED:
            assert isinstance(
                self._evaluated, (_DictNode, _ListNode, _ValueNode, _TemplateNode)
            )
            return self._evaluated

        # at this point, we're evaluating the function for the first time
        self._evaluated = _FunctionCallNode.PENDING

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

        # evaluate the function itself
        output = self.function(args)

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
            result = make_node(
                output,
                self.schema,
                self.resolution_context,
                parent=self,
                keypath=self.keypath,
                mode=self.mode,
            )

        # the result may be a function call itself, in which case we need to evaluate it
        if isinstance(result, _FunctionCallNode):
            # this will evaluate the function call recursively
            result = result.evaluate()

        self._evaluated = result
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


def _template_schema_parts(
    schema: _types.Schema, keypath: _types.KeyPath
) -> tuple[_types.Schema | _types.DynamicSchema, tuple[str, ...]]:
    """The inner schema and available variables of a template schema.

    Static schemas are not validated by resolve(), so the keys are read defensively.

    Raises
    ------
    InvalidSchemaError
        If the schema has no "schema" or no "available_variables".

    """
    for key in ("schema", "available_variables"):
        if key not in schema:
            raise InvalidSchemaError(
                f'A template schema must have a "{key}" key.', keypath + (key,)
            )
    return schema["schema"], tuple(schema["available_variables"])


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
    global_variables = dict(context.global_variables)
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
        or overrides are given for a template that is not a dict.

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
                "Overrides can only be applied when the template resolves to a "
                "dictionary.",
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
    template_schema : Schema
        The template schema (``{"type": "template", ...}``).
    inner_schema : Schema | DynamicSchema
        The schema of the template's value once evaluated.
    available_variables : tuple[str, ...]
        The variables available to this template field when it is evaluated.
    keypath : KeyPath
        The keypath to this node in the configuration tree.
    resolution_context : ResolutionContext
        The resolution context (converters, functions, variables, filters, etc.).
    parent : _ConcreteNode | None
        The parent of this node. Can be `None`, in which case this is the root.

    """

    # sentinel object denoting that a node is currently being resolved
    _PENDING = object()

    # sentinel object denoting that the resolution of this node has not yet started
    _UNDISCOVERED = object()

    def __init__(
        self,
        value: _types.Configuration,
        template_schema: _types.Schema,
        keypath: _types.KeyPath,
        resolution_context: _types.ResolutionContext,
        parent: _ConcreteNode | None = None,
        local_variables: Mapping[str, _types.Configuration] | None = None,
    ):
        super().__init__(parent, local_variables)
        self.value = value
        self.template_schema = template_schema
        self.inner_schema, self.available_variables = _template_schema_parts(
            template_schema, keypath
        )
        self.keypath = keypath
        self.resolution_context = resolution_context
        self._resolved: Any = _TemplateNode._UNDISCOVERED

    @classmethod
    def from_template(
        cls,
        template: Template,
        template_schema: _types.Schema,
        keypath: _types.KeyPath,
        resolution_context: _types.ResolutionContext,
        parent: _ConcreteNode | None = None,
    ) -> _TemplateNode:
        """A node that resolves to an existing Template, unchanged."""
        node = cls(
            template.source, template_schema, keypath, resolution_context, parent
        )
        node._resolved = template
        return node

    def resolve(self) -> Template:
        """Build (once) and return the Template for this field.

        Raises
        ------
        UnexpectedTemplateError
            If the node is in a tree built from a template's value: templates do
            not nest. Checked first, so that an existing Template is rejected too.

        """
        # templates do not nest. If the root of this node's tree has a
        # template_keypath, the tree was built from a template's value, so this
        # node is a template inside that template
        enclosing = self.root.template_keypath
        if enclosing is not None:
            where = ".".join(enclosing)
            raise UnexpectedTemplateError(
                f'A template can\'t contain a template field: the template at "{where}" '
                "already defers everything in it. Make the field a sibling of the "
                "template instead.",
                self.keypath,
                enclosing,
            )

        if self._resolved is _TemplateNode._PENDING:
            raise ResolutionError("Circular reference.", self.keypath)

        if self._resolved is not _TemplateNode._UNDISCOVERED:
            return self._resolved

        self._resolved = _TemplateNode._PENDING

        # replace every __use__ in the value with the value it stands for, so
        # that the template's source does not depend on the rest of the document
        self.value = self._expand_uses(self.value, self.keypath)

        # check the structure of the value as written: building the tree raises
        # structure errors; it is walked but never resolved. Like the tree that
        # Template.evaluate builds, it is marked as a template's tree, so a template
        # field in it is an error when resolved
        tree = make_node(
            self.value, self.inner_schema, self.resolution_context, keypath=self.keypath
        )
        tree.template_keypath = self.keypath
        self._check(tree)

        context = self.resolution_context
        self._resolved = Template(
            self.value,
            self.inner_schema,
            available_variables=self.available_variables,
            keypath=self.keypath,
            converters=context.converters,
            functions=context.functions,
            filters=context.filters,
            inject_root_as=context.inject_root_as,
            check_for_function_call=context.check_for_function_call,
        )
        return self._resolved

    def _expand_uses(
        self, value: _types.Configuration, keypath: _types.KeyPath
    ) -> _types.Configuration:
        """The value with each ``__use__`` replaced by the value it stands for.

        Every dict and list is visited, including the inputs of other function
        calls. The target template's own ``__use__`` calls were already expanded
        when that template was resolved.

        """
        if isinstance(value, list):
            return [
                self._expand_uses(item, keypath + (str(i),))
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
        if call is not None and getattr(call[0], "_role", None) == "use":
            # a __use__ call: replace it with the value it stands for
            return _expand_use(call[1], self, keypath)

        # an ordinary dict, or a call to a function other than __use__ (whose input
        # is a dict too): expand the __use__ calls inside each value
        return {k: self._expand_uses(v, keypath + (k,)) for k, v in value.items()}

    def _check(self, node: _ConcreteNode) -> None:
        """Raise if a tree built from this template's value contains a template.

        Templates do not nest. This walks the tree without resolving it, and raises
        an UnexpectedTemplateError at the first template field or ``__template__``
        wrapper it finds. Function calls are not evaluated, and their inputs are not
        walked.

        """
        if isinstance(node, _DictNode):
            for child in node.children.values():
                self._check(child)
        elif isinstance(node, _ListNode):
            for child in node.children:
                self._check(child)
        elif isinstance(node, _TemplateNode):
            node.resolve()  # raises: templates do not nest
        elif (
            isinstance(node, _FunctionCallNode)
            and getattr(node.function, "_role", None) == "template"
        ):
            where = ".".join(self.keypath)
            raise UnexpectedTemplateError(
                f'A template can\'t contain another __template__: the template at "{where}" '
                "already defers everything in it. Remove the wrapper.",
                node.keypath,
                self.keypath,
            )


def _make_template_node(
    cfg: _types.Configuration,
    schema: _types.Schema,
    resolution_context: _types.ResolutionContext,
    parent: _ConcreteNode | None,
    keypath: _types.KeyPath,
    local_variables: Mapping[str, _types.Configuration] | None,
) -> _TemplateNode:
    """Build the node for a template field (a value whose schema is a template).

    The value must be a ``__template__`` wrapper, a ``__use__`` of a template, or an
    existing Template (which is passed through unchanged).

    Raises
    ------
    TemplateRequiredError
        If the value is not wrapped.
    ResolutionError
        If the value is an invalid function call.

    """
    _, available_variables = _template_schema_parts(schema, keypath)

    if isinstance(cfg, Template):
        return _TemplateNode.from_template(
            cfg, schema, keypath, resolution_context, parent
        )

    if isinstance(cfg, dict):
        try:
            call = resolution_context.check_for_function_call(
                cfg, resolution_context.functions
            )
        except ValueError as exc:
            raise ResolutionError(f"Invalid function call: {exc}", keypath)

        if call is not None and getattr(call[0], "_role", None) == "template":
            return _TemplateNode(
                call[1],
                schema,
                keypath,
                resolution_context,
                parent=parent,
                local_variables=local_variables,
            )

        if call is not None and getattr(call[0], "_role", None) == "use":
            # the __use__ is expanded when the node is resolved (looking up its target
            # needs the whole tree)
            return _TemplateNode(
                cfg,
                schema,
                keypath,
                resolution_context,
                parent=parent,
                local_variables=local_variables,
            )

    names = ", ".join(available_variables) if available_variables else "none"
    raise TemplateRequiredError(
        f"This field is a template (available variables: {names}), evaluated later. "
        'Write it as {"__template__": ...}.',
        keypath,
        available_variables,
    )


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
    if callable(schema):
        # dynamic schema: call the function to get the actual schema
        schema = schema(cfg, keypath)
        _validate_schema(schema, allow_default=True, allow_dynamic=True)

    class _CommonKwargs(TypedDict):
        """Common keyword arguments passed to node constructors in make_node."""

        resolution_context: _types.ResolutionContext
        parent: _ConcreteNode | None
        keypath: _types.KeyPath
        local_variables: Mapping[str, _types.Configuration] | None
        schema: _types.Schema
        mode: ResolutionMode

    common_kwargs: _CommonKwargs = {
        "resolution_context": resolution_context,
        "parent": parent,
        "keypath": keypath,
        "local_variables": local_variables,
        "schema": schema,
        "mode": mode,
    }

    if cfg is None:
        if ("nullable" in schema and schema["nullable"]) or (
            "type" in schema and schema["type"] == "any"
        ):
            kwargs: _CommonKwargs = {**common_kwargs, "schema": {"type": "any"}}
            return _ValueNode.from_configuration(None, **kwargs)
        else:
            raise ResolutionError("Unexpectedly null.", keypath)

    if schema.get("type") == "template":
        return _make_template_node(
            cfg, schema, resolution_context, parent, keypath, local_variables
        )

    # construct the configuration tree. the configuration tree is a nested container
    # whose terminal leaf values are _ValueNodes. "Internal" nodes are dictionaries or
    # lists.
    if isinstance(cfg, dict):
        # dictionaries require a little extra care, since they could be function calls

        if mode != ResolutionMode.RAW:
            # check if this is a function call
            try:
                result = resolution_context.check_for_function_call(
                    cfg, resolution_context.functions
                )
            except ValueError as exc:
                raise ResolutionError(f"Invalid function call: {exc}", keypath)
        else:
            # RAW mode skips function call detection
            result = None

        if result is not None:
            return _FunctionCallNode(
                **common_kwargs,
                function=result[0],
                input=result[1],
            )
        else:
            _check_shape(cfg, schema, keypath)
            return _DictNode.from_configuration(
                cfg,
                **common_kwargs,
            )
    elif isinstance(cfg, list):
        _check_shape(cfg, schema, keypath)
        return _ListNode.from_configuration(
            cfg,
            **common_kwargs,
        )
    else:
        _check_shape(cfg, schema, keypath)
        return _ValueNode.from_configuration(
            cfg,
            **common_kwargs,
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
