"""Provides :class:`Template`, the resolved value of a template field.

A template field is a field whose schema has ``"type": "template"``. When a
configuration is resolved, the value of such a field is not evaluated; instead, it is
kept as written and returned as a :class:`Template`, which can be evaluated later
(possibly many times) with :meth:`Template.resolve`.

This module imports only ``types`` and ``exceptions`` at module level, so that
``_internals`` can import it. Anything needed from the resolution machinery is
imported lazily inside methods.

"""

from collections.abc import Callable, Iterable, Mapping
import copy
from typing import Any

from . import types as _types


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
    evaluated and the names it may use.

    Parameters
    ----------
    source : :class:`types.Configuration`
        The value as written. It is deep-copied.
    schema : Union[:class:`types.Schema`, :class:`types.DynamicSchema`]
        The schema that the evaluated value must match. Defaults to
        ``{"type": "any"}``.
    variables : Iterable[str]
        The names that must be given each time the template is evaluated.
    globals : Iterable[str]
        Other names the template may use.
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
    variables : tuple[str, ...]
        Names that must be given when evaluating: those of enclosing templates,
        then the template's own.
    globals : tuple[str, ...]
        Other names the template may use: those of enclosing templates, then the
        template's own.
    keypath : :class:`types.KeyPath`
        Where the template was written.

    """

    __hash__ = None  # type: ignore[assignment]

    def __init__(
        self,
        source: _types.Configuration,
        schema: _types.Schema | _types.DynamicSchema = {"type": "any"},
        variables: Iterable[str] = (),
        globals: Iterable[str] = (),
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
        self.variables: tuple[str, ...] = tuple(variables)
        self.globals: tuple[str, ...] = tuple(globals)
        self.keypath: _types.KeyPath = tuple(keypath)

        # the options used by .resolve(); shared (not copied) by __deepcopy__
        self._options: dict[str, Any] = {
            "converters": converters,
            "functions": functions,
            "filters": filters,
            "inject_root_as": inject_root_as,
            "check_for_function_call": check_for_function_call,
        }

    # serialization --------------------------------------------------------------------

    def to_json(self) -> dict[str, Any]:
        """Returns a JSON-compatible dict describing the template.

        The schema and the options are not included, since they may contain
        callables. Leaf values of ``source`` are left as they are, so a source
        containing (say) dates needs an encoder that handles them.

        Returns
        -------
        dict[str, Any]
            A dict with keys ``"source"``, ``"variables"``, ``"globals"`` and
            ``"keypath"``.

        """
        return {
            "source": copy.deepcopy(self.source),
            "variables": list(self.variables),
            "globals": list(self.globals),
            "keypath": list(self.keypath),
        }

    @classmethod
    def from_json(
        cls,
        data: Mapping[str, Any],
        schema: _types.Schema | _types.DynamicSchema | None = None,
        **options: Any,
    ) -> "Template":
        """Rebuilds a template from the output of :meth:`to_json`.

        Parameters
        ----------
        data : Mapping[str, Any]
            The output of :meth:`to_json`.
        schema : Union[:class:`types.Schema`, :class:`types.DynamicSchema`] | None
            The schema of the template. If ``None``, ``{"type": "any"}`` is used.
        **options
            Keyword-only options of the constructor (``converters``, ``functions``,
            ...). Options not given default to those of :func:`smartconfig.resolve`.

        Returns
        -------
        Template

        """
        if schema is None:
            schema = {"type": "any"}

        return cls(
            data["source"],
            schema,
            variables=data.get("variables", ()),
            globals=data.get("globals", ()),
            keypath=data.get("keypath", ()),
            **options,
        )

    # copying, comparison, display -----------------------------------------------------

    def __deepcopy__(self, memo: dict[int, Any]) -> "Template":
        new = object.__new__(type(self))
        memo[id(self)] = new
        new.source = copy.deepcopy(self.source, memo)
        new.schema = self.schema
        new.variables = self.variables
        new.globals = self.globals
        new.keypath = self.keypath
        new._options = self._options
        return new

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Template):
            return NotImplemented
        return (
            self.source == other.source
            and self.schema == other.schema
            and self.variables == other.variables
            and self.globals == other.globals
            and self.keypath == other.keypath
        )

    def __repr__(self) -> str:
        keypath = ".".join(self.keypath)
        variables = ", ".join(self.variables) if self.variables else "none"
        return f'Template(at "{keypath}", variables: {variables})'
