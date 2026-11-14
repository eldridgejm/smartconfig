"""Tests of where __use__ finds its target: wherever a ${...} reference would."""

from pytest import raises

from smartconfig import Template, exceptions, resolve
from smartconfig.types import ConfigurationDict, Schema

# a template defined outside the document, as an application might pass in a resolved
# configuration's templates as a global variable
HEADING = Template("Lecture: ${ this.metadata.title }")

LECTURE_SCHEMA: Schema = {
    "type": "dict",
    "required_keys": {
        "this": {
            "type": "dict",
            "required_keys": {
                "metadata": {
                    "type": "dict",
                    "required_keys": {
                        "title": {"type": "string"},
                        "heading": {"type": "string"},
                    },
                }
            },
        }
    },
}


# global variables =====================================================================


def test_target_can_be_a_global_variable_and_names_resolve_where_pasted():
    cfg: ConfigurationDict = {
        "this": {
            "metadata": {
                "title": "Introduction",
                "heading": {"__use__": "vars.heading"},
            }
        }
    }

    result = resolve(
        cfg, LECTURE_SCHEMA, global_variables={"vars": {"heading": HEADING}}
    )

    assert result["this"]["metadata"]["heading"] == "Lecture: Introduction"


def test_global_target_with_overrides():
    template = Template({"title": "${ name }", "points": "10"})
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "name": {"type": "string"},
            "page": {
                "type": "dict",
                "required_keys": {
                    "title": {"type": "string"},
                    "points": {"type": "integer"},
                },
            },
        },
    }
    cfg: ConfigurationDict = {
        "name": "hw",
        "page": {"__use__": {"template": "vars.page", "overrides": {"points": "20"}}},
    }

    result = resolve(cfg, schema, global_variables={"vars": {"page": template}})

    assert result["page"] == {"title": "hw", "points": 20}


def test_global_target_as_the_value_of_a_template_field():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "x": {
                "type": "template",
                "schema": {"type": "string"},
                "parameters": ["name"],
            }
        },
    }
    cfg: ConfigurationDict = {"x": {"__use__": "vars.greeting"}}

    result = resolve(
        cfg, schema, global_variables={"vars": {"greeting": Template("Hi ${ name }")}}
    )

    assert result["x"].source == "Hi ${ name }"
    assert result["x"].evaluate({"name": "Justin"}) == "Hi Justin"


def test_global_target_inside_a_template_value():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "x": {
                "type": "template",
                "schema": {"type": "list", "element_schema": {"type": "string"}},
                "parameters": ["name"],
            }
        },
    }
    cfg: ConfigurationDict = {
        "x": {"__template__": ["first", {"__use__": "vars.greeting"}]}
    }

    result = resolve(
        cfg, schema, global_variables={"vars": {"greeting": Template("Hi ${ name }")}}
    )

    assert result["x"].source == ["first", "Hi ${ name }"]


def test_a_document_key_shadows_a_global_of_the_same_name():
    schema: Schema = {"type": "any"}
    cfg: ConfigurationDict = {
        "vars": {"greeting": {"__template__": "from the document"}},
        "result": {"__use__": "vars.greeting"},
    }

    result = resolve(
        cfg,
        schema,
        global_variables={"vars": {"greeting": Template("from the globals")}},
    )

    assert result["result"] == "from the document"


def test_a_global_that_is_not_a_template_is_an_error():
    cfg: ConfigurationDict = {"result": {"__use__": "vars.greeting"}}

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, {"type": "any"}, global_variables={"vars": {"greeting": "hi"}})

    assert exc.value.keypath == ("result",)
    assert "must be a template" in exc.value.reason


def test_a_missing_global_key_is_an_error():
    cfg: ConfigurationDict = {"result": {"__use__": "vars.nope"}}

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, {"type": "any"}, global_variables={"vars": {"greeting": HEADING}})

    assert exc.value.reason == "Keypath 'vars.nope' does not exist."


# the other places a ${...} reference looks ============================================


def test_target_can_be_a_local_variable():
    cfg: ConfigurationDict = {
        "result": {
            "__let__": {
                "variables": {"t": {"__template__": "from a local"}},
                "in": {"__use__": "t"},
            }
        }
    }

    result = resolve(cfg, {"type": "any"})

    assert result["result"] == "from a local"


def test_target_can_be_reached_through_inject_root_as():
    cfg: ConfigurationDict = {
        "templates": {"greeting": {"__template__": "hello"}},
        "result": {"__use__": "root.templates.greeting"},
    }

    result = resolve(cfg, {"type": "any"}, inject_root_as="root")

    assert result["result"] == "hello"


def test_target_can_be_reached_through_a_list_index():
    cfg: ConfigurationDict = {
        "templates": [{"__template__": "zero"}, {"__template__": "one"}],
        "result": {"__use__": "templates.1"},
    }

    result = resolve(cfg, {"type": "any"})

    assert result["result"] == "one"


def test_target_can_be_reached_through_a_python_attribute():
    class Holder:
        greeting = Template("from an attribute")

    cfg: ConfigurationDict = {"result": {"__use__": "holder.greeting"}}

    result = resolve(cfg, {"type": "any"}, global_variables={"holder": Holder()})

    assert result["result"] == "from an attribute"
