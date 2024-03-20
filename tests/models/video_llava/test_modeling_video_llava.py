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
""" Testing suite for the PyTorch VideoLlava model. """

import gc
import unittest

import numpy as np
from huggingface_hub import hf_hub_download

from transformers import (
    VideoLlavaConfig,
    VideoLlavaForConditionalGeneration,
    VideoLlavaProcessor,
    is_torch_available,
    is_vision_available,
)
from transformers.testing_utils import require_bitsandbytes, require_torch, require_torch_gpu, slow, torch_device

from ...generation.test_utils import GenerationTesterMixin
from ...test_configuration_common import ConfigTester
from ...test_modeling_common import ModelTesterMixin, floats_tensor, ids_tensor


if is_torch_available():
    import torch
else:
    is_torch_greater_or_equal_than_2_0 = False

if is_vision_available():
    pass


class VideoLlavaVisionText2TextModelTester:
    def __init__(
        self,
        parent,
        ignore_index=-100,
        image_token_index=0,
        projector_hidden_act="gelu",
        seq_length=7,
        num_frames=2,
        vision_feature_select_strategy="default",
        vision_feature_layer=-1,
        text_config={
            "model_type": "llama",
            "seq_length": 7,
            "is_training": True,
            "use_input_mask": True,
            "use_token_type_ids": False,
            "use_labels": True,
            "vocab_size": 99,
            "hidden_size": 32,
            "num_hidden_layers": 2,
            "num_attention_heads": 4,
            "intermediate_size": 37,
            "hidden_act": "gelu",
            "hidden_dropout_prob": 0.1,
            "attention_probs_dropout_prob": 0.1,
            "max_position_embeddings": 512,
            "type_vocab_size": 16,
            "type_sequence_label_size": 2,
            "initializer_range": 0.02,
            "num_labels": 3,
            "num_choices": 4,
            "pad_token_id": 0,
        },
        is_training=True,
        vision_config={
            "batch_size": 12,
            "image_size": 30,
            "patch_size": 2,
            "num_channels": 3,
            "is_training": True,
            "hidden_size": 32,
            "projection_dim": 32,
            "num_hidden_layers": 2,
            "num_attention_heads": 4,
            "intermediate_size": 37,
            "dropout": 0.1,
            "attention_dropout": 0.1,
            "initializer_range": 0.02,
        },
    ):
        self.parent = parent
        self.ignore_index = ignore_index
        self.image_token_index = image_token_index
        self.projector_hidden_act = projector_hidden_act
        self.vision_feature_select_strategy = vision_feature_select_strategy
        self.vision_feature_layer = vision_feature_layer
        self.text_config = text_config
        self.vision_config = vision_config
        self.seq_length = seq_length
        self.num_frames = num_frames

        self.num_hidden_layers = text_config["num_hidden_layers"]
        self.vocab_size = text_config["vocab_size"]
        self.hidden_size = text_config["hidden_size"]
        self.num_attention_heads = text_config["num_attention_heads"]
        self.is_training = is_training

        self.batch_size = 3
        self.num_channels = 3
        self.image_size = 336
        self.encoder_seq_length = 455

    def get_config(self):
        return VideoLlavaConfig(
            text_config=self.text_config,
            vision_config=self.vision_config,
            ignore_index=self.ignore_index,
            image_token_index=self.image_token_index,
            projector_hidden_act=self.projector_hidden_act,
            vision_feature_select_strategy=self.vision_feature_select_strategy,
            vision_feature_layer=self.vision_feature_layer,
        )

    def prepare_config_and_inputs(self):
        pixel_values = floats_tensor(
            [
                self.batch_size,
                self.num_frames,
                self.vision_config["num_channels"],
                self.vision_config["image_size"],
                self.vision_config["image_size"],
            ]
        )
        config = self.get_config()

        return config, pixel_values

    def prepare_config_and_inputs_for_common(self):
        config_and_inputs = self.prepare_config_and_inputs()
        config, pixel_values = config_and_inputs
        input_ids = ids_tensor([self.batch_size, self.seq_length], config.text_config.vocab_size - 1) + 1
        attention_mask = input_ids.ne(1).to(torch_device)
        # we are giving 3 videos, each has 2 frames let's make sure we pass in 3 * 2 image tokens
        input_ids[:, :2] = config.image_token_index
        inputs_dict = {
            "pixel_values_videos": pixel_values,
            "input_ids": input_ids,
            "attention_mask": attention_mask,
        }
        return config, inputs_dict


@require_torch
class VideoLlavaForConditionalGenerationModelTest(ModelTesterMixin, GenerationTesterMixin, unittest.TestCase):
    """
    Model tester for `VideoLlavaForConditionalGeneration`.
    """

    all_model_classes = (VideoLlavaForConditionalGeneration,) if is_torch_available() else ()
    fx_compatible = False
    test_pruning = False
    test_resize_embeddings = True
    test_head_masking = False

    def setUp(self):
        self.model_tester = VideoLlavaVisionText2TextModelTester(self)
        self.config_tester = ConfigTester(self, config_class=VideoLlavaConfig, has_text_modality=False)

    @unittest.skip(
        reason="This architecure seem to not compute gradients properly when using GC, check: https://github.com/huggingface/transformers/pull/27124"
    )
    def test_training_gradient_checkpointing(self):
        pass

    @unittest.skip(
        reason="This architecure seem to not compute gradients properly when using GC, check: https://github.com/huggingface/transformers/pull/27124"
    )
    def test_training_gradient_checkpointing_use_reentrant(self):
        pass

    @unittest.skip(
        reason="This architecure seem to not compute gradients properly when using GC, check: https://github.com/huggingface/transformers/pull/27124"
    )
    def test_training_gradient_checkpointing_use_reentrant_false(self):
        pass


@require_torch
class VideoLlavaForConditionalGenerationIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.processor = VideoLlavaProcessor.from_pretrained("RaushanTurganbay/video-llava-7b-hf")

    def tearDown(self):
        gc.collect()
        torch.cuda.empty_cache()

    @slow
    @require_bitsandbytes
    def test_small_model_integration_test(self):
        # Let' s make sure we test the preprocessing to replace what is used
        model = VideoLlavaForConditionalGeneration.from_pretrained(
            "RaushanTurganbay/video-llava-7b-hf", load_in_4bit=True
        )

        prompt = "USER: <image><image><image><image><image><image><image><image>Why is this video funny? ASSISTANT:"
        video_file = hf_hub_download(
            repo_id="raushan-testing-hf/videos-test", filename="video_demo.npy", repo_type="dataset"
        )
        video_file = np.load(video_file)
        inputs = self.processor(prompt, videos=video_file, return_tensors="pt")

        EXPECTED_INPUT_IDS = torch.tensor([[1,  3148, 1001, 29901, 29871, 32000, 32000, 32000, 32000, 32000, 32000, 32000, 32000, 3750, 338, 445, 4863, 2090, 1460, 29973, 319, 1799, 9047, 13566, 29901]])  # fmt: skip
        self.assertTrue(torch.equal(inputs["input_ids"], EXPECTED_INPUT_IDS))

        output = model.generate(**inputs, do_sample=False, max_new_tokens=20)
        EXPECTED_DECODED_TEXT = "USER:  Why is this video funny? ASSISTANT: The video is funny because the baby is playing with a Wii remote while sitting on a bed"  # fmt: skip

        self.assertEqual(
            self.processor.decode(output[0], skip_special_tokens=True),
            EXPECTED_DECODED_TEXT,
        )

    @slow
    @require_bitsandbytes
    def test_small_model_integration_test_llama(self):
        # Let' s make sure we test the preprocessing to replace what is used
        model_id = "RaushanTurganbay/video-llava-7b-hf"

        model = VideoLlavaForConditionalGeneration.from_pretrained(
            "RaushanTurganbay/video-llava-7b-hf", load_in_4bit=True
        )
        processor = VideoLlavaProcessor.from_pretrained(model_id)

        prompt = (
            "USER: <image><image><image><image><image><image><image><image>Describe the video in details. ASSISTANT:"
        )
        video_file = hf_hub_download(
            repo_id="raushan-testing-hf/videos-test", filename="video_demo.npy", repo_type="dataset"
        )
        video_file = np.load(video_file)
        inputs = self.processor(prompt, visual_inputs=video_file, return_tensors="pt").to(torch_device, torch.float16)

        output = model.generate(**inputs, max_new_tokens=900, do_sample=False)
        EXPECTED_DECODED_TEXT = "USER:  Describe the video in details. ASSISTANT: The video features a young child sitting on a bed, holding a book and reading it. " \
            "The child appears to be enjoying the book, as they are fully engaged in the reading process. The bed is located in a bedroom, and there is a chair nearby. " \
            "The child is wearing a light blue shirt and pink pants, and they have glasses on. The room is well-lit, and there is a clock on the wall. The child seems " \
            "to be in a comfortable and relaxed environment, which is conducive to reading and learning. Overall, the video captures a heartwarming moment of a child " \
            "engaging in a simple yet essential activity, which is reading."  # fmt: skip

        self.assertEqual(
            processor.decode(output[0], skip_special_tokens=True),
            EXPECTED_DECODED_TEXT,
        )

    @slow
    @require_bitsandbytes
    def test_small_model_integration_test_llama_batched(self):
        # Let' s make sure we test the preprocessing to replace what is used
        model_id = "RaushanTurganbay/video-llava-7b-hf"

        model = VideoLlavaForConditionalGeneration.from_pretrained(
            "RaushanTurganbay/video-llava-7b-hf", load_in_4bit=True
        )
        processor = VideoLlavaProcessor.from_pretrained(model_id)
        processor.tokenizer.padding_side = "left"

        prompts = [
            "USER: <image><image><image><image><image><image><image><image>What is the baby doing? ASSISTANT:",
            "USER: <image><image><image><image><image><image><image><image>Who is sitting next to the woman? ASSISTANT:",
        ]
        video_1 = np.load(
            hf_hub_download(repo_id="raushan-testing-hf/videos-test", filename="video_demo.npy", repo_type="dataset")
        )
        video_2 = np.load(
            hf_hub_download(repo_id="raushan-testing-hf/videos-test", filename="video_demo_2.npy", repo_type="dataset")
        )

        inputs = processor(prompts, visual_inputs=[video_1, video_2], return_tensors="pt", padding=True)

        output = model.generate(**inputs, max_new_tokens=20)

        EXPECTED_DECODED_TEXT = [
            'USER:  What is the baby doing? ASSISTANT: The baby is sitting on a bed and reading a book.Ъ',
            'USER:  Who is sitting next to the woman? ASSISTANT: A small dog is sitting next to the woman.Ъ'
            ]  # fmt: skip

        self.assertEqual(processor.batch_decode(output, skip_special_tokens=True), EXPECTED_DECODED_TEXT)

    @slow
    @require_bitsandbytes
    def test_small_model_integration_test_llama_batched_regression(self):
        # Let' s make sure we test the preprocessing to replace what is used
        model_id = "RaushanTurganbay/video-llava-7b-hf"

        # Multi-image & multi-prompt (e.g. 3 images and 2 prompts now fails with SDPA, this tests if "eager" works as before)
        model = VideoLlavaForConditionalGeneration.from_pretrained(
            "RaushanTurganbay/video-llava-7b-hf", load_in_4bit=True, attn_implementation="eager"
        )
        processor = VideoLlavaProcessor.from_pretrained(model_id, pad_token="<pad>")
        processor.tokenizer.padding_side = "left"

        prompts = [
            "USER: <image><image><image><image><image><image><image><image>What is the baby doing? ASSISTANT:",
            "USER: <image><image><image><image><image><image><image><image>Who is sitting next to the woman? ASSISTANT: A small dog is sitting next to the woman. USER: <image><image><image><image><image><image><image><image>What about this video? ASSITANT:",
        ]
        video_1 = np.load(
            hf_hub_download(repo_id="raushan-testing-hf/videos-test", filename="video_demo.npy", repo_type="dataset")
        )
        video_2 = np.load(
            hf_hub_download(repo_id="raushan-testing-hf/videos-test", filename="video_demo_2.npy", repo_type="dataset")
        )

        inputs = processor(prompts, visual_inputs=[video_1, video_2, video_1], return_tensors="pt", padding=True)

        output = model.generate(**inputs, max_new_tokens=20)

        EXPECTED_DECODED_TEXT = [
            'USER:  What is the baby doing? ASSISTANT: The baby is sitting on a bed and reading a book.Ћ',
            'USER:  Who is sitting next to the woman? ASSISTANT: A small dog is sitting next to the woman. USER:  What about this video? ASSITANT: The video shows a baby sitting on a bed, reading a book. The baby is wearing glass'
            ]  # fmt: skip

        self.assertEqual(processor.batch_decode(output, skip_special_tokens=True), EXPECTED_DECODED_TEXT)

    @slow
    @require_bitsandbytes
    def test_video_llava_index_error_bug(self):
        # This is a reproducer of https://github.com/huggingface/transformers/pull/28032 and makes sure it does not happen anymore
        # Please refer to that PR, or specifically https://github.com/huggingface/transformers/pull/28032#issuecomment-1860650043 for
        # more details
        model_id = "RaushanTurganbay/video-llava-7b-hf"
        model = VideoLlavaForConditionalGeneration.from_pretrained(model_id, load_in_4bit=True)

        # Simulate a super long prompt
        user_prompt = "Describe the video:?\n" * 200
        prompt = f"USER: <image><image><image><image><image><image><image><image>{user_prompt}ASSISTANT:"
        video_file = hf_hub_download(
            repo_id="raushan-testing-hf/videos-test", filename="video_demo.npy", repo_type="dataset"
        )
        video_file = np.load(video_file)
        inputs = self.processor(prompt, visual_inputs=video_file, return_tensors="pt").to(torch_device, torch.float16)

        # Make sure that `generate` works
        _ = model.generate(**inputs, max_new_tokens=20)

    @slow
    @require_torch_gpu
    def test_video_llava_merge_inputs_error_bug(self):
        # This is a reproducer of https://github.com/huggingface/transformers/pull/28333 and makes sure it does not happen anymore
        model_id = "RaushanTurganbay/video-llava-7b-hf"
        model = VideoLlavaForConditionalGeneration.from_pretrained(
            model_id, torch_dtype=torch.float16, low_cpu_mem_usage=True
        ).to(torch_device)

        # Simulate some user inputs
        pixel_values_videos = torch.randn(
            (2, 8, 3, 224, 224),
            dtype=torch.float,
            device=torch_device,
        )
        input_ids = torch.tensor(
            [
                [
                    32001,
                    32001,
                    1,
                    15043,
                    7084,
                    32000,
                    32000,
                    32000,
                    32000,
                    32000,
                    32000,
                    32000,
                    32000,
                    29871,
                    13,
                    7900,
                ],
                [
                    1,
                    15043,
                    7084,
                    29901,
                    29871,
                    32000,
                    32000,
                    32000,
                    32000,
                    32000,
                    32000,
                    32000,
                    32000,
                    29871,
                    13,
                    7900,
                ],
            ],
            dtype=torch.long,
            device=torch_device,
        )
        attention_mask = torch.tensor(
            [[0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]],
            dtype=torch.long,
            device=torch_device,
        )

        # Make sure that the loss is properly computed
        loss = model(
            pixel_values_videos=pixel_values_videos,
            input_ids=input_ids,
            attention_mask=attention_mask,
            labels=input_ids,
        ).loss
        loss.backward()
