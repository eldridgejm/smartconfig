"""Tests of the load-time structure check of a template's value."""

import pytest
from pytest import raises

from smartconfig import DEFAULT_FUNCTIONS, exceptions, resolve
from smartconfig.types import ConfigurationDict, FunctionArgs


def explode(args: FunctionArgs):
    """A function that must not be called at load."""
    raise AssertionError("explode was called")


# DEFAULT_FUNCTIONS plus a function that raises if it is ever called
FUNCTIONS_WITH_EXPLODE = {**DEFAULT_FUNCTIONS, "explode": explode}


# an inner schema describing a "page": a dict with a required title and an optional
# integer count with a default
PAGE = {
    "type": "dict",
    "required_keys": {"title": {"type": "string"}},
    "optional_keys": {"count": {"type": "integer", "default": 1}},
}


# structure errors =====================================================================


def test_missing_required_key_is_an_error_at_load():
    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "template", "schema": PAGE, "variables": ["name"]}
        },
    }
    cfg: ConfigurationDict = {"x": {"__template__": {"count": "2"}}}

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema)

    assert exc.value.keypath == ("x", "title")
    assert exc.value.reason == 'Dictionary is missing required key "title".'


def test_wrapped_null_where_inner_schema_is_not_nullable_is_an_error():
    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "template", "schema": {"type": "string"}, "variables": []}
        },
    }
    cfg: ConfigurationDict = {"x": {"__template__": None}}

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema)

    assert exc.value.keypath == ("x",)
    assert exc.value.reason == "Unexpectedly null."


def test_structure_is_checked_in_a_default():
    schema = {
        "type": "dict",
        "optional_keys": {
            "x": {
                "type": "template",
                "schema": PAGE,
                "variables": [],
                "default": {"count": "3"},
            }
        },
    }

    with raises(exceptions.ResolutionError) as exc:
        resolve({}, schema)

    assert exc.value.keypath == ("x", "title")


def test_interpolated_string_where_dict_expected_is_an_error_at_load():
    # interpolation always produces a string, so this can never succeed
    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "template", "schema": PAGE, "variables": ["page"]}
        },
    }
    cfg: ConfigurationDict = {"x": {"__template__": "${ page }"}}

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema)

    assert exc.value.keypath == ("x",)
    assert exc.value.reason == (
        'Expected a dict, but got the string "${ page }". A ${ ... } always gives a '
        "string: to copy a dict or list, use __splice__ (or __use__ for a "
        "template)."
    )


# function calls =======================================================================


@pytest.mark.parametrize(
    "value",
    [
        # where a value is expected
        {"title": {"__explode__": {}}},
        # where a dict is expected (the whole template)
        {"__explode__": {}},
    ],
    ids=["value", "dict"],
)
def test_function_call_is_accepted_and_not_evaluated(value):
    schema = {
        "type": "dict",
        "required_keys": {"x": {"type": "template", "schema": PAGE, "variables": []}},
    }
    cfg: ConfigurationDict = {"x": {"__template__": value}}

    result = resolve(cfg, schema, functions=FUNCTIONS_WITH_EXPLODE)

    assert result["x"].source == value


def test_structure_inside_a_function_call_input_is_not_checked():
    schema = {
        "type": "dict",
        "required_keys": {"x": {"type": "template", "schema": PAGE, "variables": []}},
    }
    # the "else" branch is missing a title, but function inputs are not checked
    value: ConfigurationDict = {
        "__if__": {"condition": True, "then": {"title": "a"}, "else": {"no": "x"}}
    }
    cfg: ConfigurationDict = {"x": {"__template__": value}}

    result = resolve(cfg, schema)

    assert result["x"].source == value


# wrappers inside a template ===========================================================


@pytest.mark.parametrize(
    "inner, value, keypath",
    [
        ({"type": "string"}, {"__template__": "a"}, ("x",)),
        (PAGE, {"title": {"__template__": "a"}}, ("x", "title")),
        ({"type": "any"}, {"a": [{"__template__": "b"}]}, ("x", "a", "0")),
    ],
    ids=["string-root", "dict-value", "under-any"],
)
def test_wrapper_inside_a_template_is_unexpected(inner, value, keypath):
    schema = {
        "type": "dict",
        "required_keys": {"x": {"type": "template", "schema": inner, "variables": []}},
    }
    cfg: ConfigurationDict = {"x": {"__template__": value}}

    with raises(exceptions.UnexpectedTemplateError) as exc:
        resolve(cfg, schema)

    assert isinstance(exc.value, exceptions.ResolutionError)
    assert exc.value.keypath == keypath
    assert exc.value.enclosing == ("x",)
    assert exc.value.reason == (
        'A template can\'t contain another __template__: the template at "x" '
        "already defers everything in it. Remove the wrapper."
    )


# nested template fields ===============================================================


# a "page" whose "body" is itself a template, with variable "section"
NESTED = {
    "type": "dict",
    "required_keys": {
        "title": {"type": "string"},
        "body": {
            "type": "template",
            "schema": {
                "type": "dict",
                "required_keys": {"text": {"type": "string"}},
            },
            "variables": ["section"],
        },
    },
}


def test_nested_template_field_is_accepted_with_a_wrapper():
    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "template", "schema": NESTED, "variables": ["page"]}
        },
    }
    value: ConfigurationDict = {
        "title": "${ page }",
        "body": {"__template__": {"text": "${ section }"}},
    }
    cfg: ConfigurationDict = {"x": {"__template__": value}}

    result = resolve(cfg, schema)

    assert result["x"].source == value


def test_nested_template_value_is_checked_against_its_own_schema():
    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "template", "schema": NESTED, "variables": ["page"]}
        },
    }
    value: ConfigurationDict = {"title": "a", "body": {"__template__": {"txt": "b"}}}
    cfg: ConfigurationDict = {"x": {"__template__": value}}

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema)

    assert exc.value.keypath == ("x", "body", "text")
    assert exc.value.reason == 'Dictionary is missing required key "text".'
