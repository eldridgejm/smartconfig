"""Tests of the messages of stdlib functions, across all of them."""

import pytest
from pytest import raises

from smartconfig import resolve, exceptions


@pytest.mark.parametrize(
    "name",
    [
        "list.concatenate",
        "list.zip",
        "list.range",
        "list.loop",
        "list.filter",
        "dict.update",
        "dict.update_shallow",
        "dict.from_items",
        "datetime.at",
        "datetime.offset",
        "datetime.first",
        "datetime.parse",
    ],
)
def test_a_message_names_the_function_by_its_full_name(name):
    # 42 is the wrong kind of input for every stdlib function. The message should
    # name the function as it is written in a configuration, e.g. "list.range",
    # not just "range", so that it can be found in the docs
    with raises(exceptions.ResolutionError) as exc:
        resolve({"x": {f"__{name}__": 42}}, {"type": "any"})

    assert f"'{name}'" in str(exc.value)
