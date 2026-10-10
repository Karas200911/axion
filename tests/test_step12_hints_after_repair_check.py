"""Step 12: five hints from the repair check of tasks 10-14 (2026-10-05, 7 of 15 solved).

The language is the same; only the text a model gets after a mistake changed. Each case
below cost a model at least one attempt:

- gemma wrote `results sort by result descending` on a line of its own;
- gemma wrote `min(3, n)`, was told to define min, defined it and got a new error;
- gemma wrote `spent = spent add {...}` and repeated the same program;
- phi4 wrote `students sort by (f(student.scores)) descending` and got no Fix;
- gemma repaired `length(word)` one line per attempt although the other lines were named.

Every Fix is checked by running it: a hint that is itself wrong costs another attempt.
"""
import unittest

from helpers import AxionTest, run


def fix_of(out):
    return next((line[5:] for line in out if line.startswith("Fix: ")), None)


ROWS = 'rows = [{name: "a", result: 2}, {name: "b", result: 5}]\n'


class SortAsStatement(AxionTest):
    def test_sort_on_its_own_line_says_to_store_the_new_list(self):
        out = self.assertError(ROWS + "rows sort by result descending\nprint rows", "P202")
        self.assertIn("sort gives a new list; rows itself does not change.", out)
        self.assertEqual(fix_of(out), "rows = rows sort by result descending")

    def test_the_fix_runs(self):
        self.assertOutput(ROWS + "rows = rows sort by result descending\nprint rows[0].name", ["b"])

    def test_plain_sort(self):
        out = self.assertError("xs = [2, 1]\nxs sort\nprint xs", "P202")
        self.assertEqual(fix_of(out), "xs = xs sort")

    def test_sort_of_a_field(self):
        out = self.assertError('o = {xs: [2, 1]}\no.xs sort descending\nprint o', "P202")
        self.assertEqual(fix_of(out), "o.xs = o.xs sort descending")
        self.assertOutput('o = {xs: [1, 2]}\no.xs = o.xs sort descending\nprint o.xs', ["[2, 1]"])

    def test_sum_on_its_own_line_is_a_value(self):
        out = self.assertError("xs = [2, 1]\nxs sum\nprint xs", "P202")
        self.assertIn("xs sum is a value, not a statement.", out)
        self.assertEqual(fix_of(out), "store it: result = xs sum   or print it: print xs sum")

    def test_a_variable_named_sort_is_still_a_variable(self):
        self.assertOutput("sort = 1\nprint sort", ["1"])

    def test_a_name_alone_keeps_the_old_message(self):
        out = self.assertError("xs = [1]\nxs\nprint xs", "P202")
        self.assertIn("Expected a statement.", out)


class MinOfSeveralValues(AxionTest):
    def test_two_arguments(self):
        out = self.assertError("n = 5\ntop = min(3, n)\nprint top", "V303")
        self.assertIn("min() does not exist in Axion: min is written after a list of numbers.", out)
        self.assertEqual(fix_of(out), "top = [3, n] min")

    def test_the_fix_runs(self):
        self.assertOutput("n = 5\ntop = [3, n] min\nprint top", ["3"])

    def test_three_arguments_of_max(self):
        out = self.assertError("a = 1\nprint max(a, 2, a + 4)", "V303")
        self.assertEqual(fix_of(out), "print [a, 2, a + 4] max")
        self.assertOutput("a = 1\nprint [a, 2, a + 4] max", ["5"])

    def test_one_argument_keeps_its_hint(self):
        out = self.assertError("xs = [1, 2]\nprint min(xs)", "V303")
        self.assertEqual(fix_of(out), "print xs min")

    def test_own_function_named_min_is_called(self):
        source = ("function min(a: number, b: number) -> number\nif a < b\nreturn a\nend\n"
                  "return b\nend\nprint min(3, 5)")
        self.assertOutput(source, ["3"])

    def test_no_definition_is_suggested(self):
        code, out = run("n = 5\ntop = min(3, n)\nprint top")
        self.assertFalse(any("define it" in line for line in out), out)


class AddIsNotAValue(AxionTest):
    def test_assigning_the_list_to_itself(self):
        out = self.assertError("xs = [1]\nxs = xs add 5\nprint xs", "P202")
        self.assertIn("add changes the list itself and gives no value.", out)
        self.assertEqual(fix_of(out), "xs add 5")
        self.assertOutput("xs = [1]\nxs add 5\nprint xs", ["[1, 5]"])

    def test_an_object_is_added(self):
        source = ('spent = [] of {name: text, total: number}\n'
                  'spent = spent add {name: "food", total: 0}\nprint spent')
        out = self.assertError(source, "P202")
        self.assertEqual(fix_of(out), 'spent add {name: "food", total: 0}')

    def test_another_name_gets_two_lines(self):
        out = self.assertError("xs = [1]\nys = xs add 5\nprint ys", "P202")
        self.assertEqual(fix_of(out), "two lines: ys = xs   then   ys add 5")
        self.assertOutput("xs = [1]\nys = xs\nys add 5\nprint ys\nprint xs", ["[1, 5]", "[1]"])

    def test_indented_line(self):
        out = self.assertError("xs = [1]\nif true\n  xs = xs add 5\nend\nprint xs", "P202")
        self.assertEqual(fix_of(out), "xs add 5")

    def test_add_after_print_keeps_the_old_message(self):
        out = self.assertError("xs = [1]\nprint xs add 5", "P201")
        self.assertIn("Only one statement per line is allowed.", out)

    def test_plain_add_still_works(self):
        self.assertOutput("xs = [1]\nxs add 5\nprint xs length", ["2"])


class SortByAnExpression(AxionTest):
    def test_parenthesis_after_by(self):
        out = self.assertError(ROWS + "ys = rows sort by (rows length) descending\nprint ys", "P202")
        self.assertIn("sort by takes the name of a number field, not an expression.", out)
        self.assertIn("rows sort by result", fix_of(out))

    def test_number_after_by(self):
        out = self.assertError(ROWS + "ys = rows sort by 1\nprint ys", "P202")
        self.assertIn("sort by takes the name of a number field, not an expression.", out)

    def test_the_way_the_fix_describes_runs(self):
        source = ('people = [{name: "a", scores: [1, 2]}, {name: "b", scores: [5]}]\n'
                  'rows = [] of {name: text, result: number}\n'
                  'for p in people\n  rows add {name: p.name, result: p.scores sum}\nend\n'
                  'rows = rows sort by result descending\nprint rows[0].name')
        self.assertOutput(source, ["b"])

    def test_field_name_still_works(self):
        self.assertOutput(ROWS + "print (rows sort by result descending)[0].name", ["b"])


class SameMistakeOnOtherLines(AxionTest):
    SOURCE = ('words = ["a", "bb"]\na = length(words[0])\nb = length(words[1])\n'
              'print a + b\nprint length(words)')

    def test_several_lines(self):
        out = self.assertError(self.SOURCE, "P202")
        self.assertEqual(out[-1], "The same mistake is on lines 3, 5: fix them too.")

    def test_one_line(self):
        out = self.assertError('w = "ab"\na = length(w)\nprint a\nprint length(w)', "P202")
        self.assertEqual(out[-1], "The same mistake is on line 4: fix it too.")

    def test_a_single_mistake_has_no_such_line(self):
        out = self.assertError('w = "ab"\nprint length(w)', "P202")
        self.assertFalse(any(line.startswith("The same mistake") for line in out))

    def test_the_old_wording_is_gone(self):
        code, out = run(self.SOURCE)
        self.assertFalse(any("Also affected" in line for line in out))


if __name__ == "__main__":
    unittest.main()
