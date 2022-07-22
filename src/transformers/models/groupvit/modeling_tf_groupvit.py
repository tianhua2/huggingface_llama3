# coding=utf-8
# Copyright 2022 NVIDIA and The HuggingFace Team. All rights reserved.
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
""" TF 2.0 GroupViT model."""


import collections.abc
import math
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Union

import numpy as np
import tensorflow as tf
import tensorflow_probability as tfp

from ...activations_tf import get_tf_activation
from ...modeling_tf_outputs import TFBaseModelOutput, TFBaseModelOutputWithPooling

# Public API
from ...modeling_tf_utils import (
    DUMMY_INPUTS,
    TFModelInputType,
    TFPreTrainedModel,
    get_initializer,
    keras_serializable,
    unpack_inputs,
)
from ...tf_utils import shape_list, stable_softmax
from ...utils import (
    ModelOutput,
    add_start_docstrings,
    add_start_docstrings_to_model_forward,
    logging,
    replace_return_docstrings,
)
from .configuration_groupvit import GroupViTConfig, GroupViTTextConfig, GroupViTVisionConfig


logger = logging.get_logger(__name__)

_CHECKPOINT_FOR_DOC = "nvidia/groupvit-gcc-yfcc"

GROUPVIT_PRETRAINED_MODEL_ARCHIVE_LIST = [
    "nvidia/groupvit-gcc-yfcc",
    # See all GroupViT models at https://huggingface.co/models?filter=groupvit
]


LARGE_NEGATIVE = -1e8


# Copied from transformers.models.bart.modeling_tf_bart._expand_mask
def _expand_mask(mask: tf.Tensor, tgt_len: Optional[int] = None):
    """
    Expands attention_mask from `[bsz, seq_len]` to `[bsz, 1, tgt_seq_len, src_seq_len]`.
    """
    src_len = shape_list(mask)[1]
    tgt_len = tgt_len if tgt_len is not None else src_len
    one_cst = tf.constant(1.0)
    mask = tf.cast(mask, dtype=one_cst.dtype)
    expanded_mask = tf.tile(mask[:, None, None, :], (1, 1, tgt_len, 1))

    return (one_cst - expanded_mask) * LARGE_NEGATIVE


# contrastive loss function, adapted from
# https://sachinruk.github.io/blog/pytorch/pytorch%20lightning/loss%20function/gpu/2021/03/07/CLIP.html
def contrastive_loss(logits: tf.Tensor) -> tf.Tensor:
    return tf.math.reduce_mean(
        tf.keras.metrics.sparse_categorical_crossentropy(
            y_true=tf.range(shape_list(logits)[0]), y_pred=logits, from_logits=True
        )
    )


# Copied from transformers.models.clip.modeling_tf_clip.clip_loss with clip->groupvit
def groupvit_loss(similarity: tf.Tensor) -> tf.Tensor:
    caption_loss = contrastive_loss(similarity)
    image_loss = contrastive_loss(tf.transpose(similarity))
    return (caption_loss + image_loss) / 2.0


def hard_softmax(logits: tf.Tensor, dim: int) -> tf.Tensor:
    """
    Reference: https://gist.github.com/ariG23498/08cdae21637b8b61bdd6d21d11719fb3
    """
    y_soft = stable_softmax(logits, dim)
    # Straight through.
    index = tf.argmax(y_soft, dim)
    y_hard = tf.one_hot(
        index,
        depth=shape_list(logits)[dim],
        axis=dim,
        dtype=y_soft.dtype,
    )
    ret = y_hard - tf.stop_gradient(y_soft) + y_soft

    return ret


def gumbel_softmax(logits: tf.Tensor, tau: float = 1, hard: bool = False, dim: int = -1) -> tf.Tensor:
    gumbel_dist = tfp.distributions.Gumbel(0.0, 1.0)
    gumbels = gumbel_dist.sample(
        shape_list(logits),
        dtype=logits.dtype,
    )

    gumbels = (logits + gumbels) / tau  # ~Gumbel(logits,tau)
    y_soft = stable_softmax(gumbels, dim)

    if hard:
        # Straight through.
        index = tf.argmax(y_soft, dim)
        y_hard = tf.one_hot(
            index,
            depth=shape_list(logits)[dim],
            axis=dim,
            dtype=y_soft.dtype,
        )
        ret = y_hard - tf.stop_gradient(y_soft) + y_soft
    else:
        # Reparametrization trick.
        ret = y_soft
    return ret


def resize_attention_map(attentions: tf.Tensor, height: int, width: int, align_corners: Optional[bool] = False) -> tf.Tensor:
    """
    Refernece: https://gist.github.com/ariG23498/3777f8d9be25de8ae782256f5aacb2c5
    Args:
        attentions (`tf.Tensor`): attention map of shape [batch_size, groups, feat_height*feat_width]
        height (`int`): height of the output attention map
        width (`int`): width of the output attention map
        align_corners (`bool`, *optional*): the `align_corner` argument for `nn.functional.interpolate`.

    Returns:
        `tf.Tensor`: resized attention map of shape [batch_size, groups, height, width]
    """

    scale = (height * width // attentions.shape[2]) ** 0.5
    if height > width:
        feat_width = int(np.round(width / scale))
        feat_height = shape_list(attentions)[2] // feat_width
    else:
        feat_height = int(np.round(height / scale))
        feat_width = shape_list(attentions)[2] // feat_height

    batch_size = shape_list(attentions)[0]
    groups = shape_list(attentions)[1]  # number of group token
    # [batch_size, groups, height x width, groups] -> [batch_size, groups, height, width]
    attentions = tf.reshape(attentions, (batch_size, groups, feat_height, feat_width))
    attentions = tf.transpose(attentions, perm=(0, 2, 3, 1))
    if align_corners:
        attentions = tf.compat.v1.image.resize(
            attentions, size=(height, width), method="bilinear", align_corners=align_corners,
        )
    else:
        attentions = tf.image.resize(
            attentions, size=(height, width), method="bilinear"
        )
    attentions = tf.transpose(attentions, perm=(0, 3, 1, 2))
    return attentions


def get_grouping_from_attentions(attentions: Tuple[tf.Tensor], hw_shape: Tuple[int]) -> tf.Tensor:
    """
    Args:
        attentions (`tuple(tf.Tensor)`: tuple of attention maps returned by `TFGroupViTVisionTransformer`
        hw_shape (`tuple(int)`): height and width of the output attention map
    Returns:
        `tf.Tensor`: the attention map of shape [batch_size, groups, height, width]
    """

    attn_maps = []
    prev_attn_masks = None
    for attn_masks in attentions:
        # [batch_size, num_groups, height x width] -> [batch_size, height x width, num_groups]
        attn_masks = tf.transpose(attn_masks, perm=(0, 2, 1))
        if prev_attn_masks is None:
            prev_attn_masks = attn_masks
        else:
            prev_attn_masks = tf.matmul(prev_attn_masks, attn_masks)
        # [batch_size, height x width, num_groups] -> [batch_size, num_groups, height x width] -> [batch_size, num_groups, height, width]
        cur_attn_map = resize_attention_map(
            tf.transpose(prev_attn_masks, perm=(0, 2, 1)),
            *hw_shape
        )
        attn_maps.append(cur_attn_map)

    # [batch_size, num_groups, height, width]
    final_grouping = attn_maps[-1]

    return final_grouping


class TFGroupViTCrossAttentionLayer(tf.keras.layers.Layer):
    def __init__(self, config: GroupViTVisionConfig, **kwargs):
        super().__init__(**kwargs)
        self.attn = TFGroupViTAttention(config, name="attn")
        self.norm2 = tf.keras.layers.LayerNormalization(epsilon=config.layer_norm_eps, name="norm2")
        self.mlp = TFGroupViTMLP(config, name="mlp")
        self.norm_post = tf.keras.layers.LayerNormalization(epsilon=config.layer_norm_eps, name="norm_post")

    def call(self, query:tf.Tensor, key: tf.Tensor) -> tf.Tensor:
        x = query
        x = x + self.attn(query, encoder_hidden_states=key)[0]
        x = x + self.mlp(self.norm2(x))
        x = self.norm_post(x)
        return x


class TFGroupViTAssignAttention(tf.keras.layers.Layer):
    def __init__(self, config: GroupViTVisionConfig, **kwargs):
        super().__init__(**kwargs)
        self.scale = config.hidden_size**-0.5

        self.q_proj = tf.keras.layers.Dense(config.hidden_size, name="q_proj")
        self.k_proj = tf.keras.layers.Dense(config.hidden_size, name="k_proj")
        self.v_proj = tf.keras.layers.Dense(config.hidden_size, name="v_proj")
        self.proj = tf.keras.layers.Dense(config.hidden_size, name="proj")
        self.assign_eps = config.assign_eps

    def get_attn(self, attn: tf.Tensor, gumbel : bool = True, hard: bool = True) -> tf.Tensor:

        if gumbel and self.training:
            attn = gumbel_softmax(attn, dim=-2, hard=hard)
        else:
            if hard:
                attn = hard_softmax(attn, dim=-2)
            else:
                attn = stable_softmax(attn, axis=-2)

        return attn

    def call(self, query: tf.Tensor, key: tf.Tensor):
        value = key
        # [batch_size, query_length, channels]
        query = self.q_proj(query)

        # [batch_size, key_length, channels]
        key = self.k_proj(key)

        # [batch_size, key_length, channels]
        value = self.v_proj(value)

        # [batch_size, query_length, key_length]
        raw_attn = tf.matmul(query, key, transpose_b=True) * self.scale

        attn = self.get_attn(raw_attn)
        soft_attn = self.get_attn(raw_attn, gumbel=False, hard=False)

        attn = attn / (tf.math.reduce_sum(attn, axis=-1, keepdims=True) + self.assign_eps)

        out = tf.matmul(attn, value)

        out = self.proj(out)

        return out, soft_attn


class TFGroupViTTokenAssign(tf.keras.layers.Layer):
    def __init__(self, config: GroupViTVisionConfig, num_group_token: int, num_output_group: int, **kwargs):
        super().__init__(**kwargs)
        self.num_output_group = num_output_group
        # norm on group_tokens
        self.norm_tokens = tf.keras.layers.LayerNormalization(epsilon=config.layer_norm_eps, name="norm_tokens")
        assign_mlp_ratio = (
            config.assign_mlp_ratio
            if isinstance(config.assign_mlp_ratio, collections.abc.Iterable)
            else (config.assign_mlp_ratio, config.assign_mlp_ratio)
        )
        tokens_dim, channels_dim = [int(x * config.hidden_size) for x in assign_mlp_ratio]
        self.mlp_inter = TFGroupViTMixerMLP(config, num_group_token, tokens_dim, num_output_group, name="mlp_inter")
        self.norm_post_tokens = tf.keras.layers.LayerNormalization(epsilon=config.layer_norm_eps, name="norm_post_tokens")
        # norm on x
        self.norm_x = tf.keras.layers.LayerNormalization(epsilon=config.layer_norm_eps, name="norm_x")
        self.pre_assign_attn = TFGroupViTCrossAttentionLayer(config, name="pre_assign_attn")

        self.assign = TFGroupViTAssignAttention(config, name="assign")
        self.norm_new_x = tf.keras.layers.LayerNormalization(epsilon=config.layer_norm_eps, name="norm_new_x")
        self.mlp_channels = TFGroupViTMLP(config, config.hidden_size, channels_dim, config.hidden_size, name="mlp_channels")

    def project_group_token(self, group_tokens: tf.Tensor) -> tf.Tensor:
        """
        Args:
            group_tokens (tf.Tensor): group tokens, [batch_size, num_group_tokens, channels]

        Returns:
            projected_group_tokens (tf.Tensor): [batch_size, num_output_groups, channels]
        """
        # [B, num_output_groups, C] <- [B, num_group_tokens, C]
        projected_group_tokens = self.mlp_inter(group_tokens)
        projected_group_tokens = self.norm_post_tokens(projected_group_tokens)
        return projected_group_tokens

    def call(self, image_tokens: tf.Tensor, group_tokens: tf.Tensor):
        """
        Args:
            image_tokens (`tf.Tensor`): image tokens, of shape [batch_size, input_length, channels]
            group_tokens (`tf.Tensor`): group tokens, [batch_size, num_group_tokens, channels]
        """

        group_tokens = self.norm_tokens(group_tokens)
        image_tokens = self.norm_x(image_tokens)
        # [batch_size, num_output_groups, channels]
        projected_group_tokens = self.project_group_token(group_tokens)
        projected_group_tokens = self.pre_assign_attn(projected_group_tokens, image_tokens)
        new_image_tokens, attention = self.assign(projected_group_tokens, image_tokens)
        new_image_tokens += projected_group_tokens

        new_image_tokens = new_image_tokens + self.mlp_channels(self.norm_new_x(new_image_tokens))

        return new_image_tokens, attention


@dataclass
class TFGroupViTModelOutput(ModelOutput):
    """
    Args:
        loss (`tf.Tensor` of shape `(1,)`, *optional*, returned when `return_loss` is `True`):
            Contrastive loss for image-text similarity.
        logits_per_image (`tf.Tensor` of shape `(image_batch_size, text_batch_size)`):
            The scaled dot product scores between `image_embeds` and `text_embeds`. This represents the image-text
            similarity scores.
        logits_per_text (`tf.Tensor` of shape `(text_batch_size, image_batch_size)`):
            The scaled dot product scores between `text_embeds` and `image_embeds`. This represents the text-image
            similarity scores.
        segmentation_logits (`tf.Tensor` of shape `(batch_size, config.num_labels, logits_height, logits_width)`):
            Classification scores for each pixel.

            <Tip warning={true}>

            The logits returned do not necessarily have the same size as the `pixel_values` passed as inputs. This is
            to avoid doing two interpolations and lose some quality when a user needs to resize the logits to the
            original image size as post-processing. You should always check your logits shape and resize as needed.

            </Tip>

        text_embeds (`tf.Tensor` of shape `(batch_size, output_dim`):
            The text embeddings obtained by applying the projection layer to the pooled output of
            [`TFGroupViTTextModel`].
        image_embeds (`tf.Tensor` of shape `(batch_size, output_dim`):
            The image embeddings obtained by applying the projection layer to the pooled output of
            [`TFGroupViTVisionModel`].
        text_model_output (`TFBaseModelOutputWithPooling`):
            The output of the [`TFGroupViTTextModel`].
        vision_model_output (`TFBaseModelOutputWithPooling`):
            The output of the [`TFGroupViTVisionModel`].
    """

    loss: Optional[tf.Tensor] = None
    logits_per_image: tf.Tensor = None
    logits_per_text: tf.Tensor = None
    segmentation_logits: tf.Tensor = None
    text_embeds: tf.Tensor = None
    image_embeds: tf.Tensor = None
    text_model_output: TFBaseModelOutputWithPooling = None
    vision_model_output: TFBaseModelOutputWithPooling = None

    def to_tuple(self) -> Tuple[Any]:
        return tuple(
            self[k] if k not in ["text_model_output", "vision_model_output"] else getattr(self, k).to_tuple()
            for k in self.keys()
        )


class TFGroupViTPatchEmbeddings(tf.keras.layers.Layer):
    """
    Image to Patch Embedding.
    """

    def __init__(
        self,
        image_size: int = 224,
        patch_size: Union[int, Tuple[int, int]] = 16,
        num_channels: int = 3,
        embed_dim: int = 768,
        **kwargs
    ):
        super().__init__(**kwargs)
        image_size = image_size if isinstance(image_size, collections.abc.Iterable) else (image_size, image_size)
        patch_size = patch_size if isinstance(patch_size, collections.abc.Iterable) else (patch_size, patch_size)
        num_patches = (image_size[1] // patch_size[1]) * (image_size[0] // patch_size[0])
        self.image_size = image_size
        self.patch_size = patch_size
        self.num_patches = num_patches

        self.projection = tf.keras.layers.Conv2D(
            filters=embed_dim,
            kernel_size=patch_size,
            stride=patch_size,
            padding="valid",
            data_format="channels_last",
            name="projection",
        )

    def call(self, pixel_values: tf.Tensor, interpolate_pos_encoding: bool = False) -> tf.Tensor:
        batch_size, num_channels, height, width = shape_list(pixel_values)
        if not interpolate_pos_encoding:
            if height != self.image_size[0] or width != self.image_size[1]:
                raise ValueError(
                    f"Input image size ({height}*{width}) doesn't match model"
                    f" ({self.image_size[0]}*{self.image_size[1]})."
                )
        
        # When running on CPU, `tf.keras.layers.Conv2D` doesn't support `NCHW` format.
        # So change the input format from `NCHW` to `NHWC`.
        # shape = (batch_size, in_height, in_width, in_channels=num_channels)
        pixel_values = tf.transpose(pixel_values, perm=(0, 2, 3, 1))

        x = self.projection(pixel_values)
        
        # Change the 2D spatial dimensions to a single temporal dimension.
        # shape = (batch_size, num_patches, out_channels=embed_dim)
        num_patches = (width // self.patch_size[1]) * (height // self.patch_size[0])
        x = tf.reshape(tensor=x, shape=(batch_size, num_patches, -1))
        return x


class TFGroupViTVisionEmbeddings(tf.keras.layers.Layer):
    def __init__(self, config: GroupViTVisionConfig, **kwargs):
        super().__init__(**kwargs)

        self.patch_embeddings = TFGroupViTPatchEmbeddings(
            image_size=config.image_size,
            patch_size=config.patch_size,
            num_channels=config.num_channels,
            embed_dim=config.hidden_size,
            name="patch_embeddings",
        )
        self.dropout = tf.keras.layers.Dropout(config.dropout, name="dropout")
        self.layernorm = tf.keras.layers.LayerNormalization(epsilon=config.layer_norm_eps, name="layernorm")
        self.config = config
    
    def build(self, input_shape: tf.TensorShape):

        num_patches = self.patch_embeddings.num_patches
        self.position_embeddings = self.add_weight(
            shape=(1, num_patches, self.config.hidden_size),
            initializer="zeros",
            trainable=True,
            name="position_embeddings",
        )

        super().build(input_shape)

    def interpolate_pos_encoding(self, embeddings, height, width) -> tf.Tensor:
        """
        This method allows to interpolate the pre-trained position encodings, to be able to use the model on higher
        resolution images.

        Source:
        https://github.com/facebookresearch/dino/blob/de9ee3df6cf39fac952ab558447af1fa1365362a/vision_transformer.py#L174
        """
        npatch = shape_list(embeddings)[1]
        if npatch == shape_list(self.position_embeddings)[1] and height == width:
            return self.position_embeddings
        patch_pos_embed = self.position_embeddings
        num_original_pos_embed = shape_list(patch_pos_embed)[1]
        dim = shape_list(embeddings)[-1]
        feat_height = height // self.config.patch_size
        feat_width = width // self.config.patch_size
        original_height = original_width = math.sqrt(num_original_pos_embed)
        patch_pos_embed = tf.image.resize(
            images=tf.reshape(
                patch_pos_embed, shape=(1, int(math.sqrt(original_height)), int(math.sqrt(original_width)), dim)
            ),
            size=(feat_height, feat_width),
            method="bicubic",
        )
        patch_pos_embed = tf.reshape(tensor=patch_pos_embed, shape=(1, -1, dim))
        return patch_pos_embed


    def call(self, pixel_values: tf.Tensor, interpolate_pos_encoding: bool = False) -> tf.Tensor:
        batch_size, num_channels, height, width = shape_list(pixel_values)
        embeddings = self.patch_embeddings(pixel_values, interpolate_pos_encoding=interpolate_pos_encoding)

        embeddings = self.layernorm(embeddings)

        batch_size, seq_len, _ = shape_list(embeddings)

        # add positional encoding to each token
        if interpolate_pos_encoding:
            embeddings = embeddings + self.interpolate_pos_encoding(embeddings, height, width)
        else:
            embeddings = embeddings + self.position_embeddings

        embeddings = self.dropout(embeddings)

        return embeddings


# Copied from transformers.models.clip.modeling_tf_clip.TFCLIPTextEmbeddings with CLIP->GroupViT
class TFGroupViTTextEmbeddings(tf.keras.layers.Layer):
    def __init__(self, config: GroupViTTextConfig, **kwargs):
        super().__init__(**kwargs)

        self.embed_dim = config.hidden_size
        self.vocab_size = config.vocab_size

        self.config = config

    def build(self, input_shape: tf.TensorShape):

        with tf.name_scope("token_embedding"):
            self.weight = self.add_weight(
                shape=(self.vocab_size, self.embed_dim),
                initializer=get_initializer(self.config.initializer_factor * self.config.initializer_range),
                trainable=True,
                name="weight",
            )

        with tf.name_scope("position_embedding"):
            self.position_embedding = self.add_weight(
                shape=(self.config.max_position_embeddings, self.embed_dim),
                initializer=get_initializer(self.config.initializer_factor * self.config.initializer_range),
                trainable=True,
                name="embeddings",
            )

        super().build(input_shape)

    def call(
        self,
        input_ids: tf.Tensor = None,
        position_ids: tf.Tensor = None,
        inputs_embeds: tf.Tensor = None,
    ) -> tf.Tensor:
        """
        Applies embedding based on inputs tensor.

        Returns:
            final_embeddings (`tf.Tensor`): output embedding tensor.
        """
        if input_ids is None and inputs_embeds is None:
            raise ValueError("You have to specify either input_ids or inputs_embeds")

        if inputs_embeds is None:
            inputs_embeds = tf.gather(params=self.weight, indices=input_ids)

        input_shape = shape_list(inputs_embeds)[:-1]

        if position_ids is None:
            position_ids = tf.expand_dims(tf.range(start=0, limit=input_shape[-1]), axis=0)

        position_embeds = tf.gather(params=self.position_embedding, indices=position_ids)
        position_embeds = tf.tile(input=position_embeds, multiples=(input_shape[0], 1, 1))
        final_embeddings = inputs_embeds + position_embeds

        return final_embeddings


class TFGroupViTStage(tf.keras.layers.Layer):
    """This corresponds to the `GroupingLayer` class in the GroupViT implementation."""

    def __init__(
        self,
        config: GroupViTVisionConfig,
        depth: int,
        num_prev_group_token: int,
        num_group_token: int,
        num_output_group: int,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.depth = depth
        self.num_group_token = num_group_token
        self.gradient_checkpointing = False
        self.layers = [TFGroupViTEncoderLayer(config) for _ in range(depth)]

        if num_group_token > 0:
            self.downsample = TFGroupViTTokenAssign(
                config=config,
                num_group_token=num_group_token,
                num_output_group=num_output_group,
                name="downsample",
            )
        else:
            self.downsample = None

        if num_prev_group_token > 0 and num_group_token > 0:
            self.group_projector = tf.keras.Sequential([
                tf.keras.layers.LayerNormalization(epsilon=config.layer_norm_eps),
                TFGroupViTMixerMLP(config, num_prev_group_token, config.hidden_size // 2, num_group_token),
            ])
        else:
            self.group_projector = None
    
    def build(self, input_shape: tf.TensorShape):
        if self.num_group_token > 0:
            self.group_token = self.add_weight(
                shape=(1, self.num_group_token,
                self.config.hidden_size),
                initializer="zeros",
                trainable=True, name="group_token",
            )
        else:
            self.group_token = None
        super().build(input_shape)

    @property
    def with_group_token(self):
        return self.group_token is not None

    def split_x(self, x: tf.Tensor) -> tf.Tensor:
        if self.with_group_token:
            return x[:, : -self.num_group_token], x[:, -self.num_group_token :]
        else:
            return x, None

    def concat_x(self, x: tf.Tensor, group_token: Optional[tf.Tensor] = None) -> tf.Tensor:
        if group_token is None:
            return x
        return tf.concat([x, group_token], axis=1)

    def call(
        self,
        hidden_states: tf.Tensor,
        prev_group_token: Optional[tf.Tensor] = None,
        output_attentions: Optional[bool] = False,
    ) -> Tuple[tf.Tensor]:
        """
        Args:
            hidden_states (`tf.Tensor`): input to the layer of shape `(batch, seq_len, embed_dim)`
            attention_mask (`tf.Tensor`): attention mask of size
                `(batch, 1, tgt_len, src_len)` where padding elements are indicated by very large negative values.
                `(config.encoder_attention_heads,)`.
            output_attentions (`bool`, *optional*):
                Whether or not to return the grouping tensors of Grouping block.
        """
        if self.with_group_token:
            group_token = tf.tile(
                group_token,
                shape=(shape_list(hidden_states)[0], 1, 1)
            )
            if self.group_projector is not None:
                group_token = group_token + self.group_projector(prev_group_token)
        else:
            group_token = None

        x = hidden_states

        cat_x = self.concat_x(x, group_token)
        for layer in self.layers:
            layer_out = layer(cat_x, attention_mask=None, causal_attention_mask=None)
            cat_x = layer_out[0]

        x, group_token = self.split_x(cat_x)

        attention = None
        if self.downsample is not None:
            x, attention = self.downsample(x, group_token)

        outputs = (x, group_token)
        if output_attentions:
            outputs = outputs + (attention,)

        return outputs


class TFGroupViTMLP(tf.keras.layers.Layer):
    def __init__(
        self,
        config: GroupViTVisionConfig,
        hidden_size: Optional[int] = None,
        intermediate_size: Optional[int] = None,
        output_size: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.config = config
        self.activation_fn = get_tf_activation(config.hidden_act)
        hidden_size = hidden_size if hidden_size is not None else config.hidden_size
        intermediate_size = intermediate_size if intermediate_size is not None else config.intermediate_size
        output_size = output_size if output_size is not None else hidden_size
        self.fc1 = tf.keras.layers.Dense(intermediate_size, name="fc1")
        self.fc2 = tf.keras.layers.Dense(output_size, name="fc2")

    def call(self, hidden_states: tf.Tensor) -> tf.Tensor:
        hidden_states = self.fc1(hidden_states)
        hidden_states = self.activation_fn(hidden_states)
        hidden_states = self.fc2(hidden_states)
        return hidden_states


class TFGroupViTMixerMLP(TFGroupViTMLP):
    def call(self, x):
        x = super()(tf.transpose(x, perm=(0, 2, 1, 3)))
        return tf.transpose(x, perm=(0, 2, 1, 3))


class TFGroupViTAttention(tf.keras.layers.Layer):
    """Multi-headed attention from 'Attention Is All You Need' paper"""

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.embed_dim = config.hidden_size
        self.num_heads = config.num_attention_heads
        self.head_dim = self.embed_dim // self.num_heads
        if self.head_dim * self.num_heads != self.embed_dim:
            raise ValueError(
                f"embed_dim must be divisible by num_heads (got `embed_dim`: {self.embed_dim} and `num_heads`:"
                f" {self.num_heads})."
            )
        self.scale = self.head_dim**-0.5
        self.dropout = config.attention_dropout

        self.k_proj = tf.keras.layers.Dense(self.embed_dim, name="k_proj")
        self.v_proj = tf.keras.layers.Dense(self.embed_dim, name="v_proj")
        self.q_proj = tf.keras.layers.Dense(self.embed_dim, name="q_proj")
        self.out_proj = tf.keras.layers.Dense(self.embed_dim, name="out_proj")

    def _shape(self, tensor: tf.Tensor, seq_len: int, bsz: int):
        tensor = tf.reshape(tensor, shape=(bsz, seq_len, self.num_heads, self.head_dim))
        tensor = tf.transpose(tensor, perm=(0, 2, 1, 3))
        return tensor

    def call(
        self,
        hidden_states: tf.Tensor,
        attention_mask: Optional[tf.Tensor] = None,
        causal_attention_mask: Optional[tf.Tensor] = None,
        encoder_hidden_states: Optional[tf.Tensor] = None,
        output_attentions: Optional[bool] = False,
    ) -> Tuple[tf.Tensor, Optional[tf.Tensor], Optional[Tuple[tf.Tensor]]]:
        """Input shape: Batch x Time x Channel"""

        bsz, tgt_len, embed_dim = shape_list(hidden_states)
        is_cross_attention = encoder_hidden_states is not None

        # get query proj
        query_states = self.q_proj(hidden_states) * self.scale
        if is_cross_attention:
            key_states = self._shape(self.k_proj(encoder_hidden_states), -1, bsz)
            value_states = self._shape(self.v_proj(encoder_hidden_states), -1, bsz)
        else:
            key_states = self._shape(self.k_proj(hidden_states), -1, bsz)
            value_states = self._shape(self.v_proj(hidden_states), -1, bsz)

        proj_shape = (bsz * self.num_heads, -1, self.head_dim)
        query_states = self._shape(query_states, tgt_len, bsz)
        query_states = tf.reshape(query_states, *proj_shape)
        key_states = tf.reshape(key_states, *proj_shape)
        value_states = tf.reshape(value_states, *proj_shape)

        src_len = shape_list(key_states)[1]
        attn_weights = tf.matmul(query_states, key_states, transpose_b=True)

        if shape_list(attn_weights) != (bsz * self.num_heads, tgt_len, src_len):
            raise ValueError(
                f"Attention weights should be of size {(bsz * self.num_heads, tgt_len, src_len)}, but is"
                f" {shape_list(attn_weights)}"
            )

        # apply the causal_attention_mask first
        if causal_attention_mask is not None:
            if shape_list(causal_attention_mask) != (bsz, 1, tgt_len, src_len):
                raise ValueError(
                    f"Attention mask should be of size {(bsz, 1, tgt_len, src_len)}, but is"
                    f" {shape_list(causal_attention_mask)}"
                )
            attn_weights = tf.reshape(attn_weights, (bsz, self.num_heads, tgt_len, src_len)) + causal_attention_mask
            attn_weights = tf.reshape(attn_weights, (bsz * self.num_heads, tgt_len, src_len))

        if attention_mask is not None:
            if shape_list(attention_mask) != (bsz, 1, tgt_len, src_len):
                raise ValueError(
                    f"Attention mask should be of size {(bsz, 1, tgt_len, src_len)}, but is"
                    f"{shape_list(attention_mask)}"
                )
            attn_weights = tf.reshape(attn_weights, (bsz, self.num_heads, tgt_len, src_len)) + attention_mask
            attn_weights = tf.reshape(attn_weights, (bsz * self.num_heads, tgt_len, src_len))

        attn_weights = stable_softmax(attn_weights, axis=-1)

        if output_attentions:
            # this operation is a bit akward, but it's required to
            # make sure that attn_weights keeps its gradient.
            # In order to do so, attn_weights have to reshaped
            # twice and have to be reused in the following
            attn_weights_reshaped = tf.reshape(attn_weights, (bsz, self.num_heads, tgt_len, src_len))
            attn_weights = tf.reshape(attn_weights_reshaped, (bsz * self.num_heads, tgt_len, src_len))
        else:
            attn_weights_reshaped = None

        if self.training:
            attn_probs = tf.nn.dropout(attn_weights, rate=self.dropout)

        attn_output = tf.matmul(attn_probs, value_states)

        if shape_list(attn_output) != (bsz * self.num_heads, tgt_len, self.head_dim):
            raise ValueError(
                f"`attn_output` should be of size {(bsz, self.num_heads, tgt_len, self.head_dim)}, but is"
                f" {shape_list(attn_output)}"
            )

        attn_output = tf.reshape(attn_output, (bsz, self.num_heads, tgt_len, self.head_dim))
        attn_output = tf.transpose(attn_output, perm=(0, 2, 1, 3))
        attn_output = tf.reshape(attn_output, (bsz, tgt_len, embed_dim))

        attn_output = self.out_proj(attn_output)

        return attn_output, attn_weights_reshaped


# Copied from transformers.models.clip.modeling_tf_clip.TFCLIPEncoderLayer with CLIP->GroupViT
class TFGroupViTEncoderLayer(tf.keras.layers.Layer):
    def __init__(self, config: GroupViTConfig, **kwargs):
        super().__init__(**kwargs)

        self.embed_dim = config.hidden_size
        self.self_attn = TFGroupViTAttention(config, name="self_attn")
        self.layer_norm1 = tf.keras.layers.LayerNormalization(epsilon=config.layer_norm_eps, name="layer_norm1")
        self.mlp = TFGroupViTMLP(config, name="mlp")
        self.layer_norm2 = tf.keras.layers.LayerNormalization(epsilon=config.layer_norm_eps, name="layer_norm2")

    def call(
        self,
        hidden_states: tf.Tensor,
        attention_mask: tf.Tensor,
        causal_attention_mask: tf.Tensor,
        output_attentions: bool,
        training: bool = False,
    ) -> Tuple[tf.Tensor]:
        """
        Args:
            hidden_states (`tf.Tensor`): input to the layer of shape `(batch, seq_len, embed_dim)`
            attention_mask (`tf.Tensor`): attention mask of size
                `(batch, 1, tgt_len, src_len)` where padding elements are indicated by very large negative values.
            causal_attention_mask (`tf.Tensor`): causal attention mask of size
                `(batch, 1, tgt_len, src_len)` where padding elements are indicated by very large negative values.
            output_attentions (`bool`):
                Whether or not to return the attentions tensors of all attention layers. See `outputs` under returned
                tensors for more detail.
        """
        residual = hidden_states

        hidden_states = self.layer_norm1(inputs=hidden_states)
        attention_outputs = self.self_attn(
            hidden_states=hidden_states,
            attention_mask=attention_mask,
            causal_attention_mask=causal_attention_mask,
            output_attentions=output_attentions,
            training=training,
        )
        hidden_states = attention_outputs[0]
        hidden_states = residual + hidden_states

        residual = hidden_states
        hidden_states = self.layer_norm2(inputs=hidden_states)
        hidden_states = self.mlp(hidden_states=hidden_states)
        hidden_states = residual + hidden_states

        outputs = (hidden_states,) + attention_outputs[1:]  # add attentions if we output them

        return outputs


class TFGroupViTTextEncoder(tf.keras.layers.Layer):
    """
    Transformer encoder consisting of `config.num_hidden_layers` self-attention layers. Each layer is a
    [`TFGroupViTEncoderLayer`].

    Args:
        config: GroupViTTextConfig
    """

    def __init__(self, config: GroupViTTextConfig, **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self.layers = [TFGroupViTEncoderLayer(config) for _ in range(config.num_hidden_layers)]

    def call(
        self,
        inputs_embeds,
        attention_mask: Optional[tf.Tensor] = None,
        causal_attention_mask: Optional[tf.Tensor] = None,
        output_attentions: Optional[bool] = None,
        output_hidden_states: Optional[bool] = None,
        return_dict: Optional[bool] = None,
    ) -> Union[Tuple, TFBaseModelOutput]:
        r"""
        Args:
            inputs_embeds (`torch.FloatTensor` of shape `(batch_size, sequence_length, hidden_size)`):
                Optionally, instead of passing `input_ids` you can choose to directly pass an embedded representation.
                This is useful if you want more control over how to convert `input_ids` indices into associated vectors
                than the model's internal embedding lookup matrix.
            attention_mask (`torch.Tensor` of shape `(batch_size, sequence_length)`, *optional*):
                Mask to avoid performing attention on padding token indices. Mask values selected in `[0, 1]`:

                - 1 for tokens that are **not masked**,
                - 0 for tokens that are **masked**.

                [What are attention masks?](../glossary#attention-mask)
            causal_attention_mask (`torch.Tensor` of shape `(batch_size, sequence_length)`, *optional*):
                Causal mask for the text model. Mask values selected in `[0, 1]`:

                - 1 for tokens that are **not masked**,
                - 0 for tokens that are **masked**.

                [What are attention masks?](../glossary#attention-mask)
            output_attentions (`bool`, *optional*):
                Whether or not to return the attentions tensors of all attention layers. See `attentions` under
                returned tensors for more detail.
            output_hidden_states (`bool`, *optional*):
                Whether or not to return the hidden states of all layers. See `hidden_states` under returned tensors
                for more detail.
            return_dict (`bool`, *optional*):
                Whether or not to return a [`~utils.ModelOutput`] instead of a plain tuple.
        """
        output_attentions = output_attentions if output_attentions is not None else self.config.output_attentions
        output_hidden_states = (
            output_hidden_states if output_hidden_states is not None else self.config.output_hidden_states
        )
        return_dict = return_dict if return_dict is not None else self.config.use_return_dict

        encoder_states = () if output_hidden_states else None
        all_attentions = () if output_attentions else None

        hidden_states = inputs_embeds
        for idx, encoder_layer in enumerate(self.layers):
            if output_hidden_states:
                encoder_states = encoder_states + (hidden_states,)

            layer_outputs = encoder_layer(
                hidden_states,
                attention_mask,
                causal_attention_mask,
                output_attentions=output_attentions,
            )
            hidden_states = layer_outputs[0]

            if output_attentions:
                all_attentions = all_attentions + (layer_outputs[1],)

        if output_hidden_states:
            encoder_states = encoder_states + (hidden_states,)

        if not return_dict:
            return tuple(v for v in [hidden_states, encoder_states, all_attentions] if v is not None)
        return TFBaseModelOutput(
            last_hidden_state=hidden_states, hidden_states=encoder_states, attentions=all_attentions
        )


class TFGroupViTVisionEncoder(tf.keras.layers.Layer):
    def __init__(self, config: GroupViTVisionConfig, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config = config
        self.stages = [
            TFGroupViTStage(
                config=config,
                depth=config.depths[i],
                num_group_token=config.num_group_tokens[i],
                num_output_group=config.num_output_groups[i],
                num_prev_group_token=config.num_output_groups[i - 1] if i > 0 else 0,
            )
            for i in range(len(config.depths))
        ]

    def call(
        self,
        hidden_states: tf.Tensor,
        output_hidden_states: Optional[bool] = None,
        output_attentions: Optional[bool] = None,
        return_dict: Optional[bool] = None,
    ) -> Union[tuple, TFBaseModelOutput]:

        output_attentions = output_attentions if output_attentions is not None else self.config.output_attentions
        output_hidden_states = (
            output_hidden_states if output_hidden_states is not None else self.config.output_hidden_states
        )
        return_dict = return_dict if return_dict is not None else self.config.use_return_dict

        all_hidden_states = () if output_hidden_states else None
        all_groupings = () if output_attentions else None

        group_tokens = None

        for i, stage in enumerate(self.stages):
            if output_hidden_states:
                all_hidden_states = all_hidden_states + (hidden_states,)

            layer_outputs = stage(hidden_states, group_tokens, output_attentions)

            hidden_states = layer_outputs[0]
            group_tokens = layer_outputs[1]

            if output_attentions and layer_outputs[2] is not None:
                all_groupings = all_groupings + (layer_outputs[2],)

        if output_hidden_states:
            all_hidden_states = all_hidden_states + (hidden_states,)

        if not return_dict:
            return tuple(v for v in [hidden_states, all_hidden_states, all_groupings] if v is not None)
        return TFBaseModelOutput(
            last_hidden_state=hidden_states, hidden_states=all_hidden_states, attentions=all_groupings
        )


# Copied from transformers.models.clip.modeling_tf_clip.TFCLIPTextTransformer with CLIPText->GroupViTText, CLIPEncoder->GroupViTTextEncoder
class TFGroupViTTextTransformer(tf.keras.layers.Layer):
    def __init__(self, config: GroupViTTextConfig, **kwargs):
        super().__init__(**kwargs)

        self.embeddings = TFGroupViTTextEmbeddings(config, name="embeddings")
        self.encoder = TFGroupViTTextEncoder(config, name="encoder")
        self.final_layer_norm = tf.keras.layers.LayerNormalization(
            epsilon=config.layer_norm_eps, name="final_layer_norm"
        )

    def call(
        self,
        input_ids: TFModelInputType,
        attention_mask: tf.Tensor,
        position_ids: tf.Tensor,
        output_attentions: bool,
        output_hidden_states: bool,
        return_dict: bool,
        training: bool = False,
    ) -> Union[TFBaseModelOutputWithPooling, Tuple[tf.Tensor]]:
        input_shape = shape_list(input_ids)

        embedding_output = self.embeddings(input_ids=input_ids, position_ids=position_ids)

        batch_size, seq_length = input_shape
        # CLIP's text model uses causal mask, prepare it here.
        # https://github.com/openai/CLIP/blob/cfcffb90e69f37bf2ff1e988237a0fbe41f33c04/clip/model.py#L324
        causal_attention_mask = self._build_causal_attention_mask(batch_size, seq_length, dtype=embedding_output.dtype)

        # check attention mask and invert
        # [bsz, seq_len] -> [bsz, 1, tgt_seq_len, src_seq_len]
        attention_mask = _expand_mask(attention_mask)

        encoder_outputs = self.encoder(
            hidden_states=embedding_output,
            attention_mask=attention_mask,
            causal_attention_mask=causal_attention_mask,
            output_attentions=output_attentions,
            output_hidden_states=output_hidden_states,
            return_dict=return_dict,
            training=training,
        )

        sequence_output = encoder_outputs[0]
        sequence_output = self.final_layer_norm(inputs=sequence_output)

        # text_embeds.shape = [batch_size, n_ctx, transformer.width]
        # take features from the eot embedding (eot_token is the highest number in each sequence)
        pooled_output = tf.gather_nd(
            params=sequence_output,
            indices=tf.stack(
                values=(tf.range(input_shape[0], dtype=tf.int64), tf.math.argmax(input_ids, axis=-1)), axis=1
            ),
        )

        if not return_dict:
            return (sequence_output, pooled_output) + encoder_outputs[1:]

        return TFBaseModelOutputWithPooling(
            last_hidden_state=sequence_output,
            pooler_output=pooled_output,
            hidden_states=encoder_outputs.hidden_states,
            attentions=encoder_outputs.attentions,
        )

    def _build_causal_attention_mask(self, batch_size, seq_length, dtype=tf.float32):
        # It is possible with an unspecified sequence length for seq_length to be
        # a runtime value, which is unsupported by tf.constant. Per the TensorFlow
        # docs, tf.fill can handle runtime dynamic shapes:
        # https://www.tensorflow.org/api_docs/python/tf/fill
        diag = tf.cast(tf.fill((seq_length,), 0.0), dtype)

        # set an additive 2D attention mask with all places being masked
        to_mask = tf.cast(tf.fill((seq_length, seq_length), -10000.0), dtype)

        # set diagonal & lower triangular parts to 0 (i.e. the places not to be masked)
        # TIP: think the 2D matrix as the space of (query_seq, key_seq)
        to_mask = tf.linalg.band_part(to_mask, 0, -1)
        # to_mask = tf.linalg.band_part(to_mask, -1, 0)
        to_mask = tf.linalg.set_diag(to_mask, diagonal=diag)

        return tf.broadcast_to(input=to_mask, shape=(batch_size, 1, seq_length, seq_length))


class TFGroupViTVisionTransformer(tf.keras.layers.Layer):
    def __init__(self, config: GroupViTVisionConfig):
        super().__init__()
        self.config = config
        embed_dim = config.hidden_size

        self.embeddings = TFGroupViTVisionEmbeddings(config, name="embeddings")
        self.encoder = TFGroupViTVisionEncoder(config, name="encoder")
        self.layernorm = tf.keras.layers.LayerNormalization(
            epsilon=config.layer_norm_eps, name="layernorm"
        )

    @add_start_docstrings_to_model_forward(GROUPVIT_VISION_INPUTS_DOCSTRING)
    @replace_return_docstrings(output_type=TFBaseModelOutputWithPooling, config_class=GroupViTVisionConfig)
    def call(
        self,
        pixel_values: Optional[tf.Tensor] = None,
        output_hidden_states: Optional[bool] = None,
        output_attentions: Optional[bool] = None,
        return_dict: Optional[bool] = None,
    ) -> Union[Tuple, TFBaseModelOutputWithPooling]:
        r"""
        Returns:

        """
        output_attentions = output_attentions if output_attentions is not None else self.config.output_attentions
        output_hidden_states = (
            output_hidden_states if output_hidden_states is not None else self.config.output_hidden_states
        )
        return_dict = return_dict if return_dict is not None else self.config.use_return_dict

        if pixel_values is None:
            raise ValueError("You have to specify pixel_values")

        hidden_states = self.embeddings(pixel_values)

        encoder_outputs = self.encoder(
            hidden_states=hidden_states,
            output_hidden_states=output_hidden_states,
            output_attentions=output_attentions,
            return_dict=return_dict,
        )

        last_hidden_state = encoder_outputs[0]

        # normalize the last hidden state
        last_hidden_state = self.layernorm(last_hidden_state)
        pooled_output = tf.math.reduce_mean(last_hidden_state, axis=1)

        if not return_dict:
            return (last_hidden_state, pooled_output) + encoder_outputs[1:]

        return TFBaseModelOutputWithPooling(
            last_hidden_state=last_hidden_state,
            pooler_output=pooled_output,
            hidden_states=encoder_outputs.hidden_states,
            attentions=encoder_outputs.attentions,
        )


# Copied from transformers.models.clip.modeling_tf_clip.TFCLIPTextMainLayer with CLIPText->GroupViTText
@keras_serializable
class TFGroupViTTextMainLayer(tf.keras.layers.Layer):
    config_class = GroupViTTextConfig

    def __init__(self, config: GroupViTTextConfig, **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self.text_model = TFGroupViTTextTransformer(config, name="text_model")

    def get_input_embeddings(self) -> tf.keras.layers.Layer:
        return self.text_model.embeddings

    def set_input_embeddings(self, value: tf.Variable):
        self.text_model.embeddings.weight = value
        self.text_model.embeddings.vocab_size = shape_list(value)[0]

    @unpack_inputs
    def call(
        self,
        input_ids: Optional[TFModelInputType] = None,
        attention_mask: Optional[Union[np.ndarray, tf.Tensor]] = None,
        position_ids: Optional[Union[np.ndarray, tf.Tensor]] = None,
        output_attentions: Optional[bool] = None,
        output_hidden_states: Optional[bool] = None,
        return_dict: Optional[bool] = None,
        training: bool = False,
    ) -> Union[TFBaseModelOutputWithPooling, Tuple[tf.Tensor]]:
        if input_ids is None:
            raise ValueError("You have to specify input_ids")

        input_shape = shape_list(input_ids)

        if attention_mask is None:
            attention_mask = tf.fill(dims=input_shape, value=1)

        text_model_outputs = self.text_model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            position_ids=position_ids,
            output_attentions=output_attentions,
            output_hidden_states=output_hidden_states,
            return_dict=return_dict,
            training=training,
        )

        return text_model_outputs


# Copied from transformers.models.clip.modeling_tf_clip.TFCLIPVisionMainLayer with CLIPVision->GroupViTVision
@keras_serializable
class TFCLIPVisionMainLayer(tf.keras.layers.Layer):
    config_class = GroupViTVisionConfig

    def __init__(self, config: GroupViTVisionConfig, **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self.vision_model = TFGroupViTVisionTransformer(config, name="vision_model")

    def get_input_embeddings(self) -> tf.keras.layers.Layer:
        return self.vision_model.embeddings

    @unpack_inputs
    def call(
        self,
        pixel_values: Optional[TFModelInputType] = None,
        output_attentions: Optional[bool] = None,
        output_hidden_states: Optional[bool] = None,
        return_dict: Optional[bool] = None,
        training: bool = False,
    ) -> Union[TFBaseModelOutputWithPooling, Tuple[tf.Tensor]]:

        if pixel_values is None:
            raise ValueError("You have to specify pixel_values")

        vision_model_outputs = self.vision_model(
            pixel_values=pixel_values,
            output_attentions=output_attentions,
            output_hidden_states=output_hidden_states,
            return_dict=return_dict,
            training=training,
        )

        return vision_model_outputs


@keras_serializable
class TFGroupViTMainLayer(tf.keras.layers.Layer):
    config_class = GroupViTConfig

    def __init__(self, config: GroupViTConfig, **kwargs):
        super().__init__(**kwargs)

        if not isinstance(config.text_config, GroupViTTextConfig):
            raise ValueError(
                "config.text_config is expected to be of type GroupViTTextConfig but is of type"
                f" {type(config.text_config)}."
            )

        if not isinstance(config.vision_config, GroupViTVisionConfig):
            raise ValueError(
                "config.vision_config is expected to be of type GroupViTVisionConfig but is of type"
                f" {type(config.vision_config)}."
            )

        self.config = config

        text_config = config.text_config
        vision_config = config.vision_config

        self.projection_dim = config.projection_dim
        self.projection_intermediate_dim = config.projection_intermediate_dim
        self.text_embed_dim = text_config.hidden_size
        self.vision_embed_dim = vision_config.hidden_size

        self.text_model = TFGroupViTTextTransformer(text_config, name="text_model")
        self.vision_model = TFGroupViTVisionTransformer(vision_config, name="vision_model")

        self.visual_projection = tf.keras.Sequential([
            tf.keras.layers.Desne(self.projection_intermediate_dim),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.ReLU(),
            tf.keras.layers.Dense(self.projection_dim),
        ])
        self.text_projection = tf.keras.Sequential([
            tf.keras.layers.Desne(self.projection_intermediate_dim),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.ReLU(),
            tf.keras.layers.Dense(self.projection_dim),
        ])

    def build(self, input_shape: tf.TensorShape):

        self.logit_scale = self.add_weight(
            shape=(1,),
            initializer=tf.keras.initializers.Constant(self.config.logit_scale_init_value),
            trainable=True,
            name="logit_scale",
        )

        super().build(input_shape)

    @unpack_inputs
    def get_text_features(
        self,
        input_ids: Optional[TFModelInputType] = None,
        attention_mask: Optional[Union[np.ndarray, tf.Tensor]] = None,
        position_ids: Optional[Union[np.ndarray, tf.Tensor]] = None,
        output_attentions: Optional[bool] = None,
        output_hidden_states: Optional[bool] = None,
        return_dict: Optional[bool] = None,
        training: bool = False,
    ) -> tf.Tensor:

        if input_ids is None:
            raise ValueError("You have to specify either input_ids")

        input_shape = shape_list(input_ids)

        if attention_mask is None:
            attention_mask = tf.fill(dims=input_shape, value=1)

        text_outputs = self.text_model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            position_ids=position_ids,
            output_attentions=output_attentions,
            output_hidden_states=output_hidden_states,
            return_dict=return_dict,
            training=training,
        )

        pooled_output = text_outputs[1]
        text_features = self.text_projection(inputs=pooled_output)

        return text_features

    @unpack_inputs
    def get_image_features(
        self,
        pixel_values: Optional[TFModelInputType] = None,
        output_attentions: Optional[bool] = None,
        output_hidden_states: Optional[bool] = None,
        return_dict: Optional[bool] = None,
        training: bool = False,
    ) -> tf.Tensor:
        if pixel_values is None:
            raise ValueError("You have to specify pixel_values")

        vision_outputs = self.vision_model(
            pixel_values=pixel_values,
            output_attentions=output_attentions,
            output_hidden_states=output_hidden_states,
            return_dict=return_dict,
            training=training,
        )

        pooled_output = vision_outputs[1]  # pooled_output
        image_features = self.visual_projection(inputs=pooled_output)

        return image_features

    @unpack_inputs
    def call(
        self,
        input_ids: Optional[tf.Tensor] = None,
        pixel_values: Optional[tf.Tensor] = None,
        attention_mask: Optional[tf.Tensor] = None,
        position_ids: Optional[tf.Tensor] = None,
        return_loss: Optional[bool] = None,
        output_attentions: Optional[bool] = None,
        output_hidden_states: Optional[bool] = None,
        output_segmentation: Optional[bool] = None,
        return_dict: Optional[bool] = None,
    ) -> Union[Tuple, TFGroupViTModelOutput]:

        # Use GROUPVIT model's config for some fields (if specified) instead of those of vision & text components.
        output_attentions = output_attentions if output_attentions is not None else self.config.output_attentions
        output_segmentation = (
            output_segmentation if output_segmentation is not None else self.config.output_segmentation
        )
        if output_segmentation:
            output_attentions = True
        output_hidden_states = (
            output_hidden_states if output_hidden_states is not None else self.config.output_hidden_states
        )
        return_dict = return_dict if return_dict is not None else self.config.use_return_dict

        vision_outputs = self.vision_model(
            pixel_values=pixel_values,
            output_attentions=output_attentions,
            output_hidden_states=output_hidden_states,
            return_dict=return_dict,
        )

        text_outputs = self.text_model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            position_ids=position_ids,
            output_attentions=output_attentions,
            output_hidden_states=output_hidden_states,
            return_dict=return_dict,
        )

        image_embeds = vision_outputs[1]
        image_embeds = self.visual_projection(image_embeds)

        text_embeds = text_outputs[1]
        text_embeds = self.text_projection(text_embeds)

        # normalized features
        image_embeds = image_embeds / tf.norm(image_embeds, ord="euclidean", axis=-1, keepdims=True)
        text_embeds = text_embeds / tf.norm(text_embeds, ord="euclidean", axis=-1, keepdims=True)

        # cosine similarity as logits
        logit_scale = self.logit_scale.exp()
        logits_per_text = tf.matmul(text_embeds, image_embeds, transpose_b=True) * logit_scale
        logits_per_image = tf.transpose(logits_per_text)

        seg_logits = None
        if output_segmentation:
            # grouped features
            # [batch_size_image, num_group, hidden_size]
            image_group_embeds = vision_outputs[0]
            # [batch_size_image*num_group, hidden_size]
            image_group_embeds = self.visual_projection(
                tf.reshape(image_group_embeds, shape=(-1, shape_list(image_group_embeds)[-1]))
            )
            if output_hidden_states:
                attentions = vision_outputs[3]
            else:
                attentions = vision_outputs[2]
            # [batch_size_image, num_group, height, width]
            grouping = get_grouping_from_attentions(attentions, pixel_values.shape[2:])

            # normalized features
            image_group_embeds = image_group_embeds / image_group_embeds.norm(dim=-1, keepdim=True)
            # [batch_size_image x num_group, batch_size_text]
            logits_per_image_group = tf.matmul(image_group_embeds, text_embeds, transpose_b=True) * logit_scale
            # [batch_size_image, batch_size_text, num_group]
            logits_per_image_group = tf.reshape(logits_per_image_group,
                shape=(image_embeds.shape[0], -1, text_embeds.shape[0])
            )
            logits_per_image_group = tf.transpose(logits_per_image_group, perm=(0, 2, 1))

            # [batch_size_image, batch_size_text, height x width]
            flatten_grouping = tf.reshape(
                grouping,
                shape=(shape_list(grouping)[0], shape_list(grouping)[1], -1)
            )

            # [batch_size_image, batch_size_text, height, width]
            seg_logits = tf.matmul(logits_per_image_group, flatten_grouping) * logit_scale
            seg_logits = seg_logits.reshape(
                seg_logits.shape[0], seg_logits.shape[1], grouping.shape[2], grouping.shape[3]
            )

        loss = None
        if return_loss:
            loss = groupvit_loss(logits_per_text)

        if not return_dict:
            if seg_logits is not None:
                output = (
                    logits_per_image,
                    logits_per_text,
                    seg_logits,
                    text_embeds,
                    image_embeds,
                    text_outputs,
                    vision_outputs,
                )
            else:
                output = (logits_per_image, logits_per_text, text_embeds, image_embeds, text_outputs, vision_outputs)
            return ((loss,) + output) if loss is not None else output

        return TFGroupViTModelOutput(
            loss=loss,
            logits_per_image=logits_per_image,
            logits_per_text=logits_per_text,
            segmentation_logits=seg_logits,
            text_embeds=text_embeds,
            image_embeds=image_embeds,
            text_model_output=text_outputs,
            vision_model_output=vision_outputs,
        )


class TFGroupViTPreTrainedModel(TFPreTrainedModel):
    """
    An abstract class to handle weights initialization and a simple interface for downloading and loading pretrained
    models.
    """

    config_class = GroupViTConfig
    base_model_prefix = "groupvit"


GROUPVIT_START_DOCSTRING = r"""
    
    This model inherits from [`TFPreTrainedModel`]. Check the superclass documentation for the generic methods the
    library implements for all its model (such as downloading or saving, resizing the input embeddings, pruning heads
    etc.)

    This model is also a [tf.keras.Model](https://www.tensorflow.org/api_docs/python/tf/keras/Model) subclass. Use it
    as a regular TF 2.0 Keras Model and refer to the TF 2.0 documentation for all matter related to general usage and
    behavior.

    <Tip>

    TF 2.0 models accepts two formats as inputs:

    - having all inputs as keyword arguments (like PyTorch models), or
    - having all inputs as a list, tuple or dict in the first positional arguments.

    This second option is useful when using [`tf.keras.Model.fit`] method which currently requires having all the
    tensors in the first argument of the model call function: `model(inputs)`.

    If you choose this second option, there are three possibilities you can use to gather all the input Tensors in the
    first positional argument :

    - a single Tensor with `input_ids` only and nothing else: `model(input_ids)`
    - a list of varying length with one or several input Tensors IN THE ORDER given in the docstring:
      `model([input_ids, attention_mask])` or `model([input_ids, attention_mask, token_type_ids])`
    - a dictionary with one or several input Tensors associated to the input names given in the docstring:
      `model({"input_ids": input_ids, "token_type_ids": token_type_ids})`

    </Tip>

    Parameters:
        config ([`GroupViTConfig`]): Model configuration class with all the parameters of the model.
            Initializing with a config file does not load the weights associated with the model, only the
            configuration. Check out the [`~PreTrainedModel.from_pretrained`] method to load the model weights.
"""

GROUPVIT_TEXT_INPUTS_DOCSTRING = r"""
    Args:
        input_ids (`torch.LongTensor` of shape `(batch_size, sequence_length)`):
            Indices of input sequence tokens in the vocabulary. Padding will be ignored by default should you provide
            it.

            Indices can be obtained using [`CLIPTokenizer`]. See [`PreTrainedTokenizer.encode`] and
            [`PreTrainedTokenizer.__call__`] for details.

            [What are input IDs?](../glossary#input-ids)
        attention_mask (`torch.Tensor` of shape `(batch_size, sequence_length)`, *optional*):
            Mask to avoid performing attention on padding token indices. Mask values selected in `[0, 1]`:

            - 1 for tokens that are **not masked**,
            - 0 for tokens that are **masked**.

            [What are attention masks?](../glossary#attention-mask)
        position_ids (`torch.LongTensor` of shape `(batch_size, sequence_length)`, *optional*):
            Indices of positions of each input sequence tokens in the position embeddings. Selected in the range `[0,
            config.max_position_embeddings - 1]`.

            [What are position IDs?](../glossary#position-ids)
        output_attentions (`bool`, *optional*):
            Whether or not to return the attentions tensors of all attention layers. See `attentions` under returned
            tensors for more detail.
        output_hidden_states (`bool`, *optional*):
            Whether or not to return the hidden states of all layers. See `hidden_states` under returned tensors for
            more detail.
        return_dict (`bool`, *optional*):
            Whether or not to return a [`~utils.ModelOutput`] instead of a plain tuple.
"""

GROUPVIT_VISION_INPUTS_DOCSTRING = r"""
    Args:
        pixel_values (`torch.FloatTensor` of shape `(batch_size, num_channels, height, width)`):
            Pixel values. Padding will be ignored by default should you provide it. Pixel values can be obtained using
            [`CLIPFeatureExtractor`]. See [`CLIPFeatureExtractor.__call__`] for details.
        output_attentions (`bool`, *optional*):
            Whether or not to return the attentions tensors of all attention layers. See `attentions` under returned
            tensors for more detail.
        output_hidden_states (`bool`, *optional*):
            Whether or not to return the hidden states of all layers. See `hidden_states` under returned tensors for
            more detail.
        return_dict (`bool`, *optional*):
            Whether or not to return a [`~utils.ModelOutput`] instead of a plain tuple.
"""

GROUPVIT_INPUTS_DOCSTRING = r"""
    Args:
        input_ids (`torch.LongTensor` of shape `(batch_size, sequence_length)`):
            Indices of input sequence tokens in the vocabulary. Padding will be ignored by default should you provide
            it.

            Indices can be obtained using [`CLIPTokenizer`]. See [`PreTrainedTokenizer.encode`] and
            [`PreTrainedTokenizer.__call__`] for details.

            [What are input IDs?](../glossary#input-ids)
        attention_mask (`torch.Tensor` of shape `(batch_size, sequence_length)`, *optional*):
            Mask to avoid performing attention on padding token indices. Mask values selected in `[0, 1]`:

            - 1 for tokens that are **not masked**,
            - 0 for tokens that are **masked**.

            [What are attention masks?](../glossary#attention-mask)
        position_ids (`torch.LongTensor` of shape `(batch_size, sequence_length)`, *optional*):
            Indices of positions of each input sequence tokens in the position embeddings. Selected in the range `[0,
            config.max_position_embeddings - 1]`.

            [What are position IDs?](../glossary#position-ids)
        pixel_values (`torch.FloatTensor` of shape `(batch_size, num_channels, height, width)`):
            Pixel values. Pixel values can be obtained using [`CLIPFeatureExtractor`]. See
            [`CLIPFeatureExtractor.__call__`] for details.
        return_loss (`bool`, *optional*):
            Whether or not to return the contrastive loss.
        output_attentions (`bool`, *optional*):
            Whether or not to return the attentions tensors of all attention layers. See `attentions` under returned
            tensors for more detail.
        output_hidden_states (`bool`, *optional*):
            Whether or not to return the hidden states of all layers. See `hidden_states` under returned tensors for
            more detail.
        return_dict (`bool`, *optional*):
            Whether or not to return a [`~utils.ModelOutput`] instead of a plain tuple.
"""


class TFGroupViTVisionModel(TFGroupViTPreTrainedModel):
    config_class = GroupViTVisionConfig
    main_input_name = "pixel_values"

    def __init__(self, config: GroupViTVisionConfig, *inputs, **kwargs):
        super().__init__(config, *inputs, **kwargs)

        self.group_vit = TFCLIPVisionMainLayer(config, name="group_vit")

    @property
    def dummy_inputs(self) -> Dict[str, tf.Tensor]:
        """
        Dummy inputs to build the network.

        Returns:
            `Dict[str, tf.Tensor]`: The dummy inputs.
        """
        VISION_DUMMY_INPUTS = tf.random.uniform(
            shape=(len(DUMMY_INPUTS), 3, self.config.image_size, self.config.image_size), dtype=tf.float32
        )
        return {"pixel_values": VISION_DUMMY_INPUTS}

    @tf.function(
        input_signature=[
            {
                "pixel_values": tf.TensorSpec((None, None, None, None), tf.float32, name="pixel_values"),
            }
        ]
    )
    def serving(self, inputs: Dict[str, tf.Tensor]) -> TFBaseModelOutputWithPooling:
        """
        Method used for serving the model.

        Args:
            inputs (`Dict[str, tf.Tensor]`):
                The input of the saved model as a dictionary of tensors.
        """
        output = self.call(inputs)

        return self.serving_output(output)

    @unpack_inputs
    @add_start_docstrings_to_model_forward(GROUPVIT_VISION_INPUTS_DOCSTRING)
    @replace_return_docstrings(output_type=TFBaseModelOutputWithPooling, config_class=GroupViTVisionConfig)
    def call(
        self,
        pixel_values: Optional[TFModelInputType] = None,
        output_attentions: Optional[bool] = None,
        output_hidden_states: Optional[bool] = None,
        return_dict: Optional[bool] = None,
        training: Optional[bool] = False,
    ) -> Union[TFBaseModelOutputWithPooling, Tuple[tf.Tensor]]:
        r"""
        Returns:

        """

        outputs = self.group_vit(
            pixel_values=pixel_values,
            output_attentions=output_attentions,
            output_hidden_states=output_hidden_states,
            return_dict=return_dict,
            training=training,
        )

        return outputs

    def serving_output(self, output: TFBaseModelOutputWithPooling) -> TFBaseModelOutputWithPooling:
        hs = tf.convert_to_tensor(output.hidden_states) if self.config.output_hidden_states else None
        attns = tf.convert_to_tensor(output.attentions) if self.config.output_attentions else None

        return TFBaseModelOutputWithPooling(
            last_hidden_state=output.last_hidden_state,
            pooler_output=output.pooler_output,
            hidden_states=hs,
            attentions=attns,
        )


class TFGroupViTTextModel(TFGroupViTPreTrainedModel):
    config_class = GroupViTTextConfig

    def __init__(self, config: GroupViTTextConfig, *inputs, **kwargs):
        super().__init__(config, *inputs, **kwargs)

        self.group_vit = TFGroupViTTextMainLayer(config, name="group_vit")

    @unpack_inputs
    @add_start_docstrings_to_model_forward(GROUPVIT_TEXT_INPUTS_DOCSTRING.format("batch_size, sequence_length"))
    @replace_return_docstrings(output_type=TFBaseModelOutputWithPooling, config_class=GroupViTTextConfig)
    def call(
        self,
        input_ids: Optional[TFModelInputType] = None,
        attention_mask: Optional[Union[np.ndarray, tf.Tensor]] = None,
        position_ids: Optional[Union[np.ndarray, tf.Tensor]] = None,
        output_attentions: Optional[bool] = None,
        output_hidden_states: Optional[bool] = None,
        return_dict: Optional[bool] = None,
        training: Optional[bool] = False,
    ) -> Union[TFBaseModelOutputWithPooling, Tuple[tf.Tensor]]:
        r"""
        Returns:

        Examples:

        ```python
        >>> from transformers import CLIPTokenizer, GroupViTTextModel

        >>> tokenizer = CLIPTokenizer.from_pretrained("nvidia/groupvit-gcc-yfcc")
        >>> model = GroupViTTextModel.from_pretrained("nvidia/groupvit-gcc-yfcc")

        >>> inputs = tokenizer(["a photo of a cat", "a photo of a dog"], padding=True, return_tensors="pt")

        >>> outputs = model(**inputs)
        >>> last_hidden_state = outputs.last_hidden_state
        >>> pooled_output = outputs.pooler_output  # pooled (EOS token) states
        ```"""

        outputs = self.group_vit(
            input_ids=input_ids,
            attention_mask=attention_mask,
            position_ids=position_ids,
            output_attentions=output_attentions,
            output_hidden_states=output_hidden_states,
            return_dict=return_dict,
            training=training,
        )

        return outputs

    @tf.function(
        input_signature=[
            {
                "input_ids": tf.TensorSpec((None, None), tf.int32, name="input_ids"),
                "attention_mask": tf.TensorSpec((None, None), tf.int32, name="attention_mask"),
            }
        ]
    )
    def serving(self, inputs: Dict[str, tf.Tensor]) -> TFBaseModelOutputWithPooling:
        output = self.call(inputs)
        return self.serving_output(output)

    def serving_output(self, output: TFBaseModelOutputWithPooling) -> TFBaseModelOutputWithPooling:
        hs = tf.convert_to_tensor(output.hidden_states) if self.config.output_hidden_states else None
        attns = tf.convert_to_tensor(output.attentions) if self.config.output_attentions else None

        return TFBaseModelOutputWithPooling(
            last_hidden_state=output.last_hidden_state,
            pooler_output=output.pooler_output,
            hidden_states=hs,
            attentions=attns,
        )


@add_start_docstrings(GROUPVIT_START_DOCSTRING)
class TFGroupViTModel(TFGroupViTPreTrainedModel):
    config_class = GroupViTConfig

    def __init__(self, config: GroupViTConfig, *inputs, **kwargs):
        super().__init__(config, *inputs, **kwargs)

        self.group_vit = TFGroupViTMainLayer(config, name="group_vit")

    @property
    def dummy_inputs(self) -> Dict[str, tf.Tensor]:
        """
        Dummy inputs to build the network.

        Returns:
            `Dict[str, tf.Tensor]`: The dummy inputs.
        """
        VISION_DUMMY_INPUTS = tf.random.uniform(
            shape=(len(DUMMY_INPUTS), 3, self.config.vision_config.image_size, self.config.vision_config.image_size),
            dtype=tf.float32,
        )
        return {
            "input_ids": tf.constant(DUMMY_INPUTS, dtype=tf.int32),
            "pixel_values": VISION_DUMMY_INPUTS,
        }

    @tf.function(
        input_signature=[
            {
                "input_ids": tf.TensorSpec((None, None), tf.int32, name="input_ids"),
                "pixel_values": tf.TensorSpec((None, None, None, None), tf.float32, name="pixel_values"),
                "attention_mask": tf.TensorSpec((None, None), tf.int32, name="attention_mask"),
            }
        ]
    )
    def serving(self, inputs: Dict[str, tf.Tensor]) -> TFGroupViTModelOutput:
        """
        Method used for serving the model.

        Args:
            inputs (`Dict[str, tf.Tensor]`):
                The input of the saved model as a dictionary of tensors.
        """
        output = self.call(inputs)

        return self.serving_output(output)

    @unpack_inputs
    @add_start_docstrings_to_model_forward(GROUPVIT_TEXT_INPUTS_DOCSTRING.format("batch_size, sequence_length"))
    def get_text_features(
        self,
        input_ids: Optional[TFModelInputType] = None,
        attention_mask: Optional[Union[np.ndarray, tf.Tensor]] = None,
        position_ids: Optional[Union[np.ndarray, tf.Tensor]] = None,
        output_attentions: Optional[bool] = None,
        output_hidden_states: Optional[bool] = None,
        return_dict: Optional[bool] = None,
        training: bool = False,
    ) -> tf.Tensor:
        r"""
        Returns:
            text_features (`tf.Tensor` of shape `(batch_size, output_dim`): The text embeddings obtained by
            applying the projection layer to the pooled output of [`TFGroupViTTextModel`].

        Examples:

        ```python
        >>> from transformers import CLIPTokenizer, TFGroupViTModel

        >>> model = TFGroupViTModel.from_pretrained("nvidia/groupvit-gcc-yfcc")
        >>> tokenizer = CLIPTokenizer.from_pretrained("nvidia/groupvit-gcc-yfcc")

        >>> inputs = tokenizer(["a photo of a cat", "a photo of a dog"], padding=True, return_tensors="tf")
        >>> text_features = model.get_text_features(**inputs)
        ```"""

        text_features = self.group_vit.get_text_features(
            input_ids=input_ids,
            attention_mask=attention_mask,
            position_ids=position_ids,
            output_attentions=output_attentions,
            output_hidden_states=output_hidden_states,
            return_dict=return_dict,
        )

        return text_features

    @unpack_inputs
    @add_start_docstrings_to_model_forward(GROUPVIT_VISION_INPUTS_DOCSTRING)
    def get_image_features(
        self,
        pixel_values: Optional[TFModelInputType] = None,
        output_attentions: Optional[bool] = None,
        output_hidden_states: Optional[bool] = None,
        return_dict: Optional[bool] = None,
        training: bool = False,
    ) -> tf.Tensor:
        r"""
        Returns:
            image_features (`tf.Tensor` of shape `(batch_size, output_dim`): The image embeddings obtained by
            applying the projection layer to the pooled output of [`TFGroupViTVisionModel`].

        Examples:

        ```python
        >>> from PIL import Image
        >>> import requests
        >>> from transformers import AutoProcessor, TFGroupViTModel

        >>> model = TFGroupViTModel.from_pretrained("nvidia/groupvit-gcc-yfcc")
        >>> processor = AutoProcessor.from_pretrained("nvidia/groupvit-gcc-yfcc")

        >>> url = "http://images.cocodataset.org/val2017/000000039769.jpg"
        >>> image = Image.open(requests.get(url, stream=True).raw)

        >>> inputs = processor(images=image, return_tensors="tf")

        >>> image_features = model.get_image_features(**inputs)
        ```"""

        image_features = self.group_vit.get_image_features(
            pixel_values=pixel_values,
            output_attentions=output_attentions,
            output_hidden_states=output_hidden_states,
            return_dict=return_dict,
        )

        return image_features

    @unpack_inputs
    @add_start_docstrings_to_model_forward(GROUPVIT_INPUTS_DOCSTRING.format("batch_size, sequence_length"))
    @replace_return_docstrings(output_type=TFGroupViTModelOutput, config_class=GroupViTConfig)
    def call(
        self,
        input_ids: Optional[TFModelInputType] = None,
        pixel_values: Optional[TFModelInputType] = None,
        attention_mask: Optional[Union[np.ndarray, tf.Tensor]] = None,
        position_ids: Optional[Union[np.ndarray, tf.Tensor]] = None,
        return_loss: Optional[bool] = None,
        output_attentions: Optional[bool] = None,
        output_hidden_states: Optional[bool] = None,
        return_dict: Optional[bool] = None,
        training: bool = False,
    ) -> Union[GroupViTConfig, Tuple[tf.Tensor]]:
        r"""
        Returns:

        Examples:

        ```python
        >>> from PIL import Image
        >>> import requests
        >>> from transformers import AutoProcessor, TFGroupViTModel

        >>> model = TFGroupViTModel.from_pretrained("nvidia/groupvit-gcc-yfcc")
        >>> processor = AutoProcessor.from_pretrained("nvidia/groupvit-gcc-yfcc")

        >>> url = "http://images.cocodataset.org/val2017/000000039769.jpg"
        >>> image = Image.open(requests.get(url, stream=True).raw)

        >>> inputs = processor(
        ...     text=["a photo of a cat", "a photo of a dog"], images=image, return_tensors="pt", padding=True
        ... )

        >>> outputs = model(**inputs)
        >>> logits_per_image = outputs.logits_per_image  # this is the image-text similarity score
        >>> probs = logits_per_image.softmax(dim=1)  # we can take the softmax to get the label probabilities
        ```"""

        outputs = self.group_vit(
            input_ids=input_ids,
            pixel_values=pixel_values,
            attention_mask=attention_mask,
            position_ids=position_ids,
            return_loss=return_loss,
            output_attentions=output_attentions,
            output_hidden_states=output_hidden_states,
            return_dict=return_dict,
        )

        return outputs

    def serving_output(self, output: TFGroupViTModelOutput) -> TFGroupViTModelOutput:
        # TODO: As is this currently fails with saved_model=True, because
        # TensorFlow cannot trace through nested dataclasses. Reference:
        # https://github.com/huggingface/transformers/pull/16886
        return output
