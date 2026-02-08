"""Tests for smartconfig.stdlib.list: concatenate, zip, loop, filter, and range."""

import typing

from smartconfig import resolve, exceptions
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
        resolve(cfg, schema, functions={"concatenate": concatenate})

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
        resolve(cfg, schema, functions={"concatenate": concatenate})

    assert "Input to 'concatenate' must be a non-empty list of lists." in str(exc.value)


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
        resolve(cfg, schema, functions={"zip": zip_})

    assert "Input to 'zip' must be a non-empty list of lists." in str(exc.value)


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
        resolve(cfg, schema, functions={"range": range_})

    assert "must be a dictionary with keys" in str(exc.value)
