Custom Functions
================

.. testsetup:: python

    import smartconfig
    from smartconfig import types
    from pprint import pprint as print

Defining Custom Functions
-------------------------

As discussed in :doc:`default_functions`, `smartconfig` comes with several built-in
functions that handle common configuration needs out of the box. However, you may
find that you need to define your own functions to perform operations specific to
your application. For this, `smartconfig` allows you to define custom functions.

There are two ways to define custom functions in `smartconfig`: as simple Python functions
or as instances of :class:`smartconfig.types.Function`. In either case, the function will
be called with a single argument: an instance of :class:`smartconfig.types.FunctionArgs`,
which contains all the information the function needs to perform its task. The function
should return a :class:`smartconfig.types.Configuration` representing the result of
the function call.

.. class:: smartconfig.types.FunctionArgs
   :no-index:

   Holds the arguments passed to a custom function during resolution.

   .. attribute:: input
      :type: Configuration
      :no-index:

      The input to the function, as read from the configuration. For example,
      if the configuration contains ``{"__my_func__": {"x": 1, "y": 2}}``, then
      ``input`` will be ``{"x": 1, "y": 2}``.

   .. attribute:: root
      :type: UnresolvedDict | UnresolvedList | UnresolvedFunctionCall
      :no-index:

      The root of the configuration tree. This can be used to reference other
      parts of the configuration without causing the entire tree to be resolved
      (which might result in circular references).

   .. attribute:: keypath
      :type: KeyPath
      :no-index:

      The keypath to the location in the configuration where this function call
      appears. Useful for error messages.

   .. attribute:: schema
      :type: Schema
      :no-index:

      The schema that the result of this function is expected to conform to.
      This allows functions to adapt their behavior based on the expected
      output type.

   .. attribute:: resolve
      :type: Resolver
      :no-index:

      A callable that can be used to resolve a configuration value. This enables
      dynamic behavior such as evaluating loop bodies or conditionally resolving
      values. See :class:`smartconfig.types.Resolver` for the signature.

   .. attribute:: resolution_options
      :type: ResolutionOptions
      :no-index:

      The full resolution context, including converters, functions, and other
      options passed to :func:`smartconfig.resolve`. Rarely needed in practice.


:data:`smartconfig.DEFAULT_FUNCTIONS` is dictionary containing the built-in functions;
to override, remove, or add new custom functions, copy this dictionary first, make
modifications to the copy, and then pass the modified copy to :func:`smartconfig.resolve`
via the ``functions`` keyword argument.

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
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The second way to define a function is to create a :class:`smartconfig.types.Function`
instances. This is preferable if you need to control whether the function's input is
resolved before being passed to the function. The :class:`smartconfig.types.Function`
class provides a convenience class method for this, called
:meth:`smartconfig.types.Function.new`. This class method can be used as a decorator.

For example, the below custom function implements "raw" strings that are not interpolated
or processed in any way. To achieve this, we set ``resolve_input=False`` when defining
the function. Note that there is a built-in :func:`smartconfig.functions.raw` function
that does exactly this; we are re-implementing it here for demonstration purposes only.

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

Examples
--------

Example 1: Referencing the root of the configuration tree
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
        # we should probably do some error checking here, but for simplicity
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


Example 3: Checking the function's specification with schemas
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

It's generally a good idea for custom functions to check that their input
conforms to the expected format. One pattern that makes this easy is to define
a schema for the function's input and use :func:`smartconfig.resolve` to validate
it, using the power of `smartconfig` to implement the validation logic.

For example, let's revisit our ``repeat`` function from earlier and add input validation
to it. We expect the input to be a dictionary with two keys: ``string`` (a string to repeat)
and ``repetitions`` (an integer indicating how many times to repeat the string). First, we
define the schema for the function's input:

.. testcode:: python

    repeat_input_schema = {
        "type": "dict",
        "required_keys": {
            "string": {"type": "string"},
            "repetitions": {"type": "integer"}
        }
    }

    def repeat(args: smartconfig.types.FunctionArgs):
        validated_input = smartconfig.resolve(
            args.input,
            repeat_input_schema
        )
        return validated_input['string'] * validated_input['repetitions']


Now, when we call ``repeat``, it will first validate its input against the schema,
raising an error if the input is invalid. If the result is invalid, a
:class:`smartconfig.exceptions.ResolutionError` will be raised:

.. testcode:: python

    schema = {
        "type": "dict",
        "required_keys": {
            "message": {"type": "string"},
        }
    }

    dct = {
        "message": {"__repeat__": {"string": "Hello", "repetitions": "three"}}
    }

    result = smartconfig.resolve(dct, schema, functions={"repeat": repeat})

This will raise an error indicating that the ``repetitions`` key
could not be converted to an integer:

.. testoutput:: python
    :options: +ELLIPSIS

    Traceback (most recent call last):
        ...
    smartconfig.exceptions.ResolutionError: Cannot resolve keypath "repetitions": Cannot parse into int: 'three'.

On the other hand, if the input is valid, it will proceed to
perform the string repetition as before:

.. testcode:: python

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
