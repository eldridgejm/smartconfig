"""Tests for smartconfig.stdlib.datetime: at, offset, first, and parse."""

import datetime

from smartconfig import resolve, exceptions
from smartconfig.stdlib.datetime import at, first, offset, parse
from smartconfig.types import Schema, ConfigurationDict

from pytest import raises


# at ===============================================================================

AT_SCHEMA: Schema = {
    "type": "dict",
    "required_keys": {
        "result": {"type": "datetime"},
    },
}

AT_FUNCTIONS = {"datetime": {"at": at}}


def test_at_date_string_with_time():
    cfg: ConfigurationDict = {
        "result": {"__datetime.at__": {"date": "2021-10-05", "time": "23:59:00"}}
    }
    resolved = resolve(cfg, AT_SCHEMA, functions=AT_FUNCTIONS)
    assert resolved == {"result": datetime.datetime(2021, 10, 5, 23, 59)}


def test_at_datetime_string_overrides_time():
    cfg: ConfigurationDict = {
        "result": {
            "__datetime.at__": {"date": "2021-10-05 12:00:00", "time": "23:59:00"}
        }
    }
    resolved = resolve(cfg, AT_SCHEMA, functions=AT_FUNCTIONS)
    assert resolved == {"result": datetime.datetime(2021, 10, 5, 23, 59)}


def test_at_date_object_with_time():
    cfg: ConfigurationDict = {
        "result": {
            "__datetime.at__": {"date": datetime.date(2021, 10, 5), "time": "23:59:00"}
        }
    }
    resolved = resolve(cfg, AT_SCHEMA, functions=AT_FUNCTIONS)
    assert resolved == {"result": datetime.datetime(2021, 10, 5, 23, 59)}


def test_at_datetime_object_overrides_time():
    cfg: ConfigurationDict = {
        "result": {
            "__datetime.at__": {
                "date": datetime.datetime(2021, 10, 5, 12, 0, 0),
                "time": "23:59:00",
            }
        }
    }
    resolved = resolve(cfg, AT_SCHEMA, functions=AT_FUNCTIONS)
    assert resolved == {"result": datetime.datetime(2021, 10, 5, 23, 59)}


def test_at_raises_if_input_is_not_a_dict():
    cfg: ConfigurationDict = {"result": {"__datetime.at__": "not a dict"}}
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, AT_SCHEMA, functions=AT_FUNCTIONS)
    assert "Input to 'at' must be a dictionary" in str(exc.value)


def test_at_raises_if_date_missing():
    cfg: ConfigurationDict = {"result": {"__datetime.at__": {"time": "23:59:00"}}}
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, AT_SCHEMA, functions=AT_FUNCTIONS)
    assert "must contain 'date'" in str(exc.value)


def test_at_raises_if_time_missing():
    cfg: ConfigurationDict = {"result": {"__datetime.at__": {"date": "2021-10-05"}}}
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, AT_SCHEMA, functions=AT_FUNCTIONS)
    assert "must contain 'time'" in str(exc.value)


def test_at_raises_if_time_is_invalid():
    cfg: ConfigurationDict = {
        "result": {"__datetime.at__": {"date": "2021-10-05", "time": "not-a-time"}}
    }
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, AT_SCHEMA, functions=AT_FUNCTIONS)
    assert "Invalid time" in str(exc.value)


# offset ===========================================================================


def test_offset_before_string_days():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "deadline": {"type": "datetime"},
        },
    }

    cfg: ConfigurationDict = {
        "deadline": {"__datetime.offset__": {"before": "2021-10-05", "by": "3 days"}}
    }

    resolved = resolve(cfg, schema, functions={"datetime": {"offset": offset}})

    assert resolved == {"deadline": datetime.datetime(2021, 10, 2)}


def test_offset_after_string_days():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "deadline": {"type": "datetime"},
        },
    }

    cfg: ConfigurationDict = {
        "deadline": {"__datetime.offset__": {"after": "2021-10-05", "by": "3 days"}}
    }

    resolved = resolve(cfg, schema, functions={"datetime": {"offset": offset}})

    assert resolved == {"deadline": datetime.datetime(2021, 10, 8)}


def test_offset_before_with_datetime_reference():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "deadline": {"type": "datetime"},
        },
    }

    cfg: ConfigurationDict = {
        "deadline": {
            "__datetime.offset__": {"before": "2021-10-05 23:59:15", "by": "3 days"}
        }
    }

    resolved = resolve(cfg, schema, functions={"datetime": {"offset": offset}})

    assert resolved == {"deadline": datetime.datetime(2021, 10, 2, 23, 59, 15)}


def test_offset_after_with_datetime_reference():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "deadline": {"type": "datetime"},
        },
    }

    cfg: ConfigurationDict = {
        "deadline": {
            "__datetime.offset__": {"after": "2021-10-05 23:59:15", "by": "3 days"}
        }
    }

    resolved = resolve(cfg, schema, functions={"datetime": {"offset": offset}})

    assert resolved == {"deadline": datetime.datetime(2021, 10, 8, 23, 59, 15)}


def test_offset_before_string_hours():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "deadline": {"type": "datetime"},
        },
    }

    cfg: ConfigurationDict = {
        "deadline": {
            "__datetime.offset__": {"before": "2021-10-05 23:59:15", "by": "3 hours"}
        }
    }

    resolved = resolve(cfg, schema, functions={"datetime": {"offset": offset}})

    assert resolved == {"deadline": datetime.datetime(2021, 10, 5, 20, 59, 15)}


def test_offset_after_string_hours():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "deadline": {"type": "datetime"},
        },
    }

    cfg: ConfigurationDict = {
        "deadline": {
            "__datetime.offset__": {"after": "2021-10-05 23:59:15", "by": "3 hours"}
        }
    }

    resolved = resolve(cfg, schema, functions={"datetime": {"offset": offset}})

    assert resolved == {"deadline": datetime.datetime(2021, 10, 6, 2, 59, 15)}


def test_offset_string_multiple_units():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "deadline": {"type": "datetime"},
        },
    }

    cfg: ConfigurationDict = {
        "deadline": {
            "__datetime.offset__": {"after": "2021-10-05", "by": "1 week, 2 days"}
        }
    }

    resolved = resolve(cfg, schema, functions={"datetime": {"offset": offset}})

    assert resolved == {"deadline": datetime.datetime(2021, 10, 14)}


def test_offset_string_multiple_units_irregular_spacing():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "deadline": {"type": "datetime"},
        },
    }

    for by_str in ["1 week,2 days", "1 week,  2 days", "1 week , 2 days"]:
        cfg: ConfigurationDict = {
            "deadline": {"__datetime.offset__": {"after": "2021-10-05", "by": by_str}}
        }

        resolved = resolve(cfg, schema, functions={"datetime": {"offset": offset}})

        assert resolved == {"deadline": datetime.datetime(2021, 10, 14)}


def test_offset_before_dict():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "deadline": {"type": "datetime"},
        },
    }

    cfg: ConfigurationDict = {
        "deadline": {"__datetime.offset__": {"before": "2021-10-05", "by": {"days": 3}}}
    }

    resolved = resolve(cfg, schema, functions={"datetime": {"offset": offset}})

    assert resolved == {"deadline": datetime.datetime(2021, 10, 2)}


def test_offset_after_dict_multiple_units():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "deadline": {"type": "datetime"},
        },
    }

    cfg: ConfigurationDict = {
        "deadline": {
            "__datetime.offset__": {
                "after": "2021-10-05",
                "by": {"weeks": 1, "days": 2},
            }
        }
    }

    resolved = resolve(cfg, schema, functions={"datetime": {"offset": offset}})

    assert resolved == {"deadline": datetime.datetime(2021, 10, 14)}


def test_offset_with_date_object_reference():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "deadline": {"type": "datetime"},
        },
    }

    cfg: ConfigurationDict = {
        "deadline": {
            "__datetime.offset__": {
                "before": datetime.date(2021, 10, 5),
                "by": "3 days",
            }
        }
    }

    resolved = resolve(cfg, schema, functions={"datetime": {"offset": offset}})

    assert resolved == {"deadline": datetime.datetime(2021, 10, 2)}


def test_offset_with_datetime_object_reference():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "deadline": {"type": "datetime"},
        },
    }

    cfg: ConfigurationDict = {
        "deadline": {
            "__datetime.offset__": {
                "before": datetime.datetime(2021, 10, 5, 23, 59, 15),
                "by": "3 days",
            }
        }
    }

    resolved = resolve(cfg, schema, functions={"datetime": {"offset": offset}})

    assert resolved == {"deadline": datetime.datetime(2021, 10, 2, 23, 59, 15)}


def test_offset_raises_if_input_is_not_a_dict():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "deadline": {"type": "datetime"},
        },
    }

    cfg: ConfigurationDict = {"deadline": {"__datetime.offset__": "not a dict"}}

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"datetime": {"offset": offset}})

    assert "Input to 'offset' must be a dictionary" in str(exc.value)


def test_offset_raises_if_no_reference_provided():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "deadline": {"type": "datetime"},
        },
    }

    cfg: ConfigurationDict = {"deadline": {"__datetime.offset__": {"by": "3 days"}}}

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"datetime": {"offset": offset}})

    assert "must contain either 'before' or 'after'" in str(exc.value)


def test_offset_raises_if_both_before_and_after():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "deadline": {"type": "datetime"},
        },
    }

    cfg: ConfigurationDict = {
        "deadline": {
            "__datetime.offset__": {
                "before": "2021-10-05",
                "after": "2021-10-05",
                "by": "3 days",
            }
        }
    }

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"datetime": {"offset": offset}})

    assert "must not contain both 'before' and 'after'" in str(exc.value)


def test_offset_raises_if_by_missing():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "deadline": {"type": "datetime"},
        },
    }

    cfg: ConfigurationDict = {
        "deadline": {"__datetime.offset__": {"after": "2021-10-05"}}
    }

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"datetime": {"offset": offset}})

    assert "must contain 'by'" in str(exc.value)


def test_offset_raises_if_reference_is_invalid():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "deadline": {"type": "datetime"},
        },
    }

    cfg: ConfigurationDict = {
        "deadline": {"__datetime.offset__": {"after": "not-a-date", "by": "3 days"}}
    }

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"datetime": {"offset": offset}})

    assert "Invalid date" in str(exc.value)


def test_offset_raises_if_by_string_is_invalid():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "deadline": {"type": "datetime"},
        },
    }

    cfg: ConfigurationDict = {
        "deadline": {"__datetime.offset__": {"after": "2021-10-05", "by": "not valid"}}
    }

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"datetime": {"offset": offset}})

    assert "Cannot parse offset" in str(exc.value)


def test_offset_raises_if_by_dict_has_unknown_units():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "deadline": {"type": "datetime"},
        },
    }

    cfg: ConfigurationDict = {
        "deadline": {
            "__datetime.offset__": {"after": "2021-10-05", "by": {"fortnights": 1}}
        }
    }

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"datetime": {"offset": offset}})

    assert "Unknown unit" in str(exc.value)


# offset + skip ==================================================================


def test_offset_after_skip_skips_excluded_date():
    """3 days after Oct 5 = Oct 8, but Oct 8 excluded, so result is Oct 9."""
    schema: Schema = {
        "type": "dict",
        "required_keys": {"deadline": {"type": "datetime"}},
    }
    cfg: ConfigurationDict = {
        "deadline": {
            "__datetime.offset__": {
                "after": "2021-10-05",
                "by": "3 days",
                "skip": ["2021-10-08"],
            }
        }
    }
    resolved = resolve(cfg, schema, functions={"datetime": {"offset": offset}})
    assert resolved == {"deadline": datetime.datetime(2021, 10, 9)}


def test_offset_before_skip_skips_excluded_date():
    """3 days before Oct 5 = Oct 2, but Oct 2 excluded, so result is Oct 1."""
    schema: Schema = {
        "type": "dict",
        "required_keys": {"deadline": {"type": "datetime"}},
    }
    cfg: ConfigurationDict = {
        "deadline": {
            "__datetime.offset__": {
                "before": "2021-10-05",
                "by": "3 days",
                "skip": ["2021-10-02"],
            }
        }
    }
    resolved = resolve(cfg, schema, functions={"datetime": {"offset": offset}})
    assert resolved == {"deadline": datetime.datetime(2021, 10, 1)}


def test_offset_after_skip_skips_multiple_consecutive():
    """Oct 8, 9, 10 all excluded: result is Oct 11."""
    schema: Schema = {
        "type": "dict",
        "required_keys": {"deadline": {"type": "datetime"}},
    }
    cfg: ConfigurationDict = {
        "deadline": {
            "__datetime.offset__": {
                "after": "2021-10-05",
                "by": "3 days",
                "skip": ["2021-10-08", "2021-10-09", "2021-10-10"],
            }
        }
    }
    resolved = resolve(cfg, schema, functions={"datetime": {"offset": offset}})
    assert resolved == {"deadline": datetime.datetime(2021, 10, 11)}


def test_offset_after_skip_preserves_time():
    schema: Schema = {
        "type": "dict",
        "required_keys": {"deadline": {"type": "datetime"}},
    }
    cfg: ConfigurationDict = {
        "deadline": {
            "__datetime.offset__": {
                "after": "2021-10-05 23:59:15",
                "by": "3 days",
                "skip": ["2021-10-08"],
            }
        }
    }
    resolved = resolve(cfg, schema, functions={"datetime": {"offset": offset}})
    assert resolved == {"deadline": datetime.datetime(2021, 10, 9, 23, 59, 15)}


def test_offset_after_skip_with_hours_offset():
    """3 hours after Oct 5 23:00 = Oct 6 02:00; Oct 6 excluded, so Oct 7 02:00."""
    schema: Schema = {
        "type": "dict",
        "required_keys": {"deadline": {"type": "datetime"}},
    }
    cfg: ConfigurationDict = {
        "deadline": {
            "__datetime.offset__": {
                "after": "2021-10-05 23:00:00",
                "by": "3 hours",
                "skip": ["2021-10-06"],
            }
        }
    }
    resolved = resolve(cfg, schema, functions={"datetime": {"offset": offset}})
    assert resolved == {"deadline": datetime.datetime(2021, 10, 7, 2, 0, 0)}


def test_offset_skip_empty_list_is_noop():
    schema: Schema = {
        "type": "dict",
        "required_keys": {"deadline": {"type": "datetime"}},
    }
    cfg: ConfigurationDict = {
        "deadline": {
            "__datetime.offset__": {
                "after": "2021-10-05",
                "by": "3 days",
                "skip": [],
            }
        }
    }
    resolved = resolve(cfg, schema, functions={"datetime": {"offset": offset}})
    assert resolved == {"deadline": datetime.datetime(2021, 10, 8)}


# first ============================================================================


def test_first_before():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "due": {"type": "datetime"},
        },
    }

    cfg: ConfigurationDict = {
        "due": {"__datetime.first__": {"weekday": "monday", "before": "2021-09-17"}}
    }

    resolved = resolve(cfg, schema, functions={"datetime": {"first": first}})

    assert resolved == {"due": datetime.datetime(2021, 9, 13)}


def test_first_after():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "due": {"type": "datetime"},
        },
    }

    cfg: ConfigurationDict = {
        "due": {"__datetime.first__": {"weekday": "monday", "after": "2021-09-10"}}
    }

    resolved = resolve(cfg, schema, functions={"datetime": {"first": first}})

    assert resolved == {"due": datetime.datetime(2021, 9, 13)}


def test_first_after_multiple_choices_list():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "due": {"type": "datetime"},
        },
    }

    cfg: ConfigurationDict = {
        "due": {
            "__datetime.first__": {
                "weekday": ["monday", "friday"],
                "after": "2021-09-14",
            }
        }
    }

    resolved = resolve(cfg, schema, functions={"datetime": {"first": first}})

    assert resolved == {"due": datetime.datetime(2021, 9, 17)}


def test_first_after_multiple_choices_comma_separated():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "due": {"type": "datetime"},
        },
    }

    cfg: ConfigurationDict = {
        "due": {
            "__datetime.first__": {
                "weekday": "monday, friday",
                "after": "2021-09-14",
            }
        }
    }

    resolved = resolve(cfg, schema, functions={"datetime": {"first": first}})

    assert resolved == {"due": datetime.datetime(2021, 9, 17)}


def test_first_after_multiple_choices_comma_separated_irregular_spacing():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "due": {"type": "datetime"},
        },
    }

    for weekday_str in ["monday,friday", "monday,  friday", "monday ,friday"]:
        cfg: ConfigurationDict = {
            "due": {
                "__datetime.first__": {
                    "weekday": weekday_str,
                    "after": "2021-09-14",
                }
            }
        }

        resolved = resolve(cfg, schema, functions={"datetime": {"first": first}})

        assert resolved == {"due": datetime.datetime(2021, 9, 17)}


def test_first_before_with_datetime_reference():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "due": {"type": "datetime"},
        },
    }

    cfg: ConfigurationDict = {
        "due": {
            "__datetime.first__": {
                "weekday": "monday",
                "before": "2021-09-17 12:00:00",
            }
        }
    }

    resolved = resolve(cfg, schema, functions={"datetime": {"first": first}})

    assert resolved == {"due": datetime.datetime(2021, 9, 13, 12, 0, 0)}


def test_first_after_with_datetime_reference():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "due": {"type": "datetime"},
        },
    }

    cfg: ConfigurationDict = {
        "due": {
            "__datetime.first__": {
                "weekday": "monday",
                "after": "2021-09-10 12:00:00",
            }
        }
    }

    resolved = resolve(cfg, schema, functions={"datetime": {"first": first}})

    assert resolved == {"due": datetime.datetime(2021, 9, 13, 12, 0, 0)}


def test_first_after_multiple_choices_with_datetime():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "due": {"type": "datetime"},
        },
    }

    cfg: ConfigurationDict = {
        "due": {
            "__datetime.first__": {
                "weekday": ["monday", "friday"],
                "after": "2021-09-14 12:00:00",
            }
        }
    }

    resolved = resolve(cfg, schema, functions={"datetime": {"first": first}})

    assert resolved == {"due": datetime.datetime(2021, 9, 17, 12, 0, 0)}


def test_first_raises_if_input_is_not_a_dict():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "due": {"type": "datetime"},
        },
    }

    cfg: ConfigurationDict = {"due": {"__datetime.first__": "not a dict"}}

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"datetime": {"first": first}})

    assert "Input to 'first' must be a dictionary" in str(exc.value)


def test_first_raises_if_weekday_missing():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "due": {"type": "datetime"},
        },
    }

    cfg: ConfigurationDict = {"due": {"__datetime.first__": {"after": "2021-09-10"}}}

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"datetime": {"first": first}})

    assert "must contain 'weekday'" in str(exc.value)


def test_first_raises_if_no_direction_provided():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "due": {"type": "datetime"},
        },
    }

    cfg: ConfigurationDict = {"due": {"__datetime.first__": {"weekday": "monday"}}}

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"datetime": {"first": first}})

    assert "must contain either 'before' or 'after'" in str(exc.value)


def test_first_raises_if_both_directions_provided():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "due": {"type": "datetime"},
        },
    }

    cfg: ConfigurationDict = {
        "due": {
            "__datetime.first__": {
                "weekday": "monday",
                "before": "2021-09-17",
                "after": "2021-09-10",
            }
        }
    }

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"datetime": {"first": first}})

    assert "must not contain both 'before' and 'after'" in str(exc.value)


def test_first_raises_if_invalid_weekday():
    schema: Schema = {
        "type": "dict",
        "required_keys": {
            "due": {"type": "datetime"},
        },
    }

    cfg: ConfigurationDict = {
        "due": {"__datetime.first__": {"weekday": "notaday", "after": "2021-09-10"}}
    }

    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"datetime": {"first": first}})

    assert "Invalid day of week" in str(exc.value)


# first + skip ===================================================================


def test_first_after_skip_skips_excluded_date():
    """First monday after Sep 10 is Sep 13, but Sep 13 excluded, so Sep 20."""
    schema: Schema = {
        "type": "dict",
        "required_keys": {"due": {"type": "datetime"}},
    }
    cfg: ConfigurationDict = {
        "due": {
            "__datetime.first__": {
                "weekday": "monday",
                "after": "2021-09-10",
                "skip": ["2021-09-13"],
            }
        }
    }
    resolved = resolve(cfg, schema, functions={"datetime": {"first": first}})
    assert resolved == {"due": datetime.datetime(2021, 9, 20)}


def test_first_after_skip_skips_multiple_excluded_dates():
    """Sep 13 and Sep 20 both excluded; result is Sep 27."""
    schema: Schema = {
        "type": "dict",
        "required_keys": {"due": {"type": "datetime"}},
    }
    cfg: ConfigurationDict = {
        "due": {
            "__datetime.first__": {
                "weekday": "monday",
                "after": "2021-09-10",
                "skip": ["2021-09-13", "2021-09-20"],
            }
        }
    }
    resolved = resolve(cfg, schema, functions={"datetime": {"first": first}})
    assert resolved == {"due": datetime.datetime(2021, 9, 27)}


def test_first_before_skip_skips_excluded_date():
    """First monday before Sep 17 is Sep 13, but Sep 13 excluded, so Sep 6."""
    schema: Schema = {
        "type": "dict",
        "required_keys": {"due": {"type": "datetime"}},
    }
    cfg: ConfigurationDict = {
        "due": {
            "__datetime.first__": {
                "weekday": "monday",
                "before": "2021-09-17",
                "skip": ["2021-09-13"],
            }
        }
    }
    resolved = resolve(cfg, schema, functions={"datetime": {"first": first}})
    assert resolved == {"due": datetime.datetime(2021, 9, 6)}


def test_first_after_skip_with_date_objects():
    schema: Schema = {
        "type": "dict",
        "required_keys": {"due": {"type": "datetime"}},
    }
    cfg: ConfigurationDict = {
        "due": {
            "__datetime.first__": {
                "weekday": "monday",
                "after": "2021-09-10",
                "skip": [datetime.date(2021, 9, 13)],
            }
        }
    }
    resolved = resolve(cfg, schema, functions={"datetime": {"first": first}})
    assert resolved == {"due": datetime.datetime(2021, 9, 20)}


def test_first_after_skip_with_datetime_objects():
    """Only the date part of datetime objects in skip is compared."""
    schema: Schema = {
        "type": "dict",
        "required_keys": {"due": {"type": "datetime"}},
    }
    cfg: ConfigurationDict = {
        "due": {
            "__datetime.first__": {
                "weekday": "monday",
                "after": "2021-09-10",
                "skip": [datetime.datetime(2021, 9, 13, 12, 0, 0)],
            }
        }
    }
    resolved = resolve(cfg, schema, functions={"datetime": {"first": first}})
    assert resolved == {"due": datetime.datetime(2021, 9, 20)}


def test_first_after_skip_empty_list_is_noop():
    schema: Schema = {
        "type": "dict",
        "required_keys": {"due": {"type": "datetime"}},
    }
    cfg: ConfigurationDict = {
        "due": {
            "__datetime.first__": {
                "weekday": "monday",
                "after": "2021-09-10",
                "skip": [],
            }
        }
    }
    resolved = resolve(cfg, schema, functions={"datetime": {"first": first}})
    assert resolved == {"due": datetime.datetime(2021, 9, 13)}


def test_first_after_skip_preserves_time_from_reference():
    schema: Schema = {
        "type": "dict",
        "required_keys": {"due": {"type": "datetime"}},
    }
    cfg: ConfigurationDict = {
        "due": {
            "__datetime.first__": {
                "weekday": "monday",
                "after": "2021-09-10 14:30:00",
                "skip": ["2021-09-13"],
            }
        }
    }
    resolved = resolve(cfg, schema, functions={"datetime": {"first": first}})
    assert resolved == {"due": datetime.datetime(2021, 9, 20, 14, 30, 0)}


def test_first_after_skip_with_multiple_weekdays():
    """Mon/Fri after Sep 14: first is Fri Sep 17; excluded, so next is Mon Sep 20."""
    schema: Schema = {
        "type": "dict",
        "required_keys": {"due": {"type": "datetime"}},
    }
    cfg: ConfigurationDict = {
        "due": {
            "__datetime.first__": {
                "weekday": "monday, friday",
                "after": "2021-09-14",
                "skip": ["2021-09-17"],
            }
        }
    }
    resolved = resolve(cfg, schema, functions={"datetime": {"first": first}})
    assert resolved == {"due": datetime.datetime(2021, 9, 20)}


# skip error cases ===============================================================


def test_skip_raises_if_not_a_list():
    schema: Schema = {
        "type": "dict",
        "required_keys": {"due": {"type": "datetime"}},
    }
    cfg: ConfigurationDict = {
        "due": {
            "__datetime.first__": {
                "weekday": "monday",
                "after": "2021-09-10",
                "skip": "2021-09-13",
            }
        }
    }
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"datetime": {"first": first}})
    assert "'skip' must be a list" in str(exc.value)


def test_skip_raises_if_date_string_is_invalid():
    schema: Schema = {
        "type": "dict",
        "required_keys": {"due": {"type": "datetime"}},
    }
    cfg: ConfigurationDict = {
        "due": {
            "__datetime.first__": {
                "weekday": "monday",
                "after": "2021-09-10",
                "skip": ["not-a-date"],
            }
        }
    }
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"datetime": {"first": first}})
    assert "Invalid date" in str(exc.value)


def test_skip_raises_if_element_has_invalid_type():
    schema: Schema = {
        "type": "dict",
        "required_keys": {"due": {"type": "datetime"}},
    }
    cfg: ConfigurationDict = {
        "due": {
            "__datetime.first__": {
                "weekday": "monday",
                "after": "2021-09-10",
                "skip": [42],
            }
        }
    }
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, schema, functions={"datetime": {"first": first}})
    assert "Invalid date" in str(exc.value)


# parse ============================================================================

PARSE_SCHEMA: Schema = {
    "type": "dict",
    "required_keys": {
        "result": {"type": "datetime"},
    },
}

PARSE_FUNCTIONS = {"datetime": {"parse": parse}}


def test_parse_iso_date():
    cfg: ConfigurationDict = {"result": {"__datetime.parse__": "2021-10-05"}}
    resolved = resolve(cfg, PARSE_SCHEMA, functions=PARSE_FUNCTIONS)
    assert resolved == {"result": datetime.datetime(2021, 10, 5)}


def test_parse_iso_datetime():
    cfg: ConfigurationDict = {"result": {"__datetime.parse__": "2021-10-05 23:59:10"}}
    resolved = resolve(cfg, PARSE_SCHEMA, functions=PARSE_FUNCTIONS)
    assert resolved == {"result": datetime.datetime(2021, 10, 5, 23, 59, 10)}


def test_parse_offset_days_before():
    cfg: ConfigurationDict = {
        "result": {"__datetime.parse__": "3 days before 2021-10-05"}
    }
    resolved = resolve(cfg, PARSE_SCHEMA, functions=PARSE_FUNCTIONS)
    assert resolved == {"result": datetime.datetime(2021, 10, 2)}


def test_parse_offset_days_after():
    cfg: ConfigurationDict = {
        "result": {"__datetime.parse__": "3 days after 2021-10-05"}
    }
    resolved = resolve(cfg, PARSE_SCHEMA, functions=PARSE_FUNCTIONS)
    assert resolved == {"result": datetime.datetime(2021, 10, 8)}


def test_parse_offset_with_datetime_reference():
    cfg: ConfigurationDict = {
        "result": {"__datetime.parse__": "3 days after 2021-10-05 23:59:15"}
    }
    resolved = resolve(cfg, PARSE_SCHEMA, functions=PARSE_FUNCTIONS)
    assert resolved == {"result": datetime.datetime(2021, 10, 8, 23, 59, 15)}


def test_parse_offset_hours_before():
    cfg: ConfigurationDict = {
        "result": {"__datetime.parse__": "3 hours before 2021-10-05 23:59:15"}
    }
    resolved = resolve(cfg, PARSE_SCHEMA, functions=PARSE_FUNCTIONS)
    assert resolved == {"result": datetime.datetime(2021, 10, 5, 20, 59, 15)}


def test_parse_offset_multi_unit_comma_separated():
    cfg: ConfigurationDict = {
        "result": {"__datetime.parse__": "1 week, 2 days after 2021-10-05 12:00:00"}
    }
    resolved = resolve(cfg, PARSE_SCHEMA, functions=PARSE_FUNCTIONS)
    assert resolved == {"result": datetime.datetime(2021, 10, 14, 12, 0)}


def test_parse_offset_multi_unit_with_sub_day_and_datetime_reference():
    cfg: ConfigurationDict = {
        "result": {
            "__datetime.parse__": "1 week, 2 days, 3 hours after 2021-10-05 12:00:00"
        }
    }
    resolved = resolve(cfg, PARSE_SCHEMA, functions=PARSE_FUNCTIONS)
    assert resolved == {"result": datetime.datetime(2021, 10, 14, 15, 0)}


def test_parse_offset_sub_day_on_date_assumes_midnight():
    cfg: ConfigurationDict = {
        "result": {"__datetime.parse__": "3 hours after 2021-10-05"}
    }
    resolved = resolve(cfg, PARSE_SCHEMA, functions=PARSE_FUNCTIONS)
    assert resolved == {"result": datetime.datetime(2021, 10, 5, 3, 0)}


def test_parse_offset_with_at_time_override():
    cfg: ConfigurationDict = {
        "result": {
            "__datetime.parse__": "3 days before 2021-10-05 23:59:15 at 22:00:00"
        }
    }
    resolved = resolve(cfg, PARSE_SCHEMA, functions=PARSE_FUNCTIONS)
    assert resolved == {"result": datetime.datetime(2021, 10, 2, 22, 0, 0)}


def test_parse_first_weekday_after():
    cfg: ConfigurationDict = {
        "result": {"__datetime.parse__": "first monday after 2021-09-10"}
    }
    resolved = resolve(cfg, PARSE_SCHEMA, functions=PARSE_FUNCTIONS)
    assert resolved == {"result": datetime.datetime(2021, 9, 13)}


def test_parse_first_weekday_before():
    cfg: ConfigurationDict = {
        "result": {"__datetime.parse__": "first monday before 2021-09-17"}
    }
    resolved = resolve(cfg, PARSE_SCHEMA, functions=PARSE_FUNCTIONS)
    assert resolved == {"result": datetime.datetime(2021, 9, 13)}


def test_parse_first_weekday_multiple_comma():
    cfg: ConfigurationDict = {
        "result": {"__datetime.parse__": "first monday, friday after 2021-09-14"}
    }
    resolved = resolve(cfg, PARSE_SCHEMA, functions=PARSE_FUNCTIONS)
    assert resolved == {"result": datetime.datetime(2021, 9, 17)}


def test_parse_first_weekday_with_datetime_reference():
    cfg: ConfigurationDict = {
        "result": {"__datetime.parse__": "first monday after 2021-09-10 12:00:00"}
    }
    resolved = resolve(cfg, PARSE_SCHEMA, functions=PARSE_FUNCTIONS)
    assert resolved == {"result": datetime.datetime(2021, 9, 13, 12, 0, 0)}


def test_parse_first_weekday_multiple_comma_irregular_spacing():
    for weekday_str in [
        "first monday,friday after 2021-09-14",
        "first monday,  friday after 2021-09-14",
        "first monday ,friday after 2021-09-14",
    ]:
        cfg: ConfigurationDict = {"result": {"__datetime.parse__": weekday_str}}
        resolved = resolve(cfg, PARSE_SCHEMA, functions=PARSE_FUNCTIONS)
        assert resolved == {"result": datetime.datetime(2021, 9, 17)}


def test_parse_first_weekday_with_at_time_override():
    cfg: ConfigurationDict = {
        "result": {
            "__datetime.parse__": "first monday after 2021-09-14 23:59:00 at 22:00:00"
        }
    }
    resolved = resolve(cfg, PARSE_SCHEMA, functions=PARSE_FUNCTIONS)
    assert resolved == {"result": datetime.datetime(2021, 9, 20, 22, 0, 0)}


def test_parse_raises_if_input_is_not_a_string():
    cfg: ConfigurationDict = {"result": {"__datetime.parse__": 42}}
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, PARSE_SCHEMA, functions=PARSE_FUNCTIONS)
    assert "must be a string" in str(exc.value)


def test_parse_raises_if_unrecognized_format():
    cfg: ConfigurationDict = {"result": {"__datetime.parse__": "not a date"}}
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, PARSE_SCHEMA, functions=PARSE_FUNCTIONS)
    assert "Cannot parse date" in str(exc.value)


def test_parse_raises_if_invalid_at_time():
    cfg: ConfigurationDict = {
        "result": {"__datetime.parse__": "2021-10-05 at 99:00:00"}
    }
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, PARSE_SCHEMA, functions=PARSE_FUNCTIONS)
    assert "Invalid time" in str(exc.value)


def test_parse_raises_if_invalid_weekday():
    cfg: ConfigurationDict = {
        "result": {"__datetime.parse__": "first notaday after 2021-09-10"}
    }
    with raises(exceptions.ResolutionError) as exc:
        resolve(cfg, PARSE_SCHEMA, functions=PARSE_FUNCTIONS)
    assert "Invalid day of week" in str(exc.value)
