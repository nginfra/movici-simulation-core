from unittest.mock import Mock, call

import pytest

from movici_simulation_core.services.orchestrator.stopwatch import Stopwatch, ReportingStopwatch


class Clock:
    def __init__(self, start=0):
        self.now = start

    def step(self):
        self.now += 1

    def __call__(self):
        return self.now


class TestStopwatch:
    @pytest.fixture
    def stopwatch(self):
        return Stopwatch()

    @pytest.fixture
    def sw(self, stopwatch):
        stopwatch.start()
        stopwatch.now.step()
        return stopwatch

    def test_begins_at_0(self, stopwatch):
        assert stopwatch.elapsed == 0

    def test_can_start(self, stopwatch):
        stopwatch.now.step()
        stopwatch.start()
        assert stopwatch.running
        assert stopwatch.started_at == 1

    def test_stopwatch_start_stop(self, sw):
        assert sw.stop() == 1

        sw.start()
        sw.now.step()

        assert sw.stop() == 1
        assert sw.elapsed == 1
        assert sw.total_elapsed == 2

    def test_start_reset(self, sw):
        assert sw.elapsed == 1
        assert sw.total_elapsed == 1
        assert sw.reset() == 1
        assert sw.elapsed == 0
        assert sw.total_elapsed == 0

    def test_start_restart(self, sw):
        sw.restart()
        assert sw.running
        assert sw.elapsed == 0

    def test_elapsed_increases_while_running(self, sw):
        assert sw.elapsed == 1
        sw.now.step()
        assert sw.elapsed == 2

    def test_elapsed_doesnt_increase_while_stopped(self, sw):
        assert sw.elapsed == 1
        assert sw.total_elapsed == 1
        sw.stop()
        sw.now.step()
        assert sw.elapsed == 1
        assert sw.total_elapsed == 1

    def test_elapsed_resets_on_start(self, sw):
        assert sw.elapsed == 1
        assert sw.total_elapsed == 1
        sw.stop()
        sw.start()
        assert sw.elapsed == 0
        assert sw.total_elapsed == 1

    def test_start_stop_reset(self, sw):
        sw.stop()
        sw.start()
        sw.now.step()
        assert sw.stop() == 1
        assert sw.reset() == 2

    def test_raises_when_not_started(self, stopwatch):
        with pytest.raises(RuntimeError):
            stopwatch.stop()

    def test_doesnt_raise_when_ignoring_errors(self):
        stopwatch = Stopwatch(ignore_errors=True)
        try:
            stopwatch.stop()
        except RuntimeError:
            pytest.fail("Didn't ignore error")


class TestReportingStopwatch:
    @pytest.fixture
    def sw(self):
        sw = ReportingStopwatch(on_stop=Mock(), on_reset=Mock(), now_func=Clock())
        sw.start()
        sw.now.step()
        return sw

    def test_on_stop(self, sw):
        sw.stop()
        assert sw.on_stop.call_args == call(1)
        assert sw.on_reset.call_count == 0

    def test_on_reset(self, sw):
        sw.reset()
        assert sw.on_reset.call_args == call(1)
        assert sw.on_stop.call_count == 1
