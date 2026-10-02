"""Tests for error messages and exception keypaths."""

from smartconfig import resolve, exceptions
from smartconfig.types import (
    ConfigurationDict,
    ConfigurationList,
    Schema,
)

from pytest import raises


def test_exception_raised_when_referencing_an_undefined_key():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {"foo": {"type": "string"}},
    }

    cfg: ConfigurationDict = {"foo": "${bar}"}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema)

    assert "'bar' is undefined" in str(exc.value)


def test_exception_has_correct_path_with_missing_key_in_nested_dict():
    # given
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "foo": {
                "type": "dict",
                "required_keys": {"bar": {"type": "any"}},
            },
        },
    }

    cfg: ConfigurationDict = {"foo": {}}

    # when
    with raises(exceptions.ResolutionError) as excinfo:
        resolve(cfg, schema)

    assert excinfo.value.keypath == (
        "foo",
        "bar",
    )


def test_exception_has_correct_path_with_missing_key_in_nested_dict_within_list():
    # given
    schema: Schema = {
        "type": "list",
        "element_schema": {
            "type": "dict",
            "required_keys": {
                "foo": {
                    "type": "integer",
                },
            },
        },
    }

    cfg: ConfigurationList = [
        {
            "foo": 10,
        },
        {"bar": 42},
    ]

    # when
    with raises(exceptions.ResolutionError) as excinfo:
        resolve(cfg, schema)

    assert excinfo.value.keypath == ("1", "foo")


def test_exception_raised_when_schema_includes_default_value_that_doesnt_match_type():
    # given
    schema: Schema = {
        "type": "dict",
        "optional_keys": {
            "foo": {"type": "integer", "default": "not an int"},
        },
    }

    cfg: ConfigurationDict = {}

    # when/then
    with raises(exceptions.ResolutionError) as excinfo:
        resolve(cfg, schema)

    assert "Cannot convert to integer" in str(excinfo.value)


# values of the wrong shape ============================================================


def _resolve_error(cfg, schema) -> str:
    with raises(exceptions.ResolutionError) as excinfo:
        resolve(cfg, schema)
    return str(excinfo.value)


def test_list_where_a_dict_is_expected():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "vars": {"type": "dict", "extra_keys_schema": {"type": "any"}}
        },
    }

    message = _resolve_error({"vars": [1, 2]}, schema)

    assert message == 'Cannot resolve keypath "vars": Expected a dict, but got a list.'


def test_dict_where_a_list_is_expected():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "extensions": {"type": "list", "element_schema": {"type": "string"}}
        },
    }

    message = _resolve_error({"extensions": {"a": 1}}, schema)

    assert message == (
        'Cannot resolve keypath "extensions": Expected a list, but got a dict with '
        'key "a".'
    )


def test_string_where_a_list_is_expected():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "extensions": {"type": "list", "element_schema": {"type": "string"}}
        },
    }

    message = _resolve_error({"extensions": "foo"}, schema)

    assert message == (
        'Cannot resolve keypath "extensions": Expected a list, but got the string '
        '"foo".'
    )


def test_list_where_a_string_is_expected():
    schema: Schema = {
        "type": "dict",
        "optional_keys": {"base_path": {"type": "string", "default": "/"}},
    }

    message = _resolve_error({"base_path": [1]}, schema)

    assert message == (
        'Cannot resolve keypath "base_path": Expected a string, but got a list.'
    )


def test_number_where_a_dict_is_expected_in_a_list():
    schema: Schema = {
        "type": "list",
        "element_schema": {"type": "dict", "extra_keys_schema": {"type": "any"}},
    }

    message = _resolve_error([{"a": 1}, 42], schema)

    assert (
        message == 'Cannot resolve keypath "1": Expected a dict, but got the number 42.'
    )


def test_any_accepts_every_shape():
    schema: Schema = {"type": "dict", "extra_keys_schema": {"type": "any"}}

    result = resolve({"a": [1], "b": {"c": 2}, "d": "e"}, schema)

    assert result == {"a": [1], "b": {"c": 2}, "d": "e"}


def test_function_calls_are_not_mistaken_for_dicts():
    schema: Schema = {"type": "dict", "required_keys": {"x": {"type": "string"}}}

    result = resolve({"x": {"__raw__": "${ not interpolated }"}}, schema)

    assert result == {"x": "${ not interpolated }"}


# template errors ======================================================================


def test_template_syntax_error_names_the_keypath():
    schema: Schema = {"type": "dict", "required_keys": {"course": {"type": "string"}}}

    message = _resolve_error({"course": "${ vars. }"}, schema)

    assert message.startswith('Cannot resolve keypath "course": ')
    assert "${ vars. }" in message


def test_undefined_key_of_an_unresolved_dict_names_the_dict():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "vars": {"type": "dict", "extra_keys_schema": {"type": "any"}},
            "title": {"type": "string"},
        },
    }

    message = _resolve_error(
        {"vars": {"course": "DSC 40B"}, "title": "${ vars.nope }"}, schema
    )

    assert message == 'Cannot resolve keypath "title": "vars" has no key "nope".'
    assert "_UnresolvedDict" not in message


def test_undefined_key_of_an_unresolved_dict_suggests_a_close_key():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "vars": {"type": "dict", "extra_keys_schema": {"type": "any"}},
            "title": {"type": "string"},
        },
    }

    message = _resolve_error(
        {"vars": {"course": "DSC 40B"}, "title": "${ vars.cours }"}, schema
    )

    assert message == (
        'Cannot resolve keypath "title": "vars" has no key "cours". '
        'Did you mean "course"?'
    )


def test_undefined_key_of_a_global_dict_suggests_a_close_key():
    schema: Schema = {"type": "dict", "required_keys": {"title": {"type": "string"}}}

    with raises(exceptions.ResolutionError) as excinfo:
        resolve(
            {"title": "${ meta.topc }"},
            schema,
            global_variables={"meta": {"topic": "Sorting", "number": 1}},
        )

    assert excinfo.value.reason == 'The dict has no key "topc". Did you mean "topic"?'


def test_undefined_key_of_a_global_dict_lists_the_keys():
    schema: Schema = {"type": "dict", "required_keys": {"title": {"type": "string"}}}

    with raises(exceptions.ResolutionError) as excinfo:
        resolve(
            {"title": "${ meta.zzz }"},
            schema,
            global_variables={"meta": {"topic": "Sorting", "number": 1}},
        )

    assert excinfo.value.reason == (
        'The dict has no key "zzz". Its keys are "topic", "number".'
    )


def test_undefined_attribute_of_an_object_suggests_a_close_attribute():
    class Publication:
        def __init__(self):
            self.metadata = {"title": "Lecture"}

    schema: Schema = {"type": "dict", "required_keys": {"title": {"type": "string"}}}

    with raises(exceptions.ResolutionError) as excinfo:
        resolve(
            {"title": "${ publication.metdata.title }"},
            schema,
            global_variables={"publication": Publication()},
        )

    assert excinfo.value.reason == (
        'The Publication object has no attribute "metdata". Did you mean "metadata"?'
    )


# StrictUndefined in other templates ===================================================


def test_strict_undefined_can_be_used_in_other_jinja_environments():
    import jinja2

    from smartconfig import StrictUndefined

    environment = jinja2.Environment(undefined=StrictUndefined)
    template = environment.from_string("{{ meta.topc }}")

    with raises(jinja2.UndefinedError) as excinfo:
        template.render(meta={"topic": "Sorting"})

    assert str(excinfo.value) == 'The dict has no key "topc". Did you mean "topic"?'


# dicts and lists can't be inserted into strings =======================================

_ANY: Schema = {"type": "dict", "extra_keys_schema": {"type": "any"}}


def _reason(cfg, **kwargs) -> str:
    with raises(exceptions.ResolutionError) as excinfo:
        resolve(cfg, _ANY, **kwargs)
    return excinfo.value.reason


def test_a_dict_inserted_into_a_string_is_an_error():
    reason = _reason({"vars": {"d": {"a": 1, "b": 2}}, "x": "value: ${ vars.d }"})

    assert reason == (
        '"vars.d" is a dict, which can\'t be inserted into a string. Use one of '
        "its keys, as in ${ vars.d.a }, or copy the whole value with __splice__."
    )


def test_the_error_names_the_keypath_of_the_string():
    with raises(exceptions.ResolutionError) as excinfo:
        resolve({"vars": {"d": {"a": 1}}, "x": "value: ${ vars.d }"}, _ANY)

    assert excinfo.value.keypath == ("x",)


def test_a_key_that_is_not_a_name_is_shown_with_brackets():
    reason = _reason({"files": {"hw.pdf": "a"}, "x": "${ files }"})

    assert 'as in ${ files["hw.pdf"] }' in reason


def test_a_list_inserted_into_a_string_is_an_error():
    reason = _reason({"vars": {"l": [1, 2]}, "x": "${ vars.l }"})

    assert reason == (
        '"vars.l" is a list, which can\'t be inserted into a string. Use one of '
        "its elements, as in ${ vars.l[0] }, or copy the whole value with "
        "__splice__."
    )


def test_a_template_inserted_into_a_string_is_an_error():
    reason = _reason(
        {
            "templates": {"recipe": {"__template__": "make ${ this.n }"}},
            "this": {"n": 1, "recipe": "${ templates.recipe }"},
        }
    )

    assert reason == (
        '"templates.recipe" is a template, which can\'t be inserted into a '
        "string. Use it with __use__ instead."
    )


def test_a_dict_from_global_variables_inserted_into_a_string_is_an_error():
    reason = _reason({"x": "${ meta }"}, global_variables={"meta": {"a": 1}})

    assert reason == (
        'A dict with key "a" can\'t be inserted into a string. Use one of its '
        "keys instead."
    )


def test_values_from_dicts_and_lists_can_still_be_inserted():
    cfg: ConfigurationDict = {
        "vars": {"d": {"a": 1}, "l": ["x", "y"]},
        "x": "${ vars.d.a } ${ vars.l[1] } ${ vars.l | join(', ') }",
    }

    assert resolve(cfg, _ANY)["x"] == "1 y x, y"
