"""Tests for unresolved (lazily-evaluated) containers."""

from smartconfig import resolve
from smartconfig.types import (
    ConfigurationDict,
    Schema,
    UnresolvedDict,
    UnresolvedFunctionCall,
    UnresolvedList,
)

from pytest import raises


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


# in ${...} expressions ================================================================
#
# In an expression, the configuration's dicts and lists are unresolved containers.
# They should behave like the dicts and lists they resolve to.

_ANY: Schema = {"type": "any"}


def _evaluate(expression: str):
    """The value of expression, with l a list and d a dict in the configuration."""
    cfg: ConfigurationDict = {"l": [1, 2, 3], "d": {"x": 1, "y": 2}, "e": expression}
    return resolve(cfg, _ANY)["e"]


def test_a_list_can_be_indexed_from_the_end():
    # -1 counts from the end of the list
    assert _evaluate("${ l[-1] }") == "3"


def test_a_list_can_be_sliced():
    # l[1:] is the list without its first element
    assert _evaluate("${ l[1:] | join(',') }") == "2,3"


def test_a_dict_has_the_methods_of_a_dict():
    # items() and get() come with a dict; dictsort uses items()
    assert _evaluate("${ d.get('x') }") == "1"
    assert _evaluate("${ d | dictsort | map('join', '=') | join(',') }") == "x=1,y=2"


def test_in_checks_for_a_key_without_resolving_its_value():
    # e uses `in` to check whether d has a key x, and d.x refers back to e. If
    # checking for the key resolved d.x, that would be a circular reference
    cfg: ConfigurationDict = {"d": {"x": "${ e }"}, "e": "${ 'x' in d }"}

    assert resolve(cfg, _ANY) == {"d": {"x": "True"}, "e": "True"}


def test_a_list_can_be_converted_to_json():
    # tojson needs plain data, not the unresolved containers
    assert _evaluate("${ l | tojson }") == "[1, 2, 3]"


def test_a_missing_list_element_is_reported_by_the_list_name():
    # l has three elements, so there is no l[5]. The message should name l, not
    # the internal container class
    with raises(Exception) as exc:
        _evaluate("${ l[5] }")

    assert '"l" has no element 5' in str(exc.value)
    assert "_Unresolved" not in str(exc.value)


def test_a_list_equals_the_list_it_resolves_to():
    # l resolves to [1, 2, 3], so it should equal that list, and not a different one
    assert _evaluate("${ l == [1, 2, 3] }") == "True"
    assert _evaluate("${ l != [1, 2, 3] }") == "False"
    assert _evaluate("${ l == [3, 2, 1] }") == "False"


def test_a_list_equals_the_list_it_resolves_to_when_compared_from_the_right():
    # the plain list is on the left, so its __eq__ is tried first
    assert _evaluate("${ [1, 2, 3] == l }") == "True"


def test_a_list_of_lists_equals_the_list_it_resolves_to():
    # the inner list is itself an unresolved container
    cfg: ConfigurationDict = {"l": [[1, 2], 3], "e": "${ l == [[1, 2], 3] }"}

    assert resolve(cfg, _ANY)["e"] == "True"


def test_a_dict_holding_a_list_equals_the_dict_it_resolves_to():
    # comparing the dicts compares their values, and the value of b is a list
    cfg: ConfigurationDict = {
        "d": {"a": 1, "b": [1, 2]},
        "e": "${ d == {'a': 1, 'b': [1, 2]} }",
        "f": "${ {'a': 1, 'b': [1, 2]} == d }",
    }

    resolved = resolve(cfg, _ANY)

    assert resolved["e"] == "True"
    assert resolved["f"] == "True"


def test_a_list_does_not_equal_a_tuple():
    # as for a plain list, [1, 2, 3] == (1, 2, 3) is False
    assert _evaluate("${ l == (1, 2, 3) }") == "False"


def test_a_dict_converted_to_a_string_is_the_text_of_the_dict_it_resolves_to():
    # the string filter calls str() on d; it should give the text of the plain
    # dict, as for a dict written in the expression, not an internal object's repr
    assert _evaluate("${ d | string }") == "{'x': 1, 'y': 2}"


def test_a_list_converted_to_a_string_is_the_text_of_the_list_it_resolves_to():
    # ~ joins the text of each side, calling str() on l
    assert _evaluate("${ 'l is ' ~ l }") == "l is [1, 2, 3]"
