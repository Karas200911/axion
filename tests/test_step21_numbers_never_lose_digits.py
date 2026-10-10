"""Axion v0.3, step 21: a whole number never loses its last digits without a word.

Before this step `print 2 ** 100` printed 1267650600228229401496703205000: the right answer is
1267650600228229401496703205376, and nothing said that the last digits were gone. Now a number
with more than 28 digits before the point does not exist. It is refused wherever it could
appear: as a result (R412), in the program text (L104), in the input data (R407), in a text
turned into a number (`is number` is false, `as number` is R404, a literal text is V314).

What stays: digits after the point beyond the 28 are rounded, as in 1 / 3.
"""
import math
import sys
import unittest
from decimal import Decimal
from pathlib import Path

from helpers import AxionTest, run

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import axionlang  # noqa: E402

MAX = "9" * 28                    # the largest whole number
OVER = "1" + "0" * 28             # the first one that does not fit
TOO_LARGE = "A number became too large here: a number keeps 28 digits and cannot grow without end."


class TheLargestNumberStillWorks(AxionTest):
    def test_the_edge_is_exact(self):
        self.assertOutput(f"x = {MAX}\nprint x\nprint x - 1\nprint 0 - x\nprint x % 10\nprint x // 3",
                          [MAX, "9" * 27 + "8", "-" + MAX, "9", "3" * 28])

    def test_whole_arithmetic_below_the_edge_is_exact(self):
        self.assertOutput("print 2 ** 93", ["9903520314283042199192993792"])
        self.assertOutput("print 99999999999999 * 99999999999999", ["9999999999999800000000000001"])
        self.assertOutput("f = 1\nfor i in 1 to 26\nf = f * i\nend\nprint f", [str(math.factorial(26))])

    def test_a_fraction_is_rounded_as_before(self):
        self.assertOutput("print 1 / 3", ["0." + "3" * 28])
        self.assertOutput("print 1000000 + 1 / 3", ["1000000." + "3" * 21])
        self.assertOutput("print 2 ** 0.5", ["1.414213562373095048801688724"])

    def test_small_numbers_are_not_touched(self):
        self.assertOutput("print 10 ** (0 - 30)", ["0." + "0" * 29 + "1"])
        self.assertOutput("x = 0\nprint x * 10 ** 27 * 10", ["0"])


class AResultThatDoesNotFit(AxionTest):
    def test_power(self):
        out = self.assertError("print 2 ** 100", "R412")
        self.assertEqual(out, ["ERROR R412 line 1:7", "print 2 ** 100", "      ^^^^^^^^",
                               "The result of ** is too large for a number."])
        self.assertError("print 10 ** 28", "R412")
        self.assertError("print (0 - 10) ** 29", "R412")

    def test_multiply(self):
        out = self.assertError(f'print "a"\nx = {MAX}\ny = x * 10\nprint y', "R412", printed_before=["a"])
        self.assertEqual(out, ["ERROR R412 line 3:5", "y = x * 10", "    ^^^^^^", TOO_LARGE])

    def test_add_and_subtract(self):
        self.assertError(f"x = {MAX}\nprint x + 1", "R412")
        self.assertError(f"x = 0 - {MAX}\nprint x - 1", "R412")
        self.assertOutput(f"x = {MAX}\nprint x + 0.4", [MAX])         # the fraction is rounded, the whole part is whole
        self.assertError(f"x = {MAX}\nprint x + 0.5", "R412")         # rounds up to 29 digits

    def test_divide(self):
        out = self.assertError(f"x = {MAX}\nprint x / 0.5", "R412")
        self.assertIn(TOO_LARGE, out)

    def test_sum(self):
        out = self.assertError(f"xs = [{MAX}, 1, 0 - 5]\nprint xs sum", "R412")
        self.assertIn(TOO_LARGE, out)
        self.assertOutput(f"xs = [{MAX}, 0 - 5, 1]\nprint xs sum", ["9" * 27 + "5"])

    def test_rounding_up_over_the_edge(self):
        self.assertOutput(f"x = {MAX}.4\nprint x\nprint x round 0\nprint x floor", [MAX, MAX, MAX])
        self.assertError(f"x = {MAX}.4\nprint x ceiling", "R412")
        self.assertOutput(f"x = {MAX}.44\nprint x round 1", [MAX])       # 28 nines and .4 fits
        self.assertError(f"x = {MAX}.45\nprint x round 1", "R412")       # 28 nines and .5 does not
        self.assertOutput("x = 999999999999999999999999999.5\nprint x round 0\nprint x ceiling\nprint x floor",
                          ["1" + "0" * 27, "1" + "0" * 27, "9" * 27])

    def test_a_factorial_stops_instead_of_lying(self):
        out = self.assertError("f = 1\nfor i in 1 to 30\nf = f * i\nend\nprint f", "R412")    # 27! has 29 digits
        self.assertEqual(out[0], "ERROR R412 line 3:5")

    def test_nothing_is_printed_after_it(self):
        code, out = run('print "before"\nx = 10 ** 14\nprint x * x\nprint "after"')
        self.assertEqual((code, out[0], out[1]), (1, "before", "ERROR R412 line 3:7"))
        self.assertNotIn("after", out)


class ANumberWrittenInTheProgram(AxionTest):
    def test_twenty_nine_digits(self):
        out = self.assertError(f"print 1\nx = {OVER}\nprint x", "L104")
        self.assertEqual(out, ["ERROR L104 line 2:5", f"x = {OVER}", "    " + "^" * 29,
                               f"Invalid number {OVER}: a number keeps 28 digits."])

    def test_with_a_fraction(self):
        self.assertError(f"x = {OVER}.5", "L104")
        self.assertOutput(f"x = {MAX}.4\nprint x", [MAX])
        self.assertError(f"x = {MAX}.5\nprint x", "L104")                # would print as 1 and 28 zeros

    def test_the_hint_never_offers_a_number_that_is_refused(self):
        out = self.assertError("x = 1e40", "L104")
        self.assertFalse(any(line.startswith("Fix: write 1000") for line in out), out)
        self.assertIn("Fix: write 100000", self.assertError("x = 1e5", "L104"))


class ANumberInTheInputData(AxionTest):
    PROGRAM = "input n: number\nprint n + 1"

    def test_too_large(self):
        out = self.assertError(self.PROGRAM, "R407", data='{"n": %s}' % OVER)
        self.assertIn("Input data: n is too large for a number: a number keeps 28 digits.", out)
        self.assertError(self.PROGRAM, "R407", data='{"n": 1e400}')
        self.assertError(self.PROGRAM, "R407", data='{"n": -%s}' % OVER)

    def test_the_largest_fits(self):
        self.assertError(self.PROGRAM, "R412", data='{"n": %s}' % MAX)        # n + 1 does not fit
        self.assertOutput("input n: number\nprint n - 1", ["9" * 27 + "8"], data='{"n": %s}' % MAX)
        self.assertOutput(self.PROGRAM, ["1001"], data='{"n": 1e3}')

    def test_inside_a_list_and_an_object(self):
        out = self.assertError("input rows: list of {amount: number}\nprint rows length", "R407",
                               data='{"rows": [{"amount": 5}, {"amount": %s}]}' % OVER)
        self.assertIn("Input data: rows[1].amount is too large for a number: a number keeps 28 digits.", out)
        out = self.assertError("input m: map of number\nprint m length", "R407", data='{"m": {"a": %s}}' % OVER)
        self.assertIn('m["a"] is too large', " ".join(out))

    def test_through_the_library(self):
        r = axionlang.run(self.PROGRAM, {"n": 10 ** 30 + 7})
        self.assertEqual((r.ok, r.output, r.error.code), (False, [], "R407"))
        r = axionlang.run(self.PROGRAM, {"n": Decimal("1E+28")})
        self.assertEqual(r.error.code, "R407")
        self.assertEqual(axionlang.run(self.PROGRAM, {"n": 10 ** 27}).output, ["1" + "0" * 26 + "1"])
        with self.assertRaises(ValueError):
            axionlang.describe({"n": 10 ** 28})


class ATextTurnedIntoANumber(AxionTest):
    def test_is_number_and_as_number_agree(self):
        program = 'input s: text\nif s is number\nprint s as number\nelse\nprint "no"\nend'
        self.assertOutput(program, ["no"], data='{"s": "%s"}' % OVER)
        self.assertOutput(program, [MAX], data='{"s": "%s"}' % MAX)
        self.assertOutput(program, ["no"], data='{"s": "-%s.25"}' % OVER)

    def test_as_number_without_a_check(self):
        out = self.assertError("input s: text\nprint s as number", "R404", data='{"s": "%s"}' % OVER)
        self.assertIn(f'"{OVER}" cannot be converted to number: a number keeps 28 digits.', out)
        self.assertIn("Fix: check first: if s is number", out)

    def test_a_text_written_in_the_program(self):
        out = self.assertError(f'print "{OVER}" as number', "V314")
        self.assertIn(f'"{OVER}" is too large for a number: a number keeps 28 digits.', out)
        self.assertOutput(f'print "{MAX}" as number', [MAX])


if __name__ == "__main__":
    unittest.main()
