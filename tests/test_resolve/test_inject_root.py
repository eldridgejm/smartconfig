"""Tests for the inject_root_as option."""

from pytest import raises

from smartconfig import resolve
from smartconfig.exceptions import ResolutionError
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


def test_inject_root_with_function_at_root_level_returning_a_string_has_no_keys():
    # given — the root call returns a plain string, so myroot.x is undefined
    schema: Schema = {"type": "string"}
    cfg: ConfigurationDict = {
        "__if__": {"condition": True, "then": "${ myroot.x }", "else": "no"}
    }

    # when
    with raises(ResolutionError) as exc:
        resolve(cfg, schema, inject_root_as="myroot")

    # then
    assert 'The configuration is a single value, so it has no key "x".' in str(
        exc.value
    )


def test_inject_root_as_a_name_reserved_by_jinja_raises():
    # given — in ${ self.x }, Jinja reads self as the template itself
    cfg: ConfigurationDict = {"x": 1, "y": "${ self.x }"}

    # when
    with raises(ValueError) as exc:
        resolve(cfg, {"type": "any"}, inject_root_as="self")

    # then
    assert str(exc.value) == (
        'Invalid inject_root_as: "self" is reserved by Jinja, which reads it as the '
        "template itself, so ${ self } can't refer to it. Use another name."
    )
