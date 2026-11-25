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
