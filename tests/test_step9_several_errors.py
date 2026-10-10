"""Step 9: one pass reports up to 5 different errors.

Decided after the GPT run on task 9: eight attempts went on eight small mistakes shown one
at a time, and every attempt was a full rewrite of a 240-line program.

Rules:
- the same mistake on several lines is one error that names the other lines;
- errors come in two waves: how the program is written (lexer, parser), then what it means
  (validator); a program with mistakes of the first kind is not checked for the second;
- an error that only follows from another one is not reported;
- a runtime error is always a single one; nothing runs if anything is reported.
"""
import unittest

from helpers import AxionTest

from axionlang.engine.errors import MAX_ERRORS


def blocks(out):
    """The errors of an output: a list of (header, message, fix, also)."""
    result, current = [], None
    for line in out:
        if line.startswith("ERROR "):
            current = {"head": line, "lines": []}
            result.append(current)
        elif current is not None:
            current["lines"].append(line)
    return result


def fix_of(block):
    return next((x[5:] for x in block["lines"] if x.startswith("Fix: ")), None)


def also_of(block):
    return next((x for x in block["lines"] if x.startswith("The same mistake is on line")), None)


class SyntaxWave(AxionTest):
    def test_limit(self):
        self.assertEqual(MAX_ERRORS, 5)

    def test_two_different_mistakes_are_both_reported_in_line_order(self):
        # qwen2.5-coder:14b, task 7: needed two attempts for these two lines.
        source = ('a = "x"\np = "abc"\nif a is not number\nprint 1\nelse if length p < 8\nprint 2\nend')
        out = self.assertErrors(source, ["P202", "P202"])
        first, second = blocks(out)
        self.assertEqual(first["head"], "ERROR P202 line 3:6")
        self.assertEqual(fix_of(first), "if not a is number")
        self.assertEqual(second["head"], "ERROR P202 line 5:9")
        self.assertEqual(fix_of(second), "else if p length < 8")
        fixed = source.replace("if a is not number", "if not a is number", 1).replace(
            "else if length p < 8", "else if p length < 8")
        self.assertOutput(fixed, ["1"])

    def test_errors_are_separated_by_one_blank_line(self):
        out = self.assertErrors("x = 5.0\nprint x = 1", ["L104", "P202"])
        self.assertEqual(out.count(""), 1)
        self.assertEqual(out[out.index("") + 1], "ERROR P202 line 2:9")

    def test_lexer_and_parser_mistakes_together(self):
        # GPT, task 9, attempts 1 and 2.
        source = "pos = -1\nrate = 0.10\nif pos == -1\nprint rate\nend\nif pos != -1\nprint 0\nend"
        out = self.assertErrors(source, ["L104", "P207"])
        number, minus = blocks(out)
        self.assertEqual(fix_of(number), "write 0.1")
        self.assertEqual(fix_of(minus), "if pos == (-1)")
        self.assertEqual(also_of(minus), "The same mistake is on line 6: fix it too.")

    def test_same_mistake_stays_one_error(self):
        out = self.assertErrors("a = []\nb = []\nc = []\nprint a\nprint b\nprint c", ["P213"])
        self.assertEqual(also_of(blocks(out)[0]), "The same mistake is on lines 2, 3: fix them too.")

    def test_block_mistake_is_found_behind_line_mistakes(self):
        # GPT, task 9, attempt 1: an extra end was hidden behind 0.10 and == -1.
        source = "x = 0.10\nif x > 0\nprint x\nend\nend\nprint 1"
        out = self.assertErrors(source, ["L104", "P212"])
        self.assertEqual(blocks(out)[1]["head"], "ERROR P212 line 5:1")

    def test_unclosed_block_is_found_behind_line_mistakes(self):
        source = "xs = []\nfor x in [1]\nif x = 1\nprint x\nprint xs"
        out = self.assertErrors(source, ["P213", "P212", "P202"])
        self.assertIn("if is never closed: an end is missing between this line and the end of the program.", out)

    def test_else_without_if_behind_a_broken_if_header(self):
        source = "x = 1\nif x is not number\nprint 1\nend\nelse\nprint 2\nend"
        out = self.assertErrors(source, ["P202", "P211"])
        self.assertIn("This else comes after the end on line 4, which already closed its if.", out)

    def test_a_broken_header_does_not_break_its_block(self):
        # The if header is wrong, but its else and end are in place: one error only.
        self.assertErrors("x = 1\nif x = 1\nprint 1\nelse\nprint 2\nend", ["P202"])
        self.assertErrors("for x in 1 to = 3\nprint x\nend", ["P202"])
        self.assertErrors("x = 1\nif x > 0\nprint 1\nelse if x = 0\nprint 2\nend", ["P202"])

    def test_lines_of_a_multiline_list_are_not_statements(self):
        source = 'xs = [\n1,\n2\n]\nys = {a: 1,\nb: "t"}\nprint length xs\nprint ys'
        out = self.assertErrors(source, ["P202"])
        self.assertEqual(blocks(out)[0]["head"], "ERROR P202 line 7:7")

    def test_a_mistake_inside_a_multiline_list_is_reported_once(self):
        self.assertErrors("xs = [\n1,\n2.50\n]\nprint xs", ["L104"])

    def test_text_with_brackets_and_hash_is_not_a_bracket(self):
        self.assertErrors('a = "[ (# {"\nprint length a\nprint a', ["P202"])

    def test_meaning_is_not_checked_while_the_writing_is_wrong(self):
        # print y (unknown variable) is a validator error: it waits for the next attempt.
        out = self.assertErrors('x = 5.0\nprint y\nprint x + "a"', ["L104"])
        self.assertNotIn("Unknown variable y.", out)

    def test_keyword_used_as_a_name_is_one_mistake(self):
        # qwen2.5-coder:14b and phi4, task 8: length = ..., then length used below.
        source = 't = "abc"\nlength = t length\nprint "n: " + length as text\ntotal = 0 + length\nprint total'
        out = self.assertErrors(source, ["P214"])
        block = blocks(out)[0]
        self.assertEqual(fix_of(block), "choose another name, e.g. my_length")
        self.assertEqual(also_of(block), "The same mistake is on lines 3, 4: fix them too.")

    def test_keyword_as_a_value(self):
        out = self.assertErrors("function f(value: number) -> number\nreturn value\nend\nprint f(1)", ["P214"])
        self.assertEqual(also_of(blocks(out)[0]), "The same mistake is on line 2: fix it too.")

    def test_at_most_five(self):
        source = ("a = 5.0\nb = 'x'\nc = []\nd = a = 1\nprint length c\nprint b && d\nprint a is text")
        out = self.assertErrors(source, ["L104", "L106", "P213", "P202", "P202"])
        self.assertEqual(out[-1], "(2 more errors not shown: fix these first.)")

    def test_six_errors_say_one_more(self):
        source = "a = 5.0\nb = 'x'\nc = []\nd = a = 1\nprint length c\nprint b && d"
        out = self.assertErrors(source, ["L104", "L106", "P213", "P202", "P202"])
        self.assertEqual(out[-1], "(1 more error not shown: fix these first.)")

    def test_exactly_five_has_no_note(self):
        source = "a = 5.0\nb = 'x'\nc = []\nd = a = 1\nprint length c"
        out = self.assertErrors(source, ["L104", "L106", "P213", "P202", "P202"])
        self.assertTrue(out[-1].startswith("Fix: "))

    def test_nothing_runs(self):
        code_and_out = self.assertErrors('print "start"\nx = 5.0\nprint x = 1', ["L104", "P202"])
        self.assertTrue(code_and_out[0].startswith("ERROR "))


class MeaningWave(AxionTest):
    def test_two_independent_mistakes(self):
        source = 'f = {age: "20"}\nif f.age < 18\nprint 1\nend\nn = 5\nprint "N: " + n'
        out = self.assertErrors(source, ["V308", "V301"])
        first, second = blocks(out)
        self.assertEqual(fix_of(first), "if f.age as number < 18")
        self.assertEqual(fix_of(second), 'print "N: " + n as text')

    def test_several_unused_things(self):
        # GPT, task 9, attempts 5-8: one error per attempt.
        source = ("xs = [1]\nflags = [] of bool\nspare = 0\nfor x in xs\n"
                  "flags add false\nend\nfor y in flags\nprint 1\nend")
        out = self.assertErrors(source, ["V305", "V305", "V305"])
        self.assertIn("spare is created but never used.", out)
        self.assertIn("The loop variable x is never used.", out)
        self.assertIn("The loop variable y is never used.", out)

    def test_same_message_on_two_lines_is_one_error(self):
        source = "xs = [1]\nfor i in xs\nprint 1\nend\nfor i in xs\nprint 2\nend"
        out = self.assertErrors(source, ["V305"])
        self.assertEqual(also_of(blocks(out)[0]), "The same mistake is on line 5: fix it too.")

    def test_lines_that_need_a_broken_variable_are_not_reported(self):
        source = 'x = 1 + "a"\nprint x\ny = x + 1\nprint y\nz = y\nprint z'
        self.assertErrors(source, ["V301"])

    def test_a_misspelt_name_does_not_make_the_real_one_unused(self):
        out = self.assertErrors("total = 5\nprint totl", ["V303"])
        self.assertIn("Fix: did you mean total?", out)

    def test_a_misspelt_function_does_not_make_the_real_one_unused(self):
        source = "function tax(a: number) -> number\nreturn a\nend\nprint taks(1)"
        self.assertErrors(source, ["V303"])

    def test_names_in_a_failed_line_are_not_unused(self):
        self.assertErrors('a = 1\nb = "t"\nprint a + b', ["V301"])
        self.assertErrors('age = 15\nage = "sixteen"', ["V302"])
        self.assertErrors("x = 1\nprint x(2)", ["V303"])
        self.assertErrors('a = 1\nif a\nb = a\nprint b\nend', ["V307"])

    def test_a_really_unused_variable_is_still_reported(self):
        self.assertErrors('x = 1\nprint 10 + "a"', ["V305", "V301"])

    def test_refused_permission_does_not_make_the_read_undeclared(self):
        self.assertErrors('allow read "data/"\nprint read "data/a.txt"', ["S502"])

    def test_failed_read_does_not_make_allow_unused(self):
        self.assertErrors('allow read "notes/"\nprint read "notes/"', ["V326"],
                          policy={"allow_read": ["notes/"]})

    def test_out_of_scope_is_not_also_unused(self):
        # GPT, task 9: created inside an if, read after its end.
        out = self.assertErrors("ok = true\nif ok\nbest = 1\nend\nprint best", ["V304"])
        self.assertIn("best was created inside the if at line 2 and does not exist outside it.", out)

    def test_out_of_scope_used_twice_is_one_error(self):
        out = self.assertErrors("ok = true\nif ok\nbest = 1\nend\nprint best\nprint best + 1", ["V304"])
        self.assertEqual(also_of(blocks(out)[0]), "The same mistake is on line 6: fix it too.")

    def test_errors_inside_blocks_and_after_them(self):
        source = ('xs = [1, 2]\nfor x in xs\nprint x + "a"\nxs add 3\nend\nif xs length > 0\n'
                  'print xs + 1\nend\nbreak')
        out = self.assertErrors(source, ["V301", "V316", "V301", "V327"])
        self.assertEqual([b["head"].split()[3] for b in blocks(out)], ["3:7", "4:1", "7:7", "9:1"])

    def test_errors_in_a_function_and_in_the_main_program(self):
        source = ('function f(a: number) -> number\nprint a + "x"\nreturn a\nend\n'
                  'n = f(1)\nprint n + "y"')
        out = self.assertErrors(source, ["V301"])            # the same mistake: one error
        self.assertEqual(also_of(blocks(out)[0]), "The same mistake is on line 6: fix it too.")
        source = source.replace('print n + "y"', "print n + nope")
        self.assertErrors(source, ["V301", "V303"])

    def test_function_state_is_restored_after_an_error_in_it(self):
        # The function has no return on every path; the main program is still checked.
        source = "function f(a: number) -> number\nif a > 0\nreturn a\nend\nend\nx = f(1)\nprint x + y"
        out = self.assertErrors(source, ["V318", "V303"])
        self.assertIn("Unknown variable y.", out)

    def test_everything_after_a_return_is_one_error(self):
        source = "function f() -> number\nreturn 1\nprint 2\nprint 3\nend\nprint f()"
        out = self.assertErrors(source, ["V319"])
        self.assertEqual(also_of(blocks(out)[0]), "The same mistake is on line 4: fix it too.")

    def test_at_most_five(self):
        source = "\n".join(f"v{i} = {i}" for i in range(7)) + '\nprint "end"'
        out = self.assertErrors(source, ["V305"] * 5)
        self.assertEqual(out[-1], "(2 more errors not shown: fix these first.)")

    def test_nothing_runs(self):
        out = self.assertErrors('print "start"\nprint 1 + "a"\nprint nope', ["V301", "V303"])
        self.assertTrue(out[0].startswith("ERROR "))

    def test_runtime_error_is_single_and_keeps_the_output(self):
        source = 'xs = [1]\nprint "start"\nprint xs[5]\nprint xs[7]'
        code_out = self.assertError(source, "R403", printed_before=["start"])
        self.assertEqual(code_out[0], "ERROR R403 line 3:7")

    def test_one_error_looks_as_before(self):
        out = self.assertErrors('print 10 + "a"', ["V301"])
        self.assertEqual(out, ["ERROR V301 line 1:7", 'print 10 + "a"', "      ^^^^^^^^",
                               "Cannot add number and text.", 'Fix: print 10 as text + "a"'])


if __name__ == "__main__":
    unittest.main()
