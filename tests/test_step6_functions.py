"""Step 6 — functions.

Written from the v0.2 documentation (§13).
"""

import unittest

from helpers import AxionTest

TAX = """function tax(amount: number, rate: number) -> number
return amount * rate
end
"""


class Calls(AxionTest):
    def test_basic(self):
        self.assertOutput(TAX + "print tax(1000, 0.13)\nprint tax(2500, 0.13)", ["130", "325"])

    def test_call_before_definition(self):
        src = "print double(4)\nfunction double(x: number) -> number\nreturn x * 2\nend"
        self.assertOutput(src, ["8"])

    def test_no_result_function(self):
        src = 'function report(total: number)\nprint "Total: " + total as text\nend\nreport(5)'
        self.assertOutput(src, ["Total: 5"])

    def test_no_parameters(self):
        src = 'function hello()\nprint "hi"\nend\nhello()'
        self.assertOutput(src, ["hi"])

    def test_nested_calls(self):
        src = (TAX + 'function report(total: number)\nprint "Total: " + total as text\nend\n'
               "report(tax(1000, 0.13))")
        self.assertOutput(src, ["Total: 130"])

    def test_function_calls_function(self):
        src = ("function sq(x: number) -> number\nreturn x * x\nend\n"
               "function sum_sq(a: number, b: number) -> number\nreturn sq(a) + sq(b)\nend\n"
               "print sum_sq(3, 4)")
        self.assertOutput(src, ["25"])

    def test_return_in_branches(self):
        src = ("function sign(x: number) -> number\nif x > 0\nreturn 1\nelse if x < 0\nreturn -1\n"
               "else\nreturn 0\nend\nend\nprint sign(5)\nprint sign(-2)\nprint sign(0)")
        self.assertOutput(src, ["1", "-1", "0"])

    def test_early_return_in_loop(self):
        src = ("function first_big(xs: list of number) -> number\nfor x in xs\nif x > 10\nreturn x\n"
               "end\nend\nreturn 0\nend\nprint first_big([3, 12, 40])\nprint first_big([1])")
        self.assertOutput(src, ["12", "0"])

    def test_list_and_object_parameters(self):
        src = ('function total(items: list of {price: number, qty: number}) -> number\nsum = 0\n'
               'for it in items\nsum = sum + it.price * it.qty\nend\nreturn sum\nend\n'
               'print total([{price: 500, qty: 2}, {price: 300, qty: 1}])')
        self.assertOutput(src, ["1300"])

    def test_arguments_are_copied(self):
        src = ("function grow(xs: list of number) -> list of number\nys = xs\nys add 9\nreturn ys\nend\n"
               "a = [1]\nb = grow(a)\nprint a\nprint b")
        self.assertOutput(src, ["[1]", "[1, 9]"])

    def test_locals_do_not_leak(self):
        src = "function f(x: number) -> number\ny = x + 1\nreturn y\nend\nprint f(1)\nprint y"
        self.assertError(src, "V303")


class Isolation(AxionTest):
    def test_function_cannot_see_outer_variable(self):
        src = "rate = 0.13\nfunction tax(amount: number) -> number\nreturn amount * rate\nend\nprint tax(100)\nprint rate"
        out = self.assertError(src, "V325")
        self.assertIn("Fix: add a parameter rate and pass the value in the call", out)

    def test_same_name_inside_and_outside(self):
        src = "x = 5\nfunction f(x: number) -> number\nreturn x * 2\nend\nprint f(1)\nprint x"
        self.assertOutput(src, ["2", "5"])

    def test_parameter_is_read_only(self):
        self.assertError("function f(x: number) -> number\nx = 0\nreturn x\nend\nprint f(1)", "V324")
        self.assertError("function f(xs: list of number) -> number\nxs add 1\nreturn 0\nend\nprint f([1])",
                         "V324")


class Returns(AxionTest):
    def test_missing_return(self):
        out = self.assertError("function f(x: number) -> number\nprint x\nend\nprint f(1)", "V318")
        self.assertEqual(out[0], "ERROR V318 line 1:10")

    def test_return_only_in_if(self):
        src = "function sign(x: number) -> number\nif x >= 0\nreturn 1\nend\nend\nprint sign(1)"
        self.assertError(src, "V318")

    def test_return_in_loop_is_not_enough(self):
        src = "function f(xs: list of number) -> number\nfor x in xs\nreturn x\nend\nend\nprint f([1])"
        self.assertError(src, "V318")

    def test_code_after_return(self):
        src = "function f() -> number\nreturn 1\nprint 2\nend\nprint f()"
        self.assertError(src, "V319")

    def test_code_after_if_that_always_returns(self):
        src = ("function f(x: number) -> number\nif x > 0\nreturn 1\nelse\nreturn 2\nend\n"
               "print x\nend\nprint f(1)")
        self.assertError(src, "V319")

    def test_wrong_return_type(self):
        self.assertError('function f() -> number\nreturn "a"\nend\nprint f()', "V301")

    def test_return_without_value(self):
        self.assertError("function f() -> number\nreturn\nend\nprint f()", "V321")

    def test_return_in_function_without_result(self):
        self.assertError("function f()\nreturn 1\nend\nf()", "V321")

    def test_return_outside_function(self):
        self.assertError("return 1", "V321")

    def test_empty_function(self):
        self.assertError("function f()\nend\nf()", "V306")


class CallErrors(AxionTest):
    def test_result_must_be_used(self):
        out = self.assertError(TAX + "tax(1000, 0.13)", "V320")
        self.assertIn("Fix: result = tax(1000, 0.13), or print tax(1000, 0.13)", out)

    def test_no_result_used_as_value(self):
        src = 'function hello()\nprint "hi"\nend\nx = hello()\nprint x'
        self.assertError(src, "V323")

    def test_wrong_argument_count(self):
        out = self.assertError(TAX + "print tax(1000)", "V323")
        self.assertIn("Fix: tax(amount: number, rate: number) -> number", out)

    def test_wrong_argument_type(self):
        self.assertError(TAX + 'print tax("1000", 0.13)', "V323")

    def test_unknown_function(self):
        out = self.assertError(TAX + "print taks(1, 2)", "V303")
        self.assertIn("Fix: did you mean tax?", out)

    def test_foreign_functions(self):
        out = self.assertError("xs = [1, 2]\nprint len(xs)", "V303")
        self.assertIn("Fix: print xs length", out)
        out = self.assertError("n = 5\nprint str(n)", "V303")
        self.assertIn("Fix: print n as text", out)

    def test_variable_is_not_a_function(self):
        self.assertError("x = 1\nprint x(2)", "V303")

    def test_unused_function(self):
        out = self.assertError(TAX + "print 1", "V305")
        self.assertIn("The function tax is never called.", out)

    def test_unused_parameter(self):
        src = "function f(x: number, y: number) -> number\nreturn x\nend\nprint f(1, 2)"
        out = self.assertError(src, "V305")
        self.assertIn("The parameter y is never used.", out)

    def test_variable_cannot_shadow_function(self):
        self.assertError(TAX + "tax = 5\nprint tax(tax, 1)", "V302")


class Recursion(AxionTest):
    def test_direct(self):
        src = "function f(n: number) -> number\nreturn f(n - 1)\nend\nprint f(3)"
        out = self.assertError(src, "V322")       # v0.3: recursion that cannot stop
        self.assertIn("f calls itself on every path, so it can never finish.", out)

    def test_indirect(self):
        src = ("function a(n: number) -> number\nreturn b(n)\nend\n"
               "function b(n: number) -> number\nreturn a(n)\nend\nprint a(1)")
        self.assertError(src, "V322")


class Syntax(AxionTest):
    def test_only_top_level(self):
        self.assertError("if true\nfunction f()\nprint 1\nend\nend", "P215")

    def test_parameter_needs_type(self):
        out = self.assertError("function f(x) -> number\nreturn x\nend\nprint f(1)", "P202")
        self.assertIn("Fix: x: number", out)

    def test_def(self):
        self.assertError("def f(x):\nreturn x\nend", "P210")

    def test_missing_end(self):
        self.assertError("function f()\nprint 1", "P212")

    def test_defined_twice(self):
        self.assertError("function f()\nprint 1\nend\nfunction f()\nprint 2\nend\nf()", "P202")


if __name__ == "__main__":
    unittest.main(verbosity=2)


class KeywordNames(AxionTest):
    def test_keyword_parameter_has_a_fix(self):
        out = self.assertError("function f(value: number) -> number\nreturn value\nend\nprint f(1)", "P214")
        self.assertIn("Fix: choose another name, e.g. my_value", out)
