.. _schemas:

Schemas and Prototypes
======================

In order for `smartconfig` to properly resolve a configuration, it first needs
to know the expected structure and types of the configuration. You can specify
this structure in two ways: **schemas** (standard Python dictionaries)
or **prototypes** (Python classes with type hints). Prototypes are usually more
convenient to write and have the benefit of returning instances of your class
(helpful for type-checking), while schemas are sometimes more convenient for
specifying deeply-nested structures and remain the most expressive option (for
example, they support ``extra_keys_schema``, :ref:`dynamic schemas <dynamic_schemas_example>`, and other
fine-grained controls that prototypes currently do not).

.. testsetup::

    import smartconfig
    from pprint import pprint as print
    from typing import Any
    from smartconfig import Prototype, NotRequired

Prototypes
----------

Prototypes let you describe the structure of a configuration using Python class
syntax. Prototypes are quick to write, but they currently cannot express every
constraint that schemas can (for example, they do not allow
``extra_keys_schema``). They can also be somewhat awkward to use when
describing deeply-nested structures, and in those cases schemas may be
preferable.

Below, we'll demonstrate the basics of Prototypes using several simple
examples. For more details on how to define prototypes and the features they
support, see the :ref:`prototypes` section of the documentation.

Examples
~~~~~~~~

Example 1: A simple prototype
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The prototype below describes a student with three fields: ``name``, ``age``,
and ``enrolled_in``. The type hints tell `smartconfig` what type each field
should have, and they are used by ``resolve()`` to do type conversion and
validation. Note that the result of resolution is not a dictionary, but an
instance of the ``Student`` class.

Input:

.. testcode::

    class Student(Prototype):
        name: str
        age: int
        enrolled_in: list[str]

    config = {
        "name": "Barack Obama",
        "age": 63,
        "enrolled_in": ["Math 100", "History 101", "Physics 200"],
    }
    print(smartconfig.resolve(config, Student))

Output:

.. testoutput::

    Student(name='Barack Obama', age=63, enrolled_in=['Math 100', 'History 101', 'Physics 200'])

Example 2: Nullable fields
^^^^^^^^^^^^^^^^^^^^^^^^^^

To allow a field to be ``None``, use a union with ``None`` (e.g.,
``str | None``).

Input:

.. testcode::

    class Student(Prototype):
        name: str
        nickname: str | None

    print(
        smartconfig.resolve(
            {"name": "Barack Obama", "nickname": None},
            Student,
        )
    )

Output:

.. testoutput::

    Student(name='Barack Obama', nickname=None)

Example 3: Optional fields and defaults
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To mark a field as not required, use ``smartconfig.NotRequired`` as its type.
Fields marked with ``NotRequired`` can be omitted from the configuration
entirely.

You can also provide a default value for a field by assigning it within the
class body, as with ``standing`` in the example below. This value will be used
if the field is missing from the configuration. It is not necessary to use
``NotRequired`` in this case, as the presence of a default value already
indicates that the field is optional.

Input:

.. testcode::

    from smartconfig import NotRequired

    class Student(Prototype):
        name: str
        email: NotRequired[str]
        standing: str = "undergraduate"

    print(
        smartconfig.resolve(
            {"name": "Barack Obama"},
            Student,
        )
    )

Output:

.. testoutput::

    Student(name='Barack Obama', standing='undergraduate')

Notice that the ``email`` field is simply omitted from the resulting instance,
while the ``standing`` field is present with its default value of
``'undergraduate'``.

Example 4: Nested prototypes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Prototypes can be nested to any depth. In the example below, a ``Roster``
prototype contains a list of ``Student`` prototypes. When resolving, `smartconfig`
will recursively resolve each nested prototype into an instance of that prototype.

Input:

.. testcode::

    class Student(Prototype):
        name: str
        age: int

    class Roster(Prototype):
        students: list[Student]

    print(
        smartconfig.resolve(
            {
                "students": [
                    {"name": "Barack Obama", "age": 63},
                    {"name": "Kamala Harris", "age": 60},
                ]
            },
            Roster,
        )
    )

Output:

.. testoutput::

    Roster(students=[Student(name='Barack Obama', age=63), Student(name='Kamala Harris', age=60)])

Example 5: Any values
^^^^^^^^^^^^^^^^^^^^^

To allow a field to accept any value, use ``typing.Any`` as its type.

Input:

.. testcode::

    import typing

    class Student(Prototype):
        name: str
        metadata: typing.Any

    print(
        smartconfig.resolve(
            {"name": "Barack Obama", "metadata": {"favorite": "pineapple pizza"}},
            Student,
        )
    )

Output:

.. testoutput::

    Student(name='Barack Obama', metadata={'favorite': 'pineapple pizza'})

Example 6: Extra keys
^^^^^^^^^^^^^^^^^^^^^^

Unlike schemas, prototypes do not currently support extra keys.
An exception will be raised if unknown keys are present in the configuration.

Input:

.. testcode::

    class Person(Prototype):
        name: str

    config = {"name": "Alice", "unknown": "value"}

    try:
        smartconfig.resolve(config, Person)
    except smartconfig.exceptions.ResolutionError as exc:
        print(type(exc).__name__)

Output:

.. testoutput::

    'ResolutionError'

Schemas
-------

The most explicit way to describe the expected structure of a configuration is
via a **schema**. A schema is a dictionary defining the expected structure of a
configuration, including which keys are required or optional, the types of values,
and any default values.
More precisely, a schema dictionary follows the formal grammar below:

.. code:: text

    <SCHEMA> = (
        <DICT_SCHEMA> | <LIST_SCHEMA> | <VALUE_SCHEMA> | <ANY_SCHEMA> | <TEMPLATE_SCHEMA>
    )

    <DICT_SCHEMA> = {
        "type": "dict",
        ["required_keys": {<KEY_NAME>: <SCHEMA>, ...}],
        ["optional_keys": {<KEY_NAME>: (<SCHEMA> | <SCHEMA_WITH_DEFAULT>), ...}],
        ["extra_keys_schema": <SCHEMA>],
        ["nullable": (True | False)],
    }

    <LIST_SCHEMA> = {
        "type": "list",
        "element_schema": <SCHEMA>,
        ["nullable": (True | False)]
    }

    VALUE_SCHEMA = {
        "type": ("string" | "integer" | "float" | "boolean" | "date" | "datetime"),
        ["nullable": (True | False)]
    }

    <ANY_SCHEMA> = {
        "type": "any",
        "nullable": (True | False)
    }

    <TEMPLATE_SCHEMA> = {
        "type": "template",
        "schema": <SCHEMA>,
        "variables": [<NAME>, ...],
        ["nullable": (True | False)]
    }

    <SCHEMA_WITH_DEFAULT> = (
        <DICT_SCHEMA_WITH_DEFAULT>
        | <LIST_SCHEMA_WITH_DEFAULT>
        | <VALUE_SCHEMA_WITH_DEFAULT>
        | <ANY_SCHEMA_WITH_DEFAULT>
        | <TEMPLATE_SCHEMA_WITH_DEFAULT>
    )

The ``DICT_SCHEMA_WITH_DEFAULT``, ``LIST_SCHEMA_WITH_DEFAULT``,
``VALUE_SCHEMA_WITH_DEFAULT``, ``ANY_SCHEMA_WITH_DEFAULT`` and
``TEMPLATE_SCHEMA_WITH_DEFAULT`` grammars are the
same as their non-default counterparts, but with an additional field named
`default` that specifies the default value should that part of the
configuration be missing.

Anywhere a schema is expected, you can also provide a **dynamic schema**.
A dynamic schema is a Python function that takes a configuration and a
keypath as input and returns a schema dictionary. This allows the schema to be
determined at runtime based on the configuration itself. This is particularly
useful for handling polymorphic lists or dictionaries where the schema of an
element depends on its content (e.g., a "type" field).
(See :ref:`dynamic_schemas_example` for an example).

A **template schema** marks a field whose value is evaluated later, possibly
many times: its value is kept as written and resolves to a
:class:`smartconfig.Template`. ``"schema"`` describes the value once it is
evaluated, and ``"variables"`` names what must be given each time (it may be
empty). The inner schema may not have a top-level default; put the default on
the template schema. (See :ref:`template_fields_example`.)

Schemas can be validated using the :func:`smartconfig.validate_schema`
function.

Examples
~~~~~~~~

Example 1: A simple schema
^^^^^^^^^^^^^^^^^^^^^^^^^^

This minimal schema shows required string, integer, and list fields.

Input:

.. testcode::

    config = {
        "name": "Barack Obama",
        "age": 63,
        "enrolled_in": ["Math 100", "History 101", "Physics 200"],
    }
    schema = {
        "type": "dict",
        "required_keys": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
            "enrolled_in": {
                "type": "list",
                "element_schema": {"type": "string"},
            },
        },
    }
    print(smartconfig.resolve(config, schema))

Output:

.. testoutput::

    {'age': 63,
     'enrolled_in': ['Math 100', 'History 101', 'Physics 200'],
     'name': 'Barack Obama'}

Example 2: Allowing extra keys
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

By default, `smartconfig` will raise an error if the configuration contains
keys not specified in the schema. Sometimes, however, it is useful to allow the
user to provide "extra" keys that are not specified in the schema. This is most
often the case when we want to allow the user to define a mapping whose keys
are not known in advance.

Input:

.. testcode::

    config = {
        "name": "Barack Obama",
        "age": 63,
        "enrolled_in": ["Math 100", "History 101"],
        "grades": {"Math 100": "A-", "History 101": "A"},
    }
    schema = {
        "type": "dict",
        "required_keys": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
            "enrolled_in": {
                "type": "list",
                "element_schema": {"type": "string"},
            },
            "grades": {"type": "dict", "extra_keys_schema": {"type": "string"}},
        },
    }
    print(smartconfig.resolve(config, schema))

Output:

.. testoutput::

    {'age': 63,
     'enrolled_in': ['Math 100', 'History 101'],
     'grades': {'History 101': 'A', 'Math 100': 'A-'},
     'name': 'Barack Obama'}

Example 3: Allowing nullable values
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Mark a field as nullable when ``None`` is an allowed value in the configuration.

Input:

.. testcode::

    config = {"name": "Barack Obama", "age": None}
    schema = {
        "type": "dict",
        "required_keys": {
            "name": {"type": "string"},
            "age": {"type": "integer", "nullable": True},
        },
    }
    print(smartconfig.resolve(config, schema))

Output:

.. testoutput::

    {'age': None, 'name': 'Barack Obama'}

Example 4: Optional keys and defaults
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Optional keys can be omitted entirely, and defaults populate missing values.

Input:

.. testcode::

    config = {"name": "Barack Obama", "age": 63, "enrolled_in": []}
    schema = {
        "type": "dict",
        "required_keys": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
            "enrolled_in": {
                "type": "list",
                "element_schema": {"type": "string"},
            },
        },
        "optional_keys": {
            "email": {"type": "string"},
            "standing": {"type": "string", "default": "undergraduate"},
        },
    }
    print(smartconfig.resolve(config, schema))

Output:

.. testoutput::

    {'age': 63,
     'enrolled_in': [],
     'name': 'Barack Obama',
     'standing': 'undergraduate'}

Example 5: Nested containers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Schemas can nest lists of dictionaries to any depth.

Input:

.. testcode::

    config = [
        {"name": "Barack Obama", "age": 63, "enrolled_in": ["History 101"]},
        {"name": "Kamala Harris", "age": 60, "enrolled_in": ["Law 200"]},
    ]
    schema = {
        "type": "list",
        "element_schema": {
            "type": "dict",
            "required_keys": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
                "enrolled_in": {
                    "type": "list",
                    "element_schema": {"type": "string"},
                },
            },
        },
    }
    print(smartconfig.resolve(config, schema))

Output:

.. testoutput::

    [{'age': 63, 'enrolled_in': ['History 101'], 'name': 'Barack Obama'},
     {'age': 60, 'enrolled_in': ['Law 200'], 'name': 'Kamala Harris'}]

Example 6: "Any" schema
^^^^^^^^^^^^^^^^^^^^^^^

Use the ``any`` type when a value should be accepted without type checking.

Input:

.. testcode::

    config = {"name": "Barack Obama", "metadata": {"favorite": "pineapple pizza"}}
    schema = {
        "type": "dict",
        "required_keys": {
            "name": {"type": "string"},
            "metadata": {"type": "any"},
        },
    }
    print(smartconfig.resolve(config, schema))

Output:

.. testoutput::

    {'metadata': {'favorite': 'pineapple pizza'}, 'name': 'Barack Obama'}

.. _dynamic_schemas_example:

Example 7: Dynamic schemas
^^^^^^^^^^^^^^^^^^^^^^^^^^

Dynamic schemas are most useful for validating/resolving the elements of
containers that can contain multiple types of elements. For example, suppose a
list can contain both ``Professor`` and ``Student`` entries, each with
different fields. A dynamic schema can be used to select the appropriate schema
based on a "type" field in each entry.

Input:

.. testcode::

    def person_schema(element, keypath):
        if element.get("type") == "student":
            return {
                "type": "dict",
                "required_keys": {
                    "type": {"type": "string"},
                    "name": {"type": "string"},
                    "major": {"type": "string"},
                },
            }
        elif element.get("type") == "professor":
            return {
                "type": "dict",
                "required_keys": {
                    "type": {"type": "string"},
                    "name": {"type": "string"},
                    "department": {"type": "string"},
                },
                "optional_keys": {
                    "rank": {"type": "string", "default": "assistant professor"},
                },
            }
        else:
            raise smartconfig.exceptions.ResolutionError(
                f"Unknown person type: {element.get('type')}", keypath
            )

    config = [
        {"type": "student", "name": "Alice", "major": "Physics"},
        {"type": "professor", "name": "Bob", "department": "Math"},
    ]

    schema = {
        "type": "list",
        "element_schema": person_schema,
    }

    print(smartconfig.resolve(config, schema))

Output:

.. testoutput::

    [{'major': 'Physics', 'name': 'Alice', 'type': 'student'},
     {'department': 'Math',
      'name': 'Bob',
      'rank': 'assistant professor',
      'type': 'professor'}]


.. _template_fields_example:

Example 8: Template fields
^^^^^^^^^^^^^^^^^^^^^^^^^^

Some values can only be evaluated later, by whoever uses the configuration:
for example, a page that is made once for each homework. A field whose schema
has ``"type": "template"`` holds such a value. Its value is written in a
``__template__`` wrapper, kept as written, and resolves to a
:class:`smartconfig.Template`:

.. testcode::

    schema = {
        "type": "dict",
        "required_keys": {
            "course": {"type": "string"},
            "page": {
                "type": "template",
                "schema": {
                    "type": "dict",
                    "required_keys": {
                        "title": {"type": "string"},
                        "points": {"type": "integer"},
                    },
                },
                "variables": ["publication"],
            },
        },
    }

    config = {
        "course": "DSC 40B",
        "page": {
            "__template__": {
                "title": "${ course }: ${ publication.name }",
                "points": "${ publication.points * 2 }",
            }
        },
    }

    result = smartconfig.resolve(config, schema)
    page = result["page"]
    print(page)
    print(page.source)

Output:

.. testoutput::

    Template(at "page", variables: publication)
    {'points': '${ publication.points * 2 }',
     'title': '${ course }: ${ publication.name }'}

:meth:`Template.resolve <smartconfig.Template.resolve>` evaluates the template:
interpolation, function calls, type conversion and defaults, as
:func:`smartconfig.resolve` does. It takes a mapping of the names the
template's strings may use. Every name in ``variables`` must be given; other
names may be given too. Here, ``course`` is not part of the template, so it is
passed in:

.. testcode::

    print(
        page.resolve(
            {"publication": {"name": "Homework 1", "points": 5}, "course": "DSC 40B"}
        )
    )

Output:

.. testoutput::

    {'points': 10, 'title': 'DSC 40B: Homework 1'}

**What is checked when the configuration is resolved.** The value must be
written with ``__template__`` (or copied with :ref:`__use__ <func-use>`):
otherwise :class:`exceptions.TemplateRequiredError <smartconfig.exceptions.TemplateRequiredError>`
is raised. Its structure is checked against the inner schema: required and
unexpected keys, dicts versus lists, nulls. Nothing in it is evaluated, and
function calls inside it are not checked.

.. testcode::

    bad = {"course": "DSC 40B", "page": {"__template__": {"title": "Homework"}}}

    try:
        smartconfig.resolve(bad, schema)
    except smartconfig.exceptions.ResolutionError as exc:
        print(exc.keypath)
        print(exc.reason)

Output:

.. testoutput::

    ('page', 'points')
    'Dictionary is missing required key "points".'

**What is checked when the template is resolved.** The names its strings use.
A name that is not defined raises
:class:`exceptions.UndefinedNameError <smartconfig.exceptions.UndefinedNameError>`,
which suggests a close name or lists the names that were available:

.. testcode::

    try:
        page.resolve({"publication": {"name": "Homework 1", "points": 5}})
    except smartconfig.exceptions.UndefinedNameError as exc:
        print(exc.keypath)
        print(exc.available)

Output:

.. testoutput::

    ('page', 'title')
    ('title', 'points', 'publication')

**Templates do not nest.** A template's value can't contain a template field:
the template already defers everything in it. Doing so raises
:class:`exceptions.UnexpectedTemplateError <smartconfig.exceptions.UnexpectedTemplateError>`.
To evaluate part of a value separately, make it a sibling template that lists
all the variables it needs.

**Missing, null and default values.**

.. list-table::
   :widths: 30 35 35
   :header-rows: 1

   * - Written
     - Schema
     - Resolved value
   * - key absent
     - optional, no ``default``
     - key absent
   * - key absent
     - ``"default": None``, ``"nullable": True``
     - ``None``
   * - key absent
     - ``"default": X`` (X not ``None``)
     - a ``Template`` of ``X`` (written without a wrapper)
   * - ``None``
     - ``"nullable": True``
     - ``None``
   * - ``{"__template__": v}``
     - any template schema
     - a ``Template`` of ``v``

**Other details.**

- A ``__template__`` wrapper on a field of type ``"any"`` also resolves to a
  ``Template``, with schema ``{"type": "any"}`` and no variables. On a field of
  any other type it is an error
  (:class:`exceptions.UnexpectedTemplateError <smartconfig.exceptions.UnexpectedTemplateError>`).
- A dynamic schema inside a template is called with the value as written, both
  when the configuration is resolved and when the template is.
- :meth:`Template.to_json <smartconfig.Template.to_json>` and
  :meth:`Template.from_json <smartconfig.Template.from_json>` convert a template to
  and from JSON-compatible data (without its schema, which may contain
  functions).
