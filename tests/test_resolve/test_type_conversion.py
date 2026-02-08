"""Tests for type conversion."""

from smartconfig import resolve, exceptions
from smartconfig.types import (
    ConfigurationDict,
    ConfigurationList,
    Schema,
)

from pytest import raises


def test_leafs_are_converted_into_expected_types():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "integer"}},
    }

    cfg: ConfigurationDict = {"foo": "42"}

    # when
    result = resolve(cfg, schema)

    # then
    assert result["foo"] == 42


def test_converting_occurs_after_interpolation():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {"foo": "42", "bar": "${foo}"}

    # when
    result = resolve(cfg, schema)

    # then
    assert result["foo"] == 42
    assert result["bar"] == 42


def test_converting_of_extra_dictionary_keys():
    # given
    schema: Schema = {"type": "dict", "extra_keys_schema": {"type": "integer"}}

    cfg: ConfigurationDict = {"foo": "42", "bar": "10"}

    # when
    result = resolve(cfg, schema)

    # then
    assert result["foo"] == 42
    assert result["bar"] == 10


def test_converting_of_list_elements():
    # given
    schema: Schema = {"type": "list", "element_schema": {"type": "integer"}}

    cfg: ConfigurationList = ["10", "25"]

    # when
    result = resolve(cfg, schema)

    # then
    assert result == [10, 25]


def test_raises_if_no_converter_provided_for_type():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "integer"}},
    }

    cfg: ConfigurationDict = {"foo": "42"}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, converters={})

    assert "No converter provided" in str(exc.value)
