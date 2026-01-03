import datetime

from smartconfig import resolve, exceptions, Prototype, NotRequired
from smartconfig.types import (
    Configuration,
    ConfigurationDict,
    ConfigurationList,
    Schema,
    DynamicSchema,
    RawString,
    RecursiveString,
    Function,
    FunctionArgs,
    UnresolvedDict,
    UnresolvedList,
    UnresolvedFunctionCall,
    KeyPath,
)

from pytest import raises


# basic ================================================================================


def test_raises_if_required_keys_are_missing():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "any"},
            "bar": {"type": "any"},
        },
    }

    cfg: ConfigurationDict = {"foo": 42}

    # when
    with raises(exceptions.ResolutionError) as excinfo:
        resolve(cfg, schema)

    assert excinfo.value.keypath == ("bar",)
    assert (
        str(excinfo.value)
        == 'Cannot resolve keypath "bar": Dictionary is missing required key "bar".'
    )


def test_raises_if_required_keys_are_missing_in_nested_dict():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {
                "type": "dict",
                "required_keys": {
                    "bar": {"type": "any"},
                },
            }
        },
    }

    cfg: ConfigurationDict = {"foo": {}}

    # when
    with raises(exceptions.ResolutionError) as excinfo:
        resolve(cfg, schema)

    assert excinfo.value.keypath == ("foo", "bar")
    assert (
        str(excinfo.value)
        == 'Cannot resolve keypath "foo.bar": Dictionary is missing required key "bar".'
    )


def test_raises_if_extra_keys_without_extra_keys_schema():
    # given
    schema: Schema = {"type": "dict", "required_keys": {}}

    cfg: ConfigurationDict = {"foo": 42}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema)

    assert (
        str(exc.value)
        == 'Cannot resolve keypath "foo": Dictionary contains unexpected extra key "foo".'
    )


def test_allows_extra_keys_with_extra_keys_schema():
    # given
    schema: Schema = {"type": "dict", "extra_keys_schema": {"type": "any"}}

    cfg: ConfigurationDict = {"foo": 42}

    # when
    result = resolve(cfg, schema)

    # then
    assert result["foo"] == 42


def test_fills_in_missing_value_with_default_if_provided():
    # given
    schema: Schema = {
        "type": "dict",
        "optional_keys": {"foo": {"default": 42, "type": "integer"}},
    }

    cfg: ConfigurationDict = {}

    # when
    result = resolve(cfg, schema)

    # then
    assert result["foo"] == 42


def test_allows_missing_keys_if_required_is_false():
    # given
    schema: Schema = {
        "type": "dict",
        "optional_keys": {
            "foo": {"type": "integer"},
            "bar": {
                "type": "integer",
            },
        },
    }

    cfg: ConfigurationDict = {"bar": 42}

    # when
    result = resolve(cfg, schema)

    # then
    assert result["bar"] == 42
    assert "foo" not in result


def test_list_of_dicts():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {
            "type": "dict",
            "required_keys": {"foo": {"type": "integer"}},
        },
    }

    cfg: ConfigurationList = [{"foo": 42}, {"foo": 10}]

    # when
    result = resolve(cfg, schema)

    # then
    assert result == [{"foo": 42}, {"foo": 10}]


# non-dictionary roots =================================================================


def test_lists_are_permitted_as_root_node():
    # given
    schema: Schema = {"type": "list", "element_schema": {"type": "integer"}}

    cfg: ConfigurationList = [1, 2, 3]

    # when
    result = resolve(cfg, schema)

    # then
    assert result == [1, 2, 3]


def test_values_are_permitted_as_root_node():
    # given
    schema: Schema = {
        "type": "integer",
    }

    cfg = "1 + 2"

    # when
    result = resolve(cfg, schema)

    # then
    assert result == 3


# interpolation ========================================================================


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


# converting ==============================================================================


def test_leafs_are_converted_into_expected_types():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "integer"}},
    }

    cfg: ConfigurationDict = {"foo": "42"}

    # when
    result = resolve(cfg, schema)

    # then
    assert result["foo"] == 42


def test_converting_occurs_after_interpolation():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {"foo": "42", "bar": "${foo}"}

    # when
    result = resolve(cfg, schema)

    # then
    assert result["foo"] == 42
    assert result["bar"] == 42


def test_converting_of_extra_dictionary_keys():
    # given
    schema: Schema = {"type": "dict", "extra_keys_schema": {"type": "integer"}}

    cfg: ConfigurationDict = {"foo": "42", "bar": "10"}

    # when
    result = resolve(cfg, schema)

    # then
    assert result["foo"] == 42
    assert result["bar"] == 10


def test_converting_of_list_elements():
    # given
    schema: Schema = {"type": "list", "element_schema": {"type": "integer"}}

    cfg: ConfigurationList = ["10", "25"]

    # when
    result = resolve(cfg, schema)

    # then
    assert result == [10, 25]


def test_raw_strings_resolve_to_raw_strings():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {"foo": "this", "bar": RawString("${foo}")}

    # when
    result = resolve(cfg, schema)

    # then
    assert isinstance(result["bar"], RawString)


def test_raw_strings_are_not_interpolated():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {"foo": "this", "bar": RawString("${foo}")}

    # when
    result = resolve(cfg, schema)

    # then
    assert result["bar"] == "${foo}"


def test_raw_strings_are_still_type_checked():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {"foo": "this", "bar": RawString("42")}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema)

    assert "Schema expected something other than a string" in str(exc.value)


def test_recursive_strings_resolve_to_regular_strings():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {"foo": "this", "bar": RecursiveString("testing ${foo}")}

    # when
    result = resolve(cfg, schema)

    # then
    assert isinstance(result["bar"], str) and not isinstance(
        result["bar"], RecursiveString
    )


def test_recursive_strings_are_interpolated_recursively():
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
        "foo": "hello",
        "bar": RawString("${foo} world"),
        "baz": RecursiveString("I said: ${bar}"),
    }

    # when
    result = resolve(cfg, schema)

    # then
    assert result == {
        "foo": "hello",
        "bar": "${foo} world",
        "baz": "I said: hello world",
    }


def test_raises_if_no_converter_provided_for_type():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "integer"}},
    }

    cfg: ConfigurationDict = {"foo": "42"}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, converters={})

    assert "No converter provided" in str(exc.value)


# "any" type ===========================================================================


def test_all_types_preserved_when_any_is_used():
    # given
    schema: Schema = {
        "type": "any",
    }

    cfg: ConfigurationDict = {
        "foo": "testing",
        "bar": {"x": 1, "y": 2},
        "baz": [1, 2, 3],
    }

    # when
    result = resolve(cfg, schema)

    # then
    assert result == cfg


def test_interpolation_occurs_when_any_is_used():
    # given
    schema: Schema = {
        "type": "any",
    }

    cfg: ConfigurationDict = {"foo": "testing", "bar": "${foo} this"}

    # when
    result = resolve(cfg, schema)

    # then
    assert result["bar"] == "testing this"


def test_converts_integers_to_strings_when_schema_calls_for_it():
    # given
    schema: Schema = {"type": "dict", "required_keys": {"foo": {"type": "string"}}}

    cfg: ConfigurationDict = {"foo": 42}

    # when
    result = resolve(cfg, schema)

    # then
    assert result["foo"] == "42"


def test_converts_strings_to_integers_when_schema_calls_for_it():
    # given
    schema: Schema = {"type": "dict", "required_keys": {"foo": {"type": "integer"}}}

    cfg: ConfigurationDict = {"foo": "42"}

    # when
    result = resolve(cfg, schema)

    # then
    assert result["foo"] == 42


def test_config_contains_datetimes_objects_type_is_left_alone():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "datetime"}},
    }

    cfg: ConfigurationDict = {"foo": datetime.datetime(2020, 1, 1)}

    # when
    result = resolve(cfg, schema)

    # then
    assert result["foo"] == datetime.datetime(2020, 1, 1)


# nullable =============================================================================


def test_dictionary_can_be_nullable():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "dict", "nullable": True}},
    }

    cfg: ConfigurationDict = {"foo": None}

    # when
    result = resolve(cfg, schema)

    # then
    assert result["foo"] is None


def test_list_can_be_nullable():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {
                "type": "list",
                "element_schema": {"type": "any"},
                "nullable": True,
            }
        },
    }

    cfg: ConfigurationDict = {"foo": None}

    # when
    result = resolve(cfg, schema)

    # then
    assert result["foo"] is None


def test_leaf_can_be_nullable():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "integer", "nullable": True}},
    }

    cfg: ConfigurationDict = {"foo": None}

    # when
    result = resolve(cfg, schema)

    # then
    assert result["foo"] is None


def test_error_is_raised_if_None_is_provided_but_value_is_not_nullable():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "integer"}},
    }

    cfg: ConfigurationDict = {"foo": None}

    # when
    with raises(exceptions.ResolutionError):
        resolve(cfg, schema)


def test_any_can_be_None_without_being_nullable():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "any"}},
    }

    cfg: ConfigurationDict = {"foo": None}

    # when
    result = resolve(cfg, schema)

    # then
    assert result["foo"] is None


# good exceptions ======================================================================


def test_exception_raised_when_referencing_an_undefined_key():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "string"}},
    }

    cfg: ConfigurationDict = {"foo": "${bar}"}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema)

    assert "'bar' is undefined" in str(exc.value)


def test_exception_has_correct_path_with_missing_key_in_nested_dict():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {
                "type": "dict",
                "required_keys": {"bar": {"type": "any"}},
            },
        },
    }

    cfg: ConfigurationDict = {"foo": {}}

    # when
    with raises(exceptions.ResolutionError) as excinfo:
        resolve(cfg, schema)

    assert excinfo.value.keypath == (
        "foo",
        "bar",
    )


def test_exception_has_correct_path_with_missing_key_in_nested_dict_within_list():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {
            "type": "dict",
            "required_keys": {
                "foo": {
                    "type": "integer",
                },
            },
        },
    }

    cfg: ConfigurationList = [
        {
            "foo": 10,
        },
        {"bar": 42},
    ]

    # when
    with raises(exceptions.ResolutionError) as excinfo:
        resolve(cfg, schema)

    assert excinfo.value.keypath == ("1", "foo")


def test_exception_raised_when_schema_includes_default_value_that_doesnt_match_type():
    # given
    schema: Schema = {
        "type": "dict",
        "optional_keys": {
            "foo": {"type": "integer", "default": "not an int"},
        },
    }

    cfg: ConfigurationDict = {}

    # when/then
    with raises(exceptions.ResolutionError) as excinfo:
        resolve(cfg, schema)

    assert "Cannot parse into int" in str(excinfo.value)


# preserve_type ========================================================================


def test_preserve_type():
    class UserDict(dict):
        something = 80

    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {
                "type": "dict",
                "required_keys": {"something": {"type": "integer"}},
            },
            "baz": {"type": "list", "element_schema": {"type": "integer"}},
        },
    }

    cfg = UserDict({"foo": 10, "bar": {"something": 20}, "baz": [1, 2, 3]})

    # when
    result = resolve(cfg, schema, preserve_type=True)

    # then
    assert result == cfg


# functions ============================================================================


def test_function_call_at_root():
    # given
    schema: Schema = {"type": "integer"}
    cfg: ConfigurationDict = {"__double__": 10}

    # when
    result = resolve(cfg, schema, functions={"double": lambda x: x.input * 2})  # type: ignore

    # then
    assert result == 20


def test_function_call_at_root_raises_if_circular_reference():
    # given
    schema: Schema = {"type": "integer"}
    cfg: ConfigurationDict = {"__double__": "${x}"}

    def double(args: FunctionArgs) -> int:
        assert isinstance(args.input, int)
        return args.input * 2

    # when
    with raises(exceptions.ResolutionError):
        resolve(cfg, schema, functions={"double": double})


def test_function_call_at_root_without_circular_reference():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {"x": {"type": "integer"}, "y": {"type": "integer"}},
    }

    def make_dict(args):
        return {"x": 10, "y": "${x}"}

    cfg: ConfigurationDict = {"__make_dict__": {}}

    # when
    result = resolve(cfg, schema, functions={"make_dict": make_dict})

    # then
    assert result == {"x": 10, "y": 10}


def test_function_call_in_dictionary():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {"foo": 6, "bar": {"__double__": 10}}

    # when
    result = resolve(cfg, schema, functions={"double": lambda args: args.input * 2})  # type: ignore

    # then
    assert result["bar"] == 20


def test_function_call_in_list():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "list", "element_schema": {"type": "integer"}},
        },
    }

    cfg: ConfigurationDict = {"foo": 6, "bar": [1, {"__double__": 10}, 3]}

    # when
    result = resolve(cfg, schema, functions={"double": lambda args: args.input * 2})  # type: ignore

    # then
    assert result["bar"] == [1, 20, 3]


def test_function_call_output_is_resolved_by_default_using_schema():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {"foo": 6, "bar": {"__add_one_to__": "10"}}

    # when
    result = resolve(
        cfg, schema, functions={"add_one_to": lambda args: str(args.input) + " + 1"}
    )

    # then
    assert result["bar"] == 11


def test_function_call_input_is_resolved_by_default_using_the_any_schema():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {"foo": 6, "bar": {"__add_one_to__": "${foo}"}}

    # when
    result = resolve(
        cfg,
        schema,
        functions={"add_one_to": lambda args: int(args.input) + 1},  # type: ignore
    )

    # then
    assert result["bar"] == 7


def test_function_call_other_nodes_can_reference_keys_within_dict_computed_by_function():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "baz": {"type": "dict", "extra_keys_schema": {"type": "integer"}},
        },
    }

    cfg: ConfigurationDict = {
        "foo": "${baz.alpha} * 3",
        "baz": {"__make_numbers__": {}},
    }

    def make_numbers(_):
        return {"alpha": "6 + 4", "beta": 20}

    # when
    result = resolve(cfg, schema, functions={"make_numbers": make_numbers})

    # then
    assert result["foo"] == 30


def test_function_call_with_input_not_resolved():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "integer"}, "bar": {"type": "integer"}},
    }

    cfg: ConfigurationDict = {"foo": "4", "bar": {"__myraw__": "${foo} + 1"}}

    seen = []

    def myraw(args):
        seen.append(args.input)
        return args.input

    function = Function(myraw, resolve_input=False)

    # when
    result = resolve(cfg, schema, functions={"myraw": function})

    # then
    assert seen == ["${foo} + 1"]
    assert result == {"foo": 4, "bar": 5}


def test_function_call_with_input_and_output_not_resolved():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "integer"}, "bar": {"type": "string"}},
    }

    cfg: ConfigurationDict = {"foo": 4, "bar": {"__myraw__": "${foo} + 1"}}

    seen = []

    def myraw(args):
        seen.append(args.input)
        return RawString(args.input)

    function = Function(myraw, resolve_input=False)

    # when
    result = resolve(cfg, schema, functions={"myraw": function})

    # then
    assert seen == ["${foo} + 1"]
    assert result == {"foo": 4, "bar": "${foo} + 1"}


def test_function_call_without_resolving_output_does_not_apply_schema():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "integer"}, "bar": {"type": "string"}},
    }

    cfg: ConfigurationDict = {"foo": 4, "bar": {"__myraw__": "${foo} + 1"}}

    seen = []

    def myraw(args):
        seen.append(args.input)
        return RawString(args.input)

    function = Function(myraw, resolve_input=False)

    # when
    result = resolve(cfg, schema, functions={"myraw": function})

    # then
    assert seen == ["${foo} + 1"]
    # the result for "bar" is a string even though the schema expects an integer
    assert result == {"foo": 4, "bar": "${foo} + 1"}


def test_function_call_resolve_raises_if_function_call_is_malformed():
    # with the default behavior, a function call is expected to be a dictionary
    # with one key of the form __<name>__ where <name> is the name of the function.
    # if there's another key in that dictionary, it is considered a malformed
    # function call and we should raise a ResolutionError
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "integer"}, "bar": {"type": "integer"}},
    }

    cfg: ConfigurationDict = {
        "foo": 4,
        "bar": {"__myraw__": "${foo} + 1", "baz": "hello"},
    }
    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"mraw": lambda x: x.input})

    # then
    assert "Invalid function call" in str(exc.value)


def test_function_call_with_unknown_function():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "integer"}, "bar": {"type": "integer"}},
    }

    cfg: ConfigurationDict = {"foo": 4, "bar": {"__myraw__": "${foo} + 1"}}
    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={})

    # then
    assert "Unknown function" in str(exc.value)


def test_function_call_is_given_root_as_unresolved_dict_or_list():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {
                "type": "dict",
                "required_keys": {"a": {"type": "integer"}, "b": {"type": "integer"}},
            },
            "bar": {
                "type": "dict",
                "required_keys": {"a": {"type": "integer"}, "b": {"type": "integer"}},
            },
        },
    }

    cfg: ConfigurationDict = {
        "foo": {
            "a": 1,
            "b": 7,
        },
        "bar": {"__splice__": "foo"},
    }

    def splice(args):
        return args.root.get_keypath(args.input)

    # when
    result = resolve(cfg, schema, functions={"splice": splice})

    # then
    assert result["bar"] == {"a": 1, "b": 7}


def test_function_call_get_keypath_to_function_call_returning_a_dict():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "alpha": {"type": "integer"},
            "beta": {
                "type": "dict",
                "required_keys": {"gamma": {"type": "integer"}},
            },
        },
    }

    def triple(args: FunctionArgs) -> int:
        x = args.root.get_keypath("beta.gamma")
        assert isinstance(x, int)
        return x * 3

    def make_beta(_: FunctionArgs) -> ConfigurationDict:
        return {"gamma": 10}

    cfg: ConfigurationDict = {
        "alpha": {"__triple__": {}},
        "beta": {"__make_beta__": {}},
    }

    # when
    result = resolve(cfg, schema, functions={"triple": triple, "make_beta": make_beta})

    # then
    assert result == {"alpha": 30, "beta": {"gamma": 10}}


def test_function_call_at_root_with_result_producing_references():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
        },
    }

    def myfun(_):
        return {"foo": 10, "bar": "${foo}"}

    # when
    result = resolve({"__myfun__": {}}, schema, functions={"myfun": myfun})

    # then
    assert result == {"foo": 10, "bar": 10}


def test_function_call_at_root_producing_key_shadowing_builtin():
    # the function call produces a `range` key which shadows the builtin `range`
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "range": {"type": "integer"},
        },
    }

    def myfun(_: FunctionArgs) -> ConfigurationDict:
        return {"foo": 10, "range": 20}

    cfg: ConfigurationDict = {"__myfun__": {}}

    # when
    result = resolve(cfg, schema, functions={"myfun": myfun})

    # then
    assert result == {"foo": 10, "range": 20}


def test_function_call_at_root_does_not_produce_key_shadowing_builtin():
    # the function call does not produce range, so smartconfig drops back to the
    # builtin range

    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
        },
    }

    def myfun(_: FunctionArgs) -> ConfigurationDict:
        return {"foo": "${range(10) | length}"}

    # when
    result = resolve({"__myfun__": {}}, schema, functions={"myfun": myfun})

    # then
    assert result == {"foo": 10}


def test_function_call_with_reference_to_result_of_another_function_call_within_dict():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "alpha": {"type": "integer"},
            "beta": {"type": "integer"},
        },
    }

    def double(args):
        return args.input * 2

    def triple(args):
        return args.root["beta"] * 3

    cfg: ConfigurationDict = {"alpha": {"__triple__": {}}, "beta": {"__double__": 10}}

    # when
    result = resolve(cfg, schema, functions={"double": double, "triple": triple})

    # then
    assert result == {"alpha": 60, "beta": 20}


def test_function_call_with_reference_to_result_of_another_function_call_within_list():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {"type": "integer"},
    }

    def double(args):
        return args.input * 2

    def triple(args):
        return args.root[1] * 3

    cfg: ConfigurationList = [{"__triple__": {}}, {"__double__": 10}]

    # when
    result = resolve(cfg, schema, functions={"double": double, "triple": triple})

    # then
    assert result == [60, 20]


def test_function_call_that_returns_a_function_call():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
        },
    }

    def double(args):
        return args.input * 2

    def add_one(args):
        return {"__double__": args.input + 1}

    # when
    result = resolve(
        {"foo": {"__add_one__": 10}},
        schema,
        functions={"double": double, "add_one": add_one},
    )

    # then
    assert result == {"foo": 22}


def test_function_call_that_returns_a_function_call_that_returns_a_function_call():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
        },
    }

    def double(args):
        return args.input * 2

    def add_one(args):
        return {"__double__": args.input + 1}

    def add_two(args):
        return {"__add_one__": args.input + 2}

    # when
    result = resolve(
        {"foo": {"__add_two__": 10}},
        schema,
        functions={"double": double, "add_one": add_one, "add_two": add_two},
    )

    # then
    assert result == {"foo": 26}


def test_function_call_with_infinite_recursion():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
        },
    }

    def add_one(args):
        return {"__add_one__": args.input + 1}

    # when
    with raises(RecursionError):
        resolve({"foo": {"__add_one__": 10}}, schema, functions={"add_one": add_one})


def test_function_with_custom_call_syntax():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
        },
    }

    def add_one(args):
        return args.input + 1

    def check_for_function_call(cfg, functions):
        for key in cfg.keys():
            if key.startswith("!!"):
                function_name = key[2:]
                input = cfg[key]
                return functions[function_name], input

    # when
    result = resolve(
        {"bar": 5, "foo": {"!!add_one": 10}},
        schema,
        functions={"add_one": add_one},
        check_for_function_call=check_for_function_call,
    )

    # then
    assert result == {"bar": 5, "foo": 11}


def test_function_with_disabled_check_for_function_call():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
        },
    }

    def add_one(args):
        return args.input + 1

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(
            {"bar": 5, "foo": {"!!add_one": 10}},
            schema,
            functions={"add_one": add_one},
            check_for_function_call=None,
        )

    assert "!!add_one" in str(exc.value)


def test_functions_is_none_means_no_functions():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
        },
    }

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve({"bar": 5, "foo": {"__splice__": 10}}, schema, functions=None)

    assert "Unknown function" in str(exc.value)


# global variables =====================================================================


def test_global_variables_are_injected():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {"foo": "${ alpha }", "bar": "${ beta }"}

    # when
    result = resolve(cfg, schema, global_variables={"alpha": 10, "beta": 20})

    # then
    assert result == {"foo": 10, "bar": 20}


def test_global_variables_are_given_less_priority_when_names_clash():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {"foo": "${ foo }", "bar": "${ bar }"}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, global_variables={"foo": 10, "bar": 20})

    assert "Circular reference" in str(exc.value)


# inject root ==========================================================================


def test_inject_root_with_top_level_list():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {"type": "integer"},
    }

    cfg: ConfigurationList = [4, 1, "${ root.0 } + 1"]

    # when
    result = resolve(cfg, schema, inject_root_as="root")

    # then
    assert result == [4, 1, 5]


def test_inject_root_with_top_level_dict():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {"foo": 42, "bar": "${ myroot.keys() | length }"}

    # when
    result = resolve(cfg, schema, inject_root_as="myroot")

    # then
    assert result["bar"] == 2


def test_inject_root_with_dictionary_returned_by_function_node():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {
                "type": "dict",
                "required_keys": {
                    "foo": {"type": "integer"},
                    "bar": {"type": "integer"},
                },
            },
            "baz": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {
        "foo": 42,
        "bar": {"__make_dict__": {}},
        "baz": "${ myroot.bar.foo }",
    }

    def make_dict(_: FunctionArgs) -> ConfigurationDict:
        return {"foo": 10, "bar": 20}

    # when
    result = resolve(
        cfg, schema, functions={"make_dict": make_dict}, inject_root_as="myroot"
    )

    # then
    assert result == {"foo": 42, "bar": {"foo": 10, "bar": 20}, "baz": 10}


def test_inject_root_with_function_at_root_level_returning_a_list():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {"type": "integer"},
    }

    cfg: ConfigurationDict = {"__make_list__": {}}

    def make_list(_):
        return [1, 2, 3, "${ myroot.1 }"]

    # when
    result = resolve(
        cfg, schema, functions={"make_list": make_list}, inject_root_as="myroot"
    )

    # then
    assert result == [1, 2, 3, 2]


# filters ==============================================================================


def test_filter_is_provided_at_interpolation_time():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {"foo": "this", "bar": "${ foo | myfilter }"}

    def myfilter(value):
        return value.upper()

    # when
    result = resolve(cfg, schema, filters={"myfilter": myfilter})

    # then
    assert result["bar"] == "THIS"


def test_filter_overrides_builtin_jinja_filters():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {"foo": "this", "bar": "${ foo | length }"}

    def length(_):
        return 42

    # when
    result = resolve(cfg, schema, filters={"length": length})

    # then
    assert result["bar"] == "42"


def test_filter_with_arguments():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {"foo": "this", "bar": "${ foo | myfilter('that') }"}

    def myfilter(value, arg1):
        return value + arg1

    # when
    result = resolve(cfg, schema, filters={"myfilter": myfilter})

    # then
    assert result["bar"] == "thisthat"


# unresolved containers ================================================================


def test_unresolved_dict_values():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "dict", "extra_keys_schema": {"type": "string"}},
            "bar": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {
        "foo": {"one": "a", "two": "b"},
        "bar": "{% for s in foo.values() | sort %}${ s } {% endfor %}",
    }

    # when
    result = resolve(cfg, schema)

    # then
    assert result["bar"] == "a b "


def test_unresolved_list_returns_unresolved_dict():
    # given
    schema: Schema = {
        "required_keys": {
            "foo": {
                "type": "list",
                "element_schema": {
                    "type": "dict",
                    "required_keys": {"foo": {"type": "string"}},
                },
            },
            "bar": {"type": "string"},
        },
        "type": "dict",
    }

    def checker(args):
        assert isinstance(args.root["foo"][0], UnresolvedDict)
        return "ok"

    cfg: ConfigurationDict = {
        "foo": [{"foo": "a"}, {"foo": "b"}],
        "bar": {"__checker__": {}},
    }

    # when
    resolve(cfg, schema, functions={"checker": checker})


def test_unresolved_list_returns_unresolved_list():
    # given
    schema: Schema = {
        "required_keys": {
            "foo": {
                "type": "list",
                "element_schema": {
                    "type": "list",
                    "element_schema": {"type": "string"},
                },
            },
            "bar": {"type": "string"},
        },
        "type": "dict",
    }

    def checker(args):
        assert isinstance(args.root["foo"][0], UnresolvedList)
        return "ok"

    cfg: ConfigurationDict = {"foo": [["hi"], ["a", "b"]], "bar": {"__checker__": {}}}

    # when
    resolve(cfg, schema, functions={"checker": checker})


def test_unresolved_list_resolve():
    # given
    schema: Schema = {
        "required_keys": {
            "foo": {
                "type": "list",
                "element_schema": {
                    "type": "list",
                    "element_schema": {"type": "string"},
                },
            },
            "bar": {"type": "string"},
        },
        "type": "dict",
    }

    def checker(args):
        assert args.root["foo"].resolve() == [["hi"], ["a", "b"]]
        return "ok"

    cfg: ConfigurationDict = {"foo": [["hi"], ["a", "b"]], "bar": {"__checker__": {}}}

    # when
    resolve(cfg, schema, functions={"checker": checker})


def test_unresolved_list_get_keypath():
    # given
    schema: Schema = {
        "required_keys": {
            "foo": {
                "type": "list",
                "element_schema": {
                    "type": "list",
                    "element_schema": {"type": "string"},
                },
            },
            "bar": {"type": "string"},
        },
        "type": "dict",
    }

    def checker(args):
        assert args.root["foo"].get_keypath("1") == ["a", "b"]
        return "ok"

    cfg: ConfigurationDict = {"foo": [["hi"], ["a", "b"]], "bar": {"__checker__": {}}}

    # when
    resolve(cfg, schema, functions={"checker": checker})


def test_unresolved_function_get_keypath():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "alpha": {"type": "integer"},
            "beta": {"type": "integer"},
        },
    }

    def outer(_):
        return {"alpha": 1, "beta": {"__inner__": {}}}

    def inner(args):
        assert isinstance(args.root, UnresolvedFunctionCall)
        number = args.root.get_keypath("alpha")
        assert isinstance(number, int)
        return number + 1

    cfg: ConfigurationDict = {"__outer__": {}}

    # when
    resolve(cfg, schema, functions={"outer": outer, "inner": inner})


def test_unresolved_dict_get_keypath_deeper_than_container_raises_keyerror():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "any"},
            "bar": {"type": "any"},
        },
    }

    def inner(args):
        assert isinstance(args.root, UnresolvedDict)
        with raises(KeyError):
            args.root.get_keypath("foo.a.bar")

    cfg: ConfigurationDict = {"foo": {"a": 1, "b": 2}, "bar": {"__inner__": {}}}

    # when
    resolve(cfg, schema, functions={"inner": inner})


# dynamic schemas ======================================================================


def test_resolve_with_dynamic_schema_in_list():
    # given
    def element_schema(element, _):
        """When called on a list element, returns a schema for that element."""
        return {"type": "integer"}

    schema: Schema = {"type": "list", "element_schema": element_schema}

    cfg: ConfigurationList = ["1", "2", "3"]

    # when
    result = resolve(cfg, schema)

    # then
    assert result == [1, 2, 3]


def test_resolve_with_dynamic_schema_in_list_of_dicts():
    # given
    def element_schema(element, _):
        if "foo" in element:
            return {
                "type": "dict",
                "required_keys": {"foo": {"type": "integer"}},
            }

        if "bar" in element:
            return {
                "type": "dict",
                "required_keys": {"bar": {"type": "string"}},
            }

    schema: Schema = {"type": "list", "element_schema": element_schema}

    cfg: ConfigurationList = [{"foo": "10"}, {"bar": "hello"}]

    # when
    result = resolve(cfg, schema)

    # then
    assert result == [{"foo": 10}, {"bar": "hello"}]


def test_resolve_with_dynamic_schema_in_extra_keys():
    # given
    def extra_keys_schema(value, _):
        if value.isdigit():
            return {"type": "integer"}
        else:
            return {"type": "string"}

    schema: Schema = {
        "type": "dict",
        "extra_keys_schema": extra_keys_schema,
    }

    cfg: ConfigurationDict = {
        "num_one": "1",
        "num_two": "2",
        "str_hello": "world",
    }

    # when
    result = resolve(cfg, schema)

    # then
    assert result == {
        "num_one": 1,
        "num_two": 2,
        "str_hello": "world",
    }


def test_resolve_with_dynamic_schema_invalid_return():
    # given
    def element_schema(element, _):
        return {"type": "unknown_type"}

    schema: Schema = {"type": "list", "element_schema": element_schema}

    # when
    with raises(exceptions.InvalidSchemaError):
        resolve(["1", "2", "3"], schema)


def test_resolve_with_dynamic_schema_at_root():
    # given
    def main_schema(cfg, _):
        return {
            "type": "dict",
            "required_keys": {
                "value": {"type": "integer"},
            },
        }

    cfg: ConfigurationDict = {"value": "42"}

    # when
    result = resolve(cfg, main_schema)

    # then
    assert result == {"value": 42}


def test_resolve_with_dynamic_schema_based_on_keypath():  # given
    # if the last part of the keypath starts with "num", we want an integer schema
    # otherwise, a string schema
    def extra_keys_schema(_: Configuration, keypath: KeyPath) -> Schema:
        last_part = keypath[-1]
        if last_part.startswith("num"):
            return {"type": "integer"}
        else:
            return {"type": "string"}

    schema: Schema = {
        "type": "dict",
        "extra_keys_schema": extra_keys_schema,
    }

    cfg: ConfigurationDict = {
        "num_one": "1",
        "num_two": "2",
        "str_hello": "world",
    }

    # when
    result = resolve(cfg, schema)

    # then
    assert result == {
        "num_one": 1,
        "num_two": 2,
        "str_hello": "world",
    }


def test_resolve_with_dynamic_schemas_nested():
    # given
    def address_schema(cfg: Configuration, _: KeyPath) -> Schema:
        return {
            "type": "dict",
            "required_keys": {
                "city": {"type": "string"},
                "zip_code": {"type": "integer"},
            },
        }

    def person_schema(cfg: Configuration, _: KeyPath) -> Schema:
        return {
            "type": "dict",
            "required_keys": {
                "name": {"type": "string"},
                "address": address_schema,
            },
        }

    schema: DynamicSchema = person_schema

    cfg: ConfigurationDict = {
        "name": "Diana",
        "address": {"city": "Los Angeles", "zip_code": "90001"},
    }

    # when
    result = resolve(cfg, schema)

    # then
    assert result == {
        "name": "Diana",
        "address": {"city": "Los Angeles", "zip_code": 90001},
    }


# prototypes ===========================================================================


def test_resolve_given_prototype_as_spec():
    # given
    class Student(Prototype):
        name: str
        age: int

    cfg: ConfigurationDict = {
        "name": "Alice",
        "age": "21",
    }

    # when
    result = resolve(cfg, Student)

    # then
    assert isinstance(result, Student)
    assert result.name == "Alice"
    assert result.age == 21


def test_resolve_with_nested_prototype():
    # given
    class Address(Prototype):
        city: str
        zip_code: int

    class Person(Prototype):
        name: str
        address: Address

    cfg: ConfigurationDict = {
        "name": "Bob",
        "address": {"city": "New York", "zip_code": "10001"},
    }

    # when
    result = resolve(cfg, Person)

    # then
    assert isinstance(result, Person)
    assert isinstance(result.address, Address)
    assert result.name == "Bob"
    assert result.address.city == "New York"
    assert result.address.zip_code == 10001


def test_resolve_with_deeply_nested_prototype():
    # given
    class Address(Prototype):
        city: str
        zip_code: int

    class Person(Prototype):
        name: str
        address: Address

    class Company(Prototype):
        owner: Person
        address: Address

    cfg: ConfigurationDict = {
        "owner": {
            "name": "Charlie",
            "address": {"city": "San Francisco", "zip_code": "94105"},
        },
        "address": {"city": "Seattle", "zip_code": "98101"},
    }

    # when
    result = resolve(cfg, Company)

    # then
    assert isinstance(result, Company)
    assert isinstance(result.owner, Person)
    assert isinstance(result.owner.address, Address)
    assert result.owner.name == "Charlie"
    assert result.owner.address.city == "San Francisco"
    assert result.address.city == "Seattle"


def test_resolve_with_list_of_prototypes():
    # given
    class Address(Prototype):
        city: str
        zip_code: int

    class Person(Prototype):
        name: str
        address: Address

    class Team(Prototype):
        members: list[Person]

    cfg: ConfigurationDict = {
        "members": [
            {"name": "Member 1", "address": {"city": "A", "zip_code": 1}},
            {"name": "Member 2", "address": {"city": "B", "zip_code": 2}},
        ]
    }

    # when
    result = resolve(cfg, Team)

    # then
    assert isinstance(result, Team)
    assert len(result.members) == 2
    assert all(isinstance(member, Person) for member in result.members)
    assert result.members[0].name == "Member 1"
    assert result.members[1].address.city == "B"


def test_resolve_with_dict_of_prototypes():
    # given
    class Address(Prototype):
        city: str
        zip_code: int

    class Person(Prototype):
        name: str
        address: Address

    class Team(Prototype):
        members: list[Person]

    class Organization(Prototype):
        teams: dict[str, Team]

    cfg: ConfigurationDict = {
        "teams": {
            "alpha": {
                "members": [{"name": "Alice", "address": {"city": "A", "zip_code": 1}}]
            },
            "beta": {
                "members": [{"name": "Bob", "address": {"city": "B", "zip_code": 2}}]
            },
        }
    }

    # when
    result = resolve(cfg, Organization)

    # then
    assert isinstance(result, Organization)
    assert isinstance(result.teams["alpha"], Team)
    assert result.teams["alpha"].members[0].name == "Alice"
    assert result.teams["beta"].members[0].name == "Bob"


def test_resolve_with_optional_fields():
    # given
    class ConfigWithOptional(Prototype):
        required: int
        optional: NotRequired[int]

    cfg_with: ConfigurationDict = {"required": 1, "optional": 2}
    cfg_without: ConfigurationDict = {"required": 1}

    # when
    result_with = resolve(cfg_with, ConfigWithOptional)
    result_without = resolve(cfg_without, ConfigWithOptional)

    # then
    assert result_with.required == 1
    assert result_with.optional == 2
    assert result_without.required == 1
    # The optional attribute should not be set if the key was missing
    assert not hasattr(result_without, "optional")


def test_resolve_with_nullable_fields():
    # given
    class ConfigWithNullable(Prototype):
        not_nullable: int
        nullable: int | None

    cfg_val: ConfigurationDict = {"not_nullable": 1, "nullable": 2}
    cfg_none: ConfigurationDict = {"not_nullable": 1, "nullable": None}

    # when
    result_val = resolve(cfg_val, ConfigWithNullable)
    result_none = resolve(cfg_none, ConfigWithNullable)

    # then
    assert result_val.nullable == 2
    assert result_none.nullable is None


def test_resolve_with_default_values():
    # given
    class ConfigWithDefaults(Prototype):
        no_default: int
        with_default: int = 42

    cfg_default: ConfigurationDict = {"no_default": 1}
    cfg_override: ConfigurationDict = {"no_default": 1, "with_default": 100}

    # when
    result_default = resolve(cfg_default, ConfigWithDefaults)
    result_override = resolve(cfg_override, ConfigWithDefaults)

    # then
    assert result_default.with_default == 42
    assert result_override.with_default == 100
