"""Tests for the is_prototype_class utility."""

from smartconfig import Prototype, is_prototype_class


def test_is_prototype_class_with_prototype():
    # given
    class Student(Prototype):
        name: str
        age: int

    # when
    result = is_prototype_class(Student)

    # then
    assert result is True


def test_is_prototype_class_with_Prototype_itself():
    # when
    result = is_prototype_class(Prototype)

    # then
    assert result is False


def test_is_prototype_class_with_non_prototype_class():
    # given
    class NotAPrototype:
        pass

    # when
    result = is_prototype_class(NotAPrototype)

    # then
    assert result is False


def test_is_prototype_class_with_builtin_type():
    # when
    result = is_prototype_class(dict)

    # then
    assert result is False


def test_is_prototype_class_with_instance_of_prototype():
    # given
    class Student(Prototype):
        name: str
        age: int

    student = Student(name="Alice", age=20)

    # when
    result = is_prototype_class(student)

    # then
    assert result is False


def test_is_prototype_class_with_int():
    # when
    result = is_prototype_class(42)

    # then
    assert result is False
