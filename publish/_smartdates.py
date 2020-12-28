import enum
import typing
import datetime
import re

from .exceptions import ValidationError
from .types import DateContext


class _DaysOfTheWeek(enum.IntEnum):
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


class _RelativeDateRule(typing.NamedTuple):
    delta: datetime.timedelta
    relative_to: str
    time: typing.Optional[datetime.time] = None


class _RelativeDayOfTheWeekRule(typing.NamedTuple):
    relative_to: str
    direction: str
    day_of_the_week: _DaysOfTheWeek
    time: typing.Optional[datetime.time] = None


class _WeekRule(typing.NamedTuple):
    week_number: int
    day_of_the_week: _DaysOfTheWeek
    time: typing.Optional[datetime.time] = None


def _parse_relative_date_rule(s):
    """Reads a relative date rule from natural language.

    This supports several forms, such as:

        - 3 days before other_field
        - 1 day before other_field
        - 5 days after other_field

    Case doesn't matter. 

    Parameters
    ----------
    s : str
        The string to read.

    Raises
    ------
    ValidationError
        If the string cannot be read as a relative date.

    Returns
    -------
    RelativeDateRule
        The rule read from the text.

    """
    time_pattern = r" at (\d{2}):(\d{2}):(\d{2})$"
    match_with_time = re.search(time_pattern, s)
    if match_with_time:
        time_raw = match_with_time.groups()
        time = datetime.time(*[int(x) for x in time_raw])
        s = re.sub(time_pattern, "", s)
    else:
        time = None

    short_match = re.match(r"([\w\.]+)$", s)
    long_match = re.match(r"^(\d+) (hour|day)[s]{0,1} (after|before) ([\w\.]+)$", s)

    if not (short_match or long_match):
        raise ValidationError("Did not match.")

    if short_match:
        variable = short_match.groups()[0]
        return _RelativeDateRule(
            delta=datetime.timedelta(days=0), relative_to=variable, time=time
        )

    if long_match:
        number, hours_or_days, before_or_after, variable = long_match.groups()
        factor = -1 if before_or_after == "before" else 1
    else:
        raise ValidationError(f"Invalid relative date string {s}.")

    if hours_or_days == "hour":
        timedelta_kwargs = {"hours": factor * int(number)}
    else:
        timedelta_kwargs = {"days": factor * int(number)}

    delta = datetime.timedelta(**timedelta_kwargs)
    return _RelativeDateRule(delta=delta, relative_to=variable, time=time)


def _parse_relative_day_of_the_week_rule(s):
    match = re.match(r"^(\w+) (after|before) ([\w\.]+)$", s)
    match_with_time = re.match(
        r"^(\w+) (after|before) ([\w\.]+) at (\d{2}):(\d{2}):(\d{2})$", s
    )

    if not (match or match_with_time):
        raise ValidationError("Does not match.")

    if match:
        day_of_the_week_raw, direction, variable = match.groups()
        time = None
    elif match_with_time:
        day_of_the_week_raw, direction, variable, *time_raw = match_with_time.groups()
        time = datetime.time(*[int(x) for x in time_raw])

    try:
        day_of_the_week = getattr(_DaysOfTheWeek, day_of_the_week_raw.upper())
    except AttributeError:
        raise ValidationError("Invalid day of the week.")

    return _RelativeDayOfTheWeekRule(
        day_of_the_week=day_of_the_week,
        direction=direction,
        relative_to=variable,
        time=time,
    )


def _parse_week_rule(s):
    s = s.lower()
    short_match = re.match(r"([\w]+) of week (\d+)$", s)
    long_match = re.match(r"([\w]+) of week (\d+) at (\d{2}):(\d{2}):(\d{2})$", s)

    if not (short_match or long_match):
        raise ValidationError(f"Invalid week reference: {s}")

    if short_match:
        day_of_the_week_string, week_string = short_match.groups()
        time = None
    if long_match:
        day_of_the_week_string, week_string, h_str, m_str, s_str = long_match.groups()
        time = datetime.time(int(h_str), int(m_str), int(s_str))

    try:
        day_of_the_week = getattr(_DaysOfTheWeek, day_of_the_week_string.upper())
    except AttributeError:
        raise ValidationError(f"Invalid weekday: {day_of_the_week}")

    return _WeekRule(
        day_of_the_week=day_of_the_week, week_number=int(week_string), time=time
    )


def _topologically_sort_date_rules(rules):
    """Topologically sort rules based on their dependencies."""

    start = {}
    finish = {}

    def _dfs(source, clock):
        clock += 1
        start[source] = clock
        if isinstance(
            rules.get(source, None), (_RelativeDateRule, _RelativeDayOfTheWeekRule)
        ):
            child = rules[source].relative_to
            if (child in start) and (child not in finish):
                raise ValidationError("The smart date references are cyclical.")
            _dfs(child, clock)
        clock += 1
        finish[source] = clock
        return clock

    clock = 0
    for rule in rules:
        if rule not in finish:
            clock = _dfs(rule, clock)

    reverse_sorted = sorted(finish.keys(), key=lambda x: finish[x], reverse=True)
    return list(x for x in reverse_sorted if x in rules)


def _recurring_days_of_the_week(weekdays, starting_on):
    """Generator that yields recurring weekdays.

    Parameters
    ----------
    weekdays : Collection[Union[int, _DaysOfTheWeek]]
        A collection of days of the week (or integers, where Monday == 0).
    starting_on : datetime.date
        The starting date.

    Yields
    ------
    datetime.date
        The date of the next weekday in ``weekdays``.

    """
    current_date = starting_on
    while True:
        if current_date.weekday() in weekdays:
            yield current_date
        current_date += datetime.timedelta(days=1)


def _resolve_week_rule(rule, start_date):
    if start_date is None:
        raise RuntimeError("The start date is not set, but a smart date refers to it.")

    # get the start of the week reference by the rule
    week_start_date = start_date + datetime.timedelta(weeks=rule.week_number - 1)

    # get the next rule.day_of_the_week
    date = next(_recurring_days_of_the_week({rule.day_of_the_week}, week_start_date))

    if rule.time is not None:
        return datetime.datetime.combine(date, rule.time)
    else:
        return date


def _resolve_relative_day_of_the_week_rule(rule, universe):
    if rule.direction == "after":
        sign = 1
    else:
        sign = -1

    delta = datetime.timedelta(days=sign)
    current_date = universe[rule.relative_to] + delta
    while True:
        if current_date.weekday() == rule.day_of_the_week:
            break
        current_date += delta

    if rule.time is not None:
        return datetime.datetime.combine(current_date, rule.time)
    else:
        return current_date


def _resolve_relative_date_rule(rule, universe):
    try:
        date = universe[rule.relative_to] + rule.delta
    except KeyError:
        raise ValidationError(f"Relative rule wants unknown field: {rule.relative_to}")

    if rule.time is not None:
        return datetime.datetime.combine(date, rule.time)
    else:
        return date


def resolve_smart_dates(smart_dates, universe, date_context=None):
    """Parses the natural language "smart dates" in a dictionary.

    Parameters
    ----------
    smart_dates : dict
        A dictionary whose values are smart date strings or datetime/date
        objects. The smart dates may depend on one another, or on values in the
        universe.
    universe : dict
        A dictionary whose values are dates that the smart dates may refer to.

    Returns
    -------
    resolved
        A dictionary with the same keys as ``smart_dates``, but where the values are
        datetime or date objects.

    """
    if date_context is None:
        date_context = DateContext()

    universe = universe.copy()
    if date_context.previous is not None:
        for k, v in date_context.previous.metadata.items():
            universe["previous.metadata." + k] = v

    # a helper function to parse a smart string, or maybe a date
    def _parse(s):
        if isinstance(s, (datetime.date, datetime.datetime)):
            return s

        try:
            return _parse_relative_date_rule(s)
        except ValidationError:
            pass

        try:
            return _parse_week_rule(s)
        except ValidationError:
            pass

        try:
            return _parse_relative_day_of_the_week_rule(s)
        except ValidationError:
            pass

        raise ValidationError(f"Cannot parse smart date: {s}")

    rules = {k: _parse(v) for k, v in smart_dates.items()}
    order = _topologically_sort_date_rules(rules)

    # update the universe by resolving the smart dates
    for key in order:
        rule = rules[key]

        if isinstance(rule, _RelativeDateRule):
            universe[key] = _resolve_relative_date_rule(rule, universe)
        elif isinstance(rule, _RelativeDayOfTheWeekRule):
            universe[key] = _resolve_relative_day_of_the_week_rule(rule, universe)
        elif isinstance(rule, _WeekRule):
            universe[key] = _resolve_week_rule(rule, date_context.start_date)
        else:
            # the rule is just a datetime or date object
            universe[key] = rule

    return {k: universe[k] for k in smart_dates}
