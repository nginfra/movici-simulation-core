from pathlib import Path

import pytest

from movici_simulation_core.core.priority import Priority
from movici_simulation_core.messages import (
    AcknowledgeMessage,
    ClearDataMessage,
    DataMessage,
    ErrorMessage,
    GetDataMessage,
    NewTimeMessage,
    PathMessage,
    PutDataMessage,
    QuitMessage,
    RegistrationMessage,
    RemapMessage,
    ResultMessage,
    UpdateMessage,
    UpdateSeriesMessage,
    dump_message,
    load_message,
)


@pytest.mark.parametrize(
    "message",
    [
        RegistrationMessage(pub={"a": None}, sub={"b": None}),
        RegistrationMessage(
            pub={"a": None}, sub={"b": None}, priority=int(Priority.SOLVER_HELPER)
        ),
        RemapMessage(),
        RemapMessage(pub={"ds": {"eg": {"speed": "speed:model_a:i"}}}),
        RemapMessage(sub={"ds": {"eg": {"speed:model_a:i": "speed"}}}),
        RemapMessage(
            pub={"ds": {"eg": {"speed": "speed:model_a:i"}}},
            sub={"ds": {"eg": {"a:model_a:i": "a", "a:model_a2:i": "a"}}},
        ),
        UpdateMessage(1, "key", "address"),
        UpdateMessage(1, "key", "address", origin="some_model"),
        UpdateMessage(1, None, None),
        UpdateSeriesMessage(updates=[UpdateMessage(1, None, None), UpdateMessage(1, "a", "b")]),
        ResultMessage("key", "address", next_time=1),
        ResultMessage(None, None, None),
        NewTimeMessage(1),
        AcknowledgeMessage(),
        QuitMessage(),
        QuitMessage(due_to_failure=True),
        GetDataMessage("key", {"some": "filter"}),
        PutDataMessage("key", b"some_data"),
        ClearDataMessage("key"),
        DataMessage(b"some_data"),
        ErrorMessage(),
        PathMessage(path=Path("/some/path")),
        PathMessage(path=None),
    ],
)
def test_serialization_deserialization(message):
    assert message == load_message(*dump_message(message))


def test_dump_update_message():
    assert dump_message(UpdateMessage(1, None, None, origin="some_model")) == [
        b"UPDATE",
        b'{"timestamp": 1, "key": null, "address": null, "origin": "some_model"}',
    ]


def test_dump_update_series():
    assert dump_message(
        UpdateSeriesMessage(
            updates=[
                UpdateMessage(1, None, None),
                UpdateMessage(2, "some_key", "some_address"),
            ]
        )
    ) == [
        b"UPDATE_SERIES",
        b'{"timestamp": 1, "key": null, "address": null, "origin": null}',
        b'{"timestamp": 2, "key": "some_key", "address": "some_address", "origin": null}',
    ]


def test_load_update_series_message():
    assert load_message(
        *[
            b"UPDATE_SERIES",
            b'{"timestamp": 1, "key": null, "address": null, "origin": null}',
            b'{"timestamp": 2, "key": "some_key", "address": "some_address", "origin": null}',
        ]
    ) == UpdateSeriesMessage(
        updates=[
            UpdateMessage(1, None, None),
            UpdateMessage(2, "some_key", "some_address"),
        ]
    )


def test_dump_put_data_message():
    assert dump_message(PutDataMessage("key", b"data")) == [b"PUT", b"key", b"data"]


def test_dump_update_data_message():
    assert dump_message(DataMessage(b"some_data")) == [b"DATA", b"some_data"]


def test_error_on_invalid_message_content():
    with pytest.raises(ValueError):
        ResultMessage(key=None, address="something")


def test_registration_message_rejects_non_int_priority():
    with pytest.raises(TypeError, match="priority must be int"):
        RegistrationMessage(pub=None, sub=None, priority="high")
    with pytest.raises(TypeError, match="priority must be int"):
        RegistrationMessage(pub=None, sub=None, priority=10.5)
    with pytest.raises(TypeError, match="priority must be int"):
        # ``bool`` is a subclass of ``int`` — accepting it would silently let
        # ``priority=True`` register as priority 1.
        RegistrationMessage(pub=None, sub=None, priority=True)


def test_registration_message_rejects_negative_priority():
    with pytest.raises(ValueError, match="non-negative"):
        RegistrationMessage(pub=None, sub=None, priority=-1)


def test_update_series_message_has_no_timestamp_when_emtpy():
    assert UpdateSeriesMessage([]).timestamp is None
