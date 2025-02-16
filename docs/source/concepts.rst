Concepts
--------

Before getting started with `smartconfig`, it's useful to understand a few key concepts.

The input to `smartconfig` is a **configuration**. A configuration is defined
recursively as one of the following:

- A **dictionary** whose keys are strings and whose values are again configurations.
- A **list** of configurations.
- A **value** (a string, integer, float, boolean, date or datetime, or None).

For example, the below is a valid configuration:

.. code:: python

    config = {
        "course_name": "Introduction to Python",
        "date_of_first_lecture": "2025-01-10",
        "date_of_first_discussion": "7 days after ${this.first_lecture}",
        "message": [
            "Welcome to ${this.course_name}!",
            "The first lecture is on ${this.first_lecture}.",
            "The first discussion is on ${this.first_discussion}."
        ]
    }

The input configuration is typically read from a file (e.g., a JSON, YAML, or
TOML file), and contains values that are not yet fully "resolved" (such as
`date_of_first_discussion` in the above example). The goal of `smartconfig` is
to **resolve** these values and convert the configuration into its final form.

Resolving a value in a configuration involves two steps: interpolation and
parsing. **Interpolation** involves replacing placeholders (e.g.,
``${this.course_name}``) with their corresponding resolved values. During the
interpolation step, all of the referened entries in the configuration are
first resolved if they haven't been already. If the value being resolved is a
string, the interpolation step is performed once. However, if the value being
resolved is a :class:`RawString`, interpolation is not performed at all, and if
it is a :class:`RecursiveString`, interpolation is performed recursively until
the value doesn't change. **Parsing** involves converting the resulting string into
a Python object of the appropriate type (e.g., converting `"2025-01-10"` to a
Python `date` object). Just as :class:`RawString` is not interpolated, it is
also not parsed.

In order to know what type of object to parse a string into, `smartconfig` uses
a **schema**. A schema is a dictionary which specifies the expected structure
of the configuration. For example, the schema for the above configuration is:

.. code:: python

    schema = {
        "type": "dict",
        "required_keys": {
            "course_name": {"type": "string"},
            "date_of_first_lecture": {"type": "date"},
            "date_of_first_discussion": {"type": "date"},
            "message": {"type": "list", "element_schema": {"type": "string"}}
        }
    }

The result of resolving the configuration is also a **configuration**.
