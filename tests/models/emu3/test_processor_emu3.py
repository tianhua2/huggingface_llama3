# coding=utf-8
# Copyright 2024 The HuggingFace Inc. team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Testing suite for the PyTorch emu3 model."""

import tempfile
import unittest

from transformers import Emu3Processor, Emu3Tokenizer
from transformers.testing_utils import get_tests_dir
from transformers.utils import is_vision_available

from ...test_processing_common import ProcessorTesterMixin


if is_vision_available():
    from transformers import Emu3ImageProcessor


SAMPLE_VOCAB = get_tests_dir("fixtures/test_sentencepiece.model")


class Emu3ProcessorTest(ProcessorTesterMixin, unittest.TestCase):
    processor_class = Emu3Processor

    def setUp(self):
        self.tmpdirname = tempfile.mkdtemp()
        image_processor = Emu3ImageProcessor()
        tokenizer = Emu3Tokenizer(vocab_file=SAMPLE_VOCAB)
        tokenizer.pad_token_id = 0
        tokenizer.sep_token_id = 1
        processor = self.processor_class(image_processor=image_processor, tokenizer=tokenizer)
        processor.save_pretrained(self.tmpdirname)
