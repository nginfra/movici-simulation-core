import dataclasses
import datetime
import functools
import typing as t

import dateutil.parser


@dataclasses.dataclass(frozen=True)
class TimelineInfo:
    reference: float
    time_scale: float
    start_time: int

    def timestamp_to_unix_time(self, timestamp: int) -> float:
        return self.reference + self.timestamp_to_seconds(timestamp)

    def unix_time_to_timestamp(self, unix_time: float) -> int:
        return self.seconds_to_timestamp(unix_time - self.reference)

    def timestamp_to_seconds(self, timestamp: int) -> float:
        return self.time_scale * timestamp

    def seconds_to_timestamp(self, seconds: float) -> int:
        return int(seconds / self.time_scale)

    def datetime_to_timestamp(self, dt: datetime.datetime) -> int:
        return self.unix_time_to_timestamp(dt.timestamp())

    def timestamp_to_datetime(self, timestamp: int):
        return datetime.datetime.fromtimestamp(self.timestamp_to_unix_time(timestamp))

    def is_at_beginning(self, timestamp: int):
        return timestamp == self.start_time


global_timeline_info: t.Optional[TimelineInfo] = None


def set_timeline_info(
    info_or_reference: t.Union[float, TimelineInfo],
    time_scale: t.Optional[float] = None,
    start_time: t.Optional[int] = None,
):
    global global_timeline_info

    if isinstance(info_or_reference, TimelineInfo):
        global_timeline_info = info_or_reference
    elif info_or_reference is None:
        global_timeline_info = None
    elif start_time is None or time_scale is None:
        raise ValueError("`start_time` and `time_scale` cannot be None")
    else:
        global_timeline_info = TimelineInfo(
            reference=info_or_reference, time_scale=time_scale, start_time=start_time
        )


def get_timeline_info() -> t.Optional[TimelineInfo]:
    return global_timeline_info


@functools.total_ordering
@dataclasses.dataclass
class Moment:
    timestamp: int
    timeline_info: t.Optional[TimelineInfo] = None

    def __post_init__(self):
        if self.timeline_info is None:
            self.timeline_info = global_timeline_info

    @property
    def seconds(self):
        timeline_info = self.assert_timeline_info(self.timeline_info)
        return timeline_info.timestamp_to_seconds(self.timestamp)

    @property
    def world_time(self):
        timeline_info = self.assert_timeline_info(self.timeline_info)
        return timeline_info.timestamp_to_unix_time(self.timestamp)

    def is_at_beginning(self):
        timeline_info = self.assert_timeline_info(self.timeline_info)
        return timeline_info.is_at_beginning(self.timestamp)

    def __eq__(self, other):
        if isinstance(other, Moment):
            other = other.seconds
        return other == self.seconds

    def __lt__(self, other):
        if isinstance(other, Moment):
            other = other.seconds
        return self.seconds < other

    @classmethod
    def from_seconds(cls, seconds: float, timeline_info: t.Optional[TimelineInfo] = None):
        timeline_info = cls.assert_timeline_info(timeline_info)
        return cls(timeline_info.seconds_to_timestamp(seconds), timeline_info)

    @classmethod
    def from_string(cls, datetime_str: str, timeline_info: t.Optional[TimelineInfo] = None):
        timeline_info = cls.assert_timeline_info(timeline_info)
        return cls.from_datetime(string_to_datetime(datetime_str, dayfirst=True), timeline_info)

    @classmethod
    def from_datetime(cls, dt: datetime.datetime, timeline_info: t.Optional[TimelineInfo] = None):
        timeline_info = cls.assert_timeline_info(timeline_info)
        return cls(timeline_info.unix_time_to_timestamp(dt.timestamp()), timeline_info)

    @classmethod
    def assert_timeline_info(cls, timeline_info: t.Optional[TimelineInfo] = None):
        timeline_info = timeline_info or global_timeline_info
        if timeline_info is None:
            raise ValueError("global TimelineInfo not set. Invoke `set_timeline_info()` first")
        return timeline_info


def string_to_datetime(datetime_str: str, max_year=5000, **kwargs) -> datetime.datetime:
    """Convert a string into a datetime. `datetime_str` can be one of the following
    - A year (eg. '2025')
    - A unix timestamp (in seconds) (eg. '1626684322')
    - A `dateutil` parsable string

    :param max_year: int. The cutoff for when a `datestime_str` representing a single integer is
        interpreted as a year or as a unix timestamp
    :param kwargs: Additional parameters passed directly into the `dateutil.parser` to customize
    parsing. For example `dayfirst=True`.
    """
    try:
        datetime_as_int = int(datetime_str)
    except ValueError:
        return dateutil.parser.parse(datetime_str, **kwargs)
    else:
        if datetime_as_int < max_year:
            return datetime.datetime(datetime_as_int, month=1, day=1)
        return datetime.datetime.fromtimestamp(datetime_as_int)
