Inline Python
=============

.. testsetup:: inline-python

    import smartconfig
    from pprint import pprint

`smartconfig` makes configurations dynamic with interpolation (``${...}``), the
default functions, and custom functions. All of these are defined by the program
that resolves the configuration: the configuration can use only what the program
provides.

In some cases, the user writing the configuration wants to do something dynamic
that the resolving program doesn't provide for. The ``python`` function is for
these situations: it runs a string of Python code written in the configuration,
and uses what the code returns as the value. This allows the configuration to
do anything Python can do.

.. warning::

    ``python`` runs whatever code the configuration contains, with the same
    permissions as your program. Anyone who can write the configuration can make
    it read or delete files, start processes or send data over the network. Only
    turn it on for configurations you trust as much as your own code.

For this reason, ``python`` is not one of the default functions. To use it, import
it from :mod:`smartconfig.stdlib.python` and add it to the functions passed to
:func:`smartconfig.resolve`:

.. testcode:: inline-python

    from smartconfig.stdlib.python import python

    functions = {**smartconfig.DEFAULT_FUNCTIONS, "python": python}

    config = {"answer": {"__python__": "return 6 * 7"}}
    schema = {"type": "dict", "required_keys": {"answer": {"type": "integer"}}}

    pprint(smartconfig.resolve(config, schema, functions=functions))

.. testoutput:: inline-python

    {'answer': 42}

The examples below use this ``functions`` mapping.

Writing the code
----------------

The string is the body of a function. It is run as if it were indented under
``def body(args):``. The function's one input, ``args``, is an instance of
:class:`~smartconfig.types.FunctionArgs`, the same object that a custom function
receives, so the code can use ``args.root``, ``args.resolve`` and the rest of its
attributes. Like any function body, it can import modules, define helper
functions and use loops, and it gives its value with ``return``. The code is
dedented before it runs, so it can be indented to fit where it is written, as in
this triple-quoted string:

.. testcode:: inline-python

    config = {
        "sides": {
            "__python__": """
                import math

                def hypotenuse(a, b):
                    return math.sqrt(a**2 + b**2)

                return [hypotenuse(a, b) for a, b in [(3, 4), (5, 12)]]
            """
        }
    }
    schema = {
        "type": "dict",
        "required_keys": {
            "sides": {"type": "list", "element_schema": {"type": "float"}},
        },
    }

    pprint(smartconfig.resolve(config, schema, functions=functions))

.. testoutput:: inline-python

    {'sides': [5.0, 13.0]}

The body must ``return`` its value. A body with no ``return`` of its own (one in a
helper function doesn't count) is an error, since it would always give ``None``.
To give ``None`` on purpose, write ``return None``. The body can't be a generator:
a body that uses ``yield`` is an error too. To give several values, return a list.

The returned value is converted to the field's schema, like any other value: a
body that returns the string ``"42"`` in a field of type ``integer`` gives ``42``,
and one whose value doesn't match the schema is an error. It is not resolved,
though: a ``${...}`` in it is not filled in, and a function call in it is not
evaluated. See `Interpolation`_ below.

Reading other values
--------------------

The body reads other values in the configuration with ``args.root``, which
behaves like the configuration itself. A value read this way is resolved first,
with its own schema, so it has its final type: below, ``start`` is a
:class:`datetime.date`, not a string.

.. testcode:: inline-python

    config = {
        "start": "2025-10-01",
        "weeks": 10,
        "end": {
            "__python__": (
                "import datetime\n"
                "weeks = datetime.timedelta(weeks=args.root['weeks'])\n"
                "return args.root['start'] + weeks\n"
            )
        },
    }
    schema = {
        "type": "dict",
        "required_keys": {
            "start": {"type": "date"},
            "weeks": {"type": "integer"},
            "end": {"type": "date"},
        },
    }

    pprint(smartconfig.resolve(config, schema, functions=functions))

.. testoutput:: inline-python

    {'end': datetime.date(2025, 12, 10),
     'start': datetime.date(2025, 10, 1),
     'weeks': 10}

Nested values are read the same way, as in ``args.root['course']['start']``. A
body that reads its own value, directly or through other values, is a circular
reference, which is an error.

Interpolation
-------------

Neither the code nor what it returns is interpolated. The code is run as written,
so Python that happens to contain ``${`` or ``{{`` is left alone. The value it
returns is used as it is, then converted to the field's schema. Here the
``${ name }`` is not filled in:

.. testcode:: inline-python

    config = {
        "name": "Ada",
        "greeting": {"__python__": "return 'Hello ${ name }'"},
    }
    schema = {
        "type": "dict",
        "required_keys": {
            "name": {"type": "string"},
            "greeting": {"type": "string"},
        },
    }

    pprint(smartconfig.resolve(config, schema, functions=functions))

.. testoutput:: inline-python

    {'greeting': 'Hello ${ name }', 'name': 'Ada'}

This matters because the value is often built from values read with
``args.root``, which are already resolved. Resolving them again could change them:
a value made with ``__raw__`` would be interpolated after all.

To interpolate a value, pass it to ``args.resolve`` and return the result.
``args.resolve`` treats its argument as configuration, so ``${...}`` is filled in
and function calls in it are evaluated. With ``local_variables=``, it can also be
given names to fill in. This lets the code use configuration written in the
configuration's own syntax. Below, the welcome message is written as a template,
kept from being interpolated with ``__raw__``, and the code fills it in once for
each student:

.. testcode:: inline-python

    config = {
        "course": "DSC 10",
        "students": ["Ada", "Grace"],
        "message": {"__raw__": "Welcome to ${ course }, ${ name }!"},
        "welcomes": {
            "__python__": """
                return [
                    args.resolve(
                        args.root["message"],
                        schema={"type": "string"},
                        local_variables={"name": name},
                    )
                    for name in args.root["students"]
                ]
            """
        },
    }
    schema = {
        "type": "dict",
        "required_keys": {
            "course": {"type": "string"},
            "students": {"type": "list", "element_schema": {"type": "string"}},
            "message": {"type": "string"},
            "welcomes": {"type": "list", "element_schema": {"type": "string"}},
        },
    }

    pprint(smartconfig.resolve(config, schema, functions=functions))

.. testoutput:: inline-python

    {'course': 'DSC 10',
     'message': 'Welcome to ${ course }, ${ name }!',
     'students': ['Ada', 'Grace'],
     'welcomes': ['Welcome to DSC 10, Ada!', 'Welcome to DSC 10, Grace!']}

``args.resolve`` resolves with the schema of the call unless given another with
``schema=``. Above, the call's schema is a list of strings, but each message is a
single string, so the code passes that schema. In a field of type ``any``,
interpolation gives a string, so pass the schema of the value you want:

.. testcode:: inline-python

    config = {
        "n": 3,
        "as_string": {"__python__": "return args.resolve('${ n }')"},
        "as_integer": {
            "__python__": "return args.resolve('${ n }', schema={'type': 'integer'})"
        },
    }
    schema = {
        "type": "dict",
        "required_keys": {
            "n": {"type": "integer"},
            "as_string": {"type": "any"},
            "as_integer": {"type": "any"},
        },
    }

    pprint(smartconfig.resolve(config, schema, functions=functions))

.. testoutput:: inline-python

    {'as_integer': 3, 'as_string': '3', 'n': 3}

Reading a value with ``args.root`` avoids this, since the value already has its
type.

Errors
------

Every problem with the code is reported as a
:class:`~smartconfig.exceptions.ResolutionError` at the keypath of the call:

- The input is not a string, or is empty.
- The code is not valid Python. The message gives the number of the line with
  the error, counting from the first line of the code, and Python's reason.
- The code has no ``return`` statement, or uses ``yield``.
- The code raises an exception. The message gives the exception's type and
  message, and the exception is kept as the error's ``__cause__``.

.. testcode:: inline-python

    config = {"ratio": {"__python__": "return 1 / 0"}}
    schema = {"type": "dict", "required_keys": {"ratio": {"type": "float"}}}

    try:
        smartconfig.resolve(config, schema, functions=functions)
    except smartconfig.exceptions.ResolutionError as exc:
        print(exc)

.. testoutput:: inline-python

    Cannot resolve keypath "ratio": ZeroDivisionError: division by zero

A ``ResolutionError`` raised while the code runs, such as one from reading a value
with ``args.root`` that can't be resolved, is passed on unchanged, so it gives the
keypath of the value with the problem.
