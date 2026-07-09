from __future__ import annotations

from abc import ABC

from movici_simulation_core.messages import ModelMessage, QuitMessage
from movici_simulation_core.services.orchestrator.context import Context
from movici_simulation_core.services.orchestrator.fsm import (
    Condition,
    FSMDone,
    FSMError,
    State,
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


class WaitForModels(OrchestratorState, ABC):
    requires_event = True

    def handle_event(self, event: ModelMessage):
        ident, msg = event

        if not (model := self.context.models.get(ident)):
            return
        self.context.recv_message(model, msg)


class ModelsRegistration(WaitForModels):
    pass


class StartRunningPhase(OrchestratorState):
    def run(self):
        self.context.models.determine_interdependency()
        self.context.log_interconnectivity_matrix()
        self.context.phase_timer.restart()
        self.context.log_new_phase("Running Phase")


class NewTime(OrchestratorState):
    def run(self):
        self.context.log_new_time()
        self.context.queue_models_for_next_time()


class WaitForResults(WaitForModels):
    pass


class StartFinalizingPhase(OrchestratorState):
    def run(self):
        self.context.phase_timer.restart()
        self.context.log_new_phase("Finalizing Phase")
        self.context.recv_for_all(QuitMessage(due_to_failure=bool(self.context.failed)))


class FinalizingWaitForModels(WaitForModels):
    pass


class EndFinalizingPhase(OrchestratorState):
    def run(self):
        self.context.finalize()
        raise FSMError if self.context.failed else FSMDone
