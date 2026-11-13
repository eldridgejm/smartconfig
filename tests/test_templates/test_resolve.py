"""Tests of Template.resolve()."""

import datetime

from pytest import raises

from smartconfig import DEFAULT_FUNCTIONS, Template, exceptions, resolve
from smartconfig.types import ConfigurationDict, FunctionArgs


# an inner schema describing a "page": a title, a count and a due date, plus an
# optional subtitle with a default that refers to the title
PAGE = {
    "type": "dict",
    "required_keys": {
        "title": {"type": "string"},
        "count": {"type": "integer"},
        "due": {"type": "date"},
    },
    "optional_keys": {
        "subtitle": {"type": "string", "default": "${ title }!"},
    },
}


def test_resolve_interpolates_converts_and_fills_defaults():
    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "template", "schema": PAGE, "variables": ["name", "n"]}
        },
    }
    cfg: ConfigurationDict = {
        "x": {
            "__template__": {
                "title": "${ name }",
                "count": "${ n + 1 }",
                "due": "2026-01-0${ n }",
            }
        }
    }
    template = resolve(cfg, schema)["x"]

    result = template.resolve({"name": "hw", "n": 1})

    assert result == {
        "title": "hw",
        "count": 2,
        "due": datetime.date(2026, 1, 1),
        "subtitle": "hw!",
    }


def test_resolve_evaluates_function_calls():
    template = Template(
        {"answer": {"__if__": {"condition": "${ flag }", "then": "yes", "else": "no"}}},
        schema={"type": "dict", "required_keys": {"answer": {"type": "string"}}},
        variables=["flag"],
    )

    assert template.resolve({"flag": True}) == {"answer": "yes"}
    assert template.resolve({"flag": False}) == {"answer": "no"}


def test_a_template_whose_value_is_a_function_call_can_use_its_variables():
    template = Template(
        {"__if__": {"condition": "${ flag }", "then": "yes", "else": "no"}},
        schema={"type": "string"},
        variables=["flag"],
    )

    assert template.resolve({"flag": True}) == "yes"
    assert template.resolve({"flag": False}) == "no"


def test_resolving_twice_gives_independent_results():
    template = Template(
        {"tags": ["${ a }"]},
        schema={
            "type": "dict",
            "required_keys": {
                "tags": {"type": "list", "element_schema": {"type": "string"}}
            },
        },
        variables=["a"],
    )

    first = template.resolve({"a": "x"})
    first["tags"].append("changed")
    second = template.resolve({"a": "y"})

    assert first == {"tags": ["x", "changed"]}
    assert second == {"tags": ["y"]}
    assert template.source == {"tags": ["${ a }"]}


# variables ============================================================================


def test_missing_variable_is_an_error():
    template = Template(
        "${ a } ${ b }",
        schema={"type": "string"},
        variables=["a", "b", "c"],
        keypath=["x", "y"],
    )

    with raises(exceptions.ResolutionError) as exc:
        template.resolve({"b": 1})

    assert exc.value.keypath == ("x", "y")
    assert exc.value.reason == "Missing variables: a, c. This template needs: a, b, c."


def test_extra_names_are_allowed():
    template = Template(
        "${ a } ${ course }", schema={"type": "string"}, variables=["a"]
    )

    assert template.resolve({"a": 1, "course": "dsc"}) == "1 dsc"


# options ==============================================================================


def double(args: FunctionArgs):
    assert isinstance(args.input, int)
    return args.input * 2


def test_a_template_remembers_the_options_of_the_resolve_that_made_it():
    schema = {
        "type": "dict",
        "required_keys": {
            "x": {
                "type": "template",
                "schema": {
                    "type": "dict",
                    "required_keys": {
                        "a": {"type": "integer"},
                        "b": {"type": "integer"},
                        "c": {"type": "string"},
                    },
                },
                "variables": ["n"],
            }
        },
    }
    cfg: ConfigurationDict = {
        "x": {
            "__template__": {
                "a": "${ n }",
                "b": {"__double__": 4},
                "c": "${ 'hi' | shout }",
            }
        }
    }
    template = resolve(
        cfg,
        schema,
        converters={
            "integer": lambda x: int(x) * 10,
            "string": str,
            "any": lambda x: x,
        },
        functions={**DEFAULT_FUNCTIONS, "double": double},
        filters={"shout": str.upper},
    )["x"]

    result = template.resolve({"n": 1})

    assert result == {"a": 10, "b": 80, "c": "HI"}


# nested templates =====================================================================


# a "page" whose "body" is itself a template, with variable "section"
NESTED = {
    "type": "dict",
    "required_keys": {
        "x": {
            "type": "template",
            "schema": {
                "type": "dict",
                "required_keys": {
                    "title": {"type": "string"},
                    "body": {
                        "type": "template",
                        "schema": {"type": "string"},
                        "variables": ["section"],
                    },
                },
            },
            "variables": ["page"],
        }
    },
}


def test_a_nested_template_has_the_outer_and_inner_variables():
    cfg: ConfigurationDict = {
        "x": {
            "__template__": {
                "title": "${ page }",
                "body": {"__template__": "${ page }: ${ section }"},
            }
        }
    }
    template = resolve(cfg, NESTED)["x"]

    result = template.resolve({"page": "p1"})
    body = result["body"]

    assert result["title"] == "p1"
    assert isinstance(body, Template)
    assert body.variables == ("page", "section")
    assert body.keypath == ("x", "body")
    assert body.resolve({"page": "p1", "section": "s1"}) == "p1: s1"


# errors ===============================================================================


def test_errors_are_reported_at_the_template_keypath_plus_the_inner_path():
    template = Template(
        {"count": "${ n }"},
        schema={"type": "dict", "required_keys": {"count": {"type": "integer"}}},
        variables=["n"],
        keypath=["pages", "x"],
    )

    with raises(exceptions.ResolutionError) as exc:
        template.resolve({"n": "many"})

    assert exc.value.keypath == ("pages", "x", "count")


def test_undefined_name_is_reported_at_the_template_keypath_plus_the_inner_path():
    template = Template(
        {"title": "${ nope }"},
        schema={"type": "dict", "required_keys": {"title": {"type": "string"}}},
        keypath=["pages", "x"],
    )

    with raises(exceptions.ResolutionError) as exc:
        template.resolve()

    assert exc.value.keypath == ("pages", "x", "title")


def test_a_function_call_producing_the_wrong_shape_is_an_error():
    template = Template(
        {"__if__": {"condition": True, "then": "s", "else": "t"}},
        schema={"type": "dict", "required_keys": {"title": {"type": "string"}}},
        keypath=["x"],
    )

    with raises(exceptions.ResolutionError) as exc:
        template.resolve()

    assert exc.value.keypath == ("x",)
    assert exc.value.reason == 'Expected a dict, but got the string "s".'
