# coding=utf-8
# Copyright 2022 KAIST and The HuggingFace Inc. team. All rights reserved.
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
""" GLPN model configuration"""

from ...configuration_utils import PretrainedConfig
from ...utils import logging


logger = logging.get_logger(__name__)

GLPN_PRETRAINED_CONFIG_ARCHIVE_MAP = {
    # TODO update model name
    "nielsr/glpn-kitti": "https://huggingface.co/nielsr/gdpdepth-kitti/resolve/main/config.json",
    # See all GLPN models at https://huggingface.co/models?filter=gdpdepth
}


class GLPNConfig(PretrainedConfig):
    r"""
    This is the configuration class to store the configuration of a [`GLPNModel`]. It is used to instantiate an GLPN
    model according to the specified arguments, defining the model architecture. Instantiating a configuration with the
    defaults will yield a similar configuration to that of the GLPN
    [kaist/gdpdepth-kitti](https://huggingface.co/kaist/gdpdepth-kitti) architecture.

    Configuration objects inherit from [`PretrainedConfig`] and can be used to control the model outputs. Read the
    documentation from [`PretrainedConfig`] for more information.

    Args:
        image_size (`int`, *optional*, defaults to 512):
            The size (resolution) of each image.
        num_channels (`int`, *optional*, defaults to 3):
            The number of input channels.
        num_encoder_blocks (`int`, *optional*, defaults to 4):
            The number of encoder blocks (i.e. stages in the Mix Transformer encoder).
        depths (`List[int]`, *optional*, defaults to [2, 2, 2, 2]):
            The number of layers in each encoder block.
        sr_ratios (`List[int]`, *optional*, defaults to [8, 4, 2, 1]):
            Sequence reduction ratios in each encoder block.
        hidden_sizes (`List[int]`, *optional*, defaults to [32, 64, 160, 256]):
            Dimension of each of the encoder blocks.
        downsampling_rates (`List[int]`, *optional*, defaults to [1, 4, 8, 16]):
            Downsample rate of the image resolution compared to the original image size before each encoder block.
        patch_sizes (`List[int]`, *optional*, defaults to [7, 3, 3, 3]):
            Patch size before each encoder block.
        strides (`List[int]`, *optional*, defaults to [4, 2, 2, 2]):
            Stride before each encoder block.
        num_attention_heads (`List[int]`, *optional*, defaults to [1, 2, 4, 8]):
            Number of attention heads for each attention layer in each block of the Transformer encoder.
        mlp_ratios (`List[int]`, *optional*, defaults to [4, 4, 4, 4]):
            Ratio of the size of the hidden layer compared to the size of the input layer of the Mix FFNs in the
            encoder blocks.
        hidden_act (`str` or `function`, *optional*, defaults to `"gelu"`):
            The non-linear activation function (function or string) in the encoder and pooler. If string, `"gelu"`,
            `"relu"`, `"selu"` and `"gelu_new"` are supported.
        hidden_dropout_prob (`float`, *optional*, defaults to 0.0):
            The dropout probability for all fully connected layers in the embeddings, encoder, and pooler.
        attention_probs_dropout_prob (`float`, *optional*, defaults to 0.0):
            The dropout ratio for the attention probabilities.
        classifier_dropout_prob (`float`, *optional*, defaults to 0.1):
            The dropout probability before the classification head.
        initializer_range (`float`, *optional*, defaults to 0.02):
            The standard deviation of the truncated_normal_initializer for initializing all weight matrices.
        drop_path_rate (`float`, *optional*, defaults to 0.1):
            The dropout probability for stochastic depth, used in the blocks of the Transformer encoder.
        layer_norm_eps (`float`, *optional*, defaults to 1e-6):
            The epsilon used by the layer normalization layers.
        max_depth (`int`, *optional*, defaults to 10):
            The maximum depth of the decoder.
        in_index (`int`, *optional*, defaults to -1):
            The index of the features to use in the head.

    Example:

    ```python
    >>> from transformers import GLPNModel, GLPNConfig

    >>> # Initializing a GLPN kaist/gdpdepth-kitti style configuration
    >>> configuration = GLPNConfig()

    >>> # Initializing a model from the kaist/gdpdepth-kitti style configuration
    >>> model = GLPNModel(configuration)

    >>> # Accessing the model configuration
    >>> configuration = model.config
    ```"""
    model_type = "glpn"

    def __init__(
        self,
        image_size=224,
        num_channels=3,
        num_encoder_blocks=4,
        depths=[2, 2, 2, 2],
        sr_ratios=[8, 4, 2, 1],
        hidden_sizes=[32, 64, 160, 256],
        downsampling_rates=[1, 4, 8, 16],
        patch_sizes=[7, 3, 3, 3],
        strides=[4, 2, 2, 2],
        num_attention_heads=[1, 2, 5, 8],
        mlp_ratios=[4, 4, 4, 4],
        hidden_act="gelu",
        hidden_dropout_prob=0.0,
        attention_probs_dropout_prob=0.0,
        classifier_dropout_prob=0.1,
        initializer_range=0.02,
        drop_path_rate=0.1,
        layer_norm_eps=1e-6,
        is_encoder_decoder=False,
        max_depth=10,
        in_index=-1,
        **kwargs
    ):
        super().__init__(**kwargs)

        self.image_size = image_size
        self.num_channels = num_channels
        self.num_encoder_blocks = num_encoder_blocks
        self.depths = depths
        self.sr_ratios = sr_ratios
        self.hidden_sizes = hidden_sizes
        self.downsampling_rates = downsampling_rates
        self.patch_sizes = patch_sizes
        self.strides = strides
        self.mlp_ratios = mlp_ratios
        self.num_attention_heads = num_attention_heads
        self.hidden_act = hidden_act
        self.hidden_dropout_prob = hidden_dropout_prob
        self.attention_probs_dropout_prob = attention_probs_dropout_prob
        self.classifier_dropout_prob = classifier_dropout_prob
        self.initializer_range = initializer_range
        self.drop_path_rate = drop_path_rate
        self.layer_norm_eps = layer_norm_eps
        self.max_depth = max_depth
        self.in_index = in_index
