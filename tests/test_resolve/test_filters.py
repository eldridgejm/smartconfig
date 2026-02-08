"""Tests for custom Jinja2 filters."""

from smartconfig import resolve
from smartconfig.types import (
    ConfigurationDict,
    Schema,
)


def test_filter_is_provided_at_interpolation_time():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {"foo": "this", "bar": "${ foo | myfilter }"}

    def myfilter(value):
        return value.upper()

    # when
    result = resolve(cfg, schema, filters={"myfilter": myfilter})

    # then
    assert result["bar"] == "THIS"


def test_filter_overrides_builtin_jinja_filters():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {"foo": "this", "bar": "${ foo | length }"}

    def length(_):
        return 42

    # when
    result = resolve(cfg, schema, filters={"length": length})

    # then
    assert result["bar"] == "42"


def test_filter_with_arguments():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {"foo": "this", "bar": "${ foo | myfilter('that') }"}

    def myfilter(value, arg1):
        return value + arg1

    # when
    result = resolve(cfg, schema, filters={"myfilter": myfilter})

    # then
    assert result["bar"] == "thisthat"
