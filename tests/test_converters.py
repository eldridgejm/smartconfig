from smartconfig import converters
from smartconfig.exceptions import ConversionError

import datetime

from pytest import raises


# integer ==============================================================================


def test_integer_from_int():
    assert converters.integer(42) == 42


def test_integer_from_whole_float():
    result = converters.integer(3.0)
    assert result == 3
    assert isinstance(result, int)


def test_integer_from_non_whole_float_raises():
    with raises(ConversionError):
        converters.integer(3.5)


def test_integer_from_numeric_string():
    assert converters.integer("42") == 42


def test_integer_from_invalid_string_raises():
    with raises(ConversionError):
        converters.integer("not a number")


def test_integer_from_bool_raises():
    with raises(ConversionError):
        converters.integer(True)


# float ================================================================================


def test_float_from_float():
    assert converters.float_(4.5) == 4.5


def test_float_from_int():
    result = converters.float_(3)
    assert result == 3.0
    assert isinstance(result, float)


def test_float_from_numeric_string():
    assert converters.float_("4.5") == 4.5


def test_float_from_invalid_string_raises():
    with raises(ConversionError):
        converters.float_("not a number")


def test_float_from_bool_raises():
    with raises(ConversionError):
        converters.float_(True)


# boolean ==============================================================================


def test_boolean_from_bool():
    assert converters.boolean(True) is True
    assert converters.boolean(False) is False


def test_boolean_from_true_string():
    assert converters.boolean("True") is True


def test_boolean_from_false_string():
    assert converters.boolean("False") is False


def test_boolean_from_other_string_raises():
    with raises(ConversionError):
        converters.boolean("yes")


def test_boolean_from_non_string_raises():
    with raises(ConversionError):
        converters.boolean(42)  # type: ignore[arg-type]


# date =================================================================================


def test_date_from_iso_string():
    assert converters.date("2021-10-05") == datetime.date(2021, 10, 5)


def test_date_from_iso_datetime_string_discards_time():
    assert converters.date("2021-10-05 23:59:10") == datetime.date(2021, 10, 5)


def test_date_from_date_object_passthrough():
    assert converters.date(datetime.date(2021, 10, 5)) == datetime.date(2021, 10, 5)


def test_date_from_datetime_object_simplifies():
    assert converters.date(datetime.datetime(2021, 10, 5, 23, 59, 59)) == datetime.date(
        2021, 10, 5
    )


def test_date_raises_on_invalid_string():
    with raises(ConversionError):
        converters.date("not-a-date")


def test_date_raises_on_non_string_non_date():
    with raises(ConversionError):
        converters.date(42)  # type: ignore[arg-type]


# datetime =============================================================================


def test_datetime_from_iso_string():
    assert converters.datetime("2021-10-05 23:59:10") == datetime.datetime(
        2021, 10, 5, 23, 59, 10
    )


def test_datetime_from_datetime_object_passthrough():
    assert converters.datetime(
        datetime.datetime(2021, 10, 5, 12, 0)
    ) == datetime.datetime(2021, 10, 5, 12, 0)


def test_datetime_from_date_only_string_raises():
    with raises(ConversionError) as exc:
        converters.datetime("2021-10-05")

    assert "time component" in str(exc.value)


def test_datetime_from_date_object_raises():
    with raises(ConversionError) as exc:
        converters.datetime(datetime.date(2021, 10, 5))

    assert "Cannot implicitly convert" in str(exc.value)


def test_datetime_raises_on_invalid_string():
    with raises(ConversionError):
        converters.datetime("not-a-datetime 12:00:00")


def test_datetime_raises_on_non_string_non_date():
    with raises(ConversionError):
        converters.datetime(42)  # type: ignore[arg-type]


def test_datetime_accepts_midnight_if_explicitly_written():
    """'2021-10-05 00:00:00' has an explicit time component and should be accepted."""
    assert converters.datetime("2021-10-05 00:00:00") == datetime.datetime(
        2021, 10, 5, 0, 0, 0
    )
