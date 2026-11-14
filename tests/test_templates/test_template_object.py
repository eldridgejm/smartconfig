"""Tests for the smartconfig.Template class as a data object (no resolution)."""

import copy
from typing import Any


from smartconfig import Template


# constructor ==========================================================================


def test_constructor_defaults():
    t = Template("Hi ${ name }")

    assert t.source == "Hi ${ name }"
    assert t.schema == {"type": "any"}
    assert t.parameters == ()
    assert t.keypath == ()


def test_variables_and_keypath_are_tuples():
    t = Template(
        "Hi ${ name }",
        schema={"type": "string"},
        parameters=["name"],
        keypath=["a", "b"],
    )

    assert t.parameters == ("name",)
    assert t.keypath == ("a", "b")
    assert t.schema == {"type": "string"}


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


def test_templates_with_different_variables_are_not_equal():
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
