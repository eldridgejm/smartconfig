"""Static typing checks: mypy (run by ``make typecheck``) checks the assert_type
calls below, which do nothing at run time.

A field typed ``Annotated[T, ...]`` is seen as a ``T``, resolve() with a
Prototype class returns an instance of it, and the dataclass ``__init__`` is
known to type checkers.

"""

import datetime
from dataclasses import field
from typing import Annotated, Any, assert_type

import smartconfig
from smartconfig import Prototype
from smartconfig.types import Template


class Course(Prototype):
    name: str
    start: datetime.date
    url: str | None = None
    instructors: list[str] = field(default_factory=list)


class Config(Prototype, extra_keys=str):
    course: Course
    calendar: Annotated[
        dict[str, Any] | None, smartconfig.schema({"type": "any", "default": None})
    ]
    title: Annotated[Template, smartconfig.template({"type": "string"})]


CFG = {
    "course": {"name": "DSC 40B", "start": "2026-09-24"},
    "title": {"__template__": "${ x }"},
    "motto": "hi",
}


def test_resolve_returns_the_prototype_type():
    # when
    config = smartconfig.resolve(CFG, Config)

    # then
    assert_type(config, Config)
    assert_type(config.course, Course)
    assert_type(config.course.start, datetime.date)
    assert_type(config.course.url, str | None)
    assert_type(config.course.instructors, list[str])
    assert_type(config.calendar, dict[str, Any] | None)
    assert_type(config.title, Template)
    assert_type(config.extra_keys, dict[str, Any])
    assert config.extra_keys == {"motto": "hi"}


def test_init_is_typed():
    # when
    course = Course(name="DSC 40B", start=datetime.date(2026, 9, 24))

    # then
    assert_type(course, Course)
    assert course.url is None


def test_instantiate_returns_the_prototype_type():
    # when
    course = smartconfig.instantiate(
        Course, {"name": "n", "start": datetime.date(2026, 1, 1)}
    )

    # then
    assert_type(course, Course)


def test_resolve_with_a_schema_still_returns_a_dict():
    # when
    result = smartconfig.resolve({"x": 1}, {"type": "any"})

    # then
    assert_type(result, dict)
