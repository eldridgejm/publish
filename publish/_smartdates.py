"""Functions for converting natural language descriptions of dates to Python objects."""


import enum
import typing
import datetime
import re

from .exceptions import ValidationError
from .types import DateContext


# first, we parse each smart date string into a Node object which represents the
# smart date in Python, but is not yet a datetime object. These nodes may contain
# links to other nodes; a link (a, b) means that b must be resolved before a. We
# topologically sort the nodes to determine resolution order, then we resolve each
# node in turn.


class _MatchError(Exception):
    """Raised if a parse fails because the string does not match."""


class _DaysOfTheWeek(enum.IntEnum):
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


def _parse_and_remove_time(s):
    """Looks for a time at the end of the smart date string.

    A time is of the form " at 23:59:00"

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
        
    """
    time_pattern = r" at (\d{2}):(\d{2}):(\d{2})$"
    match = re.search(time_pattern, s)

    if match:
        time_raw = match.groups()
        time = datetime.time(*[int(x) for x in time_raw])
        s = re.sub(time_pattern, "", s)
    else:
        time = None

    return s, time


def _combine_date_and_time(date, time):
    if time is not None:
        return datetime.datetime.combine(date, time)
    else:
        return date


# node types
# --------------------------------------------------------------------------------------


class _DateNode:
    """A non-reference node representing a date/datetime."""

    def __init(self, date):
        self.date = date

    @classmethod
    def parse(cls, date):
        if not isinstance(date, (datetime.date, datetime.datetime)):
            raise _MatchError("Not a date/datetime.")

        return cls(date)

    def resolve(self, universe, date_context):
        return self.date


class _DirectReferenceNode:
    """A node representing a direct reference.

    Parameters
    ----------
    relative_to : str
        The name of the node that is referred to.
    time : Optional[datetime.time]
        The time. If ``None``, the result will be inferred from referred field
        (if it is a datetime field) or will not have a time component (if the referred
        field is just a date).

    """

    def __init__(self, relative_to, time):
        self.relative_to = relative_to
        self.time = time

    @classmethod
    def parse(cls, s):
        s = s.lower()
        s, time = _parse_and_remove_time(s)

        match = re.match(r"([\w\.]+)$", s)
        if not match:
            raise _MatchError("Not a match.")

        return cls(relative_to=match.groups()[0], time=time)

    def resolve(self, universe, date_context):
        return _combine_date_and_time(universe[self.relative_to], self.time)


class _DeltaReferenceNode:
    """A node representing a delta reference.

    Parameters
    ----------
    delta : datetime.timedelta
        The time delta between this date and the referred date.
    relative_to : str
        The name of the node that is referred to.
    time : Optional[datetime.time]
        The time. If ``None``, the result will be inferred from referred field
        (if it is a datetime field) or will not have a time component (if the referred
        field is just a date).

    """

    def __init__(self, delta, relative_to, time):
        self.delta = delta
        self.relative_to = relative_to
        self.time = time

    @classmethod
    def parse(cls, s):
        s = s.lower()
        s, time = _parse_and_remove_time(s)

        match = re.match(r"^(\d+) (hour|day)[s]{0,1} (after|before) ([\w\.]+)$", s)

        if not match:
            raise _MatchError("Did not match.")

        number, hours_or_days, before_or_after, variable = match.groups()
        factor = -1 if before_or_after == "before" else 1

        if hours_or_days == "hour":
            timedelta_kwargs = {"hours": factor * int(number)}
        else:
            timedelta_kwargs = {"days": factor * int(number)}

        delta = datetime.timedelta(**timedelta_kwargs)
        return cls(delta=delta, relative_to=variable, time=time)

    def resolve(self, universe, date_context):
        date = universe[self.relative_to] + self.delta
        return _combine_date_and_time(date, self.time)


def _parse_day_of_the_week(s):
    return {getattr(_DaysOfTheWeek, x.upper()) for x in s.split()}


class _FirstAvailableNode:
    """A node representing a first available reference.

    Parameters
    ----------
    day_of_the_week : Collection[DaysOfTheWeek]
    relative_to : str
        The name of the node that is referred to.
    time : Optional[datetime.time]
        The time. If ``None``, the result will be inferred from referred field
        (if it is a datetime field) or will not have a time component (if the referred
        field is just a date).

    """

    def __init__(self, day_of_the_week, before_or_after, relative_to, time):
        self.day_of_the_week = day_of_the_week
        self.before_or_after = before_or_after
        self.relative_to = relative_to
        self.time = time

    @classmethod
    def parse(cls, s):
        s = s.lower()
        s, time = _parse_and_remove_time(s)

        s = s.replace(",", " ")
        s = s.replace(" or ", " ")

        match = re.match(r"^first ([\w ]+) (after|before) ([\w\.]+)$", s)

        if not match:
            raise _MatchError("Did not match.")

        day_of_the_week_raw, before_or_after, relative_to = match.groups()
        day_of_the_week = _parse_day_of_the_week(day_of_the_week_raw)

        return cls(day_of_the_week, before_or_after, relative_to, time)

    def resolve(self, universe, date_context):
        sign = 1 if self.before_or_after == "after" else -1
        delta = datetime.timedelta(days=sign)

        cursor_date = universe[self.relative_to] + delta

        while cursor_date.weekday() not in self.day_of_the_week:
            cursor_date += delta

        return _combine_date_and_time(cursor_date, self.time)


class _DayOfGivenWeekNode:
    """A node representing a day in a given week.

    Parameters
    ----------
    day_of_the_week : DaysOfTheWeek
        The day of the week.
    week_number : int
        The week number.
    time : Optional[datetime.time]
        The time. If ``None``, the result will be inferred from referred field
        (if it is a datetime field) or will not have a time component (if the referred
        field is just a date).

    """

    def __init__(self, day_of_the_week, week_number, time):
        self.day_of_the_week = day_of_the_week
        self.week_number = week_number
        self.time = time

    @classmethod
    def parse(cls, s):
        s = s.lower()
        s, time = _parse_and_remove_time(s)

        match = re.match(r"([\w]+) of week (\d+)$", s)

        if not match:
            raise _MatchError(f"Invalid week reference: {s}")

        day_of_the_week_string, week_string = match.groups()
        day_of_the_week = getattr(_DaysOfTheWeek, day_of_the_week_string.upper())

        return cls(
            day_of_the_week=day_of_the_week, week_number=int(week_string), time=time
        )

    def resolve(self, universe, date_context):
        # get the first day of the week referenced by the smart date
        week_start = date_context.start_of_week_one + datetime.timedelta(
            weeks=self.week_number - 1
        )

        cursor_date = week_start
        while cursor_date.weekday() != self.day_of_the_week:
            cursor_date += datetime.timedelta(days=1)

        return _combine_date_and_time(cursor_date, self.time)


def _parse(s):
    """Parse a smart date into a node, inferring the node type by guess and check."""
    node_types = [
        _DateNode,
        _DirectReferenceNode,
        _DeltaReferenceNode,
        _FirstAvailableNode,
        _DayOfGivenWeekNode,
    ]

    for NodeType in node_types:
        try:
            node = NodeType.parse(s)
        except _MatchError:
            pass
        else:
            # we've found the right type of node
            return node
    else:
        # we tried everything and nothing worked
        raise ValidationError(f"The smart date string is invalid: {s}")


def _topological_sort(nodes):
    """Topologically sort nodes based on their dependencies."""

    start = {}
    finish = {}

    def _dfs(source, clock):
        clock += 1
        start[source] = clock

        if source in nodes and hasattr(nodes[source], "relative_to"):
            child = nodes[source].relative_to
            if (child in start) and (child not in finish):
                raise ValidationError("The smart date references are cyclical.")
            _dfs(child, clock)

        clock += 1
        finish[source] = clock
        return clock

    clock = 0
    for key in nodes:
        if key not in finish:
            clock = _dfs(key, clock)

    reverse_sorted = sorted(finish.keys(), key=lambda x: finish[x], reverse=True)
    return list(x for x in reverse_sorted if x in nodes)


def resolve_smart_dates(smart_dates, date_context=None):
    """Converts the natural language "smart dates" to datetime objects.

    Parameters
    ----------
    smart_dates : dict
        A dictionary whose values are smart date strings or datetime/date
        objects. The smart dates may depend on one another, or on values in the
        date context.
    date_context : DateContext
        A context used in the resolution of smart dates. If None, an "empty"
        DateContext is created.

    Returns
    -------
    resolved
        A dictionary with the same keys as ``smart_dates``, but where the values are
        datetime or date objects.

    """
    if date_context is None:
        date_context = DateContext()

    # the universe is the set of all known dates
    universe = {} if date_context.known is None else date_context.known.copy()

    # parse each smart date
    nodes = {k: _parse(v) for k, v in smart_dates.items()}
    order = _topological_sort(nodes)

    # update the universe by resolving the nodes
    for key in order:
        node = nodes[key]
        universe[key] = node.resolve(universe, date_context)

    return {k: universe[k] for k in smart_dates}
