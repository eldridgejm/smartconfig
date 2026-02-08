"""Tests of the function calling machinery."""

from smartconfig import resolve, exceptions
from smartconfig.types import (
    ConfigurationDict,
    ConfigurationList,
    Function,
    FunctionArgs,
    Schema,
)

from pytest import raises


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
        cfg,
        schema,
        functions={"add_one_to": lambda args: f"${{ {args.input} + 1 }}"},
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
        "foo": "${baz.alpha * 3}",
        "baz": {"__make_numbers__": {}},
    }

    def make_numbers(_):
        return {"alpha": "${6 + 4}", "beta": 20}

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

    cfg: ConfigurationDict = {"foo": "4", "bar": {"__myraw__": "${foo + 1}"}}

    seen = []

    def myraw(args):
        seen.append(args.input)
        return args.input

    function = Function(myraw, resolve_input=False)

    # when
    result = resolve(cfg, schema, functions={"myraw": function})

    # then
    assert seen == ["${foo + 1}"]
    assert result == {"foo": 4, "bar": 5}


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


def test_namespaced_function_call():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {"foo": 6, "bar": {"__math.double__": 10}}

    def double(args: FunctionArgs) -> int:
        assert isinstance(args.input, int)
        return args.input * 2

    # when
    result = resolve(
        cfg,
        schema,
        functions={"math": {"double": double}},
    )

    # then
    assert result == {"foo": 6, "bar": 20}


def test_deeply_nested_namespaced_function_call():
    # given
    schema: Schema = {"type": "integer"}
    cfg: ConfigurationDict = {"__a.b.c__": 5}

    def triple(args: FunctionArgs) -> int:
        assert isinstance(args.input, int)
        return args.input * 3

    # when
    result = resolve(
        cfg,
        schema,
        functions={"a": {"b": {"c": triple}}},
    )

    # then
    assert result == 15


def test_mixed_flat_and_namespaced_functions():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "integer"},
            "y": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {
        "x": {"__double__": 5},
        "y": {"__math.triple__": 4},
    }

    def double(args: FunctionArgs) -> int:
        assert isinstance(args.input, int)
        return args.input * 2

    def triple(args: FunctionArgs) -> int:
        assert isinstance(args.input, int)
        return args.input * 3

    # when
    result = resolve(
        cfg,
        schema,
        functions={
            "double": double,
            "math": {"triple": triple},
        },
    )

    # then
    assert result == {"x": 10, "y": 12}
