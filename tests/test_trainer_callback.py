import shutil
import tempfile
import unittest

from transformers import (
    DefaultFlowCallback,
    EvaluationStrategy,
    PrinterCallback,
    ProgressCallback,
    Trainer,
    TrainerCallback,
    TrainingArguments,
)
from transformers.testing_utils import require_torch
from transformers.trainer import DEFAULT_CALLBACKS

from .test_trainer import RegressionDataset, RegressionModelConfig, RegressionPreTrainedModel


class TestTrainerCallback(TrainerCallback):
    "A callback that registers the events that goes through."

    def __init__(self):
        self.events = []

    def on_init_end(self, args, state, control, **kwargs):
        self.events.append("on_init_end")

    def on_train_begin(self, args, state, control, **kwargs):
        self.events.append("on_train_begin")

    def on_train_end(self, args, state, control, **kwargs):
        self.events.append("on_train_end")

    def on_epoch_begin(self, args, state, control, **kwargs):
        self.events.append("on_epoch_begin")

    def on_epoch_end(self, args, state, control, **kwargs):
        self.events.append("on_epoch_end")

    def on_step_begin(self, args, state, control, **kwargs):
        self.events.append("on_step_begin")

    def on_step_end(self, args, state, control, **kwargs):
        self.events.append("on_step_end")

    def on_evaluate(self, args, state, control, **kwargs):
        self.events.append("on_evaluate")

    def on_save(self, args, state, control, **kwargs):
        self.events.append("on_save")

    def on_log(self, args, state, control, **kwargs):
        self.events.append("on_log")

    def on_prediction_step(self, args, state, control, **kwargs):
        self.events.append("on_prediction_step")


@require_torch
class TrainerCallbackTest(unittest.TestCase):
    def setUp(self):
        self.output_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.output_dir)

    def get_trainer(self, a=0, b=0, train_len=64, eval_len=64, callbacks=None, **kwargs):
        train_dataset = RegressionDataset(length=train_len)
        eval_dataset = RegressionDataset(length=eval_len)
        config = RegressionModelConfig(a=a, b=b)
        model = RegressionPreTrainedModel(config)

        args = TrainingArguments(self.output_dir, **kwargs)
        return Trainer(
            model,
            args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            callbacks=callbacks,
        )

    def check_callbacks_equality(self, cbs1, cbs2):
        self.assertEqual(len(cbs1), len(cbs2))

        # Order doesn't matter
        cbs1 = list(sorted(cbs1, key=lambda cb: cb.__name__ if isinstance(cb, type) else cb.__class__.__name__))
        cbs2 = list(sorted(cbs2, key=lambda cb: cb.__name__ if isinstance(cb, type) else cb.__class__.__name__))

        for cb1, cb2 in zip(cbs1, cbs2):
            if isinstance(cb1, type) and isinstance(cb2, type):
                self.assertEqual(cb1, cb2)
            elif isinstance(cb1, type) and not isinstance(cb2, type):
                self.assertEqual(cb1, cb2.__class__)
            elif not isinstance(cb1, type) and isinstance(cb2, type):
                self.assertEqual(cb1.__class__, cb2)
            else:
                self.assertEqual(cb1, cb2)

    def get_expected_events(self, trainer):
        expected_events = ["on_init_end", "on_train_begin"]
        step = 0
        train_dl_len = len(trainer.get_eval_dataloader())
        evaluation_events = ["on_prediction_step"] * len(trainer.get_eval_dataloader()) + ["on_log", "on_evaluate"]
        for _ in range(trainer.state.num_train_epochs):
            expected_events.append("on_epoch_begin")
            for _ in range(train_dl_len):
                step += 1
                expected_events += ["on_step_begin", "on_step_end"]
                if step % trainer.args.logging_steps == 0:
                    expected_events.append("on_log")
                if (
                    trainer.args.evaluation_strategy == EvaluationStrategy.STEPS
                    and step % trainer.args.eval_steps == 0
                ):
                    expected_events += evaluation_events.copy()
                if step % trainer.args.save_steps == 0:
                    expected_events.append("on_save")
            expected_events.append("on_epoch_end")
            if trainer.args.evaluation_strategy == EvaluationStrategy.EPOCH:
                expected_events += evaluation_events.copy()
        expected_events.append("on_train_end")
        return expected_events

    def test_init_callback(self):
        trainer = self.get_trainer()
        expected_callbacks = DEFAULT_CALLBACKS + [ProgressCallback]
        self.check_callbacks_equality(trainer.callback_handler.callbacks, expected_callbacks)

        # Callbacks passed at init are added to the default callbacks
        trainer = self.get_trainer(callbacks=[TestTrainerCallback])
        expected_callbacks.append(TestTrainerCallback)
        self.check_callbacks_equality(trainer.callback_handler.callbacks, expected_callbacks)

        # TrainingArguments.disable_tqdm controls if use ProgressCallback or PrinterCallback
        trainer = self.get_trainer(disable_tqdm=True)
        expected_callbacks = DEFAULT_CALLBACKS + [PrinterCallback]
        self.check_callbacks_equality(trainer.callback_handler.callbacks, expected_callbacks)

    def test_add_remove_callback(self):
        expected_callbacks = DEFAULT_CALLBACKS.copy() + [ProgressCallback]
        trainer = self.get_trainer()

        # We can add, pop, or remove by class name
        trainer.remove_callback(DefaultFlowCallback)
        expected_callbacks.remove(DefaultFlowCallback)
        self.check_callbacks_equality(trainer.callback_handler.callbacks, expected_callbacks)

        trainer = self.get_trainer()
        cb = trainer.pop_callback(DefaultFlowCallback)
        self.assertEqual(cb.__class__, DefaultFlowCallback)
        self.check_callbacks_equality(trainer.callback_handler.callbacks, expected_callbacks)

        trainer.add_callback(DefaultFlowCallback)
        expected_callbacks.insert(0, DefaultFlowCallback)
        self.check_callbacks_equality(trainer.callback_handler.callbacks, expected_callbacks)

        # We can also add, pop, or remove by instance
        trainer = self.get_trainer()
        cb = trainer.callback_handler.callbacks[0]
        trainer.remove_callback(cb)
        expected_callbacks.remove(DefaultFlowCallback)
        self.check_callbacks_equality(trainer.callback_handler.callbacks, expected_callbacks)

        trainer = self.get_trainer()
        cb1 = trainer.callback_handler.callbacks[0]
        cb2 = trainer.pop_callback(cb1)
        self.assertEqual(cb1, cb2)
        self.check_callbacks_equality(trainer.callback_handler.callbacks, expected_callbacks)

        trainer.add_callback(cb1)
        expected_callbacks.insert(0, DefaultFlowCallback)
        self.check_callbacks_equality(trainer.callback_handler.callbacks, expected_callbacks)

    def test_event_flow(self):
        trainer = self.get_trainer(callbacks=[TestTrainerCallback])
        trainer.train()
        events = trainer.callback_handler.callbacks[-2].events
        self.assertEqual(events, self.get_expected_events(trainer))

        # Independent log/save/eval
        trainer = self.get_trainer(callbacks=[TestTrainerCallback], logging_steps=5)
        trainer.train()
        events = trainer.callback_handler.callbacks[-2].events
        self.assertEqual(events, self.get_expected_events(trainer))

        trainer = self.get_trainer(callbacks=[TestTrainerCallback], save_steps=5)
        trainer.train()
        events = trainer.callback_handler.callbacks[-2].events
        self.assertEqual(events, self.get_expected_events(trainer))

        trainer = self.get_trainer(callbacks=[TestTrainerCallback], eval_steps=5, evaluation_strategy="steps")
        trainer.train()
        events = trainer.callback_handler.callbacks[-2].events
        self.assertEqual(events, self.get_expected_events(trainer))

        trainer = self.get_trainer(callbacks=[TestTrainerCallback], evaluation_strategy="epoch")
        trainer.train()
        events = trainer.callback_handler.callbacks[-2].events
        self.assertEqual(events, self.get_expected_events(trainer))

        # A bit of everything
        trainer = self.get_trainer(
            callbacks=[TestTrainerCallback], logging_steps=3, save_steps=10, eval_steps=5, evaluation_strategy="steps"
        )
        trainer.train()
        events = trainer.callback_handler.callbacks[-2].events
        self.assertEqual(events, self.get_expected_events(trainer))
