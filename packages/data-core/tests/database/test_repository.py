import asyncio
import dataclasses
import typing as t
import uuid
from asyncio import Barrier
from io import BytesIO
from unittest.mock import patch

import numpy as np
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from movici_data_core.database import model as db
from movici_data_core.database.backend import SQLAlchemyServer
from movici_data_core.database.repository import (
    DatasetDataRepository,
    SQLAlchemyRepository,
)
from movici_data_core.domain_model import (
    AttributeSummary,
    AttributeType,
    BoundingBox,
    Dataset,
    DatasetFormat,
    DatasetSummary,
    DatasetType,
    EntityGroupSummary,
    EntityType,
    ModelType,
    Scenario,
    ScenarioDataset,
    ScenarioModel,
    SimulationInfo,
    Update,
    UpdateModel,
    Workspace,
)
from movici_data_core.exceptions import (
    InvalidAction,
    InvalidResource,
    MoviciValidationError,
    ResourceAlreadyExists,
    ResourceDoesNotExist,
)
from movici_data_core.validators import ModelConfigValidator
from movici_simulation_core.core import DataType
from movici_simulation_core.core.schema import DEFAULT_ROWPTR_KEY
from movici_simulation_core.testing import (
    assert_dataset_dicts_equal,
    dataset_data_to_numpy,
    dataset_dicts_equal,
)


class TestWorkspaceRepository:
    @pytest.fixture
    async def filled_workspace(
        self, repository: SQLAlchemyRepository, a_workspace, a_dataset, a_scenario
    ):
        await repository.datasets.create(dataclasses.replace(a_dataset, name="another_dataset"))
        return await repository.workspaces.get_by_id(a_workspace.id)

    async def test_list_workspaces_with_counts(
        self, repository: SQLAlchemyRepository, filled_workspace
    ):
        result = await repository.workspaces.list()
        assert len(result) == 1
        assert result[0].dataset_count == 2
        assert result[0].scenario_count == 1

    async def filled_workspace_has_counts(self, filled_workspace):
        assert filled_workspace.dataset_count == 2
        assert filled_workspace.scenario_count == 1

    async def test_get_workspace_by_id(self, repository: SQLAlchemyRepository, filled_workspace):
        assert filled_workspace.id is not None
        found = await repository.workspaces.get_by_id(filled_workspace.id)
        assert filled_workspace == found

    async def test_get_workspace_by_name(self, repository: SQLAlchemyRepository, filled_workspace):
        found = await repository.workspaces.get_by_name(filled_workspace.name)
        assert filled_workspace == found

    async def test_get_non_existing_workspace_by_name(self, repository: SQLAlchemyRepository):
        assert (await repository.workspaces.get_by_name("invalid")) is None

    async def test_get_non_existing_workspace_by_id(self, repository: SQLAlchemyRepository):
        assert (await repository.workspaces.get_by_id(uuid.uuid4())) is None

    async def test_created_workspace_gets_a_uuid(self, repository: SQLAlchemyRepository):
        workspace_id = await repository.workspaces.create(
            Workspace(name="some_workspace", display_name="Some Workspace")
        )
        assert int(workspace_id) > 0

    async def test_create_and_delete_a_workspace(self, repository: SQLAlchemyRepository):
        existing = len(await repository.workspaces.list())
        workspace_id = await repository.workspaces.create(
            Workspace(name="some_workspace", display_name="Some Workspace")
        )
        assert len(await repository.workspaces.list()) == existing + 1

        await repository.workspaces.delete(workspace_id)

        assert len(await repository.workspaces.list()) == existing

    async def test_workspace_exists(self, repository: SQLAlchemyRepository):
        assert not await repository.workspaces.exists("some_workspace")
        await repository.workspaces.create(
            Workspace(name="some_workspace", display_name="Some Workspace")
        )
        assert await repository.workspaces.exists("some_workspace")

    async def test_update_workspace(
        self, repository: SQLAlchemyRepository, a_workspace: Workspace
    ):
        assert a_workspace.id is not None
        assert a_workspace.name != "new_name"
        assert a_workspace.display_name != "New Name"
        assert not repository.options.IMMUTABLE_WORKSPACE_NAMES

        await repository.workspaces.update(
            a_workspace.id,
            dataclasses.replace(a_workspace, name="new_name", display_name="New Name"),
        )
        updated = await repository.workspaces.get_by_id(a_workspace.id)
        assert updated is not None
        assert updated.name == "new_name"
        assert updated.display_name == "New Name"

    async def test_cannot_update_workspace_name_when_immutable(
        self, repository: SQLAlchemyRepository, a_workspace
    ):
        assert a_workspace.id is not None
        assert a_workspace.name != "new_name"
        repository.options.IMMUTABLE_WORKSPACE_NAMES = True

        with pytest.raises(InvalidAction, match="cannot update workspace name"):
            await repository.workspaces.update(
                a_workspace.id,
                dataclasses.replace(a_workspace, name="new_name"),
            )

    async def test_create_validates_max_lengths(self, repository: SQLAlchemyRepository):
        with pytest.raises(MoviciValidationError) as e:
            await repository.workspaces.create(Workspace(name="a" * 51, display_name="d" * 51))

        assert set(m[0] for m in e.value.iter_messages()) == {"name", "display_name"}

    async def test_update_validates_max_lengths(self, repository: SQLAlchemyRepository):
        id = await repository.workspaces.create(Workspace(name="a", display_name="d"))
        with pytest.raises(MoviciValidationError) as e:
            await repository.workspaces.update(id, Workspace(name="a" * 51, display_name="d" * 51))

        assert set(m[0] for m in e.value.iter_messages()) == {"name", "display_name"}

    @pytest.mark.database_mode(db.DatabaseMode.SINGLE_WORKSPACE)
    async def test_cannot_delete_default_workspace(
        self, a_workspace, repository: SQLAlchemyRepository
    ):
        with pytest.raises(InvalidAction) as e:
            await repository.workspaces.delete(a_workspace.id)
        assert e.value.message == "Cannot delete default workspace"

    async def test_deleting_workspace_clears_dataset_and_update_data(
        self,
        session,
        repository: SQLAlchemyRepository,
        an_entity_type,
        a_workspace,
        a_dataset,
        a_scenario,
        create_update,
    ):
        base_count = await session.scalar(select(func.count(db.Attribute.id)))
        await repository.dataset_data.create(
            a_dataset.id,
            dataset_data_to_numpy({an_entity_type.name: {"id": [1, 2]}}),
            format=DatasetFormat.ENTITY_BASED,
        )
        await create_update(
            timestamp=0,
            iteration=0,
            data={"transport_nodes": {"id": [1, 3], "transport.capacity": [13.0, 14.0]}},
        )
        assert (await session.scalar(select(func.count(db.Attribute.id)))) == base_count + 3

        await repository.workspaces.delete(a_workspace.id)

        assert (await session.scalar(select(func.count(db.Attribute.id)))) == base_count

    async def test_deleting_workspace_clears_raw_data(
        self, session, repository: SQLAlchemyRepository, a_workspace, a_dataset
    ):
        base_count = await session.scalar(select(func.count(db.RawDataChunk.id)))
        await repository.dataset_data.create(
            a_dataset.id,
            b"asdfasdf",
            format=DatasetFormat.BINARY,
        )
        assert (await session.scalar(select(func.count(db.RawDataChunk.id)))) > base_count

        await repository.workspaces.delete(a_workspace.id)

        assert (await session.scalar(select(func.count(db.RawDataChunk.id)))) == base_count


class TestDatasetTypeRepository:
    async def test_create_and_delete_a_dataset_type(self, repository: SQLAlchemyRepository):
        existing = len(await repository.dataset_types.list())
        dataset_type_id = await repository.dataset_types.create(
            DatasetType(name="a_dataset_type", format=DatasetFormat.ENTITY_BASED)
        )

        assert dataset_type_id is not None
        assert len(await repository.dataset_types.list()) == existing + 1

        await repository.dataset_types.delete(dataset_type_id)

        assert len(await repository.dataset_types.list()) == existing

    @pytest.mark.parametrize(
        "dataset_type, stores_mimetype",
        [
            (DatasetType("a_type", DatasetFormat.ENTITY_BASED, mimetype="asdf"), False),
            (DatasetType("a_type", DatasetFormat.UNSTRUCTURED, mimetype="asdf"), False),
            (DatasetType("a_type", DatasetFormat.BINARY, mimetype="asdf"), True),
        ],
    )
    async def test_stores_or_ignores_mimetype_on_create(
        self, repository: SQLAlchemyRepository, dataset_type, stores_mimetype
    ):
        id = await repository.dataset_types.create(dataset_type)
        result = await repository.dataset_types.get_by_id(id)
        assert result is not None
        if stores_mimetype:
            assert result.mimetype == dataset_type.mimetype
        else:
            assert result.mimetype is None

    @pytest.mark.parametrize(
        "dataset_type, stores_mimetype",
        [
            (DatasetType("transport_network", DatasetFormat.ENTITY_BASED, mimetype="asdf"), False),
            (DatasetType("tabular", DatasetFormat.UNSTRUCTURED, mimetype="asdf"), False),
            (DatasetType("flooding_tape", DatasetFormat.BINARY, mimetype="asdf"), True),
        ],
    )
    async def test_stores_or_ignores_mimetype_on_update(
        self, repository: SQLAlchemyRepository, dataset_type, stores_mimetype
    ):
        current = await repository.dataset_types.get_by_name(dataset_type.name)
        assert current is not None
        assert current.id is not None
        await repository.dataset_types.update(current.id, dataset_type)

        result = await repository.dataset_types.get_by_id(current.id)
        assert result is not None
        if stores_mimetype:
            assert result.mimetype == dataset_type.mimetype
        else:
            assert result.mimetype != dataset_type.mimetype

    async def test_cannot_create_dataset_type_with_unknown_format(
        self, repository: SQLAlchemyRepository
    ):
        with pytest.raises(InvalidAction):
            await repository.dataset_types.create(DatasetType(name="a_dataset_type"))

    async def test_cannot_delete_dataset_type_when_in_use(
        self, repository: SQLAlchemyRepository, a_dataset_type, a_dataset
    ):

        with pytest.raises(InvalidAction) as e:
            await repository.dataset_types.delete(a_dataset_type.id)

        assert e.value.message == "Cannot delete dataset_type when it is still in use"

    async def test_update_dataset_type(self, repository: SQLAlchemyRepository):

        dataset_type = DatasetType(name="a_dataset_type", format=DatasetFormat.ENTITY_BASED)

        dataset_type_id = await repository.dataset_types.create(dataset_type)

        await repository.dataset_types.update(
            dataset_type_id, dataclasses.replace(dataset_type, name="new_name")
        )
        updated = await repository.dataset_types.get_by_id(dataset_type_id)
        assert updated is not None
        assert updated.name == "new_name"

    async def test_cannot_change_format(self, repository: SQLAlchemyRepository):
        dataset_type = DatasetType(name="a_dataset_type", format=DatasetFormat.ENTITY_BASED)
        dataset_type_id = await repository.dataset_types.create(dataset_type)

        dataset_type.format = DatasetFormat.UNSTRUCTURED
        with pytest.raises(InvalidAction):
            await repository.dataset_types.update(
                dataset_type_id, dataclasses.replace(dataset_type, name="new_name")
            )

    async def test_returns_existing_dataset_type_when_format_unknown(
        self, repository: SQLAlchemyRepository, a_dataset_type
    ):
        repository.options.STRICT_DATASET_TYPES = True
        found = await repository.dataset_types.ensure_dataset_type(
            DatasetType(name="transport_network")
        )
        assert found == a_dataset_type

    async def test_returns_existing_dataset_type_when_compatible(
        self, repository: SQLAlchemyRepository, a_dataset_type
    ):
        repository.options.STRICT_DATASET_TYPES = True
        found = await repository.dataset_types.ensure_dataset_type(
            DatasetType(name="transport_network", format=DatasetFormat.ENTITY_BASED)
        )
        assert found == a_dataset_type

    async def test_raises_on_non_existing_dataset_type_when_strict(
        self, repository: SQLAlchemyRepository
    ):
        repository.options.STRICT_DATASET_TYPES = True

        with pytest.raises(ResourceDoesNotExist):
            await repository.dataset_types.ensure_dataset_type(
                DatasetType(name="non_existing", format=DatasetFormat.ENTITY_BASED)
            )

    async def test_automatically_creates_dataset_type_when_not_strict(
        self, repository: SQLAlchemyRepository
    ):
        repository.options.STRICT_DATASET_TYPES = False

        dataset_type = await repository.dataset_types.ensure_dataset_type(
            DatasetType(name="transport_network", format=DatasetFormat.ENTITY_BASED)
        )

        assert dataset_type is not None
        assert dataset_type.name == "transport_network"
        assert dataset_type.id is not None

    @pytest.mark.parametrize("strict_dataset_types", [True, False])
    async def test_raises_on_incompatible_existing_dataset_type(
        self, repository: SQLAlchemyRepository, a_dataset_type, strict_dataset_types
    ):
        repository.options.STRICT_DATASET_TYPES = strict_dataset_types

        assert a_dataset_type.format == DatasetFormat.ENTITY_BASED
        with pytest.raises(InvalidResource):
            await repository.dataset_types.ensure_dataset_type(
                dataclasses.replace(a_dataset_type, format=DatasetFormat.BINARY)
            )

    async def test_create_validates_max_lengths(self, repository: SQLAlchemyRepository):
        with pytest.raises(MoviciValidationError) as e:
            await repository.dataset_types.create(
                DatasetType(name="a" * 51, format=DatasetFormat.ENTITY_BASED)
            )

        assert set(m[0] for m in e.value.iter_messages()) == {"name"}

    async def test_update_validates_max_lengths(self, repository: SQLAlchemyRepository):
        id = await repository.dataset_types.create(
            DatasetType(name="a", format=DatasetFormat.ENTITY_BASED)
        )
        with pytest.raises(MoviciValidationError) as e:
            await repository.dataset_types.update(
                id, DatasetType(name="a" * 51, format=DatasetFormat.ENTITY_BASED)
            )

        assert set(m[0] for m in e.value.iter_messages()) == {"name"}


class TestEntityTypeRepository:
    async def test_create_and_delete_an_entity_type(self, repository: SQLAlchemyRepository):
        existing = len(await repository.entity_types.list())
        entity_type_id = await repository.entity_types.create(EntityType(name="some_entity_type"))
        assert len(await repository.entity_types.list()) == existing + 1

        await repository.entity_types.delete(entity_type_id)

        assert len(await repository.entity_types.list()) == existing

    async def test_update_entity_type(
        self, repository: SQLAlchemyRepository, an_entity_type: EntityType
    ):
        assert an_entity_type.id is not None

        await repository.entity_types.update(
            an_entity_type.id, dataclasses.replace(an_entity_type, name="new_name")
        )
        updated = await repository.entity_types.get_by_id(an_entity_type.id)
        assert updated is not None
        assert updated.name == "new_name"

    async def test_returns_existing_entity_type_when_compatible(
        self, repository: SQLAlchemyRepository, an_entity_type
    ):
        repository.options.STRICT_ENTITY_TYPES = True
        found = await repository.entity_types.ensure_entity_type(EntityType(an_entity_type.name))
        assert found is not None
        assert found.id == an_entity_type.id

    async def test_raises_on_non_existing_entity_type_when_strict(
        self, repository: SQLAlchemyRepository
    ):
        repository.options.STRICT_ENTITY_TYPES = True

        with pytest.raises(ResourceDoesNotExist):
            await repository.entity_types.ensure_entity_type(EntityType("new_type"))

    async def test_automatically_creates_entity_type_when_not_strict(
        self, repository: SQLAlchemyRepository
    ):
        repository.options.STRICT_ENTITY_TYPES = False

        entity_type = await repository.entity_types.ensure_entity_type(EntityType("new_type"))

        assert entity_type is not None
        assert entity_type.name == "new_type"
        assert entity_type.id is not None

    async def test_create_validates_max_lengths(self, repository: SQLAlchemyRepository):
        with pytest.raises(MoviciValidationError) as e:
            await repository.entity_types.create(EntityType(name="a" * 51))

        assert set(m[0] for m in e.value.iter_messages()) == {"name"}

    async def test_update_validates_max_lengths(self, repository: SQLAlchemyRepository):
        id = await repository.entity_types.create(EntityType(name="a"))
        with pytest.raises(MoviciValidationError) as e:
            await repository.entity_types.update(id, EntityType(name="a" * 51))

        assert set(m[0] for m in e.value.iter_messages()) == {"name"}

    async def test_cannot_delete_entity_type_when_in_use(
        self, repository: SQLAlchemyRepository, an_entity_type, a_dataset
    ):

        await repository.dataset_data.create(
            a_dataset.id,
            dataset_data_to_numpy({an_entity_type.name: {"id": [1, 2]}}),
            format=DatasetFormat.ENTITY_BASED,
        )
        with pytest.raises(InvalidAction) as e:
            await repository.entity_types.delete(an_entity_type.id)

        assert e.value.message == "Cannot delete entity_type when it is still in use"


class TestAttributeTypeRepository:
    async def test_created_attribute_type_has_data_type(self, repository: SQLAlchemyRepository):
        data_type = DataType(int, (2,), csr=True)
        await repository.attribute_types.create(
            AttributeType("attribute_type", data_type=data_type)
        )
        attribute_type = await repository.attribute_types.get_by_name("attribute_type")
        assert attribute_type is not None
        assert attribute_type.data_type == data_type

    async def test_create_attribute_type_with_enum(self, repository: SQLAlchemyRepository):
        data_type = DataType(float)
        await repository.attribute_types.create(
            AttributeType("attribute_type", data_type=data_type, enum_name="something")
        )
        attribute_type = await repository.attribute_types.get_by_name("attribute_type")
        assert attribute_type is not None
        assert attribute_type.enum_name == "something"

    async def test_create_and_delete_an_attribute_type(self, repository: SQLAlchemyRepository):
        existing = len(await repository.attribute_types.list())
        attribute_type_id = await repository.attribute_types.create(
            AttributeType(name="some_attribute_type", data_type=DataType(float))
        )
        assert len(await repository.attribute_types.list()) == existing + 1

        await repository.attribute_types.delete(attribute_type_id)

        assert len(await repository.attribute_types.list()) == existing

    async def test_update_attribute_type(
        self, repository: SQLAlchemyRepository, an_attribute_type: AttributeType
    ):
        assert an_attribute_type.id is not None

        await repository.attribute_types.update(
            an_attribute_type.id, dataclasses.replace(an_attribute_type, name="new_name")
        )
        updated = await repository.attribute_types.get_by_id(an_attribute_type.id)
        assert updated is not None
        assert updated.name == "new_name"

    async def test_cannot_update_data_type_if_in_use(
        self,
        repository: SQLAlchemyRepository,
        an_attribute_type: AttributeType,
        a_dataset,
        an_entity_type,
    ):
        assert an_attribute_type.id is not None

        await repository.dataset_data.create(
            a_dataset.id,
            {
                an_entity_type.name: {
                    an_attribute_type.name: {
                        "data": np.array([1.0, 2.0]),
                    },
                }
            },
            format=DatasetFormat.ENTITY_BASED,
        )
        with pytest.raises(InvalidAction):
            await repository.attribute_types.update(
                an_attribute_type.id,
                dataclasses.replace(an_attribute_type, data_type=DataType(int)),
            )

    async def test_returns_existing_attribute_type_when_compatible(
        self, repository: SQLAlchemyRepository, an_attribute_type
    ):
        repository.options.STRICT_ATTRIBUTE_TYPES = True
        found = await repository.attribute_types.ensure_attribute_type(
            AttributeType("some.attribute", data_type=DataType(float))
        )
        assert found is not None
        assert found.id == an_attribute_type.id

    async def test_raises_on_non_existing_attribute_type_when_strict(
        self, repository: SQLAlchemyRepository
    ):
        repository.options.STRICT_ATTRIBUTE_TYPES = True

        with pytest.raises(ResourceDoesNotExist):
            await repository.attribute_types.ensure_attribute_type(
                AttributeType("some.attribute", data_type=DataType(float))
            )

    async def test_automatically_creates_attribute_type_when_not_strict(
        self, repository: SQLAlchemyRepository
    ):
        repository.options.STRICT_ATTRIBUTE_TYPES = False

        attribute_type = await repository.attribute_types.ensure_attribute_type(
            AttributeType("some.attribute", data_type=DataType(float))
        )

        assert attribute_type is not None
        assert attribute_type.name == "some.attribute"
        assert attribute_type.id is not None

    async def test_raises_on_incompatible_existing_attribute_type(
        self, repository: SQLAlchemyRepository, an_attribute_type
    ):
        repository.options.STRICT_ATTRIBUTE_TYPES = False

        with pytest.raises(InvalidResource):
            await repository.attribute_types.ensure_attribute_type(
                AttributeType("some.attribute", data_type=DataType(int))
            )

    async def test_create_validates_max_lengths(self, repository: SQLAlchemyRepository):
        with pytest.raises(MoviciValidationError) as e:
            await repository.attribute_types.create(
                AttributeType(
                    name="a" * 101,
                    unit="a" * 21,
                    description="a" * 256,
                    enum_name="a" * 21,
                    data_type=DataType(int),
                )
            )

        assert set(m[0] for m in e.value.iter_messages()) == {
            "name",
            "unit",
            "description",
            "enum_name",
        }

    async def test_update_validates_max_lengths(self, repository: SQLAlchemyRepository):
        id = await repository.attribute_types.create(
            AttributeType(name="a", data_type=DataType(int))
        )
        with pytest.raises(MoviciValidationError) as e:
            await repository.attribute_types.update(
                id,
                AttributeType(
                    name="a" * 101,
                    unit="a" * 21,
                    description="a" * 256,
                    enum_name="a" * 21,
                    data_type=DataType(int),
                ),
            )

        assert set(m[0] for m in e.value.iter_messages()) == {
            "name",
            "unit",
            "description",
            "enum_name",
        }

    async def test_cannot_delete_attribute_type_when_in_use(
        self, repository: SQLAlchemyRepository, an_entity_type, an_attribute_type, a_dataset
    ):

        await repository.dataset_data.create(
            a_dataset.id,
            dataset_data_to_numpy(
                {an_entity_type.name: {"id": [1, 2], an_attribute_type.name: [1.0, 2.0]}}
            ),
            format=DatasetFormat.ENTITY_BASED,
        )
        with pytest.raises(InvalidAction) as e:
            await repository.attribute_types.delete(an_attribute_type.id)

        assert e.value.message == "Cannot delete attribute_type when it is still in use"


class TestModelTypeRepository:
    @pytest.fixture
    async def a_model_type(self, repository: SQLAlchemyRepository):
        model_type_id = await repository.model_types.create(
            ModelType(name="some_model", jsonschema={"some": "schema"})
        )
        return await repository.model_types.get_by_id(model_type_id)

    async def test_created_model_type_has_schema(self, a_model_type):
        assert a_model_type.jsonschema == {"some": "schema"}

    async def test_cannot_create_model_type_without_jsonschema(
        self, repository: SQLAlchemyRepository
    ):
        with pytest.raises(InvalidAction):
            await repository.model_types.create(ModelType("no_schema_here", jsonschema=None))

    async def test_update_model_type(
        self, a_model_type: ModelType, repository: SQLAlchemyRepository
    ):
        assert a_model_type.id is not None

        await repository.model_types.update(
            a_model_type.id, ModelType("another_name", {"some": "othershema"})
        )

        updated = await repository.model_types.get_by_name("another_name")
        assert updated is not None
        assert updated.jsonschema == {"some": "othershema"}

    async def test_cannot_update_model_type_without_jsonschema(
        self, a_model_type: ModelType, repository: SQLAlchemyRepository
    ):
        assert a_model_type.id is not None
        with pytest.raises(InvalidAction):
            await repository.model_types.update(
                a_model_type.id, ModelType("no_schema_here", jsonschema=None)
            )

    async def test_returns_existing_model_type(
        self, repository: SQLAlchemyRepository, a_model_type
    ):
        repository.options.STRICT_MODEL_TYPES = True
        found = await repository.model_types.ensure_model_types([ModelType("some_model")])
        assert found == [a_model_type]

    async def test_raises_on_non_existing_model_type_when_strict(
        self, repository: SQLAlchemyRepository
    ):
        repository.options.STRICT_MODEL_TYPES = True

        with pytest.raises(ResourceDoesNotExist):
            await repository.model_types.ensure_model_types([ModelType("non_existing")])

    async def test_automatically_creates_model_type_with_passall_schema_when_not_strict(
        self, repository: SQLAlchemyRepository, a_model_type
    ):
        repository.options.STRICT_MODEL_TYPES = False

        created, existing = await repository.model_types.ensure_model_types(
            [ModelType("new"), a_model_type]
        )
        assert existing == a_model_type
        assert created is not None
        assert created.name == "new"
        assert created.jsonschema == {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "$id": "/new/1.0.0",
            "type": "object",
            "additionalProperties": True,
        }

    async def test_create_validates_max_lengths(self, repository: SQLAlchemyRepository):
        with pytest.raises(MoviciValidationError) as e:
            await repository.model_types.create(
                ModelType(
                    name="a" * 51,
                    jsonschema={},
                )
            )

        assert set(m[0] for m in e.value.iter_messages()) == {"name"}

    async def test_update_validates_max_lengths(self, repository: SQLAlchemyRepository):
        id = await repository.model_types.create(ModelType(name="a", jsonschema={}))
        with pytest.raises(MoviciValidationError) as e:
            await repository.model_types.update(id, ModelType(name="a" * 51, jsonschema={}))

        assert set(m[0] for m in e.value.iter_messages()) == {"name"}

    async def test_validates_max_length_in_ensure_model_types(
        self, repository: SQLAlchemyRepository
    ):
        repository.options.STRICT_MODEL_TYPES = False
        with pytest.raises(MoviciValidationError) as e:
            await repository.model_types.ensure_model_types([ModelType(name="a" * 51)])

        assert set(m[0] for m in e.value.iter_messages()) == {"name"}

    async def test_cannot_delete_model_type_when_in_use(
        self, repository: SQLAlchemyRepository, a_scenario
    ):

        model_type_name = a_scenario.models[0].type.name
        model_type = await repository.model_types.get_by_name(model_type_name)
        assert model_type is not None
        assert model_type.id is not None

        with pytest.raises(InvalidAction) as e:
            await repository.model_types.delete(model_type.id)

        assert e.value.message == "Cannot delete model_type when it is still in use"


class TestDatasetRepository:
    async def test_get_dataset_with_workspace_and_dataset_type(
        self, repository: SQLAlchemyRepository, a_dataset
    ):
        dataset = await repository.datasets.get_by_id(a_dataset.id)
        assert dataset is not None
        assert isinstance(dataset.workspace, Workspace)
        assert isinstance(dataset.dataset_type, DatasetType)

    async def test_create_dataset(self, repository: SQLAlchemyRepository, a_dataset_type):
        dataset_id = await repository.datasets.create(
            Dataset("another_dataset", "Another Dataset", dataset_type=a_dataset_type)
        )
        assert int(dataset_id) > 0

    async def test_dataset_exists(self, repository: SQLAlchemyRepository, a_dataset_type):
        assert not await repository.datasets.exists("another_dataset")

        await repository.datasets.create(
            Dataset("another_dataset", "Another Dataset", dataset_type=a_dataset_type)
        )

        assert await repository.datasets.exists("another_dataset")

    async def test_raises_on_existing_dataset(self, repository: SQLAlchemyRepository, a_dataset):
        with pytest.raises(ResourceAlreadyExists):
            await repository.datasets.create(a_dataset)

    async def test_update_dataset(self, repository: SQLAlchemyRepository, a_dataset):
        await repository.datasets.update(
            a_dataset.id, dataclasses.replace(a_dataset, name="new_name")
        )
        updated = await repository.datasets.get_by_id(a_dataset.id)
        assert updated is not None
        assert updated.name == "new_name"

    async def test_raises_on_invalid_dataset_type_when_strict(
        self, repository: SQLAlchemyRepository, a_workspace, a_dataset_type
    ):
        repository.options.STRICT_DATASET_TYPES = True

        with pytest.raises(InvalidResource):
            await repository.for_workspace(a_workspace.id).datasets.create(
                Dataset(
                    "some_dataset",
                    "some dataset",
                    dataset_type=DatasetType(a_dataset_type.name, format=DatasetFormat.BINARY),
                ),
            )

    async def test_delete_dataset_deletes_data(self, repository: SQLAlchemyRepository, a_dataset):
        with patch.object(DatasetDataRepository, "delete") as mock:
            await repository.datasets.delete(a_dataset.id)
            mock.assert_awaited_once_with(a_dataset.id)

    async def test_returns_existing_datasets(self, repository: SQLAlchemyRepository, a_dataset):
        repository.options.STRICT_SCENARIO_DATASETS = True
        another_dataset_id = await repository.datasets.create(
            Dataset(
                "another_dataset",
                "another_dataset",
                DatasetType("tabular", format=DatasetFormat.UNSTRUCTURED),
            ),
        )
        another_dataset = await repository.datasets.get_by_id(another_dataset_id)
        assert another_dataset is not None

        found = await repository.datasets.ensure_scenario_datasets(
            [
                ScenarioDataset(a_dataset.name, a_dataset.dataset_type),
                ScenarioDataset(another_dataset.name, another_dataset.dataset_type),
            ],
        )
        assert [ds.id for ds in found] == [a_dataset.id, another_dataset.id]

    async def test_raises_on_missing_dataset_when_strict(self, repository: SQLAlchemyRepository):
        repository.options.STRICT_SCENARIO_DATASETS = True

        with pytest.raises(MoviciValidationError):
            await repository.datasets.ensure_scenario_datasets(
                [ScenarioDataset("non_existing", dataset_type=DatasetType("transport_network"))],
            )

    async def test_automatically_creates_dataset_stubs_when_not_strict(
        self, repository: SQLAlchemyRepository, a_dataset
    ):
        repository.options.STRICT_SCENARIO_DATASETS = False

        scenario_datasets = await repository.datasets.ensure_scenario_datasets(
            [
                ScenarioDataset("new", DatasetType("transport_network")),
                ScenarioDataset(a_dataset.name, a_dataset.dataset_type),
                ScenarioDataset("new_tapefile", DatasetType("tabular")),
            ],
        )
        assert [ds.name for ds in scenario_datasets] == ["new", a_dataset.name, "new_tapefile"]
        assert [ds.dataset_type for ds in scenario_datasets] == [
            DatasetType("transport_network", format=DatasetFormat.ENTITY_BASED),
            a_dataset.dataset_type,
            DatasetType("tabular", format=DatasetFormat.UNSTRUCTURED),
        ]
        assert None not in [ds.id for ds in scenario_datasets]

    async def test_create_new_dataset_type_when_required(self, repository: SQLAlchemyRepository):
        repository.options.STRICT_SCENARIO_DATASETS = False
        repository.options.STRICT_DATASET_TYPES = False

        await repository.datasets.ensure_scenario_datasets(
            [ScenarioDataset("new", DatasetType("new_type"))]
        )
        created = await repository.dataset_types.get_by_name("new_type")
        assert created is not None
        assert created == DatasetType("new_type", format=DatasetFormat.ENTITY_BASED)

    async def test_raises_on_new_scenario_dataset_with_incorrect_type(
        self, repository: SQLAlchemyRepository, a_dataset_type
    ):

        repository.options.STRICT_SCENARIO_DATASETS = False

        assert a_dataset_type.format != DatasetFormat.BINARY
        with pytest.raises(MoviciValidationError, match="incompatible dataset type"):
            await repository.datasets.ensure_scenario_datasets(
                [
                    ScenarioDataset(
                        name="new_dataset",
                        dataset_type=dataclasses.replace(
                            a_dataset_type, format=DatasetFormat.BINARY
                        ),
                    )
                ]
            )

    async def test_raises_on_existing_scenario_dataset_with_incorrect_type(
        self, repository: SQLAlchemyRepository, a_dataset
    ):

        repository.options.STRICT_SCENARIO_DATASETS = False

        with pytest.raises(MoviciValidationError, match="incompatible dataset already exists"):
            await repository.datasets.ensure_scenario_datasets(
                [ScenarioDataset(name=a_dataset.name, dataset_type=DatasetType("tabular"))]
            )

    async def test_raises_on_conflicting_dataset_format(
        self, repository: SQLAlchemyRepository, a_dataset
    ):

        repository.options.STRICT_SCENARIO_DATASETS = False

        assert a_dataset.dataset_type.format != DatasetFormat.BINARY
        with pytest.raises(MoviciValidationError, match="incompatible dataset already exists"):
            await repository.datasets.ensure_scenario_datasets(
                [
                    ScenarioDataset(
                        name=a_dataset.name,
                        dataset_type=dataclasses.replace(
                            a_dataset.dataset_type, format=DatasetFormat.BINARY
                        ),
                    )
                ]
            )

    async def test_validates_max_length_in_ensure_scenario_datasets(
        self, repository: SQLAlchemyRepository, a_dataset_type
    ):
        repository.options.STRICT_SCENARIO_DATASETS = False
        with pytest.raises(MoviciValidationError) as e:
            await repository.datasets.ensure_scenario_datasets(
                [ScenarioDataset(name="a" * 51, dataset_type=a_dataset_type)]
            )

        assert set(m[0] for m in e.value.iter_messages()) == {"name", "display_name"}

    async def test_update_with_data(self, repository: SQLAlchemyRepository, a_dataset):
        await repository.datasets.update(
            a_dataset.id,
            dataclasses.replace(
                a_dataset,
                general={"enum": {"label": ["a", "b"]}},
                epsg_code=1234,
                bounding_box=BoundingBox(1.0, 2.0, 3.0, 4.0),
                data=dataset_data_to_numpy(
                    {
                        "transport_nodes": {
                            "id": [1, 2, 3],
                            "labels": {"data": [0, 0, 1, 1], "rowptr": [0, 1, 3, 4]},
                        },
                    }
                ),
            ),
        )
        result = await repository.datasets.get_by_id(a_dataset.id)
        assert result is not None
        assert result.epsg_code == 1234
        assert result.bounding_box == BoundingBox(1.0, 2.0, 3.0, 4.0)
        assert result.general == {"enum": {"label": ["a", "b"]}}
        data = await repository.dataset_data.get_entity_data(a_dataset.id)
        assert dataset_dicts_equal(
            data,
            {
                "transport_nodes": {
                    "id": {"data": np.array([1, 2, 3])},
                    "labels": {
                        "data": np.array([0, 0, 1, 1]),
                        DEFAULT_ROWPTR_KEY: [0, 1, 3, 4],
                    },
                }
            },
        )

    async def test_create_validates_max_lengths(
        self, repository: SQLAlchemyRepository, a_dataset_type
    ):
        with pytest.raises(MoviciValidationError) as e:
            await repository.datasets.create(
                Dataset(name="a" * 51, display_name="a" * 51, dataset_type=a_dataset_type)
            )

        assert set(m[0] for m in e.value.iter_messages()) == {"name", "display_name"}

    async def test_update_validates_max_lengths(
        self, repository: SQLAlchemyRepository, a_dataset_type
    ):
        id = await repository.datasets.create(
            Dataset(name="a", display_name="a", dataset_type=a_dataset_type)
        )
        with pytest.raises(MoviciValidationError) as e:
            await repository.datasets.update(
                id, Dataset(name="a" * 51, display_name="a" * 51, dataset_type=a_dataset_type)
            )

        assert set(m[0] for m in e.value.iter_messages()) == {"name", "display_name"}

    async def test_cannot_delete_dataset_when_in_use_by_scenario(
        self, repository: SQLAlchemyRepository, a_scenario, a_dataset
    ):

        with pytest.raises(InvalidAction) as e:
            await repository.datasets.delete(a_dataset.id)

        assert e.value.message == "Cannot delete dataset when it is still in use by a scenario"

    async def test_raises_not_found_when_creating_dataset_when_workspace_gets_deleted(
        self, db: SQLAlchemyServer, a_dataset_type, a_workspace
    ):
        b1 = Barrier(2)
        b2 = Barrier(2)

        async def retrieve_workspace_and_create_dataset(
            server: SQLAlchemyServer, workspace_id: uuid.UUID
        ):
            async with server.get_backend() as backend:
                workspace = await backend.workspaces.get(id=workspace_id)
                assert workspace is not None
                await b1.wait()
                await b2.wait()

                await backend.for_workspace(workspace_id).datasets.create(
                    Dataset("a_new_dataset", "some name", dataset_type=a_dataset_type)
                )

        async def delete_workspace(server: SQLAlchemyServer, workspace_id: uuid.UUID):
            async with server.get_backend() as backend:
                await b1.wait()

                await backend.workspaces.delete(workspace_id)
            await b2.wait()

        with pytest.raises(ResourceDoesNotExist) as exc:
            await asyncio.gather(
                retrieve_workspace_and_create_dataset(db, workspace_id=a_workspace.id),
                delete_workspace(db, workspace_id=a_workspace.id),
            )
        assert exc.value.id == a_workspace.id
        assert exc.value.resource_type == "workspace"


class TestDatasetDataRepository:
    @pytest.mark.parametrize("method", ["path", "bytes", "bytesio"])
    async def test_store_and_retrieve_raw_data_bytes(
        self, repository: SQLAlchemyRepository, a_dataset, method, tmp_path
    ):
        assert not await repository.dataset_data.exists_for(a_dataset.id)
        raw_bytes = b"somethingbinarydata"
        data = None
        if method == "path":
            data = tmp_path / "data.bin"
            data.write_bytes(raw_bytes)
        elif method == "bytes":
            data = raw_bytes
        elif method == "bytesio":
            data = BytesIO(raw_bytes)
        assert data is not None

        await repository.dataset_data.create(
            a_dataset.id, data, format=DatasetFormat.BINARY, chunk_size=2
        )
        assert await repository.dataset_data.exists_for(a_dataset.id)
        result = b""
        n_chunks = 0

        gen = await repository.dataset_data.stream_binary_data(a_dataset.id)
        async for chunk in gen:
            result += chunk
            n_chunks += 1
        assert n_chunks == len(raw_bytes) // 2 + 1
        assert result == raw_bytes

    async def test_store_and_retrieve_unstructured_data(
        self, repository: SQLAlchemyRepository, a_dataset
    ):
        assert not await repository.dataset_data.exists_for(a_dataset.id)
        data = {"some": "data"}
        await repository.dataset_data.create(a_dataset.id, data, format=DatasetFormat.UNSTRUCTURED)
        assert await repository.dataset_data.exists_for(a_dataset.id)
        result = await repository.dataset_data.get_unstructured_data(a_dataset.id)
        assert result == data

    async def test_store_and_retrieve_entity_data(
        self,
        repository: SQLAlchemyRepository,
        a_dataset,
        an_entity_type,
        an_attribute_type,
        a_csr_attribute_type,
    ):
        assert not await repository.dataset_data.exists_for(a_dataset.id)
        data = {
            an_entity_type.name: {
                an_attribute_type.name: {
                    "data": np.array([1.0, 2.0]),
                },
                a_csr_attribute_type.name: {
                    "data": np.array([1.0, 2.0]),
                    "indptr": np.array([0, 2, 2]),
                },
            }
        }
        await repository.dataset_data.create(a_dataset.id, data, format=DatasetFormat.ENTITY_BASED)
        assert await repository.dataset_data.exists_for(a_dataset.id)
        result = await repository.dataset_data.get_entity_data(a_dataset.id)
        assert_dataset_dicts_equal(data, result)

    async def test_store_multiple_entity_data_retrieve_one(
        self,
        repository: SQLAlchemyRepository,
        a_dataset,
        an_entity_type,
        an_attribute_type,
        a_csr_attribute_type,
    ):
        another_dataset = Dataset("another_dataset", "Another Dataset", a_dataset.dataset_type)

        another_dataset_id = await repository.datasets.create(another_dataset)
        data = {
            an_entity_type.name: {
                an_attribute_type.name: {
                    "data": np.array([1.0, 2.0]),
                }
            }
        }
        await repository.dataset_data.create(
            another_dataset_id,
            {
                an_entity_type.name: {
                    a_csr_attribute_type.name: {
                        "data": np.array([1.0, 2.0]),
                        "indptr": np.array([0, 2, 2]),
                    },
                }
            },
            format=DatasetFormat.ENTITY_BASED,
        )
        await repository.dataset_data.create(a_dataset.id, data, format=DatasetFormat.ENTITY_BASED)
        result = await repository.dataset_data.get_entity_data(a_dataset.id)
        assert_dataset_dicts_equal(data, result)

    @pytest.mark.parametrize(
        "datatype, values, min_val, max_val",
        [
            (bool, [False, False], False, False),
            (bool, [True, False], False, True),
            (int, [2, -1], -1, 2),
            (float, [0.0, np.nan], 0.0, 0.0),
            (float, [np.nan], None, None),
            (float, [], None, None),
            (str, ["a", "b"], None, None),
        ],
    )
    async def test_stores_min_max(
        self,
        repository: SQLAlchemyRepository,
        datatype,
        values,
        min_val,
        max_val,
        a_dataset,
        an_entity_type,
    ):
        await repository.attribute_types.create(AttributeType("some.attr", DataType(datatype)))

        await repository.dataset_data.create(
            a_dataset.id,
            {an_entity_type.name: {"some.attr": {"data": np.asarray(values, dtype=datatype)}}},
            format=DatasetFormat.ENTITY_BASED,
        )
        attribute = await repository.session.scalar(
            select(db.Attribute)
            .options(joinedload(db.Attribute.data))
            .join(db.DatasetAttribute)
            .where(db.DatasetAttribute.dataset_id == a_dataset.id)
            .limit(1)
        )
        assert attribute is not None
        assert attribute.data.min_val == min_val
        assert attribute.data.max_val == max_val

    @pytest.mark.parametrize(
        "unit_shape, values, length",
        [
            ((), [1, 2, 3], 3),
            ((2,), [[1, 2], [2, 3], [3, 4], [4, 5]], 4),
        ],
    )
    async def test_stores_attribute_length(
        self,
        repository: SQLAlchemyRepository,
        a_dataset,
        an_entity_type,
        unit_shape,
        values,
        length,
    ):
        await repository.attribute_types.create(
            AttributeType("some.attr", DataType(int, unit_shape=unit_shape))
        )

        await repository.dataset_data.create(
            a_dataset.id,
            {an_entity_type.name: {"some.attr": {"data": np.asarray(values)}}},
            format=DatasetFormat.ENTITY_BASED,
        )

        attribute = await repository.session.scalar(
            select(db.Attribute)
            .join(db.DatasetAttribute)
            .where(db.DatasetAttribute.dataset_id == a_dataset.id)
            .limit(1)
        )
        assert attribute is not None
        assert attribute.length == length

    async def test_deletes_entity_data(
        self, repository: SQLAlchemyRepository, a_dataset, an_entity_type, an_attribute_type
    ):
        data = {
            an_entity_type.name: {
                an_attribute_type.name: {
                    "data": np.array([1.0, 2.0]),
                }
            }
        }
        await repository.dataset_data.create(a_dataset.id, data, format=DatasetFormat.ENTITY_BASED)
        attribute_count = await repository.session.scalar(select(func.count(db.Attribute.id)))
        assert attribute_count != 0

        await repository.dataset_data.delete(a_dataset.id)

        attribute_count = await repository.session.scalar(select(func.count(db.Attribute.id)))
        assert attribute_count == 0

    async def test_deletes_raw_data(self, repository: SQLAlchemyRepository, a_dataset):
        raw_bytes = b"somethingbinarydata"

        await repository.dataset_data.create(a_dataset.id, raw_bytes, format=DatasetFormat.BINARY)
        data_count = await repository.session.scalar(select(func.count(db.RawData.id)))
        assert data_count != 0

        await repository.dataset_data.delete(a_dataset.id)

        data_count = await repository.session.scalar(select(func.count(db.RawData.id)))
        assert data_count == 0

    async def test_get_dataset_summary(self, repository: SQLAlchemyRepository, a_dataset):
        await repository.datasets.update(
            a_dataset.id,
            dataclasses.replace(
                a_dataset,
                general={"enum": {"label": ["a", "b"]}},
                epsg_code=1234,
                bounding_box=BoundingBox(1.0, 2.0, 3.0, 4.0),
                data=dataset_data_to_numpy(
                    {
                        "transport_nodes": {
                            "id": [1, 2, 3],
                            "labels": {"data": [0, 0, 1, 1], "rowptr": [0, 1, 3, 4]},
                            "geometry.x": [4.0, 5.0, 6.0],
                            "geometry.y": [4.0, 5.0, 6.0],
                        },
                        "roads": {
                            "id": [4, 5, 6, 7],
                            "transport.capacity": [12.0, 13.0, 14.0, 15.0],
                        },
                    }
                ),
            ),
        )

        summary = await repository.datasets.get_summary(a_dataset.id)
        assert summary == DatasetSummary(
            general={"enum": {"label": ["a", "b"]}},
            epsg_code=1234,
            bounding_box=BoundingBox(1.0, 2.0, 3.0, 4.0),
            count=7,
            entity_groups=[
                EntityGroupSummary(
                    name="roads",
                    count=4,
                    attributes=[
                        AttributeSummary(
                            name="id",
                            data_type=DataType(int),
                            description="Entity ID",
                            enum_name=None,
                            unit="",
                            min_val=4,
                            max_val=7,
                        ),
                        AttributeSummary(
                            name="transport.capacity",
                            data_type=DataType(float),
                            description="",
                            enum_name=None,
                            unit="",
                            min_val=12,
                            max_val=15,
                        ),
                    ],
                ),
                EntityGroupSummary(
                    name="transport_nodes",
                    count=3,
                    attributes=[
                        AttributeSummary(
                            name="geometry.x",
                            data_type=DataType(float),
                            description="",
                            enum_name=None,
                            unit="m",
                            min_val=4,
                            max_val=6,
                        ),
                        AttributeSummary(
                            name="geometry.y",
                            data_type=DataType(float),
                            description="",
                            enum_name=None,
                            unit="m",
                            min_val=4,
                            max_val=6,
                        ),
                        AttributeSummary(
                            name="id",
                            data_type=DataType(int),
                            description="Entity ID",
                            enum_name=None,
                            unit="",
                            min_val=1,
                            max_val=3,
                        ),
                        AttributeSummary(
                            name="labels",
                            data_type=DataType(int, csr=True),
                            description="",
                            enum_name="label",
                            unit="",
                            min_val=0,
                            max_val=1,
                        ),
                    ],
                ),
            ],
        )

    async def test_raises_not_found_when_creating_scenario_when_workspace_gets_deleted(
        self, db: SQLAlchemyServer, a_scenario, a_workspace
    ):
        b1 = Barrier(2)
        b2 = Barrier(2)

        async def retrieve_workspace_and_create_scenario(
            server: SQLAlchemyServer, workspace_id: uuid.UUID
        ):
            async with server.get_backend() as backend:
                workspace = await backend.workspaces.get(id=workspace_id)
                assert workspace is not None
                await b1.wait()
                await b2.wait()

                await backend.for_workspace(workspace_id).scenarios.create(
                    Scenario("a_new_scenario", "some name", "descripton"),
                    ModelConfigValidator(),
                )

        async def delete_workspace(server: SQLAlchemyServer, workspace_id: uuid.UUID):
            async with server.get_backend() as backend:
                await b1.wait()

                await backend.workspaces.delete(workspace_id)
            await b2.wait()

        with pytest.raises(ResourceDoesNotExist) as exc:
            await asyncio.gather(
                retrieve_workspace_and_create_scenario(db, workspace_id=a_workspace.id),
                delete_workspace(db, workspace_id=a_workspace.id),
            )
        assert exc.value.id == a_workspace.id
        assert exc.value.resource_type == "workspace"


class TestScenarioRepository:
    @pytest.fixture
    def new_scenario(self, a_dataset, default_model_types):
        return Scenario(
            name="some_scenario",
            workspace=a_dataset.workspace,
            display_name="Some Scenario",
            description="Scenario for testing",
            epsg_code=28992,
            simulation_info=SimulationInfo.default(),
            datasets=[ScenarioDataset.from_dataset(a_dataset)],
            models=[
                ScenarioModel(
                    name="model1",
                    type=default_model_types[0],
                    config={
                        "dataset": a_dataset.name,
                        "entity_group": "transport_nodes",
                        "attribute": "id",
                    },
                ),
                ScenarioModel(
                    name="model2",
                    type=default_model_types[1],
                    config={"field": "value"},
                ),
            ],
        )

    async def test_for_id_changes_scenario_id(self, repository: SQLAlchemyRepository):
        new_id = uuid.uuid4()
        assert repository.scenarios.for_id(new_id).scenario_id == new_id

    async def test_cannot_change_scenario_id_in_single_scenario_mode(
        self, repository: SQLAlchemyRepository, a_scenario
    ):

        assert a_scenario.id is not None
        repository = repository.for_scenario(a_scenario.id)
        repository.options.mode = db.DatabaseMode.SINGLE_SCENARIO

        new_id = uuid.uuid4()
        with pytest.raises(InvalidAction):
            assert repository.scenarios.for_id(new_id)

    async def test_change_scenario_id_to_current_id_in_single_scenario_mode(
        self, repository: SQLAlchemyRepository, a_scenario
    ):
        assert a_scenario.id is not None
        repository = repository.for_scenario(a_scenario.id)
        repository.options.mode = db.DatabaseMode.SINGLE_SCENARIO

        assert repository.scenarios.for_id(a_scenario.id).scenario_id == a_scenario.id

    async def test_list_scenarios_with_updates(
        self,
        repository: SQLAlchemyRepository,
        a_scenario,
        new_scenario,
        get_model_config_validator,
        create_update,
    ):
        validator = await get_model_config_validator()
        await repository.scenarios.create(new_scenario, validator)
        await create_update(
            timestamp=0,
            iteration=0,
            data={"transport_nodes": {"id": [1, 3], "transport.capacity": [13.0, 14.0]}},
        )
        scenarios = await repository.scenarios.list()

        has_updates = {scenario.name: scenario.has_updates for scenario in scenarios}

        assert has_updates == {a_scenario.name: True, new_scenario.name: False}

    async def test_scenario_round_trip(
        self,
        repository: SQLAlchemyRepository,
        new_scenario,
        a_dataset,
        get_model_config_validator,
    ):
        validator = await get_model_config_validator()

        scenario_id = await repository.scenarios.create(new_scenario, validator)
        result = await repository.scenarios.for_id(scenario_id).get()
        assert result is not None

        assert result.id is not None
        assert result.created_at is not None
        assert result.updated_at is not None
        assert result.datasets[0].id == a_dataset.id
        assert [model.as_dict() for model in result.models] == [
            model.as_dict() for model in new_scenario.models
        ]
        assert dataclasses.replace(
            result,
            id=None,
            created_at=None,
            updated_at=None,
            datasets=[dataclasses.replace(result.datasets[0], id=None)],
            models=[],
        ) == dataclasses.replace(new_scenario, models=[])

    async def test_get_scenario_with_updates(
        self, repository: SQLAlchemyRepository, a_scenario, create_update
    ):
        scenario = await repository.scenarios.for_id(a_scenario.id).get()
        assert scenario is not None
        assert not scenario.has_updates

        await create_update(
            timestamp=0,
            iteration=0,
            data={"transport_nodes": {"id": [1, 3], "transport.capacity": [13.0, 14.0]}},
        )
        scenario = await repository.scenarios.for_id(a_scenario.id).get()
        assert scenario is not None
        assert scenario.has_updates

    async def test_create_scenario_with_no_models_and_datasets(
        self, repository: SQLAlchemyRepository, get_model_config_validator
    ):
        scenario_id = await repository.scenarios.create(
            Scenario(
                name="a_scenario",
                display_name="a scenario",
                description="",
                epsg_code=0,
            ),
            validator=await get_model_config_validator(),
        )
        assert scenario_id is not None

    async def test_raises_on_duplicate_datasets_on_create(
        self, repository: SQLAlchemyRepository, get_model_config_validator, a_dataset
    ):
        with pytest.raises(MoviciValidationError) as exc:
            await repository.scenarios.create(
                Scenario(
                    name="a_scenario",
                    display_name="a scenario",
                    description="",
                    epsg_code=0,
                    datasets=[
                        ScenarioDataset.from_dataset(a_dataset),
                        ScenarioDataset.from_dataset(a_dataset),
                    ],
                ),
                validator=await get_model_config_validator(),
            )
        assert list(exc.value.iter_messages()) == [("datasets.1", "duplicate dataset in scenario")]

    async def test_raises_on_duplicate_model_name_on_create(
        self,
        repository: SQLAlchemyRepository,
        get_model_config_validator,
        a_dataset,
        default_model_types,
    ):
        with pytest.raises(MoviciValidationError) as exc:
            await repository.scenarios.create(
                Scenario(
                    name="a_scenario",
                    display_name="a scenario",
                    description="",
                    epsg_code=0,
                    models=[
                        ScenarioModel("name", default_model_types[1], config={"field": "value"}),
                        ScenarioModel("name", default_model_types[1], config={"field": "value"}),
                    ],
                ),
                validator=await get_model_config_validator(),
            )
        assert list(exc.value.iter_messages()) == [
            ("models.1", "duplicate model name in scenario")
        ]

    async def test_get_scenario_by_name(self, repository: SQLAlchemyRepository, a_scenario):
        result = await repository.scenarios.get_by_name(a_scenario.name)
        assert result is not None

    async def test_get_scenario_by_name_with_updates(
        self, repository: SQLAlchemyRepository, a_scenario, create_update
    ):
        scenario = await repository.scenarios.get_by_name(a_scenario.name)
        assert scenario is not None
        assert not scenario.has_updates

        await create_update(
            timestamp=0,
            iteration=0,
            data={"transport_nodes": {"id": [1, 3], "transport.capacity": [13.0, 14.0]}},
        )
        scenario = await repository.scenarios.get_by_name(a_scenario.name)
        assert scenario is not None
        assert scenario.has_updates

    async def test_scenario_exists(
        self, repository: SQLAlchemyRepository, new_scenario, get_model_config_validator
    ):
        assert not await repository.scenarios.exists_by_name(new_scenario.name)

        validator = await get_model_config_validator()
        await repository.scenarios.create(new_scenario, validator)

        assert await repository.scenarios.exists_by_name(new_scenario.name)

    async def test_update_scenario(
        self, repository: SQLAlchemyRepository, a_scenario: Scenario, get_model_config_validator
    ):

        validator = await get_model_config_validator()

        assert a_scenario is not None
        assert a_scenario.id is not None

        a_scenario.name = "new_name"
        a_scenario.models = list(reversed(a_scenario.models))
        await repository.scenarios.for_id(a_scenario.id).update(a_scenario, validator)

        result = await repository.scenarios.for_id(a_scenario.id).get()

        assert result is not None
        assert result.name == a_scenario.name
        assert result.models == a_scenario.models

    async def test_delete_scenario_deletes_scenario_datasets(
        self, repository: SQLAlchemyRepository, a_scenario
    ):
        query = (
            select(func.count())
            .select_from(db.ScenarioDataset)
            .where(db.ScenarioDataset.scenario_id == a_scenario.id)
        )
        assert (await repository.session.scalar(query)) != 0
        await repository.scenarios.for_id(a_scenario.id).delete()
        assert len(await repository.scenarios.list()) == 0
        assert (await repository.session.scalar(query)) == 0

    async def test_delete_scenario_deletes_scenario_models(
        self, repository: SQLAlchemyRepository, a_scenario
    ):
        query = (
            select(func.count())
            .select_from(db.ScenarioModel)
            .where(db.ScenarioModel.scenario_id == a_scenario.id)
        )
        assert (await repository.session.scalar(query)) != 0
        await repository.scenarios.for_id(a_scenario.id).delete()
        await repository.session.commit()
        assert len(await repository.scenarios.list()) == 0
        assert (await repository.session.scalar(query)) == 0

    async def test_delete_scenario_deletes_update_data(
        self, session, repository: SQLAlchemyRepository, create_update, a_scenario
    ):
        base_count = await session.scalar(select(func.count(db.Attribute.id)))
        await create_update(
            timestamp=0,
            iteration=0,
            data={"transport_nodes": {"id": [1, 3], "transport.capacity": [13.0, 14.0]}},
        )
        assert (await session.scalar(select(func.count(db.Attribute.id)))) == base_count + 2

        await repository.scenarios.for_id(a_scenario.id).delete()

        assert (await session.scalar(select(func.count(db.Attribute.id)))) == base_count

    @pytest.mark.database_mode(db.DatabaseMode.SINGLE_SCENARIO)
    async def test_cannot_delete_default_scenario(
        self, repository: SQLAlchemyRepository, a_scenario
    ):
        with pytest.raises(InvalidAction) as e:
            await repository.scenarios.for_id(a_scenario.id).delete()
        assert e.value.message == "Cannot delete default scenario"

    async def test_create_invalid_scenario(
        self, repository: SQLAlchemyRepository, new_scenario: Scenario, get_model_config_validator
    ):
        new_scenario.models[1].config["field"] = 42
        validator = await get_model_config_validator()

        with pytest.raises(MoviciValidationError) as e:
            await repository.scenarios.create(new_scenario, validator)

        path, _ = next(iter(e.value.iter_messages()))
        assert path == "models.1.field"

    async def test_scenario_bounding_box_from_datasets_and_updates(
        self, repository: SQLAlchemyRepository, a_scenario: Scenario, a_dataset
    ):
        repository = repository.for_scenario(t.cast(uuid.UUID, a_scenario.id))
        await repository.datasets.update(
            a_dataset.id,
            dataclasses.replace(a_dataset, bounding_box=BoundingBox(1, 1, 2, 2), data={}),
        )
        update = Update(
            dataset=a_scenario.datasets[0],
            timestamp=0,
            iteration=0,
            model=UpdateModel.from_scenario_model(a_scenario.models[0]),
            data={},
        )
        await repository.updates.create(
            dataclasses.replace(update, iteration=1, bounding_box=BoundingBox(-1, 2, 2, 2))
        )
        await repository.updates.create(
            # update without bounding box
            dataclasses.replace(update, iteration=2)
        )
        await repository.updates.create(
            dataclasses.replace(update, iteration=3, bounding_box=BoundingBox(0, 2, 3, 4))
        )
        scenario_by_id = await repository.scenarios.get()
        assert scenario_by_id is not None
        assert scenario_by_id.bounding_box == BoundingBox(-1, 1, 3, 4)

        scenario_by_name = await repository.scenarios.get_by_name(a_scenario.name)
        assert scenario_by_name is not None
        assert scenario_by_name.bounding_box == BoundingBox(-1, 1, 3, 4)

    async def test_get_scenario_summary(
        self, repository: SQLAlchemyRepository, a_dataset, a_scenario: Scenario, create_update
    ):
        assert a_scenario.id is not None
        await repository.datasets.update(
            a_dataset.id,
            dataclasses.replace(
                a_dataset,
                general={"enum": {"label": ["a", "b"]}},
                epsg_code=1234,
                bounding_box=BoundingBox(1.0, 2.0, 3.0, 4.0),
                data=dataset_data_to_numpy(
                    {
                        "transport_nodes": {
                            "id": [1, 2, 3],
                        },
                        "roads": {
                            "id": [4, 5, 6, 7],
                            "transport.capacity": [12.0, 13.0, 14.0, 15.0],
                        },
                    }
                ),
            ),
        )
        await create_update(
            timestamp=0,
            iteration=0,
            data={"transport_nodes": {"id": [1, 3], "transport.capacity": [13.0, 14.0]}},
        )
        await create_update(
            timestamp=0,
            iteration=1,
            data={"roads": {"id": [4, 5], "transport.capacity": [10.0, 20.0]}},
        )

        assert (
            await repository.scenarios.for_id(a_scenario.id).get_summary(a_dataset.id)
        ) == DatasetSummary(
            general={"enum": {"label": ["a", "b"]}},
            epsg_code=1234,
            bounding_box=BoundingBox(1.0, 2.0, 3.0, 4.0),
            count=7,
            entity_groups=[
                EntityGroupSummary(
                    name="roads",
                    count=4,
                    attributes=[
                        AttributeSummary(
                            name="id",
                            data_type=DataType(int),
                            description="Entity ID",
                            enum_name=None,
                            unit="",
                            min_val=4,
                            max_val=7,
                        ),
                        AttributeSummary(
                            name="transport.capacity",
                            data_type=DataType(float),
                            description="",
                            enum_name=None,
                            unit="",
                            min_val=10,
                            max_val=20,
                        ),
                    ],
                ),
                EntityGroupSummary(
                    name="transport_nodes",
                    count=3,
                    attributes=[
                        AttributeSummary(
                            name="id",
                            data_type=DataType(int),
                            description="Entity ID",
                            enum_name=None,
                            unit="",
                            min_val=1,
                            max_val=3,
                        ),
                        AttributeSummary(
                            name="transport.capacity",
                            data_type=DataType(float),
                            description="",
                            enum_name=None,
                            unit="",
                            min_val=13,
                            max_val=14,
                        ),
                    ],
                ),
            ],
        )

    async def test_get_scenario_summary_with_str_type(
        self, repository: SQLAlchemyRepository, a_dataset, a_scenario: Scenario, create_update
    ):
        assert a_scenario.id is not None
        await repository.datasets.update(
            a_dataset.id,
            dataclasses.replace(
                a_dataset,
                data=dataset_data_to_numpy(
                    {
                        "transport_nodes": {
                            "id": [1, 2, 3],
                            "text": ["a", "b"],
                        },
                    }
                ),
            ),
        )
        await create_update(
            timestamp=0,
            iteration=0,
            data={
                "transport_nodes": {
                    "id": [1, 2],
                    "text": ["c", "c"],
                },
            },
        )

        assert (
            await repository.scenarios.for_id(a_scenario.id).get_summary(a_dataset.id)
        ) == DatasetSummary(
            general={},
            epsg_code=None,
            bounding_box=BoundingBox.empty(),
            count=3,
            entity_groups=[
                EntityGroupSummary(
                    name="transport_nodes",
                    count=3,
                    attributes=[
                        AttributeSummary(
                            name="id",
                            data_type=DataType(int),
                            description="Entity ID",
                            enum_name=None,
                            unit="",
                            min_val=1,
                            max_val=3,
                        ),
                        AttributeSummary(
                            name="text",
                            data_type=DataType(str),
                            description="",
                            enum_name=None,
                            unit="",
                            min_val=None,
                            max_val=None,
                        ),
                    ],
                ),
            ],
        )

    async def test_doesnt_return_summary_for_other_dataset(
        self,
        repository: SQLAlchemyRepository,
        a_dataset,
        a_scenario,
        a_dataset_type,
        get_model_config_validator,
    ):
        another_dataset = Dataset(
            name="another_dataset",
            display_name="another dataset",
            dataset_type=a_dataset_type,
            data=dataset_data_to_numpy({"roads": {"id": [10, 11]}}),
        )
        another_dataset_id = await repository.datasets.create(another_dataset)
        repository = repository.for_scenario(a_scenario.id)
        await repository.datasets.update(another_dataset_id, another_dataset)
        await repository.scenarios.update(
            dataclasses.replace(
                a_scenario,
                datasets=[
                    ScenarioDataset(a_dataset.name, a_dataset.dataset_type),
                    ScenarioDataset(another_dataset.name, another_dataset.dataset_type),
                ],
            ),
            validator=await get_model_config_validator(),
        )

        summary = await repository.scenarios.get_summary(a_dataset.id)
        assert "roads" not in {eg.name for eg in summary.entity_groups}

    async def test_doesnt_return_summary_for_other_scenario(
        self,
        repository: SQLAlchemyRepository,
        a_dataset,
        a_scenario,
        get_model_config_validator,
        an_entity_type,
        create_update,
    ):
        another_scenario_id = await repository.scenarios.create(
            dataclasses.replace(a_scenario, name="another_scenario"),
            await get_model_config_validator(),
        )
        await repository.dataset_data.create(
            a_dataset.id,
            dataset_data_to_numpy({an_entity_type.name: {"id": [10, 20]}}),
            format=DatasetFormat.ENTITY_BASED,
        )
        await create_update(
            timestamp=0,
            iteration=0,
            data={an_entity_type.name: {"id": [10, 11], "topology.from_node_id": [2, 2]}},
            dataset=a_dataset,
            scenario_id=a_scenario.id,
        )
        await create_update(
            timestamp=0,
            iteration=0,
            data={an_entity_type.name: {"id": [10, 11], "transport.capacity": [1.0, 1.0]}},
            dataset=a_dataset,
            scenario_id=another_scenario_id,
        )

        summary = await repository.for_scenario(a_scenario.id).scenarios.get_summary(a_dataset.id)
        eg_summary = summary.entity_groups[0]
        assert eg_summary.name == an_entity_type.name
        assert {attr.name for attr in eg_summary.attributes} == {"id", "topology.from_node_id"}

    async def test_create_validates_max_lengths(
        self, repository: SQLAlchemyRepository, new_scenario, get_model_config_validator
    ):
        validator = await get_model_config_validator()

        with pytest.raises(MoviciValidationError) as e:
            await repository.scenarios.create(
                dataclasses.replace(
                    new_scenario, name="a" * 51, display_name="a" * 51, description="a" * 501
                ),
                validator,
            )

        assert set(m[0] for m in e.value.iter_messages()) == {
            "name",
            "display_name",
            "description",
        }

    async def test_update_validates_max_lengths(
        self, repository: SQLAlchemyRepository, new_scenario, get_model_config_validator
    ):
        validator = await get_model_config_validator()
        scenario_id = await repository.scenarios.create(new_scenario, validator)

        with pytest.raises(MoviciValidationError) as e:
            await repository.scenarios.for_id(scenario_id).update(
                dataclasses.replace(
                    new_scenario, name="a" * 51, display_name="a" * 51, description="a" * 501
                ),
                validator,
            )

        assert set(m[0] for m in e.value.iter_messages()) == {
            "name",
            "display_name",
            "description",
        }

    async def test_raises_not_found_when_creating_dataset_when_workspace_gets_deleted(
        self, db: SQLAlchemyServer, a_dataset_type, a_workspace
    ):
        b1 = Barrier(2)
        b2 = Barrier(2)

        async def retrieve_workspace_and_create_dataset(
            server: SQLAlchemyServer, workspace_id: uuid.UUID
        ):
            async with server.get_backend() as backend:
                workspace = await backend.workspaces.get(id=workspace_id)
                assert workspace is not None
                await b1.wait()
                await b2.wait()

                await backend.for_workspace(workspace_id).datasets.create(
                    Dataset("a_new_dataset", "some name", dataset_type=a_dataset_type)
                )

        async def delete_workspace(server: SQLAlchemyServer, workspace_id: uuid.UUID):
            async with server.get_backend() as backend:
                await b1.wait()

                await backend.workspaces.delete(workspace_id)
            await b2.wait()

        with pytest.raises(ResourceDoesNotExist) as exc:
            await asyncio.gather(
                retrieve_workspace_and_create_dataset(db, workspace_id=a_workspace.id),
                delete_workspace(db, workspace_id=a_workspace.id),
            )
        assert exc.value.id == a_workspace.id
        assert exc.value.resource_type == "workspace"


class TestUpdateRepository:
    @pytest.fixture
    def repository(self, repository: SQLAlchemyRepository, a_scenario):
        return repository.for_scenario(a_scenario.id)

    async def test_update_round_trip(
        self,
        a_scenario,
        a_dataset,
        an_entity_type,
        an_attribute_type,
        repository: SQLAlchemyRepository,
    ):
        update = Update(
            dataset=ScenarioDataset(a_dataset.name, a_dataset.dataset_type),
            timestamp=12,
            iteration=2,
            model=UpdateModel.from_scenario_model(a_scenario.models[0]),
            data={
                an_entity_type.name: {
                    "id": {"data": np.asarray([0, 1])},
                    an_attribute_type.name: {"data": np.asarray([1.0, 2.0])},
                }
            },
        )

        update_id = await repository.updates.create(update)

        result = await repository.updates.get_by_id(update_id, with_data=True)
        assert result is not None
        assert result.created_at is not None
        assert dataclasses.replace(update, data=None, id=update_id) == dataclasses.replace(
            result, data=None, created_at=None
        )
        assert_dataset_dicts_equal(update.data, result.data)

    async def test_updates_exist(self, create_update, repository: SQLAlchemyRepository):
        assert not await repository.updates.exists()
        await create_update(timestamp=1, iteration=0, ids=[0, 1], array=[1.0, 2.0])

        assert await repository.updates.exists()

    async def test_gets_all_updates_in_order(
        self, create_update, repository: SQLAlchemyRepository
    ):
        update1 = await create_update(timestamp=1, iteration=0, ids=[0, 1], array=[1.0, 2.0])
        update4 = await create_update(timestamp=6, iteration=1, ids=[0, 1], array=[2.0, 3.0])
        update2 = await create_update(timestamp=2, iteration=1, ids=[0, 1], array=[2.0, 3.0])
        update3 = await create_update(timestamp=2, iteration=2, ids=[0, 1], array=[2.0, 3.0])
        all_updates = await repository.updates.list()
        assert [upd.id for upd in all_updates] == [update1, update2, update3, update4]

    async def test_doesnt_return_updates_for_different_scenario(
        self,
        a_scenario,
        create_scenario,
        repository: SQLAlchemyRepository,
        create_update,
    ):

        another_scenario_id = await create_scenario(
            dataclasses.replace(a_scenario, name="another_scenario")
        )
        await create_update(timestamp=6, iteration=1, ids=[0, 1], array=[2.0, 3.0])
        updates = await repository.updates.list()
        assert len(updates) == 1

        other_updates = await repository.for_scenario(another_scenario_id).updates.list()
        assert len(other_updates) == 0

    async def test_deletes_all_updates_for_scenario_but_not_others(
        self,
        a_scenario,
        create_update,
        repository: SQLAlchemyRepository,
        create_scenario,
    ):
        another_scenario_id = await create_scenario(
            dataclasses.replace(a_scenario, name="another_scenario")
        )
        await create_update(timestamp=6, iteration=1, ids=[0, 1], array=[2.0, 3.0])
        await create_update(timestamp=2, iteration=1, ids=[0, 1], array=[2.0, 3.0])
        await create_update(timestamp=2, iteration=2, ids=[0, 1], array=[2.0, 3.0])
        await create_update(
            scenario_id=another_scenario_id, timestamp=1, iteration=0, ids=[0, 1], array=[1.0, 2.0]
        )

        assert len(await repository.updates.list()) == 3
        assert len(await repository.for_scenario(another_scenario_id).updates.list()) == 1

        await repository.updates.delete_all()

        assert len(await repository.updates.list()) == 0
        assert len(await repository.for_scenario(another_scenario_id).updates.list()) == 1

    async def test_deletes_all_underlying_data(
        self,
        a_scenario,
        create_update,
        repository: SQLAlchemyRepository,
        create_scenario,
        session,
    ):

        another_scenario_id = await create_scenario(
            dataclasses.replace(a_scenario, name="another_scenario")
        )
        await create_update(timestamp=6, iteration=1, ids=[0, 1], array=[2.0, 3.0])
        await create_update(timestamp=2, iteration=1, ids=[0, 1], array=[2.0, 3.0])
        await create_update(timestamp=2, iteration=2, ids=[0, 1], array=[2.0, 3.0])
        await create_update(
            scenario_id=another_scenario_id, timestamp=1, iteration=0, ids=[0, 1], array=[1.0, 2.0]
        )

        assert (await session.scalar(select(func.count(db.DataArray.id)))) == 8

        await repository.updates.delete_all()

        assert (await session.scalar(select(func.count(db.DataArray.id)))) == 2

    async def test_cannot_create_duplicate_update(self, create_update):
        await create_update(timestamp=0, iteration=1, ids=[0, 1], array=[2.0, 3.0])

        with pytest.raises(ResourceAlreadyExists) as e:
            await create_update(timestamp=0, iteration=1, ids=[0, 1], array=[2.0, 3.0])
        assert e.value.name == "t0_1"

    async def test_raises_validation_error_for_incorrect_scenario_model(
        self, repository: SQLAlchemyRepository, a_scenario
    ):

        with pytest.raises(MoviciValidationError) as exc:
            await repository.updates.create(
                Update(
                    a_scenario.datasets[0],
                    0,
                    0,
                    UpdateModel("invalid"),
                    data={},
                )
            )
        assert exc.value.path == "model.name"

    async def test_raises_not_found_when_scenario_gets_deleted_during_update(
        self, db: SQLAlchemyServer, a_scenario: Scenario
    ):
        assert a_scenario.id is not None
        b1 = Barrier(2)
        b2 = Barrier(2)

        async def retrieve_scenario_and_create_update(
            server: SQLAlchemyServer, scenario_id: uuid.UUID
        ):
            async with server.get_backend() as backend:
                scenario = await backend.scenarios.get(id=scenario_id)
                assert scenario is not None
                await b1.wait()
                await b2.wait()

                await backend.for_scenario(scenario_id).repository.updates.create(
                    Update(
                        a_scenario.datasets[0],
                        0,
                        0,
                        UpdateModel.from_scenario_model(a_scenario.models[0]),
                        data={},
                    )
                )

        async def delete_scenario(server: SQLAlchemyServer, scenario_id: uuid.UUID):
            async with server.get_backend() as backend:
                await b1.wait()

                await backend.for_scenario(scenario_id).scenarios.delete()
            await b2.wait()

        with pytest.raises(ResourceDoesNotExist) as exc:
            await asyncio.gather(
                retrieve_scenario_and_create_update(db, scenario_id=a_scenario.id),
                delete_scenario(db, scenario_id=a_scenario.id),
            )
        assert exc.value.resource_type == "scenario"
        assert exc.value.id == a_scenario.id
