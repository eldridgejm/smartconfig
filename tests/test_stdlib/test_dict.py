"""Tests for smartconfig.stdlib.dict: update, update_shallow, and from_items."""

import typing

from smartconfig import resolve, exceptions
from smartconfig.stdlib.dict import update, update_shallow, from_items
from smartconfig.stdlib.list import loop
from smartconfig.types import Schema, ConfigurationDict, ConfigurationList

from pytest import raises

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
    resolved = resolve(cfg, schema, functions={"update_shallow": update_shallow})

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
    resolved = resolve(cfg, schema, functions={"update_shallow": update_shallow})

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
        resolve(cfg, schema, functions={"update_shallow": update_shallow})

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
        resolve(cfg, schema, functions={"update_shallow": update_shallow})

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
        resolve(cfg, schema, functions={"update_shallow": update_shallow})

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
    resolved = resolve(cfg, schema, functions={"update": update})

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
    resolved = resolve(cfg, schema, functions={"update": update})

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
    resolved = resolve(cfg, schema, functions={"update": update})

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
    resolved = resolve(cfg, schema, functions={"update": update})

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
        resolve(cfg, schema, functions={"update": update})

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
        resolve(cfg, schema, functions={"update": update})

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
        resolve(cfg, schema, functions={"update": update})

    assert "Input to 'update' must be a non-empty list of dictionaries." in str(
        exc.value
    )


# from_items ======================================================================


def test_from_items_simple_example():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "string"},
        },
    }

    cfg: ConfigurationDict = {
        "__from_items__": [
            {"key": "foo", "value": 42},
            {
                "key": "bar",
                "value": "hello",
            },
        ]
    }

    # when
    resolved = resolve(cfg, schema, functions={"from_items": from_items})

    # then
    assert resolved == {"foo": 42, "bar": "hello"}


def test_from_items_generated_within_loop():
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
        "__from_items__": {
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
            "from_items": from_items,
            "loop": loop,
        },
    )

    # then
    assert resolved == {"foo": 1, "bar": 2, "baz": 3}


def test_from_items_generated_within_loop_checks_schema_for_required_keys():
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
        "__from_items__": {
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
                "from_items": from_items,
                "loop": loop,
            },
        )

    assert "missing required key" in str(exc.value)


def test_from_items_raises_if_input_is_not_a_list():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {
        "__from_items__": "not a list",
    }

    # when
    with raises(exceptions.ResolutionError):
        resolve(cfg, schema, functions={"from_items": from_items})


def test_from_items_raises_if_input_is_not_a_list_of_dicts_each_with_keys_key_and_value():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "integer"},
        },
    }

    cfg: ConfigurationDict = {
        "__from_items__": [
            {"key": "foo", "value": 42},
            {"key": "bar", "value": 42},
            "not a dictionary",
        ]
    }

    # when
    with raises(exceptions.ResolutionError):
        resolve(cfg, schema, functions={"from_items": from_items})
