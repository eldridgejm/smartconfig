"""Acceptance tests: automata's configuration, written as Prototypes.

automata (https://github.com/eldridgejm/automata) describes each section of its
configuration twice, as a dataclass and as a schema dict. The schemas below are
copied from its ``src/automata/config.py``, its default theme's elements and its
schedule element. Each Prototype must generate exactly the same schema.

"""

import datetime
from dataclasses import field
from typing import Annotated, Any

import smartconfig
from smartconfig import Prototype
from smartconfig.prototypes import schema_of
from smartconfig.types import ConfigurationDict, ConfigurationList, Schema, Template

# automata/config.py ===================================================================

WEBSITE_SCHEMA: Schema = {
    "type": "dict",
    "required_keys": {
        "theme": {"type": "any"},
        "content_directory": {"type": "string"},
        "build_directory": {"type": "string"},
    },
    "optional_keys": {
        "materials_directory_name": {"type": "string", "default": "materials"},
        "clean_build_directory": {"type": "boolean", "default": True},
        "no_render_suffix": {
            "type": "string",
            "nullable": True,
            "default": ".no_render",
        },
        "base_path": {"type": "string", "default": "/"},
        "elements": {
            "type": "dict",
            "extra_keys_schema": {"type": "any"},
            "default": {},
        },
    },
}

COURSE_SCHEMA: Schema = {
    "type": "dict",
    "required_keys": {
        "name": {"type": "string"},
        "title": {"type": "string"},
        "term": {"type": "string"},
        "first_week_start": {"type": "date"},
        "timezone": {"type": "string"},
    },
    "optional_keys": {
        "first_week_number": {"type": "integer", "default": 1},
        "instructors": {
            "type": "list",
            "element_schema": {"type": "string"},
            "default": [],
        },
        "url": {"type": "string", "nullable": True, "default": None},
    },
}

BUILD_SCHEMA: Schema = {
    "type": "dict",
    "optional_keys": {
        "jobs": {"type": "integer", "nullable": True, "default": None},
    },
    "default": {},
}


def _any_dict() -> Schema:
    return {"type": "dict", "extra_keys_schema": {"type": "any"}, "default": {}}


_CALENDAR_LABEL_SCHEMA: Schema = {
    "type": "template",
    "schema": {"type": "string"},
    "parameters": ["publication", "vars", "course"],
    "nullable": True,
}

_CALENDAR_COLOR_SCHEMA: Schema = {
    "type": "string",
    "nullable": True,
    "default": None,
}

CALENDAR_SCHEMA: Schema = {
    "type": "dict",
    "optional_keys": {
        "collections": {
            "type": "dict",
            "extra_keys_schema": {
                "type": "dict",
                "required_keys": {
                    "dates": {
                        "type": "dict",
                        "extra_keys_schema": _CALENDAR_LABEL_SCHEMA,
                    },
                },
                "optional_keys": {"color": _CALENDAR_COLOR_SCHEMA},
            },
            "default": {},
        },
        "events": {
            "type": "dict",
            "extra_keys_schema": {
                "type": "dict",
                "required_keys": {
                    "dates": {
                        "type": "list",
                        "element_schema": {
                            "type": "dict",
                            "required_keys": {
                                "label": {"type": "string"},
                                "date": {"type": "any"},
                            },
                            "optional_keys": {
                                "end": {
                                    "type": "any",
                                    "nullable": True,
                                    "default": None,
                                }
                            },
                        },
                    },
                },
                "optional_keys": {"color": _CALENDAR_COLOR_SCHEMA},
            },
            "default": {},
        },
    },
    "nullable": True,
    "default": None,
}

CONFIG_SCHEMA: Schema = {
    "type": "dict",
    "required_keys": {
        "website": WEBSITE_SCHEMA,
        "course": COURSE_SCHEMA,
    },
    "optional_keys": {
        "vars": _any_dict(),
        "extensions": {
            "type": "list",
            "element_schema": {"type": "any"},
            "default": [],
        },
        "materials": _any_dict(),
        "publish": _any_dict(),
        "calendar": CALENDAR_SCHEMA,
        "build": BUILD_SCHEMA,
        "ignore": {
            "type": "list",
            "element_schema": {"type": "string"},
            "default": [],
        },
    },
}


class WebsiteConfig(Prototype):
    theme: Any
    content_directory: str
    build_directory: str
    materials_directory_name: str = "materials"
    clean_build_directory: bool = True
    no_render_suffix: str | None = ".no_render"
    base_path: str = "/"
    elements: dict[str, Any] = field(default_factory=dict)


class CourseConfig(Prototype):
    name: str
    title: str
    term: str
    first_week_start: datetime.date
    timezone: str
    first_week_number: int = 1
    instructors: list[str] = field(default_factory=list)
    url: str | None = None


class BuildConfig(Prototype):
    jobs: int | None = None


class Config(Prototype):
    website: WebsiteConfig
    course: CourseConfig
    vars: dict[str, Any] = field(default_factory=dict)
    extensions: list[Any] = field(default_factory=list)
    materials: dict[str, Any] = field(default_factory=dict)
    publish: dict[str, Any] = field(default_factory=dict)
    calendar: Annotated[
        dict[str, Any] | None, smartconfig.prototypes.schema(CALENDAR_SCHEMA)
    ] = None
    build: BuildConfig = field(default_factory=BuildConfig)
    ignore: list[str] = field(default_factory=list)


def test_website_config_schema_equals_automatas():
    assert schema_of(WebsiteConfig) == WEBSITE_SCHEMA


def test_course_config_schema_equals_automatas():
    assert schema_of(CourseConfig) == COURSE_SCHEMA


def test_build_config_schema_equals_automatas_as_a_field():
    # BUILD_SCHEMA's top-level default belongs to the field that holds it, so it
    # is in Config's schema, not in BuildConfig's
    build_without_default = {k: v for k, v in BUILD_SCHEMA.items() if k != "default"}
    assert schema_of(BuildConfig) == build_without_default
    assert schema_of(Config)["optional_keys"]["build"] == BUILD_SCHEMA


def test_config_schema_equals_automatas():
    assert schema_of(Config) == CONFIG_SCHEMA


def test_config_resolves_to_nested_instances():
    # given
    cfg: ConfigurationDict = {
        "website": {
            "theme": "default",
            "content_directory": "website",
            "build_directory": "_build",
        },
        "course": {
            "name": "DSC 40B",
            "title": "Theoretical Foundations II",
            "term": "Fall 2026",
            "first_week_start": "2026-09-24",
            "timezone": "America/Los_Angeles",
        },
        "calendar": {
            "collections": {
                "homeworks": {"dates": {"due": {"__template__": "Due: ${ course }"}}}
            }
        },
    }

    # when
    config = smartconfig.resolve(cfg, Config)

    # then
    assert isinstance(config.website, WebsiteConfig)
    assert config.website.no_render_suffix == ".no_render"
    assert config.course.first_week_start == datetime.date(2026, 9, 24)
    assert config.build == BuildConfig(jobs=None)
    assert config.vars == {}
    # the calendar has an explicit schema, so it is kept as resolved: a dict
    # holding a Template
    assert config.calendar is not None
    label = config.calendar["collections"]["homeworks"]["dates"]["due"]
    assert isinstance(label, Template)
    assert label.evaluate({"publication": {}, "vars": {}, "course": "x"}) == "Due: x"


def test_config_without_calendar_has_none():
    # given
    cfg: ConfigurationDict = {
        "website": {"theme": "t", "content_directory": "c", "build_directory": "b"},
        "course": {
            "name": "n",
            "title": "t",
            "term": "t",
            "first_week_start": "2026-01-01",
            "timezone": "UTC",
        },
    }

    # when
    config = smartconfig.resolve(cfg, Config)

    # then
    assert config.calendar is None


# default theme elements ===============================================================

BUTTON_SCHEMA: Schema = {
    "type": "dict",
    "required_keys": {"label": {"type": "string"}, "url": {"type": "string"}},
}

DATE_PILL_SCHEMA: Schema = {
    "type": "dict",
    "required_keys": {
        "date": {"type": "date"},
        "text_before": {"type": "string"},
        "text_after": {"type": "string"},
    },
    "optional_keys": {"text_class": {"type": "string", "default": "text-sm"}},
}

PERSON_SCHEMA: Schema = {
    "type": "dict",
    "required_keys": {"name": {"type": "string"}},
    "optional_keys": {
        "website": {"type": "string", "nullable": True, "default": None},
        "role": {"type": "string", "nullable": True, "default": None},
        "photo": {"type": "string", "nullable": True, "default": None},
        "about": {"type": "string", "nullable": True, "default": None},
    },
}

GROUP_SCHEMA: Schema = {
    "type": "dict",
    "required_keys": {
        "group": {"type": "string"},
        "members": {"type": "list", "element_schema": PERSON_SCHEMA},
    },
}


class Button(Prototype):
    label: str
    url: str


class DatePill(Prototype):
    date: datetime.date
    text_before: str
    text_after: str
    text_class: str = "text-sm"


class Person(Prototype):
    name: str
    website: str | None = None
    role: str | None = None
    photo: str | None = None
    about: str | None = None


class Group(Prototype):
    group: str
    members: list[Person]


def test_button_schema_equals_automatas():
    assert schema_of(Button) == BUTTON_SCHEMA


def test_date_pill_schema_equals_automatas():
    assert schema_of(DatePill) == DATE_PILL_SCHEMA


def test_person_and_group_schemas_equal_automatas():
    assert schema_of(Person) == PERSON_SCHEMA
    assert schema_of(Group) == GROUP_SCHEMA


def test_people_list_resolves_to_groups_of_people():
    # given: the people element's config is a list of groups, which is a list
    # schema, not a dict, so it is resolved against the element schema
    # {"type": "list", "element_schema": schema_of(Group)} and built one group at
    # a time
    cfg: ConfigurationList = [{"group": "Instructors", "members": [{"name": "Justin"}]}]
    people_schema: Schema = {"type": "list", "element_schema": schema_of(Group)}

    # when
    resolved = smartconfig.resolve(cfg, people_schema)
    groups = [smartconfig.prototypes.instantiate(Group, group) for group in resolved]

    # then
    assert groups == [Group(group="Instructors", members=[Person(name="Justin")])]


# schedule element =====================================================================

ANNOUNCEMENT_SCHEMA: Schema = {
    "type": "dict",
    "required_keys": {
        "week": {"type": "integer", "nullable": True},
        "content": {"type": "string"},
    },
    "optional_keys": {
        "urgent": {"type": "boolean", "default": False},
        "start_displaying_on": {"type": "date", "nullable": True, "default": None},
    },
}

EVENT_SCHEMA: Schema = {
    "type": "dict",
    "required_keys": {"name": {"type": "string"}, "date": {"type": "date"}},
}


class Announcement(Prototype):
    week: int | None
    content: str
    urgent: bool = False
    start_displaying_on: datetime.date | None = None


class Event(Prototype):
    name: str
    date: datetime.date


def test_announcement_schema_equals_automatas():
    assert schema_of(Announcement) == ANNOUNCEMENT_SCHEMA


def test_event_schema_equals_automatas():
    assert schema_of(Event) == EVENT_SCHEMA


# the schedule's activity collections use template fields, through the escape hatch

RENDER_CONTEXT_NAMES = ("vars", "course")

ACTIVITY_SCHEMA: Schema = {
    "type": "dict",
    "required_keys": {"title": {"type": "string"}},
}

ACTIVITY_COLLECTION_CONFIG_SCHEMA: Schema = {
    "type": "dict",
    "required_keys": {
        "collection": {"type": "string"},
        "for_each_publication": {
            "type": "template",
            "schema": ACTIVITY_SCHEMA,
            "parameters": ["publication", *RENDER_CONTEXT_NAMES],
        },
    },
}


class ActivityCollectionConfig(Prototype):
    collection: str
    for_each_publication: Annotated[
        Template,
        smartconfig.prototypes.template(
            ACTIVITY_SCHEMA, parameters=["publication", *RENDER_CONTEXT_NAMES]
        ),
    ]


def test_activity_collection_config_schema_equals_automatas():
    assert schema_of(ActivityCollectionConfig) == ACTIVITY_COLLECTION_CONFIG_SCHEMA


EXTRA_ACTIVITIES_SCHEMA: Schema = {
    "type": "template",
    "schema": {"type": "list", "element_schema": ACTIVITY_SCHEMA},
    "parameters": [*RENDER_CONTEXT_NAMES],
    "default": [],
}


class Schedule(Prototype):
    week_topics: list[str]
    week_order: str = "this_week_first"
    events: list[Event] = field(default_factory=list)
    announcements: list[Announcement] = field(default_factory=list)
    # a template field whose default is the template as written (an empty list)
    extra_primary_activities: Annotated[
        Template, smartconfig.prototypes.schema(EXTRA_ACTIVITIES_SCHEMA)
    ]


def test_schedule_with_a_template_default_matches_automatas_shape():
    # then
    assert schema_of(Schedule) == {
        "type": "dict",
        "required_keys": {
            "week_topics": {"type": "list", "element_schema": {"type": "string"}},
        },
        "optional_keys": {
            "week_order": {"type": "string", "default": "this_week_first"},
            "events": {"type": "list", "element_schema": EVENT_SCHEMA, "default": []},
            "announcements": {
                "type": "list",
                "element_schema": ANNOUNCEMENT_SCHEMA,
                "default": [],
            },
            "extra_primary_activities": EXTRA_ACTIVITIES_SCHEMA,
        },
    }


def test_schedule_resolves_with_template_default():
    # when
    schedule = smartconfig.resolve({"week_topics": ["Intro"]}, Schedule)

    # then
    assert schedule.events == []
    assert isinstance(schedule.extra_primary_activities, Template)
    assert schedule.extra_primary_activities.evaluate({"vars": {}, "course": {}}) == []
