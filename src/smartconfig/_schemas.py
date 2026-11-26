"""Provides validate_schema(), which checks that a schema is valid.

Note that this module does *not* check that a configuration matches its schema. That is
done by resolve().

"""

from collections.abc import Callable, Mapping, Set
from . import exceptions as _exceptions, types as _types
from ._utils import jinja_reserved_name_problem

# the types of value schemas when no converters are given: the default converters
_DEFAULT_VALUE_TYPES = frozenset(
    {"string", "integer", "float", "boolean", "date", "datetime"}
)

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
    value_types: Set[str],
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
    value_types: Set[str],
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

    # required_keys and optional_keys map key names to schemas. Check that before
    # reading them below, where a list would raise a bare AttributeError. A key
    # must be a string, since configuration keys are, or no key could match it
    for section in ("required_keys", "optional_keys"):
        keys_schemas = dict_schema.get(section, {})
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
    for key in dict_schema.get("optional_keys", {}):
        if key in dict_schema.get("required_keys", {}):
            raise _exceptions.InvalidSchemaError(
                "Key is both required and optional.",
                keypath + ("optional_keys", key),
            )

    # recursively check the children corresponding to the required keys
    for key, key_schema in dict_schema.get("required_keys", {}).items():
        validate_schema(
            key_schema,
            keypath + ("required_keys", key),
            allow_dynamic=allow_dynamic,
            value_types=value_types,
        )

    # recursively check the children corresponding to the optional keys, allowing
    # defaults to be specified
    for key, key_schema in dict_schema.get("optional_keys", {}).items():
        validate_schema(
            key_schema,
            keypath + ("optional_keys", key),
            allow_default=True,
            allow_dynamic=allow_dynamic,
            value_types=value_types,
        )

    # if the schema provides an "extra_keys_schema", check that it is a valid schema
    if "extra_keys_schema" in dict_schema:
        validate_schema(
            dict_schema["extra_keys_schema"],
            keypath + ("extra_keys_schema",),
            allow_dynamic=allow_dynamic,
            value_types=value_types,
        )


def _validate_list_schema(
    list_schema, keypath, allow_default, allow_dynamic: bool, value_types: Set[str]
):
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

    # recursively check the children. The list itself may have a default (under
    # optional_keys), but its elements may not: an element can't be missing, so a
    # default there would be silently ignored
    validate_schema(
        list_schema["element_schema"],
        keypath + ("element_schema",),
        allow_default=False,
        allow_dynamic=allow_dynamic,
        value_types=value_types,
    )


def _validate_value_schema(
    value_schema, keypath, allow_default, allow_dynamic: bool, value_types: Set[str]
):
    """Validates a value schema.

    A value schema has the following form:

        VALUE_SCHEMA = {
            "type": <a name in value_types>,
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

    # list the valid types, since a type can be invalid because no converter for
    # it was given, not only because it is misspelled
    if value_schema["type"] not in value_types:
        structural = ["any", "dict", "list", "template"]
        others = sorted(set(value_types) - set(structural))
        valid = ", ".join(structural + others)
        raise _exceptions.InvalidSchemaError(
            f"Invalid type: {value_schema['type']}. Valid types: {valid}. A type other "
            "than any, dict, list or template must be the name of a converter.",
            keypath + ("type",),
        )


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


def _validate_template_schema(
    template_schema: _types.Schema,
    keypath: _types.KeyPath,
    allow_default: bool,
    allow_dynamic: bool,
    value_types: Set[str],
):
    """Validates a template schema.

    A template schema has the following form:

        <TEMPLATE_SCHEMA> = {
            "type": "template",
            "schema": <SCHEMA>,
            "parameters": [<NAME>, ...],
            ["nullable": (True | False)]
        }

    The inner schema is validated recursively; it may not have a default at its
    top level (the default of a template field belongs on the template schema).

    """
    _check_keys(
        template_schema.keys(),
        required={"type", "schema", "parameters"},
        optional={"nullable"},
        keypath=keypath,
        allow_default=allow_default,
    )

    _validate_names(template_schema["parameters"], keypath + ("parameters",))

    validate_schema(
        template_schema["schema"],
        keypath + ("schema",),
        allow_default=False,
        allow_dynamic=allow_dynamic,
        value_types=value_types,
    )

    # a template's value can't be a template field (templates don't nest), so an
    # inner schema that is itself a template schema can never be satisfied. The
    # error at resolve time would advise making the field a sibling of the
    # template, which isn't possible here, so the schema is rejected instead
    inner_schema = template_schema["schema"]
    if isinstance(inner_schema, Mapping) and inner_schema.get("type") == "template":
        raise _exceptions.InvalidSchemaError(
            "The schema of a template can't itself be a template schema: templates "
            "don't nest. Use the inner template schema in place of the outer one.",
            keypath + ("schema",),
        )

    # A template's top-level keys can be referenced by name, like its parameters,
    # so a parameter named like a key that the inner schema declares would be
    # ambiguous. Catch it here, where it is visible from the schema alone.
    inner = template_schema["schema"]
    declared: set[str] = set()
    if isinstance(inner, Mapping) and inner["type"] == "dict":
        declared = {*inner.get("required_keys", {}), *inner.get("optional_keys", {})}
    for i, name in enumerate(template_schema["parameters"]):
        if name in declared:
            raise _exceptions.InvalidSchemaError(
                f'The parameter "{name}" has the same name as a key of the '
                "template's schema. A template's keys can be referenced by name, "
                "like its parameters, so the name would be ambiguous. Rename the "
                "parameter or the key.",
                keypath + ("parameters", str(i)),
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

    args = (schema, keypath, allow_default, allow_dynamic, value_types)

    if schema["type"] == "any":
        _validate_any_schema(*args)
    elif schema["type"] == "dict":
        _validate_dict_schema(*args)
    elif schema["type"] == "list":
        _validate_list_schema(*args)
    elif schema["type"] == "template":
        _validate_template_schema(*args)
    else:
        _validate_value_schema(*args)
