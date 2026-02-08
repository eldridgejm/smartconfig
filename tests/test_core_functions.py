"""Tests of the core functions: raw, splice, let, if, and resolve."""

import datetime
import typing

from smartconfig import resolve, exceptions, CORE_FUNCTIONS
from smartconfig.types import (
    ConfigurationDict,
    ConfigurationList,
    Function,
    Schema,
)

import pytest

# Convenience aliases for the individual core functions.
_raw = CORE_FUNCTIONS["raw"]
_splice = CORE_FUNCTIONS["splice"]
_let = CORE_FUNCTIONS["let"]
_resolve_fn = CORE_FUNCTIONS["resolve"]
_fully_resolve = CORE_FUNCTIONS["fully_resolve"]
_if = CORE_FUNCTIONS["if"]
_template = CORE_FUNCTIONS["template"]
_use = CORE_FUNCTIONS["use"]

# raw ==================================================================================


def test_raw_strings_are_not_interpolated():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {"foo": "this", "bar": {"__raw__": "${foo}"}}

    # when
    result = resolve(cfg, schema, functions={"raw": _raw})

    # then
    assert result["bar"] == "${foo}"


def test_raw_strings_are_still_type_converted():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {"foo": "this", "bar": {"__raw__": "42"}}

    # when
    result = resolve(cfg, schema, functions={"raw": _raw})

    # then — raw bypasses interpolation, but type conversion still applies
    assert result["bar"] == 42


def test_raw_list_with_interpolation_placeholders():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "list", "element_schema": {"type": "string"}},
        },
    }

    cfg: ConfigurationDict = {
        "foo": "hello",
        "bar": {"__raw__": ["${foo}", "${foo} world"]},
    }

    # when
    result = resolve(cfg, schema, functions={"raw": _raw})

    # then — placeholders are not interpolated
    assert result["bar"] == ["${foo}", "${foo} world"]


def test_raw_dict_with_interpolation_placeholders():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {
                "type": "dict",
                "required_keys": {
                    "x": {"type": "string"},
                    "y": {"type": "string"},
                },
            },
        },
    }

    cfg: ConfigurationDict = {
        "foo": "hello",
        "bar": {"__raw__": {"x": "${foo}", "y": "${foo} world"}},
    }

    # when
    result = resolve(cfg, schema, functions={"raw": _raw})

    # then — placeholders are not interpolated
    assert result["bar"] == {"x": "${foo}", "y": "${foo} world"}


def test_raw_dict_that_looks_like_function_call_is_not_evaluated():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "bar": {"type": "any"},
        },
    }

    cfg: ConfigurationDict = {
        "bar": {"__raw__": {"__splice__": "something"}},
    }

    # when
    result = resolve(cfg, schema, functions={"raw": _raw, "splice": _splice})

    # then — the inner dict is returned as-is, not treated as a function call
    assert result["bar"] == {"__splice__": "something"}


# splice ===============================================================================


def test_splice_returns_referenced_value():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {"foo": 42, "bar": {"__splice__": "foo"}}

    # when
    result = resolve(cfg, schema, functions={"splice": _splice})

    # then
    assert result == {"foo": 42, "bar": 42}


def test_splice_referenced_string_is_resolved():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "name": {"type": "string"},
            "greeting": {"type": "string"},
            "copy": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {
        "name": "Justin",
        "greeting": "hello ${name}",
        "copy": {"__splice__": "greeting"},
    }

    # when
    result = resolve(cfg, schema, functions={"splice": _splice})

    # then
    assert result == {
        "name": "Justin",
        "greeting": "hello Justin",
        "copy": "hello Justin",
    }


def test_splice_referenced_value_is_a_dict():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "original": {
                "type": "dict",
                "required_keys": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                },
            },
            "copy": {
                "type": "dict",
                "required_keys": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                },
            },
        },
    }

    cfg: ConfigurationDict = {
        "original": {"x": 1, "y": 2},
        "copy": {"__splice__": "original"},
    }

    # when
    result = resolve(cfg, schema, functions={"splice": _splice})

    # then
    assert result == {"original": {"x": 1, "y": 2}, "copy": {"x": 1, "y": 2}}


def test_splice_referenced_value_is_a_list():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "items": {"type": "list", "element_schema": {"type": "integer"}},
            "copy": {"type": "list", "element_schema": {"type": "integer"}},
        },
    }

    cfg: ConfigurationDict = {
        "items": [1, 2, 3],
        "copy": {"__splice__": "items"},
    }

    # when
    result = resolve(cfg, schema, functions={"splice": _splice})

    # then
    assert result == {"items": [1, 2, 3], "copy": [1, 2, 3]}


def test_splice_referenced_dict_with_interpolation_placeholders():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "name": {"type": "string"},
            "template": {
                "type": "dict",
                "required_keys": {
                    "msg": {"type": "string"},
                },
            },
            "copy": {
                "type": "dict",
                "required_keys": {
                    "msg": {"type": "string"},
                },
            },
        },
    }

    cfg: ConfigurationDict = {
        "name": "world",
        "template": {"msg": "hello ${name}"},
        "copy": {"__splice__": "template"},
    }

    # when
    result = resolve(cfg, schema, functions={"splice": _splice})

    # then — the referenced dict's strings are interpolated
    assert result == {
        "name": "world",
        "template": {"msg": "hello world"},
        "copy": {"msg": "hello world"},
    }


def test_splice_referenced_value_is_a_function_call():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "items": {"type": "list", "element_schema": {"type": "integer"}},
            "copy": {"type": "list", "element_schema": {"type": "integer"}},
        },
    }

    def double(args):
        return args.input + args.input

    cfg: ConfigurationDict = {
        "items": {"__double__": [1, 2]},
        "copy": {"__splice__": "items"},
    }

    # when
    result = resolve(cfg, schema, functions={"splice": _splice, "double": double})

    # then — the function call is evaluated, and splice gets the result
    assert result == {"items": [1, 2, 1, 2], "copy": [1, 2, 1, 2]}


def test_splice_with_nested_keypath():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {
                "type": "dict",
                "required_keys": {
                    "bar": {
                        "type": "dict",
                        "required_keys": {
                            "baz": {"type": "integer"},
                        },
                    },
                },
            },
            "copy": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {
        "foo": {"bar": {"baz": 99}},
        "copy": {"__splice__": "foo.bar.baz"},
    }

    # when
    result = resolve(cfg, schema, functions={"splice": _splice})

    # then
    assert result == {"foo": {"bar": {"baz": 99}}, "copy": 99}


def test_splice_nested_keypath_into_function_call_result():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "data": {
                "type": "dict",
                "required_keys": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                },
            },
            "copy": {"type": "integer"},
        },
    }

    def make_dict(args):
        return {"x": args.input, "y": args.input * 2}

    cfg: ConfigurationDict = {
        "data": {"__make_dict__": 5},
        "copy": {"__splice__": "data.y"},
    }

    # when
    result = resolve(cfg, schema, functions={"splice": _splice, "make_dict": make_dict})

    # then
    assert result == {"data": {"x": 5, "y": 10}, "copy": 10}


def test_splice_converts_to_target_schema():
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
    result = resolve(cfg, schema, functions={"splice": _splice})

    # then — integers are converted to strings per the target schema
    assert result == {
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
    with pytest.raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"splice": _splice})

    assert "Keypath 'quux' does not exist." in str(exc.value)


def test_splice_raises_if_data_does_not_match_target_schema():
    # given — source has keys "a" and "b", but target requires "a", "b", and "c"
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "source": {
                "type": "dict",
                "required_keys": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
            },
            "target": {
                "type": "dict",
                "required_keys": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                    "c": {"type": "integer"},
                },
            },
        },
    }

    cfg: ConfigurationDict = {
        "source": {"a": 1, "b": 2},
        "target": {"__splice__": "source"},
    }

    # when
    with pytest.raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"splice": _splice})

    assert "missing required key" in str(exc.value)


def test_splice_raises_when_root_is_a_splice():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {"__splice__": "baz"}

    with pytest.raises(exceptions.ResolutionError):
        resolve(
            cfg,
            schema,
            functions={"splice": _splice},
            global_variables={"baz": 44},
        )


def test_splice_does_not_see_global_variables():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {
        "foo": 1,
        "bar": {"__splice__": "baz"},
    }

    # when — "baz" exists as a global variable but not in the config
    with pytest.raises(exceptions.ResolutionError) as exc:
        resolve(
            cfg,
            schema,
            functions={"splice": _splice},
            global_variables={"baz": 44},
        )

    assert "Keypath 'baz' does not exist." in str(exc.value)


# let ==================================================================================


def test_let_references_self():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "outer": {
                "type": "dict",
                "required_keys": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                },
            },
        },
    }

    cfg: ConfigurationDict = {
        "outer": {
            "__let__": {
                "references": {"this": "__this__"},
                "in": {
                    "x": 10,
                    "y": "${this.x}",
                },
            }
        },
    }

    # when
    result = resolve(cfg, schema, functions={"let": _let})

    assert result == {"outer": {"x": 10, "y": 10}}


def test_let_references_self_uses_innermost_scope():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "a": {"type": "integer"},
            "inner": {
                "type": "dict",
                "required_keys": {
                    "b": {"type": "integer"},
                    "from_inner": {"type": "integer"},
                    "from_outer": {"type": "integer"},
                },
            },
        },
    }

    cfg: ConfigurationDict = {
        "__let__": {
            "references": {"this": "__this__"},
            "in": {
                "a": 1,
                "inner": {
                    "__let__": {
                        "references": {"this": "__this__"},
                        "in": {
                            "b": 2,
                            # "this" here should refer to the inner dict
                            "from_inner": "${this.b}",
                            # the outer "a" is still reachable by absolute path
                            "from_outer": "${a}",
                        },
                    }
                },
            },
        }
    }

    # when
    result = resolve(cfg, schema, functions={"let": _let})

    # then — ${this.b} uses the inner "this", not the outer one
    assert result == {"a": 1, "inner": {"b": 2, "from_inner": 2, "from_outer": 1}}


def test_let_references_self_combined_with_variables():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "integer"},
            "y": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {
        "__let__": {
            "variables": {"scale": 10},
            "references": {"this": "__this__"},
            "in": {
                "x": 3,
                "y": "${this.x * scale}",
            },
        }
    }

    # when
    result = resolve(cfg, schema, functions={"let": _let})

    # then
    assert result == {"x": 3, "y": 30}


def test_let_references_self_with_nested_dotted_access():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "nested": {
                "type": "dict",
                "required_keys": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
            },
            "result": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {
        "__let__": {
            "references": {"this": "__this__"},
            "in": {
                "nested": {"a": 1, "b": 2},
                "result": "${this.nested.a + this.nested.b}",
            },
        }
    }

    # when
    result = resolve(cfg, schema, functions={"let": _let})

    # then
    assert result == {"nested": {"a": 1, "b": 2}, "result": 3}


def test_let_references_self_with_list_in_block():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {"type": "integer"},
    }

    cfg: ConfigurationDict = {
        "__let__": {
            "references": {"this": "__this__"},
            "in": [10, "${this[0] + 5}"],
        }
    }

    # when
    result = resolve(cfg, schema, functions={"let": _let})

    # then
    assert result == [10, 15]


def test_let_references_self_raises_on_scalar_in_block():
    # given
    schema: Schema = {"type": "integer"}

    cfg: ConfigurationDict = {
        "__let__": {
            "references": {"this": "__this__"},
            "in": "${this}",
        }
    }

    # when
    with pytest.raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"let": _let})

    assert "'__this__' cannot be used when 'in' is a scalar value" in str(exc.value)


def test_let_arithmetic_with_this_reference():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "integer"},
            "y": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {
        "__let__": {
            "references": {"this": "__this__"},
            "in": {
                "x": 7,
                "y": "${this.x + 3}",
            },
        }
    }

    # when
    result = resolve(cfg, schema, functions={"let": _let})

    # then
    assert result == {"x": 7, "y": 10}


def test_let_references_previous_in_list():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {
            "type": "dict",
            "required_keys": {
                "x": {"type": "integer"},
            },
        },
    }

    cfg: ConfigurationList = [
        {"x": 10},
        {
            "__let__": {
                "references": {"prev": "__previous__"},
                "in": {
                    "x": "${prev.x + 1}",
                },
            }
        },
    ]

    # when
    result = resolve(cfg, schema, functions={"let": _let})

    # then
    assert result == [{"x": 10}, {"x": 11}]


def test_let_references_previous_raises_on_first_element():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {"type": "integer"},
    }

    cfg: ConfigurationList = [
        {
            "__let__": {
                "references": {"prev": "__previous__"},
                "in": "${prev}",
            }
        },
    ]

    # when
    with pytest.raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"let": _let})

    assert "__previous__" in str(exc.value)


def test_let_references_previous_uses_innermost_list():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {
            "type": "dict",
            "required_keys": {
                "name": {"type": "string"},
                "scores": {
                    "type": "list",
                    "element_schema": {"type": "integer"},
                },
            },
        },
    }

    cfg: ConfigurationList = [
        {"name": "first", "scores": [10, 20]},
        {
            "__let__": {
                "references": {"prev_item": "__previous__"},
                "in": {
                    # prev_item refers to the previous element of the OUTER list
                    "name": "${prev_item.name}",
                    "scores": [
                        1,
                        {
                            "__let__": {
                                # prev_score refers to the previous element of
                                # the INNER list, not the outer one
                                "references": {"prev_score": "__previous__"},
                                "in": "${prev_score + 1}",
                            }
                        },
                    ],
                },
            }
        },
    ]

    # when
    result = resolve(cfg, schema, functions={"let": _let})

    # then
    assert result == [
        {"name": "first", "scores": [10, 20]},
        {"name": "first", "scores": [1, 2]},
    ]


def test_let_references_previous_raises_outside_list():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {
        "x": {
            "__let__": {
                "references": {"prev": "__previous__"},
                "in": 1,
            }
        },
    }

    # when
    with pytest.raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"let": _let})

    assert "__previous__" in str(exc.value)


def test_let_references_previous_chained_across_multiple_elements():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {
            "type": "dict",
            "required_keys": {
                "n": {"type": "integer"},
            },
        },
    }

    cfg: ConfigurationList = [
        {"n": 1},
        {
            "__let__": {
                "references": {"prev": "__previous__"},
                "in": {"n": "${prev.n + 1}"},
            }
        },
        {
            "__let__": {
                "references": {"prev": "__previous__"},
                "in": {"n": "${prev.n + 1}"},
            }
        },
        {
            "__let__": {
                "references": {"prev": "__previous__"},
                "in": {"n": "${prev.n + 1}"},
            }
        },
    ]

    # when
    result = resolve(cfg, schema, functions={"let": _let})

    # then — each element increments the previous, producing 1, 2, 3, 4
    assert result == [{"n": 1}, {"n": 2}, {"n": 3}, {"n": 4}]


def test_let_references_previous_combined_with_this():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {
            "type": "dict",
            "required_keys": {
                "base": {"type": "integer"},
                "doubled": {"type": "integer"},
            },
        },
    }

    cfg: ConfigurationList = [
        {"base": 5, "doubled": 10},
        {
            "__let__": {
                "references": {"prev": "__previous__", "this": "__this__"},
                "in": {
                    "base": "${prev.base + 1}",
                    "doubled": "${this.base * 2}",
                },
            }
        },
    ]

    # when
    result = resolve(cfg, schema, functions={"let": _let})

    # then
    assert result == [
        {"base": 5, "doubled": 10},
        {"base": 6, "doubled": 12},
    ]


def test_let_provides_local_variables_to_in_block():
    # given
    schema: Schema = {"type": "integer"}

    cfg: ConfigurationDict = {
        "__let__": {
            "variables": {"x": 3, "y": 4},
            "in": "${x + y}",
        }
    }

    # when
    result = resolve(cfg, schema, functions={"let": _let})

    # then
    assert result == 7


def test_let_can_be_nested_and_local_variables_nest_as_well():
    # given
    schema: Schema = {"type": "integer"}

    cfg: ConfigurationDict = {
        "__let__": {
            "variables": {"x": 3, "y": 4},
            "in": {
                "__let__": {
                    "variables": {"z": 5},
                    "in": "${x + y + z}",
                }
            },
        }
    }

    # when
    result = resolve(cfg, schema, functions={"let": _let})

    # then
    assert result == 12


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
                "variables": {"y": "${foo}"},
                "in": "${y}",
            }
        },
    }

    # when
    result = resolve(cfg, schema, functions={"let": _let})

    # then
    assert result == {"foo": 42, "bar": 42}


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
                "in": "${x + 4}",
            }
        },
    }

    # when
    result = resolve(cfg, schema, functions={"let": _let})

    # then
    assert result == {"x": 3, "y": 9}


def test_local_variables_are_given_priority_over_global_variables():
    # given
    schema: Schema = {"type": "integer"}

    cfg: ConfigurationDict = {
        "__let__": {
            "variables": {"x": 5},
            "in": "${x}",
        },
    }

    # when
    result = resolve(cfg, schema, functions={"let": _let}, global_variables={"x": 7})

    # then
    assert result == 5


def test_let_raises_if_input_is_not_a_dict():
    # given
    schema: Schema = {"type": "integer"}

    cfg: ConfigurationDict = {
        "__let__": "not a dictionary",
    }

    # when
    with pytest.raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"let": _let})

    assert "Input to 'let' must be a dictionary." in str(exc.value)


def test_let_raises_if_does_not_contain_in_key():
    # given
    schema: Schema = {"type": "integer"}

    cfg: ConfigurationDict = {
        "__let__": {"x": 3},
    }

    # when
    with pytest.raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"let": _let})

    assert "must contain an 'in' key" in str(exc.value)


def test_let_raises_if_variables_is_not_a_dict():
    # given
    schema: Schema = {"type": "integer"}

    cfg: ConfigurationDict = {
        "__let__": {"variables": "not a dictionary", "in": 3},
    }

    # when
    with pytest.raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"let": _let})

    assert "must be a dictionary" in str(exc.value)


def test_let_with_variables_that_are_resolved_from_a_function():
    # given
    @Function.new()
    def variables(_):
        return {"x": 3, "y": 4}

    schema: Schema = {"type": "integer"}

    cfg: ConfigurationDict = {
        "__let__": {
            "variables": {"__variables__": {}},
            "in": "${x + y}",
        }
    }

    # when
    result = resolve(cfg, schema, functions={"let": _let, "variables": variables})

    # then
    assert result == 7


def test_let_raises_if_variables_do_not_resolve_to_a_dict():
    # given
    @Function.new()
    def variables(_):
        return 42

    schema: Schema = {"type": "integer"}

    cfg: ConfigurationDict = {
        "__let__": {
            "variables": {"__variables__": {}},
            "in": "${x + y}",
        }
    }

    # when
    with pytest.raises(exceptions.ResolutionError) as exc:
        resolve(
            cfg,
            schema,
            functions={"let": _let, "variables": variables},
        )

    assert "must be a dictionary" in str(exc.value)


# resolve ==============================================================================


def test_resolve_interpolates_inline_data():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "timeout": {"type": "integer"},
            "service": {
                "type": "dict",
                "required_keys": {
                    "timeout": {"type": "integer"},
                    "health_check": {"type": "string"},
                },
            },
        },
    }

    cfg: ConfigurationDict = {
        "timeout": 30,
        "service": {
            "__resolve__": {
                "timeout": "${timeout}",
                "health_check": "/health",
            }
        },
    }

    # when
    result = resolve(cfg, schema, functions={"resolve": _resolve_fn})

    # then — the raw data is resolved in the current scope
    assert result == {
        "timeout": 30,
        "service": {"timeout": 30, "health_check": "/health"},
    }


def test_resolve_on_raw():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {
        "foo": "hello",
        "bar": {"__resolve__": {"__raw__": "${foo}"}},
    }

    # when
    result = resolve(cfg, schema, functions={"resolve": _resolve_fn, "raw": _raw})

    # then — if the input WERE pre-resolved, __raw__ would evaluate first
    # (returning "${foo}" as plain data), and then __resolve__ would re-resolve
    # "${foo}" → "hello". Since input is NOT pre-resolved, __raw__ is handled
    # inside __resolve__'s own node tree, preserving raw behavior.
    assert result == {"foo": "hello", "bar": "${foo}"}


def test_resolve_does_standard_not_full_resolution():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "name": {"type": "string"},
            "template": {"type": "string"},
            "result": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {
        "name": "world",
        "template": {"__raw__": "hello ${name}"},
        "result": {"__resolve__": "${template}"},
    }

    # when
    result = resolve(cfg, schema, functions={"resolve": _resolve_fn, "raw": _raw})

    # then — standard resolution interpolates "${template}" once, yielding the
    # raw string "hello ${name}". Full resolution would interpolate again,
    # producing "hello world". Standard stops after one pass.
    assert result == {
        "name": "world",
        "template": "hello ${name}",
        "result": "hello ${name}",
    }


def test_resolve_scalar_with_interpolation_and_conversion():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "integer"},
            "y": {"type": "integer"},
            "result": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {
        "x": 3,
        "y": 4,
        "result": {"__resolve__": "${x + y}"},
    }

    # when
    result = resolve(cfg, schema, functions={"resolve": _resolve_fn})

    # then — interpolation and type conversion both happen
    assert result == {"x": 3, "y": 4, "result": 7}


def test_resolve_list_input():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "integer"},
            "y": {"type": "integer"},
            "items": {"type": "list", "element_schema": {"type": "integer"}},
        },
    }

    cfg: ConfigurationDict = {
        "x": 10,
        "y": 20,
        "items": {"__resolve__": ["${x}", "${y}", "${x + y}"]},
    }

    # when
    result = resolve(cfg, schema, functions={"resolve": _resolve_fn})

    # then
    assert result == {"x": 10, "y": 20, "items": [10, 20, 30]}


# fully_resolve ========================================================================


def test_fully_resolve_interpolates_recursively():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "name": {"type": "string"},
            "template": {"type": "string"},
            "result": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {
        "name": "world",
        "template": {"__raw__": "hello ${name}"},
        "result": {"__fully_resolve__": "${template}"},
    }

    # when
    result = resolve(
        cfg, schema, functions={"fully_resolve": _fully_resolve, "raw": _raw}
    )

    # then — unlike __resolve__, __fully_resolve__ interpolates recursively:
    # "${template}" → "hello ${name}" → "hello world"
    assert result == {
        "name": "world",
        "template": "hello ${name}",
        "result": "hello world",
    }


def test_fully_resolve_does_not_pre_resolve_its_input():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {
        "foo": "hello",
        "bar": {"__fully_resolve__": {"__raw__": "${foo}"}},
    }

    # when
    result = resolve(
        cfg, schema, functions={"fully_resolve": _fully_resolve, "raw": _raw}
    )

    # then — input is not pre-resolved, so __raw__ is honored inside the node
    # tree. Even though fully_resolve uses recursive interpolation, the raw
    # node prevents interpolation entirely.
    assert result == {"foo": "hello", "bar": "${foo}"}


def test_fully_resolve_scalar_with_interpolation_and_conversion():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "integer"},
            "y": {"type": "integer"},
            "result": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {
        "x": 3,
        "y": 4,
        "result": {"__fully_resolve__": "${x + y}"},
    }

    # when
    result = resolve(cfg, schema, functions={"fully_resolve": _fully_resolve})

    # then
    assert result == {"x": 3, "y": 4, "result": 7}


# template =============================================================================


def test_template_resolves_to_itself():
    """__template__ should resolve to a dict {"__template__": <contents>}, preserving
    any ${...} references in the contents as literal text."""
    # given
    template = CORE_FUNCTIONS["template"]

    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "any"},
        },
    }

    cfg: ConfigurationDict = {
        "foo": {"__template__": "Hello ${name}!"},
    }

    # when
    result = resolve(cfg, schema, functions={"template": template})

    # then
    assert result == {"foo": {"__template__": "Hello ${name}!"}}


def test_template_survives_multiple_resolutions():
    """Resolving a __template__ and then resolving the output again should produce
    the same result — the template wrapper persists across resolution boundaries."""
    # given
    template = CORE_FUNCTIONS["template"]

    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "any"},
        },
    }

    cfg: ConfigurationDict = {
        "foo": {"__template__": "Hello ${name}!"},
    }

    # when — resolve twice
    first = resolve(cfg, schema, functions={"template": template})
    second = resolve(first, schema, functions={"template": template})

    # then
    assert first == second == {"foo": {"__template__": "Hello ${name}!"}}


def test_template_with_content_schema():
    """The schema can describe what a template must contain by using a dict schema
    with a __template__ required key whose value schema specifies the expected
    structure of the template contents."""
    # given
    template = CORE_FUNCTIONS["template"]

    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "my_template": {
                "type": "dict",
                "required_keys": {
                    "__template__": {
                        "type": "dict",
                        "required_keys": {
                            "host": {"type": "string"},
                            "port": {"type": "string"},
                        },
                    },
                },
            },
        },
    }

    cfg: ConfigurationDict = {
        "my_template": {
            "__template__": {"host": "localhost", "port": "${default_port}"}
        },
    }

    # when
    result = resolve(cfg, schema, functions={"template": template})

    # then — structure is validated, ${...} references are preserved
    assert result == {
        "my_template": {
            "__template__": {"host": "localhost", "port": "${default_port}"}
        },
    }


# use ==================================================================================


def test_use_works_when_keypath_resolves_to_a_template():
    # given — a custom function that returns a template dict
    @Function.new()
    def make_template(args):
        return {"__template__": {"greeting": "Hello ${name}!", "farewell": "Bye!"}}

    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "name": {"type": "string"},
            "source": {"type": "any"},
            "result": {
                "type": "dict",
                "required_keys": {
                    "greeting": {"type": "string"},
                    "farewell": {"type": "string"},
                },
            },
        },
    }

    cfg: ConfigurationDict = {
        "name": "world",
        "source": {"__make_template__": {}},
        "result": {"__use__": "source"},
    }

    # when
    result = resolve(
        cfg,
        schema,
        functions={"use": _use, "template": _template, "make_template": make_template},
    )

    # then — __use__ resolves "source", gets the template dict, unwraps and resolves it
    assert result == {
        "name": "world",
        "source": {"__template__": {"greeting": "Hello ${name}!", "farewell": "Bye!"}},
        "result": {"greeting": "Hello world!", "farewell": "Bye!"},
    }


def test_use_resolves_template():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "timeout": {"type": "integer"},
            "template": {"type": "any"},
            "service": {
                "type": "dict",
                "required_keys": {
                    "timeout": {"type": "integer"},
                    "health_check": {"type": "string"},
                },
            },
        },
    }

    cfg: ConfigurationDict = {
        "timeout": 30,
        "template": {
            "__template__": {
                "timeout": "${timeout}",
                "health_check": "/health",
            }
        },
        "service": {"__use__": "template"},
    }

    # when
    result = resolve(cfg, schema, functions={"use": _use, "template": _template})

    # then — __use__ unwraps the template and resolves it with interpolation.
    assert result == {
        "timeout": 30,
        "template": {
            "__template__": {"timeout": "${timeout}", "health_check": "/health"}
        },
        "service": {"timeout": 30, "health_check": "/health"},
    }


def test_use_applies_destination_schema_for_type_conversion():
    # given — the template stores everything as strings, but the destination
    # schema expects integers and booleans. Type conversion should be applied
    # according to the destination schema, not the template's.
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "template": {"type": "any"},
            "result": {
                "type": "dict",
                "required_keys": {
                    "port": {"type": "integer"},
                    "debug": {"type": "boolean"},
                    "name": {"type": "string"},
                },
            },
        },
    }

    cfg: ConfigurationDict = {
        "template": {
            "__template__": {
                "port": "8080",
                "debug": "True",
                "name": "my-service",
            }
        },
        "result": {"__use__": "template"},
    }

    # when
    result = resolve(cfg, schema, functions={"use": _use, "template": _template})

    # then — strings are converted per the destination schema
    assert result == {
        "template": {
            "__template__": {"port": "8080", "debug": "True", "name": "my-service"}
        },
        "result": {"port": 8080, "debug": True, "name": "my-service"},
    }


def test_use_performs_only_one_resolve():
    # given — y is a raw value containing "${x}"; the template references y.
    # Standard (single-pass) interpolation means "${y}" expands to "${x}"
    # but does not expand further.
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "string"},
            "y": {"type": "string"},
            "template": {"type": "any"},
            "result": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {
        "x": "world",
        "y": {"__raw__": "${x}"},
        "template": {"__template__": "${y}"},
        "result": {"__use__": "template"},
    }

    # when
    result = resolve(
        cfg, schema, functions={"use": _use, "template": _template, "raw": _raw}
    )

    # then — __use__ unwraps "${y}", standard interpolation expands it once
    # to "${x}", but does not expand "${x}" to "world".
    assert result == {
        "x": "world",
        "y": "${x}",
        "template": {"__template__": "${y}"},
        "result": "${x}",
    }


def test_use_with_nested_keypath():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "templates": {
                "type": "dict",
                "required_keys": {
                    "greeting": {"type": "any"},
                },
            },
            "name": {"type": "string"},
            "result": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {
        "templates": {"greeting": {"__template__": "hello ${name}"}},
        "name": "world",
        "result": {"__use__": "templates.greeting"},
    }

    # when
    result = resolve(cfg, schema, functions={"use": _use, "template": _template})

    # then
    assert result == {
        "templates": {"greeting": {"__template__": "hello ${name}"}},
        "name": "world",
        "result": "hello world",
    }


def test_use_raises_if_input_is_not_a_string_or_dict():
    # given
    schema: Schema = {"type": "integer"}

    cfg: ConfigurationDict = {"__use__": 42}

    # when
    with pytest.raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"use": _use})

    assert "string" in str(exc.value)


def test_use_raises_if_target_is_not_a_template():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "not_a_template": {"type": "string"},
            "result": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {
        "not_a_template": "just a string",
        "result": {"__use__": "not_a_template"},
    }

    # when
    with pytest.raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"use": _use, "template": _template})

    # then
    assert "__template__" in str(exc.value)


def test_use_dict_form_raises_if_target_is_not_a_template():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "not_a_template": {"type": "string"},
            "result": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {
        "not_a_template": "just a string",
        "result": {
            "__use__": {
                "template": "not_a_template",
            }
        },
    }

    # when
    with pytest.raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"use": _use, "template": _template})

    # then
    assert "__template__" in str(exc.value)


def test_use_raises_if_keypath_does_not_exist():
    # given
    schema: Schema = {"type": "any"}

    cfg: ConfigurationDict = {
        "foo": {"__template__": {"a": 1}},
        "result": {"__use__": "nonexistent"},
    }

    # when / then
    with pytest.raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"use": _use, "template": _template})

    assert "nonexistent" in str(exc.value).lower()


# use with overrides ===================================================================


def test_use_with_overrides_replaces_template_key():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "name": {"type": "string"},
            "template": {"type": "any"},
            "messages": {
                "type": "dict",
                "required_keys": {
                    "greeting": {"type": "string"},
                    "farewell": {"type": "string"},
                },
            },
        },
    }

    cfg: ConfigurationDict = {
        "name": "Alice",
        "template": {
            "__template__": {
                "greeting": "Hello ${name}!",
                "farewell": "Goodbye ${name}!",
            }
        },
        "messages": {
            "__use__": {
                "template": "template",
                "overrides": {
                    "greeting": "Hi ${name}!",
                },
            }
        },
    }

    # when
    result = resolve(cfg, schema, functions={"use": _use, "template": _template})

    # then
    assert result == {
        "name": "Alice",
        "template": {
            "__template__": {
                "greeting": "Hello ${name}!",
                "farewell": "Goodbye ${name}!",
            }
        },
        "messages": {"greeting": "Hi Alice!", "farewell": "Goodbye Alice!"},
    }


def test_use_with_overrides_adds_new_key():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "name": {"type": "string"},
            "template": {"type": "any"},
            "messages": {
                "type": "dict",
                "required_keys": {
                    "greeting": {"type": "string"},
                    "farewell": {"type": "string"},
                },
            },
        },
    }

    cfg: ConfigurationDict = {
        "name": "Alice",
        "template": {
            "__template__": {
                "greeting": "Hello ${name}!",
            }
        },
        "messages": {
            "__use__": {
                "template": "template",
                "overrides": {
                    "farewell": "Goodbye ${name}!",
                },
            }
        },
    }

    # when
    result = resolve(cfg, schema, functions={"use": _use, "template": _template})

    # then
    assert result == {
        "name": "Alice",
        "template": {"__template__": {"greeting": "Hello ${name}!"}},
        "messages": {"greeting": "Hello Alice!", "farewell": "Goodbye Alice!"},
    }


def test_use_with_overrides_interpolates_override_values():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "name": {"type": "string"},
            "template": {"type": "any"},
            "result": {
                "type": "dict",
                "required_keys": {
                    "greeting": {"type": "string"},
                },
            },
        },
    }

    cfg: ConfigurationDict = {
        "name": "Bob",
        "template": {
            "__template__": {
                "greeting": "Hello!",
            }
        },
        "result": {
            "__use__": {
                "template": "template",
                "overrides": {
                    "greeting": "Hi ${name}!",
                },
            }
        },
    }

    # when
    result = resolve(cfg, schema, functions={"use": _use, "template": _template})

    # then
    assert result == {
        "name": "Bob",
        "template": {"__template__": {"greeting": "Hello!"}},
        "result": {"greeting": "Hi Bob!"},
    }


def test_use_with_empty_overrides_is_noop():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "name": {"type": "string"},
            "template": {"type": "any"},
            "result": {
                "type": "dict",
                "required_keys": {
                    "greeting": {"type": "string"},
                },
            },
        },
    }

    cfg: ConfigurationDict = {
        "name": "Alice",
        "template": {
            "__template__": {
                "greeting": "Hello ${name}!",
            }
        },
        "result": {
            "__use__": {
                "template": "template",
                "overrides": {},
            }
        },
    }

    # when
    result = resolve(cfg, schema, functions={"use": _use, "template": _template})

    # then
    assert result == {
        "name": "Alice",
        "template": {"__template__": {"greeting": "Hello ${name}!"}},
        "result": {"greeting": "Hello Alice!"},
    }


def test_use_dict_form_without_overrides_key():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "name": {"type": "string"},
            "template": {"type": "any"},
            "result": {
                "type": "dict",
                "required_keys": {
                    "greeting": {"type": "string"},
                },
            },
        },
    }

    cfg: ConfigurationDict = {
        "name": "Alice",
        "template": {
            "__template__": {
                "greeting": "Hello ${name}!",
            }
        },
        "result": {
            "__use__": {
                "template": "template",
            }
        },
    }

    # when
    result = resolve(cfg, schema, functions={"use": _use, "template": _template})

    # then
    assert result == {
        "name": "Alice",
        "template": {"__template__": {"greeting": "Hello ${name}!"}},
        "result": {"greeting": "Hello Alice!"},
    }


def test_use_with_overrides_raises_if_template_contents_is_not_dict():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "template": {"type": "any"},
            "result": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {
        "template": {"__template__": "just a string"},
        "result": {
            "__use__": {
                "template": "template",
                "overrides": {"key": "value"},
            }
        },
    }

    # when
    with pytest.raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"use": _use, "template": _template})

    assert "dictionary" in str(exc.value).lower()


def test_use_raises_if_dict_missing_template_key():
    # given
    schema: Schema = {"type": "any"}

    cfg: ConfigurationDict = {
        "__use__": {
            "overrides": {"key": "value"},
        }
    }

    # when
    with pytest.raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"use": _use})

    assert "template" in str(exc.value).lower()


def test_use_raises_if_dict_has_extra_keys():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "t": {"type": "any"},
            "result": {"type": "any"},
        },
    }

    cfg: ConfigurationDict = {
        "t": {"__template__": {"a": "1"}},
        "result": {
            "__use__": {
                "template": "t",
                "overrides": {},
                "foo": "bar",
            }
        },
    }

    # when
    with pytest.raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"use": _use, "template": _template})

    assert "foo" in str(exc.value).lower()


def test_use_raises_if_template_value_is_not_string():
    # given
    schema: Schema = {"type": "any"}

    cfg: ConfigurationDict = {
        "__use__": {
            "template": 42,
        }
    }

    # when
    with pytest.raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"use": _use})

    assert "string" in str(exc.value).lower()


def test_use_raises_if_overrides_value_is_not_dict():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "t": {"type": "any"},
            "result": {"type": "any"},
        },
    }

    cfg: ConfigurationDict = {
        "t": {"__template__": {"a": "1"}},
        "result": {
            "__use__": {
                "template": "t",
                "overrides": "bad",
            }
        },
    }

    # when
    with pytest.raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"use": _use, "template": _template})

    assert "dictionary" in str(exc.value).lower()


def test_use_with_overrides_deep_merge():
    """Overriding a nested key should merge deeply, not replace the entire sub-dict."""
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "template": {"type": "any"},
            "result": {
                "type": "dict",
                "required_keys": {
                    "server": {
                        "type": "dict",
                        "required_keys": {
                            "host": {"type": "string"},
                            "port": {"type": "integer"},
                        },
                    },
                },
            },
        },
    }

    cfg: ConfigurationDict = {
        "template": {
            "__template__": {
                "server": {
                    "host": "localhost",
                    "port": "8080",
                },
            }
        },
        "result": {
            "__use__": {
                "template": "template",
                "overrides": {
                    "server": {
                        "port": "9090",
                    },
                },
            }
        },
    }

    # when
    result = resolve(cfg, schema, functions={"use": _use, "template": _template})

    # then — deep merge should preserve "host" while overriding "port"
    assert result == {
        "template": {"__template__": {"server": {"host": "localhost", "port": "8080"}}},
        "result": {"server": {"host": "localhost", "port": 9090}},
    }


# if ===================================================================================


def test_if_evaluates_then_if_condition_is_true():
    # given
    schema: Schema = {
        "type": "integer",
    }

    cfg: ConfigurationDict = {"__if__": {"condition": "True", "then": 1, "else": 2}}

    # when
    resolved = resolve(cfg, schema, functions={"if": _if})

    # then
    assert resolved == 1


def test_if_evaluates_else_if_condition_is_false():
    # given
    schema: Schema = {
        "type": "integer",
    }

    cfg: ConfigurationDict = {"__if__": {"condition": "False", "then": 1, "else": 2}}

    # when
    resolved = resolve(cfg, schema, functions={"if": _if})

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
        "foo": {"__if__": {"condition": "${False or bar}", "then": 1, "else": 2}},
    }

    # when
    resolved = resolve(cfg, schema, functions={"if": _if})

    # then
    assert resolved == {"bar": True, "foo": 1}


def test_if_resolves_then_branch_only_if_condition_is_true():
    # given
    schema: Schema = {
        "type": "integer",
    }

    cfg: ConfigurationDict = {
        "__if__": {"condition": "False", "then": "not an integer!", "else": "${3 + 4}"}
    }

    # when
    resolved = resolve(cfg, schema, functions={"if": _if})

    # then
    assert resolved == 7

    # when
    if_body = typing.cast(dict[str, object], cfg["__if__"])
    if_body["condition"] = "True"
    with pytest.raises(exceptions.ResolutionError):
        resolve(cfg, schema, functions={"if": _if})


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
        with pytest.raises(exceptions.ResolutionError) as exc:
            resolve(cfg, schema, functions={"if": _if})

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
    with pytest.raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"if": _if})

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
    resolved = resolve(cfg, schema, functions={"if": _if})

    # then
    assert resolved == {
        "date_a": datetime.date(2021, 10, 5),
        "date_b": datetime.date(2021, 10, 6),
        "most_recent": datetime.date(2021, 10, 6),
    }


# integration =========================================================================


def test_use_and_previous_with_multiple_templates():
    """Integration test combining __use__, __template__, and __let__ with __previous__.

    A list of items shares the same structure (number, topic, two artifacts).
    Three templates reduce repetition:

    - ``slides_template``: default artifact settings (path, ready, missing_ok).
    - ``number_template``: auto-increments from the previous item's number.

    Each item after the first applies __use__ on the templates, overriding only
    the fields that change (topic, and artifact readiness).
    """
    # given
    artifact_schema: Schema = {
        "type": "dict",
        "required_keys": {
            "path": {"type": "string"},
            "ready": {"type": "boolean"},
            "missing_ok": {"type": "boolean"},
        },
    }

    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "slides_template": {"type": "any"},
            "number_template": {"type": "any"},
            "lectures": {
                "type": "list",
                "element_schema": {
                    "type": "dict",
                    "required_keys": {
                        "number": {"type": "integer"},
                        "topic": {"type": "string"},
                        "slides_pdf": artifact_schema,
                        "slides_pptx": artifact_schema,
                    },
                },
            },
        },
    }

    cfg: ConfigurationDict = {
        # Reusable artifact template — __template__ preserves ${...} references.
        # Defaults: not ready, missing is OK.
        "slides_template": {
            "__template__": {
                "path": "slides.pdf",
                "ready": "False",
                "missing_ok": "True",
            }
        },
        # Reusable number template — auto-increments from the previous item.
        # Assumes "prev" is bound via __let__ with __previous__.
        "number_template": {"__template__": "${prev.number + 1}"},
        "lectures": [
            # Item 1: explicitly defined (no previous to reference).
            {
                "number": 1,
                "topic": "Intro to Algorithms",
                "slides_pdf": {"__use__": "slides_template"},
                "slides_pptx": {
                    "__use__": {
                        "template": "slides_template",
                        "overrides": {"path": "slides.pptx"},
                    }
                },
            },
            # Item 2: number from template; slides are ready.
            {
                "__let__": {
                    "references": {"prev": "__previous__"},
                    "in": {
                        "number": {"__use__": "number_template"},
                        "topic": "Sorting Algorithms",
                        "slides_pdf": {
                            "__use__": {
                                "template": "slides_template",
                                "overrides": {"ready": "True"},
                            }
                        },
                        "slides_pptx": {
                            "__use__": {
                                "template": "slides_template",
                                "overrides": {
                                    "path": "slides.pptx",
                                    "ready": "True",
                                },
                            }
                        },
                    },
                }
            },
            # Item 3: number from template; slides not yet ready (default).
            {
                "__let__": {
                    "references": {"prev": "__previous__"},
                    "in": {
                        "number": {"__use__": "number_template"},
                        "topic": "Graph Traversal",
                        "slides_pdf": {"__use__": "slides_template"},
                        "slides_pptx": {
                            "__use__": {
                                "template": "slides_template",
                                "overrides": {"path": "slides.pptx"},
                            }
                        },
                    },
                }
            },
        ],
    }

    # when
    result = resolve(
        cfg,
        schema,
        functions={"use": _use, "let": _let, "template": _template},
    )

    # then
    assert result == {
        "slides_template": {
            "__template__": {
                "path": "slides.pdf",
                "ready": "False",
                "missing_ok": "True",
            }
        },
        "number_template": {"__template__": "${prev.number + 1}"},
        "lectures": [
            {
                "number": 1,
                "topic": "Intro to Algorithms",
                "slides_pdf": {
                    "path": "slides.pdf",
                    "ready": False,
                    "missing_ok": True,
                },
                "slides_pptx": {
                    "path": "slides.pptx",
                    "ready": False,
                    "missing_ok": True,
                },
            },
            {
                "number": 2,
                "topic": "Sorting Algorithms",
                "slides_pdf": {
                    "path": "slides.pdf",
                    "ready": True,
                    "missing_ok": True,
                },
                "slides_pptx": {
                    "path": "slides.pptx",
                    "ready": True,
                    "missing_ok": True,
                },
            },
            {
                "number": 3,
                "topic": "Graph Traversal",
                "slides_pdf": {
                    "path": "slides.pdf",
                    "ready": False,
                    "missing_ok": True,
                },
                "slides_pptx": {
                    "path": "slides.pptx",
                    "ready": False,
                    "missing_ok": True,
                },
            },
        ],
    }
