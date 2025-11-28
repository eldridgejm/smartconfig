smartconfig
===========

`smartconfig` is a Python library for enhancing standard configuration formats (JSON, YAML, TOML) with dynamic features like interpolation, natural language parsing, and type validation, allowing you to build powerful configuration systems for your applications.

Use Cases and Quick Start
-------------------------

Python programs that require user configuration often use simple configuration formats such as JSON, YAML, or TOML. These formats are easier to read and write than coding languages, but they may not support more advanced features like string interpolation, date parsing, or type checking. Another approach is to use a full-fledged programming language to define the configuration, such as Python itself. However, this approach vastly increases the possible complexity of the configuration file, and it requires that users know how to write Python code.

`smartconfig` aims to bridge the gap between these two approaches by providing a simple way to extend configuration formats with "smart" features. To see how this works, consider the following example. Suppose you have a configuration file in JSON format that looks like this:

**config.json**

.. code:: json

    {
        "course_name": "Introduction to Computer Science",
        "start_date": "2025-09-01",
        "first_homework_due": "first tuesday after ${start_date}",
        "welcome_msg": "Welcome to ${course_name}!"
    }

Notice the use of ``${...}`` for interpolation and natural language date expressions. Of course, the JSON parser will not "resolve" these values automatically.  This is where `smartconfig` comes in:

**Python Code**

.. testsetup::

    import datetime
    from pprint import pprint as print

.. testcode::

    import json
    import smartconfig

    # 1. Load raw configuration
    with open("config.json") as f:
        raw_config = json.load(f)

    # 2. Define a prototype (class-based schema)
    class Course(smartconfig.Prototype):
        course_name: str
        start_date: datetime.date
        first_homework_due: datetime.date
        welcome_msg: str

    # 3. Resolve to a Prototype instance
    resolved = smartconfig.resolve(raw_config, Course)
    print(resolved)

The resolved configuration is an instance of ``Course`` with all values computed:

**Output**

.. testoutput::

    Course(course_name='Introduction to Computer Science', start_date=datetime.date(2025, 9, 1), first_homework_due=datetime.date(2025, 9, 2), welcome_msg='Welcome to Introduction to Computer Science!')

.. testsetup::

    import json
    import datetime
    from smartconfig import Prototype

    config = {
        "course_name": "Introduction to Computer Science",
        "start_date": "2025-09-01",
        "first_homework_due": "first tuesday after ${start_date}",
        "welcome_msg": "Welcome to ${course_name}!"
    }
    with open("config.json", "w") as f:
        json.dump(config, f)

Features
--------

`smartconfig` supports extending configuration formats with the following
features:

- **String interpolation**: Use ``${...}`` to refer to other values in the
  configuration file. This helps avoid tedious duplication and the errors that
  can arise from it.
- **Natural language parsers**: `smartconfig` includes natural language parsers
  for dates, numbers, and boolean values. When combined with string
  interpolation, this allows you to define values relative to other values in
  the configuration file. For example, you can define a value as ``7 days after
  ${start_date}``, or ``${previous_lecture_number} + 1``.
- **Default values**: default values can be provided, so that the user
  can save typing and highlight what's important by only specifying the values
  that are different from the default.
- **Basic type checking**: `smartconfig` can check that values in the
  configuration file are of the expected type. For example, you can specify
  that a value should be a date, a number, or a boolean, and `smartconfig` will
  raise an error if the value is not of the expected type.
- **Function calls**: `smartconfig` defines a syntax for calling functions in
  the configuration file. This allows the user to specify complex values that
  are calculated at runtime. Functions are provided for merging dictionaries,
  concatenating lists, etc., and developers can define their own functions as well.
- **Complex control flow**: the Jinja2 templating engine is used under
  the hood, which means that you can use Jinja2's control flow constructs
  like `if` statements, `for` loops, and more to define complex values in
  your configuration file. You can also use Jinja2 filters to transform
  values in your configuration file, as in ``${value | capitalize}`` to capitalize
  a string.

Additionally, `smartconfig` provides the following features to developers:

- **Extensibility**: `smartconfig` is designed to be easily extensible.
  Developers can define custom type converters, custom functions for complex runtime
  behavior, and custom filters for transforming values during string interpolation.
- **Format agnostic**: `smartconfig` can be used with any configuration format
  that can be loaded into a Python dictionary. This includes JSON, YAML, TOML,
  and any future format that might be developed.

.. toctree::
   :maxdepth: 1
   :caption: Key Concepts

   configurations
   schemas
   resolution

.. toctree::
   :maxdepth: 1
   :caption: Default Behavior

   default_converters
   default_functions

.. toctree::
   :maxdepth: 1
   :caption: Customizing Behavior

   resolution_in_detail
   custom_converters
   custom_functions
   custom_filters
   external_variables
   type_preservation

.. toctree::
   :maxdepth: 1
   :caption: Reference

   api
   prototypes
   types
   converters
   functions
   exceptions

.. toctree::
   :maxdepth: 1
   :caption: Recipes

   recipes

Installation
------------

Install directly from GitHub using `uv <https://docs.astral.sh/uv/>`_:

.. code:: bash

    uv add git+https://github.com/eldridgejm/smartconfig.git

Or with pip:

.. code:: bash

    pip install git+https://github.com/eldridgejm/smartconfig.git
