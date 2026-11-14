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


def test_wrapped_null_where_inner_schema_is_not_nullable_is_an_error():
    schema = {
        "type": "dict",
        "required_keys": {
            "x": {
                "type": "template",
                "schema": {"type": "string"},
                "parameters": [],
            }
        },
    }
    cfg: ConfigurationDict = {"x": {"__template__": None}}

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema)

    assert exc.value.keypath == ("x",)
    assert exc.value.reason == "Unexpectedly null."


# the structure check runs when the configuration is resolved, though nothing in the
# template's value is evaluated


def page_template_schema():
    """A schema with one template field, "x", whose value is a page."""
    return {
        "type": "dict",
        "required_keys": {"x": {"type": "template", "schema": PAGE, "parameters": []}},
    }


def test_a_written_template_missing_a_required_key_is_an_error():
    cfg: ConfigurationDict = {"x": {"__template__": {"count": "3"}}}

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, page_template_schema())

    assert exc.value.keypath == ("x", "title")
    assert exc.value.reason == 'Dictionary is missing required key "title".'


def test_a_written_template_with_an_unexpected_key_is_an_error():
    cfg: ConfigurationDict = {"x": {"__template__": {"title": "a", "extra": "b"}}}

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, page_template_schema())

    assert exc.value.keypath == ("x", "extra")
    assert exc.value.reason == 'Dictionary contains unexpected extra key "extra".'


def test_a_written_template_that_is_a_value_where_a_dict_is_expected_is_an_error():
    cfg: ConfigurationDict = {"x": {"__template__": "a"}}

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, page_template_schema())

    assert exc.value.keypath == ("x",)
    assert exc.value.reason == 'Expected a dict, but got the string "a".'


def test_a_value_that_cannot_be_converted_is_an_error_only_when_evaluated():
    # value types are not checked at load: a value like "${ n + 1 }" is not known
    # until it is interpolated, so conversion waits for evaluate()
    cfg: ConfigurationDict = {"x": {"__template__": {"title": "a", "count": "many"}}}

    template = resolve(cfg, page_template_schema())["x"]

    assert template.source == {"title": "a", "count": "many"}

    with raises(exceptions.ResolutionError) as exc:
        template.evaluate()

    assert exc.value.keypath == ("x", "count")
    assert exc.value.reason == "Cannot convert to integer: 'many'."


def test_structure_is_checked_in_a_default():
    schema = {
        "type": "dict",
        "optional_keys": {
            "x": {
                "type": "template",
                "schema": PAGE,
                "parameters": [],
                "default": {"count": "3"},
            }
        },
    }

    with raises(exceptions.ResolutionError) as exc:
        resolve({}, schema)

    assert exc.value.keypath == ("x", "title")


# function calls =======================================================================


def test_function_call_is_accepted_and_not_evaluated():
    value: ConfigurationDict = {"title": {"__explode__": {}}}
    schema = {
        "type": "dict",
        "required_keys": {"x": {"type": "template", "schema": PAGE, "parameters": []}},
    }
    cfg: ConfigurationDict = {"x": {"__template__": value}}

    result = resolve(cfg, schema, functions=FUNCTIONS_WITH_EXPLODE)

    assert result["x"].source == value


def test_structure_inside_a_function_call_input_is_not_checked():
    schema = {
        "type": "dict",
        "required_keys": {"x": {"type": "template", "schema": PAGE, "parameters": []}},
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
        (PAGE, {"title": {"__template__": "a"}}, ("x", "title")),
        ({"type": "any"}, {"a": [{"__template__": "b"}]}, ("x", "a", "0")),
    ],
    ids=["dict-value", "under-any"],
)
def test_wrapper_inside_a_template_is_unexpected(inner, value, keypath):
    schema = {
        "type": "dict",
        "required_keys": {"x": {"type": "template", "schema": inner, "parameters": []}},
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


def test_a_template_field_inside_a_template_is_an_error():
    # a "page" whose "body" would itself be a template, with variable "section"
    page = {
        "type": "dict",
        "required_keys": {
            "title": {"type": "string"},
            "body": {
                "type": "template",
                "schema": {"type": "string"},
                "parameters": ["section"],
            },
        },
    }
    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "template", "schema": page, "parameters": ["page"]}
        },
    }
    value: ConfigurationDict = {"title": "a", "body": {"__template__": "b"}}
    cfg: ConfigurationDict = {"x": {"__template__": value}}

    with raises(exceptions.UnexpectedTemplateError) as exc:
        resolve(cfg, schema)

    assert exc.value.keypath == ("x", "body")
    assert exc.value.enclosing == ("x",)
    assert exc.value.reason == (
        'A template can\'t contain a template field: the template at "x" already '
        "defers everything in it. Make the field a sibling of the template instead."
    )


@pytest.mark.parametrize(
    "body",
    [
        {"__use__": "fragments.body"},
        "a plain value",
        {
            "__if__": {
                "condition": True,
                "then": {"__template__": "b"},
                "else": {"__template__": "c"},
            }
        },
    ],
    ids=["use", "plain", "if"],
)
def test_a_template_field_inside_a_template_is_an_error_whatever_its_value(body):
    # a template field's value can be any function call that makes a template; inside
    # a template it is rejected at load, without the call being evaluated
    page = {
        "type": "dict",
        "required_keys": {
            "title": {"type": "string"},
            "body": {
                "type": "template",
                "schema": {"type": "string"},
                "parameters": [],
            },
        },
    }
    schema = {
        "type": "dict",
        "required_keys": {
            "fragments": {"type": "any"},
            "x": {"type": "template", "schema": page, "parameters": []},
        },
    }
    cfg: ConfigurationDict = {
        "fragments": {"body": {"__template__": "b"}},
        "x": {"__template__": {"title": "a", "body": body}},
    }

    with raises(exceptions.UnexpectedTemplateError) as exc:
        resolve(cfg, schema)

    assert exc.value.keypath == ("x", "body")
    assert exc.value.enclosing == ("x",)
