"""Tests for unresolved (lazily-evaluated) containers."""

from smartconfig import resolve
from smartconfig.types import (
    ConfigurationDict,
    Schema,
    UnresolvedDict,
    UnresolvedFunctionCall,
    UnresolvedList,
)

from pytest import raises


def test_unresolved_list_returns_unresolved_dict():
    # given
    schema: Schema = {
        "required_keys": {
            "foo": {
                "type": "list",
                "element_schema": {
                    "type": "dict",
                    "required_keys": {"foo": {"type": "string"}},
                },
            },
            "bar": {"type": "string"},
        },
        "type": "dict",
    }

    def checker(args):
        assert isinstance(args.root["foo"][0], UnresolvedDict)
        return "ok"

    cfg: ConfigurationDict = {
        "foo": [{"foo": "a"}, {"foo": "b"}],
        "bar": {"__checker__": {}},
    }

    # when
    resolve(cfg, schema, functions={"checker": checker})


def test_unresolved_list_returns_unresolved_list():
    # given
    schema: Schema = {
        "required_keys": {
            "foo": {
                "type": "list",
                "element_schema": {
                    "type": "list",
                    "element_schema": {"type": "string"},
                },
            },
            "bar": {"type": "string"},
        },
        "type": "dict",
    }

    def checker(args):
        assert isinstance(args.root["foo"][0], UnresolvedList)
        return "ok"

    cfg: ConfigurationDict = {"foo": [["hi"], ["a", "b"]], "bar": {"__checker__": {}}}

    # when
    resolve(cfg, schema, functions={"checker": checker})


def test_unresolved_list_resolve():
    # given
    schema: Schema = {
        "required_keys": {
            "foo": {
                "type": "list",
                "element_schema": {
                    "type": "list",
                    "element_schema": {"type": "string"},
                },
            },
            "bar": {"type": "string"},
        },
        "type": "dict",
    }

    def checker(args):
        assert args.root["foo"].resolve() == [["hi"], ["a", "b"]]
        return "ok"

    cfg: ConfigurationDict = {"foo": [["hi"], ["a", "b"]], "bar": {"__checker__": {}}}

    # when
    resolve(cfg, schema, functions={"checker": checker})


def test_unresolved_list_get_keypath():
    # given
    schema: Schema = {
        "required_keys": {
            "foo": {
                "type": "list",
                "element_schema": {
                    "type": "list",
                    "element_schema": {"type": "string"},
                },
            },
            "bar": {"type": "string"},
        },
        "type": "dict",
    }

    def checker(args):
        assert args.root["foo"].get_keypath("1") == ["a", "b"]
        return "ok"

    cfg: ConfigurationDict = {"foo": [["hi"], ["a", "b"]], "bar": {"__checker__": {}}}

    # when
    resolve(cfg, schema, functions={"checker": checker})


def test_unresolved_function_get_keypath():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "alpha": {"type": "integer"},
            "beta": {"type": "integer"},
        },
    }

    def outer(_):
        return {"alpha": 1, "beta": {"__inner__": {}}}

    def inner(args):
        assert isinstance(args.root, UnresolvedFunctionCall)
        number = args.root.get_keypath("alpha")
        assert isinstance(number, int)
        return number + 1

    cfg: ConfigurationDict = {"__outer__": {}}

    # when
    resolve(cfg, schema, functions={"outer": outer, "inner": inner})


def test_unresolved_dict_get_keypath_deeper_than_container_raises_keyerror():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "any"},
            "bar": {"type": "any"},
        },
    }

    def inner(args):
        assert isinstance(args.root, UnresolvedDict)
        with raises(KeyError):
            args.root.get_keypath("foo.a.bar")

    cfg: ConfigurationDict = {"foo": {"a": 1, "b": 2}, "bar": {"__inner__": {}}}

    # when
    resolve(cfg, schema, functions={"inner": inner})
