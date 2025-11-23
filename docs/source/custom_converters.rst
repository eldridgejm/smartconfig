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
specify. These include ``"integer"``, ``"float"``, ``"string"``, ``"boolean"``,
``"date"``, and ``"datetime"``. For example, you might want to
override the default ``"integer"`` converter to accept hexadecimal strings, or
override ``"boolean"`` to accept ``"yes"`` and ``"no"`` in addition to ``"true"``
and ``"false"``.

To override a default converter, simply copy :data:`smartconfig.DEFAULT_CONVERTERS`
and replace the entry for the type you wish to customize (do not modify the original
dictionary in place). Then, pass the modified dictionary to :func:`smartconfig.resolve`
via the `converters` keyword argument.

Example: A Date Converter
~~~~~~~~~~~~~~~~~~~~~~~~~

`smartconfig` comes with a built-in converter for dates, which is defined in
:func:`smartconfig.converters.smartdate`. However, for the sake of illustration,
let's define a custom date converter that accepts dates in the format
``YYYY-MM-DD`` and returns a Python `date` object.

.. testcode:: python

    from datetime import date

    def date_converter(value: str):
        year, month, day = [int(x) for x in value.split("-")]
        return date(year, month, day)

    schema = {
        "type": "date"
    }

    dct = "2025-01-10"

    converters = smartconfig.DEFAULT_CONVERTERS.copy()
    converters['date'] = date_converter

    result = smartconfig.resolve(dct, schema, converters=converters)
    print(type(result))

We will see the following output:

.. testoutput:: python

    <class 'datetime.date'>


Type Validation and Error Handling
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Converters are responsible for validating their input and raising an appropriate
exception if the input cannot be converted to the expected type. When a converter
encounters invalid input, it should raise a :class:`smartconfig.exceptions.ConversionError`.
This exception will be caught by `smartconfig` and re-raised with additional
context about where in the configuration the error occurred.

For example, a more robust version of our date converter might look like this:

.. testcode:: python

    from datetime import date
    from smartconfig.exceptions import ConversionError

    def date_converter(value):
        if not isinstance(value, str):
            raise ConversionError(f"expected a string, got {type(value).__name__}")
        parts = value.split("-")
        if len(parts) != 3:
            raise ConversionError(f"expected date in YYYY-MM-DD format, got {value!r}")
        try:
            year, month, day = [int(x) for x in parts]
            return date(year, month, day)
        except ValueError as e:
            raise ConversionError(f"invalid date {value!r}: {e}")
