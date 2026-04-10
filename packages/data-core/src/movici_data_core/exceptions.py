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

    def __str__(self) -> str:
        parts = [self.resource_type]
        if self.name is not None:
            parts.append(f"({self.name})")
        if self.id is not None:
            parts.append(f"({self.id})")
        if self.message is not None:
            parts.append(f"[{self.message}]")
        return " ".join(parts)


class ResourceDoesNotExist(InvalidResource):
    pass


class ResourceAlreadyExists(InvalidResource):
    pass


class InvalidAction(MoviciDataError):
    def __init__(self, message: str | None = None):
        self.message = message
