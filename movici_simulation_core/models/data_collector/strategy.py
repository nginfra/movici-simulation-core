from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from movici_simulation_core.settings import Settings

if TYPE_CHECKING:
    from movici_simulation_core.models.data_collector.data_collector import (
        DataCollector,
        UpdateInfo,
    )


class StorageStrategy:
    @classmethod
    def choose(
        cls, model_config: dict, settings: Settings, logger: logging.Logger
    ) -> StorageStrategy:
        raise NotImplementedError

    def initialize(self):
        pass

    def store(self, info: UpdateInfo):
        raise NotImplementedError

    def reset_iterations(self, model: DataCollector):
        pass
