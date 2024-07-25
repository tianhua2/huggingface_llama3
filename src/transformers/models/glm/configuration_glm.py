# coding=utf-8
# Copyright 2024 GLM & ZhipuAI team. All rights reserved.
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

"""GLM model configuration"""

from ...configuration_utils import PretrainedConfig
from ...utils import logging


logger = logging.get_logger(__name__)


class GLMConfig(PretrainedConfig):
    r"""
    This is the configuration class to store the configuration of a [`GLMModel`]. It is used to instantiate a Phi-3
    model according to the specified arguments, defining the model architecture. Instantiating a configuration with the
    defaults will yield a similar configuration to that of the
    [THUDM/glm-4-9b-chat](https://huggingface.co/THUDM/glm-4-9b-chat).

    Configuration objects inherit from [`PretrainedConfig`] and can be used to control the model outputs. Read the
    documentation from [`PretrainedConfig`] for more information.

    Args:
        num_hidden_layers (`int`, *optional*, defaults to 40):
            Number of hidden layers in the Transformer decoder.
        vocab_size (`int`, *optional*, defaults to 151552):
            Vocabulary size of the Phi-3 model. Defines the number of different tokens that can be represented by the
            `inputs_ids` passed when calling [`GLMModel`].
        hidden_size (`int`, *optional*, defaults to 4096):
            Dimension of the hidden representations.
        intermediate_size (`int`, *optional*, defaults to 13696):
            Dimension of the MLP representations.
        kv_channels (`<fill_type>`, *optional*, defaults to 128): <fill_docstring>
        num_attention_heads (`int`, *optional*, defaults to 32):
            Number of attention heads for each attention layer in the Transformer decoder.
        num_key_value_heads (`int`, *optional*, defaults to 32):
            This is the number of key_value heads that should be used to implement Grouped Query Attention. If
            `num_key_value_heads=num_attention_heads`, the model will use Multi Head Attention (MHA), if
            `num_key_value_heads=1` the model will use Multi Query Attention (MQA) otherwise GQA is used. When
            converting a multi-head checkpoint to a GQA checkpoint, each group key and value head should be constructed
            by meanpooling all the original heads within that group. For more details checkout [this
            paper](https://arxiv.org/pdf/2305.13245.pdf). If it is not specified, will default to `32`.
        hidden_act (`<fill_type>`, *optional*, defaults to `"gelu"`): <fill_docstring>
        seq_length (`<fill_type>`, *optional*, defaults to 131072): <fill_docstring>
        hidden_dropout (`<fill_type>`, *optional*, defaults to 0.0): <fill_docstring>
        classifier_dropout (`<fill_type>`, *optional*): <fill_docstring>
        attention_dropout (`float`, *optional*, defaults to 0.0):
            The dropout ratio after computing the attention scores.
        max_position_embeddings (`int`, *optional*, defaults to 32768):
            The maximum sequence length that this model might ever be used with.
        initializer_range (`float`, *optional*, defaults to 0.02):
            The standard deviation of the truncated_normal_initializer for initializing all weight matrices.
        rms_norm_eps (`float`, *optional*, defaults to 0.0):
            The epsilon value used for the RMSNorm.
        rmsnorm (`<fill_type>`, *optional*, defaults to `True`): <fill_docstring>
        apply_residual_connection_post_layernorm (`<fill_type>`, *optional*, defaults to `False`): <fill_docstring>
        post_layer_norm (`<fill_type>`, *optional*, defaults to `True`): <fill_docstring>
        add_bias_linear (`<fill_type>`, *optional*, defaults to `False`): <fill_docstring>
        add_qkv_bias (`<fill_type>`, *optional*, defaults to `False`): <fill_docstring>
        bias_dropout_fusion (`<fill_type>`, *optional*, defaults to `True`): <fill_docstring>
        multi_query_attention (`<fill_type>`, *optional*, defaults to `False`): <fill_docstring>
        multi_query_group_num (`<fill_type>`, *optional*, defaults to 2): <fill_docstring>
        rope_ratio (`<fill_type>`, *optional*, defaults to 1): <fill_docstring>
        apply_query_key_layer_scaling (`<fill_type>`, *optional*, defaults to `True`): <fill_docstring>
        attention_softmax_in_fp32 (`<fill_type>`, *optional*, defaults to `True`): <fill_docstring>
        fp32_residual_connection (`<fill_type>`, *optional*, defaults to `False`): <fill_docstring>
        use_cache (`bool`, *optional*, defaults to `True`):
            Whether or not the model should return the last key/values attentions (not used by all models). Only
            relevant if `config.is_decoder=True`. Whether to tie weight embeddings or not.
    Example:

    ```python
    >>> from transformers import GLMModel, GLMConfig
    >>> configuration = GLMConfig.from_pretrained("THUDM/glm-4-9b-chat")
    >>> model = GLMModel(configuration)
    >>> configuration = model.config
    ```"""

    model_type = "glm"
    keys_to_ignore_at_inference = ["past_key_values"]

    def __init__(
        self,
        num_hidden_layers=40,
        vocab_size=151552,
        hidden_size=4096,
        intermediate_size=13696,
        kv_channels=128,
        num_attention_heads=32,
        num_key_value_heads=32,
        hidden_act="gelu",
        seq_length=131072,
        hidden_dropout=0.0,
        classifier_dropout=None,
        attention_dropout=0.0,
        max_position_embeddings=32768,
        initializer_range=0.02,
        rms_norm_eps=1.5625e-07,
        rmsnorm=True,
        apply_residual_connection_post_layernorm=False,
        post_layer_norm=True,
        add_bias_linear=False,
        add_qkv_bias=False,
        bias_dropout_fusion=True,
        multi_query_attention=False,
        multi_query_group_num=2,
        rope_ratio=1,
        apply_query_key_layer_scaling=True,
        attention_softmax_in_fp32=True,
        fp32_residual_connection=False,
        use_cache=True,
        **kwargs
    ):
        self.num_hidden_layers = num_hidden_layers
        self.num_attention_heads = num_attention_heads
        self.vocab_size = vocab_size
        self.max_position_embeddings = max_position_embeddings
        self.initializer_range = initializer_range
        self.hidden_size = hidden_size
        self.intermediate_size = intermediate_size
        self.kv_channels = kv_channels

        if num_key_value_heads is None:
            num_key_value_heads = num_attention_heads

        self.num_key_value_heads = num_key_value_heads
        self.hidden_act = hidden_act
        self.seq_length = seq_length
        self.hidden_dropout = hidden_dropout
        self.classifier_dropout = classifier_dropout
        self.attention_dropout = attention_dropout
        self.rms_norm_eps = rms_norm_eps
        self.rmsnorm = rmsnorm
        self.apply_residual_connection_post_layernorm = (
            apply_residual_connection_post_layernorm
        )
        self.post_layer_norm = post_layer_norm
        self.add_bias_linear = add_bias_linear
        self.add_qkv_bias = add_qkv_bias
        self.bias_dropout_fusion = bias_dropout_fusion
        self.multi_query_attention = multi_query_attention
        self.multi_query_group_num = multi_query_group_num
        self.rope_ratio = rope_ratio
        self.apply_query_key_layer_scaling = apply_query_key_layer_scaling
        self.attention_softmax_in_fp32 = attention_softmax_in_fp32
        self.fp32_residual_connection = fp32_residual_connection
        self.use_cache = use_cache
        super().__init__(**kwargs)
