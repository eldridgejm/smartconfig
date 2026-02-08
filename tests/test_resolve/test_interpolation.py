"""Tests for string interpolation."""

from smartconfig import resolve, exceptions, CORE_FUNCTIONS
from smartconfig.types import (
    ConfigurationDict,
    Schema,
)

from pytest import raises


def test_interpolation_of_other_dictionary_entries_same_level():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {"foo": "hello", "bar": "testing ${foo}"}

    # when
    result = resolve(cfg, schema)

    # then
    assert result["bar"] == "testing hello"


def test_interpolation_of_a_high_node_referencing_a_deeper_node():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {
                "type": "dict",
                "required_keys": {"baz": {"type": "string"}},
            },
        },
    }

    cfg: ConfigurationDict = {"foo": "testing ${bar.baz}", "bar": {"baz": "this"}}

    # when
    result = resolve(cfg, schema)

    # then
    assert result["foo"] == "testing this"


def test_interpolation_of_a_deep_node_referencing_a_higher_node():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {
                "type": "dict",
                "required_keys": {"baz": {"type": "string"}},
            },
        },
    }

    cfg: ConfigurationDict = {"foo": "testing", "bar": {"baz": "${foo} this"}}

    # when
    result = resolve(cfg, schema)

    # then
    assert result["foo"] == "testing"
    assert result["bar"]["baz"] == "testing this"


def test_interpolation_can_reference_list_elements():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {
                "type": "list",
                "element_schema": {"type": "string"},
            },
        },
    }

    cfg: ConfigurationDict = {
        "foo": "testing ${bar.1}",
        "bar": ["this", "that", "the other"],
    }

    # when
    result = resolve(cfg, schema)

    # then
    assert result["foo"] == "testing that"


def test_chain_of_multiple_interpolations():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
            "baz": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {
        "foo": "this",
        "bar": "testing ${foo}",
        "baz": "now ${bar}",
    }

    # when
    result = resolve(cfg, schema)

    # then
    assert result["foo"] == "this"
    assert result["bar"] == "testing this"
    assert result["baz"] == "now testing this"


def test_raises_if_self_reference_detected():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {
        "foo": "${foo}",
    }

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema)

    assert str(exc.value) == 'Cannot resolve keypath "foo": Circular reference.'


def test_raises_if_cyclical_reference_detected():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
            "baz": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {
        "foo": "${baz}",
        "bar": "${foo}",
        "baz": "${bar}",
    }

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema)

    assert str(exc.value) == 'Cannot resolve keypath "foo": Circular reference.'


def test_interpolation_can_use_jinja_to_loop_over_list():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "list", "element_schema": {"type": "string"}},
            "bar": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {
        "foo": ["this", "that", "the other"],
        "bar": "{% for item in foo %}item: ${ item } {% endfor %}",
    }

    # when
    result = resolve(cfg, schema)

    # then
    assert result["bar"] == "item: this item: that item: the other "


def test_interpolation_can_use_jinja_to_loop_over_dict_keys_explicitly():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "dict", "extra_keys_schema": {"type": "string"}},
            "bar": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {
        "foo": {"this": "that", "the": "other"},
        "bar": "{% for key in foo.keys() | sort %}key: ${ key } {% endfor %}",
    }

    # when
    result = resolve(cfg, schema)

    # then
    assert result["bar"] == "key: the key: this "


def test_interpolation_can_use_jinja_to_loop_over_dict_keys_implicitly():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "dict", "extra_keys_schema": {"type": "string"}},
            "bar": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {
        "foo": {"this": "that", "the": "other"},
        "bar": "{% for key in foo | sort %}key: ${ key } {% endfor %}",
    }

    # when
    result = resolve(cfg, schema)

    # then
    assert result["bar"] == "key: the key: this "


def test_can_use_jinja_methods():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {
        "foo": "this",
        "bar": "testing ${foo.upper()}",
    }

    # when
    result = resolve(cfg, schema)

    # then
    assert result["foo"] == "this"
    assert result["bar"] == "testing THIS"


def test_can_use_builtin_jinja_function_range():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "integer"}, "bar": {"type": "string"}},
    }

    cfg: ConfigurationDict = {
        "foo": 3,
        "bar": "{% for i in range(foo) %}${ i }{% endfor %}",
    }

    # when
    result = resolve(cfg, schema)

    # then
    assert result["bar"] == "012"


def test_can_treat_floats_as_floats():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "float"},
            "bar": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {
        "foo": 3.00,
        "bar": "testing ${foo + 4}",
    }

    # when
    result = resolve(cfg, schema)

    # then
    assert result["foo"] == 3.0
    assert result["bar"] == "testing 7.0"


def test_jinja_arithmetic_with_global_variable():
    """Jinja2 can do arithmetic on a global variable inside ${...}."""
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "y": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {
        "y": "${x + 3}",
    }

    # when
    result = resolve(cfg, schema, global_variables={"x": 7})

    # then
    assert result["y"] == 10


def test_jinja_arithmetic_with_let_variable():
    """Jinja2 can do arithmetic on a __let__ variable inside ${...}."""
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "y": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {
        "__let__": {
            "variables": {"x": 7},
            "in": {
                "y": "${x + 3}",
            },
        }
    }

    # when
    result = resolve(cfg, schema, functions={"let": CORE_FUNCTIONS["let"]})

    # then
    assert result["y"] == 10


def test_interpolation_of_keys_with_dots():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "this": {
                "type": "dict",
                "required_keys": {
                    "foo.txt": {"type": "string"},
                    "bar": {"type": "string"},
                },
            }
        },
    }

    cfg: ConfigurationDict = {
        "this": {
            "foo.txt": "this",
            "bar": "testing ${this['foo.txt']}",
        }
    }

    # when
    result = resolve(cfg, schema)

    # then
    assert result["this"]["foo.txt"] == "this"
    assert result["this"]["bar"] == "testing this"


def test_interpolation_is_not_confused_by_different_jinja_syntax():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {
        "foo": "this",
        "bar": "testing ${foo} $[ that ]",
    }

    # when
    result = resolve(cfg, schema)

    # then
    assert result["foo"] == "this"
    assert result["bar"] == "testing this $[ that ]"


def test_interpolation_from_deeply_nested_list():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "publication_schema": {
                "type": "dict",
                "required_keys": {
                    "required_artifacts": {
                        "type": "list",
                        "element_schema": {"type": "string"},
                    },
                    "optional_artifacts": {
                        "type": "list",
                        "element_schema": {"type": "string"},
                    },
                },
            }
        },
    }

    cfg: ConfigurationDict = {
        "publication_schema": {
            "required_artifacts": [
                "foo",
                "bar",
                "${publication_schema.optional_artifacts.0}",
            ],
            "optional_artifacts": ["baz"],
        }
    }

    # when
    result = resolve(cfg, schema)

    # then
    assert result["publication_schema"]["required_artifacts"][2] == "baz"


def test_interpolate_entire_dict_raises_exception():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {
                "type": "dict",
                "required_keys": {"x": {"type": "integer"}, "y": {"type": "integer"}},
            },
            "bar": {
                "type": "dict",
                "required_keys": {"x": {"type": "integer"}, "y": {"type": "integer"}},
            },
        },
    }

    cfg: ConfigurationDict = {
        "foo": {"x": 1, "y": 2},
        "bar": "${foo}",
    }

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema)

    assert (
        str(exc.value)
        == 'Cannot resolve keypath "bar": No converter provided for type: "dict".'
    )


def test_interpolate_entire_dict_indirectly_raises_exception():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {
                "type": "dict",
                "required_keys": {"x": {"type": "integer"}, "y": {"type": "integer"}},
            },
            "bar": {
                "type": "dict",
                "required_keys": {"x": {"type": "integer"}, "y": {"type": "integer"}},
            },
            "baz": {"type": "integer"},
            "quux": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {
        "foo": {"x": 1, "y": 2},
        "bar": "${foo}",
        "baz": "${bar.y}",
        "quux": "${baz}",
    }

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema)

    assert 'No converter provided for type: "dict"' in str(exc.value)


def test_interpolate_entire_dict_indirectly_reverse_order_raises_exception():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {
                "type": "dict",
                "required_keys": {"x": {"type": "integer"}, "y": {"type": "integer"}},
            },
            "bar": {
                "type": "integer",
            },
            "baz": {
                "type": "dict",
                "required_keys": {"x": {"type": "integer"}, "y": {"type": "integer"}},
            },
            "quux": {
                "type": "dict",
                "required_keys": {"x": {"type": "integer"}, "y": {"type": "integer"}},
            },
        },
    }

    cfg: ConfigurationDict = {
        "foo": {"x": 1, "y": 2},
        "bar": "${baz.y}",
        "baz": "${quux}",
        "quux": "${foo}",
    }

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema)

    # then
    assert 'No converter provided for type: "dict"' in str(exc.value)


def test_interpolate_entire_list_raises_exception():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {
                "type": "list",
                "element_schema": {"type": "integer"},
            },
            "bar": {
                "type": "list",
                "element_schema": {"type": "integer"},
            },
        },
    }

    cfg: ConfigurationDict = {
        "foo": [1, 2],
        "bar": "${foo}",
    }

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema)

    # then
    assert 'No converter provided for type: "list"' in str(exc.value)
