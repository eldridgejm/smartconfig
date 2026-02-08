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

"""

from typing import (
    Any,
    Callable,
    Mapping,
    TypedDict,
)
import abc
import enum
import typing

import jinja2

from . import types as _types
from .exceptions import Error, ResolutionError
from ._schemas import validate_schema as _validate_schema


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
        elif isinstance(child, _ValueNode):
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
        assert not isinstance(node, _ValueNode)
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

# _Node ABC ----------------------------------------------------------------------------

type _ConcreteNode = _DictNode | _ListNode | _ValueNode | _FunctionCallNode


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

    """

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
        assert isinstance(self, (_DictNode, _ListNode, _ValueNode, _FunctionCallNode))
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
                _validate_schema(key_schema, keypath + (key,), allow_default=True)
            if "default" in key_schema:
                # default was provided
                value = key_schema["default"]
            else:
                # no default was provided
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
    extra_keys = dct.keys() - expected_keys

    if extra_keys and "extra_keys_schema" not in dict_schema:
        key = extra_keys.pop()
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
        root_container: (
            _UnresolvedDict | _UnresolvedList | _UnresolvedFunctionCall | dict[str, Any]
        )
        if isinstance(self.root, (_DictNode, _ListNode, _FunctionCallNode)):
            root_container = _make_unresolved_container(self.root)
        else:
            # if the root is a value node, then the configuration tree is a single
            # isolated node. This node cannot have any in-tree references, because
            # they'd be circular. In this case, an empty root container does the job.
            root_container = {}

        # save a copy of self, because we shadow `self` in `resolve_or_missing` below
        this_node = self

        # copy the globals to prevent modification, then insert the root node if
        # requested
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
                except KeyError, IndexError:
                    pass

                # then try the global variables
                try:
                    return global_variables[key]
                except KeyError:
                    pass

                # finally, try jinja's default behavior, including jinja builtins
                return super().resolve_or_missing(key)

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
        environment = jinja2.Environment(
            variable_start_string="${", variable_end_string="}"
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
        environment.undefined = jinja2.StrictUndefined

        template = environment.from_string(s)

        try:
            result = template.render()
        except jinja2.exceptions.UndefinedError as exc:
            raise ResolutionError(str(exc), self.keypath)

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

    def evaluate(self) -> _DictNode | _ListNode | _ValueNode:
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
            assert isinstance(self._evaluated, (_DictNode, _ListNode, _ValueNode))
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
        if isinstance(output, (_DictNode, _ListNode, _ValueNode, _FunctionCallNode)):
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


# make_node() ==========================================================================


def make_node(
    cfg: _types.Configuration,
    schema: _types.Schema | _types.DynamicSchema,
    resolution_context: _types.ResolutionContext,
    parent: _ConcreteNode | None = None,
    keypath: _types.KeyPath = tuple(),
    local_variables: Mapping[str, _types.Configuration] | None = None,
    mode: ResolutionMode = ResolutionMode.STANDARD,
) -> _DictNode | _ListNode | _ValueNode | _FunctionCallNode:
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
    _DictNode | _ListNode | _ValueNode | _FunctionCallNode
        The root node of the configuration tree.

    """
    if callable(schema):
        # dynamic schema: call the function to get the actual schema
        schema = schema(cfg, keypath)
        _validate_schema(schema)

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
