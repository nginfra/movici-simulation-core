import typing as t

T = t.TypeVar("T")


class TimeSeries(list, t.List[t.Tuple[int, T]]):
    def __init__(self, iterable: t.Iterable[t.Tuple[int, T]] = ()):
        super().__init__(iterable)
        self.sort()

    def sort(self):
        super().sort(key=lambda i: i[0], reverse=True)

    @property
    def next_time(self):
        return self[-1][0] if self else None

    def pop_until(self, timestamp: int) -> t.Iterable[t.Tuple[int, T]]:
        while (next_time := self.next_time) is not None and next_time <= timestamp:
            yield self.pop()
