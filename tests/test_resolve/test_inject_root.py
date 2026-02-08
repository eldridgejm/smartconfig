"""Tests for the inject_root_as option."""

from smartconfig import resolve
from smartconfig.types import (
    ConfigurationDict,
    ConfigurationList,
    FunctionArgs,
    Schema,
)


def test_inject_root_with_top_level_list():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {"type": "integer"},
    }

    cfg: ConfigurationList = [4, 1, "${ root.0 + 1 }"]

    # when
    result = resolve(cfg, schema, inject_root_as="root")

    # then
    assert result == [4, 1, 5]


def test_inject_root_with_top_level_dict():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {"foo": 42, "bar": "${ myroot.keys() | length }"}

    # when
    result = resolve(cfg, schema, inject_root_as="myroot")

    # then
    assert result["bar"] == 2


def test_inject_root_with_dictionary_returned_by_function_node():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {
                "type": "dict",
                "required_keys": {
                    "foo": {"type": "integer"},
                    "bar": {"type": "integer"},
                },
            },
            "baz": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {
        "foo": 42,
        "bar": {"__make_dict__": {}},
        "baz": "${ myroot.bar.foo }",
    }

    def make_dict(_: FunctionArgs) -> ConfigurationDict:
        return {"foo": 10, "bar": 20}

    # when
    result = resolve(
        cfg, schema, functions={"make_dict": make_dict}, inject_root_as="myroot"
    )

    # then
    assert result == {"foo": 42, "bar": {"foo": 10, "bar": 20}, "baz": 10}


def test_inject_root_with_function_at_root_level_returning_a_list():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {"type": "integer"},
    }

    cfg: ConfigurationDict = {"__make_list__": {}}

    def make_list(_):
        return [1, 2, 3, "${ myroot.1 }"]

    # when
    result = resolve(
        cfg, schema, functions={"make_list": make_list}, inject_root_as="myroot"
    )

    # then
    assert result == [1, 2, 3, 2]
