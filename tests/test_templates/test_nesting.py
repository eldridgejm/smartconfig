"""Tests of templates inside templates."""

import copy
from typing import Any

from pytest import raises

from smartconfig import exceptions, resolve, validate_schema
from smartconfig.types import ConfigurationDict, Template


# an activity made once per publication, with links made once per video. "links"
# is a template inside the "activity" template
LINK: dict[str, Any] = {
    "type": "dict",
    "required_keys": {"text": {"type": "string"}, "url": {"type": "string"}},
}

ACTIVITY: dict[str, Any] = {
    "type": "dict",
    "required_keys": {
        "title": {"type": "string"},
        "for_each_link": {"type": "template", "schema": LINK, "parameters": ["link"]},
    },
}

SCHEMA: dict[str, Any] = {
    "type": "dict",
    "required_keys": {
        "activity": {
            "type": "template",
            "schema": ACTIVITY,
            "parameters": ["publication"],
        }
    },
}

LINK_VALUE: dict[str, Any] = {
    "text": "${ link.title } (lecture ${ publication.number })",
    "url": "${ link.url }",
}

ACTIVITY_VALUE: dict[str, Any] = {
    "title": "Lecture ${ publication.number }",
    "for_each_link": {"__template__": LINK_VALUE},
}

CONFIG: dict[str, Any] = {"activity": {"__template__": ACTIVITY_VALUE}}


def template_schema(inner: Any, parameters: list[str]) -> dict[str, Any]:
    """A dict schema whose only key, "x", is a template field."""
    return {
        "type": "dict",
        "required_keys": {
            "x": {"type": "template", "schema": inner, "parameters": parameters}
        },
    }


# evaluating ===========================================================================


def test_evaluating_the_outer_template_gives_the_inner_one_as_a_template():
    result = resolve(CONFIG, SCHEMA)

    activity = result["activity"].evaluate({"publication": {"number": 3}})

    assert activity["title"] == "Lecture 3"
    links = activity["for_each_link"]
    assert isinstance(links, Template)
    assert links.source == LINK_VALUE
    assert links.schema == LINK


def test_the_inner_template_sees_the_outer_parameters():
    result = resolve(CONFIG, SCHEMA)
    activity = result["activity"].evaluate({"publication": {"number": 3}})

    link = activity["for_each_link"].evaluate(
        {"link": {"title": "Part 1", "url": "https://a"}}
    )

    assert link == {"text": "Part 1 (lecture 3)", "url": "https://a"}


def test_each_outer_evaluation_gives_an_inner_template_with_its_own_values():
    result = resolve(CONFIG, SCHEMA)
    first = result["activity"].evaluate({"publication": {"number": 1}})
    second = result["activity"].evaluate({"publication": {"number": 2}})
    link = {"link": {"title": "Part 1", "url": "https://a"}}

    assert first["for_each_link"].evaluate(link)["text"] == "Part 1 (lecture 1)"
    assert second["for_each_link"].evaluate(link)["text"] == "Part 1 (lecture 2)"


def test_the_inner_template_takes_only_its_own_parameters():
    result = resolve(CONFIG, SCHEMA)
    activity = result["activity"].evaluate({"publication": {"number": 3}})
    links = activity["for_each_link"]

    with raises(exceptions.ResolutionError) as exc:
        links.evaluate({"link": {"title": "a", "url": "b"}, "publication": {}})

    assert links.parameters == ("link",)
    assert exc.value.reason == (
        "Unexpected parameters: publication. This template's parameters: link."
    )


def test_templates_nest_to_any_depth():
    innermost = {"type": "template", "schema": {"type": "string"}, "parameters": ["c"]}
    middle = {
        "type": "dict",
        "required_keys": {
            "y": {
                "type": "template",
                "schema": {"type": "dict", "required_keys": {"z": innermost}},
                "parameters": ["b"],
            }
        },
    }
    cfg: ConfigurationDict = {
        "x": {
            "__template__": {
                "y": {"__template__": {"z": {"__template__": "${ a }${ b }${ c }"}}}
            }
        }
    }

    result = resolve(cfg, template_schema(middle, ["a"]))
    y = result["x"].evaluate({"a": 1})["y"]
    z = y.evaluate({"b": 2})["z"]

    assert z.parameters == ("c",)
    assert z.outer_parameters == {"a": 1, "b": 2}
    assert z.evaluate({"c": 3}) == "123"


def test_an_inner_template_does_not_see_the_outer_templates_keys():
    # the inner template is evaluated on its own, so "title" is not a name in it
    inner = {"type": "template", "schema": {"type": "string"}, "parameters": []}
    outer = {
        "type": "dict",
        "required_keys": {"title": {"type": "string"}, "footer": inner},
    }
    cfg: ConfigurationDict = {
        "x": {"__template__": {"title": "a", "footer": {"__template__": "${ title }"}}}
    }

    footer = resolve(cfg, template_schema(outer, []))["x"].evaluate()["footer"]

    with raises(exceptions.UndefinedNameError) as exc:
        footer.evaluate()

    assert exc.value.keypath == ("x", "footer")


def test_an_undefined_name_in_an_inner_template_lists_the_outer_parameters():
    cfg = copy.deepcopy(CONFIG)
    inner = cfg["activity"]["__template__"]["for_each_link"]["__template__"]
    inner["text"] = "${ lnk.title }"

    result = resolve(cfg, SCHEMA)
    activity = result["activity"].evaluate({"publication": {"number": 3}})

    with raises(exceptions.UndefinedNameError) as exc:
        activity["for_each_link"].evaluate({"link": {"title": "a", "url": "b"}})

    assert exc.value.keypath == ("activity", "for_each_link", "text")
    assert "link" in exc.value.available
    assert "publication" in exc.value.available


def test_an_outer_parameter_wins_over_a_global_in_the_inner_template():
    result = resolve(
        CONFIG, SCHEMA, global_variables={"publication": {"number": 99}, "g": 1}
    )
    activity = result["activity"].evaluate({"publication": {"number": 3}})

    link = activity["for_each_link"].evaluate({"link": {"title": "a", "url": "b"}})

    assert link["text"] == "a (lecture 3)"


def test_globals_are_visible_in_the_inner_template():
    cfg = copy.deepcopy(CONFIG)
    inner = cfg["activity"]["__template__"]["for_each_link"]["__template__"]
    inner["url"] = "${ site }/${ link.url }"

    result = resolve(cfg, SCHEMA, global_variables={"site": "https://s"})
    activity = result["activity"].evaluate({"publication": {"number": 3}})
    links = activity["for_each_link"]

    assert links.evaluate({"link": {"title": "a", "url": "b"}})["url"] == "https://s/b"
    assert links.outer_parameters == {"publication": {"number": 3}}


def test_an_error_in_an_inner_template_is_reported_where_it_was_written():
    cfg = copy.deepcopy(CONFIG)
    inner = cfg["activity"]["__template__"]["for_each_link"]["__template__"]
    inner["url"] = "${ link.url + 1 }"

    result = resolve(cfg, SCHEMA)
    activity = result["activity"].evaluate({"publication": {"number": 3}})

    with raises(exceptions.ResolutionError) as exc:
        activity["for_each_link"].evaluate({"link": {"title": "a", "url": "b"}})

    assert activity["for_each_link"].keypath == ("activity", "for_each_link")
    assert exc.value.keypath == ("activity", "for_each_link", "url")


def test_an_inner_template_chosen_by_a_call_while_evaluating_works():
    # the __if__ is evaluated with the outer template, and makes the inner one
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
            "body": {
                "__if__": {
                    "condition": "${ flag }",
                    "then": {"__template__": "a ${ section }"},
                    "else": {"__template__": "b ${ section }"},
                }
            }
        },
        schema=inner,
        parameters=["flag"],
        keypath=["x"],
    )

    body = template.evaluate({"flag": True})["body"]

    assert body.evaluate({"section": 1}) == "a 1"
    assert body.outer_parameters == {"flag": True}


def test_a_template_object_in_an_outer_source_carries_the_outer_values():
    # a Template can be put in a source only from Python, not from a config file
    inner = Template("${ a }${ b }", parameters=["b"], keypath=["y"])
    template = Template(
        {"k": inner},
        schema={
            "type": "dict",
            "required_keys": {
                "k": {
                    "type": "template",
                    "schema": {"type": "string"},
                    "parameters": ["b"],
                }
            },
        },
        parameters=["a"],
        keypath=["x"],
    )

    k = template.evaluate({"a": 1})["k"]

    assert k.keypath == ("x", "k")
    assert k.evaluate({"b": 2}) == "12"


def test_a_template_whose_schema_is_a_template_evaluates_to_a_template():
    inner = {"type": "template", "schema": {"type": "string"}, "parameters": ["b"]}
    cfg: ConfigurationDict = {"x": {"__template__": {"__template__": "${ a }${ b }"}}}

    result = resolve(cfg, template_schema(inner, ["a"]))
    curried = result["x"].evaluate({"a": 1})

    assert isinstance(curried, Template)
    assert curried.evaluate({"b": 2}) == "12"


def test_the_default_of_an_inner_template_field_is_a_template():
    links = {"type": "template", "schema": {"type": "string"}, "parameters": ["b"]}
    outer = {
        "type": "dict",
        "optional_keys": {"links": {**links, "default": "${ a }${ b }"}},
    }
    cfg: ConfigurationDict = {"x": {"__template__": {}}}

    result = resolve(cfg, template_schema(outer, ["a"]))

    assert result["x"].evaluate({"a": 1})["links"].evaluate({"b": 2}) == "12"


def test_a_wrapper_on_an_any_field_inside_a_template_carries_the_outer_values():
    cfg: ConfigurationDict = {"x": {"__template__": {"a": {"__template__": "${ n }"}}}}

    result = resolve(cfg, template_schema({"type": "any"}, ["n"]))
    a = result["x"].evaluate({"n": 5})["a"]

    assert a.parameters == ()
    assert a.evaluate() == "5"


# checks when the configuration is resolved ============================================


def test_the_inner_value_is_checked_when_the_configuration_is_resolved():
    cfg = copy.deepcopy(CONFIG)
    del cfg["activity"]["__template__"]["for_each_link"]["__template__"]["url"]

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, SCHEMA)

    assert exc.value.keypath == ("activity", "for_each_link", "url")
    assert exc.value.reason == 'Dictionary is missing required key "url".'


def test_a_value_inside_a_template_inside_a_template_is_checked_too():
    innermost = {
        "type": "template",
        "schema": {"type": "dict", "required_keys": {"q": {"type": "string"}}},
        "parameters": [],
    }
    middle = {
        "type": "dict",
        "required_keys": {
            "y": {
                "type": "template",
                "schema": {"type": "dict", "required_keys": {"z": innermost}},
                "parameters": [],
            }
        },
    }
    cfg: ConfigurationDict = {
        "x": {"__template__": {"y": {"__template__": {"z": {"__template__": {}}}}}}
    }

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, template_schema(middle, []))

    assert exc.value.keypath == ("x", "y", "z", "q")


def test_a_dynamic_inner_schema_is_checked_when_the_configuration_is_resolved():
    def link_schema(cfg, keypath):
        return LINK

    schema = copy.deepcopy(SCHEMA)
    activity = schema["required_keys"]["activity"]["schema"]
    activity["required_keys"]["for_each_link"]["schema"] = link_schema
    cfg = copy.deepcopy(CONFIG)
    del cfg["activity"]["__template__"]["for_each_link"]["__template__"]["url"]

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema)

    assert exc.value.keypath == ("activity", "for_each_link", "url")


def test_a_missing_wrapper_on_an_inner_template_is_an_error():
    cfg = copy.deepcopy(CONFIG)
    activity = cfg["activity"]["__template__"]
    activity["for_each_link"] = activity["for_each_link"]["__template__"]

    with raises(exceptions.TemplateRequiredError) as exc:
        resolve(cfg, SCHEMA)

    assert exc.value.keypath == ("activity", "for_each_link")
    assert exc.value.parameters == ("link",)


def test_a_wrapper_on_a_field_inside_a_template_that_is_not_a_template_is_an_error():
    cfg = copy.deepcopy(CONFIG)
    cfg["activity"]["__template__"]["title"] = {"__template__": "a"}

    with raises(exceptions.UnexpectedTemplateError) as exc:
        resolve(cfg, SCHEMA)

    assert exc.value.keypath == ("activity", "title")
    assert exc.value.enclosing == ("activity",)
    assert exc.value.reason == (
        "This field is not a template: it is evaluated now. "
        "Remove the __template__ wrapper."
    )


def test_a_wrapper_on_a_field_that_is_not_a_template_names_the_innermost_template():
    cfg = copy.deepcopy(CONFIG)
    inner = cfg["activity"]["__template__"]["for_each_link"]["__template__"]
    inner["url"] = {"__template__": "a"}

    with raises(exceptions.UnexpectedTemplateError) as exc:
        resolve(cfg, SCHEMA)

    assert exc.value.keypath == ("activity", "for_each_link", "url")
    assert exc.value.enclosing == ("activity", "for_each_link")


def test_a_use_inside_an_inner_template_is_expanded_when_resolved():
    schema = copy.deepcopy(SCHEMA)
    schema["required_keys"]["fragments"] = {"type": "any"}
    cfg = copy.deepcopy(CONFIG)
    cfg["fragments"] = {"url": {"__template__": "${ link.url }"}}
    inner = cfg["activity"]["__template__"]["for_each_link"]["__template__"]
    inner["url"] = {"__use__": "fragments.url"}

    result = resolve(cfg, schema)

    expected = LINK_VALUE
    assert result["activity"].source["for_each_link"]["__template__"] == expected


def test_a_use_as_the_value_of_an_inner_template_field_is_an_error():
    # the __use__ is expanded where it stands, which leaves the inner field without
    # a wrapper; writing the __use__ inside a __template__ is what works
    schema = copy.deepcopy(SCHEMA)
    schema["required_keys"]["fragments"] = {"type": "any"}
    cfg = copy.deepcopy(CONFIG)
    cfg["fragments"] = {"link": ACTIVITY_VALUE["for_each_link"]}
    cfg["activity"]["__template__"]["for_each_link"] = {"__use__": "fragments.link"}

    with raises(exceptions.TemplateRequiredError) as exc:
        resolve(cfg, schema)

    assert exc.value.keypath == ("activity", "for_each_link")
    assert exc.value.reason == (
        "This field is a template inside a template, so a __use__ here is "
        "replaced by the value it copies, which leaves the field without its "
        'wrapper. Write it as {"__template__": {"__use__": ...}}.'
    )


def test_a_use_inside_a_wrapper_on_an_inner_template_field_works():
    schema = copy.deepcopy(SCHEMA)
    schema["required_keys"]["fragments"] = {"type": "any"}
    cfg = copy.deepcopy(CONFIG)
    cfg["fragments"] = {"link": ACTIVITY_VALUE["for_each_link"]}
    activity = cfg["activity"]["__template__"]
    activity["for_each_link"] = {"__template__": {"__use__": "fragments.link"}}

    result = resolve(cfg, schema)
    links = result["activity"].evaluate({"publication": {"number": 3}})

    link = links["for_each_link"].evaluate({"link": {"title": "a", "url": "b"}})
    assert link == {"text": "a (lecture 3)", "url": "b"}


def test_a_use_whose_target_is_inside_a_template_is_an_error():
    # before the outer template is evaluated, there is no inner template to copy
    schema = copy.deepcopy(SCHEMA)
    schema["required_keys"]["other"] = {
        "type": "template",
        "schema": LINK,
        "parameters": ["link"],
    }
    cfg = copy.deepcopy(CONFIG)
    cfg["other"] = {"__use__": "activity.for_each_link"}

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema)

    assert exc.value.keypath == ("other",)
    assert exc.value.reason == "Keypath 'activity.for_each_link' does not exist."


# names ================================================================================


def test_an_inner_parameter_named_like_an_outer_one_is_an_invalid_schema():
    schema = copy.deepcopy(SCHEMA)
    activity = schema["required_keys"]["activity"]["schema"]
    activity["required_keys"]["for_each_link"]["parameters"] = ["publication"]

    with raises(exceptions.InvalidSchemaError) as exc:
        validate_schema(schema)

    assert exc.value.keypath == (
        "required_keys",
        "activity",
        "schema",
        "required_keys",
        "for_each_link",
        "parameters",
        "0",
    )


def test_an_inner_parameter_named_like_an_outer_one_is_found_at_any_depth():
    innermost = {"type": "template", "schema": {"type": "string"}, "parameters": ["a"]}
    middle = {
        "type": "template",
        "schema": {"type": "list", "element_schema": innermost},
        "parameters": ["b"],
    }
    schema = {
        "type": "template",
        "schema": {"type": "dict", "extra_keys_schema": middle},
        "parameters": ["a"],
    }

    with raises(exceptions.InvalidSchemaError) as exc:
        validate_schema(schema)

    assert exc.value.keypath == (
        "schema",
        "extra_keys_schema",
        "schema",
        "element_schema",
        "parameters",
        "0",
    )


def test_an_inner_parameter_named_like_an_outer_one_behind_a_dynamic_schema():
    # the inner schema is only known when the configuration is resolved
    def activity_schema(cfg, keypath):
        inner = copy.deepcopy(ACTIVITY)
        inner["required_keys"]["for_each_link"]["parameters"] = ["publication"]
        return inner

    schema = copy.deepcopy(SCHEMA)
    schema["required_keys"]["activity"]["schema"] = activity_schema

    with raises(exceptions.ResolutionError) as exc:
        resolve(CONFIG, schema)

    assert exc.value.keypath == ("activity", "for_each_link")
    assert exc.value.reason == (
        '"publication" is a parameter of this template and of a template around '
        "it. A template inside a template sees the parameters of the templates "
        "around it, so the name is ambiguous. Rename one of them."
    )


def test_an_inner_parameter_named_like_an_outer_one_when_evaluating():
    # a Template made in Python is not checked when the configuration is resolved
    template = Template(
        {"body": {"__template__": "${ a }"}},
        schema={
            "type": "dict",
            "required_keys": {
                "body": {
                    "type": "template",
                    "schema": {"type": "string"},
                    "parameters": ["a"],
                }
            },
        },
        parameters=["a"],
        keypath=["x"],
    )

    with raises(exceptions.ResolutionError) as exc:
        template.evaluate({"a": 1})

    assert exc.value.keypath == ("x", "body")


def test_an_inner_key_named_like_an_outer_parameter_is_an_invalid_schema():
    schema = copy.deepcopy(SCHEMA)
    activity = schema["required_keys"]["activity"]["schema"]
    link = activity["required_keys"]["for_each_link"]["schema"]
    link["required_keys"]["publication"] = {"type": "string"}

    with raises(exceptions.InvalidSchemaError) as exc:
        validate_schema(schema)

    assert exc.value.keypath == (
        "required_keys",
        "activity",
        "schema",
        "required_keys",
        "for_each_link",
        "schema",
        "required_keys",
        "publication",
    )


def test_an_inner_key_named_like_an_outer_parameter_behind_a_dynamic_schema():
    def link_schema(cfg, keypath):
        return {"type": "dict", "extra_keys_schema": {"type": "string"}}

    schema = copy.deepcopy(SCHEMA)
    activity = schema["required_keys"]["activity"]["schema"]
    activity["required_keys"]["for_each_link"]["schema"] = link_schema
    cfg = copy.deepcopy(CONFIG)
    inner = cfg["activity"]["__template__"]["for_each_link"]["__template__"]
    inner["publication"] = "x"

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema)

    assert exc.value.keypath == ("activity", "for_each_link", "publication")
    assert exc.value.reason == (
        '"publication" is both a key of this template and a parameter of a '
        "template around it. A template's keys can be referenced by name, like "
        "the parameters it sees, so the name is ambiguous. Rename the key or the "
        "parameter."
    )


# adopting =============================================================================


def test_an_inner_template_passed_to_resolve_keeps_its_outer_values():
    # adopted under another field, it is rebuilt from its source, and keeps the
    # values it carries
    result = resolve(CONFIG, SCHEMA)
    links = result["activity"].evaluate({"publication": {"number": 3}})
    schema = template_schema(LINK, ["link"])

    adopted = resolve({"x": links["for_each_link"]}, schema)["x"]

    assert adopted.keypath == ("x",)
    assert adopted.outer_parameters == {"publication": {"number": 3}}
    link = adopted.evaluate({"link": {"title": "a", "url": "b"}})
    assert link["text"] == "a (lecture 3)"


def test_an_adopted_template_whose_values_clash_with_the_evaluation_is_an_error():
    inner = Template("${ a }", parameters=[], keypath=["y"], outer_parameters={"a": 1})
    template = Template(
        {"k": inner},
        schema={
            "type": "dict",
            "required_keys": {
                "k": {
                    "type": "template",
                    "schema": {"type": "string"},
                    "parameters": [],
                }
            },
        },
        parameters=["a"],
        keypath=["x"],
    )

    with raises(exceptions.ResolutionError) as exc:
        template.evaluate({"a": 2})

    assert exc.value.keypath == ("x", "k")
