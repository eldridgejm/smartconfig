"""Tests for resolve() with a Prototype class in place of a schema."""

import datetime
from dataclasses import field
from typing import Annotated, Any

import pytest

import smartconfig
from smartconfig import Prototype, resolve
from smartconfig.prototypes import schema_of
from smartconfig.exceptions import InvalidSchemaError, ResolutionError
from smartconfig.types import (
    Configuration,
    ConfigurationDict,
    KeyPath,
    Schema,
    Template,
)


class Address(Prototype):
    street: str
    city: str = "San Diego"


class Person(Prototype):
    name: str
    age: int
    address: Address
    born: datetime.date | None = None
    nicknames: list[str] = field(default_factory=list)


PERSON_CFG: dict[str, Any] = {
    "name": "Alice",
    "age": "3",
    "address": {"street": "Gilman"},
}


def test_resolve_returns_an_instance():
    # when
    person = resolve(PERSON_CFG, Person)

    # then
    assert person == Person(name="Alice", age=3, address=Address(street="Gilman"))


def test_resolve_gives_the_same_values_as_the_schema_dict():
    # when
    instance = resolve(PERSON_CFG, Person)
    as_dict = resolve(PERSON_CFG, schema_of(Person))

    # then
    assert instance == smartconfig.prototypes.instantiate(Person, as_dict)


def test_interpolation_functions_and_global_variables_work():
    # given
    cfg: ConfigurationDict = {
        "name": "${ first } ${ last }",
        "age": {"__if__": {"condition": True, "then": 4, "else": 5}},
        "address": {"street": "${ street }", "city": "${ name }ville"},
        "born": {"__datetime.parse__": "2026-01-01"},
    }

    # when
    person = resolve(
        cfg, Person, global_variables={"first": "A", "last": "B", "street": "S"}
    )

    # then
    assert person.name == "A B"
    assert person.age == 4
    assert person.address == Address(street="S", city="A Bville")
    assert person.born == datetime.date(2026, 1, 1)


def test_custom_functions_work():
    # given
    def double(args: smartconfig.types.FunctionArgs) -> Configuration:
        value = args.resolve(args.input)
        assert isinstance(value, int)
        return 2 * value

    # when
    person = resolve(
        {**PERSON_CFG, "age": {"__double__": 21}}, Person, functions={"double": double}
    )

    # then
    assert person.age == 42


def _error(cfg: Any, spec: Any) -> tuple[type, KeyPath, str]:
    """The kind, keypath and reason of the error resolving cfg against spec."""
    with pytest.raises((ResolutionError, InvalidSchemaError)) as excinfo:
        resolve(cfg, spec)
    error = excinfo.value
    assert isinstance(error, (ResolutionError, InvalidSchemaError))
    return type(error), error.keypath, str(error)


def test_missing_key_error_is_the_same_as_for_the_schema_dict():
    # given
    cfg = {"name": "A", "age": 1, "address": {}}

    # then
    assert _error(cfg, Person) == _error(cfg, schema_of(Person))
    assert _error(cfg, Person)[1] == ("address", "street")


def test_extra_key_error_is_the_same_as_for_the_schema_dict():
    # given
    cfg = {**PERSON_CFG, "address": {"street": "s", "zip": 92093}}

    # then
    assert _error(cfg, Person) == _error(cfg, schema_of(Person))
    assert _error(cfg, Person)[1] == ("address", "zip")


def test_conversion_error_is_the_same_as_for_the_schema_dict():
    # given
    cfg = {**PERSON_CFG, "age": "three"}

    # then
    assert _error(cfg, Person) == _error(cfg, schema_of(Person))
    assert _error(cfg, Person)[1] == ("age",)


def test_list_element_error_is_the_same_as_for_the_schema_dict():
    # given
    cfg = {**PERSON_CFG, "nicknames": ["a", None]}

    # then
    assert _error(cfg, Person) == _error(cfg, schema_of(Person))
    assert _error(cfg, Person)[1] == ("nicknames", "1")


def test_reference_error_is_the_same_as_for_the_schema_dict():
    # given
    cfg = {**PERSON_CFG, "name": "${ nope }"}

    # then
    assert _error(cfg, Person) == _error(cfg, schema_of(Person))


def test_invalid_explicit_schema_error_is_the_same_as_for_the_schema_dict():
    # given: the explicit schema is used as given, so it is checked by resolve()
    class Bad(Prototype):
        x: Annotated[Any, smartconfig.prototypes.schema({"type": "nonsense"})]

    # then
    assert _error({"x": 1}, Bad) == _error({"x": 1}, schema_of(Bad))
    assert _error({"x": 1}, Bad)[1] == ("required_keys", "x", "type")


def test_dynamic_schema_through_the_escape_hatch():
    # given
    def by_kind(cfg: Configuration, keypath: KeyPath) -> Schema:
        assert isinstance(cfg, dict)
        if cfg["kind"] == "number":
            return {
                "type": "dict",
                "required_keys": {"kind": {"type": "string"}, "x": {"type": "integer"}},
            }
        raise ResolutionError("Unknown kind.", keypath + ("kind",))

    class Thing(Prototype):
        item: Annotated[dict[str, Any], smartconfig.prototypes.schema(by_kind)]

    # when
    thing = resolve({"item": {"kind": "number", "x": "3"}}, Thing)

    # then
    assert thing.item == {"kind": "number", "x": 3}
    assert _error({"item": {"kind": "word"}}, Thing)[1] == ("item", "kind")


def test_template_field_resolves_to_a_template():
    # given
    class Page(Prototype):
        title: Annotated[
            Template,
            smartconfig.prototypes.template(
                {"type": "string"}, parameters=["publication"]
            ),
        ]

    # when
    page = resolve({"title": {"__template__": "Lecture ${ publication.number }"}}, Page)

    # then
    assert isinstance(page.title, Template)
    assert page.title.evaluate({"publication": {"number": 4}}) == "Lecture 4"


def test_extra_keys_are_resolved_against_their_schema():
    # given
    class Website(Prototype, extra_keys=int):
        title: str

    # when
    website = resolve({"title": "t", "a": "1", "b": "${ a }2"}, Website)

    # then
    assert website.title == "t"
    assert website.extra_keys == {"a": 1, "b": 12}


def test_extra_key_errors_are_the_same_as_for_the_schema_dict():
    # given
    class Website(Prototype, extra_keys=int):
        title: str

    # then
    cfg = {"title": "t", "a": "x"}
    assert _error(cfg, Website) == _error(cfg, schema_of(Website))
    assert _error(cfg, Website)[1] == ("a",)


def test_preserve_type_keeps_containers_inside_annotated_fields():
    # given
    class MyDict(dict):
        pass

    class Holder(Prototype):
        data: Annotated[dict[str, Any], smartconfig.prototypes.schema({"type": "any"})]

    # when
    holder = resolve({"data": MyDict(x=1)}, Holder, preserve_type=True)

    # then
    assert isinstance(holder, Holder)
    assert type(holder.data) is MyDict
