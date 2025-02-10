"""Provides the resolve() function for resolving raw configurations.

This section describes the implementation of the resolve() function. For higher-level
notes, see the documentation.

Approach
========

In the documentation, it is described how a configuration can be conceptualized as a
directed "configuration graph", and how resolution is a depth-first search on this
graph. This module works by building a concrete representation of the configuration
graph and performing that traversal.

Each node in the graph is represented by one of four node classes: _DictNode, _ListNode,
_ValueNode, and _FunctionCallNode. Each has a .resolve() method that recursively
resolves the node and its children. Each node also has a corresponding
.from_configuration() method that constructs the node from a configuration of the
appropriate type -- e.g., _DictNode.from_configuration() builds a _DictNode from a
dictionary, _ListNode.from_configuration() builds a _ListNode from a list, etc.

The creation of the tree is orchestrated by the _make_node() function, whose job is to
take an arbitrary configuration and determine which node class to use to represent it.
This function is called with the whole configuration to create the root node, and is
also called by the container node classes to create their children. _make_node is also
responsible for detecting when a dictionary represents a function call and creating a
_FunctionCallNode in that case.

The main function, resolve(), is a thin wrapper around the root node's .resolve()
method. It constructs the root node using _make_node, calls .resolve() on it, and
returns the result.

String Interpolation with Jinja2
================================

String interpolation (like in "${foo.bar}") is delegated to Jinja2. During the
resolution of a _ValueNode representing a string, the string is passed to Jinja2 for
interpolation. Other parts of the configuration tree are made available to Jinja2 as
template variables. Typically, this is done by passing a dictionary to Jinja2's render()
method. However, we cannot pass the fully-resolved configuration tree at the time of
interpolation, because it hasn't been fully resolved at that point. Instead, the root of
the configuration tree is passed as a nested "lazy" collection -- either a _LazyDict,
_LazyList, or _LazyFunctionCall. When an element of a lazy collection is accessed, the
resolution process is triggered for that element if it is a function node or a value
node. Otherwise, another lazy collection is returned.

Worked Example
==============

Consider the configuration:

    .. code:: python

        {
            "foo": "${bar.baz} + 1",
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

When resolve() is called on this configuration, the following major steps occur:

    1. resolve() calls _make_node() to create the root node, a _DictNode. _make_node()
       delegates this to _DictNode.from_configuration(). This class method creates the
       children of the node, calling _make_node() on each child. The process continues
       recursively, and at the end the root node will contain two children: a _ValueNode
       representing the "${bar.baz}" string and a _DictNode representing the "bar"
       dictionary. This _DictNode has one child: a _ValueNode representing the number
       42.

    2. resolve() calls .resolve() on the root node. Because the root node is a
       _DictNode, resolving it amounts to calling the .resolve() method on each of its
       children. Suppose the "foo" child is first.

    3. Because the "foo" child is a _ValueNode representing a string, its .resolve()
       method begins by interpolating the string using Jinja2. Before interpolation, the
       Jinja2 environment is set up to allow access to the root of the configuration
       tree. More precisely, because the root node is a _DictNode, an instance of
       _LazyDict is created wrapping the root node. A custom Jinja2 context class is
       made by overriding the resolve_or_missing() method to look up keys in the
       _LazyDict first, and then fall back to the default behavior of searching the
       template variables.

    4. Jinja2 begins interpolating the string. It sees the reference to ${bar.baz} and
       looks up "bar" in the context. The overridden resolve_or_missing() method first
       attempts to get the "bar" key from the _LazyDict. The _LazyDict recognizes the
       key as a reference to a child node of type _DictNode, and so it returns a new
       _LazyDict wrapping the child node. Jinja2 next looks up "baz" in this new
       _LazyDict. This time, the _LazyDict recognizes the key as a reference to a child
       _ValueNode, and so it triggers the resolution of the child node by calling
       its .resolve() method. Interpolation of the string pauses momentarily while the
       child node is resolved.

    5. When .resolve() is called on the _ValueNode representing the number 42,
       interpolation is skipped since the contained value is not a string. The schema
       expects this value to be an integer, so the arithmetic parser is called on the
       value, and the result (42) is returned.

    6. Jinja resumes interpolating the string, replacing ${bar.baz} with the resolved
       value of 42. The string is now "42 + 1".

    7. The schema expects the value of "foo" to be an integer, so the arithmetic parser
       is called on the string "42 + 1", and the result (43) is returned. This is the
       resolved value of the "foo" key.

    8. Now that "foo" has been resolved, the code backtracks to the _DictNode's
       .resolve() method, which then attempts to resolve the "bar" child. This is a
       _DictNode, so its .resolve() method is called. This call attempts to resolve its
       only child, the _ValueNode representing the number 42. This node was already
       resolved during the resolution of "foo", and the resolved value is returned.

    9. The _DictNode representing "bar" is now fully resolved, and the _DictNode
       representing the root of the configuration tree is also fully resolved. The
       resolved configuration is returned from resolve().

"""

from typing import (
    Dict,
    List,
    Mapping,
    Optional,
    Union,
    Callable,
    Any,
)
import abc
import copy
import dataclasses
import typing

import jinja2

from . import parsers as _parsers, functions as _functions, types as _types
from ._schemas import validate_schema as _validate_schema
from .exceptions import Error, ResolutionError
from .types import FunctionArgs, Function, RawString, RecursiveString


# defaults =============================================================================

# the default parsers used by resolve()
DEFAULT_PARSERS = {
    "integer": _parsers.arithmetic(int),
    "float": _parsers.arithmetic(float),
    "string": str,
    "boolean": _parsers.logic,
    "date": _parsers.smartdate,
    "datetime": _parsers.smartdatetime,
    "any": lambda x: x,
}

# the default functions available to resolve()
DEFAULT_FUNCTIONS = {
    "raw": _functions.raw,
    "splice": _functions.splice,
    "update_shallow": _functions.update_shallow,
    "update": _functions.update_shallow,
    "concatenate": _functions.concatenate,
}


def default_template_variables_factory(
    root: Union["_LazyDict", "_LazyList", "_LazyFunctionCall", None],
):
    """Create a template variables dictionary for Jinja2 interpolation.

    Parameters
    ----------
    root : Union[_LazyDict, _LazyList, _LazyFunctionCall]
        The root of the configuration tree.

    Returns
    -------
    Mapping[str, Any]
        A dictionary of template variables.

    """
    return {"get_root": lambda: root}


# basic types ==========================================================================


@dataclasses.dataclass
class _ResolutionContext:
    """Holds information available at the time that a node is resolved.

    Attributes
    ----------
    parsers : Mapping[str, Callable]
        Parsers for different types of values.
    functions : Mapping[str, Function]
        Functions that can be called from the configuration.

    """

    parsers: Mapping[str, Callable]
    functions: Mapping[str, "Function"]


# sentinel object denoting that a node is currently being resolved
_PENDING = object()

# lazy containers ======================================================================
#
# These lazy containers are used to represent the unresolved parts of the configuration
# during resolution. They are passed to Jinja as template variables available during
# string interpolation, and they are provided to functions as part of their input so
# that they can reference other parts of the configuration as well. Accessing an element
# in a lazy container triggers the resolution of that element if it is a function node
# or a value node. Otherwise, it returns another lazy container.


class _LazyDict(_types.LazyDict):
    """Implements LazyDict using a _DictNode as the backing data structure."""

    def __init__(self, dict_node: "_DictNode"):
        self.dict_node = dict_node

    def __getitem__(self, key) -> Union["_LazyDict", "_LazyList", _types.Configuration]:
        child = self.dict_node[key]

        if isinstance(child, _FunctionCallNode):
            child = child.evaluate().resolve()

        if isinstance(child, _DictNode):
            return _LazyDict(child)
        elif isinstance(child, _ListNode):
            return _LazyList(child)
        elif isinstance(child, _ValueNode):
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
        return self.dict_node.resolve()

    def get_keypath(self, keypath: Union[_types.KeyPath, str]) -> _types.Configuration:
        return _get_keypath(self, keypath, str)


class _LazyList(_types.LazyList):
    """Implements LazyList using a _ListNode as the backing data structure."""

    def __init__(self, list_node: "_ListNode"):
        self.list_node = list_node

    def __getitem__(self, ix) -> Union["_LazyDict", "_LazyList", _types.Configuration]:
        if ix not in range(len(self)):
            raise IndexError(ix)

        child = self.list_node[ix]

        if isinstance(child, _FunctionCallNode):
            child = child.evaluate().resolve()

        if isinstance(child, _DictNode):
            return _LazyDict(child)
        elif isinstance(child, _ListNode):
            return _LazyList(child)
        elif isinstance(child, _ValueNode):
            return child.resolve()

    def __iter__(self):
        for i in range(len(self)):
            yield self[i]

    def __len__(self):
        return len(self.list_node.children)

    def resolve(self) -> _types.ConfigurationList:
        return self.list_node.resolve()

    def get_keypath(self, keypath: Union[_types.KeyPath, str]) -> _types.Configuration:
        return _get_keypath(self, keypath, int)


class _LazyFunctionCall(_types.LazyFunctionCall):
    """Implements LazyFunction using a _FunctionNode as the backing data structure."""

    def __init__(self, function_node: "_FunctionCallNode"):
        self.function_node = function_node

    def resolve(self):
        return self.function_node.evaluate().resolve()

    def get_keypath(self, keypath: Union[_types.KeyPath, str]) -> _types.Configuration:
        node = self.function_node.evaluate()
        if isinstance(node, _DictNode):
            return _LazyDict(node).get_keypath(keypath)
        elif isinstance(node, _ListNode):
            return _LazyList(node).get_keypath(keypath)

    def __getitem__(self, key) -> Union["_LazyDict", "_LazyList", _types.Configuration]:
        node = self.function_node.evaluate()
        if isinstance(node, _DictNode):
            return _LazyDict(node)[key]
        elif isinstance(node, _ListNode):
            return _LazyList(node)[key]


def _make_lazy_container(
    node: Union["_DictNode", "_ListNode", "_FunctionCallNode"],
) -> Union[_LazyDict, _LazyList, _LazyFunctionCall]:
    """Create a lazy container from a node."""
    if isinstance(node, _DictNode):
        return _LazyDict(node)
    elif isinstance(node, _ListNode):
        return _LazyList(node)
    elif isinstance(node, _FunctionCallNode):
        return _LazyFunctionCall(node)


def _get_keypath(
    container: Union["_LazyDict", "_LazyList", "_LazyFunctionCall"],
    keypath: Union[_types.KeyPath, str],
    cast_key: Optional[Callable[[str], Any]] = None,
) -> _types.Configuration:
    if cast_key is None:
        cast_key = lambda x: x

    if isinstance(keypath, str):
        keypath = tuple(keypath.split("."))

    if len(keypath) == 1:
        result = container[cast_key(keypath[0])]
        if isinstance(result, (_LazyDict, _LazyList)):
            return result.resolve()
        else:
            return result
    else:
        first, *rest_of_path = keypath

        first = container[cast_key(first)]

        if not isinstance(first, (_LazyDict, _LazyList)):
            raise KeyError(first)

        return first.get_keypath(tuple(rest_of_path))


# node types ===========================================================================
#
# A configuration tree is the internal representation of a configuration. The
# nodes of tree come in three types:
#
#   ValueNode: a leaf node in the tree that can be resolved into a non-container value,
#       such as an integer. Can reference other ValueNodes.
#
#   DictNode: an internal node that behaves like a dictionary, mapping keys to child
#       nodes.
#
#   ListNode: an internal node that behaves like a list, mapping indices to child
#       nodes.
#

# base node ----------------------------------------------------------------------------


class _Node(abc.ABC):
    """Abstract base class for all nodes in a configuration tree.

    Attributes
    ----------
    parent : Optional[Node]
        The parent of this node. Can be `None`, in which case this is the root
        of the tree.

    """

    def __init__(self, parent: Optional["_Node"] = None):
        self.parent = parent

        # cache the root of the tree
        self._root = None

    @property
    def root(self) -> "_Node":
        """The root of the configuration tree."""
        if self._root is None:
            if self.parent is None:
                self._root = self
            else:
                self._root = self.parent.root
        return self._root

    @abc.abstractmethod
    def resolve(self) -> _types.Configuration:
        """Recursively resolve the node into a configuration."""
        ...


# dict nodes ---------------------------------------------------------------------------


def _populate_required_children(
    children: Dict[str, _Node],
    dct: _types.ConfigurationDict,
    dict_schema: _types.Schema,
    resolution_context: _ResolutionContext,
    parent: _Node,
    keypath: _types.KeyPath,
):
    """Populates the required children of a DictNode.

    This uses the schema to determine which keys are required and then creates
    the child nodes for those keys. If a required key is missing, a
    ResolutionError is raised.

    Modifications are made to the children dictionary in place.

    """
    required_keys = dict_schema.get("required_keys", {})

    for key, key_schema in required_keys.items():
        if key not in dct:
            raise ResolutionError("Missing required key.", (keypath + (key,)))

        children[key] = _make_node(
            dct[key], key_schema, resolution_context, parent, keypath + (key,)
        )


def _populate_optional_children(
    children: Dict[str, _Node],
    dct: _types.ConfigurationDict,
    dict_schema: _types.Schema,
    resolution_context: _ResolutionContext,
    parent: _Node,
    keypath: _types.KeyPath,
):
    """Populates the optional children of a DictNode.

    This uses the schema to determine which keys are optional and then creates
    the child nodes for those keys. If an optional key is missing and a default
    is provided, the default is used. If an optional key is missing and no
    default is provided, the key is simply not added to the children.

    Modifications are made to the children dictionary in place.

    """
    optional_keys = dict_schema.get("optional_keys", {})

    for key, key_schema in optional_keys.items():
        if key in dct:
            # key is not missing
            value = dct[key]
        elif "default" in key_schema:
            # key is missing and default was provided
            value = key_schema["default"]
        else:
            # key is missing and no default was provided
            continue

        children[key] = _make_node(
            value, key_schema, resolution_context, parent, keypath + (key,)
        )


def _populate_extra_children(
    children: Dict[str, _Node],
    dct: _types.ConfigurationDict,
    dict_schema: _types.Schema,
    resolution_context: _ResolutionContext,
    parent: _Node,
    keypath: _types.KeyPath,
):
    """Populates the extra children of a DictNode.

    This uses the schema to determine how to handle extra keys in the raw
    configuration dictionary. If extra keys are not allowed, a ResolutionError
    is raised. If extra keys are allowed, the schema for the extra keys is used
    to create the child nodes.

    Modifications are made to the children dictionary in place.

    """
    required_keys = dict_schema.get("required_keys", {})

    optional_keys = dict_schema.get("optional_keys", {})
    expected_keys = set(required_keys) | set(optional_keys)
    extra_keys = dct.keys() - expected_keys

    if extra_keys and "extra_keys_schema" not in dict_schema:
        raise ResolutionError(f"Unexpected extra key.", keypath + (extra_keys.pop(),))

    for key in extra_keys:
        children[key] = _make_node(
            dct[key],
            dict_schema["extra_keys_schema"],
            resolution_context,
            parent,
            keypath + (key,),
        )


class _DictNode(_Node):
    """Represents an internal dictionary node in a configuration tree.

    Attributes
    ----------
    resolution_context : _ResolutionContext
        The context in which the node is being resolved.
    children : Dict[str, Node]
        A dictionary of child nodes.
    parent : Optional[Node]
        The parent of this node. Can be `None`, in which case this is the root
        of the tree.

    """

    def __init__(
        self,
        resolution_context: _ResolutionContext,
        children: Optional[Dict[str, _Node]] = None,
        parent: Optional[_Node] = None,
    ):
        super().__init__(parent)
        self.resolution_context = resolution_context
        self.children: Dict[str, _Node] = {} if children is None else children

    @classmethod
    def from_configuration(
        cls,
        dct: _types.ConfigurationDict,
        schema: _types.Schema,
        keypath: _types.KeyPath,
        resolution_context: _ResolutionContext,
        parent: Optional[_Node] = None,
    ) -> "_DictNode":
        """Construct a DictNode from a raw configuration dictionary and its schema.

        Parameters
        ----------
        raw_dct : ConfigurationDict
            The raw configuration dictionary.
        schema : Schema
            The schema to enforce on the raw configuration dictionary.
        keypath : _types.KeyPath
            The keypath to this node in the configuration tree.
        resolution_context : ResolutionContext
            The context in which the node is being resolved.
        parent : Optional[Node]
            The parent of this node. Can be `None`.

        """
        node = cls(resolution_context, parent=parent)

        if schema["type"] == "any":
            schema = {
                "type": "dict",
                "extra_keys_schema": {"type": "any", "nullable": True},
            }

        children = {}

        # these private functiuons are used to populate the children of the
        # node. they also enforce the schema by checking that all required keys
        # are present and that no extra keys are present. It is most natural to
        # do this validation here and not in .resolve() because the process of
        # populating children already requires us to check if children are missing; for
        # example, to fill in default values.

        _populate_required_children(
            children,
            dct,
            schema,
            resolution_context,
            node,
            keypath,
        )
        _populate_optional_children(
            children,
            dct,
            schema,
            resolution_context,
            node,
            keypath,
        )
        _populate_extra_children(
            children,
            dct,
            schema,
            resolution_context,
            node,
            keypath,
        )

        node.children = children
        return node

    def __getitem__(self, key: str) -> _Node:
        """Get a child node by key."""
        return self.children[key]

    def resolve(self) -> _types.ConfigurationDict:
        """Recursively resolve the DictNode into a configuration dictionary."""
        # first, we evaluate all function nodes contained in the dictionary
        for key, child_node in self.children.items():
            if isinstance(child_node, _FunctionCallNode):
                self.children[key] = child_node.evaluate()

        result = {}
        for key, child_node in self.children.items():
            assert isinstance(child_node, (_DictNode, _ListNode, _ValueNode))
            result[key] = child_node.resolve()

        return result


# list nodes ---------------------------------------------------------------------------


class _ListNode(_Node):
    """Represents an internal list node in a configuration tree.

    Attributes
    ----------
    children : List[Node]
        A list of the node's children.
    parent : Optional[Node]
        The parent of this node. Can be `None`, in which case this is the root
        of the tree.
    resolution_context : ResolutionContext
        The context in which the node is being resolved.

    """

    def __init__(
        self,
        resolution_context: _ResolutionContext,
        children: Optional[List[_Node]] = None,
        parent: Optional[_Node] = None,
    ):
        super().__init__(parent)
        self.resolution_context = resolution_context
        self.children: List[_Node] = [] if children is None else []

    @classmethod
    def from_configuration(
        cls,
        lst: _types.ConfigurationList,
        list_schema: _types.Schema,
        keypath: _types.KeyPath,
        resolution_context: _ResolutionContext,
        parent: Optional[_Node] = None,
    ) -> "_ListNode":
        """Make an internal list node from a raw list and recurse on the children."""
        node = cls(resolution_context, parent=parent)

        if list_schema["type"] == "any":
            list_schema = {
                "type": "list",
                "element_schema": {"type": "any", "nullable": True},
            }

        child_schema = list_schema["element_schema"]

        children = []
        for i, lst_value in enumerate(lst):
            r = _make_node(
                lst_value,
                child_schema,
                resolution_context,
                node,
                keypath + (i,),
            )
            children.append(r)

        node.children = children
        return node

    def __getitem__(self, ix) -> _Node:
        return self.children[ix]

    def resolve(self) -> _types.ConfigurationList:
        """Recursively resolve the ListNode into a list."""
        # first, we evaluate all function nodes contained in the list
        for i, child_node in enumerate(self.children):
            if isinstance(child_node, _FunctionCallNode):
                self.children[i] = child_node.evaluate()

        result = []
        for child_node in self.children:
            assert isinstance(child_node, (_DictNode, _ListNode, _ValueNode))
            result.append(child_node.resolve())

        return result


# value nodes --------------------------------------------------------------------------


class _ValueNode(_Node):
    """Represents a leaf of the configuration tree.

    Attributes
    ----------
    raw : ConfigurationValue
        The "raw" value of the leaf node as it appeared in the raw configuration.
        This can be any type.
    type_ : str
        A string describing the expected type of this leaf once resolved. Used
        to determined which parser to use from the resolution context.
    keypath : _types.KeyPath
        The keypath to this node in the configuration tree.
    resolution_context : ResolutionContext
        The context in which the node is being resolved.
    nullable : Optional[bool]
        Whether the value can be None or not. If raw is None this is True, it
        is not parsed (no matter what type_ is). Default: False.
    parent : Optional[Node]
        The parent of this node. Can be `None`, in which case this is the root.

    """

    def __init__(
        self,
        value: _types.ConfigurationValue,
        type_,
        keypath: _types.KeyPath,
        resolution_context: _ResolutionContext,
        nullable: bool = False,
        parent: Optional[_Node] = None,
    ):
        super().__init__(parent)
        self.value = value
        self.type_ = type_
        self.keypath = keypath
        self.resolution_context = resolution_context
        self.nullable = nullable

        # The resolved value of the leaf node. There are two special values. If
        # this is None, the resolution process has not yet discovered
        # the leaf node (this is the default value). If this is _PENDING, a
        # step in the resolution process has started to resolve the leaf. Otherwise,
        # this contains the resolved value. Necessary in order to detect circular
        # references.
        self._resolved = None

    @classmethod
    def from_configuration(
        cls,
        value: _types.ConfigurationValue,
        schema: _types.Schema,
        keypath: _types.KeyPath,
        resolution_context: _ResolutionContext,
        parent: Optional[_Node] = None,
        nullable: bool = False,
    ) -> "_ValueNode":
        """Create a leaf node from the raw configuration and schema."""
        return cls(
            value,
            schema["type"],
            keypath,
            resolution_context,
            nullable=nullable,
            parent=parent,
        )

    def resolve(self) -> _types.ConfigurationValue:
        """Resolve the leaf's value by 1) interpolating and 2) parsing.

        Returns
        -------
        The resolved value.

        """
        if isinstance(self.value, RawString):
            # check that the expected type is a string (or any)
            if self.type_ not in ("string", "any"):
                raise ResolutionError(
                    "Schema expected something other than a string.", self.keypath
                )

            return self.value

        if self._resolved is _PENDING:
            raise ResolutionError("Circular reference", self.keypath)

        if self._resolved is not None:
            self._resolved = typing.cast(_types.ConfigurationValue, self._resolved)
            return self._resolved

        self._resolved = _PENDING

        if isinstance(self.value, RecursiveString):
            # interpolate until the string no longer changes
            changed = True
            s = self.value
            while changed:
                old_s = s
                s = self._safely(self._interpolate, s)
                changed = s != old_s
        elif isinstance(self.value, str):
            s = self._safely(self._interpolate, self.value)
        else:
            s = self.value

        if self.nullable and self.value is None:
            self._resolved = None
        else:
            self._resolved = self._safely(self._parse, s, self.type_)

        return self._resolved

    def _interpolate(self, s: str) -> str:
        """Replace a reference keypath with its resolved value.

        Parameters
        ----------
        s : str
            A configuration string with references to other values.

        Returns
        -------
        The interpolated string.

        """
        environment = jinja2.Environment(
            variable_start_string="${", variable_end_string="}"
        )

        if isinstance(self.root, (_DictNode, _ListNode, _FunctionCallNode)):
            root = _make_lazy_container(self.root)
        else:
            root = None

        if root is not None:
            # we create this custom context to carefully control how Jinja2 resolves
            # references. The typical way to provide template variables to Jinja2 is to
            # pass a dictionary-like object to the .render() method. This object is used
            # by Jinja to create a "context". However, in creating the context iteself,
            # Jinja immediately accesses the values in the top-level of the dictionary.
            # This is problematic because the values in the dictionary may be references
            # to other parts of the configuration. If Jinja2 accesses these values
            # before the references are resolved, it can create circular dependencies.
            # To avoid this, we create a custom context class that only resolves
            # references when they are accessed during interpolation, and not during the
            # creation of the context. The root of the configuration is stored in a
            # _LazyDict, _LazyList, or _LazyFunctionCall, which are lazy containers that
            # resolve their contents only when accessed. If a key is not found in the
            # lazy container, Jinja2 will fall back to the default behavior of looking
            # up the key in the template variables.
            class CustomContext(jinja2.runtime.Context):
                def resolve_or_missing(self, key):
                    try:
                        return root[key]
                    except (KeyError, IndexError):
                        return super().resolve_or_missing(key)

            environment.context_class = CustomContext

        template = environment.from_string(s)

        template_variables = default_template_variables_factory(root)

        try:
            return template.render(template_variables)
        except jinja2.exceptions.UndefinedError as exc:
            raise ResolutionError(str(exc), self.keypath)

    def _parse(self, s, type_) -> _types.ConfigurationValue:
        """Parse the configuration string into its final type."""
        parsers = self.resolution_context.parsers

        try:
            parser = parsers[type_]
        except KeyError:
            raise ResolutionError(
                f"No parser provided for type: '{type_}'.", self.keypath
            )

        return parser(s)

    def _safely(self, fn, *args):
        """Apply the function and catch any exceptions, raising a ResolutionError."""
        try:
            return fn(*args)
        except Error as exc:
            raise ResolutionError(str(exc), self.keypath)


# function nodes -----------------------------------------------------------------------


def _is_dunder(key: str) -> bool:
    return key.startswith("__") and key.endswith("__")


def _check_for_function_call(dct: _types.ConfigurationDict) -> Union[str, None]:
    """Checks if a configuration represents a function call.

    A function call is a dictionary with a single key of the form
    "__<function_name>__".

    Parameters
    ----------
    dct : ConfigurationDict
        The dictionary to check.

    Returns
    -------
    Union[str, None]
        The name of the function if the dictionary represents a function call,
        `None` otherwise.

    Raises
    ------
    ValueError
        If the dictionary has a key of the form "__<function_name>__" but there
        are other keys present, making this an invalid function call.

    """

    is_potential_function_call = any(_is_dunder(key) for key in dct.keys())

    if is_potential_function_call:
        if len(dct) != 1:
            raise ValueError("Invalid function call.")
        else:
            key = next(iter(dct.keys()))
            return key[2:-2]
    else:
        return None


def _has_dunder_key(dct: _types.ConfigurationDict) -> bool:
    """Checks if a configuration dictionary has a key of the form "__<function_name>__".

    Parameters
    ----------
    dct : ConfigurationDict
        The dictionary to check.

    Returns
    -------
    bool
        True if the dictionary has a key of the form "__<function_name>__", False otherwise.

    """
    return any(_is_dunder(key) for key in dct.keys())


class _FunctionCallNode(_Node):
    def __init__(
        self,
        keypath: _types.KeyPath,
        resolution_context: _ResolutionContext,
        function: Function,
        input: _types.Configuration,
        schema: _types.Schema,
        parent: Optional[_Node] = None,
    ):
        super().__init__(parent)
        self.keypath = keypath
        self.resolution_context = resolution_context
        self.schema = schema
        self.function = function
        self.input = input

    @classmethod
    def from_configuration(
        cls,
        dct: _types.ConfigurationDict,
        schema: _types.Schema,
        keypath: _types.KeyPath,
        resolution_context: _ResolutionContext,
        parent: Optional[_Node] = None,
    ) -> "_FunctionCallNode":
        try:
            function_name = _check_for_function_call(dct)
        except ValueError as exc:
            raise ResolutionError(str(exc), keypath)

        if function_name is None:
            raise ResolutionError("Invalid function call.", keypath)

        if function_name not in resolution_context.functions:
            raise ResolutionError(f"Unknown function: {function_name}", keypath)

        # the function name is the key, the input to the function is its
        # associated value
        function = resolution_context.functions[function_name]
        if not isinstance(function, Function):
            function = Function(function)

        input = dct["__" + function_name + "__"]

        return cls(
            keypath,
            resolution_context,
            function,
            input,
            schema,
            parent=parent,
        )

    def evaluate(self) -> _Node:
        """Evaluate the function node and return the result."""
        if self.function.resolve_input:
            input_node = _make_node(
                self.input,
                {"type": "any"},
                self.resolution_context,
                parent=self,
                keypath=self.keypath,
            )
            input = input_node.resolve()
        else:
            input = self.input

        if isinstance(self.root, (_DictNode, _ListNode, _FunctionCallNode)):
            root = _make_lazy_container(self.root)
        else:
            root = None

        args = FunctionArgs(
            input,
            root,
            self.keypath,
        )

        # evaluate the function itself
        output = self.function(args)

        return _make_node(
            output,
            self.schema,
            self.resolution_context,
            parent=self,
            keypath=self.keypath,
        )

    def resolve(self) -> _types.Configuration:
        """Evaluate the function node and return the result."""
        return self.evaluate().resolve()


# make_node() ==========================================================================


def _make_node(
    cfg,
    schema,
    resolution_context: _ResolutionContext,
    parent=None,
    keypath=tuple(),
):
    """Recursively constructs a configuration tree from a raw configuration.

    The raw configuration can be a dictionary, list, or a non-container type. In any
    case, the provided schema must match the type of the raw configuration; for example,
    if the raw configuration is a dictionary, the schema must be a dict schema.

    A reference node is created if the configuration is a string of the form "${...}",
    _and_ the schema is expecting either a dictionary, a list, or anything. Otherwise,
    it is better to treat it as a value node (because value nodes allow more advanced
    parsing and interpolation).


    Parameters
    ----------
    raw_cfg
        A dictionary, list, or non-container type representing the "raw", unresolved
        configuration.
    schema
        A schema dictionary describing the types of the configuration tree nodes.
    parent
        The parent node of the node being built. Can be `None`.

    Returns
    -------
        The configuration tree.

    """
    if cfg is None:
        if "nullable" in schema and schema["nullable"]:
            return _ValueNode.from_configuration(
                None,
                {"type": "any"},
                keypath,
                resolution_context,
                parent=parent,
            )
        else:
            raise ResolutionError("Unexpectedly null.", keypath)

    # construct the configuration tree
    # the configuration tree is a nested container whose terminal leaf values
    # are ValueNodes. "Internal" nodes are dictionaries or lists.
    if isinstance(cfg, dict):
        # check if this is a function call
        if _has_dunder_key(cfg):
            return _FunctionCallNode.from_configuration(
                cfg,
                schema,
                keypath,
                resolution_context,
                parent=parent,
            )
        return _DictNode.from_configuration(
            cfg, schema, keypath, resolution_context, parent=parent
        )
    elif isinstance(cfg, list):
        return _ListNode.from_configuration(
            cfg,
            schema,
            keypath,
            resolution_context,
            parent=parent,
        )
    else:
        return _ValueNode.from_configuration(
            cfg,
            schema,
            keypath,
            resolution_context,
            parent=parent,
        )


# resolve() ============================================================================


def _is_leaf(x):
    return not isinstance(x, dict) and not isinstance(x, list)


def _copy_into(dst, src):
    """Recursively copy the leaf values from src to dst.

    Used when preserve_type = True in resolve()
    """
    if isinstance(dst, dict):
        keys = dst.keys()
    elif isinstance(dst, list):
        keys = range(len(dst))
    else:
        raise ValueError("The destination must be a dictionary or list.")

    for key in keys:
        x = src[key]
        if _is_leaf(x):
            dst[key] = src[key]
        else:
            _copy_into(dst[key], src[key])


def _update_parsers(overrides):
    """Override some of the default parsers.

    Returns a dictionary of all parsers."""
    parsers = DEFAULT_PARSERS.copy()
    if overrides is not None:
        for type_, parser in overrides.items():
            parsers[type_] = parser
    return parsers


@typing.overload
def resolve(
    raw_cfg: dict,
    schema: _types.Schema,
    override_parsers: Optional[Mapping[str, Callable]] = None,
    schema_validator: Callable[[_types.Schema], None] = _validate_schema,
    preserve_type: bool = False,
) -> dict:
    pass


@typing.overload
def resolve(
    raw_cfg: list,
    schema: _types.Schema,
    override_parsers: Optional[Mapping[str, Callable]] = None,
    schema_validator: Callable[[_types.Schema], None] = _validate_schema,
    preserve_type: bool = False,
) -> list:
    pass


@typing.overload
def resolve(
    raw_cfg: Any,
    schema: _types.Schema,
    override_parsers: Optional[Mapping[str, Callable]] = None,
    schema_validator: Callable[[_types.Schema], None] = _validate_schema,
    preserve_type: bool = False,
) -> Any:
    pass


def resolve(
    raw_cfg: _types.Configuration,
    schema: _types.Schema,
    override_parsers: Optional[Mapping[str, Callable]] = None,
    schema_validator: Callable[[_types.Schema], None] = _validate_schema,
    preserve_type: bool = False,
    functions=None,
    parsers=None,
    global_variables=None,
    filters=None,
) -> _types.Configuration:
    """Resolve a raw configuration by interpolating and parsing its entries.

    Parameters
    ----------
    raw_cfg
        The raw configuration.
    schema
        The schema describing the types in the raw configuration.
    override_parsers
        A dictionary mapping leaf type names to parser functions. The parser functions
        should take the raw value (after interpolation) and convert it to the specified
        type. If this is not provided, the default parsers are used.
    preserve_type : bool (default: False)
        If False, the return value of this function is a plain dictionary. If this is
        True, however, the return type will be the same as the type of raw_cfg. See
        below for details.

    Raises
    ------
    InvalidSchemaError
        If the schema is not valid.
    ResolutionError
        If the configuration does not match the schema, if there is a circular
        reference, or there is some other issue with the configuration itself.

    Notes
    -----

    The raw configuration can be a dictionary, list, or a non-container type;
    resolution will be done recursively. In any case, the provided schema must
    match the type of the raw configuration; for example, if the raw
    configuration is a dictionary, the schema must be a dict schema.

    Default parsers are provided which attempt to convert raw values to the
    specified types. They are:

        - "integer": :func:`smartconfig.parsers.arithmetic` with type `int`
        - "float": :func:`smartconfig.parsers.arithmetic` with type `float`
        - "string": n/a.
        - "boolean": :func:`smartconfig.parsers.logic`
        - "date": :func:`smartconfig.parsers.smartdate`
        - "datetime": :func:`smartconfig.parsers.smartdatetime`

    These parsers provide "smart" behavior, allowing values to be expressed in
    a variety of formats. They can be overridden by providing a dictionary of
    parsers to `override_parsers`.

    This function uses the `jinja2` template engine for interpolation. This
    means that many powerful `Jinja2` features can be used. For example, a
    `Jinja2` supports a ternary operator, so dictionaries can contain
    expressions like the following:"

    .. code-block:: python

        {
            'x': 10,
            'y': 3,
            'z': '${ this.x if this.x > this.y else this.y }'
        }

    Typically, `raw_cfg` will be a plain Python dictionary. Sometimes, however,
    it may be another mapping type that behaves like a `dict`, but has some
    additional functionality. One example is the `ruamel` package which is
    capable of round-tripping yaml, comments and all. To accomplish this,
    ruamel produces a dict-like object which stores the comments internally. If
    we resolve this dict-like object with :code:`preserve_type = False`, then
    we'll lose these comments; therefore, we should use :code:`preserve_type =
    True`.

    At present, type preservation is done by constructing the resolved output
    as normal, but then making a deep copy of `raw_cfg` and recursively copying
    each leaf value into this deep copy. Therefore, there is a performance
    cost.

    """
    if schema_validator is not None:
        schema_validator(schema)

    if functions is None:
        functions = {}

    if global_variables is None:
        global_variables = {}

    parsers = _update_parsers(override_parsers)

    resolution_context = _ResolutionContext(parsers, functions)

    root = _make_node(raw_cfg, schema, resolution_context)

    resolved = root.resolve()

    if not preserve_type:
        return resolved
    else:
        output = copy.deepcopy(raw_cfg)
        _copy_into(output, resolved)
        return output
