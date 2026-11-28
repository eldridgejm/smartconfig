Custom Functions
================

.. testsetup:: python

    import smartconfig
    from smartconfig import types
    from pprint import pprint as print

Defining Custom Functions
-------------------------

As discussed in :doc:`default_functions`, `smartconfig` comes with several default
functions that handle common configuration needs out of the box. However, you may
find that you need to define your own functions to perform operations specific to
your application. For this, `smartconfig` allows you to define custom functions.

There are two ways to define custom functions in `smartconfig`: as simple Python functions
or as instances of :class:`smartconfig.types.Function`. In either case, the function will
be called with a single argument: an instance of :class:`smartconfig.types.FunctionArgs`,
which contains all the information the function needs to perform its task. The function
should return a :class:`smartconfig.types.Configuration` representing the result of
the function call.

If the function raises an exception that isn't one of `smartconfig`'s own, it is
reported as a :class:`smartconfig.exceptions.ResolutionError` at the keypath of the
function call, with the original exception as its ``__cause__``. An
``AssertionError`` is not wrapped, since it signals a bug in the function rather
than a mistake in the configuration.

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

   .. attribute:: resolution_context
      :type: ResolutionContext
      :no-index:

      The full resolution context, including converters, functions, and other
      options passed to :func:`smartconfig.resolve`. Rarely needed in practice.


Adding, overriding and removing functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:data:`smartconfig.DEFAULT_FUNCTIONS` is a dictionary containing the default
functions, and it is what :func:`smartconfig.resolve` uses when no ``functions``
argument is given. To add, override, or remove functions, make a deep copy of it,
modify the copy, and pass the copy to :func:`smartconfig.resolve` via the
``functions`` keyword argument:

.. testsetup:: copying

    import smartconfig

    def repeat(args):
        return args.input["string"] * args.input["repetitions"]

    def my_loop(args):
        return []

.. testcode:: copying

    import copy

    functions = copy.deepcopy(smartconfig.DEFAULT_FUNCTIONS)
    functions["repeat"] = repeat          # add
    functions["list"]["loop"] = my_loop   # override a namespaced function
    del functions["if"]                   # remove a core function
    del functions["list"]["filter"]       # remove a namespaced function

    config = {"message": {"__repeat__": {"string": "Hi", "repetitions": 2}}}
    print(smartconfig.resolve(config, {"type": "any"}, functions=functions))

    # the defaults are unchanged
    print("filter" in smartconfig.DEFAULT_FUNCTIONS["list"])

.. testoutput:: copying

    {'message': 'HiHi'}
    True

A plain ``.copy()`` isn't enough: the namespaces (such as ``"list"``) are nested
dictionaries, so a shallow copy shares them, and changing them would change the
defaults too. If you only need to add top-level functions, a dictionary literal
works: ``{**smartconfig.DEFAULT_FUNCTIONS, "repeat": repeat}``.

For brevity, the examples on this page pass only the custom function, as in
``functions={"repeat": repeat}``. This turns off the default functions.

Approach #1: Simple Python Functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The first approach is to write a simple Python function
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

The second way to define a function is to create :class:`smartconfig.types.Function`
instances. This is preferable if you need to control whether the function's input is
resolved before being passed to the function. The :class:`smartconfig.types.Function`
class provides a convenience class method for this, called
:meth:`smartconfig.types.Function.new`. This class method can be used as a decorator.

For example, the below custom function wraps its input in a list without resolving
the input first. To achieve this, we set ``resolve_input=False`` when defining
the function.

.. testcode:: python

    from smartconfig.types import Function, FunctionArgs, Configuration

    @Function.new(resolve_input=False)
    def wrap_list(args: FunctionArgs) -> Configuration:
        return [args.input]

    schema = {
        "type": "list",
        "element_schema": {"type": "string"},
    }

    dct = {"__wrap_list__": "hello"}

    result = smartconfig.resolve(dct, schema, functions={"wrap_list": wrap_list})
    print(result)

The result will be:

.. testoutput:: python

    ['hello']

How return values are resolved
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

By default, a function's return value is treated as configuration and resolved
like any other part of the configuration: ``${...}`` strings in it are
interpolated, function calls in it are evaluated, and the result is converted to
the field's schema. This lets a function act like a macro, returning
configuration that is filled in afterwards:

.. testcode:: python

    def use_name(args: FunctionArgs) -> Configuration:
        return "Hello ${ name }"

    config = {"name": "Ada", "greeting": {"__use_name__": None}}
    result = smartconfig.resolve(config, {"type": "any"}, functions={"use_name": use_name})
    print(result["greeting"])

.. testoutput:: python

    'Hello Ada'

If a function returns values that are already resolved, such as the result of
``args.resolve``, resolving them again can change them. For example, a value
produced by ``__raw__`` would be interpolated after all. Set
``resolve_output=False`` to treat the return value as finished data: it is still
converted to the field's schema, but nothing in it is interpolated or evaluated.

.. testcode:: python

    @Function.new(resolve_output=False)
    def use_name_literally(args: FunctionArgs) -> Configuration:
        return "Hello ${ name }"

    config = {"name": "Ada", "greeting": {"__use_name_literally__": None}}
    functions = {"use_name_literally": use_name_literally}
    result = smartconfig.resolve(config, {"type": "any"}, functions=functions)
    print(result["greeting"])

.. testoutput:: python

    'Hello ${ name }'

Many of the stdlib functions, such as ``list.concatenate`` and ``dict.update``,
use ``resolve_output=False``.

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

`smartconfig` comes with a default ``list.loop`` function
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

   @Function.new(resolve_input=False, resolve_output=False)
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
variable ``x`` to the current iteration number. Because the body is resolved
here, the function sets ``resolve_output=False`` so that the results are not
resolved a second time (see `How return values are resolved`_).

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
a schema for the function's input and resolve the input against it with
``args.resolve``, using the power of `smartconfig` to implement the validation logic.

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

    @Function.new(resolve_input=False)
    def repeat(args: FunctionArgs) -> Configuration:
        validated_input = args.resolve(args.input, schema=repeat_input_schema)
        return validated_input['string'] * validated_input['repetitions']

Unlike a nested call to :func:`smartconfig.resolve`, ``args.resolve`` keeps the
keypath of the function call, so errors point to the right place, and it uses the
caller's functions, converters and global variables. The function sets
``resolve_input=False`` so that its input isn't resolved twice: once before the
call, and again by ``args.resolve`` (see `How return values are resolved`_).

Now, when we call ``repeat``, it will first validate its input against the schema.
If the input is invalid, a :class:`smartconfig.exceptions.ResolutionError` will be
raised:

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

This will raise an error indicating that the ``message.repetitions`` key
could not be converted to an integer:

.. testoutput:: python
    :options: +ELLIPSIS

    Traceback (most recent call last):
        ...
    smartconfig.exceptions.ResolutionError: Cannot resolve keypath "message.repetitions": Cannot convert to integer: 'three'.

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

By default, :func:`smartconfig.resolve` looks for function calls that are
dictionaries with a single key of the form ``__<function_name>__``. If you want
to use a different syntax, you can provide a custom function call checker via
the ``check_for_function_call`` keyword argument to :func:`resolve`. This
should be a callable matching the :data:`~smartconfig.types.FunctionCallChecker` signature.
That is, the function should take two arguments: a
:data:`~smartconfig.types.ConfigurationDict` that is possibly a function call and a mapping
of function names to available functions. If the dictionary is a function call,
it should return a 2-tuple of the :class:`~smartconfig.types.Function` to call and the input
to the function. If the dictionary is not a function call, it should return
None. If the dictionary is an invalid function call, it should raise a
:class:`ValueError`.

Function calls can be disabled entirely by setting ``check_for_function_call`` to
None in the call to :func:`resolve`.
