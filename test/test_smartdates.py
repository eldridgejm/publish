"""Tests for resolve_smart_dates."""

import datetime

from pytest import raises

import publish


# there are several types of smart dates:
#
#   - direct reference;
#       "due"
#   - delta reference (before or after), (days or hours);
#       "7 days before due", "7 days after due"
#   - day of given week;
#       "monday of week 2"
#   - first available (before or after);
#       "first monday, wednesday, or friday after previous.release",
#       "first monday, wednesday, or friday before previous.released"
#
# any of these can have a time appended. for example:
#
#   - due at 23:59:00
#   - 7 days before due at 23:59:00
#   - monday of week 02 at 23:59:00
#   - first monday, wednesday, or friday after previous.release at 23:59:00


# direct reference
# --------------------------------------------------------------------------------------


def test_direct_reference():
    # given
    smart_dates = {
        "released": "due",
    }
    date_context = publish.DateContext(known={"due": datetime.date(2020, 12, 15),})

    # when
    resolved = publish.resolve_smart_dates(smart_dates, date_context=date_context)

    # then
    assert resolved == {
        "released": datetime.date(2020, 12, 15),
    }


def test_direct_reference_with_dotted_name():
    # given
    smart_dates = {
        "released": "previous.due",
    }
    date_context = publish.DateContext(
        known={"previous.due": datetime.date(2020, 12, 15),}
    )

    # when
    resolved = publish.resolve_smart_dates(smart_dates, date_context=date_context)

    # then
    assert resolved == {
        "released": datetime.date(2020, 12, 15),
    }


def test_direct_reference_with_time():
    # given
    smart_dates = {
        "released": "due at 13:13:13",
    }
    date_context = publish.DateContext(known={"due": datetime.date(2020, 12, 15),})

    # when
    resolved = publish.resolve_smart_dates(smart_dates, date_context=date_context)

    # then
    assert resolved == {
        "released": datetime.datetime(2020, 12, 15, 13, 13, 13),
    }


# case sensitivity / insensitivity


def test_direct_reference_variable_case_sensitive():
    # given
    smart_dates = {
        "released": "Due",
    }
    date_context = publish.DateContext(known={"due": datetime.date(2020, 12, 15),})

    with raises(publish.ValidationError):
        publish.resolve_smart_dates(smart_dates, date_context=date_context)


def test_direct_reference_with_time_case_insensitive_except_for_variable_names():
    # case insensitive, EXCEPT for the variable names
    # given
    smart_dates = {
        "released": "due AT 13:13:13",
    }
    date_context = publish.DateContext(known={"due": datetime.date(2020, 12, 15),})

    # when
    resolved = publish.resolve_smart_dates(smart_dates, date_context=date_context)

    # then
    assert resolved == {
        "released": datetime.datetime(2020, 12, 15, 13, 13, 13),
    }


# error handling


def test_direct_reference_raises_if_field_is_unknown():
    # given
    smart_dates = {
        "released": "badfield",
    }
    date_context = publish.DateContext(known={"due": datetime.date(2020, 12, 15),})

    # when
    with raises(publish.ValidationError):
        publish.resolve_smart_dates(smart_dates, date_context=date_context)


def test_direct_reference_raises_if_time_is_bad():
    # given
    smart_dates = {
        "released": "badfield at 55:00:00",
    }
    date_context = publish.DateContext(known={"due": datetime.date(2020, 12, 15),})

    # when
    with raises(publish.ValidationError):
        publish.resolve_smart_dates(smart_dates, date_context=date_context)


def test_direct_reference_raises_if_circular_reference():
    # given
    smart_dates = {
        "foo": "bar",
        "bar": "foo",
    }
    date_context = publish.DateContext(known={"due": datetime.date(2020, 12, 15),})

    # when
    with raises(publish.ValidationError):
        publish.resolve_smart_dates(smart_dates, date_context=date_context)


def test_direct_reference_raises_if_self_reference():
    # given
    smart_dates = {
        "foo": "foo",
    }
    date_context = publish.DateContext(known={"due": datetime.date(2020, 12, 15),})

    # when
    with raises(publish.ValidationError):
        publish.resolve_smart_dates(smart_dates, date_context=date_context)


# delta reference
# --------------------------------------------------------------------------------------
#  e.g., "7 days before due", "7 days after due", "7 hours after due"


def test_delta_reference_before_days():
    # given
    smart_dates = {
        "released": "7 days before due",
    }

    date_context = publish.DateContext(known={"due": datetime.date(2020, 12, 15)})

    # when
    resolved = publish.resolve_smart_dates(smart_dates, date_context=date_context)

    # then
    assert resolved == {
        "released": datetime.date(2020, 12, 8),
    }


def test_delta_reference_after_days():
    # given
    smart_dates = {
        "released": "7 days after due",
    }

    date_context = publish.DateContext(known={"due": datetime.date(2020, 12, 15)})

    # when
    resolved = publish.resolve_smart_dates(smart_dates, date_context=date_context)

    # then
    assert resolved == {
        "released": datetime.date(2020, 12, 22),
    }


def test_delta_reference_before_hours():
    # given
    smart_dates = {
        "released": "7 hours before due",
    }

    date_context = publish.DateContext(
        known={"due": datetime.datetime(2020, 12, 15, 23, 59, 0)}
    )

    # when
    resolved = publish.resolve_smart_dates(smart_dates, date_context=date_context)

    # then
    assert resolved == {
        "released": datetime.datetime(2020, 12, 15, 16, 59, 0),
    }


def test_delta_reference_after_hours():
    # given
    smart_dates = {
        "released": "7 hours after due",
    }

    date_context = publish.DateContext(
        known={"due": datetime.datetime(2020, 12, 15, 0, 59, 0)}
    )

    # when
    resolved = publish.resolve_smart_dates(smart_dates, date_context=date_context)

    # then
    assert resolved == {
        "released": datetime.datetime(2020, 12, 15, 7, 59, 0),
    }


def test_delta_reference_with_dotted_name():
    # given
    smart_dates = {
        "released": "7 days before previous.due",
    }

    date_context = publish.DateContext(
        known={"previous.due": datetime.date(2020, 12, 15)}
    )

    # when
    resolved = publish.resolve_smart_dates(smart_dates, date_context=date_context)

    # then
    assert resolved == {
        "released": datetime.date(2020, 12, 8),
    }


def test_delta_reference_with_time():
    # given
    smart_dates = {
        "released": "7 days before due at 13:13:13",
    }

    date_context = publish.DateContext(known={"due": datetime.date(2020, 12, 15)})

    # when
    resolved = publish.resolve_smart_dates(smart_dates, date_context=date_context)

    # then
    assert resolved == {
        "released": datetime.datetime(2020, 12, 8, 13, 13, 13),
    }


def test_delta_reference_dependency_chain_is_resolved():
    # given
    smart_dates = {
        "c": "1 hour after due",
        "bar": "1 hour after foo",
        "a": "1 hour after baz",
        "baz": "1 hour after foo",
        "foo": "1 hour after due",
        "b": "1 hour after a",
    }

    date_context = publish.DateContext(
        known={"due": datetime.datetime(2020, 12, 15, 0, 0, 0)}
    )

    # when
    resolved = publish.resolve_smart_dates(smart_dates, date_context=date_context)

    # then
    assert resolved == {
        "foo": datetime.datetime(2020, 12, 15, 1, 0, 0),
        "bar": datetime.datetime(2020, 12, 15, 2, 0, 0),
        "baz": datetime.datetime(2020, 12, 15, 2, 0, 0),
        "a": datetime.datetime(2020, 12, 15, 3, 0, 0),
        "b": datetime.datetime(2020, 12, 15, 4, 0, 0),
        "c": datetime.datetime(2020, 12, 15, 1, 0, 0),
    }


# case sensitivity / insensitivity


def test_delta_reference_variables_case_sensitive():
    # given
    smart_dates = {
        "released": "7 days before Due",
    }

    date_context = publish.DateContext(known={"due": datetime.date(2020, 12, 15)})

    # when
    with raises(publish.ValidationError):
        publish.resolve_smart_dates(smart_dates, date_context=date_context)


def test_delta_reference_case_insensitive_apart_from_variables():
    # given
    smart_dates = {
        "released": "7 DAYS BeFoRe due",
    }

    date_context = publish.DateContext(known={"due": datetime.date(2020, 12, 15)})

    # when
    resolved = publish.resolve_smart_dates(smart_dates, date_context=date_context)

    # then
    assert resolved == {
        "released": datetime.date(2020, 12, 8),
    }


# error handling


def test_delta_reference_with_cycle_raises():
    # given
    smart_dates = {
        "due": "1 day before released",
        "released": "7 days before due",
        "graded": "5 days after due",
    }

    # when
    with raises(publish.ValidationError):
        publish.resolve_smart_dates(smart_dates)


def test_delta_reference_missing_reference_raises():
    # given
    smart_dates = {
        "released": "7 days before badfield",
    }

    date_context = publish.DateContext(known={"due": datetime.date(2020, 12, 15)})

    # when
    with raises(publish.ValidationError):
        publish.resolve_smart_dates(smart_dates, date_context=date_context)


def test_delta_reference_raises_if_hour_reference_used_with_date_and_not_datetime():
    # given
    smart_dates = {
        "released": "3 hours before due",
    }

    date_context = publish.DateContext(known={"due": datetime.date(2020, 12, 15)})

    # when
    with raises(publish.ValidationError):
        publish.resolve_smart_dates(smart_dates, date_context=date_context)


def test_delta_reference_raises_if_time_used_with_hour_delta():
    # given
    smart_dates = {
        "released": "3 hours before due at 23:00:00",
    }

    date_context = publish.DateContext(
        known={"due": datetime.datetime(2020, 12, 15, 0, 0, 0)}
    )

    # when
    with raises(publish.ValidationError):
        publish.resolve_smart_dates(smart_dates, date_context=date_context)


# first available reference
# --------------------------------------------------------------------------------------
# e.g., "first monday, wednesday, or friday after previous.release",
# e.g., "first monday, wednesday, or friday before previous.released"


def test_first_available_after_single_day():
    # given
    smart_dates = {
        "released": "first monday after previous.released",
    }

    date_context = publish.DateContext(
        known={"previous.released": datetime.date(2020, 12, 15)}
    )

    # when
    resolved = publish.resolve_smart_dates(smart_dates, date_context=date_context)

    # then
    assert resolved == {
        "released": datetime.date(2020, 12, 21),
    }


def test_first_available_before_single_day():
    # given
    smart_dates = {
        "released": "first monday before previous.released",
    }

    date_context = publish.DateContext(
        known={"previous.released": datetime.date(2020, 12, 15)}
    )

    # when
    resolved = publish.resolve_smart_dates(smart_dates, date_context=date_context)

    # then
    assert resolved == {
        "released": datetime.date(2020, 12, 14),
    }


def test_first_available_after_single_day_excludes_current_day():
    # given
    smart_dates = {
        "released": "first tuesday after previous.released",
    }

    date_context = publish.DateContext(
        known={"previous.released": datetime.date(2020, 12, 15)}  # this is a tuesday
    )

    # when
    resolved = publish.resolve_smart_dates(smart_dates, date_context=date_context)

    # then
    assert resolved == {
        "released": datetime.date(2020, 12, 22),
    }


def test_first_available_before_single_day_excludes_current_day():
    # given
    smart_dates = {
        "released": "first tuesday before previous.released",
    }

    date_context = publish.DateContext(
        known={"previous.released": datetime.date(2020, 12, 15)}  # this is a tuesday
    )

    # when
    resolved = publish.resolve_smart_dates(smart_dates, date_context=date_context)

    # then
    assert resolved == {
        "released": datetime.date(2020, 12, 8),
    }


def test_first_available_after_multiple_days():
    # given
    smart_dates = {
        "released": "first monday or wednesday after previous.released",
    }

    date_context = publish.DateContext(
        known={"previous.released": datetime.date(2020, 12, 16)}
    )

    # when
    resolved = publish.resolve_smart_dates(smart_dates, date_context=date_context)

    # then
    assert resolved == {
        "released": datetime.date(2020, 12, 21),
    }


def test_first_available_before_multiple_days():
    # given
    smart_dates = {
        "released": "first monday or wednesday before previous.released",
    }

    date_context = publish.DateContext(
        known={"previous.released": datetime.date(2020, 12, 16)}
    )

    # when
    resolved = publish.resolve_smart_dates(smart_dates, date_context=date_context)

    # then
    assert resolved == {
        "released": datetime.date(2020, 12, 14),
    }


def test_first_available_before_multiple_days_with_commas():
    # given
    smart_dates = {
        "released": "first monday, wednesday, or friday before previous.released",
    }

    date_context = publish.DateContext(
        known={"previous.released": datetime.date(2020, 12, 16)}
    )

    # when
    resolved = publish.resolve_smart_dates(smart_dates, date_context=date_context)

    # then
    assert resolved == {
        "released": datetime.date(2020, 12, 14),
    }


# case sensitivity / insensitivity


def test_first_available_variables_case_sensitive():
    # given
    smart_dates = {
        "released": "first monday, wednesday, or friday before Previous.Released",
    }

    date_context = publish.DateContext(
        known={"previous.released": datetime.date(2020, 12, 16)}
    )

    # when
    with raises(publish.ValidationError):
        publish.resolve_smart_dates(smart_dates, date_context=date_context)


def test_first_available_case_insensitive_apart_from_variables():
    # given
    smart_dates = {
        "released": "first Monday, Wednesday, or Friday BEFORE previous.released",
    }

    date_context = publish.DateContext(
        known={"previous.released": datetime.date(2020, 12, 16)}
    )

    # when
    resolved = publish.resolve_smart_dates(smart_dates, date_context=date_context)

    # then
    assert resolved == {
        "released": datetime.date(2020, 12, 14),
    }


# error handling


def test_first_available_raises_if_unknown_reference():
    # given
    smart_dates = {
        "released": "first monday, wednesday, or friday before badfield",
    }

    date_context = publish.DateContext(
        known={"previous.released": datetime.date(2020, 12, 16)}
    )

    # when
    with raises(publish.ValidationError):
        publish.resolve_smart_dates(smart_dates, date_context=date_context)


def test_first_available_raises_if_unknown_day_of_week():
    # given
    smart_dates = {
        "released": "first monday, wednesday, or ferday before previous.released",
    }

    date_context = publish.DateContext(
        known={"previous.released": datetime.date(2020, 12, 16)}
    )

    # when
    with raises(publish.ValidationError):
        publish.resolve_smart_dates(smart_dates, date_context=date_context)


# day of given week
# --------------------------------------------------------------------------------------
# e.g., "monday of week 02"


def test_day_of_given_week():
    # given
    smart_dates = {
        "released": "tuesday of week 02",
    }

    date_context = publish.DateContext(start_of_week_one=datetime.date(2020, 12, 10))

    # when
    resolved = publish.resolve_smart_dates(smart_dates, date_context=date_context)

    # then
    assert resolved == {
        "released": datetime.date(2020, 12, 22),
    }


def test_day_of_given_week_works_without_zero_padding():
    # given
    smart_dates = {
        "released": "tuesday of week 2",
    }

    date_context = publish.DateContext(start_of_week_one=datetime.date(2020, 12, 10))

    # when
    resolved = publish.resolve_smart_dates(smart_dates, date_context=date_context)

    # then
    assert resolved == {
        "released": datetime.date(2020, 12, 22),
    }


def test_day_of_given_week_with_time():
    # given
    smart_dates = {
        "released": "tuesday of week 02 at 23:00:00",
    }

    date_context = publish.DateContext(start_of_week_one=datetime.date(2020, 12, 10))

    # when
    resolved = publish.resolve_smart_dates(smart_dates, date_context=date_context)

    # then
    assert resolved == {
        "released": datetime.datetime(2020, 12, 22, 23, 0, 0),
    }


# case sensitivity / insensitivity


def test_day_of_given_week_case_insensitive():
    # given
    smart_dates = {
        "released": "TueSday oF Week 2 AT 23:00:00",
    }

    date_context = publish.DateContext(start_of_week_one=datetime.date(2020, 12, 10))

    # when
    resolved = publish.resolve_smart_dates(smart_dates, date_context=date_context)

    # then
    assert resolved == {
        "released": datetime.datetime(2020, 12, 22, 23, 0, 0),
    }


# error handling


def test_day_of_given_week_case_raises_if_start_is_not_provided():
    # given
    smart_dates = {"released": "tersday of week 02"}

    date_context = publish.DateContext()

    # when
    with raises(publish.ValidationError):
        publish.resolve_smart_dates(smart_dates, date_context=date_context)


def test_day_of_given_week_case_raises_if_invalid_day_of_week():
    # given
    smart_dates = {"released": "tersday of week 02"}

    date_context = publish.DateContext(start_of_week_one=datetime.date(2020, 12, 10))

    # when
    with raises(publish.ValidationError):
        publish.resolve_smart_dates(smart_dates, date_context=date_context)


def test_day_of_given_week_case_raises_if_multiple_days_given():
    # given
    smart_dates = {"released": "tuesday or thursday of week 02"}

    date_context = publish.DateContext(start_of_week_one=datetime.date(2020, 12, 10))

    # when
    with raises(publish.ValidationError):
        publish.resolve_smart_dates(smart_dates, date_context=date_context)
