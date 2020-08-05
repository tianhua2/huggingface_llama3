import os
import unittest
from distutils.util import strtobool

from .file_utils import _tf_available, _torch_available, _torch_tpu_available


SMALL_MODEL_IDENTIFIER = "julien-c/bert-xsmall-dummy"
DUMMY_UNKWOWN_IDENTIFIER = "julien-c/dummy-unknown"
# Used to test Auto{Config, Model, Tokenizer} model_type detection.


def parse_flag_from_env(key, default=False):
    try:
        value = os.environ[key]
    except KeyError:
        # KEY isn't set, default to `default`.
        _value = default
    else:
        # KEY is set, convert it to True or False.
        try:
            _value = strtobool(value)
        except ValueError:
            # More values are supported, but let's keep the message simple.
            raise ValueError("If set, {} must be yes or no.".format(key))
    return _value


def parse_int_from_env(key, default=None):
    try:
        value = os.environ[key]
    except KeyError:
        _value = default
    else:
        try:
            _value = int(value)
        except ValueError:
            raise ValueError("If set, {} must be a int.".format(key))
    return _value


_run_slow_tests = parse_flag_from_env("RUN_SLOW", default=False)
_run_custom_tokenizers = parse_flag_from_env("RUN_CUSTOM_TOKENIZERS", default=False)
_tf_gpu_memory_limit = parse_int_from_env("TF_GPU_MEMORY_LIMIT", default=None)


def slow(test_case):
    """
    Decorator marking a test as slow.

    Slow tests are skipped by default. Set the RUN_SLOW environment variable
    to a truthy value to run them.

    """
    if not _run_slow_tests:
        test_case = unittest.skip("test is slow")(test_case)
    return test_case


def custom_tokenizers(test_case):
    """
    Decorator marking a test for a custom tokenizer.

    Custom tokenizers require additional dependencies, and are skipped
    by default. Set the RUN_CUSTOM_TOKENIZERS environment variable
    to a truthy value to run them.
    """
    if not _run_custom_tokenizers:
        test_case = unittest.skip("test of custom tokenizers")(test_case)
    return test_case


def require_torch(test_case):
    """
    Decorator marking a test that requires PyTorch.

    These tests are skipped when PyTorch isn't installed.

    """
    if not _torch_available:
        test_case = unittest.skip("test requires PyTorch")(test_case)
    return test_case


def require_tf(test_case):
    """
    Decorator marking a test that requires TensorFlow.

    These tests are skipped when TensorFlow isn't installed.

    """
    if not _tf_available:
        test_case = unittest.skip("test requires TensorFlow")(test_case)
    return test_case


def require_multigpu(test_case):
    """
    Decorator marking a test that requires a multi-GPU setup (in PyTorch).

    These tests are skipped on a machine without multiple GPUs.

    To run *only* the multigpu tests, assuming all test names contain multigpu:
    $ pytest -sv ./tests -k "multigpu"
    """
    if not _torch_available:
        return unittest.skip("test requires PyTorch")(test_case)

    import torch

    if torch.cuda.device_count() < 2:
        return unittest.skip("test requires multiple GPUs")(test_case)
    return test_case


def require_torch_tpu(test_case):
    """
    Decorator marking a test that requires a TPU (in PyTorch).
    """
    if not _torch_tpu_available:
        return unittest.skip("test requires PyTorch TPU")

    return test_case


if _torch_available:
    # Set the USE_CUDA environment variable to select a GPU.
    torch_device = "cuda" if parse_flag_from_env("USE_CUDA") else "cpu"
else:
    torch_device = None


def require_torch_and_cuda(test_case):
    """Decorator marking a test that requires CUDA and PyTorch). """
    if torch_device != "cuda":
        return unittest.skip("test requires CUDA")
    else:
        return test_case


class DictAttr:
    """This is a wrapper class that turns a plain dict into an object-like dict
    that allows key access via a method.

    For example:
    data = {
        "loss_1": 1,
        "mems_1": 2,
    }
    result = DictAttr(data)

    now the values can be accessed as a subscription or a an accessor:

    print(result["loss_1"]) # 1
    print(result.loss_1)    # 1

    """

    def __init__(self, args):
        for k in args:
            setattr(self, k, args[k])

    def __getitem__(self, item):
        return getattr(self, item)
