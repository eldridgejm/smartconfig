"""Tests for Prototype __eq__ behavior."""

from smartconfig import Prototype


def test_prototype_equality_with_same_field_values():
    # given
    class Student(Prototype):
        name: str
        age: int

    student1 = Student(name="Alice", age=20)
    student2 = Student(name="Alice", age=20)

    # then
    assert student1 == student2


def test_prototype_inequality_with_different_field_values():
    # given
    class Student(Prototype):
        name: str
        age: int

    student1 = Student(name="Alice", age=20)
    student2 = Student(name="Bob", age=22)

    # then
    assert student1 != student2


def test_prototype_inequality_with_different_types():
    # given
    class Student(Prototype):
        name: str
        age: int

    student = Student(name="Alice", age=20)
    not_a_student = {"name": "Alice", "age": 20}

    # then
    assert student != not_a_student


def test_prototype_inequality_with_different_prototype_types():
    # given
    class Student(Prototype):
        name: str
        age: int

    class Teacher(Prototype):
        name: str
        age: int

    student = Student(name="Alice", age=20)
    teacher = Teacher(name="Alice", age=20)

    # then
    assert student != teacher


def test_prototype_equality_with_list_fields():
    # given
    class Student(Prototype):
        name: str
        enrolled_in: list[str]

    student1 = Student(name="Alice", enrolled_in=["Math", "Science"])
    student2 = Student(name="Alice", enrolled_in=["Math", "Science"])

    # then
    assert student1 == student2


def test_prototype_equality_with_nested_prototypes():  # given
    class Advisor(Prototype):
        name: str

    class Student(Prototype):
        name: str
        advisor: Advisor

    advisor1 = Advisor(name="Dr. Smith")
    advisor2 = Advisor(name="Dr. Smith")

    student1 = Student(name="Alice", advisor=advisor1)
    student2 = Student(name="Alice", advisor=advisor2)

    # then
    assert student1 == student2


def test_prototype_inequality_with_extra_fields():
    # given
    class Student(Prototype):
        name: str
        age: int

    student1 = Student(name="Alice", age=20)
    student2 = Student(name="Alice", age=20)

    # when
    student2.extra_field = "extra"  # type: ignore

    # then
    assert student1 != student2


def test_prototype_equality_with_extra_fields():
    # given
    class Student(Prototype):
        name: str
        age: int

    student1 = Student(name="Alice", age=20)
    student2 = Student(name="Alice", age=20)

    # when
    student1.extra_field = "extra"  # type: ignore
    student2.extra_field = "extra"  # type: ignore

    # then
    assert student1 == student2


def test_prototype_equality_with_missing_fields_uses_defaults():  # given
    class Student(Prototype):
        name: str
        age: int = 18

    student1 = Student(name="Alice")
    student2 = Student(name="Alice", age=18)

    # then
    assert student1 == student2
