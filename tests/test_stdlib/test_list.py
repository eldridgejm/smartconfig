"""Tests for smartconfig.stdlib.list: concatenate, zip, loop, filter, and range."""

import typing

from smartconfig import resolve, exceptions, CORE_FUNCTIONS
from smartconfig.stdlib.list import concatenate, zip_, range_, loop, filter_
from smartconfig.types import Schema, ConfigurationDict, ConfigurationList

from pytest import raises

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
    resolved = resolve(cfg, schema, functions={"concatenate": concatenate})

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
    resolved = resolve(cfg, schema, functions={"concatenate": concatenate})

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
        resolve(cfg, schema, functions={"concatenate": concatenate})

    assert "Input to 'list.concatenate' must be a list of lists." in str(exc.value)


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
        resolve(cfg, schema, functions={"concatenate": concatenate})

    assert "Input to 'list.concatenate' must be a list of lists." in str(exc.value)


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
        resolve(cfg, schema, functions={"concatenate": concatenate})

    assert "Input to 'list.concatenate' must be a non-empty list of lists." in str(
        exc.value
    )


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
    resolved = resolve(cfg, schema, functions={"zip": zip_})

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
    resolved = resolve(cfg, schema, functions={"zip": zip_})

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
        resolve(cfg, schema, functions={"zip": zip_})

    assert "Input to 'list.zip' must be a list of lists." in str(exc.value)


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
        resolve(cfg, schema, functions={"zip": zip_})

    assert "Input to 'list.zip' must be a non-empty list of lists." in str(exc.value)


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
    resolved = resolve(cfg, schema, functions={"loop": loop})

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
    resolved = resolve(cfg, schema, functions={"loop": loop})

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
    resolved = resolve(cfg, schema, functions={"loop": loop})

    # then
    assert resolved == [
        {"x": 1, "y": 2},
        {"x": 3, "y": 4},
        {"x": 5, "y": 6},
    ]


def test_loop_reports_an_error_in_its_body_at_the_element():
    # the body divides by i - 2, so it fails for the second element (i = 2): the
    # error should say which element, x.1.v, not just x.v
    cfg: ConfigurationDict = {
        "x": {
            "__loop__": {
                "variable": "i",
                "over": [1, 2],
                "in": {"v": "${ 10 // (i - 2) }"},
            }
        }
    }
    schema: Schema = {
        "type": "dict",
        "required_keys": {"x": {"type": "list", "element_schema": {"type": "any"}}},
    }

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"loop": loop})

    assert exc.value.keypath == ("x", "1", "v")


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
        resolve(cfg, schema, functions={"loop": loop})

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
        resolve(cfg, schema, functions={"loop": loop})

    assert "must be a dictionary with keys" in str(exc.value)


def test_loop_under_an_any_schema():
    # the schema is "any", so it has no element_schema for the loop's elements;
    # they should be resolved under "any" too
    cfg: ConfigurationDict = {
        "x": {"__loop__": {"variable": "i", "over": [1, 2], "in": "${ i }"}}
    }

    resolved = resolve(cfg, {"type": "any"}, functions={"loop": loop})

    # "${ i }" is interpolated into a string, and the "any" type doesn't convert
    # it, so the numbers come out as strings
    assert resolved == {"x": ["1", "2"]}


def test_loop_raises_if_variable_is_not_a_string():
    # the loop variable must be a name, but it's the integer 1
    cfg: ConfigurationDict = {
        "x": {"__loop__": {"variable": 1, "over": [1], "in": "a"}}
    }
    schema: Schema = {
        "type": "dict",
        "required_keys": {"x": {"type": "list", "element_schema": {"type": "string"}}},
    }

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"loop": loop})

    assert exc.value.keypath == ("x",)
    assert "'variable'" in str(exc.value)


def test_loop_raises_if_variable_is_reserved_by_jinja():
    # ${ true } is Jinja's literal True, so a variable named true could never be
    # referred to: the body would silently ignore the elements
    cfg: ConfigurationDict = {
        "x": {"__loop__": {"variable": "true", "over": [1, 2], "in": "${ true }"}}
    }
    schema: Schema = {
        "type": "dict",
        "required_keys": {"x": {"type": "list", "element_schema": {"type": "any"}}},
    }

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"loop": loop})

    assert exc.value.keypath == ("x",)
    assert '"true" is reserved by Jinja' in str(exc.value)


def test_loop_with_function_returning_over():
    def over(_):
        return [1, 2, 3]

    # given
    schema: Schema = {"type": "list", "element_schema": {"type": "integer"}}

    cfg: ConfigurationDict = {
        "__loop__": {"variable": "x", "over": {"__over__": {}}, "in": "${x + 1}"},
    }

    # when
    resolved = resolve(cfg, schema, functions={"loop": loop, "over": over})

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
        resolve(cfg, schema, functions={"loop": loop, "over": over})


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
            "condition": "${(x % 2 == 0) or (x == 5)}",
        }
    }

    # when
    resolved = resolve(cfg, schema, functions={"filter": filter_})

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
        resolve(cfg, schema, functions={"filter": filter_})

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
        resolve(cfg, schema, functions={"filter": filter_})


def test_filter_raises_if_variable_is_not_a_string():
    # the filter variable must be a name, but it's the integer 3
    cfg: ConfigurationDict = {
        "x": {
            "__filter__": {
                "iterable": [1, 2],
                "variable": 3,
                "condition": "${ True }",
            }
        }
    }
    schema: Schema = {
        "type": "dict",
        "required_keys": {"x": {"type": "list", "element_schema": {"type": "any"}}},
    }

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"filter": filter_})

    assert exc.value.keypath == ("x",)
    assert "'variable'" in str(exc.value)


def test_filter_raises_if_variable_is_reserved_by_jinja():
    # ${ self } is Jinja's template object, so a variable named self could never
    # be referred to in the condition
    cfg: ConfigurationDict = {
        "x": {
            "__filter__": {
                "iterable": [1, 2],
                "variable": "self",
                "condition": "${ True }",
            }
        }
    }
    schema: Schema = {
        "type": "dict",
        "required_keys": {"x": {"type": "list", "element_schema": {"type": "any"}}},
    }

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"filter": filter_})

    assert exc.value.keypath == ("x",)
    assert '"self" is reserved by Jinja' in str(exc.value)


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
    resolved = resolve(cfg, schema, functions={"range": range_})

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
    resolved = resolve(cfg, schema, functions={"range": range_})

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
    resolved = resolve(cfg, schema, functions={"range": range_})

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
    resolved = resolve(cfg, schema, functions={"range": range_})

    # then
    assert resolved == [1, 4, 7]


def test_range_values_can_come_from_references():
    # given — stop is "${ n }", which interpolates to the string "3", not the
    # integer 3
    schema: Schema = {"type": "list", "element_schema": {"type": "integer"}}
    cfg: ConfigurationDict = {"__range__": {"stop": "${ n }"}}

    # when
    resolved = resolve(
        cfg, schema, functions={"range": range_}, global_variables={"n": 3}
    )

    # then
    assert resolved == [0, 1, 2]


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
        resolve(cfg, schema, functions={"range": range_})

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
        resolve(cfg, schema, functions={"range": range_})

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
        resolve(cfg, schema, functions={"range": range_})

    assert "'stop' in 'list.range' must be an integer" in str(exc.value)


def test_range_raises_if_step_is_zero():
    # a step of 0 would never reach stop
    cfg: ConfigurationDict = {"x": {"__range__": {"stop": 3, "step": 0}}}

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, {"type": "any"}, functions={"range": range_})

    assert exc.value.keypath == ("x",)
    assert "'step'" in str(exc.value)


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
        resolve(cfg, schema, functions={"range": range_})

    assert "must be a dictionary with keys" in str(exc.value)


# raw values in input or body ==========================================================
#
# A __raw__ value resolves to its literal contents. These functions return it as
# part of their result, and it must not be interpolated or evaluated again.

_raw = CORE_FUNCTIONS["raw"]
_ANY_LIST: Schema = {"type": "list", "element_schema": {"type": "any"}}


def test_concatenate_keeps_raw_values_literal():
    # given
    cfg: ConfigurationList = [[{"__raw__": "${q}"}], [{"__raw__": {"__splice__": "c"}}]]

    # when
    resolved = resolve(
        {"__concatenate__": cfg},
        _ANY_LIST,
        functions={"concatenate": concatenate, "raw": _raw},
    )

    # then
    assert resolved == ["${q}", {"__splice__": "c"}]


def test_zip_keeps_raw_values_literal():
    # given
    cfg: ConfigurationDict = {"__zip__": [[{"__raw__": "${q}"}], [1]]}

    # when
    resolved = resolve(cfg, _ANY_LIST, functions={"zip": zip_, "raw": _raw})

    # then
    assert resolved == [["${q}", 1]]


def test_loop_keeps_raw_values_in_the_body_literal():
    # given
    cfg: ConfigurationDict = {
        "__loop__": {"variable": "i", "over": [1, 2], "in": {"__raw__": "${q}"}}
    }

    # when
    resolved = resolve(cfg, _ANY_LIST, functions={"loop": loop, "raw": _raw})

    # then
    assert resolved == ["${q}", "${q}"]


def test_filter_keeps_raw_values_literal():
    # given
    cfg: ConfigurationDict = {
        "__filter__": {
            "iterable": [{"__raw__": "${q}"}],
            "variable": "v",
            "condition": "True",
        }
    }

    # when
    resolved = resolve(cfg, _ANY_LIST, functions={"filter": filter_, "raw": _raw})

    # then
    assert resolved == ["${q}"]
