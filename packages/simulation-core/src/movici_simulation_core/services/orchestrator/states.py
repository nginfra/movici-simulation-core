from __future__ import annotations

from abc import ABC

from movici_simulation_core.messages import QuitMessage
from movici_simulation_core.services.orchestrator.context import Context
from movici_simulation_core.services.orchestrator.fsm import (
    Always,
    Condition,
    FSMDone,
    FSMError,
    State,
    TransitionsT,
)
from movici_simulation_core.services.orchestrator.remap import RemapConflictError


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
            (AllModelsReady, ComputeAndSendRemap),
        ]


class ComputeAndSendRemap(OrchestratorState):
    """Compute the REMAP plan from the registered pub/sub masks + priorities and queue a
    REMAP command for every affected model. Each affected model transitions to its
    Remapping state (Busy) and must acknowledge. Models that need no remap stay in
    AwaitingRemap (not busy) and pass through transparently. See issue #127.

    REMAP is one-shot: this state runs exactly once, after all models have registered and
    before the first ``NEW_TIME``. Attribute ownership (and therefore the pub/sub renaming)
    is fixed for the whole run — there is no path that re-enters this state, so priorities
    cannot change mid-simulation. Runtime ownership transfer is deliberately out of scope
    (see issue #127)."""

    def run(self):
        try:
            plan = self.context.models.compute_remap_plan()
        except RemapConflictError as exc:
            # Conflict — log a user-actionable message and tear the simulation down via
            # the standard finalize path so any partially-registered models still get a
            # clean QUIT.
            self.context.logger.error(str(exc))
            for model in self.context.models.values():
                model.failed = True
            return
        if not plan:
            return
        self.context.models.apply_remap_plan(plan)

    def transitions(self) -> TransitionsT:
        return [
            (Failed, StartFinalizingPhase),
            (AllModelsReady, StartRunningPhase),
            (Always, WaitForRemapAcks),
        ]


class WaitForRemapAcks(WaitForModels):
    """Wait until every model that received a REMAP has acknowledged before proceeding to
    the Running phase. See issue #127."""

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
        self.context.models.queue_all(QuitMessage(due_to_failure=bool(self.context.failed)))

    def transitions(self) -> TransitionsT:
        return [(AllModelsReady, EndFinalizingPhase), (Always, FinalizingWaitForModels)]


class FinalizingWaitForModels(WaitForModels):
    def transitions(self) -> TransitionsT:
        return [(AllModelsReady, EndFinalizingPhase)]


class EndFinalizingPhase(OrchestratorState):
    def run(self):
        self.context.finalize()
        raise FSMError if self.context.failed else FSMDone

    def transitions(self) -> TransitionsT:
        return []
