"""Tests for the Prototype feature."""

import datetime
from typing import Any

from pytest import raises

from smartconfig import NotRequired, Prototype, validate_schema, is_prototype_class


# prototype definition =================================================================


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


# initialization =======================================================================

# the initializer for a Prototype doesn't do much of anything: it doesn't do type
# checking, coercion, or anything else. It *does* fill in default values, however.


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


# __eq__ ===============================================================================


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


# __repr__ =============================================================================


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


# _schema() ============================================================================


def test_schema_with_basic_prototype():
    # given
    class Student(Prototype):
        name: str
        age: int

    # when
    schema = Student._schema()

    # then
    validate_schema(schema)
    assert schema == {
        "type": "dict",
        "required_keys": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
        },
    }


def test_schema_with_list_field():
    # given
    class Student(Prototype):
        enrolled_in: list[str]

    # when
    schema = Student._schema()

    # then
    validate_schema(schema)
    assert schema == {
        "type": "dict",
        "required_keys": {
            "enrolled_in": {
                "type": "list",
                "element_schema": {"type": "string"},
            },
        },
    }


def test_schema_with_list_any_field():
    # given
    class Student(Prototype):
        metadata: list[Any]

    # when
    schema = Student._schema()

    # then
    validate_schema(schema)
    assert schema == {
        "type": "dict",
        "required_keys": {
            "metadata": {
                "type": "list",
                "element_schema": {"type": "any"},
            },
        },
    }


def test_schema_with_dict_str_int_field():
    # given
    class Student(Prototype):
        grades: dict[str, int]

    # when
    schema = Student._schema()

    # then
    validate_schema(schema)
    assert schema == {
        "type": "dict",
        "required_keys": {
            "grades": {
                "type": "dict",
                "extra_keys_schema": {"type": "integer"},
            },
        },
    }


def test_schema_with_dict_str_any_field():
    # given
    class Student(Prototype):
        metadata: dict[str, Any]

    # when
    schema = Student._schema()

    # then
    validate_schema(schema)
    assert schema == {
        "type": "dict",
        "required_keys": {
            "metadata": {
                "type": "dict",
                "extra_keys_schema": {"type": "any"},
            },
        },
    }


def test_schema_with_datetime_field():
    # given
    class Student(Prototype):
        enrolled_at: datetime.datetime

    # when
    schema = Student._schema()

    # then
    validate_schema(schema)
    assert schema == {
        "type": "dict",
        "required_keys": {
            "enrolled_at": {"type": "datetime"},
        },
    }


def test_schema_with_optional_field():
    # given
    class Student(Prototype):
        email: NotRequired[str]

    # when
    schema = Student._schema()

    # then
    validate_schema(schema)
    assert schema == {
        "type": "dict",
        "optional_keys": {
            "email": {"type": "string"},
        },
    }


def test_schema_with_default_field():
    # given
    class Student(Prototype):
        name: str = "Unknown"

    # when
    schema = Student._schema()

    # then
    validate_schema(schema)
    assert schema == {
        "type": "dict",
        "optional_keys": {
            "name": {"type": "string", "default": "Unknown"},
        },
    }


def test_schema_with_nullable_field():
    # given
    class Student(Prototype):
        nickname: str | None

    # when
    schema = Student._schema()

    # then
    validate_schema(schema)
    assert schema == {
        "type": "dict",
        "required_keys": {
            "nickname": {"type": "string", "nullable": True},
        },
    }


def test_schema_with_nested_dict_values():
    # given
    class Student(Prototype):
        grades: dict[str, dict[str, int]]

    # when
    schema = Student._schema()

    # then
    validate_schema(schema)
    assert schema == {
        "type": "dict",
        "required_keys": {
            "grades": {
                "type": "dict",
                "extra_keys_schema": {
                    "type": "dict",
                    "extra_keys_schema": {"type": "integer"},
                },
            },
        },
    }


def test_schema_with_any_field():
    # given
    class Student(Prototype):
        metadata: Any

    # when
    schema = Student._schema()

    # then
    validate_schema(schema)
    assert schema == {
        "type": "dict",
        "required_keys": {
            "metadata": {"type": "any"},
        },
    }


def test_schema_with_nullable_list_elements():
    # given
    class Student(Prototype):
        nicknames: list[str | None]

    # when
    schema = Student._schema()

    # then
    validate_schema(schema)
    assert schema == {
        "type": "dict",
        "required_keys": {
            "nicknames": {
                "type": "list",
                "element_schema": {"type": "string", "nullable": True},
            },
        },
    }


def test_schema_with_nullable_dict_values():
    # given
    class Student(Prototype):
        grades: dict[str, int | None]

    # when
    schema = Student._schema()

    # then
    validate_schema(schema)
    assert schema == {
        "type": "dict",
        "required_keys": {
            "grades": {
                "type": "dict",
                "extra_keys_schema": {"type": "integer", "nullable": True},
            },
        },
    }


def test_schema_with_default_dict():
    # given
    class Student(Prototype):
        grades: dict[str, int] = {"math": 100, "science": 95}

    # when
    schema = Student._schema()

    # then
    validate_schema(schema)
    assert schema == {
        "type": "dict",
        "optional_keys": {
            "grades": {
                "type": "dict",
                "extra_keys_schema": {"type": "integer"},
                "default": {"math": 100, "science": 95},
            },
        },
    }


def test_schema_with_nested_prototype():
    # given
    class Advisor(Prototype):
        name: str
        office: str

    class Student(Prototype):
        name: str
        advisor: Advisor

    # when
    schema = Student._schema()

    # then
    validate_schema(schema)
    assert schema == {
        "type": "dict",
        "required_keys": {
            "name": {"type": "string"},
            "advisor": {
                "type": "dict",
                "required_keys": {
                    "name": {"type": "string"},
                    "office": {"type": "string"},
                },
            },
        },
    }


def test_schema_with_deeply_nested_prototypes():
    # given
    class Engine(Prototype):
        horsepower: int

    class Car(Prototype):
        engine: Engine

    class Garage(Prototype):
        car: Car

    # when
    schema = Garage._schema()

    # then
    validate_schema(schema)
    assert schema == {
        "type": "dict",
        "required_keys": {
            "car": {
                "type": "dict",
                "required_keys": {
                    "engine": {
                        "type": "dict",
                        "required_keys": {
                            "horsepower": {"type": "integer"},
                        },
                    },
                },
            },
        },
    }


def test_schema_with_optional_nested_prototype():
    # given
    class Advisor(Prototype):
        name: str

    class Student(Prototype):
        advisor: NotRequired[Advisor]

    # when
    schema = Student._schema()

    # then
    validate_schema(schema)
    assert schema == {
        "type": "dict",
        "optional_keys": {
            "advisor": {
                "type": "dict",
                "required_keys": {
                    "name": {"type": "string"},
                },
            },
        },
    }


def test_schema_with_default_nested_prototype():
    # given
    class Advisor(Prototype):
        name: str
        age: int

    class Student(Prototype):
        advisor: Advisor = Advisor(name="TBD", age=50)

    # when
    schema = Student._schema()

    # then
    validate_schema(schema)
    assert schema == {
        "type": "dict",
        "optional_keys": {
            "advisor": {
                "type": "dict",
                "required_keys": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "default": {"name": "TBD", "age": 50},
            },
        },
    }


def test_schema_with_empty_prototype():
    # given
    class Empty(Prototype):
        pass

    # when
    schema = Empty._schema()

    # then
    validate_schema(schema)
    assert schema == {"type": "dict"}


# _from_dict() =========================================================================

# _from_dict constructs a Prototype instance from a dictionary. No type checking or
# coercion is performed; however, nested Prototypes are constructed as needed.


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


# _as_dict() ===========================================================================


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


# round-trip tests =====================================================================


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


# is_prototype_class ===================================================================


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
