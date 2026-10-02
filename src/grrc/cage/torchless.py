"""Read PyTorch ``.pth`` checkpoints into NumPy without importing torch.

A ``torch.save`` file (zip format, protocol 2+) is a zip archive holding a pickle
(``*/data.pkl``) whose tensors refer to raw little-endian storages (``*/data/<key>``).
This loader resolves those references with a restricted unpickler that only accepts
the handful of globals a plain state dict needs, so it cannot execute arbitrary code.
It is used to run the CAGE Challenge 2 winning agent's small MLPs in NumPy.
"""
from __future__ import annotations

import collections
import pickle
import zipfile

import numpy as np

_DTYPES = {"FloatStorage": np.float32, "DoubleStorage": np.float64, "HalfStorage": np.float16,
           "LongStorage": np.int64, "IntStorage": np.int32, "ByteStorage": np.uint8,
           "BoolStorage": np.bool_}


class _StorageType:
    def __init__(self, name):
        self.name = name


def _rebuild_tensor_v2(storage, offset, size, stride, requires_grad=False, hooks=None,
                       metadata=None):
    if not size:
        return np.array(storage[offset])
    item = storage.itemsize
    return np.lib.stride_tricks.as_strided(storage[offset:], shape=tuple(size),
                                           strides=tuple(s * item for s in stride)).copy()


class _Unpickler(pickle.Unpickler):
    def __init__(self, fh, archive, prefix):
        super().__init__(fh)
        self.archive, self.prefix = archive, prefix

    def find_class(self, module, name):
        if module == "collections" and name == "OrderedDict":
            return collections.OrderedDict
        if module == "torch._utils" and name == "_rebuild_tensor_v2":
            return _rebuild_tensor_v2
        if module == "torch" and name in _DTYPES:
            return _StorageType(name)
        raise pickle.UnpicklingError(f"refusing to load {module}.{name}")

    def persistent_load(self, pid):
        _, storage_type, key, _location, _numel = pid
        dtype = _DTYPES[storage_type.name]
        raw = self.archive.read(f"{self.prefix}/data/{key}")
        return np.frombuffer(raw, dtype=np.dtype(dtype).newbyteorder("<"))


def load_state_dict(path) -> dict:
    """``{parameter name: ndarray}`` from a ``torch.save``-d state dict."""
    with zipfile.ZipFile(path) as archive:
        pkl = next(n for n in archive.namelist() if n.endswith("data.pkl"))
        prefix = pkl[: -len("/data.pkl")]
        with archive.open(pkl) as fh:
            return dict(_Unpickler(fh, archive, prefix).load())
