"""Types and type aliases."""

import abc
import dataclasses
from typing import Dict, List, Union, Mapping, Any, Tuple, Callable, Iterable, Optional
import datetime

# configuration type aliases ===========================================================

# configurations are "raw" dictionaries, lists, or non-container types; a
# configuration tree can be built from configurations, and a resolved
# configuration is again a configuration
ConfigurationContainer = Union["ConfigurationDict", "ConfigurationList"]
ConfigurationValue = Union[
    str, int, float, bool, datetime.datetime, datetime.date, None
]
ConfigurationList = List[Union[ConfigurationContainer, ConfigurationValue]]
ConfigurationDict = Dict[str, Union[ConfigurationContainer, ConfigurationValue]]
Configuration = Union[ConfigurationContainer, ConfigurationValue]

# configuration tree nodes =============================================================


class Node(abc.ABC):
    """Abstract base class for all nodes in a configuration tree.

    Attributes
    ----------
    parent : Optional[Node]
        The parent of this node. Can be `None`, in which case this is the root
        of the tree.

    """

    def __init__(self, parent: Optional["Node"] = None):
        self.parent = parent

        # cache the root of the tree
        self._root = None

    @property
    def root(self) -> "Node":
        """The root of the configuration tree."""
        if self._root is None:
            if self.parent is None:
                self._root = self
            else:
                self._root = self.parent.root
        return self._root

    @abc.abstractmethod
    def resolve(self) -> Configuration:
        """Recursively resolve the node into a configuration."""
        ...


class DictNode(abc.ABC):
    """A dictionary that lazily resolves its values."""

    @abc.abstractmethod
    def __getitem__(self, key: str) -> Union["DictNode", "ListNode", Configuration]: ...

    @abc.abstractmethod
    def __len__(self) -> int: ...

    @abc.abstractmethod
    def __iter__(self) -> Iterable[str]: ...

    @abc.abstractmethod
    def keys(self) -> Iterable[str]: ...

    @abc.abstractmethod
    def values(self) -> Iterable[Union["DictNode", "ListNode", Configuration]]: ...

    @abc.abstractmethod
    def resolve(self) -> ConfigurationDict: ...

    @abc.abstractmethod
    def get_keypath(self, keypath: Union["KeyPath", str]) -> Configuration: ...


class ListNode(abc.ABC):
    """A list that lazily resolves its values."""

    @abc.abstractmethod
    def __getitem__(self, ix) -> Union["DictNode", "ListNode", Configuration]: ...

    @abc.abstractmethod
    def __iter__(self) -> Iterable[Union["DictNode", "ListNode", Configuration]]: ...

    @abc.abstractmethod
    def __len__(self) -> int: ...

    @abc.abstractmethod
    def resolve(self) -> ConfigurationList: ...

    @abc.abstractmethod
    def get_keypath(self, keypath: Union["KeyPath", str]) -> Configuration: ...


class FunctionNode(abc.ABC):
    """A function that lazily resolves its values."""

    @abc.abstractmethod
    def __getitem__(self, key: str) -> Union["DictNode", "ListNode", Configuration]: ...

    @abc.abstractmethod
    def resolve(self) -> Configuration: ...

    @abc.abstractmethod
    def get_keypath(self, keypath: Union["KeyPath", str]) -> Configuration: ...


class ValueNode(abc.ABC):
    """A value that lazily resolves its values."""

    @abc.abstractmethod
    def resolve(self) -> Configuration: ...

    @abc.abstractmethod
    def get_keypath(self, keypath: Union["KeyPath", str]) -> Configuration: ...


# lazy containers ======================================================================


class UnresolvedDict(abc.ABC):
    """A dictionary that lazily resolves its values."""

    @abc.abstractmethod
    def __getitem__(
        self, key: str
    ) -> Union["UnresolvedDict", "UnresolvedList", Configuration]: ...

    @abc.abstractmethod
    def __len__(self) -> int: ...

    @abc.abstractmethod
    def __iter__(self) -> Iterable[str]: ...

    @abc.abstractmethod
    def keys(self) -> Iterable[str]: ...

    @abc.abstractmethod
    def values(
        self,
    ) -> Iterable[Union["UnresolvedDict", "UnresolvedList", Configuration]]: ...

    @abc.abstractmethod
    def resolve(self) -> ConfigurationDict: ...

    @abc.abstractmethod
    def get_keypath(self, keypath: Union["KeyPath", str]) -> Configuration: ...


class UnresolvedList(abc.ABC):
    """A list that lazily resolves its values."""

    @abc.abstractmethod
    def __getitem__(
        self, ix
    ) -> Union["UnresolvedDict", "UnresolvedList", Configuration]: ...

    @abc.abstractmethod
    def __iter__(
        self,
    ) -> Iterable[Union["UnresolvedDict", "UnresolvedList", Configuration]]: ...

    @abc.abstractmethod
    def __len__(self) -> int: ...

    @abc.abstractmethod
    def resolve(self) -> ConfigurationList: ...

    @abc.abstractmethod
    def get_keypath(self, keypath: Union["KeyPath", str]) -> Configuration: ...


class UnresolvedFunctionCall(abc.ABC):
    """A function call that lazily resolves its values."""

    @abc.abstractmethod
    def __getitem__(
        self, key: str
    ) -> Union["UnresolvedDict", "UnresolvedList", Configuration]: ...

    @abc.abstractmethod
    def resolve(self) -> Configuration: ...

    @abc.abstractmethod
    def get_keypath(self, keypath: Union["KeyPath", str]) -> Configuration: ...


# functions ============================================================================


@dataclasses.dataclass
class FunctionArgs:
    """Holds the arguments for a function call.

    Attributes
    ----------
    input : ConfigurationValue
        The input to the function.
    root : Union[LazyDict, LazyList]
        The root of the configuration tree.
    keypath : KeyPath
        The keypath to the function being evaluated.
    resolution_context : ResolutionContext
        The context in which the function is being evaluated.

    """

    input: Configuration
    root: Union[UnresolvedDict, UnresolvedList, UnresolvedFunctionCall]
    keypath: "KeyPath"
    resolution_context: "ResolutionContext"


class Function:
    """A function that, when called on a configuration, produces a new configuration."""

    def __init__(self, fn: Callable, resolve_input=True):
        self.fn = fn
        self.resolve_input = resolve_input

    def __call__(self, args: FunctionArgs) -> Configuration:
        return self.fn(args)

    @classmethod
    def new(
        cls, resolve_input: bool = True
    ) -> Callable[[Callable[[FunctionArgs], Configuration]], "Function"]:
        """Decorator for creating a new Function object.

        Parameters
        ----------
        resolve_input : bool
            If `True`, the input will be resolved before being passed to the function.

        """

        def decorator(fn: Callable[[FunctionArgs], Configuration]) -> "Function":
            return cls(fn, resolve_input)

        return decorator


# special strings ======================================================================


class RawString(str):
    """A string that should not be resolved."""


class RecursiveString(str):
    """A string that should be resolved recursively."""


# misc. type aliases ===================================================================

# a schema is a dictionary that describes the expected structure of a configuration
Schema = Mapping[str, Any]

# a keypath is a tuple of strings that represents a path through a configuration
# tree. For example, ("foo", "bar", "baz") would represent the path to the value
# of the key "baz" in the dictionary {"foo": {"bar": {"baz": 42}}}.
KeyPath = Tuple[str, ...]


@dataclasses.dataclass
class ResolutionContext:
    """Holds information available at the time that a node is resolved.

    Attributes
    ----------
    parsers : Mapping[str, Callable]
        Parsers for different types of values.
    functions : Mapping[str, Function]
        Functions that can be called from the configuration.
    global_variables : Mapping[str, Any]
        Global variables that are available during string interpolation.
    filters : Mapping[str, Callable]
        Filters that can be applied during string interpolation.
    inject_root_as : Optional[str]
        If not `None`, the root of the configuration tree will be injected into
        the global variables under this name.

    """

    parsers: Mapping[str, Callable]
    functions: Mapping[str, Function]
    global_variables: Mapping[str, Any]
    filters: Mapping[str, Callable]
    inject_root_as: Optional[str]
