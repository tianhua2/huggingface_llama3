# coding=utf-8
# Copyright 2022 The HuggingFace Inc. team. All rights reserved.
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
""" Whisper model configuration"""

from ...configuration_utils import PretrainedConfig
from ...utils import logging


logger = logging.get_logger(__name__)

WHISPER_PRETRAINED_CONFIG_ARCHIVE_MAP = {
    "openai/whisper-base": "https://huggingface.co/openai/whisper-base/resolve/main/config.json",
}

# fmt: off
NON_SPEECH_TOKENS = [
    1, 2, 6, 7, 8, 9, 10, 12, 14, 25,
    26, 27, 28, 29, 31, 58, 59, 60, 61, 62,
    63, 90, 91, 92, 93, 359, 503, 522, 542, 873,
    893, 902, 918, 922, 931, 1350, 1853, 1982, 2460, 2627,
    3246, 3253, 3268, 3536, 3846, 3961, 4183, 4667, 6585, 6647,
    7273, 9061, 9383, 10428, 10929, 11938, 12033, 12331, 12562, 13793,
    14157, 14635, 15265, 15618, 16553, 16604, 18362, 18956, 20075, 21675,
    22520, 26130, 26161, 26435, 28279, 29464, 31650, 32302, 32470, 36865,
    42863, 47425, 49870, 50254
]
# fmt: on


class WhisperConfig(PretrainedConfig):
    r"""
    This is the configuration class to store the configuration of a [`WhisperModel`]. It is used to instantiate an
    Whisper model according to the specified arguments, defining the model architecture. Instantiating a configuration
    with the defaults will yield a similar configuration to that of the Whisper
    [openai/whisper-base](https://huggingface.co/openai/whisper-base) architecture.

    Configuration objects inherit from [`PretrainedConfig`] and can be used to control the model outputs. Read the
    documentation from [`PretrainedConfig`] for more information.


    Args:
        vocab_size (`int`, *optional*, defaults to 50265):
            Vocabulary size of the Whisper model. Defines the number of different tokens that can be represented by the
            `inputs_ids` passed when calling [`WhisperModel`]
        d_model (`int`, *optional*, defaults to 1024):
            Dimensionality of the layers and the pooler layer.
        encoder_layers (`int`, *optional*, defaults to 12):
            Number of encoder layers.
        decoder_layers (`int`, *optional*, defaults to 12):
            Number of decoder layers.
        encoder_attention_heads (`int`, *optional*, defaults to 16):
            Number of attention heads for each attention layer in the Transformer encoder.
        decoder_attention_heads (`int`, *optional*, defaults to 16):
            Number of attention heads for each attention layer in the Transformer decoder.
        decoder_ffn_dim (`int`, *optional*, defaults to 4096):
            Dimensionality of the "intermediate" (often named feed-forward) layer in decoder.
        encoder_ffn_dim (`int`, *optional*, defaults to 4096):
            Dimensionality of the "intermediate" (often named feed-forward) layer in decoder.
        activation_function (`str` or `function`, *optional*, defaults to `"gelu"`):
            The non-linear activation function (function or string) in the encoder and pooler. If string, `"gelu"`,
            `"relu"`, `"silu"` and `"gelu_new"` are supported.
        dropout (`float`, *optional*, defaults to 0.1):
            The dropout probability for all fully connected layers in the embeddings, encoder, and pooler.
        attention_dropout (`float`, *optional*, defaults to 0.0):
            The dropout ratio for the attention probabilities.
        activation_dropout (`float`, *optional*, defaults to 0.0):
            The dropout ratio for activations inside the fully connected layer.
        classifier_dropout (`float`, *optional*, defaults to 0.0):
            The dropout ratio for classifier.
        init_std (`float`, *optional*, defaults to 0.02):
            The standard deviation of the truncated_normal_initializer for initializing all weight matrices.
        encoder_layerdrop (`float`, *optional*, defaults to 0.0):
            The LayerDrop probability for the encoder. See the [LayerDrop paper](see https://arxiv.org/abs/1909.11556)
            for more details.
        decoder_layerdrop (`float`, *optional*, defaults to 0.0):
            The LayerDrop probability for the decoder. See the [LayerDrop paper](see https://arxiv.org/abs/1909.11556)
            for more details.
        use_cache (`bool`, *optional*, defaults to `True`):
            Whether or not the model should return the last key/values attentions (not used by all models).
        max_source_positions (`int`, *optional*, defaults to 6000):
            The maximum sequence length of log-mel filter-bank features that this model might ever be used with.
        max_target_positions (`int`, *optional*, defaults to 1024):
            The maximum sequence length that this model might ever be used with. Typically set this to something large
            just in case (e.g., 512 or 1024 or 2048).
        num_conv_layers (`int`, *optional*, defaults to 2):
            Number of 1D convolutional layers in the conv module.
        conv_kernel_sizes (`Tuple[int]`, *optional*, defaults to `(5, 5)`):
            A tuple of integers defining the kernel size of each 1D convolutional layer in the conv module. The length
            of `conv_kernel_sizes` has to match `num_conv_layers`.
        conv_channels (`int`, *optional*, defaults to 1024):
            An integer defining the number of output channels of each convolution layers except the final one in the
            conv module.
        input_feat_per_channel (`int`, *optional*, defaults to 80):
            An integer specifying the size of feature vector. This is also the dimensions of log-mel filter-bank
            features.
        input_channels (`int`, *optional*, defaults to 1):
            An integer specifying number of input channels of the input feature vector.

    Example:

    ```python
    >>> from transformers import WhisperModel, WhisperConfig

    >>> # Initializing a Whisper tiny style configuration
    >>> configuration = WhisperConfig()

    >>> # Initializing a model from the tiny style configuration
    >>> model = WhisperModel(configuration)

    >>> # Accessing the model configuration
    >>> configuration = model.config
    ```"""
    model_type = "whisper"
    keys_to_ignore_at_inference = ["past_key_values"]
    attribute_map = {"num_attention_heads": "encoder_attention_heads", "hidden_size": "d_model"}

    def __init__(
        self,
        vocab_size=51865,
        feature_size=1,
        num_mel_bins=80,
        encoder_layers=6,
        encoder_attention_heads=4,
        decoder_layers=6,
        decoder_attention_heads=4,
        decoder_ffn_dim=1536,
        encoder_ffn_dim=1536,
        encoder_layerdrop=0.0,
        decoder_layerdrop=0.0,
        decoder_start_token_id=[50258, 50259, 50359],
        use_cache=True,
        is_encoder_decoder=True,
        activation_function="gelu",
        d_model=256,
        dropout=0.0,
        attention_dropout=0.0,
        activation_dropout=0.0,
        init_std=0.02,
        scale_embedding=False,
        max_source_positions=1500,
        max_target_positions=448,
        pad_token_id=0,
        bos_token_id=50257,
        eos_token_id=50257,
        input_channels=1,
        tie_word_embeddings=True,
        **kwargs
    ):
        self.vocab_size = vocab_size
        self.num_mel_bins = num_mel_bins
        self.d_model = d_model
        self.encoder_layers = encoder_layers
        self.encoder_attention_heads = encoder_attention_heads
        self.decoder_layers = decoder_layers
        self.decoder_attention_heads = decoder_attention_heads
        self.decoder_ffn_dim = decoder_ffn_dim
        self.encoder_ffn_dim = encoder_ffn_dim
        self.dropout = dropout
        self.attention_dropout = attention_dropout
        self.activation_dropout = activation_dropout
        self.activation_function = activation_function
        self.init_std = init_std
        self.encoder_layerdrop = encoder_layerdrop
        self.decoder_layerdrop = decoder_layerdrop
        self.use_cache = use_cache
        self.num_hidden_layers = encoder_layers
        self.scale_embedding = scale_embedding  # scale factor will be sqrt(d_model) if True
        self.tie_word_embeddings = tie_word_embeddings
        self.input_channels = input_channels
        self.max_source_positions = max_source_positions
        self.max_target_positions = max_target_positions
        self.feature_size = feature_size
        self.non_speech_tokens = NON_SPEECH_TOKENS
        super().__init__(
            pad_token_id=pad_token_id,
            bos_token_id=bos_token_id,
            eos_token_id=eos_token_id,
            is_encoder_decoder=is_encoder_decoder,
            decoder_start_token_id=decoder_start_token_id,
            tie_word_embeddings = tie_word_embeddings,
            **kwargs,
        )
