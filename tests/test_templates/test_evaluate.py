"""Tests of Template.evaluate()."""

import datetime

from pytest import raises

from smartconfig import DEFAULT_FUNCTIONS, exceptions, resolve
from smartconfig.types import Template
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


def test_a_template_whose_value_is_a_function_call_can_use_its_parameters():
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


# parameters ===========================================================================


def test_missing_parameter_is_an_error():
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


def test_extra_parameter_is_an_error():
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


def test_missing_and_extra_parameters_are_reported_together():
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


def test_parameters_can_be_passed_by_keyword():
    template = Template("${ a }", schema={"type": "integer"}, parameters=["a"])

    assert template.evaluate(parameters={"a": 1}) == 1


# A template's top-level keys can be referenced by name, like its parameters, so a
# key and a parameter with the same name would be ambiguous. That is an error.


def test_a_function_call_producing_a_key_named_like_a_parameter_is_an_error():
    # the __if__ produces a dict with a key "name", which is also a parameter;
    # the key isn't known until the template is evaluated
    template = Template(
        {"__if__": {"condition": "True", "then": {"name": "x"}, "else": {}}},
        parameters=["name"],
        keypath=["t"],
    )

    with raises(exceptions.ResolutionError) as exc:
        template.evaluate({"name": "bob"})

    assert exc.value.keypath == ("t", "name")
    assert "parameter" in str(exc.value)


def test_a_nested_key_named_like_a_parameter_is_allowed():
    # "name" is a key of page, not a top-level key, so ${ name } is unambiguous
    template = Template({"page": {"name": "${ name }"}}, parameters=["name"])

    assert template.evaluate({"name": "bob"}) == {"page": {"name": "bob"}}


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
        },
        functions={**DEFAULT_FUNCTIONS, "double": double},
        filters={"shout": str.upper},
    )["x"]

    result = template.evaluate({"n": 1})

    assert result == {"a": 10, "b": 80, "c": "HI"}


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


def test_a_template_field_in_the_source_without_a_wrapper_is_an_error_when_evaluated():
    # a Template made in Python is not checked at load
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

    with raises(exceptions.TemplateRequiredError) as exc:
        template.evaluate()

    assert exc.value.keypath == ("x", "body")


# global variables =====================================================================


GREETING = {
    "type": "dict",
    "required_keys": {
        "greeting": {
            "type": "template",
            "schema": {"type": "string"},
            "parameters": ["name"],
        }
    },
}


def test_a_template_field_sees_the_global_variables_of_the_resolve_that_made_it():
    cfg: ConfigurationDict = {
        "greeting": {"__template__": "Hello ${ name } from ${ course }"}
    }
    template = resolve(cfg, GREETING, global_variables={"course": "DSC 10"})["greeting"]

    assert template.evaluate({"name": "Ana"}) == "Hello Ana from DSC 10"


def test_a_parameter_wins_over_a_global_variable_of_the_same_name():
    # the parameter wins, and the collision is not an error: whoever calls resolve()
    # may pass globals that the template's author never saw
    cfg: ConfigurationDict = {"greeting": {"__template__": "Hello ${ name }"}}
    template = resolve(cfg, GREETING, global_variables={"name": "global"})["greeting"]

    assert template.evaluate({"name": "Ana"}) == "Hello Ana"


def test_a_template_made_directly_takes_global_variables():
    template = Template(
        "${ greeting }, ${ name }",
        parameters=["name"],
        global_variables={"greeting": "Hi"},
    )

    assert template.evaluate({"name": "Ana"}) == "Hi, Ana"


def test_a_template_evaluating_to_a_tree_nested_too_deeply_is_a_resolution_error():
    # given — the deep tree comes from a function, since a source this deep can't
    # even be copied into a Template; it is deeper than Python's default recursion
    # limit allows
    def deep(args: FunctionArgs) -> ConfigurationDict:
        result: ConfigurationDict = {"a": 1}
        for _ in range(1000):
            result = {"a": result}
        return result

    template = Template({"__deep__": {}}, functions={"deep": deep})

    # when
    with raises(exceptions.ResolutionError) as exc:
        template.evaluate({})

    # then
    assert "nested too deeply" in str(exc.value)
