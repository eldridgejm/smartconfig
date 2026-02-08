"""Tests for the "any" schema type."""

import datetime

from smartconfig import resolve
from smartconfig.types import (
    ConfigurationDict,
    Schema,
)


def test_all_types_preserved_when_any_is_used():
    # given
    schema: Schema = {
        "type": "any",
    }

    cfg: ConfigurationDict = {
        "foo": "testing",
        "bar": {"x": 1, "y": 2},
        "baz": [1, 2, 3],
    }

    # when
    result = resolve(cfg, schema)

    # then
    assert result == cfg


def test_interpolation_occurs_when_any_is_used():
    # given
    schema: Schema = {
        "type": "any",
    }

    cfg: ConfigurationDict = {"foo": "testing", "bar": "${foo} this"}

    # when
    result = resolve(cfg, schema)

    # then
    assert result["bar"] == "testing this"


def test_converts_integers_to_strings_when_schema_calls_for_it():
    # given
    schema: Schema = {"type": "dict", "required_keys": {"foo": {"type": "string"}}}

    cfg: ConfigurationDict = {"foo": 42}

    # when
    result = resolve(cfg, schema)

    # then
    assert result["foo"] == "42"


def test_converts_strings_to_integers_when_schema_calls_for_it():
    # given
    schema: Schema = {"type": "dict", "required_keys": {"foo": {"type": "integer"}}}

    cfg: ConfigurationDict = {"foo": "42"}

    # when
    result = resolve(cfg, schema)

    # then
    assert result["foo"] == 42


def test_config_contains_datetimes_objects_type_is_left_alone():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "datetime"}},
    }

    cfg: ConfigurationDict = {"foo": datetime.datetime(2020, 1, 1)}

    # when
    result = resolve(cfg, schema)

    # then
    assert result["foo"] == datetime.datetime(2020, 1, 1)
