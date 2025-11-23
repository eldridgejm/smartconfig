Default Converters
==================

`smartconfig` is configured with sensible defaults to handle common configuration
needs out of the box. This includes a set of built-in converters for common types. Custom converters can also be defined; see :doc:`custom_converters` for more information. The default converters are implemented in the :mod:`smartconfig.converters` module.

Which converter is applied to a configuration value depends on the schema
provided to :func:`smartconfig.resolve`. Each converter is associated with one
or more schema types.

.. testsetup:: python

    import smartconfig
    from smartconfig import types
    from pprint import pprint as print


Arithmetic
----------

By default, the Arithmetic converter is applied to any configuration value
whose schema type is ``integer`` or ``float``. It evaluates arithmetic
expressions written in strings. For example:

- ``"2 + 2"`` evaluates to ``4``
- ``"(7 + 3) / 5"`` evaluates to ``2``

If the schema calls for an integer but the value is a float (or evaluates to a
float), it will be converted to an integer only if it represents a whole number.
Otherwise, a :class:`~smartconfig.exceptions.ConversionError` is raised.

For example:

.. testcode:: python

    config = {
        "value": "6.0 / 3"
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "value": {"type": "integer"}
        }
    }

    resolved = smartconfig.resolve(config, schema)
    print(resolved)

.. testoutput:: python

    {'value': 2}

On the other hand:

.. testcode:: python

    config = {
        "value": "7 / 3"
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "value": {"type": "integer"}
        }
    }

    resolved = smartconfig.resolve(config, schema)
    print(resolved)

.. testoutput:: python

    Traceback (most recent call last):
      ...
    smartconfig.exceptions.ResolutionError: Cannot resolve keypath "value": Cannot parse into int: '7 / 3'.


Logic
-----

By default, the Logic converter is applied to any configuration value whose
schema type is ``boolean``. It evaluates boolean logic expressions written in
strings. For example:

- ``"True and False"`` evaluates to ``False``
- ``"True or False"`` evaluates to ``True``
- ``"not False"`` evaluates to ``True``
- ``"True and (False or True)"`` evaluates to ``True``

The supported operators are ``and``, ``or``, and ``not``. If the value is
already a boolean, it is returned unchanged.

.. testcode:: python

    config = {
        "enabled": "True and not False"
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "enabled": {"type": "boolean"}
        }
    }

    resolved = smartconfig.resolve(config, schema)
    print(resolved)

.. testoutput:: python

    {'enabled': True}


Smartdate and Smartdatetime
---------------------------

By default, the smartdate converter is applied to any configuration value whose
schema type is ``date``, and the smartdatetime converter is applied to values
with schema type ``datetime``. These converters parse natural language date
expressions into Python :class:`datetime.date` and :class:`datetime.datetime`
objects, respectively.

The supported input formats are:

- ISO format dates: ``"2021-10-01"`` or ``"2021-10-01 23:59:00"``
- Relative dates: ``"3 days before 2021-10-05"`` or ``"2 days after 2021-10-01"``
- Day-of-week expressions: ``"first monday after 2021-09-10"`` or ``"first monday, friday before 2021-10-01"``

The Smartdatetime converter additionally supports ISO times (e.g.,
``"2021-10-01 23:59:00"``) and explicit time overrides using the ``at`` keyword
(e.g., ``"3 days after 2021-10-01 at 15:00:00"``).

.. note::

   Currently, the natural language parser only supports day-based offsets (e.g.,
   ``"3 days before"``), not hour-based offsets.

If the smartdate converter is given a datetime string (e.g., ``"2021-10-01
23:59:00"``), the time component is silently discarded. Conversely, the
smartdatetime converter requires a time component and raises an error if given a
date-only string (e.g., ``"2021-10-01"``) or a :class:`datetime.date` object.

When combined with string interpolation, this allows you to define dates
relative to other values in the configuration.

.. testcode:: python

    config = {
        "start": "2021-10-01",
        "reminder": "3 days before ${start}"
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "start": {"type": "date"},
            "reminder": {"type": "date"}
        }
    }

    resolved = smartconfig.resolve(config, schema)
    print(resolved)

.. testoutput:: python

    {'reminder': datetime.date(2021, 9, 28), 'start': datetime.date(2021, 10, 1)}

The Smartdatetime converter also supports times:

.. testcode:: python

    config = {
        "deadline": "2021-10-01 23:59:00",
        "warning": "1 day before ${deadline}"
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "deadline": {"type": "datetime"},
            "warning": {"type": "datetime"}
        }
    }

    resolved = smartconfig.resolve(config, schema)
    print(resolved)

.. testoutput:: python

    {'deadline': datetime.datetime(2021, 10, 1, 23, 59),
     'warning': datetime.datetime(2021, 9, 30, 23, 59)}
