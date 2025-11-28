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
example, they support ``extra_keys_schema`` and other fine-grained controls
that prototypes currently do not).

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
describing deeply-nested structures, and so in those cases schemas may be
preferable.

Prototypes have several useful methods, including
:meth:`smartconfig.Prototype._as_dict()` which converts the prototype instance
into a dictionary, :meth:`smartconfig.Prototype._from_dict()`, which creates a
prototype instance from a dictionary, and
:meth:`smartconfig.Prototype._schema()`, which returns the schema
representation of the prototype.

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

    <SCHEMA> = (<DICT_SCHEMA> | <LIST_SCHEMA> | <VALUE_SCHEMA> | <ANY_SCHEMA>)

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

    <SCHEMA_WITH_DEFAULT> = (
        <DICT_SCHEMA_WITH_DEFAULT>
        | <LIST_SCHEMA_WITH_DEFAULT>
        | <VALUE_SCHEMA_WITH_DEFAULT>
        | <ANY_SCHEMA_WITH_DEFAULT>
    )

The ``DICT_SCHEMA_WITH_DEFAULT``, ``LIST_SCHEMA_WITH_DEFAULT``,
``VALUE_SCHEMA_WITH_DEFAULT``, and ``ANY_SCHEMA_WITH_DEFAULT`` grammars are the
same as their non-default counterparts, but with an additional field named
`default` that specifies the default value should that part of the
configuration be missing.

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
