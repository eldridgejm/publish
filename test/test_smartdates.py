import publish
import datetime

from pytest import raises


def test_resolve_smart_dates_on_simple_example():
    # given
    smart_dates = {
        "due": datetime.date(2020, 12, 15),
        "released": "7 days before due",
        "graded": "5 days after due",
    }

    # when
    resolved = publish.resolve_smart_dates(smart_dates, universe={})

    # then
    assert resolved == {
        "due": datetime.date(2020, 12, 15),
        "released": datetime.date(2020, 12, 8),
        "graded": datetime.date(2020, 12, 20),
    }


def test_resolve_smart_dates_on_simple_example_with_time():
    # given
    smart_dates = {
        "due": datetime.date(2020, 12, 15),
        "released": "7 days before due at 13:13:13",
        "graded": "5 days after due",
    }

    # when
    resolved = publish.resolve_smart_dates(smart_dates, universe={})

    # then
    assert resolved == {
        "due": datetime.date(2020, 12, 15),
        "released": datetime.datetime(2020, 12, 8, 13, 13, 13),
        "graded": datetime.date(2020, 12, 20),
    }


def test_resolve_smart_dates_on_short_example_with_time():
    # given
    smart_dates = {
        "released": "due at 13:13:13",
    }
    universe = {
        "due": datetime.date(2020, 12, 15),
    }

    # when
    resolved = publish.resolve_smart_dates(smart_dates, universe=universe)

    # then
    assert resolved == {
        "released": datetime.datetime(2020, 12, 15, 13, 13, 13),
    }


def test_resolve_smart_dates_raises_on_cycle():
    # given
    smart_dates = {
        "due": "1 day before released",
        "released": "7 days before due",
        "graded": "5 days after due",
    }

    # when
    with raises(publish.ValidationError):
        publish.resolve_smart_dates(smart_dates, universe={})


def test_resolve_smart_dates_raises_on_cycle():
    # given
    smart_dates = {
        "due": "1 day before released",
        "released": "7 days before due",
        "graded": "5 days after due",
    }

    # when
    with raises(publish.ValidationError):
        publish.resolve_smart_dates(smart_dates, universe={})


def test_resolve_smart_dates_with_week_reference():
    # given
    smart_dates = {
        "due": "tuesday of week 02",
        "released": "7 days before due",
        "graded": "5 days after due",
    }

    date_context = publish.DateContext(start_date=datetime.date(2021, 1, 15))

    # when
    resolved = publish.resolve_smart_dates(
        smart_dates, universe={}, date_context=date_context
    )

    # then
    assert resolved["due"] == datetime.date(2021, 1, 26)
    assert resolved["released"] == datetime.date(2021, 1, 19)
    assert resolved["graded"] == datetime.date(2021, 1, 31)



def test_resolve_smart_dates_with_week_reference_with_time():
    # given
    smart_dates = {
        "due": "tuesday of week 02 at 11:11:11",
        "released": "7 days before due",
        "graded": "5 days after due",
    }

    date_context = publish.DateContext(start_date=datetime.date(2021, 1, 15))

    # when
    resolved = publish.resolve_smart_dates(
        smart_dates, universe={}, date_context=date_context
    )

    # then
    assert resolved["due"] == datetime.datetime(2021, 1, 26, 11, 11, 11)
    assert resolved["released"] == datetime.datetime(2021, 1, 19, 11, 11, 11)
    assert resolved["graded"] == datetime.datetime(2021, 1, 31, 11, 11, 11)



def test_resolve_smart_dates_with_week_reference_raises_if_start_week_not_set():
    # given
    smart_dates = {
        "due": "tuesday of week 02",
        "released": "7 days before due",
        "graded": "5 days after due",
    }

    # when
    with raises(RuntimeError):
        resolved = publish.resolve_smart_dates(smart_dates, universe={},)



def test_resolve_smart_dates_with_weekday_references_before():
    # given
    smart_dates = {
        "due": "tuesday of week 02",
        "released": "monday before due",  # <----- this is what we're testing
        "graded": "5 days after due",
    }
    date_context = publish.DateContext(start_date=datetime.date(2021, 1, 15))

    # when
    resolved = publish.resolve_smart_dates(
        smart_dates, universe={}, date_context=date_context
    )

    # then
    assert resolved["due"] == datetime.date(2021, 1, 26)
    assert resolved["released"] == datetime.date(2021, 1, 25)
    assert resolved["graded"] == datetime.date(2021, 1, 31)



def test_resolve_smart_dates_with_weekday_references_after():
    # given
    smart_dates = {
        "due": "tuesday of week 02",
        "released": "friday after due",  # <----- this is what we're testing
        "graded": "5 days after due",
    }
    date_context = publish.DateContext(start_date=datetime.date(2021, 1, 15))

    # when
    resolved = publish.resolve_smart_dates(
        smart_dates, universe={}, date_context=date_context
    )

    # then
    assert resolved["due"] == datetime.date(2021, 1, 26)
    assert resolved["released"] == datetime.date(2021, 1, 29)
    assert resolved["graded"] == datetime.date(2021, 1, 31)



def test_resolve_smart_dates_with_weekday_references_with_time():
    # given
    smart_dates = {
        "due": "tuesday of week 02",
        "released": "friday after due at 08:00:00",  # <----- this is what we're testing
        "graded": "5 days after due",
    }
    date_context = publish.DateContext(start_date=datetime.date(2021, 1, 15))

    # when
    resolved = publish.resolve_smart_dates(
        smart_dates, universe={}, date_context=date_context
    )

    # then
    assert resolved["due"] == datetime.date(2021, 1, 26)
    assert resolved["released"] == datetime.datetime(2021, 1, 29, 8, 0, 0)
    assert resolved["graded"] == datetime.date(2021, 1, 31)



def test_resolve_smart_dates_with_weekday_references_before_excludes_current_day():
    # given
    smart_dates = {
        "due": "tuesday of week 02",
        "released": "tuesday before due",  # <----- this is what we're testing
        "graded": "5 days after due",
    }
    date_context = publish.DateContext(start_date=datetime.date(2021, 1, 15))

    # when
    resolved = publish.resolve_smart_dates(
        smart_dates, universe={}, date_context=date_context
    )

    # then
    assert resolved["due"] == datetime.date(2021, 1, 26)
    assert resolved["released"] == datetime.date(2021, 1, 19)
    assert resolved["graded"] == datetime.date(2021, 1, 31)



def test_resolve_smart_dates_with_weekday_references_after_excludes_current_day():
    # given
    smart_dates = {
        "due": "tuesday of week 02",
        "released": "tuesday after due",  # <----- this is what we're testing
        "graded": "5 days after due",
    }
    date_context = publish.DateContext(start_date=datetime.date(2021, 1, 15))

    # when
    resolved = publish.resolve_smart_dates(
        smart_dates, universe={}, date_context=date_context
    )

    # then
    assert resolved["due"] == datetime.date(2021, 1, 26)
    assert resolved["released"] == datetime.date(2021, 2, 2)
    assert resolved["graded"] == datetime.date(2021, 1, 31)
