"""Tests for Prototype __repr__ behavior."""

from smartconfig import NotRequired, Prototype


def test_prototype_repr():
    # given
    class Student(Prototype):
        name: str
        age: int

    student = Student(name="Alice", age=20)

    # when
    repr_str = repr(student)

    # then
    assert repr_str == "Student(name='Alice', age=20)"


def test_prototype_repr_with_optional_field():
    # given
    class Student(Prototype):
        name: str
        age: NotRequired[int]

    student = Student(name="Alice")

    # when
    repr_str = repr(student)

    # then
    assert repr_str == "Student(name='Alice')"
