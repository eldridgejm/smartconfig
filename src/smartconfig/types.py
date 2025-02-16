"""Types and type aliases."""

from typing import Dict, List, Union, Mapping, Any, Tuple, Callable, Iterable, Optional
import abc
import dataclasses
import datetime
import functools

# configuration type aliases ===========================================================

# configurations are "raw" dictionaries, lists, or non-container types; a
# configuration tree can be built from configurations, and a resolved
# configuration is again a configuration.

# as of Feb. 2025, using the "type" keyword in the type alias causes the type
# checker to throw a fit, so we'll use the old way for now

ConfigurationValue = Union[
    str, int, float, bool, datetime.datetime, datetime.date, None
]
ConfigurationContainer = Union["ConfigurationDict", "ConfigurationList"]
ConfigurationList = List[Union[ConfigurationContainer, ConfigurationValue]]
ConfigurationDict = Dict[str, Union[ConfigurationContainer, ConfigurationValue]]

Configuration = Union[ConfigurationContainer, ConfigurationValue]

# unresolved containers ================================================================

# these unresolved container types are provided to user-defined functions so that they
# may reference other parts of the configuration tree and trigger their resolution if
# necessary, without exposing the user to the details of how resolution is performed


class UnresolvedDict(abc.ABC):
    """A dictionary that lazily resolves its values.

    This is an abstract base class and is not meant to be instantiated directly.

    """

    @abc.abstractmethod
    def __getitem__(
        self, key: str
    ) -> Union["UnresolvedDict", "UnresolvedList", Configuration]:
        """Get an item from the dictionary.

        The semantics of this depend on the type of object being retrieved. If the
        object is a container (a dictionary or list), it will be returned as an
        :class:`UnresolvedDict` or :class:`UnresolvedList`, respectively. If the object
        is a value, it will be resolved before being returned. If it is a function call,
        it will be evaluated. If it evaluates to a container, it will be returned as an
        :class:`UnresolvedDict` or :class:`UnresolvedList`, respectively. If it
        evaluates to a value, it will again be resolved before being returned.

        """

    @abc.abstractmethod
    def __len__(self) -> int:
        """Get the number of items in the dictionary. Does not trigger resolution."""

    @abc.abstractmethod
    def __iter__(self) -> Iterable[str]:
        """Iterate over the keys of the dictionary. Does not trigger resolution."""

    @abc.abstractmethod
    def keys(self) -> Iterable[str]:
        """Get the keys of the dictionary. Does not trigger resolution."""

    @abc.abstractmethod
    def values(
        self,
    ) -> Iterable[Union["UnresolvedDict", "UnresolvedList", Configuration]]:
        """Get the values of the dictionary.

        This will trigger the resolution of leaf values and function nodes.

        """

    @abc.abstractmethod
    def resolve(self) -> ConfigurationDict:
        """Recursively resolves the dictionary."""

    @abc.abstractmethod
    def get_keypath(self, keypath: Union["KeyPath", str]) -> Configuration:
        """Return the resolved configuration at the given keypath.

        This drills down through nested containers to find the part of the configuration
        at the keypath. It then resolves that part of the configuration and returns it.

        """


class UnresolvedList(abc.ABC):
    """A list that lazily resolves its values.

    This is an abstract base class and is not meant to be instantiated directly.

    """

    @abc.abstractmethod
    def __getitem__(
        self, ix
    ) -> Union["UnresolvedDict", "UnresolvedList", Configuration]:
        """Get an item from the list.

        The semantics of this depend on the type of object being retrieved. If the
        object is a container (a dictionary or list), it will be returned as an
        :class:`UnresolvedDict` or :class:`UnresolvedList`, respectively. If the object
        is a value, it will be resolved before being returned. If it is a function call,
        it will be evaluated. If it evaluates to a container, it will be returned as an
        :class:`UnresolvedDict` or :class:`UnresolvedList`, respectively. If it
        evaluates to a value, it will again be resolved before being returned.

        """

    @abc.abstractmethod
    def __iter__(
        self,
    ) -> Iterable[Union["UnresolvedDict", "UnresolvedList", Configuration]]:
        """Iterate over the items in the list.

        This will trigger the resolution of leaf values and function nodes.

        """

    @abc.abstractmethod
    def __len__(self) -> int:
        """Get the number of items in the list. Does not trigger resolution."""

    @abc.abstractmethod
    def resolve(self) -> ConfigurationList:
        """Recursively resolves the list."""

    @abc.abstractmethod
    def get_keypath(self, keypath: Union["KeyPath", str]) -> Configuration:
        """Return the resolved configuration at the given keypath.

        This drills down through nested containers to find the part of the configuration
        at the keypath. It then resolves that part of the configuration and returns it.

        """


class UnresolvedFunctionCall(abc.ABC):
    """A function call that lazily resolves its values.

    This is an abstract base class and is not meant to be instantiated directly.

    Unlike :class:`UnresolvedDict` and :class:`UnresolvedList`, this does not provide a
    :meth:`resolve` method. This is because there is never a need to resolve an
    unresolved function call explicitly -- it will always be resolved implicitly when it
    is indexed into, accessed as a child of another container, or when its
    :meth:`get_keypath` method is called. Calling :meth:`resolve` on an
    :class:`UnresolvedFunctionCall` would only result in infinite recursion, so it is
    not provided.

    """

    @abc.abstractmethod
    def __getitem__(
        self, key: str
    ) -> Union["UnresolvedDict", "UnresolvedList", Configuration]:
        """Get an item from the result of the function call.

        The result of the function call might not be a container. If it isn't, this
        should raise a `TypeError`.

        Otherwise, the semantics match those of :meth:`UnresolvedDict.__getitem__` or
        :meth:`UnresolvedList.__getitem__`, depending on the type of the result.

        """

    @abc.abstractmethod
    def get_keypath(self, keypath: Union["KeyPath", str]) -> Configuration:
        """Return the resolved configuration at the given keypath.

        This drills down through nested containers to find the part of the configuration
        at the keypath. It then resolves that part of the configuration and returns it.

        May raise a `TypeError` if the result of the function call is not a container.

        """


# functions ============================================================================


@dataclasses.dataclass
class FunctionArgs:
    """Holds the arguments for a function call."""

    #: The input to the function. This is read from the configuration.
    input: Configuration

    #: The root of the configuration tree.
    root: Union[UnresolvedDict, UnresolvedList, UnresolvedFunctionCall]

    #: The keypath to the function being evaluated.
    keypath: "KeyPath"

    #: The context in which the function is being evaluated.
    resolution_context: "ResolutionContext"


class Function:
    """Represents a function that can be called from within a configuration.

    Parameters
    ----------
    fn : Callable[[FunctionArgs], Configuration]
        The function to call.
    resolve_input : bool
        If `True`, the input will be resolved before being passed to the function.
        Defaults to `True`.

    """

    def __init__(self, fn: Callable[[FunctionArgs], Configuration], resolve_input=True):
        self.fn = fn
        self.resolve_input = resolve_input

    def __call__(self, args: FunctionArgs) -> Configuration:
        """Call the function.

        If :attr:`resolve_input` is `True`, the input will be resolved before being
        passed to the function. Otherwise, it will be passed as-is.

        """
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

        Example
        -------

        .. code:: python

            # define a function whose input is not resolved
            @Function.new(resolve_input=False)
            def raw(args: FunctionArgs):
                return RawString(args.input)

        """

        @functools.wraps(cls)
        def decorator(fn: Callable[[FunctionArgs], Configuration]) -> "Function":
            return cls(fn, resolve_input)

        return decorator


# special strings ======================================================================


class RawString(str):
    """If this appears in a configuration, it will not be interpolated or parsed.

    A subclass of :class:`str`.

    """


class RecursiveString(str):
    """If this appears in a configuration, it will be interpolated recursively.

    A subclass of :class:`str`.

    """


# misc. type aliases ===================================================================

# a schema is a dictionary that describes the expected structure of a configuration
type Schema = Mapping[str, Any]

# a keypath is a tuple of strings that represents a path through a configuration
# tree. For example, ("foo", "bar", "baz") would represent the path to the value
# of the key "baz" in the dictionary {"foo": {"bar": {"baz": 42}}}.
type KeyPath = Tuple[str, ...]

FunctionCallChecker = Callable[
    [ConfigurationDict, Mapping[str, Function]],
    Union[tuple[Function, Configuration], None],
]


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
    check_for_function_call : FunctionCallChecker
        A function that checks if a ConfigurationDict represents a function call. It
        is given the configuration and the available functions. If it is a function
        call, it returns a 2-tuple of the function and the input to the function. If
        not, it returns None. If it is an invalid function call, it should raise
        a ValueError.

    """

    parsers: Mapping[str, Callable]
    functions: Mapping[str, Function]
    global_variables: Mapping[str, Any]
    filters: Mapping[str, Callable]
    inject_root_as: Optional[str]
    check_for_function_call: FunctionCallChecker
