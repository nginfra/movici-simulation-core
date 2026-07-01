import typing as t
from uuid import UUID

from fastapi import APIRouter

from movici_data_core.database.backend import SQLAlchemyBackend
from movici_data_core.exceptions import ResourceDoesNotExist
from movici_data_core.marshalling import (
    AttributeTypeIn,
    AttributeTypeListOut,
    AttributeTypeOut,
    DatasetTypeIn,
    DatasetTypeListOut,
    DatasetTypeOut,
    EntityTypeIn,
    EntityTypeListOut,
    EntityTypeOut,
    InModel,
    ModelTypeIn,
    ModelTypeListOut,
    ModelTypeOut,
    OperationSuccess,
    OutModel,
)
from movici_data_core.services.common import GenericService

from .dependencies import DepBackend

T = t.TypeVar("T")
ServiceGetter = t.Callable[[SQLAlchemyBackend], GenericService[T]]


def create_router(
    prefix: str,
    resource_type: str,
    get_service: ServiceGetter[T],
    in_model: type[InModel[T]],
    out_model: type[OutModel[T]],
    out_model_list: type[OutModel[t.Sequence[T]]],
):
    router = APIRouter(prefix=prefix)

    async def list_resources(backend: DepBackend):
        service = get_service(backend)
        return out_model_list.from_domain(await service.list())

    async def get_resource(id: UUID, backend: DepBackend):
        service = get_service(backend)
        resource = await service.get(id=id)
        if resource is None:
            raise ResourceDoesNotExist(resource_type, id=id)
        return out_model.from_domain(resource)

    async def create_resource(backend: DepBackend, payload: InModel) -> OperationSuccess:
        service = get_service(backend)
        result = await service.create(obj=payload.to_domain())
        return OperationSuccess(resource=resource_type, verb="created", id=result)

    create_resource.__annotations__["payload"] = in_model

    async def update_resource(id: UUID, backend: DepBackend, payload: InModel) -> OperationSuccess:
        service = get_service(backend)
        await service.update(id=id, obj=payload.to_domain())
        return OperationSuccess(resource=resource_type, verb="updated", id=id)

    update_resource.__annotations__["payload"] = in_model

    async def delete_resource(id: UUID, backend: DepBackend) -> OperationSuccess:
        service = get_service(backend)
        await service.delete(id=id)
        return OperationSuccess(resource=resource_type, verb="deleted", id=id)

    router.get("/", response_model=out_model_list)(list_resources)
    router.get("/{id}", response_model=out_model)(get_resource)
    router.post("/")(create_resource)
    router.put("/{id}")(update_resource)
    router.delete("/{id}")(delete_resource)
    return router


dataset_type_router = create_router(
    "/dataset_types",
    "dataset_type",
    lambda b: b.dataset_types,
    in_model=DatasetTypeIn,
    out_model=DatasetTypeOut,
    out_model_list=DatasetTypeListOut,
)
entity_type_router = create_router(
    "/entity_types",
    "entity_type",
    lambda b: b.entity_types,
    in_model=EntityTypeIn,
    out_model=EntityTypeOut,
    out_model_list=EntityTypeListOut,
)
attribute_type_router = create_router(
    "/attribute_types",
    "attribute_type",
    lambda b: b.attribute_types,
    in_model=AttributeTypeIn,
    out_model=AttributeTypeOut,
    out_model_list=AttributeTypeListOut,
)
model_type_router = create_router(
    "/model_types",
    "model_type",
    lambda b: b.model_types,
    in_model=ModelTypeIn,
    out_model=ModelTypeOut,
    out_model_list=ModelTypeListOut,
)
