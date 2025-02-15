from smartconfig import resolve, exceptions
from smartconfig.types import RawString, RecursiveString, Function

from pytest import raises


# dictionaries
# ============


def test_raises_if_required_keys_are_missing():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "any"},
            "bar": {"type": "any"},
        },
    }

    dct = {"foo": 42}

    # when
    with raises(exceptions.ResolutionError) as excinfo:
        resolve(dct, schema)

    assert excinfo.value.keypath == ("bar",)


def test_raises_if_extra_keys_without_extra_keys_schema():
    # given
    schema = {"type": "dict", "required_keys": {}}

    dct = {"foo": 42}

    # when
    with raises(exceptions.ResolutionError):
        resolve(dct, schema)


def test_allows_extra_keys_with_extra_keys_schema():
    # given
    schema = {"type": "dict", "extra_keys_schema": {"type": "any"}}

    dct = {"foo": 42}

    # when
    result = resolve(dct, schema)

    # then
    assert result["foo"] == 42


def test_fills_in_missing_value_with_default_if_provided():
    # given
    schema = {
        "type": "dict",
        "optional_keys": {"foo": {"default": 42, "type": "integer"}},
    }

    dct = {}

    # when
    result = resolve(dct, schema)

    # then
    assert result["foo"] == 42


def test_allows_missing_keys_if_required_is_false():
    # given
    schema = {
        "type": "dict",
        "optional_keys": {
            "foo": {"type": "integer"},
            "bar": {
                "type": "integer",
            },
        },
    }

    dct = {"bar": 42}

    # when
    result = resolve(dct, schema)

    # then
    assert result["bar"] == 42
    assert "foo" not in result


# non-dictionary roots
# ====================


def test_lists_are_permitted_as_root_node():
    # given
    schema = {"type": "list", "element_schema": {"type": "integer"}}

    lst = [1, 2, 3]

    # when
    result = resolve(lst, schema)

    # then
    assert result == [1, 2, 3]


def test_leafs_are_permitted_as_root_node():
    # given
    schema = {
        "type": "integer",
    }

    x = 42

    # when
    result = resolve(x, schema)

    # then
    assert result == 42


# interpolation
# =============


def test_interpolation_of_other_dictionary_entries_same_level():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
        },
    }

    dct = {"foo": "hello", "bar": "testing ${foo}"}

    # when
    result = resolve(dct, schema)

    # then
    assert result["bar"] == "testing hello"


def test_interpolation_of_a_high_node_referencing_a_deeper_node():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {
                "type": "dict",
                "required_keys": {"baz": {"type": "string"}},
            },
        },
    }

    dct = {"foo": "testing ${bar.baz}", "bar": {"baz": "this"}}

    # when
    result = resolve(dct, schema)

    # then
    assert result["foo"] == "testing this"


def test_interpolation_of_a_deep_node_referencing_a_higher_node():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {
                "type": "dict",
                "required_keys": {"baz": {"type": "string"}},
            },
        },
    }

    dct = {"foo": "testing", "bar": {"baz": "${foo} this"}}

    # when
    result = resolve(dct, schema)

    # then
    assert result["foo"] == "testing"
    assert result["bar"]["baz"] == "testing this"


def test_interpolation_can_reference_list_elements():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {
                "type": "list",
                "element_schema": {"type": "string"},
            },
        },
    }

    dct = {"foo": "testing ${bar.1}", "bar": ["this", "that", "the other"]}

    # when
    result = resolve(dct, schema)

    # then
    assert result["foo"] == "testing that"


def test_chain_of_multiple_interpolations():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
            "baz": {"type": "string"},
        },
    }

    dct = {
        "foo": "this",
        "bar": "testing ${foo}",
        "baz": "now ${bar}",
    }

    # when
    result = resolve(dct, schema)

    # then
    assert result["foo"] == "this"
    assert result["bar"] == "testing this"
    assert result["baz"] == "now testing this"


def test_raises_if_self_reference_detected():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
        },
    }

    dct = {
        "foo": "${foo}",
    }

    # when
    with raises(exceptions.ResolutionError):
        resolve(dct, schema)


def test_raises_if_cyclical_reference_detected():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
            "baz": {"type": "string"},
        },
    }

    dct = {
        "foo": "${baz}",
        "bar": "${foo}",
        "baz": "${bar}",
    }

    # when
    with raises(exceptions.ResolutionError):
        resolve(dct, schema)


def test_interpolation_can_use_jinja_to_loop_over_list():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "list", "element_schema": {"type": "string"}},
            "bar": {"type": "string"},
        },
    }

    dct = {
        "foo": ["this", "that", "the other"],
        "bar": "{% for item in foo %}item: ${ item } {% endfor %}",
    }

    # when
    result = resolve(dct, schema)

    # then
    assert result["bar"] == "item: this item: that item: the other "


def test_interpolation_can_use_jinja_to_loop_over_dict_keys_explicitly():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "dict", "extra_keys_schema": {"type": "string"}},
            "bar": {"type": "string"},
        },
    }

    dct = {
        "foo": {"this": "that", "the": "other"},
        "bar": "{% for key in foo.keys() | sort %}key: ${ key } {% endfor %}",
    }

    # when
    result = resolve(dct, schema)

    # then
    assert result["bar"] == "key: the key: this "


def test_interpolation_can_use_jinja_to_loop_over_dict_keys_implicitly():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "dict", "extra_keys_schema": {"type": "string"}},
            "bar": {"type": "string"},
        },
    }

    dct = {
        "foo": {"this": "that", "the": "other"},
        "bar": "{% for key in foo | sort %}key: ${ key } {% endfor %}",
    }

    # when
    result = resolve(dct, schema)

    # then
    assert result["bar"] == "key: the key: this "


def test_can_use_jinja_methods():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
        },
    }

    dct = {
        "foo": "this",
        "bar": "testing ${foo.upper()}",
    }

    # when
    result = resolve(dct, schema)

    # then
    assert result["foo"] == "this"
    assert result["bar"] == "testing THIS"


def test_can_use_builtin_jinja_function_range():
    # given
    schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "integer"}, "bar": {"type": "string"}},
    }

    dct = {
        "foo": 3,
        "bar": "{% for i in range(foo) %}${ i }{% endfor %}",
    }

    # when
    result = resolve(dct, schema)

    # then
    assert result["bar"] == "012"


def test_can_treat_floats_as_floats():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "float"},
            "bar": {"type": "string"},
        },
    }

    dct = {
        "foo": 3.00,
        "bar": "testing ${foo + 4}",
    }

    # when
    result = resolve(dct, schema)

    # then
    assert result["foo"] == 3.0
    assert result["bar"] == "testing 7.0"


def test_interpolation_of_keys_with_dots():
    # given
    schema = {
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

    dct = {
        "this": {
            "foo.txt": "this",
            "bar": "testing ${this['foo.txt']}",
        }
    }

    # when
    result = resolve(dct, schema)

    # then
    assert result["this"]["foo.txt"] == "this"
    assert result["this"]["bar"] == "testing this"


def test_interpolation_is_not_confused_by_different_jinja_syntax():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
        },
    }

    dct = {
        "foo": "this",
        "bar": "testing ${foo} $[ that ]",
    }

    # when
    result = resolve(dct, schema)

    # then
    assert result["foo"] == "this"
    assert result["bar"] == "testing this $[ that ]"


def test_interpolation_from_deeply_nested_list():
    # given
    schema = {
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

    dct = {
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
    result = resolve(dct, schema)

    # then
    assert result["publication_schema"]["required_artifacts"][2] == "baz"


# parsing
# =======


def test_leafs_are_parsed_into_expected_types():
    # given
    schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "integer"}},
    }

    dct = {"foo": "42"}

    # when
    result = resolve(dct, schema)

    # then
    assert result["foo"] == 42


def test_parsing_occurs_after_interpolation():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
        },
    }

    dct = {"foo": "42", "bar": "${foo}"}

    # when
    result = resolve(dct, schema)

    # then
    assert result["foo"] == 42
    assert result["bar"] == 42


def test_parsing_of_extra_dictionary_keys():
    # given
    schema = {"type": "dict", "extra_keys_schema": {"type": "integer"}}

    dct = {"foo": "42", "bar": "10"}

    # when
    result = resolve(dct, schema)

    # then
    assert result["foo"] == 42
    assert result["bar"] == 10


def test_parsing_of_list_elements():
    # given
    schema = {"type": "list", "element_schema": {"type": "integer"}}

    dct = ["10", "25"]

    # when
    result = resolve(dct, schema)

    # then
    assert result == [10, 25]


def test_raw_strings_resolve_to_raw_strings():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
        },
    }

    dct = {"foo": "this", "bar": RawString("${foo}")}

    # when
    result = resolve(dct, schema)

    # then
    assert isinstance(result["bar"], RawString)


def test_raw_strings_are_not_interpolated():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
        },
    }

    dct = {"foo": "this", "bar": RawString("${foo}")}

    # when
    result = resolve(dct, schema)

    # then
    assert result["bar"] == "${foo}"


def test_raw_strings_are_still_type_checked():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "integer"},
        },
    }

    dct = {"foo": "this", "bar": RawString("42")}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(dct, schema)

    assert "Schema expected something other than a string" in str(exc.value)


def test_recursive_strings_resolve_to_regular_strings():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
        },
    }

    dct = {"foo": "this", "bar": RecursiveString("testing ${foo}")}

    # when
    result = resolve(dct, schema)

    # then
    assert isinstance(result["bar"], str) and not isinstance(
        result["bar"], RecursiveString
    )


def test_recursive_strings_are_interpolated_recursively():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
            "baz": {"type": "string"},
        },
    }

    dct = {
        "foo": "hello",
        "bar": RawString("${foo} world"),
        "baz": RecursiveString("I said: ${bar}"),
    }

    # when
    result = resolve(dct, schema)

    # then
    assert result == {
        "foo": "hello",
        "bar": "${foo} world",
        "baz": "I said: hello world",
    }


def test_raises_if_no_parser_provided_for_type():
    # given
    schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "unknown"}},
    }

    dct = {"foo": "42"}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(dct, schema)

    assert "No parser provided for type: 'unknown'" in str(exc.value)


# "any" type
# ==========


def test_all_types_preserved_when_any_is_used():
    # given
    schema = {
        "type": "any",
    }

    dct = {"foo": "testing", "bar": {"x": 1, "y": 2}, "baz": [1, 2, 3]}

    # when
    result = resolve(dct, schema)

    # then
    assert result == dct


def test_interpolation_occurs_when_any_is_used():
    # given
    schema = {
        "type": "any",
    }

    dct = {"foo": "testing", "bar": "${foo} this"}

    # when
    result = resolve(dct, schema)

    # then
    assert result["bar"] == "testing this"


# nullable
# ========


def test_dictionary_can_be_nullable():
    # given
    schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "dict", "nullable": True}},
    }

    dct = {"foo": None}

    # when
    result = resolve(dct, schema)

    # then
    assert result["foo"] is None


def test_list_can_be_nullable():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {
                "type": "list",
                "element_schema": {"type": "any"},
                "nullable": True,
            }
        },
    }

    dct = {"foo": None}

    # when
    result = resolve(dct, schema)

    # then
    assert result["foo"] is None


def test_leaf_can_be_nullable():
    # given
    schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "integer", "nullable": True}},
    }

    dct = {"foo": None}

    # when
    result = resolve(dct, schema)

    # then
    assert result["foo"] is None


def test_error_is_raised_if_None_is_provided_but_value_is_not_nullable():
    # given
    schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "integer"}},
    }

    dct = {"foo": None}

    # when
    with raises(exceptions.ResolutionError):
        resolve(dct, schema)


# good exceptions
# ===============


def test_exception_has_correct_path_with_missing_key_in_nested_dict():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {
                "type": "dict",
                "required_keys": {"bar": {"type": "any"}},
            },
        },
    }

    dct = {"foo": {}}

    # when
    with raises(exceptions.ResolutionError) as excinfo:
        resolve(dct, schema)

    assert excinfo.value.keypath == (
        "foo",
        "bar",
    )


def test_exception_has_correct_path_with_missing_key_in_nested_dict_within_list():
    # given
    schema = {
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

    lst = [
        {
            "foo": 10,
        },
        {"bar": 42},
    ]

    # when
    with raises(exceptions.ResolutionError) as excinfo:
        resolve(lst, schema)

    assert excinfo.value.keypath == (1, "foo")


# preserve_type
# =============


def test_preserve_type():
    class UserDict(dict):
        something = 80

    # given
    schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "integer"}},
    }

    dct = UserDict({"foo": "42"})

    # when
    result = resolve(dct, schema, preserve_type=True)

    # then
    assert result.something == 80  # type: ignore


# container references
# ====================


def test_reference_entire_dict_raises_exception():
    # given
    schema = {
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

    dct = {
        "foo": {"x": 1, "y": 2},
        "bar": "${foo}",
    }

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(dct, schema)

    assert "No parser provided for type: 'dict'" in str(exc.value)


def test_reference_entire_dict_indirectly_raises_exception():
    # given
    schema = {
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

    dct = {
        "foo": {"x": 1, "y": 2},
        "bar": "${foo}",
        "baz": "${bar.y}",
        "quux": "${baz}",
    }

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(dct, schema)

    assert "No parser provided for type: 'dict'" in str(exc.value)


def test_reference_entire_dict_indirectly_reverse_order_raises_exception():
    # given
    schema = {
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

    dct = {
        "foo": {"x": 1, "y": 2},
        "bar": "${baz.y}",
        "baz": "${quux}",
        "quux": "${foo}",
    }

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(dct, schema)

    # then
    assert "No parser provided for type: 'dict'" in str(exc.value)


def test_reference_entire_list_raises_exception():
    # given
    schema = {
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

    dct = {
        "foo": [1, 2],
        "bar": "${foo}",
    }

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(dct, schema)

    # then
    assert "No parser provided for type: 'list'" in str(exc.value)


# functions
# =========


def test_function_call_at_root():
    # given
    schema = {"type": "integer"}
    dct = {"__double__": 10}

    # when
    result = resolve(dct, schema, functions={"double": lambda x: x.input * 2})

    # then
    assert result == 20


def test_function_call_in_dictionary():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
        },
    }

    dct = {"foo": 6, "bar": {"__double__": 10}}

    # when
    result = resolve(dct, schema, functions={"double": lambda args: args.input * 2})

    # then
    assert result["bar"] == 20


def test_function_call_in_list():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "list", "element_schema": {"type": "integer"}},
        },
    }

    dct = {"foo": 6, "bar": [1, {"__double__": 10}, 3]}

    # when
    result = resolve(dct, schema, functions={"double": lambda args: args.input * 2})

    # then
    assert result["bar"] == [1, 20, 3]


def test_function_call_output_is_resolved_by_default_using_schema():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
        },
    }

    dct = {"foo": 6, "bar": {"__add_one_to__": "10"}}

    # when
    result = resolve(
        dct, schema, functions={"add_one_to": lambda args: str(args.input) + " + 1"}
    )

    # then
    assert result["bar"] == 11


def test_function_call_input_is_resolved_by_default_using_the_any_schema():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
        },
    }

    dct = {"foo": 6, "bar": {"__add_one_to__": "${foo}"}}

    # when
    result = resolve(
        dct, schema, functions={"add_one_to": lambda args: int(args.input) + 1}
    )

    # then
    assert result["bar"] == 7


def test_function_call_other_nodes_can_reference_keys_within_dict_computed_by_function():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "baz": {"type": "dict", "extra_keys_schema": {"type": "integer"}},
        },
    }

    dct = {"foo": "${baz.alpha} * 3", "baz": {"__make_numbers__": {}}}

    def make_numbers(_):
        return {"alpha": "6 + 4", "beta": 20}

    # when
    result = resolve(dct, schema, functions={"make_numbers": make_numbers})

    # then
    assert result["foo"] == 30


def test_function_call_with_input_not_resolved():
    # given
    schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "integer"}, "bar": {"type": "integer"}},
    }

    dct = {"foo": "4", "bar": {"__myraw__": "${foo} + 1"}}

    seen = []

    def myraw(args):
        seen.append(args.input)
        return args.input

    function = Function(myraw, resolve_input=False)

    # when
    result = resolve(dct, schema, functions={"myraw": function})

    # then
    assert seen == ["${foo} + 1"]
    assert result == {"foo": 4, "bar": 5}


def test_function_call_with_input_and_output_not_resolved():
    # given
    schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "integer"}, "bar": {"type": "string"}},
    }

    dct = {"foo": 4, "bar": {"__myraw__": "${foo} + 1"}}

    seen = []

    def myraw(args):
        seen.append(args.input)
        return RawString(args.input)

    function = Function(myraw, resolve_input=False)

    # when
    result = resolve(dct, schema, functions={"myraw": function})

    # then
    assert seen == ["${foo} + 1"]
    assert result == {"foo": 4, "bar": "${foo} + 1"}


def test_function_call_without_resolving_output_does_not_apply_schema():
    # given
    schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "integer"}, "bar": {"type": "string"}},
    }

    dct = {"foo": 4, "bar": {"__myraw__": "${foo} + 1"}}

    seen = []

    def myraw(args):
        seen.append(args.input)
        return RawString(args.input)

    function = Function(myraw, resolve_input=False)

    # when
    result = resolve(dct, schema, functions={"myraw": function})

    # then
    assert seen == ["${foo} + 1"]
    # the result for "bar" is a string even though the schema expects an integer
    assert result == {"foo": 4, "bar": "${foo} + 1"}


def test_function_call_is_given_root_as_lazy_dict_or_list():
    # given
    schema = {
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

    dct = {
        "foo": {
            "a": 1,
            "b": 7,
        },
        "bar": {"__splice__": "foo"},
    }

    def splice(args):
        return args.root.get_keypath(args.input)

    # when
    result = resolve(dct, schema, functions={"splice": splice})

    # then
    assert result["bar"] == {"a": 1, "b": 7}


def test_function_call_get_keypath_to_function_call_returning_a_dict():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "alpha": {"type": "integer"},
            "beta": {
                "type": "dict",
                "required_keys": {"gamma": {"type": "integer"}},
            },
        },
    }

    def triple(args):
        return args.root.get_keypath("beta.gamma") * 3

    def make_beta(_):
        return {"gamma": 10}

    dct = {"alpha": {"__triple__": {}}, "beta": {"__make_beta__": {}}}

    # when
    result = resolve(dct, schema, functions={"triple": triple, "make_beta": make_beta})

    # then
    assert result == {"alpha": 30, "beta": {"gamma": 10}}


def test_function_call_at_root_with_result_producing_references():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
        },
    }

    def myfun(arg):
        return {"foo": 10, "bar": "${foo}"}

    # when
    result = resolve({"__myfun__": {}}, schema, functions={"myfun": myfun})

    # then
    assert result == {"foo": 10, "bar": 10}


def test_function_call_at_root_producing_key_shadowing_builtin():
    # the function call produces a `range` key which shadows the builtin `range`
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "range": {"type": "integer"},
        },
    }

    def myfun(arg):
        return {"foo": 10, "range": 20}

    # when
    result = resolve({"__myfun__": {}}, schema, functions={"myfun": myfun})

    # then
    assert result == {"foo": 10, "range": 20}


def test_function_call_at_root_does_not_produce_key_shadowing_builtin():
    # the function call does not produce range, so smartconfig drops back to the
    # builtin range

    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
        },
    }

    def myfun(arg):
        return {"foo": "${range(10) | length}"}

    # when
    result = resolve({"__myfun__": {}}, schema, functions={"myfun": myfun})

    # then
    assert result == {"foo": 10}


def test_function_call_with_reference_to_result_of_another_function_call_within_dict():
    # given
    schema = {
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

    dct = {"alpha": {"__triple__": {}}, "beta": {"__double__": 10}}

    # when
    result = resolve(dct, schema, functions={"double": double, "triple": triple})

    # then
    assert result == {"alpha": 60, "beta": 20}


def test_function_call_with_reference_to_result_of_another_function_call_within_list():
    # given
    schema = {
        "type": "list",
        "element_schema": {"type": "integer"},
    }

    def double(args):
        return args.input * 2

    def triple(args):
        return args.root[1] * 3

    lst = [{"__triple__": {}}, {"__double__": 10}]

    # when
    result = resolve(lst, schema, functions={"double": double, "triple": triple})

    # then
    assert result == [60, 20]


def test_function_call_that_returns_a_function_call():
    # given
    schema = {
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
    schema = {
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
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
        },
    }

    def add_one(args):
        return {"__add_one__": args.input + 1}

    # when
    with raises(RecursionError) as exc:
        resolve({"foo": {"__add_one__": 10}}, schema, functions={"add_one": add_one})


def test_get_root_with_dictionary_returned_by_function_node():
    # given
    schema = {
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

    dct = {
        "foo": 42,
        "bar": {"__make_dict__": {}},
        "baz": "${ get_root().bar.foo }",
    }

    def make_dict(_):
        return {"foo": 10, "bar": 20}

    # when
    result = resolve(dct, schema, functions={"make_dict": make_dict})

    # then
    assert result == {"foo": 42, "bar": {"foo": 10, "bar": 20}, "baz": 10}


def test_get_root_with_function_at_root_level_returning_a_list():
    # given
    schema = {
        "type": "list",
        "element_schema": {"type": "integer"},
    }

    dct = {"__make_list__": {}}

    def make_list(_):
        return [1, 2, 3, "${ get_root().1 }"]

    # when
    result = resolve(dct, schema, functions={"make_list": make_list})

    # then
    assert result == [1, 2, 3, 2]


def test_get_root_with_top_level_list():
    # given
    schema = {
        "type": "list",
        "element_schema": {"type": "integer"},
    }

    lst = [1, 2, 3, "${ get_root().1 }"]

    # when
    result = resolve(lst, schema)

    # then
    assert result == [1, 2, 3, 2]


def test_get_root_with_top_level_dict():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
        },
    }

    dct = {"foo": 42, "bar": "${ get_root().keys() | length }"}

    # when
    result = resolve(dct, schema)

    # then
    assert result["bar"] == 2
