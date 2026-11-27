"""Tests for schema_of(): the schema a Prototype's type hints describe."""

import dataclasses
import datetime
from dataclasses import field
from typing import Annotated, Any, ClassVar, Optional

import pytest

import smartconfig
from smartconfig import Prototype
from smartconfig.prototypes import schema_of
from smartconfig.types import Configuration, KeyPath, Schema, Template


# simple types =========================================================================


def test_simple_types():
    # given
    class Simple(Prototype):
        s: str
        i: int
        f: float
        b: bool
        d: datetime.date
        dt: datetime.datetime
        a: Any

    # then
    assert schema_of(Simple) == {
        "type": "dict",
        "required_keys": {
            "s": {"type": "string"},
            "i": {"type": "integer"},
            "f": {"type": "float"},
            "b": {"type": "boolean"},
            "d": {"type": "date"},
            "dt": {"type": "datetime"},
            "a": {"type": "any"},
        },
    }


def test_class_without_fields():
    # given
    class Empty(Prototype):
        pass

    # then
    assert schema_of(Empty) == {"type": "dict"}


# nullable =============================================================================


def test_union_with_none_is_nullable():
    # given
    class Nullable(Prototype):
        x: int | None

    # then
    assert schema_of(Nullable) == {
        "type": "dict",
        "required_keys": {"x": {"type": "integer", "nullable": True}},
    }


def test_optional_is_nullable():
    # given
    class Nullable(Prototype):
        x: Optional[int]  # noqa: UP045 (testing the older spelling)

    # then
    assert schema_of(Nullable)["required_keys"]["x"] == {
        "type": "integer",
        "nullable": True,
    }


def test_none_first_in_union_is_nullable():
    # given
    class Nullable(Prototype):
        x: None | str

    # then
    assert schema_of(Nullable)["required_keys"]["x"] == {
        "type": "string",
        "nullable": True,
    }


def test_any_or_none_is_nullable_any():
    # given
    class Nullable(Prototype):
        x: Any | None

    # then
    assert schema_of(Nullable)["required_keys"]["x"] == {
        "type": "any",
        "nullable": True,
    }


# defaults =============================================================================


def test_field_with_default_is_optional_with_that_default():
    # given
    class WithDefault(Prototype):
        x: int = 3

    # then
    assert schema_of(WithDefault) == {
        "type": "dict",
        "optional_keys": {"x": {"type": "integer", "default": 3}},
    }


def test_nullable_field_with_default_none():
    # given
    class WithDefault(Prototype):
        x: str | None = None

    # then
    assert schema_of(WithDefault)["optional_keys"]["x"] == {
        "type": "string",
        "nullable": True,
        "default": None,
    }


def test_nullable_field_without_default_is_required():
    # being nullable doesn't make a field optional: only a default does
    class Nullable(Prototype):
        x: str | None

    # then
    assert "x" in schema_of(Nullable)["required_keys"]


def test_default_factory_gives_the_factorys_value_as_default():
    # given
    class WithFactory(Prototype):
        xs: list[int] = field(default_factory=lambda: [1, 2])

    # then
    assert schema_of(WithFactory)["optional_keys"]["xs"] == {
        "type": "list",
        "element_schema": {"type": "integer"},
        "default": [1, 2],
    }


def test_date_default():
    # given
    class WithDate(Prototype):
        start: datetime.date = datetime.date(2026, 1, 1)

    # then
    assert schema_of(WithDate)["optional_keys"]["start"] == {
        "type": "date",
        "default": datetime.date(2026, 1, 1),
    }


def test_field_with_default_given_by_field():
    # given
    class WithDefault(Prototype):
        x: int = field(default=4)

    # then
    assert schema_of(WithDefault)["optional_keys"]["x"] == {
        "type": "integer",
        "default": 4,
    }


# containers ===========================================================================


def test_list():
    # given
    class WithList(Prototype):
        xs: list[str]

    # then
    assert schema_of(WithList)["required_keys"]["xs"] == {
        "type": "list",
        "element_schema": {"type": "string"},
    }


def test_list_of_nullable():
    # given
    class WithList(Prototype):
        xs: list[int | None]

    # then
    assert schema_of(WithList)["required_keys"]["xs"] == {
        "type": "list",
        "element_schema": {"type": "integer", "nullable": True},
    }


def test_nullable_list():
    # given
    class WithList(Prototype):
        xs: list[int] | None

    # then
    assert schema_of(WithList)["required_keys"]["xs"] == {
        "type": "list",
        "element_schema": {"type": "integer"},
        "nullable": True,
    }


def test_dict_of_str_is_extra_keys():
    # given
    class WithDict(Prototype):
        d: dict[str, int]

    # then
    assert schema_of(WithDict)["required_keys"]["d"] == {
        "type": "dict",
        "extra_keys_schema": {"type": "integer"},
    }


def test_nested_containers():
    # given
    class Nested(Prototype):
        d: dict[str, list[dict[str, float]]]

    # then
    assert schema_of(Nested)["required_keys"]["d"] == {
        "type": "dict",
        "extra_keys_schema": {
            "type": "list",
            "element_schema": {
                "type": "dict",
                "extra_keys_schema": {"type": "float"},
            },
        },
    }


# nested prototypes ====================================================================


class Address(Prototype):
    street: str
    city: str = "San Diego"


def test_nested_prototype():
    # given
    class Person(Prototype):
        address: Address

    # then
    assert schema_of(Person)["required_keys"]["address"] == schema_of(Address)


def test_list_of_prototypes():
    # given
    class People(Prototype):
        addresses: list[Address]

    # then
    assert schema_of(People)["required_keys"]["addresses"] == {
        "type": "list",
        "element_schema": schema_of(Address),
    }


def test_nullable_nested_prototype_with_default_none():
    # given
    class Person(Prototype):
        address: Address | None = None

    # then
    assert schema_of(Person)["optional_keys"]["address"] == {
        **schema_of(Address),
        "nullable": True,
        "default": None,
    }


def test_nested_prototype_with_its_class_as_default_factory_defaults_to_empty():
    # given: default_factory=Cls means "all of Cls's defaults", which is {}
    class Options(Prototype):
        verbose: bool = False

    class Settings(Prototype):
        options: Options = field(default_factory=Options)

    # then
    assert schema_of(Settings)["optional_keys"]["options"] == {
        **schema_of(Options),
        "default": {},
    }


def test_inherited_fields():
    # given
    class Base(Prototype):
        x: int

    class Derived(Base):
        y: str = "y"

    # then
    assert schema_of(Derived) == {
        "type": "dict",
        "required_keys": {"x": {"type": "integer"}},
        "optional_keys": {"y": {"type": "string", "default": "y"}},
    }


def test_schema_of_returns_a_copy():
    # given
    class Simple(Prototype):
        x: int

    # when
    schema_of(Simple)["required_keys"]["x"]["type"] = "string"

    # then
    assert schema_of(Simple)["required_keys"]["x"] == {"type": "integer"}


def test_class_variables_and_methods_are_not_fields():
    # given
    class WithClassVar(Prototype):
        x: int
        kind: ClassVar[str] = "thing"

        def double(self) -> int:
            return 2 * self.x

    # then
    assert schema_of(WithClassVar) == {
        "type": "dict",
        "required_keys": {"x": {"type": "integer"}},
    }


# the escape hatch: smartconfig.prototypes.schema() ===============================================


CALENDAR_SCHEMA: Schema = {
    "type": "dict",
    "optional_keys": {"color": {"type": "string"}},
    "nullable": True,
}


def test_annotated_schema_is_used_as_given():
    # given
    class WithSchema(Prototype):
        calendar: Annotated[
            dict[str, Any] | None, smartconfig.prototypes.schema(CALENDAR_SCHEMA)
        ]

    # then
    assert schema_of(WithSchema)["required_keys"]["calendar"] == CALENDAR_SCHEMA


def test_annotated_schema_gets_the_fields_default():
    # given
    class WithSchema(Prototype):
        calendar: Annotated[
            dict[str, Any] | None, smartconfig.prototypes.schema(CALENDAR_SCHEMA)
        ] = None

    # then
    assert schema_of(WithSchema)["optional_keys"]["calendar"] == {
        **CALENDAR_SCHEMA,
        "default": None,
    }


def test_annotated_schema_with_the_same_default_as_the_field():
    # given
    class WithSchema(Prototype):
        x: Annotated[
            int, smartconfig.prototypes.schema({"type": "integer", "default": 3})
        ] = 3

    # then
    assert schema_of(WithSchema)["optional_keys"]["x"] == {
        "type": "integer",
        "default": 3,
    }


def test_annotated_schema_with_its_own_default_makes_the_field_optional():
    # given: a template field's default is the template as written, which is not
    # a value of the field's type, so it can be given only in the schema
    template_schema: Schema = {
        "type": "template",
        "schema": {"type": "list", "element_schema": {"type": "string"}},
        "parameters": [],
        "default": [],
    }

    class WithTemplate(Prototype):
        items: Annotated[Template, smartconfig.prototypes.schema(template_schema)]

    # then
    assert schema_of(WithTemplate)["optional_keys"]["items"] == template_schema


def test_annotated_dynamic_schema_is_used_as_given():
    # given
    def dynamic(cfg: Configuration, keypath: KeyPath) -> Schema:
        return {"type": "string"}

    class WithDynamic(Prototype):
        x: Annotated[Any, smartconfig.prototypes.schema(dynamic)]

    # then
    assert schema_of(WithDynamic)["required_keys"]["x"] is dynamic


def test_annotated_dynamic_schema_with_default_is_optional():
    # given
    def dynamic(cfg: Configuration, keypath: KeyPath) -> Schema:
        return {"type": "string", "default": "x"}

    class WithDynamic(Prototype):
        x: Annotated[str, smartconfig.prototypes.schema(dynamic)] = "x"

    # then
    assert schema_of(WithDynamic)["optional_keys"]["x"] is dynamic


def test_annotated_without_smartconfig_metadata_is_inferred_from_the_type():
    # given
    class WithOtherMetadata(Prototype):
        x: Annotated[int, "some other library's metadata"]

    # then
    assert schema_of(WithOtherMetadata)["required_keys"]["x"] == {"type": "integer"}


def test_annotated_inside_a_container():
    # given
    class Inside(Prototype):
        xs: list[Annotated[Any, smartconfig.prototypes.schema({"type": "string"})]]

    # then
    assert schema_of(Inside)["required_keys"]["xs"] == {
        "type": "list",
        "element_schema": {"type": "string"},
    }


def test_annotated_or_none_is_the_same_as_annotated_with_none_inside():
    # given
    nullable: Schema = {"type": "string", "nullable": True}

    class Outside(Prototype):
        x: Annotated[str, smartconfig.prototypes.schema(nullable)] | None

    # then
    assert schema_of(Outside)["required_keys"]["x"] == nullable


# the escape hatch: smartconfig.prototypes.template() =============================================


def test_template_field():
    # given
    class WithTemplate(Prototype):
        title: Annotated[
            Template,
            smartconfig.prototypes.template(
                {"type": "string"}, parameters=["publication"]
            ),
        ]

    # then
    assert schema_of(WithTemplate)["required_keys"]["title"] == {
        "type": "template",
        "schema": {"type": "string"},
        "parameters": ["publication"],
    }


def test_template_field_without_parameters():
    # given
    class WithTemplate(Prototype):
        title: Annotated[Template, smartconfig.prototypes.template({"type": "string"})]

    # then
    assert schema_of(WithTemplate)["required_keys"]["title"] == {
        "type": "template",
        "schema": {"type": "string"},
        "parameters": [],
    }


def test_template_field_parameters_given_as_a_tuple_become_a_list():
    # given
    class WithTemplate(Prototype):
        title: Annotated[
            Template,
            smartconfig.prototypes.template({"type": "string"}, parameters=("a", "b")),
        ]

    # then
    assert schema_of(WithTemplate)["required_keys"]["title"]["parameters"] == [
        "a",
        "b",
    ]


def test_nullable_template_field_from_the_type():
    # given
    class WithTemplate(Prototype):
        label: Annotated[
            Template | None, smartconfig.prototypes.template({"type": "string"})
        ]

    # then
    assert schema_of(WithTemplate)["required_keys"]["label"] == {
        "type": "template",
        "schema": {"type": "string"},
        "parameters": [],
        "nullable": True,
    }


def test_template_field_with_a_default():
    # given
    class WithTemplate(Prototype):
        items: Annotated[
            Template,
            smartconfig.prototypes.template(
                {"type": "list", "element_schema": {"type": "string"}}, default=[]
            ),
        ]

    # then
    assert schema_of(WithTemplate)["optional_keys"]["items"] == {
        "type": "template",
        "schema": {"type": "list", "element_schema": {"type": "string"}},
        "parameters": [],
        "default": [],
    }


def test_template_field_defaulting_to_none():
    # given
    class WithTemplate(Prototype):
        label: Annotated[
            Template | None, smartconfig.prototypes.template({"type": "string"})
        ] = None

    # then
    assert schema_of(WithTemplate)["optional_keys"]["label"] == {
        "type": "template",
        "schema": {"type": "string"},
        "parameters": [],
        "nullable": True,
        "default": None,
    }


# extra keys ===========================================================================


def test_extra_keys_from_a_type():
    # given
    class Website(Prototype, extra_keys=str):
        title: str

    # then
    assert schema_of(Website) == {
        "type": "dict",
        "required_keys": {"title": {"type": "string"}},
        "extra_keys_schema": {"type": "string"},
    }


def test_extra_keys_from_a_schema():
    # given
    class Website(Prototype, extra_keys=smartconfig.prototypes.schema({"type": "any"})):
        title: str

    # then
    assert schema_of(Website)["extra_keys_schema"] == {"type": "any"}


def test_extra_keys_from_a_prototype():
    # given
    class Book(Prototype, extra_keys=Address):
        pass

    # then
    assert schema_of(Book) == {"type": "dict", "extra_keys_schema": schema_of(Address)}


def test_extra_keys_are_inherited():
    # given
    class Base(Prototype, extra_keys=int):
        x: int

    class Derived(Base):
        y: int

    # then
    assert schema_of(Derived) == {
        "type": "dict",
        "required_keys": {"x": {"type": "integer"}, "y": {"type": "integer"}},
        "extra_keys_schema": {"type": "integer"},
    }


def test_extra_keys_attribute_is_a_dataclass_field_but_not_in_the_schema():
    # given
    class Website(Prototype, extra_keys=str):
        title: str

    # then
    names = [f.name for f in dataclasses.fields(Website)]
    assert names == ["title", "extra_keys"]
    assert "extra_keys" not in schema_of(Website).get("required_keys", {})
    assert "optional_keys" not in schema_of(Website)


# errors ===============================================================================


def test_schema_of_a_non_prototype_raises():
    with pytest.raises(TypeError):
        schema_of(dict)  # type: ignore[arg-type]


def test_schema_of_prototype_itself_raises():
    with pytest.raises(TypeError):
        schema_of(Prototype)
