"""Types and type aliases."""

import abc
import dataclasses
from typing import Dict, List, Union, Mapping, Any, Tuple, Callable, Iterable
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

# lazy containers ======================================================================


class LazyDict(abc.ABC):
    """A dictionary that lazily resolves its values."""

    @abc.abstractmethod
    def __getitem__(self, key: str) -> Union["LazyDict", "LazyList", Configuration]: ...

    @abc.abstractmethod
    def __len__(self) -> int: ...

    @abc.abstractmethod
    def __iter__(self) -> Iterable[str]: ...

    @abc.abstractmethod
    def keys(self) -> Iterable[str]: ...

    @abc.abstractmethod
    def values(self) -> Iterable[Union["LazyDict", "LazyList", Configuration]]: ...

    @abc.abstractmethod
    def resolve(self) -> ConfigurationDict: ...

    @abc.abstractmethod
    def get_keypath(self, keypath: Union["KeyPath", str]) -> Configuration: ...


class LazyList(abc.ABC):
    """A list that lazily resolves its values."""

    @abc.abstractmethod
    def __getitem__(self, ix) -> Union["LazyDict", "LazyList", Configuration]: ...

    @abc.abstractmethod
    def __iter__(self) -> Iterable[Union["LazyDict", "LazyList", Configuration]]: ...

    @abc.abstractmethod
    def __len__(self) -> int: ...

    @abc.abstractmethod
    def resolve(self) -> ConfigurationList: ...

    @abc.abstractmethod
    def get_keypath(self, keypath: Union["KeyPath", str]) -> Configuration: ...


class LazyFunctionCall(abc.ABC):
    """A function that lazily resolves its values."""

    @abc.abstractmethod
    def __getitem__(self, key: str) -> Union["LazyDict", "LazyList", Configuration]: ...

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

    """

    input: Configuration
    root: Union[LazyDict, LazyList, LazyFunctionCall, None]
    keypath: "KeyPath"


class Function:
    """A function that, when called on a configuration, produces a new configuration."""

    def __init__(self, fn: Callable, resolve_input=True):
        self.fn = fn
        self.resolve_input = resolve_input

    def __call__(self, args: FunctionArgs) -> Configuration:
        return self.fn(args)

    @classmethod
    def new(cls, resolve_input=True):
        """Decorator for creating a new Function object.

        Parameters
        ----------
        resolve_input : bool
            If `True`, the input will be resolved before being passed to the function.

        """

        def decorator(fn):
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
