"""Tests of the opt-in python function, which runs a string as a function body."""

import datetime
import textwrap

from smartconfig import resolve, exceptions, DEFAULT_FUNCTIONS
from smartconfig.stdlib.python import python
from smartconfig.types import ConfigurationDict, Schema

import pytest

# python is opt-in, so each test adds it to the default functions
FUNCTIONS = {**DEFAULT_FUNCTIONS, "python": python}


def test_body_is_run_as_a_function_and_its_return_value_is_used():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {
        "foo": {
            "__python__": textwrap.dedent(
                """\
                def double(x):
                    return x * 2

                return double(21)
                """
            )
        },
    }

    # when
    result = resolve(cfg, schema, functions=FUNCTIONS)

    # then
    assert result == {"foo": 42}


def test_values_elsewhere_in_the_tree_are_read_from_args_root_with_their_types():
    # given
    # foo has no type, so nothing converts what the body returns: the value it
    # reads from args.root is already a date, resolved by date's own schema
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "start": {"type": "date"},
            "foo": {"type": "any"},
        },
    }

    cfg: ConfigurationDict = {
        "start": "2025-10-01",
        "foo": {
            "__python__": (
                "import datetime\n"
                "return args.root['start'] + datetime.timedelta(days=3)\n"
            )
        },
    }

    # when
    result = resolve(cfg, schema, functions=FUNCTIONS)

    # then
    assert result == {
        "start": datetime.date(2025, 10, 1),
        "foo": datetime.date(2025, 10, 4),
    }


def test_body_and_return_value_are_not_interpolated():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "bar": {"type": "string"},
            "foo": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {
        "bar": "hello",
        "foo": {"__python__": "return '${bar}'"},
    }

    # when
    result = resolve(cfg, schema, functions=FUNCTIONS)

    # then
    assert result == {"bar": "hello", "foo": "${bar}"}


def test_exception_in_body_is_reported_as_a_resolution_error_at_the_call():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {
        "foo": {"__python__": "return 1 / 0"},
    }

    # when
    with pytest.raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions=FUNCTIONS)

    # then
    assert exc.value.keypath == ("foo",)
    assert "ZeroDivisionError: division by zero" in str(exc.value)


def test_python_is_not_available_by_default():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {
        "foo": {"__python__": "return 42"},
    }

    # when
    with pytest.raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema)

    # then
    assert "Unknown function: python" in str(exc.value)


def test_input_that_is_not_a_string_is_an_error():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {
        "foo": {"__python__": {"return": 42}},
    }

    # when
    with pytest.raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions=FUNCTIONS)

    # then
    assert exc.value.keypath == ("foo",)
    assert "must be a string, got dict" in str(exc.value)


def test_empty_body_is_an_error():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {
        "foo": {"__python__": "  \n"},
    }

    # when
    with pytest.raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions=FUNCTIONS)

    # then
    assert exc.value.keypath == ("foo",)
    assert "must not be empty" in str(exc.value)


def test_syntax_error_is_reported_at_the_call_with_its_line_in_the_body():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {
        "foo": {"__python__": "x = 1\nreturn (x\n"},
    }

    # when
    with pytest.raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions=FUNCTIONS)

    # then
    assert exc.value.keypath == ("foo",)
    assert "Invalid Python in line 2" in str(exc.value)
    assert isinstance(exc.value.__cause__, SyntaxError)


def test_resolution_error_in_body_keeps_its_own_keypath():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
        },
    }

    # bar can't be resolved, so reading it in the body raises an error about bar.
    # foo comes first in the schema, so that it is resolved first: the error is
    # raised while its body runs, not when bar is resolved on its own
    cfg: ConfigurationDict = {
        "foo": {"__python__": "return args.root['bar']"},
        "bar": "${ undefined }",
    }

    # when
    with pytest.raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions=FUNCTIONS)

    # then
    assert exc.value.keypath == ("bar",)


def test_body_without_a_return_statement_is_an_error():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
        },
    }

    # the helper returns, but the body itself doesn't, so its result would be None
    cfg: ConfigurationDict = {
        "foo": {
            "__python__": textwrap.dedent(
                """\
                def double(x):
                    return x * 2

                double(21)
                """
            )
        },
    }

    # when
    with pytest.raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions=FUNCTIONS)

    # then
    assert exc.value.keypath == ("foo",)
    assert "has no return statement" in str(exc.value)


def test_body_can_return_none_explicitly():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer", "nullable": True},
        },
    }

    cfg: ConfigurationDict = {
        "foo": {"__python__": "return None"},
    }

    # when
    result = resolve(cfg, schema, functions=FUNCTIONS)

    # then
    assert result == {"foo": None}


def test_body_that_yields_is_an_error():
    # given
    # foo has no type, so without the check, the generator itself would be the result
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "any"},
        },
    }

    cfg: ConfigurationDict = {
        "foo": {"__python__": "for i in range(3):\n    yield i\n"},
    }

    # when
    with pytest.raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions=FUNCTIONS)

    # then
    assert exc.value.keypath == ("foo",)
    assert "must not use 'yield'" in str(exc.value)
