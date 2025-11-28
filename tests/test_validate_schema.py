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
