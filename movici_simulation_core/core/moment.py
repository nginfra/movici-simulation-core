import dataclasses
import datetime
import functools
import typing as t

from ..utils.time import string_to_datetime


@dataclasses.dataclass(frozen=True)
class TimelineInfo:
    reference: float
    time_scale: float = 1
    start_time: int = 0
    duration: int = 0

    @property
    def end_time(self) -> int:
        return self.start_time + self.duration

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

    def string_to_timestamp(self, dt_string: str, **kwargs):
        return self.datetime_to_timestamp(string_to_datetime(dt_string, **kwargs))

    def is_at_beginning(self, timestamp: int):
        return timestamp == self.start_time


global_timeline_info: t.Optional[TimelineInfo] = None


def get_timeline_info() -> t.Optional[TimelineInfo]:
    return global_timeline_info


def set_timeline_info(
    info_or_reference: t.Union[float, TimelineInfo, None],
    time_scale: t.Optional[float] = None,
    start_time: t.Optional[int] = None,
):

    if isinstance(info_or_reference, TimelineInfo):
        info = info_or_reference
    elif info_or_reference is None:
        info = None
    elif start_time is None or time_scale is None:
        raise ValueError("`start_time` and `time_scale` cannot be None")
    else:
        info = TimelineInfo(
            reference=info_or_reference, time_scale=time_scale, start_time=start_time
        )
    return _TemporaryTimelineInfo(info)


class _TemporaryTimelineInfo:
    def __init__(self, timeline_info: TimelineInfo):
        global global_timeline_info
        self.backup = global_timeline_info
        global_timeline_info = timeline_info
        self.info = timeline_info

    def __enter__(self):
        return self.info

    def __exit__(self, exc_type, exc_val, exc_tb):
        global global_timeline_info
        global_timeline_info = self.backup


@functools.total_ordering
@dataclasses.dataclass
class Moment:
    timestamp: int
    timeline_info: t.Optional[TimelineInfo] = None

    def __post_init__(self):
        self.timestamp = int(self.timestamp)
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
