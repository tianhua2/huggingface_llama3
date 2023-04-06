# This file is autogenerated by the command `make fix-copies`, do not edit.
from ..utils import DummyObject, requires_backends


class TFBertTokenizer(metaclass=DummyObject):
    _backends = ["tensorflow_text"]

    def __init__(self, *args, **kwargs):
        requires_backends(self, ["tensorflow_text"])


class TFPoNetTokenizer(metaclass=DummyObject):
    _backends = ["tensorflow_text"]

    def __init__(self, *args, **kwargs):
        requires_backends(self, ["tensorflow_text"])
