"""Tests for defining Prototypes: they are dataclasses, and bad fields are errors."""

import dataclasses
import datetime
from dataclasses import field
from typing import Annotated, Any, Literal

import pytest

import smartconfig
from smartconfig import Prototype
from smartconfig.types import Template


# Prototypes are dataclasses ===========================================================


class Person(Prototype):
    name: str
    age: int = 0
    tags: list[str] = field(default_factory=list)


def test_subclass_is_a_dataclass():
    assert dataclasses.is_dataclass(Person)
    assert [f.name for f in dataclasses.fields(Person)] == ["name", "age", "tags"]


def test_init_eq_and_repr_come_from_dataclasses():
    # when
    person = Person(name="Alice", age=3)

    # then
    assert person == Person(name="Alice", age=3, tags=[])
    assert person != Person(name="Bob", age=3)
    assert repr(person) == "Person(name='Alice', age=3, tags=[])"


def test_fields_are_keyword_only():
    # so that a field without a default may follow one with a default
    with pytest.raises(TypeError):
        Person("Alice")  # type: ignore[misc]


def test_required_field_without_default_must_be_given():
    with pytest.raises(TypeError):
        Person()  # type: ignore[call-arg]


def test_default_factory_gives_each_instance_its_own_value():
    # when
    first = Person(name="a")
    second = Person(name="b")
    first.tags.append("x")

    # then
    assert second.tags == []


def test_mutable_default_is_an_error_from_dataclasses():
    with pytest.raises(ValueError, match="default_factory"):

        class Bad(Prototype):
            xs: list[str] = []


def test_instances_of_different_prototypes_are_not_equal():
    # given
    class A(Prototype):
        x: int

    class B(Prototype):
        x: int

    # then
    assert A(x=1) != B(x=1)


def test_extra_keys_is_an_init_argument_and_compared_in_eq():
    # given
    class Website(Prototype, extra_keys=str):
        title: str

    # when
    website = Website(title="t", extra_keys={"a": "b"})

    # then
    assert website.extra_keys == {"a": "b"}
    assert website != Website(title="t")
    assert Website(title="t").extra_keys == {}
    assert repr(website) == "Website(title='t', extra_keys={'a': 'b'})"


# unsupported type hints ===============================================================


def test_unsupported_type_names_the_class_and_field():
    with pytest.raises(TypeError, match=r"Bad\.x"):

        class Bad(Prototype):
            x: set[int]


def test_bare_list_is_unsupported():
    with pytest.raises(TypeError, match=r"Bad\.xs"):

        class Bad(Prototype):
            xs: list


def test_bare_dict_is_unsupported():
    with pytest.raises(TypeError, match=r"Bad\.d"):

        class Bad(Prototype):
            d: dict


def test_dict_with_non_string_keys_is_unsupported():
    with pytest.raises(TypeError, match=r"Bad\.d"):

        class Bad(Prototype):
            d: dict[int, str]


def test_union_of_two_types_is_unsupported():
    with pytest.raises(TypeError, match=r"Bad\.x"):

        class Bad(Prototype):
            x: int | str


def test_literal_is_unsupported():
    with pytest.raises(TypeError, match=r"Bad\.x"):

        class Bad(Prototype):
            x: Literal["a", "b"]


def test_arbitrary_class_is_unsupported():
    with pytest.raises(TypeError, match=r"Bad\.x"):

        class Bad(Prototype):
            x: datetime.timedelta


def test_unsupported_type_inside_a_container_names_the_field():
    with pytest.raises(TypeError, match=r"Bad\.xs"):

        class Bad(Prototype):
            xs: list[set[int]]


def test_template_without_a_schema_is_unsupported_and_says_what_to_do():
    with pytest.raises(TypeError, match=r"smartconfig\.template"):

        class Bad(Prototype):
            title: Template


def test_plain_dataclass_is_unsupported():
    # given
    @dataclasses.dataclass
    class Plain:
        x: int

    # then
    with pytest.raises(TypeError, match=r"Bad\.plain"):

        class Bad(Prototype):
            plain: Plain


# defaults =============================================================================


def test_nested_prototype_with_an_instance_default_is_an_error():
    # given
    class Options(Prototype):
        verbose: bool = False

    # then: dataclasses would share the instance; default_factory=Options is meant
    with pytest.raises((TypeError, ValueError)):

        class Bad(Prototype):
            options: Options = Options()


def test_nested_prototype_with_another_default_factory_is_an_error():
    # given
    class Options(Prototype):
        verbose: bool = False

    # then
    with pytest.raises(TypeError, match=r"Bad\.options"):

        class Bad(Prototype):
            options: Options = field(default_factory=lambda: Options(verbose=True))


def test_nested_prototype_defaulting_to_its_class_needs_all_defaults():
    # given
    class Options(Prototype):
        level: int

    # then: Options() has no value for level, so {} wouldn't resolve
    with pytest.raises(TypeError, match=r"Bad\.options"):

        class Bad(Prototype):
            options: Options = field(default_factory=Options)


def test_default_holding_a_prototype_instance_is_an_error():
    # given
    class Options(Prototype):
        verbose: bool = False

    # then: a schema's default is configuration, not an instance
    with pytest.raises(TypeError, match=r"Bad\.options"):

        class Bad(Prototype):
            options: list[Options] = field(default_factory=lambda: [Options()])


def test_explicit_schema_default_different_from_the_fields_is_an_error():
    with pytest.raises(TypeError, match=r"Bad\.x"):

        class Bad(Prototype):
            x: Annotated[int, smartconfig.schema({"type": "integer", "default": 1})] = 2


# the escape hatch =====================================================================


def test_two_smartconfig_annotations_are_an_error():
    with pytest.raises(TypeError, match=r"Bad\.x"):

        class Bad(Prototype):
            x: Annotated[
                int,
                smartconfig.schema({"type": "integer"}),
                smartconfig.schema({"type": "integer"}),
            ]


def test_nullable_type_with_non_nullable_schema_is_an_error():
    with pytest.raises(TypeError, match=r"Bad\.x.*nullable"):

        class Bad(Prototype):
            x: Annotated[str | None, smartconfig.schema({"type": "string"})]


def test_non_nullable_type_with_nullable_schema_is_an_error():
    with pytest.raises(TypeError, match=r"Bad\.x.*nullable"):

        class Bad(Prototype):
            x: Annotated[str, smartconfig.schema({"type": "string", "nullable": True})]


def test_any_type_with_any_schema_is_fine():
    # given: Any includes None, so either kind of schema fits it
    class Fine(Prototype):
        x: Annotated[Any, smartconfig.schema({"type": "string", "nullable": True})]
        y: Annotated[Any, smartconfig.schema({"type": "string"})]

    # then
    assert dataclasses.is_dataclass(Fine)


def test_nullable_type_with_any_schema_is_fine():
    # given: "any" accepts None unless it says it isn't nullable
    class Fine(Prototype):
        x: Annotated[str | None, smartconfig.schema({"type": "any"})]

    # then
    assert dataclasses.is_dataclass(Fine)


def test_schema_marker_needs_a_mapping_or_callable():
    with pytest.raises(TypeError):
        smartconfig.schema("string")  # type: ignore[arg-type]


def test_template_on_a_non_template_type_is_an_error():
    with pytest.raises(TypeError, match=r"Bad\.x.*Template"):

        class Bad(Prototype):
            x: Annotated[str, smartconfig.template({"type": "string"})]


# extra keys ===========================================================================


def test_field_named_extra_keys_with_extra_keys_option_is_an_error():
    with pytest.raises(TypeError, match=r"Bad.*extra_keys"):

        class Bad(Prototype, extra_keys=str):
            extra_keys: str


def test_field_named_extra_keys_without_the_option_is_also_an_error():
    # the name is reserved in every Prototype, so that a subclass can add the
    # option, and type checkers can know the attribute's type
    with pytest.raises(TypeError, match=r"Bad.*extra_keys"):

        class Bad(Prototype):
            extra_keys: dict[str, Any]


def test_unsupported_extra_keys_type_is_an_error():
    with pytest.raises(TypeError, match=r"Bad.*extra keys"):

        class Bad(Prototype, extra_keys=set[int]):
            pass
