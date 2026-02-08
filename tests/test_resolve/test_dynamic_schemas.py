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
