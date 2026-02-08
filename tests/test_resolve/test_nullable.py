"""Tests for nullable fields."""

from smartconfig import resolve, exceptions
from smartconfig.types import (
    ConfigurationDict,
    Schema,
)

from pytest import raises


def test_dictionary_can_be_nullable():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "dict", "nullable": True}},
    }

    cfg: ConfigurationDict = {"foo": None}

    # when
    result = resolve(cfg, schema)

    # then
    assert result["foo"] is None


def test_list_can_be_nullable():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {
                "type": "list",
                "element_schema": {"type": "any"},
                "nullable": True,
            }
        },
    }

    cfg: ConfigurationDict = {"foo": None}

    # when
    result = resolve(cfg, schema)

    # then
    assert result["foo"] is None


def test_leaf_can_be_nullable():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "integer", "nullable": True}},
    }

    cfg: ConfigurationDict = {"foo": None}

    # when
    result = resolve(cfg, schema)

    # then
    assert result["foo"] is None


def test_error_is_raised_if_None_is_provided_but_value_is_not_nullable():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "integer"}},
    }

    cfg: ConfigurationDict = {"foo": None}

    # when
    with raises(exceptions.ResolutionError):
        resolve(cfg, schema)


def test_any_can_be_None_without_being_nullable():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "any"}},
    }

    cfg: ConfigurationDict = {"foo": None}

    # when
    result = resolve(cfg, schema)

    # then
    assert result["foo"] is None
