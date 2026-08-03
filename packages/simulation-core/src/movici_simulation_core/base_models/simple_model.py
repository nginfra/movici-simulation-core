from __future__ import annotations

import logging
import typing as t

from movici_simulation_core.core import AttributeSchema, Model, Moment
from movici_simulation_core.core.types import ModelAdapterBase
from movici_simulation_core.messages import (
    NewTimeMessage,
    QuitMessage,
    UpdateMessage,
    UpdateSeriesMessage,
)
from movici_simulation_core.model_connector import InitDataHandler
from movici_simulation_core.postprocessing import merge_updates
from movici_simulation_core.settings import Settings
from movici_simulation_core.types import (
    DataMask,
    Result,
    Timestamp,
    UpdateData,
)

from .common import EntityAwareInitDataHandler


class SimpleModelAdapter(ModelAdapterBase):
    model: SimpleModel
    schema: AttributeSchema = None

    def __init__(self, model: Model, settings: Settings, logger: logging.Logger):
        super().__init__(model, settings, logger)

    def initialize(self, init_data_handler: InitDataHandler) -> DataMask:
        init_data_handler = EntityAwareInitDataHandler(init_data_handler)

        return self.model.initialize(
            settings=self.settings,
            schema=self.schema,
            init_data_handler=init_data_handler,
            logger=self.logger,
        )

    def new_time(self, message: NewTimeMessage):
        self.model.new_time(new_time=Moment(message.timestamp), message=message)

    def update(self, message: UpdateMessage, data: UpdateData) -> Result:
        result = self.model.update(moment=Moment(message.timestamp), data=data, message=message)
        return self.process_result(result)

    def update_series(self, message: UpdateSeriesMessage, data: t.Iterable[UpdateData]) -> Result:
        result = self.model.update_series(Moment(message.timestamp), data, message=message)
        return self.process_result(result)

    def process_result(
        self, result: t.Tuple[UpdateData, t.Union[Moment, Timestamp, None]]
    ) -> Result:
        data, next_time = result
        if isinstance(next_time, Moment):
            next_time = next_time.timestamp
        return data, next_time

    def close(self, message: QuitMessage):
        self.model.close(message=message)

    def set_schema(self, schema):
        self.schema = schema


class SimpleModel(Model):
    def initialize(
        self,
        settings: Settings,
        schema: AttributeSchema,
        init_data_handler: InitDataHandler,
        logger: logging.Logger,
    ) -> DataMask:
        raise NotImplementedError

    def update(
        self, moment: Moment, data: UpdateData, message: UpdateMessage
    ) -> t.Tuple[UpdateData, t.Optional[Moment]]:
        raise NotImplementedError

    def update_series(
        self, moment: Moment, data: t.Iterable[UpdateData], message: UpdateSeriesMessage
    ) -> t.Tuple[UpdateData, t.Optional[Moment]]:
        output = (self.update(moment, upd, msg) for upd, msg in zip(data, message.updates))

        # to go from ((moment, data), (moment, data), ...) to ((moment, moment), (data, data))
        # we use this zip trick to transpose the output
        results, moments = zip(*output)

        if len(moments) == 0:
            return None, None

        merged = merge_updates(*(result for result in results if result is not None))

        return merged, moments[-1]

    def new_time(self, new_time: Moment, message: NewTimeMessage):
        pass

    def close(self, message: QuitMessage):
        pass

    def get_adapter(self) -> t.Type[ModelAdapterBase]:
        return SimpleModelAdapter
