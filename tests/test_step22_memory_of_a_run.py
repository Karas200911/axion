"""Axion v0.3, step 22: the memory of one run has a total limit (max_memory_mb, default 256).

Before this step the limits bounded one list (1,000,000 elements) and one text (1,000,000
characters), but not everything together. A program within every limit could keep 20,000 large
texts or a thousand copies of a large list and use up the memory; `axionlang.run` then ended with a
Python MemoryError instead of an Axion error. Now every value the program stores is counted
(size_of), and the run stops with R406 when the total passes the limit. A variable overwritten
with a new value frees the old one, so an ordinary loop that rebuilds a text or a number is not
counted against it.
"""
import sys
import unittest
from pathlib import Path

from helpers import AxionTest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import axionlang  # noqa: E402

BIG_TEXTS = ('s = "a"\nfor i in 1 to 19\ns = s + s\nend\n'       # s is 524,288 characters
             'xs = [] of text\nfor i in 1 to 20000\nxs add s + "b"\nend\nprint xs length\n')
BIG_LISTS = ('row = 1 to 1000000\ngrid = [] of list of number\n'
             'for i in 1 to 1000\ngrid add row\nend\nprint grid length\n')


class TheTwoAttacksAreStopped(AxionTest):
    def test_many_big_texts(self):
        out = self.assertError(BIG_TEXTS, "R406")
        self.assertIn("kept more than 256 MB of data", " ".join(out))

    def test_many_copies_of_a_big_list(self):
        out = self.assertError(BIG_LISTS, "R406")
        self.assertIn("kept more than 256 MB", " ".join(out))

    def test_through_the_library(self):
        r = axionlang.run(BIG_TEXTS)
        self.assertEqual((r.ok, r.error.code), (False, "R406"))


class OrdinaryProgramsStillRun(AxionTest):
    def test_a_long_list_of_numbers(self):
        self.assertOutput("xs = [] of number\nfor i in 1 to 100000\nxs add i * 3\nend\nprint xs length",
                          ["100000"])

    def test_a_text_built_in_a_loop(self):
        # 20,000 passes: the text grows to 40,000 characters, but each old value is freed
        self.assertOutput('s = ""\nfor i in 1 to 20000\ns = s + "ab"\nend\nprint s length', ["40000"])

    def test_a_number_accumulated_in_a_loop(self):
        self.assertOutput("t = 0\nfor i in 1 to 200000\nt = t + i\nend\nprint t", ["20000100000"])

    def test_reusing_a_variable_for_a_fresh_list_each_pass(self):
        self.assertOutput("n = 0\nfor i in 1 to 5000\nys = 1 to 1000\nn = n + ys length\nend\nprint n",
                          ["5000000"])

    def test_nested_data_within_the_limit(self):
        self.assertOutput("grid = [] of list of number\nfor i in 1 to 100\ngrid add (1 to 1000)\nend\n"
                          "print grid length", ["100"])


class TheLimitIsSetByThePolicy(AxionTest):
    def test_a_smaller_limit_stops_sooner(self):
        program = "xs = [] of text\nbig = \"\"\nfor i in 1 to 20\nbig = big + \"xxxxxxxxxx\"\nend\n" + \
                  "for i in 1 to 100000\nxs add big\nend\nprint xs length"
        self.assertOutput(program, ["100000"])                         # fits under the default 256 MB
        r = axionlang.run(program, max_memory_mb=1)
        self.assertEqual((r.ok, r.error.code), (False, "R406"))
        self.assertIn("more than 1 MB", r.error.message)

    def test_a_larger_limit_allows_more(self):
        r = axionlang.run(BIG_TEXTS)                                        # stops at 256
        self.assertEqual(r.error.code, "R406")

    def test_the_policy_rejects_a_bad_value(self):
        with self.assertRaises(ValueError):
            axionlang.run("print 1", max_memory_mb=0)

    def test_from_a_policy_dict(self):
        from axionlang.engine.policy import Policy
        p = Policy.from_dict({"max_memory_mb": 64})
        self.assertEqual(p.limits["max_memory_mb"], 64)


class TheSizeOfAValue(unittest.TestCase):
    def test_bool_is_free_and_number_is_small(self):
        from axionlang.engine.values import size_of
        from decimal import Decimal
        self.assertEqual(size_of(True), 0)
        self.assertLess(size_of(Decimal("1.5")), 200)
        self.assertGreater(size_of("a" * 1000), 1000)
        self.assertGreater(size_of([Decimal(1)] * 100), 100 * 100)


if __name__ == "__main__":
    unittest.main()
