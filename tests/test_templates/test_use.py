"""Tests of __use__ on template fields and inside templates (run at load)."""

from pytest import raises

from smartconfig import CORE_FUNCTIONS, Template, exceptions, resolve
from smartconfig.types import ConfigurationDict


# a configuration with a schema-less "fragments" section and a template field "x" of
# a "page" (a title and a body), with the variable "name"
SCHEMA = {
    "type": "dict",
    "required_keys": {
        "fragments": {"type": "any"},
        "x": {
            "type": "template",
            "schema": {
                "type": "dict",
                "required_keys": {
                    "title": {"type": "string"},
                    "body": {"type": "any"},
                },
            },
            "parameters": ["name"],
        },
    },
}


# __use__ as the value of a template field =============================================


def test_use_as_the_value_of_a_template_field_gives_the_fragment_as_written():
    cfg: ConfigurationDict = {
        "fragments": {
            "page": {"__template__": {"title": "${ name }", "body": "${ name }!"}}
        },
        "x": {"__use__": "fragments.page"},
    }

    result = resolve(cfg, SCHEMA)

    assert isinstance(result["x"], Template)
    assert result["x"].source == {"title": "${ name }", "body": "${ name }!"}
    assert result["x"].keypath == ("x",)
    assert result["x"].evaluate({"name": "hw"}) == {"title": "hw", "body": "hw!"}


def test_use_with_overrides_is_merged_as_written():
    cfg: ConfigurationDict = {
        "fragments": {
            "page": {
                "__template__": {
                    "title": "${ name }",
                    "body": {"a": "1", "b": "2"},
                }
            }
        },
        "x": {
            "__use__": {
                "template": "fragments.page",
                "overrides": {"body": {"b": "${ name }"}},
            }
        },
    }

    result = resolve(cfg, SCHEMA)

    assert result["x"].source == {
        "title": "${ name }",
        "body": {"a": "1", "b": "${ name }"},
    }


# __use__ inside a template's value ====================================================


def test_use_in_a_list_inside_a_template_is_expanded_at_load():
    cfg: ConfigurationDict = {
        "fragments": {"part": {"__template__": {"p": "${ name }"}}},
        "x": {
            "__template__": {
                "title": "t",
                "body": [1, {"__use__": "fragments.part"}],
            }
        },
    }

    result = resolve(cfg, SCHEMA)

    assert result["x"].source == {"title": "t", "body": [1, {"p": "${ name }"}]}


def test_use_in_another_function_input_inside_a_template_is_expanded_at_load():
    # the __use__ is expanded; the __if__ around it is kept as written, to be
    # evaluated with the template
    cfg: ConfigurationDict = {
        "fragments": {"part": {"__template__": {"p": "${ name }"}}},
        "x": {
            "__template__": {
                "title": "t",
                "body": {
                    "__if__": {
                        "condition": True,
                        "then": {"__use__": "fragments.part"},
                    }
                },
            }
        },
    }

    result = resolve(cfg, SCHEMA)

    assert result["x"].source == {
        "title": "t",
        "body": {"__if__": {"condition": True, "then": {"p": "${ name }"}}},
    }


def test_a_fragment_that_uses_another_fragment_is_expanded():
    cfg: ConfigurationDict = {
        "fragments": {
            "part": {"__template__": {"p": "${ name }"}},
            "page": {
                "__template__": {"title": "t", "body": {"__use__": "fragments.part"}}
            },
        },
        "x": {"__use__": "fragments.page"},
    }

    result = resolve(cfg, SCHEMA)

    assert result["x"].source == {"title": "t", "body": {"p": "${ name }"}}


def test_the_target_can_be_reached_through_a_function_call():
    cfg: ConfigurationDict = {
        "fragments": {
            "__if__": {
                "condition": True,
                "then": {"page": {"__template__": {"title": "t", "body": "b"}}},
                "else": {},
            }
        },
        "x": {"__use__": "fragments.page"},
    }

    result = resolve(cfg, SCHEMA)

    assert result["x"].source == {"title": "t", "body": "b"}


# errors ===============================================================================


def test_the_expanded_value_is_structure_checked():
    cfg: ConfigurationDict = {
        "fragments": {"page": {"__template__": {"body": "b"}}},
        "x": {"__use__": "fragments.page"},
    }

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, SCHEMA)

    assert exc.value.keypath == ("x", "title")
    assert exc.value.reason == 'Dictionary is missing required key "title".'


def test_fragments_that_use_each_other_are_a_circular_reference():
    cfg: ConfigurationDict = {
        "fragments": {
            "a": {"__template__": {"__use__": "fragments.b"}},
            "b": {"__template__": {"__use__": "fragments.a"}},
        },
        "x": {"__use__": "fragments.a"},
    }

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, SCHEMA)

    assert exc.value.reason == "Circular reference."


def test_use_errors_are_raised_at_load():
    cfg: ConfigurationDict = {
        "fragments": {"plain": {"a": 1}},
        "x": {"__template__": {"title": "t", "body": {"__use__": "fragments.plain"}}},
    }

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, SCHEMA)

    assert exc.value.keypath == ("x", "body")
    assert (
        exc.value.reason
        == "The target of 'use' must be a template (written with __template__)."
    )


def test_an_invalid_function_call_in_a_template_is_still_an_error_at_load():
    cfg: ConfigurationDict = {
        "fragments": {},
        "x": {"__template__": {"title": "t", "body": {"__nope__": 1}}},
    }

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, SCHEMA)

    assert exc.value.keypath == ("x", "body")
    assert exc.value.reason.startswith("Invalid function call")


def test_use_in_a_template_at_the_root_has_no_target():
    schema = {"type": "template", "schema": {"type": "any"}, "parameters": []}

    with raises(exceptions.ResolutionError) as exc:
        resolve({"__use__": "x"}, schema)

    assert exc.value.keypath == ()
    assert exc.value.reason == "Keypath 'x' does not exist."


def test_use_under_another_name_is_expanded_inside_a_template():
    # the resolver recognizes the use function itself, not its name
    cfg: ConfigurationDict = {
        "fragments": {"part": {"__tmpl__": {"p": "${ name }"}}},
        "x": {"__tmpl__": {"title": "t", "body": {"__copy__": "fragments.part"}}},
    }

    result = resolve(
        cfg,
        SCHEMA,
        functions={
            "tmpl": CORE_FUNCTIONS["template"],
            "copy": CORE_FUNCTIONS["use"],
        },
    )

    assert result["x"].source == {"title": "t", "body": {"p": "${ name }"}}
