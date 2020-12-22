# flake8: noqa
# There's no way to ignore "F401 '...' imported but unused" warnings in this
# module, but to preserve other warnings. So, don't check this module at all.

# Copyright 2020 The HuggingFace Team. All rights reserved.
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
from ...file_utils import is_tf_available, is_tokenizers_available

from .configuration_muril import MURIL_PRETRAINED_CONFIG_ARCHIVE_MAP, MuRILConfig
from .tokenization_muril import MuRILTokenizer

if is_tokenizers_available():
    from .tokenization_muril_fast import MuRILTokenizerFast
if is_tf_available():
    from .modeling_tf_muril import (
        TF_MURIL_PRETRAINED_MODEL_ARCHIVE_LIST,
        TFMuRILForMaskedLM,
        TFMuRILForCausalLM,
        TFMuRILForMultipleChoice,
        TFMuRILForQuestionAnswering,
        TFMuRILForSequenceClassification,
        TFMuRILForTokenClassification,
        TFMuRILLayer,
        TFMuRILModel,
        TFMuRILPreTrainedModel,
    )
