Resolution
==========

.. testsetup:: python

    import smartconfig
    from smartconfig import types
    from pprint import pprint as print

A configuration is resolved using the :func:`smartconfig.resolve` function.

.. module:: smartconfig

.. function:: resolve(...) -> Configuration

    Resolve a configuration by interpolating and parsing its entries.

    Parameters
    ----------
    cfg : :class:`types.Configuration`
        The "raw" configuration to resolve.
    schema : :class:`types.Schema`
        The schema describing the structure of the resolved configuration.
    converters : Mapping[str, Callable]
        A dictionary mapping value types to converter functions. The converter functions
        should take the raw value (after interpolation) and convert it to the specified
        type. If this is not provided, the default converters in :data:`DEFAULT_CONVERTERS` are used.
    functions : Mapping[str, Union[Callable, :class:`types.Function`]]
        A mapping of function names to functions. The functions should either be basic
        Python functions accepting an instance of :class:`types.FunctionArgs` as input
        and returning a :class:`types.Configuration`, or they should be
        :class:`smartconfig.types.Function` instances. If this is not provided, the
        default functions in :data:`DEFAULT_FUNCTIONS` are used. If it is ``None``, no
        functions are made available.
    global_variables : Optional[Mapping[str, Any]]
        A dictionary of global variables to make available during string interpolation.
        If this is not provided, no global variables are available.
    inject_root_as : Optional[str]
        If this is not None, the root of the configuration tree is made available to
        Jinja2 templates as an :class:`types.UnresolvedDict`,
        :class:`types.UnresolvedList`, or :class:`types.UnresolvedFunctionCall` by
        injecting it into the template variables as the value of this key. This allows
        the root to be referenced directly during string interpolation. Defaults to
        ``None``.
    filters : Optional[Mapping[str, Callable]]
        A dictionary of Jinja2 filters to make available to templates. These will be
        added to Jinja2's set of default filters. If ``None``, no custom filters are
        provided. Defaults to ``None``.
    preserve_type : bool (default: False)
        If False, the return value of this function is a plain Python dictionary or
        list. If this is True, however, the return type will be the same as the type of
        ``cfg``. See :ref:`type-preservation` below for more information.
    check_for_function_call : :class:`types.FunctionCallChecker`
        A function that checks if a :class:`types.ConfigurationDict` represents a
        function call. It is given the configuration and the available functions. If it
        is a function call, it returns a 2-tuple of the :class:`types.Function` and the
        input to the function. If not, it returns None. If it is an invalid function
        call, it should raise a ``ValueError``. If this is not provided, a default
        implementation is used that assumes function calls are dictionaries with a
        single key of the form ``__<function_name>__``. If set to None, function calls
        are effectively disabled.

    Raises
    ------
    :class:`exceptions.InvalidSchemaError`
        If the schema is not valid.
    :class:`exceptions.ResolutionError`
        If the configuration does not match the schema, if there is a circular
        reference, or there is some other issue with the configuration itself.

Converters
----------

The last step in resolving a configuration value is converting it to the type specified
in the schema. This is done by passing the value to a "converter" function, which
accepts an object of any type and returns a Python object of the appropriate type (e.g.,
a converter for the "integer" value type should always return a Python ``int``). The
converter is responsible not only for converting the value, but also for validating that
the value is of the correct type.

:func:`resolve` expects a dictionary mapping the value types (e.g., "integer",
"float", "string", "boolean", "date", "datetime") to converter functions.
`smartconfig` provides several built-in converters in :mod:`smartconfig.converters`,
and default converters are defined in :data:`DEFAULT_CONVERTERS`:

.. data:: DEFAULT_CONVERTERS

    A mapping of default converters.

In summary, the default converters are:

- **integer**: :func:`smartconfig.converters.arithmetic` with type `int`. Allows for basic
  arithmetic, like ``1+2``
- **float**: :func:`smartconfig.converters.arithmetic` with type `float`. Allows for basic
  floating point arithmetic, like ``1.5 + 2.3``
- **string**: :class:`str`
- **boolean**: :func:`smartconfig.converters.logic`. Allows for basic boolean logic, like
  ``true and not (false or true)``
- **date**: :func:`smartconfig.converters.smartdate`. Allows for natural language dates,
  like ``"7 days after 2025-01-01"``
- **datetime**: :func:`smartconfig.converters.smartdatetime`. Allows for natural language
  datetimes, like ``"7 days after 2025-01-01 12:00:00"``

In general, if a converter is provided an instance of the type it is supposed to
convert to, it should return it unchanged. For instance, a converter to "datetime" that
is given a Python `datetime` object should return it unchanged.

To override the default converters, simply provide a different mapping from the possible
value types to converter functions to the ``converters`` keyword argument of
:func:`resolve`. The :data:`DEFAULT_CONVERTERS` dictionary should not be modified
directly, but it can be copied and modified.

.. _function-calls:
Functions
---------

:func:`resolve` allows configurations to contain function calls. During a function call,
the function is evaluated and the result is inserted into the configuration.

The default convention for function call syntax is a dictionary with a single key of the
form ``__<function_name>__`` (this behavior can be modified; see
:ref:`customizing-function-call-syntax` below). The value of the key is the argument
that is passed to the function. For example, the following configuration contains a
function call to a function named "double" which doubles its input:

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
        "y": {"__double__": "${x}"}
    }

    result = smartconfig.resolve(
        config, schema, functions={"double": lambda x: int(x.input) * 2}
    )
    print(result)

The result will be:

.. testoutput:: python

    {'x': 10, 'y': 20}

The functions available to a configuration are specified by passing a dictionary
mapping function names to functions to :func:`resolve`. The functions should either be
:class:`smartconfig.types.Function` instances or they should be basic Python functions
that take an instance of :class:`smartconfig.types.FunctionArgs` as input and return a
:class:`smartconfig.types.Configuration`.

Built-in Functions
^^^^^^^^^^^^^^^^^^

`smartconfig` provides several built-in functions for convenience. These are
implemented in :mod:`smartconfig.functions`. The default functions available to
:func:`resolve` are defined in :data:`DEFAULT_FUNCTIONS`:

.. data:: DEFAULT_FUNCTIONS

    A mapping of default functions.

They provide the following functionality:

.. _raw-builtin:
raw
***

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
*********

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

splice
******

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


update_shallow
**************

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


update
******

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

concatenate
***********

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

To override the default functions or provide your own, copy :data:`DEFAULT_FUNCTIONS`
and modify it as needed.

Providing Custom Functions
^^^^^^^^^^^^^^^^^^^^^^^^^^

You can define custom functions by passing a dictionary mapping function names to
functions to the ``functions`` keyword argument of :func:`resolve`. The
:data:`DEFAULT_FUNCTIONS` dictionary should not be modified directly, but it can be
copied and modified.

There are two ways to define functions. First, you can create a simple Python function
that takes one argument (an instance of :class:`smartconfig.types.FunctionArgs`) and
returns a :class:`smartconfig.types.Configuration` representing the result of the
function call. For example, below is a simple function that takes a string and a number
and repeats the string that many times:

.. testcode:: python

    def repeat(args: smartconfig.types.FunctionArgs):
        return args.input['string'] * args.input['repetitions']

    schema = {
        "type": "dict",
        "required_keys": {
            "message": {"type": "string"},
        }
    }

    dct = {
        "message": {"__repeat__": {"string": "Hello", "repetitions": 3}}
    }

    result = smartconfig.resolve(dct, schema, functions={"repeat": repeat})
    print(result)

The result will be:

.. testoutput:: python

    {'message': 'HelloHelloHello'}

The second way to define a function is to create a :class:`smartconfig.types.Function`
instances. This is preferable if you need to control whether the function's input is
resolved before being passed to the function. The :class:`smartconfig.types.Function`
class provides a convenience class method for this, called
:meth:`smartconfig.types.Function.new`. This class method can be used as a decorator.
For example:

.. testcode:: python

    from smartconfig.types import Function, FunctionArgs, Configuration, RawString
    @Function.new(resolve_input=False)
    def raw(args: FunctionArgs) -> Configuration:
        return RawString(args.input)

    schema = {
        "type": "dict",
        "required_keys": {
            "message": {"type": "string"},
        }
    }

    dct = {
        "message": {"__raw__": "${x}"},
    }

    result = smartconfig.resolve(dct, schema, functions={"raw": raw})
    print(result)

The result will be:

.. testoutput:: python

    {'message': '${x}'}

Functions are provided with with an object representing the entire unresolved
configuration via the :attr:`smartconfig.types.FunctionArgs.root` attribute. This
object can be used to reference other parts of the configuration without causing the
whole configuration to be resolved (which might result in circular references). For
example:

.. testcode:: python

    from smartconfig.types import Function, FunctionArgs, Configuration

    def compute_bar(args: FunctionArgs) -> Configuration:
         return args.root["foo"]["x"] + 1

    schema = {
        "type": "dict",
        "required_keys": {
            "foo": {"type": "dict", "required_keys": {"x": {"type": "integer"}}},
            "bar": {"type": "integer"}
        }
    }

    dct = {
        "foo": {"x": 5},
        "bar": {"__compute_bar__": None}
    }

    result = smartconfig.resolve(dct, schema, functions={"compute_bar": compute_bar})
    print(result)

The result will be:

.. testoutput:: python

    {'bar': 6, 'foo': {'x': 5}}

For more on how the :attr:`smartconfig.types.FunctionArgs.root` attribute can be used,
see the documentation for :class:`types.UnresolvedDict`, :class:`types.UnresolvedList`,
and :class:`types.UnresolvedFunctionCall`.


.. _customizing-function-call-syntax:
Customizing Function Call Syntax
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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


Jinja2 Features
----------------

:func:`resolve` uses the `jinja2` template engine for interpolation. This means that
many powerful `Jinja2` features can be used. For example, `Jinja2` supports a
ternary operator, so dictionaries can contain expressions like the following:"

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

It is also possible to use more advanced control flow constructs, like
`for` loops and `if` statements. For example:

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

Jinja2 filters are functions that can be applied during string interpolation. Jinja
provides many built-in filters, but custom filters can also be provided via the
`filters` keyword argument.

Global variables can be provided to Jinja2 templates through the `global_variables`
keyword argument. If a global variable's name clashes with a key in the
configuration, the value from the configuration takes precedence. Typically, this
manifests as a circular reference.

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

When a leaf node is encountered, it is first interpolated (if the value is a string) and
then converted. Interpolation is handled by the Jinja2 templating engine. During
interpolation, the engine is given access to the root of the configuration as an
instance of :class:`types.UnresolvedDict`, :class:`types.UnresolvedList`, or
:class:`types.UnresolvedFunctionCall`. These "unresolved" container objects represent
the root without resolving the whole configuration, but otherwise behave like normal
Python containers. This allows the template to refer to other parts of the configuration
without resolving the whole thing.

When a reference like ``${foo.bar.baz}`` is encountered during interpolation, Jinja
looks up the sequence of keys ``foo`` and ``bar`` in the template variables, "drilling
down" through the nested configuration. When ``foo`` is looked up, the result is again
an unresolved container; the same happens when ``bar`` is accessed. When Jinja finally
looks up ``baz`` in the unresolved dictionary containing it, the container type
recognizes that a leaf value is being accessed, and it triggers the resolution
(interpolation and conversion) of that value into a Python type. In this way,
interpolation can implictly trigger the resolution of other parts of the configuration.

Once the value has been interpolated (if necessary), it is passed to a converter
function that attempts to convert it to the appropriate type. Converters are general,
taking in objects of any type and returning objects of the appropriate type. If the
input is a string, the converter typically "parses" it into the appropriate type,
sometimes by applying natural language processing (like in
:func:`smartconfig.converters.smartdate`).

If during resolution a node is encountered that is currently being resolved, a circular
dependency is detected, and an error is raised.
