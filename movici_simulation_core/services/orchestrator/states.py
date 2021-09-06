from __future__ import annotations
from abc import ABC
import typing as t

from movici_simulation_core.networking.messages import (
    Message,
    RegistrationMessage,
    ResultMessage,
    AcknowledgeMessage,
    QuitMessage,
)
from movici_simulation_core.services.orchestrator.context import Context
from movici_simulation_core.exceptions import SimulationExit
from movici_simulation_core.services.orchestrator.fsm import (
    State,
    Condition,
    Always,
    TransitionsT,
    FSMDone,
)


class OrchestratorCondition(Condition[Context], ABC):
    pass


class AllModelsReady(OrchestratorCondition):
    def met(self) -> bool:
        return not (self.context.models.waiting or self.context.models.messages_pending)


class AllModelsDone(OrchestratorCondition):
    def met(self) -> bool:
        return AllModelsReady(self.context).met() and self.context.models.next_time is None


class Quitting(OrchestratorCondition):
    def met(self) -> bool:
        return self.context.quitting or bool(self.context.failed)


class OrchestratorState(State[Context]):
    pass


class StartInitializingPhase(OrchestratorState):
    def run(self):
        self.context.models.wait_for_all()
        self.context.global_timer.start()
        self.context.phase_timer.start()

    def transitions(self):
        return [(Always, ModelsRegistration)]


class WaitForModels(OrchestratorState, ABC):
    valid_messages: t.Optional[t.Tuple[t.Type[Message]]] = None

    def run(self):
        ident, msg = yield

        if not (model := self.context.models.get(ident)):
            return

        try:
            model.handle_message(msg, self.valid_messages)
        except SimulationExit:
            self.context.failed.append(ident)
        else:
            self.context.models.send_pending_messages()


class ModelsRegistration(WaitForModels):
    valid_messages = (RegistrationMessage,)

    def transitions(self) -> TransitionsT:
        return [
            (Quitting, StartFinalizingPhase),
            (AllModelsReady, StartRunningPhase),
        ]


class StartRunningPhase(OrchestratorState):
    def run(self):
        self.context.models.determine_interdependency()
        self.context.phase_timer.restart()

    def transitions(self) -> TransitionsT:
        return [(Always, NewTime)]


class NewTime(OrchestratorState):
    def run(self):
        self.context.timeline.queue_for_next_time(self.context.models)
        self.context.models.send_pending_messages()

    def transitions(self) -> TransitionsT:
        return [(Always, WaitForResults)]


class WaitForResults(WaitForModels):
    valid_messages = (ResultMessage, AcknowledgeMessage)

    def transitions(self) -> TransitionsT:
        return [
            (Quitting, StartFinalizingPhase),
            (AllModelsDone, StartFinalizingPhase),
            (AllModelsReady, NewTime),
        ]


class StartFinalizingPhase(OrchestratorState):
    def run(self):
        self.context.phase_timer.restart()
        self.context.models.clear_queue()
        self.context.models.queue_all(QuitMessage())
        self.context.models.send_pending_messages()

    def transitions(self) -> TransitionsT:
        return [(Always, FinalizingWaitForModels)]


class FinalizingWaitForModels(WaitForModels):
    valid_messages = (AcknowledgeMessage,)

    def transitions(self) -> TransitionsT:
        return [(AllModelsReady, EndFinalizingPhase)]


class EndFinalizingPhase(OrchestratorState):
    def run(self):
        self.context.finalize()
        raise FSMDone

    def transitions(self) -> TransitionsT:
        return []
