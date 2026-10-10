"""Step 8: changes decided after the applied-task run (qwen2.5-coder:14b, gemma3:12b, phi4,
llama3.2:3b on tasks 1-8).

Language: break (3 of 4 models wrote it), read takes the whole expression, indentation has
no meaning (the last two are tested in test_hints_full_line.py).
Hints: every Fix below was either wrong or unclear in that run; each test applies the Fix
and checks that the corrected program runs.
"""
import unittest

from helpers import AxionTest

from axionlang.engine.lexer import KEYWORDS


def fix_of(out):
    return next(line[5:] for line in out if line.startswith("Fix: "))


def also(out):
    return next((line for line in out if line.startswith("The same mistake is on line")), None)


class BreakStatement(AxionTest):
    def test_keyword_count(self):
        self.assertEqual(len(KEYWORDS), 33)      # v0.3 added while, continue, exit
        self.assertIn("break", KEYWORDS)

    def test_stops_the_loop(self):
        self.assertOutput("for x in [1, 2, 3]\nif x == 2\nbreak\nend\nprint x\nend\nprint 9", ["1", "9"])

    def test_search_then_stop(self):
        source = ('names = ["a", "b", "c", "b"]\npos = 0 - 1\nfor i in 0 to names length - 1\n'
                  'if names[i] == "b"\npos = i\nbreak\nend\nend\nprint pos')
        self.assertOutput(source, ["1"])

    def test_stops_only_the_nearest_loop(self):
        source = "for a in 1 to 2\nfor b in 1 to 3\nif b == 2\nbreak\nend\nprint a * 10 + b\nend\nend"
        self.assertOutput(source, ["11", "21"])

    def test_break_in_else_branch(self):
        self.assertOutput("for x in [1, 2, 3]\nif x < 2\nprint x\nelse\nbreak\nend\nend", ["1"])

    def test_block_variables_are_gone_after_break(self):
        source = "t = 0\nfor x in [1, 2]\ny = x\nt = t + y\nbreak\nend\nprint t"
        self.assertOutput(source, ["1"])

    def test_break_in_a_function_loop(self):
        source = ("function first_big(xs: list of number) -> number\nfound = 0\nfor x in xs\n"
                  "if x > 10\nfound = x\nbreak\nend\nend\nreturn found\nend\nprint first_big([1, 20, 30])")
        self.assertOutput(source, ["20"])

    def test_steps_are_still_counted(self):
        source = "for x in 1 to 100\nif x == 3\nbreak\nend\nend\nprint 1"
        self.assertOutput(source, ["1"], policy={"max_steps": 20})

    def test_outside_a_loop(self):
        out = self.assertError("x = 1\nif x == 1\nbreak\nend", "V327")
        self.assertIn("break works only inside a loop.", out)
        self.assertEqual(fix_of(out), "remove it; to end the program here write exit")    # v0.3

    def test_at_top_level(self):
        self.assertError("break", "V327")

    def test_function_inside_loop_call_is_not_in_the_loop(self):
        source = "function f()\nbreak\nend\nfor x in [1]\nf()\nprint x\nend"
        self.assertError(source, "V327")

    def test_nothing_runs_when_break_is_misplaced(self):
        self.assertError('print "start"\nbreak', "V327")

    def test_code_after_break_never_runs(self):
        out = self.assertError("for x in [1]\nprint x\nbreak\nprint 2\nend", "V319")
        self.assertEqual(out[0], "ERROR V319 line 4:1")
        self.assertIn("This line can never run: break has already stopped the loop.", out)

    def test_code_after_if_that_always_leaves(self):
        source = ("function f(xs: list of number) -> number\nfor x in xs\nif x > 1\nreturn x\n"
                  "else\nbreak\nend\nprint 1\nend\nreturn 0\nend\nprint f([1])")
        out = self.assertError(source, "V319")
        self.assertEqual(out[0], "ERROR V319 line 8:1")

    def test_break_is_not_a_return(self):
        source = "function f(xs: list of number) -> number\nfor x in xs\nbreak\nend\nend\nprint f([1])"
        self.assertError(source, "V305")           # x unused comes first
        source = ("function f(xs: list of number) -> number\nfor x in xs\nif x > 0\nbreak\nend\n"
                  "end\nend\nprint f([1])")
        self.assertError(source, "V318")

    def test_break_with_something_after_it(self):
        self.assertError("for x in [1]\nprint x\nbreak x\nend", "P201")

    def test_break_cannot_be_a_name(self):
        out = self.assertError("break = true\nprint break", "P214")
        self.assertEqual(fix_of(out), "choose another name, e.g. my_break")

    def test_break_as_a_field_name(self):
        self.assertOutput("o = {break: 1}\nprint o.break", ["1"])

    def test_continue_exists_since_v03(self):
        self.assertOutput("for x in [1, 2, 3]\nif x == 2\ncontinue\nend\nprint x\nend", ["1", "3"])


class SameMistakeOnSeveralLines(AxionTest):
    """One parser mistake repeated on other lines is reported once, with all its lines."""

    def test_prefix_length_twice(self):
        # gemma3:12b, task 8: lost two attempts fixing the same mistake line by line.
        source = 'f = "abc"\ntotal = 0\ntotal = total + length f\nprint "n: " + length f as text\nprint total'
        out = self.assertError(source, "P202")
        self.assertEqual(out[0], "ERROR P202 line 3:17")
        self.assertEqual(also(out), "The same mistake is on line 4: fix it too.")

    def test_single_equals_in_two_headers(self):
        # llama3.2:3b, task 5.
        source = 'k = "in"\nif k = "in"\nprint 1\nelse if k = "out"\nprint 2\nend'
        out = self.assertError(source, "P202")
        self.assertEqual(fix_of(out), 'if k == "in"')
        self.assertEqual(also(out), "The same mistake is on line 4: fix it too.")
        fixed = 'k = "in"\nif k == "in"\nprint 1\nelse if k == "out"\nprint 2\nend'
        self.assertOutput(fixed, ["1"])

    def test_untyped_empty_lists(self):
        # gemma3:12b and phi4, task 6: regions = [] / totals = [] / counts = [].
        source = "a = []\nb = []\nc = [] of text\nprint a\nprint b\nprint c"
        out = self.assertError(source, "P213")
        self.assertEqual(also(out), "The same mistake is on line 2: fix it too.")

    def test_for_header_is_checked_too(self):
        source = "xs = [1]\nn = length xs\nfor i in 0 to length xs - 1\nprint i + n\nend"
        out = self.assertError(source, "P202")
        self.assertEqual(also(out), "The same mistake is on line 3: fix it too.")

    def test_a_different_mistake_is_its_own_error(self):
        source = 'xs = [1]\nprint length xs\nif xs length = 1\nprint 1\nend'
        out = self.assertErrors(source, ["P202", "P202"])
        self.assertFalse(any(line.startswith("The same mistake is on line") for line in out))

    def test_one_mistake_has_no_also_affected(self):
        out = self.assertError("xs = [1]\nprint length xs\nprint xs length", "P202")
        self.assertIsNone(also(out))

    def test_lines_of_a_multiline_list_are_not_reported(self):
        source = "xs = [\n1,\n2\n]\nprint length xs"
        out = self.assertError(source, "P202")
        self.assertIsNone(also(out))

    def test_indented_lines_are_found(self):
        source = "xs = [1]\nfor x in xs\n    print length xs\n    print x + length xs\nend"
        out = self.assertError(source, "P202")
        self.assertEqual(also(out), "The same mistake is on line 4: fix it too.")


class HabitHints(AxionTest):
    def check(self, source, code, fix, bad_line, expected):
        """source fails with code; the Fix is `fix`; with the Fix in place of bad_line it prints expected."""
        out = self.assertError(source, code)
        self.assertEqual(fix_of(out), fix)
        self.assertOutput(source.replace(bad_line, fix), expected)
        return out

    def test_length_before_a_field(self):
        # The old Fix was "form length.password": wrong.
        self.check('f = {password: "abc"}\nif length f.password < 8\nprint "short"\nend', "P202",
                   "if f.password length < 8", "if length f.password < 8", ["short"])

    def test_length_before_an_element(self):
        self.check('xs = ["ab"]\nprint length xs[0]', "P202", "print xs[0] length",
                   "print length xs[0]", ["2"])

    def test_length_call_form(self):
        self.check("xs = [1, 2]\nprint length(xs)", "P202", "print xs length", "print length(xs)", ["2"])

    def test_is_not_number(self):
        # qwen2.5-coder:14b and phi4, task 7. The old Fix was "text is number".
        out = self.check('age = "x"\nif age is not number\nprint "bad"\nend', "P202",
                         "if not age is number", "if age is not number", ["bad"])
        self.assertIn("is not number does not exist: put not before the value.", out)

    def test_is_not_number_on_a_field(self):
        self.check('f = {age: "x"}\nif f.age is not number\nprint "bad"\nend', "P202",
                   "if not f.age is number", "if f.age is not number", ["bad"])

    def test_is_not_number_in_else_if(self):
        source = 'a = "x"\nif a == ""\nprint 1\nelse if a is not number\nprint 2\nend'
        self.check(source, "P202", "else if not a is number", "else if a is not number", ["2"])

    def test_is_as_equality(self):
        # gemma3:12b, task 5: if op.kind is "in".
        self.check('k = "in"\nif k is "in"\nprint 1\nend', "P202", 'if k == "in"', 'if k is "in"', ["1"])

    def test_is_not_as_inequality(self):
        self.check('k = "in"\nif k is not "out"\nprint 1\nend', "P202", 'if k != "out"',
                   'if k is not "out"', ["1"])

    def test_is_another_type(self):
        out = self.assertError('k = "in"\nif k is text\nprint 1\nend', "P202")
        self.assertIn("Only is number and is date exist: every type is known before the run.", out)

    def test_empty_braces_are_a_dictionary_that_needs_its_type(self):
        # qwen2.5-coder:14b and llama3.2:3b, task 6. v0.2 answered "Axion has no dictionaries"
        # and offered a list of objects; v0.3 has a dictionary, so the Fix is its typed form.
        out = self.assertError("regions = {}\nprint regions", "P213")
        self.assertIn("An empty dictionary needs the type of its values.", out)
        self.assertTrue(fix_of(out).startswith("regions = {} of number"))
        self.assertOutput("regions = {} of number\nprint regions", ["{}"])

    def test_dictionary_type_form(self):
        # v0.3: a key is always text, so only the type of the values is written
        out = self.assertError("totals = {} of text to number\nprint totals", "P202")
        self.assertIn("A key is always text, so only the type of the values is written.", out)
        self.assertEqual(fix_of(out), "totals = {} of number")
        self.assertOutput("totals = {} of number\nprint totals length", ["0"])

    def test_text_as_a_list_index(self):
        out = self.assertError('xs = [1]\nk = "a"\nprint xs[k]', "V301")
        self.assertIn("for i in 0 to xs length - 1", fix_of(out))

    def test_membership(self):
        # v0.3: the hint is the ready line with contains (until then: a search loop)
        for line, fixed in (('if "a" in xs', 'if xs contains "a"'),
                            ('if not ("a" in xs)', 'if not (xs contains "a")'),
                            ('if "a" not in xs', 'if not xs contains "a"')):
            source = f'xs = ["a"]\n{line}\nprint 1\nelse\nprint 2\nend'
            out = self.assertError(source, "P202")
            self.assertIn("in works only in a for header; a membership test is written "
                          "with contains.", out)
            self.assertEqual(fix_of(out), fixed)
            self.assertOutput(source.replace(line, fixed), ["2" if "not" in fixed else "1"])

    def test_for_header_in_is_untouched(self):
        self.assertOutput('for x in ["a"]\nprint x\nend', ["a"])

    def test_else_after_end(self):
        # gemma3:12b, task 7: end before every else if; the old message blamed the for loop.
        source = "x = 2\nfor i in 1 to 1\nif x == 1\nprint i\nend\nelse if x == 2\nprint 2\nend\nend"
        out = self.assertError(source, "P211")
        self.assertEqual(out[0], "ERROR P211 line 6:1")
        self.assertIn("This else comes after the end on line 5, which already closed its if.", out)
        self.assertTrue(fix_of(out).startswith("remove the end on line 5"))
        self.assertOutput(source.replace("print i\nend\nelse", "print i\nelse"), ["2"])

    def test_else_after_end_at_top_level_and_in_function(self):
        out = self.assertError("x = 1\nif x == 1\nprint 1\nend\nelse\nprint 2\nend", "P211")
        self.assertTrue(fix_of(out).startswith("remove the end on line 4"))
        source = "function f(x: number)\nif x == 1\nprint 1\nend\nelse\nprint 2\nend\nend\nf(1)"
        out = self.assertError(source, "P211")
        self.assertTrue(fix_of(out).startswith("remove the end on line 4"))

    def test_else_without_any_if(self):
        out = self.assertError("else\nprint 1\nend", "P211")
        self.assertIn("else without a matching if.", out)
        out = self.assertError("for x in [1]\nprint x\nelse\nprint 2\nend", "P211")
        self.assertIn("else cannot be used in a for loop.", out)

    def test_unclosed_if_chain_explains_one_end(self):
        out = self.assertError("x = 1\nif x == 1\nprint 1\nelse if x == 2\nprint 2", "P212")
        self.assertIn("an if / else if / else chain has one end", fix_of(out))

    def test_text_compared_as_a_number(self):
        # Next error of qwen2.5-coder:14b and phi4 in task 7: form.age < 18 with age: text.
        self.check('f = {age: "20"}\nif f.age < 18\nprint 1\nelse\nprint 2\nend', "V308",
                   "if f.age as number < 18", "if f.age < 18", ["2"])

    def test_text_literal_that_is_not_a_number_keeps_the_general_hint(self):
        # v0.3: "abc" can never be a number, so no fix is offered (text and text now compare)
        out = self.assertError('n = 1\nif n < "abc"\nprint 1\nend', "V308")
        self.assertIn("< compares two numbers or two texts, got number and text.", out)
        self.assertFalse(any(line.startswith("Fix: ") for line in out))

    def test_changing_a_field_of_the_loop_variable(self):
        # gemma3:12b, phi4, qwen2.5-coder:14b, twice each: item.qty = ... inside for item in stock.
        # The loop variable is the element itself, so this changes the list.
        source = 'stock = [{sku: "a", qty: 1}]\nfor item in stock\nitem.qty = item.qty + 1\nend\nprint stock'
        self.assertOutput(source, ['[{sku: "a", qty: 2}]'])

    def test_replacing_the_loop_variable_points_to_positions(self):
        out = self.assertError("xs = [1, 2]\nfor x in xs\nx = x * 2\nend\nprint xs", "V315")
        self.assertIn("x is the loop variable and cannot be replaced.", out)
        self.assertEqual(fix_of(out), "to replace elements of xs loop over positions: "
                                      "for i in 0 to xs length - 1, then xs[i] = ...")
        self.assertOutput("xs = [1, 2]\nfor i in 0 to xs length - 1\nxs[i] = xs[i] * 2\nend\nprint xs",
                          ["[2, 4]"])

    def test_changing_the_loop_variable_itself_keeps_the_old_hint(self):
        # A loop over a literal list: there is no named list to change.
        out = self.assertError("for x in [1]\nx = 2\nprint x\nend", "V315")
        self.assertEqual(fix_of(out), "copy it first: new_x = x")


class ForeignCallFix(AxionTest):
    """str(x) and friends: the Fix must be valid for the type of x."""

    def test_str_of_text_drops_the_call(self):
        # llama3.2:3b, task 4: str(total as text). The old Fix was "total as text as text".
        source = 'total = 5\nprint "T: " + str(total as text)'
        out = self.assertError(source, "V303")
        self.assertEqual(fix_of(out), 'print "T: " + total as text')
        self.assertOutput('total = 5\n' + fix_of(out), ["T: 5"])

    def test_str_of_number(self):
        out = self.assertError('total = 5\nprint "T: " + str(total)', "V303")
        self.assertEqual(fix_of(out), 'print "T: " + total as text')

    def test_str_of_sum_keeps_parentheses(self):
        out = self.assertError('a = 5\nprint "T: " + str(a + 1)', "V303")
        self.assertEqual(fix_of(out), 'print "T: " + (a + 1) as text')
        self.assertOutput('a = 5\n' + fix_of(out), ["T: 6"])

    def test_int_of_number_is_the_whole_part(self):
        # v0.3: int() of a number cuts the fraction, which is floor (until then the call was
        # simply dropped, which left a fraction in place without a word)
        out = self.assertError("a = 5\nprint int(a) + 1", "V303")
        self.assertEqual(fix_of(out), "print (a floor) + 1")

    def test_int_of_text(self):
        out = self.assertError('a = "5"\nprint int(a) + 1', "V303")
        self.assertEqual(fix_of(out), "print a as number + 1")
        self.assertOutput('a = "5"\n' + fix_of(out), ["6"])

    def test_str_of_list(self):
        out = self.assertError("xs = [1]\nprint str(xs)", "V303")
        self.assertEqual(fix_of(out), "print shows lists, objects and dictionaries directly: print xs")

    def test_len_and_range_unchanged(self):
        out = self.assertError("xs = [1]\nprint len(xs)", "V303")
        self.assertEqual(fix_of(out), "print xs length")

    def test_statement_starting_with_a_keyword(self):
        out = self.assertError("number x = 1", "P202")
        self.assertIn("A statement cannot start with number.", out)


class FixNeverLeadsToANewError(AxionTest):
    def test_text_literal_plus_number_offers_only_the_join(self):
        out = self.assertError('n = 5\nprint "N: " + n', "V301")
        self.assertEqual(fix_of(out), 'print "N: " + n as text')
        self.assertOutput('n = 5\n' + fix_of(out), ["N: 5"])

    def test_numeric_text_literal_keeps_both_options(self):
        out = self.assertError('n = 5\nprint "10" + n', "V301")
        self.assertEqual(fix_of(out), 'to join text: "10" + n as text; to add numbers: "10" as number + n')

    def test_text_variable_keeps_both_options(self):
        out = self.assertError('n = 5\ns = "1"\nprint s + n', "V301")
        self.assertIn("to add numbers: s as number + n", fix_of(out))

    def test_read_swallowed_the_rest_of_the_line(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "n").mkdir()
            (Path(tmp) / "n" / "a.txt").write_text("7", encoding="utf-8")
            launch = {"policy": {"allow_read": ["n/"]}, "base_dir": tmp}
            out = self.assertError('allow read "n/"\nprint read "n/a.txt" + "!"', "R408", **launch)
            self.assertIn('File "n/a.txt!" does not exist.', out)
            self.assertIn("(read path)", fix_of(out))
            self.assertOutput('allow read "n/"\nprint (read "n/a.txt") + "!"', ["7!"], **launch)
            out = self.assertError('allow read "n/"\nprint read "n/zzz.txt"', "R408", **launch)
            self.assertFalse(any(line.startswith("Fix: ") for line in out))


class RepeatNTimes(AxionTest):
    """for i in 1 to n may leave i unused; for x in list may not.

    GPT wrote "repeat n times" loops in all three of its runs on task 9; the old rule made it
    write flags add (i != i).
    """

    def test_fill_a_list_n_times(self):
        source = "orders = [5, 6, 7]\nflags = [] of bool\nfor i in 0 to orders length - 1\nflags add false\nend\nprint flags"
        self.assertOutput(source, ["[false, false, false]"])

    def test_range_in_parentheses(self):
        self.assertOutput("n = 2\nfor i in (1 to n)\nprint 0\nend", ["0", "0"])

    def test_used_counter_still_works(self):
        self.assertOutput("for i in 1 to 2\nprint i\nend", ["1", "2"])

    def test_list_variable_is_not_a_range(self):
        # A list of numbers in a variable is a list of things, not a count.
        out = self.assertErrors("idx = 1 to 3\nfor k in idx\nprint 0\nend", ["V305"])
        self.assertIn("The loop variable k is never used.", out)

    def test_loop_over_a_list_gets_the_way_out(self):
        source = "orders = [5, 6]\nflags = [] of bool\nfor o in orders\nflags add false\nend\nprint flags"
        out = self.assertErrors(source, ["V305"])
        fix = fix_of(out)
        self.assertEqual(fix, "use o inside the loop; to only repeat N times write: "
                              "for o in 1 to orders length")
        self.assertOutput(source.replace("for o in orders", "for o in 1 to orders length"),
                          ["[false, false]"])

    def test_loop_over_a_literal_list(self):
        out = self.assertErrors('for w in ["a", "b"]\nprint 1\nend', ["V305"])
        self.assertEqual(fix_of(out), "use w inside the loop; to only repeat N times write: "
                                      "for w in 1 to n")

    def test_other_unused_things_are_still_errors(self):
        self.assertErrors("spare = 0\nfor i in 1 to 2\nprint 0\nend", ["V305"])
        self.assertErrors("function f(a: number)\nfor i in 1 to 2\nprint 0\nend\nend\nf(1)", ["V305"])

    def test_typo_inside_the_loop_is_still_caught(self):
        # The case the rule exists for: the element is never looked at.
        source = 'orders = [{id: "a"}, {id: "b"}]\nfor o in orders\nprint orders[0].id\nend'
        self.assertErrors(source, ["V305"])


class NeedlessAllow(AxionTest):
    """Models copy allow lines from the cheat sheet into programs that read nothing."""

    def test_unused_allow_is_reported_before_the_policy(self):
        # qwen2.5-coder:14b, task 5: S502 said "only the person running the program can grant this".
        out = self.assertError('allow read "data/"\nprint 1', "V305")
        self.assertEqual(fix_of(out), "remove it: a program asks only for what it uses")

    def test_policy_still_decides_when_the_program_reads(self):
        self.assertError('allow read "data/"\nprint read "data/a.txt"', "S502")

    def test_misplaced_allow_in_a_program_without_read(self):
        # phi4, tasks 2, 4: allow read "dir/" after the input line.
        out = self.assertError('input a: number\nallow read "dir/"\nprint a', "P215", data='{"a": 1}')
        self.assertEqual(fix_of(out), "delete this line: this program reads no files")

    def test_misplaced_allow_in_a_program_with_read(self):
        out = self.assertError('input a: text\nallow read "dir/"\nprint read "dir/" + a', "P215",
                               data='{"a": "x"}')
        self.assertEqual(fix_of(out), "move this line to the top of the program")

    def test_bare_allow(self):
        # llama3.2:3b, tasks 5, 7.
        out = self.assertError("allow\nprint 1", "P202")
        self.assertEqual(out[0], "ERROR P202 line 1:1")
        self.assertEqual(fix_of(out), "delete this line: this program reads no files")

    def test_allow_write(self):
        out = self.assertError('allow write "dir/"\nprint 1', "P202")
        self.assertEqual(fix_of(out), "delete this line: this program reads no files")

    def test_allow_write_in_a_program_with_read(self):
        out = self.assertError('allow write "dir/"\nprint read "dir/a.txt"', "P202")
        self.assertEqual(fix_of(out), 'allow read "folder/"')


if __name__ == "__main__":
    unittest.main()
