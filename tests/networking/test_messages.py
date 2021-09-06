import pytest

from movici_simulation_core.networking.messages import (
    RegistrationMessage,
    load_message,
    dump_message,
    UpdateMessage,
    UpdateSeriesMessage,
    ResultMessage,
    NewTimeMessage,
    AcknowledgeMessage,
    QuitMessage,
    GetDataMessage,
    PutDataMessage,
    ClearDataMessage,
    DataMessage,
    ErrorMessage,
)


@pytest.mark.parametrize(
    "message",
    [
        RegistrationMessage(pub={"a": None}, sub={"b": None}),
        UpdateMessage(1, "key", "address"),
        UpdateMessage(1, None, None),
        UpdateSeriesMessage(updates=[UpdateMessage(1, None, None), UpdateMessage(1, "a", "b")]),
        ResultMessage("key", "address", next_time=1),
        ResultMessage(None, None, None),
        NewTimeMessage(1),
        AcknowledgeMessage(),
        QuitMessage(),
        GetDataMessage("key", {"some": "filter"}),
        PutDataMessage("key", b"some_data"),
        ClearDataMessage("key"),
        DataMessage(b"some_data"),
        ErrorMessage(),
    ],
)
def test_serialization_deserialization(message):
    assert message == load_message(*dump_message(message))


def test_dump_update_message():
    assert dump_message(UpdateMessage(1, None, None)) == [
        b"UPDATE",
        b'{"timestamp": 1, "key": null, "address": null}',
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
        b'{"timestamp": 1, "key": null, "address": null}',
        b'{"timestamp": 2, "key": "some_key", "address": "some_address"}',
    ]


def test_load_update_series_message():
    assert load_message(
        *[
            b"UPDATE_SERIES",
            b'{"timestamp": 1, "key": null, "address": null}',
            b'{"timestamp": 2, "key": "some_key", "address": "some_address"}',
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


def test_update_series_message_calculates_timestamp_as_maximum_timestamp():
    assert UpdateSeriesMessage([UpdateMessage(1), UpdateMessage(2)]).timestamp == 2


def test_update_series_message_has_no_timestamp_when_emtpy():
    assert UpdateSeriesMessage([]).timestamp is None
