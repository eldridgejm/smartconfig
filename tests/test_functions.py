from smartconfig import resolve, exceptions
from smartconfig import functions

from pytest import raises

# raw ==================================================================================


def test_raw_does_not_parse():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "string"},
        },
    }

    dct = {"foo": 42, "bar": {"__raw__": "1 + 3"}}

    # when
    resolved = resolve(dct, schema, functions={"raw": functions.raw})

    # then
    assert resolved == {"foo": 42, "bar": "1 + 3"}


def test_raw_does_not_interpolate():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "string"},
        },
    }

    dct = {"foo": 42, "bar": {"__raw__": "${this.foo} + 3"}}

    # when
    resolved = resolve(dct, schema, functions={"raw": functions.raw})

    # then
    assert resolved == {"foo": 42, "bar": "${this.foo} + 3"}


def test_referencing_a_raw_string_in_normal_string_will_interpolate_once():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "string"},
            "baz": {"type": "string"},
        },
    }

    dct = {"foo": 42, "bar": {"__raw__": "${foo} + 3"}, "baz": "${bar} + 4"}

    # when
    resolved = resolve(dct, schema, functions={"raw": functions.raw})

    # then
    assert resolved == {"foo": 42, "bar": "${foo} + 3", "baz": "${foo} + 3 + 4"}


def test_raw_with_a_non_string_raises():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "list", "element_schema": {"type": "integer"}},
        },
    }

    dct = {"foo": 42, "bar": {"__raw__": [1, 2, 3, 4]}}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(dct, schema, functions={"raw": functions.raw})

    assert "Input to 'raw' must be a string." in str(exc.value)


# recursive ============================================================================


def test_referencing_a_raw_string_in_recursive_string_will_interpolate_repeatedly():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "string"},
            "baz": {"type": "integer"},
        },
    }

    dct = {
        "foo": 42,
        "bar": {"__raw__": "${foo} + 3"},
        "baz": {"__recursive__": "${bar} + 4"},
    }

    # when
    resolved = resolve(
        dct, schema, functions={"raw": functions.raw, "recursive": functions.recursive}
    )

    # then
    assert resolved == {"foo": 42, "bar": "${foo} + 3", "baz": 49}


def test_recursive_with_a_non_string_raises():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "integer"},
            "bar": {"type": "list", "element_schema": {"type": "integer"}},
        },
    }

    dct = {"foo": 42, "bar": {"__recursive__": [1, 2, 3, 4]}}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(dct, schema, functions={"recursive": functions.recursive})

    assert "Input to 'recursive' must be a string." in str(exc.value)


# update_shallow =======================================================================


def test_update_shallow_does_not_perform_a_deep_update():
    # given
    schema = {
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

    dct = {
        "baz": {
            "__update_shallow__": [
                {"a": 1, "b": {"c": 5, "d": 6}},
                {"a": 3, "b": {"c": 4}},
            ]
        }
    }

    # when
    resolved = resolve(
        dct, schema, functions={"update_shallow": functions.update_shallow}
    )

    # then
    assert resolved == {
        "baz": {"a": 3, "b": {"c": 4}},
    }


def test_update_shallow_with_four_dictionaries():
    # given
    schema = {
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

    dct = {
        "baz": {"__update_shallow__": [{"a": 1, "b": 2}, {"a": 3}, {"a": 5}, {"b": 7}]}
    }

    # when
    resolved = resolve(
        dct, schema, functions={"update_shallow": functions.update_shallow}
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
    schema = {
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

    dct = {"baz": {"__update_shallow__": 4}}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(dct, schema, functions={"update_shallow": functions.update_shallow})

    assert "Input to 'update_shallow' must be a list of dictionaries." in str(exc.value)


def test_update_shallow_raises_if_input_is_not_a_list_of_dicts():
    # given
    schema = {
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

    dct = {"baz": {"__update_shallow__": [{"hi": "there"}, 5]}}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(dct, schema, functions={"update_shallow": functions.update_shallow})

    assert "Input to 'update_shallow' must be a list of dictionaries." in str(exc.value)


def test_update_shallow_raises_if_input_is_empty():
    # given
    schema = {
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

    dct = {"baz": {"__update_shallow__": []}}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(dct, schema, functions={"update_shallow": functions.update_shallow})

    assert "Input to 'update_shallow' must be a non-empty list of dictionaries." in str(
        exc.value
    )


# update ==========================================================================


def test_update_uses_values_from_the_righmost_map():
    # given
    schema = {
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

    dct = {"baz": {"__update__": [{"a": 1, "b": 2}, {"a": 3}]}}

    # when
    resolved = resolve(dct, schema, functions={"update": functions.update})

    # then
    assert resolved == {
        "baz": {
            "a": 3,
            "b": 2,
        },
    }


def test_update_with_partial_update():
    # the second dictionary does not have all the keys of the first one at the
    # second level of nesting

    # given
    schema = {
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

    dct = {
        "baz": {
            "__update__": [
                {"a": 1, "b": {"c": 5, "d": 6}},
                {"a": 3, "b": {"c": 4}},
            ]
        }
    }

    # when
    resolved = resolve(dct, schema, functions={"update": functions.update})

    # then
    assert resolved == {
        "baz": {"a": 3, "b": {"c": 4, "d": 6}},
    }


def test_update_with_four_dictionaries():
    # given
    schema = {
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

    dct = {
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
    resolved = resolve(dct, schema, functions={"update": functions.update})

    # then
    assert resolved == {
        "baz": {"a": 2, "b": {"c": 9, "d": 7}},
    }


def test_update_raises_if_input_is_not_a_list():
    # given
    schema = {
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

    dct = {"baz": {"__update__": 4}}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(dct, schema, functions={"update": functions.update})

    assert "Input to 'update' must be a list of dictionaries." in str(exc.value)


def test_update_raises_if_input_is_not_a_list_of_dicts():
    # given
    schema = {
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

    dct = {"baz": {"__update__": [{"hi": "there"}, 5]}}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(dct, schema, functions={"update": functions.update})

    assert "Input to 'update' must be a list of dictionaries." in str(exc.value)


def test_update_raises_if_input_is_empty():
    # given
    schema = {
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

    dct = {"baz": {"__update__": []}}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(dct, schema, functions={"update": functions.update})

    assert "Input to 'update' must be a non-empty list of dictionaries." in str(
        exc.value
    )


# concatenate ==========================================================================


def test_concatenate_with_two_lists():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "baz": {
                "type": "list",
                "element_schema": {"type": "integer"},
            },
        },
    }

    dct = {"baz": {"__concatenate__": [[1, 2], [3, 4]]}}

    # when
    resolved = resolve(dct, schema, functions={"concatenate": functions.concatenate})

    # then
    assert resolved == {
        "baz": [1, 2, 3, 4],
    }


def test_concatenate_with_three_lists():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "baz": {
                "type": "list",
                "element_schema": {"type": "integer"},
            },
        },
    }

    dct = {"baz": {"__concatenate__": [[1, 2], [3, 4], [5, 6]]}}

    # when
    resolved = resolve(dct, schema, functions={"concatenate": functions.concatenate})

    # then
    assert resolved == {
        "baz": [1, 2, 3, 4, 5, 6],
    }


def test_concatenate_raises_if_input_is_not_a_list():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "baz": {
                "type": "list",
                "element_schema": {"type": "integer"},
            },
        },
    }

    dct = {"baz": {"__concatenate__": 4}}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(dct, schema, functions={"concatenate": functions.concatenate})

    assert "Input to 'concatenate' must be a list of lists." in str(exc.value)


def test_concatenate_raises_if_input_is_not_a_list_of_lists():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "baz": {
                "type": "list",
                "element_schema": {"type": "integer"},
            },
        },
    }

    dct = {"baz": {"__concatenate__": [[1, 2], 5]}}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(dct, schema, functions={"concatenate": functions.concatenate})

    assert "Input to 'concatenate' must be a list of lists." in str(exc.value)


def test_concatenate_raises_if_input_is_empty():
    # given
    schema = {
        "type": "dict",
        "required_keys": {
            "baz": {
                "type": "list",
                "element_schema": {"type": "integer"},
            },
        },
    }

    dct = {"baz": {"__concatenate__": []}}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(dct, schema, functions={"concatenate": functions.concatenate})

    assert "Input to 'concatenate' must be a non-empty list of lists." in str(exc.value)


# splice ===============================================================================


def test_splice_a_dictionary():
    # given
    schema = {
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

    dct = {
        "baz": {"a": 1, "b": 2},
        "foo": {"__splice__": "baz"},
    }

    # when
    resolved = resolve(dct, schema, functions={"splice": functions.splice})

    # then
    assert resolved == {
        "baz": {"a": 1, "b": 2},
        "foo": {"a": 1, "b": 2},
    }


def test_splice_still_parses():
    # given
    schema = {
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

    dct = {
        "baz": {"a": 1, "b": 2},
        "foo": {"__splice__": "baz"},
    }

    # when
    resolved = resolve(dct, schema, functions={"splice": functions.splice})

    # then
    assert resolved == {
        "baz": {"a": 1, "b": 2},
        "foo": {"a": "1", "b": "2"},
    }


def test_splice_raises_if_key_does_not_exist():
    # given
    schema = {
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

    dct = {
        "baz": {"a": 1, "b": 2},
        "foo": {"__splice__": "quux"},
    }

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(dct, schema, functions={"splice": functions.splice})

    assert "Keypath 'quux' does not exist." in str(exc.value)


def test_splice_argument_can_be_an_integer_index_of_list():
    # given a schema for a list of lists
    schema = {"type": "list", "element_schema": {"type": "string"}}

    dct = [
        "one",
        {"__splice__": 0},
        "three",
    ]

    # when
    resolved = resolve(dct, schema, functions={"splice": functions.splice})

    # then
    assert resolved == [
        "one",
        "one",
        "three",
    ]


def test_splice_raises_if_key_is_not_a_valid_keypath():
    # given a schema for a list of lists
    schema = {"type": "list", "element_schema": {"type": "string"}}

    dct = [
        "one",
        {"__splice__": True},
        "three",
    ]

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(dct, schema, functions={"splice": functions.splice})

    assert "Input to 'splice' must be a string or int." in str(exc.value)
