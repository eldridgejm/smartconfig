"""Types and type aliases."""

from typing import (
    Dict,
    List,
    Union,
    Mapping,
    Any,
    Tuple,
    Callable,
    Iterable,
    Optional,
    Protocol,
)
import abc
import dataclasses
import datetime

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

        The reason for resolving values before returning them (instead of returning a
        hypothetical "UnresolvedValue" type) is so that :class:`UnresolvedDict` behaves
        like a normal dictionary in most situations where a specific value is retrieved.
        In particular, we can pass :class:`UnresolvedDict` into Jinja2 to provide
        template variables, and Jinja2 will correctly perform string interpolation.

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

        The reason for resolving values before returning them (instead of returning a
        hypothetical "UnresolvedValue" type) is so that :class:`UnresolvedList` behaves
        like a normal list in most situations where a specific value is retrieved.

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

    Users rarely interact with :class:`UnresolvedFunctionCall` instances directly, and
    only when the very root of the configuration is a function call. In most cases, the
    function call will be contained within an :class:`UnresolvedDict` or
    :class:`UnresolvedList`, and accessing the function call through those containers
    will trigger its evaluation into a value or another unresolved container.

    Because of this, :class:`UnresolvedFunctionCall` does not provide a :meth:`resolve`
    method. There is never a need to resolve an unresolved function call explicitly --
    it will always be resolved implicitly when it is indexed into, accessed as a child
    of another container, or when its :meth:`get_keypath` method is called. Since the
    user will only see an :class:`UnresolvedFunctionCall` instance when the call is the
    root of the configuration, calling a ``.resolve()`` on it would result in infinite
    recursion.

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

        The main (and maybe only) use case for this method is in configurations with
        "nested" functions calls, where the outer function is the root of the
        configuration, and it returns a container that contains another function call.
        If that inner function call needs to obtain a value at a keypath, this method
        might be needed. For example:

        .. code:: python

            config = {
                "__outer__": {
                    "foo": {
                        "x": 1,
                        "y": 2,
                    },
                    "bar": {"__inner__": {}}
                }
            }

        If the inner function call needs to get the value of ``"foo.x"``, it can use
        ``.get_keypath("foo.x")`` on the root of the configuration, which will be a
        :class:`UnresolvedFunctionCall` instance.

        In other situations, the :class:`UnresolvedFunctionCall` will be implicitly
        resolved into a value or another unresolved container when it is accessed
        through :meth:`UnresolvedDict.__getitem__` or
        :meth:`UnresolvedList.__getitem__`. So this method exists only to support the
        edge case of nested function calls.

        """


# functions ============================================================================


class Resolver(Protocol):
    """A protocol for a function that resolves a configuration.

    This is a callable that takes a configuration and returns a resolved configuration.

    Parameters
    ----------
    configuration : Configuration
        The configuration to resolve.
    schema : Optional[Schema]
        The schema that the configuration is expected to conform to. If provided, the
        resolved configuration will be validated against the schema. Defaults to
        `None`.
    local_variables : Optional[Mapping[str, Configuration]]
        Local variables that are made available during string interpolation. Defaults to
        `None`, in which case no local variables are available.

    """

    def __call__(
        self,
        configuration: Configuration,
        schema: Optional["Schema"] = None,
        local_variables: Optional[Mapping[str, Configuration]] = None,
    ) -> Configuration: ...


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
    resolution_options: "ResolutionOptions"

    #: A function that resolves a configuration.
    resolve: Resolver

    #: The schema that the result of the function is expected to conform to.
    schema: "Schema"


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

        def decorator(fn: Callable[[FunctionArgs], Configuration]) -> "Function":
            result = cls(fn, resolve_input)
            result.__doc__ = fn.__doc__
            return result

        return decorator


# special strings ======================================================================


class RawString(str):
    """If this appears in a configuration, it will not be interpolated or converted.

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
class ResolutionOptions:
    """Holds information available at the time that a node is resolved.

    Attributes
    ----------
    converters : Mapping[str, Callable]
        Converters for different types of values.
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

    converters: Mapping[str, Callable]
    functions: Mapping[str, Function]
    global_variables: Mapping[str, Any]
    filters: Mapping[str, Callable]
    inject_root_as: Optional[str]
    check_for_function_call: FunctionCallChecker
