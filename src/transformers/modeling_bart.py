# coding=utf-8
# Copyright 2020 The Facebook AI Research Team Authors and The HuggingFace Inc. team.
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
"""PyTorch BART model, ported from the fairseq repo."""

import logging
import random
from typing import Dict, List, Optional, Tuple

import torch
import torch.nn.functional as F
from torch import Tensor, nn

from .configuration_bart import BartConfig
from .docs_bart import BART_START_DOCSTRING
from .file_utils import add_start_docstrings
from .modeling_utils import PreTrainedModel, create_position_ids_from_input_ids


logger = logging.getLogger(__name__)


BART_PRETRAINED_MODEL_ARCHIVE_MAP = {
    "bart-large": "https://s3.amazonaws.com/models.huggingface.co/bert/facebook/bart-large/pytorch_model.bin",
    "bart-large-mnli": "https://s3.amazonaws.com/models.huggingface.co/bert/facebook/bart-large-mnli/pytorch_model.bin",
}

BART_START_DOCSTRING = r"""  Ported from https://github.com/pytorch/fairseq/tree/master/examples/bart
    An encoder decoder transformer pre-trained in a text-to-text denoising generative setting.

    This model is a PyTorch `torch.nn.Module`_ sub-class. Use it as a regular PyTorch Module and
    refer to the PyTorch documentation for all matter related to general usage and behavior.

    .. _`Exploring the Limits of Transfer Learning with a Unified Text-to-Text Transformer`:
        https://arxiv.org/abs/1910.10683

    .. _`torch.nn.Module`:
        https://pytorch.org/docs/stable/nn.html#module

    Parameters:
        config (:class:`~transformers.BartConfig`): Model configuration class with all the parameters of the model.
            Initializing with a config file does not load the weights associated with the model, only the configuration.
            Check out the :meth:`~transformers.PreTrainedModel.from_pretrained` method to load the model weights.
"""

BART_INPUTS_DOCSTRING = r"""
    Inputs:
        **input_ids**: ``torch.LongTensor`` of shape ``(batch_size, sequence_length)``:
            Indices of input sequence tokens in the vocabulary. Use BartTokenizer.encode to produce them.
            Padding will be ignored by default should you provide it.
            Indices can be obtained using :class:`transformers.BartTokenizer.encode(text)`.
            Also see :func:`transformers.PreTrainedTokenizer.convert_tokens_to_ids` for details.
        **attention_mask**: (`optional`) ``torch.FloatTensor`` of shape ``(batch_size, sequence_length)``:
            Mask to avoid performing attention on padding token indices in the encoder inputs.
            Default: a mask will be created that ignore config.pad_token_id
            Mask values selected in ``[0, 1]``:
            ``1`` for tokens that are NOT MASKED, ``0`` for MASKED tokens.
        **decoder_input_ids**: (`optional`) ``torch.FloatTensor`` of shape ``(batch_size, sequence_length)``:
            only use for translation and summarization. Otherwise use the default which shifts the encoder's 
            input_ids right

        **decoder_attention_mask**  `optional`) ``torch.FloatTensor`` of shape ``(batch_size, sequence_length)``:
           default behavior ignore pad tokens and future tokens.
             See diagram 1 in the paper for more info on the default strategy
             
    see `prepare_bart_inputs` for more information on the default behavior.

"""

def prepare_bart_inputs(
    config, input_ids, attention_mask=None, decoder_input_ids=None, decoder_attn_mask=None,
):
    """Prepare masks that ignore padding tokens for both encoder and decoder and a causal lm mask for the decoder if
    none are provided.
    This mimics the default behavior in fairseq. To override it pass in masks."""
    pad_token_id = config.pad_token_id
    need_causal_mask = not config.output_past
    if attention_mask is None:  # ignore pad tokens in input_ids
        attention_mask = make_padding_mask(input_ids, padding_idx=pad_token_id)
    if decoder_input_ids is None:
        decoder_input_ids = shift_tokens_right(input_ids, pad_token_id)
    if decoder_attn_mask is None:

        bsz, tgt_len = input_ids.size()[:2]
        decoder_padding_mask = make_padding_mask(input_ids, pad_token_id)
        tgt_len = input_ids.shape[1]
        # encoder_attn_mask = _combine_masks(encoder_attn_mask, )
        if need_causal_mask:
            causal_lm_mask = torch.triu(fill_with_neg_inf(torch.zeros(tgt_len, tgt_len)), 1)
        else:
            causal_lm_mask = None
        new_shape = (bsz, tgt_len, tgt_len)
        decoder_attn_mask = _combine_masks(decoder_padding_mask, causal_lm_mask, new_shape)
        # decoder_attention_mask.shape =  (bsz, 1, tgt_len, tgt_len)
    return attention_mask, decoder_input_ids, decoder_attn_mask


def prepare_barts_input_dict(config, input_ids, **kwargs):
    attention_mask, decoder_input_ids, decoder_attn_mask = prepare_bart_inputs(config, input_ids, **kwargs)
    return {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
        "decoder_attention_mask": decoder_attn_mask,
        "decoder_input_ids": decoder_input_ids,
    }


class PretrainedBartModel(PreTrainedModel):
    config_class = BartConfig
    base_model_prefix = "model"
    pretrained_model_archive_map = BART_PRETRAINED_MODEL_ARCHIVE_MAP

    def _init_weights(self, module):
        std = self.config.init_std

        # called init_bert_params in fairseq
        if isinstance(module, nn.Linear):
            module.weight.data.normal_(mean=0.0, std=std)
            if module.bias is not None:
                module.bias.data.zero_()
        if isinstance(module, nn.Embedding):
            module.weight.data.normal_(mean=0.0, std=std)
            if module.padding_idx is not None:
                module.weight.data[module.padding_idx].zero_()

    # TODO(SS): def prepare_inputs_for_generation(self, input_ids, **kwargs):

    @property
    def dummy_inputs(self):
        pad_token = 1
        input_ids = torch.Tensor(
            [
                [0, 31414, 232, 328, 740, 1140, 12695, 69, 46078, 1588, 2],
                [0, 31414, 232, 328, 740, 1140, 12695, 69, 46078, 2, pad_token],
            ]
        ).long()
        attention_mask, decoder_input_ids, decoder_attn_mask = prepare_bart_inputs(
            self.config, input_ids, attention_mask=None, decoder_input_ids=None, decoder_attn_mask=None
        )
        dummy_inputs = {
            "decoder_input_ids": decoder_input_ids,
            "attention_mask": attention_mask,
            "input_ids": input_ids,
            "decoder_attention_mask": decoder_attn_mask,
        }
        return dummy_inputs


def _make_linear_from_emb(emb):
    vocab_size, emb_size = emb.weight.shape
    lin_layer = nn.Linear(vocab_size, emb_size, bias=False)
    lin_layer.weight.data = emb.weight.data  # .T
    return lin_layer


# Helper Functions, mostly for making masks
def _check_shapes(shape_1, shape2):
    if shape_1 != shape2:
        raise AssertionError("shape mismatch: {} != {}".format(shape_1, shape2))


def _combine_masks(key_padding_mask, attn_mask, targ_size):
    # targ_size = (bsz, tgt_len, src_len)
    a = torch.zeros(targ_size)
    b = torch.zeros(targ_size)
    if key_padding_mask is not None:  # (bsz, tgt_len) -> targ_size
        _check_shapes(key_padding_mask.shape, targ_size[:2])
        reshaped = key_padding_mask.unsqueeze(2).expand(*targ_size)
        a[reshaped] = 1e-8

    if attn_mask is not None:  # (tgt_len, src_len) -> targ_size
        _check_shapes(attn_mask.shape, targ_size[-2:])
        b = attn_mask.unsqueeze(0).expand(*targ_size)
    return (a + b).unsqueeze(1)


def shift_tokens_right(input_ids, pad_token_id):
    """Shift input ids one token to the right, and wrap the last non pad token (usually <eos>)."""
    prev_output_tokens = input_ids.clone()
    index_of_eos = (input_ids.ne(pad_token_id).sum(dim=1) - 1).unsqueeze(-1)
    prev_output_tokens[:, 0] = input_ids.gather(1, index_of_eos).squeeze()
    prev_output_tokens[:, 1:] = input_ids[:, :-1]
    return prev_output_tokens


def make_padding_mask(input_ids, padding_idx=1):
    """True for pad tokens"""
    padding_mask = input_ids.eq(padding_idx)
    if not padding_mask.any():
        padding_mask = None
    return padding_mask


# Helper Modules


class EncoderLayer(nn.Module):
    def __init__(self, config: BartConfig):
        super().__init__()
        self.embed_dim = config.d_model
        self.output_attentions = config.output_attentions
        self.self_attn = SelfAttention(
            self.embed_dim, config.encoder_attention_heads, dropout=config.attention_dropout,
        )
        self.self_attn_layer_norm = LayerNorm(self.embed_dim)
        self.dropout = config.dropout
        self.activation_fn = F.gelu
        self.activation_dropout = config.activation_dropout
        self.fc1 = nn.Linear(self.embed_dim, config.encoder_ffn_dim)
        self.fc2 = nn.Linear(config.encoder_ffn_dim, self.embed_dim)
        self.final_layer_norm = LayerNorm(self.embed_dim)

    def forward(self, x, encoder_padding_mask):
        """
        Args:
            x (Tensor): input to the layer of shape `(seq_len, batch, embed_dim)`
            encoder_padding_mask (ByteTensor): binary ByteTensor of shape
                `(batch, src_len)` where padding elements are indicated by ``1``.
            for t_tgt, t_src is excluded (or masked out), =0 means it is
            included in attention

        Returns:
            encoded output of shape `(seq_len, batch, embed_dim)`
        """
        residual = x
        x, attn_weights = self.self_attn.forward(
            query=x, key=x, value=x, key_padding_mask=encoder_padding_mask, need_weights=self.output_attentions,
        )
        x = F.dropout(x, p=self.dropout, training=self.training)
        x = residual + x
        x = self.self_attn_layer_norm(x)

        residual = x
        x = self.activation_fn(self.fc1(x))
        x = F.dropout(x, p=self.activation_dropout, training=self.training)
        x = self.fc2(x)
        x = F.dropout(x, p=self.dropout, training=self.training)
        x = residual + x
        x = self.final_layer_norm(x)
        return x, attn_weights


class BartEncoder(nn.Module):
    """
    Transformer encoder consisting of *config.encoder_layers* layers. Each layer
    is a :class:`EncoderLayer`.

    Args:
        config (argparse.Namespace): parsed command-line arguments
        dictionary (~fairseq.data.Dictionary): encoding dictionary
        embed_tokens (torch.nn.Embedding): input embedding
    """

    def __init__(self, config: BartConfig, embed_tokens):
        super().__init__()

        self.dropout = config.dropout
        self.layerdrop = config.encoder_layerdrop
        self.output_attentions = config.output_attentions
        self.output_hidden_states = config.output_hidden_states

        embed_dim = embed_tokens.embedding_dim
        self.padding_idx = embed_tokens.padding_idx
        self.max_source_positions = config.max_position_embeddings

        self.embed_tokens = embed_tokens

        self.embed_positions = LearnedPositionalEmbedding(config.max_position_embeddings, embed_dim, self.padding_idx,)
        self.layers = nn.ModuleList([EncoderLayer(config) for _ in range(config.encoder_layers)])
        self.layernorm_embedding = LayerNorm(embed_dim)

    def forward(self, input_ids=None, attention_mask=None, **unused):  # TODO(SS): this will need more
        """
        Args:
            input_ids (LongTensor): tokens in the source language of shape
                `(batch, src_len)`
            attention_mask (torch.LongTensor):
        Returns:
            namedtuple:
                - **encoder_hidden_states** (Tensor): the last encoder layer's output of
                  shape `(src_len, batch, embed_dim)`
                - **encoder_attn_mask** (ByteTensor): the positions of
                  padding elements of shape `(batch, src_len)`
                - **encoder_states** (List[Tensor]): all intermediate
                  hidden states of shape `(src_len, batch, embed_dim)`.
                  Only populated if *return_all_hiddens* is True.
        """

        inputs_embeds = self.embed_tokens(input_ids)
        embed_pos = self.embed_positions(input_ids)
        x = inputs_embeds + embed_pos
        x = self.layernorm_embedding(x)
        x = F.dropout(x, p=self.dropout, training=self.training)

        # B x T x C -> T x B x C
        x = x.transpose(0, 1)

        encoder_states, all_attentions = [], []

        # encoder layers
        for encoder_layer in self.layers:

            if self.output_hidden_states:
                encoder_states.append(x)
            # add LayerDrop (see https://arxiv.org/abs/1909.11556 for description)
            dropout_probability = random.uniform(0, 1)
            if self.training and (dropout_probability < self.layerdrop):  # skip the layer
                attn = None
            else:
                x, attn = encoder_layer.forward(x, attention_mask)

            if self.output_attentions:
                all_attentions.append(attn)

        if self.output_hidden_states:
            encoder_states.append(x)
        if self.output_attentions:
            assert len(all_attentions) == len(self.layers)  # TODO(DELETEME)

        encoder_states = [hidden_state.transpose(0, 1) for hidden_state in encoder_states]

        return x, encoder_states, all_attentions


class DecoderLayer(nn.Module):
    def __init__(self, config: BartConfig):
        super().__init__()
        self.embed_dim = config.d_model
        self.self_attn = SelfAttention(
            embed_dim=self.embed_dim, num_heads=config.decoder_attention_heads, dropout=config.attention_dropout,
        )
        self.dropout = config.dropout
        self.activation_fn = F.gelu
        self.activation_dropout = config.activation_dropout

        self.self_attn_layer_norm = LayerNorm(self.embed_dim)
        self.encoder_attn = SelfAttention(
            self.embed_dim,
            config.decoder_attention_heads,
            dropout=config.attention_dropout,
            encoder_decoder_attention=True,
        )
        self.encoder_attn_layer_norm = LayerNorm(self.embed_dim)
        self.fc1 = nn.Linear(self.embed_dim, config.decoder_ffn_dim)
        self.fc2 = nn.Linear(config.decoder_ffn_dim, self.embed_dim)
        self.final_layer_norm = LayerNorm(self.embed_dim)

    def forward(
        self,
        x,
        encoder_hidden_states,
        encoder_attn_mask=None,
        cached_states=None,
        attention_mask=None,
        need_attn_weights=False,
    ):
        """
        Args:
            x (Tensor): input to the layer of shape `(seq_len, batch, embed_dim)`
            encoder_attn_mask (ByteTensor, optional): binary
                ByteTensor of shape `(batch, src_len)` where padding
                elements are indicated by ``1``.
            need_attn_weights (bool, optional): return attention weights
                for each head (default: return average over heads).

        Returns:
            encoded output of shape `(seq_len, batch, embed_dim)`
        """
        if cached_states is None:
            prev_self_attn_state, prev_attn_state = (None, None)
            cached_states = {}
        else:
            prev_self_attn_state, prev_attn_state = cached_states["self_attn"], cached_states["encoder_decoder_attn"]

        residual = x
        if prev_self_attn_state is not None:
            saved_state = prev_self_attn_state
            self.self_attn._update_layer_cache(cached_states, saved_state)
        y = x  # TODO(SS): figure out why fairseq did this, then hopefully delete it

        x, self_attn_weights = self.self_attn.forward(
            query=x,
            key=y,
            value=y,
            cached_states=cached_states,
            need_weights=need_attn_weights,
            attn_mask=attention_mask,
        )
        x = F.dropout(x, p=self.dropout, training=self.training)
        x = residual + x
        x = self.self_attn_layer_norm(x)
        residual = x
        assert self.encoder_attn.attn_key != self.self_attn.attn_key
        if prev_attn_state is not None:
            saved_state = prev_attn_state
            self.encoder_attn._update_layer_cache(cached_states, saved_state)
        x, encoder_attn_weights = self.encoder_attn.forward(
            query=x,
            key=encoder_hidden_states,  # could be None
            value=encoder_hidden_states,
            key_padding_mask=encoder_attn_mask,
            cached_states=cached_states,
            static_kv=True,
            need_weights=False,  # not returning it so why compute it
        )
        x = F.dropout(x, p=self.dropout, training=self.training)
        x = residual + x

        x = self.encoder_attn_layer_norm(x)

        residual = x
        x = self.activation_fn(self.fc1(x))
        x = F.dropout(x, p=self.activation_dropout, training=self.training)
        x = self.fc2(x)
        x = F.dropout(x, p=self.dropout, training=self.training)
        x = residual + x
        x = self.final_layer_norm(x)
        return (
            x,
            self_attn_weights,
            cached_states,
        )  # just self_attn weights for now, following t5, cached_states = cache for decoding

    def _past_to_dict(self, prev_attn_state):
        prev_key, prev_value = prev_attn_state[:2]
        saved_state = {"prev_key": prev_key, "prev_value": prev_value}
        if len(prev_attn_state) >= 3:
            saved_state["prev_key_padding_mask"] = prev_attn_state[2]
        return saved_state


class BartDecoder(nn.Module):
    """
    Transformer decoder consisting of *config.decoder_layers* layers. Each layer
    is a :class:`DecoderLayer`.
    Args:
        config: BartConfig
        embed_tokens (torch.nn.Embedding): output embedding
    """

    def __init__(self, config: BartConfig, embed_tokens: nn.Embedding):
        super().__init__()
        self.output_past = config.output_past
        self.output_attentions = config.output_attentions
        self.output_hidden_states = config.output_hidden_states
        self.dropout = config.dropout
        self.layerdrop = config.decoder_layerdrop
        self.padding_idx = embed_tokens.padding_idx
        self.max_target_positions = config.max_position_embeddings
        self.embed_tokens = embed_tokens
        self.embed_positions = LearnedPositionalEmbedding(
            config.max_position_embeddings, config.d_model, self.padding_idx,
        )
        self.layers = nn.ModuleList(
            [DecoderLayer(config) for _ in range(config.decoder_layers)]
        )  # type: List[DecoderLayer]
        self.layernorm_embedding = LayerNorm(config.d_model)

    def forward(
        self, input_ids, encoder_hidden_states, encoder_padding_mask, combined_mask, cached_states=None, **unused
    ):
        """
        Includes several features from "Jointly Learning to Align and
        Translate with Transformer Models" (Garg et al., EMNLP 2019).

        Args:
            input_ids (LongTensor): previous decoder outputs of shape
                `(batch, tgt_len)`, for teacher forcing
            encoder_hidden_states: output from the encoder, used for
                encoder-side attention
            encoder_padding_mask: for ignoring pad tokens
            cached_states (dict or None): dictionary used for storing state during generation

        Returns:
            tuple:
                - the decoder's features of shape `(batch, tgt_len, embed_dim)`
                - hidden states
                - attentions
        """
        # embed positions
        positions = self.embed_positions(input_ids, cached_states=cached_states)

        if cached_states is not None:
            input_ids = input_ids[:, -1:]
            positions = positions[:, -1:]

        # embed tokens and positions
        x = self.embed_tokens(input_ids)

        if positions is not None:
            x += positions

        x = self.layernorm_embedding(x)
        x = F.dropout(x, p=self.dropout, training=self.training)

        # B x T x C -> T x B x C
        x = x.transpose(0, 1)
        # decoder layers
        all_hidden_states = ()
        all_self_attns = ()
        present = []

        for i, decoder_layer in enumerate(self.layers):
            decoder_layer  # type: DecoderLayer

            # add LayerDrop (see https://arxiv.org/abs/1909.11556 for description)
            dropout_probability = random.uniform(0, 1)

            if not self.training or (dropout_probability > self.layerdrop):
                x, layer_self_attn, layer_past = decoder_layer.forward(
                    x,
                    encoder_hidden_states,
                    encoder_padding_mask,
                    cached_states=cached_states[i] if cached_states is not None else None,
                    attention_mask=combined_mask,
                    # causal_lm_mask=causal_lm_mask,
                    # decoder_padding_mask=decoder_padding_mask,
                    need_attn_weights=self.output_attentions,
                )
                if self.output_past:
                    present.append(layer_past)
                if self.output_hidden_states:
                    all_hidden_states += (x,)
                if self.output_attentions:
                    all_self_attns += (layer_self_attn,)  # .float?
                # if layer_self_attn is not None and i == alignment_layer:
                #    attn = layer_self_attn.float()

        # T x B x C -> B x T x C
        all_hidden_states = [hidden_state.transpose(0, 1) for hidden_state in all_hidden_states]
        x = x.transpose(0, 1)

        return x, present, all_hidden_states, list(all_self_attns)


class SelfAttention(nn.Module):
    """Multi-headed attention from "Attention Is All You Need"""

    def __init__(
        self,
        embed_dim,
        num_heads,
        kdim=None,
        vdim=None,
        dropout=0.0,
        bias=True,
        encoder_decoder_attention=False,  # otherwise self_attention
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.kdim = kdim if kdim is not None else embed_dim
        self.vdim = vdim if vdim is not None else embed_dim

        self.num_heads = num_heads
        self.dropout = dropout
        self.head_dim = embed_dim // num_heads
        assert self.head_dim * num_heads == self.embed_dim, "embed_dim must be divisible by num_heads"
        self.scaling = self.head_dim ** -0.5

        self.encoder_decoder_attention = encoder_decoder_attention
        qkv_same_dim = self.kdim == embed_dim and self.vdim == embed_dim  # True for all BART

        assert self.encoder_decoder_attention or qkv_same_dim, (
            "Self-attention requires query, key and " "value to be of the same size"
        )
        self.k_proj = nn.Linear(self.kdim, embed_dim, bias=bias)
        self.v_proj = nn.Linear(self.vdim, embed_dim, bias=bias)
        self.q_proj = nn.Linear(embed_dim, embed_dim, bias=bias)
        self.out_proj = nn.Linear(embed_dim, embed_dim, bias=bias)
        self.attn_key = "{}_attn".format("encoder_decoder" if self.encoder_decoder_attention else "self")

    def _shape(self, tensor, dim_0, bsz):
        return tensor.contiguous().view(dim_0, bsz * self.num_heads, self.head_dim).transpose(0, 1)

    def forward(
        self,
        query,
        key: Optional[Tensor],
        value: Optional[Tensor],
        key_padding_mask: Optional[Tensor] = None,
        cached_states: Optional[Dict[str, Dict[str, Optional[Tensor]]]] = None,
        need_weights: bool = False,
        static_kv: bool = False,
        attn_mask: Optional[Tensor] = None,
    ) -> Tuple[Tensor, Optional[Tensor]]:
        """Input shape: Time x Batch x Channel

        Args:
            key_padding_mask (ByteTensor, optional): mask to exclude
                keys that are pads, of shape `(batch, src_len)`, where
                padding elements are indicated by 1s.
            need_weights (bool, optional): return the attention weights,
                averaged over heads (default: False).
            attn_mask (ByteTensor, optional): typically used to
                implement causal attention, where the mask prevents the
                attention from looking forward in time (default: None).
        """
        tgt_len, bsz, embed_dim = query.size()
        assert embed_dim == self.embed_dim
        assert list(query.size()) == [tgt_len, bsz, embed_dim]
        # get here for encoder decoder cause of static_kv
        if cached_states is not None:  # get the last k,v and mask for reuse
            saved_state = cached_states.get(self.attn_key, {})
            if "prev_key" in saved_state:
                # previous time steps are cached - no need to recompute key and value if they are static
                if static_kv:
                    assert self.encoder_decoder_attention
                    key = value = None
        else:
            saved_state = None

        q = self.q_proj(query) * self.scaling
        if self.encoder_decoder_attention:
            if key is None:
                assert value is None
                k = v = None
            else:
                k = self.k_proj(key)
                v = self.v_proj(key)
        else:
            k = self.k_proj(query)
            v = self.v_proj(query)

        q = self._shape(q, tgt_len, bsz)  # .view(tgt_len, bsz * self.num_heads, self.head_dim).transpose(0, 1)
        if k is not None:
            k = self._shape(k, -1, bsz)
        if v is not None:
            v = self._shape(v, -1, bsz)

        if saved_state is not None:
            k, v, key_padding_mask = self._use_and_update_saved_state(
                k, v, saved_state, key_padding_mask, cached_states, static_kv, bsz
            )
            # new_entry = {"prev_key": k.view(bsz, self.num_heads, -1, self.head_dim),
            #              "prev_value": v.view(bsz, self.num_heads, -1, self.head_dim),
            #              "prev_key_padding_mask": key_padding_mask}
            # self._update_layer_cache(cached_states, new_entry)
        assert k is not None
        src_len = k.size(1)

        attn_weights = torch.bmm(q, k.transpose(1, 2))

        assert attn_weights.size() == (bsz * self.num_heads, tgt_len, src_len)

        if attn_mask is not None:
            attn_weights = attn_weights.view(bsz, self.num_heads, tgt_len, src_len) + attn_mask
            attn_weights = attn_weights.view(bsz * self.num_heads, tgt_len, src_len)

        # This is part of a workaround to get around fork/join parallelism not supporting Optional types.
        if key_padding_mask is not None and key_padding_mask.dim() == 0:
            key_padding_mask = None
        assert key_padding_mask is None or key_padding_mask.size()[:2] == (bsz, src_len)

        if key_padding_mask is not None:  # don't attend to padding symbols
            attn_weights = attn_weights.view(bsz, self.num_heads, tgt_len, src_len)

            reshaped = key_padding_mask.unsqueeze(1).unsqueeze(2).to(torch.bool)
            attn_weights = attn_weights.masked_fill(reshaped, float("-inf"))
            attn_weights = attn_weights.view(bsz * self.num_heads, tgt_len, src_len)
        attn_weights_float = F.softmax(attn_weights, dim=-1, dtype=torch.float32)
        attn_weights = attn_weights_float.type_as(attn_weights)
        attn_probs = F.dropout(attn_weights_float, p=self.dropout, training=self.training,)
        assert v is not None
        attn_output = torch.bmm(attn_probs, v)
        assert attn_output.size() == (bsz * self.num_heads, tgt_len, self.head_dim)
        attn_output = attn_output.transpose(0, 1).contiguous().view(tgt_len, bsz, embed_dim)
        attn_output = self.out_proj(attn_output)
        attn_weights = attn_weights.view(bsz, self.num_heads, tgt_len, src_len)
        return attn_output, attn_weights

    def _use_and_update_saved_state(self, k, v, saved_state, key_padding_mask, incremental_state, static_kv, bsz):
        # saved states are stored with shape (bsz, num_heads, seq_len, head_dim)
        if "prev_key" in saved_state:
            _prev_key = saved_state["prev_key"]
            assert _prev_key is not None
            prev_key = _prev_key.view(bsz * self.num_heads, -1, self.head_dim)
            if static_kv:
                k = prev_key
            else:
                assert k is not None
                k = torch.cat([prev_key, k], dim=1)
        if "prev_value" in saved_state:
            _prev_value = saved_state["prev_value"]
            assert _prev_value is not None
            prev_value = _prev_value.view(bsz * self.num_heads, -1, self.head_dim)
            if static_kv:
                v = prev_value
            else:
                assert v is not None
                v = torch.cat([prev_value, v], dim=1)
        prev_key_padding_mask = None  # type: Optional[Tensor]
        if "prev_key_padding_mask" in saved_state:
            prev_key_padding_mask = saved_state["prev_key_padding_mask"]
        assert k is not None and v is not None
        key_padding_mask = self._cat_prev_key_padding_mask(
            key_padding_mask, prev_key_padding_mask, bsz, k.size(1), static_kv
        )
        saved_state["prev_key"] = k.view(bsz, self.num_heads, -1, self.head_dim)
        saved_state["prev_value"] = v.view(bsz, self.num_heads, -1, self.head_dim)
        saved_state["prev_key_padding_mask"] = key_padding_mask
        # In this branch cached_states is never None
        assert incremental_state is not None
        self._update_layer_cache(incremental_state, saved_state)
        return k, v, key_padding_mask

    @staticmethod
    def _cat_prev_key_padding_mask(
        key_padding_mask: Optional[Tensor],
        prev_key_padding_mask: Optional[Tensor],
        batch_size: int,
        src_len: int,
        static_kv: bool,
    ) -> Optional[Tensor]:
        # saved key padding masks have shape (bsz, seq_len)
        if prev_key_padding_mask is not None and static_kv:
            new_key_padding_mask = prev_key_padding_mask
        elif prev_key_padding_mask is not None and key_padding_mask is not None:
            new_key_padding_mask = torch.cat([prev_key_padding_mask.float(), key_padding_mask.float()], dim=1)
        # During incremental decoding, as the padding token enters and
        # leaves the frame, there will be a time when prev or current
        # is None
        elif prev_key_padding_mask is not None:

            filler = torch.zeros(batch_size, src_len - prev_key_padding_mask.size(1))
            if prev_key_padding_mask.is_cuda:
                filler = filler.cuda()
            new_key_padding_mask = torch.cat([prev_key_padding_mask.float(), filler.float()], dim=1)
        elif key_padding_mask is not None:
            filler = torch.zeros(batch_size, src_len - key_padding_mask.size(1))
            if key_padding_mask.is_cuda:
                filler = filler.cuda()
            new_key_padding_mask = torch.cat([filler.float(), key_padding_mask.float()], dim=1)
        else:
            new_key_padding_mask = prev_key_padding_mask
        return new_key_padding_mask

    def _update_layer_cache(
        self, layer_cache: Dict[str, Dict[str, Optional[Tensor]]], new_entry: Dict[str, Optional[Tensor]],
    ):
        layer_cache[self.attn_key] = new_entry


class BartClassificationHead(nn.Module):
    """Head for sentence-level classification tasks."""

    # This can trivially be shared with RobertaClassificationHead

    def __init__(
        self, input_dim, inner_dim, num_classes, pooler_dropout,
    ):
        super().__init__()
        self.dense = nn.Linear(input_dim, inner_dim)
        self.dropout = nn.Dropout(p=pooler_dropout)
        self.out_proj = nn.Linear(inner_dim, num_classes)

    def forward(self, x, **unused):
        x = self.dropout(x)
        x = self.dense(x)
        x = torch.tanh(x)
        x = self.dropout(x)
        x = self.out_proj(x)
        return x


class LearnedPositionalEmbedding(nn.Embedding):
    """
    This module learns positional embeddings up to a fixed maximum size.
    Padding ids are ignored by either offsetting based on padding_idx
    or by setting padding_idx to None and ensuring that the appropriate
    position ids are passed to the forward function.
    """

    def __init__(
        self, num_embeddings: int, embedding_dim: int, padding_idx: int,
    ):
        # if padding_idx is specified then offset the embedding ids by
        # this index and adjust num_embeddings appropriately
        assert padding_idx is not None
        num_embeddings += padding_idx + 1  # WHY?
        super().__init__(num_embeddings, embedding_dim, padding_idx=padding_idx)

    def forward(self, input, cached_states=None):
        """Input is expected to be of size [bsz x seqlen]."""
        if cached_states is not None:
            # positions is the same for every token when decoding a single step
            # Without the int() cast, it doesn't work in some cases when exporting to ONNX
            positions = input.data.new(1, 1).fill_(int(self.padding_idx + input.size(1)))
        else:
            positions = create_position_ids_from_input_ids(input, self.padding_idx)
        return super().forward(positions)


def LayerNorm(normalized_shape, eps=1e-5, elementwise_affine=True):
    if torch.cuda.is_available():
        try:
            from apex.normalization import FusedLayerNorm

            return FusedLayerNorm(normalized_shape, eps, elementwise_affine)
        except ImportError:
            pass
    return torch.nn.LayerNorm(normalized_shape, eps, elementwise_affine)


def fill_with_neg_inf(t):
    """FP16-compatible function that fills a input_ids with -inf."""
    return t.float().fill_(float("-inf")).type_as(t)


def _filter_out_falsey_values(tup) -> Tuple:
    """Remove entries that are None or [] from an iterable."""
    return tuple(x for x in tup if isinstance(x, torch.Tensor) or x)


# Public API


@add_start_docstrings(
    "The bare BART Model model outputting raw hidden-states without any specific head on top.",
    BART_START_DOCSTRING,
    BART_INPUTS_DOCSTRING,
)
class BartModel(PretrainedBartModel):
    """"""

    def __init__(self, config: BartConfig):
        super().__init__(config)
        self.output_attentions = config.output_attentions
        self.output_hidden_states = config.output_hidden_states

        padding_idx, vocab_size = config.pad_token_id, config.vocab_size
        self.shared = nn.Embedding(vocab_size, config.d_model, padding_idx)

        self.encoder = BartEncoder(config, self.shared)
        self.decoder = BartDecoder(config, self.shared)

        self.init_weights()

    def get_input_embeddings(self):
        return self.shared

    def set_input_embeddings(self, value):
        self.shared = value

    def get_output_embeddings(self):
        return _make_linear_from_emb(self.shared)

    def forward(
        self,
        input_ids,
        attention_mask=None,
        decoder_input_ids=None,
        encoder_outputs=None,  # type: Tuple
        decoder_attention_mask=None,
        cached_states=None,
        **unused  # TODO(SS): does fairseq have an equivalent to token_type_ids?
    ):
        """
        Args:
            input_ids:
            attention_mask: Ignore pad tokens in the input_ids
            decoder_input_ids:
            encoder_outputs: None or Tuple. If a tuple is passed, its first entry is assumed to be the features. If
            none is passed, we call the encoder.
            decoder_attention_mask:
            **unused:

        Returns:

        """
        # make masks if user doesn't supply
        attention_mask, decoder_input_ids, decoder_attn_mask = prepare_bart_inputs(
            self.config,
            input_ids,
            attention_mask=attention_mask,
            decoder_input_ids=decoder_input_ids,
            decoder_attn_mask=decoder_attention_mask,
        )
        assert decoder_input_ids is not None
        if encoder_outputs is None:
            # TODO(SS): make this caching more usable when overwrite generate
            encoder_outputs = self.encoder.forward(input_ids=input_ids, attention_mask=attention_mask)
        assert isinstance(encoder_outputs, tuple)
        # dec_features, cached_states, dec_hidden, dec_attn
        decoder_outputs = self.decoder.forward(
            decoder_input_ids, encoder_outputs[0], attention_mask, decoder_attention_mask, cached_states=cached_states,
        )
        # Attention and hidden_states will be [] or None if they aren't needed
        decoder_outputs = _filter_out_falsey_values(decoder_outputs)  # type: tuple
        assert isinstance(decoder_outputs[0], torch.Tensor)
        encoder_outputs = _filter_out_falsey_values(encoder_outputs)  # type: tuple
        return decoder_outputs + encoder_outputs


class BartForMaskedLM(PretrainedBartModel):
    r"""
        **lm_labels**: (`optional`) ``torch.LongTensor`` of shape ``(batch_size, sequence_length)``:
            Labels for computing the masked language modeling loss.
            Indices should either be in ``[0, ..., config.vocab_size]`` or -100 (see ``input_ids`` docstring).
            Tokens with indices set to ``-100`` are ignored (masked), the loss is only computed for the tokens with labels
            in ``[0, ..., config.vocab_size]``.

    Outputs: `Tuple` comprising various elements depending on the configuration (config) and inputs:
        **loss**: (`optional`, returned when ``lm_labels`` is provided) ``torch.FloatTensor`` of shape ``(1,)``:
            Masked language modeling loss.
        **prediction_scores**: ``torch.FloatTensor`` of shape ``(batch_size, sequence_length, config.vocab_size)``
            Prediction scores of the language modeling head (scores for each vocabulary token before SoftMax).
        **hidden_states**: (`optional`, returned when ``config.output_hidden_states=True``)
            list of ``torch.FloatTensor`` (one for the output of each layer + the output of the embeddings)
            of shape ``(batch_size, sequence_length, hidden_size)``:
            Hidden-states of the model at the output of each layer plus the initial embedding outputs.
        **attentions**: (`optional`, returned when ``config.output_attentions=True``)
            list of ``torch.FloatTensor`` (one for each layer) of shape ``(batch_size, num_heads, sequence_length, sequence_length)``:
            Attentions weights after the attention softmax, used to compute the weighted average in the self-attention heads.

    Examples::

        tokenizer = BartTokenizer.from_pretrained('bart-large')
        model = BartForMaskedLM.from_pretrained('bart-large')
        input_ids = torch.tensor(tokenizer.encode("Hello, my dog is cute")).unsqueeze(0)  # Batch size 1
        outputs = model(input_ids=input_ids, lm_labels=input_ids)
        loss, prediction_scores = outputs[:2]

    """
    base_model_prefix = "model"


    def __init__(self, config: BartConfig):
        super().__init__(config)
        self.model = BartModel(config)
        self.lm_head = _make_linear_from_emb(self.model.shared)

    def forward(
        self,
        input_ids,
        attention_mask=None,
        encoder_hidden_states=None,
        decoder_input_ids=None,
        decoder_attention_mask=None,
        cached_states=None,
        lm_labels=None,
        **unused
    ):
        outputs = self.model.forward(
            input_ids,
            attention_mask=attention_mask,
            decoder_input_ids=decoder_input_ids,
            encoder_hidden_states=encoder_hidden_states,
            decoder_attention_mask=decoder_attention_mask,
            cached_states=cached_states,
        )
        lm_logits = self.lm_head.forward(outputs[0])
        outputs = (lm_logits,) + outputs[1:]  # Add hidden states and attention if they are here
        if lm_labels is not None:
            loss_fct = nn.CrossEntropyLoss()
            masked_lm_loss = loss_fct(lm_logits.view(-1, self.config.vocab_size), lm_labels.view(-1))
            outputs = (masked_lm_loss,) + outputs

        return outputs

    @staticmethod
    def prepare_inputs_for_generation(input_ids, past, **kwargs):
        return {"input_ids": input_ids, "cached_states": past, "decoder_input_ids": input_ids}

    def get_output_embeddings(self):
        return self.lm_head

@add_start_docstrings(
    """Bart model with a sequence classification/regression head on top (a linear layer
    on top of the pooled output) e.g. for GLUE tasks. """,
    BART_START_DOCSTRING, BART_INPUTS_DOCSTRING)
class BartForSequenceClassification(PretrainedBartModel):
    r"""
        labels (:obj:`torch.LongTensor` of shape :obj:`(batch_size,)`, `optional`, defaults to :obj:`None`):
            Labels for computing the sequence classification/regression loss.
            Indices should be in :obj:`[0, ..., config.num_labels - 1]`.
            If :obj:`config.num_labels == 1` a regression loss is computed (Mean-Square loss),
            If :obj:`config.num_labels > 1` a classification loss is computed (Cross-Entropy).

    Returns:
        :obj:`tuple(torch.FloatTensor)` comprising various elements depending on the configuration (:class:`~transformers.BartConfig`) and inputs:
        loss (:obj:`torch.FloatTensor` of shape :obj:`(1,)`, `optional`, returned when :obj:`label` is provided):
            Classification (or regression if config.num_labels==1) loss.
        logits (:obj:`torch.FloatTensor` of shape :obj:`(batch_size, config.num_labels)`):
            Classification (or regression if config.num_labels==1) scores (before SoftMax).
        hidden_states (:obj:`tuple(torch.FloatTensor)`, `optional`, returned when ``config.output_hidden_states=True``):
            Tuple of :obj:`torch.FloatTensor` (one for the output of the embeddings + one for the output of each layer)
            of shape :obj:`(batch_size, sequence_length, hidden_size)`.

            Hidden-states of the model at the output of each layer plus the initial embedding outputs.
        attentions (:obj:`tuple(torch.FloatTensor)`, `optional`, returned when ``config.output_attentions=True``):
            Tuple of :obj:`torch.FloatTensor` (one for each layer) of shape
            :obj:`(batch_size, num_heads, sequence_length, sequence_length)`.

            Attentions weights after the attention softmax, used to compute the weighted average in the self-attention
            heads.

    Examples::

        from transformers import BartTokenizer, BartForSequenceClassification
        import torch

        tokenizer = BartTokenizer.from_pretrained('bart-large')
        model = BartForSequenceClassification.from_pretrained('bart-large')
        input_ids = torch.tensor(tokenizer.encode("Hello, my dog is cute", add_special_tokens=True)).unsqueeze(0)  # Batch size 1
        labels = torch.tensor([1]).unsqueeze(0)  # Batch size 1
        outputs = model(input_ids, labels=labels)
        loss, logits = outputs[:2]

    """

    def __init__(self, config: BartConfig, **kwargs):
        super().__init__(config, **kwargs)
        self.model = BartModel(config)
        self.classification_head = BartClassificationHead(
            config.d_model, config.d_model, config.num_labels, config.classif_dropout,
        )
        self.model._init_weights(self.classification_head.dense)
        self.model._init_weights(self.classification_head.out_proj)

    def forward(
        self,
        input_ids,
        attention_mask=None,
        encoder_hidden_states=None,
        decoder_input_ids=None,
        decoder_attention_mask=None,
        labels=None,
        **unused
    ):
        outputs = self.model.forward(
            input_ids,
            attention_mask=attention_mask,
            decoder_input_ids=decoder_input_ids,
            decoder_attention_mask=decoder_attention_mask,
            encoder_outputs=encoder_hidden_states,
        )
        x = outputs[0]  # last hidden state
        eos_mask = input_ids.eq(self.config.eos_token_id)
        if len(torch.unique(eos_mask.sum(1))) > 1:
            raise ValueError("All examples must have the same number of <eos> tokens.")
        sentence_representation = x[eos_mask, :].view(x.size(0), -1, x.size(-1))[:, -1, :]
        logits = self.classification_head(sentence_representation)
        # Prepend logits
        outputs = (logits,) + outputs[1:]  # Add hidden states and attention if they are here
        if labels is not None:  # prepend loss to output,
            # TODO(SS): do we need to ignore pad tokens?
            loss = F.cross_entropy(logits.view(-1, self.num_labels), labels.view(-1))
            outputs = (loss,) + outputs

        return outputs
