"""Tests of template fields at load: the wrapper is required, a Template is returned."""

from typing import Any

import pytest
from pytest import raises

from smartconfig import CORE_FUNCTIONS, DEFAULT_FUNCTIONS, Template, exceptions, resolve
from smartconfig.types import ConfigurationDict, ConfigurationList, Schema


# a template field holding a string, with one variable
STRING_TEMPLATE = {
    "type": "template",
    "schema": {"type": "string"},
    "variables": ["name"],
}


# the result is a Template =============================================================


def test_template_field_resolves_to_a_template():
    schema = {"type": "dict", "required_keys": {"x": STRING_TEMPLATE}}
    cfg: ConfigurationDict = {"x": {"__template__": "Hi ${ name }"}}

    result = resolve(cfg, schema)

    t = result["x"]
    assert isinstance(t, Template)
    assert t.source == "Hi ${ name }"
    assert t.variables == ("name",)
    assert t.globals == ()
    assert t.keypath == ("x",)
    assert t.schema == {"type": "string"}


def test_template_field_records_its_globals():
    schema = {
        "type": "dict",
        "required_keys": {
            "x": {
                "type": "template",
                "schema": {"type": "string"},
                "variables": ["name"],
                "globals": ["vars", "course"],
            }
        },
    }
    cfg: ConfigurationDict = {"x": {"__template__": "Hi ${ name }"}}

    result = resolve(cfg, schema)

    assert result["x"].globals == ("vars", "course")


def test_dict_valued_template_is_kept_as_written():
    inner = {
        "type": "dict",
        "required_keys": {
            "title": {"type": "string"},
            "count": {"type": "integer"},
        },
        "optional_keys": {"extra": {"type": "integer", "default": 3}},
    }
    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "template", "schema": inner, "variables": ["name"]}
        },
    }
    cfg: ConfigurationDict = {
        "x": {"__template__": {"title": "${ name }", "count": "1"}}
    }

    result = resolve(cfg, schema)

    # not interpolated, not converted, no defaults filled in
    assert result["x"].source == {"title": "${ name }", "count": "1"}


def test_list_valued_template_is_kept_as_written():
    inner = {"type": "list", "element_schema": {"type": "integer"}}
    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "template", "schema": inner, "variables": ["n"]}
        },
    }
    cfg: ConfigurationDict = {"x": {"__template__": ["1", "${ n + 1 }"]}}

    result = resolve(cfg, schema)

    assert result["x"].source == ["1", "${ n + 1 }"]


def test_template_source_does_not_alias_the_input():
    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "template", "schema": {"type": "any"}, "variables": []}
        },
    }
    cfg: dict[str, Any] = {"x": {"__template__": {"a": ["b"]}}}

    result = resolve(cfg, schema)
    cfg["x"]["__template__"]["a"].append("c")

    assert result["x"].source == {"a": ["b"]}


def test_template_function_is_recognized_by_role_not_by_name():
    schema = {"type": "dict", "required_keys": {"x": STRING_TEMPLATE}}
    cfg: ConfigurationDict = {"x": {"__tmpl__": "Hi ${ name }"}}

    result = resolve(cfg, schema, functions={"tmpl": CORE_FUNCTIONS["template"]})

    assert result["x"].source == "Hi ${ name }"


# the wrapper is required ==============================================================


@pytest.mark.parametrize(
    "value",
    [
        "Hi ${ name }",
        {"title": "${ name }"},
        ["${ name }"],
        {"__raw__": "Hi ${ name }"},
    ],
    ids=["string", "dict", "list", "other-function-call"],
)
def test_unwrapped_value_raises_template_required(value):
    schema = {
        "type": "dict",
        "required_keys": {
            "x": {
                "type": "template",
                "schema": {"type": "any"},
                "variables": ["publication"],
            }
        },
    }
    cfg: ConfigurationDict = {"x": value}

    with raises(exceptions.TemplateRequiredError) as exc:
        resolve(cfg, schema)

    assert isinstance(exc.value, exceptions.ResolutionError)
    assert exc.value.keypath == ("x",)
    assert exc.value.variables == ("publication",)
    assert exc.value.reason == (
        "This field is a template (variables: publication), evaluated later. "
        'Write it as {"__template__": ...}.'
    )


def test_template_required_message_with_no_variables():
    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "template", "schema": {"type": "string"}, "variables": []}
        },
    }

    with raises(exceptions.TemplateRequiredError) as exc:
        resolve({"x": "hello"}, schema)

    assert exc.value.variables == ()
    assert "(variables: none)" in exc.value.reason


def test_template_required_message_with_several_variables():
    schema = {
        "type": "dict",
        "required_keys": {
            "x": {
                "type": "template",
                "schema": {"type": "string"},
                "variables": ["a", "b"],
            }
        },
    }

    with raises(exceptions.TemplateRequiredError) as exc:
        resolve({"x": "hello"}, schema)

    assert "(variables: a, b)" in exc.value.reason


def test_wrapper_is_an_unknown_function_when_template_function_is_unavailable():
    schema = {"type": "dict", "required_keys": {"x": STRING_TEMPLATE}}
    cfg: ConfigurationDict = {"x": {"__template__": "Hi"}}

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions=None)

    assert "Invalid function call: Unknown function: template" in str(exc.value)


def test_wrapper_is_required_when_function_calls_are_disabled():
    schema = {"type": "dict", "required_keys": {"x": STRING_TEMPLATE}}
    cfg: ConfigurationDict = {"x": {"__template__": "Hi"}}

    with raises(exceptions.TemplateRequiredError):
        resolve(cfg, schema, check_for_function_call=None)


def test_unknown_function_call_on_template_field_is_an_error():
    schema = {"type": "dict", "required_keys": {"x": STRING_TEMPLATE}}
    cfg: ConfigurationDict = {"x": {"__nope__": 1}}

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema)

    assert exc.value.keypath == ("x",)
    assert "Invalid function call" in str(exc.value)


# null, optional and default ===========================================================


def test_absent_optional_template_without_default_is_absent():
    schema = {"type": "dict", "optional_keys": {"x": STRING_TEMPLATE}}

    assert resolve({}, schema) == {}


def test_absent_template_with_null_default_is_none():
    field = {**STRING_TEMPLATE, "nullable": True, "default": None}
    schema = {"type": "dict", "optional_keys": {"x": field}}

    assert resolve({}, schema) == {"x": None}


def test_absent_template_with_default_is_a_template_of_the_default():
    field = {**STRING_TEMPLATE, "default": "Hello ${ name }"}
    schema = {"type": "dict", "optional_keys": {"x": field}}

    result = resolve({}, schema)

    t = result["x"]
    assert isinstance(t, Template)
    assert t.source == "Hello ${ name }"
    assert t.variables == ("name",)
    assert t.keypath == ("x",)


def test_absent_template_with_dict_default_is_kept_as_written():
    inner = {
        "type": "dict",
        "required_keys": {"title": {"type": "string"}, "count": {"type": "integer"}},
    }
    field = {
        "type": "template",
        "schema": inner,
        "variables": ["name"],
        "default": {"title": "${ name }", "count": "2"},
    }
    schema = {"type": "dict", "optional_keys": {"x": field}}

    result = resolve({}, schema)

    assert result["x"].source == {"title": "${ name }", "count": "2"}


def test_absent_template_with_default_from_dynamic_schema():
    def dynamic(cfg, keypath):
        return {**STRING_TEMPLATE, "default": "Hello ${ name }"}

    schema = {"type": "dict", "optional_keys": {"x": dynamic}}

    result = resolve({}, schema)

    assert result["x"].source == "Hello ${ name }"


def test_null_template_field_that_is_nullable_is_none():
    schema = {
        "type": "dict",
        "required_keys": {"x": {**STRING_TEMPLATE, "nullable": True}},
    }

    assert resolve({"x": None}, schema) == {"x": None}


def test_null_template_field_that_is_not_nullable_is_an_error():
    schema = {"type": "dict", "required_keys": {"x": STRING_TEMPLATE}}

    with raises(exceptions.ResolutionError) as exc:
        resolve({"x": None}, schema)

    assert exc.value.keypath == ("x",)
    assert "Unexpectedly null." in str(exc.value)


def test_wrapped_null_is_a_template_of_null():
    schema = {
        "type": "dict",
        "required_keys": {
            "x": {
                "type": "template",
                "schema": {"type": "string", "nullable": True},
                "variables": [],
            }
        },
    }

    result = resolve({"x": {"__template__": None}}, schema)

    assert isinstance(result["x"], Template)
    assert result["x"].source is None


# Template objects as input ============================================================


def test_template_given_to_a_template_field_comes_back_unchanged():
    t = Template("Hi ${ name }", {"type": "string"}, ["name"], keypath=["x"])
    schema = {"type": "dict", "required_keys": {"x": STRING_TEMPLATE}}

    result = resolve({"x": t}, schema)  # type: ignore[dict-item]

    assert result["x"] is t


def test_template_given_to_an_any_field_comes_back_unchanged():
    t = Template("Hi ${ name }", {"type": "string"}, ["name"], keypath=["x"])
    schema = {"type": "dict", "required_keys": {"x": {"type": "any"}}}

    result = resolve({"x": t}, schema)  # type: ignore[dict-item]

    assert result["x"] is t


@pytest.mark.parametrize(
    "field_schema, expected",
    [
        ({"type": "string"}, "a string"),
        ({"type": "integer"}, "an integer"),
        ({"type": "dict"}, "a dict"),
        ({"type": "list", "element_schema": {"type": "any"}}, "a list"),
    ],
)
def test_template_given_to_another_field_is_a_shape_error(field_schema, expected):
    t = Template("Hi")
    schema = {"type": "dict", "required_keys": {"x": field_schema}}

    with raises(exceptions.ResolutionError) as exc:
        resolve({"x": t}, schema)  # type: ignore[dict-item]

    assert exc.value.keypath == ("x",)
    assert exc.value.reason == f"Expected {expected}, but got a template."


def test_resolving_the_output_again_leaves_templates_alone():
    inner = {"type": "dict", "required_keys": {"title": {"type": "string"}}}
    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "template", "schema": inner, "variables": ["name"]},
            "y": {"type": "string"},
        },
    }
    cfg: ConfigurationDict = {
        "x": {"__template__": {"title": "${ name }"}},
        "y": "hello",
    }

    first = resolve(cfg, schema)
    second = resolve(first, schema)

    assert second == first
    assert second["x"] is first["x"]


# where template fields can appear =====================================================


def test_template_field_reached_through_a_dynamic_schema():
    def dynamic(cfg, keypath):
        return STRING_TEMPLATE

    schema = {"type": "dict", "required_keys": {"x": dynamic}}

    result = resolve({"x": {"__template__": "Hi ${ name }"}}, schema)

    assert result["x"].source == "Hi ${ name }"


def test_template_fields_as_list_elements():
    schema: Schema = {"type": "list", "element_schema": STRING_TEMPLATE}
    cfg: ConfigurationList = [
        {"__template__": "a ${ name }"},
        {"__template__": "b ${ name }"},
    ]

    result = resolve(cfg, schema)

    assert [t.source for t in result] == ["a ${ name }", "b ${ name }"]
    assert [t.keypath for t in result] == [("0",), ("1",)]


def test_unwrapped_list_element_raises_at_its_keypath():
    schema: Schema = {"type": "list", "element_schema": STRING_TEMPLATE}
    cfg: ConfigurationList = [{"__template__": "a ${ name }"}, "b ${ name }"]

    with raises(exceptions.TemplateRequiredError) as exc:
        resolve(cfg, schema)

    assert exc.value.keypath == ("1",)


def test_template_fields_as_extra_keys():
    schema: Schema = {"type": "dict", "extra_keys_schema": STRING_TEMPLATE}
    cfg: ConfigurationDict = {
        "a": {"__template__": "a ${ name }"},
        "b": {"__template__": "b"},
    }

    result = resolve(cfg, schema)

    assert result["a"].source == "a ${ name }"
    assert result["b"].keypath == ("b",)


def test_root_can_be_a_template_field():
    result = resolve({"__template__": "Hi ${ name }"}, STRING_TEMPLATE)

    assert isinstance(result, Template)
    assert result.source == "Hi ${ name }"
    assert result.keypath == ()


def test_template_field_can_be_referenced_from_elsewhere_without_error():
    # referring to the template field's keypath is allowed (e.g. by __splice__ of
    # an any field); it gives back the Template
    schema = {
        "type": "dict",
        "required_keys": {"x": STRING_TEMPLATE, "y": {"type": "any"}},
    }
    cfg: ConfigurationDict = {
        "x": {"__template__": "Hi ${ name }"},
        "y": {"__splice__": "x"},
    }

    result = resolve(cfg, schema)

    assert result["y"] == result["x"]


def test_preserve_type_copies_the_template_as_a_leaf():
    class MyDict(dict):
        pass

    schema = {
        "type": "dict",
        "required_keys": {"x": STRING_TEMPLATE, "y": {"type": "integer"}},
    }
    base: ConfigurationDict = {"x": {"__template__": "Hi ${ name }"}, "y": "3"}
    cfg = MyDict(base)

    result = resolve(cfg, schema, preserve_type=True)

    assert isinstance(result, MyDict)
    assert isinstance(result["x"], Template)
    assert result["x"].source == "Hi ${ name }"
    assert result["y"] == 3


def test_preserve_type_with_a_template_at_the_root():
    result = resolve(
        {"__template__": "Hi ${ name }"}, STRING_TEMPLATE, preserve_type=True
    )

    assert isinstance(result, Template)


# invalid template schemas =============================================================


@pytest.mark.parametrize("missing", ["schema", "variables"])
def test_static_template_schema_missing_a_key_is_an_invalid_schema(missing):
    field = dict(STRING_TEMPLATE)
    del field[missing]
    schema = {"type": "dict", "required_keys": {"x": field}}

    with raises(exceptions.InvalidSchemaError) as exc:
        resolve({"x": {"__template__": "Hi"}}, schema)

    assert missing in str(exc.value)


def test_default_functions_include_template():
    # sanity check for the tests above, which rely on the default functions
    assert "template" in DEFAULT_FUNCTIONS
