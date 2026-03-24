class MoviciDataError(Exception):
    pass


class DatabaseAlreadyInitialized(MoviciDataError):
    pass


class DatabaseNotYetInitialized(MoviciDataError):
    pass
