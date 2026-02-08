"""Provides the built-in converters.

A converter is a function that accepts a raw value -- often, but not necessarily a
string -- and returns a resolved value with the appropriate type. Converters often
act as parsers, converting string expressions into Python objects. They also act as
type validators, ensuring that the resulting value is of the correct type.

"""

import datetime as datetimelib
import re

from . import exceptions

# numeric ==============================================================================


def integer(value: int | float | str) -> int:
    """Convert a value to an integer.

    Accepts ``int`` values (pass-through), whole-number ``float`` values
    (coerced to ``int``), and numeric strings. Rejects ``bool`` values,
    non-whole floats, and non-numeric strings.

    Parameters
    ----------
    value
        The value to convert.

    Returns
    -------
    int
        The converted integer.

    Example
    -------

    >>> from smartconfig.converters import integer
    >>> integer('42')
    42
    >>> integer(3.0)
    3

    """
    if isinstance(value, bool):
        raise exceptions.ConversionError(f"Cannot convert bool to integer: {value!r}.")

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        raise exceptions.ConversionError(
            f"Cannot convert float {value} to integer: value is not a whole number.",
        )

    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            raise exceptions.ConversionError(
                f"Cannot convert to integer: '{value}'.",
            )

    raise exceptions.ConversionError(f"Cannot convert to integer: {value!r}.")


def float_(value: int | float | str) -> float:
    """Convert a value to a float.

    Accepts ``float`` values (pass-through), ``int`` values (coerced to
    ``float``), and numeric strings. Rejects ``bool`` values and non-numeric
    strings.

    Parameters
    ----------
    value
        The value to convert.

    Returns
    -------
    float
        The converted float.

    Example
    -------

    >>> from smartconfig.converters import float_
    >>> float_('4.5')
    4.5
    >>> float_(3)
    3.0

    """
    if isinstance(value, bool):
        raise exceptions.ConversionError(f"Cannot convert bool to float: {value!r}.")

    if isinstance(value, float):
        return value

    if isinstance(value, (int, str)):
        try:
            return float(value)
        except ValueError, TypeError:
            raise exceptions.ConversionError(
                f"Cannot convert to float: '{value}'.",
            )

    raise exceptions.ConversionError(f"Cannot convert to float: {value!r}.")


# logical ==============================================================================


def boolean(value: bool | str) -> bool:
    """Convert a value to a boolean.

    Accepts ``bool`` values (pass-through) and the strings ``"True"`` and
    ``"False"``. Rejects all other types and string values.

    Parameters
    ----------
    value
        The value to convert.

    Returns
    -------
    bool
        The converted boolean.

    Example
    -------

    >>> from smartconfig.converters import boolean
    >>> boolean('True')
    True
    >>> boolean(False)
    False

    """
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        if value == "True":
            return True
        if value == "False":
            return False

    raise exceptions.ConversionError(f"Cannot convert to bool: {value!r}.")


# dates / datetimes ====================================================================


def _contains_time_component(s: str) -> bool:
    """Check if a string contains a time pattern (HH:MM)."""
    return bool(re.search(r"\d{2}:\d{2}", s))


def date(value: str | datetimelib.date | datetimelib.datetime) -> datetimelib.date:
    """Convert a value to a date object.

    Accepts ``datetime.date`` objects (pass-through), ``datetime.datetime``
    objects (simplified to date by discarding the time), ISO format date
    strings, and ISO format datetime strings (the time component is discarded).

    Parameters
    ----------
    value
        The value to convert.

    Returns
    -------
    datetime.date
        The converted date.

    Example
    -------

    >>> import datetime
    >>> from smartconfig.converters import date
    >>> date('2021-10-01')
    datetime.date(2021, 10, 1)
    >>> date('2021-10-01 23:59:59')
    datetime.date(2021, 10, 1)
    >>> date(datetime.datetime(2021, 10, 1, 23, 59, 59))
    datetime.date(2021, 10, 1)

    """
    # datetime is a subclass of date, so check it first
    if isinstance(value, datetimelib.datetime):
        return value.date()

    if isinstance(value, datetimelib.date):
        return value

    if isinstance(value, str):
        try:
            return datetimelib.date.fromisoformat(value)
        except ValueError:
            pass
        # Also accept datetime strings, discarding the time component.
        try:
            return datetimelib.datetime.fromisoformat(value).date()
        except ValueError:
            pass

    raise exceptions.ConversionError(f"Cannot convert to date: '{value}'.")


def datetime(
    value: str | datetimelib.date | datetimelib.datetime,
) -> datetimelib.datetime:
    """Convert a value to a datetime object.

    Accepts ``datetime.datetime`` objects (pass-through) and ISO format
    datetime strings. Rejects bare ``datetime.date`` objects and date-only
    strings to avoid an implicit midnight assumption.

    Parameters
    ----------
    value
        The value to convert.

    Returns
    -------
    datetime.datetime
        The converted datetime.

    Example
    -------

    >>> import datetime as dt
    >>> from smartconfig.converters import datetime
    >>> datetime('2021-10-01 23:59:59')
    datetime.datetime(2021, 10, 1, 23, 59, 59)
    >>> datetime('2021-10-01')
    Traceback (most recent call last):
    ...
    smartconfig.exceptions.ConversionError: Cannot implicitly convert date string '2021-10-01' into datetime. Please include a time component.
    >>> datetime(dt.date(2021, 10, 1))
    Traceback (most recent call last):
    ...
    smartconfig.exceptions.ConversionError: Cannot implicitly convert date '2021-10-01' into datetime.

    """
    if isinstance(value, datetimelib.datetime):
        return value

    if isinstance(value, datetimelib.date):
        raise exceptions.ConversionError(
            f"Cannot implicitly convert date '{value}' into datetime.",
        )

    if isinstance(value, str):
        if not _contains_time_component(value):
            raise exceptions.ConversionError(
                f"Cannot implicitly convert date string '{value}' into datetime. "
                "Please include a time component.",
            )
        try:
            return datetimelib.datetime.fromisoformat(value)
        except ValueError:
            raise exceptions.ConversionError(
                f"Cannot convert to datetime: '{value}'.",
            )

    raise exceptions.ConversionError(f"Cannot convert to datetime: '{value}'.")
