"""Tests that the Jinja2 template engine works as expected."""

import jinja2


def test_jinja_prefers_dictionary_methods_over_keys_in_dot_notation():
    # given
    template = jinja2.Template("{{ foo.keys }}")
    context = {"foo": {"keys": "bar"}}

    # when
    result = template.render(context)

    # then
    assert "built-in method keys" in result


def test_jinja_can_add_two_numbers():
    # given
    template = jinja2.Template("{{ foo + 2 }}")
    context = {"foo": 40}

    # when
    result = template.render(context)

    # then
    assert result == "42"


def test_jinja_can_provide_function_in_context():
    # given
    template = jinja2.Template("{{ double(3) }}")
    context = {"double": lambda x: x * 2}

    # when
    result = template.render(context)

    # then
    assert result == "6"
