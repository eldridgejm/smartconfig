"""Tests for the smartconfig.Template class as a data object (no resolution)."""

import copy
import json
from typing import Any


from smartconfig import Template


# constructor ==========================================================================


def test_constructor_defaults():
    t = Template("Hi ${ name }")

    assert t.source == "Hi ${ name }"
    assert t.schema == {"type": "any"}
    assert t.variables == ()
    assert t.keypath == ()


def test_variables_and_keypath_are_tuples():
    t = Template(
        "Hi ${ name }",
        schema={"type": "string"},
        variables=["name"],
        keypath=["a", "b"],
    )

    assert t.variables == ("name",)
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
    assert Template("a", variables=["x"]) != Template("a", variables=["y"])


def test_templates_with_different_keypath_are_not_equal():
    assert Template("a", keypath=["x"]) != Template("a", keypath=["y"])


def test_templates_with_different_schema_are_not_equal():
    assert Template("a", schema={"type": "string"}) != Template("a")


def test_template_is_not_equal_to_other_types():
    assert Template("a") != "a"
    assert Template("a") != {"__template__": "a"}


# json =================================================================================


def test_to_json_is_json_serializable():
    t = Template(
        {"title": "${ name }", "items": [1, 2.5, True, None]},
        schema={"type": "any"},
        variables=["name"],
        keypath=["a", "b"],
    )

    data = t.to_json()

    assert data == {
        "source": {"title": "${ name }", "items": [1, 2.5, True, None]},
        "variables": ["name"],
        "keypath": ["a", "b"],
    }
    assert json.loads(json.dumps(data)) == data


def test_to_json_does_not_alias_source():
    t = Template({"title": "x"})

    data = t.to_json()
    data["source"]["title"] = "changed"

    assert t.source == {"title": "x"}


def test_from_json_round_trip_with_schema():
    t = Template(
        {"title": "${ name }"},
        schema={"type": "dict", "required_keys": {"title": {"type": "string"}}},
        variables=["name"],
        keypath=["a", "b"],
    )

    assert Template.from_json(t.to_json(), schema=t.schema) == t


def test_from_json_without_schema_has_any_schema():
    t = Template("x", schema={"type": "string"}, variables=["y"])

    rebuilt = Template.from_json(t.to_json())

    assert rebuilt.schema == {"type": "any"}
    assert rebuilt.source == "x"
    assert rebuilt.variables == ("y",)


# copying ==============================================================================


def test_deepcopy_is_equal_with_independent_source():
    t = Template({"tags": ["a"]}, variables=["x"], keypath=["k"])

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
