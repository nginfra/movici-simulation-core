import threading
import time
import typing as t
from concurrent.futures import Future

import pytest

from movici_simulation_core.models.data_collector.concurrent import (
    MultipleException,
    MultipleFutures,
)


@pytest.fixture
def run_in_thread():
    threads = set()

    def _run(fn: callable, *args, **kwargs):
        th = threading.Thread(target=fn, args=args, kwargs=kwargs)
        threads.add(th)
        th.start()

    yield _run
    for th in threads:
        th.join()


class TestMultipleFutures:
    @pytest.fixture
    def mf(self):
        return MultipleFutures()

    @pytest.fixture
    def get_fut(self, mf) -> t.Callable[[], Future]:
        def _get() -> Future:
            fut = Future()
            mf.add(fut)
            return fut

        return _get

    def test_zero_futs(self, mf):
        assert mf.done()
        assert not mf.exception()
        assert mf.wait() is None

    def test_pending_to_done_fut(self, mf, get_fut):
        futs = [get_fut() for _ in range(3)]

        assert not mf.done()
        for fut in futs:
            fut.set_result(None)
        assert mf.done()

    def test_wait_for_fut(self, mf, get_fut, run_in_thread):
        """Here we test whether we can wait for a future that is not done yet at the time."""
        fut = get_fut()

        assert not mf.done()

        def set_done():
            time.sleep(1e-3)
            fut.set_result(None)

        run_in_thread(set_done)
        assert not mf.done()
        assert mf.wait() is None

    def test_exception(self, mf, get_fut):
        e = ValueError()
        fut = get_fut()
        fut.set_exception(e)
        result = mf.exception()
        assert result.exceptions == [e]


def test_multiple_exceptions_message():
    msg1 = "an error occurred"
    msg2 = "another error occurred"
    exc_str = str(MultipleException([ValueError(msg1), TypeError(msg2)]))
    assert "2 errors were raised" in exc_str
    assert msg1 in exc_str
    assert msg2 in exc_str
