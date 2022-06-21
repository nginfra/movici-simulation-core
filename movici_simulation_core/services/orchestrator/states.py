from __future__ import annotations

from abc import ABC

from movici_simulation_core.messages import QuitMessage
from movici_simulation_core.services.orchestrator.context import Context
from movici_simulation_core.services.orchestrator.fsm import (
    Always,
    Condition,
    FSMDone,
    State,
    TransitionsT,
)


class OrchestratorCondition(Condition[Context], ABC):
    pass


class AllModelsReady(OrchestratorCondition):
    def met(self) -> bool:
        return not self.context.models.busy


class AllModelsDone(OrchestratorCondition):
    def met(self) -> bool:
        return AllModelsReady(self.context).met() and self.context.models.next_time is None


class Failed(OrchestratorCondition):
    def met(self) -> bool:
        return bool(self.context.failed)


class OrchestratorState(State[Context]):
    pass


class StartInitializingPhase(OrchestratorState):
    def run(self):
        self.context.global_timer.start()
        self.context.phase_timer.start()
        self.context.log_new_phase("Initializing Phase")

    def transitions(self):
        return [(Always, ModelsRegistration)]


class WaitForModels(OrchestratorState, ABC):
    def run(self):
        ident, msg = yield

        if not (model := self.context.models.get(ident)):
            return
        model.recv_event(msg)


class ModelsRegistration(WaitForModels):
    def transitions(self) -> TransitionsT:
        return [
            (Failed, StartFinalizingPhase),
            (AllModelsReady, StartRunningPhase),
        ]


class StartRunningPhase(OrchestratorState):
    def run(self):
        self.context.models.determine_interdependency()
        self.context.log_interconnectivity_matrix()
        self.context.phase_timer.restart()
        self.context.log_new_phase("Running Phase")

    def transitions(self) -> TransitionsT:
        return [(Always, NewTime)]


class NewTime(OrchestratorState):
    def run(self):
        self.context.log_new_time()
        self.context.timeline.queue_for_next_time(self.context.models)

    def transitions(self) -> TransitionsT:
        return [(Always, WaitForResults)]


class WaitForResults(WaitForModels):
    def transitions(self) -> TransitionsT:
        return [
            (Failed, StartFinalizingPhase),
            (AllModelsDone, StartFinalizingPhase),
            (AllModelsReady, NewTime),
        ]


class StartFinalizingPhase(OrchestratorState):
    def run(self):
        self.context.phase_timer.restart()
        self.context.log_new_phase("Finalizing Phase")
        self.context.models.queue_all(QuitMessage())

    def transitions(self) -> TransitionsT:
        return [(AllModelsReady, EndFinalizingPhase), (Always, FinalizingWaitForModels)]


class FinalizingWaitForModels(WaitForModels):
    def transitions(self) -> TransitionsT:
        return [(AllModelsReady, EndFinalizingPhase)]


class EndFinalizingPhase(OrchestratorState):
    def run(self):
        self.context.finalize()
        raise FSMDone

    def transitions(self) -> TransitionsT:
        return []
