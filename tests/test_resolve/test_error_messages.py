"""Tests for error messages and exception keypaths."""

from smartconfig import resolve, exceptions
from smartconfig.types import Template
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


def test_a_key_that_is_not_a_string_is_an_error():
    # keys must be strings, but the key 2 is an integer (YAML reads "2: y" this way)
    cfg = {"a": {2: "y"}}

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, {"type": "any"})  # type: ignore[arg-type]

    assert exc.value.keypath == ("a", "2")
    assert "must be a string" in str(exc.value)


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


# undefined names ======================================================================


def test_an_undefined_name_suggests_a_close_name():
    schema: Schema = {
        "type": "dict",
        "required_keys": {"title": {"type": "string"}, "x": {"type": "string"}},
    }
    cfg: ConfigurationDict = {"title": "t", "x": "${ titel }"}

    with raises(exceptions.UndefinedNameError) as exc:
        resolve(cfg, schema)

    assert isinstance(exc.value, exceptions.ResolutionError)
    assert exc.value.keypath == ("x",)
    assert exc.value.name == "titel"
    assert exc.value.reason == "'titel' is undefined. Did you mean \"title\"?"


def test_an_undefined_name_without_a_close_match_lists_the_available_names():
    # in lookup order: local variables, then the root's keys, then global variables
    schema: Schema = {
        "type": "dict",
        "required_keys": {"a": {"type": "string"}, "x": {"type": "string"}},
    }
    cfg: ConfigurationDict = {
        "a": "1",
        "x": {"__let__": {"variables": {"loc": 1}, "in": "${ zzz }"}},
    }

    with raises(exceptions.UndefinedNameError) as exc:
        resolve(cfg, schema, global_variables={"glob": 1})

    assert exc.value.available == ("loc", "a", "x", "glob")
    assert exc.value.reason == (
        "'zzz' is undefined. Names available here: loc, a, x, glob."
    )


def test_an_undefined_name_inside_an_attribute_access_is_reported():
    schema: Schema = {"type": "dict", "required_keys": {"x": {"type": "string"}}}

    with raises(exceptions.UndefinedNameError) as exc:
        resolve(
            {"x": "${ publcation.title }"}, schema, global_variables={"publication": 1}
        )

    assert exc.value.reason == (
        "'publcation' is undefined. Did you mean \"publication\"?"
    )


def test_is_defined_still_works_for_an_undefined_name():
    schema: Schema = {"type": "dict", "required_keys": {"x": {"type": "string"}}}
    cfg: ConfigurationDict = {"x": "{% if zzz is defined %}a{% else %}b{% endif %}"}

    assert resolve(cfg, schema) == {"x": "b"}


def test_an_undefined_name_in_a_template_suggests_a_variable_or_a_key():
    template = Template(
        {"title": "${ publication }", "body": "${ publcation } ${ titel }"},
        schema={
            "type": "dict",
            "required_keys": {
                "title": {"type": "string"},
                "body": {"type": "string"},
            },
        },
        parameters=["publication"],
        keypath=["pages", "x"],
    )

    with raises(exceptions.UndefinedNameError) as exc:
        template.evaluate({"publication": "hw"})

    assert exc.value.keypath == ("pages", "x", "body")
    assert exc.value.reason == (
        "'publcation' is undefined. Did you mean \"publication\"?"
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


def test_strict_undefined_in_other_environments_reports_an_undefined_name():
    import jinja2

    from smartconfig import StrictUndefined

    environment = jinja2.Environment(undefined=StrictUndefined)
    template = environment.from_string("{{ nope }}")

    with raises(jinja2.UndefinedError) as excinfo:
        template.render()

    assert str(excinfo.value) == "'nope' is undefined"


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


# errors in referenced values ==========================================================
#
# An error raised while resolving a referenced value must be reported as that
# error, not as an undefined name or a circular reference. These tests check the
# message rather than the exception type, since errors that aren't smartconfig's
# own may later be wrapped in a ResolutionError.


def _assert_reports_the_real_error(exc: BaseException, message: str) -> None:
    assert message in str(exc)
    assert "Circular reference" not in str(exc)
    assert not isinstance(exc, exceptions.UndefinedNameError)


def test_error_in_a_value_referenced_by_attribute_is_reported():
    # given — a.f fails: it adds a string and an int
    cfg: ConfigurationDict = {"b": "${a.f}", "a": {"f": "${'x' + 1}"}}

    # when
    with raises(Exception) as exc:
        resolve(cfg, _ANY)

    # then
    _assert_reports_the_real_error(exc.value, "can only concatenate")


def test_error_in_a_list_element_referenced_by_index_is_reported():
    # given — l[0] fails: it adds a string and an int
    cfg: ConfigurationDict = {"b": "${l[0]}", "l": ["${'x' + 1}"]}

    # when
    with raises(Exception) as exc:
        resolve(cfg, _ANY)

    # then
    _assert_reports_the_real_error(exc.value, "can only concatenate")


def test_error_in_a_value_referenced_by_name_is_reported():
    # given — x fails: the function it calls raises an IndexError
    def fails(args):
        raise IndexError("the real problem")

    cfg: ConfigurationDict = {"c": "${x}", "x": {"__fails__": None}}

    # when
    with raises(Exception) as exc:
        resolve(cfg, _ANY, functions={"fails": fails})

    # then
    _assert_reports_the_real_error(exc.value, "the real problem")


def test_splice_of_an_index_that_does_not_exist_reports_the_keypath():
    # given — x splices l.5, but l has only one element
    cfg: ConfigurationDict = {"c": "${x}", "x": {"__splice__": "l.5"}, "l": [1]}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, _ANY)

    # then
    assert "Keypath 'l.5' does not exist" in str(exc.value)


def test_a_value_that_failed_reports_the_same_error_when_referenced_again():
    # given — a.f fails: it adds a string and an int. retry catches that error,
    # then references a.f again; the second attempt must not look circular
    def retry(args):
        try:
            args.resolve("${a.f}", schema={"type": "any"})
        except Exception:
            pass
        return args.resolve("${a.f}", schema={"type": "any"})

    cfg: ConfigurationDict = {"c": {"__retry__": None}, "a": {"f": "${'x' + 1}"}}

    # when
    with raises(Exception) as exc:
        resolve(cfg, _ANY, functions={"retry": retry})

    # then
    _assert_reports_the_real_error(exc.value, "can only concatenate")


# errors raised by expressions, filters and functions ==================================
#
# An exception that isn't smartconfig's own, raised by an expression, a filter or a
# function, is wrapped in a ResolutionError at the keypath where it was raised. The
# original is kept as the cause.


def test_an_error_in_an_expression_is_reported_at_its_keypath():
    # given — the expression divides by zero
    cfg: ConfigurationDict = {"n": 0, "a": "${ 10 / n }"}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, _ANY)

    # then
    assert exc.value.keypath == ("a",)
    assert "ZeroDivisionError" in str(exc.value)
    assert isinstance(exc.value.__cause__, ZeroDivisionError)


def test_an_error_in_a_filter_is_reported_at_its_keypath():
    # given — the filter raises a ValueError
    def fails(value):
        raise ValueError("bad value")

    cfg: ConfigurationDict = {"a": "${ 1 | fails }"}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, _ANY, filters={"fails": fails})

    # then
    assert exc.value.keypath == ("a",)
    assert "bad value" in str(exc.value)
    assert isinstance(exc.value.__cause__, ValueError)


def test_an_error_in_a_function_is_reported_at_the_call_not_where_it_is_referenced():
    # given — the function at a raises its own exception, and b refers to a, so
    # the exception passes through b's string on its way out
    class OwnError(Exception):
        pass

    def fails(args):
        raise OwnError("from the function")

    cfg: ConfigurationDict = {"b": "${ a }", "a": {"__fails__": None}}

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, _ANY, functions={"fails": fails})

    # then — reported at a, where it was raised, not re-wrapped at b
    assert exc.value.keypath == ("a",)
    assert "from the function" in str(exc.value)
    assert isinstance(exc.value.__cause__, OwnError)


def test_an_assertion_error_is_not_wrapped():
    # given — the function fails an assert. That is a bug in the code, not a
    # mistake in the configuration, so it is not reported as a ResolutionError
    def fails(args):
        assert False, "a bug"

    cfg: ConfigurationDict = {"a": {"__fails__": None}}

    # when / then
    with raises(AssertionError):
        resolve(cfg, _ANY, functions={"fails": fails})


# limits ===============================================================================


def test_a_chain_of_references_too_long_to_resolve_is_reported():
    # given — k0 refers to k1, which refers to k2, and so on, 2000 deep: each
    # reference is resolved inside the one before it, which exhausts the stack
    cfg: ConfigurationDict = {f"k{i}": f"${{ k{i + 1} }}" for i in range(2000)}
    cfg["k2000"] = "end"

    # when
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, {"type": "any"})

    # then
    assert "too deep" in str(exc.value)
