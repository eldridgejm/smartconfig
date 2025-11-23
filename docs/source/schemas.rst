.. _schemas:

Schemas
=======

In order for `smartconfig` to properly resolve a configuration, it first needs
to know the expected structure and types of the configuration. This is
specified using a **schema**. A schema is a dictionary defining the expected
structure of a configuration. Importantly, `smartconfig` uses the schema to
determine what type a value should have (integer, date, string, etc.) and
therefore which converter should be used to produce the final value.

Concretely, a schema is a dictionary that follows the formal grammar below.

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
``VALUE_SCHEMA_WITH_DEFAULT``, and ``ANY_SCHEMA_WITH_DEFAULT`` are the same as
their non-default counterparts, but with an additional field named `default`
that specifies the default value should that part of the configuration be
missing.

Schemas can be validated using the :func:`smartconfig.validate_schema`
function.

Examples
--------

Example 1: A simple schema
^^^^^^^^^^^^^^^^^^^^^^^^^^

Suppose a configuration should contain information about a student, including their
name, age, and a list of the classes they are taking. For example:

.. code:: python

    config = {
        "name": "Barack Obama",
        "age": 63,
        "enrolled_in": ["Math 100", "History 101", "Physics 200"]
    }

The schema describing this structure is:

.. code:: python

    schema = {
        "type": "dict",
        "required_keys": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
            "enrolled_in": {
                "type": "list",
                "element_schema": {"type": "string"}
            }
        },
    }

Example 2: Allowing extra keys
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

By default, `smartconfig` will raise an error if the configuration contains
keys not specified in the schema. Sometimes, however, it is useful to allow the
user to provide "extra" keys that are not specified in the schema. This is most
often the case when we want to allow the user to define a mapping whose keys
are not known in advance.

Building off of the previous example, suppose we want to allow the user to
specify a student's grades in each class as a mapping from class name to letter
grade. Such a configuration might look like this:

.. code:: python

    config = {
        "name": "Barack Obama",
        "age": 63,
        "enrolled_in": ["Math 100", "History 101", "Physics 200"],
        "grades": {
            "Math 100": "A-",
            "History 101": "A",
        }
    }

In this example, the "grades" entry is the mapping that should allow extra
keys. We can allow for this using the `extra_keys_schema` field in the schema:

.. code:: python

    schema = {
        "type": "dict",
        "required_keys": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
            "enrolled_in": {
                "type": "list",
                "element_schema": {"type": "string"}
            },
            "grades": {
                "type": "dict",
                "extra_keys_schema": {"type": "string"}
            }
        }
    }

Example 3: Allowing nullable values
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

By default, values in a configuration are not allowed to be `None`. However, we
can allow for `None` values by setting the `nullable` field to `True` in the
schema. For example, suppose we want to require the user to include the "age"
key in the configuration, but we want to allow them to give it a value of `None`
to indicate that the student's age is unknown. We can do this with the following
schema:

.. code:: python

    schema = {
        "type": "dict",
        "required_keys": {
            "name": {"type": "string"},
            "age": {"type": "integer", "nullable": True},
            "enrolled_in": {
                "type": "list",
                "element_schema": {"type": "string"}
            }
        }
    }


Example 4: Optional keys and defaults
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Sometimes we do not want to require the user to specify a key in the
configuration. For example, we might want to allow the user to specify an
optional email address. In this case, we can use the `optional_keys` field in
the schema:

.. code:: python

    schema = {
        "type": "dict",
        "required_keys": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
            "enrolled_in": {
                "type": "list",
                "element_schema": {"type": "string"}
            }
        },
        "optional_keys": {
            "email": {"type": "string"}
        }
    }

If the user provides a schema without specifying the "email" key, `smartconfig`
will not raise an error. Instead, it will simply not include the "email" key in
the resulting configuration.

Sometimes we want to provide a default value for an optional key. For example,
suppose we want to allow for a `standing` key specifying whether the student is an
undergraduate or graduate student. If the user does not specify a `standing`,
we want to default to "undergraduate". We can do this with the following schema:

.. code:: python

    schema = {
        "type": "dict",
        "required_keys": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
            "enrolled_in": {
                "type": "list",
                "element_schema": {"type": "string"}
            }
        },
        "optional_keys": {
            "email": {"type": "string"},
            "standing": {"type": "string", "default": "undergraduate"}
        }
    }

An optional key with a default value will always appear in the resulting
configuration, even if the user does not specify it. A common pattern is to
specify a default value of `None` for optional keys, so that they key always
appears in the resulting configuration, but is `None` if the user does not
specify it. To do this, it is necessary to set the `nullable` field to `True`
in the schema. For example, to make the `email` key optional with a default
value of `None`:

.. code:: python

    schema = {
        "type": "dict",
        "required_keys": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
            "enrolled_in": {
                "type": "list",
                "element_schema": {"type": "string"}
            }
        },
        "optional_keys": {
            "email": {"type": "string", "nullable": True, "default": None}
        }
    }

Example 5: Nested containers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The schema can be nested to any depth. For example, suppose we want to allow
the user to specify a list of students, each with the same structure as in
Example 1. We can do this with the following schema:

.. code:: python

    schema = {
        "type": "list",
        "element_schema": {
            "type": "dict",
            "required_keys": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
                "enrolled_in": {
                    "type": "list",
                    "element_schema": {"type": "string"}
                }
            }
        }
    }

Example 6: "Any" schema
^^^^^^^^^^^^^^^^^^^^^^^

Sometimes we do not know in advance what the structure of a configuration will
be, and we want to allow the user to specify any possible configuration. In
this case, we can use the `any` schema:

.. code:: python

    schema = {
        "type": "any"
    }

This schema will allow any configuration to be read, regardless of its
structure. However, if the "any" schema is used, `smartconfig` will not be able
to determine the intended type of the values in the configuration, and will
therefore do no parsing of the values. String interpolation will still be
performed.
