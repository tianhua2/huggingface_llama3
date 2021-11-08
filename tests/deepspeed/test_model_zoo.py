# Copyright 2020 The HuggingFace Team. All rights reserved.
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

import itertools
import os
import subprocess

from parameterized import parameterized
from transformers import is_torch_available
from transformers.testing_utils import (
    ExtendSysPath,
    TestCasePlus,
    execute_subprocess_async,
    get_gpu_count,
    require_deepspeed,
    require_torch_gpu,
    slow,
)
from transformers.trainer_utils import set_seed


tests_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
root_dir = os.path.dirname(tests_dir)
with ExtendSysPath(tests_dir):
    from test_trainer import TrainerIntegrationCommon  # noqa

    if is_torch_available():
        from test_trainer import RegressionModelConfig, RegressionPreTrainedModel, get_regression_trainer  # noqa


set_seed(42)

# default torch.distributed port
DEFAULT_MASTER_PORT = "10999"

# translation
FSMT_TINY = "stas/tiny-wmt19-en-de"
BART_TINY = "sshleifer/bart-tiny-random"
T5_SMALL = "t5-small"
T5_TINY = "patrickvonplaten/t5-tiny-random"
MBART_TINY = "sshleifer/tiny-mbart"
MARIAN_TINY = "sshleifer/tiny-marian-en-de"

# summarization
PEGASUS_TINY = "stas/pegasus-cnn_dailymail-tiny-random"

# causal lm
GPT2_TINY = "sshleifer/tiny-gpt2"
XLM_ROBERTA_TINY = "hf-internal-testing/tiny-xlm-roberta"

# question-answering
ROBERTA_TINY = "sshleifer/tiny-distilroberta-base"

# masked lm
DISTILBERT_TINY = "sshleifer/tiny-distilbert-base-cased"
ELECTRA_TINY = "hf-internal-testing/tiny-electra"

# classification
XLNET_TINY = "sshleifer/tiny-xlnet-base-cased"
BERT_TINY = "hf-internal-testing/tiny-bert"


# TODO: to add:
# albert
# deberta
# funnel
# longformer
# dpr
# gpt_neo
# camembert
# deberta-v2
# m2m_100
# tapas
# vit
# big_bird


def get_launcher(distributed=False):
    # 1. explicitly set --num_nodes=1 just in case these tests end up run on a multi-node setup
    # - it won't be able to handle that
    # 2. for now testing with just 2 gpus max (since some quality tests may give different
    # results with mode gpus because we use very little data)
    num_gpus = min(2, get_gpu_count()) if distributed else 1
    master_port = os.environ.get('DS_TEST_PORT', DEFAULT_MASTER_PORT)
    return f"deepspeed --num_nodes 1 --num_gpus {num_gpus} --master_port {master_port}".split()


def make_task_cmds():
    data_dir_fixtures = f"{tests_dir}/fixtures"
    data_dir_samples = f"{data_dir_fixtures}/tests_samples"
    data_dir_wmt = f"{data_dir_samples}/wmt_en_ro"
    data_dir_xsum = f"{data_dir_samples}/xsum"
    args_main = """
        --do_train
        --max_train_samples 4
        --per_device_train_batch_size 2
        --num_train_epochs 1
        --fp16
        --report_to none
        --overwrite_output_dir
        """.split()

    # XXX: try to cover as many models as possible once (it's enough to run on one task per model)
    # but need a tiny model for each
    #
    # should have T5_TINY, etc. global var defined
    tasks2models = dict(
        trans=[
            "bart",
            "fsmt",
            "marian",
            "mbart",
            "t5",
        ],
        sum=[
            "pegasus",
        ],
        clm=[
            "gpt2",
            "xlm-roberta",
        ],
        mlm=[
            "electra",
            "distilbert",
        ],
        qa=[
            "roberta",
        ],
        clas=[
            "bert",
            "xlnet",
        ],
    )

    scripts_dir = f"{root_dir}/examples/pytorch"

    tasks = dict(
        trans=f"""
        {scripts_dir}/translation/run_translation.py
        --train_file {data_dir_wmt}/train.json
        --source_lang en
        --target_lang ro
        """,
        sum=f"""
        {scripts_dir}/summarization/run_summarization.py
        --train_file {data_dir_xsum}/sample.json
        --max_source_length 12
        --max_target_length 12
        """,
        clm=f"""
        {scripts_dir}/language-modeling/run_clm.py
        --train_file {data_dir_fixtures}/sample_text.txt
        --block_size 8
        """,
        mlm=f"""
        {scripts_dir}/language-modeling/run_mlm.py
        --train_file {data_dir_fixtures}/sample_text.txt
        """,
        qa=f"""
        {scripts_dir}/question-answering/run_qa.py
        --train_file {data_dir_samples}/SQUAD/sample.json
        """,
        clas=f"""
        {scripts_dir}/text-classification/run_glue.py
        --train_file {data_dir_samples}/MRPC/train.csv
        --max_seq_length 12
        --task_name MRPC
        """,
    )

    launcher = get_launcher(distributed=True)

    cmds = {}
    for task, args in tasks.items():
        args = args.split()
        for model in tasks2models[task]:
            model_name = globals()[f"{model.upper().replace('-', '_')}_TINY"]
            args_model = f"--model_name_or_path {model_name}".split()
            cmds[f"{task}_{model}"] = launcher + args + args_model + args_main

            # # generation special case
            # if task == "gen":
            #     launcher = f"deepspeed --num_nodes 1 --num_gpus 1".split()
            #     args_model += f"--model_type {model}".split()
            #     cmds[f"{task}_{model}"] = launcher + args + args_model
            # else:

    return cmds


task_cmds = make_task_cmds()

ZERO2 = "zero2"
ZERO3 = "zero3"
stages = [ZERO2, ZERO3]


def parameterized_custom_name_func(func, param_num, param):
    # customize the test name generator function as we want both params to appear in the sub-test
    # name, as by default it shows only the first param
    param_based_name = parameterized.to_safe_name("_".join(str(x) for x in param.args))
    return f"{func.__name__}_{param_based_name}"


# Cartesian-product of zero stages with models to test
params = list(itertools.product(stages, task_cmds.keys()))


@slow
@require_deepspeed
@require_torch_gpu
class TestDeepSpeedModelZoo(TestCasePlus):
    """This class is for testing via an external script - can do multiple gpus"""

    def get_task_cmd(self, task, stage):
        # return a ready to run train cmd
        if task not in task_cmds:
            raise ValueError(f"don't know of task {task}, have {task_cmds.keys()}")

        cmd = task_cmds[task]
        args_ds = f"--deepspeed {self.test_file_dir_str}/ds_config_{stage}.json".split()

        output_dir = self.get_auto_remove_tmp_dir()
        args_out = f"--output_dir {output_dir}".split()

        cmd += args_ds + args_out

        return cmd, output_dir

    @parameterized.expand(params, name_func=parameterized_custom_name_func)
    def test_zero_to_fp32(self, stage, task):
        # testing the ability to do a run followed by recovery of full fp32 weights

        cmd, output_dir = self.get_task_cmd(task, stage)

        # 1. generate the checkpoint
        cmd += "--save_steps 1".split()
        # keep for quick debug
        # print(" ".join([f"\nPYTHONPATH={self.src_dir_str}"] + cmd)); die
        execute_subprocess_async(cmd, env=self.get_env())

        # 2. test that the fp32 weights get reconsolidated
        chkpt_dir = f"{output_dir}/checkpoint-1"
        recovered_model_path = f"{chkpt_dir}/out.bin"
        cmd = f"{chkpt_dir}/zero_to_fp32.py {chkpt_dir} {recovered_model_path}"
        # keep for quick debug
        # print(" ".join([f"\nPYTHONPATH={self.src_dir_str}"] +cmd)); die
        subprocess.check_call(cmd, shell=True)
        assert os.path.exists(recovered_model_path), f"{recovered_model_path} was not found"

        # possibly could also test that the resulting saved model is usable but given that we use
        # random models we won't know if it's any good
