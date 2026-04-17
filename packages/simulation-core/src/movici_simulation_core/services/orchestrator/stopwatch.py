import time
import typing as t


class Stopwatch:
    def __init__(self, now_func: t.Callable[[], float] = None, ignore_errors=False):
        self.started_at = None
        self._elapsed = 0
        self._total_elapsed = 0
        self.now = now_func or time.monotonic
        self.ignore_errors = ignore_errors

    @property
    def running(self):
        return self.started_at is not None

    @property
    def elapsed(self):
        if not self.running:
            return self._elapsed
        return self.now() - self.started_at

    @property
    def total_elapsed(self):
        if not self.running:
            return self._total_elapsed
        return self.elapsed + self._total_elapsed

    def start(self):
        self.started_at = self.now()

    def stop(self) -> float:
        """returns Stopwatch.elapsed"""
        self._update_elapsed()
        self.started_at = None
        return self.elapsed

    def reset(self) -> float:
        """returns Stopwatch.total_elapsed"""
        if self.running:
            self.stop()
        total_elapsed = self.total_elapsed
        self._elapsed = 0
        self._total_elapsed = 0
        return total_elapsed

    def restart(self) -> float:
        rv = self.reset()
        self.start()
        return rv

    def _update_elapsed(self):
        if not (self.ignore_errors or self.running):
            raise RuntimeError("Stopwatch not started")
        if self.started_at is None:
            return
        self._elapsed = self.now() - self.started_at
        self._total_elapsed += self._elapsed


class ReportingStopwatch(Stopwatch):
    def __init__(
        self,
        on_stop: t.Optional[t.Callable[[float], None]] = None,
        on_reset: t.Optional[t.Callable[[float], None]] = None,
        now_func: t.Callable[[], float] = time.monotonic,
        ignore_errors=False,
    ):
        super().__init__(now_func, ignore_errors)
        self.on_stop = on_stop
        self.on_reset = on_reset

    def stop(self) -> float:
        rv = super().stop()
        if self.on_stop is not None:
            self.on_stop(rv)
        return rv

    def reset(self) -> float:
        rv = super().reset()
        if self.on_reset is not None:
            self.on_reset(rv)
        return rv
