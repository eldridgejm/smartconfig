Custom Jinja2 Filters
=====================

.. testsetup:: python

    import smartconfig
    from pprint import pprint as print


Defining Custom Filters
-----------------------

As discussed in :doc:`resolution_in_detail`, `smartconfig` uses Jinja2 for string
interpolation. This means you can use Jinja2 filters to transform values within your
configuration strings. For example, ``${name | upper}`` would convert the value of
``name`` to uppercase.

While Jinja2 comes with many built-in filters, you may want to define your own to
handle specific transformation logic required by your application.

A Jinja2 filter is simply a Python function that takes the value to be filtered as
its first argument, and optionally extra arguments. You can register these functions
as custom filters by passing them to :func:`smartconfig.resolve` via the ``filters``
keyword argument.

The ``filters`` argument expects a dictionary mapping filter names (as strings) to
the Python functions that implement them.

Example: A Reverse Filter
~~~~~~~~~~~~~~~~~~~~~~~~~

Let's define a simple filter that reverses a string.

.. testcode:: python

    def reverse_filter(value):
        return value[::-1]

    schema = {
        "type": "dict",
        "required_keys": {
            "original": {"type": "string"},
            "reversed": {"type": "string"},
        }
    }

    config = {
        "original": "Hello World",
        "reversed": "${original | reverse}"
    }

    # Pass the custom filter to resolve
    result = smartconfig.resolve(
        config,
        schema,
        filters={"reverse": reverse_filter}
    )
    print(result)

The output shows that the string was successfully reversed:

.. testoutput:: python

    {'original': 'Hello World', 'reversed': 'dlroW olleH'}


Example: Filter with Arguments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Jinja2 filters can also accept arguments. Let's define a ``encrypt`` filter that
performs a simple Caesar cipher shift. It will take the shift amount as an argument.

.. testcode:: python

    def encrypt_filter(value, shift=1):
        result = ""
        for char in value:
            if char.isalpha():
                start = ord('A') if char.isupper() else ord('a')
                result += chr((ord(char) - start + shift) % 26 + start)
            else:
                result += char
        return result

    schema = {
        "type": "string"
    }

    # Shift by 1 (default) and shift by 13
    config = "Default: ${'abc' | encrypt}, ROT13: ${'abc' | encrypt(13)}"

    result = smartconfig.resolve(
        config,
        schema,
        filters={"encrypt": encrypt_filter}
    )
    print(result)

.. testoutput:: python

    'Default: bcd, ROT13: nop'
