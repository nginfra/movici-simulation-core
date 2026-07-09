class SimulationException(Exception):
    pass


class StreamDone(SimulationException):
    pass


class StartupFailure(SimulationException):
    pass


class OrchestratorException(SimulationException):
    pass


class InvalidCommand(OrchestratorException):
    pass


class NotReady(SimulationException):
    pass


class InvalidMessage(SimulationException):
    pass


class RemapError(SimulationException):
    """Raised when a model cannot honour a ``REMAP`` command. The canonical case is a
    many-to-one sub remap delivered to a model that has not implemented the ``remap()``
    callback. See issue #127."""

    pass


class FSMException(Exception):
    pass


class FSMStarted(FSMException):
    pass


class FSMDone(FSMException):
    pass


class FSMError(FSMException):
    pass
