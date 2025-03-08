.. _converters:

Converters
==========

.. testsetup:: python

    import smartconfig

The last step in resolving a configuration value is converting it to the type specified
in the schema. This is done by passing the value to a "converter" function, which
accepts an object of any type and returns a Python object of the appropriate type (e.g.,
a converter for the "integer" value type should always return a Python ``int``). The
converter is responsible not only for converting the value, but also for validating that
the value is of the correct type.

Defining a Converter
--------------------

A converter is a function that accepts a single argument and returns a Python
object. The argument is the value to be converted. Custom converters can be
provided by passing a dictionary mapping type names to converter functions to
the ``converters`` keyword argument of :func:`smartconfig.resolve`. The
:data:`DEFAULT_CONVERTERS` dictionary should not be modified directly, but it
can be copied and modified.

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

Built-in Converters
-------------------

`smartconfig` comes with several built-in converters that allow for the
conversion of basic types; these are defined in the
:mod:`smartconfig.converters` module. The default converters available to
:func:`smartconfig.resolve` are defined in
:data:`smartconfig.DEFAULT_CONVERTERS`.

.. module:: smartconfig.converters

The provided converters are:

.. autosummary::

   arithmetic
   logic
   smartdate
   smartdatetime

.. autofunction:: arithmetic

.. autofunction:: logic

.. autofunction:: smartdate

.. autofunction:: smartdatetime
