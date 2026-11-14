"""Provides :class:`Template`, the resolved value of a template field.

A template field is a field whose schema has ``"type": "template"``. When a
configuration is resolved, the value of such a field is not evaluated; instead, it is
kept as written and returned as a :class:`Template`, which can be evaluated later
(possibly many times) with :meth:`Template.evaluate`.

This module imports only ``types`` and ``exceptions`` at module level, so that
``_internals`` can import it. Anything needed from the resolution machinery is
imported lazily inside methods.

"""

from collections.abc import Callable, Iterable, Mapping
import copy
from typing import Any

from . import types as _types
from .exceptions import ResolutionError


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

    """

    __hash__ = None  # type: ignore[assignment]

    def __init__(
        self,
        source: _types.Configuration,
        schema: _types.Schema | _types.DynamicSchema = {"type": "any"},
        parameters: Iterable[str] = (),
        keypath: Iterable[str] = (),
        *,
        converters: Mapping[str, Callable] = _DEFAULT,
        functions: _types.FunctionMapping | None = _DEFAULT,
        filters: Mapping[str, Callable] | None = None,
        inject_root_as: str | None = None,
        check_for_function_call: _types.FunctionCallChecker | None = _DEFAULT,
    ):
        self.source = copy.deepcopy(source)
        self.schema = schema
        self.parameters: tuple[str, ...] = tuple(parameters)
        self.keypath: _types.KeyPath = tuple(keypath)

        # the options used by .evaluate(); shared (not copied) by __deepcopy__
        self._options: dict[str, Any] = {
            "converters": converters,
            "functions": functions,
            "filters": filters,
            "inject_root_as": inject_root_as,
            "check_for_function_call": check_for_function_call,
        }

    # resolution -----------------------------------------------------------------------

    def evaluate(self, variables: Mapping[str, Any] | None = None) -> Any:
        """Evaluates the template.

        The source is resolved against the schema as by :func:`smartconfig.resolve`
        (interpolation, function calls, type conversion, defaults), with the
        template's options.

        Parameters
        ----------
        variables : Mapping[str, Any] | None
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
            If a variable is missing, if a name that is not a parameter is
            given, or if the template cannot be evaluated. The
            keypath is that of the template followed by the path inside it.

        """
        from ._internals import make_node
        from ._resolve import _make_resolution_context

        if variables is None:
            variables = {}

        # the keys must be exactly the parameters: no more and no fewer
        missing = [n for n in self.parameters if n not in variables]
        unexpected = [n for n in variables if n not in self.parameters]
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
        context = _make_resolution_context(global_variables=variables, **options)

        root = make_node(self.source, self.schema, context, keypath=self.keypath)
        # a template field in the tree would be a template inside this one
        root.template_keypath = self.keypath
        return root.resolve()

    # copying, comparison, display -----------------------------------------------------

    def __deepcopy__(self, memo: dict[int, Any]) -> "Template":
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
