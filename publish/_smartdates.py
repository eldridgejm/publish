"""Functions for converting natural language descriptions of dates to Python objects.

Smart dates can be of the following forms:

    - direct references
        e.g., "due"
    - delta references
        e.g., "7 days before due", "3 hours before due", "1 day before due at 23:00:00"
    - first available references
        e.g., "first monday before due", "first tuesday or thursday after due"
    - day of given week
        e.g., "monday of week 02"

"""

import enum
import typing
import datetime
import re

from .exceptions import ValidationError
from .types import DateContext


"""
implementation details
----------------------

The important object of this module is a Node. A Node is a class that encapsulates
the important information for each smart date type and includes methods for parsing
this information from a string and for resolving the smart date into a date/datetime
object. Nodes are defined for each of the smart date types described above.

"""


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


# helper functions
# --------------------------------------------------------------------------------------


def _parse(s):
    """Parse a smart date string into a Node, inferring node type by guess and check.

    Parameters
    ----------
    s : str
        The smart date string

    Returns
    -------
    Node
        A node object.

    Raises
    ------
    ValidationError
        If the smart date string didn't parse as any node type.


    """
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

    Raises
    ------
    ValidationError
        If there is a time string, but it's an invalid time (like 55:00:00).
        
    """
    time_pattern = r" at (\d{2}):(\d{2}):(\d{2})$"
    match = re.search(time_pattern, s, flags=re.IGNORECASE)

    if match:
        time_raw = match.groups()
        try:
            time = datetime.time(*[int(x) for x in time_raw])
        except ValueError:
            raise ValidationError(f"Invalid time: {time_raw}.")
        s = re.sub(time_pattern, "", s, flags=re.IGNORECASE)
    else:
        time = None

    return s, time


def _combine_date_and_time(date, time):
    """Convenience function for turning a date and time into a datetime.

    Parameters
    ----------
    date : Union[date, datetime]
        The date part.
    time : Union[time]
        The time part. Can possibly be None, in which case the input date is returned.

    Returns
    -------
    Union[datetime, date]
        If a time is provided, the result is a datetime using the date from the
        ``date`` argument and the time from ``time``. If ``date`` is a
        datetime, the time is overwritten.  If ``time`` is ``None``, the
        ``date`` argument is returned.


    """
    if time is not None:
        return datetime.datetime.combine(date, time)
    else:
        return date


def _parse_day_of_the_week(s):
    """Turn a day of the week string, like "Monday", and turn it into a _DaysOfTheWeek.

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
        raise ValidationError(f"Invalid day of week: {s}")


def _topological_sort(nodes):
    """Topologically sort nodes based on their dependencies.

    This uses the ``relative_to`` attribute of a node to determine which of the
    other nodes it depends on.

    Parameters
    ----------
    nodes : Mapping[str, Node]
        A mapping of node field names to Node objects.

    Returns
    -------
    List[str]
        A list of the node field names in topologically-sorted order.

    """

    start = {}
    finish = {}

    # we must reverse the "relative_to" direction for the toposort.
    children = {k: [] for k in nodes}
    for key, node in nodes.items():
        if hasattr(node, "relative_to") and node.relative_to in nodes:
            children[node.relative_to].append(key)

    def _dfs(source, clock):
        clock += 1
        start[source] = clock

        for child in children[source]:
            if child in start and child not in finish:
                raise ValidationError("Cycle detected in smart date references.")
            if child not in start:
                clock = _dfs(child, clock)

        clock += 1
        finish[source] = clock
        return clock

    clock = 0
    for key in nodes:
        if key not in finish:
            clock = _dfs(key, clock)

    reverse_sorted = sorted(finish.keys(), key=lambda x: finish[x], reverse=True)
    order = list(x for x in reverse_sorted if x in nodes)
    return order


# node types
# --------------------------------------------------------------------------------------


class _DateNode:
    """A non-reference node representing a date/datetime."""

    def __init__(self, date):
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
        s, time = _parse_and_remove_time(s)

        match = re.match(r"([\w\.]+)$", s)
        if not match:
            raise _MatchError("Not a match.")

        return cls(relative_to=match.groups()[0], time=time)

    def resolve(self, universe, date_context):
        try:
            referred_value = universe[self.relative_to]
        except KeyError:
            raise ValidationError(f"Reference of an unknown field: {self.relative_to}")

        return _combine_date_and_time(referred_value, self.time)


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
    is_hours_delta : bool
        True iff the delta is in hours.

    """

    def __init__(self, delta, relative_to, time, is_hours_delta):
        self.delta = delta
        self.relative_to = relative_to
        self.time = time
        self.is_hours_delta = is_hours_delta

    @classmethod
    def parse(cls, s):
        s, time = _parse_and_remove_time(s)

        match = re.match(
            r"^(\d+) (hour|day)[s]{0,1} (after|before) ([\w\.]+)$",
            s,
            flags=re.IGNORECASE,
        )

        if not match:
            raise _MatchError("Did not match.")

        number, hours_or_days, before_or_after, variable = match.groups()
        factor = -1 if before_or_after.lower() == "before" else 1

        if hours_or_days.lower() == "hour":
            timedelta_kwargs = {"hours": factor * int(number)}
            is_hours_delta = True
        else:
            timedelta_kwargs = {"days": factor * int(number)}
            is_hours_delta = False

        delta = datetime.timedelta(**timedelta_kwargs)
        return cls(
            delta=delta, relative_to=variable, time=time, is_hours_delta=is_hours_delta
        )

    def resolve(self, universe, date_context):
        try:
            date = universe[self.relative_to] + self.delta
        except KeyError:
            raise ValidationError(f"Reference of an unknown field: {self.relative_to}")

        # we shouldn't allow hour deltas with date objects, because the hours are lost
        # we don't use isinstance below because datetime is a subclass of date
        if type(date) is datetime.date and self.is_hours_delta:
            msg = "Cannot use hours delta in reference to a date (must be a datetime)."
            raise ValidationError(msg)

        # we also shouldn't allow times to be provided when using an hour delta
        # e.g.: 3 hours before then at 23:00:00
        if self.time is not None and self.is_hours_delta:
            msg = "Cannot use hours delta and specify an exact time."
            raise ValidationError(msg)

        return _combine_date_and_time(date, self.time)


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
        s, time = _parse_and_remove_time(s)

        s = s.replace(",", " ")
        s = s.replace(" or ", " ")

        match = re.match(
            r"^first ([\w ]+) (after|before) ([\w\.]+)$", s, flags=re.IGNORECASE
        )

        if not match:
            raise _MatchError("Did not match.")

        day_of_the_week_raw, before_or_after, relative_to = match.groups()
        day_of_the_week = {
            _parse_day_of_the_week(x) for x in day_of_the_week_raw.split()
        }

        return cls(day_of_the_week, before_or_after, relative_to, time)

    def resolve(self, universe, date_context):
        sign = 1 if self.before_or_after.lower() == "after" else -1
        delta = datetime.timedelta(days=sign)

        try:
            cursor_date = universe[self.relative_to] + delta
        except KeyError:
            raise ValidationError(f"Reference of an unknown field: {self.relative_to}")

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
        day_of_the_week = _parse_day_of_the_week(day_of_the_week_string)

        return cls(
            day_of_the_week=day_of_the_week, week_number=int(week_string), time=time
        )

    def resolve(self, universe, date_context):
        if date_context.start_of_week_one is None:
            raise ValidationError("Start date of week one was not provided.")

        # get the first day of the week referenced by the smart date
        week_start = date_context.start_of_week_one + datetime.timedelta(
            weeks=self.week_number - 1
        )

        cursor_date = week_start
        while cursor_date.weekday() != self.day_of_the_week:
            cursor_date += datetime.timedelta(days=1)

        return _combine_date_and_time(cursor_date, self.time)


# resolve_smart_dates
# --------------------------------------------------------------------------------------


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
        DateContext is created. See :type:`date_context`.

    Returns
    -------
    resolved
        A dictionary with the same keys as ``smart_dates``, but where the values are
        datetime or date objects.

    Raises
    ------
    ValidationError
        If smart dates could not be resolved due to a problem with their definition.

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
