"""Step 2 — bool, comparisons, and/or/not, unary minus, %.

Written from the v0.2 documentation (§5, §7).
"""

import unittest

from helpers import AxionTest


class Bools(AxionTest):
    def test_literals(self):
        self.assertOutput("print true\nprint false", ["true", "false"])

    def test_variable(self):
        self.assertOutput("ok = true\nprint ok", ["true"])

    def test_type_is_fixed(self):
        self.assertError("ok = true\nok = 1", "V302")

    def test_keyword_cannot_be_name(self):
        self.assertError("true = 1", "P214")

    def test_no_arithmetic_on_bool(self):
        self.assertError("print true + 1", "V301")


class Comparisons(AxionTest):
    def test_numbers(self):
        self.assertOutput("print 18 >= 18\nprint 3 < 2\nprint 3 > 2\nprint 2 <= 1",
                          ["true", "false", "true", "false"])

    def test_equality(self):
        self.assertOutput("print 1 == 2 / 2\nprint 1 != 1", ["true", "false"])

    def test_decimal_equality(self):
        self.assertOutput("print 0.1 + 0.2 == 0.3", ["true"])

    def test_text_equality_is_case_sensitive(self):
        self.assertOutput('print "Egor" == "Egor"\nprint "Egor" == "egor"\nprint "a" != "b"',
                          ["true", "false", "true"])

    def test_bool_equality(self):
        self.assertOutput("print true == false\nprint false != true", ["false", "true"])

    def test_arithmetic_binds_tighter(self):
        self.assertOutput("a = 5\nprint a + 1 > 5", ["true"])

    def test_different_types(self):
        out = self.assertError('print 10 == "10"', "V308")
        self.assertIn('Fix: convert the text side: "10" as number', out)

    def test_fix_never_leads_to_new_error(self):
        # "abc" as number would itself fail, so no conversion is suggested.
        out = self.assertError('print 10 == "abc"', "V308")
        self.assertFalse(any(line.startswith("Fix:") for line in out), out)

    def test_text_is_ordered_by_character_code(self):
        # v0.3: until then text had no order (V308)
        self.assertOutput('print "a" < "b"', ["true"])
        self.assertError('print "a" < 1', "V308")

    def test_bool_has_no_ordering(self):
        self.assertError("print true > false", "V308")

    def test_no_chains(self):
        out = self.assertError("age = 20\nprint 18 <= age <= 25", "P206")
        self.assertIn("Fix: 18 <= age and age <= 25", out)

    def test_no_equality_chains(self):
        self.assertError("a = 1\nb = 1\nc = 1\nprint a == b == c", "P206")

    def test_assignment_inside_expression(self):
        out = self.assertError("a = 1\nprint a = 5", "P202")
        self.assertIn("Fix: print a == 5", out)


class Logic(AxionTest):
    def test_and_or_not(self):
        self.assertOutput("print true and false\nprint true or false\nprint not true",
                          ["false", "true", "false"])

    def test_with_comparisons(self):
        self.assertOutput("age = 20\nprint age >= 18 and age <= 25", ["true"])

    def test_not_with_parentheses(self):
        self.assertOutput("print not (true and false)", ["true"])
        self.assertOutput("a = 20\nprint not (a >= 18)", ["false"])

    def test_mixing_with_parentheses(self):
        self.assertOutput("print true or (true and false)", ["true"])
        self.assertOutput("print (true or true) and false", ["false"])

    def test_same_operator_chain(self):
        self.assertOutput("print true and true and false", ["false"])
        self.assertOutput("print false or false or true", ["true"])

    def test_mixing_without_parentheses(self):
        self.assertError("print true or true and false", "P205")

    def test_not_before_compound(self):
        out = self.assertError("a = 20\nprint not a >= 18", "P209")
        self.assertIn("Fix: not (a >= 18)", out)

    def test_bool_only(self):
        self.assertError("print not 5", "V301")
        self.assertError("print 1 and true", "V301")
        self.assertError('print true or "yes"', "V301")

    def test_short_circuit_and(self):
        self.assertOutput("z = 0\nprint false and 1 / z > 0", ["false"])

    def test_short_circuit_or(self):
        self.assertOutput("z = 0\nprint true or 1 / z > 0", ["true"])

    def test_both_sides_type_checked(self):
        # Short-circuit is runtime only; the validator still checks the right side.
        self.assertError("print false and 1", "V301")


class UnaryMinus(AxionTest):
    def test_basic(self):
        self.assertOutput("x = 10\nprint -x\nprint -(x + 5)", ["-10", "-15"])

    def test_with_parentheses_after_operator(self):
        self.assertOutput("x = 10\nprint x * (-1)\nprint 5 - (-3)", ["-10", "8"])

    def test_binds_tighter_than_multiplication(self):
        self.assertOutput("print -2 * 3", ["-6"])

    def test_negative_zero_prints_zero(self):
        self.assertOutput("print -0", ["0"])

    def test_after_operator(self):
        out = self.assertError("x = 2\nprint x * -1", "P207")
        self.assertIn("Fix: print x * (-1)", out)
        self.assertError("a = 1\nb = 2\nprint a - -b", "P207")
        self.assertError("x = 1\nprint x > -1", "P207")

    def test_double_minus(self):
        self.assertError("x = 1\nprint --x", "P207")

    def test_numbers_only(self):
        self.assertError('print -"a"', "V301")
        self.assertError("print -true", "V301")


class Modulo(AxionTest):
    def test_basic(self):
        self.assertOutput("print 10 % 3\nprint 9 % 3", ["1", "0"])

    def test_result_never_negative(self):
        self.assertOutput("print -7 % 3\nprint -3 % 2", ["2", "1"])

    def test_precedence(self):
        self.assertOutput("print 1 + 7 % 3", ["2"])

    def test_through_variables(self):
        self.assertOutput("n = 17\nd = 5\nprint n % d", ["2"])

    def test_literal_errors(self):
        self.assertError("print 7 % 0", "V312")
        self.assertError("print 7 % (-3)", "V312")
        self.assertError("print 10.5 % 3", "V312")

    def test_runtime_errors(self):
        self.assertError("d = 0\nprint 7 % d", "R402")
        self.assertError("x = 10.5\nprint x % 3", "R402")
        self.assertError("d = 0 - 3\nprint 7 % d", "R402")

    def test_numbers_only(self):
        self.assertError('print "a" % 2', "V301")


if __name__ == "__main__":
    unittest.main(verbosity=2)
