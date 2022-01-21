# coding=utf-8
# Copyright 2022 The HuggingFace Inc. team.
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
"""Convert ConvNext checkpoints from the original repository."""


import argparse
import json
from pathlib import Path

import torch
from PIL import Image

import requests
from huggingface_hub import cached_download, hf_hub_url
from transformers import ViTFeatureExtractor, ConvNextConfig, ConvNextForImageClassification
from transformers.utils import logging


logging.set_verbosity_info()
logger = logging.get_logger(__name__)


def get_convnext_config(checkpoint_url):
    config = ConvNextConfig()

    if "tiny" not in checkpoint_url:
        depths = [3, 3, 27, 3]
    
    if "base" in checkpoint_url:
        dims = [128, 256, 512, 1024]
    elif "large" in checkpoint_url:
        dims = [192, 384, 768, 1536]
    elif "xlarge" in checkpoint_url:
        dims = [256, 512, 1024, 2048]

    if "22k" in checkpoint_url:
        num_labels = 21841
        filename = "imagenet-22k-id2label.json"
    else:
        num_labels = 1000
        filename = "imagenet-1k-id2label.json"

    repo_id = "datasets/huggingface/label-files"
    config.num_labels = num_labels
    id2label = json.load(open(cached_download(hf_hub_url(repo_id, filename)), "r"))
    id2label = {int(k): v for k, v in id2label.items()}
    if "22k" in checkpoint_url:
        # this dataset contains 21843 labels but the model only has 21841
        # we delete the classes as mentioned in https://github.com/google-research/big_transfer/issues/18
        del id2label[9205]
        del id2label[15027]
    config.id2label = id2label
    config.label2id = {v: k for k, v in id2label.items()}
    config.dims = dims
    config.depths = depths

    return config


# here we list all keys to be renamed (original name on the left, our name on the right)
def create_rename_keys(config):
    rename_keys = []
    for i in range(config.num_hidden_layers):
        # encoder layers: output projection, 2 feedforward neural networks and 2 layernorms
        rename_keys.append((f"blocks.{i}.norm1.weight", f"vit.encoder.layer.{i}.layernorm_before.weight"))
        rename_keys.append((f"blocks.{i}.norm1.bias", f"vit.encoder.layer.{i}.layernorm_before.bias"))
        rename_keys.append((f"blocks.{i}.attn.proj.weight", f"vit.encoder.layer.{i}.attention.output.dense.weight"))
        rename_keys.append((f"blocks.{i}.attn.proj.bias", f"vit.encoder.layer.{i}.attention.output.dense.bias"))
        rename_keys.append((f"blocks.{i}.norm2.weight", f"vit.encoder.layer.{i}.layernorm_after.weight"))
        rename_keys.append((f"blocks.{i}.norm2.bias", f"vit.encoder.layer.{i}.layernorm_after.bias"))
        rename_keys.append((f"blocks.{i}.mlp.fc1.weight", f"vit.encoder.layer.{i}.intermediate.dense.weight"))
        rename_keys.append((f"blocks.{i}.mlp.fc1.bias", f"vit.encoder.layer.{i}.intermediate.dense.bias"))
        rename_keys.append((f"blocks.{i}.mlp.fc2.weight", f"vit.encoder.layer.{i}.output.dense.weight"))
        rename_keys.append((f"blocks.{i}.mlp.fc2.bias", f"vit.encoder.layer.{i}.output.dense.bias"))

    # layernorm + classification head
    rename_keys.extend(
        [
            ("norm.weight", "vit.layernorm.weight"),
            ("norm.bias", "vit.layernorm.bias"),
            ("head.weight", "classifier.weight"),
            ("head.bias", "classifier.bias"),
        ]
    )

    return rename_keys


def rename_key(dct, old, new):
    val = dct.pop(old)
    dct[new] = val


# We will verify our results on an image of cute cats
def prepare_img():
    url = "http://images.cocodataset.org/val2017/000000039769.jpg"
    im = Image.open(requests.get(url, stream=True).raw)
    return im


@torch.no_grad()
def convert_convnext_checkpoint(checkpoint_url, pytorch_dump_folder_path):
    """
    Copy/paste/tweak model's weights to our ConvNext structure.
    """

    # define ConvNext configuration
    config = get_convnext_config(checkpoint_url)
    # load original state_dict from URL
    state_dict = torch.hub.load_state_dict_from_url()
    rename_keys = create_rename_keys(config)
    for src, dest in rename_keys:
        rename_key(state_dict, src, dest)

    # load HuggingFace model
    model = ConvNextForImageClassification(config).eval()
    model.load_state_dict(state_dict)

    # Check outputs on an image, prepared by ViTFeatureExtractor
    feature_extractor = ViTFeatureExtractor(size=config.image_size)
    encoding = feature_extractor(images=prepare_img(), return_tensors="pt")
    pixel_values = encoding["pixel_values"]
    outputs = model(pixel_values)

    # TODO assert

    Path(pytorch_dump_folder_path).mkdir(exist_ok=True)
    print(f"Saving model to {pytorch_dump_folder_path}")
    model.save_pretrained(pytorch_dump_folder_path)
    print(f"Saving feature extractor to {pytorch_dump_folder_path}")
    feature_extractor.save_pretrained(pytorch_dump_folder_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # Required parameters
    parser.add_argument(
        "--checkpoint_url",
        default="https://dl.fbaipublicfiles.com/convnext/convnext_tiny_1k_224_ema.pth",
        type=str,
        help="URL of the ConvNext original checkpoint you'd like to convert.",
    )
    parser.add_argument(
        "--pytorch_dump_folder_path", default=None, type=str, help="Path to the output PyTorch model directory."
    )

    args = parser.parse_args()
    convert_convnext_checkpoint(args.checkpoint_url, args.pytorch_dump_folder_path)