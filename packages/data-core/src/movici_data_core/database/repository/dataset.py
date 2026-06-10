from __future__ import annotations

import dataclasses
import typing as t
from uuid import UUID

import sqlalchemy.exc
from sqlalchemy import (
    ColumnElement,
    Insert,
    Select,
    delete,
    exists,
    insert,
    select,
    update,
)
from sqlalchemy.orm import joinedload

from movici_data_core.database import model as db
from movici_data_core.domain_model import (
    AttributeSummary,
    Dataset,
    DatasetData,
    DatasetFormat,
    DatasetSummary,
    DatasetType,
    EntityGroupSummary,
    ScenarioDataset,
)
from movici_data_core.exceptions import (
    InvalidAction,
    InvalidResource,
    MoviciValidationError,
    ResourceAlreadyExists,
    ResourceDoesNotExist,
    map_errors,
)

from .common import (
    EntityDataProcessor,
    EntityDataSelector,
    RawDataProcessor,
    SQLResourceRepository,
)


@dataclasses.dataclass
class DatasetRepository(SQLResourceRepository):
    workspace_id: UUID | None = None

    def _ensure_workspace_id(self) -> UUID:
        if self.workspace_id is None:
            raise ValueError("DatasetRepository.workspace_id is required")
        return self.workspace_id

    @property
    def selector(self):
        workspace_id = self._ensure_workspace_id()
        return (
            select(db.Dataset)
            .where(db.Dataset.workspace_id == workspace_id)
            .options(joinedload(db.Dataset.workspace), joinedload(db.Dataset.dataset_type))
        )

    @property
    def selector_with_has_data(self):
        return select(
            db.Dataset,
            exists().where(db.RawData.dataset_id == db.Dataset.id),
            exists().where(db.DatasetAttribute.dataset_id == db.Dataset.id),
        ).options(joinedload(db.Dataset.workspace), joinedload(db.Dataset.dataset_type))

    async def exists(self, name: str):
        """return whether the dataset (by name) already exists in the database for the acitve
        workspace.

        :param name: dataset name
        :return: a boolean indicating the dataset exists for the active workspace
        """
        workspace_id = self._ensure_workspace_id()
        return await self._exists(db.Dataset.workspace_id == workspace_id, db.Dataset.name == name)

    async def list(self) -> list[Dataset]:
        workspace_id = self._ensure_workspace_id()
        rows = await self.session.execute(
            self.selector_with_has_data.where(db.Dataset.workspace_id == workspace_id)
        )

        return [
            ds.to_domain(has_data_raw, has_attributes) for ds, has_data_raw, has_attributes in rows
        ]

    async def get_by_name(self, name: str) -> Dataset | None:
        workspace_id = self._ensure_workspace_id()
        return await self._get_one_with_has_data(
            (db.Dataset.workspace_id == workspace_id) & (db.Dataset.name == name)
        )

    async def get_by_id(self, id: UUID) -> Dataset | None:
        return await self._get_one_with_has_data(db.Dataset.id == id)

    async def _get_one_with_has_data(self, where_clause: ColumnElement[bool]):
        result = (
            await self.session.execute(self.selector_with_has_data.where(where_clause).limit(1))
        ).first()

        if result is None:
            return None
        ds, has_raw_data, has_attributes = result
        return ds.to_domain(has_raw_data, has_attributes)

    async def delete(self, id: UUID):
        await self.all_data.dataset_data.delete(id)
        await self.session.execute(delete(db.Dataset).where(db.Dataset.id == id))

    async def get_summary(self, id: UUID):
        """Request a DatasetSummary for the dataset id

        :param id: the dataset id
        :return: A ``DatasetSummary``
        """
        dataset = await self.get_by_id(id)
        if dataset is None:
            raise ResourceDoesNotExist("dataset", id=id)

        entity_groups: dict[str, EntityGroupSummary] = {}
        attribute: db.Attribute
        for attribute, min_val, max_val in await self.session.execute(
            select(db.Attribute, db.DataArray.min_val, db.DataArray.max_val)
            .join(db.DataArray, db.DataArray.attribute_id == db.Attribute.id)
            .join(db.DatasetAttribute)
            .options(
                joinedload(db.Attribute.attribute_type),
                joinedload(db.Attribute.entity_type),
            )
            .where(db.DatasetAttribute.dataset_id == id)
        ):
            attribute_type = attribute.attribute_type
            entity_group_name = attribute.entity_type.name
            entity_group = entity_groups.setdefault(
                entity_group_name, EntityGroupSummary(entity_group_name, 0, [])
            )

            if attribute.attribute_type.name == "id":
                entity_group.count = max(entity_group.count, attribute.length)
            entity_group.attributes.append(
                AttributeSummary(
                    name=attribute_type.name,
                    data_type=attribute_type.data_type,
                    description=attribute_type.description,
                    unit=attribute_type.unit,
                    enum_name=attribute_type.enum_name,
                    min_val=min_val,
                    max_val=max_val,
                )
            )

        return DatasetSummary(
            general=dataset.general or {},
            epsg_code=dataset.epsg_code,
            bounding_box=dataset.bounding_box,
            entity_groups=sorted(
                (
                    dataclasses.replace(eg, attributes=sorted(eg.attributes, key=lambda a: a.name))
                    for eg in entity_groups.values()
                ),
                key=lambda eg: eg.name,
            ),
            count=sum(e.count for e in entity_groups.values()),
        )

    @map_errors(
        {
            sqlalchemy.exc.IntegrityError: lambda obj: ResourceAlreadyExists(
                "dataset", name=obj.name
            )
        }
    )
    async def create(self, obj: Dataset) -> UUID:
        workspace_id = self._ensure_workspace_id()
        dataset_type = await self.all_data.dataset_types.ensure_dataset_type(obj.dataset_type)
        return t.cast(
            UUID,
            await self.session.scalar(
                insert(db.Dataset)
                .values(
                    workspace_id=workspace_id,
                    name=obj.name,
                    display_name=obj.display_name,
                    dataset_type_id=t.cast(UUID, dataset_type.id),
                )
                .returning(db.Dataset.id)
            ),
        )

    async def update(self, id: UUID, obj: Dataset, chunk_size=0):
        """Update a dataset when providing a full dataset with data, processes all fields, except
        the data section, which must be processed separately using the
        :class:`DatasetDataRepository`.

        :param id: the UUID of the stored ``Dataset``
        :param obj: the ``Dataset`` object with the changes
        :param chunk_size: the chunk size in bytes when storing unstructured or binary data. When
            set to 0, the default, the chunk size is set to
            :attr:`RawDataProcessor.RAW_DATA_CHUNK_SIZE`
        """
        current = await self.get_by_id(id)
        if current is None:
            raise ResourceDoesNotExist("dataset", id=id)

        # TODO: accept changes to dataset type if the dataset does not have data and is not used
        #  anywhere?
        payload: dict[str, t.Any] = dict(name=obj.name, display_name=obj.display_name)
        if obj.data is not None:
            if not current.dataset_type.is_equivalent(obj.dataset_type):
                raise InvalidAction("Cannot change dataset type when updating data")
            payload.update(
                dict(
                    name=obj.name,
                    display_name=obj.display_name,
                    general=obj.general,
                    epsg_code=obj.epsg_code,
                    bounding_box=obj.bounding_box.as_tuple_or_none(),
                )
            )

            await self.all_data.dataset_data.delete(id, prune_dataset=False)
            await self.all_data.dataset_data.create(
                id,
                data=obj.data,
                format=t.cast(DatasetFormat, current.dataset_type.format),
                chunk_size=chunk_size,
            )

        await self.session.execute(update(db.Dataset).where(db.Dataset.id == id).values(**payload))

    async def ensure_scenario_datasets(
        self, datasets: t.Sequence[ScenarioDataset]
    ) -> t.List[ScenarioDataset]:
        r"""Ensure that the :class:`Dataset`s of a sequences of :class:`ScenarioDataset`\s exist in
        the database or raise an error. If one or more of the ``Dataset``s do not exist and the
        database option ``STRICT_SCENARIO_DATASETS`` is unset, the non-existing datasets will be
        created as a stub. If any of the newly created datasets has a dataset type that does not
        yet exist, then the ``STRICT_DATASET_TYPES`` database option must also be unset. Otherwise
        an error will be raise.  An error is also raised if a ``Dataset`` already exists but with a
        different dataset type.

        :param datasets: The ``ScenarioDataset``s to ensure
        :return: The datasets as they exist in the database, as ``ScenarioDataset`` objects, in
            the same order as the input sequence
        """
        workspace_id = self._ensure_workspace_id()
        existing_datasets = {
            ds.name: ScenarioDataset(ds.name, dataset_type=ds.dataset_type.to_domain(), id=ds.id)
            for ds in await self.session.scalars(
                self.selector.where(
                    db.Dataset.name.in_(ds.name for ds in datasets),
                )
            )
        }
        existing_types = None  # delay retrieving existing dataset types, we might not need them
        to_create: list[ScenarioDataset] = []
        for idx, scenario_dataset in enumerate(datasets):
            name = scenario_dataset.name
            if name not in existing_datasets:
                if self.options.STRICT_SCENARIO_DATASETS:
                    raise MoviciValidationError(f"dataset '{name}' does not exist", path=idx)
                if scenario_dataset.dataset_type is None:
                    raise MoviciValidationError(
                        "cannot create new dataset when dataset type is unknown", path=idx
                    )

                if existing_types is None:
                    existing_types = {
                        tp.name: tp for tp in await self.all_data.dataset_types.list()
                    }

                if (
                    scenario_dataset.dataset_type.name not in existing_types
                    and self.options.STRICT_DATASET_TYPES
                ):
                    raise MoviciValidationError(
                        {
                            "type": [
                                f"dataset type '{scenario_dataset.dataset_type}' does not exist"
                            ]
                        },
                        path=idx,
                    )
                to_create.append(scenario_dataset)
                continue

            existing = existing_datasets[name]
            if not (
                scenario_dataset.dataset_type is None
                or t.cast(DatasetType, existing.dataset_type).is_equivalent(
                    scenario_dataset.dataset_type
                )
            ):
                raise MoviciValidationError("incompatible dataset already exists", path=idx)

            if scenario_dataset.dataset_type is None:
                scenario_dataset.dataset_type = existing.dataset_type

        if to_create:
            # to_create will only have entries after we have checked a dataset's dataset type and
            # have retrieved ``existing_types`` so we can make the following assertion
            assert existing_types is not None
            for scenario_dataset in to_create:
                # A ScenarioDataset can only be added to to_create if it has a dataset_type
                assert scenario_dataset.dataset_type is not None
                if scenario_dataset.dataset_type.name not in existing_types:
                    ds_type = scenario_dataset.dataset_type
                    new_type = await self.all_data.dataset_types.ensure_dataset_type(
                        dataclasses.replace(
                            ds_type, format=ds_type.format or DatasetFormat.ENTITY_BASED
                        )
                    )
                    existing_types[new_type.name] = new_type

            created_ids = await self.session.scalars(
                insert(db.Dataset).returning(db.Dataset.id),
                [
                    {
                        "name": ds.name,
                        "display_name": ds.name,
                        "dataset_type_id": existing_types[
                            t.cast(DatasetType, ds.dataset_type).name
                        ].id,
                        "workspace_id": workspace_id,
                    }
                    for ds in to_create
                ],
            )

            existing_datasets.update(
                (
                    ds.name,
                    ScenarioDataset(
                        ds.name,
                        dataset_type=existing_types[t.cast(DatasetType, ds.dataset_type).name],
                        id=id,
                    ),
                )
                for id, ds in zip(created_ids, to_create)
            )

        return [existing_datasets[ds.name] for ds in datasets]


class DatasetDataRepository(SQLResourceRepository):
    async def exists_for(self, id: UUID):
        """
        :param id: a dataset id
        :return: a boolean wether the dataset has data (either entity data or raw data)
        """
        raw_data_exists = await self._exists(db.RawData.dataset_id == id)
        entity_data_exists = await self._exists(db.DatasetAttribute.dataset_id == id)
        return raw_data_exists or entity_data_exists

    async def stream_binary_data(self, id: UUID, yield_per=1) -> t.AsyncGenerator[bytes]:
        """
        :param id: the dataset ``UUID``
        :param yield_per: an optimzation parameter for the database to request n chunks at a time.
            Default: 1

        :return: An async generator that can be iterated over (async for loop) to produce
            chunks of binary data. The chunk size is determined by the data stored in the database
            and is :attr:`RawDataProcessor.RAW_DATA_CHUNK_SIZE` by default
        """
        _, generator = await RawDataProcessor(self.session).stream_bytes(id, yield_per=yield_per)
        return generator

    async def get_unstructured_data(self, id: UUID) -> dict:
        """return the dataset data for an ``UNSTRUCTURED`` dataset

        :param id: the dataset ``UUID``
        :return: The unstructured dataset data section
        """
        return await RawDataProcessor(self.session).get_dict(id)

    async def get_entity_data(self, id: UUID):
        """return the dataset data for an ``ENTITY_BASED`` dataset

        :param id: the dataset ``UUID``
        :return: The entity based dataset data section
        """
        return await EntityDataProcessor(
            self.session, all_data=self.all_data, selector=DatasetDataSelector()
        ).get(id)

    async def create(self, id: UUID, data: DatasetData, format: DatasetFormat, chunk_size=0):
        """Store dataset data for a dataset. The dataset must currently not contain any data

        :param id: A dataset id
        :param data: The dataset data as dict, bytes, BytesIO or pathlib.Path
        :param format: The dataset's ``DatasetFormat``
        :param chunk_size: The maximum chunk size in bytes to store data. By default set to the
            value of DatasetRepository.RAW_DATA_CHUNK_SIZE. This parameter is ignore when the
            dataset format is DatasetFormat.ENTITY_BASED
        """

        if await self.exists_for(id):
            raise InvalidResource("dataset", id=id, message="Dataset already has data")

        if format == DatasetFormat.ENTITY_BASED:
            if not isinstance(data, dict):
                raise ValueError("Entity based data must be provided as a dictionary")
            await EntityDataProcessor(
                self.session, self.all_data, selector=DatasetDataSelector()
            ).store(id, data)

        if format == DatasetFormat.UNSTRUCTURED:
            await RawDataProcessor(self.session).store(id, data, chunk_size=chunk_size)

        if format == DatasetFormat.BINARY:
            await RawDataProcessor(self.session).store(id, data, chunk_size=chunk_size)

    async def delete(self, id: UUID, prune_dataset=True):
        await self.session.execute(
            delete(db.Attribute).where(
                db.Attribute.id.in_(
                    select(db.DatasetAttribute.attribute_id).where(
                        db.DatasetAttribute.dataset_id == id
                    )
                )
            )
        )
        await self.session.execute(delete(db.RawData).where(db.RawData.dataset_id == id))
        if prune_dataset:
            await self.session.execute(
                update(db.Dataset)
                .where(db.Dataset.id == id)
                .values(general=None, epsg_code=None, bounding_box=None)
            )


class DatasetDataSelector(EntityDataSelector):
    def select_linked_attribute(self, id: UUID) -> Select[tuple[db.Attribute]]:
        return (
            select(db.Attribute)
            .join(db.DatasetAttribute)
            .where(db.DatasetAttribute.dataset_id == id)
        )

    def insert_linked_attribute(self, id: UUID, attribute_id: UUID) -> Insert:
        return insert(db.DatasetAttribute).values(dataset_id=id, attribute_id=attribute_id)
