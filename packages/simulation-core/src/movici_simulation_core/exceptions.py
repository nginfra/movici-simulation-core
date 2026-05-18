class SimulationException(Exception):
    pass


class StreamDone(SimulationException):
    pass


class StartupFailure(SimulationException):
    pass


class OrchestratorException(SimulationException):
    pass


class SimulationExit(OrchestratorException):
    pass


class NotReady(SimulationException):
    pass


class InvalidMessage(SimulationException):
    pass


class FSMException(Exception):
    pass


class FSMStarted(FSMException):
    pass


class FSMDone(FSMException):
    pass


class FSMError(FSMException):
    pass
