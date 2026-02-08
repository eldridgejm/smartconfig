"""Tests for Prototype._schema() method."""

import datetime
from typing import Any

from smartconfig import NotRequired, Prototype, validate_schema


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
