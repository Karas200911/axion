"""Step 1 — foundation: lines, numbers, text, variables, + - * /, error format.

Written from the v0.2 documentation, not from the old prototype.
Run from the Axion folder:  python3 -m unittest discover -s tests -v
"""

import unittest

from helpers import AxionTest


class Numbers(AxionTest):
    """§3 number: decimal, 28 digits, one canonical literal, print format."""

    def test_integer(self):
        self.assertOutput("print 42", ["42"])

    def test_fraction_literal(self):
        self.assertOutput("print 99.5", ["99.5"])
        self.assertOutput("print 0.5", ["0.5"])

    def test_whole_result_prints_without_point(self):
        self.assertOutput("print 7 / 7", ["1"])
        self.assertOutput("print 100 / 10 / 2", ["5"])
        self.assertOutput("print 2.5 * 2", ["5"])

    def test_fraction_result(self):
        self.assertOutput("print 10 / 4", ["2.5"])

    def test_decimal_arithmetic(self):
        self.assertOutput("print 0.1 + 0.2", ["0.3"])

    def test_28_significant_digits(self):
        self.assertOutput("print 1 / 3", ["0.3333333333333333333333333333"])
        self.assertOutput("print 1 / 3 * 3", ["0.9999999999999999999999999999"])

    def test_never_exponent_form(self):
        self.assertOutput("print 100000000000000000000 * 10", ["1000000000000000000000"])
        self.assertOutput("print 1 / 10000000", ["0.0000001"])

    def test_zero(self):
        self.assertOutput("print 5 - 5", ["0"])
        self.assertOutput("print 0", ["0"])

    def test_invalid_literals(self):
        for literal in (".5", "5.", "5.0", "2.50", "007", "1e3", "1_000", "5.x"):
            with self.subTest(literal=literal):
                self.assertError(f"print {literal}", "L104")

    def test_invalid_literal_fix(self):
        out = self.assertError("print 5.0", "L104")
        self.assertIn("Fix: write 5", out)
        out = self.assertError("print .5", "L104")
        self.assertIn("Fix: write 0.5", out)
        out = self.assertError("print 1e3", "L104")
        self.assertIn("Fix: write 1000", out)


class Texts(AxionTest):
    """§4 text: double quotes, one line, three escapes."""

    def test_print_text_raw(self):
        self.assertOutput('print "hi"', ["hi"])

    def test_empty_text(self):
        self.assertOutput('print ""', [""])

    def test_concat(self):
        self.assertOutput('name = "Egor"\nprint "Hello, " + name', ["Hello, Egor"])

    def test_escapes(self):
        self.assertOutput('print "he said \\"hi\\""', ['he said "hi"'])
        self.assertOutput('print "C:\\\\files"', ["C:\\files"])
        self.assertOutput('print "one\\ntwo"', ["one", "two"])

    def test_unicode(self):
        self.assertOutput('print "Привет"', ["Привет"])

    def test_unknown_escape(self):
        out = self.assertError('print "a\\tb"', "L103")
        self.assertEqual(out[0], "ERROR L103 line 1:9")

    def test_backslash_must_be_escaped(self):
        self.assertError('print "C:\\files"', "L103")

    def test_unclosed(self):
        self.assertError('print "abc', "L102")

    def test_no_multiline_text(self):
        self.assertError('print "ab\ncd"', "L102")

    def test_single_quotes(self):
        out = self.assertError("print 'Egor'", "L106")
        self.assertIn('Fix: write "Egor"', out)


class Lines(AxionTest):
    """§1 lines: one statement per line, indentation has no meaning, comments, blank lines."""

    def test_two_statements_on_one_line(self):
        self.assertError("print 1 print 2", "P201")

    def test_extra_value_on_line(self):
        self.assertError("x = 1 2", "P201")

    def test_semicolon_is_unknown(self):
        self.assertError("print 1; print 2", "L101")

    def test_indentation_space(self):
        self.assertOutput("x = 1\n    print x", ["1"])      # leading spaces have no meaning

    def test_indentation_tab(self):
        self.assertOutput("\tprint 1", ["1"])

    def test_whitespace_only_line_is_blank(self):
        self.assertOutput("print 1\n   \nprint 2", ["1", "2"])

    def test_blank_lines(self):
        self.assertOutput("\n\nprint 1\n\n\nprint 2\n\n", ["1", "2"])

    def test_comments(self):
        self.assertOutput("# full line\nprint 1 # trailing\n# end", ["1"])

    def test_empty_program(self):
        self.assertOutput("", [])

    def test_only_comments(self):
        self.assertOutput("# nothing\n# here", [])

    def test_windows_line_endings(self):
        self.assertOutput("x = 1\r\nprint x\r\n", ["1"])

    def test_no_line_break_inside_parentheses(self):
        self.assertError("print (1 +\n2)", "P204")

    def test_unknown_character(self):
        self.assertError("print 1 @ 2", "L101")


class Expressions(AxionTest):
    """§7 precedence and associativity for + - * / and parentheses."""

    def test_precedence(self):
        self.assertOutput("print 15 + 10 * 2", ["35"])

    def test_parentheses(self):
        self.assertOutput("print (15 + 10) * 2", ["50"])

    def test_left_associative(self):
        self.assertOutput("print 10 - 3 - 2", ["5"])
        self.assertOutput("print 8 / 4 / 2", ["1"])

    def test_deep_parentheses(self):
        self.assertOutput("print ((((1 + 2))))", ["3"])

    def test_missing_closing_paren(self):
        self.assertError("print (1 + 2", "P203")

    def test_extra_closing_paren(self):
        self.assertError("print 1 + 2)", "P203")

    def test_missing_value(self):
        out = self.assertError("x =", "P202")
        self.assertEqual(out[0], "ERROR P202 line 1:4")

    def test_print_without_value(self):
        self.assertError("print", "P202")

    def test_unary_plus(self):
        self.assertError("print +1", "P208")


class Variables(AxionTest):
    """§6 variables: created by assignment, type fixed, unknown names."""

    def test_create_and_read(self):
        self.assertOutput("age = 15\nnext = age + 1\nprint next", ["16"])

    def test_reassign_same_type(self):
        self.assertOutput("age = 15\nage = 16\nprint age", ["16"])

    def test_type_is_fixed(self):
        out = self.assertError('age = 15\nage = "sixteen"', "V302")
        self.assertEqual(out[0], "ERROR V302 line 2:7")
        # The hint must not lead to a new error ("sixteen" as number would fail).
        self.assertIn('Fix: use a new name: age_text = "sixteen"', out)

    def test_type_change_from_expression_suggests_conversion(self):
        out = self.assertError('age = 15\nraw = "16"\nage = raw', "V302")
        self.assertIn("Fix: use a new name, or convert: age = raw as number", out)

    def test_unknown_variable(self):
        self.assertError("print missing", "V303")

    def test_did_you_mean(self):
        out = self.assertError("total = 5\nprint totl", "V303")
        self.assertIn("Fix: did you mean total?", out)

    def test_self_reference_before_creation(self):
        self.assertError("x = x + 1", "V303")

    def test_keyword_as_name(self):
        for word in ("and", "or", "not", "print", "if", "value", "length"):
            with self.subTest(word=word):
                self.assertError(f"{word} = 5", "P214")

    def test_foreign_syntax(self):
        self.assertError("var x = 1", "P210")
        self.assertError("x = True", "P210")
        self.assertError("x = None", "P210")


class Types(AxionTest):
    """§7 operator type rules."""

    def test_number_plus_text(self):
        self.assertError('print 10 + "hello"', "V301")

    def test_text_minus_text(self):
        self.assertError('print "a" - "b"', "V301")

    def test_text_times_number(self):
        self.assertError('print "a" * 3', "V301")

    def test_types_through_variables(self):
        self.assertError('a = 1\nb = "x"\nprint a + b', "V301")


class Division(AxionTest):
    """§7 division by zero: literal -> VALIDATION, otherwise RUNTIME."""

    def test_literal_zero(self):
        self.assertError("print 5 / 0", "V312")
        self.assertError("print 5 / (0)", "V312")

    def test_runtime_zero(self):
        self.assertError("z = 0\nprint 5 / z", "R401")

    def test_runtime_error_keeps_previous_output(self):
        self.assertError("z = 5 - 5\nprint 1\nprint 2 / z", "R401", printed_before=["1"])


class FailClosed(AxionTest):
    """§0 an invalid program executes nothing."""

    def test_nothing_runs_when_invalid(self):
        self.assertError('print 1\nx = 1 + "a"', "V301")

    def test_nothing_runs_on_late_parse_error(self):
        self.assertError("print 1\nprint 2 print 3", "P201")


class ErrorFormat(AxionTest):
    """§17 message format: code + position, source line, marker, problem, fix."""

    def test_full_format(self):
        out = self.assertError('x = 1\nprint 10 + "a"', "V301")
        self.assertEqual(out[0], "ERROR V301 line 2:7")
        self.assertEqual(out[1], 'print 10 + "a"')
        self.assertEqual(out[2], "      ^^^^^^^^")
        self.assertEqual(out[3], "Cannot add number and text.")
        self.assertEqual(out[4], 'Fix: print 10 as text + "a"')      # "a" can never be a number

    def test_fix_wraps_compound_expressions(self):
        out = self.assertError('a = 1\nprint "N: " + (a + 1)', "V301")
        self.assertIn("(a + 1) as text", out[4])


if __name__ == "__main__":
    unittest.main(verbosity=2)
