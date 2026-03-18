from unittest.mock import Mock

from movici_simulation_core.base_models.tracked_model import TrackedModel


class DummyModel(TrackedModel):
    setup = Mock()
    initialize = Mock()
    update = Mock()
    install = Mock()
    shutdown = Mock()
    close = Mock()

    @classmethod
    def reset_mocks(cls):
        for attr in vars(cls).values():
            if isinstance(attr, Mock):
                attr.reset_mock()
