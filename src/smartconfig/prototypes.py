"""Prototypes: configuration schemas written as dataclasses.

A :class:`Prototype` subclass is a stdlib dataclass whose fields describe the keys of
a dict schema. Each field's schema is inferred from its type hint for the
unambiguous cases (``str``, ``int``, ``list[T]``, ``T | None``, a nested Prototype,
...), or given explicitly with ``typing.Annotated`` and :func:`schema` or
:func:`template`. The schema is built once, when the class is defined, so a field
that can't be described is a ``TypeError`` there.

:func:`schema_of` gives a class's schema, and :func:`instantiate` builds an instance
from a dict resolved against it. :func:`smartconfig.resolve` does both when it is
given a Prototype class.

:class:`Prototype` is also available as ``smartconfig.Prototype``. The functions are
kept here, rather than at the top level, so that their names (``schema``,
``template``) don't read as the general schema and template tools.

"""

import copy
import dataclasses
import datetime
import inspect
import types
import typing
from collections.abc import Iterable, Mapping
from typing import Any

from . import types as _types

# the schema types of the type hints that are inferred directly
_SIMPLE_TYPES: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "float",
    bool: "boolean",
    datetime.date: "date",
    datetime.datetime: "datetime",
}

# the attribute holding the extra keys, in a Prototype with extra_keys=. The name is
# reserved in every Prototype, so that a field can never collide with it
_EXTRA_KEYS = "extra_keys"

# the class attribute where a Prototype's _PrototypeInfo is kept
_INFO = "__smartconfig_prototype__"

# marks a template() without a default
_NO_DEFAULT: Any = object()


# the escape hatch =====================================================================


@dataclasses.dataclass(frozen=True)
class _SchemaAnnotation:
    """The result of :func:`schema`: a field's schema, given explicitly."""

    schema: _types.Schema | _types.DynamicSchema


@dataclasses.dataclass(frozen=True)
class _TemplateAnnotation:
    """The result of :func:`template`: a template field's schema, in parts."""

    schema: _types.Schema | _types.DynamicSchema
    parameters: tuple[str, ...]
    default: Any


def schema(schema: _types.Schema | _types.DynamicSchema) -> _SchemaAnnotation:
    """Give a Prototype field (or its extra keys) a schema explicitly.

    Used as ``typing.Annotated`` metadata, for a field whose schema can't be
    inferred from its type: one with a complex, nested or dynamic schema. The schema
    is used as given, with two exceptions: if the field has a default and the schema
    doesn't, the field's default is added to it; and if the field's type includes
    ``None``, the schema must be nullable (and if it doesn't, it must not be). The
    field's resolved value is kept as is: a dict stays a dict, even if it has the
    shape of a Prototype.

    Parameters
    ----------
    schema : Union[:class:`types.Schema`, :class:`types.DynamicSchema`]
        The field's schema: a schema dict, or a dynamic schema (a function).

    Returns
    -------
    object
        Metadata for ``typing.Annotated``, or the value of a Prototype's
        ``extra_keys`` class option.

    Raises
    ------
    TypeError
        If ``schema`` is neither a mapping nor callable.

    Examples
    --------
    >>> from typing import Annotated, Any
    >>> import smartconfig
    >>> class Config(smartconfig.Prototype):
    ...     calendar: Annotated[
    ...         dict[str, Any] | None,
    ...         smartconfig.prototypes.schema({"type": "any", "nullable": True}),
    ...     ] = None
    >>> smartconfig.prototypes.schema_of(Config)
    {'type': 'dict', 'optional_keys': {'calendar': {'type': 'any', 'nullable': True, 'default': None}}}

    """
    _check_is_schema(schema, "smartconfig.prototypes.schema()")
    return _SchemaAnnotation(schema)


def template(
    schema: _types.Schema | _types.DynamicSchema,
    parameters: Iterable[str] = (),
    *,
    default: Any = _NO_DEFAULT,
) -> _TemplateAnnotation:
    """Make a Prototype field a template field.

    Used as ``typing.Annotated`` metadata on a field typed
    :class:`types.Template` (or ``Template | None``, for a nullable template field).
    The field's schema is ``{"type": "template", "schema": schema, "parameters":
    [...]}``, nullable if the type includes ``None``, and its resolved value is a
    :class:`types.Template`.

    Parameters
    ----------
    schema : Union[:class:`types.Schema`, :class:`types.DynamicSchema`]
        The schema of the template's value, once it is evaluated.
    parameters : Iterable[str]
        The names given to the template each time it is evaluated. Defaults to none.
    default : Any
        Keyword-only. The default of the template field: the template as written
        (without a ``__template__`` wrapper), used when the key is missing. A field
        with a default is optional. If not given, the field is optional only if it
        has a default of its own (such as ``None``).

    Returns
    -------
    object
        Metadata for ``typing.Annotated``.

    Raises
    ------
    TypeError
        If ``schema`` is neither a mapping nor callable, or ``parameters`` is a
        string rather than an iterable of strings.

    Examples
    --------
    >>> from typing import Annotated
    >>> import smartconfig
    >>> from smartconfig.types import Template
    >>> class Page(smartconfig.Prototype):
    ...     title: Annotated[
    ...         Template, smartconfig.prototypes.template({"type": "string"}, ["publication"])
    ...     ]
    >>> page = smartconfig.resolve(
    ...     {"title": {"__template__": "Lecture ${ publication.number }"}}, Page
    ... )
    >>> page.title.evaluate({"publication": {"number": 4}})
    'Lecture 4'

    """
    _check_is_schema(schema, "smartconfig.prototypes.template()")
    if isinstance(parameters, str):
        raise TypeError(
            "smartconfig.prototypes.template()'s parameters must be an iterable of names, not "
            "a string."
        )
    return _TemplateAnnotation(schema, tuple(parameters), default)


def _check_is_schema(schema: object, where: str) -> None:
    """Raise a TypeError if ``schema`` is neither a schema dict nor dynamic."""
    if not isinstance(schema, Mapping) and not callable(schema):
        raise TypeError(
            f"{where} takes a schema (a mapping) or a dynamic schema (a function), "
            f"not {schema!r}."
        )


# Prototype ============================================================================


@dataclasses.dataclass(frozen=True)
class _PrototypeInfo:
    """What a Prototype class's definition gives: its schema, and how to build it."""

    # the class's dict schema
    schema: _types.Schema

    # each field's type hint (with its Annotated metadata), by field name
    field_hints: dict[str, Any]

    # the type hint of the extra keys' values, or None if there are none. An
    # explicit schema for them is wrapped as Annotated[Any, <annotation>]
    extra_keys_hint: Any


@typing.dataclass_transform(kw_only_default=True, field_specifiers=(dataclasses.field,))
class Prototype:
    """Base class for configuration schemas written as dataclasses.

    Each subclass is a stdlib dataclass with keyword-only fields (so a field without
    a default may follow one with a default): ``__init__``, ``__eq__`` and
    ``__repr__`` come from :mod:`dataclasses`, as does ``dataclasses.field()``, and
    its fields describe the keys of a dict schema. Pass the class to
    :func:`smartconfig.resolve` in place of a schema to get an instance of it, or
    get its schema with :func:`schema_of`.

    A field's schema is inferred from its type hint:

    - ``str``, ``int``, ``float``, ``bool``, ``datetime.date`` and
      ``datetime.datetime`` are the value types ``string``, ``integer``,
      ``float``, ``boolean``, ``date`` and ``datetime``;
    - ``typing.Any`` is ``{"type": "any"}``;
    - ``T | None`` (or ``Optional[T]``) is ``T``'s schema, nullable;
    - ``list[T]`` is a list schema whose element schema is ``T``'s;
    - ``dict[str, T]`` is a dict schema whose ``extra_keys_schema`` is ``T``'s;
    - a Prototype subclass is its dict schema, and its value becomes an instance.

    Any other type is a ``TypeError`` when the class is defined. A field whose schema
    can't be inferred is given one with ``typing.Annotated`` and :func:`schema` or
    :func:`template`, as in ``Annotated[dict[str, Any], smartconfig.prototypes.schema(...)]``.

    A field is optional exactly when it has a default (``= value``, or
    ``dataclasses.field(default_factory=...)``), and its schema gets that default.
    A field holding a Prototype may default to ``None`` (if it is nullable) or to
    ``field(default_factory=TheClass)``, which is the schema default ``{}``: all of
    that class's own defaults. A field with an explicit schema is also optional
    when that schema has a default of its own (a template field's default is the
    template as written, which isn't a value of the field's type).

    The class option ``extra_keys`` allows keys besides the fields, as a dict
    schema's ``extra_keys_schema`` does. Its value is a type hint or an explicit
    :func:`schema`, as for a field. The extra keys are kept in the ``extra_keys``
    attribute, a dict, which is an ``__init__`` argument and is compared by
    ``__eq__``. The name ``extra_keys`` is reserved: no Prototype may have a field
    called that.

    Examples
    --------
    >>> import datetime
    >>> from dataclasses import field
    >>> import smartconfig
    >>> class Course(smartconfig.Prototype):
    ...     name: str
    ...     start: datetime.date
    ...     url: str | None = None
    ...     instructors: list[str] = field(default_factory=list)
    >>> smartconfig.resolve({"name": "DSC 40B", "start": "2026-09-24"}, Course)
    Course(name='DSC 40B', start=datetime.date(2026, 9, 24), url=None, instructors=[])

    """

    if typing.TYPE_CHECKING:
        # the extra keys, in a Prototype with extra_keys= (see the class docstring)
        extra_keys: dict[str, Any]

    def __init_subclass__(cls, *, extra_keys: Any = None, **kwargs: Any) -> None:
        """Make the subclass a dataclass, and build its schema.

        Parameters
        ----------
        extra_keys : Any
            The extra keys' type hint, or an explicit :func:`schema`, or ``None``
            (the default) for no extra keys, or those of a base class.

        Raises
        ------
        TypeError
            If a field's type hint can't be turned into a schema, its default
            can't be a schema's default, or a field is named ``extra_keys``.

        """
        super().__init_subclass__(**kwargs)

        if _EXTRA_KEYS in inspect.get_annotations(cls):
            raise TypeError(
                f"{cls.__name__} has a field named {_EXTRA_KEYS!r}, a name that "
                "Prototypes reserve for their extra keys."
            )

        # the extra keys' type hint: this class's option, or else its base's
        base_info: _PrototypeInfo | None = getattr(cls, _INFO, None)
        extra_keys_hint: Any
        if isinstance(extra_keys, (_SchemaAnnotation, _TemplateAnnotation)):
            extra_keys_hint = typing.Annotated[Any, extra_keys]
        elif extra_keys is not None:
            extra_keys_hint = extra_keys
        elif base_info is not None:
            extra_keys_hint = base_info.extra_keys_hint
        else:
            extra_keys_hint = None

        # the extra keys are a dataclass field of their own, so that __init__,
        # __eq__ and __repr__ include them. A base with extra keys already has it
        inherited_fields = getattr(cls, "__dataclass_fields__", {})
        if extra_keys_hint is not None and _EXTRA_KEYS not in inherited_fields:
            cls.__annotations__[_EXTRA_KEYS] = dict[str, Any]
            setattr(cls, _EXTRA_KEYS, dataclasses.field(default_factory=dict))

        dataclasses.dataclass(cls, kw_only=True)
        setattr(cls, _INFO, _make_info(cls, extra_keys_hint))


def _is_prototype(x: object) -> typing.TypeGuard[type[Prototype]]:
    """Whether ``x`` is a Prototype subclass (not Prototype itself)."""
    return isinstance(x, type) and issubclass(x, Prototype) and x is not Prototype


def _info(cls: object) -> _PrototypeInfo:
    """The _PrototypeInfo of a Prototype subclass; a TypeError for anything else."""
    if not _is_prototype(cls):
        raise TypeError(f"{cls!r} is not a subclass of smartconfig.Prototype.")
    return getattr(cls, _INFO)


class _Unsupported(Exception):
    """A type hint or default that can't be turned into a schema; says why."""


def _make_info(cls: type, extra_keys_hint: Any) -> _PrototypeInfo:
    """Build a Prototype subclass's schema from its dataclass fields."""
    try:
        hints = typing.get_type_hints(cls, include_extras=True)
    except NameError as e:
        raise TypeError(f"{cls.__name__}: a type hint can't be evaluated: {e}") from e

    required_keys: dict[str, Any] = {}
    optional_keys: dict[str, Any] = {}
    field_hints: dict[str, Any] = {}

    for f in dataclasses.fields(cls):
        if extra_keys_hint is not None and f.name == _EXTRA_KEYS:
            continue

        hint = hints[f.name]
        field_hints[f.name] = hint
        try:
            key_schema = _schema_for(hint)
            if _has_default(f):
                key_schema = _with_default(key_schema, _schema_default(f, hint))
        except _Unsupported as e:
            raise TypeError(f"{cls.__name__}.{f.name}: {e}") from None

        if _has_default(f) or (not callable(key_schema) and "default" in key_schema):
            optional_keys[f.name] = key_schema
        else:
            required_keys[f.name] = key_schema

    result: dict[str, Any] = {"type": "dict"}
    if required_keys:
        result["required_keys"] = required_keys
    if optional_keys:
        result["optional_keys"] = optional_keys

    if extra_keys_hint is not None:
        try:
            result["extra_keys_schema"] = _schema_for(extra_keys_hint)
        except _Unsupported as e:
            raise TypeError(f"{cls.__name__}'s extra keys: {e}") from None

    return _PrototypeInfo(result, field_hints, extra_keys_hint)


# type hints to schemas ================================================================


def _is_union(hint: Any) -> bool:
    origin = typing.get_origin(hint)
    return origin is typing.Union or origin is types.UnionType


def _includes_none(hint: Any) -> bool:
    """Whether the type hint is ``T | None``."""
    return _is_union(hint) and type(None) in typing.get_args(hint)


def _without_none(hint: Any) -> Any:
    """``T`` from ``T | None``; other hints as they are."""
    if not _is_union(hint):
        return hint
    others = [arg for arg in typing.get_args(hint) if arg is not type(None)]
    return others[0] if len(others) == 1 else hint


def _annotation_of(hint: Any) -> _SchemaAnnotation | _TemplateAnnotation | None:
    """The smartconfig metadata of an Annotated type hint, if it has one.

    Raises
    ------
    _Unsupported
        If it has more than one.

    """
    found = [
        m
        for m in hint.__metadata__
        if isinstance(m, (_SchemaAnnotation, _TemplateAnnotation))
    ]
    if len(found) > 1:
        raise _Unsupported("Annotated has more than one smartconfig schema.")
    return found[0] if found else None


def _schema_for(hint: Any) -> _types.Schema | _types.DynamicSchema:
    """The schema a type hint describes.

    Raises
    ------
    _Unsupported
        If the type hint isn't one that a schema can be inferred from.

    """
    if typing.get_origin(hint) is typing.Annotated:
        annotation = _annotation_of(hint)
        if annotation is None:
            # metadata for something else: the schema comes from the type
            return _schema_for(hint.__origin__)
        return _explicit_schema(hint.__origin__, annotation)

    if _is_union(hint):
        others = [arg for arg in typing.get_args(hint) if arg is not type(None)]
        if len(others) != 1:
            raise _Unsupported(
                f"Unsupported type hint {hint!r}: a union is supported only as "
                "T | None. Give the field a schema with Annotated[..., "
                "smartconfig.prototypes.schema(...)]."
            )
        (inner,) = others
        if typing.get_origin(inner) is typing.Annotated:
            # Annotated[T, ...] | None is Annotated[T | None, ...]
            return _schema_for(
                typing.Annotated[(inner.__origin__ | None, *inner.__metadata__)]
            )
        inner_schema = _schema_for(inner)
        # only an explicit schema can be dynamic, and that case is handled above
        assert not callable(inner_schema)
        return {**inner_schema, "nullable": True}

    if hint is Any:
        return {"type": "any"}

    if isinstance(hint, type) and hint in _SIMPLE_TYPES:
        return {"type": _SIMPLE_TYPES[hint]}

    if _is_prototype(hint):
        return copy.deepcopy(_info(hint).schema)

    origin = typing.get_origin(hint)
    args = typing.get_args(hint)

    if origin is list and len(args) == 1:
        return {"type": "list", "element_schema": _schema_for(args[0])}

    if origin is dict and len(args) == 2 and args[0] is str:
        return {"type": "dict", "extra_keys_schema": _schema_for(args[1])}

    if hint is _types.Template:
        raise _Unsupported(
            "A Template field needs the schema of its value and its parameters: "
            "type it Annotated[Template, smartconfig.prototypes.template(<schema>, "
            "parameters=[...])]."
        )

    raise _Unsupported(
        f"Unsupported type hint {hint!r}. Supported are str, int, float, bool, "
        "datetime.date, datetime.datetime, Any, T | None, list[T], dict[str, T] and "
        "Prototype subclasses; give any other field a schema with Annotated[..., "
        "smartconfig.prototypes.schema(...)]."
    )


def _explicit_schema(
    base: Any, annotation: _SchemaAnnotation | _TemplateAnnotation
) -> _types.Schema | _types.DynamicSchema:
    """The schema of a field typed ``Annotated[base, annotation]``."""
    nullable = _includes_none(base)

    if isinstance(annotation, _TemplateAnnotation):
        if base is not Any and _without_none(base) is not _types.Template:
            raise _Unsupported(
                "smartconfig.prototypes.template() makes a template field, whose value is a "
                f"Template, so its type must be Template (or Template | None), not "
                f"{base!r}."
            )
        result: dict[str, Any] = {
            "type": "template",
            "schema": annotation.schema,
            "parameters": list(annotation.parameters),
        }
        if nullable:
            result["nullable"] = True
        if annotation.default is not _NO_DEFAULT:
            result["default"] = annotation.default
        return result

    given = annotation.schema
    if callable(given) or base is Any:
        # a dynamic schema's nullability isn't known until it is called
        return given

    # "any" accepts None unless it says it doesn't, like make_node()
    schema_nullable = given.get("nullable", given.get("type") == "any")
    if nullable and not schema_nullable:
        raise _Unsupported(
            f"The type {base!r} includes None, but the schema isn't nullable. Add "
            '"nullable": True to the schema, or remove None from the type.'
        )
    if not nullable and given.get("nullable"):
        raise _Unsupported(
            f"The schema is nullable, but the type {base!r} doesn't include None. "
            "Add | None to the type, or remove nullable from the schema."
        )
    return given


# defaults =============================================================================


def _has_default(f: dataclasses.Field) -> bool:
    return (
        f.default is not dataclasses.MISSING
        or f.default_factory is not dataclasses.MISSING
    )


def _schema_default(f: dataclasses.Field, hint: Any) -> Any:
    """The schema default of a field with a default.

    Raises
    ------
    _Unsupported
        If the default can't be written as configuration.

    """
    # a field holding a Prototype (and not given a schema explicitly) defaults to
    # None or to all of its class's defaults
    core = hint
    if typing.get_origin(core) is typing.Annotated and _annotation_of(core) is None:
        core = core.__origin__
    core = _without_none(core)
    if _is_prototype(core):
        if f.default_factory is core:
            if "required_keys" in _info(core).schema:
                raise _Unsupported(
                    f"default_factory={core.__name__} is {core.__name__}'s defaults, "
                    f"but {core.__name__} has fields without defaults."
                )
            return {}
        if f.default_factory is dataclasses.MISSING and f.default is None:
            return None
        raise _Unsupported(
            f"A field holding a {core.__name__} may default only to None or to "
            f"field(default_factory={core.__name__}), which is all of "
            f"{core.__name__}'s defaults."
        )

    if f.default_factory is not dataclasses.MISSING:
        value = f.default_factory()
    else:
        value = f.default

    if _contains_prototype(value):
        raise _Unsupported(
            "The default holds a Prototype instance, but a schema's default is "
            "configuration, as it would be written (dicts, lists and values)."
        )
    return value


def _contains_prototype(value: object) -> bool:
    if _is_prototype(type(value)):
        return True
    if isinstance(value, Mapping):
        return any(_contains_prototype(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_prototype(v) for v in value)
    return False


def _with_default(
    key_schema: _types.Schema | _types.DynamicSchema, default: Any
) -> _types.Schema | _types.DynamicSchema:
    """``key_schema`` with the field's default.

    A dynamic schema is returned as is: it gives its own default, when it is called
    for a missing key.

    Raises
    ------
    _Unsupported
        If the schema has a different default of its own.

    """
    if callable(key_schema):
        return key_schema
    if "default" in key_schema:
        if key_schema["default"] != default:
            raise _Unsupported(
                f"The field's default, {default!r}, isn't the schema's, "
                f"{key_schema['default']!r}."
            )
        return key_schema
    return {**key_schema, "default": default}


# public functions =====================================================================


def schema_of(cls: type[Prototype]) -> _types.Schema:
    """The schema of a Prototype class.

    Resolving a configuration against this schema and passing the result to
    :func:`instantiate` is what :func:`smartconfig.resolve` does with the class. The
    schema can also be used inside other schemas, where it resolves to a dict.

    Parameters
    ----------
    cls : type[Prototype]
        A subclass of :class:`Prototype`.

    Returns
    -------
    :class:`types.Schema`
        A dict schema, a copy that is the caller's to change.

    Raises
    ------
    TypeError
        If ``cls`` isn't a subclass of :class:`Prototype`.

    Examples
    --------
    >>> import smartconfig
    >>> class Button(smartconfig.Prototype):
    ...     label: str
    ...     url: str | None = None
    >>> smartconfig.prototypes.schema_of(Button)
    {'type': 'dict', 'required_keys': {'label': {'type': 'string'}}, 'optional_keys': {'url': {'type': 'string', 'nullable': True, 'default': None}}}

    """
    return copy.deepcopy(_info(cls).schema)


def instantiate[P: Prototype](cls: type[P], data: Mapping[str, Any]) -> P:
    """Build an instance of a Prototype class from a resolved configuration.

    ``data`` is a dict resolved against ``schema_of(cls)``. Each value whose field
    holds a Prototype (directly, or in a list, a dict or ``| None``) becomes an
    instance of it; every other value is used as it is, including those of fields
    with an explicit schema (a dict stays a dict, a Template a Template). A missing
    key gets the field's default. Nothing is checked or converted: that was done by
    resolving.

    Parameters
    ----------
    cls : type[Prototype]
        A subclass of :class:`Prototype`.
    data : Mapping[str, Any]
        The resolved configuration.

    Returns
    -------
    Prototype
        An instance of ``cls``.

    Raises
    ------
    TypeError
        If ``cls`` isn't a subclass of :class:`Prototype`, a key isn't a field (and
        ``cls`` has no extra keys), or a field without a default is missing.

    Examples
    --------
    >>> import smartconfig
    >>> class Address(smartconfig.Prototype):
    ...     street: str
    >>> class Person(smartconfig.Prototype):
    ...     name: str
    ...     address: Address
    >>> smartconfig.prototypes.instantiate(Person, {"name": "A", "address": {"street": "S"}})
    Person(name='A', address=Address(street='S'))

    """
    info = _info(cls)
    kwargs: dict[str, Any] = {}
    extra: dict[str, Any] = {}
    for key, value in data.items():
        if key in info.field_hints:
            kwargs[key] = _build(info.field_hints[key], value)
        elif info.extra_keys_hint is not None:
            extra[key] = _build(info.extra_keys_hint, value)
        else:
            raise TypeError(f"{cls.__name__} has no field {key!r} (an unexpected key).")
    if info.extra_keys_hint is not None:
        kwargs[_EXTRA_KEYS] = extra
    return cls(**kwargs)


def _build(hint: Any, value: Any) -> Any:
    """A resolved value, with the Prototypes its type hint holds made instances."""
    if not _holds_prototype(hint) or value is None:
        # nothing to build, so the value is kept as resolved (with its container's
        # type, if preserve_type was used)
        return value
    if typing.get_origin(hint) is typing.Annotated:
        return _build(hint.__origin__, value)
    if _is_union(hint):
        return _build(_without_none(hint), value)
    if _is_prototype(hint):
        return instantiate(hint, value)
    (*_, inner) = typing.get_args(hint)
    if typing.get_origin(hint) is list:
        return [_build(inner, element) for element in value]
    return {key: _build(inner, element) for key, element in value.items()}


def _holds_prototype(hint: Any) -> bool:
    """Whether a (supported) type hint has an inferred Prototype in it."""
    if typing.get_origin(hint) is typing.Annotated:
        return _annotation_of(hint) is None and _holds_prototype(hint.__origin__)
    if _is_prototype(hint):
        return True
    return any(_holds_prototype(arg) for arg in typing.get_args(hint))
