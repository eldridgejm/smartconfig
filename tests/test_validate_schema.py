from smartconfig import validate_schema, exceptions
from smartconfig.types import Schema
from pytest import raises


# all schemata =========================================================================


def test_raises_if_type_field_is_omitted():
    schema: Schema = {}

    with raises(exceptions.InvalidSchemaError):
        validate_schema(schema)


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
    schema = {"type": "template", "schema": {"type": "string"}, "variables": ["name"]}
    validate_schema(schema)


def test_template_type_with_empty_variables():
    schema = {"type": "template", "schema": {"type": "string"}, "variables": []}
    validate_schema(schema)


def test_template_type_with_nullable():
    schema = {
        "type": "template",
        "schema": {"type": "string"},
        "variables": ["publication"],
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
                "variables": [],
                "default": "hello ${ name }",
            }
        },
    }
    validate_schema(schema)


def test_template_type_with_default_where_defaults_are_not_allowed_raises():
    schema = {
        "type": "template",
        "schema": {"type": "string"},
        "variables": [],
        "default": "hello",
    }

    with raises(exceptions.InvalidSchemaError) as exc:
        validate_schema(schema)

    assert exc.value.keypath == ("default",)
    assert "Unexpected key." in str(exc.value)


def test_template_type_raises_if_schema_is_missing():
    schema = {"type": "template", "variables": []}

    with raises(exceptions.InvalidSchemaError) as exc:
        validate_schema(schema)

    assert exc.value.keypath == ("schema",)
    assert "Missing key." in str(exc.value)


def test_template_type_raises_if_variables_is_missing():
    schema = {"type": "template", "schema": {"type": "string"}}

    with raises(exceptions.InvalidSchemaError) as exc:
        validate_schema(schema)

    assert exc.value.keypath == ("variables",)
    assert "Missing key." in str(exc.value)


def test_template_type_raises_on_unknown_key():
    schema = {
        "type": "template",
        "schema": {"type": "string"},
        "variables": [],
        "foo": 1,
    }

    with raises(exceptions.InvalidSchemaError) as exc:
        validate_schema(schema)

    assert exc.value.keypath == ("foo",)
    assert "Unexpected key." in str(exc.value)


def test_template_type_raises_if_variables_is_not_a_list():
    schema = {"type": "template", "schema": {"type": "string"}, "variables": "name"}

    with raises(exceptions.InvalidSchemaError) as exc:
        validate_schema(schema)

    assert exc.value.keypath == ("variables",)


def test_template_type_raises_if_a_variable_is_not_a_string():
    schema = {"type": "template", "schema": {"type": "string"}, "variables": [1]}

    with raises(exceptions.InvalidSchemaError) as exc:
        validate_schema(schema)

    assert exc.value.keypath == ("variables", "0")


def test_template_type_raises_if_a_variable_is_not_an_identifier():
    schema = {
        "type": "template",
        "schema": {"type": "string"},
        "variables": ["ok", "not ok"],
    }

    with raises(exceptions.InvalidSchemaError) as exc:
        validate_schema(schema)

    assert exc.value.keypath == ("variables", "1")


def test_template_type_raises_if_globals_is_given():
    # names other than the variables are not declared
    schema = {
        "type": "template",
        "schema": {"type": "string"},
        "variables": [],
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
                "variables": [],
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


def test_template_type_inner_schema_may_be_dynamic():
    def inner(_):
        return {"type": "string"}

    schema = {"type": "template", "schema": inner, "variables": []}
    validate_schema(schema)


def test_template_type_inner_schema_may_not_be_dynamic_if_disallowed():
    def inner(_):
        return {"type": "string"}

    schema = {"type": "template", "schema": inner, "variables": []}

    with raises(exceptions.InvalidSchemaError) as exc:
        validate_schema(schema, allow_dynamic=False)

    assert exc.value.keypath == ("schema",)


def test_template_type_inner_schema_may_contain_template_fields():
    schema = {
        "type": "template",
        "schema": {
            "type": "dict",
            "required_keys": {
                "inner": {
                    "type": "template",
                    "schema": {"type": "string"},
                    "variables": ["y"],
                },
            },
        },
        "variables": ["x"],
    }
    validate_schema(schema)


def test_template_type_rejects_default_at_top_of_inner_schema():
    schema = {
        "type": "template",
        "schema": {"type": "string", "default": "hi"},
        "variables": [],
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
