Concepts
--------

Before getting started with `smartconfig`, it's useful to understand a few key concepts.

The input to `smartconfig` is a **configuration**. A configuration is recursively defined
as one of the following:

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

The input configuration is typically read from a file (e.g., a JSON, YAML, or TOML file)
and contains values that are not yet fully "resolved" (such as
``date_of_first_discussion`` in the above example). The goal of `smartconfig` is to
**resolve** these values and convert the configuration into its final form.

.. note::

    `smartconfig` does not actually read the input file; that is left to
    third-party packages for reading configuration formats (like `PyYaml` or
    the `json` module). Instead, `smartconfig` accepts as input the standard
    Python types returned by those libraries; this makes it agnostic to the
    configuration format used and very general in its applicability.

Resolving a value in a configuration involves two steps: **interpolation** and
**conversion**. **Interpolation** involves replacing placeholders (e.g.,
``${this.course_name}``) with their corresponding resolved values. During the
interpolation step, all of the referenced entries in the configuration are
first resolved if they haven't been already. **Conversion** involves converting the
resulting string into a Python object of the appropriate type (e.g., converting
`"2025-01-10"` to a Python `date` object). Several built-in converters are provided
in :mod:`smartconfig.parsers`. Some of them, like
:func:`smartconfig.converters.smartdatetime`, are "smart" in the sense that they
can parse natural language strings into Python objects. The converters also act as type
validators: if the value cannot be converted to the expected type, an error is raised.

In order to know what the final type of a configuration value should be (and therefore
which converter to use), `smartconfig` employs a **schema**. A schema is a dictionary
specifying the expected structure of the configuration. For example, the schema for the
above configuration is:

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

Several features are provided for allowing configuration values to be dynamically
computed. For instance, a configuration can contain **function calls**. A function call
is represented by a dictionary with a special format: by default, it is a dictionary
with a single key of the form ``__<function_name>__``. The value of the key is the
argument that is passed to the function. `smartconfig` provides a number of built-in
functions in :mod:`smartconfig.functions`, but custom functions can also be provided.

The result of resolving the configuration is also a **configuration**.
