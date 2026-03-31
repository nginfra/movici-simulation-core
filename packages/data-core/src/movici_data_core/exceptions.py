from uuid import UUID


class MoviciDataError(Exception):
    pass


class DatabaseAlreadyInitialized(MoviciDataError):
    pass


class DatabaseNotYetInitialized(MoviciDataError):
    pass


class InconsistentDatabase(MoviciDataError):
    pass


class InvalidResource(MoviciDataError):
    def __init__(
        self,
        resource_type: str,
        name: str | None = None,
        id: UUID | None = None,
        message: str | None = None,
    ):
        if not (name or id):
            raise ValueError("Supply at least one of name or id")
        self.resource_type = resource_type
        self.name = name
        self.id = id
        self.message = message


class ResourceDoesNotExist(InvalidResource):
    pass


class ResourceAlreadyExists(InvalidResource):
    pass


class InvalidAction(MoviciDataError):
    def __init__(self, message: str | None = None):
        self.message = message
