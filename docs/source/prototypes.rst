.. _prototypes:

Prototypes
==========

A **prototype** describes a configuration as a Python class, instead of a
schema dictionary. Subclass :class:`smartconfig.Prototype` and give it fields
with type hints, as you would a dataclass; pass the class to
:func:`smartconfig.resolve` in place of a schema, and the result is an instance
of the class rather than a dictionary. Type checkers such as mypy know the
types of its attributes.

.. testsetup::

    import datetime
    import smartconfig
    from dataclasses import field
    from pprint import pprint as print
    from typing import Annotated, Any
    from smartconfig import Prototype
    from smartconfig.types import Template

.. testcode::

    class Course(Prototype):
        name: str
        start: datetime.date
        url: str | None = None
        instructors: list[str] = field(default_factory=list)

    config = {"name": "DSC 40B", "start": "2026-09-24", "instructors": ["Justin"]}
    print(smartconfig.resolve(config, Course))

.. testoutput::

    Course(name='DSC 40B',
           start=datetime.date(2026, 9, 24),
           url=None,
           instructors=['Justin'])

A prototype is equivalent to a schema dictionary, its **schema**, which
:func:`smartconfig.prototypes.schema_of` gives:

.. testcode::

    print(smartconfig.prototypes.schema_of(Course))

.. testoutput::

    {'optional_keys': {'instructors': {'default': [],
                                       'element_schema': {'type': 'string'},
                                       'type': 'list'},
                       'url': {'default': None,
                               'nullable': True,
                               'type': 'string'}},
     'required_keys': {'name': {'type': 'string'}, 'start': {'type': 'date'}},
     'type': 'dict'}

Resolving against a prototype is resolving against its schema: every other
feature of :func:`smartconfig.resolve` (interpolation, functions, global
variables) works the same, and an error reports the same keypath and reason it
would for the schema dictionary.

Prototypes are dataclasses
--------------------------

Each subclass of :class:`smartconfig.Prototype` *is* a standard
:mod:`dataclasses` dataclass. Its ``__init__``, ``__eq__`` and ``__repr__``
come from :mod:`dataclasses`, :func:`dataclasses.field` works as usual (use
``default_factory`` for a list or dict default, so that instances don't share
one), and :func:`dataclasses.fields` lists its fields. Its fields are
keyword-only, so a field without a default may follow one with a default.

Fields
------

A field's schema is inferred from its type hint:

=================================  ===============================================
Type hint                          Schema
=================================  ===============================================
``str``                            ``{"type": "string"}``
``int``                            ``{"type": "integer"}``
``float``                          ``{"type": "float"}``
``bool``                           ``{"type": "boolean"}``
``datetime.date``                  ``{"type": "date"}``
``datetime.datetime``              ``{"type": "datetime"}``
``typing.Any``                     ``{"type": "any"}``
``T | None`` (or ``Optional[T]``)  ``T``'s schema, with ``"nullable": True``
``list[T]``                        ``{"type": "list", "element_schema": <T's>}``
``dict[str, T]``                   ``{"type": "dict", "extra_keys_schema": <T's>}``
a Prototype subclass               its schema
=================================  ===============================================

Any other type hint (a union of two types, ``set[int]``, a plain ``list``, a
class that isn't a Prototype, ...) is a ``TypeError`` when the class is
defined, naming the class and field. Such a field can still be described, with
an explicit schema (see `Explicit schemas`_).

A field is **optional** exactly when it has a default (``= value``, or
``field(default_factory=...)``), and its schema then gets that default. A field
is **nullable** exactly when its type includes ``None``. The two are
independent: ``x: str | None`` is required but may be null, and ``x: str =
"a"`` is optional but may not be null.

A field holding a prototype becomes an instance of it, as do the prototypes in
a ``list[...]``, a ``dict[str, ...]`` or ``... | None``. Such a field may
default to ``None`` (if it is nullable), or to ``field(default_factory=C)``,
where ``C`` is its class: the schema default ``{}``, which gives each of
``C``'s fields its own default.

.. testcode::

    class Build(Prototype):
        jobs: int | None = None

    class Person(Prototype):
        name: str
        email: str | None = None

    class Project(Prototype):
        people: list[Person]
        build: Build = field(default_factory=Build)

    print(smartconfig.resolve({"people": [{"name": "Ada"}]}, Project))

.. testoutput::

    Project(people=[Person(name='Ada', email=None)], build=Build(jobs=None))

Explicit schemas
----------------

When a field's schema can't be inferred from its type, give it one with
``typing.Annotated`` and :func:`smartconfig.prototypes.schema`. The schema is used as
given, so anything a schema dictionary can say, a prototype can say. This is
the way to describe a complex or deeply nested value, or one whose schema is
:ref:`dynamic <dynamic_schemas_example>`:

.. testcode::

    CALENDAR_SCHEMA = {
        "type": "dict",
        "extra_keys_schema": {"type": "list", "element_schema": {"type": "date"}},
        "nullable": True,
    }

    class Config(Prototype):
        title: str
        calendar: Annotated[
            dict[str, Any] | None, smartconfig.prototypes.schema(CALENDAR_SCHEMA)
        ] = None

    config = {"title": "DSC 40B", "calendar": {"exams": ["2026-10-20"]}}
    print(smartconfig.resolve(config, Config))

.. testoutput::

    Config(title='DSC 40B', calendar={'exams': [datetime.date(2026, 10, 20)]})

The type inside ``Annotated`` is what type checkers see; the schema is what
`smartconfig` uses. Two things connect them. If the field has a default and the
schema doesn't, the field's default is added to the schema (as with
``calendar`` above). And the type's ``None`` must agree with the schema's
``nullable``: a field typed ``str | None`` with a schema that isn't nullable is
a ``TypeError``. A field with an explicit schema keeps its resolved value as
is: here, ``calendar`` is a dict, and it would be one even if its schema were a
prototype's.

A schema that has a default of its own also makes its field optional. This is
how a template field gets a default, since a template's default is the
template as written, which isn't a value of the field's type.

Template fields
~~~~~~~~~~~~~~~

A :ref:`template field <template_fields_example>` resolves to a
:class:`smartconfig.types.Template`. Type it ``Template`` (or ``Template |
None``, to make it nullable) and give it its schema with
:func:`smartconfig.prototypes.template`, which takes the schema of the template's value
and its parameters:

.. testcode::

    class Page(Prototype):
        title: Annotated[
            Template, smartconfig.prototypes.template({"type": "string"}, ["publication"])
        ]

    page = smartconfig.resolve(
        {"title": {"__template__": "Lecture ${ publication.number }"}}, Page
    )
    print(page.title.evaluate({"publication": {"number": 4}}))

.. testoutput::

    'Lecture 4'

Extra keys
----------

By default, a key that isn't a field is an error, as for a schema dictionary
without ``extra_keys_schema``. The class option ``extra_keys`` allows such keys
and gives their schema, as a type hint (``extra_keys=str``) or an explicit
schema (``extra_keys=smartconfig.prototypes.schema({...})``). The extra keys are kept,
resolved, in the instance's ``extra_keys`` attribute, a dict:

.. testcode::

    class Website(Prototype, extra_keys=str):
        title: str

    website = smartconfig.resolve(
        {"title": "DSC 40B", "motto": "Learn", "room": "CENTR 115"}, Website
    )
    print(website.extra_keys)

.. testoutput::

    {'motto': 'Learn', 'room': 'CENTR 115'}

``extra_keys`` is a dataclass field of its own, compared by ``__eq__`` and
shown by ``__repr__``, and so the name is reserved: no prototype may have a
field called ``extra_keys``. A subclass inherits its base's extra keys.
(Type checkers know the attribute, but not that ``__init__`` takes it.)

Prototypes and schema dictionaries together
-------------------------------------------

:func:`smartconfig.prototypes.schema_of` gives a prototype's schema, to use inside a
schema dictionary, where it resolves to a dict. :func:`smartconfig.prototypes.instantiate`
builds an instance from such a dict, which is what :func:`smartconfig.resolve`
does with a prototype:

.. testcode::

    people_schema = {"type": "list", "element_schema": smartconfig.prototypes.schema_of(Person)}
    resolved = smartconfig.resolve([{"name": "Ada"}], people_schema)
    print([smartconfig.prototypes.instantiate(Person, p) for p in resolved])

.. testoutput::

    [Person(name='Ada', email=None)]
