"""Provides the resolve() function.

This module does the heavy-lifting of resolving configurations.

We describe the implementation details of the resolve() function here. For instructions
on how to use it, see the main documentation.

Approach
========

In the documentation, it is described how a configuration can be interpreted as a
directed "configuration graph", and how config resolution is a depth-first search on
this graph. This module works by building a concrete representation of the configuration
graph and performing that traversal.

Each node in the graph is represented by one of four node classes: _DictNode, _ListNode,
_ValueNode, and _FunctionCallNode. Each has a .resolve() method that recursively
resolves the node and its children. Each node also has a corresponding
.from_configuration() method that constructs the node from a configuration of the
appropriate type -- e.g., _DictNode.from_configuration() builds a _DictNode from a
dictionary, _ListNode.from_configuration() builds a _ListNode from a list, etc. The
exception is a _FunctionCallNode, which has no .from_configuration() method because it
is easy enough to create using its constructor.

The creation of the tree is orchestrated by the _make_node() function, whose job is to
take an arbitrary configuration and determine which node class represents it. This
function is called with the whole configuration to create the root node, and is also
called by the container node classes to create their children. _make_node() is also
responsible for detecting when a dictionary represents a function call and creating a
_FunctionCallNode in that case.

The main function, resolve(), is a thin wrapper around the root node's .resolve()
method. It constructs the root node using _make_node(), calls .resolve() on it, and
returns the result.

String Interpolation with Jinja2
================================

String interpolation (like in "${foo.bar}") is delegated to Jinja2. During the
resolution of a _ValueNode representing a string, the string is passed to Jinja2 for
interpolation. Other parts of the configuration tree are made available to Jinja2 as
template variables. Typically, this is done by passing a dictionary to Jinja2's render()
method. However, we cannot pass the fully-resolved configuration tree at the time of
interpolation, because it hasn't been fully resolved at that point. Instead, the root of
the configuration tree is passed as an "unresolved" container -- either an
_UnresolvedDict, _UnresolvedList, or _UnresolvedFunctionCall. When an element of one of
these containers is accessed, the resolution process is triggered for that element if it
is a function node or a value node. Otherwise, another unresolved collection is
returned.

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

    1. resolve() calls _make_node() to create the root node, which in this case a
       _DictNode. _make_node() delegates this to _DictNode.from_configuration(). This
       class method creates the children of the node, calling _make_node() on each
       child. The process continues recursively, and at the end the root node will
       contain two children: a _ValueNode representing the "${bar.baz}" string and a
       _DictNode representing the "bar" dictionary. This _DictNode has one child: a
       _ValueNode representing the number 42.

    2. resolve() calls .resolve() on the root node. Because the root node is a
       _DictNode, resolving it amounts to calling the .resolve() method on each of its
       children. Suppose the "foo" child is first.

    3. Because the "foo" child is a _ValueNode representing a string, its .resolve()
       method begins by interpolating the string using Jinja2. Before interpolation, the
       Jinja2 environment is set up to allow access to the root of the configuration
       tree. More precisely, because the root node is a _DictNode, an instance of
       _UnresolvedDict is created wrapping the root node. A custom Jinja2 context class
       is made by overriding the .resolve_or_missing() method to look up keys in the
       _UnresolvedDict first, falling back to the default behavior of searching
       the template variables if the variable is not found.

    4. Jinja2 begins interpolating the string. It sees the reference to ${bar.baz} and
       looks up "bar" in the context. The overridden .resolve_or_missing() method first
       attempts to get the "bar" key from the _UnresolvedDict. The _UnresolvedDict
       recognizes the key as a reference to a child node of type _DictNode, and so it
       returns a new _UnresolvedDict wrapping the child node. Jinja2 next looks up "baz"
       in this new _UnresolvedDict. This time, the _UnresolvedDict recognizes the key as
       a reference to a child _ValueNode, and so it triggers the resolution of the child
       node by calling its .resolve() method. Interpolation of the string pauses
       momentarily while the child node is resolved.

    5. When .resolve() is called on the _ValueNode representing the number 42,
       interpolation is skipped since the contained value is not a string. The schema
       expects this value to be an integer, so the arithmetic converter is called on the
       value, and the result (42) is returned.

    6. Jinja resumes interpolating the string, replacing ${bar.baz} with the resolved
       value of 42. The string is now "42 + 1".

    7. The schema expects the value of "foo" to be an integer, so the arithmetic converter
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
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Union,
)
import abc
import copy
import typing

import jinja2

from . import converters as _converters, functions as _functions, types as _types
from .exceptions import Error, ResolutionError


# unresolved containers ================================================================
#
# These containers are used to represent the configuration while it is being resolved.
# They are passed to Jinja as template variables available during string interpolation,
# and they are provided to functions as part of their input so that they can reference
# other parts of the configuration as well. Accessing an element in a unresolved
# container triggers the resolution of that element if it is a function node or a value
# node. Otherwise, it returns another unresolved container.

# _UnresolvedDict ----------------------------------------------------------------------


class _UnresolvedDict(_types.UnresolvedDict):
    """Implements UnresolvedDict using a _DictNode as the backing data structure."""

    def __init__(self, dict_node: "_DictNode"):
        self.dict_node = dict_node

    def __getitem__(
        self, key
    ) -> Union["_UnresolvedDict", "_UnresolvedList", _types.Configuration]:
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
        """Resolve all values recursively, returning a ConfigurationDict."""
        return self.dict_node.resolve()

    def get_keypath(self, keypath: Union[_types.KeyPath, str]) -> _types.Configuration:
        """Resolve the value at the given keypath."""
        return _get_keypath(self, keypath, str)


# _UnresolvedList ----------------------------------------------------------------------


class _UnresolvedList(_types.UnresolvedList):
    """Implements UnresolvedList using a _ListNode as the backing data structure."""

    def __init__(self, list_node: "_ListNode"):
        self.list_node = list_node

    def __getitem__(
        self, ix
    ) -> Union["_UnresolvedDict", "_UnresolvedList", _types.Configuration]:
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
        elif isinstance(child, _ValueNode):
            return child.resolve()

    def __iter__(self):
        for i in range(len(self)):
            yield self[i]

    def __len__(self):
        return len(self.list_node.children)

    def resolve(self) -> _types.ConfigurationList:
        """Resolve all values recursively, returning a ConfigurationList."""
        return self.list_node.resolve()

    def get_keypath(self, keypath: Union[_types.KeyPath, str]) -> _types.Configuration:
        """Resolve the value at the given keypath."""
        return _get_keypath(self, keypath, int)


# _UnresolvedFunctionCall --------------------------------------------------------------


class _UnresolvedFunctionCall(_types.UnresolvedFunctionCall):
    """Implements UnresolvedFunctionCall using _FunctionCallNode."""

    def __init__(self, function_node: "_FunctionCallNode"):
        self.function_node = function_node

    def _evaluate_to_unresolved_container(
        self,
    ) -> Union["_UnresolvedDict", "_UnresolvedList"]:
        """Evaluate the function call and return a unresolved container.

        If the result of the function call is not a collection, a TypeError is raised.

        """
        node = self.function_node.evaluate()
        assert not isinstance(node, _ValueNode)
        if isinstance(node, _DictNode):
            return _UnresolvedDict(node)
        else:
            # must be a _ListNode
            return _UnresolvedList(node)

    def __getitem__(
        self, key
    ) -> Union["_UnresolvedDict", "_UnresolvedList", _types.Configuration]:
        """Attempt to access an element in the result of the unresolved function call.

        This will trigger the evaluation of the function call if it has not already been
        resolved. If the result is a dictionary or list, the key is looked up in that
        collection. If the result is not a dictionary or list, a TypeError is raised.

        """
        return self._evaluate_to_unresolved_container()[key]

    def get_keypath(self, keypath: Union[_types.KeyPath, str]) -> _types.Configuration:
        """Resolve the value at the given keypath."""
        return self._evaluate_to_unresolved_container().get_keypath(keypath)


# helpers ------------------------------------------------------------------------------


def _make_unresolved_container(
    node: Union["_DictNode", "_ListNode", "_FunctionCallNode"],
) -> Union[_UnresolvedDict, _UnresolvedList, _UnresolvedFunctionCall]:
    """Create a unresolved container from a node."""
    if isinstance(node, _DictNode):
        return _UnresolvedDict(node)
    elif isinstance(node, _ListNode):
        return _UnresolvedList(node)
    elif isinstance(node, _FunctionCallNode):
        return _UnresolvedFunctionCall(node)


def _get_keypath(
    unresolved_container: Union[
        "_UnresolvedDict", "_UnresolvedList", "_UnresolvedFunctionCall"
    ],
    keypath: Union[_types.KeyPath, str],
    cast_key: Callable[[str], Any],
) -> _types.Configuration:
    """Resolve the node at the given keypath.

    This always returns a configuration, even if the keypath is to an internal node of
    the configuration tree (that is, a _DictNode, _ListNode, or _FunctionCallNode). The
    node at the keypath is resolved and the result is returned, no matter the node's
    type.

    Parameters
    ----------
    unresolved_container : Union[UnresolvedDict, UnresolvedList, UnresolvedFunctionCall]
        The (nested) container to search.
    keypath : Union[KeyPath, str]
        The keypath to the value to resolve. Can be a string or a tuple of strings.
    cast_key : Callable[[str], Any]
        A function to cast the key to the appropriate type. For example, int() to
        convert to an integer.

    Returns
    -------
    Configuration
        The resolved value at the keypath.

    """
    # string keypaths are split into tuples
    if isinstance(keypath, str):
        keypath = tuple(keypath.split("."))

    if len(keypath) == 1:
        # we are at the end of the road. resolve and return whatever node we're at.
        # if the thing at the keypath is a value node or a function call node, the next
        # line will resolve it automatically; otherwise, it will be a unresolved
        # container.
        result = unresolved_container[cast_key(keypath[0])]
        if isinstance(result, (_UnresolvedDict, _UnresolvedList)):
            return result.resolve()
        else:
            return result
    else:
        head_key, *rest_of_path = keypath

        # again, the result of this line will either be an _UnresolvedDict, an
        # _UnresolvedList, or a configuration. It cannot be an _UnresolvedFunctionCall.
        first_element = unresolved_container[cast_key(head_key)]

        if not isinstance(first_element, (_UnresolvedDict, _UnresolvedList)):
            raise KeyError(head_key)

        return first_element.get_keypath(tuple(rest_of_path))


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

# _Node Abstract Base Class ------------------------------------------------------------

_ConcreteNode = Union["_DictNode", "_ListNode", "_ValueNode", "_FunctionCallNode"]


class _Node(abc.ABC):
    """Abstract base class for all nodes in a configuration tree.

    Attributes
    ----------
    parent : Optional[_ConcreteNode]
        The parent of this node. Can be `None`, in which case this is the root of the
        tree.
    local_variables : Optional[Mapping[str, Configuration]]
        A dictionary of local variables that can be accessed during string
        interpolation. If None, this is made an empty dictionary.

    """

    def __init__(
        self,
        parent: Optional["_ConcreteNode"] = None,
        local_variables: Optional[Mapping[str, _types.Configuration]] = None,
    ):
        self.parent = parent

        if local_variables is None:
            self.local_variables = {}
        else:
            self.local_variables = local_variables

        # cache the root of the tree
        self._root: Optional[_ConcreteNode] = None

    @property
    def root(self) -> "_ConcreteNode":
        """The root of the configuration tree."""
        assert isinstance(self, (_DictNode, _ListNode, _ValueNode, _FunctionCallNode))
        if self._root is None:
            if self.parent is None:
                self._root = self
            else:
                self._root = self.parent.root
        return self._root

    @abc.abstractmethod
    def resolve(self) -> _types.Configuration:
        """Recursively resolve the node into a configuration."""

    def get_local_variable(self, key: str) -> _types.Configuration:
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
    children: Dict[str, _ConcreteNode],
    dct: _types.ConfigurationDict,
    dict_schema: _types.Schema,
    resolution_options: _types.ResolutionOptions,
    parent: _ConcreteNode,
    keypath: _types.KeyPath,
):
    """Populates the required children of a _DictNode.

    This uses the schema to determine which keys are required and then creates the child
    nodes for those keys. If a required key is missing, a ResolutionError is raised.

    Modifications are made to the node's .children dictionary in place.

    """
    required_keys = dict_schema.get("required_keys", {})

    for key, key_schema in required_keys.items():
        if key not in dct:
            raise ResolutionError("Missing required key.", (keypath + (key,)))

        children[key] = _make_node(
            dct[key], key_schema, resolution_options, parent, keypath + (key,)
        )


def _populate_optional_children(
    children: Dict[str, _ConcreteNode],
    dct: _types.ConfigurationDict,
    dict_schema: _types.Schema,
    resolution_options: _types.ResolutionOptions,
    parent: _ConcreteNode,
    keypath: _types.KeyPath,
):
    """Populates the optional children of a _DictNode.

    This uses the schema to determine which keys are optional and then creates
    the child nodes for those keys. If an optional key is missing and a default
    is provided, the default is used. If an optional key is missing and no
    default is provided, the key is simply not added to the children.

    Modifications are made to the .children dictionary in place.

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
            value, key_schema, resolution_options, parent, keypath + (key,)
        )


def _populate_extra_children(
    children: Dict[str, _ConcreteNode],
    dct: _types.ConfigurationDict,
    dict_schema: _types.Schema,
    resolution_options: _types.ResolutionOptions,
    parent: _ConcreteNode,
    keypath: _types.KeyPath,
):
    """Populates the extra children of a _DictNode.

    This uses the schema to determine how to handle extra keys in the configuration
    dictionary. If extra keys are not allowed, a ResolutionError is raised. If extra
    keys are allowed, the schema for the extra keys is used to create the child nodes.

    Modifications are made to the .children dictionary in place.

    """
    required_keys = dict_schema.get("required_keys", {})

    optional_keys = dict_schema.get("optional_keys", {})
    expected_keys = set(required_keys) | set(optional_keys)
    extra_keys = dct.keys() - expected_keys

    if extra_keys and "extra_keys_schema" not in dict_schema:
        raise ResolutionError("Unexpected extra key.", keypath + (extra_keys.pop(),))

    for key in extra_keys:
        children[key] = _make_node(
            dct[key],
            dict_schema["extra_keys_schema"],
            resolution_options,
            parent,
            keypath + (key,),
        )


class _DictNode(_Node):
    """Represents an internal dictionary node in a configuration tree.

    Attributes
    ----------
    resolution_options : _types.ResolutionOptions
        The settings that control how the configuration is resolved.
    children : Dict[str, _ConcreteNode]
        A dictionary of child nodes.
    parent : Optional[_ConcreteNode]
        The parent of this node. Can be `None`, in which case this is the root of the
        tree.
    local_variables : Optional[Mapping[str, Configuration]]
        A dictionary of local variables that can be accessed during string
        interpolation.

    """

    def __init__(
        self,
        resolution_options: _types.ResolutionOptions,
        children: Optional[Dict[str, _ConcreteNode]] = None,
        parent: Optional[_ConcreteNode] = None,
        local_variables: Optional[Mapping[str, _types.Configuration]] = None,
    ):
        super().__init__(parent, local_variables)
        self.resolution_options = resolution_options
        self.children: Dict[str, _ConcreteNode] = {} if children is None else children

    @classmethod
    def from_configuration(
        cls,
        dct: _types.ConfigurationDict,
        schema: _types.Schema,
        keypath: _types.KeyPath,
        resolution_options: _types.ResolutionOptions,
        parent: Optional[_ConcreteNode] = None,
        local_variables: Optional[Mapping[str, _types.Configuration]] = None,
    ) -> "_DictNode":
        """Construct a _DictNode from a configuration dictionary and its schema.

        Parameters
        ----------
        dct : ConfigurationDict
            The configuration dictionary.
        schema : Schema
            The schema to enforce on the configuration dictionary.
        keypath : _types.KeyPath
            The keypath to this node in the configuration tree.
        resolution_options : ResolutionOptions
            The settings that control how the configuration is resolved.
        parent : Optional[Node]
            The parent of this node. Can be `None`.

        """
        node = cls(resolution_options, parent=parent, local_variables=local_variables)

        if schema["type"] == "any":
            schema = {
                "type": "dict",
                "extra_keys_schema": {"type": "any", "nullable": True},
            }

        children = {}

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
            resolution_options,
            node,
            keypath,
        )
        _populate_optional_children(
            children,
            dct,
            schema,
            resolution_options,
            node,
            keypath,
        )
        _populate_extra_children(
            children,
            dct,
            schema,
            resolution_options,
            node,
            keypath,
        )

        node.children = children
        return node

    def resolve(self) -> _types.ConfigurationDict:
        """Recursively resolve the _DictNode into a ConfigurationDict."""
        # first, we evaluate all function call nodes contained in the dictionary
        for key, child_node in self.children.items():
            if isinstance(child_node, _FunctionCallNode):
                self.children[key] = child_node.evaluate()

        result = {}
        for key, child_node in self.children.items():
            assert isinstance(child_node, (_DictNode, _ListNode, _ValueNode))
            result[key] = child_node.resolve()

        return result


# _ListNode ----------------------------------------------------------------------------


class _ListNode(_Node):
    """Represents an internal list node in a configuration tree.

    Attributes
    ----------
    resolution_options : ResolutionOptions
        The settings that control how the configuration is resolved.
    children : List[_ConcreteNode]
        A list of the node's children.
    parent : Optional[_ConcreteNode]
        The parent of this node. Can be `None`, in which case this is the root of the
        tree.
    local_variables : Optional[Mapping[str, Configuration]]
        A dictionary of local variables that can be accessed during string
        interpolation

    """

    def __init__(
        self,
        resolution_options: _types.ResolutionOptions,
        children: Optional[List[_ConcreteNode]] = None,
        parent: Optional[_ConcreteNode] = None,
        local_variables: Optional[Mapping[str, _types.Configuration]] = None,
    ):
        super().__init__(parent, local_variables)
        self.resolution_options = resolution_options
        self.children: List[_ConcreteNode] = [] if children is None else []

    @classmethod
    def from_configuration(
        cls,
        lst: _types.ConfigurationList,
        schema: _types.Schema,
        keypath: _types.KeyPath,
        resolution_options: _types.ResolutionOptions,
        parent: Optional[_ConcreteNode] = None,
        local_variables: Optional[Mapping[str, _types.Configuration]] = None,
    ) -> "_ListNode":
        """Recursively make an internal list node from a ConfigurationList."""
        node = cls(resolution_options, parent=parent, local_variables=local_variables)

        if schema["type"] == "any":
            schema = {
                "type": "list",
                "element_schema": {"type": "any", "nullable": True},
            }

        child_schema = schema["element_schema"]

        children = []
        for i, lst_value in enumerate(lst):
            r = _make_node(
                lst_value,
                child_schema,
                resolution_options,
                node,
                keypath + (str(i),),
            )
            children.append(r)

        node.children = children
        return node

    def resolve(self) -> _types.ConfigurationList:
        """Recursively resolve the ListNode into a ConfigurationList."""
        # first, we evaluate all function nodes contained in the list
        for i, child_node in enumerate(self.children):
            if isinstance(child_node, _FunctionCallNode):
                self.children[i] = child_node.evaluate()

        result = []
        for child_node in self.children:
            assert isinstance(child_node, (_DictNode, _ListNode, _ValueNode))
            result.append(child_node.resolve())

        return result


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
    resolution_options : ResolutionOptions
        The settings that control how the configuration is resolved.
    nullable : Optional[bool]
        Whether the value can be None or not. If `raw` is None this is True, it
        is not converted (no matter what type_ is). Default: False.
    parent : Optional[Node]
        The parent of this node. Can be `None`, in which case this is the root.
    local_variables : Optional[Mapping[str, Configuration]]
        A dictionary of local variables that can be accessed during string
        interpolation.

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
        resolution_options: _types.ResolutionOptions,
        nullable: bool = False,
        parent: Optional[_ConcreteNode] = None,
        local_variables: Optional[Mapping[str, _types.Configuration]] = None,
    ):
        super().__init__(parent, local_variables)
        self.value = value
        self.type_ = type_
        self.keypath = keypath
        self.resolution_options = resolution_options
        self.nullable = nullable

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
        resolution_options: _types.ResolutionOptions,
        parent: Optional[_ConcreteNode] = None,
        local_variables: Optional[Mapping[str, _types.Configuration]] = None,
    ) -> "_ValueNode":
        """Create a leaf node from the configuration and schema."""
        if schema["type"] == "any":
            schema = {"type": "any", "nullable": True}

        return cls(
            value,
            schema["type"],
            keypath,
            resolution_options,
            nullable=schema["nullable"] if "nullable" in schema else False,
            parent=parent,
            local_variables=local_variables,
        )

    def resolve(self) -> _types.ConfigurationValue:
        """Resolve the leaf's value by 1) interpolating and 2) parsing.

        Returns
        -------
        The resolved value.

        """
        if isinstance(self.value, _types.RawString):
            # check that the expected type is a string (or any)
            if self.type_ not in ("string", "any"):
                raise ResolutionError(
                    "Schema expected something other than a string.", self.keypath
                )
            return self.value

        if self._resolved is _ValueNode._PENDING:
            raise ResolutionError("Circular reference", self.keypath)

        if self._resolved is not _ValueNode._UNDISCOVERED:
            self._resolved = typing.cast(_types.ConfigurationValue, self._resolved)
            return self._resolved

        self._resolved = _ValueNode._PENDING

        if isinstance(self.value, str):
            value = self._safely(
                self._interpolate,
                self.value,
                recursive=isinstance(self.value, _types.RecursiveString),
            )
        else:
            value = self.value

        if self.nullable and self.value is None:
            self._resolved = None
        else:
            self._resolved = self._safely(self._convert, value, self.type_)

        return self._resolved

    def _make_custom_jinja_context(
        self, global_variables: Mapping[str, Any], inject_root_as: Optional[str] = None
    ):
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

        First, a key is looked up in the local variables. If it is not found, it looked
        up in the unresolved container representing the root of the configuration tree.
        If a key is not found in the unresolved container, Jinja2 will fall back to the
        default behavior of looking up the key in the template variables.

        """
        if isinstance(self.root, (_DictNode, _ListNode, _FunctionCallNode)):
            root_container = _make_unresolved_container(self.root)
        else:
            root_container = {}

        this_node = self

        global_variables = dict(global_variables)
        if inject_root_as is not None:
            global_variables[inject_root_as] = root_container

        class CustomContext(jinja2.runtime.Context):
            def resolve_or_missing(self, key):
                # first try local variables
                try:
                    return this_node.get_local_variable(key)
                except KeyError:
                    pass

                # then try the root of the configuration tree
                try:
                    return root_container[key]
                except (KeyError, IndexError):
                    pass

                # then try the global variables
                try:
                    return global_variables[key]
                except KeyError:
                    pass

                # finally, try jinja's default behavior, including jinja builtins
                return super().resolve_or_missing(key)

        return CustomContext

    def _interpolate(self, s: str, recursive=False) -> str:
        """Replace references in the string with their resolved values.

        Parameters
        ----------
        s : str
            A configuration string with references to other values.
        recursive : bool
            If True, this will continue interpolating until the string no longer
            changes. Default: False.

        Returns
        -------
        The interpolated string.

        """
        environment = jinja2.Environment(
            variable_start_string="${", variable_end_string="}"
        )

        # create a custom jinja context for resolving references. This will first
        # loop up variables in the local variables, and then in the root of the
        # configuration tree, and finally in the global variables. See
        # the _make_custom_jinja_context() method for more information.
        environment.context_class = self._make_custom_jinja_context(
            self.resolution_options.global_variables,
            inject_root_as=self.resolution_options.inject_root_as,
        )

        # register the custom filters
        environment.filters.update(self.resolution_options.filters)

        # make undefined references raise an error
        environment.undefined = jinja2.StrictUndefined

        template = environment.from_string(s)

        try:
            result = template.render()
        except jinja2.exceptions.UndefinedError as exc:
            raise ResolutionError(str(exc), self.keypath)

        if recursive and result != s:
            # if the string changed, we need to interpolate again
            return self._interpolate(result, recursive=True)
        else:
            return result

    def _convert(self, value, type_) -> _types.ConfigurationValue:
        """convert the configuration value into its final type."""
        converters = self.resolution_options.converters

        try:
            converter = converters[type_]
        except KeyError:
            raise ResolutionError(
                f"No converter provided for type: '{type_}'.", self.keypath
            )

        return converter(value)

    def _safely(self, fn, *args, **kwargs):
        """Apply the function and catch any exceptions, raising a ResolutionError."""
        try:
            return fn(*args, **kwargs)
        except Error as exc:
            raise ResolutionError(str(exc), self.keypath) from exc


# _FunctionCallNode --------------------------------------------------------------------


class _FunctionCallNode(_Node):
    """Represents a function call in the configuration tree.

    Attributes
    ----------
    keypath : _types.KeyPath
        The keypath to this node in the configuration tree.
    resolution_options : _types.ResolutionOptions
        The settings that control how resolution is performed.
    function : _types.Function
        The function being called.
    input : _types.Configuration
        The input to the function.
    schema : _types.Schema
        The schema for the function's output.
    parent : Optional[_ConcreteNode]
        The parent of this node. Can be `None`, in which case this is the root
    local_variables : Optional[Mapping[str, Configuration]]
        A dictionary of local variables that can be accessed during string
        interpolation.

    """

    # sentinel object denoting that a node is currently being evaluated
    PENDING = object()

    # sentinel object denoting that the evaluation of this node has not yet started
    UNDISCOVERED = object()

    def __init__(
        self,
        keypath: _types.KeyPath,
        resolution_options: _types.ResolutionOptions,
        function: _types.Function,
        input: _types.Configuration,
        schema: _types.Schema,
        parent: Optional[_ConcreteNode] = None,
        local_variables: Optional[Mapping[str, _types.Configuration]] = None,
    ):
        super().__init__(parent, local_variables)
        self.keypath = keypath
        self.resolution_options = resolution_options
        self.schema = schema
        self.function = function
        self.input = input

        # The evaluated value of the function node. There are two special
        # values. If this is _UNDISCOVERED, the evaluation process has not yet
        # discovered the function node (this is the default value). If this is
        # _PENDING, a step in the resolution process has started to evaluate
        # the function. Otherwise, this contains the evaluated value. Necessary
        # in order to detect circular references.
        self._evaluated = _FunctionCallNode.UNDISCOVERED

    def evaluate(self) -> Union[_DictNode, _ListNode, _ValueNode]:
        """Evaluate the function, returning a _DictNode, _ListNode, or _ValueNode.

        This operates recursively, so that if the function returns a ConfigurationDict
        representing another function call, that child function call is also evaluated,
        and so on.

        """
        if self._evaluated is _FunctionCallNode.PENDING:
            raise ResolutionError("Circular reference", self.keypath)

        if self._evaluated is not _FunctionCallNode.UNDISCOVERED:
            assert isinstance(self._evaluated, (_DictNode, _ListNode, _ValueNode))
            return self._evaluated

        self._evaluated = _FunctionCallNode.PENDING

        if self.function.resolve_input:
            input_node = _make_node(
                self.input,
                {"type": "any"},
                self.resolution_options,
                parent=self,
                keypath=self.keypath,
            )
            input = input_node.resolve()
        else:
            input = self.input

        # root can't be a value node, because we're calling this from a
        # function node that is either 1) the root, or 2) the successor of a root
        # that is a container node
        assert isinstance(self.root, (_DictNode, _ListNode, _FunctionCallNode))
        root = _make_unresolved_container(self.root)

        # make a "resolve" function that can be used by the function to resolve
        # configurations. This enables advanced use cases like using a function
        # to implement for-loops.
        def resolve(
            configuration: _types.Configuration,
            schema: Optional[_types.Schema] = None,
            local_variables: Optional[Mapping[str, _types.Configuration]] = None,
        ) -> _types.Configuration:
            if schema is None:
                schema = self.schema
            node = _make_node(
                configuration,
                schema,
                self.resolution_options,
                parent=self,
                keypath=self.keypath,
                local_variables=local_variables,
            )
            return node.resolve()

        args = _types.FunctionArgs(
            input, root, self.keypath, self.resolution_options, resolve, self.schema
        )

        # evaluate the function itself
        output = self.function(args)

        result = _make_node(
            output,
            self.schema,
            self.resolution_options,
            parent=self,
            keypath=self.keypath,
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


# make_node() ==========================================================================


def _make_node(
    cfg: _types.Configuration,
    schema: _types.Schema,
    resolution_options: _types.ResolutionOptions,
    parent: Optional[_ConcreteNode] = None,
    keypath: _types.KeyPath = tuple(),
    local_variables: Optional[Mapping[str, _types.Configuration]] = None,
) -> Union[_DictNode, _ListNode, _ValueNode, _FunctionCallNode]:
    """Recursively constructs a configuration tree from a configuration.

    The configuration can be a dictionary, list, or a non-container type. In any case,
    the provided schema must match the type of the configuration; for example, if the
    configuration is a dictionary, the schema must be a dict schema.

    A function call node is created if the configuration is a dictionary with a key of
    the form "__<function_name>__". In this case, the schema is used to validate the
    output of the function.

    Parameters
    ----------
    cfg
        A dictionary, list, or non-container type representing the "raw", unresolved
        configuration.
    schema
        A schema dictionary describing the types of the configuration tree nodes.
    resolution_options
        The settings that control how resolution is performed.
    check_for_function_call
        A function that checks if a ConfigurationDict represents a function call. It
        is given the configuration and the available functions. If it is a function
        call, it returns a 2-tuple of the function and the input to the function. If
        not, it returns None. If it is an invalid function call, it should raise
        a ValueError.
    parent
        The parent node of the node being built. Can be `None`.
    keypath
        The keypath to this node in the configuration tree.

    Returns
    -------
    Union[DictNode, ListNode, ValueNode, FunctionCallNode]
        The root node of the configuration tree.

    """
    common_kwargs = {
        "resolution_options": resolution_options,
        "parent": parent,
        "keypath": keypath,
        "local_variables": local_variables,
        "schema": schema,
    }

    if cfg is None:
        if ("nullable" in schema and schema["nullable"]) or (
            "type" in schema and schema["type"] == "any"
        ):
            kwargs = common_kwargs.copy()
            kwargs["schema"] = {"type": "any"}
            return _ValueNode.from_configuration(None, **kwargs)
        else:
            raise ResolutionError("Unexpectedly null.", keypath)

    elif isinstance(cfg, dict):
        # construct the configuration tree. the configuration tree is a nested container
        # whose terminal leaf values are _ValueNodes. "Internal" nodes are dictionaries or
        # lists.

        # check if this is a function call
        try:
            result = resolution_options.check_for_function_call(
                cfg, resolution_options.functions
            )
        except ValueError as exc:
            raise ResolutionError(f"Invalid function call: {exc}", keypath)

        if result is not None:
            return _FunctionCallNode(
                **common_kwargs,
                function=result[0],
                input=result[1],
            )
        else:
            return _DictNode.from_configuration(
                cfg,
                **common_kwargs,
            )
    elif isinstance(cfg, list):
        return _ListNode.from_configuration(
            cfg,
            **common_kwargs,
        )
    else:
        return _ValueNode.from_configuration(
            cfg,
            **common_kwargs,
        )


# resolve() ============================================================================

# defaults -----------------------------------------------------------------------------

# the default converters used by resolve()
DEFAULT_CONVERTERS = {
    "integer": _converters.arithmetic(int),
    "float": _converters.arithmetic(float),
    "string": str,
    "boolean": _converters.logic,
    "date": _converters.smartdate,
    "datetime": _converters.smartdatetime,
    "any": lambda x: x,
}

# the default functions available to resolve()
DEFAULT_FUNCTIONS = {
    "raw": _functions.raw,
    "recursive": _functions.recursive,
    "splice": _functions.splice,
    "update_shallow": _functions.update_shallow,
    "update": _functions.update,
    "concatenate": _functions.concatenate,
}


def _check_for_dunder_function_call(
    dct: _types.ConfigurationDict, functions: Mapping[str, _types.Function]
) -> Union[tuple[_types.Function, _types.Configuration], None]:
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


def _is_leaf(x):
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
    callable_or_function: Union[
        Callable[[_types.FunctionArgs], _types.Configuration], _types.Function
    ],
):
    """Converts standard Python functions to _type.Function instances."""
    if isinstance(callable_or_function, _types.Function):
        return callable_or_function
    else:
        return _types.Function(callable_or_function)


# overloads ----------------------------------------------------------------------------

# these overloads are provided so that type checkers can predict that the return
# type of resolve() is the same as the input type. This is useful for IDEs and
# static type checkers.


@typing.overload
def resolve(
    cfg: _types.ConfigurationDict,
    schema: _types.Schema,
    converters: Mapping[str, Callable] = ...,
    functions: Optional[
        Mapping[
            str,
            Union[
                _types.Function, Callable[[_types.FunctionArgs], _types.Configuration]
            ],
        ]
    ] = ...,
    global_variables: Optional[Mapping[str, Any]] = ...,
    inject_root_as: Optional[str] = ...,
    filters: Optional[Mapping[str, Callable]] = ...,
    preserve_type: bool = ...,
    check_for_function_call: Optional[_types.FunctionCallChecker] = ...,
) -> dict:
    """Overloaded resolve() for ConfigurationDict."""


@typing.overload
def resolve(
    cfg: _types.ConfigurationList,
    schema: _types.Schema,
    converters: Mapping[str, Callable] = DEFAULT_CONVERTERS,
    functions: Optional[
        Mapping[
            str,
            Union[
                _types.Function, Callable[[_types.FunctionArgs], _types.Configuration]
            ],
        ]
    ] = DEFAULT_FUNCTIONS,
    global_variables: Optional[Mapping[str, Any]] = None,
    inject_root_as: Optional[str] = None,
    filters: Optional[Mapping[str, Callable]] = None,
    preserve_type: bool = False,
    check_for_function_call: Optional[
        _types.FunctionCallChecker
    ] = _check_for_dunder_function_call,
) -> list:
    """Overloaded resolve() for ConfigurationList."""


@typing.overload
def resolve(
    cfg: _types.ConfigurationValue,
    schema: _types.Schema,
    converters: Mapping[str, Callable] = ...,
    functions: Optional[
        Mapping[
            str,
            Union[
                _types.Function, Callable[[_types.FunctionArgs], _types.Configuration]
            ],
        ]
    ] = ...,
    global_variables: Optional[Mapping[str, Any]] = ...,
    inject_root_as: Optional[str] = ...,
    filters: Optional[Mapping[str, Callable]] = ...,
    preserve_type: bool = ...,
    check_for_function_call: Optional[_types.FunctionCallChecker] = ...,
) -> Any:
    """Overloaded resolve() for ConfigurationValue."""


# implementation -----------------------------------------------------------------------


def resolve(
    cfg: _types.Configuration,
    schema: _types.Schema,
    converters: Mapping[str, Callable] = DEFAULT_CONVERTERS,
    functions: Optional[
        Mapping[
            str,
            Union[
                _types.Function, Callable[[_types.FunctionArgs], _types.Configuration]
            ],
        ]
    ] = DEFAULT_FUNCTIONS,
    global_variables: Optional[Mapping[str, Any]] = None,
    inject_root_as: Optional[str] = None,
    filters: Optional[Mapping[str, Callable]] = None,
    preserve_type: bool = False,
    check_for_function_call: Optional[  # type:ignore[assignment]
        _types.FunctionCallChecker
    ] = _check_for_dunder_function_call,
) -> _types.Configuration:
    """Resolve a configuration by interpolating and parsing its entries.

    Parameters
    ----------
    cfg : :class:`types.Configuration`
        The "raw" configuration to resolve.
    schema : :class:`types.Schema`
        The schema describing the structure of the resolved configuration.
    converters : Mapping[str, Callable]
        A dictionary mapping value types to converter functions. The converter functions
        should take the raw value (after interpolation) and convert it to the specified
        type. If this is not provided, the default converters in :data:`DEFAULT_CONVERTERS` are used.
    functions : Mapping[str, Union[Callable, :class:`types.Function`]]
        A mapping of function names to functions. The functions should either be basic
        Python functions accepting an instance of :class:`types.FunctionArgs` as input
        and returning a :class:`types.Configuration`, or they should be
        :class:`smartconfig.types.Function` instances. If this is not provided, the
        default functions in :data:`DEFAULT_FUNCTIONS` are used. If it is ``None``, no
        functions are made available.
    global_variables : Optional[Mapping[str, Any]]
        A dictionary of global variables to make available during string interpolation.
        If this is not provided, no global variables are available.
    inject_root_as : Optional[str]
        If this is not None, the root of the configuration tree is made available to
        Jinja2 templates as an :class:`types.UnresolvedDict`,
        :class:`types.UnresolvedList`, or :class:`types.UnresolvedFunctionCall` by
        injecting it into the template variables as the value of this key. This allows
        the root to be referenced directly during string interpolation. Defaults to
        ``None``.
    filters : Optional[Mapping[str, Callable]]
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
        # convert standard Python functions to _types.Function instances
        converted_functions = {k: _ensure_function(v) for k, v in functions.items()}

    if global_variables is None:
        global_variables = {}
    else:
        global_variables = dict(global_variables)

    if filters is None:
        filters = {}

    if check_for_function_call is None:
        # do not check for function calls
        def check_for_function_call(*_):
            return None

    resolution_options = _types.ResolutionOptions(
        converters,
        converted_functions,
        global_variables,
        filters,
        inject_root_as,
        check_for_function_call,
    )

    root = _make_node(cfg, schema, resolution_options)

    resolved = root.resolve()

    if not preserve_type:
        return resolved
    else:
        output = copy.deepcopy(cfg)
        _copy_into(output, resolved)
        return output
