"""Tests for Prototype class-based schemas."""

from smartconfig import resolve, Prototype, NotRequired
from smartconfig.types import (
    ConfigurationDict,
)


def test_resolve_given_prototype_as_spec():
    # given
    class Student(Prototype):
        name: str
        age: int

    cfg: ConfigurationDict = {
        "name": "Alice",
        "age": "21",
    }

    # when
    result = resolve(cfg, Student)

    # then
    assert isinstance(result, Student)
    assert result.name == "Alice"
    assert result.age == 21


def test_resolve_with_nested_prototype():
    # given
    class Address(Prototype):
        city: str
        zip_code: int

    class Person(Prototype):
        name: str
        address: Address

    cfg: ConfigurationDict = {
        "name": "Bob",
        "address": {"city": "New York", "zip_code": "10001"},
    }

    # when
    result = resolve(cfg, Person)

    # then
    assert isinstance(result, Person)
    assert isinstance(result.address, Address)
    assert result.name == "Bob"
    assert result.address.city == "New York"
    assert result.address.zip_code == 10001


def test_resolve_with_deeply_nested_prototype():
    # given
    class Address(Prototype):
        city: str
        zip_code: int

    class Person(Prototype):
        name: str
        address: Address

    class Company(Prototype):
        owner: Person
        address: Address

    cfg: ConfigurationDict = {
        "owner": {
            "name": "Charlie",
            "address": {"city": "San Francisco", "zip_code": "94105"},
        },
        "address": {"city": "Seattle", "zip_code": "98101"},
    }

    # when
    result = resolve(cfg, Company)

    # then
    assert isinstance(result, Company)
    assert isinstance(result.owner, Person)
    assert isinstance(result.owner.address, Address)
    assert result.owner.name == "Charlie"
    assert result.owner.address.city == "San Francisco"
    assert result.address.city == "Seattle"


def test_resolve_with_list_of_prototypes():
    # given
    class Address(Prototype):
        city: str
        zip_code: int

    class Person(Prototype):
        name: str
        address: Address

    class Team(Prototype):
        members: list[Person]

    cfg: ConfigurationDict = {
        "members": [
            {"name": "Member 1", "address": {"city": "A", "zip_code": 1}},
            {"name": "Member 2", "address": {"city": "B", "zip_code": 2}},
        ]
    }

    # when
    result = resolve(cfg, Team)

    # then
    assert isinstance(result, Team)
    assert len(result.members) == 2
    assert all(isinstance(member, Person) for member in result.members)
    assert result.members[0].name == "Member 1"
    assert result.members[1].address.city == "B"


def test_resolve_with_dict_of_prototypes():
    # given
    class Address(Prototype):
        city: str
        zip_code: int

    class Person(Prototype):
        name: str
        address: Address

    class Team(Prototype):
        members: list[Person]

    class Organization(Prototype):
        teams: dict[str, Team]

    cfg: ConfigurationDict = {
        "teams": {
            "alpha": {
                "members": [{"name": "Alice", "address": {"city": "A", "zip_code": 1}}]
            },
            "beta": {
                "members": [{"name": "Bob", "address": {"city": "B", "zip_code": 2}}]
            },
        }
    }

    # when
    result = resolve(cfg, Organization)

    # then
    assert isinstance(result, Organization)
    assert isinstance(result.teams["alpha"], Team)
    assert result.teams["alpha"].members[0].name == "Alice"
    assert result.teams["beta"].members[0].name == "Bob"


def test_resolve_with_optional_fields():
    # given
    class ConfigWithOptional(Prototype):
        required: int
        optional: NotRequired[int]

    cfg_with: ConfigurationDict = {"required": 1, "optional": 2}
    cfg_without: ConfigurationDict = {"required": 1}

    # when
    result_with = resolve(cfg_with, ConfigWithOptional)
    result_without = resolve(cfg_without, ConfigWithOptional)

    # then
    assert result_with.required == 1
    assert result_with.optional == 2
    assert result_without.required == 1
    # The optional attribute should not be set if the key was missing
    assert not hasattr(result_without, "optional")


def test_resolve_with_nullable_fields():
    # given
    class ConfigWithNullable(Prototype):
        not_nullable: int
        nullable: int | None

    cfg_val: ConfigurationDict = {"not_nullable": 1, "nullable": 2}
    cfg_none: ConfigurationDict = {"not_nullable": 1, "nullable": None}

    # when
    result_val = resolve(cfg_val, ConfigWithNullable)
    result_none = resolve(cfg_none, ConfigWithNullable)

    # then
    assert result_val.nullable == 2
    assert result_none.nullable is None


def test_resolve_with_default_values():
    # given
    class ConfigWithDefaults(Prototype):
        no_default: int
        with_default: int = 42

    cfg_default: ConfigurationDict = {"no_default": 1}
    cfg_override: ConfigurationDict = {"no_default": 1, "with_default": 100}

    # when
    result_default = resolve(cfg_default, ConfigWithDefaults)
    result_override = resolve(cfg_override, ConfigWithDefaults)

    # then
    assert result_default.with_default == 42
    assert result_override.with_default == 100
