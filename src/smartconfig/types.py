"""Types and type aliases."""

import abc
import collections.abc
import dataclasses
from typing import Dict, List, Union, Mapping, Any, Tuple, Callable
import datetime

# type aliases =========================================================================

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

# a schema is a dictionary that describes the expected structure of a configuration
Schema = Mapping[str, Any]

# a keypath is a tuple of strings that represents a path through a configuration
# tree. For example, ("foo", "bar", "baz") would represent the path to the value
# of the key "baz" in the dictionary {"foo": {"bar": {"baz": 42}}}.
KeyPath = Tuple[str, ...]

# namespaces ===========================================================================


class Namespace:
    """ABC for a namespace object.

    A namespace acts like a dictionary that also supports access to the keys as
    attributes.

    """

    @abc.abstractmethod
    def __getitem__(self, key: Union[str, int]) -> Union["Namespace", Configuration]:
        pass

    @abc.abstractmethod
    def __getattr__(self, key: Union[str, int]) -> Union["Namespace", Configuration]:
        pass

    @abc.abstractmethod
    def _get_keypath(self, keypath: Union[KeyPath, str]) -> Configuration:
        pass


# functions ============================================================================


@dataclasses.dataclass
class FunctionArgs:
    """Holds the arguments for a function call.

    Attributes
    ----------
    input : ConfigurationValue
        The input to the function.
    namespace : Namespace
        The namespace containing the root of the configuration tree (as the "this" key)
        and all external variables.
    keypath : KeyPath
        The keypath to the function being evaluated.

    """

    input: ConfigurationValue
    namespace: Namespace
    keypath: KeyPath


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


class RawString(str):
    """A string that should not be resolved."""

    pass


class RecursiveString(str):
    """A string that should be resolved recursively."""

    pass
