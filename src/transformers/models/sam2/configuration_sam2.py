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
"""SAM2 model configuration"""

from ...configuration_utils import PretrainedConfig
from ...utils import logging


logger = logging.get_logger(__name__)


# Copied from transformers.models.sam.configuration_sam.SamPromptEncoderConfig with Sam->Sam2
class Sam2PromptEncoderConfig(PretrainedConfig):
    r"""
    This is the configuration class to store the configuration of a [`Sam2PromptEncoder`]. The [`Sam2PromptEncoder`]
    module is used to encode the input 2D points and bounding boxes. Instantiating a configuration defaults will yield
    a similar configuration to that of the SAM2-hiera-tiny
    [facebook/sam2-hiera-tiny](https://huggingface.co/facebook/sam2-hiera-tiny) architecture.

    Configuration objects inherit from [`PretrainedConfig`] and can be used to control the model outputs. Read the
    documentation from [`PretrainedConfig`] for more information.

    Args:
        hidden_size (`int`, *optional*, defaults to 256):
            Dimensionality of the hidden states.
        image_size (`int`, *optional*, defaults to 1024):
            The expected output resolution of the image.
        patch_size (`int`, *optional*, defaults to 16):
            The size (resolution) of each patch.
        mask_input_channels (`int`, *optional*, defaults to 16):
            The number of channels to be fed to the `MaskDecoder` module.
        num_point_embeddings (`int`, *optional*, defaults to 4):
            The number of point embeddings to be used.
        hidden_act (`str`, *optional*, defaults to `"gelu"`):
            The non-linear activation function in the encoder and pooler.
    """

    def __init__(
        self,
        hidden_size=256,
        image_size=1024,
        patch_size=16,
        mask_input_channels=16,
        num_point_embeddings=4,
        hidden_act="gelu",
        layer_norm_eps=1e-6,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.hidden_size = hidden_size
        self.image_size = image_size
        self.patch_size = patch_size
        self.image_embedding_size = image_size // patch_size
        self.mask_input_channels = mask_input_channels
        self.num_point_embeddings = num_point_embeddings
        self.hidden_act = hidden_act
        self.layer_norm_eps = layer_norm_eps


class Sam2PositionEmbeddingConfig(PretrainedConfig):
    r"""
    This is the configuration class to store the configuration of a [`Sam2PositionEmbedding`]. The [`Sam2PositionEmbedding`]
    module is used to encode the input 2D points and bounding boxes. Instantiating a configuration defaults will yield
    a similar configuration to that of the SAM2-hiera-tiny
    [facebook/sam2-hiera-tiny](https://huggingface.co/facebook/sam2-hiera-tiny) architecture.

    Configuration objects inherit from [`PretrainedConfig`] and can be used to control the model outputs. Read the
    documentation from [`PretrainedConfig`] for more information.

    Args:
        num_pos_feats (`int`):
            The number of feature size for positioinal features.
        temperature (`int`, *optional*, defaults to 10000):
            The temperature value to consider.
        normalize (`bool`, *optional*, defaults to True):
            Whether to normalize the embedding vector.
        scale (`float`, *optional*, defaults to None):
            The scale value for embedding vector.
    """

    def __init__(
        self,
        num_pos_feats,
        temperature=10000,
        normalize=True,
        scale=None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.num_pos_feats = num_pos_feats
        self.temperature = temperature
        self.normalize = normalize
        self.scale = scale


class Sam2MaskDecoderConfig(PretrainedConfig):
    r"""
    This is the configuration class to store the configuration of a [`Sam2MaskDecoder`]. It is used to instantiate a SAM2
    mask decoder to the specified arguments, defining the model architecture. Instantiating a configuration defaults
    will yield a similar configuration to that of the SAM2-hiera-tiny
    [facebook/sam2-hiera-tiny](https://huggingface.co/facebook/sam2-hiera-tiny) architecture.

    Configuration objects inherit from [`PretrainedConfig`] and can be used to control the model outputs. Read the
    documentation from [`PretrainedConfig`] for more information.

    Args:
        hidden_size (`int`, *optional*, defaults to 256):
            Dimensionality of the hidden states.
        hidden_act (`str`, *optional*, defaults to `"gelu"`):
            The non-linear activation function used inside the `Sam2MaskDecoder` module.
        mlp_dim (`int`, *optional*, defaults to 2048):
            Dimensionality of the "intermediate" (i.e., feed-forward) layer in the Transformer encoder.
        num_hidden_layers (`int`, *optional*, defaults to 2):
            Number of hidden layers in the Transformer encoder.
        num_attention_heads (`int`, *optional*, defaults to 8):
            Number of attention heads for each attention layer in the Transformer encoder.
        attention_downsample_rate (`int`, *optional*, defaults to 2):
            The downsampling rate of the attention layer.
        num_multimask_outputs (`int`, *optional*, defaults to 3):
            The number of outputs from the `SamMaskDecoder` module. In the Segment Anything paper, this is set to 3.
        iou_head_depth (`int`, *optional*, defaults to 3):
            The number of layers in the IoU head module.
        iou_head_hidden_dim (`int`, *optional*, defaults to 256):
            The dimensionality of the hidden states in the IoU head module.
        use_high_res_features (`bool`, *optional*, defaults to False):
            whether to use high-resolution feature maps in the SAM mask decoder.
        iou_prediction_use_sigmoid (`bool`, *optional*, defaults to False):
            Whether to use sigmoid to restrict ious prediction to [0-1]
        dynamic_multimask_via_stability (`bool`, *optional*, defaults to False):
            Whether to use the best multimask output token if the single mask output token gives low stability scores
        dynamic_multimask_stability_delta (`float`, *optional*, defaults to 0.05):
            The margin of mask logits to compute stability scores.
        dynamic_multimask_stability_thresh (`float`, *optional*, defaults to 0.98):
            The minimum threshold of stability scores.
        pred_obj_scores (`bool`, *optional*, defaults to False):
            Whether to predict if there is an object in the frame.
        pred_obj_scores_mlp (`bool`, *optional*, defaults to False):
            Whether to use an MLP to predict object scores.
        use_multimask_token_for_obj_ptr (`bool`, *optional*, defaults to False):
            Whether to use multimask tokens for obj ptr. Only relevant when both `use_obj_ptrs_in_encoder=True` and multimask_output_for_tracking=True`.
        layer_norm_eps (`float`, *optional*, defaults to 1e-06):
            The epsilon used by the layer normalization layers.

    """

    def __init__(
        self,
        hidden_size=256,
        hidden_act="gelu",
        mlp_dim=2048,
        num_hidden_layers=2,
        num_attention_heads=8,
        attention_downsample_rate=2,
        num_multimask_outputs=3,
        iou_head_depth=3,
        iou_head_hidden_dim=256,
        use_high_res_features=False,
        iou_prediction_use_sigmoid=False,
        dynamic_multimask_via_stability=False,
        dynamic_multimask_stability_delta=0.05,
        dynamic_multimask_stability_thresh=0.98,
        pred_obj_scores=False,
        pred_obj_scores_mlp=False,
        use_multimask_token_for_obj_ptr=False,
        layer_norm_eps=1e-6,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.hidden_size = hidden_size
        self.hidden_act = hidden_act
        self.mlp_dim = mlp_dim
        self.num_hidden_layers = num_hidden_layers
        self.num_attention_heads = num_attention_heads
        self.attention_downsample_rate = attention_downsample_rate
        self.num_multimask_outputs = num_multimask_outputs
        self.iou_head_depth = iou_head_depth
        self.iou_head_hidden_dim = iou_head_hidden_dim
        self.use_high_res_features = (use_high_res_features,)
        self.iou_prediction_use_sigmoid = (iou_prediction_use_sigmoid,)
        self.dynamic_multimask_via_stability = (dynamic_multimask_via_stability,)
        self.dynamic_multimask_stability_delta = (dynamic_multimask_stability_delta,)
        self.dynamic_multimask_stability_thresh = (dynamic_multimask_stability_thresh,)
        self.pred_obj_scores = (pred_obj_scores,)
        self.pred_obj_scores_mlp = (pred_obj_scores_mlp,)
        self.use_multimask_token_for_obj_ptr = (use_multimask_token_for_obj_ptr,)
        self.layer_norm_eps = layer_norm_eps


class Sam2MemoryAttentionConfig(PretrainedConfig):
    r"""
    This is the configuration class to store the configuration of a [`Sam2MemoryAttentionConfig`]. It is used to instantiate a SAM2
    memory attention according to the specified arguments, defining the model architecture. Instantiating a configuration
    defaults will yield a similar configuration to that of the SAM2-hiera-tiny
    [facebook/sam2-hiera-tiny](https://huggingface.co/facebook/sam2-hiera-tiny) architecture.

    Configuration objects inherit from [`PretrainedConfig`] and can be used to control the model outputs. Read the
    documentation from [`PretrainedConfig`] for more information.

    Args:

    """

    def __init__(
        self,
        # TO DO
        **kwargs,
    ):
        super().__init__(**kwargs)

        # TO DO


class Sam2MemoryEncoderConfig(PretrainedConfig):
    r"""
    This is the configuration class to store the configuration of a [`Sam2MemoryEncoderConfig`]. It is used to instantiate a SAM2
    memory encoder according to the specified arguments, defining the model architecture. Instantiating a configuration
    defaults will yield a similar configuration to that of the SAM2-hiera-tiny
    [facebook/sam2-hiera-tiny](https://huggingface.co/facebook/sam2-hiera-tiny) architecture.

    Configuration objects inherit from [`PretrainedConfig`] and can be used to control the model outputs. Read the
    documentation from [`PretrainedConfig`] for more information.

    Args:

    """

    def __init__(
        self,
        out_dim=64,
        positional_encoding_config=None,
        mask_downsmapler_config=None,
        fuser_config=None,
        in_dim=256,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if positional_encoding_config is None:
            positional_encoding_config = {"num_pos_feats": 64, "normalize": True, "scale": None, "temperature": 1000}
        if mask_downsmapler_config is None:
            mask_downsmapler_config = {"kernel_size": 3, "stride": 2, "padding": 1}
        if fuser_config is None:
            fuser_config = {
                "layer": {
                    "dim": 256,
                    "kernel_size": 7,
                    "padding": 3,
                    "layer_scale_init_value": 1e-6,
                    "use_dwconv": True,
                },
                "num_layers": 2,
            }

        self.out_dim = out_dim
        self.positional_encoding_config = positional_encoding_config
        self.mask_downsmapler_config = mask_downsmapler_config
        self.fuser_config = fuser_config


# TO DO
class Sam2VisionConfig(PretrainedConfig):
    r"""
    This is the configuration class to store the configuration of a [`Sam2VisionModel`]. It is used to instantiate a SAM2
    vision encoder according to the specified arguments, defining the model architecture. Instantiating a configuration
    defaults will yield a similar configuration to that of the SAM2-hiera-tiny
    [facebook/sam2-hiera-tiny](https://huggingface.co/facebook/sam2-hiera-tiny) architecture.

    Configuration objects inherit from [`PretrainedConfig`] and can be used to control the model outputs. Read the
    documentation from [`PretrainedConfig`] for more information.

    Args:
        hidden_size (`int`, *optional*, defaults to 768):
            Dimensionality of the encoder layers and the pooler layer.
        output_channels (`int`, *optional*, defaults to 256):
            Dimensionality of the output channels in the Patch Encoder.
        num_hidden_layers (`int`, *optional*, defaults to 12):
            Number of hidden layers in the Transformer encoder.
        num_attention_heads (`int`, *optional*, defaults to 12):
            Number of attention heads for each attention layer in the Transformer encoder.
        num_channels (`int`, *optional*, defaults to 3):
            Number of channels in the input image.
        image_size (`int`, *optional*, defaults to 1024):
            Expected resolution. Target size of the resized input image.
        patch_size (`int`, *optional*, defaults to 16):
            Size of the patches to be extracted from the input image.
        hidden_act (`str`, *optional*, defaults to `"gelu"`):
            The non-linear activation function (function or string)
        layer_norm_eps (`float`, *optional*, defaults to 1e-06):
            The epsilon used by the layer normalization layers.
        attention_dropout (`float`, *optional*, defaults to 0.0):
            The dropout ratio for the attention probabilities.
        initializer_range (`float`, *optional*, defaults to 1e-10):
            The standard deviation of the truncated_normal_initializer for initializing all weight matrices.
        qkv_bias (`bool`, *optional*, defaults to `True`):
            Whether to add a bias to query, key, value projections.
        mlp_ratio (`float`, *optional*, defaults to 4.0):
            Ratio of mlp hidden dim to embedding dim.
        use_abs_pos (`bool`, *optional*, defaults to `True`):
            Whether to use absolute position embedding.
        use_rel_pos (`bool`, *optional*, defaults to `True`):
            Whether to use relative position embedding.
        window_size (`int`, *optional*, defaults to 14):
            Window size for relative position.
        global_attn_indexes (`List[int]`, *optional*, defaults to `[2, 5, 8, 11]`):
            The indexes of the global attention layers.
        num_pos_feats (`int`, *optional*, defaults to 128):
            The dimensionality of the position embedding.
        mlp_dim (`int`, *optional*):
            The dimensionality of the MLP layer in the Transformer encoder. If `None`, defaults to `mlp_ratio *
            hidden_size`.
    """

    def __init__(
        self,
        scalp=1,
        hidden_size=96,
        num_heads=1,
        drop_path_rate=0,
        q_pool=3,
        q_stride=[2, 2],
        stages=[1, 2, 7, 2],
        dim_mul=2.0,
        head_mul=2.0,
        window_pos_embed_bkg_spatial_size=[7, 7],
        window_spec=[8, 4, 14, 7],
        global_att_blocks=[5, 7, 9],
        return_interm_layers=False,
        neck_position_encoding_config=None,
        neck_hidden_size=256,
        neck_backbone_channel_list=[768, 384, 192, 96],
        neck_kernel_size=1,
        neck_stride=1,
        neck_padding=0,
        neck_fpn_interp_model="nearest",
        neck_fuse_type="sum",
        neck_fpn_top_down_level=[2, 3],
        **kwargs,
    ):
        super().__init__(**kwargs)
        if neck_position_encoding_config is None:
            neck_position_encoding_config = Sam2PositionEmbeddingConfig(num_pos_feats=256)

        self.scalp = scalp
        self.hidden_size = hidden_size
        self.num_heads = num_heads
        self.drop_path_rate = drop_path_rate
        self.q_pool = q_pool
        self.q_stride = q_stride
        self.stages = stages
        self.dim_mul = dim_mul
        self.head_mul = head_mul
        self.window_pos_embed_bkg_spatial_size = window_pos_embed_bkg_spatial_size
        self.window_spec = window_spec
        self.global_att_blocks = global_att_blocks
        self.return_interm_layers = return_interm_layers
        self.neck_position_encoding_config = neck_position_encoding_config
        self.neck_hidden_size = neck_hidden_size
        self.neck_backbone_channel_list = neck_backbone_channel_list
        self.neck_kernel_size = neck_kernel_size
        self.neck_stride = neck_stride
        self.neck_padding = neck_padding
        self.neck_fpn_interp_model = neck_fpn_interp_model
        self.neck_fuse_type = neck_fuse_type
        self.neck_fpn_top_down_level = neck_fpn_top_down_level


class Sam2Config(PretrainedConfig):
    r"""
    [`Sam2Config`] is the configuration class to store the configuration of a [`Sam2Model`]. It is used to instantiate a
    SAM2 model according to the specified arguments, defining the vision model, prompt-encoder model, mask decoder, and memory-encoder model
    configs. Instantiating a configuration with the defaults will yield a similar configuration to that of the
    [facebook/sam2-hiera-tiny](https://huggingface.co/facebook/sam2-hiera-tiny) architecture.

    Configuration objects inherit from [`PretrainedConfig`] and can be used to control the model outputs. Read the
    documentation from [`PretrainedConfig`] for more information.

    Args:
        vision_config (Union[`dict`, `Sam2VisionConfig`], *optional*):
            Dictionary of configuration options used to initialize [`Sam2VisionConfig`].
        prompt_encoder_config (Union[`dict`, `Sam2PromptEncoderConfig`], *optional*):
            Dictionary of configuration options used to initialize [`Sam2PromptEncoderConfig`].
        mask_decoder_config (Union[`dict`, `Sam2MaskDecoderConfig`], *optional*):
            Dictionary of configuration options used to initialize [`Sam2MaskDecoderConfig`].
        memory_attention_config (Union[`dict`, `Sam2MemoryAttentionConfig`], *optional*):
            Dictionary of configuration options used to initialize [`Sam2MemoryAttentionConfig`].
        memory_encoder_config (Union[`dict`, `Sam2MemoryEncoderConfig`], *optional*):
            Dictionary of configuration options used to initialize [`Sam2MemoryEncoderConfig`].

        kwargs (*optional*):
            Dictionary of keyword arguments.

    Example:

    ```python
    >>> from transformers import (
    ...     Sam2VisionConfig,
    ...     Sam2PromptEncoderConfig,
    ...     Sam2MaskDecoderConfig,
    ...     Sam2MemoryAttentionConfig,
    ...     Sam2MemoryEncoderConfig,
    ...     Sam2Model,
    ... )

    >>> # Initializing a Sam2Config with `"facebook/sam2-hiera-tiny"` style configuration
    >>> configuration = Sam2Config()

    >>> # Initializing a SamModel (with random weights) from the `"facebook/sam2-hiera-tiny"` style configuration
    >>> model = Sam2Model(configuration)

    >>> # Accessing the model configuration
    >>> configuration = model.config

    >>> # We can also initialize a Sam2Config from a Sam2VisionConfig, Sam2PromptEncoderConfig, Sam2MaskDecoderConfig, Sam2MemoryAttentionConfig and Sam2MemoryEncoderConfig

    >>> # Initializing SAM2 vision, prompt_encoder, mask_decoder, and memory_encoder
    >>> vision_config = SamVisionConfig()
    >>> prompt_encoder_config = Sam2PromptEncoderConfig()
    >>> mask_decoder_config = Sam2MaskDecoderConfig()
    >>> memory_attention_config = Sam2MemoryAttentionConfig()
    >>> memory_encoder_config = Sam2MemoryEncoderConfig()

    >>> config = Sam2Config(vision_config, prompt_encoder_config, mask_decoder_config, memory_attention_config, memory_encoder_config)
    ```"""

    model_type = "sam2"

    def __init__(
        self,
        vision_config=None,
        prompt_encoder_config=None,
        mask_decoder_config=None,
        memory_attention_config=None,
        memory_encoder_config=None,
        initializer_range=0.02,
        **kwargs,
    ):
        super().__init__(**kwargs)
        vision_config = vision_config if vision_config is not None else {}
        prompt_encoder_config = prompt_encoder_config if prompt_encoder_config is not None else {}
        mask_decoder_config = mask_decoder_config if mask_decoder_config is not None else {}
        memory_attention_config = memory_attention_config if memory_attention_config is not None else {}
        memory_encoder_config = memory_encoder_config if memory_encoder_config is not None else {}

        if isinstance(vision_config, Sam2VisionConfig):
            vision_config = vision_config.to_dict()
        if isinstance(prompt_encoder_config, Sam2PromptEncoderConfig):
            prompt_encoder_config = prompt_encoder_config.to_dict()
        if isinstance(mask_decoder_config, Sam2MaskDecoderConfig):
            mask_decoder_config = mask_decoder_config.to_dict()
        if isinstance(memory_attention_config, Sam2MemoryAttentionConfig):
            memory_attention_config = memory_attention_config.to_dict()
        if isinstance(memory_encoder_config, Sam2MemoryEncoderConfig):
            memory_encoder_config = memory_encoder_config.to_dict()

        self.vision_config = Sam2VisionConfig(**vision_config)
        self.prompt_encoder_config = Sam2PromptEncoderConfig(**prompt_encoder_config)
        self.mask_decoder_config = Sam2MaskDecoderConfig(**mask_decoder_config)
        self.memory_attention_config = Sam2MemoryAttentionConfig(**memory_attention_config)
        self.memory_encoder_config = Sam2MemoryEncoderConfig(**memory_encoder_config)
        self.initializer_range = initializer_range