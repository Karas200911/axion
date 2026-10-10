"""Step 4 — lists, ranges (a to b), for loops.

Written from the v0.2 documentation (§6, §8, §12 for).
"""

import unittest

from helpers import AxionTest

FIZZBUZZ = """for i in 1 to 15
if i % 15 == 0
print "FizzBuzz"
else if i % 3 == 0
print "Fizz"
else if i % 5 == 0
print "Buzz"
else
print i
end
end"""


class ListLiterals(AxionTest):
    def test_print_numbers(self):
        self.assertOutput("print [1, 2, 3]", ["[1, 2, 3]"])

    def test_print_text_is_quoted_inside(self):
        self.assertOutput('print ["A", "B"]', ['["A", "B"]'])
        self.assertOutput('print ["a\\"b", "x\\ny"]', ['["a\\"b", "x\\ny"]'])

    def test_print_bool_and_fraction(self):
        self.assertOutput("print [true, false]\nprint [0.5, 7 / 7]", ["[true, false]", "[0.5, 1]"])

    def test_nested(self):
        self.assertOutput("print [[1, 2], [3]]", ["[[1, 2], [3]]"])

    def test_multiline(self):
        self.assertOutput("xs = [\n1,\n2\n]\nprint xs", ["[1, 2]"])

    def test_multiline_indented(self):
        self.assertOutput("xs = [\n  1,\n  2\n]\nprint xs", ["[1, 2]"])

    def test_one_type_only(self):
        out = self.assertError('print [1, "a"]', "V310")
        self.assertIn("All list elements must have one type: element 1 is number, element 2 is text.", out)

    def test_trailing_comma(self):
        self.assertError("print [1, 2,]", "P202")


class EmptyLists(AxionTest):
    def test_typed_empty(self):
        self.assertOutput("xs = [] of number\nprint xs", ["[]"])

    def test_nested_type(self):
        self.assertOutput("m = [] of list of number\nm add [1, 2]\nprint m", ["[[1, 2]]"])

    def test_bare_empty_list(self):
        out = self.assertError("xs = []\nprint xs", "P213")
        # No single template to copy blindly: the model must choose the element type.
        self.assertIn("Fix: xs = [] of text   (or [] of number, [] of bool, "
                      "[] of {name: text})", out)

    def test_missing_type(self):
        self.assertError("xs = [] of\nprint xs", "P202")

    def test_type_must_match_later_use(self):
        self.assertError('xs = [] of number\nxs add "a"\nprint xs', "V310")


class Indexing(AxionTest):
    def test_read(self):
        self.assertOutput("xs = [10, 20, 30]\nprint xs[0]\nprint xs[2]", ["10", "30"])

    def test_index_expression(self):
        self.assertOutput("xs = [10, 20, 30]\nprint xs[7 / 7]", ["20"])

    def test_nested(self):
        self.assertOutput("m = [[1, 2], [3, 4]]\nprint m[1][0]", ["3"])

    def test_set(self):
        self.assertOutput("xs = [1, 2, 3]\nxs[1] = 20\nprint xs", ["[1, 20, 3]"])

    def test_set_nested(self):
        self.assertOutput("m = [[1, 2], [3, 4]]\nm[1][0] = 9\nprint m", ["[[1, 2], [9, 4]]"])

    def test_set_wrong_type(self):
        self.assertError('xs = [1, 2]\nxs[0] = "a"\nprint xs', "V310")

    def test_literal_negative(self):
        self.assertError("xs = [1, 2]\nprint xs[-1]", "V313")

    def test_literal_fraction(self):
        self.assertError("xs = [1, 2]\nprint xs[1.5]", "V313")

    def test_out_of_range(self):
        out = self.assertError("items = [1, 2, 3]\nprint items[3]", "R403")
        self.assertIn("Index 3 is out of range: items has 3 elements (valid: 0 to 2).", out)

    def test_empty_list(self):
        out = self.assertError("xs = [] of number\nprint xs[0]", "R403")
        self.assertIn("Index 0 is out of range: xs has 0 elements (it is empty).", out)

    def test_runtime_fraction(self):
        self.assertError("xs = [1, 2]\ni = 0.5\nprint xs[i]", "R402")

    def test_index_must_be_number(self):
        self.assertError('xs = [1, 2]\nprint xs["0"]', "V301")

    def test_not_a_list(self):
        self.assertError("x = 5\nprint x[0]", "V301")
        self.assertOutput('t = "ab"\nprint t[0]', ["a"])          # v0.3: text has positions


class ListOperations(AxionTest):
    def test_add(self):
        self.assertOutput("xs = [1]\nxs add 2\nxs add 2\nprint xs", ["[1, 2, 2]"])

    def test_remove_index(self):
        self.assertOutput('xs = ["a", "b", "c"]\nxs remove index 1\nprint xs', ['["a", "c"]'])

    def test_remove_value(self):
        self.assertOutput('xs = ["a", "b", "c"]\nxs remove value "c"\nprint xs', ['["a", "b"]'])

    def test_remove_value_no_match(self):
        self.assertError('xs = ["a"]\nxs remove value "z"\nprint xs', "R405")

    def test_remove_value_two_matches(self):
        out = self.assertError('xs = ["a", "a"]\nxs remove value "a"\nprint xs', "R405")
        self.assertIn("Fix: use remove index to choose one", out)

    def test_remove_index_out_of_range(self):
        self.assertError("xs = [1]\nxs remove index 5\nprint xs", "R403")

    def test_remove_needs_mode(self):
        self.assertError("xs = [1]\nxs remove 1\nprint xs", "P202")

    def test_add_to_non_list(self):
        self.assertError("x = 1\nx add 2\nprint x", "V301")

    def test_length(self):
        self.assertOutput('xs = [1, 2, 3]\nprint xs length\nprint "Егор" length\nprint "" length',
                          ["3", "4", "0"])

    def test_length_binds_to_value_before(self):
        self.assertOutput("xs = [1, 2]\nprint xs length + 1", ["3"])

    def test_length_of_number(self):
        self.assertError("x = 5\nprint x length", "V301")

    def test_equality_is_deep_and_ordered(self):
        self.assertOutput("print [1, 2] == [1, 2]\nprint [1, 2] == [2, 1]\nprint [[1]] != [[2]]",
                          ["true", "false", "true"])

    def test_compare_different_list_types(self):
        self.assertError('print [1] == ["1"]', "V308")

    def test_no_list_plus(self):
        self.assertError("print [1] + [2]", "V301")

    def test_change_without_reading_is_unused(self):
        self.assertError("xs = [] of number\nxs add 1", "V305")


class CopySemantics(AxionTest):
    def test_assignment_copies(self):
        self.assertOutput("a = [1, 2]\nb = a\nb add 3\nprint a\nprint b", ["[1, 2]", "[1, 2, 3]"])

    def test_nested_copy(self):
        self.assertOutput("m = [[1]]\nrow = m[0]\nrow add 2\nprint m\nprint row", ["[[1]]", "[1, 2]"])

    def test_add_copies(self):
        self.assertOutput("a = [1]\nm = [] of list of number\nm add a\na add 2\nprint m",
                          ["[[1]]"])


class Ranges(AxionTest):
    def test_inclusive(self):
        self.assertOutput("print 1 to 5", ["[1, 2, 3, 4, 5]"])

    def test_single(self):
        self.assertOutput("print 3 to 3", ["[3]"])

    def test_precedence(self):
        self.assertOutput("xs = [7, 8, 9]\nprint 0 to xs length - 1", ["[0, 1, 2]"])

    def test_computed_empty(self):
        self.assertOutput("n = 0\nprint 0 to n - 1", ["[]"])

    def test_literal_empty(self):
        out = self.assertError("print 5 to 1", "V317")
        self.assertIn("Fix: 1 to 5", out)

    def test_literal_fraction(self):
        self.assertError("print 1 to 2.5", "V317")

    def test_runtime_fraction(self):
        self.assertError("n = 2.5\nprint 1 to n", "R402")

    def test_numbers_only(self):
        self.assertError('print 1 to "5"', "V301")

    def test_no_chain(self):
        self.assertError("print 1 to 5 to 9", "P202")


class ForLoops(AxionTest):
    def test_sum(self):
        self.assertOutput("total = 0\nfor p in [10, 20, 30]\ntotal = total + p\nend\nprint total", ["60"])

    def test_fizzbuzz(self):
        expected = ["1", "2", "Fizz", "4", "Buzz", "Fizz", "7", "8", "Fizz", "Buzz",
                    "11", "Fizz", "13", "14", "FizzBuzz"]
        self.assertOutput(FIZZBUZZ, expected)

    def test_max_and_position(self):
        src = ("prices = [30, 90, 50]\nmax = prices[0]\npos = 0\n"
               "for i in 0 to prices length - 1\nif prices[i] > max\nmax = prices[i]\npos = i\nend\nend\n"
               "print max\nprint pos")
        self.assertOutput(src, ["90", "1"])

    def test_build_new_list(self):
        src = ('ages = [15, 20, 30]\nadults = [] of number\nfor a in ages\nif a >= 18\n'
               'adults add a\nend\nend\nprint adults')
        self.assertOutput(src, ["[20, 30]"])

    def test_nested_loops(self):
        src = "for a in 1 to 2\nfor b in 1 to 2\nprint a * 10 + b\nend\nend"
        self.assertOutput(src, ["11", "12", "21", "22"])

    def test_empty_list_runs_zero_times(self):
        self.assertOutput('xs = [] of number\nfor x in xs\nprint x\nend\nprint "done"', ["done"])

    def test_index_loop_over_empty_list(self):
        self.assertOutput('xs = [] of number\nfor i in 0 to xs length - 1\nprint xs[i]\nend\nprint "ok"',
                          ["ok"])

    def test_body_starts_clean_each_pass(self):
        src = "for i in 1 to 2\nlocal = i * 2\nprint local\nend"
        self.assertOutput(src, ["2", "4"])

    def test_loop_variable_dies_at_end(self):
        self.assertError("for x in [1]\nprint x\nend\nprint x", "V304")

    def test_loop_variable_must_be_new(self):
        self.assertError("x = 0\nfor x in [1]\nprint x\nend\nprint x", "V315")

    def test_loop_variable_is_read_only(self):
        self.assertError("for x in [1, 2]\nx = 5\nprint x\nend", "V315")

    def test_unused_loop_variable(self):
        # A loop over a list that never looks at its elements is still an error...
        self.assertError('for x in ["a", "b"]\nprint "hi"\nend', "V305")

    def test_counting_loop_may_leave_its_variable_unused(self):
        # ...but "repeat n times" is not (decided after the GPT runs on task 9).
        self.assertOutput('for i in 1 to 3\nprint "hi"\nend', ["hi", "hi", "hi"])

    def test_cannot_change_iterated_list(self):
        self.assertError("items = [1, 2]\nfor x in items\nitems add x\nend\nprint items", "V316")
        self.assertError("items = [1, 2]\nfor x in items\nitems = [x]\nend\nprint items", "V316")
        self.assertError("items = [1, 2]\nfor x in items\nitems[0] = x\nend\nprint items", "V316")

    def test_can_change_list_when_looping_over_a_range(self):
        src = "xs = [1, 2]\nfor i in 0 to xs length - 1\nxs[i] = xs[i] * 10\nend\nprint xs"
        self.assertOutput(src, ["[10, 20]"])

    def test_needs_a_list(self):
        out = self.assertError("n = 3\nfor i in n\nprint i\nend", "V301")
        self.assertIn("Fix: for i in 1 to n", out)

    def test_empty_body(self):
        self.assertError("for x in [1]\nend", "V306")

    def test_missing_end(self):
        self.assertError("for x in [1]\nprint x", "P212")

    def test_missing_in(self):
        self.assertError("for x [1]\nprint x\nend", "P202")

    def test_c_style(self):
        self.assertError("for (i in [1])\nprint i\nend", "P210")

    def test_while(self):
        # v0.2 refused while; v0.3 has it, and an empty body is the error here.
        self.assertError("x = 1\nwhile x < 3\nend", "V306")

    def test_else_in_for(self):
        self.assertError("for x in [1]\nprint x\nelse\nprint 0\nend", "P211")


if __name__ == "__main__":
    unittest.main(verbosity=2)


class Hints(AxionTest):
    def test_iterated_list_fix_is_working_code(self):
        out = self.assertError("items = [1, 2]\nfor x in items\nitems add x\nend\nprint items", "V316")
        self.assertIn("Fix: loop over a copy: items_copy = items, then for ... in items_copy", out)
        # ...and the suggested program really works:
        src = "items = [1, 2]\nitems_copy = items\nfor x in items_copy\nitems add x\nend\nprint items"
        self.assertOutput(src, ["[1, 2, 1, 2]"])

    def test_semicolon_hint(self):
        out = self.assertError("x = 1; print x", "L101")
        self.assertIn("Fix: put each statement on its own line", out)
