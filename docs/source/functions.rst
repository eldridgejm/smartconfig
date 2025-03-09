.. _function-calls:
Functions
=========

.. testsetup:: python

    import smartconfig

`smartconfig` allows for the definition of custom functions that can be called
from within the configuration file. These functions can be used to compute
values at runtime, significantly expanding what is possible to express in a
configuration file.

Defining Custom Functions
-------------------------

You can define custom functions by passing a dictionary mapping function names to
functions to the ``functions`` keyword argument of :func:`resolve`. The
:data:`DEFAULT_FUNCTIONS` dictionary should not be modified directly, but it can be
copied and modified.

Approach #1: Simple Python Functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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

Approach #2: Using :class:`smartconfig.types.Function`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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

Information provided to functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Functions are called with a single argument, an instance of
:class:`smartconfig.types.FunctionArgs`. Several attributes of this object are
worth noting in particular.


The :attr:`smartconfig.types.FunctionArgs.input` attribute contains the input to the
function.

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

    {'foo': {'x': 5}, 'bar': 6}

For more on how the :attr:`smartconfig.types.FunctionArgs.root` attribute can be used,
see the documentation for :class:`types.UnresolvedDict`, :class:`types.UnresolvedList`,
and :class:`types.UnresolvedFunctionCall`.

The :attr:`smartconfig.types.FunctionArgs.resolve` attribute is a function that
can be used to resolve a configuration value. It follows the same signature as
:class:`smartconfig.types.Resolver`. This is provided to allow for very dynamic
behavior. For example, the built-in :func:`smartconfig.functions.loop` function
uses this to evaluate the loop body dynamically on each iteration.

Examples
~~~~~~~~

Example 1: Referencing the root of the configuration tree
*********************************************************

Let's write a function that returns the number of keys in the dictionary at the
root of the configuration tree. We'll use the :attr:`smartconfig.types.FunctionArgs.root`
attribute to access the root of the configuration tree.

.. testcode:: python

    from smartconfig.types import FunctionArgs, Configuration

    def count_keys(args: FunctionArgs) -> int:
        return len(args.root)

    schema = {
        "type": "dict",
        "required_keys": {
            "count": {"type": "integer"},
        },
        "extra_keys_schema": {"type": "any"}
    }

    dct = {
        "count": {"__count_keys__": {}},
        "foo": 1,
        "bar": 2,
        "baz": 3
    }

    result = smartconfig.resolve(dct, schema, functions={"count_keys": count_keys})
    print(result["count"])

We get:

.. testoutput:: python

   4

Example 2: Implementing loops
*****************************

`smartconfig` comes with a built-in :func:`smartconfig.functions.loop` function
that implements a simple loop construct. However, for pedagogical purposes,
let's implement our own version, as this will demonstrate the flexibility of
the function system.

Our loop syntax will be as follows:

.. testcode:: python

   # should evaluate to:
   # ["current number: 0", "current number: 1", "current number: 2"]
   config = {
        "__my_loop__": {
            "variable": "x",
            "start": 0,
            "stop": 3,
            "body": "current number: ${x}"
        }
    }

To accomplish this, we define the function:

.. testcode:: python

   from smartconfig.types import Function, FunctionArgs, Configuration

   @Function.new(resolve_input=False)
   def my_loop(args: FunctionArgs) -> Configuration:
        # probably should do some error checking here, but for simplicity
        # we'll omit it
        start = args.input["start"]
        stop = args.input["stop"]

        return [
            args.resolve(
                args.input["body"],
                local_variables={args.input["variable"]: i},
                schema=args.schema["element_schema"]
            )
            for i in range(start, stop)
        ]

Notice the use of ``args.resolve`` to dynamically evaluate the body of the
loop, as well as the use of the ``local_variables`` argument to bind the loop
variable ``x`` to the current iteration number.

Now we test it out:

.. testcode:: python

    schema = {
        "type": "list",
        "element_schema": {"type": "string"}
    }

    result = smartconfig.resolve(config, schema, functions={"my_loop": my_loop})
    print(result)

We get:

.. testoutput:: python

    ['current number: 0', 'current number: 1', 'current number: 2']


Built-in Functions
------------------

`smartconfig` comes with several built-in functions that allow for basic
manipulation of the configuration; these are defined in the
:mod:`smartconfig.functions` module. The default functions available to
:func:`smartconfig.resolve` are defined in
:data:`smartconfig.DEFAULT_FUNCTIONS`.

.. module:: smartconfig.functions

The built-in functions are:

.. autosummary::

   concatenate
   dict_from_items
   filter_
   if_
   let
   loop
   range_
   raw
   recursive
   splice
   update
   update_shallow
   zip_

.. autofunction:: concatenate

.. function:: raw(args: FunctionArgs)

   Makes a :class:`smartconfig.types.RawString` that will not be interpolated or converted.

   ``args.input`` should be a single string. If not, an error is raised.

.. autofunction:: recursive
.. autofunction:: splice
.. autofunction:: update
.. autofunction:: update_shallow
.. autofunction:: if_
.. autofunction:: let
.. autofunction:: loop
.. autofunction:: concatenate
.. autofunction:: zip_
.. autofunction:: filter_
.. autofunction:: range_
.. autofunction:: dict_from_items
