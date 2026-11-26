"""Tests for dynamic schemas."""

from smartconfig import resolve, exceptions
from smartconfig.types import (
    Configuration,
    ConfigurationDict,
    ConfigurationList,
    DynamicSchema,
    KeyPath,
    Schema,
)

from pytest import raises


def test_resolve_with_dynamic_schema_in_list():
    # given
    def element_schema(element, _):
        """When called on a list element, returns a schema for that element."""
        return {"type": "integer"}

    schema: Schema = {"type": "list", "element_schema": element_schema}

    cfg: ConfigurationList = ["1", "2", "3"]

    # when
    result = resolve(cfg, schema)

    # then
    assert result == [1, 2, 3]


def test_resolve_with_dynamic_schema_in_list_of_dicts():
    # given
    def element_schema(element, _):
        if "foo" in element:
            return {
                "type": "dict",
                "required_keys": {"foo": {"type": "integer"}},
            }

        if "bar" in element:
            return {
                "type": "dict",
                "required_keys": {"bar": {"type": "string"}},
            }

    schema: Schema = {"type": "list", "element_schema": element_schema}

    cfg: ConfigurationList = [{"foo": "10"}, {"bar": "hello"}]

    # when
    result = resolve(cfg, schema)

    # then
    assert result == [{"foo": 10}, {"bar": "hello"}]


def test_resolve_with_dynamic_schema_in_extra_keys():
    # given
    def extra_keys_schema(value, _):
        if value.isdigit():
            return {"type": "integer"}
        else:
            return {"type": "string"}

    schema: Schema = {
        "type": "dict",
        "extra_keys_schema": extra_keys_schema,
    }

    cfg: ConfigurationDict = {
        "num_one": "1",
        "num_two": "2",
        "str_hello": "world",
    }

    # when
    result = resolve(cfg, schema)

    # then
    assert result == {
        "num_one": 1,
        "num_two": 2,
        "str_hello": "world",
    }


def test_resolve_with_dynamic_schema_invalid_return():
    # given
    def element_schema(element, _):
        return {"type": "unknown_type"}

    schema: Schema = {"type": "list", "element_schema": element_schema}

    # when
    with raises(exceptions.InvalidSchemaError):
        resolve(["1", "2", "3"], schema)


def test_resolve_with_dynamic_schema_at_root():
    # given
    def main_schema(cfg, _):
        return {
            "type": "dict",
            "required_keys": {
                "value": {"type": "integer"},
            },
        }

    cfg: ConfigurationDict = {"value": "42"}

    # when
    result = resolve(cfg, main_schema)

    # then
    assert result == {"value": 42}


def test_resolve_with_dynamic_schema_based_on_keypath():  # given
    # if the last part of the keypath starts with "num", we want an integer schema
    # otherwise, a string schema
    def extra_keys_schema(_: Configuration, keypath: KeyPath) -> Schema:
        last_part = keypath[-1]
        if last_part.startswith("num"):
            return {"type": "integer"}
        else:
            return {"type": "string"}

    schema: Schema = {
        "type": "dict",
        "extra_keys_schema": extra_keys_schema,
    }

    cfg: ConfigurationDict = {
        "num_one": "1",
        "num_two": "2",
        "str_hello": "world",
    }

    # when
    result = resolve(cfg, schema)

    # then
    assert result == {
        "num_one": 1,
        "num_two": 2,
        "str_hello": "world",
    }


def test_resolve_with_dynamic_schema_in_optional_keys():
    # given
    def value_schema(value, _):
        return {"type": "integer"}

    schema: Schema = {
        "type": "dict",
        "optional_keys": {
            "foo": value_schema,
        },
    }

    cfg: ConfigurationDict = {"foo": "42"}

    # when
    result = resolve(cfg, schema)

    # then
    assert result == {"foo": 42}


def test_resolve_with_dynamic_schema_in_optional_keys_with_default():
    # given
    def value_schema(value, _):
        return {"type": "integer", "default": 99}

    schema: Schema = {
        "type": "dict",
        "optional_keys": {
            "foo": value_schema,
        },
    }

    cfg: ConfigurationDict = {}

    # when
    result = resolve(cfg, schema)

    # then
    assert result == {"foo": 99}


def test_resolve_with_dynamic_schemas_nested():
    # given
    def address_schema(cfg: Configuration, _: KeyPath) -> Schema:
        return {
            "type": "dict",
            "required_keys": {
                "city": {"type": "string"},
                "zip_code": {"type": "integer"},
            },
        }

    def person_schema(cfg: Configuration, _: KeyPath) -> Schema:
        return {
            "type": "dict",
            "required_keys": {
                "name": {"type": "string"},
                "address": address_schema,
            },
        }

    schema: DynamicSchema = person_schema

    cfg: ConfigurationDict = {
        "name": "Diana",
        "address": {"city": "Los Angeles", "zip_code": "90001"},
    }

    # when
    result = resolve(cfg, schema)

    # then
    assert result == {
        "name": "Diana",
        "address": {"city": "Los Angeles", "zip_code": 90001},
    }


def test_raises_if_a_dynamic_schema_gives_a_required_key_a_default():
    # given — a default makes no sense for a required key, which is never missing;
    # a static schema like this is invalid, so a dynamic one should be too
    schema: Schema = {
        "type": "dict",
        "required_keys": {"a": lambda cfg, keypath: {"type": "integer", "default": 5}},
    }

    cfg: ConfigurationDict = {"a": 1}

    # when
    with raises(exceptions.InvalidSchemaError) as exc:
        resolve(cfg, schema)

    # then
    assert "default" in str(exc.value)


# errors in a dynamic schema ===========================================================


def test_invalid_schema_from_a_dynamic_schema_on_a_list_element_has_its_keypath():
    # given — a list element's schema is called in make_node, not by its parent
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "a": {
                "type": "list",
                "element_schema": lambda cfg, keypath: {"type": "nonsense"},
            }
        },
    }

    cfg: ConfigurationDict = {"a": [1]}

    # when
    with raises(exceptions.InvalidSchemaError) as exc:
        resolve(cfg, schema)

    # then
    assert exc.value.keypath == ("a", "0", "type")


def test_raises_if_a_dynamic_schema_at_the_root_returns_a_dynamic_schema():
    # given
    def schema(cfg, keypath):
        return lambda cfg, keypath: {"type": "any"}

    # when
    with raises(exceptions.InvalidSchemaError) as exc:
        resolve(1, schema)

    # then
    assert "another dynamic schema" in str(exc.value)
    assert exc.value.keypath == ()


def test_raises_if_a_dynamic_schema_for_a_required_key_returns_a_dynamic_schema():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "a": lambda cfg, keypath: lambda cfg, keypath: {"type": "any"}
        },
    }

    cfg: ConfigurationDict = {"a": 1}

    # when
    with raises(exceptions.InvalidSchemaError) as exc:
        resolve(cfg, schema)

    # then
    assert "another dynamic schema" in str(exc.value)
    assert exc.value.keypath == ("a",)


def test_raises_if_a_dynamic_schema_for_a_missing_optional_key_returns_a_dynamic_schema():
    # given
    schema: Schema = {
        "type": "dict",
        "optional_keys": {
            "a": lambda cfg, keypath: (
                lambda cfg, keypath: {
                    "type": "any",
                    "default": 3,
                }
            )
        },
    }

    cfg: ConfigurationDict = {}

    # when
    with raises(exceptions.InvalidSchemaError) as exc:
        resolve(cfg, schema)

    # then
    assert "another dynamic schema" in str(exc.value)
    assert exc.value.keypath == ("a",)


def _raises_value_error(cfg, keypath):
    raise ValueError("boom")


def test_exception_from_a_dynamic_schema_at_the_root_is_wrapped():
    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(1, _raises_value_error)

    # then
    assert "ValueError: boom" in str(exc.value)
    assert exc.value.keypath == ()
    assert isinstance(exc.value.__cause__, ValueError)


def test_exception_from_a_dynamic_schema_for_a_required_key_is_wrapped():
    # given
    schema: Schema = {"type": "dict", "required_keys": {"a": _raises_value_error}}

    cfg: ConfigurationDict = {"a": 1}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema)

    # then
    assert "ValueError: boom" in str(exc.value)
    assert exc.value.keypath == ("a",)
    assert isinstance(exc.value.__cause__, ValueError)


def test_exception_from_a_dynamic_schema_for_a_missing_optional_key_is_wrapped():
    # given
    schema: Schema = {"type": "dict", "optional_keys": {"a": _raises_value_error}}

    cfg: ConfigurationDict = {}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema)

    # then
    assert "ValueError: boom" in str(exc.value)
    assert exc.value.keypath == ("a",)
    assert isinstance(exc.value.__cause__, ValueError)


def test_assertion_error_from_a_dynamic_schema_is_not_wrapped():
    # given — an AssertionError is a bug in the code, so it is not wrapped, as for
    # one raised by a function
    def schema(cfg, keypath):
        raise AssertionError("bug")

    # when / then
    with raises(AssertionError):
        resolve(1, schema)
