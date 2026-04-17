import dataclasses
import typing as t


@dataclasses.dataclass
class AuthorizationRequest:
    verb: str
    resource_type: str
    resource_name: str
    parent_resource_type: str
    parent_resource_name: str


class AuthorizationProvider(t.Protocol):
    def is_allowed(self, request: AuthorizationRequest): ...
