"""Step 13: whole division `//`, a value chosen with `if ... then ... else ...`, and the
hints that test A showed to be wrong or missing.

Test A (2026-10-05, tasks 15, 16, 18, 20, 25: 5 of 15 solved) is the evidence:

- no whole division: qwen wrote `t div 3600`, phi4 `t // 3600` (four attempts), gemma
  `seconds to 3600`; nobody wrote `(t - t % 60) / 60`;
- all three models chose a value inside a line: `(if m < 10 then "0" else "")`,
  `next_id = if ids length > 0 then ids max + 1 else 1`, and phi4 also `c ? a : b`;
- `row_sum = sum row` was answered with "row is not an operation";
- `continue`, `keys index k`, `xs sort by id descending[0]` and a bare `[]` had hints that
  did not say what to write.

The value-if is a decided exception to "one way to write a thing" (a block if does
something, a value-if is something). It is to be re-checked on the next runs: if models
start to build long nested lines with it, it goes away again.
"""
import unittest
from decimal import Decimal

from helpers import AxionTest, run

from axionlang.engine.lexer import KEYWORDS


def fix_of(out):
    return next((line[5:] for line in out if line.startswith("Fix: ")), None)


def fixes(out):
    return [line[5:] for line in out if line.startswith("Fix: ")]


class WholeDivision(AxionTest):
    def test_simple(self):
        self.assertOutput("print 7 // 2", ["3"])

    def test_hours_minutes_seconds(self):
        source = "t = 3725\nprint t // 3600\nprint t % 3600 // 60\nprint t % 60"
        self.assertOutput(source, ["1", "2", "5"])

    def test_exact_division_and_zero(self):
        self.assertOutput("print 6 // 3\nprint 0 // 5\nprint 2 // 5", ["2", "0", "0"])

    def test_same_level_as_multiplication_left_to_right(self):
        self.assertOutput("print 6 // 3 * 2\nprint 2 * 7 // 4\nprint 100 // 7 // 2\nprint 1 + 7 // 2",
                          ["4", "3", "7", "4"])

    def test_agrees_with_the_remainder_for_negative_numbers(self):
        # a == (a // b) * b + a % b, and a % b is never negative
        self.assertOutput("a = 0 - 7\nprint a // 2\nprint a % 2\nprint (a // 2) * 2 + a % 2",
                          ["-4", "1", "-7"])

    def test_the_identity_holds_for_many_values(self):
        for a in (-13, -12, -1, 0, 1, 5, 12, 13, 1000001):
            for b in (1, 2, 5, 12, 7):
                source = f"a = 0 + ({a})\nb = {b}\nprint (a // b) * b + a % b"
                self.assertOutput(source, [str(a)])

    def test_large_numbers(self):
        self.assertOutput("print 123456789012345678 // 1000", ["123456789012345"])

    def test_literal_fraction_is_found_before_the_run(self):
        out = self.assertError("print 7.5 // 2", "V312")
        self.assertIn("// works only with whole numbers.", out)
        self.assertEqual(fix_of(out), "for a result with a fraction use /")

    def test_fraction_at_run_time(self):
        out = self.assertError("x = 7.5\nprint x // 2", "R402")
        self.assertIn("// works only with whole numbers: x is 7.5.", out)

    def test_literal_zero_divisor(self):
        out = self.assertError("print 7 // 0", "V312")
        self.assertIn("The divisor of // must be greater than 0.", out)

    def test_zero_divisor_at_run_time(self):
        out = self.assertError("x = 0\nprint 7 // x", "R402")
        self.assertIn("The divisor of // must be greater than 0: x is 0.", out)

    def test_negative_divisor(self):
        self.assertError("print 7 // (-2)", "V312")
        self.assertError("x = 0 - 2\nprint 7 // x", "R402")

    def test_text_operand(self):
        out = self.assertError('print "7" // 2', "V301")
        self.assertIn("Operator // needs numbers, got text and number.", out)

    def test_unary_minus_after_it_needs_parentheses(self):
        self.assertError("print 7 // -2", "P207")

    def test_the_remainder_is_unchanged(self):
        self.assertOutput("print 7 % 2", ["1"])
        out = self.assertError("print 7.5 % 2", "V312")
        self.assertIn("% works only with whole numbers.", out)
        self.assertIsNone(fix_of(out))

    def test_plain_division_is_unchanged(self):
        self.assertOutput("print 7 / 2", ["3.5"])

    def test_slashes_at_the_start_of_a_line_are_a_comment_of_another_language(self):
        out = self.assertError("// the total\nprint 1", "P210")
        self.assertIn("A comment starts with #; // is whole division.", out)
        self.assertEqual(fix_of(out), "# the total")


class DivisionWords(AxionTest):
    def test_div(self):
        out = self.assertError("t = 100\nhours = t div 3600\nprint hours", "P202")
        self.assertIn("Whole division is written // and the remainder %.", out)
        self.assertEqual(fix_of(out), "hours = t // 3600")

    def test_mod(self):
        out = self.assertError("t = 100\nprint t mod 60", "P202")
        self.assertEqual(fix_of(out), "print t % 60")

    def test_both_in_one_line_inside_parentheses(self):
        out = self.assertError("t = 100\nm = (t mod 3600) div 60\nprint m", "P202")
        self.assertEqual(fix_of(out), "m = (t % 3600) // 60")
        self.assertOutput("t = 100\nm = (t % 3600) // 60\nprint m", ["1"])

    def test_other_lines_are_named(self):
        source = "t = 100\nh = t div 3600\nm = (t mod 3600) div 60\nprint h + m"
        out = self.assertError(source, "P202")
        self.assertEqual(out[-1], "The same mistake is on line 3: fix it too.")

    def test_inside_an_index_and_a_call(self):
        self.assertIn("Whole division is written // and the remainder %.",
                      self.assertError("xs = [1, 2]\nprint xs[3 mod 2]", "P202"))
        source = "function f(n: number) -> number\nreturn n\nend\nprint f(7 div 2)"
        self.assertEqual(fix_of(self.assertError(source, "P202")), "print f(7 // 2)")

    def test_names_div_and_mod_are_free(self):
        self.assertOutput("div = 2\nmod = 3\nprint div + mod", ["5"])

    def test_another_unknown_word_keeps_its_message(self):
        out = self.assertError("t = 100\nprint t times 2", "P202")
        self.assertIn("times is not an operation in Axion.", out)


class ChoiceOfAValue(AxionTest):
    def test_assignment(self):
        self.assertOutput('m = 5\npad = if m < 10 then "0" else ""\nprint pad + m as text', ["05"])

    def test_both_cases(self):
        for m, expected in ((5, "small"), (50, "big")):
            self.assertOutput(f'm = {m}\nprint if m < 10 then "small" else "big"', [expected])

    def test_inside_a_longer_expression_in_parentheses(self):
        source = 'm = 5\nprint "t " + (if m >= 10 then m as text else "0" + m as text) + ":"'
        self.assertOutput(source, ["t 05:"])

    def test_else_if_chain(self):
        source = "n = {}\nprint if n > 100 then 3 else if n > 4 then 2 else 1"
        for n, expected in ((500, "3"), (50, "2"), (1, "1")):
            self.assertOutput(source.format(n), [expected])

    def test_else_takes_the_rest_of_the_expression(self):
        self.assertOutput("c = false\nprint if c then 1 else 2 + 3", ["5"])
        self.assertOutput("c = true\nprint if c then 1 else 2 + 3", ["1"])

    def test_then_takes_a_whole_expression_too(self):
        self.assertOutput("c = true\nprint if c then 1 + 1 else 0", ["2"])

    def test_nested_in_then_needs_parentheses(self):
        self.assertError("a = true\nb = false\nprint if a then if b then 1 else 2 else 3", "P202")
        self.assertOutput("a = true\nb = false\nprint if a then (if b then 1 else 2) else 3", ["2"])

    def test_everywhere_a_whole_expression_stands(self):
        source = ('function sign(n: number) -> text\n'
                  '  return if n < 0 then "minus" else "plus"\n'
                  'end\n'
                  'function twice(n: number) -> number\n'
                  '  return n * 2\n'
                  'end\n'
                  'k = 3\n'
                  'xs = [if k > 2 then 1 else 0, 5]\n'
                  'xs add if k > 2 then 10 else 20\n'
                  'o = {size: if k > 2 then "L" else "S"}\n'
                  'xs[0] = if k > 2 then 7 else 8\n'
                  'print xs\nprint o.size\nprint sign(0 - k)\n'
                  'print twice(if k > 2 then 4 else 5)')
        self.assertOutput(source, ["[7, 5, 10]", "L", "minus", "8"])

    def test_every_type(self):
        self.assertOutput("c = true\nb = if c then false else true\nprint b", ["false"])
        self.assertOutput("c = false\nxs = if c then [1] else [2, 3]\nprint xs", ["[2, 3]"])
        self.assertOutput('c = true\no = if c then {n: 1} else {n: 2}\nprint o.n', ["1"])
        self.assertOutput("c = true\nxs = if c then [] of number else [1]\nprint xs length", ["0"])

    def test_only_the_chosen_value_is_computed(self):
        self.assertOutput("d = 0\nprint if d == 0 then 0 else 10 / d", ["0"])
        self.assertOutput("xs = [] of number\nprint if xs length > 0 then xs max + 1 else 1", ["1"])

    def test_both_values_are_checked_before_the_run(self):
        self.assertError("c = true\nprint if c then 1 else nothing", "V303")
        self.assertError('c = true\nprint if c then 1 else 1 + "a"', "V301")

    def test_reading_a_variable_inside_it_counts_as_a_use(self):
        self.assertOutput("a = 1\nb = 2\nc = true\nprint if c then a else b", ["1"])

    def test_inside_blocks_the_else_does_not_end_the_block(self):
        source = ('for x in [1, 7]\n'
                  '  if x > 0\n'
                  '    y = if x > 5 then "big" else "small"\n'
                  '    print y\n'
                  '  else\n'
                  '    print "none"\n'
                  '  end\n'
                  'end')
        self.assertOutput(source, ["small", "big"])

    def test_then_is_not_a_keyword(self):
        self.assertNotIn("then", KEYWORDS)
        self.assertEqual(len(KEYWORDS), 33)      # v0.3 added while, continue, exit
        self.assertOutput("then = 4\nprint then", ["4"])

    def test_the_block_if_is_unchanged(self):
        source = 'm = 5\nif m < 10\n  print "a"\nelse if m < 20\n  print "b"\nelse\n  print "c"\nend'
        self.assertOutput(source, ["a"])


class ChoiceMistakes(AxionTest):
    def test_else_is_required(self):
        out = self.assertError('m = 5\nx = if m < 10 then "0"\nprint x', "P202")
        self.assertIn("A value chosen with if always needs else: there must be a value for both cases.", out)
        self.assertEqual(fix_of(out), 'x = if m < 10 then "0" else ...   (the value for the other case)')

    def test_then_is_required(self):
        out = self.assertError('m = 5\nx = if m < 10 "0" else ""\nprint x', "P202")
        self.assertIn("then is missing here.", out[3])

    def test_the_values_must_have_one_type(self):
        out = self.assertError('m = 5\nx = if m < 10 then "0" else 0\nprint x', "V301")
        self.assertIn("Both values of if ... then ... else must have one type, got text and number.", out)
        self.assertEqual(fix_of(out), 'make both text: write "0" instead of 0')

    def test_number_variable_against_text(self):
        out = self.assertError('m = 5\nx = if m < 10 then "0" else m\nprint x', "V301")
        self.assertEqual(fix_of(out), "make both text: write m as text instead of m")
        self.assertOutput('m = 5\nx = if m < 10 then "0" else m as text\nprint x', ["0"])

    def test_other_type_pairs_have_no_guessed_fix(self):
        out = self.assertError("m = 5\nx = if m < 10 then true else 0\nprint x", "V301")
        self.assertIsNone(fix_of(out))

    def test_the_condition_must_be_bool(self):
        out = self.assertError("m = 5\nx = if m then 1 else 0\nprint x", "V307")
        self.assertIn("The condition must be bool, got number.", out)
        self.assertEqual(fix_of(out), "compare it, e.g. if m > 0 then ...")

    def test_without_parentheses_inside_a_longer_expression(self):
        out = self.assertError('m = 5\nprint "a" + if m < 10 then "0" else ""', "P202")
        self.assertIn("if ... then ... else ... inside a longer expression needs parentheses.", out)
        self.assertEqual(fix_of(out), "put it in parentheses: (if condition then a else b)")

    def test_block_if_with_then(self):
        out = self.assertError("m = 5\nif m < 10 then\n  print m\nend", "P210")
        self.assertIn("A block if has no then: the line itself ends the condition.", out)
        self.assertEqual(fix_of(out), "if m < 10")

    def test_one_line_if_that_sets_one_variable_becomes_a_value(self):
        source = "m = 5\ny = 0\nif m < 10 then y = 1 else y = 2\nprint y"
        out = self.assertErrors(source, ["P210"])            # and no "if is never closed" echo
        self.assertEqual(fix_of(out), "y = if m < 10 then 1 else 2")
        self.assertOutput("m = 5\ny = 0\ny = if m < 10 then 1 else 2\nprint y", ["1"])

    def test_one_line_if_with_another_body(self):
        out = self.assertErrors("m = 5\nif m < 10 then print m\nprint m", ["P210"])
        self.assertEqual(fix_of(out), "end the line after the condition, put the rest on the next "
                                      "lines and close the block with end")

    def test_do_keeps_its_message(self):
        out = self.assertError("for x in [1] do\n  print x\nend", "P210")
        self.assertIn("Axion has no do: the line itself ends the loop header.", out)
        self.assertEqual(fix_of(out), "for x in [1]")

    def test_question_mark_operator(self):
        out = self.assertError("m = 5\nx = m > 0 ? 1 : 2\nprint x", "L101")
        self.assertIn("Axion has no ? : operator.", out)
        self.assertEqual(fix_of(out), "x = if m > 0 then 1 else 2")
        self.assertOutput("m = 5\nx = if m > 0 then 1 else 2\nprint x", ["1"])

    def test_question_mark_after_print_and_return(self):
        self.assertEqual(fix_of(self.assertError('m = 5\nprint m > 0 ? "a" : "b"', "L101")),
                         'print if m > 0 then "a" else "b"')

    def test_question_mark_in_a_shape_that_is_not_rewritten(self):
        out = self.assertError("m = 5\nx = 1 + (m > 0 ? 1 : 2) ? 3 : 4\nprint x", "L101")
        self.assertEqual(fix_of(out), "write: if condition then a else b")


class ListWordBeforeTheList(AxionTest):
    def test_sum(self):
        out = self.assertError("row = [1, 2]\nrow_sum = sum row\nprint row_sum", "P202")
        self.assertIn("sum comes after the list.", out)
        self.assertEqual(fix_of(out), "row_sum = row sum")
        self.assertOutput("row = [1, 2]\nrow_sum = row sum\nprint row_sum", ["3"])

    def test_max_of_a_field(self):
        out = self.assertError("o = {xs: [1, 5]}\nprint max o.xs", "P202")
        self.assertEqual(fix_of(out), "print o.xs max")

    def test_sort_with_by(self):
        source = 'ps = [{age: 3}, {age: 1}]\nqs = sort ps by age\nprint qs'
        self.assertEqual(fix_of(self.assertError(source, "P202")), "qs = ps sort by age")

    def test_a_variable_named_sum_is_still_free(self):
        self.assertOutput("sum = 1\nsum = sum + 2\nprint sum", ["3"])

    def test_call_form_keeps_its_own_hint(self):
        out = self.assertError("row = [1, 2]\nprint sum(row)", "V303")
        self.assertEqual(fix_of(out), "print row sum")


class ElementOfASortedList(AxionTest):
    PEOPLE = 'ps = [{id: 2}, {id: 5}]\n'

    def test_index_right_after_sort(self):
        out = self.assertError(self.PEOPLE + "top = ps sort by id descending[0].id + 1\nprint top", "P202")
        self.assertIn("Put sort and its list in parentheses before taking an element.", out)
        self.assertEqual(fix_of(out), "top = (ps sort by id descending)[0].id + 1")

    def test_the_fix_runs(self):
        self.assertOutput(self.PEOPLE + "top = (ps sort by id descending)[0].id + 1\nprint top", ["6"])

    def test_plain_sort(self):
        out = self.assertError("xs = [3, 1]\nprint xs sort[0]", "P202")
        self.assertEqual(fix_of(out), "print (xs sort)[0]")

    def test_length_after_sort_still_works(self):
        self.assertOutput("xs = [3, 1]\nprint xs sort length", ["2"])


class PositionOfAValue(AxionTest):
    def test_index_as_an_operation(self):
        out = self.assertError('keys = ["a"]\nrs = ["x"]\nprint rs[keys index "a"]', "P202")
        self.assertIn("Axion has no operation that finds the position of a value in a list.", out)
        self.assertEqual(fix_of(out), "find it with a loop: for i in 0 to keys length - 1   "
                                      "and inside it: if keys[i] == value")

    def test_remove_index_is_unchanged(self):
        self.assertOutput("xs = [1, 2]\nxs remove index 0\nprint xs", ["[2]"])


class Continue(AxionTest):
    """v0.2 refused continue and explained how to rewrite the loop with else.
    v0.3 has continue (decision 12), so the same programs now run."""
    LOOP = ('xs = [1, 30, 2]\n'
            'for x in xs\n'
            '  if x > 20\n'
            '    print "big"\n'
            '    continue\n'
            '  end\n'
            '  print x\n'
            'end')

    def test_continue_that_ends_an_if(self):
        self.assertOutput(self.LOOP, ["1", "big", "2"])

    def test_the_rewritten_loop_runs(self):
        fixed = ('xs = [1, 30, 2]\nfor x in xs\n  if x > 20\n    print "big"\n  else\n'
                 '  print x\n  end\nend')
        self.assertOutput(fixed, ["1", "big", "2"])

    def test_another_broken_line_is_the_only_error(self):
        source = self.LOOP.replace("  print x\n", "  y = = 1\n  print x\n")
        self.assertErrors(source, ["P202"])

    def test_continue_as_the_only_line_of_a_branch(self):
        source = 'for x in [1, 30]\n  if x > 20\n    continue\n  else\n    print x\n  end\nend'
        self.assertOutput(source, ["1"])

    def test_a_line_after_continue_can_never_run(self):
        out = self.assertError("for x in [1]\n  print x\n  continue\n  print x\nend", "V319")
        self.assertEqual(fix_of(out), "remove it, or move it before the continue")

    def test_two_continues(self):
        source = ('for x in [1, 30, -2]\n  if x > 20\n    continue\n  end\n  if x < 0\n'
                  '    print "neg"\n    continue\n  end\n  print x\nend')
        self.assertOutput(source, ["1", "neg"])

    def test_break_is_unchanged(self):
        self.assertOutput("for x in [1, 2]\n  print x\n  break\nend", ["1"])


class EmptyListWithoutAType(AxionTest):
    GENERIC = "xs = [] of text   (or [] of number, [] of bool, [] of {name: text})"

    def test_the_type_comes_from_the_first_add(self):
        out = self.assertError("xs = []\nxs add 5\nprint xs", "P213")
        self.assertIn("An empty list needs the type of its elements.", out)
        self.assertEqual(fix_of(out), "xs = [] of number")
        self.assertOutput("xs = [] of number\nxs add 5\nprint xs", ["[5]"])

    def test_text_and_objects(self):
        out = self.assertError('names = []\nnames add "a"\nprint names', "P213")
        self.assertEqual(fix_of(out), "names = [] of text")
        source = 'seen = []\nk = "a"\nseen add {key: k, answer: "ok", n: 1}\nprint seen'
        self.assertEqual(fix_of(self.assertError(source, "P213")),
                         "seen = [] of {key: text, answer: text, n: number}")

    def test_the_list_is_read_before_anything_is_added(self):
        # the usual shape of "seen so far": read in a loop first, added to at the end of it
        source = ('seen = []\n'
                  'for r in ["a", "b", "a"]\n'
                  '  known = false\n'
                  '  for s in seen\n'
                  '    if s.key == r\n'
                  '      known = true\n'
                  '    end\n'
                  '  end\n'
                  '  if not known\n'
                  '    seen add {key: r, n: 1}\n'
                  '  end\n'
                  'end\n'
                  'print seen length')
        out = self.assertError(source, "P213")
        self.assertEqual(fix_of(out), "seen = [] of {key: text, n: number}")
        self.assertOutput(source.replace("seen = []", "seen = [] of {key: text, n: number}"), ["2"])

    def test_every_list_gets_its_own_line(self):
        source = 'keys = []\nsizes = []\nkeys add "a"\nsizes add 1\nprint keys\nprint sizes'
        out = self.assertErrors(source, ["P213", "P213"])
        self.assertEqual(fixes(out), ["keys = [] of text", "sizes = [] of number"])
        self.assertFalse(any(line.startswith("The same mistake") for line in out))

    def test_a_list_that_gets_another_list(self):
        out = self.assertError("xs = []\nys = [1, 2]\nxs = ys\nprint xs", "P213")
        self.assertEqual(fix_of(out), "xs = [] of number")

    def test_nothing_is_added_the_general_hint_stays(self):
        out = self.assertError("xs = []\nprint xs", "P213")
        self.assertEqual(fix_of(out), self.GENERIC)

    def test_known_and_unknown_together(self):
        out = self.assertErrors("xs = []\nys = []\nxs add 1\nprint xs\nprint ys", ["P213", "P213"])
        self.assertEqual(fixes(out), ["xs = [] of number", "ys = [] of text   (or [] of number, "
                                                           "[] of bool, [] of {name: text})"])

    def test_another_broken_line_does_not_hide_the_type(self):
        out = self.assertErrors("xs = []\ny = = 2\nxs add 5\nprint xs", ["P213", "P202"])
        self.assertEqual(fixes(out)[0], "xs = [] of number")

    def test_a_block_mistake_leaves_the_general_hint(self):
        out = self.assertError("xs = []\nif true\nxs add 5\nprint xs", "P213")
        self.assertEqual(fix_of(out), self.GENERIC)

    def test_an_empty_list_in_other_places_keeps_its_hint(self):
        out = self.assertError("xs = [1]\nxs = []\nprint xs", "P213")
        self.assertEqual(fix_of(out), "xs = [] of number")
        out = self.assertError("function f(xs: list of number)\n  print xs\nend\nf([])", "P213")
        self.assertIn("[] of text", fix_of(out))

    def test_a_bare_empty_list_never_runs(self):
        code, out = run("xs = []\nxs add 5\nprint xs")
        self.assertEqual(code, 1)
        self.assertNotIn("[5]", out)

    def test_the_typed_form_is_unchanged(self):
        self.assertOutput("xs = [] of number\nxs add 5\nprint xs", ["[5]"])


class UnusedAfterAFailedTwin(AxionTest):
    """phi4, task 16: a variable set in both branches of an if; the first line failed, its
    use was therefore not checked, and the second line was reported as 'never used' with
    the advice to delete it."""

    SOURCE = ('n = 5\n'
              'if n > 0\n'
              '  label = n + ":"\n'
              'else\n'
              '  label = "none"\n'
              'end\n'
              'print "total " + label')

    def test_only_the_real_mistake_is_reported(self):
        self.assertErrors(self.SOURCE, ["V301"])

    def test_after_the_repair_the_scope_mistake_is_reported(self):
        fixed = self.SOURCE.replace('n + ":"', 'n as text + ":"')
        out = self.assertError(fixed, "V304")
        self.assertEqual(fix_of(out), "create label before the if and only change it inside")

    def test_a_really_unused_variable_is_still_reported(self):
        self.assertError("x = 1\ny = 2\nprint y", "V305")


class Arithmetic(unittest.TestCase):
    def test_whole_division_matches_floor_division(self):
        for a in range(-30, 31):
            for b in range(1, 9):
                code, out = run(f"a = 0 + ({a})\nprint a // {b}")
                self.assertEqual((code, Decimal(out[0])), (0, Decimal(a // b)), (a, b))


if __name__ == "__main__":
    unittest.main()
