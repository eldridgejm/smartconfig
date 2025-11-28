Default Functions
=================

`smartconfig` allows for dynamic behavior in configurations via **functions**.
A set of built-in functions is provided which implement control flow,
list manipulation, and dictionary merging. Custom functions can also be defined;
see :doc:`custom_functions` for more information. The default functions are
implemented in the :mod:`smartconfig.functions` module.

Functions are invoked in configurations using the syntax ``{"__function_name__": ...}``.
For example, ``{"__if__": {"condition": "...", "then": ..., "else": ...}}`` calls
the ``if`` function.

The default functions available to use with :func:`smartconfig.resolve` are summarized in the table below:

.. list-table::
   :widths: 20 80
   :header-rows: 1

   * - Function
     - Description
   * - :ref:`__if__ <func-if>`
     - Conditional logic
   * - :ref:`__let__ <func-let>`
     - Define local variables
   * - :ref:`__loop__ <func-loop>`
     - Generate a list by iteration
   * - :ref:`__range__ <func-range>`
     - Generate a list of numbers
   * - :ref:`__filter__ <func-filter>`
     - Filter a list by condition
   * - :ref:`__zip__ <func-zip>`
     - Zip lists together
   * - :ref:`__concatenate__ <func-concatenate>`
     - Concatenate lists
   * - :ref:`__splice__ <func-splice>`
     - Copy another part of the configuration
   * - :ref:`__update__ <func-update>`
     - Deep merge dictionaries
   * - :ref:`__update_shallow__ <func-update-shallow>`
     - Shallow merge dictionaries
   * - :ref:`__dict_from_items__ <func-dict-from-items>`
     - Create a dictionary from key-value pairs
   * - :ref:`__raw__ <func-raw>`
     - Prevent interpolation
   * - :ref:`__recursive__ <func-recursive>`
     - Force repeated interpolation

.. testsetup:: python

    import smartconfig
    from smartconfig import types
    from pprint import pprint as print


Control Flow
------------

.. _func-if:

if
~~

Conditional logic using ``__if__``. The argument is a dictionary with
``condition``, ``then``, and ``else`` keys.

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

**Output**:

.. testoutput:: python

    {'x': 10, 'y': 1}

.. _func-let:

let
~~~

Define local variables using ``__let__``. The argument is a dictionary with
``variables`` (a dictionary of variable bindings) and ``in`` (the expression
to evaluate with those variables).

**Example**:

.. testcode:: python

    config = {
        "x": 10,
        "y": {"__let__": {"variables": {"z": 12}, "in": "${z} + 2"}}
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "integer"},
            "y": {"type": "integer"}
        }
    }

    print(smartconfig.resolve(config, schema))

**Output**:

.. testoutput:: python

    {'x': 10, 'y': 14}


List Operations
---------------

.. _func-loop:

loop
~~~~

Generate a list using ``__loop__``. The argument is a dictionary with
``variable`` (the loop variable name), ``over`` (the iterable), and ``in``
(the expression to evaluate for each element).

**Example**:

.. testcode:: python

    config = {
        "x": 3,
        "y": {"__loop__": {"variable": "i", "over": [1, 2, 3], "in": "${i * x}"}}
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "integer"},
            "y": {"type": "list", "element_schema": {"type": "integer"}}
        }
    }

    print(smartconfig.resolve(config, schema))

**Output**:

.. testoutput:: python

    {'x': 3, 'y': [3, 6, 9]}

.. _func-range:

range
~~~~~

Generate a list of numbers using ``__range__``. The argument is a dictionary
with ``stop`` (required), and optionally ``start`` (defaults to 0) and ``step``
(defaults to 1).

**Example**:

.. testcode:: python

    config = {
        "y": {"__range__": {"start": 0, "stop": 10, "step": 2}}
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "y": {"type": "list", "element_schema": {"type": "integer"}}
        }
    }

    print(smartconfig.resolve(config, schema))

**Output**:

.. testoutput:: python

    {'y': [0, 2, 4, 6, 8]}

.. _func-filter:

filter
~~~~~~

Filter a list using ``__filter__``. The argument is a dictionary with
``iterable``, ``variable`` (the name for each element), and ``condition``.

**Example**:

.. testcode:: python

    config = {
        "__filter__": {
            "iterable": [1, 2, 3, 4, 5],
            "variable": "item",
            "condition": "${item % 2 == 0}"
        }
    }

    schema = {"type": "list", "element_schema": {"type": "integer"}}

    print(smartconfig.resolve(config, schema))

**Output**:

.. testoutput:: python

    [2, 4]

.. _func-zip:

zip
~~~

Zip lists together using ``__zip__``. The argument is a list of lists.

**Example**:

.. testcode:: python

    config = {"__zip__": [[1, 2, 3], [4, 5, 6]]}

    schema = {
        "type": "list",
        "element_schema": {"type": "list", "element_schema": {"type": "integer"}}
    }

    print(smartconfig.resolve(config, schema))

**Output**:

.. testoutput:: python

    [[1, 4], [2, 5], [3, 6]]

.. _func-concatenate:

concatenate
~~~~~~~~~~~

Concatenate lists using ``__concatenate__``. The argument is a list of lists.

**Example**:

.. testcode:: python

    config = {"x": {"__concatenate__": [[1, 2], [3, 4]]}}

    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "list", "element_schema": {"type": "integer"}}
        }
    }

    print(smartconfig.resolve(config, schema))

**Output**:

.. testoutput:: python

    {'x': [1, 2, 3, 4]}


Dictionary Operations
---------------------

.. _func-splice:

splice
~~~~~~

Copy another part of the configuration using ``__splice__``. The argument is a
keypath string.

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

**Output**:

.. testoutput:: python

    {'x': {'a': 1, 'b': [1, 2, 3]}, 'y': [1, 2, 3]}

.. _func-update:

update
~~~~~~

Deep merge dictionaries using ``__update__``. The argument is a list of
dictionaries to merge, with later dictionaries taking precedence.

**Example**:

.. testcode:: python

    config = {
        "x": {"__update__": [{"a": {"foo": 1}}, {"a": {"bar": 2}}]}
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

**Output**:

.. testoutput:: python

    {'x': {'a': {'bar': 2, 'foo': 1}}}

.. _func-update-shallow:

update_shallow
~~~~~~~~~~~~~~

Shallow merge dictionaries using ``__update_shallow__``. Unlike ``update``,
this does not merge nested dictionaries recursively.

**Example**:

.. testcode:: python

    config = {
        "x": {"__update_shallow__": [{"a": 3, "b": 4}, {"b": 5}]}
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

**Output**:

.. testoutput:: python

    {'x': {'a': 3, 'b': 5}}

.. _func-dict-from-items:

dict_from_items
~~~~~~~~~~~~~~~

Create a dictionary from key-value pairs using ``__dict_from_items__``. The
argument is a list of dictionaries, each with ``key`` and ``value`` keys.

**Example**:

.. testcode:: python

    config = {
        "__dict_from_items__": [
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

**Output**:

.. testoutput:: python

    {'x': 10, 'y': 20}


String Handling
---------------

.. _func-raw:

raw
~~~

Prevent interpolation using ``__raw__``. The argument is a string that will
not be interpolated or converted.

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

**Output**:

.. testoutput:: python

    {'x': '${y}', 'y': 4}

.. _func-recursive:

recursive
~~~~~~~~~

Force repeated interpolation using ``__recursive__``. The argument is a string
that will be interpolated repeatedly until it stops changing. This is useful
when referencing raw strings that themselves contain interpolation syntax.

**Example**:

.. testcode:: python

    config = {
        "x": 5,
        "y": {"__raw__": "${x} + 1"},
        "z": {"__recursive__": "${y} + 2"}
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "integer"},
            "y": {"type": "string"},
            "z": {"type": "integer"}
        }
    }

    print(smartconfig.resolve(config, schema))

**Output**:

.. testoutput:: python

    {'x': 5, 'y': '${x} + 1', 'z': 8}


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
