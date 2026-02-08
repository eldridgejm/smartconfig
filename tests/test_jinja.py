"""Tests checking that the Jinja2 template engine works as expected."""

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


def test_jinja_with_custom_context_class():
    def make_context_class(extras):
        class MyContext(jinja2.runtime.Context):
            def resolve_or_missing(self, key):
                if key in extras:
                    return extras[key]
                else:
                    result = super().resolve_or_missing(key)
                    return result

        return MyContext

    # given
    environment = jinja2.Environment()
    environment.context_class = make_context_class({"foo": {"bar": "hello"}})
    template = environment.from_string("{{ foo.bar }}")

    # when
    result = template.render()

    # then
    assert result == "hello"


def test_jinja_range_function_is_available():
    # given
    template = jinja2.Template("{% for i in range(5) %}{{ i }}{% endfor %}")

    # when
    result = template.render()

    # then
    assert result == "01234"


def test_jinja_prefers_template_variables_to_builtin_functions():
    # given
    template = jinja2.Template("{{ range }}")
    context = {"range": "foo"}

    # when
    result = template.render(context)

    # then
    assert result == "foo"


def test_jinja_custom_filter():
    # given
    def reverse(value):
        return value[::-1]

    environment = jinja2.Environment()
    environment.filters["reverse"] = reverse
    template = environment.from_string("{{ 'hello' | reverse }}")

    # when
    result = template.render()

    # then
    assert result == "olleh"


def test_jinja_tuple_in_string_interpolation_with_custom_filter():
    # given
    def reverse(value):
        return value[::-1]

    environment = jinja2.Environment()
    environment.filters["reverse"] = reverse
    template = environment.from_string("{{ (1, 2) | reverse }}")

    # when
    result = template.render()

    # then
    assert result == "(2, 1)"
