"""Tests of Template.evaluate()."""

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


def test_evaluate_interpolates_converts_and_fills_defaults():
    schema = {
        "type": "dict",
        "required_keys": {
            "x": {
                "type": "template",
                "schema": PAGE,
                "parameters": ["name", "n"],
            }
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

    result = template.evaluate({"name": "hw", "n": 1})

    assert result == {
        "title": "hw",
        "count": 2,
        "due": datetime.date(2026, 1, 1),
        "subtitle": "hw!",
    }


def test_evaluate_calls_functions():
    template = Template(
        {"answer": {"__if__": {"condition": "${ flag }", "then": "yes", "else": "no"}}},
        schema={"type": "dict", "required_keys": {"answer": {"type": "string"}}},
        parameters=["flag"],
    )

    assert template.evaluate({"flag": True}) == {"answer": "yes"}
    assert template.evaluate({"flag": False}) == {"answer": "no"}


def test_a_template_whose_value_is_a_function_call_can_use_its_variables():
    template = Template(
        {"__if__": {"condition": "${ flag }", "then": "yes", "else": "no"}},
        schema={"type": "string"},
        parameters=["flag"],
    )

    assert template.evaluate({"flag": True}) == "yes"
    assert template.evaluate({"flag": False}) == "no"


def test_evaluating_twice_gives_independent_results():
    template = Template(
        {"tags": ["${ a }"]},
        schema={
            "type": "dict",
            "required_keys": {
                "tags": {"type": "list", "element_schema": {"type": "string"}}
            },
        },
        parameters=["a"],
    )

    first = template.evaluate({"a": "x"})
    first["tags"].append("changed")
    second = template.evaluate({"a": "y"})

    assert first == {"tags": ["x", "changed"]}
    assert second == {"tags": ["y"]}
    assert template.source == {"tags": ["${ a }"]}


# variables ============================================================================


def test_missing_variable_is_an_error():
    template = Template(
        "${ a } ${ b }",
        schema={"type": "string"},
        parameters=["a", "b", "c"],
        keypath=["x", "y"],
    )

    with raises(exceptions.ResolutionError) as exc:
        template.evaluate({"b": 1})

    assert exc.value.keypath == ("x", "y")
    assert exc.value.reason == (
        "Missing parameters: a, c. This template's parameters: a, b, c."
    )


def test_extra_variable_is_an_error():
    template = Template(
        "${ a }",
        schema={"type": "string"},
        parameters=["a"],
        keypath=["x"],
    )

    with raises(exceptions.ResolutionError) as exc:
        template.evaluate({"a": 1, "course": "dsc"})

    assert exc.value.keypath == ("x",)
    assert exc.value.reason == (
        "Unexpected parameters: course. This template's parameters: a."
    )


def test_missing_and_extra_variables_are_reported_together():
    template = Template("${ a }", parameters=["a"])

    with raises(exceptions.ResolutionError) as exc:
        template.evaluate({"b": 1})

    assert exc.value.reason == (
        "Missing parameters: a. Unexpected parameters: b. "
        "This template's parameters: a."
    )


def test_a_template_with_no_parameters_takes_none():
    template = Template("hi")

    assert template.evaluate() == "hi"
    with raises(exceptions.ResolutionError):
        template.evaluate({"a": 1})


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
                "parameters": ["n"],
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

    result = template.evaluate({"n": 1})

    assert result == {"a": 10, "b": 80, "c": "HI"}


# nested templates =====================================================================


def test_a_template_field_produced_while_evaluating_a_template_is_an_error():
    # the __if__ hides the template field from the check made at load
    inner = {
        "type": "dict",
        "required_keys": {
            "body": {
                "type": "template",
                "schema": {"type": "string"},
                "parameters": ["section"],
            }
        },
    }
    template = Template(
        {
            "__if__": {
                "condition": "${ flag }",
                "then": {"body": {"__template__": "a"}},
                "else": {"body": {"__template__": "b"}},
            }
        },
        schema=inner,
        parameters=["flag"],
        keypath=["x"],
    )

    with raises(exceptions.UnexpectedTemplateError) as exc:
        template.evaluate({"flag": True})

    assert exc.value.enclosing == ("x",)


def test_a_template_object_inside_a_template_source_is_an_error():
    # a Template can be put in a source only from Python, not from a config file
    inner = Template("${ a }", parameters=["a"], keypath=["y"])
    template = Template(
        {"k": inner},
        schema={
            "type": "dict",
            "required_keys": {
                "k": {
                    "type": "template",
                    "schema": {"type": "string"},
                    "parameters": ["a"],
                }
            },
        },
        keypath=["x"],
    )

    with raises(exceptions.UnexpectedTemplateError) as exc:
        template.evaluate()

    assert exc.value.keypath == ("x", "k")
    assert exc.value.enclosing == ("x",)


# errors ===============================================================================


def test_errors_are_reported_at_the_template_keypath_plus_the_inner_path():
    template = Template(
        {"count": "${ n }"},
        schema={"type": "dict", "required_keys": {"count": {"type": "integer"}}},
        parameters=["n"],
        keypath=["pages", "x"],
    )

    with raises(exceptions.ResolutionError) as exc:
        template.evaluate({"n": "many"})

    assert exc.value.keypath == ("pages", "x", "count")


def test_undefined_name_is_reported_at_the_template_keypath_plus_the_inner_path():
    template = Template(
        {"title": "${ nope }"},
        schema={"type": "dict", "required_keys": {"title": {"type": "string"}}},
        keypath=["pages", "x"],
    )

    with raises(exceptions.ResolutionError) as exc:
        template.evaluate()

    assert exc.value.keypath == ("pages", "x", "title")


def test_a_function_call_producing_the_wrong_shape_is_an_error():
    template = Template(
        {"__if__": {"condition": True, "then": "s", "else": "t"}},
        schema={"type": "dict", "required_keys": {"title": {"type": "string"}}},
        keypath=["x"],
    )

    with raises(exceptions.ResolutionError) as exc:
        template.evaluate()

    assert exc.value.keypath == ("x",)
    assert exc.value.reason == 'Expected a dict, but got the string "s".'


def test_a_template_field_in_the_source_is_a_nesting_error_when_evaluated():
    # a Template made in Python is not checked at load; evaluating it reports the
    # nested template field, not a missing __template__ wrapper
    template = Template(
        {"body": "plain"},
        schema={
            "type": "dict",
            "required_keys": {
                "body": {
                    "type": "template",
                    "schema": {"type": "string"},
                    "parameters": [],
                }
            },
        },
        keypath=["x"],
    )

    with raises(exceptions.UnexpectedTemplateError) as exc:
        template.evaluate()

    assert exc.value.keypath == ("x", "body")
    assert exc.value.enclosing == ("x",)
