from fastapi import APIRouter

from movici_data_core.marshalling import OperationSuccess, OptionsIn, OptionsOut

from .dependencies import DepBackend

options_router = APIRouter(prefix="/options")


@options_router.get("")
async def get_options(backend: DepBackend) -> OptionsOut:
    options = backend.options
    return OptionsOut(
        mode=options.mode,
        strict_dataset_types=options.STRICT_DATASET_TYPES,
        strict_entity_types=options.STRICT_ENTITY_TYPES,
        strict_attribute_types=options.STRICT_ATTRIBUTE_TYPES,
        strict_model_types=options.STRICT_MODEL_TYPES,
        strict_scenario_datasets=options.STRICT_SCENARIO_DATASETS,
        immutable_workspace_names=options.IMMUTABLE_WORKSPACE_NAMES,
    )


@options_router.patch("", response_model_exclude_none=True)
async def update_options(
    options: OptionsIn,
    backend: DepBackend,
) -> OperationSuccess:
    if options.mode is not None:
        await backend.set_database_mode(options.mode)
    backend.set_options(
        strict_dataset_types=options.strict_dataset_types,
        strict_entity_types=options.strict_entity_types,
        strict_attribute_types=options.strict_attribute_types,
        strict_model_types=options.strict_model_types,
        strict_scenario_datasets=options.strict_scenario_datasets,
        immutable_workspace_names=options.immutable_workspace_names,
    )
    return OperationSuccess.for_path_operation(resource="options", verb="updated")
