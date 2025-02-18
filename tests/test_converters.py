from smartconfig import converters
from smartconfig.exceptions import ConversionError

import datetime

from pytest import raises


# arithmetic ===========================================================================


def test_integer_arithmetic():
    # given
    converter = converters.arithmetic(int)

    # when
    result = converter("(42 - 10) * 3 + 2")

    # then
    assert result == 98


def test_float_arithmetic():
    # given
    converter = converters.arithmetic(float)

    # when
    result = converter("9 / 2")

    # then
    assert result == 4.5


def test_arithmetic_raises_type_error_if_given_unknown_operator():
    # given
    converter = converters.arithmetic(int)

    # when / then
    with raises(ConversionError):
        converter("9 % 2")


def test_arithmetic_with_negative_numbers():
    # given
    converter = converters.arithmetic(int)

    # when
    result = converter("-9 + 2")

    # then
    assert result == -7


def test_arithmetic_parser_when_given_integer_value_leaves_it_alone():
    # given
    converter = converters.arithmetic(int)

    # when
    result = converter(42)

    # then
    assert result == 42


def test_arithmetic_parser_when_given_float_value_leaves_it_alone():
    # given
    converter = converters.arithmetic(float)

    # when
    result = converter(42.0)

    # then
    assert result == 42.0


def test_integer_parser_when_given_float_value_raises():
    # given
    converter = converters.arithmetic(int)

    # when
    with raises(ConversionError):
        converter(42.9)


def test_float_parser_when_given_integer_value_leaves_it_alone():
    # given
    converter = converters.arithmetic(float)

    # when
    result = converter(42)

    # then
    assert result == 42.0


def test_arithmetic_parser_when_given_syntax_error_raises():
    # given
    converter = converters.arithmetic(int)

    # when
    with raises(ConversionError):
        converter("not a number")


# logic ================================================================================


def test_logic():
    assert converters.logic("True and not (False or True)") is False


def test_logic_raises_type_error_if_given_unknown_operator():
    # given
    converter = converters.logic

    # when / then
    with raises(ConversionError):
        converter("True % False")


def test_logic_parser_when_given_bool_value_leaves_it_alone():
    # given
    converter = converters.logic

    # when
    result = converter(True)

    # then
    assert result is True


def test_logic_parser_when_given_integer_value_raises():
    # given
    converter = converters.logic

    # when
    with raises(ConversionError) as exc:
        converter(42)

    assert "Cannot convert type <class 'int'> to bool." in str(exc.value)


def test_logic_parser_when_given_syntax_error_raises():
    # given
    converter = converters.logic

    # when
    with raises(ConversionError):
        converter("not a boolean")


# smartdate ============================================================================


def test_smartdate_from_explicit_date():
    assert converters.smartdate("2021-10-05") == datetime.date(2021, 10, 5)


def test_smartdate_from_explicit_datetime():
    assert converters.smartdate("2021-10-05 23:59:10") == datetime.date(2021, 10, 5)


def test_smartdate_delta_days_before():
    assert converters.smartdate("3 days before 2021-10-05") == datetime.date(
        2021, 10, 2
    )


def test_smartdate_delta_days_after():
    assert converters.smartdate("3 days after 2021-10-05") == datetime.date(2021, 10, 8)


def test_smartdate_delta_days_simplifies_datetimes_to_dates():
    assert converters.smartdate("3 days before 2021-10-05 23:59:00") == datetime.date(
        2021, 10, 2
    )


def test_smartdate_first_date_before():
    assert converters.smartdate("first monday before 2021-09-17") == datetime.date(
        2021, 9, 13
    )


def test_smartdate_first_date_after():
    assert converters.smartdate("first monday after 2021-09-10") == datetime.date(
        2021, 9, 13
    )


def test_smartdate_first_date_after_multiple_choices():
    assert converters.smartdate(
        "first monday, friday after 2021-09-14"
    ) == datetime.date(2021, 9, 17)


def test_smartdate_first_date_before_simplifies_datetimes_to_dates():
    assert converters.smartdate(
        "first monday before 2021-09-14 23:59:00"
    ) == datetime.date(2021, 9, 13)


def test_smartdate_raises_if_no_pattern_is_matched():
    with raises(ConversionError):
        converters.smartdate("foo")


def test_smartdate_given_a_date_object_leaves_it_alone():
    assert converters.smartdate(datetime.date(2021, 10, 5)) == datetime.date(
        2021, 10, 5
    )


def test_smartdate_given_a_datetime_object_simplifies_it_to_date():
    assert converters.smartdate(
        datetime.datetime(2021, 10, 5, 23, 59, 59)
    ) == datetime.date(2021, 10, 5)


# smartdatetime ========================================================================


def test_smartdatetime_from_explicit_date():
    assert converters.smartdatetime("2021-10-05") == datetime.datetime(2021, 10, 5)


def test_smartdatetime_from_explicit_datetime():
    assert converters.smartdatetime("2021-10-05 23:59:10") == datetime.datetime(
        2021, 10, 5, 23, 59, 10
    )


def test_smartdatetime_from_explicit_datetime_with_at_time_overwrites():
    assert converters.smartdatetime(
        "2021-10-05 23:59:10 at 22:00:00"
    ) == datetime.datetime(2021, 10, 5, 22, 0, 0)


def test_smartdatetime_delta_days_before():
    assert converters.smartdatetime(
        "3 days before 2021-10-05 23:59:15"
    ) == datetime.datetime(2021, 10, 2, 23, 59, 15)


def test_smartdatetime_delta_days_after():
    assert converters.smartdatetime(
        "3 days after 2021-10-05 23:59:15"
    ) == datetime.datetime(2021, 10, 8, 23, 59, 15)


def test_smartdatetime_delta_allows_overwriting_time_with_at():
    assert converters.smartdatetime(
        "3 days before 2021-10-05 23:59:15 at 22:00:00"
    ) == datetime.datetime(2021, 10, 2, 22, 0, 0)


def test_smartdatetime_delta_hours_before():
    assert converters.smartdatetime(
        "3 hours before 2021-10-05 23:59:15"
    ) == datetime.datetime(2021, 10, 5, 20, 59, 15)


def test_smartdatetime_delta_hours_after():
    assert converters.smartdatetime(
        "3 hours after 2021-10-05 23:59:15"
    ) == datetime.datetime(2021, 10, 6, 2, 59, 15)


def test_smartdatetime_first_date_before():
    assert converters.smartdatetime(
        "first monday before 2021-09-17"
    ) == datetime.datetime(2021, 9, 13)


def test_smartdatetime_first_date_after():
    assert converters.smartdatetime(
        "first monday after 2021-09-10"
    ) == datetime.datetime(2021, 9, 13)


def test_smartdatetime_first_date_after_multiple_choices():
    assert converters.smartdatetime(
        "first monday, friday after 2021-09-14"
    ) == datetime.datetime(2021, 9, 17)


def test_smartdatetime_first_date_after_allows_overwriting_time_with_at():
    assert converters.smartdatetime(
        "first monday after 2021-09-14 23:59:00 at 22:00:00"
    ) == datetime.datetime(2021, 9, 20, 22, 0, 0)


def test_smartdatetime_raises_if_time_is_invalid():
    with raises(ConversionError):
        converters.smartdatetime("first monday after 2021-10-05 at 23:99:10")


def test_smartdatetime_raises_if_date_is_invalid():
    with raises(ConversionError):
        converters.smartdatetime("3 days after 2021-99-05 23:59:10")


def test_raises_if_invalid_day_of_the_week_is_given():
    with raises(ConversionError):
        converters.smartdatetime("first foo after 2021-09-14")


def test_smartdatetime_given_a_datetime_object_leaves_it_alone():
    assert converters.smartdatetime(
        datetime.datetime(2021, 10, 5)
    ) == datetime.datetime(2021, 10, 5)


def test_smartdatetime_given_a_date_object_raises():
    with raises(ConversionError) as exc:
        converters.smartdatetime(datetime.date(2021, 10, 5))

    assert "Cannot implicitly convert" in str(exc.value)
