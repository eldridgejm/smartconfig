"""Tests for Prototype constructor behavior."""

from pytest import raises

from smartconfig import NotRequired, Prototype


def test_init_with_all_fields_provided():
    # given
    class Student(Prototype):
        name: str
        age: int

    # when
    student = Student(name="Alice", age=20)

    # then
    assert student.name == "Alice"
    assert student.age == 20


def test_init_with_missing_required_field_raises():
    # given
    class Student(Prototype):
        name: str
        age: int

    # when/then
    with raises(TypeError, match="missing required field 'age'"):
        Student(name="Alice")


def test_init_ignores_extra_fields():
    # given
    class Student(Prototype):
        name: str
        age: int

    # when
    student = Student(name="Alice", age=20, grade="A")

    # then
    assert student.name == "Alice"
    assert student.age == 20
    assert not hasattr(student, "grade")


def test_init_with_missing_optional_field():
    # given
    class Student(Prototype):
        name: str
        age: NotRequired[int]

    # when
    student = Student(name="Bob")

    # then
    assert student.name == "Bob"
    assert not hasattr(student, "age")


def test_init_with_missing_field_with_default_value():
    # given
    class Student(Prototype):
        name: str
        age: int = 18

    # when
    student = Student(name="Charlie")

    # then
    assert student.name == "Charlie"
    assert student.age == 18


def test_init_supplying_optional_field_with_value_overrides_default():  # given
    class Student(Prototype):
        name: str
        age: int = 18

    # when
    student = Student(name="Diana", age=21)

    # then
    assert student.name == "Diana"
    assert student.age == 21


def test_init_does_not_perform_type_checking_or_coercion():
    # given
    class Student(Prototype):
        name: str
        age: int

    # when
    student = Student(name=123, age="old")

    # then
    assert student.name == 123
    assert student.age == "old"


def test_init_does_not_validate_nullability():
    # given
    class Student(Prototype):
        # not nullable
        name: str

    # when
    student = Student(name=None)

    # then
    assert student.name is None
