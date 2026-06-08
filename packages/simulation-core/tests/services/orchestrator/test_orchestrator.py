import logging
import typing as t
from unittest.mock import MagicMock, Mock, call

import pytest

from movici_simulation_core.messages import (
    AcknowledgeMessage,
    ErrorMessage,
    Message,
    NewTimeMessage,
    QuitMessage,
    RegistrationMessage,
    ResultMessage,
    UpdateMessage,
    UpdateSeriesMessage,
    dump_message,
    load_message,
)
from movici_simulation_core.networking.stream import MessageRouterSocket, Stream
from movici_simulation_core.services.orchestrator import Orchestrator
from movici_simulation_core.services.orchestrator.context import (
    ConnectedModel,
    Context,
    ModelCollection,
    TimelineController,
)
from movici_simulation_core.services.orchestrator.fsm import FSM, Always, FSMConfig
from movici_simulation_core.services.orchestrator.states import (
    AllModelsReady,
    EndFinalizingPhase,
    Failed,
    FinalizingWaitForModels,
    OrchestratorState,
    StartFinalizingPhase,
    StartInitializingPhase,
)
from movici_simulation_core.settings import Settings


@pytest.fixture
def timeline():
    return TimelineController(0, 10, 0)


def get_model(name="dummy", timeline=None, send=None, **kwargs):
    send = send or Mock()
    model = ConnectedModel(name, timeline, send, **kwargs)
    model.recv_event = Mock()
    return model


class TestModelCollection:
    @pytest.fixture
    def models(self, timeline):
        return ModelCollection(
            a=get_model(timeline=timeline),
            b=get_model(timeline=timeline),
        )

    @pytest.mark.parametrize("model_busy", [True, False])
    def test_waiting(self, models, model_busy):
        models["b"].busy = False
        models["a"].busy = model_busy
        assert models.busy == model_busy

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

    def test_determine_interdependency_publishes_to(self, timeline):
        """
        a publishes to c
        b publishes to a and c
        """
        a = get_model("a", timeline=timeline, pub={"a": None}, sub={"b": None})
        b = get_model("b", timeline=timeline, pub={"b": None}, sub={})
        c = get_model("c", timeline=timeline, pub={"c": None}, sub={"a": None, "b": None})
        models = ModelCollection(a=a, b=b, c=c)
        models.determine_interdependency()
        assert a.publishes_to == [c]
        assert b.publishes_to == [a, c]
        assert c.publishes_to == []

    def test_determine_interdependency_subscribed_to(self, timeline):
        """
        a publishes to c
        b publishes to a and c
        """
        a = get_model("a", timeline=timeline, pub={"a": None}, sub={"b": None})
        b = get_model("b", timeline=timeline, pub={"b": None}, sub={})
        c = get_model("c", timeline=timeline, pub={"c": None}, sub={"a": None, "b": None})
        models = ModelCollection(a=a, b=b, c=c)
        models.determine_interdependency()
        assert a.subscribed_to == [b]
        assert b.subscribed_to == []
        assert c.subscribed_to == [a, b]

    def test_reset_model_timers(self, models):
        mock = self.mock_with_single_object(models, "timer")
        models.reset_model_timers()
        assert mock.reset.call_count == 2


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
    return MessageRouterSocket(socket)


@pytest.fixture
def orchestrator(create_orchestrator, config):
    return create_orchestrator(config)


@pytest.fixture
def setup_orchestrator(create_orchestrator):
    def make_orchestrator(models: t.Sequence[str], orchestrator_cls=Orchestrator):
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

        return create_orchestrator(config, orchestrator_cls=orchestrator_cls)

    return make_orchestrator


@pytest.fixture
def settings():
    return Settings(name="orchestrator")


@pytest.fixture
def create_orchestrator(message_socket, settings):
    def _create(config, orchestrator_cls=Orchestrator):
        settings.apply_scenario_config(config)
        orchestrator = orchestrator_cls()
        logger = logging.getLogger()
        stream = Stream(message_socket, logger)
        orchestrator.setup(logger=logger, stream=stream, settings=settings)
        return orchestrator

    return _create


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
    """This is a fixture that can be called to run an orchestrator session / simulate a simulation.
    The fixture is a callable that takes in a sequence of strings (one unique identifier per
    "model" participating in the simulation) and a sequence of model's responses: tuples where the
    first item is a model's identifier, the second item is the Message that the model sends to the
    orchestrator. The result of calling this fixture is a similar list of tuples with the
    orchestrator's commands to the respective models following from the incoming messages from the
    models.

    If the sequence of model responses runs out before the orchestrator finishes, or if there are
    model responses pending after the orchestrator finishes, a ValueError is raised.
    """

    def message_to_bytes(payload: t.Tuple[str, Message]):
        ident, message = payload
        return [ident.encode(), b"", *dump_message(message)]

    def bytes_to_message(raw_bytes: t.Sequence[bytes]):
        ident, _, *payload = raw_bytes
        msg_type, *content = payload
        return ident.decode(), load_message(msg_type, *content)

    def _run_fsm(
        models: t.Sequence[str],
        updates: t.Sequence[t.Tuple[str, Message]],
        orchestrator_cls=Orchestrator,
    ):
        incoming = map(message_to_bytes, updates)
        orchestrator = setup_orchestrator(models, orchestrator_cls=orchestrator_cls)
        socket.recv_multipart.side_effect = incoming
        try:
            orchestrator.run()
        except StopIteration as e:
            raise ValueError(
                "Requires more model responses\n\nResult so far:\n"
                + "\n".join(
                    str(bytes_to_message(call[0][0]))
                    for call in socket.send_multipart.call_args_list
                )
            ) from e
        try:
            msg = socket.recv_multipart()
        except StopIteration:
            pass
        else:
            raise ValueError(
                "Orchestrator finished while there were still model responses pending:\n"
                + f" {bytes_to_message(msg)}\n\nResult so far:\n"
                + "\n".join(
                    str(bytes_to_message(call[0][0]))
                    for call in socket.send_multipart.call_args_list
                )
            )

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
            #
            ("model_a", AcknowledgeMessage()),
            ("model_b", AcknowledgeMessage()),
            ("model_c", AcknowledgeMessage()),
            # 2) orchestrator sends out t=0 update calls. The message for model_b is postponed
            # since it's dependency is busy, the models respond
            ("model_a", ResultMessage(key="a", address="address_a", next_time=1)),
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
        # 2) orchestrator sends out t=0 update calls. Model b update is postponed because it
        # depends on model a
        ("model_a", UpdateMessage(0)),
        ("model_c", UpdateMessage(0)),
        # 3) orchestrator sends update series to model_b with its first, postponed major update and
        # info about model_a
        (
            "model_b",
            UpdateSeriesMessage(
                [UpdateMessage(0), UpdateMessage(0, key="a", address="address_a")]
            ),
        ),
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
        (
            "model_b",
            UpdateSeriesMessage(
                updates=[
                    UpdateMessage(0),
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


def test_cascading_updates_have_preference_over_next_time_updates(run_orchestrator):
    # Here we have to make sure that A is first called for a major update. Since A depends on B,
    # this is only possible if B is not called first for its major update. We postpone the
    # major t=0 update for B by introducing a dependency C that is busy the first time B returns
    # (Acknowledge). Now A gets called and can return with next_time=0 before a cascading update
    # from B can come in. The rest resolves as normal

    results = run_orchestrator(
        ["model_a", "model_b", "model_c"],
        [
            ("model_a", RegistrationMessage(pub={"a": None}, sub={"b": None})),
            ("model_b", RegistrationMessage(pub={"b": None}, sub={"c": None})),
            ("model_c", RegistrationMessage(pub={"c": None}, sub={})),
            ("model_b", AcknowledgeMessage()),
            ("model_a", AcknowledgeMessage()),
            ("model_c", AcknowledgeMessage()),
            ("model_a", ResultMessage(next_time=0)),
            ("model_c", ResultMessage()),
            ("model_b", ResultMessage(key="b", address="address_b")),
            ("model_a", ResultMessage(next_time=0)),
            ("model_a", ResultMessage()),
            ("model_a", AcknowledgeMessage()),
            ("model_b", AcknowledgeMessage()),
            ("model_c", AcknowledgeMessage()),
        ],
    )

    assert results == [
        ("model_a", NewTimeMessage(0)),
        ("model_b", NewTimeMessage(0)),
        ("model_c", NewTimeMessage(0)),
        ("model_a", UpdateMessage(0)),
        ("model_c", UpdateMessage(0)),
        ("model_b", UpdateMessage(0)),
        ("model_a", UpdateMessage(0, key="b", address="address_b")),
        ("model_a", UpdateMessage(0)),
        ("model_a", QuitMessage()),
        ("model_b", QuitMessage()),
        ("model_c", QuitMessage()),
    ]


def test_failed_model_doesnt_have_to_quit(run_orchestrator):
    results = run_orchestrator(["model_a"], [("model_a", ErrorMessage())])
    assert results == []


def test_multiple_models_can_fail(run_orchestrator):
    results = run_orchestrator(
        ["model_a", "model_b"],
        [
            ("model_a", ErrorMessage()),
            ("model_b", ErrorMessage()),
        ],
    )
    assert results == []


def test_sends_quit_after_failed_model(run_orchestrator):
    results = run_orchestrator(
        ["model_a", "model_b"],
        [
            ("model_b", ErrorMessage()),
            ("model_a", RegistrationMessage(pub={"a": None}, sub={"b": None})),
            ("model_a", AcknowledgeMessage()),
        ],
    )

    assert results == [
        ("model_a", QuitMessage(due_to_failure=True)),
    ]


def test_invalid_response_fails_model(run_orchestrator):
    results = run_orchestrator(
        ["model_a"],
        [
            ("model_a", AcknowledgeMessage()),  # Should've been RegistrationMessage
            ("model_a", AcknowledgeMessage()),
        ],
    )
    assert results == [
        ("model_a", QuitMessage()),
    ]


def test_invalid_response_in_finalizing_doesnt_trigger_another_quit(run_orchestrator):
    results = run_orchestrator(
        ["model_a"],
        [
            ("model_a", RegistrationMessage(pub={}, sub={})),
            ("model_a", AcknowledgeMessage()),
            ("model_a", ResultMessage()),
            # Simulation is done, quitting
            ("model_a", ResultMessage()),  # Should've been AcknowledgeMessage
        ],
    )
    assert results == [
        ("model_a", NewTimeMessage(0)),
        ("model_a", UpdateMessage(0)),
        ("model_a", QuitMessage()),
    ]


def test_acknowledge_message_triggers_pending_model_with_NoUpdateMessage(run_orchestrator):
    results = run_orchestrator(
        ["a", "b", "c"],
        [
            # SETUP UNTIL T>0
            ("a", RegistrationMessage(pub={"c": None}, sub={})),
            ("b", RegistrationMessage(pub={"c": None}, sub={})),
            ("c", RegistrationMessage(pub={}, sub={"c": None})),
            # Models respond to new time
            ("a", AcknowledgeMessage()),
            ("b", AcknowledgeMessage()),
            ("c", AcknowledgeMessage()),
            ("a", ResultMessage(next_time=1)),
            ("b", ResultMessage()),
            ("c", ResultMessage()),
            # END SETUP
            # new time = 1
            ("a", AcknowledgeMessage()),
            # Model a is very fast to respond
            ("a", ResultMessage(key="a", address="a", next_time=2)),
            ("c", AcknowledgeMessage()),
            # model c has now pending updates but waits for b
            # Model b is slow to respond to new time, model c still expects Update/NoUpdate from b
            # the AcknowledgeMessage sends a NoUpdate to c
            ("b", AcknowledgeMessage()),
            # Now c is called and sends a Result back
            ("c", ResultMessage()),
            # FINISHING UP THE SIMULATION
            ("a", AcknowledgeMessage()),
            ("b", AcknowledgeMessage()),
            ("c", AcknowledgeMessage()),
            ("a", ResultMessage()),
            ("a", AcknowledgeMessage()),
            ("b", AcknowledgeMessage()),
            ("c", AcknowledgeMessage()),
        ],
    )
    assert results == [
        # SETUP
        ("a", NewTimeMessage(0)),
        ("b", NewTimeMessage(0)),
        ("c", NewTimeMessage(0)),
        ("a", UpdateMessage(0)),
        ("b", UpdateMessage(0)),
        ("c", UpdateMessage(0)),
        # END SETUP
        ("a", NewTimeMessage(1)),
        ("b", NewTimeMessage(1)),
        ("c", NewTimeMessage(1)),
        ("a", UpdateMessage(1)),
        ("c", UpdateMessage(timestamp=1, key="a", address="a")),
        # FINISHING UP THE SIMULATION
        ("a", NewTimeMessage(2)),
        ("b", NewTimeMessage(2)),
        ("c", NewTimeMessage(2)),
        ("a", UpdateMessage(2)),
        ("a", QuitMessage()),
        ("b", QuitMessage()),
        ("c", QuitMessage()),
    ]


def test_acknowledge_message_doesnt_trigger_pending_model_when_dependency_should_calculate(
    run_orchestrator,
):
    results = run_orchestrator(
        ["a", "b", "c"],
        [
            # SETUP UNTIL T>0
            ("a", RegistrationMessage(pub={"c": None}, sub={})),
            ("b", RegistrationMessage(pub={"c": None}, sub={})),
            ("c", RegistrationMessage(pub={}, sub={"c": None})),
            # Models respond to new time
            ("a", AcknowledgeMessage()),
            ("b", AcknowledgeMessage()),
            ("c", AcknowledgeMessage()),
            ("a", ResultMessage(next_time=1)),
            ("b", ResultMessage(next_time=1)),
            ("c", ResultMessage()),
            # END SETUP
            # new time = 1
            ("a", AcknowledgeMessage()),
            # Model a is very fast to respond
            ("a", ResultMessage(key="a", address="a", next_time=2)),
            ("c", AcknowledgeMessage()),
            # model c has now pending updates but waits for b
            # Model b is slow to respond to new time, model c still expects Update/NoUpdate from b
            # the AcknowledgeMessage does not send NoUpdate to c
            ("b", AcknowledgeMessage()),
            # First b must send its result
            ("b", ResultMessage(key="b", address="b")),
            # Now c is called and sends a Result back
            ("c", ResultMessage()),
            # FINISHING UP THE SIMULATION
            ("a", AcknowledgeMessage()),
            ("b", AcknowledgeMessage()),
            ("c", AcknowledgeMessage()),
            ("a", ResultMessage()),
            ("a", AcknowledgeMessage()),
            ("b", AcknowledgeMessage()),
            ("c", AcknowledgeMessage()),
        ],
    )
    assert results == [
        # SETUP
        ("a", NewTimeMessage(0)),
        ("b", NewTimeMessage(0)),
        ("c", NewTimeMessage(0)),
        ("a", UpdateMessage(0)),
        ("b", UpdateMessage(0)),
        ("c", UpdateMessage(0)),
        # END SETUP
        ("a", NewTimeMessage(1)),
        ("b", NewTimeMessage(1)),
        ("c", NewTimeMessage(1)),
        ("a", UpdateMessage(1)),
        ("b", UpdateMessage(1)),
        (
            "c",
            UpdateSeriesMessage(
                [
                    UpdateMessage(timestamp=1, key="a", address="a"),
                    UpdateMessage(timestamp=1, key="b", address="b"),
                ]
            ),
        ),
        # FINISHING UP THE SIMULATION
        ("a", NewTimeMessage(2)),
        ("b", NewTimeMessage(2)),
        ("c", NewTimeMessage(2)),
        ("a", UpdateMessage(2)),
        ("a", QuitMessage()),
        ("b", QuitMessage()),
        ("c", QuitMessage()),
    ]


def test_crashing_model_shuts_down_simulation_during_registration(run_orchestrator):
    results = run_orchestrator(
        ["a", "b"],
        [
            ("a", ErrorMessage()),
            ("b", RegistrationMessage(pub=None, sub=None)),
            ("b", AcknowledgeMessage()),
        ],
    )
    assert results == [
        ("b", QuitMessage(due_to_failure=True)),
    ]


def test_invalid_command_gracefully_shuts_down_models(run_orchestrator):
    class IncorrectState(OrchestratorState):
        def run(self):
            self.context.recv_for_all(UpdateMessage(0))

    failing_fsm_config = FSMConfig(
        initial_state=IncorrectState,
        states={
            IncorrectState: [
                (Failed, StartFinalizingPhase),
            ],
            StartFinalizingPhase: [
                (AllModelsReady, EndFinalizingPhase),
                (Always, FinalizingWaitForModels),
            ],
            FinalizingWaitForModels: [
                (AllModelsReady, EndFinalizingPhase),
            ],
            EndFinalizingPhase: [],
        },
    )

    class FailingOrchestrator(Orchestrator):
        def _setup_fsm(self):
            self.fsm = FSM(failing_fsm_config, context=self.context)
            self.stream.set_handler(self.fsm.send)

    results = run_orchestrator(
        ["a", "b"],
        [
            ("a", RegistrationMessage(pub={}, sub={})),
            ("b", RegistrationMessage(pub={}, sub={})),
            # Models acknowledge Quitmessage
            ("a", AcknowledgeMessage()),
            ("b", AcknowledgeMessage()),
        ],
        orchestrator_cls=FailingOrchestrator,
    )
    assert results == [
        ("a", QuitMessage()),
        ("b", QuitMessage()),
    ]
