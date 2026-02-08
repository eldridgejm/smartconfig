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


Integer and Float
-----------------

The integer converter is applied to any configuration value whose schema type
is ``integer``, and the float converter is applied to values with schema type
``float``. These converters accept numeric values and numeric strings:

- Integer values pass through unchanged.
- Whole-number floats (e.g., ``3.0``) are coerced to ``int``.
- The float converter accepts ``int`` values, coercing them to ``float``.
- Numeric strings (e.g., ``"42"``, ``"4.5"``) are parsed with ``int()`` or
  ``float()``.

.. note::

   Arithmetic expressions like ``"2 + 2"`` are **not** evaluated by the
   converter. Use Jinja2 interpolation instead: ``"${2 + 2}"``.

.. testcode:: python

    config = {
        "count": "42",
        "ratio": "3.14",
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "count": {"type": "integer"},
            "ratio": {"type": "float"},
        }
    }

    resolved = smartconfig.resolve(config, schema)
    print(resolved)

.. testoutput:: python

    {'count': 42, 'ratio': 3.14}


Boolean
-------

The boolean converter is applied to any configuration value whose schema type
is ``boolean``. It accepts ``bool`` values (pass-through) and the strings
``"True"`` and ``"False"``. All other values are rejected.

.. note::

   Boolean expressions like ``"True and False"`` are **not** evaluated by
   the converter. Use Jinja2 interpolation instead: ``"${True and False}"``.

.. testcode:: python

    config = {
        "enabled": "True",
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "enabled": {"type": "boolean"},
        }
    }

    resolved = smartconfig.resolve(config, schema)
    print(resolved)

.. testoutput:: python

    {'enabled': True}


Date and Datetime
-----------------

By default, the date converter is applied to any configuration value whose
schema type is ``date``, and the datetime converter is applied to values with
schema type ``datetime``. These converters parse ISO format date strings into
Python :class:`datetime.date` and :class:`datetime.datetime` objects,
respectively.

The date converter accepts:

- ISO format date strings: ``"2021-10-01"``
- ISO format datetime strings (time is discarded): ``"2021-10-01 23:59:00"``
- :class:`datetime.date` objects (pass-through)
- :class:`datetime.datetime` objects (simplified to date)

The datetime converter accepts:

- ISO format datetime strings: ``"2021-10-01 23:59:00"``
- :class:`datetime.datetime` objects (pass-through)

The datetime converter rejects date-only strings (e.g., ``"2021-10-01"``) and
bare :class:`datetime.date` objects to avoid an implicit midnight assumption.

.. testcode:: python

    config = {
        "start": "2021-10-01",
        "deadline": "2021-10-01 23:59:00",
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "start": {"type": "date"},
            "deadline": {"type": "datetime"},
        }
    }

    resolved = smartconfig.resolve(config, schema)
    print(resolved)

.. testoutput:: python

    {'deadline': datetime.datetime(2021, 10, 1, 23, 59),
     'start': datetime.date(2021, 10, 1)}

.. note::

   For more advanced date manipulation — such as relative dates, day-of-week
   lookups, and time offsets — use the ``datetime`` stdlib functions
   (``datetime.offset``, ``datetime.first``, ``datetime.at``, ``datetime.parse``).
