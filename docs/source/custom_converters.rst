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
and ``"False"``. You can also add a converter under a new name (other than
``any``, ``dict``, ``list`` or ``template``, which are structural types and
never use a converter), such as ``"hex"``, and use that name as a type in a
schema. A schema whose type has no converter is rejected with an
:class:`~smartconfig.exceptions.InvalidSchemaError`.

Converters are responsible for validating their input and raising an appropriate
exception if the input cannot be converted to the expected type. When a converter
encounters invalid input, it should raise a :class:`smartconfig.exceptions.ConversionError`.
This exception will be caught by `smartconfig` and re-raised with additional
context about where in the configuration the error occurred. Any other
exception escapes as it is, without a keypath, and isn't a `smartconfig`
exception, so a converter should catch the errors it expects and raise a
``ConversionError`` instead:

.. testcode:: python

    from smartconfig.exceptions import ConversionError

    def hex_converter(value):
        try:
            return int(value, 16)
        except ValueError as e:
            raise ConversionError(f"Not hex: {value}.") from e

    converters = {**smartconfig.DEFAULT_CONVERTERS, "hex": hex_converter}
    schema = {"type": "dict", "required_keys": {"color": {"type": "hex"}}}

    try:
        smartconfig.resolve({"color": "zz"}, schema, converters=converters)
    except smartconfig.exceptions.ResolutionError as exc:
        print(str(exc))

.. testoutput:: python

    'Cannot resolve keypath "color": Not hex: zz.'

Whether you override a default converter or add a new one, start from a copy
of :data:`smartconfig.DEFAULT_CONVERTERS` and change the copy (do not modify the
original dictionary in place). The ``converters`` argument replaces the default
converters rather than adding to them, so passing ``converters={"hex": ...}``
alone would leave out ``string`` and the rest. Then, pass the modified
dictionary to :func:`smartconfig.resolve` via the `converters` keyword argument.

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
