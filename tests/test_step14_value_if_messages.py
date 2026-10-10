"""Step 14: three repairs after the repair check of test A (10 of 15).

The value-if is one step old, and two of the five remaining failures were its messages:

- phi4, task 20, wrote the chain over three lines and was told only "needs else";
- phi4, task 25, wrote `bookings max by id.id` inside a value-if and was told "needs else"
  although the else was there: the mistake was `max by`, which does not exist.

(The third repair, a model going round between two programs, is in test_bench_tasks.)
"""
import unittest

from helpers import AxionTest


def fix_of(out):
    return next((line[5:] for line in out if line.startswith("Fix: ")), None)


ONE_LINE = "A value chosen with if is written on one line, together with its else."
NEEDS_ELSE = "A value chosen with if always needs else: there must be a value for both cases."


class ValueIfOverSeveralLines(AxionTest):
    SPREAD = ('w = 3\n'
              'price = if w <= 1 then 100\n'
              '        else if w <= 5 then 250\n'
              '        else 600\n'
              'print price')

    def test_one_error_with_the_joined_line(self):
        out = self.assertErrors(self.SPREAD, ["P202"])
        self.assertIn(ONE_LINE, out)
        self.assertEqual(fix_of(out), "price = if w <= 1 then 100 else if w <= 5 then 250 else 600")
        self.assertEqual(out[0], "ERROR P202 line 2:9")

    def test_the_joined_line_runs(self):
        self.assertOutput("w = 3\nprice = if w <= 1 then 100 else if w <= 5 then 250 else 600\nprint price",
                          ["250"])

    def test_inside_blocks_as_phi4_wrote_it(self):
        source = ('w = 3\n'
                  'for i in 1 to 2\n'
                  '  if w > 20\n'
                  '    print "heavy"\n'
                  '  else\n'
                  '    price = if w <= 1 then 100\n'
                  '            else if w <= 5 then 250\n'
                  '            else 600\n'
                  '\n'
                  '    if w > 2\n'
                  '      price = price + i\n'
                  '    end\n'
                  '    print price\n'
                  '  end\n'
                  'end')
        out = self.assertErrors(source, ["P202"])            # no echo about else, end or indentation
        self.assertEqual(fix_of(out), "price = if w <= 1 then 100 else if w <= 5 then 250 else 600")
        fixed = source.replace('    price = if w <= 1 then 100\n            else if w <= 5 then 250\n'
                               '            else 600\n',
                               '    price = if w <= 1 then 100 else if w <= 5 then 250 else 600\n')
        self.assertOutput(fixed, ["251", "252"])

    def test_together_with_another_broken_line(self):
        out = self.assertErrors("x = = 1\n" + self.SPREAD, ["P202", "P202"])
        self.assertIn(ONE_LINE, out)
        self.assertEqual([line for line in out if line.startswith("Fix: ")],
                         ["Fix: price = if w <= 1 then 100 else if w <= 5 then 250 else 600"])

    def test_two_lines(self):
        out = self.assertError('m = 5\npad = if m < 10 then "0"\n      else ""\nprint pad', "P202")
        self.assertEqual(fix_of(out), 'pad = if m < 10 then "0" else ""')

    def test_a_block_else_below_is_not_taken_for_its_else(self):
        source = 'm = 5\nif m > 1\n  x = if m < 10 then "0"\nelse\n  print m\nend'
        out = self.assertError(source, "P202")
        self.assertIn(NEEDS_ELSE, out)
        self.assertEqual(fix_of(out), 'x = if m < 10 then "0" else ...   (the value for the other case)')

    def test_an_else_alone_on_a_deeper_line_is_not_joined(self):
        source = 'm = 5\nx = if m < 10 then "0"\n      else\nprint x'
        self.assertIn(NEEDS_ELSE, self.assertError(source, "P202"))


class ElseIsMissing(AxionTest):
    def test_at_the_end_of_the_line(self):
        out = self.assertError('m = 5\nx = if m < 10 then "0"\nprint x', "P202")
        self.assertIn(NEEDS_ELSE, out)
        self.assertEqual(fix_of(out), 'x = if m < 10 then "0" else ...   (the value for the other case)')

    def test_inside_parentheses_the_else_goes_inside(self):
        out = self.assertError('m = 5\nx = (if m < 10 then "0") + "a"\nprint x', "P202")
        self.assertEqual(fix_of(out),
                         'x = (if m < 10 then "0" else ...) + "a"   (the value for the other case)')

    def test_another_word_in_place_of_else(self):
        out = self.assertError('m = 5\nx = if m < 10 then "0" otherwise ""\nprint x', "P202")
        self.assertIn("After the value of then comes else, not otherwise.", out)
        self.assertEqual(fix_of(out), 'x = if m < 10 then "0" else ""')
        self.assertOutput('m = 5\nx = if m < 10 then "0" else ""\nprint x', ["0"])

    def test_a_stray_word_before_an_existing_else_gets_no_guess(self):
        out = self.assertError('m = 5\nx = if m < 10 then m thing else 0\nprint x', "P202")
        self.assertIn("After the value of then comes else, not thing.", out)
        self.assertIsNone(fix_of(out))

    def test_division_word_after_then(self):
        out = self.assertError("m = 5\nx = if m < 10 then m div 2 else 0\nprint x", "P202")
        self.assertEqual(fix_of(out), "x = if m < 10 then m // 2 else 0")

    def test_membership_after_then(self):
        out = self.assertError("xs = [1]\nm = 5\nb = if m < 10 then m in xs else false\nprint b", "P202")
        self.assertFalse(any(NEEDS_ELSE in line for line in out), out)


class MaxBy(AxionTest):
    BS = 'bs = [{id: 3, n: 1}, {id: 7, n: 2}]\n'

    def test_inside_a_value_if_the_real_mistake_is_named(self):
        out = self.assertError(self.BS + "next_id = if bs length > 0 then bs max by id.id else 1\n"
                                         "print next_id", "P202")
        self.assertIn("max has no by: it works on a list of numbers. Only sort has by.", out)
        self.assertFalse(any(NEEDS_ELSE in line for line in out))
        self.assertEqual(fix_of(out), "the element with the largest id: next_id = if bs length > 0 "
                                      "then (bs sort by id descending)[0].id else 1")

    def test_the_fix_runs(self):
        self.assertOutput(self.BS + "next_id = if bs length > 0 then (bs sort by id descending)[0].id else 1\n"
                                    "print next_id", ["7"])

    def test_max_by_alone_says_it_is_the_element(self):
        out = self.assertError(self.BS + "top = bs max by id\nprint top", "P202")
        self.assertEqual(fix_of(out), "the element with the largest id: top = (bs sort by id descending)[0]"
                                      "   (this is the element; add .id for its number)")
        self.assertOutput(self.BS + "top = (bs sort by id descending)[0]\nprint top.id", ["7"])

    def test_min_by(self):
        out = self.assertError(self.BS + "low = bs min by id\nprint low", "P202")
        self.assertIn("min has no by", out[3])
        self.assertEqual(fix_of(out), "the element with the smallest id: low = (bs sort by id)[0]"
                                      "   (this is the element; add .id for its number)")

    def test_sum_by(self):
        out = self.assertError(self.BS + "print bs sum by n", "P202")
        self.assertEqual(fix_of(out), "add the numbers up in a loop: total = 0, then for x in bs "
                                      "with total = total + x.n")

    def test_by_without_a_field(self):
        out = self.assertError(self.BS + "print bs max by 1", "P202")
        self.assertIn("max has no by: it works on a list of numbers. Only sort has by.", out)

    def test_plain_max_and_sort_by_are_unchanged(self):
        self.assertOutput("xs = [3, 9]\nprint xs max", ["9"])
        self.assertOutput(self.BS + "print (bs sort by id descending)[0].n", ["2"])

    def test_a_variable_named_by_after_a_sum_on_the_next_line(self):
        self.assertOutput("xs = [1, 2]\nby = 5\nt = xs sum\nprint t + by", ["8"])


if __name__ == "__main__":
    unittest.main()
