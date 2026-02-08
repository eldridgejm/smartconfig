"""Provides validate_schema(), which checks that a schema is valid.

Note that this module does *not* check that a configuration matches its schema. That is
done by resolve().

"""

from collections.abc import Set
from . import exceptions as _exceptions, types as _types

# helpers ==============================================================================


def _check_keys(
    provided: Set[str],
    required: Set[str],
    optional: Set[str],
    keypath: _types.KeyPath,
    allow_default: bool,
):
    """Checks that there are no missing or extra keys in the provided set.

    Raises
    ------
    InvalidSchemaError
        If the schema is missing required keys or has unexpected keys.

    """
    allowed = set(required | optional)
    if allow_default:
        allowed.add("default")

    extra = set(provided - allowed)
    missing = set(required - provided)

    if extra:
        exemplar = extra.pop()
        raise _exceptions.InvalidSchemaError("Unexpected key.", keypath + (exemplar,))

    if missing:
        exemplar = missing.pop()
        raise _exceptions.InvalidSchemaError("Missing key.", keypath + (exemplar,))


# dict, list, and value schema validators ==============================================


def _validate_any_schema(
    any_schema: _types.Schema,
    keypath: _types.KeyPath,
    allow_default: bool,
    allow_dynamic: bool,
):
    """Validates an "any" schema.

    An any schema has the following form:

        <ANY_SCHEMA> = {
            "type": "any",
            ["nullable": (True | False)]
        }

    """
    _check_keys(
        any_schema.keys(),
        required={"type"},
        optional={"nullable"},
        keypath=keypath,
        allow_default=allow_default,
    )


def _validate_dict_schema(
    dict_schema: _types.Schema,
    keypath: _types.KeyPath,
    allow_default: bool,
    allow_dynamic: bool,
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
        dict_schema.keys(),
        required={"type"},
        optional={"required_keys", "optional_keys", "extra_keys_schema", "nullable"},
        keypath=keypath,
        allow_default=allow_default,
    )

    # recursively check the children corresponding to the required keys
    for key, key_schema in dict_schema.get("required_keys", {}).items():
        validate_schema(
            key_schema, keypath + ("required_keys", key), allow_dynamic=allow_dynamic
        )

    # recursively check the children corresponding to the optional keys, allowing
    # defaults to be specified
    for key, key_schema in dict_schema.get("optional_keys", {}).items():
        validate_schema(
            key_schema,
            keypath + ("optional_keys", key),
            allow_default=True,
            allow_dynamic=allow_dynamic,
        )

    # if the schema provides an "extra_keys_schema", check that it is a valid schema
    if "extra_keys_schema" in dict_schema:
        validate_schema(
            dict_schema["extra_keys_schema"],
            keypath + ("extra_keys_schema",),
            allow_dynamic=allow_dynamic,
        )


def _validate_list_schema(list_schema, keypath, allow_default, allow_dynamic: bool):
    """Validates a list schema.

    A list schema has the following form:

        <LIST_SCHEMA> = {
            "type": "list",
            "element_schema": <SCHEMA>,
            ["nullable": (True | False)]
        }

    """
    _check_keys(
        list_schema.keys(),
        required={"type", "element_schema"},
        optional={"nullable"},
        keypath=keypath,
        allow_default=allow_default,
    )

    # recursively check the children
    validate_schema(
        list_schema["element_schema"],
        keypath + ("element_schema",),
        allow_default,
        allow_dynamic=allow_dynamic,
    )


def _validate_value_schema(value_schema, keypath, allow_default, allow_dynamic: bool):
    """Validates a value schema.

    A value schema has the following form:

        VALUE_SCHEMA = {
            "type": ("string" | "integer" | "float" | "boolean" | "date" | "datetime"),
            ["nullable": (True | False)]
        }

    """
    _check_keys(
        value_schema.keys(),
        required={"type"},
        optional={"nullable"},
        keypath=keypath,
        allow_default=allow_default,
    )

    valid_types = {"string", "integer", "float", "boolean", "date", "datetime"}
    if value_schema["type"] not in valid_types:
        raise _exceptions.InvalidSchemaError(
            f"Invalid type: {value_schema['type']}.", keypath + ("type",)
        )


# implementation =======================================================================


def validate_schema(
    schema: _types.Schema | _types.DynamicSchema,
    keypath: _types.KeyPath = tuple(),
    allow_default: bool = False,
    allow_dynamic: bool = True,
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

    try:
        schema = dict(schema)
    except Exception:
        raise _exceptions.InvalidSchemaError("Schema must be a mapping.", keypath)

    if "type" not in schema:
        raise _exceptions.InvalidSchemaError(
            "Required key missing.", keypath + ("type",)
        )

    args = (schema, keypath, allow_default, allow_dynamic)

    if schema["type"] == "any":
        _validate_any_schema(*args)
    elif schema["type"] == "dict":
        _validate_dict_schema(*args)
    elif schema["type"] == "list":
        _validate_list_schema(*args)
    else:
        _validate_value_schema(*args)
