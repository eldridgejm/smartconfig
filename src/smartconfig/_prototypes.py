"""Prototype: Define configuration schemas using Python class syntax."""

from typing import Self
import typing
import types
import datetime

from smartconfig.types import Schema

# sentinel for missing default values
_MISSING = object()

# mapping from Python types to schema types
_TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "float",
    bool: "boolean",
    datetime.date: "date",
    datetime.datetime: "datetime",
}


class NotRequired[T]:
    """Marker for optional fields in a Prototype.

    Annotating a field with ``NotRequired[T]`` will cause it to be placed in the
    "optional_keys" section of the schema generated from the Prototype. This type hint
    is called ``NotRequired`` rather than simply ``Optional`` to avoid confusion with
    ``typing.Optional`` from the Python standard library. We do not use
    ``typing.Optional`` here because it is an alias for ``Union[T, None]``, which
    indicates nullability rather than optionality.

    Examples
    --------
    The ``email`` field below is not required and may be omitted from the
    configuration entirely::

        from smartconfig import NotRequired, Prototype

        class Person(Prototype):
            name: str
            email: NotRequired[str]
    """

    pass


class Prototype:
    """Base class for defining configuration schemas using Python class syntax.

    Subclass this to define a configuration schema. The resulting class can be used in
    place of a schema in :func:`resolve`, and the result of resolution will be an
    instance of the prototype class.

    .. warning::

       The initializer does **not** perform any type checking, coercion, or
       nullability validation. Type conversion and validation are the jobs of
       :func:`resolve`. Generally, you should not instantiate Prototype subclasses
       directly; instead, use :func:`resolve` to create instances from configuration
       data.


    Examples
    --------
    A simple prototype describing a person::

        from smartconfig import Prototype, resolve

        class Person(Prototype):
            name: str
            age: int

        cfg = {"name": "Alice", "age": 30}
        person = resolve(cfg, Person)
        assert isinstance(person, Person)
        assert person.name == "Alice"

    """

    def __init_subclass__(cls) -> None:
        """Validate the fields defined in the Prototype subclass.

        This checks that the types used in type hints are supported and that all class
        attributes have annotations.

        This function is called automatically when a subclass is defined.

        """
        for field_name, (type_hint, _) in cls._defined_fields().items():
            if not _is_supported_type_hint(type_hint):
                raise TypeError(
                    f"Unsupported type hint for field '{field_name}': {type_hint}"
                )

        undefined_fields = cls.__dict__.keys() - cls._defined_fields().keys()

        # filter out special attributes/methods and private fields
        undefined_fields = {f for f in undefined_fields if not f.startswith("_")}

        if undefined_fields:
            raise TypeError(
                f"Undefined fields in Prototype subclass '{cls.__name__}': "
                f"{', '.join(undefined_fields)}"
            )

    def __init__(self, **kwargs):
        """Initialize the Prototype instance.

        This method sets the attributes of the instance based on the provided keyword
        arguments.

        - If a field is provided in ``kwargs``, its value is set on the instance.
        - If a field is missing from ``kwargs`` but has a default value, the default
          value is set.
        - If a field is ``NotRequired`` and missing from ``kwargs``, it is skipped
          (the attribute is left unset).
        - If a required field is missing from ``kwargs`` and has no default value,
          a ``TypeError`` is raised.
        - Extra keyword arguments that do not correspond to a defined field are ignored
          (they are not set as attributes, and no error is raised).

        **Important:** This initializer does **not** perform any type checking,
        coercion, or nullability validation. Type conversion and validation are
        the jobs of :func:`resolve`.

        Parameters
        ----------
        **kwargs
            Keyword arguments corresponding to the fields defined in the Prototype.

        """
        for field_name, (type_hint, default_value) in self._defined_fields().items():
            if field_name in kwargs:
                setattr(self, field_name, kwargs[field_name])
            elif default_value is not _MISSING:
                setattr(self, field_name, default_value)
            elif _is_not_required_type(type_hint):
                pass
            else:
                raise TypeError(f"missing required field '{field_name}'")

    def __eq__(self, other: typing.Any) -> bool:
        """Check equality between two Prototype instances.

        Two Prototype instances are equal if they are of the same class
        and all their fields are equal.

        Parameters
        ----------
        other : typing.Any
            The other object to compare against.

        Returns
        -------
        bool
            True if the two instances are equal, False otherwise.

        """
        if not is_prototype_class(type(other)):
            return False

        if type(self) is not type(other):
            return False

        for field_name in self._defined_fields().keys():
            self_has = hasattr(self, field_name)
            other_has = hasattr(other, field_name)
            if self_has != other_has:
                return False
            if self_has and getattr(self, field_name) != getattr(other, field_name):
                return False

        # handle "extra" fields that are not defined in the Prototype
        self_extra_fields = self.__dict__.keys() - self._defined_fields().keys()
        other_extra_fields = other.__dict__.keys() - other._defined_fields().keys()
        if self_extra_fields != other_extra_fields:
            return False

        return True

    def __repr__(self) -> str:
        """Get a string representation of the Prototype instance.

        Examples
        --------
        >>> class Person(Prototype):
        ...     name: str
        ...     age: int
        >>> Person(name='Alice', age=30)
        Person(name='Alice', age=30)

        """
        field_strs = []
        for field_name in self._defined_fields().keys():
            if hasattr(self, field_name):
                value = getattr(self, field_name)
                field_strs.append(f"{field_name}={value!r}")

        return f"{self.__class__.__name__}({', '.join(field_strs)})"

    @classmethod
    def _defined_fields(cls) -> dict[str, typing.Any]:
        """Get the fields defined in the Prototype subclass.

        This is a privately used helper method.

        Returns
        -------
        dict
            A dictionary mapping field names to (type_hint, default_value) tuples.
            The default_value is _MISSING if no default is specified.

        """
        type_hints = typing.get_type_hints(cls)

        result = {}
        for field_name, type_hint in type_hints.items():
            default_value = getattr(cls, field_name, _MISSING)
            result[field_name] = (type_hint, default_value)

        return result

    @classmethod
    def _schema(cls) -> Schema:
        """Convert this Prototype class to an equivalent schema dictionary.

        This is a public method; the leading underscore is to avoid name clashes
        with user-defined fields.

        Returns
        -------
        Schema
            The schema dictionary that is equivalent to this Prototype class.
        """
        required_keys: dict[str, typing.Any] = {}
        optional_keys: dict[str, typing.Any] = {}

        for field_name, (type_hint, default) in cls._defined_fields().items():
            # Convert the inner type to a schema. This handles nested Prototypes, lists,
            # dicts, etc., as well as the simple types.
            type_schema = dict(_type_to_schema(type_hint))

            # Field is optional if it has a default or is wrapped in NotRequired[]
            if default is not _MISSING:
                if is_prototype_class(type_hint):
                    type_schema["default"] = default._as_dict()
                else:
                    type_schema["default"] = default
                optional_keys[field_name] = type_schema
            elif _is_not_required_type(type_hint):
                optional_keys[field_name] = type_schema
            else:
                required_keys[field_name] = type_schema

        result: dict[str, typing.Any] = {"type": "dict"}
        if required_keys:
            result["required_keys"] = required_keys
        if optional_keys:
            result["optional_keys"] = optional_keys

        return typing.cast(Schema, result)

    def _as_dict(self) -> dict[str, typing.Any]:
        """Convert this Prototype instance to a dictionary.

        This is a public method. The leading underscore is used to avoid name
        clashes with user-defined attributes on Prototype subclasses.

        Returns
        -------
        dict
            A dictionary representation of this Prototype instance.

        """

        def _to_dict_value(item: typing.Any) -> typing.Any:
            if is_prototype_class(type(item)):
                return item._as_dict()
            elif isinstance(item, list):
                return [_to_dict_value(sub_item) for sub_item in item]
            elif isinstance(item, dict):
                return {k: _to_dict_value(v) for k, v in item.items()}
            return item

        result = {}
        for field_name in self._defined_fields().keys():
            if hasattr(self, field_name):
                value = getattr(self, field_name)
                result[field_name] = _to_dict_value(value)
        return result

    @classmethod
    def _from_dict(cls, data: dict[str, typing.Any]) -> Self:
        """Create a Prototype instance from a dictionary.

        This is a public method; the leading underscore is to avoid name clashes
        with user-defined fields.

        This will recursively create nested Prototype instances as needed.

        Parameters
        ----------
        data : dict
            A dictionary representation of the Prototype.

        Returns
        -------
        Prototype
            A Prototype instance created from the dictionary.

        Examples
        --------
        >>> from smartconfig import Prototype
        >>> class Address(Prototype):
        ...     street: str
        ...     city: str
        >>> class Person(Prototype):
        ...     name: str
        ...     address: Address
        >>> data = {
        ...     "name": "Alice",
        ...     "address": {"street": "123 Main St", "city": "Anytown"}
        ... }
        >>> person_instance = Person._from_dict(data)
        >>> person_instance.name
        'Alice'
        >>> person_instance.address.city
        'Anytown'
        >>> isinstance(person_instance.address, Address)
        True

        """

        def _convert_value(type_hint: type, value: typing.Any) -> typing.Any:
            # handle nested Prototype subclasses
            if is_prototype_class(type_hint):
                return type_hint._from_dict(value)

            # handle list types (list[T])
            type_origin = typing.get_origin(type_hint)
            if type_origin is list:
                assert len(typing.get_args(type_hint)) == 1
                element_type = typing.get_args(type_hint)[0]
                return [_convert_value(element_type, item) for item in value]

            # handle dict types (Dict[str, T])
            if type_origin is dict:
                # we only support Dict[str, T]
                assert len(typing.get_args(type_hint)) == 2
                _, value_type = typing.get_args(type_hint)
                return {k: _convert_value(value_type, v) for k, v in value.items()}

            # for simple types, return the value directly
            return value

        init_kwargs = {}
        for field_name, (type_hint, _) in cls._defined_fields().items():
            if field_name in data:
                init_kwargs[field_name] = _convert_value(type_hint, data[field_name])
        return cls(**init_kwargs)


def _is_not_required_type(type_hint: type) -> bool:
    """Check if a type hint is smartconfig.NotRequired[T].

    Uses typing.get_origin/get_args to inspect the typing construct; for
    example, get_origin(NotRequired[int]) returns ``smartconfig._prototypes.NotRequired``.
    """
    return typing.get_origin(type_hint) is NotRequired


def _unwrap_not_required(type_hint: type) -> type:
    """Extract T from smartconfig.NotRequired[T]."""
    args = typing.get_args(type_hint)
    if args:
        return args[0]
    raise TypeError(
        f"Cannot unwrap NotRequired without type argument: {type_hint}"
    )  # pragma: no cover


def _is_nullable_type(type_hint: type) -> bool:
    """Check if a type hint is T | None (nullable).

    This handles both `T | None` (Python 3.10+ syntax) and `Union[T, None]`
    via get_origin/get_args.
    """
    origin = typing.get_origin(type_hint)
    if origin is typing.Union or origin is types.UnionType:
        args = typing.get_args(type_hint)
        # Check if exactly one of the args is NoneType
        none_count = sum(1 for arg in args if arg is type(None))
        return none_count == 1 and len(args) == 2
    return False


def _unwrap_nullable(type_hint: type) -> type:
    """Extract T from T | None."""
    args = typing.get_args(type_hint)
    for arg in args:
        if arg is not type(None):
            return arg
    raise TypeError(f"Cannot unwrap nullable type: {type_hint}")  # pragma: no cover


def _unwrap_type_hint(type_hint: type) -> type:
    """Unwrap NotRequired and nullable from a type hint.

    For example, unwraps NotRequired[int] to int, and int | None to int. Leaves
    other type hints unchanged.

    """
    if _is_not_required_type(type_hint):
        type_hint = _unwrap_not_required(type_hint)

    if _is_nullable_type(type_hint):
        type_hint = _unwrap_nullable(type_hint)

    return type_hint


def _is_supported_type_hint(type_hint: type) -> bool:
    """Check if a type hint is supported in Prototype fields.

    Supported type hints include:
    - Builtin types: str, int, float, bool, datetime.date, datetime.datetime
    - smartconfig.NotRequired[T]
    - T | None (nullable types)
    - list[T]
    - dict[str, T]
    - Prototype subclasses

    Parameters
    ----------
    type_hint : type
        The type hint to check.

    """
    type_hint = _unwrap_type_hint(type_hint)

    # Prototype subclasses
    if is_prototype_class(type_hint):
        return True

    # get_origin returns the base generic type (e.g., list in list[int])
    type_origin = typing.get_origin(type_hint)

    # get_args returns the type arguments (e.g., (int,) in list[int])
    type_args = typing.get_args(type_hint)

    if type_origin is list:
        return len(type_args) == 1 and _is_supported_type_hint(type_args[0])

    if type_origin is dict:
        return (
            len(type_args) == 2
            and type_args[0] is str
            and _is_supported_type_hint(type_args[1])
        )

    # Simple builtin types
    if type_hint in _TYPE_MAP:
        return True

    # typing.Any is supported
    if type_hint is typing.Any:
        return True

    return False


def _type_to_schema(type_hint: type) -> Schema:
    """Convert a Python type hint to a Schema type specification.

    This function assumes that _is_supported_type_hint(type_hint) is True.

    Parameters
    ----------
    type_hint
        A Python type (e.g., str, int, float, bool, list[T], Any, Prototype).

    Returns
    -------
    Schema
        A schema type specification.

    Raises
    ------
    TypeError
        If the type hint is not supported.
    """
    if _is_not_required_type(type_hint):
        type_hint = _unwrap_not_required(type_hint)

    # Handle simple types
    if type_hint in _TYPE_MAP:
        return {"type": _TYPE_MAP[type_hint]}

    # Handle typing.Any
    if type_hint is typing.Any:
        return {"type": "any"}

    # Handle Prototype subclasses
    if is_prototype_class(type_hint):
        return dict(type_hint._schema())

    type_origin = typing.get_origin(type_hint)  # e.g., list[str] -> list

    # Handle list types (list[T])
    if type_origin is list:
        type_args = typing.get_args(type_hint)
        # plain list without type argument is not supported
        assert len(type_args) == 1
        element_schema = _type_to_schema(type_args[0])
        return {"type": "list", "element_schema": element_schema}

    # Handle dict types (Dict[str, T])
    if type_origin is dict:
        type_args = typing.get_args(type_hint)  # Dict[str, T] -> (str, T)
        assert len(type_args) == 2
        # Dict[K, V] - we only support str keys
        _, value_type = type_args
        value_schema = _type_to_schema(value_type)
        return {"type": "dict", "extra_keys_schema": value_schema}

    # Handle nullable types (T | None)
    if _is_nullable_type(type_hint):
        inner_type = _unwrap_nullable(type_hint)
        schema = dict(_type_to_schema(inner_type))
        schema["nullable"] = True
        return schema

    # we should never reach here if the type hint is supported
    raise TypeError(f"Unsupported type hint: {type_hint}")  # pragma: no cover


def is_prototype_class(
    type_: typing.Any,
) -> typing.TypeGuard[type[Prototype]]:
    """Check if a type is a Prototype subclass (but not Prototype itself).

    Uses ``TypeGuard`` so static type checkers know that when this returns True,
    ``type_`` can be treated as ``type[Prototype]`` (excluding the base
    Prototype class itself). This enables safe recursive handling of nested
    prototype types elsewhere in the codebase.

    Examples
    --------
    >>> from smartconfig import Prototype, is_prototype_class
    >>> class Person(Prototype):
    ...     name: str
    >>> is_prototype_class(Person)
    True
    >>> is_prototype_class(Prototype)
    False
    >>> person = Person(name="Alice")
    >>> is_prototype_class(person) # because 'person' is an instance, not a class
    False

    """
    return (
        isinstance(type_, type)
        and issubclass(type_, Prototype)
        and type_ is not Prototype
    )
