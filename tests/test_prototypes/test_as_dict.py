"""Tests for Prototype._as_dict() method."""

from smartconfig import Prototype


def test_as_dict_with_basic_prototype():
    # given
    class Student(Prototype):
        name: str
        age: int

    student = Student(name="Alice", age=20)

    # when
    data = student._as_dict()

    # then
    assert data == {"name": "Alice", "age": 20}


def test_as_dict_with_nested_prototype():
    # given
    class Advisor(Prototype):
        name: str

    class Student(Prototype):
        name: str
        advisor: Advisor

    advisor = Advisor(name="Dr. Smith")
    student = Student(name="Barack", advisor=advisor)

    # when
    data = student._as_dict()

    # then
    assert data == {"name": "Barack", "advisor": {"name": "Dr. Smith"}}


def test_as_dict_with_deeply_nested_prototypes():
    # given
    class Engine(Prototype):
        horsepower: int

    class Car(Prototype):
        engine: Engine

    class Garage(Prototype):
        car: Car

    engine = Engine(horsepower=400)
    car = Car(engine=engine)
    garage = Garage(car=car)

    # when
    data = garage._as_dict()

    # then
    assert data == {"car": {"engine": {"horsepower": 400}}}


def test_as_dict_with_list_of_str_field():
    # given
    class Student(Prototype):
        enrolled_in: list[str]

    student = Student(enrolled_in=["Math", "Science"])

    # when
    data = student._as_dict()

    # then
    assert data == {"enrolled_in": ["Math", "Science"]}


def test_as_dict_with_list_of_prototypes():
    # given
    class Course(Prototype):
        title: str

    class Student(Prototype):
        enrolled_in: list[Course]

    student = Student(enrolled_in=[Course(title="Math"), Course(title="Science")])

    # when
    data = student._as_dict()

    # then
    assert data == {"enrolled_in": [{"title": "Math"}, {"title": "Science"}]}


def test_as_dict_with_dict_str_prototype_values():
    # given
    class Course(Prototype):
        number: int

    class Student(Prototype):
        courses: dict[str, Course]

    student = Student(
        courses={
            "math": Course(number=120),
            "science": Course(number=200),
        }
    )

    # when
    data = student._as_dict()

    # then
    assert data == {
        "courses": {
            "math": {"number": 120},
            "science": {"number": 200},
        }
    }
