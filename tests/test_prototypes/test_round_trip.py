"""Tests for _as_dict -> _from_dict round trips."""

from smartconfig import Prototype


def test_round_trip_basic_prototype():
    # given
    class Student(Prototype):
        name: str
        age: int

    original_student = Student(name="Alice", age=20)

    # when
    data = original_student._as_dict()
    reconstructed_student = Student._from_dict(data)

    # then
    assert isinstance(reconstructed_student, Student)
    assert reconstructed_student == original_student


def test_round_trip_nested_prototype():
    # given
    class Advisor(Prototype):
        name: str

    class Student(Prototype):
        name: str
        advisor: Advisor

    original_student = Student(name="Bob", advisor=Advisor(name="Dr. Smith"))

    # when
    data = original_student._as_dict()
    reconstructed_student = Student._from_dict(data)

    # then
    assert isinstance(reconstructed_student, Student)
    assert reconstructed_student == original_student


def test_round_trip_deeply_nested_prototypes():
    # given
    class Engine(Prototype):
        horsepower: int

    class Car(Prototype):
        engine: Engine

    class Garage(Prototype):
        car: Car

    original_garage = Garage(car=Car(engine=Engine(horsepower=500)))

    # when
    data = original_garage._as_dict()
    reconstructed_garage = Garage._from_dict(data)

    # then
    assert isinstance(reconstructed_garage, Garage)
    assert reconstructed_garage == original_garage


def test_round_trip_list_of_prototypes():
    # given
    class Course(Prototype):
        title: str

    class Student(Prototype):
        enrolled_in: list[Course]

    original_student = Student(
        enrolled_in=[Course(title="Math"), Course(title="Science")]
    )

    # when
    data = original_student._as_dict()
    reconstructed_student = Student._from_dict(data)

    # then
    assert isinstance(reconstructed_student, Student)
    assert reconstructed_student == original_student
