import logging
import typing as t
from unittest.mock import Mock, call, MagicMock

import pytest

from movici_simulation_core.exceptions import SimulationExit
from movici_simulation_core.networking.messages import (
    RegistrationMessage,
    AcknowledgeMessage,
    ResultMessage,
    UpdateMessage,
    NewTimeMessage,
    UpdateSeriesMessage,
    QuitMessage,
    dump_message,
    load_message,
    Message,
)
from movici_simulation_core.networking.stream import Stream, MessageRouterSocketAdapter
from movici_simulation_core.services.orchestrator import Orchestrator
from movici_simulation_core.services.orchestrator.context import (
    ConnectedModel,
    TimelineController,
    ModelCollection,
    MultipleUpdatesAwareQueue,
    Context,
)
from movici_simulation_core.services.orchestrator.fsm import FSM
from movici_simulation_core.services.orchestrator.states import StartInitializingPhase


def get_model(name="dummy", timeline=None, send=None, **kwargs):
    return ConnectedModel(name, timeline, send, **kwargs)


@pytest.fixture
def timeline():
    return TimelineController(0, 10, 0)


class TestContext:
    @pytest.fixture
    def make_context(self):
        def _make(
            models=MagicMock(ModelCollection),
            timeline=Mock(),
            phase_timer=Mock(),
            global_timer=Mock(),
            logger=Mock(),
            **kwargs,
        ):
            return Context(
                models=models,
                timeline=timeline,
                phase_timer=phase_timer,
                global_timer=global_timer,
                logger=logger,
                **kwargs,
            )

        return _make

    @pytest.fixture
    def context(self, make_context):
        return make_context()

    def test_logs_on_global_timer_reset(self, make_context):
        context = make_context(global_timer=None, phase_timer=None)
        context.global_timer.reset()
        assert context.logger.info.call_args == call("Total elapsed time: 0")

    def test_logs_on_phase_timer_reset(self, make_context):
        context = make_context(global_timer=None, phase_timer=None)
        context.phase_timer.reset()
        assert context.logger.info.call_args == call("Previous phase finished in 0 seconds")

    def test_resets_timers_on_finalize(self, context):
        context.finalize()
        assert context.phase_timer.reset.call_count == 1
        assert context.global_timer.reset.call_count == 1
        assert context.models.reset_model_timers.call_count == 1

    @pytest.mark.parametrize(
        "failures,loglevel,msg_endswith",
        [
            ([], "info", "successfully finished"),
            (["one"], "error", "model 'one'"),
            (["one", "two"], "error", "models 'one', 'two'"),
        ],
    )
    def test_logs_finalize_message(self, failures, loglevel, msg_endswith, context):
        context.failed = failures
        context.finalize()

        assert getattr(context.logger, loglevel).call_args[0][0].endswith(msg_endswith)


class TestTimelineController:
    def test_can_set_model_next_time_to_start(self):
        timeline = TimelineController(start=1, end=10)
        model = get_model(timeline=timeline)
        timeline.set_model_to_start(model)
        assert model.next_time == 1

    def test_sets_next_time_for_model(self):
        model = get_model()
        timeline = TimelineController(start=1, end=10)
        timeline.set_next_time(model, 2)
        assert model.next_time == 2

    def test_sets_next_time_for_model_at_end(self):
        model = get_model()
        timeline = TimelineController(start=1, end=10)
        timeline.set_next_time(model, 11)
        assert model.next_time == 10

    def test_prevents_next_time_in_past(self):
        timeline = TimelineController(start=1, end=10, current_time=5)
        assert timeline._get_validated_next_time(3) is None

    def test_clamps_next_time_to_end_time(self):
        timeline = TimelineController(start=1, end=10, current_time=9)
        assert timeline._get_validated_next_time(11) == 10

    def test_can_request_end_time_at_end_time(self):
        timeline = TimelineController(start=1, end=10, current_time=10)
        assert timeline._get_validated_next_time(10) == 10

    def test_prevents_next_time_beyond_end_time_at_end_time(self):
        timeline = TimelineController(start=1, end=10, current_time=10)
        assert timeline._get_validated_next_time(11) is None

    def test_can_register_at_current_time(self):
        timeline = TimelineController(start=1, end=20, current_time=10)
        assert timeline._get_validated_next_time(10) == 10

    @pytest.mark.parametrize(
        "next_a, next_b, exp_a, exp_b",
        [
            (0, 1, [UpdateMessage(0)], []),
            (2, 1, [NewTimeMessage(1)], [NewTimeMessage(1), UpdateMessage(1)]),
            (1, 2, [NewTimeMessage(1), UpdateMessage(1)], [NewTimeMessage(1)]),
            (2, None, [NewTimeMessage(2), UpdateMessage(2)], [NewTimeMessage(2)]),
            (None, 2, [NewTimeMessage(2)], [NewTimeMessage(2), UpdateMessage(2)]),
        ],
    )
    def test_queue_for_next_time(self, next_a, next_b, exp_a, exp_b):
        timeline = TimelineController(start=0, end=20, current_time=0)
        models = ModelCollection(
            a=get_model("a", timeline=timeline),
            b=get_model("b", timeline=timeline),
        )
        models["a"].next_time = next_a
        models["b"].next_time = next_b
        timeline.queue_for_next_time(models)
        assert list(models["a"].message_queue) == exp_a
        assert list(models["b"].message_queue) == exp_b


class TestConnectedModel:
    @pytest.fixture
    def message(self):
        return object()

    @pytest.fixture
    def subscriber(self, timeline):
        return get_model("subscriber", timeline=timeline)

    @pytest.fixture
    def model(self, message, timeline, subscriber):
        model = get_model(
            send=Mock(),
            timeline=timeline,
            subscribers=[subscriber],
        )
        model.queue_message(message)
        assert not model.waiting

        return model

    @pytest.fixture
    def running_model(self, model):
        model.waiting = True
        model.timer.start()
        assert model.timer.running
        assert model.waiting
        return model

    def test_queues_message_at_end_of_queue(self, model):
        msg2 = object()
        model.queue_message(msg2)
        assert len(model.message_queue) == 2
        assert model.message_queue[1] is msg2

    def test_sends_first_message(self, model, message):
        model.send_pending_message()
        assert model.send.call_args == call(message)

    def test_send_message_starts_timer(self, model):
        model.send_pending_message()
        assert model.timer.running

    def test_send_message_marks_model_as_waiting(self, model):
        model.send_pending_message()
        assert model.waiting

    def test_send_message_only_when_not_waiting(self, model, message):
        model.waiting = True
        model.send_pending_message()
        assert model.send.call_count == 0

    def test_can_clear_queue(self, model):
        assert len(model.message_queue) == 1
        model.clear_queue()
        assert len(model.message_queue) == 0

    def test_doesnt_send_on_empty_queue(self, model):
        model.clear_queue()
        model.send_pending_message()
        assert model.send.call_count == 0

    def handle_message_stops_timer_and_waiting(self, running_model):
        running_model.handle_message(AcknowledgeMessage())
        assert not running_model.timer.running
        assert not running_model.waiting

    def test_registration_message_sets_pub_sub(self, running_model):
        message = RegistrationMessage(pub=object(), sub=object())
        running_model.handle_message(message)
        assert running_model.pub == message.pub
        assert running_model.sub == message.sub

    def test_registration_message_sets_next_time_to_start(self, running_model):
        assert running_model.next_time is None
        message = RegistrationMessage(pub=object(), sub=object())
        running_model.handle_message(message)
        assert running_model.next_time == 0

    def test_result_message_sets_next_time(self, running_model):
        message = ResultMessage(next_time=1)
        running_model.handle_message(message)
        assert running_model.next_time == 1

    def test_result_message_queues_subscriber(self, running_model, subscriber, timeline):
        result = ResultMessage(next_time=1, key="bla", address="some_address")
        running_model.handle_message(result)
        assert subscriber.message_queue[0] == UpdateMessage(
            timestamp=timeline.current_time, key=result.key, address=result.address
        )

    def test_result_doesnt_queue_subscriber_on_empty_result(
        self, running_model, subscriber, timeline
    ):
        result = ResultMessage(next_time=1)
        running_model.handle_message(result)
        assert len(subscriber.message_queue) == 0

    def test_accepts_valid_message(self, running_model):
        try:
            running_model.handle_message(AcknowledgeMessage(), valid_events=(AcknowledgeMessage,))
        except SimulationExit:
            pytest.fail("Message not accepted")

    def test_raises_on_invalid_message(self, running_model):
        with pytest.raises(SimulationExit):
            running_model.handle_message(AcknowledgeMessage(), valid_events=())


class TestModelCollection:
    @pytest.fixture
    def models(self, timeline):
        return ModelCollection(
            a=get_model("a", timeline=timeline),
            b=get_model("b", timeline=timeline),
        )

    def test_waiting(self, models):
        assert not models.waiting
        models["a"].waiting = True
        assert models.waiting

    def mock_with_single_object(self, models, attr):
        mock = Mock()
        for model in models.values():
            setattr(model, attr, mock)
        return mock

    @pytest.mark.parametrize(
        "next_a, next_b, expected",
        [
            (None, 1, 1),
            (None, None, None),
            (2, 1, 1),
            (1, None, 1),
        ],
    )
    def test_next_time(self, models, next_a, next_b, expected):
        models["a"].next_time = next_a
        models["b"].next_time = next_b
        assert models.next_time == expected

    def test_queue_all(self, models):
        message = object()
        models.queue_all(message)
        for model in models.values():
            assert model.message_queue[-1] is message, f"failed for model {model.name}"

    @pytest.mark.parametrize(
        "next_a, next_b, exp_a, exp_b",
        [
            (0, 1, [UpdateMessage(0)], []),
            (2, 1, [], [UpdateMessage(1)]),
        ],
    )
    def test_queue_models_for_next_time(self, models, next_a, next_b, exp_a, exp_b):
        models["a"].next_time = next_a
        models["b"].next_time = next_b
        models.queue_models_for_next_time()
        assert list(models["a"].message_queue) == exp_a
        assert list(models["b"].message_queue) == exp_b

    def test_determine_interdependency(self, timeline):
        """
        a publishes to c
        b publishes to a and c
        """
        a = get_model("a", timeline=timeline, pub={"a": None}, sub={"b": None})
        b = get_model("b", timeline=timeline, pub={"b": None}, sub={})
        c = get_model("c", timeline=timeline, pub={"c": None}, sub={"a": None, "b": None})
        models = ModelCollection(a=a, b=b, c=c)
        models.determine_interdependency()
        assert a.subscribers == [c]
        assert b.subscribers == [a, c]

    def test_wait_for_all(self, models):
        assert not models.waiting
        models.wait_for_all()
        assert any(model.waiting for model in models.values())

    def test_send_pending_messages(self, models):
        mock = self.mock_with_single_object(models, "send_pending_message")
        models.send_pending_messages()
        assert mock.call_count == 2

    def test_clear_queue(self, models):
        mock = self.mock_with_single_object(models, "clear_queue")
        models.clear_queue()
        assert mock.call_count == 2

    def test_reset_model_timers(self, models):
        mock = self.mock_with_single_object(models, "timer")
        models.reset_model_timers()
        assert mock.reset.call_count == 2

    def test_messages_pending(self, models):
        assert not models.messages_pending

        models["a"].message_queue.add(UpdateMessage(0))
        assert models.messages_pending


class TestUpdatesAwareQueue:
    @pytest.fixture
    def queue(self):
        return MultipleUpdatesAwareQueue()

    def test_add_and_pop_normal_message(self, queue):
        msg = AcknowledgeMessage()
        queue.add(msg)
        assert queue.pop() is msg
        assert len(queue) == 0

    def test_add_and_pop_update_message(self, queue):
        msg = UpdateMessage(0)
        assert queue.upd_pos is None
        queue.add(msg)
        assert queue.upd_pos == 0
        assert queue.pop() is msg
        assert queue.upd_pos is None

    def test_add_multiple_updates(self, queue):
        msgs = [UpdateMessage(0), UpdateMessage(1)]
        for msg in msgs:
            queue.add(msg)
        assert queue.pop() == UpdateSeriesMessage(msgs)

    def test_complex_add_to_queue_and_pop(self, queue):
        msgs = [
            NewTimeMessage(0),
            UpdateMessage(0),
            NewTimeMessage(1),
            UpdateMessage(1),
            UpdateMessage(2),
            NewTimeMessage(2),
        ]
        for msg in msgs:
            queue.add(msg)
        results = []
        while True:
            try:
                results.append(queue.pop())
            except IndexError:
                break
        assert results == [
            NewTimeMessage(0),
            UpdateSeriesMessage([UpdateMessage(0), UpdateMessage(1), UpdateMessage(2)]),
            NewTimeMessage(1),
            NewTimeMessage(2),
        ]
        assert queue.upd_pos is None


@pytest.fixture
def config():
    return {
        "name": "test_scenario",
        "simulation_info": {
            "mode": "time_oriented",
            "start_time": 0,
            "time_scale": 1,
            "reference_time": 42,
            "duration": 20,
        },
        "models": [
            {
                "type": "type_a",
                "name": "model_a",
            },
            {
                "type": "type_b",
                "name": "model_b",
            },
            {
                "type": "type_c",
                "name": "model_c",
            },
        ],
    }


@pytest.fixture
def socket():
    return MagicMock()


@pytest.fixture
def message_socket(socket):
    return MessageRouterSocketAdapter(socket)


@pytest.fixture
def orchestrator(config, message_socket):
    return _create_orchestrator(config, message_socket)


@pytest.fixture
def setup_orchestrator(message_socket):
    def make_orchestrator(models: t.Sequence[str]):
        config = {
            "name": "test_scenario",
            "simulation_info": {
                "mode": "time_oriented",
                "start_time": 0,
                "time_scale": 1,
                "reference_time": 42,
                "duration": 20,
            },
            "models": [{"name": model, "type": model} for model in models],
        }

        return _create_orchestrator(config, message_socket)

    return make_orchestrator


def _create_orchestrator(config, socket):
    orchestrator = Orchestrator()
    logger = logging.getLogger()
    stream = Stream(socket, logger)
    orchestrator.setup(config=config, logger=logger, stream=stream)
    return orchestrator


@pytest.fixture
def connected_model(orchestrator):
    return next(iter(orchestrator.context.models.values()))


def test_sets_up_logger(orchestrator, connected_model):
    logger = orchestrator.logger
    assert isinstance(logger, logging.Logger)
    assert orchestrator.context.logger is logger
    assert orchestrator.stream.logger is logger
    assert connected_model.logger is logger


def test_sets_up_timeline(orchestrator, connected_model):
    timeline = orchestrator.timeline
    assert timeline == TimelineController(start=0, end=20)
    assert orchestrator.context.timeline is timeline
    assert connected_model.timeline is timeline


def test_sets_up_context(orchestrator):
    context = orchestrator.context
    assert isinstance(context, Context)
    assert context.models.keys() == {"model_a", "model_b", "model_c"}


def test_sets_up_connected_models(connected_model):
    assert isinstance(connected_model, ConnectedModel)
    assert connected_model.name == "model_a"


def test_creates_the_right_send_method(connected_model, socket):
    connected_model.send(AcknowledgeMessage())
    assert socket.send_multipart.call_args == call([b"model_a", b"", b"ACK", b"{}"])


def test_sets_up_fsm(orchestrator):
    assert isinstance(orchestrator.fsm, FSM)
    assert isinstance(orchestrator.fsm.state, StartInitializingPhase)
    assert isinstance(orchestrator.fsm.context, Context)


def test_sets_up_stream(orchestrator):
    assert isinstance(orchestrator.stream, Stream)


@pytest.fixture
def run_orchestrator(setup_orchestrator, socket):
    def message_to_bytes(payload: t.Tuple[str, Message]):
        ident, message = payload
        return [ident.encode(), b"", *dump_message(message)]

    def bytes_to_message(raw_bytes: t.Sequence[bytes]):
        ident, _, *payload = raw_bytes
        msg_type, *content = payload
        return ident.decode(), load_message(msg_type, *content)

    def _run_fsm(models: t.Sequence[str], updates: t.Sequence[t.Tuple[str, Message]]):
        incoming = map(message_to_bytes, updates)
        orchestrator = setup_orchestrator(models)
        socket.recv_multipart.side_effect = incoming
        try:
            orchestrator.run()
        except StopIteration as e:
            raise ValueError("Requires more model responses") from e
        return [bytes_to_message(call[0][0]) for call in socket.send_multipart.call_args_list]

    return _run_fsm


def test_run_simulation(run_orchestrator):
    """Run a simulation with three models:
    model_a publishes at t=0, gets called at t=1 as well but has no data
    model_b subscribes to model_a and publishes to model_c,
    model_c subscribes to model_b
    """
    results = run_orchestrator(
        ["model_a", "model_b", "model_c"],
        [
            ("model_a", RegistrationMessage(pub={"a": None}, sub={})),
            ("model_b", RegistrationMessage(pub={"b": None}, sub={"a": None})),
            ("model_c", RegistrationMessage(pub={"c": None}, sub={"b": None})),
            # 1) orchestrator sends out t=0 new time events. The models respond
            ("model_a", AcknowledgeMessage()),
            ("model_b", AcknowledgeMessage()),
            ("model_c", AcknowledgeMessage()),
            # 2) orchestrator sends out t=0 update calls. The models respond
            ("model_a", ResultMessage(key="a", address="address_a", next_time=1)),
            ("model_b", ResultMessage()),
            ("model_c", ResultMessage()),
            # 3) orchestrator sends update to model_b with info about model_a
            ("model_b", ResultMessage(key="b", address="address_b")),
            # 4) orchestrator sends update to model_c with info about model_b
            ("model_c", ResultMessage(key="c", address="address_c")),
            # no-one is interested in model_c data
            # 5) everyone is done, new time t=1
            ("model_a", AcknowledgeMessage()),
            ("model_b", AcknowledgeMessage()),
            ("model_c", AcknowledgeMessage()),
            # 6) model_a gets updated, no data and no next time
            ("model_a", ResultMessage()),
            # # 7) no-one is queued, ending simulation, send out QuitMessages
            ("model_a", AcknowledgeMessage()),
            ("model_b", AcknowledgeMessage()),
            ("model_c", AcknowledgeMessage()),
        ],
    )
    assert results == [
        # 1) orchestrator sends out t=0 new time events
        ("model_a", NewTimeMessage(0)),
        ("model_b", NewTimeMessage(0)),
        ("model_c", NewTimeMessage(0)),
        # 2) orchestrator sends out t=0 update calls.
        ("model_a", UpdateMessage(0)),
        ("model_b", UpdateMessage(0)),
        ("model_c", UpdateMessage(0)),
        # 3) orchestrator sends update to model_b with info about model_a
        ("model_b", UpdateMessage(0, key="a", address="address_a")),
        # 4) orchestrator sends update to model_c with info about model_b
        ("model_c", UpdateMessage(0, key="b", address="address_b")),
        # 5) everyone is done, new time t=1
        ("model_a", NewTimeMessage(1)),
        ("model_b", NewTimeMessage(1)),
        ("model_c", NewTimeMessage(1)),
        # 6) model_a gets updated
        ("model_a", UpdateMessage(1)),
        # 7) no-one is queued, ending simulation, send out QuitMessages
        ("model_a", QuitMessage()),
        ("model_b", QuitMessage()),
        ("model_c", QuitMessage()),
    ]


def test_series_update(run_orchestrator):
    """model_a1 and _a2 both publish to model_b. These updates are aggregated into an UpdateSeries
    and sent as one to model_b
    """
    results = run_orchestrator(
        ["model_a1", "model_a2", "model_b"],
        [
            ("model_a1", RegistrationMessage(pub={"a": None}, sub={})),
            ("model_a2", RegistrationMessage(pub={"a": None}, sub={})),
            ("model_b", RegistrationMessage(pub={"b": None}, sub={"a": None})),
            ("model_a1", AcknowledgeMessage()),
            ("model_a2", AcknowledgeMessage()),
            ("model_b", AcknowledgeMessage()),
            ("model_a1", ResultMessage(key="a1", address="address_a1")),
            ("model_a2", ResultMessage(key="a2", address="address_a2")),
            ("model_b", ResultMessage()),
            ("model_b", ResultMessage()),
            ("model_a1", AcknowledgeMessage()),
            ("model_a2", AcknowledgeMessage()),
            ("model_b", AcknowledgeMessage()),
        ],
    )

    assert results == [
        ("model_a1", NewTimeMessage(0)),
        ("model_a2", NewTimeMessage(0)),
        ("model_b", NewTimeMessage(0)),
        ("model_a1", UpdateMessage(0)),
        ("model_a2", UpdateMessage(0)),
        ("model_b", UpdateMessage(0)),
        (
            "model_b",
            UpdateSeriesMessage(
                updates=[
                    UpdateMessage(0, key="a1", address="address_a1"),
                    UpdateMessage(0, key="a2", address="address_a2"),
                ]
            ),
        ),
        ("model_a1", QuitMessage()),
        ("model_a2", QuitMessage()),
        ("model_b", QuitMessage()),
    ]


def test_call_at_next_time_equals_current_time(run_orchestrator):
    results = run_orchestrator(
        ["model_a"],
        [
            ("model_a", RegistrationMessage(pub={"a": None}, sub={})),
            ("model_a", AcknowledgeMessage()),
            ("model_a", ResultMessage(next_time=0)),
            ("model_a", ResultMessage(next_time=1)),
            ("model_a", AcknowledgeMessage()),
            ("model_a", ResultMessage()),
            ("model_a", AcknowledgeMessage()),
        ],
    )

    assert results == [
        ("model_a", NewTimeMessage(0)),
        ("model_a", UpdateMessage(0)),
        ("model_a", UpdateMessage(0)),
        ("model_a", NewTimeMessage(1)),
        ("model_a", UpdateMessage(1)),
        ("model_a", QuitMessage()),
    ]


def test_updates_have_preference_over_next_time_at_current_time(run_orchestrator):
    results = run_orchestrator(
        ["model_a", "model_b"],
        [
            ("model_a", RegistrationMessage(pub={"a": None}, sub={"b": None})),
            ("model_b", RegistrationMessage(pub={"b": None}, sub={})),
            ("model_a", AcknowledgeMessage()),
            ("model_b", AcknowledgeMessage()),
            ("model_a", ResultMessage(next_time=0)),
            ("model_b", ResultMessage(key="b", address="address_b")),
            ("model_a", ResultMessage(next_time=0)),
            ("model_a", ResultMessage()),
            ("model_a", AcknowledgeMessage()),
            ("model_b", AcknowledgeMessage()),
        ],
    )

    assert results == [
        ("model_a", NewTimeMessage(0)),
        ("model_b", NewTimeMessage(0)),
        ("model_a", UpdateMessage(0)),
        ("model_b", UpdateMessage(0)),
        ("model_a", UpdateMessage(0, key="b", address="address_b")),
        ("model_a", UpdateMessage(0)),
        ("model_a", QuitMessage()),
        ("model_b", QuitMessage()),
    ]
