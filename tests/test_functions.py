"""This module tests the built-in functions in smartconfig.functions.

Tests of the function-calling mechanism itself are in test_resolve.py.

"""

import datetime
import typing

from smartconfig import resolve, exceptions
from smartconfig import functions
from smartconfig.types import Function, Schema, ConfigurationDict, ConfigurationList

from pytest import raises

# raw ==================================================================================


def test_raw_does_not_convert():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {"foo": 42, "bar": {"__raw__": "1 + 3"}}

    # when
    resolved = resolve(cfg, schema, functions={"raw": functions.raw})

    # then
    assert resolved == {"foo": 42, "bar": "1 + 3"}


def test_raw_does_not_interpolate():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {"foo": 42, "bar": {"__raw__": "${this.foo} + 3"}}

    # when
    resolved = resolve(cfg, schema, functions={"raw": functions.raw})

    # then
    assert resolved == {"foo": 42, "bar": "${this.foo} + 3"}


def test_referencing_a_raw_string_in_normal_string_will_interpolate_once():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "string"},
            "baz": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {
        "foo": 42,
        "bar": {"__raw__": "${foo} + 3"},
        "baz": "${bar} + 4",
    }

    # when
    resolved = resolve(cfg, schema, functions={"raw": functions.raw})

    # then
    assert resolved == {"foo": 42, "bar": "${foo} + 3", "baz": "${foo} + 3 + 4"}


def test_raw_with_a_non_string_raises():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "list", "element_schema": {"type": "integer"}},
        },
    }

    cfg: ConfigurationDict = {"foo": 42, "bar": {"__raw__": [1, 2, 3, 4]}}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"raw": functions.raw})

    assert "Input to 'raw' must be a string." in str(exc.value)


# recursive ============================================================================


def test_referencing_a_raw_string_in_recursive_string_will_interpolate_repeatedly():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "string"},
            "baz": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {
        "foo": 42,
        "bar": {"__raw__": "${foo} + 3"},
        "baz": {"__recursive__": "${bar} + 4"},
    }

    # when
    resolved = resolve(
        cfg, schema, functions={"raw": functions.raw, "recursive": functions.recursive}
    )

    # then
    assert resolved == {"foo": 42, "bar": "${foo} + 3", "baz": 49}


def test_recursive_with_a_non_string_raises():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "list", "element_schema": {"type": "integer"}},
        },
    }

    cfg: ConfigurationDict = {"foo": 42, "bar": {"__recursive__": [1, 2, 3, 4]}}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"recursive": functions.recursive})

    assert "Input to 'recursive' must be a string." in str(exc.value)


# update_shallow =======================================================================


def test_update_shallow_does_not_perform_a_deep_update():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "baz": {
                "type": "dict",
                "required_keys": {
                    "a": {"type": "integer"},
                    "b": {
                        "type": "dict",
                        "required_keys": {
                            "c": {"type": "integer"},
                        },
                        "optional_keys": {
                            "d": {"type": "integer"},
                        },
                    },
                },
            },
        },
    }

    cfg: ConfigurationDict = {
        "baz": {
            "__update_shallow__": [
                {"a": 1, "b": {"c": 5, "d": 6}},
                {"a": 3, "b": {"c": 4}},
            ]
        }
    }

    # when
    resolved = resolve(
        cfg, schema, functions={"update_shallow": functions.update_shallow}
    )

    # then
    assert resolved == {
        "baz": {"a": 3, "b": {"c": 4}},
    }


def test_update_shallow_with_four_dictionaries():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "baz": {
                "type": "dict",
                "required_keys": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
            },
        },
    }

    cfg: ConfigurationDict = {
        "baz": {"__update_shallow__": [{"a": 1, "b": 2}, {"a": 3}, {"a": 5}, {"b": 7}]}
    }

    # when
    resolved = resolve(
        cfg, schema, functions={"update_shallow": functions.update_shallow}
    )

    # then
    assert resolved == {
        "baz": {
            "a": 5,
            "b": 7,
        },
    }


def test_update_shallow_raises_if_input_is_not_a_list():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "baz": {
                "type": "dict",
                "required_keys": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
            },
        },
    }

    cfg: ConfigurationDict = {"baz": {"__update_shallow__": 4}}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"update_shallow": functions.update_shallow})

    assert "Input to 'update_shallow' must be a list of dictionaries." in str(exc.value)


def test_update_shallow_raises_if_input_is_not_a_list_of_dicts():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "baz": {
                "type": "dict",
                "required_keys": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
            },
        },
    }

    cfg: ConfigurationDict = {"baz": {"__update_shallow__": [{"hi": "there"}, 5]}}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"update_shallow": functions.update_shallow})

    assert "Input to 'update_shallow' must be a list of dictionaries." in str(exc.value)


def test_update_shallow_raises_if_input_is_empty():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "baz": {
                "type": "dict",
                "required_keys": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
            },
        },
    }

    cfg: ConfigurationDict = {"baz": {"__update_shallow__": []}}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"update_shallow": functions.update_shallow})

    assert "Input to 'update_shallow' must be a non-empty list of dictionaries." in str(
        exc.value
    )


# update ==========================================================================


def test_update_uses_values_from_the_righmost_map():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "baz": {
                "type": "dict",
                "required_keys": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
            },
        },
    }

    cfg: ConfigurationDict = {"baz": {"__update__": [{"a": 1, "b": 2}, {"a": 3}]}}

    # when
    resolved = resolve(cfg, schema, functions={"update": functions.update})

    # then
    assert resolved == {
        "baz": {
            "a": 3,
            "b": 2,
        },
    }


def test_update_is_recursive():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "x": {
                "type": "any",
                "required_keys": {
                    "a": {"type": "dict", "required_keys": {"foo": {"type": "integer"}}}
                },
            }
        },
    }

    cfg: ConfigurationDict = {
        "x": {"__update__": [{"a": {"foo": 1}}, {"a": {"bar": 2}}]}
    }

    # when
    resolved = resolve(cfg, schema, functions={"update": functions.update})

    assert resolved == {"x": {"a": {"foo": 1, "bar": 2}}}


def test_update_with_partial_update():
    # the second dictionary does not have all the keys of the first one at the
    # second level of nesting

    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "baz": {
                "type": "dict",
                "required_keys": {
                    "a": {"type": "integer"},
                    "b": {
                        "type": "dict",
                        "required_keys": {
                            "c": {"type": "integer"},
                        },
                        "optional_keys": {
                            "d": {"type": "integer"},
                        },
                    },
                },
            },
        },
    }

    cfg: ConfigurationDict = {
        "baz": {
            "__update__": [
                {"a": 1, "b": {"c": 5, "d": 6}},
                {"a": 3, "b": {"c": 4}},
            ]
        }
    }

    # when
    resolved = resolve(cfg, schema, functions={"update": functions.update})

    # then
    assert resolved == {
        "baz": {"a": 3, "b": {"c": 4, "d": 6}},
    }


def test_update_with_four_dictionaries():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "baz": {
                "type": "dict",
                "required_keys": {
                    "a": {"type": "integer"},
                    "b": {
                        "type": "dict",
                        "required_keys": {
                            "c": {"type": "integer"},
                        },
                        "optional_keys": {
                            "d": {"type": "integer"},
                        },
                    },
                },
            },
        },
    }

    cfg: ConfigurationDict = {
        "baz": {
            "__update__": [
                {"a": 1, "b": {"c": 5, "d": 6}},
                {"a": 3, "b": {"c": 4}},
                {"a": 2, "b": {"d": 7}},
                {"b": {"c": 9}},
            ]
        }
    }

    # when
    resolved = resolve(cfg, schema, functions={"update": functions.update})

    # then
    assert resolved == {
        "baz": {"a": 2, "b": {"c": 9, "d": 7}},
    }


def test_update_raises_if_input_is_not_a_list():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "baz": {
                "type": "dict",
                "required_keys": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
            },
        },
    }

    cfg: ConfigurationDict = {"baz": {"__update__": 4}}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"update": functions.update})

    assert "Input to 'update' must be a list of dictionaries." in str(exc.value)


def test_update_raises_if_input_is_not_a_list_of_dicts():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "baz": {
                "type": "dict",
                "required_keys": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
            },
        },
    }

    cfg: ConfigurationDict = {"baz": {"__update__": [{"hi": "there"}, 5]}}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"update": functions.update})

    assert "Input to 'update' must be a list of dictionaries." in str(exc.value)


def test_update_raises_if_input_is_empty():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "baz": {
                "type": "dict",
                "required_keys": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
            },
        },
    }

    cfg: ConfigurationDict = {"baz": {"__update__": []}}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"update": functions.update})

    assert "Input to 'update' must be a non-empty list of dictionaries." in str(
        exc.value
    )


# concatenate ==========================================================================


def test_concatenate_with_two_lists():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "baz": {
                "type": "list",
                "element_schema": {"type": "integer"},
            },
        },
    }

    cfg: ConfigurationDict = {"baz": {"__concatenate__": [[1, 2], [3, 4]]}}

    # when
    resolved = resolve(cfg, schema, functions={"concatenate": functions.concatenate})

    # then
    assert resolved == {
        "baz": [1, 2, 3, 4],
    }


def test_concatenate_with_three_lists():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "baz": {
                "type": "list",
                "element_schema": {"type": "integer"},
            },
        },
    }

    cfg: ConfigurationDict = {"baz": {"__concatenate__": [[1, 2], [3, 4], [5, 6]]}}

    # when
    resolved = resolve(cfg, schema, functions={"concatenate": functions.concatenate})

    # then
    assert resolved == {
        "baz": [1, 2, 3, 4, 5, 6],
    }


def test_concatenate_raises_if_input_is_not_a_list():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "baz": {
                "type": "list",
                "element_schema": {"type": "integer"},
            },
        },
    }

    cfg: ConfigurationDict = {"baz": {"__concatenate__": 4}}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"concatenate": functions.concatenate})

    assert "Input to 'concatenate' must be a list of lists." in str(exc.value)


def test_concatenate_raises_if_input_is_not_a_list_of_lists():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "baz": {
                "type": "list",
                "element_schema": {"type": "integer"},
            },
        },
    }

    cfg: ConfigurationDict = {"baz": {"__concatenate__": [[1, 2], 5]}}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"concatenate": functions.concatenate})

    assert "Input to 'concatenate' must be a list of lists." in str(exc.value)


def test_concatenate_raises_if_input_is_empty():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "baz": {
                "type": "list",
                "element_schema": {"type": "integer"},
            },
        },
    }

    cfg: ConfigurationDict = {"baz": {"__concatenate__": []}}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"concatenate": functions.concatenate})

    assert "Input to 'concatenate' must be a non-empty list of lists." in str(exc.value)


# splice ===============================================================================


def test_splice_a_dictionary():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "baz": {
                "type": "dict",
                "required_keys": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
            },
            "foo": {
                "type": "dict",
                "required_keys": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
            },
        },
    }

    cfg: ConfigurationDict = {
        "baz": {"a": 1, "b": 2},
        "foo": {"__splice__": "baz"},
    }

    # when
    resolved = resolve(cfg, schema, functions={"splice": functions.splice})

    # then
    assert resolved == {
        "baz": {"a": 1, "b": 2},
        "foo": {"a": 1, "b": 2},
    }


def test_splice_still_converts():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "baz": {
                "type": "dict",
                "required_keys": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
            },
            "foo": {
                "type": "dict",
                "required_keys": {
                    "a": {"type": "string"},
                    "b": {"type": "string"},
                },
            },
        },
    }

    cfg: ConfigurationDict = {
        "baz": {"a": 1, "b": 2},
        "foo": {"__splice__": "baz"},
    }

    # when
    resolved = resolve(cfg, schema, functions={"splice": functions.splice})

    # then
    assert resolved == {
        "baz": {"a": 1, "b": 2},
        "foo": {"a": "1", "b": "2"},
    }


def test_splice_raises_if_key_does_not_exist():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "baz": {
                "type": "dict",
                "required_keys": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
            },
            "foo": {
                "type": "dict",
                "required_keys": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
            },
        },
    }

    cfg: ConfigurationDict = {
        "baz": {"a": 1, "b": 2},
        "foo": {"__splice__": "quux"},
    }

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"splice": functions.splice})

    assert "Keypath 'quux' does not exist." in str(exc.value)


def test_splice_argument_can_be_an_integer_index_of_list():
    # given a schema for a list of lists
    schema: Schema = {"type": "list", "element_schema": {"type": "string"}}

    cfg: ConfigurationList = [
        "one",
        {"__splice__": 0},
        "three",
    ]

    # when
    resolved = resolve(cfg, schema, functions={"splice": functions.splice})

    # then
    assert resolved == [
        "one",
        "one",
        "three",
    ]


def test_splice_raises_if_key_is_not_a_valid_keypath():
    # given a schema for a list of lists
    schema: Schema = {"type": "list", "element_schema": {"type": "string"}}

    cfg: ConfigurationList = [
        "one",
        {"__splice__": True},
        "three",
    ]

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"splice": functions.splice})

    assert "Input to 'splice' must be a string or int." in str(exc.value)


def test_splice_from_global_variables_raises():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {"__splice__": "baz"}

    with raises(exceptions.ResolutionError) as exc:
        resolve(
            cfg,
            schema,
            functions={"splice": functions.splice},
            global_variables={"baz": 44},
        )

    assert "Keypath 'baz' does not exist." in str(exc.value)


# if ===================================================================================


def test_if_evaluates_then_if_condition_is_true():
    # given
    schema: Schema = {
        "type": "integer",
    }

    cfg: ConfigurationDict = {"__if__": {"condition": "True", "then": 1, "else": 2}}

    # when
    resolved = resolve(cfg, schema, functions={"if": functions.if_})

    # then
    assert resolved == 1


def test_if_evaluates_else_if_condition_is_false():
    # given
    schema: Schema = {
        "type": "integer",
    }

    cfg: ConfigurationDict = {"__if__": {"condition": "False", "then": 1, "else": 2}}

    # when
    resolved = resolve(cfg, schema, functions={"if": functions.if_})

    # then
    assert resolved == 2


def test_if_resolves_the_condition():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "integer"}, "bar": {"type": "boolean"}},
    }

    cfg: ConfigurationDict = {
        "bar": "True",
        "foo": {"__if__": {"condition": "False or ${bar}", "then": 1, "else": 2}},
    }

    # when
    resolved = resolve(cfg, schema, functions={"if": functions.if_})

    # then
    assert resolved == {"bar": True, "foo": 1}


def test_if_resolves_then_branch_only_if_condition_is_true():
    # given
    schema: Schema = {
        "type": "integer",
    }

    cfg: ConfigurationDict = {
        "__if__": {"condition": "False", "then": "not an integer!", "else": "3 + 4"}
    }

    # when
    resolved = resolve(cfg, schema, functions={"if": functions.if_})

    # then
    assert resolved == 7

    # when
    if_body = typing.cast(dict[str, object], cfg["__if__"])
    if_body["condition"] = "True"
    with raises(exceptions.ResolutionError):
        resolve(cfg, schema, functions={"if": functions.if_})


def test_if_raises_if_keys_are_not_condition_then_else():
    # given
    schema: Schema = {
        "type": "integer",
    }

    # extra key
    cfg_1: ConfigurationDict = {
        "__if__": {"condition": "False", "then": 1, "else": 2, "hi": "there"}
    }
    # missing key
    cfg_2: ConfigurationDict = {"__if__": {"then": 1, "else": 2}}
    # missing key
    cfg_3: ConfigurationDict = {"__if__": {"condition": "False", "then": 1}}
    # missing key
    cfg_4: ConfigurationDict = {"__if__": {"condition": "False", "else": 1}}

    for cfg in (cfg_1, cfg_2, cfg_3, cfg_4):
        # when
        with raises(exceptions.ResolutionError) as exc:
            resolve(cfg, schema, functions={"if": functions.if_})

        # then
        assert "must be a dictionary with keys" in str(exc.value)


def test_if_raises_if_input_is_not_a_dict():
    # given
    schema: Schema = {
        "type": "integer",
    }

    cfg: ConfigurationDict = {
        "__if__": "not a dictionary",
    }

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"if": functions.if_})

    assert "Input to 'if' must be a dictionary." in str(exc.value)


def test_if_with_dates_in_comparison():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "date_a": {"type": "date"},
            "date_b": {"type": "date"},
            "most_recent": {"type": "date"},
        },
    }

    cfg: ConfigurationDict = {
        "date_a": "2021-10-05",
        "date_b": "2021-10-06",
        "most_recent": {
            "__if__": {
                "condition": "${date_a > date_b}",
                "then": "${date_a}",
                "else": "${date_b}",
            }
        },
    }

    # when
    resolved = resolve(cfg, schema, functions={"if": functions.if_})

    # then
    assert resolved == {
        "date_a": datetime.date(2021, 10, 5),
        "date_b": datetime.date(2021, 10, 6),
        "most_recent": datetime.date(2021, 10, 6),
    }


# let ==================================================================================


def test_let_provides_local_variables_to_in_block():
    # given
    schema: Schema = {
        "type": "integer",
    }

    cfg: ConfigurationDict = {
        "__let__": {
            "variables": {"x": 3, "y": 4},
            "in": "${x} + ${y}",
        }
    }

    # when
    resolved = resolve(cfg, schema, functions={"let": functions.let})

    # then
    assert resolved == 7


def test_let_can_be_nested_and_local_variables_nest_as_well():
    # given
    schema: Schema = {
        "type": "integer",
    }

    cfg: ConfigurationDict = {
        "__let__": {
            "variables": {"x": 3, "y": 4},
            "in": {
                "__let__": {
                    "variables": {"z": 5},
                    "in": "${x} + ${y} + ${z}",
                }
            },
        }
    }

    # when
    resolved = resolve(cfg, schema, functions={"let": functions.let})

    # then
    assert resolved == 12


def test_let_resolves_the_variables_before_substitution():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {
        "foo": 42,
        "bar": {
            "__let__": {
                "variables": {"x": 3, "y": "${foo}"},
                "in": "${x} + ${y}",
            }
        },
    }

    # when
    resolved = resolve(cfg, schema, functions={"let": functions.let})

    # then
    assert resolved == {"foo": 42, "bar": 45}


def test_local_variables_are_given_priority_over_references_to_elsewhere_in_configuration():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "integer"},
            "y": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {
        "x": 3,
        "y": {
            "__let__": {
                "variables": {"x": 5},
                "in": "${x} + 4",
            }
        },
    }

    # when
    resolved = resolve(cfg, schema, functions={"let": functions.let})

    # then
    assert resolved == {"x": 3, "y": 9}


def test_local_variables_are_given_priority_over_global_variables():
    # given
    schema: Schema = {
        "type": "integer",
    }

    cfg: ConfigurationDict = {
        "__let__": {
            "variables": {"x": 5},
            "in": "${x}",
        },
    }

    # when
    resolved = resolve(
        cfg, schema, functions={"let": functions.let}, global_variables={"x": 7}
    )

    # then
    assert resolved == 5


def test_let_raises_if_input_is_not_a_dict():
    # given
    schema: Schema = {
        "type": "integer",
    }

    cfg: ConfigurationDict = {
        "__let__": "not a dictionary",
    }

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"let": functions.let})

    assert "Input to 'let' must be a dictionary." in str(exc.value)


def test_let_raises_if_does_not_contain_keys_variables_and_in():
    # given
    schema: Schema = {
        "type": "integer",
    }

    cfg: ConfigurationDict = {
        "__let__": {"x": 3},
    }

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"let": functions.let})

    assert "must be a dictionary with keys" in str(exc.value)


def test_let_raises_if_variables_is_not_a_dict():
    # given
    schema: Schema = {
        "type": "integer",
    }

    cfg: ConfigurationDict = {
        "__let__": {"variables": "not a dictionary", "in": 3},
    }

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"let": functions.let})

    assert "must be a dictionary" in str(exc.value)


def test_let_with_variables_that_are_resolved_from_a_function():
    # given
    @Function.new()
    def variables(_):
        return {"x": 3, "y": 4}

    schema: Schema = {
        "type": "integer",
    }

    cfg: ConfigurationDict = {
        "__let__": {
            "variables": {"__variables__": {}},
            "in": "${x} + ${y}",
        }
    }

    # when
    resolved = resolve(
        cfg, schema, functions={"let": functions.let, "variables": variables}
    )

    # then
    assert resolved == 7


def test_let_raises_if_variables_do_not_resolve_to_a_dict():
    # given
    @Function.new()
    def variables(_):
        return 42

    schema: Schema = {
        "type": "integer",
    }

    cfg: ConfigurationDict = {
        "__let__": {
            "variables": {"__variables__": {}},
            "in": "${x} + ${y}",
        }
    }

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"let": functions.let, "variables": variables})

    assert "must be a dictionary" in str(exc.value)


# loop =================================================================================


def test_loop_over_a_list():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {
            "type": "dict",
            "required_keys": {"x": {"type": "integer"}, "y": {"type": "integer"}},
        },
    }

    cfg: ConfigurationDict = {
        "__loop__": {
            "variable": "x",
            "over": [1, 2, 3],
            "in": {
                "x": "${2*x}",
                "y": "${3*x}",
            },
        },
    }

    # when
    resolved = resolve(cfg, schema, functions={"loop": functions.loop})

    # then
    assert resolved == [
        {"x": 2, "y": 3},
        {"x": 4, "y": 6},
        {"x": 6, "y": 9},
    ]


def test_nested_loop():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {
            "type": "list",
            "element_schema": {
                "type": "dict",
                "required_keys": {"x": {"type": "integer"}, "y": {"type": "integer"}},
            },
        },
    }

    cfg: ConfigurationDict = {
        "__loop__": {
            "variable": "x",
            "over": [1, 2],
            "in": {
                "__loop__": {
                    "variable": "y",
                    "over": [3, 4],
                    "in": {
                        "x": "${x}",
                        "y": "${y}",
                    },
                }
            },
        },
    }

    # when
    resolved = resolve(cfg, schema, functions={"loop": functions.loop})

    # then
    assert resolved == [
        [
            {"x": 1, "y": 3},
            {"x": 1, "y": 4},
        ],
        [
            {"x": 2, "y": 3},
            {"x": 2, "y": 4},
        ],
    ]


def test_loop_producing_list_of_dicts():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {
            "type": "dict",
            "required_keys": {"x": {"type": "integer"}, "y": {"type": "integer"}},
        },
    }

    cfg: ConfigurationDict = {
        "__loop__": {
            "variable": "pair",
            "over": typing.cast(ConfigurationList, [(1, 2), (3, 4), (5, 6)]),
            "in": {
                "x": "${pair[0]}",
                "y": "${pair[1]}",
            },
        },
    }

    # when
    resolved = resolve(cfg, schema, functions={"loop": functions.loop})

    # then
    assert resolved == [
        {"x": 1, "y": 2},
        {"x": 3, "y": 4},
        {"x": 5, "y": 6},
    ]


def test_loop_raises_if_input_is_not_a_dict():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {
            "type": "dict",
            "required_keys": {"x": {"type": "integer"}, "y": {"type": "integer"}},
        },
    }

    cfg: ConfigurationDict = {
        "__loop__": "not a dictionary",
    }

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"loop": functions.loop})

    assert "must be a dictionary" in str(exc.value)


def test_loop_raises_if_does_not_contain_keys_variable_over_and_in():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {
            "type": "dict",
            "required_keys": {"x": {"type": "integer"}, "y": {"type": "integer"}},
        },
    }

    cfg: ConfigurationDict = {
        "__loop__": {"x": 3},
    }

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"loop": functions.loop})

    assert "must be a dictionary with keys" in str(exc.value)


def test_loop_with_function_returning_over():
    def over(_):
        return [1, 2, 3]

    # given
    schema: Schema = {"type": "list", "element_schema": {"type": "integer"}}

    cfg: ConfigurationDict = {
        "__loop__": {"variable": "x", "over": {"__over__": {}}, "in": "${x} + 1"},
    }

    # when
    resolved = resolve(cfg, schema, functions={"loop": functions.loop, "over": over})

    # then
    assert resolved == [2, 3, 4]


def test_loop_raises_if_value_of_over_does_not_resolve_to_a_list():
    def over(_):
        return 42

    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {
            "type": "dict",
            "required_keys": {"x": {"type": "integer"}, "y": {"type": "integer"}},
        },
    }

    cfg: ConfigurationDict = {
        "__loop__": {"variable": "x", "over": {"__over__": {}}, "in": {"x": 1, "y": 2}},
    }

    # when
    with raises(exceptions.ResolutionError):
        resolve(cfg, schema, functions={"loop": functions.loop, "over": over})


# dict_from_items ======================================================================


def test_dict_from_items_simple_example():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {
        "__dict_from_items__": [
            {"key": "foo", "value": 42},
            {
                "key": "bar",
                "value": "hello",
            },
        ]
    }

    # when
    resolved = resolve(
        cfg, schema, functions={"dict_from_items": functions.dict_from_items}
    )

    # then
    assert resolved == {"foo": 42, "bar": "hello"}


def test_dict_from_items_generated_within_loop():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
            "baz": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {
        "__dict_from_items__": {
            "__loop__": {
                "variable": "pair",
                "over": typing.cast(
                    ConfigurationList, [("foo", 1), ("bar", 2), ("baz", 3)]
                ),
                "in": {
                    "key": "${pair[0]}",
                    "value": "${pair[1]}",
                },
            }
        }
    }

    # when
    resolved = resolve(
        cfg,
        schema,
        functions={
            "dict_from_items": functions.dict_from_items,
            "loop": functions.loop,
        },
    )

    # then
    assert resolved == {"foo": 1, "bar": 2, "baz": 3}


def test_dict_from_items_generated_within_loop_checks_schema_for_required_keys():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
            "baz": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {
        "__dict_from_items__": {
            "__loop__": {
                "variable": "pair",
                "over": typing.cast(
                    ConfigurationList, [("foo", 1), ("bar", 2), ("no!", 3)]
                ),
                "in": {
                    "key": "${pair[0]}",
                    "value": "${pair[1]}",
                },
            }
        }
    }

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(
            cfg,
            schema,
            functions={
                "dict_from_items": functions.dict_from_items,
                "loop": functions.loop,
            },
        )

    assert "missing required key" in str(exc.value)


def test_dict_from_items_raises_if_input_is_not_a_list():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {
        "__dict_from_items__": "not a list",
    }

    # when
    with raises(exceptions.ResolutionError):
        resolve(cfg, schema, functions={"dict_from_items": functions.dict_from_items})


def test_dict_from_items_raises_if_input_is_not_a_list_of_dicts_each_with_keys_key_and_value():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {
        "__dict_from_items__": [
            {"key": "foo", "value": 42},
            {"key": "bar", "value": 42},
            "not a dictionary",
        ]
    }

    # when
    with raises(exceptions.ResolutionError):
        resolve(cfg, schema, functions={"dict_from_items": functions.dict_from_items})


# zip ==================================================================================


def test_zip_two_lists():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {
            "type": "list",
            "element_schema": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {
        "__zip__": [
            [1, 2, 3],
            [4, 5, 6],
        ]
    }

    # when
    resolved = resolve(cfg, schema, functions={"zip": functions.zip_})

    # then
    assert resolved == [
        [1, 4],
        [2, 5],
        [3, 6],
    ]


def test_zip_three_lists():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {
            "type": "list",
            "element_schema": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {
        "__zip__": [
            [1, 2, 3],
            [4, 5, 6],
            [7, 8, 9],
        ]
    }

    # when
    resolved = resolve(cfg, schema, functions={"zip": functions.zip_})

    # then
    assert resolved == [
        [1, 4, 7],
        [2, 5, 8],
        [3, 6, 9],
    ]


def test_zip_raises_if_input_is_not_a_list_of_lists():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {
            "type": "list",
            "element_schema": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {
        "__zip__": [
            [1, 2, 3],
            4,
        ]
    }

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"zip": functions.zip_})

    assert "Input to 'zip' must be a list of lists." in str(exc.value)


def test_zip_raises_if_input_is_empty():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {
            "type": "list",
            "element_schema": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {"__zip__": []}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"zip": functions.zip_})

    assert "Input to 'zip' must be a non-empty list of lists." in str(exc.value)


# filter ===============================================================================


def test_filter_simple_example():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {"type": "integer"},
    }

    cfg: ConfigurationDict = {
        "__filter__": {
            "iterable": [1, 2, 3, 4, 5],
            "variable": "x",
            "condition": "${x % 2 == 0} or ${x == 5}",
        }
    }

    # when
    resolved = resolve(cfg, schema, functions={"filter": functions.filter_})

    # then
    assert resolved == [2, 4, 5]


def test_filter_raises_if_input_is_not_a_dict():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {"type": "integer"},
    }

    cfg: ConfigurationDict = {
        "__filter__": "not a dictionary",
    }

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"filter": functions.filter_})

    assert "must be a dictionary" in str(exc.value)


def test_filter_raises_if_value_of_iterable_does_not_resolve_to_a_list():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {"type": "integer"},
    }

    cfg: ConfigurationDict = {
        "__filter__": {
            "iterable": 42,
            "variable": "x",
            "condition": "${x % 2 == 0}",
        }
    }

    # when
    with raises(exceptions.ResolutionError):
        resolve(cfg, schema, functions={"filter": functions.filter_})


# range ================================================================================


def test_range_uses_start_0_by_default():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {"type": "integer"},
    }

    cfg: ConfigurationDict = {
        "__range__": {
            "stop": 5,
        }
    }

    # when
    resolved = resolve(cfg, schema, functions={"range": functions.range_})

    # then
    assert resolved == [0, 1, 2, 3, 4]


def test_range_with_explicit_start():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {"type": "integer"},
    }

    cfg: ConfigurationDict = {
        "__range__": {
            "start": 1,
            "stop": 5,
        }
    }

    # when
    resolved = resolve(cfg, schema, functions={"range": functions.range_})

    # then
    assert resolved == [1, 2, 3, 4]


def test_range_with_negative_step():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {"type": "integer"},
    }

    cfg: ConfigurationDict = {
        "__range__": {
            "start": 5,
            "stop": 1,
            "step": -1,
        }
    }

    # when
    resolved = resolve(cfg, schema, functions={"range": functions.range_})

    # then
    assert resolved == [5, 4, 3, 2]


def test_range_with_step_of_3():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {"type": "integer"},
    }

    cfg: ConfigurationDict = {
        "__range__": {
            "start": 1,
            "stop": 10,
            "step": 3,
        }
    }

    # when
    resolved = resolve(cfg, schema, functions={"range": functions.range_})

    # then
    assert resolved == [1, 4, 7]


def test_range_raises_if_input_is_not_a_dict():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {"type": "integer"},
    }

    cfg: ConfigurationDict = {
        "__range__": "not a dictionary",
    }

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"range": functions.range_})

    assert "must be a dictionary" in str(exc.value)


def test_range_raises_if_stop_is_not_provided():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {"type": "integer"},
    }

    cfg: ConfigurationDict = {
        "__range__": {
            "start": 1,
        }
    }

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"range": functions.range_})

    assert "with a key 'stop'" in str(exc.value)


def test_range_raises_if_non_integer_values_are_provided():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {"type": "integer"},
    }

    cfg: ConfigurationDict = {
        "__range__": {
            "start": 1,
            "stop": 3.2,
        }
    }

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"range": functions.range_})

    assert "must be integers" in str(exc.value)


def test_range_raises_if_extra_keys_are_provided():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {"type": "integer"},
    }

    cfg: ConfigurationDict = {
        "__range__": {
            "start": 1,
            "stop": 5,
            "extra": "not allowed",
        }
    }

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"range": functions.range_})

    assert "must be a dictionary with keys" in str(exc.value)
