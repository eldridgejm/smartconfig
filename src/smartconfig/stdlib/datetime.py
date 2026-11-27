"""Datetime-related functions: at, offset, first, and parse."""

import datetime as datetimelib
import enum
import re
from collections.abc import Callable

from ..types import (
    Configuration,
    ConfigurationDict,
    FunctionArgs,
    FunctionMapping,
    KeyPath,
)
from ..exceptions import ResolutionError
from ._args import to_integer


# helpers ==============================================================================

# valid units for offsets
_VALID_TIMEDELTA_UNITS = {"weeks", "days", "hours", "minutes", "seconds"}


# a datetime is a date too; the alias says that either is meant
type _DateOrDatetime = datetimelib.date | datetimelib.datetime


def _read_date_or_datetime(value: Configuration, keypath: KeyPath) -> _DateOrDatetime:
    """Read a date or datetime from a string, date, or datetime object.

    Parameters
    ----------
    value : str or datetime.date or datetime.datetime
        If a string, it must be in ISO format (e.g., ``"2021-10-05"`` or
        ``"2021-10-05 23:59:15"``). A date (or a string with no time) stays a
        date, rather than becoming a datetime at midnight.
    keypath : tuple of str
        The keypath for error reporting.

    Returns
    -------
    datetime.date or datetime.datetime

    Raises
    ------
    ResolutionError
        If ``value`` is a string that cannot be parsed as an ISO date/datetime.

    Examples
    --------
    >>> _read_date_or_datetime("2021-10-05", keypath=())
    datetime.date(2021, 10, 5)
    >>> _read_date_or_datetime(datetimelib.date(2021, 10, 5), keypath=())
    datetime.date(2021, 10, 5)
    >>> _read_date_or_datetime("2021-10-05 23:59:15", keypath=())
    datetime.datetime(2021, 10, 5, 23, 59, 15)

    """
    # a datetime is a subclass of date, so this passes both through unchanged
    if isinstance(value, datetimelib.date):
        return value
    if isinstance(value, str):
        # a string with no time is a date: as a datetime it would be midnight,
        # which then shows up as "00:00:00" wherever the result is inserted
        try:
            return datetimelib.date.fromisoformat(value)
        except ValueError:
            pass
        try:
            return datetimelib.datetime.fromisoformat(value)
        except ValueError:
            raise ResolutionError(f"Invalid date: '{value}'.", keypath)
    raise ResolutionError(
        f"Invalid date: expected a string or date/datetime object, "
        f"got {type(value).__name__}.",
        keypath,
    )


def _day(value: _DateOrDatetime) -> datetimelib.date:
    """The date of ``value``, a date or a datetime."""
    if isinstance(value, datetimelib.datetime):
        return value.date()
    return value


def _shift(
    reference: _DateOrDatetime, delta: datetimelib.timedelta, before: bool
) -> _DateOrDatetime:
    """``reference`` moved by ``delta``, earlier if ``before``, else later.

    A date moved by whole days stays a date. Moved by part of a day (hours, say),
    it becomes a datetime, starting from midnight.

    Examples
    --------
    >>> _shift(datetimelib.date(2021, 10, 5), datetimelib.timedelta(days=3), False)
    datetime.date(2021, 10, 8)
    >>> _shift(datetimelib.date(2021, 10, 5), datetimelib.timedelta(hours=3), True)
    datetime.datetime(2021, 10, 4, 21, 0)

    """
    # date arithmetic drops anything smaller than a day, so a date moved by part
    # of a day is made a datetime first
    whole_days = delta % datetimelib.timedelta(days=1) == datetimelib.timedelta(0)
    if not isinstance(reference, datetimelib.datetime) and not whole_days:
        reference = datetimelib.datetime.combine(reference, datetimelib.time())
    return reference - delta if before else reference + delta


def _read_offset(value: Configuration, keypath: KeyPath) -> datetimelib.timedelta:
    """Read an offset from a string or dict into a timedelta.

    Parameters
    ----------
    value : str or dict
        If a string, a comma-separated list of ``"<n> <unit>"`` pairs, e.g.,
        ``"1 week, 2 days"``; each unit may appear only once. If a dict, keys
        are unit names and values are integers, e.g., ``{"weeks": 1, "days": 2}``.
        Valid units are ``weeks``, ``days``, ``hours``, ``minutes``, and
        ``seconds``.
    keypath : tuple of str
        The keypath for error reporting.

    Returns
    -------
    datetime.timedelta

    Raises
    ------
    ResolutionError
        If the string cannot be parsed or repeats a unit, or the dict contains
        unknown units.

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
            # case-insensitive, like the rest of a date phrase ("3 Days After ...")
            match = re.match(
                r"^(\d+)\s+(week|day|hour|minute|second)s?$", part, flags=re.IGNORECASE
            )
            if not match:
                raise ResolutionError(f"Cannot parse offset: '{value}'.", keypath)
            amount, unit = match.groups()
            key = unit.lower() + "s"
            # a repeated unit ("1 day, 2 days") is almost surely a mistake;
            # assigning would silently drop the earlier amount, so reject it
            if key in kwargs:
                raise ResolutionError(
                    f"Unit '{unit.lower()}' appears more than once in offset: "
                    f"'{value}'.",
                    keypath,
                )
            kwargs[key] = int(amount)
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
    >>> sorted(_parse_weekdays("monday, friday", keypath=()))
    [<_DaysOfTheWeek.MONDAY: 0>, <_DaysOfTheWeek.FRIDAY: 4>]

    """
    normalized = raw.replace(",", " ").replace(" or ", " ")
    parts = normalized.split()
    return {_get_day_of_the_week(p, keypath) for p in parts}


def _parse_and_remove_time(
    s: str, keypath: KeyPath
) -> tuple[str, datetimelib.time | None]:
    """Extract and remove an ``at HH:MM`` or ``at HH:MM:SS`` suffix from a string.

    Parameters
    ----------
    s : str
        The input string, possibly ending with ``" at HH:MM"`` or ``" at HH:MM:SS"``.
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
    # seconds are optional and the hour may have one digit ("at 9:00"), as people
    # write times by hand. Without this, a time like "at 23:59" wouldn't match, so
    # it would be left on the end of the date, and the date would be reported as
    # invalid instead
    time_pattern = r" at (\d{1,2}):(\d{2})(?::(\d{2}))?$"
    match = re.search(time_pattern, s, flags=re.IGNORECASE)

    if match:
        hours, minutes = int(match.group(1)), int(match.group(2))
        seconds = int(match.group(3) or 0)
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
        ``_read_date_or_datetime``.
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
    >>> sorted(_read_skip_dates(["2021-10-05", "2021-10-06"], keypath=()))
    [datetime.date(2021, 10, 5), datetime.date(2021, 10, 6)]

    """
    if not isinstance(value, list):
        raise ResolutionError("'skip' must be a list of dates.", keypath)
    return {_day(_read_date_or_datetime(item, keypath)) for item in value}


def _find_first_weekday(
    reference: _DateOrDatetime,
    weekdays: set[_DaysOfTheWeek],
    before: bool,
) -> _DateOrDatetime:
    """Find the first occurrence of a weekday before/after a reference date.

    Parameters
    ----------
    reference : datetime.date or datetime.datetime
        The starting point. This date is excluded from the search.
    weekdays : set of _DaysOfTheWeek
        The target weekday(s) to search for.
    before : bool
        If True, search backward in time; otherwise search forward.

    Returns
    -------
    datetime.date or datetime.datetime
        The first matching date, of the same type as ``reference``. The time
        component of a datetime is preserved.

    Examples
    --------
    The first Monday after Sep 14, 2021 (a Tuesday):

    >>> _find_first_weekday(
    ...     datetimelib.datetime(2021, 9, 14), {_DaysOfTheWeek.MONDAY}, before=False
    ... )
    datetime.datetime(2021, 9, 20, 0, 0)

    """
    sign = -1 if before else 1
    delta = datetimelib.timedelta(days=sign)
    cursor = reference + delta
    while cursor.weekday() not in weekdays:
        cursor += delta
    return cursor


def _skip_excluded(
    result: _DateOrDatetime,
    skip_dates: set[datetimelib.date],
    next_candidate: Callable[[_DateOrDatetime], _DateOrDatetime],
    keypath: KeyPath,
) -> _DateOrDatetime:
    """Advance past excluded dates using a caller-supplied step function.

    Parameters
    ----------
    result : datetime.date or datetime.datetime
        The initial candidate date.
    skip_dates : set of datetime.date
        Dates to skip.
    next_candidate : callable
        A function ``(date) -> date`` that produces the next candidate when the
        current one is excluded.
    keypath : tuple of str
        The keypath for error reporting.

    Returns
    -------
    datetime.date or datetime.datetime

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
    while _day(result) in skip_dates:
        result = next_candidate(result)
        retries += 1
        if retries > _MAX_SKIP_RETRIES:
            raise ResolutionError(
                "Could not find a valid date: all candidates are excluded.",
                keypath,
            )
    return result


# the two computations =================================================================

# offset and first compute these from a dict, and parse from a string; doing it in
# one place means the two forms handle skips, missing weekdays and dates out of
# range the same way


def _describe_offset(delta: datetimelib.timedelta) -> str:
    """``delta`` in words, as written in an offset.

    Examples
    --------
    >>> _describe_offset(datetimelib.timedelta(days=5))
    '5 days'
    >>> _describe_offset(datetimelib.timedelta(days=1, hours=2, seconds=1))
    '1 day, 2 hours, 1 second'

    """
    hours, rest = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    amounts = [
        (delta.days, "day"),
        (hours, "hour"),
        (minutes, "minute"),
        (seconds, "second"),
    ]
    parts = [f"{n} {unit}{'' if n == 1 else 's'}" for n, unit in amounts if n]
    return ", ".join(parts) or "0 seconds"


def _offset_date(
    reference: _DateOrDatetime,
    delta: datetimelib.timedelta,
    before: bool,
    skip_dates: set[datetimelib.date],
    keypath: KeyPath,
) -> _DateOrDatetime:
    """``reference`` moved by ``delta``, then on past any of ``skip_dates``.

    Raises
    ------
    ResolutionError
        If the result is past the first or last representable date, or every
        candidate is skipped.

    """
    # going past the first or last representable date raises a bare
    # OverflowError, which would say nothing about which offset it was
    try:
        result = _shift(reference, delta, before=before)
        if skip_dates:
            day_step = datetimelib.timedelta(days=-1 if before else 1)
            result = _skip_excluded(
                result, skip_dates, lambda dt: dt + day_step, keypath
            )
    except OverflowError:
        direction = "before" if before else "after"
        raise ResolutionError(
            f"The date {_describe_offset(delta)} {direction} {reference} is out of "
            "range.",
            keypath,
        ) from None
    return result


def _first_weekday(
    reference: _DateOrDatetime,
    weekdays: set[_DaysOfTheWeek],
    before: bool,
    skip_dates: set[datetimelib.date],
    keypath: KeyPath,
) -> _DateOrDatetime:
    """The first of ``weekdays`` before or after ``reference``, not in ``skip_dates``.

    Raises
    ------
    ResolutionError
        If ``weekdays`` is empty, the result is past the first or last
        representable date, or every candidate is skipped.

    """
    # with no weekdays to match, the search would never stop (until the date
    # overflowed)
    if not weekdays:
        raise ResolutionError("At least one weekday must be given.", keypath)

    # going past the first or last representable date raises a bare
    # OverflowError, which would say nothing about which search it was
    try:
        result = _find_first_weekday(reference, weekdays, before=before)
        if skip_dates:
            result = _skip_excluded(
                result,
                skip_dates,
                lambda dt: _find_first_weekday(dt, weekdays, before=before),
                keypath,
            )
    except OverflowError:
        names = ", ".join(day.name.lower() for day in sorted(weekdays))
        direction = "before" if before else "after"
        raise ResolutionError(
            f"The first {names} {direction} {reference} is out of range.", keypath
        ) from None
    return result


# functions ============================================================================

# at -----------------------------------------------------------------------------------


def _check_input(
    args: FunctionArgs,
    function: str,
    allowed: set[str],
    required: tuple[str, ...] = (),
) -> ConfigurationDict:
    """``args.input``, checked to be a dict with the ``required`` keys and no others.

    An unknown key is otherwise ignored, so a misspelling like "skp" for "skip"
    would silently do nothing.

    """
    input_ = args.input
    if not isinstance(input_, dict):
        raise ResolutionError(
            f"Input to '{function}' must be a dictionary.", args.keypath
        )

    unknown = set(input_) - allowed
    if unknown:
        raise ResolutionError(
            f"Unknown key(s) in the input to '{function}': "
            f"{', '.join(sorted(map(str, unknown)))}. Its keys are "
            f"{', '.join(repr(k) for k in sorted(allowed))}.",
            args.keypath,
        )

    for key in required:
        if key not in input_:
            raise ResolutionError(
                f"Input to '{function}' must contain '{key}'.", args.keypath
            )
    return input_


def _direction(input_: ConfigurationDict, function: str, keypath: KeyPath) -> str:
    """Which of ``"before"`` and ``"after"`` the input to ``function`` contains.

    Raises
    ------
    ResolutionError
        If it contains neither or both.

    """
    has_before = "before" in input_
    has_after = "after" in input_

    if not has_before and not has_after:
        raise ResolutionError(
            f"Input to '{function}' must contain either 'before' or 'after'.",
            keypath,
        )

    if has_before and has_after:
        raise ResolutionError(
            f"Input to '{function}' must not contain both 'before' and 'after'.",
            keypath,
        )

    return "before" if has_before else "after"


def at(args: FunctionArgs) -> datetimelib.datetime:
    """Combine a date (or datetime) with a time, returning a new datetime.

    ``args.input`` should be a dictionary with keys:

        - ``date``: the reference date or datetime (string, date, or datetime)
        - ``time``: a time string in ISO format (e.g., ``"23:59:00"``)

    If the input date is already a datetime, the time component is overridden.

    """
    input_ = _check_input(args, "datetime.at", {"date", "time"}, ("date", "time"))

    reference = _read_date_or_datetime(input_["date"], args.keypath)

    raw_time = input_["time"]
    if not isinstance(raw_time, str):
        raise ResolutionError(
            f"'time' must be a string, got {type(raw_time).__name__}.", args.keypath
        )
    try:
        time = datetimelib.time.fromisoformat(raw_time)
    except ValueError:
        raise ResolutionError(f"Invalid time: '{raw_time}'.", args.keypath)

    # through _combine, so that the date's time zone is kept
    return _combine(reference, time)


def _combine(
    reference: _DateOrDatetime, time: datetimelib.time
) -> datetimelib.datetime:
    """The date of ``reference`` at ``time``, keeping ``reference``'s time zone.

    ``datetime.combine`` takes the time zone from ``time``, so a time without one
    (like ``10:00:00``) would drop the time zone of an aware reference. A time with
    its own time zone (like ``10:00:00+05:00``) keeps it, as the more specific.

    """
    # a date has no time zone to keep
    reference_tzinfo = getattr(reference, "tzinfo", None)
    tzinfo = time.tzinfo if time.tzinfo is not None else reference_tzinfo
    return datetimelib.datetime.combine(reference, time, tzinfo=tzinfo)


# offset -------------------------------------------------------------------------------


def offset(args: FunctionArgs) -> _DateOrDatetime:
    """Offset a date or datetime by a given amount.

    A date offset by whole days (or weeks) is a date; offset by hours, minutes or
    seconds, it is a datetime.

    ``args.input`` should be a dictionary with keys:

        - ``before`` or ``after``: the reference date (mutually exclusive)
        - ``by``: the offset amount (string or dict)

    """
    function = "datetime.offset"
    input_ = _check_input(args, function, {"before", "after", "by", "skip"})
    direction = _direction(input_, function, args.keypath)

    if "by" not in input_:
        raise ResolutionError(f"Input to '{function}' must contain 'by'.", args.keypath)

    skip_dates = _read_skip_dates(input_.get("skip", []), args.keypath)
    reference = _read_date_or_datetime(input_[direction], args.keypath)
    by = input_["by"]
    # convert the values of a dict of units, so that a value written as "${ n }",
    # which interpolates to a string, is accepted
    if isinstance(by, dict):
        by = {
            unit: to_integer(n, f"by.{unit}", function, args) for unit, n in by.items()
        }
    delta = _read_offset(by, args.keypath)

    before = direction == "before"
    return _offset_date(reference, delta, before, skip_dates, args.keypath)


# first --------------------------------------------------------------------------------


def first(args: FunctionArgs) -> _DateOrDatetime:
    """Find the first occurrence of a given weekday before/after a reference date.

    The result is a date if the reference is a date, and a datetime (at the same
    time of day) if it is a datetime.

    ``args.input`` should be a dictionary with keys:

        - ``weekday``: a day name (string) or list of day names
        - ``before`` or ``after``: the reference date (mutually exclusive)

    """
    function = "datetime.first"
    allowed = {"weekday", "before", "after", "skip"}
    input_ = _check_input(args, function, allowed, ("weekday",))
    direction = _direction(input_, function, args.keypath)

    raw_weekday = input_["weekday"]
    if isinstance(raw_weekday, str):
        weekdays = _parse_weekdays(raw_weekday, args.keypath)
    elif isinstance(raw_weekday, list):
        weekdays = {_get_day_of_the_week(d, args.keypath) for d in raw_weekday}
    else:
        raise ResolutionError(
            "The 'weekday' key must be a string or list of strings.", args.keypath
        )

    skip_dates = _read_skip_dates(input_.get("skip", []), args.keypath)
    reference = _read_date_or_datetime(input_[direction], args.keypath)

    before = direction == "before"
    return _first_weekday(reference, weekdays, before, skip_dates, args.keypath)


# parse --------------------------------------------------------------------------------


class _ParseError(Exception):
    """Raised when a parse attempt fails because the string does not match.

    Used for control flow: parsers are tried one after another until one
    succeeds.

    """


def _try_parse_first_weekday(s: str, keypath: KeyPath) -> _DateOrDatetime:
    """Try to parse ``s`` as ``"first <weekdays> after|before <reference>"``."""
    match = re.match(r"^first\s+(.+?)\s+(after|before)\s+(.+)$", s, flags=re.IGNORECASE)
    if not match:
        raise _ParseError

    weekday_raw, direction, reference_raw = match.groups()
    weekdays = _parse_weekdays(weekday_raw, keypath)
    reference = _read_date_or_datetime(reference_raw.strip(), keypath)
    before = direction.lower() == "before"
    return _first_weekday(reference, weekdays, before, set(), keypath)


def _try_read_offset(s: str, keypath: KeyPath) -> _DateOrDatetime:
    """Try to parse ``s`` as ``"<offset> after|before <reference>"``."""
    match = re.match(r"^(.+?)\s+(after|before)\s+(.+)$", s, flags=re.IGNORECASE)
    if not match:
        raise _ParseError

    offset_raw, direction, reference_raw = match.groups()
    delta = _read_offset(offset_raw.strip(), keypath)
    reference = _read_date_or_datetime(reference_raw.strip(), keypath)
    before = direction.lower() == "before"
    return _offset_date(reference, delta, before, set(), keypath)


def _try_parse_iso(s: str, keypath: KeyPath) -> _DateOrDatetime:
    """Try to parse ``s`` as a plain ISO date or datetime."""
    try:
        return _read_date_or_datetime(s.strip(), keypath)
    except ResolutionError:
        raise _ParseError


def parse(args: FunctionArgs) -> _DateOrDatetime:
    """Parse a natural language date/datetime string.

    ``args.input`` should be a string in one of the following forms:

        - An ISO date or datetime: ``"2021-10-05"`` or ``"2021-10-05 23:59:10"``
        - An offset: ``"3 days after 2021-10-05"``
        - A first-weekday: ``"first monday, friday after 2021-09-14"``

    Any form may end with an ``" at HH:MM"`` or ``" at HH:MM:SS"`` suffix to
    override the time component of the result.

    The result is a date when nothing in the string gives a time (a date, offset
    by whole days or found by weekday), and a datetime otherwise.

    """
    if not isinstance(args.input, str):
        raise ResolutionError(
            "Input to 'datetime.parse' must be a string.", args.keypath
        )

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
        # through _combine, so that the date's time zone is kept
        result = _combine(result, time_override)

    return result


DATETIME_FUNCTIONS: FunctionMapping = {
    "at": at,
    "first": first,
    "offset": offset,
    "parse": parse,
}
