from smartconfig import validate_schema, exceptions
from pytest import raises


# all schemata =========================================================================


def test_raises_if_type_field_is_omitted():
    schema = {}

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

    with raises(exceptions.InvalidSchemaError):
        validate_schema(schema)


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
