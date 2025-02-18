"""Provides the built-in converters.

A converter is a function that accepts a raw value -- often, but not necessarily a
string -- and returns a resolved value with the appropriate type. Converters often
act as parsers, converting string expressions into Python objects. They also act as
type validators, ensuring that the resulting value is of the correct type.

"""

from typing import Optional, Any
import ast
import datetime as datetimelib
import enum
import operator as op
import re

from . import exceptions

# the AST code in this module is based on:
# https://stackoverflow.com/questions/2371436/evaluating-a-mathematical-expression-in-a-string

# arithmetic ===========================================================================


def arithmetic(type_):
    """A factory that creates an arithmetic expression converter.

    The resulting function parses things like "(7 + 3) / 5" into the specified
    numeric type.

    If the integer converter is given an integer value (instead of a string) it leaves
    it alone. Same for the float converter. However, if the integer converter is given
    a float value, it will raise a :class::`ConversionError`, even if that float
    represents an integer. This is to avoid possible unexpected loss of precision. If
    the float converter is given an integer value, it will convert it to a float, since
    there are no ambiguities there.

    Parameters
    ----------
    type_
        The end type that the resulting value should be converted to.

    Example
    -------

    >>> from smartconfig.converters import arithmetic
    >>> converter = arithmetic(int)
    >>> converter('(7 + 3) / 5')
    2
    >>> converter(42)
    42

    """

    def _eval(node):
        operators = {
            ast.Add: op.add,
            ast.Sub: op.sub,
            ast.Mult: op.mul,
            ast.Div: op.truediv,
            ast.Pow: op.pow,
            ast.BitXor: op.xor,
            ast.USub: op.neg,
        }

        if isinstance(node, ast.Constant):  # <number>
            return node.value
        elif type(node.op) not in operators:
            raise TypeError(node)

        if isinstance(node, ast.BinOp):  # <left> <operator> <right>
            assert isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow))
            return operators[type(node.op)](_eval(node.left), _eval(node.right))
        elif isinstance(node, ast.UnaryOp):  # <operator> <operand> e.g., -1
            assert isinstance(node.op, (ast.BitXor, ast.USub))
            return operators[type(node.op)](_eval(node.operand))

    def converter(value: Any):
        if isinstance(value, type_):
            return value

        if type_ is float and isinstance(value, int):
            return float(value)

        if type_ is int and isinstance(value, float):
            raise exceptions.ConversionError(
                f"Cannot implicitly convert float {value} into integer.", value
            )

        try:
            number = _eval(ast.parse(value, mode="eval").body)
        except Exception:
            raise exceptions.ConversionError(
                f"Cannot parse into {type_.__name__}: '{value}'."
            )
        assert isinstance(number, (int, float))
        return type_(number)

    return converter


# logical ==============================================================================


def logic(value: Any) -> bool:
    """Converts boolean logic expressions.

    If the converter is given a boolean value, it leaves it alone. If it is given a
    string, it parses the string as a boolean expression. If given another type, like an
    integer, it raises a :class:`ConversionError`.

    Example
    -------

    >>> from smartconfig.converters import logic
    >>> logic('True and (False or True)')
    True

    """
    if isinstance(value, bool):
        return value

    if not isinstance(value, str):
        raise exceptions.ConversionError(f"Cannot convert type {type(value)} to bool.")

    def _eval(node):
        operators = {ast.Or: op.or_, ast.And: op.and_, ast.Not: op.not_}

        if isinstance(node, ast.Constant):
            return node.value
        elif type(node.op) not in operators:
            raise exceptions.ConversionError(
                f"Cannot parse: '{value}'. Unknown operator."
            )

        if isinstance(node, ast.UnaryOp):  # <operator> <operand> e.g., -1
            assert isinstance(node.op, ast.Not)
            return operators[type(node.op)](_eval(node.operand))
        elif isinstance(node, ast.BoolOp):
            assert isinstance(node.op, (ast.Or, ast.And))
            return operators[type(node.op)](*[_eval(v) for v in node.values])

    try:
        return bool(_eval(ast.parse(value, mode="eval").body))
    except Exception:
        raise exceptions.ConversionError(f"Cannot parse into bool: '{value}'.")


# dates / datetimes ====================================================================


class _DateMatchError(Exception):
    """Raised if a parse fails because the string does not match.

    This is used in control flow: parsers are tried one after another until one
    succeeds. If a parser fails because the string does not match, this is raised so
    that the process can move on to the next parser.

    """


# helpers ------------------------------------------------------------------------------


def _parse_datetime_from_explicit(s: str) -> datetimelib.datetime:
    """Parses a datetime from a string of the form "YYYY-MM-DD HH:MM:SS"."""
    s, at_time = _parse_and_remove_time(s)
    try:
        parsed = datetimelib.datetime.fromisoformat(s)
    except ValueError:
        raise _DateMatchError

    if at_time is not None:
        parsed = datetimelib.datetime.combine(parsed, at_time)

    return parsed


def _parse_and_remove_time(s: str) -> tuple[str, Optional[datetimelib.time]]:
    """Looks for a time at the end of the smart date string.

    A time is of the form "at 23:59:00"

    Parameters
    ----------
    s : str
        The smart date string

    Returns
    -------
    str
        The input, ``s``, but without a time at the end (if there was one in the first
        place).

    Union[datetime.time, None]
        The time, if there was one; otherwise this is ``None``.

    Raises
    ------
    ConversionError
        If there is a time string, but it's an invalid time (like 55:00:00).

    """
    time_pattern = r" at (\d{2}):(\d{2}):(\d{2})$"
    match = re.search(time_pattern, s, flags=re.IGNORECASE)

    if match:
        hours, minutes, seconds = [int(s) for s in match.groups()]
        try:
            time = datetimelib.time(hours, minutes, seconds)
        except ValueError:
            raise exceptions.ConversionError(f"Invalid time: {s}.")

        s = re.sub(time_pattern, "", s, flags=re.IGNORECASE)
    else:
        time = None

    return s, time


def _parse_timedelta_before_or_after(s: str) -> datetimelib.datetime:
    """Converts a string of the form "<n> days (before|after) <date(time)> [at HH:MM:SS]".

    This will always return a datetime object.

    """
    s, at_time = _parse_and_remove_time(s)

    match = re.match(
        r"^(\d+) (day|hour)[s]{0,1} (after|before) (.*)?$",
        s,
        flags=re.IGNORECASE,
    )

    if not match:
        raise _DateMatchError("Did not match.")

    number, hours_or_days, before_or_after, reference_date = match.groups()
    factor = -1 if before_or_after.lower() == "before" else 1

    if hours_or_days.lower() == "hour":
        timedelta_kwargs = {"hours": factor * int(number)}
    else:
        timedelta_kwargs = {"days": factor * int(number)}

    try:
        reference_date = datetimelib.datetime.fromisoformat(reference_date.strip())
    except ValueError:
        raise _DateMatchError(f"Reference date {reference_date} not in ISO format.")

    delta = datetimelib.timedelta(**timedelta_kwargs)

    parsed_date = reference_date + delta

    if at_time is not None:
        parsed_date = datetimelib.datetime.combine(parsed_date, at_time)

    return parsed_date


class _DaysOfTheWeek(enum.IntEnum):
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


def _get_day_of_the_week(s: str) -> _DaysOfTheWeek:
    """Take a day of the week string, like "Monday", and turn it into a _DaysOfTheWeek.

    Parameters
    ----------
    s : str
        Day of the week as a string. Must be the full name, e.g., "Wednesday". Case
        insensitive.

    Returns
    -------
    _DaysOfTheWeek
        The day of the week.

    Raises
    ------
    ValidationError
        If ``s`` was not a valid day name.

    """
    try:
        return getattr(_DaysOfTheWeek, s.upper())
    except AttributeError:
        raise _DateMatchError(f"Invalid day of week: {s}")


def _parse_first_available_day(s: str) -> datetimelib.datetime:
    """Convert a string of the form "first monday before 2021-10-01 [at HH:MM:SS]".

    Always returns a datetime object.

    """
    s = s.replace(",", " ")
    s = s.replace(" or ", " ")

    s, at_time = _parse_and_remove_time(s)

    match = re.match(r"^first ([\w ]+) (after|before) (.*)$", s, flags=re.IGNORECASE)

    if not match:
        raise _DateMatchError("Did not match.")

    day_of_the_week_raw, before_or_after, relative_to = match.groups()
    day_of_the_week = {_get_day_of_the_week(x) for x in day_of_the_week_raw.split()}

    relative_to = datetimelib.datetime.fromisoformat(relative_to)

    sign = 1 if before_or_after.lower() == "after" else -1
    delta = datetimelib.timedelta(days=sign)

    cursor_date = relative_to + delta

    while cursor_date.weekday() not in day_of_the_week:
        cursor_date += delta

    if at_time is not None:
        cursor_date = datetimelib.datetime.combine(cursor_date, at_time)

    return cursor_date


# converter implementations ---------------------------------------------------------------


def smartdate(value: Any) -> datetimelib.date:
    """Converts natural language relative dates into date objects.

    Input strings can be in one of three forms:

        1. Dates in ISO format, e.g.: "2021-10-01".
        2. Relative dates of the form :code:`"<n> day(s) (before|after) <ISO date>"`,
           e.g., "3 days before 2021-10-10"
        3. Relative dates of the form :code:`"first
           <day_of_week>[,<day_of_week>,...,<day_of_week>] (before|after) <ISO date>"`,
           e.g., "first monday, wednesday after 2021-10-10"

    If the input is already a date, it is returned as-is. If the input is a datetime, it
    is simplified to a date by discarding the time.

    Example
    -------

    .. testsetup::

        import datetime

    >>> from smartconfig.converters import smartdate
    >>> smartdate('2021-10-01')
    datetime.date(2021, 10, 1)
    >>> smartdate('1 day after 2021-10-01')
    datetime.date(2021, 10, 2)
    >>> smartdate('3 days before 2021-10-05')
    datetime.date(2021, 10, 2)
    >>> smartdate('first monday after 2021-09-10')
    datetime.date(2021, 9, 13)
    >>> smartdate('first monday, friday after 2021-09-10')
    datetime.date(2021, 9, 13)
    >>> smartdate(datetime.datetime(2021, 10, 1, 23, 59, 59))
    datetime.date(2021, 10, 1)

    """
    # this must come before the check for isinstance(value, date), because datetime
    # is a subclass of date
    if isinstance(value, datetimelib.datetime):
        return value.date()

    if isinstance(value, datetimelib.date):
        return value

    if not isinstance(value, str):
        raise exceptions.ConversionError(
            f"Cannot convert type {type(value)} into date."
        )

    try:
        return datetimelib.datetime.fromisoformat(value).date()
    except ValueError:
        # the date was not in ISO format
        pass

    try:
        return _parse_timedelta_before_or_after(value).date()
    except _DateMatchError:
        # the string does not match the pattern, move on
        pass

    try:
        return _parse_first_available_day(value).date()
    except _DateMatchError:
        # the string does not match the pattern, move on
        pass

    raise exceptions.ConversionError(f"Cannot parse into date: '{value}'.")


def smartdatetime(value: Any) -> datetimelib.datetime:
    """Converts natural language relative dates into datetime objects.

    The forms of the input are the same as for :func:`smartdate`, except ISO times
    are permitted. For instance: :code:`3 days after 2021-10-05 23:59:00`.

    If the input is already a datetime, it is returned as-is. If the input is a date, it
    raises a :class:`ConversionError` in order to avoid possible unexpected loss of
    precision.

    Examples
    --------

    .. testsetup::

        import datetime

    >>> from smartconfig.converters import smartdatetime
    >>> smartdatetime('2021-10-01 23:59:59')
    datetime.datetime(2021, 10, 1, 23, 59, 59)
    >>> smartdatetime('3 days after 2021-10-05 23:59:00')
    datetime.datetime(2021, 10, 8, 23, 59)
    >>> smartdatetime('first monday after 2021-09-10 23:59:00')
    datetime.datetime(2021, 9, 13, 23, 59)
    >>> smartdatetime(datetime.date(2021, 10, 1))
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

    if not isinstance(value, str):
        raise exceptions.ConversionError(
            f"Cannot convert type {type(value)} into datetime."
        )

    try:
        return datetimelib.datetime.fromisoformat(value)
    except ValueError:
        # the date was not in ISO format
        pass

    try:
        return _parse_datetime_from_explicit(value)
    except _DateMatchError:
        pass

    try:
        return _parse_timedelta_before_or_after(value)
    except _DateMatchError:
        pass

    try:
        return _parse_first_available_day(value)
    except _DateMatchError:
        pass

    raise exceptions.ConversionError(f"Cannot parse into datetime: '{value}'.")
