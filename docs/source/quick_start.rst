Features and Quick Start
========================

`smartconfig` is a toolkit that your application can use to make its
configuration files smarter. A typical use case of `smartconfig` might only
need its basic features, like string interpolation and type validation, but
`smartconfig` also enables more complex behavior, like function calling and
control flow. This page gives a crash course introduction to what `smartconfig`
can do, starting with the most basic features and working up to the more
advanced ones.

Basic Features
--------------

Interpolation
^^^^^^^^^^^^^

**Interpolation** is the first way in which `smartconfig` makes configurations
smarter. Interpolation allows a field in the configuration to refer to other
values in the same configuration (or even outside of the configuration). The
main benefit of this is *reuse*: define a value once, and any changes to it are
automatically reflected in all other values that refer to it.

For example, let's say you're configuring a website for a college course, and
the website generator needs to know three things: the name of the course, the
name of the instructor, and a welcome message that is displayed on the
homepage. With `smartconfig`, you could define the following configuration in a
JSON file:

**config.json**

.. code:: json

    {
        "course_name": "Introduction to Computer Science",
        "instructor": "Dr. Obama",
        "welcome_msg": "Welcome to ${course_name}! My name is ${instructor}."
    }


Here, ``${course_name}`` and ``${instructor}`` are intended to be placeholders
that will be replaced with the values of ``course_name`` and ``instructor``
when the configuration is loaded. Of course, this is not a standard feature of
JSON, so if you were to load this configuration with the standard Python
``json`` library, you wouldn't get the expected result; instead, you'd get what
you might call the "raw" configuration, with the placeholders still in place.

.. note::

    `smartconfig` does not actually read the input file; that is left to
    third-party packages for reading configuration formats (like `PyYaml` or
    the `json` module). Instead, `smartconfig` accepts as input the standard
    Python types returned by those libraries; this makes it agnostic to the
    configuration format used and very general in its applicability.

Let's use `smartconfig` to "resolve" the raw configuration loaded by the
``json`` library into one where the placeholders have been replaced. First, you
must define a *schema* that describes the expected structure of the
configuration. Among other things, the schema enables basic type validation and
error checking, so that if the configuration is missing a required field or has
the wrong type, an error will be raised. For more information on schemas (and
how to define them), see :doc:`Schemas <schemas>`.

Once the schema is defined, you can call ``smartconfig.resolve()`` on the "raw"
configuration to get the "resolved" configuration, with all placeholders
replaced with their actual values:

.. testsetup::

    import json
    import os
    import tempfile
    from pprint import pprint as print

    # write the config.json shown above, in a temporary directory
    _previous_directory = os.getcwd()
    _directory = tempfile.TemporaryDirectory()
    os.chdir(_directory.name)
    with open("config.json", "w") as f:
        json.dump(
            {
                "course_name": "Introduction to Computer Science",
                "instructor": "Dr. Obama",
                "welcome_msg": "Welcome to ${course_name}! My name is ${instructor}.",
            },
            f,
        )

.. testcleanup::

    os.chdir(_previous_directory)
    _directory.cleanup()

.. testcode::

    import json
    import smartconfig

    # 1. Load raw configuration
    with open("config.json") as f:
        raw_config = json.load(f)

    # 2. Describe the expected structure with a schema
    schema = {
        "type": "dict",
        "required_keys": {
            "course_name": {"type": "string"},
            "instructor": {"type": "string"},
            "welcome_msg": {"type": "string"},
        },
    }

    # 3. Resolve
    resolved = smartconfig.resolve(raw_config, schema)
    print(resolved)

The resolved configuration is a dictionary with all values computed:

**Output**

.. testoutput::

    {'course_name': 'Introduction to Computer Science',
     'instructor': 'Dr. Obama',
     'welcome_msg': 'Welcome to Introduction to Computer Science! My name is Dr. '
                    'Obama.'}

A placeholder can also refer to a value from outside the configuration. Pass
such values to ``smartconfig.resolve()`` as *global variables*:

.. testcode:: globals

    config = {"title": "${course_name} (${quarter})"}
    schema = {"type": "dict", "required_keys": {"title": {"type": "string"}}}

    resolved = smartconfig.resolve(
        config,
        schema,
        global_variables={"course_name": "DSC 10", "quarter": "Fall 2025"},
    )
    print(resolved)

**Output**

.. testoutput:: globals

    {'title': 'DSC 10 (Fall 2025)'}

.. testsetup:: globals

    import smartconfig


Type Conversion and Validation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

`smartconfig` also allows for type conversion and validation of configuration
fields.

For example, formats like JSON have no type for dates, and interpolation always
produces a string. The schema says what type each value should be, and
`smartconfig` converts the value to that type:

.. testcode:: conversion

    config = {
        "start_date": "2025-09-01",
        "weeks": 10,
        "lectures": "${weeks * 3}",
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "start_date": {"type": "date"},
            "weeks": {"type": "integer"},
            "lectures": {"type": "integer"},
        },
    }

    print(smartconfig.resolve(config, schema))

**Output**

.. testoutput:: conversion

    {'start_date': datetime.date(2025, 9, 1), 'weeks': 10, 'lectures': 30}

A value that can't be converted is an error, and the error says where it is:

.. testcode:: conversion

    config["start_date"] = "Sept 1"

    try:
        smartconfig.resolve(config, schema)
    except smartconfig.exceptions.ResolutionError as exc:
        print(exc)

**Output**

.. testoutput:: conversion

    Cannot resolve keypath "start_date": Cannot convert to date: 'Sept 1'.

The same goes for a missing required key or an unexpected extra one. For
example, in the configuration below the ``weeks`` key is missing, and the schema
marked it as required:

.. testcode:: conversion

    config = {
        "start_date": "2025-09-01",
        "lectures": "${weeks * 3}",
    }

    try:
        smartconfig.resolve(config, schema)
    except smartconfig.exceptions.ResolutionError as exc:
        print(exc)

**Output**

.. testoutput:: conversion

    Cannot resolve keypath "weeks": Dictionary is missing required key "weeks".

.. testsetup:: conversion

    import smartconfig


Default Values
^^^^^^^^^^^^^^

A key doesn't have to be required. Put it under ``optional_keys`` instead, and
give it a default that is used when the key is missing. In the example below,
``weeks`` and ``lectures`` are optional, and if they are missing, they get default
values of 10 and 30, respectively:

.. testcode:: defaults

    schema = {
        "type": "dict",
        "required_keys": {
            "start_date": {"type": "date"},
        },
        "optional_keys": {
            "weeks": {"type": "integer", "default": 10},
            "lectures": {"type": "integer", "default": "${weeks * 3}"},
        },
    }

    print(smartconfig.resolve({"start_date": "2025-09-01"}, schema))

**Output**

.. testoutput:: defaults

    {'start_date': datetime.date(2025, 9, 1), 'weeks': 10, 'lectures': 30}

.. testsetup:: defaults

    import smartconfig


Advanced Features
-----------------

Function Calls
^^^^^^^^^^^^^^

Some values are easiest to compute rather than write out. For this,
`smartconfig` allows for **function calling**. Several built-in functions are
provided for the most common use cases.

A configuration field calls a function by making its value a dictionary with a
single key: the function's name wrapped in double underscores. That key's value
is the function's input.

For example, `smartconfig` provides functions for working with dates and times.
One such function is ``__datetime.parse__``, which reads a date written in
plain English and works out which day it is. In the example below, the
``midterm`` field will resolve to the date that is four weeks after the
``start_date``:

.. testcode:: functions

    config = {
        "start_date": "2025-09-25",
        "midterm": {"__datetime.parse__": "4 weeks after ${start_date}"},
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "start_date": {"type": "date"},
            "midterm": {"type": "date"},
        },
    }

    print(smartconfig.resolve(config, schema))

**Output**

.. testoutput:: functions

    {'start_date': datetime.date(2025, 9, 25), 'midterm': datetime.date(2025, 10, 23)}

If the start date is changed, the midterm date moves with it. `smartconfig`
comes with functions for conditionals, as well as performing basic operations
on lists, dictionaries and dates (see :doc:`default_functions`), and your
application can add its own (see :doc:`custom_functions`).

.. testsetup:: functions

    import smartconfig


Control Flow
^^^^^^^^^^^^

A configuration can choose between values. The ``__if__`` function takes a
``condition``, a ``then`` value and an ``else`` value. Below, a course with no
midterm gets a longer final exam:

.. testcode:: control-flow

    config = {
        "has_midterm": False,
        "final_length": {
            "__if__": {
                "condition": "${has_midterm}",
                "then": "2 hours",
                "else": "3 hours",
            }
        },
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "has_midterm": {"type": "boolean"},
            "final_length": {"type": "string"},
        },
    }

    print(smartconfig.resolve(config, schema))

**Output**

.. testoutput:: control-flow

    {'has_midterm': False, 'final_length': '3 hours'}

``then`` and ``else`` can be any configuration, including dictionaries, lists
and other function calls.

For short choices inside a string, a placeholder can also hold a Jinja2
expression, like ``"${'2 hours' if has_midterm else '3 hours'}"``. Jinja2's
``{% if %}`` and ``{% for %}`` blocks work in strings too. See
:doc:`default_functions` for ``__if__`` and the list functions, such as
``__list.loop__``, that build values in a loop.

.. testsetup:: control-flow

    import smartconfig


Template Fields
^^^^^^^^^^^^^^^

Sometimes part of a configuration can't be resolved yet, because it depends on
values that only your application knows. For example, the course website might
have one page per homework, and every page follows the same pattern. We'd like
for part of the configuration to be evaluated multiple times: once for each
homework assignment. In particular, it *should not* be evaluated when the
configuration is first loaded, because it will refer to names and due dates
that are not known until later.

To allow for this, `smartconfig` provides **template fields**. A template field
is not resolved when the configuration is loaded, and must be "manually"
evaluated later by your application. The benefit of this is that any dynamic
values -- such as interpolated placeholders, function calls, and control flow
-- are deferred until the template is evaluated, so they can depend on values
that are only known at runtime.

To define a template field, the schema specifies ``"type": "template"``, a
schema for the value it will produce, and a list of *parameters*: the names the
template can refer to. In the configuration, a template is marked with the
``__template__`` function:

.. testcode:: templates

    schema = {
        "type": "dict",
        "required_keys": {
            "homework_page": {
                "type": "template",
                "schema": {
                    "type": "dict",
                    "required_keys": {
                        "title": {"type": "string"},
                        "due": {"type": "date"},
                    },
                },
                "parameters": ["number", "due_date"],
            },
        },
    }

    config = {
        "homework_page": {
            "__template__": {
                "title": "Homework ${number}",
                "due": "${due_date}",
            }
        }
    }

    page = smartconfig.resolve(config, schema)["homework_page"]

Resolving the configuration leaves the template unevaluated. The template field
will be an instance of :class:`smartconfig.types.Template`, which keeps the value as
written in its ``source`` attribute:

.. testcode:: templates

    print(page)
    print(page.source)

**Output**

.. testoutput:: templates

    Template(at "homework_page", parameters: number, due_date)
    {'title': 'Homework ${number}', 'due': '${due_date}'}

Your application
then evaluates it as many times as it needs, giving a value for each
parameter:

.. testcode:: templates

    print(page.evaluate({"number": 1, "due_date": "2025-10-03"}))
    print(page.evaluate({"number": 2, "due_date": "2025-10-10"}))

**Output**

.. testoutput:: templates

    {'title': 'Homework 1', 'due': datetime.date(2025, 10, 3)}
    {'title': 'Homework 2', 'due': datetime.date(2025, 10, 10)}

Each evaluation converts types and fills in defaults just as
``smartconfig.resolve()`` does. For more, see :ref:`template_fields_example`.

.. testsetup:: templates

    import smartconfig
