"""Tests for Prototype class definition and type validation."""

from pytest import raises

from smartconfig import Prototype


def test_defining_simple_prototype():
    # given
    class Student(Prototype):
        name: str
        age: int

    # then
    assert Student.__annotations__ == {"name": str, "age": int}
    assert issubclass(Student, Prototype)


def test_defining_prototype_with_unsupported_type_raises():
    with raises(TypeError):

        class BadPrototype(Prototype):
            coords: tuple[int, int]


def test_defining_prototype_with_non_str_dict_key_type_raises():
    with raises(TypeError):

        class BadPrototype(Prototype):
            mapping: dict[int, str]


def test_defining_prototype_with_none_default_for_nullable_field():
    # given
    class GoodPrototype(Prototype):
        name: str | None = None

    # then
    assert GoodPrototype.__annotations__ == {"name": str | None}


def test_defining_prototype_with_unparameterized_generic_type_raises():
    with raises(TypeError):

        class BadPrototype(Prototype):
            items: list


def test_defining_prototype_with_union_type_raises():
    with raises(TypeError):

        class BadPrototype(Prototype):
            value: int | str


def test_defining_prototype_with_list_of_union_type_raises():
    with raises(TypeError):

        class BadPrototype(Prototype):
            values: list[int | str]


def test_defining_prototype_without_type_annotation_raises():
    with raises(TypeError):

        class BadPrototype(Prototype):
            name = "Unnamed"
