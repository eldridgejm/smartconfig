Default Functions
=================

`smartconfig` allows for dynamic behavior in configurations via **functions**.
A set of default functions is provided which implement control flow,
list manipulation, dictionary merging, and date operations. Custom functions
can also be defined; see :doc:`custom_functions` for more information.

Functions are invoked in configurations using the syntax ``{"__function_name__": ...}``.
For example, ``{"__if__": {"condition": "...", "then": ..., "else": ...}}`` calls
the ``if`` function.

Default functions are organized into two groups:

- **Core functions** handle control flow, string interpolation modes, and
  structural operations like splicing and template reuse.
- **Standard library (stdlib) functions** are namespaced and provide list,
  dictionary, and datetime operations. Stdlib functions use dotted names, e.g.,
  ``__list.loop__``, ``__dict.update__``, ``__datetime.parse__``.

The default functions are available by default — :func:`smartconfig.resolve`
uses :data:`smartconfig.DEFAULT_FUNCTIONS` as the default value for its
``functions`` parameter. To disable functions, pass ``functions=None``.

The default functions are summarized in the tables below:

**Core Functions**

.. list-table::
   :widths: 20 80
   :header-rows: 1

   * - Function
     - Description
   * - :ref:`__if__ <func-if>`
     - Conditional logic
   * - :ref:`__let__ <func-let>`
     - Define local variables and references
   * - :ref:`__raw__ <func-raw>`
     - Prevent interpolation
   * - :ref:`__resolve__ <func-resolve>`
     - Single-pass interpolation (override inherited mode)
   * - :ref:`__fully_resolve__ <func-fully-resolve>`
     - Repeated interpolation until stable
   * - :ref:`__splice__ <func-splice>`
     - Copy another part of the configuration
   * - :ref:`__template__ <func-template>`
     - Define a reusable template
   * - :ref:`__use__ <func-use>`
     - Copy a template with optional overrides

**Standard Library: List Functions**

.. list-table::
   :widths: 20 80
   :header-rows: 1

   * - Function
     - Description
   * - :ref:`__list.loop__ <func-loop>`
     - Generate a list by iteration
   * - :ref:`__list.range__ <func-range>`
     - Generate a list of numbers
   * - :ref:`__list.filter__ <func-filter>`
     - Filter a list by condition
   * - :ref:`__list.zip__ <func-zip>`
     - Zip lists together
   * - :ref:`__list.concatenate__ <func-concatenate>`
     - Concatenate lists

**Standard Library: Dictionary Functions**

.. list-table::
   :widths: 20 80
   :header-rows: 1

   * - Function
     - Description
   * - :ref:`__dict.update__ <func-update>`
     - Deep merge dictionaries
   * - :ref:`__dict.update_shallow__ <func-update-shallow>`
     - Shallow merge dictionaries
   * - :ref:`__dict.from_items__ <func-dict-from-items>`
     - Create a dictionary from key-value pairs

**Standard Library: Datetime Functions**

.. list-table::
   :widths: 20 80
   :header-rows: 1

   * - Function
     - Description
   * - :ref:`__datetime.parse__ <func-datetime-parse>`
     - Parse a natural language date/datetime string
   * - :ref:`__datetime.offset__ <func-datetime-offset>`
     - Offset a date by a given amount
   * - :ref:`__datetime.first__ <func-datetime-first>`
     - Find the first weekday before/after a date
   * - :ref:`__datetime.at__ <func-datetime-at>`
     - Combine a date with a time

.. testsetup:: python

    import smartconfig
    from smartconfig import types
    from pprint import pprint as print


Core Functions
--------------

.. _func-if:

if
~~

Selects between two configurations based on a condition.

**Input**: A dictionary with the following keys:

.. list-table::
   :widths: 15 10 75
   :header-rows: 1

   * - Key
     - Required
     - Description
   * - ``condition``
     - Yes
     - A boolean expression (typically an interpolated string like ``"${x > 5}"``).
   * - ``then``
     - Yes
     - The configuration to use if the condition is true.
   * - ``else``
     - Yes
     - The configuration to use if the condition is false.

**Example**:

.. testcode:: python

    config = {
        "x": 10,
        "y": {"__if__": {"condition": "${x > 5}", "then": 1, "else": 0}}
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "integer"},
            "y": {"type": "integer"}
        }
    }

    print(smartconfig.resolve(config, schema))

This produces:

.. testoutput:: python

    {'x': 10, 'y': 1}

.. _func-let:

let
~~~

Introduces local variables and/or references for use within a subtree.

**Input**: A dictionary with the following keys:

.. list-table::
   :widths: 15 10 75
   :header-rows: 1

   * - Key
     - Required
     - Description
   * - ``variables``
     - No
     - A dictionary of variable bindings. Each key-value pair is resolved and made available as a local variable within the body. At least one of ``variables`` or ``references`` must be provided.
   * - ``references``
     - No
     - A dictionary mapping names to special targets: ``"__this__"`` (the body itself) or ``"__previous__"`` (the previous sibling in a list). These are exposed as unresolved containers. At least one of ``variables`` or ``references`` must be provided.
   * - ``in``
     - Yes
     - The configuration to evaluate with the defined variables and references.

**Example**:

.. testcode:: python

    config = {
        "x": 10,
        "y": {"__let__": {"variables": {"z": 12}, "in": "${z + 2}"}}
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "integer"},
            "y": {"type": "integer"}
        }
    }

    print(smartconfig.resolve(config, schema))

This produces:

.. testoutput:: python

    {'x': 10, 'y': 14}


.. _func-raw:

raw
~~~

Prevents interpolation of ``${...}`` references, preserving them as literal text.

**Input**: Any configuration. The input is returned as-is without interpolation.

**Example**:

.. testcode:: python

    config = {
        "x": {"__raw__": "${y}"},
        "y": 4
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "string"},
            "y": {"type": "integer"}
        }
    }

    print(smartconfig.resolve(config, schema))

This produces:

.. testoutput:: python

    {'x': '${y}', 'y': 4}

.. _func-resolve:

resolve
~~~~~~~

Explicitly resolves the input with a single pass of interpolation. This is the
default behavior, but is useful when referring to a raw template — a reference
like ``${template}`` is expanded once, but any ``${...}`` placeholders in the
result are left as-is.

**Input**: Any configuration. The input is resolved with a single interpolation pass.

**Example**:

.. testcode:: python

    config = {
        "name": "world",
        "template": {"__raw__": "hello ${name}"},
        "result": {"__resolve__": "${template}"}
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "name": {"type": "string"},
            "template": {"type": "string"},
            "result": {"type": "string"}
        }
    }

    print(smartconfig.resolve(config, schema))

This produces:

.. testoutput:: python

    {'name': 'world', 'result': 'hello ${name}', 'template': 'hello ${name}'}

.. _func-fully-resolve:

fully_resolve
~~~~~~~~~~~~~

Resolves the input with repeated interpolation until the result stabilizes.
This is useful when referencing raw strings that themselves contain
interpolation syntax.

Compare with ``__resolve__``, which only performs a single pass. In the
example below, ``__fully_resolve__`` expands ``${template}`` to
``"hello ${name}"``, then expands ``${name}`` to ``"world"``, producing
``"hello world"``.

**Input**: Any configuration. The input is interpolated repeatedly until the string stops changing.

**Example**:

.. testcode:: python

    config = {
        "name": "world",
        "template": {"__raw__": "hello ${name}"},
        "result": {"__fully_resolve__": "${template}"}
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "name": {"type": "string"},
            "template": {"type": "string"},
            "result": {"type": "string"}
        }
    }

    print(smartconfig.resolve(config, schema))

This produces:

.. testoutput:: python

    {'name': 'world', 'result': 'hello world', 'template': 'hello ${name}'}


.. _func-splice:

splice
~~~~~~

Copies a subtree from elsewhere in the configuration.

**Input**: A string keypath (e.g., ``"x.b"``). The node at that keypath is resolved and inserted at the splice location.

**Example**:

.. testcode:: python

    config = {
        "x": {"a": 1, "b": [1, 2, 3]},
        "y": {"__splice__": "x.b"}
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "x": {
                "type": "dict",
                "required_keys": {
                    "a": {"type": "integer"},
                    "b": {"type": "list", "element_schema": {"type": "integer"}}
                }
            },
            "y": {"type": "list", "element_schema": {"type": "integer"}}
        }
    }

    print(smartconfig.resolve(config, schema))

This produces:

.. testoutput:: python

    {'x': {'a': 1, 'b': [1, 2, 3]}, 'y': [1, 2, 3]}

.. _func-template:

template
~~~~~~~~

Defines a reusable template that survives resolution. Unlike ``__raw__``, which
unwraps on resolution (producing plain data), ``__template__`` resolves to a
dictionary ``{"__template__": <contents>}`` that preserves the wrapper. This
means templates persist across resolution boundaries — if a resolved
configuration is serialized and then resolved again, templates are still
recognized. To instantiate a template, use :ref:`__use__ <func-use>`.

**Input**: Any configuration. The input is wrapped in ``{"__template__": ...}``
and ``${...}`` references are preserved as literal text.

**Example**:

.. testcode:: python

    config = {
        "service_template": {"__template__": {"host": "localhost", "port": "${port}"}},
        "port": 8080,
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "service_template": {"type": "any"},
            "port": {"type": "integer"},
        }
    }

    result = smartconfig.resolve(config, schema)
    print(result)

This produces:

.. testoutput:: python

    {'port': 8080,
     'service_template': {'__template__': {'host': 'localhost', 'port': '${port}'}}}

The template wrapper is preserved, and the ``${port}`` reference is kept as
literal text.

Resolving the output a second time produces the same result — the template is
idempotent:

.. testcode:: python

    result2 = smartconfig.resolve(result, schema)
    assert result == result2

.. _func-use:

use
~~~

Copies and resolves a template from elsewhere in the configuration, with
optional overrides. The target keypath must point to a ``__template__`` (or to
something that resolves to a ``{"__template__": ...}`` dictionary).

**Input**: Either a string keypath (simple form) or a dictionary with the following keys:

.. list-table::
   :widths: 15 10 75
   :header-rows: 1

   * - Key
     - Required
     - Description
   * - ``template``
     - Yes
     - A string keypath pointing to the template to copy.
   * - ``overrides``
     - No
     - A dictionary that is deep-merged on top of the template contents before resolution.

**Example (simple)**:

A common pattern is to define a template containing ``${...}`` references.
When ``__use__`` copies the template, the references are resolved in the context
of the destination:

.. testcode:: python

    config = {
        "greeting_template": {"__template__": "Hello, ${name}!"},
        "name": "Alice",
        "message": {"__use__": "greeting_template"},
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "greeting_template": {"type": "any"},
            "name": {"type": "string"},
            "message": {"type": "string"},
        }
    }

    print(smartconfig.resolve(config, schema))

.. testoutput:: python

    {'greeting_template': {'__template__': 'Hello, ${name}!'},
     'message': 'Hello, Alice!',
     'name': 'Alice'}

Notice that the template itself remains wrapped (the ``${name}`` reference is
preserved inside the ``__template__`` wrapper), but the copy produced by
``__use__`` has ``${name}`` resolved to ``"Alice"``.

**Example (with overrides)**:

When the template resolves to a dictionary, ``__use__`` accepts an ``overrides``
key that is deep-merged on top of the template contents before resolution. This
lets you define shared defaults in one place and selectively override individual
fields at each use site:

.. testcode:: python

    config = {
        "defaults": {"__template__": {"host": "localhost", "port": 8080}},
        "server": {
            "__use__": {
                "template": "defaults",
                "overrides": {"port": 9090}
            }
        },
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "defaults": {"type": "any"},
            "server": {
                "type": "dict",
                "required_keys": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                }
            },
        }
    }

    print(smartconfig.resolve(config, schema))

.. testoutput:: python

    {'defaults': {'__template__': {'host': 'localhost', 'port': 8080}},
     'server': {'host': 'localhost', 'port': 9090}}


List Operations
---------------

.. _func-loop:

list.loop
~~~~~~~~~

Generates a list by iterating over a sequence and evaluating a body for each element.

**Input**: A dictionary with the following keys:

.. list-table::
   :widths: 15 10 75
   :header-rows: 1

   * - Key
     - Required
     - Description
   * - ``variable``
     - Yes
     - The name of the loop variable.
   * - ``over``
     - Yes
     - The list to iterate over.
   * - ``in``
     - Yes
     - The configuration to evaluate for each element. The loop variable is available for interpolation.

**Example**:

.. testcode:: python

    config = {
        "x": 3,
        "y": {"__list.loop__": {"variable": "i", "over": [1, 2, 3], "in": "${i * x}"}}
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "integer"},
            "y": {"type": "list", "element_schema": {"type": "integer"}}
        }
    }

    print(smartconfig.resolve(config, schema))

This produces:

.. testoutput:: python

    {'x': 3, 'y': [3, 6, 9]}

.. _func-range:

list.range
~~~~~~~~~~

Generates a list of integers, similar to Python's ``range()``.

**Input**: A dictionary with the following keys:

.. list-table::
   :widths: 15 10 75
   :header-rows: 1

   * - Key
     - Required
     - Description
   * - ``start``
     - No
     - The start of the range (inclusive). Defaults to 0.
   * - ``stop``
     - Yes
     - The end of the range (exclusive).
   * - ``step``
     - No
     - The step between elements. Defaults to 1.

**Example**:

.. testcode:: python

    config = {
        "y": {"__list.range__": {"start": 0, "stop": 10, "step": 2}}
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "y": {"type": "list", "element_schema": {"type": "integer"}}
        }
    }

    print(smartconfig.resolve(config, schema))

This produces:

.. testoutput:: python

    {'y': [0, 2, 4, 6, 8]}

.. _func-filter:

list.filter
~~~~~~~~~~~

Filters a list by evaluating a condition for each element.

**Input**: A dictionary with the following keys:

.. list-table::
   :widths: 15 10 75
   :header-rows: 1

   * - Key
     - Required
     - Description
   * - ``iterable``
     - Yes
     - The list to filter.
   * - ``variable``
     - Yes
     - The name of the variable assigned to each element.
   * - ``condition``
     - Yes
     - A boolean expression evaluated for each element. Elements for which the condition is true are kept.

**Example**:

.. testcode:: python

    config = {
        "__list.filter__": {
            "iterable": [1, 2, 3, 4, 5],
            "variable": "item",
            "condition": "${item % 2 == 0}"
        }
    }

    schema = {"type": "list", "element_schema": {"type": "integer"}}

    print(smartconfig.resolve(config, schema))

This produces:

.. testoutput:: python

    [2, 4]

.. _func-zip:

list.zip
~~~~~~~~

Zips lists together, producing a list of lists.

**Input**: A list of lists.

**Example**:

.. testcode:: python

    config = {"__list.zip__": [[1, 2, 3], [4, 5, 6]]}

    schema = {
        "type": "list",
        "element_schema": {"type": "list", "element_schema": {"type": "integer"}}
    }

    print(smartconfig.resolve(config, schema))

This produces:

.. testoutput:: python

    [[1, 4], [2, 5], [3, 6]]

.. _func-concatenate:

list.concatenate
~~~~~~~~~~~~~~~~

Concatenates multiple lists into one.

**Input**: A list of lists.

**Example**:

.. testcode:: python

    config = {"x": {"__list.concatenate__": [[1, 2], [3, 4]]}}

    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "list", "element_schema": {"type": "integer"}}
        }
    }

    print(smartconfig.resolve(config, schema))

This produces:

.. testoutput:: python

    {'x': [1, 2, 3, 4]}


Dictionary Operations
---------------------

.. _func-update:

dict.update
~~~~~~~~~~~

Deep merges dictionaries, with later dictionaries taking precedence. Nested
dictionaries are merged recursively.

**Input**: A list of dictionaries.

**Example**:

.. testcode:: python

    config = {
        "x": {"__dict.update__": [{"a": {"foo": 1}}, {"a": {"bar": 2}}]}
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "x": {
                "type": "dict",
                "required_keys": {
                    "a": {
                        "type": "dict",
                        "required_keys": {
                            "foo": {"type": "integer"},
                            "bar": {"type": "integer"}
                        }
                    }
                }
            }
        }
    }

    print(smartconfig.resolve(config, schema))

This produces:

.. testoutput:: python

    {'x': {'a': {'bar': 2, 'foo': 1}}}

.. _func-update-shallow:

dict.update_shallow
~~~~~~~~~~~~~~~~~~~

Shallow merges dictionaries, with later dictionaries taking precedence. Unlike
``dict.update``, nested dictionaries are not merged recursively.

**Input**: A list of dictionaries.

**Example**:

.. testcode:: python

    config = {
        "x": {"__dict.update_shallow__": [{"a": 3, "b": 4}, {"b": 5}]}
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "x": {
                "type": "dict",
                "required_keys": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"}
                }
            }
        }
    }

    print(smartconfig.resolve(config, schema))

This produces:

.. testoutput:: python

    {'x': {'a': 3, 'b': 5}}

.. _func-dict-from-items:

dict.from_items
~~~~~~~~~~~~~~~

Creates a dictionary from a list of key-value pairs.

**Input**: A list of dictionaries, each with the following keys:

.. list-table::
   :widths: 15 10 75
   :header-rows: 1

   * - Key
     - Required
     - Description
   * - ``key``
     - Yes
     - The key for the dictionary entry.
   * - ``value``
     - Yes
     - The value for the dictionary entry.

**Example**:

.. testcode:: python

    config = {
        "__dict.from_items__": [
            {"key": "x", "value": 10},
            {"key": "y", "value": 20}
        ]
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "integer"},
            "y": {"type": "integer"}
        }
    }

    print(smartconfig.resolve(config, schema))

This produces:

.. testoutput:: python

    {'x': 10, 'y': 20}


Datetime Operations
-------------------

.. _func-datetime-parse:

datetime.parse
~~~~~~~~~~~~~~

Parses a natural language date/datetime string.

**Input**: A string in one of the following forms:

- An ISO date or datetime: ``"2021-10-05"`` or ``"2021-10-05 23:59:10"``
- An offset: ``"3 days after 2021-10-05"`` (multiple units can be comma-separated,
  e.g., ``"1 week, 2 days after 2021-10-05"``)
- A first-weekday: ``"first monday after 2021-09-14"`` (multiple day names can be
  separated by commas, e.g., ``"first monday, wednesday after 2021-09-14"``)

Any form may end with ``" at HH:MM:SS"`` to override the time component.

**Example**:

.. testcode:: python

    import datetime

    config = {
        "start": "2025-09-01",
        "first_tuesday": {"__datetime.parse__": "first tuesday after ${start}"},
        "later": {"__datetime.parse__": "1 week, 2 days after ${start}"},
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "start": {"type": "date"},
            "first_tuesday": {"type": "date"},
            "later": {"type": "date"},
        }
    }

    print(smartconfig.resolve(config, schema))

This produces:

.. testoutput:: python

    {'first_tuesday': datetime.date(2025, 9, 2),
     'later': datetime.date(2025, 9, 10),
     'start': datetime.date(2025, 9, 1)}

.. _func-datetime-offset:

datetime.offset
~~~~~~~~~~~~~~~

Offsets a date or datetime by a given amount.

**Input**: A dictionary with the following keys:

.. list-table::
   :widths: 15 10 75
   :header-rows: 1

   * - Key
     - Required
     - Description
   * - ``before``
     - No
     - The reference date to offset backward from. Mutually exclusive with ``after``; exactly one must be provided.
   * - ``after``
     - No
     - The reference date to offset forward from. Mutually exclusive with ``before``; exactly one must be provided.
   * - ``by``
     - Yes
     - The offset amount. Either a string like ``"7 days"`` or ``"1 week, 2 days"``, or a dictionary like ``{"weeks": 1, "days": 2}``. Valid units are ``weeks``, ``days``, ``hours``, ``minutes``, and ``seconds``.
   * - ``skip``
     - No
     - A list of dates to skip over. If the result lands on a skipped date, it advances in the same direction until a non-skipped date is found.

**Example**:

.. testcode:: python

    import datetime

    config = {
        "start": "2025-01-10",
        "one_week_later": {
            "__datetime.offset__": {
                "after": "${start}",
                "by": "1 week",
            }
        }
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "start": {"type": "date"},
            "one_week_later": {"type": "date"},
        }
    }

    print(smartconfig.resolve(config, schema))

This produces:

.. testoutput:: python

    {'one_week_later': datetime.date(2025, 1, 17),
     'start': datetime.date(2025, 1, 10)}

.. _func-datetime-first:

datetime.first
~~~~~~~~~~~~~~

Finds the first occurrence of a given weekday before or after a reference date.

**Input**: A dictionary with the following keys:

.. list-table::
   :widths: 15 10 75
   :header-rows: 1

   * - Key
     - Required
     - Description
   * - ``weekday``
     - Yes
     - A day name (e.g., ``"monday"``) or comma-separated list of day names (e.g., ``"monday, friday"``).
   * - ``before``
     - No
     - The reference date to search backward from. Mutually exclusive with ``after``; exactly one must be provided.
   * - ``after``
     - No
     - The reference date to search forward from. Mutually exclusive with ``before``; exactly one must be provided.
   * - ``skip``
     - No
     - A list of dates to skip over. If the result lands on a skipped date, the search continues in the same direction.

**Example**:

.. testcode:: python

    import datetime

    config = {
        "start": "2025-09-01",
        "first_friday": {
            "__datetime.first__": {
                "weekday": "friday",
                "after": "${start}",
            }
        }
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "start": {"type": "date"},
            "first_friday": {"type": "date"},
        }
    }

    print(smartconfig.resolve(config, schema))

This produces:

.. testoutput:: python

    {'first_friday': datetime.date(2025, 9, 5), 'start': datetime.date(2025, 9, 1)}

.. _func-datetime-at:

datetime.at
~~~~~~~~~~~

Combines a date (or datetime) with a time, producing a datetime.

**Input**: A dictionary with the following keys:

.. list-table::
   :widths: 15 10 75
   :header-rows: 1

   * - Key
     - Required
     - Description
   * - ``date``
     - Yes
     - The reference date or datetime.
   * - ``time``
     - Yes
     - A time string in ISO format (e.g., ``"23:59:00"``).

**Example**:

.. testcode:: python

    import datetime

    config = {
        "start": "2025-01-10",
        "deadline": {
            "__datetime.at__": {
                "date": "${start}",
                "time": "23:59:00",
            }
        }
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "start": {"type": "date"},
            "deadline": {"type": "datetime"},
        }
    }

    print(smartconfig.resolve(config, schema))

This produces:

.. testoutput:: python

    {'deadline': datetime.datetime(2025, 1, 10, 23, 59),
     'start': datetime.date(2025, 1, 10)}


Jinja2 Features
---------------

:func:`smartconfig.resolve` uses the Jinja2 template engine for interpolation.
This means that many Jinja2 features can be used within ``${...}`` expressions.

Ternary Operator
~~~~~~~~~~~~~~~~

Jinja2 supports inline conditionals:

.. testcode:: python

    config = {
        "x": 10,
        "y": 3,
        "z": "${ x if x > y else y }"
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "integer"},
            "y": {"type": "integer"},
            "z": {"type": "integer"}
        }
    }

    print(smartconfig.resolve(config, schema))

.. testoutput:: python

    {'x': 10, 'y': 3, 'z': 10}

Filters
~~~~~~~

Jinja2 filters transform values during interpolation. Built-in filters like
``capitalize``, ``lower``, and ``upper`` work as expected:

.. testcode:: python

    config = {
        "x": "hello",
        "y": "world",
        "z": "${ x | capitalize } ${ y | upper }"
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "string"},
            "y": {"type": "string"},
            "z": {"type": "string"}
        }
    }

    print(smartconfig.resolve(config, schema))

.. testoutput:: python

    {'x': 'hello', 'y': 'world', 'z': 'Hello WORLD'}

Custom filters can be provided via the ``filters`` keyword argument to
:func:`smartconfig.resolve`.
