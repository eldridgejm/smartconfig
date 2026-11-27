"""Tests for instantiate(): building a Prototype instance from a resolved dict."""

import datetime
from dataclasses import field
from typing import Annotated, Any

import pytest

import smartconfig
from smartconfig import Prototype
from smartconfig.prototypes import instantiate


class Address(Prototype):
    street: str
    city: str = "San Diego"


class Person(Prototype):
    name: str
    address: Address
    born: datetime.date | None = None


def test_simple_fields_are_used_as_given():
    # when
    address = instantiate(Address, {"street": "Gilman", "city": "La Jolla"})

    # then
    assert address == Address(street="Gilman", city="La Jolla")


def test_nested_prototype_becomes_an_instance():
    # when
    person = instantiate(Person, {"name": "A", "address": {"street": "Gilman"}})

    # then
    assert person == Person(name="A", address=Address(street="Gilman"))


def test_missing_optional_key_takes_the_fields_default():
    # when
    address = instantiate(Address, {"street": "Gilman"})

    # then
    assert address.city == "San Diego"


def test_missing_required_key_raises():
    with pytest.raises(TypeError):
        instantiate(Address, {})


def test_unexpected_key_raises():
    with pytest.raises(TypeError, match="unexpected"):
        instantiate(Address, {"street": "Gilman", "zip": "92093"})


def test_nullable_nested_prototype_that_is_none_stays_none():
    # given
    class Maybe(Prototype):
        address: Address | None

    # then
    assert instantiate(Maybe, {"address": None}) == Maybe(address=None)
    assert instantiate(Maybe, {"address": {"street": "s"}}) == Maybe(
        address=Address(street="s")
    )


def test_list_and_dict_of_prototypes_become_instances():
    # given
    class Directory(Prototype):
        people: list[Address]
        by_name: dict[str, Address]
        maybe: list[Address | None]

    # when
    directory = instantiate(
        Directory,
        {
            "people": [{"street": "a"}],
            "by_name": {"b": {"street": "b"}},
            "maybe": [None, {"street": "c"}],
        },
    )

    # then
    assert directory == Directory(
        people=[Address(street="a")],
        by_name={"b": Address(street="b")},
        maybe=[None, Address(street="c")],
    )


def test_annotated_schema_field_is_kept_as_is():
    # given: a dict that looks like an Address stays a dict
    class Raw(Prototype):
        address: Annotated[
            dict[str, Any], smartconfig.prototypes.schema({"type": "any"})
        ]

    # when
    raw = instantiate(Raw, {"address": {"street": "s"}})

    # then
    assert raw.address == {"street": "s"}


def test_any_field_is_kept_as_is():
    # given
    class Anything(Prototype):
        x: Any

    # then
    assert instantiate(Anything, {"x": {"street": "s"}}).x == {"street": "s"}


def test_extra_keys_go_into_extra_keys():
    # given
    class Book(Prototype, extra_keys=Address):
        title: str

    # when
    book = instantiate(Book, {"title": "t", "home": {"street": "s"}})

    # then
    assert book.title == "t"
    assert book.extra_keys == {"home": Address(street="s")}


def test_extra_keys_with_schema_are_kept_as_is():
    # given
    class Book(Prototype, extra_keys=smartconfig.prototypes.schema({"type": "any"})):
        title: str

    # when
    book = instantiate(Book, {"title": "t", "home": {"street": "s"}})

    # then
    assert book.extra_keys == {"home": {"street": "s"}}


def test_default_factory_class_field_missing_takes_a_fresh_instance():
    # given
    class Options(Prototype):
        verbose: bool = False

    class Settings(Prototype):
        options: Options = field(default_factory=Options)

    # then
    assert instantiate(Settings, {}) == Settings(options=Options())


def test_instantiate_a_non_prototype_raises():
    with pytest.raises(TypeError):
        instantiate(dict, {})  # type: ignore[type-var]


def test_annotated_with_other_metadata_holding_a_prototype_is_built():
    # given
    class Options(Prototype):
        verbose: bool = False

    class Settings(Prototype):
        options: Annotated[Options, "other metadata"] = field(default_factory=Options)

    # then
    assert (
        smartconfig.prototypes.schema_of(Settings)["optional_keys"]["options"][
            "default"
        ]
        == {}
    )
    assert instantiate(Settings, {"options": {"verbose": True}}) == Settings(
        options=Options(verbose=True)
    )
