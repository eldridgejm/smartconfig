"""Tests for the smartconfig.types.Template class as a data object (no resolution)."""

import copy
from typing import Any


from pytest import raises

from smartconfig.exceptions import InvalidSchemaError
from smartconfig.types import Template


# constructor ==========================================================================


def test_constructor_defaults():
    t = Template("Hi ${ name }")

    assert t.source == "Hi ${ name }"
    assert t.schema == {"type": "any"}
    assert t.parameters == ()
    assert t.keypath == ()


def test_parameters_and_keypath_are_tuples():
    t = Template(
        "Hi ${ name }",
        schema={"type": "string"},
        parameters=["name"],
        keypath=["a", "b"],
    )

    assert t.parameters == ("name",)
    assert t.keypath == ("a", "b")
    assert t.schema == {"type": "string"}


def test_parameters_given_as_a_string_is_an_error():
    # a string is an iterable of characters, so "abc" would mean the parameters
    # a, b and c; it is almost certainly a mistake for ["abc"]
    with raises(TypeError):
        Template("x", parameters="abc")


def test_a_parameter_reserved_by_jinja_is_an_error():
    # ${ true } is Jinja's literal True, so the parameter could never be used
    with raises(ValueError) as exc:
        Template("${ true }", parameters=["true"])

    assert str(exc.value) == (
        'Invalid parameter: "true" is reserved by Jinja, which reads it as a '
        "literal, so ${ true } can't refer to it. Use another name."
    )


def test_an_invalid_schema_is_an_error():
    with raises(InvalidSchemaError) as exc:
        Template("x", schema={"type": "integr"})

    assert exc.value.keypath == ("type",)


def test_a_global_variable_reserved_by_jinja_is_an_error():
    # raised when the template is made, not first when it is evaluated
    with raises(ValueError) as exc:
        Template("x", global_variables={"true": 1})

    assert str(exc.value).startswith('Invalid global variable: "true" is reserved')


def test_source_is_a_deep_copy_of_what_was_passed():
    tags = ["a", "b"]
    source: dict[str, Any] = {"title": "${ name }", "tags": tags}
    t = Template(source)

    source["title"] = "changed"
    tags.append("c")

    assert t.source == {"title": "${ name }", "tags": ["a", "b"]}


# equality, hashing, repr ==============================================================


def test_templates_with_different_source_are_not_equal():
    assert Template("a") != Template("b")


def test_templates_with_different_parameters_are_not_equal():
    assert Template("a", parameters=["x"]) != Template("a", parameters=["y"])


def test_templates_with_different_keypath_are_not_equal():
    assert Template("a", keypath=["x"]) != Template("a", keypath=["y"])


def test_templates_with_different_schema_are_not_equal():
    assert Template("a", schema={"type": "string"}) != Template("a")


def test_template_is_not_equal_to_other_types():
    assert Template("a") != "a"
    assert Template("a") != {"__template__": "a"}


# copying ==============================================================================


def test_deepcopy_is_equal_with_independent_source():
    t = Template({"tags": ["a"]}, parameters=["x"], keypath=["k"])

    c = copy.deepcopy(t)

    assert c == t
    assert c is not t
    assert isinstance(c.source, dict) and isinstance(c.source["tags"], list)
    c.source["tags"].append("b")
    assert t.source == {"tags": ["a"]}


def test_deepcopy_shares_schema():
    schema = {"type": "dict", "extra_keys_schema": {"type": "any"}}
    t = Template({}, schema=schema)

    c = copy.deepcopy(t)

    assert c.schema is t.schema


# outer parameters =====================================================================


def test_outer_parameters_default_to_empty():
    assert Template("a").outer_parameters == {}


def test_outer_parameters_are_a_read_only_copy_of_what_was_passed():
    values = {"publication": {"number": 3}}
    t = Template("a", outer_parameters=values)

    values["other"] = {}

    assert t.outer_parameters == {"publication": {"number": 3}}
    with raises(TypeError):
        t.outer_parameters["x"] = 1  # type: ignore[index]


def test_a_parameter_named_like_an_outer_parameter_is_an_error():
    with raises(ValueError) as exc:
        Template("a", parameters=["a", "b"], outer_parameters={"b": 1})

    assert str(exc.value) == (
        'Invalid parameter: "b" is also an outer parameter, so ${ b } would be '
        "ambiguous. Use another name."
    )


def test_templates_with_different_outer_parameters_are_not_equal():
    assert Template("a", outer_parameters={"x": 1}) != Template(
        "a", outer_parameters={"x": 2}
    )
    assert Template("a", outer_parameters={"x": 1}) == Template(
        "a", outer_parameters={"x": 1}
    )


def test_deepcopy_shares_the_outer_values():
    publication = {"number": 3}
    t = Template("a", outer_parameters={"publication": publication})

    c = copy.deepcopy(t)

    assert c == t
    assert c.outer_parameters["publication"] is publication


def test_repr_names_the_outer_parameters():
    t = Template(
        "a", parameters=["link"], keypath=["x", "y"], outer_parameters={"p": 1}
    )

    assert repr(t) == 'Template(at "x.y", parameters: link; outer: p)'
