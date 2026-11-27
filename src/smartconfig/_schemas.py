"""Provides validate_schema(), which checks that a schema is valid.

Note that this module does *not* check that a configuration matches its schema. That is
done by resolve().

"""

from collections.abc import Callable, Iterator, Mapping, Set
from . import exceptions as _exceptions, types as _types
from ._utils import jinja_reserved_name_problem

# the types of value schemas when no converters are given: the default converters
_DEFAULT_VALUE_TYPES = frozenset(
    {"string", "integer", "float", "boolean", "date", "datetime"}
)

# helpers ==============================================================================


def _check_keys(
    schema: _types.Schema,
    keypath: _types.KeyPath,
    allow_default: bool,
    required: Set[str] = frozenset(),
    optional: Set[str] = frozenset(),
):
    """Checks that a schema has no missing or extra keys.

    Every schema requires "type" and may have "nullable", and "default" where
    ``allow_default`` is true; ``required`` and ``optional`` are the other keys.

    Raises
    ------
    InvalidSchemaError
        If the schema is missing required keys or has unexpected keys.

    """
    required = {"type", *required}
    allowed = required | optional | {"nullable"}
    if allow_default:
        allowed.add("default")

    extra = set(schema.keys() - allowed)
    missing = set(required - schema.keys())

    if extra:
        exemplar = extra.pop()
        raise _exceptions.InvalidSchemaError("Unexpected key.", keypath + (exemplar,))

    if missing:
        exemplar = missing.pop()
        raise _exceptions.InvalidSchemaError("Missing key.", keypath + (exemplar,))


def _validate_names(names: object, keypath: _types.KeyPath):
    """Checks that ``names`` is a list of strings, each a valid identifier that
    Jinja doesn't reserve (such as ``true`` or ``self``).

    Raises
    ------
    InvalidSchemaError
        If ``names`` is not a list, or if an element is not an identifier string or
        is reserved by Jinja.

    """
    if not isinstance(names, list):
        raise _exceptions.InvalidSchemaError(
            "Must be a list of names (strings).", keypath
        )

    for i, name in enumerate(names):
        if not isinstance(name, str) or not name.isidentifier():
            raise _exceptions.InvalidSchemaError(
                f"Invalid name: {name!r}. Names must be valid identifiers.",
                keypath + (str(i),),
            )
        # an identifier like true or self could still never be referred to
        problem = jinja_reserved_name_problem(name)
        if problem is not None:
            raise _exceptions.InvalidSchemaError(problem, keypath + (str(i),))


# validators for each type of schema ===================================================

# validates a child schema, given its keys under the current one (see validate_schema)
type _ValidateChild = Callable[..., None]


def _validate_dict_schema(
    schema: _types.Schema,
    keypath: _types.KeyPath,
    allow_default: bool,
    validate_child: _ValidateChild,
):
    """Validates a dict schema.

    A dict schema has the following form:

        <DICT_SCHEMA> = {
            "type": "dict",
            ["required_keys": {<KEY_NAME>: <SCHEMA>, ...}],
            ["optional_keys": {<KEY_NAME>: (<SCHEMA> | <SCHEMA_WITH_DEFAULT>), ...}],
            ["extra_keys_schema": <SCHEMA>],
            ["nullable": (True | False)],
        }

    """
    _check_keys(
        schema,
        keypath,
        allow_default,
        optional={"required_keys", "optional_keys", "extra_keys_schema"},
    )

    # required_keys and optional_keys map key names to schemas. Check that before
    # reading them below, where a list would raise a bare AttributeError. A key
    # must be a string, since configuration keys are, or no key could match it
    for section in ("required_keys", "optional_keys"):
        keys_schemas = schema.get(section, {})
        if not isinstance(keys_schemas, Mapping):
            raise _exceptions.InvalidSchemaError(
                "Must be a mapping from key names to schemas.", keypath + (section,)
            )
        for key in keys_schemas:
            if not isinstance(key, str):
                raise _exceptions.InvalidSchemaError(
                    "A key name must be a string.", keypath + (section, str(key))
                )

    # a key that is both required and optional is ambiguous: it is unclear
    # whether it may be missing, and which schema applies to it
    for key in schema.get("optional_keys", {}):
        if key in schema.get("required_keys", {}):
            raise _exceptions.InvalidSchemaError(
                "Key is both required and optional.", keypath + ("optional_keys", key)
            )

    for key, key_schema in schema.get("required_keys", {}).items():
        validate_child(key_schema, "required_keys", key)

    # an optional key may have a default
    for key, key_schema in schema.get("optional_keys", {}).items():
        validate_child(key_schema, "optional_keys", key, allow_default=True)

    if "extra_keys_schema" in schema:
        validate_child(schema["extra_keys_schema"], "extra_keys_schema")


def _validate_list_schema(
    schema: _types.Schema,
    keypath: _types.KeyPath,
    allow_default: bool,
    validate_child: _ValidateChild,
):
    """Validates a list schema.

    A list schema has the following form:

        <LIST_SCHEMA> = {
            "type": "list",
            "element_schema": <SCHEMA>,
            ["nullable": (True | False)]
        }

    """
    _check_keys(schema, keypath, allow_default, required={"element_schema"})

    # The list itself may have a default (under optional_keys), but its elements
    # may not: an element can't be missing, so a default there would be silently
    # ignored
    validate_child(schema["element_schema"], "element_schema")


def _validate_template_schema(
    schema: _types.Schema,
    keypath: _types.KeyPath,
    allow_default: bool,
    validate_child: _ValidateChild,
):
    """Validates a template schema.

    A template schema has the following form:

        <TEMPLATE_SCHEMA> = {
            "type": "template",
            "schema": <SCHEMA>,
            "parameters": [<NAME>, ...],
            ["nullable": (True | False)]
        }

    """
    _check_keys(schema, keypath, allow_default, required={"schema", "parameters"})
    _validate_names(schema["parameters"], keypath + ("parameters",))

    # the inner schema may not have a default at its top level: the default of a
    # template field belongs on the template schema
    inner = schema["schema"]
    validate_child(inner, "schema")

    # A template's top-level keys can be referenced by name, like its parameters,
    # so a parameter named like a key that the inner schema declares would be
    # ambiguous. Catch it here, where it is visible from the schema alone.
    declared = {key for _, key in _declared_keys(inner)}
    for i, name in enumerate(schema["parameters"]):
        if name in declared:
            raise _exceptions.InvalidSchemaError(
                f'The parameter "{name}" has the same name as a key of the '
                "template's schema. A template's keys can be referenced by name, "
                "like its parameters, so the name would be ambiguous. Rename the "
                "parameter or the key.",
                keypath + ("parameters", str(i)),
            )

    # A template inside this one sees this template's parameters by name, so a
    # parameter or a top-level key of it with the same name would be ambiguous.
    # Each template checks the templates inside it, at any depth, so every pair of
    # enclosing and enclosed templates is checked
    outer = set(schema["parameters"])
    for inner_keypath, inner_template in _templates_inside(
        inner, keypath + ("schema",)
    ):
        for i, name in enumerate(inner_template["parameters"]):
            if name in outer:
                raise _exceptions.InvalidSchemaError(
                    f'The parameter "{name}" is also a parameter of a template '
                    "around this one. A template inside a template sees the "
                    "parameters of the templates around it, so the name would be "
                    "ambiguous. Rename one of them.",
                    inner_keypath + ("parameters", str(i)),
                )
        for section, key in _declared_keys(inner_template["schema"]):
            if key in outer:
                raise _exceptions.InvalidSchemaError(
                    f'The key "{key}" has the same name as a parameter of a template '
                    "around this one. A template's keys can be referenced by name, "
                    "like the parameters it sees, so the name would be ambiguous. "
                    "Rename the key or the parameter.",
                    inner_keypath + ("schema", section, key),
                )


def _templates_inside(
    schema: _types.Schema | _types.DynamicSchema, keypath: _types.KeyPath
) -> Iterator[tuple[_types.KeyPath, _types.Schema]]:
    """The template schemas inside a valid schema, at any depth, with their keypaths.

    Dynamic schemas are not called, so the templates behind them are not found;
    they are checked when the configuration is resolved.

    """
    if callable(schema):
        return
    if schema["type"] == "dict":
        for section in ("required_keys", "optional_keys"):
            for key, key_schema in schema.get(section, {}).items():
                yield from _templates_inside(key_schema, keypath + (section, key))
        if "extra_keys_schema" in schema:
            yield from _templates_inside(
                schema["extra_keys_schema"], keypath + ("extra_keys_schema",)
            )
    elif schema["type"] == "list":
        yield from _templates_inside(
            schema["element_schema"], keypath + ("element_schema",)
        )
    elif schema["type"] == "template":
        yield keypath, schema
        yield from _templates_inside(schema["schema"], keypath + ("schema",))


def _declared_keys(
    schema: _types.Schema | _types.DynamicSchema,
) -> Iterator[tuple[str, str]]:
    """The (section, key) of each top-level key that a dict schema declares."""
    if callable(schema) or schema["type"] != "dict":
        return
    for section in ("required_keys", "optional_keys"):
        for key in schema.get(section, {}):
            yield section, key


def _validate_value_schema(
    schema: _types.Schema,
    keypath: _types.KeyPath,
    allow_default: bool,
    value_types: Set[str],
):
    """Validates a value schema.

    A value schema has the following form:

        <VALUE_SCHEMA> = {
            "type": <a name in value_types>,
            ["nullable": (True | False)]
        }

    """
    _check_keys(schema, keypath, allow_default)

    # list the valid types, since a type can be invalid because no converter for it
    # was given, not only because it is misspelled
    if schema["type"] not in value_types:
        structural = ["any", "dict", "list", "template"]
        others = sorted(set(value_types) - set(structural))
        valid = ", ".join(structural + others)
        raise _exceptions.InvalidSchemaError(
            f"Invalid type: {schema['type']}. Valid types: {valid}. A type other "
            "than any, dict, list or template must be the name of a converter.",
            keypath + ("type",),
        )


# implementation =======================================================================


def validate_schema(
    schema: _types.Schema | _types.DynamicSchema,
    keypath: _types.KeyPath = tuple(),
    allow_default: bool = False,
    allow_dynamic: bool = True,
    converters: Mapping[str, Callable] | None = None,
    *,
    value_types: Set[str] | None = None,
):
    """Validates a schema.

    Parameters
    ----------
    schema : Union[:class:`types.Schema`, :class:`types.DynamicSchema`]
        The schema to validate. Can be a schema dictionary or a dynamic schema
        function.
    keypath : :class:`types.KeyPath`
        The keypath of the configuration whose schema is being validated. This is useful
        for recursively validating nested configurations. Defaults to ``()``.
    allow_default : bool
        If ``True``, the "default" key is allowed in the schema. Defaults to ``False``.
    allow_dynamic : bool
        If ``True``, dynamic schemas (callables) are allowed. Defaults to ``True``.
    converters : Mapping[str, Callable] | None
        The converters the schema will be used with. The type of a value schema
        must be the name of one of them. Defaults to ``None``, meaning the default
        converters: ``string``, ``integer``, ``float``, ``boolean``, ``date`` and
        ``datetime``.
    value_types : Set[str] | None
        Keyword-only. The names a value schema's type may have. It is computed
        from ``converters`` at the top of the schema and passed down by the
        recursive calls, so it is normally left as ``None``. If given, it is used
        instead of ``converters``.

    Raises
    ------
    InvalidSchemaError
        If the schema is not valid or if a dynamic schema is provided when
        ``allow_dynamic`` is ``False``.

    """
    if callable(schema):
        if not allow_dynamic:
            raise _exceptions.InvalidSchemaError(
                "Dynamic schemas are not allowed.", keypath
            )
        return

    # check the type rather than trying dict(schema): dict() also accepts a list of
    # pairs, which would pass here and then crash resolve(), which needs a mapping
    if not isinstance(schema, Mapping):
        raise _exceptions.InvalidSchemaError("Schema must be a mapping.", keypath)

    if "type" not in schema:
        raise _exceptions.InvalidSchemaError(
            "Required key missing.", keypath + ("type",)
        )

    # the type is compared with names and looked up in a set of them below; a list
    # or dict there would raise a bare TypeError (unhashable type)
    if not isinstance(schema["type"], str):
        raise _exceptions.InvalidSchemaError(
            "Must be the name of a type (a string).", keypath + ("type",)
        )

    # the names a value schema's type may have. `value_types` is used by the
    # recursive calls, so the set is computed once, at the top
    if value_types is None:
        value_types = _DEFAULT_VALUE_TYPES if converters is None else set(converters)

    # nullable is checked by truthiness when resolving, so a string like "no"
    # would silently mean True
    if "nullable" in schema and not isinstance(schema["nullable"], bool):
        raise _exceptions.InvalidSchemaError(
            "Must be True or False.", keypath + ("nullable",)
        )

    def validate_child(child, *keys: str, allow_default: bool = False):
        """Validate the schema ``child`` at ``keys`` under this one."""
        validate_schema(
            child,
            keypath + keys,
            allow_default=allow_default,
            allow_dynamic=allow_dynamic,
            value_types=value_types,
        )

    if schema["type"] == "any":
        # {"type": "any", ["nullable": bool]}
        _check_keys(schema, keypath, allow_default)
    elif schema["type"] == "dict":
        _validate_dict_schema(schema, keypath, allow_default, validate_child)
    elif schema["type"] == "list":
        _validate_list_schema(schema, keypath, allow_default, validate_child)
    elif schema["type"] == "template":
        _validate_template_schema(schema, keypath, allow_default, validate_child)
    else:
        _validate_value_schema(schema, keypath, allow_default, value_types)
