"""Types and type aliases."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Mapping,
    Any,
    Callable,
    Iterable,
    Iterator,
    Protocol,
)
import abc
import typing
import collections.abc
import copy
import dataclasses
import datetime

from ._utils import jinja_reserved_name_problem

# configurations =======================================================================

# these type aliases define a "configuration", which is the type of both the input
# and output of resolve(). A resolved template field is a Template, which is a leaf.

type ConfigurationValue = (
    str | int | float | bool | datetime.datetime | datetime.date | Template | None
)
type ConfigurationContainer = ConfigurationDict | ConfigurationList
type ConfigurationList = list[ConfigurationContainer | ConfigurationValue]
type ConfigurationDict = dict[str, ConfigurationContainer | ConfigurationValue]

type Configuration = ConfigurationContainer | ConfigurationValue

# unresolved containers ================================================================

# these unresolved container types are provided to user-defined functions so that they
# may reference other parts of the configuration tree and trigger their resolution if
# necessary, without exposing the user to the details of how resolution is performed


# a Mapping and a Sequence, so that in ${...} expressions they have the methods and
# behaviour of the dicts and lists they resolve to (items(), get(), negative
# indexes, slices, ...), and filters that expect a dict or list accept them
class UnresolvedDict(collections.abc.Mapping[str, Any]):
    """A dictionary that lazily resolves its values.

    This is an abstract base class and is not meant to be instantiated directly. It
    is a :class:`collections.abc.Mapping`, so it has ``keys()``, ``values()``,
    ``items()`` and ``get()``; ``keys()`` and ``in`` do not trigger resolution.

    """

    @abc.abstractmethod
    def __getitem__(self, key: str) -> UnresolvedDict | UnresolvedList | Configuration:
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
    def __iter__(self) -> Iterator[str]:
        """Iterate over the keys of the dictionary. Does not trigger resolution."""

    @abc.abstractmethod
    def resolve(self) -> ConfigurationDict:
        """Recursively resolves the dictionary."""

    @abc.abstractmethod
    def get_keypath(self, keypath: KeyPath | str) -> Configuration:
        """Return the resolved configuration at the given keypath.

        This drills down through nested containers to find the part of the configuration
        at the keypath. It then resolves that part of the configuration and returns it.

        """


class UnresolvedList(collections.abc.Sequence[Any]):
    """A list that lazily resolves its values.

    This is an abstract base class and is not meant to be instantiated directly.

    """

    # overloaded like Sequence.__getitem__: an index gives one element, a slice
    # gives a list of them
    @typing.overload
    def __getitem__(
        self, ix: int
    ) -> UnresolvedDict | UnresolvedList | Configuration: ...

    @typing.overload
    def __getitem__(
        self, ix: slice
    ) -> list[UnresolvedDict | UnresolvedList | Configuration]: ...

    @abc.abstractmethod
    def __getitem__(self, ix):
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
    ) -> Iterator[UnresolvedDict | UnresolvedList | Configuration]:
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
    def get_keypath(self, keypath: KeyPath | str) -> Configuration:
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
    of another container, or when its :meth:`get_keypath` method is called.

    Furthermore, resolving an :class:`UnresolvedFunctionCall` would always be a circular
    reference. The only way to obtain a reference to one is during the evaluation of that
    same function call (via ``args.root``), at which point the call is already in progress.
    Attempting to resolve it again would be detected as a circular reference.

    """

    @abc.abstractmethod
    def __getitem__(self, key: str) -> UnresolvedDict | UnresolvedList | Configuration:
        """Get an item from the result of the function call.

        The result of the function call might not be a container. If it isn't, this
        should raise a `TypeError`.

        Otherwise, the semantics match those of :meth:`UnresolvedDict.__getitem__` or
        :meth:`UnresolvedList.__getitem__`, depending on the type of the result.

        """

    @abc.abstractmethod
    def get_keypath(self, keypath: KeyPath | str) -> Configuration:
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
    schema : Schema | None
        The schema that the resolved configuration must match. Defaults to `None`,
        which uses the same schema as the function call. For example, if the call
        appears where the schema expects an integer, the configuration is resolved as
        an integer. To resolve with no schema, pass ``{"type": "any"}``.
    local_variables : Mapping[str, Configuration] | None
        Local variables that are made available during string interpolation. Defaults to
        `None`, in which case no local variables are available.
    relative_keypath : KeyPath
        Where the configuration is, relative to the function call, for error
        messages. For example, a loop resolving its body for its second element
        passes ``("1",)``, so that an error in it is reported at ``<call>.1``.
        Defaults to ``()``: at the function call itself.

    """

    def __call__(
        self,
        configuration: Configuration,
        schema: Schema | None = None,
        local_variables: Mapping[str, Configuration] | None = None,
        relative_keypath: KeyPath = (),
    ) -> Configuration: ...


# According to the public interface, functions should return Configuration. However,
# internal functions may return node types (defined in _resolve.py) instead of
# Configuration, as this allows for more expressivity. At runtime, _FunctionResult
# equals Configuration so that documentation generators display the public type. At
# type-check time, we use the wider union to allow internal node types without requiring
# # type: ignore comments.

if TYPE_CHECKING:
    from ._internals import _ConcreteNode, _FunctionCallNode

    type _FunctionResult = Configuration | _ConcreteNode
else:
    type _FunctionResult = Configuration


@dataclasses.dataclass
class FunctionArgs:
    """Holds the arguments for a function call."""

    #: The input to the function. This is read from the configuration.
    input: Configuration

    #: The root of the configuration tree.
    root: UnresolvedDict | UnresolvedList | UnresolvedFunctionCall

    #: The keypath to the function being evaluated.
    keypath: KeyPath

    #: The context in which the function is being evaluated.
    resolution_context: ResolutionContext

    #: A function that resolves a configuration.
    resolve: Resolver

    #: The schema that the result of the function is expected to conform to.
    schema: Schema

    # the below are undocumented; used internally by core functions

    # Root node of the configuration tree.
    _root_node: _ConcreteNode

    # The node corresponding to the function call being evaluated.
    _function_call_node: _FunctionCallNode


class Function:
    """Represents a function that can be called from within a configuration.

    Parameters
    ----------
    fn : Callable[[FunctionArgs], Configuration]
        The function to call.
    resolve_input : bool
        If `True`, the input will be resolved before being passed to the function.
        Defaults to `True`.
    resolve_output : bool
        If `True`, the function's return value is treated as configuration: it is
        resolved, so ``${...}`` strings in it are interpolated and function calls
        in it are evaluated. If `False`, it is treated as finished data: it is
        converted to the schema, but nothing in it is interpolated or evaluated.
        Use `False` when the function returns values that are already resolved,
        such as the result of ``args.resolve``. Defaults to `True`.

    """

    def __init__(
        self,
        fn: Callable[[FunctionArgs], _FunctionResult],
        resolve_input: bool = True,
        resolve_output: bool = True,
    ):
        self.fn = fn
        self.resolve_input = resolve_input
        self.resolve_output = resolve_output

    def __call__(self, args: FunctionArgs) -> _FunctionResult:
        """Call the function.

        If :attr:`resolve_input` is `True`, the input will be resolved before being
        passed to the function. Otherwise, it will be passed as-is.

        """
        return self.fn(args)

    @classmethod
    def new(
        cls, resolve_input: bool = True, resolve_output: bool = True
    ) -> Callable[[Callable[[FunctionArgs], _FunctionResult]], Function]:
        """Decorator for creating a new Function object.

        Parameters
        ----------
        resolve_input : bool
            If `True`, the input will be resolved before being passed to the function.
        resolve_output : bool
            If `True`, the return value will be resolved as configuration. If
            `False`, it is only converted to the schema. See :class:`Function`.

        Example
        -------

        .. code:: python

            # define a function whose input is not resolved
            @Function.new(resolve_input=False)
            def verbatim(args: FunctionArgs):
                return args.input

        """

        def decorator(fn: Callable[[FunctionArgs], _FunctionResult]) -> Function:
            result = cls(fn, resolve_input, resolve_output)
            result.__doc__ = fn.__doc__
            return result

        return decorator


# a function that can be called from within a configuration, either as a
# Function instance or a plain callable
type FunctionOrCallable = Function | Callable[[FunctionArgs], _FunctionResult]

# a mapping from function names to functions or nested FunctionMapping instances,
# allowing namespaced function organization
type FunctionMapping = Mapping[str, FunctionOrCallable | FunctionMapping]

# a callable that inspects a ConfigurationDict and determines whether it represents a
# function call. Returns a (function, input) tuple if so, or None if not. Should raise
# ValueError for invalid function calls.
type FunctionCallChecker = Callable[
    [ConfigurationDict, Mapping[str, Function]],
    tuple[Function, Configuration] | None,
]


# schemas ==============================================================================


# a schema is a dictionary that describes the expected structure of a configuration
type Schema = Mapping[str, Any]

# a dynamic schema is a function that returns a schema based on the configuration
# and keypath
type DynamicSchema = Callable[[Configuration, KeyPath], Schema]

# misc. type aliases ===================================================================

# a keypath is a tuple of strings that represents a path through a configuration
# tree. For example, ("foo", "bar", "baz") would represent the path to the value
# of the key "baz" in the dictionary {"foo": {"bar": {"baz": 42}}}.
type KeyPath = tuple[str, ...]


@dataclasses.dataclass
class ResolutionContext:
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
    inject_root_as: str | None
    check_for_function_call: FunctionCallChecker


# templates ============================================================================

# a Template is the resolved value of a template field: a field whose schema has
# "type": "template". Its value is kept as written and can be evaluated later
# (possibly many times) with Template.evaluate().


class _UseResolveDefault:
    """Sentinel type: "use the default of :func:`smartconfig.resolve`"."""

    def __repr__(self) -> str:
        return "<resolve() default>"


# sentinel meaning "use the default of resolve()". None cannot be used for this,
# since in resolve() `functions=None` means "no functions" and
# `check_for_function_call=None` means "function calls are disabled".
_DEFAULT: Any = _UseResolveDefault()


class Template:
    """A configuration value whose evaluation is deferred.

    A :class:`Template` is the resolved value of a template field. It holds the
    value as written, along with the schema that the value must match once it is
    evaluated and its parameters: the names that are given to it each time it is
    evaluated.

    Parameters
    ----------
    source : :class:`types.Configuration`
        The value as written. It is deep-copied.
    schema : Union[:class:`types.Schema`, :class:`types.DynamicSchema`]
        The schema that the evaluated value must match. Defaults to
        ``{"type": "any"}``.
    parameters : Iterable[str]
        The template's parameters: the names whose values are given each time the
        template is evaluated, exactly these and no others.
    keypath : Iterable[str]
        The keypath where the template was written. Errors raised while evaluating
        the template are reported relative to it.
    converters : Mapping[str, Callable]
        Converters used when evaluating. Defaults to those of
        :func:`smartconfig.resolve`.
    functions : :class:`types.FunctionMapping` | None
        Functions available when evaluating. Defaults to those of
        :func:`smartconfig.resolve`.
    filters : Mapping[str, Callable] | None
        Jinja2 filters available when evaluating. Defaults to ``None``.
    global_variables : Mapping[str, Any] | None
        Variables available when evaluating, as in :func:`smartconfig.resolve`. A
        parameter of the same name shadows one. Defaults to ``None``.
    inject_root_as : str | None
        As in :func:`smartconfig.resolve`. Defaults to ``None``.
    check_for_function_call : :class:`types.FunctionCallChecker` | None
        As in :func:`smartconfig.resolve`. Defaults to that of
        :func:`smartconfig.resolve`.

    Attributes
    ----------
    source : :class:`types.Configuration`
        The value as written.
    schema : Union[:class:`types.Schema`, :class:`types.DynamicSchema`]
        The schema of the evaluated value.
    parameters : tuple[str, ...]
        The names that must be given, no more and no fewer, when evaluating.
    keypath : :class:`types.KeyPath`
        Where the template was written.

    Raises
    ------
    TypeError
        If ``parameters`` is a string rather than a list of names.
    ValueError
        If a parameter has a name that Jinja reserves, such as ``true`` or
        ``self``, since ``${...}`` could never refer to it.

    """

    __hash__ = None  # type: ignore[assignment]

    def __init__(
        self,
        source: Configuration,
        schema: Schema | DynamicSchema = {"type": "any"},
        parameters: Iterable[str] = (),
        keypath: Iterable[str] = (),
        *,
        converters: Mapping[str, Callable] = _DEFAULT,
        functions: FunctionMapping | None = _DEFAULT,
        filters: Mapping[str, Callable] | None = None,
        global_variables: Mapping[str, Any] | None = None,
        inject_root_as: str | None = None,
        check_for_function_call: FunctionCallChecker | None = _DEFAULT,
    ):
        self.source = copy.deepcopy(source)
        self.schema = schema
        # a string is an iterable of characters, so "abc" would be the parameters a,
        # b and c; it is almost certainly a mistake for ["abc"]
        if isinstance(parameters, str):
            raise TypeError(
                f"parameters must be a list of names, not the string {parameters!r}."
            )
        self.parameters: tuple[str, ...] = tuple(parameters)

        # a parameter named like true or self could never be referred to: ${ true }
        # would be Jinja's literal, silently, not the parameter
        for name in self.parameters:
            problem = jinja_reserved_name_problem(name)
            if problem is not None:
                raise ValueError(f"Invalid parameter: {problem}")
        self.keypath: KeyPath = tuple(keypath)

        # the options used by .evaluate(); shared (not copied) by __deepcopy__
        self._options: dict[str, Any] = {
            "converters": converters,
            "functions": functions,
            "filters": filters,
            "global_variables": global_variables,
            "inject_root_as": inject_root_as,
            "check_for_function_call": check_for_function_call,
        }

    # resolution -----------------------------------------------------------------------

    def evaluate(self, parameters: Mapping[str, Any] | None = None) -> Any:
        """Evaluates the template.

        The source is resolved against the schema as by :func:`smartconfig.resolve`
        (interpolation, function calls, type conversion, defaults), with the
        template's options.

        Parameters
        ----------
        parameters : Mapping[str, Any] | None
            The values of the template's parameters. Its keys must be exactly the
            names in :attr:`parameters`.

        Returns
        -------
        Any
            The value: a :class:`types.Configuration`. Typed as ``Any`` so
            that callers can index into it, as with :func:`smartconfig.resolve`.

        Raises
        ------
        ResolutionError
            If a parameter is missing, if a name that is not a parameter is
            given, or if the template cannot be evaluated. The
            keypath is that of the template followed by the path inside it.

        """
        # imported here: these modules import this one
        from ._internals import (
            _FunctionCallNode,
            check_keys_are_not_parameters,
            make_template_tree,
            reporting_recursion_errors,
        )
        from ._resolve import _make_resolution_context
        from .exceptions import ResolutionError

        # named like the schema's "parameters" and Template.parameters (it was
        # "variables" before 0.6.0)
        if parameters is None:
            parameters = {}

        # the keys must be exactly the parameters: no more and no fewer
        missing = [n for n in self.parameters if n not in parameters]
        unexpected = [n for n in parameters if n not in self.parameters]
        if missing or unexpected:
            problems = []
            if missing:
                problems.append(f"Missing parameters: {', '.join(missing)}.")
            if unexpected:
                problems.append(f"Unexpected parameters: {', '.join(unexpected)}.")
            needs = ", ".join(self.parameters) or "none"
            raise ResolutionError(
                f"{' '.join(problems)} This template's parameters: {needs}.",
                self.keypath,
            )

        # options left at _DEFAULT take resolve()'s defaults
        options = {k: v for k, v in self._options.items() if v is not _DEFAULT}

        # the parameters are added to the globals, and win over them: whoever
        # calls resolve() may pass globals that the template's author never saw,
        # and the template should not break because one shares a parameter's name
        global_variables = {**(options.pop("global_variables") or {}), **parameters}
        context = _make_resolution_context(global_variables=global_variables, **options)

        # as in resolve(): a tree too deep to build or resolve is a ResolutionError
        with reporting_recursion_errors():
            # a template field in the tree would be a template inside this one
            root = make_template_tree(self.source, self.schema, context, self.keypath)

            # Keys named like parameters are also checked when a template field is
            # resolved, but a function call's keys are only known once it is
            # evaluated, and a Template can be made directly, without resolve().
            keyed = root.evaluate() if isinstance(root, _FunctionCallNode) else root
            check_keys_are_not_parameters(keyed, self.parameters)

            return root.resolve()

    # copying, comparison, display -----------------------------------------------------

    def __deepcopy__(self, memo: dict[int, Any]) -> Template:
        new = object.__new__(type(self))
        memo[id(self)] = new
        new.source = copy.deepcopy(self.source, memo)
        new.schema = self.schema
        new.parameters = self.parameters
        new.keypath = self.keypath
        new._options = self._options
        return new

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Template):
            return NotImplemented
        return (
            self.source == other.source
            and self.schema == other.schema
            and self.parameters == other.parameters
            and self.keypath == other.keypath
        )

    def __repr__(self) -> str:
        keypath = ".".join(self.keypath)
        names = ", ".join(self.parameters) or "none"
        return f'Template(at "{keypath}", parameters: {names})'
