Configurations
--------------

Using `smartconfig` involves three steps:

1. Read a **"raw" configuration** (usually from JSON, YAML, or TOML) into a Python dictionary.
2. Define a **schema** that specifies the expected structure and types of the configuration.
3. Call :func:`smartconfig.resolve()` to produce a **"resolved" configuration** where all dynamic values have been computed.

This section introduces the first concept: the **configuration**. For the others, see :doc:`schemas` and :doc:`resolution`.

.. note::

    `smartconfig` does not actually read the input file; that is left to
    third-party packages for reading configuration formats (like `PyYaml` or
    the `json` module). Instead, `smartconfig` accepts as input the standard
    Python types returned by those libraries; this makes it agnostic to the
    configuration format used and very general in its applicability.


Structure of a Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In `smartconfig`, a **configuration** is a data structure that represents your application's settings. It serves as both the input to and the output of the resolution process.

Formally, a configuration is defined recursively as one of the following:

- A **dictionary** whose keys are strings and whose values are again configurations.
- A **list** of configurations.
- A **value** (a string, integer, float, boolean, date or datetime, or None).

The input to `smartconfig` is a "raw" configuration. It typically comes directly from a configuration file (JSON, YAML, TOML) and contains values that are not yet fully processed. In the example below, the ``config`` dictionary is a raw configuration: it contains interpolation placeholders (``${...}``) and natural language expressions that have not yet been evaluated.

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

A **resolved configuration** is the output of `smartconfig`. It is a configuration where all dynamic values have been computed, all interpolations have been performed, and all values have been converted to their final Python types. For example, after resolving the above configuration, we would get:

.. code:: python

    resolved = {
        "course_name": "Introduction to Python",
        "date_of_first_lecture": datetime.date(2025, 1, 10),
        "date_of_first_discussion": datetime.date(2025, 1, 17),
        "message": [
            "Welcome to Introduction to Python!",
            "The first lecture is on 2025-01-10.",
            "The first discussion is on 2025-01-17."
        ]
    }

In order to resolve a raw configuration, `smartconfig` needs to know what structure and types to expect. This is the purpose of :doc:`schemas`, which are discussed next.
