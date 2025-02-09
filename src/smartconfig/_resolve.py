"""Provides the resolve() function for resolving raw configurations.

Implementation
==============

In the documentation, it is described how a configuration can be conceptualized
as a directed graph, and how resolution is a process of traversing this graph.
This module works by building a concrete representation of this graph and
performing that traversal.

Each node in the graph is represented by one of four node classes: _DictNode,
_ListNode, _ValueNode, and _FunctionNode. Each node has a .resolve() method that
recursively resolves the node and its successors. Each node also has a
corresponding .from_configuration() method that constructs the node from a
configuration of the appropriate type (e.g., _DictNode.from_configuration() builds
a _DictNode from a dictionary, _ListNode.from_configuration() builds a _ListNode
from a list, etc.).

The creation of the tree is orchestrated by the _make_node() function, whose
job is to take an arbitrary configuration and determine which node class to use
to represent it. This function is called with the whole configuration to create
the root node, and is also called by the container node classes to create their
children. _make_node is also responsible for detecting when a dictionary
represents a function call and creating a _FunctionNode in that case.

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
from .types import FunctionArgs, Function, Namespace, RawString, RecursiveString


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


# denotes that a node is currently being resolved.
_PENDING = object()


class LazyValue:
    def __init__(self, value):
        self._value = value

    def __str__(self):
        return str(self._value.resolve())

    def __getattr__(self, name: str, /) -> Any:
        return getattr(self._value.resolve(), name)


class _ConfigurationTreeNamespace(_types.Namespace):
    """A Namespace that allows for keypath access to a configuration tree."""

    def __init__(self, container: _types.ConfigurationContainer):
        self.container = container

    def __getitem__(self, key: Union[str, int]) -> Union[Namespace, Any]:
        """Retrieves a child by key.

        If that child is a container, a new _ConfigurationTreeNamespace is returned.
        However, if the child is a leaf node (either a value or a function),
        the resolved value is returned.

        """
        if isinstance(self.container, (list, _ListNode)):
            child = self.container[int(key)]
        else:
            child = self.container[str(key)]

        if isinstance(child, (_DictNode, _ListNode, dict, list)):
            return _ConfigurationTreeNamespace(child)
        elif isinstance(child, (_ValueNode, _FunctionNode)):
            return LazyValue(child)
        else:
            raise TypeError(f"Unexpected child type: {type(child)}")

    def __getattr__(self, key):
        """Allows accessing a child by attribute. Same behavior as __getitem__."""
        return self[key]

    def _get_keypath(self, keypath: Union[_types.KeyPath, str]) -> _types.Configuration:
        """Follow a keypath to a part of the nested configuration.

        Unlike __getitem__, this method always returns a :type:`Configuration`.
        This is true even if the keypath does not point to a leaf node, and
        instead refers to a container. The container is resolved recursively
        and returned.

        Parameters
        ----------
        keypath : Union[KeyPath, str]
            The keypath to follow.

        """
        if isinstance(keypath, str):
            keypath = tuple(keypath.split("."))

        if len(keypath) == 0:
            if isinstance(
                self.container, (_DictNode, _ListNode, _ValueNode, _FunctionNode)
            ):
                return self.container.resolve()
            else:
                return self.container
        else:
            first, *rest = keypath
            child = self[first]
            if isinstance(child, Namespace):
                return child._get_keypath(tuple(rest))
            else:
                return child


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

    def __getitem__(
        self, key: str
    ) -> Union[_ConfigurationTreeNamespace, _types.ConfigurationValue]:
        """Get a child node by key."""
        return self.children[key]

    def resolve(self) -> _types.ConfigurationDict:
        """Recursively resolve the DictNode into a configuration dictionary."""
        # first, we evaluate all function nodes contained in the dictionary
        for key, child_node in self.children.items():
            if isinstance(child_node, _FunctionNode):
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

    def __getitem__(
        self, ix
    ) -> Union[_ConfigurationTreeNamespace, _types.ConfigurationValue]:
        return self.children[ix]

    def resolve(self) -> _types.ConfigurationList:
        """Recursively resolve the ListNode into a list."""
        # first, we evaluate all function nodes contained in the list
        for i, child_node in enumerate(self.children):
            if isinstance(child_node, _FunctionNode):
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
        template = jinja2.Template(
            s, variable_start_string="${", variable_end_string="}"
        )

        if isinstance(self.root, _DictNode):
            namespace = _ConfigurationTreeNamespace(self.root)
            template_variables = {k: namespace[k] for k in self.root.children}
        else:
            template_variables = {}

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


class _FunctionNode(_Node):
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
    ) -> "_FunctionNode":
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

        args = FunctionArgs(
            input,
            _ConfigurationTreeNamespace(self.root),
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

    def resolve(self) -> _types.ConfigurationValue:
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
            return _FunctionNode.from_configuration(
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
