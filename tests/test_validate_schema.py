from typing import Callable

from smartconfig import DEFAULT_CONVERTERS, exceptions, resolve, validate_schema
from smartconfig.types import Schema
import pytest
from pytest import raises


# all schemata =========================================================================


def test_raises_if_type_field_is_omitted():
    schema: Schema = {}

    with raises(exceptions.InvalidSchemaError):
        validate_schema(schema)


def test_raises_if_the_type_is_not_a_string():
    # the type is a list of names, not a name
    schema = {"type": ["dict"]}

    with raises(exceptions.InvalidSchemaError) as exc:
        validate_schema(schema)

    assert exc.value.keypath == ("type",)


# dict schemata ========================================================================


def test_dict_schema_smoke():
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
        },
        "optional_keys": {
            "bar": {"type": "integer", "default": 42},
        },
    }

    validate_schema(schema)


@pytest.mark.parametrize(
    "section, value, keypath",
    [
        # a list of key names, not a mapping from names to schemas
        ("required_keys", ["a"], ("required_keys",)),
        ("optional_keys", ["a"], ("optional_keys",)),
        # a mapping, but the key 1 is not a string, so no configuration key matches it
        ("required_keys", {1: {"type": "integer"}}, ("required_keys", "1")),
    ],
)
def test_raises_if_a_keys_section_is_not_a_mapping_from_strings(
    section, value, keypath
):
    schema = {"type": "dict", section: value}

    with raises(exceptions.InvalidSchemaError) as exc:
        validate_schema(schema)

    assert exc.value.keypath == keypath


def test_raises_if_unknown_key_is_provided_for_dict_schema():
    schema = {"type": "dict", "foo": 42}

    with raises(exceptions.InvalidSchemaError) as excinfo:
        validate_schema(schema)

    assert "Unexpected key." in str(excinfo.value)


def test_raises_if_unknown_key_is_provided_for_required_key_spec():
    schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "integer", "testing": 42}},
    }

    with raises(exceptions.InvalidSchemaError):
        validate_schema(schema)


def test_raises_if_unknown_key_is_provided_for_optional_key_spec():
    schema = {
        "type": "dict",
        "optional_keys": {"foo": {"type": "integer", "testing": 42}},
    }

    with raises(exceptions.InvalidSchemaError):
        validate_schema(schema)


def test_raises_if_a_key_is_both_required_and_optional():
    # "a" is listed twice, so it's unclear whether it may be missing
    schema = {
        "type": "dict",
        "required_keys": {"a": {"type": "integer"}},
        "optional_keys": {"a": {"type": "integer", "default": 0}},
    }

    with raises(exceptions.InvalidSchemaError) as exc:
        validate_schema(schema)

    assert exc.value.keypath == ("optional_keys", "a")


def test_raises_if_extra_keys_schema_is_not_a_valid_schema():
    schema = {"type": "dict", "extra_keys_schema": 42}

    with raises(exceptions.InvalidSchemaError):
        validate_schema(schema)


def test_raises_if_default_is_provided_for_a_required_key():
    schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "integer", "default": 42}},
    }

    with raises(exceptions.InvalidSchemaError) as excinfo:
        validate_schema(schema)

    assert excinfo.value.keypath == ("required_keys", "foo", "default")


def test_raises_if_there_are_missing_keys():
    schema = {"type": "list"}

    with raises(exceptions.InvalidSchemaError) as exc:
        validate_schema(schema)

    assert "Missing key." in str(exc.value)


def test_does_not_raise_if_default_value_does_not_match_type():
    # this is the job of resolve, not validate_schema
    schema = {
        "type": "dict",
        "optional_keys": {"foo": {"type": "integer", "default": "not an integer"}},
    }

    validate_schema(schema)


# value schemata =======================================================================


def test_raises_if_the_type_is_unexpected():
    schema = {"type": "int", "nullable": True}

    with raises(exceptions.InvalidSchemaError) as exc:
        validate_schema(schema)

    assert "Invalid type: int." in str(exc.value)


# list schemata ========================================================================


def test_list_schema_smoke():
    schema = {"type": "list", "element_schema": {"type": "integer"}, "nullable": True}

    validate_schema(schema)


def test_raises_if_unknown_key_is_provided_for_list_schema():
    schema = {"type": "list", "woo": "hoo"}

    with raises(exceptions.InvalidSchemaError):
        validate_schema(schema)


# nullable =============================================================================


def test_allow_defaults_to_be_null():
    schema = {
        "type": "dict",
        "optional_keys": {"foo": {"default": None, "type": "any"}},
    }

    validate_schema(schema)


def test_raises_if_nullable_is_not_a_boolean():
    # "no" is a string, not False
    schema = {"type": "integer", "nullable": "no"}

    with raises(exceptions.InvalidSchemaError) as exc:
        validate_schema(schema)

    assert exc.value.keypath == ("nullable",)


# any types ============================================================================


def test_any_type_smoke():
    schema = {"type": "any", "nullable": True}
    validate_schema(schema)


def test_raises_if_unknown_key_provided_with_any_type():
    schema = {"type": "any", "nullable": True, "foo": "bar"}

    with raises(exceptions.InvalidSchemaError):
        validate_schema(schema)


# template types =======================================================================


def test_template_type_smoke():
    schema = {
        "type": "template",
        "schema": {"type": "string"},
        "parameters": ["name"],
    }
    validate_schema(schema)


def test_template_type_with_nullable():
    schema = {
        "type": "template",
        "schema": {"type": "string"},
        "parameters": ["publication"],
        "nullable": True,
    }
    validate_schema(schema)


def test_template_type_with_default_where_defaults_are_allowed():
    schema = {
        "type": "dict",
        "optional_keys": {
            "foo": {
                "type": "template",
                "schema": {"type": "string"},
                "parameters": [],
                "default": "hello ${ name }",
            }
        },
    }
    validate_schema(schema)


def test_template_type_with_default_where_defaults_are_not_allowed_raises():
    schema = {
        "type": "template",
        "schema": {"type": "string"},
        "parameters": [],
        "default": "hello",
    }

    with raises(exceptions.InvalidSchemaError) as exc:
        validate_schema(schema)

    assert exc.value.keypath == ("default",)
    assert "Unexpected key." in str(exc.value)


def test_template_type_raises_if_schema_is_missing():
    schema = {"type": "template", "parameters": []}

    with raises(exceptions.InvalidSchemaError) as exc:
        validate_schema(schema)

    assert exc.value.keypath == ("schema",)
    assert "Missing key." in str(exc.value)


def test_template_type_raises_if_variables_is_missing():
    schema = {"type": "template", "schema": {"type": "string"}}

    with raises(exceptions.InvalidSchemaError) as exc:
        validate_schema(schema)

    assert exc.value.keypath == ("parameters",)
    assert "Missing key." in str(exc.value)


def test_template_type_raises_on_unknown_key():
    schema = {
        "type": "template",
        "schema": {"type": "string"},
        "parameters": [],
        "foo": 1,
    }

    with raises(exceptions.InvalidSchemaError) as exc:
        validate_schema(schema)

    assert exc.value.keypath == ("foo",)
    assert "Unexpected key." in str(exc.value)


def test_template_type_raises_if_variables_is_not_a_list():
    schema = {
        "type": "template",
        "schema": {"type": "string"},
        "parameters": "name",
    }

    with raises(exceptions.InvalidSchemaError) as exc:
        validate_schema(schema)

    assert exc.value.keypath == ("parameters",)


def test_template_type_raises_if_a_variable_is_not_a_string():
    schema = {
        "type": "template",
        "schema": {"type": "string"},
        "parameters": [1],
    }

    with raises(exceptions.InvalidSchemaError) as exc:
        validate_schema(schema)

    assert exc.value.keypath == ("parameters", "0")


def test_template_type_raises_if_a_variable_is_not_an_identifier():
    schema = {
        "type": "template",
        "schema": {"type": "string"},
        "parameters": ["ok", "not ok"],
    }

    with raises(exceptions.InvalidSchemaError) as exc:
        validate_schema(schema)

    assert exc.value.keypath == ("parameters", "1")


@pytest.mark.parametrize("section", ["required_keys", "optional_keys"])
def test_template_type_raises_if_a_key_of_its_schema_is_named_like_a_parameter(
    section,
):
    # the inner schema declares a key "name", and "name" is also a parameter. A
    # template's top-level keys can be referenced by name, like its parameters, so
    # the two would be ambiguous
    key_schema = {"type": "string"}
    if section == "optional_keys":
        key_schema["default"] = "x"
    schema = {
        "type": "template",
        "schema": {"type": "dict", section: {"name": key_schema}},
        "parameters": ["name"],
    }

    with raises(exceptions.InvalidSchemaError) as exc:
        validate_schema(schema)

    assert exc.value.keypath == ("parameters", "0")


def test_template_type_raises_if_globals_is_given():
    # names other than the variables are not declared
    schema = {
        "type": "template",
        "schema": {"type": "string"},
        "parameters": [],
        "globals": ["vars"],
    }

    with raises(exceptions.InvalidSchemaError):
        validate_schema(schema)


def test_template_type_validates_inner_schema_recursively():
    schema = {
        "type": "dict",
        "required_keys": {
            "x": {
                "type": "template",
                "schema": {
                    "type": "dict",
                    "required_keys": {"title": {"type": "int"}},
                },
                "parameters": [],
            }
        },
    }

    with raises(exceptions.InvalidSchemaError) as exc:
        validate_schema(schema)

    assert exc.value.keypath == (
        "required_keys",
        "x",
        "schema",
        "required_keys",
        "title",
        "type",
    )


def test_template_type_raises_if_its_schema_is_a_template():
    # the template's inner schema is itself a template schema, so its value would
    # be a template inside a template, which can never be resolved
    schema = {
        "type": "template",
        "schema": {"type": "template", "schema": {"type": "string"}, "parameters": []},
        "parameters": [],
    }

    with raises(exceptions.InvalidSchemaError) as exc:
        validate_schema(schema)

    assert exc.value.keypath == ("schema",)


def test_template_type_inner_schema_may_be_dynamic():
    def inner(_):
        return {"type": "string"}

    schema = {"type": "template", "schema": inner, "parameters": []}
    validate_schema(schema)


def test_template_type_inner_schema_may_not_be_dynamic_if_disallowed():
    def inner(_):
        return {"type": "string"}

    schema = {"type": "template", "schema": inner, "parameters": []}

    with raises(exceptions.InvalidSchemaError) as exc:
        validate_schema(schema, allow_dynamic=False)

    assert exc.value.keypath == ("schema",)


def test_template_type_rejects_default_at_top_of_inner_schema():
    schema = {
        "type": "template",
        "schema": {"type": "string", "default": "hi"},
        "parameters": [],
    }

    with raises(exceptions.InvalidSchemaError) as exc:
        validate_schema(schema)

    assert exc.value.keypath == ("schema", "default")


# dynamic schemata ====================================================================


def test_allows_functions_as_schemata():
    def dynamic_schema():
        return {"type": "integer"}

    schema = {
        "type": "dict",
        "required_keys": {
            "foo": dynamic_schema,
        },
    }

    validate_schema(schema)


def test_raises_if_function_is_provided_and_allow_dynamic_is_false():
    def dynamic_schema():
        return {"type": "integer"}

    schema = {
        "type": "dict",
        "required_keys": {
            "foo": dynamic_schema,
        },
    }

    with raises(exceptions.InvalidSchemaError):
        validate_schema(schema, allow_dynamic=False)


# resolve() validates schemas ==========================================================


def test_resolve_raises_if_the_schema_is_invalid():
    # a list schema needs an element_schema
    schema = {"type": "list"}

    with raises(exceptions.InvalidSchemaError):
        resolve([1], schema)


def test_a_type_with_a_custom_converter_is_valid_wherever_resolve_validates():
    # "hex" isn't a built-in type, but there is a converter for it. It's used in a
    # static schema (x), a dynamic schema (y), and the dynamic schema of a missing
    # optional key with a default (z): each place that resolve() validates a schema
    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "hex"},
            "y": lambda cfg, keypath: {"type": "hex"},
        },
        "optional_keys": {
            "z": lambda cfg, keypath: {"type": "hex", "default": "10"},
        },
    }

    def hex_converter(s: str) -> int:
        return int(s, 16)

    converters: dict[str, Callable] = {**DEFAULT_CONVERTERS, "hex": hex_converter}

    result = resolve({"x": "ff", "y": "a"}, schema, converters=converters)

    assert result == {"x": 255, "y": 10, "z": 16}
