smartconfig
===========

`smartconfig` is a Python library that extends configuration formats (like
JSON, YAML, TOML, etc.) with "smart" features, such as string interpolation,
natural language parsing, and type checking.

Use Cases and Example
---------------------

Python programs that require user configuration often use simple configuration
formats such as JSON, YAML, or TOML. These formats are easy to understand, but
they may not support more advanced features like string interpolation, date
parsing, or type checking. Another approach is to use a full-fledged
programming language to define the configuration, such as Python itself.
However, this approach vastly increases the possible complexity of the
configuration file, and it requires that users know how to write Python code.

`smartconfig` aims to bridge the gap between these two approaches by providing
a simple way to extend simple configuration formats with "smart" features. To
see how this works, consider the following example. Suppose you have a
configuration file in JSON format that looks like this:

.. code:: json

   {
        "course_name": "Introduction to Python",
        "date_of_first_lecture": "2025-01-10",
        "date_of_first_discussion": "7 days after ${this.first_lecture}",
        "message": [
            "Welcome to ${this.course_name}!",
            "The first lecture is on ${this.first_lecture}.",
            "The first discussion is on ${this.first_discussion}."
        ]
   }

.. testsetup::

    import json
    from pprint import pprint as print

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

    json.dump(config, open('example.json', 'w'))

Notice the use of the `${...}` syntax to refer to other values in the
configuration file and the fact that the `date_of_first_discussion` key is
defined relative to the `date_of_first_lecture` key. Of course, if we try to
load this configuration file using Python's `json` module, we will not see
anything special happen; the references will not be resolved. Now let's use
`smartconfig` to load the configuration:


.. testcode::

    import smartconfig
    import json

    # read the configuration json
    with open('example.json') as f:
        config = json.load(f)

    # first we define a schema to let smartconfig know what to expect
    schema = {
        "type": "dict",
        "required_keys": {
            "course_name": {"type": "string"},
            "date_of_first_lecture": {"type": "date"},
            "date_of_first_discussion": {"type": "date"},
            "message": {"type": "list", "element_schema": {"type": "string"}}
        }
    }

    # now we "resolve" the references in the configuration
    result = smartconfig.resolve(config, schema)
    print(result)

We will see the following output:

.. testoutput::

    {'course_name': 'Introduction to Python',
     'date_of_first_lecture': datetime.date(2025, 1, 10),
     'date_of_first_discussion': datetime.date(2025, 1, 17),
     'message': ['Welcome to Introduction to Python!',
                 'The first lecture is on 2025-01-10.',
                 'The first discussion is on 2025-01-17.']}

Notice that the `${...}` references have been resolved, and the date of the
first discussion, defined relative to the date of the first lecture in the
original JSON, has been calculated correctly. This example demonstrates the
most basic use case of `smartconfig`: extending simple configuration formats.
But `smartconfig` provides many more features that can be used to create
powerful and flexible configuration files.

Features
--------

`smartconfig` supports extending configuration formats with the following
features:

- **String interpolation**: Use `${...}` to refer to other values in the
  configuration file. This helps avoid duplication and the errors that can
  arise from it.
- **Natural language parsers**: `smartconfig` includes natural language parsers
  for dates, numbers, and boolean values. When combined with string
  interpolation, this allows you to define values relative to other values in
  the configuration file. For example, you can define a value as ``7 days after
  ${this.start_date}``, or ``${this.previous_lecture_number} + 1``.
- **Function calls**: `smartconfig` defines a syntax for calling functions in
  the configuration file. This allows the user to specify complex values that
  are calculated at runtime. Functions are provided for merging dictionaries,
  concatenating lists, etc., and developers can define their own functions as well.
- **Complex control flow**: the Jinja2 templating engine is used under
  the hood, which means that you can use Jinja2's control flow constructs
  like `if` statements, `for` loops, and more to define complex values in
  your configuration file.
- **Default values**: default values can be provided, so that the user
  can save typing and highlight what's important by only specifying the values
  that are different from the default.
- **Basic type checking**: `smartconfig` can check that values in the
  configuration file are of the expected type. For example, you can specify
  that a value should be a date, a number, or a boolean, and `smartconfig` will
  raise an error if the value is not of the expected type.

Additionally, `smartconfig` provides the following features to developers:

- **Extensibility**: `smartconfig` is designed to be easily extensible. You can
  define your own parsers for custom natural language parsing and you can
  define your own functions for complex runtime behavior.
- **Format agnostic**: `smartconfig` can be used with any configuration format
  that can be loaded into a Python dictionary. This includes JSON, YAML, TOML,
  and more.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   ./concepts.rst
   ./schemas.rst
   ./resolve.rst
