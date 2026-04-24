import pytest
from movici_data_core.exceptions import SerializationError, UnsupportedFileType
from movici_data_core.serialization import dump_dict, load_dict

from movici_simulation_core.types import FileType


def test_serialize_and_deserialize_json():
    data = {"some": "data"}
    assert load_dict(dump_dict(data, FileType.JSON), filetype=FileType.JSON)


def test_serialize_and_deserialize_mspack():
    data = {"some": "data"}
    assert load_dict(dump_dict(data, FileType.MSGPACK), filetype=FileType.MSGPACK)


def test_raises_on_unsupported_filetype_on_load():
    with pytest.raises(UnsupportedFileType):
        load_dict(b"123", filetype=FileType.NETCDF)


def test_raises_on_unsupported_filetype_on_dump():
    with pytest.raises(UnsupportedFileType):
        dump_dict({"some": "data"}, filetype=FileType.NETCDF)


@pytest.mark.parametrize("filetype", [FileType.JSON, FileType.MSGPACK])
def test_raises_on_invalid_data(filetype):
    with pytest.raises(SerializationError):
        load_dict(b"{invalid}", filetype=filetype)
