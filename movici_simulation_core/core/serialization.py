import msgpack
import numpy as np

from ..types import InternalSerializationStrategy


class UpdateDataFormat(InternalSerializationStrategy):
    CURRENT_VERSION = 1

    def loads(self, raw_bytes: bytes):
        return msgpack.unpackb(raw_bytes, object_hook=self.decode_numpy_array)

    def dumps(self, data: dict):
        return msgpack.packb(data, default=self.encode_numpy_array)

    @classmethod
    def decode_numpy_array(cls, obj):
        ver = obj.get("__np_encode_version__", None)
        if ver is None:
            return obj
        if ver == 1:
            return np.frombuffer(obj["data"], dtype=obj["dtype"]).reshape(obj["shape"]).copy()
        raise TypeError("Unsupported Numpy encoding version")

    @classmethod
    def encode_numpy_array(cls, obj):
        if isinstance(obj, np.ndarray):
            return {
                "__np_encode_version__": cls.CURRENT_VERSION,
                "dtype": obj.dtype.str,
                "shape": obj.shape,
                "data": obj.tobytes(),
            }
        return obj


def load_update(raw_bytes: bytes):
    return UpdateDataFormat().loads(raw_bytes)


def dump_update(data: dict):
    return UpdateDataFormat().dumps(data)
