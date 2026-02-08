"""Tests for basic resolution."""

from smartconfig import resolve, exceptions
from smartconfig.types import (
    ConfigurationDict,
    ConfigurationList,
    Schema,
)

from pytest import raises


def test_raises_if_required_keys_are_missing():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "any"},
            "bar": {"type": "any"},
        },
    }

    cfg: ConfigurationDict = {"foo": 42}

    # when
    with raises(exceptions.ResolutionError) as excinfo:
        resolve(cfg, schema)

    assert excinfo.value.keypath == ("bar",)
    assert (
        str(excinfo.value)
        == 'Cannot resolve keypath "bar": Dictionary is missing required key "bar".'
    )


def test_raises_if_required_keys_are_missing_in_nested_dict():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {
                "type": "dict",
                "required_keys": {
                    "bar": {"type": "any"},
                },
            }
        },
    }

    cfg: ConfigurationDict = {"foo": {}}

    # when
    with raises(exceptions.ResolutionError) as excinfo:
        resolve(cfg, schema)

    assert excinfo.value.keypath == ("foo", "bar")
    assert (
        str(excinfo.value)
        == 'Cannot resolve keypath "foo.bar": Dictionary is missing required key "bar".'
    )


def test_raises_if_extra_keys_without_extra_keys_schema():
    # given
    schema: Schema = {"type": "dict", "required_keys": {}}

    cfg: ConfigurationDict = {"foo": 42}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema)

    assert (
        str(exc.value)
        == 'Cannot resolve keypath "foo": Dictionary contains unexpected extra key "foo".'
    )


def test_allows_extra_keys_with_extra_keys_schema():
    # given
    schema: Schema = {"type": "dict", "extra_keys_schema": {"type": "any"}}

    cfg: ConfigurationDict = {"foo": 42}

    # when
    result = resolve(cfg, schema)

    # then
    assert result["foo"] == 42


def test_fills_in_missing_value_with_default_if_provided():
    # given
    schema: Schema = {
        "type": "dict",
        "optional_keys": {"foo": {"default": 42, "type": "integer"}},
    }

    cfg: ConfigurationDict = {}

    # when
    result = resolve(cfg, schema)

    # then
    assert result["foo"] == 42


def test_allows_missing_keys_if_required_is_false():
    # given
    schema: Schema = {
        "type": "dict",
        "optional_keys": {
            "foo": {"type": "integer"},
            "bar": {
                "type": "integer",
            },
        },
    }

    cfg: ConfigurationDict = {"bar": 42}

    # when
    result = resolve(cfg, schema)

    # then
    assert result["bar"] == 42
    assert "foo" not in result


def test_list_of_dicts():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {
            "type": "dict",
            "required_keys": {"foo": {"type": "integer"}},
        },
    }

    cfg: ConfigurationList = [{"foo": 42}, {"foo": 10}]

    # when
    result = resolve(cfg, schema)

    # then
    assert result == [{"foo": 42}, {"foo": 10}]


def test_lists_are_permitted_as_root_node():
    # given
    schema: Schema = {"type": "list", "element_schema": {"type": "integer"}}

    cfg: ConfigurationList = [1, 2, 3]

    # when
    result = resolve(cfg, schema)

    # then
    assert result == [1, 2, 3]


def test_values_are_permitted_as_root_node():
    # given
    schema: Schema = {
        "type": "integer",
    }

    cfg = "2"

    # when
    result = resolve(cfg, schema)

    # then
    assert result == 2


def test_preserve_type():
    class UserDict(dict):
        something = 80

    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {
                "type": "dict",
                "required_keys": {"something": {"type": "integer"}},
            },
            "baz": {"type": "list", "element_schema": {"type": "integer"}},
        },
    }

    cfg = UserDict({"foo": 10, "bar": {"something": 20}, "baz": [1, 2, 3]})

    # when
    result = resolve(cfg, schema, preserve_type=True)

    # then
    assert result == cfg
