# This file is autogenerated by the command `make fix-copies`, do not edit.
from ..file_utils import requires_backends


class FlaxLogitsProcessor:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])


class FlaxLogitsProcessorList:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])


class FlaxLogitsWarper:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])


class FlaxTemperatureLogitsWarper:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])


class FlaxTopKLogitsWarper:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])


class FlaxTopPLogitsWarper:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])


class FlaxPreTrainedModel:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


FLAX_MODEL_FOR_CAUSAL_LM_MAPPING = None


FLAX_MODEL_FOR_MASKED_LM_MAPPING = None


FLAX_MODEL_FOR_MULTIPLE_CHOICE_MAPPING = None


FLAX_MODEL_FOR_NEXT_SENTENCE_PREDICTION_MAPPING = None


FLAX_MODEL_FOR_PRETRAINING_MAPPING = None


FLAX_MODEL_FOR_QUESTION_ANSWERING_MAPPING = None


FLAX_MODEL_FOR_SEQUENCE_CLASSIFICATION_MAPPING = None


FLAX_MODEL_FOR_TOKEN_CLASSIFICATION_MAPPING = None


FLAX_MODEL_MAPPING = None


class FlaxAutoModel:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxAutoModelForCausalLM:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxAutoModelForMaskedLM:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxAutoModelForMultipleChoice:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxAutoModelForNextSentencePrediction:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxAutoModelForPreTraining:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxAutoModelForQuestionAnswering:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxAutoModelForSequenceClassification:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxAutoModelForTokenClassification:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxBertForMaskedLM:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxBertForMultipleChoice:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxBertForNextSentencePrediction:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])


class FlaxBertForPreTraining:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])


class FlaxBertForQuestionAnswering:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxBertForSequenceClassification:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxBertForTokenClassification:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxBertModel:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxBertPreTrainedModel:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxCLIPModel:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxBigBirdForMaskedLM:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(self, *args, **kwargs):
        requires_backends(self, ["flax"])


class FlaxBigBirdForMultipleChoice:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(self, *args, **kwargs):
        requires_backends(self, ["flax"])


class FlaxBigBirdForPreTraining:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])


class FlaxBigBirdForQuestionAnswering:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(self, *args, **kwargs):
        requires_backends(self, ["flax"])


class FlaxBigBirdForSequenceClassification:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(self, *args, **kwargs):
        requires_backends(self, ["flax"])


class FlaxBigBirdForTokenClassification:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(self, *args, **kwargs):
        requires_backends(self, ["flax"])


class FlaxBigBirdModel:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(self, *args, **kwargs):
        requires_backends(self, ["flax"])


class FlaxBigBirdPreTrainedModel:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(self, *args, **kwargs):
        requires_backends(self, ["flax"])


class FlaxElectraForMaskedLM:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxCLIPTextModel:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxCLIPVisionModel:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxElectraForMaskedLM:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxElectraForMultipleChoice:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxElectraForPreTraining:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])


class FlaxElectraForQuestionAnswering:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxElectraForSequenceClassification:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxElectraForTokenClassification:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxElectraModel:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxElectraPreTrainedModel:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxGPT2LMHeadModel:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxGPT2Model:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxRobertaForMaskedLM:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxRobertaForMultipleChoice:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxRobertaForQuestionAnswering:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxRobertaForSequenceClassification:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxRobertaForTokenClassification:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxRobertaModel:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxRobertaPreTrainedModel:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])


class FlaxViTForImageClassification:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])


class FlaxViTModel:
    def __init__(self, *args, **kwargs):
        requires_backends(self, ["flax"])

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        requires_backends(cls, ["flax"])
