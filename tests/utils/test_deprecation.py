# Copyright 2024 The HuggingFace Team. All rights reserved.
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

import unittest
import warnings

from transformers import __version__
from transformers.utils.deprecation import deprecate_kwarg


class DeprecationDecoratorTester(unittest.TestCase):
    INFINITE_VERSION = "9999.0.0"

    def test_rename_kwarg(self):

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            @deprecate_kwarg("deprecated_name", new_name="new_name", version=self.INFINITE_VERSION)
            def dummy_function(new_name=None, other_name=None):
                return new_name, other_name

            # Test keyword argument is renamed
            value, other_value = dummy_function(deprecated_name="old_value")
            self.assertEqual(value, "old_value")
            self.assertIsNone(other_value)

            # Test deprecated keyword argument not passed
            value, other_value = dummy_function(new_name="new_value")
            self.assertEqual(value, "new_value")
            self.assertIsNone(other_value)

            # Test other keyword argument
            value, other_value = dummy_function(other_name="other_value")
            self.assertIsNone(value)
            self.assertEqual(other_value, "other_value")

            # Test deprecated and new args are passed, the new one should be returned
            value, other_value = dummy_function(deprecated_name="old_value", new_name="new_value")
            self.assertEqual(value, "new_value")
            self.assertIsNone(other_value)


    def test_rename_multiple_kwargs(self):

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            @deprecate_kwarg("deprecated_name1", new_name="new_name1", version=self.INFINITE_VERSION)
            @deprecate_kwarg("deprecated_name2", new_name="new_name2", version=self.INFINITE_VERSION)
            def dummy_function(new_name1=None, new_name2=None, other_name=None):
                return new_name1, new_name2, other_name

            # Test keyword argument is renamed
            value1, value2, other_value = dummy_function(deprecated_name1="old_value1", deprecated_name2="old_value2")
            self.assertEqual(value1, "old_value1")
            self.assertEqual(value2, "old_value2")
            self.assertIsNone(other_value)

            # Test deprecated keyword argument is not passed
            value1, value2, other_value = dummy_function(new_name1="new_value1", new_name2="new_value2")
            self.assertEqual(value1, "new_value1")
            self.assertEqual(value2, "new_value2")
            self.assertIsNone(other_value)

            # Test other keyword argument is passed and correctly returned
            value1, value2, other_value = dummy_function(other_name="other_value")
            self.assertIsNone(value1)
            self.assertIsNone(value2)
            self.assertEqual(other_value, "other_value")


    def test_warnings(self):

        # Test warning is raised for future version
        @deprecate_kwarg("deprecated_name", new_name="new_name", version=self.INFINITE_VERSION)
        def dummy_function(new_name=None, other_name=None):
            return new_name, other_name

        with self.assertWarns(DeprecationWarning):
            dummy_function(deprecated_name="old_value")

        # Test warning is not raised for past version, but arg is still renamed
        @deprecate_kwarg("deprecated_name", new_name="new_name", version="0.0.0")
        def dummy_function(new_name=None, other_name=None):
            return new_name, other_name

        with warnings.catch_warnings(record=True) as raised_warnings:
            warnings.simplefilter("always")

            value, other_value = dummy_function(deprecated_name="old_value")

            self.assertEqual(value, "old_value")
            self.assertIsNone(other_value)
            self.assertEqual(len(raised_warnings), 0, f"Warning raised: {[w.message for w in raised_warnings]}")

        # Test warning is raised for future version if warn_if_greater_or_equal_version is set
        @deprecate_kwarg("deprecated_name", version="0.0.0", warn_if_greater_or_equal_version=True)
        def dummy_function(deprecated_name=None):
            return deprecated_name
        
        with self.assertWarns(DeprecationWarning):
            value = dummy_function(deprecated_name="deprecated_value")
        self.assertEqual(value, "deprecated_value")

        # Test arg is not renamed if new_name is not specified, but warning is raised
        @deprecate_kwarg("deprecated_name", version=self.INFINITE_VERSION)
        def dummy_function(deprecated_name=None):
            return deprecated_name

        with self.assertWarns(DeprecationWarning):
            value = dummy_function(deprecated_name="deprecated_value")
        self.assertEqual(value, "deprecated_value")


    def test_raises(self):

        # Test if deprecated name and new name are both passed and raise_if_both_names is set -> raise error
        @deprecate_kwarg("deprecated_name", new_name="new_name", version=self.INFINITE_VERSION, raise_if_both_names=True)
        def dummy_function(new_name=None, other_name=None):
            return new_name, other_name
        
        with self.assertRaises(ValueError):
            dummy_function(deprecated_name="old_value", new_name="new_value")

        # Test for current version == deprecation version
        @deprecate_kwarg("deprecated_name", version=__version__, raise_if_greater_or_equal_version=True)
        def dummy_function(deprecated_name=None):
            return deprecated_name
        
        with self.assertRaises(ValueError):
            dummy_function(deprecated_name="old_value")

        # Test for current version > deprecation version
        @deprecate_kwarg("deprecated_name", version="0.0.0", raise_if_greater_or_equal_version=True)
        def dummy_function(deprecated_name=None):
            return deprecated_name
        
        with self.assertRaises(ValueError):
            dummy_function(deprecated_name="old_value")

    def test_additional_message(self):
        
        # Test additional message is added to the warning
        @deprecate_kwarg("deprecated_name", version=self.INFINITE_VERSION, additional_message="Additional message")
        def dummy_function(deprecated_name=None):
            return deprecated_name
        
        with warnings.catch_warnings(record=True) as raised_warnings:
            warnings.simplefilter("always")
            dummy_function(deprecated_name="old_value")

            self.assertTrue("Additional message" in str(raised_warnings[0].message))