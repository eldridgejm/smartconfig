"""Tests for global variable injection."""

from smartconfig import resolve, exceptions
from smartconfig.types import (
    ConfigurationDict,
    Schema,
)

from pytest import raises


def test_global_variables_are_injected():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {"foo": "${ alpha }", "bar": "${ beta }"}

    # when
    result = resolve(cfg, schema, global_variables={"alpha": 10, "beta": 20})

    # then
    assert result == {"foo": 10, "bar": 20}


def test_global_variables_are_given_less_priority_when_names_clash():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {"foo": "${ foo }", "bar": "${ bar }"}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, global_variables={"foo": 10, "bar": 20})

    assert "Circular reference" in str(exc.value)
