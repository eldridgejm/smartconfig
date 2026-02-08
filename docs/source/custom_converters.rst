Custom Converters
=================

.. testsetup:: python

    import smartconfig
    from smartconfig import types
    from pprint import pprint as print


Defining Custom Converters
--------------------------

As mentioned in :doc:`default_converters`, `smartconfig` uses converter functions
to transform string values into typed Python objects. By default, several common
converters are provided, but you can also define your own custom converters to
handle specific types or formats.

A converter is a function that accepts a single argument (usually, but not
necessarily, a string) and returns a Python object. The argument is the value
to be converted.

You can provide custom converters for any of the basic types that a schema can
specify. These include ``integer``, ``float``, ``string``, ``boolean``,
``date``, and ``datetime``. For example, you might want to
override the default ``integer`` converter to accept hexadecimal strings, or
override ``boolean`` to accept ``"yes"`` and ``"no"`` in addition to ``"True"``
and ``"False"``.

Converters are responsible for validating their input and raising an appropriate
exception if the input cannot be converted to the expected type. When a converter
encounters invalid input, it should raise a :class:`smartconfig.exceptions.ConversionError`.
This exception will be caught by `smartconfig` and re-raised with additional
context about where in the configuration the error occurred.

To override a default converter, simply copy :data:`smartconfig.DEFAULT_CONVERTERS`
and replace the entry for the type you wish to customize (do not modify the original
dictionary in place). Then, pass the modified dictionary to :func:`smartconfig.resolve`
via the `converters` keyword argument.

Example: A Boolean Converter
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`smartconfig` comes with a built-in converter for booleans, which is defined in
:func:`smartconfig.converters.boolean`. However, for the sake of illustration,
let's define a custom boolean converter that accepts ``"yes"`` and ``"no"`` in
addition to ``"True"`` and ``"False"``.

.. testcode:: python

    from smartconfig.exceptions import ConversionError

    def boolean_converter(value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            if value.lower() in {"true", "yes"}:
                return True
            if value.lower() in {"false", "no"}:
                return False
        raise ConversionError(f"cannot convert {value!r} to boolean")

    schema = {
        "type": "boolean"
    }

    converters = smartconfig.DEFAULT_CONVERTERS.copy()
    converters['boolean'] = boolean_converter

    result = smartconfig.resolve("yes", schema, converters=converters)
    print(result)

We will see the following output:

.. testoutput:: python

    True
