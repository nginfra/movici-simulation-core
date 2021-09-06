class SimulationException(Exception):
    pass


class OrchestratorException(SimulationException):
    pass


class SimulationExit(OrchestratorException):
    pass


class NotReady(SimulationException):
    pass


class InvalidMessage(SimulationException):
    pass
