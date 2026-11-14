"""Tests of template fields at load: the wrapper is required, a Template is returned."""

import pytest
from pytest import raises

from smartconfig import CORE_FUNCTIONS, Template, exceptions, resolve
from smartconfig.types import ConfigurationDict, ConfigurationList, Schema


# a template field holding a string, with one variable
STRING_TEMPLATE = {
    "type": "template",
    "schema": {"type": "string"},
    "parameters": ["name"],
}


# the result is a Template =============================================================


def test_template_field_resolves_to_a_template():
    schema = {"type": "dict", "required_keys": {"x": STRING_TEMPLATE}}
    cfg: ConfigurationDict = {"x": {"__template__": "Hi ${ name }"}}

    result = resolve(cfg, schema)

    t = result["x"]
    assert isinstance(t, Template)
    assert t.source == "Hi ${ name }"
    assert t.parameters == ("name",)
    assert t.keypath == ("x",)
    assert t.schema == {"type": "string"}


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
            "x": {"type": "template", "schema": inner, "parameters": ["name"]}
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
            "x": {"type": "template", "schema": inner, "parameters": ["n"]}
        },
    }
    cfg: ConfigurationDict = {"x": {"__template__": ["1", "${ n + 1 }"]}}

    result = resolve(cfg, schema)

    assert result["x"].source == ["1", "${ n + 1 }"]


def test_template_function_works_under_another_name():
    schema = {"type": "dict", "required_keys": {"x": STRING_TEMPLATE}}
    cfg: ConfigurationDict = {"x": {"__tmpl__": "Hi ${ name }"}}

    result = resolve(cfg, schema, functions={"tmpl": CORE_FUNCTIONS["template"]})

    assert result["x"].source == "Hi ${ name }"


# other functions on a template field ==================================================


def test_a_function_that_produces_a_template_is_accepted():
    # __if__ chooses a __template__ when the configuration is resolved; the chosen
    # template is kept as written
    schema = {
        "type": "dict",
        "required_keys": {"long": {"type": "boolean"}, "x": STRING_TEMPLATE},
    }
    cfg: ConfigurationDict = {
        "long": True,
        "x": {
            "__if__": {
                "condition": "${ long }",
                "then": {"__template__": "Hello, ${ name }!"},
                "else": {"__template__": "Hi ${ name }"},
            }
        },
    }

    result = resolve(cfg, schema)

    assert result["x"] == Template(
        "Hello, ${ name }!",
        schema={"type": "string"},
        parameters=["name"],
        keypath=["x"],
    )
    assert result["x"].evaluate({"name": "Justin"}) == "Hello, Justin!"


def test_a_let_around_a_template_is_accepted():
    schema = {"type": "dict", "required_keys": {"x": STRING_TEMPLATE}}
    cfg: ConfigurationDict = {
        "x": {
            "__let__": {
                "variables": {"unused": 1},
                "in": {"__template__": "Hi ${ name }"},
            }
        }
    }

    result = resolve(cfg, schema)

    assert result["x"].source == "Hi ${ name }"
    assert result["x"].parameters == ("name",)


def test_a_custom_function_returning_a_template_is_accepted():
    def make(args):
        return Template("Hi ${ name }")

    schema = {"type": "dict", "required_keys": {"x": STRING_TEMPLATE}}

    result = resolve({"x": {"__make__": {}}}, schema, functions={"make": make})

    # it takes the field's schema and parameters
    assert result["x"] == Template(
        "Hi ${ name }", schema={"type": "string"}, parameters=["name"], keypath=["x"]
    )


def test_a_template_from_elsewhere_is_structure_checked_under_the_field_schema():
    def make(args):
        return Template({"wrong": "key"})

    schema = {
        "type": "dict",
        "required_keys": {
            "x": {
                "type": "template",
                "schema": {
                    "type": "dict",
                    "required_keys": {"title": {"type": "string"}},
                },
                "parameters": [],
            }
        },
    }

    with raises(exceptions.ResolutionError) as exc:
        resolve({"x": {"__make__": {}}}, schema, functions={"make": make})

    assert exc.value.keypath == ("x", "title")


def test_a_function_that_does_not_produce_a_template_is_an_error():
    schema = {"type": "dict", "required_keys": {"x": STRING_TEMPLATE}}
    cfg: ConfigurationDict = {
        "x": {"__if__": {"condition": True, "then": "hello", "else": "bye"}}
    }

    with raises(exceptions.TemplateRequiredError) as exc:
        resolve(cfg, schema)

    assert exc.value.keypath == ("x",)


# the wrapper is required ==============================================================


@pytest.mark.parametrize(
    "value",
    [
        "Hi ${ name }",
        {"__raw__": "Hi ${ name }"},
    ],
    ids=["string", "other-function-call"],
)
def test_unwrapped_value_raises_template_required(value):
    schema = {
        "type": "dict",
        "required_keys": {
            "x": {
                "type": "template",
                "schema": {"type": "any"},
                "parameters": ["publication"],
            }
        },
    }
    cfg: ConfigurationDict = {"x": value}

    with raises(exceptions.TemplateRequiredError) as exc:
        resolve(cfg, schema)

    assert isinstance(exc.value, exceptions.ResolutionError)
    assert exc.value.keypath == ("x",)
    assert exc.value.parameters == ("publication",)
    assert exc.value.reason == (
        "This field is a template (parameters: publication), evaluated later. "
        'Write it as {"__template__": ...}.'
    )


def test_template_required_message_with_no_variables():
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

    with raises(exceptions.TemplateRequiredError) as exc:
        resolve({"x": "hello"}, schema)

    assert exc.value.parameters == ()
    assert "(parameters: none)" in exc.value.reason


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
    assert t.parameters == ("name",)
    assert t.keypath == ("x",)


def test_absent_template_with_dict_default_is_kept_as_written():
    inner = {
        "type": "dict",
        "required_keys": {"title": {"type": "string"}, "count": {"type": "integer"}},
    }
    field = {
        "type": "template",
        "schema": inner,
        "parameters": ["name"],
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
                "parameters": [],
            }
        },
    }

    result = resolve({"x": {"__template__": None}}, schema)

    assert isinstance(result["x"], Template)
    assert result["x"].source is None


# Template objects as input ============================================================


def test_template_given_to_another_field_is_a_shape_error():
    t = Template("Hi")
    schema = {"type": "dict", "required_keys": {"x": {"type": "dict"}}}

    with raises(exceptions.ResolutionError) as exc:
        resolve({"x": t}, schema)  # type: ignore[dict-item]

    assert exc.value.keypath == ("x",)
    assert exc.value.reason == "Expected a dict, but got a template."


def test_resolving_the_output_again_leaves_templates_alone():
    inner = {"type": "dict", "required_keys": {"title": {"type": "string"}}}
    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "template", "schema": inner, "parameters": ["name"]},
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


# wrappers on fields that are not templates ============================================


@pytest.mark.parametrize(
    "field_schema",
    [
        {"type": "string"},
        {"type": "dict", "required_keys": {"a": {"type": "string"}}},
    ],
    ids=["string", "dict"],
)
def test_wrapper_on_a_field_that_is_not_a_template_is_unexpected(field_schema):
    schema = {"type": "dict", "required_keys": {"x": field_schema}}
    cfg: ConfigurationDict = {"x": {"__template__": "Hi ${ name }"}}

    with raises(exceptions.UnexpectedTemplateError) as exc:
        resolve(cfg, schema)

    assert isinstance(exc.value, exceptions.ResolutionError)
    assert exc.value.keypath == ("x",)
    assert exc.value.enclosing is None
    assert exc.value.reason == (
        "This field is not a template: it is evaluated now. "
        "Remove the __template__ wrapper."
    )


def test_wrapper_at_the_root_that_is_not_a_template_is_unexpected():
    with raises(exceptions.UnexpectedTemplateError) as exc:
        resolve({"__template__": "Hi ${ name }"}, {"type": "string"})

    assert exc.value.keypath == ()


def test_wrapper_on_an_any_field_is_a_template():
    schema = {"type": "dict", "required_keys": {"x": {"type": "any"}}}
    cfg: ConfigurationDict = {"x": {"__template__": {"a": "Hi ${ name }"}}}

    result = resolve(cfg, schema)

    t = result["x"]
    assert isinstance(t, Template)
    assert t.source == {"a": "Hi ${ name }"}
    assert t.schema == {"type": "any"}
    assert t.parameters == ()
    assert t.keypath == ("x",)


# invalid template schemas =============================================================


@pytest.mark.parametrize("missing", ["schema", "parameters"])
def test_static_template_schema_missing_a_key_is_an_invalid_schema(missing):
    field = dict(STRING_TEMPLATE)
    del field[missing]
    schema = {"type": "dict", "required_keys": {"x": field}}

    with raises(exceptions.InvalidSchemaError) as exc:
        resolve({"x": {"__template__": "Hi"}}, schema)

    assert missing in str(exc.value)
