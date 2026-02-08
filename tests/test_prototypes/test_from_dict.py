"""Tests for Prototype._from_dict() method."""

from smartconfig import Prototype


def test_from_dict_with_basic_prototype():
    # given
    class Student(Prototype):
        name: str
        age: int

    data = {"name": "Alice", "age": 20}

    # when
    student = Student._from_dict(data)

    # then
    assert isinstance(student, Student)
    assert student.name == "Alice"
    assert student.age == 20


def test_from_dict_with_nested_prototype():
    # given
    class Advisor(Prototype):
        name: str

    class Student(Prototype):
        name: str
        advisor: Advisor

    data = {"name": "Bob", "advisor": {"name": "Dr. Smith"}}

    # when
    student = Student._from_dict(data)

    # then
    assert isinstance(student, Student)
    assert student.name == "Bob"
    assert isinstance(student.advisor, Advisor)
    assert student.advisor.name == "Dr. Smith"


def test_from_dict_with_deeply_nested_prototypes():
    # given
    class Engine(Prototype):
        horsepower: int

    class Car(Prototype):
        engine: Engine

    class Garage(Prototype):
        car: Car

    data = {"car": {"engine": {"horsepower": 300}}}

    # when
    garage = Garage._from_dict(data)

    # then
    assert isinstance(garage, Garage)
    assert isinstance(garage.car, Car)
    assert isinstance(garage.car.engine, Engine)
    assert garage.car.engine.horsepower == 300


def test_from_dict_with_list_of_prototypes():
    # given
    class Course(Prototype):
        title: str

    class Student(Prototype):
        enrolled_in: list[Course]

    data = {"enrolled_in": [{"title": "Math"}, {"title": "Science"}]}

    # when
    student = Student._from_dict(data)

    # then
    assert isinstance(student, Student)
    assert len(student.enrolled_in) == 2
    assert all(isinstance(course, Course) for course in student.enrolled_in)
    assert student.enrolled_in[0].title == "Math"
    assert student.enrolled_in[1].title == "Science"


def test_from_dict_with_dict_str_prototype_values():
    # given
    class Course(Prototype):
        number: int

    class Student(Prototype):
        courses: dict[str, Course]

    data = {"courses": {"math": {"number": 120}, "science": {"number": 200}}}

    # when
    student = Student._from_dict(data)

    # then
    assert isinstance(student, Student)
    assert "math" in student.courses
    assert "science" in student.courses
    assert isinstance(student.courses["math"], Course)
    assert isinstance(student.courses["science"], Course)
    assert student.courses["math"].number == 120
    assert student.courses["science"].number == 200


def test_from_dict_with_list_of_list_of_prototypes():
    # given
    class Course(Prototype):
        title: str

    class Student(Prototype):
        schedule: list[list[Course]]

    data = {
        "schedule": [
            [{"title": "Math"}, {"title": "Science"}],
            [{"title": "History"}, {"title": "Art"}],
        ]
    }

    # when
    student = Student._from_dict(data)

    # then
    assert isinstance(student, Student)
    assert len(student.schedule) == 2
    assert all(isinstance(day, list) for day in student.schedule)
    assert all(isinstance(course, Course) for day in student.schedule for course in day)
    assert student.schedule[0][0].title == "Math"
    assert student.schedule[0][1].title == "Science"
    assert student.schedule[1][0].title == "History"
    assert student.schedule[1][1].title == "Art"
