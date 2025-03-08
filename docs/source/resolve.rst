Resolution
==========

.. module:: smartconfig

.. testsetup:: python

    import smartconfig
    from smartconfig import types
    from pprint import pprint as print

A configuration is resolved using the :func:`smartconfig.resolve` function. In
many cases, using :func:`smartconfig.resolve` is as simple as providing a
configuration and a schema:

.. testcode:: python

   import smartconfig

   config = {
       "x": 10,
       "y": "${x} + 1"
   }

   schema = {
       "type": "dict",
       "required_keys": {
           "x": {"type": "integer"},
           "y": {"type": "integer"}
       }
   }

   result = smartconfig.resolve(config, schema)
   print(result)

This will output:

.. testoutput:: python

    {'x': 10, 'y': 11}

More complex use cases are supported by providing additional arguments.
The full signature of :func:`smartconfig.resolve` is:

.. function:: resolve(...) -> Configuration

    Resolve a configuration by interpolating and parsing its entries.

    Parameters
    ----------
    cfg : :class:`types.Configuration`
        The "raw" configuration to resolve.
    schema : :class:`types.Schema`
        The schema describing the structure of the resolved configuration.
        See: :ref:`schemas`.
    converters : Mapping[str, Callable]
        A dictionary mapping value types (as strings) to converter functions.
        The converter functions should take the raw value (after interpolation)
        and convert it to the specified type.

        If this argument not provided, the default converters in
        :data:`DEFAULT_CONVERTERS` are used. See: :ref:`converters` for more information
        on the built-in converters and how to define custom converters.
    functions : Mapping[str, Union[Callable, :class:`types.Function`]]
        A mapping of function names to functions. The functions should either be basic
        Python functions accepting an instance of :class:`types.FunctionArgs` as input
        and returning a :class:`types.Configuration`, or they should be
        :class:`smartconfig.types.Function` instances.

        If this argument is not provided, the
        default functions in :data:`DEFAULT_FUNCTIONS` are used. If it is ``None``, no
        functions are made available.
        See: :ref:`function-calls` for more information on the built-in functions and
        how to define custom functions.
    global_variables : Optional[Mapping[str, Any]]
        A dictionary of global variables to make available during string interpolation.
        If this is not provided, no global variables are available.

        Global variables are not interpolated or parsed. For this reason, they are
        mostly used to provide extra functions to the string interpolation
        engine. If you wish to provide external variables, it is suggested to
        include them in the configuration itself as shown in
        :ref:`recipes_external_variables`.
    inject_root_as : Optional[str]
        If this is not None, the root of the configuration tree is made
        available during string interpolation as a variable with this name.
        The root is passed as an :class:`types.UnresolvedDict`,
        :class:`types.UnresolvedList`, or
        :class:`types.UnresolvedFunctionCall`. Defaults to ``None``.

        It is suggested to avoid this and instead include use the convention in
        :ref:`recipes_external_variables`.
    filters : Optional[Mapping[str, Callable]]
        A dictionary of Jinja2 filters to make available to templates. These will be
        added to Jinja2's set of default filters. If ``None``, no custom filters are
        provided. Defaults to ``None``.
    preserve_type : bool (default: False)
        If False, the return value of this function is a plain Python
        dictionary or list. If this is True, however, `smartconfig` will
        attempt to return an object of the same type as the input ``cfg``.
        This is most useful in cases where the input is of a custom mapping type
        (such as an ordered dictionary) that should be preserved in the output.
        See :ref:`type-preservation` below for more information.
    check_for_function_call : :class:`types.FunctionCallChecker`
        A function that checks if a :class:`types.ConfigurationDict` represents a
        function call. It is given the configuration and the available functions. If it
        is determined to be a function call, it returns a 2-tuple of the
        :class:`types.Function` and the input to the function. If not, it
        returns None. If it is determined to be a malformed function call, it
        should raise a ``ValueError``.

        If this argument is not provided, a default implementation is used that
        assumes function calls are dictionaries with a single key of the form
        ``__<function_name>__``. If set to None, function calls are effectively
        disabled.

        See: :ref:`customizing-function-call-syntax` for more information.

    Raises
    ------
    :class:`exceptions.InvalidSchemaError`
        If the schema is not valid.
    :class:`exceptions.ResolutionError`
        If the configuration does not match the schema, if there is a circular
        reference, or there is some other issue with the configuration itself.

Default Converters
------------------

After configuration values are interpolated, they are passed to a converter function
that attempts to convert them to the appropriate type (as determined by the schema).
The converters are responsible for both converting the value and validating that it is
of the correct type.

The default converters used in :func:`resolve` are defined in
:data:`DEFAULT_CONVERTERS`:

.. data:: DEFAULT_CONVERTERS

    A mapping of default converters. Keys are strings representing the value types
    ("integer", "float", "string", "boolean", "date", "datetime"), and values are
    converter functions.

Detailed information about the convertes is found in :ref:`converters`, but in summary,
the default converters are:

- **integer**: parses basic arithmetic expressions, like ``1 + 2`` and checks that the result is an integer. See: :func:`smartconfig.converters.arithmetic`.
- **float**: parses basic arithmetic expressions, like ``1.0 + 2.3`` and checks that the result is a float. See: :func:`smartconfig.converters.arithmetic`.
- **string**: converts the value to a string using ``str``.
- **boolean**:
  Allows for basic boolean logic, like
  ``true and not (false or true)``. See: :func:`smartconfig.converters.logic`.
- **date**:  Allows for natural language dates,
  like ``"7 days after 2025-01-01"``. See: :func:`smartconfig.converters.smartdate`.
- **datetime**: Allows for natural language
  datetimes, like ``"7 days after 2025-01-01 12:00:00"``. See: :func:`smartconfig.converters.smartdatetime`.

In general, if a converter is provided an instance of the type it is supposed to
convert to, it returns it unchanged. For instance, a converter to "datetime" that
is given a Python `datetime` returns a `datetime`.

To override the default converters, simply provide a different mapping from the possible
value types to converter functions to the ``converters`` keyword argument of
:func:`resolve`. The :data:`DEFAULT_CONVERTERS` dictionary should not be
modified directly, but it can be copied and modified.

Default Functions
-----------------

:func:`resolve` allows configurations to contain function calls. During a
function call, the function is evaluated and the result is inserted into the
configuration.

`smartconfig` provides several built-in functions for convenience. These are
implemented in :mod:`smartconfig.functions`. The default functions available to
:func:`resolve` are defined in :data:`DEFAULT_FUNCTIONS`:

.. data:: DEFAULT_FUNCTIONS

    A mapping of default functions. Keys are strings representing the function names,
    and values are instances of :class:`types.Function`.

To override the default functions or provide your own, copy :data:`DEFAULT_FUNCTIONS`
and modify it as needed.

The default functions are described in more detail in :ref:`function-calls`.
In summary, they are:

- :ref:`raw-builtin`: Designate that the argument is a :class:`RawString` and should not be interpolated or parsed. See :ref:`special-strings` below.
- :ref:`recursive-builtin`: Designate that the argument is a :class:`RecursiveString` and should be interpolated repeatedly until it stops changing. See :ref:`special-strings` below.
- :ref:`splice-builtin`: Copies another part of the configuration. The single argument is a keypath to the part to copy.
- :ref:`if-builtin`: A simple if-else statement.
- :ref:`loop-builtin`: Generates a list using a for loop.
- :ref:`let-builtin`: Assigns a value to a variable.
- :ref:`range-builtin`: Generates a list of numbers.
- :ref:`zip-builtin`: Zips two lists together.
- :ref:`concatenate-builtin`: Concatenates a list of lists.
- :ref:`filter-builtin`: Filters a list.
- :ref:`dict_from_items-builtin`: Creates a dictionary from a list of key-value pairs.
- :ref:`update-shallow-builtin`: Updates a dictionary by merging another dictionary into it. The argument should be a list of dictionaries to merge. Unlike ``update``, this does not operate recursively.
- :ref:`update-builtin`: Like ``update-shallow``, but operates recursively.

.. _raw-builtin:
raw
~~~

Designate that the argument is a :class:`RawString` and should not be interpolated or
parsed. See :ref:`special-strings` below. Implemented by
:func:`smartconfig.functions.raw`.

**Example**:

.. testcode:: python

    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "string"},
            "y": {"type": "integer"}
        }
    }

    config = {
         "x": {"__raw__": "${y}"},
         "y": 4
    }

    result = smartconfig.resolve(config, schema)
    print(result)

This resolves to:

.. testoutput:: python

    {'x': '${y}', 'y': 4}

.. _recursive-builtin:
recursive
~~~~~~~~~

Designate that the argument is a :class:`RecursiveString` and should be interpolated
repeatedly until it stops changing. See :ref:`special-strings` below. Implemented by
:func:`smartconfig.functions.recursive`.

**Example**:

.. testcode:: python

   schema = {
       "type": "dict",
       "required_keys": {
           "x": {"type": "integer"},
           "y": {"type": "string"},
           "z": {"type": "integer"}
       }
   }

   config = {
       "x": 5,
       "y": {"__raw__": "${x} + 1"},
       "z": {"__recursive__": "${y} + 2"}
   }

   print(smartconfig.resolve(config, schema))

This resolves to:

.. testoutput:: python

    {'x': 5, 'y': '${x} + 1', 'z': 8}

.. _splice-builtin:
splice
~~~~~~

Copies a another part of the configuration. The single argument is a
keypath to the part to copy. Implemented by :func:`smartconfig.functions.splice`.

**Example**:

.. testcode:: python

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

    config = {
        "x": {"a": 1, "b": [1 ,2 ,3]},
        "y": {"__splice__": "x.b"}
    }

    print(smartconfig.resolve(config, schema))

This resolves to:

.. testoutput:: python

    {'x': {'a': 1, 'b': [1, 2, 3]}, 'y': [1, 2, 3]}

.. _if-builtin:

if
~~

A simple if-else statement. Implemented by :func:`smartconfig.functions.if_`.

**Example**:

.. testcode:: python

    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "integer"},
            "y": {"type": "integer"}
        }
    }

    config = {
        "x": 10,
        "y": {"__if__": {"condition": "${x > 5}", "then": 1, "else": 0}}
    }

    print(smartconfig.resolve(config, schema))

This resolves to:

.. testoutput:: python

    {'x': 10, 'y': 1}

.. _loop-builtin:

loop
~~~~

Generates a list using a for loop. Implemented by :func:`smartconfig.functions.loop`.

**Example**:

.. testcode:: python

    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "integer"},
            "y": {"type": "list", "element_schema": {"type": "integer"}}
        }
    }

    config = {
        "x": 3,
        "y": {"__loop__": {"variable": "i", "over": [1, 2, 3], "in": "${i * x}"}}
    }

    print(smartconfig.resolve(config, schema))

The result is:

.. testoutput:: python

    {'x': 3, 'y': [3, 6, 9]}


.. _let-builtin:

let
~~~

Assigns a value to a variable. Implemented by :func:`smartconfig.functions.let`.

**Example**:

.. testcode:: python

    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "integer"},
            "y": {"type": "integer"}
        }
    }

    config = {
        "x": 10,
        "y": {"__let__": {"variables": {"z": 12}, "in": "${z} + 2"}}
    }

    print(smartconfig.resolve(config, schema))

This resolves to:

.. testoutput:: python

    {'x': 10, 'y': 14}

.. _range-builtin:

range
~~~~~

Generates a list of numbers. Implemented by :func:`smartconfig.functions.range_`.

**Example**:

.. testcode:: python

    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "integer"},
            "y": {"type": "list", "element_schema": {"type": "integer"}}
        }
    }

    config = {
        "x": 10,
        "y": {
            "__range__": {
                "start": 0,
                "stop": 10,
                "step": 2
            }
        }
    }

    print(smartconfig.resolve(config, schema))

This resolves to:

.. testoutput:: python

    {'x': 10, 'y': [0, 2, 4, 6, 8]}

.. _zip-builtin:

zip
~~~

Zips two lists together. Implemented by :func:`smartconfig.functions.zip`.

**Example**:

.. testcode:: python

    schema = {
        "type": "list",
        "element_schema": {"type": "list", "element_schema": {"type": "integer"}}
    }

    config = {
        "__zip__": [[1, 2, 3], [4, 5, 6]]
    }

    print(smartconfig.resolve(config, schema))

This resolves to:

.. testoutput:: python

    [[1, 4], [2, 5], [3, 6]]

.. _concatenate-builtin:

concatenate
~~~~~~~~~~~

Concatenates a list of lists. Implemented by :func:`smartconfig.functions.concatenate`.

**Example**:

.. testcode:: python

   schema = {
       "type": "dict",
       "required_keys": {
           "x": {"type": "list", "element_schema": {"type": "integer"}}
       }
   }

   config = {
       "x": {"__concatenate__": [[1, 2], [3, 4]]}
   }

   print(smartconfig.resolve(config, schema))

This resolves to:

.. testoutput:: python

  {'x': [1, 2, 3, 4]}

.. _filter-builtin:

filter
~~~~~~

Filters a list. Implemented by :func:`smartconfig.functions.filter_`.

**Example**:

.. testcode:: python

    schema = {
        "type": "list",
        "element_schema": {"type": "integer"}
    }

    config = {
        "__filter__": {
            "iterable": [1, 2, 3, 4, 5],
            "variable": "item",
            "condition": "${item % 2 == 0}"
        }
    }

    print(smartconfig.resolve(config, schema))

This resolves to:

.. testoutput:: python

    [2, 4]

.. _dict_from_items-builtin:

dict_from_items
~~~~~~~~~~~~~~~

Creates a dictionary from a list of key-value pairs. Implemented by
:func:`smartconfig.functions.dict_from_items`.

**Example**:

.. testcode:: python

    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "integer"},
            "y": {"type": "integer"}
        }
    }

    config = {
        "__dict_from_items__": [
            {"key": "x", "value": 10},
            {"key": "y", "value": 20}
        ]
    }

    print(smartconfig.resolve(config, schema))

This resolves to:

.. testoutput:: python

    {'x': 10, 'y': 20}

.. _update-shallow-builtin:

update_shallow
~~~~~~~~~~~~~~

Updates a dictionary by merging another dictionary into it.
The argument should be a list of dictionaries to merge. Unlike ``update``, this
does not operate recursively. Implemented by :func:`smartconfig.functions.update_shallow`.

**Example**:

.. testcode:: python

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

    config = {
        "x": {"__update_shallow__": [{"a": 3, "b": 4}, {"b": 5}]}
    }

    print(smartconfig.resolve(config, schema))

This resolves to:

.. testoutput:: python

    {'x': {'a': 3, 'b': 5}}

.. _update-builtin:

update
~~~~~~

Like ``update_shallow``, but operates recursively. Implemented by
:func:`smartconfig.functions.update`.

**Example**:

.. testcode:: python

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

    config = {
        "x": {"__update__": [{"a": {"foo": 1}}, {"a": {"bar": 2}}]}
    }

    print(smartconfig.resolve(config, schema))

This resolves to:

.. testoutput:: python

    {'x': {'a': {'bar': 2, 'foo': 1}}}


Jinja2 Features
----------------

:func:`resolve` uses the `jinja2` template engine for interpolation. This means that
many powerful `Jinja2` features can be used. For example, `Jinja2` supports a
ternary operator, so dictionaries can contain expressions like the following:

.. testcode:: python

    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "integer"},
            "y": {"type": "integer"},
            "z": {"type": "integer"}
        }
    }

    config = {
        'x': 10,
        'y': 3,
        'z': '${ x if x > y else y }'
    }

    print(smartconfig.resolve(config, schema))

The result will be:

.. testoutput:: python

    {'x': 10, 'y': 3, 'z': 10}

Control Flow
~~~~~~~~~~~~

Jinja2 allows the use of more advanced control flow constructs, like `for`
loops and `if` statements, within string interpolation. For example:

.. testcode:: python

    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "integer"},
            "y": {"type": "integer"},
            "z": {"type": "string"}
        }
    }

    config = {
        'x': 10,
        'y': 3,
        'z': '{% for i in range(x) %}${ i } {% endfor %}'
    }

    print(smartconfig.resolve(config, schema))

The result is:

.. testoutput:: python

    {'x': 10, 'y': 3, 'z': '0 1 2 3 4 5 6 7 8 9 '}

.. note::

   The result of the `for` loop is a **string**, not a *list*, since Jinja2 is a
   templating engine and not a programming language. However, a built-in
   :func:`smartconfig.functions.loop` function is provided that can be used to
   generate lists.

Filters
~~~~~~~

Jinja2 filters are functions that can be applied during string interpolation. Jinja
provides many built-in filters, such as ``capitalize``, ``lower``, and ``upper``. These
work as expected:

.. testcode:: python

    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "string"},
            "y": {"type": "string"},
            "z": {"type": "string"}
        }
    }

    config = {
        'x': 'hello',
        'y': 'world',
        'z': '${ x | capitalize } ${ y | upper }'
    }

    print(smartconfig.resolve(config, schema))

The result is:

.. testoutput:: python

    {'x': 'hello', 'y': 'world', 'z': 'Hello WORLD'}

Custom filters can also be provided via the `filters` keyword argument.

.. testcode:: python

    schema = {
        "type": "dict",
        "required_keys": {
            "x": {"type": "string"},
            "y": {"type": "string"},
            "z": {"type": "string"}
        }
    }

    config = {
        'x': 'hello',
        'y': 'world',
        'z': '${ x | repeat } ${ y | repeat }'
    }

    def repeat(s: str) -> str:
        return s * 2

    print(smartconfig.resolve(config, schema, filters={"repeat": repeat}))

The result is:

.. testoutput:: python

    {'x': 'hello', 'y': 'world', 'z': 'hellohello worldworld'}

Custom Jinja2 Functions
~~~~~~~~~~~~~~~~~~~~~~~

It is sometimes desirable to provide a custom function to the Jinja2
templating engine (rather than a filter). This can be done by providing a
function in the `global_variables` keyword argument to :func:`resolve`. If a
global variable's name clashes with a key in the configuration, the value from
the configuration takes precedence. Typically, this manifests as a circular
reference.


.. _special-strings:
Raw and Recursive String Values
-------------------------------

By default, `smartconfig` will interpolate all strings values in the configuration
*once*. However, sometimes we want to indicate that a string should not be interpolated
or converted at all. For example, we might want to include a template string in the
configuration that will be evaluated elsewhere. To do this, we can wrap the string
in a :class:`types.RawString`. A :class:`types.RawString` is a subclass of :class:`str`
that indicates that the string should not be interpolated or parsed. In practice, it is
usually created by calling the built-in function, :ref:`raw-builtin`.

Similarly, sometimes we might want to indicate that a string should be interpolated
repeatedly until it stops changing. This is most useful when the string contains
references to raw strings (which themselves might contain references to raw strings, and
so on). We can do this by wrapping the string in a :class:`types.RecursiveString`. A
:class:`types.RecursiveString` is a subclass of :class:`str` as well. In practice, it
is usually created by calling the built-in function, :ref:`recursive-builtin`.

Recursive strings and raw strings are typically used in conjunction to define template
strings and to evaluate them somewhere else. For example, suppose we have the
configuration:

.. testcode:: python

    from smartconfig.types import RecursiveString, RawString

    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "string"},
            "bar": {"type": "string"},
            "baz": {"type": "string"},
        },
    }

    dct = {
        "foo": "hello",
        "bar": RawString("${foo} world"),
        "baz": RecursiveString("I said: ${bar}"),
    }

    result = smartconfig.resolve(dct, schema)
    print(result)

.. testoutput:: python

    {'bar': '${foo} world', 'baz': 'I said: hello world', 'foo': 'hello'}


.. _type-preservation:
Type Preservation
-----------------

Typically, the input to :func:`resolve` will be a plain Python object (e.g., a ``dict``
or a ``list``). Sometimes, however, it may be another mapping type that behaves like a
`dict`, but has some additional functionality. One example is the `ruamel` package which
is capable of round-tripping yaml, comments and all. To accomplish this, ruamel produces
a dict-like object which stores the comments internally. If we resolve this dict-like
object with :code:`preserve_type = False`, then we'll lose these comments; therefore, we
should use :code:`preserve_type = True`. At present, type preservation is done by
constructing the resolved output as normal, but then making a deep copy of `cfg` and
recursively copying each leaf value into this deep copy. Therefore, there is a
performance cost.

.. _customizing-function-call-syntax:
Customizing Function Call Syntax
--------------------------------

By default, `smartconfig` assumes that function calls are dictionaries with a single key
of the form ``__<function_name>__``. If you want to use a different syntax, you can
provide a custom function call checker via the ``check_for_function_call`` keyword
argument to :func:`resolve`. This should be a callable matching the
:class:`types.FunctionCallChecker` signature. That is, the function should take two
arguments: a :class:`types.ConfigurationDict` that is possibly a function call and a
mapping of function names to available functions. If the dictionary is a function call,
it should return a 2-tuple of the :class:`types.Function` to call and the input to the
function. If the dictionary is not a function call, it should return None. If the
dictionary is an invalid function call, it should raise a :class:`ValueError`.

Function calls can be disabled entirely by setting ``check_for_function_call`` to
None in the call to :func:`resolve`.


Resolution in Detail
--------------------

How exactly does resolution work? This section provides a detailed explanation
of the resolution process. It is typically not necessary to understand this
section in order to use `smartconfig`, but it may be helpful for understanding
the operation of `smartconfig` in more complex scenarios.

It is helpful to conceptualize a configuration as a graph. Each node in the
graph represents a piece of the configuration. We can imagine four different
types of node: dictionary, list, value, and function call. Each edge in the
graph represents a dependency between nodes.

For example, consider the following configuration:

.. code:: python

   {
        "course_name": "Introduction to Python",
        "date_of_first_lecture": "2025-01-10",
        "date_of_first_discussion": "7 days after ${this.first_lecture}",
        "message": [
            "Welcome to ${this.course_name}!",
            "The first lecture is on ${this.first_lecture}.",
            "The first discussion is on ${this.first_discussion}."
        ],
   }

To build the graph representing this configuration, we start by making a
tree. For this configuration, the root of the tree represents the outermost
dictionary. This root has four children: the nodes representing
``course_name``, ``date_of_first_lecture``, ``date_of_first_discussion``, and
``message``. The first three of these children are leaf nodes, as they are
simple values. The ``message`` node represents a list, and it has three
children: the nodes representing the three strings in the list.

On one hand, the edges in this tree represent inclusion relationships. On the
other, they also represent dependencies. For example, in order to resolve the
outermost dictionary, we must first resolve each of its children. As-is, the tree
does not capture *all* of the dependencies in the configuration; for example, the
value of ``date_of_first_discussion`` depends on the value of
``date_of_first_lecture``. We can represent this dependency by adding an edge
from the node representing ``date_of_first_discussion`` to the node representing
``date_of_first_lecture``, resulting in a graph.

When a configuration is resolved, a depth-first search is performed on this
graph, starting at the "root" node of the configuration. When a dictionary or
list node is encountered, an arbitrary child is recursively resolved before the
next child is resolved.

When a leaf node is encountered, it is first interpolated (if the value is a
string) and then converted. Interpolation is handled by the Jinja2 templating
engine. When a reference like ``${foo.bar.baz}`` is encountered during
interpolation, Jinja looks up the sequence of keys ``foo`` and ``bar`` in the
variables available to it. First, the "local variables" are searched; these are
the variables that are available only in certain subtrees of the configuration
tree, and which are set by functions like :ref:`let-builtin` and
:ref:`loop-builtin`.

If the key is not found in the local variables, the configuration itself is
searched by "drilling down" through an unresolved version of the configuration,
represented as either an :class:`types.UnresolvedDict`,
:class:`types.UnresolvedList`, or :class:`types.UnresolvedFunctionCall`. When
``foo`` is looked up, the result is again an unresolved container; the same
happens when ``bar`` is accessed. When Jinja finally looks up ``baz`` in the
unresolved dictionary containing it, the container type recognizes that a leaf
value is being accessed, and it triggers the resolution (interpolation and
conversion) of that value into a Python type. In this way, interpolation can
implictly trigger the resolution of other parts of the configuration.

Finally, if the variable is not found in the configuration, the global variables
are searched. Global variables are not interpolated or parsed, so they are mostly
used to provide extra functions to the string interpolation engine.

Once the value has been interpolated (if necessary), it is passed to a converter
function that attempts to convert it to the appropriate type. Converters are general,
taking in objects of any type and returning objects of the appropriate type. If the
input is a string, the converter typically "parses" it into the appropriate type,
sometimes by applying natural language processing (like in
:func:`smartconfig.converters.smartdate`).

If during resolution a node is encountered that is currently being resolved, a circular
dependency is detected, and an error is raised.
