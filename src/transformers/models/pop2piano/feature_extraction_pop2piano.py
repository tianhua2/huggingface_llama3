# coding=utf-8
# Copyright 2023 The HuggingFace Inc. team.
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
""" Feature extractor class for Pop2Piano"""

import copy
import warnings
from typing import List, Optional, Union

import librosa
import numpy as np
import scipy
import torch
from torch.nn.utils.rnn import pad_sequence

from ...audio_utils import mel_filter_bank, spectrogram
from ...feature_extraction_sequence_utils import SequenceFeatureExtractor
from ...feature_extraction_utils import BatchFeature
from ...utils import OptionalDependencyNotAvailable, TensorType, is_essentia_available, logging


try:
    if not is_essentia_available:
        raise OptionalDependencyNotAvailable()
except ImportError:
    raise ImportError("There was an error while importing essentia!")
else:
    import essentia
    import essentia.standard


logger = logging.get_logger(__name__)


class Pop2PianoFeatureExtractor(SequenceFeatureExtractor):
    r"""
    Constructs a Pop2Piano feature extractor.

    This feature extractor inherits from [`~feature_extraction_sequence_utils.SequenceFeatureExtractor`] which contains
    most of the main methods. Users should refer to this superclass for more information regarding those methods.

    Args:
    This class extracts rhythm and does preprocesses before being passed through the transformer model.
        sampling_rate (`int`, *optional*, defaults to 22050):
            Target Sampling rate of audio signal. It's the sampling rate that we forward to the model.
        padding_value (`int`, *optional*, defaults to 0):
            Padding value used to pad the audio. Should correspond to silences.
        window_size (`int`, *optional*, defaults to 4096):
            Length of the window in samples to which the Fourier transform is applied.
        hop_length (`int`, *optional*, defaults to 1024):
            Step size between each window of the waveform, in samples.
        min_frequency (`float`, *optional*, defaults to 10.0):
            Lowest frequency that will be used in the log-mel spectrogram.
        feature_size (`int`, *optional*, defaults to 512):
            The feature dimension of the extracted features.
        num_bars (`int`, *optional*, defaults to 2):
            Determines interval between each sequence.
    """
    model_input_names = ["inputs_embeds"]

    def __init__(
        self,
        sampling_rate: int = 22050,
        padding_value: int = 0,
        window_size: int = 4096,
        hop_length: int = 1024,
        min_frequency: float = 10.0,
        feature_size: int = 512,
        num_bars: int = 2,
        **kwargs,
    ):
        super().__init__(
            feature_size=feature_size,
            sampling_rate=sampling_rate,
            padding_value=padding_value,
            **kwargs,
        )
        self.sampling_rate = sampling_rate
        self.padding_value = padding_value
        self.window_size = window_size
        self.hop_length = hop_length
        self.min_frequency = min_frequency
        self.feature_size = feature_size
        self.num_bars = num_bars
        self.mel_filters = mel_filter_bank(
            num_frequency_bins=(self.window_size // 2) + 1,
            num_mel_filters=self.feature_size,
            min_frequency=self.min_frequency,
            max_frequency=float(self.sampling_rate // 2),
            sampling_rate=self.sampling_rate,
            norm=None,
            mel_scale="htk",
        ).astype(np.float32)

    def log_mel_spectogram(self, sequence):
        """Generates MelSpectrogram then applies log base e."""

        mel_specs = []
        for seq in sequence:
            window = np.hanning(self.window_size + 1)[:-1]
            mel_specs.append(
                spectrogram(
                    waveform=seq,
                    window=window,
                    frame_length=self.window_size,
                    hop_length=self.hop_length,
                    power=2.0,
                    mel_filters=self.mel_filters,
                )
            )
        mel_specs = np.array(mel_specs)
        log_mel_specs = np.log(np.clip(mel_specs, a_min=1e-6, a_max=None)).astype(np.float32)

        return log_mel_specs

    def extract_rhythm(self, audio):
        """
        This algorithm(`RhythmExtractor2013`) extracts the beat positions and estimates their confidence as well as
        tempo in bpm for an audio signal. For more information please visit
        https://essentia.upf.edu/reference/std_RhythmExtractor2013.html .
        """
        essentia_tracker = essentia.standard.RhythmExtractor2013(method="multifeature")
        bpm, beat_times, confidence, estimates, essentia_beat_intervals = essentia_tracker(audio)

        return bpm, beat_times, confidence, estimates, essentia_beat_intervals

    def interpolate_beat_times(self, beat_times, steps_per_beat, extend=False):
        beat_times_function = scipy.interpolate.interp1d(
            np.arange(beat_times.size),
            beat_times,
            bounds_error=False,
            fill_value="extrapolate",
        )
        if extend:
            beat_steps_8th = beat_times_function(np.linspace(0, beat_times.size, beat_times.size * steps_per_beat + 1))
        else:
            beat_steps_8th = beat_times_function(
                np.linspace(0, beat_times.size - 1, beat_times.size * steps_per_beat - 1)
            )
        return beat_steps_8th

    def extrapolate_beat_times(self, beat_times, n_extend=1):
        beat_times_function = scipy.interpolate.interp1d(
            np.arange(beat_times.size),
            beat_times,
            bounds_error=False,
            fill_value="extrapolate",
        )
        ext_beats = beat_times_function(np.linspace(0, beat_times.size + n_extend - 1, beat_times.size + n_extend))

        return ext_beats

    def preprocess_mel(
        self,
        audio,
        beatstep,
        num_bars,
        padding_value,
    ):
        """Preprocessing for log-mel spectrogram"""

        num_steps = num_bars * 4
        num_target_steps = len(beatstep)
        extrapolated_beatstep = self.extrapolate_beat_times(beatstep, (num_bars + 1) * 4 + 1)

        batch = []
        for i in range(0, num_target_steps, num_steps):
            start_idx = i
            end_idx = min(i + num_steps, num_target_steps)

            start_sample = int(extrapolated_beatstep[start_idx] * self.sampling_rate)
            end_sample = int(extrapolated_beatstep[end_idx] * self.sampling_rate)
            feature = audio[start_sample:end_sample]
            batch.append(feature)
        batch = pad_sequence(batch, batch_first=True, padding_value=padding_value)

        return batch, extrapolated_beatstep

    def single_preprocess(
        self,
        beatstep,
        audio=None,
    ):
        """Preprocessing method for a single sequence."""

        if audio is not None:
            if len(audio.shape) != 1:
                raise ValueError(
                    f"Expected `audio` to be a single channel audio input of shape (n, ) but found shape {audio.shape}."
                )

        if beatstep[0] > 0.01:
            logger.warning(f"`beatstep[0]` is not 0. All beatstep will be shifted by {beatstep[0]}.")
            beatstep = beatstep - beatstep[0]

        batch, extrapolated_beatstep = self.preprocess_mel(
            audio,
            beatstep,
            num_bars=self.num_bars,
            padding_value=self.padding_value,
        )

        return batch, extrapolated_beatstep

    def pad(self, inputs: BatchFeature):
        """
        Takes inputs_embeds of shape (batch, dim1, dim2, dim3), beatsteps of shape (batch, dim1) and
        extrapolated_beatstep of shape (batch, dim1) and returns the padded version of themselves along with the
        attention_mask. Please note that dim1, dim2, dim3 are variable sizes so the padding is applied on those axis.
        """

        inputs_embeds_shapes = [inputs_embed.shape for inputs_embed in inputs["inputs_embeds"]]
        beatsteps_shapes = [beatsteps.shape for beatsteps in inputs["beatsteps"]]
        ext_beatstep_shapes = [
            extrapolated_beatstep.shape for extrapolated_beatstep in inputs["extrapolated_beatstep"]
        ]

        for i, inputs_embed in enumerate(inputs["inputs_embeds"]):
            padding = (
                (0, 0),
                (0, max([*zip(*inputs_embeds_shapes)][1]) - inputs_embeds_shapes[i][1]),
                (0, 0),
            )
            inputs["inputs_embeds"][i] = np.concatenate(
                [
                    np.pad(inputs_embed, padding, "constant", constant_values=self.padding_value),
                    np.zeros(
                        [1, max([*zip(*inputs_embeds_shapes)][1]), 512]
                    ),  # if it is batched then we seperate each examples using zero array
                ],
                axis=0,
            )

            # compute attention_mask for inputs_embeds and add it to dict
            attention_mask_inputs_embed = np.ones(inputs_embeds_shapes[i][:2], dtype=np.int64)
            inputs["attention_mask"][i] = np.concatenate(
                [
                    np.pad(
                        attention_mask_inputs_embed,
                        (padding[0], padding[1]),
                        "constant",
                        constant_values=self.padding_value,
                    ),
                    np.zeros(
                        [1, max([*zip(*inputs_embeds_shapes)][1])], dtype=np.int64
                    ),  # if it is batched then we seperate each examples using zero array
                ],
                axis=0,
            )

        inputs["inputs_embeds"] = np.concatenate(inputs["inputs_embeds"], axis=0).astype(np.float32)
        inputs["attention_mask"] = np.concatenate(inputs["attention_mask"], axis=0)

        for i, beatsteps in enumerate(inputs["beatsteps"]):
            padding = (0, max([*zip(*beatsteps_shapes)][0]) - beatsteps_shapes[i][0])
            inputs["beatsteps"][i] = np.pad(beatsteps, padding, "constant", constant_values=self.padding_value)

            # compute attention_mask for beatsteps and add it to dict
            attention_mask_beatsteps = np.ones(beatsteps_shapes[i])
            inputs["attention_mask_beatsteps"][i] = np.pad(
                attention_mask_beatsteps, padding, "constant", constant_values=self.padding_value
            )

        for i, extrapolated_beatstep in enumerate(inputs["extrapolated_beatstep"]):
            padding = (0, max([*zip(*ext_beatstep_shapes)][0]) - ext_beatstep_shapes[i][0])
            inputs["extrapolated_beatstep"][i] = np.pad(
                extrapolated_beatstep, padding, "constant", constant_values=self.padding_value
            )

            # compute attention_mask for extrapolated_beatstep and add it to dict
            attention_mask_extrapolated_beatstep = np.ones(ext_beatstep_shapes[i])
            inputs["attention_mask_extrapolated_beatstep"][i] = np.pad(
                attention_mask_extrapolated_beatstep, padding, "constant", constant_values=self.padding_value
            )

        return inputs

    def __call__(
        self,
        audio: Union[np.ndarray, List[float], List[np.ndarray]],
        sampling_rate: Union[int, List[int]],
        steps_per_beat: int = 2,
        return_attention_mask: Optional[bool] = False,
        return_tensors: Optional[Union[str, TensorType]] = "pt",
        **kwargs,
    ) -> BatchFeature:
        """
        Main method to featurize and prepare for the model.

        Args:
            audio (`np.ndarray`, `List`):
                The sequence or batch of sequences to be processed. Each sequence can be a numpy array, a list of float
                values, a list of numpy arrays or a list of list of float values.
            sampling_rate (`int`):
                The sampling rate at which the `audio` input was sampled. It is strongly recommended to pass
                `sampling_rate` at the forward call to prevent silent errors.
            steps_per_beat (`int`, *optional*, defaults to 2):
                An excellent description of what this argument actually means.
            return_attention_mask (`bool` *optional*, defaults to False):
                Denotes if attention_mask for inputs_embeds, beatsteps and extrapolated_beatstep will be given as
                output or not. Automatically set to True for batched inputs.
            return_tensors (`str` or [`~utils.TensorType`], *optional*, defaults to 'pt'):
                If set, will return tensors instead of list of python integers. Acceptable values are:
                - `'pt'`: Return PyTorch `torch.Tensor` objects.
                - `'np'`: Return Numpy `np.ndarray` objects.
        """
        is_batched = bool(
            isinstance(audio, (list, tuple))
            and (isinstance(audio[0], np.ndarray) or isinstance(audio[0], (tuple, list)))
        )
        if is_batched:
            # This enables the user to process files of different sampling_rate at same time
            if not isinstance(sampling_rate, list):
                raise ValueError(
                    "Please give sampling_rate of each audio separately when you are passing multiple raw_audios at the same time. "
                    f"Received {sampling_rate}, expected [audio_1_sr, ..., audio_n_sr]."
                )
            warnings.warn("return_attention_mask is set to True for batched inputs")
            return_attention_mask = True
        else:
            # To process it in the same pipeline
            audio = [audio]
            sampling_rate = [sampling_rate]

        batch_size = 0
        batch_inputs_embed, batch_beatsteps, batch_ext_beatstep = [], [], []
        for single_raw_audio, single_sampling_rate in zip(audio, sampling_rate):
            # If it's [np.ndarray]
            if isinstance(single_raw_audio, list) and isinstance(single_raw_audio[0], np.ndarray):
                single_raw_audio = single_raw_audio[0]

            bpm, beat_times, confidence, estimates, essentia_beat_intervals = self.extract_rhythm(
                audio=single_raw_audio
            )
            beatsteps = self.interpolate_beat_times(beat_times, steps_per_beat, extend=True)

            if self.sampling_rate != single_sampling_rate and self.sampling_rate is not None:
                # Change sampling_rate to self.sampling_rate
                single_raw_audio = librosa.core.resample(
                    single_raw_audio,
                    orig_sr=single_sampling_rate,
                    target_sr=self.sampling_rate,
                    res_type="kaiser_best",
                )

            single_sampling_rate = self.sampling_rate
            start_sample = int(beatsteps[0] * single_sampling_rate)
            end_sample = int(beatsteps[-1] * single_sampling_rate)

            inputs_embed, extrapolated_beatstep = self.single_preprocess(
                beatstep=beatsteps - beatsteps[0],
                audio=torch.from_numpy(single_raw_audio)[start_sample:end_sample],
            )

            inputs_embed = np.transpose(self.log_mel_spectogram(inputs_embed), (0, -1, -2))

            batch_inputs_embed.append(inputs_embed)
            batch_beatsteps.append(beatsteps)
            batch_ext_beatstep.append(extrapolated_beatstep)
            batch_size += 1

        if return_attention_mask:
            output = BatchFeature(
                {
                    "inputs_embeds": batch_inputs_embed,
                    "beatsteps": batch_beatsteps,
                    "extrapolated_beatstep": batch_ext_beatstep,
                    "attention_mask": [None] * batch_size,
                    "attention_mask_beatsteps": [None] * batch_size,
                    "attention_mask_extrapolated_beatstep": [None] * batch_size,
                }
            )
        else:
            output = BatchFeature(
                {
                    "inputs_embeds": batch_inputs_embed,
                    "beatsteps": batch_beatsteps,
                    "extrapolated_beatstep": batch_ext_beatstep,
                }
            )

        if return_attention_mask:
            output = self.pad(output)

        if not is_batched and not return_attention_mask:
            output["inputs_embeds"] = output["inputs_embeds"][0]

        if return_tensors is not None:
            output = output.convert_to_tensors(return_tensors)

        return output

    def to_dict(self):
        """
        Serializes this instance to a Python dictionary.

        Returns:
            `Dict[str, Any]`: Dictionary of all the attributes that make up this configuration instance.
        """
        output = copy.deepcopy(self.__dict__)
        output["feature_extractor_type"] = self.__class__.__name__
        if "mel_filters" in output:
            del output["mel_filters"]
        return output
