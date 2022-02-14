import itertools
import traceback
import typing as t
from concurrent import futures
from threading import Lock, Semaphore


class MultipleFutures:
    """Keep track of multiple `concurrent.Futures`"""

    def __init__(self, iterable: t.Iterable[futures.Future] = ()):
        self.futs = set()
        self._lock = Lock()
        self._exceptions = []
        if iterable:
            for it in iterable:
                self.add(it)

    def add(self, fut: futures.Future):
        self.futs.add(fut)
        fut.add_done_callback(self._callback)

    def _callback(self, fut: futures.Future):
        with self._lock:
            self.futs.remove(fut)
            if exc := fut.exception():
                self._exceptions.append(exc)

    def done(self):
        return not self.futs

    def exception(self):
        if self._exceptions:
            return MultipleException(self._exceptions)

    def wait(self):
        futures.wait(self.futs)


class LimitedThreadPoolExecutor(futures.ThreadPoolExecutor):
    """Similar to ThreadPoolExecutor, but blocks on submit when all workers are busy"""

    def __init__(self, max_workers=None, thread_name_prefix="", initializer=None, initargs=()):
        super().__init__(max_workers, thread_name_prefix, initializer, initargs)
        self._lock = Semaphore(self._max_workers)

    def submit(self, function, *args, **kwargs):
        """"""
        self._lock.acquire()
        fut = super().submit(function, *args, **kwargs)
        fut.add_done_callback(lambda f: self._lock.release())
        return fut


class MultipleException(Exception):
    def __init__(self, exceptions: t.Sequence[Exception]):
        self.exceptions = exceptions

    def __str__(self):
        return "".join(
            (
                f"{len(self.exceptions)} errors were raised:\n",
                *itertools.chain.from_iterable(self.format_exception(e) for e in self.exceptions),
            )
        )

    @staticmethod
    def format_exception(e: Exception):
        return traceback.format_exception(None, e, e.__traceback__)
