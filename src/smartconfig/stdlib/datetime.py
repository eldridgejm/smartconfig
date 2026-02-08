"""Datetime-related functions: at, offset, first, and parse."""

import datetime as datetimelib
import enum
import re
from collections.abc import Callable

from ..types import Configuration, FunctionArgs, FunctionMapping, KeyPath
from ..exceptions import ResolutionError


# helpers ==============================================================================

# valid units for offsets
_VALID_TIMEDELTA_UNITS = {"weeks", "days", "hours", "minutes", "seconds"}


def _read_datetime(value: Configuration, keypath: KeyPath) -> datetimelib.datetime:
    """Read a date/datetime from a string, date, or datetime object.

    Parameters
    ----------
    value : str or datetime.date or datetime.datetime
        If a string, it must be in ISO format (e.g., ``"2021-10-05"`` or
        ``"2021-10-05 23:59:15"``). A ``date`` is promoted to a ``datetime``
        at midnight.
    keypath : tuple of str
        The keypath for error reporting.

    Returns
    -------
    datetime.datetime

    Raises
    ------
    ResolutionError
        If ``value`` is a string that cannot be parsed as an ISO date/datetime.

    Examples
    --------
    >>> _read_datetime("2021-10-05", keypath=())
    datetime.datetime(2021, 10, 5, 0, 0)
    >>> _read_datetime(datetimelib.date(2021, 10, 5), keypath=())
    datetime.datetime(2021, 10, 5, 0, 0)
    >>> _read_datetime("2021-10-05 23:59:15", keypath=())
    datetime.datetime(2021, 10, 5, 23, 59, 15)

    """
    if isinstance(value, datetimelib.datetime):
        return value
    if isinstance(value, datetimelib.date):
        return datetimelib.datetime.combine(value, datetimelib.time())
    if isinstance(value, str):
        try:
            return datetimelib.datetime.fromisoformat(value)
        except ValueError:
            raise ResolutionError(f"Invalid date: '{value}'.", keypath)
    raise ResolutionError(
        f"Invalid date: expected a string or date/datetime object, "
        f"got {type(value).__name__}.",
        keypath,
    )


def _read_offset(value: Configuration, keypath: KeyPath) -> datetimelib.timedelta:
    """Read an offset from a string or dict into a timedelta.

    Parameters
    ----------
    value : str or dict
        If a string, a comma-separated list of ``"<n> <unit>"`` pairs, e.g.,
        ``"1 week, 2 days"``. If a dict, keys are unit names and values are
        integers, e.g., ``{"weeks": 1, "days": 2}``. Valid units are
        ``weeks``, ``days``, ``hours``, ``minutes``, and ``seconds``.
    keypath : tuple of str
        The keypath for error reporting.

    Returns
    -------
    datetime.timedelta

    Raises
    ------
    ResolutionError
        If the string cannot be parsed or the dict contains unknown units.

    Examples
    --------
    >>> _read_offset("1 week, 2 days", keypath=())
    datetime.timedelta(days=9)
    >>> _read_offset({"weeks": 1, "days": 2}, keypath=())
    datetime.timedelta(days=9)

    """
    if isinstance(value, dict):
        unknown = set(value.keys()) - _VALID_TIMEDELTA_UNITS
        if unknown:
            raise ResolutionError(
                f"Unknown unit(s) in 'by': {', '.join(sorted(unknown))}. "
                f"Valid units are: {', '.join(sorted(_VALID_TIMEDELTA_UNITS))}.",
                keypath,
            )
        units: dict[str, int] = {}
        for k, v in value.items():
            if not isinstance(v, int):
                raise ResolutionError(
                    f"Offset values must be integers, got {type(v).__name__} "
                    f"for '{k}'.",
                    keypath,
                )
            units[k] = v
        return datetimelib.timedelta(**units)

    if isinstance(value, str):
        kwargs: dict[str, int] = {}
        parts = [p.strip() for p in value.split(",")]
        for part in parts:
            match = re.match(r"^(\d+)\s+(week|day|hour|minute|second)s?$", part)
            if not match:
                raise ResolutionError(f"Cannot parse offset: '{value}'.", keypath)
            amount, unit = match.groups()
            kwargs[unit + "s"] = int(amount)
        return datetimelib.timedelta(**kwargs)

    raise ResolutionError(
        f"'by' must be a string or dictionary, got {type(value).__name__}.", keypath
    )


class _DaysOfTheWeek(enum.IntEnum):
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


def _get_day_of_the_week(s: Configuration, keypath: KeyPath) -> _DaysOfTheWeek:
    """Convert a day name string to a ``_DaysOfTheWeek`` value.

    Parameters
    ----------
    s : str
        Full day name, case-insensitive (e.g., ``"Monday"``).
    keypath : tuple of str
        The keypath for error reporting.

    Returns
    -------
    _DaysOfTheWeek

    Raises
    ------
    ResolutionError
        If ``s`` is not a valid day name.

    Examples
    --------
    >>> _get_day_of_the_week("Monday", keypath=())
    <_DaysOfTheWeek.MONDAY: 0>
    >>> _get_day_of_the_week("friday", keypath=())
    <_DaysOfTheWeek.FRIDAY: 4>

    """
    if not isinstance(s, str):
        raise ResolutionError(
            f"Expected a day name string, got {type(s).__name__}.", keypath
        )
    try:
        return _DaysOfTheWeek[s.upper()]
    except KeyError:
        raise ResolutionError(f"Invalid day of week: '{s}'.", keypath)


def _parse_weekdays(raw: str, keypath: KeyPath) -> set[_DaysOfTheWeek]:
    """Parse a string of weekday names into a set of ``_DaysOfTheWeek`` values.

    Names may be separated by commas, spaces, or the word ``"or"``.
    All separators are normalized before splitting, so ``"monday, friday"``,
    ``"monday friday"``, and ``"monday or friday"`` are all equivalent.

    Parameters
    ----------
    raw : str
        The raw weekday string.
    keypath : tuple of str
        The keypath for error reporting.

    Returns
    -------
    set of _DaysOfTheWeek

    Raises
    ------
    ResolutionError
        If any name in the string is not a valid day name.

    Examples
    --------
    >>> _parse_weekdays("monday, friday", keypath=())
    {_DaysOfTheWeek.MONDAY, _DaysOfTheWeek.FRIDAY}

    """
    normalized = raw.replace(",", " ").replace(" or ", " ")
    parts = normalized.split()
    return {_get_day_of_the_week(p, keypath) for p in parts}


def _parse_and_remove_time(
    s: str, keypath: KeyPath
) -> tuple[str, datetimelib.time | None]:
    """Extract and remove an ``at HH:MM:SS`` suffix from a string.

    Parameters
    ----------
    s : str
        The input string, possibly ending with ``" at HH:MM:SS"``.
    keypath : tuple of str
        The keypath for error reporting.

    Returns
    -------
    tuple of (str, datetime.time or None)
        The input with the suffix removed, and the parsed time (or None).

    Examples
    --------
    >>> _parse_and_remove_time("first monday after 2021-09-14 at 23:59:00", keypath=())
    ('first monday after 2021-09-14', datetime.time(23, 59))
    >>> _parse_and_remove_time("2021-10-05", keypath=())
    ('2021-10-05', None)

    """
    time_pattern = r" at (\d{2}):(\d{2}):(\d{2})$"
    match = re.search(time_pattern, s, flags=re.IGNORECASE)

    if match:
        hours, minutes, seconds = [int(x) for x in match.groups()]
        try:
            time = datetimelib.time(hours, minutes, seconds)
        except ValueError:
            raise ResolutionError(f"Invalid time in '{s}'.", keypath)
        s = re.sub(time_pattern, "", s, flags=re.IGNORECASE)
    else:
        time = None

    return s, time


# Maximum number of skip attempts before giving up. Set to 366 to guarantee
# that at least one full year of candidates is tried.
_MAX_SKIP_RETRIES = 366


def _read_skip_dates(value: Configuration, keypath: KeyPath) -> set[datetimelib.date]:
    """Read a ``skip`` list into a set of ``datetime.date`` objects.

    Parameters
    ----------
    value : list
        A list of date strings (ISO format), ``datetime.date``, or
        ``datetime.datetime`` objects — anything accepted by
        ``_read_datetime``.
    keypath : tuple of str
        The keypath for error reporting.

    Returns
    -------
    set of datetime.date

    Raises
    ------
    ResolutionError
        If ``value`` is not a list, or any element cannot be parsed.

    Examples
    --------
    >>> _read_skip_dates(["2021-10-05", "2021-10-06"], keypath=())
    {datetime.date(2021, 10, 5), datetime.date(2021, 10, 6)}

    """
    if not isinstance(value, list):
        raise ResolutionError("'skip' must be a list of dates.", keypath)
    return {_read_datetime(item, keypath).date() for item in value}


def _find_first_weekday(
    reference: datetimelib.datetime,
    weekdays: set[_DaysOfTheWeek],
    before: bool,
) -> datetimelib.datetime:
    """Find the first occurrence of a weekday before/after a reference date.

    Parameters
    ----------
    reference : datetime.datetime
        The starting point. This date is excluded from the search.
    weekdays : set of _DaysOfTheWeek
        The target weekday(s) to search for.
    before : bool
        If True, search backward in time; otherwise search forward.

    Returns
    -------
    datetime.datetime
        The first matching date. The time component is preserved from
        ``reference``.

    Examples
    --------
    >>> _find_first_weekday(datetime(2021, 9, 14), {MONDAY}, before=False)
    datetime(2021, 9, 20)  # first Monday after Sep 14 (a Tuesday)

    """
    sign = -1 if before else 1
    delta = datetimelib.timedelta(days=sign)
    cursor = reference + delta
    while cursor.weekday() not in weekdays:
        cursor += delta
    return cursor


def _skip_excluded(
    result: datetimelib.datetime,
    skip_dates: set[datetimelib.date],
    next_candidate: Callable[[datetimelib.datetime], datetimelib.datetime],
    keypath: KeyPath,
) -> datetimelib.datetime:
    """Advance past excluded dates using a caller-supplied step function.

    Parameters
    ----------
    result : datetime.datetime
        The initial candidate date.
    skip_dates : set of datetime.date
        Dates to skip.
    next_candidate : callable
        A function ``(datetime) -> datetime`` that produces the next candidate
        when the current one is excluded.
    keypath : tuple of str
        The keypath for error reporting.

    Returns
    -------
    datetime.datetime

    Raises
    ------
    ResolutionError
        If no valid date is found within ``_MAX_SKIP_RETRIES`` attempts.

    Examples
    --------
    >>> skip = {datetimelib.date(2021, 10, 6)}
    >>> candidate = datetimelib.datetime(2021, 10, 6)
    >>> step = lambda dt: dt + datetimelib.timedelta(days=1)
    >>> _skip_excluded(candidate, skip, step, keypath=())
    datetime.datetime(2021, 10, 7, 0, 0)

    """
    retries = 0
    while result.date() in skip_dates:
        result = next_candidate(result)
        retries += 1
        if retries > _MAX_SKIP_RETRIES:
            raise ResolutionError(
                "Could not find a valid date: all candidates are excluded.",
                keypath,
            )
    return result


# functions ============================================================================

# at -----------------------------------------------------------------------------------


def at(args: FunctionArgs) -> datetimelib.datetime:
    """Combine a date (or datetime) with a time, returning a new datetime.

    ``args.input`` should be a dictionary with keys:

        - ``date``: the reference date or datetime (string, date, or datetime)
        - ``time``: a time string in ISO format (e.g., ``"23:59:00"``)

    If the input date is already a datetime, the time component is overridden.

    """
    if not isinstance(args.input, dict):
        raise ResolutionError("Input to 'at' must be a dictionary.", args.keypath)

    if "date" not in args.input:
        raise ResolutionError("Input to 'at' must contain 'date'.", args.keypath)

    if "time" not in args.input:
        raise ResolutionError("Input to 'at' must contain 'time'.", args.keypath)

    reference = _read_datetime(args.input["date"], args.keypath)

    raw_time = args.input["time"]
    if not isinstance(raw_time, str):
        raise ResolutionError(
            f"'time' must be a string, got {type(raw_time).__name__}.", args.keypath
        )
    try:
        time = datetimelib.time.fromisoformat(raw_time)
    except ValueError:
        raise ResolutionError(f"Invalid time: '{raw_time}'.", args.keypath)

    return datetimelib.datetime.combine(reference, time)


# offset -------------------------------------------------------------------------------


def offset(args: FunctionArgs) -> datetimelib.datetime:
    """Offset a date or datetime by a given amount.

    ``args.input`` should be a dictionary with keys:

        - ``before`` or ``after``: the reference date (mutually exclusive)
        - ``by``: the offset amount (string or dict)

    """
    if not isinstance(args.input, dict):
        raise ResolutionError("Input to 'offset' must be a dictionary.", args.keypath)

    has_before = "before" in args.input
    has_after = "after" in args.input

    if not has_before and not has_after:
        raise ResolutionError(
            "Input to 'offset' must contain either 'before' or 'after'.", args.keypath
        )

    if has_before and has_after:
        raise ResolutionError(
            "Input to 'offset' must not contain both 'before' and 'after'.",
            args.keypath,
        )

    if "by" not in args.input:
        raise ResolutionError("Input to 'offset' must contain 'by'.", args.keypath)

    skip_dates: set[datetimelib.date] = set()
    if "skip" in args.input:
        skip_dates = _read_skip_dates(args.input["skip"], args.keypath)

    direction_key = "before" if has_before else "after"
    reference = _read_datetime(args.input[direction_key], args.keypath)
    delta = _read_offset(args.input["by"], args.keypath)

    result = reference - delta if has_before else reference + delta

    if skip_dates:
        sign = -1 if has_before else 1
        day_step = datetimelib.timedelta(days=sign)
        result = _skip_excluded(
            result,
            skip_dates,
            lambda dt: dt + day_step,
            args.keypath,
        )

    return result


# first --------------------------------------------------------------------------------


def first(args: FunctionArgs) -> datetimelib.datetime:
    """Find the first occurrence of a given weekday before/after a reference date.

    ``args.input`` should be a dictionary with keys:

        - ``weekday``: a day name (string) or list of day names
        - ``before`` or ``after``: the reference date (mutually exclusive)

    """
    if not isinstance(args.input, dict):
        raise ResolutionError("Input to 'first' must be a dictionary.", args.keypath)

    if "weekday" not in args.input:
        raise ResolutionError("Input to 'first' must contain 'weekday'.", args.keypath)

    has_before = "before" in args.input
    has_after = "after" in args.input

    if not has_before and not has_after:
        raise ResolutionError(
            "Input to 'first' must contain either 'before' or 'after'.", args.keypath
        )

    if has_before and has_after:
        raise ResolutionError(
            "Input to 'first' must not contain both 'before' and 'after'.",
            args.keypath,
        )

    # parse weekday(s)
    raw_weekday = args.input["weekday"]
    if isinstance(raw_weekday, str):
        weekdays = _parse_weekdays(raw_weekday, args.keypath)
    elif isinstance(raw_weekday, list):
        weekdays = {_get_day_of_the_week(d, args.keypath) for d in raw_weekday}
    else:
        raise ResolutionError(
            "The 'weekday' key must be a string or list of strings.", args.keypath
        )

    skip_dates: set[datetimelib.date] = set()
    if "skip" in args.input:
        skip_dates = _read_skip_dates(args.input["skip"], args.keypath)

    direction_key = "before" if has_before else "after"
    reference = _read_datetime(args.input[direction_key], args.keypath)

    result = _find_first_weekday(reference, weekdays, before=has_before)

    if skip_dates:
        result = _skip_excluded(
            result,
            skip_dates,
            lambda dt: _find_first_weekday(dt, weekdays, before=has_before),
            args.keypath,
        )

    return result


# parse --------------------------------------------------------------------------------


class _ParseError(Exception):
    """Raised when a parse attempt fails because the string does not match.

    Used for control flow: parsers are tried one after another until one
    succeeds.

    """


def _try_parse_first_weekday(s: str, keypath: KeyPath) -> datetimelib.datetime:
    """Try to parse ``s`` as ``"first <weekdays> after|before <reference>"``."""
    match = re.match(r"^first\s+(.+?)\s+(after|before)\s+(.+)$", s, flags=re.IGNORECASE)
    if not match:
        raise _ParseError

    weekday_raw, direction, reference_raw = match.groups()
    weekdays = _parse_weekdays(weekday_raw, keypath)
    reference = _read_datetime(reference_raw.strip(), keypath)
    return _find_first_weekday(
        reference, weekdays, before=direction.lower() == "before"
    )


def _try_read_offset(s: str, keypath: KeyPath) -> datetimelib.datetime:
    """Try to parse ``s`` as ``"<offset> after|before <reference>"``."""
    match = re.match(r"^(.+?)\s+(after|before)\s+(.+)$", s, flags=re.IGNORECASE)
    if not match:
        raise _ParseError

    offset_raw, direction, reference_raw = match.groups()
    delta = _read_offset(offset_raw.strip(), keypath)
    reference = _read_datetime(reference_raw.strip(), keypath)

    if direction.lower() == "before":
        return reference - delta
    else:
        return reference + delta


def _try_parse_iso(s: str, keypath: KeyPath) -> datetimelib.datetime:
    """Try to parse ``s`` as a plain ISO date or datetime."""
    try:
        return datetimelib.datetime.fromisoformat(s.strip())
    except ValueError:
        raise _ParseError


def parse(args: FunctionArgs) -> datetimelib.datetime:
    """Parse a natural language date/datetime string.

    ``args.input`` should be a string in one of the following forms:

        - An ISO date or datetime: ``"2021-10-05"`` or ``"2021-10-05 23:59:10"``
        - An offset: ``"3 days after 2021-10-05"``
        - A first-weekday: ``"first monday, friday after 2021-09-14"``

    Any form may end with an ``" at HH:MM:SS"`` suffix to override the time
    component of the result.

    """
    if not isinstance(args.input, str):
        raise ResolutionError("Input to 'parse' must be a string.", args.keypath)

    s, time_override = _parse_and_remove_time(args.input, args.keypath)

    parsers = [_try_parse_first_weekday, _try_read_offset, _try_parse_iso]
    for try_parse in parsers:
        try:
            result = try_parse(s, args.keypath)
            break
        except _ParseError:
            continue
    else:
        raise ResolutionError(f"Cannot parse date: '{args.input}'.", args.keypath)

    if time_override is not None:
        result = datetimelib.datetime.combine(result, time_override)

    return result


DATETIME_FUNCTIONS: FunctionMapping = {
    "at": at,
    "first": first,
    "offset": offset,
    "parse": parse,
}
