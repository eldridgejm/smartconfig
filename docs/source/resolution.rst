Resolution
----------

.. testsetup:: python

    import smartconfig
    from smartconfig import types
    from pprint import pprint
    print = pprint

The process of converting a raw configuration into a resolved configuration is
called **resolution**. During resolution, `smartconfig` processes the
configuration according to the provided schema, performing
interpolation of placeholders, conversion of values to their appropriate types,
and evaluation of any function calls.

:func:`smartconfig.resolve` is the main function that performs resolution. It
takes two arguments: the raw configuration (a Python dictionary) and the schema
specifying its expected structure. The behavior of
:func:`smartconfig.resolve` can be customized using various optional
parameters; see the function documentation as well as the pages in the
"Customizing Behavior" section for more details.

Interpolation
~~~~~~~~~~~~~

The first step in resolution is **interpolation**. Interpolation involves
replacing placeholders (e.g., ``${course_name}``) with their corresponding
resolved values. During the interpolation step, all of the referenced entries
in the configuration are first resolved if they haven't been already. The
result of interpolation is always a string.

When a string references another value via ``${...}``, that referenced value is automatically resolved first (if it hasn't been already). This means references can chain through multiple levels. For example:

.. testcode:: python

    config = {
        "course_name": "Introduction to Python",
        "welcome_message": "Welcome to ${course_name}!",
        "detailed_message": "${welcome_message} Enjoy your learning journey."
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "course_name": {"type": "string"},
            "welcome_message": {"type": "string"},
            "detailed_message": {"type": "string"},
        },
    }

    resolved = smartconfig.resolve(config, schema)
    pprint(resolved)

This would output:

.. testoutput:: python

    {'course_name': 'Introduction to Python',
     'detailed_message': 'Welcome to Introduction to Python! Enjoy your learning '
                         'journey.',
     'welcome_message': 'Welcome to Introduction to Python!'}

Jinja2
^^^^^^

Interpolation is implemented using the `Jinja2` templating engine, which supports a wide range of expressions, including filters, conditionals, and arithmetic operations. This allows for powerful and flexible configurations. For example, the below uses Jinja2's built-in `length` filter to dynamically compute the length of another string in the configuration:

.. testcode:: python

    config = {
        "course_name": "Advanced Python",
        "name_length": "${course_name | length}",
        "is_advanced": "${ course_name.startswith('Advanced') }"
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "course_name": {"type": "string"},
            "name_length": {"type": "integer"},
            "is_advanced": {"type": "boolean"},
        },
    }

    resolved = smartconfig.resolve(config, schema)
    pprint(resolved)

This would output:

.. testoutput:: python

    {'course_name': 'Advanced Python', 'is_advanced': True, 'name_length': 15}

Besides ``${ ... }``, Jinja2 also reads ``{% ... %}`` as a block tag (such as a
``for`` loop) and ``{# ... #}`` as a comment. To write ``{%`` or ``{#`` literally,
insert it as a string:

.. testcode:: python

    config = {"note": "Issue ${ '{#' }123}, 50${ '{%' } off"}

    pprint(smartconfig.resolve(config, {"type": "any"}))

.. testoutput:: python

    {'note': 'Issue {#123}, 50{% off'}

A string without any of ``${``, ``{%`` or ``{#`` is not passed to Jinja2 at all,
so it is kept exactly as written.

Conversion
~~~~~~~~~~

After interpolation is **conversion**. Conversion involves converting the
resulting string into a Python object of the appropriate type (e.g., converting
`"2025-01-10"` to a Python `date` object).

Several built-in converters are provided by `smartconfig`; the defaults are discussed in :doc:`default_converters`. Custom converters can also be defined; see :doc:`custom_converters` for more information.

The built-in converters parse ISO format strings into the appropriate Python
types. For example, the ``date`` converter parses ``"2025-01-10"`` into a
``datetime.date`` object, and the ``datetime`` converter parses
``"2025-09-01 09:00:00"`` into a ``datetime.datetime`` object. See
:doc:`default_converters` for full details.

The converters also act as type validators: if the value cannot be converted to
the expected type, an error is raised.

Function Evaluation
~~~~~~~~~~~~~~~~~~~

A configuration can also contain **function calls**. `smartconfig` provides a
number of default functions implementing control flow, string manipulation,
list operations, and more; see :doc:`default_functions` for details. At the same time, custom functions can also be defined; see :doc:`custom_functions` for more information.

A function call is represented by a dictionary with a special format: by
default, it is a dictionary with a single key of the form
``__<function_name>__``. The value of the key is the argument that is passed to
the function.

For example, consider the default :code:`if` function, implementing conditional
logic. It takes a dictionary with three keys: ``condition``, ``then``, and
``else``, as shown below:

.. testcode:: python

    schema = {
        "type": "dict",
        "required_keys": {
            "student_score": {"type": "integer"},
            "is_eligible": {"type": "boolean"},
        },
    }

    config = {
        "student_score": 85,
        "is_eligible": {"__if__": {"condition": "${student_score >= 70}", "then": True, "else": False}}
    }

    print(smartconfig.resolve(config, schema))

This resolves to:

.. testoutput:: python

    {'is_eligible': True, 'student_score': 85}

Here we are taking advantage of the fact that templating is done by the
Jinja2 and so during interpolation ``${student_score >= 70}`` evaluates to ``True``, and
thus the ``then`` branch is taken.

More Details
~~~~~~~~~~~~

The above is a simplified overview of the resolution process. For more details on
each step, see the :doc:`resolution_in_detail` page.
