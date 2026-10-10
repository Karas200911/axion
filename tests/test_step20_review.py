"""Axion v0.3: what an independent review found, and its repairs.

After the five steps of v0.3 a separate tester, who had not written the code, was asked to
break it. It wrote about 300 probes and 16 complete programs from the cheat sheet alone.
No wrong result turned up in while / continue / exit, recursion, joining lists, the sort by
several fields, dictionaries, dates or rounding. What it did find is repaired and kept here:

    crashes         a Python exception instead of an Axion error (numbers past 28 digits,
                    a path no file can have, a very long expression, a file that is not text)
    a limit hole    a text could double until the memory was gone
    two rules       `exists` as a variable before `then`; the rounding rule refusing lines
                    whose meaning was already clear
    loop guards     a change through a loop variable (seen and unseen in the wrong places)
    Fix hints       lines that were themselves refused, or changed the meaning
"""
import shutil
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import AxionTest, run

ROOT = Path(__file__).resolve().parent.parent


def fix_of(out):
    return next((line[5:] for line in out if line.startswith("Fix: ")), None)


class NumbersPastTwentyEightDigits(AxionTest):
    def test_remainder_of_an_inexact_number(self):
        # since step 21 such a number is never made: the program stops one line earlier
        out = self.assertError('print "a"\nx = 2 ** 100\nprint x % 7', "R412", printed_before=["a"])
        self.assertEqual(out[:2], ["ERROR R412 line 2:5", "x = 2 ** 100"])
        self.assertIn("The result of ** is too large for a number.", out)

    def test_whole_division_too(self):
        self.assertError("print 10 ** 30 // 7", "R412")

    def test_twenty_eight_digits_are_still_exact(self):
        self.assertOutput("x = 10 ** 27 + 1\nprint x % 10\nprint x // 10 ** 26", ["1", "10"])

    def test_a_number_that_cannot_grow_further(self):
        out = self.assertError("x = 10 ** 500000\ny = x * x\nz = y * x\nprint z > 0", "R412")
        self.assertIn("The result of ** is too large for a number.", out)       # since step 21: at once
        out = self.assertError("x = 10 ** 20\ny = x * x\nz = y * x\nprint z > 0", "R412")
        self.assertEqual(out[0], "ERROR R412 line 2:5")
        self.assertIn("A number became too large here", " ".join(out))

    def test_rounding_a_huge_number_changes_nothing(self):
        self.assertError("x = 10 ** 30\nprint x round 2 == x\nprint x floor == x", "R412")   # no such number
        self.assertOutput("x = 9999999999999999999999999999\nprint x round 2 == x\nprint x floor == x", ["true", "true"])


class TextHasASizeLimit(AxionTest):
    def test_doubling_is_stopped(self):
        out = self.assertError('s = "ab"\nfor i in 1 to 60\n  s = s + s\nend\nprint s length', "R406")
        self.assertIn("A text would have 1048576 characters; the limit of the launch policy is 1000000.", out)

    def test_it_is_the_limit_of_lists(self):
        source = 's = "abcd"\nt = s + s\nprint t length'
        self.assertOutput(source, ["8"], policy={"max_list_size": 8})
        self.assertError(source, "R406", policy={"max_list_size": 7})

    def test_join_is_bounded_too(self):
        source = 'parts = ["abc", "abc", "abc"]\nprint (parts join "--") length'
        self.assertOutput(source, ["13"], policy={"max_list_size": 13})
        self.assertError(source, "R406", policy={"max_list_size": 12})


class PathsNoFileCanHave(AxionTest):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / "data").mkdir()
        (self.dir / "data" / "a.txt").write_text("hello", encoding="utf-8")
        self.launch = {"policy": {"allow_read": ["data/"]}, "base_dir": self.dir}

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_exists_says_no(self):
        source = 'allow read "data/"\ninput n: text\nprint exists "data/" + n'
        self.assertOutput(source, ["false"], data='{"n": "a\\u0000b"}', **self.launch)
        self.assertOutput(source, ["false"], data='{"n": "' + "a" * 300 + '"}', **self.launch)

    def test_read_is_an_ordinary_error(self):
        source = 'allow read "data/"\ninput n: text\nprint read "data/" + n'
        self.assertError(source, "R408", data='{"n": "a\\u0000b"}', **self.launch)
        self.assertError(source, "R408", data='{"n": "' + "a" * 300 + '"}', **self.launch)

    def test_a_file_larger_than_the_text_limit(self):
        source = 'allow read "data/"\nprint (read "data/a.txt") length'
        self.assertOutput(source, ["5"], policy={"allow_read": ["data/"], "max_list_size": 5}, base_dir=self.dir)
        self.assertError(source, "R406", policy={"allow_read": ["data/"], "max_list_size": 4}, base_dir=self.dir)

    def test_a_word_after_read_is_not_silently_applied_to_the_path(self):
        out = self.assertError('allow read "data/"\np = "data/a.txt"\nt = read p trim\nprint t', "V301", **self.launch)
        self.assertIn("read takes the whole expression after it as the path, so trim would apply to the "
                      "path, not to the file.", out)
        self.assertEqual(fix_of(out), "t = (read p) trim   (or, for the path itself: read (p trim))")
        self.assertOutput('allow read "data/"\np = "data/a.txt"\nt = (read p) upper\nprint t', ["HELLO"], **self.launch)

    def test_in_parentheses_the_word_belongs_to_the_path(self):
        self.assertOutput('allow read "data/"\np = " data/a.txt "\nprint read (p trim)', ["hello"], **self.launch)

    def test_split_and_contains_after_read(self):
        out = self.assertError('allow read "data/"\nrows = read "data/a.txt" split "l"\nprint rows', "V301", **self.launch)
        self.assertTrue(fix_of(out).startswith('rows = (read "data/a.txt") split "l"'))


class VeryLongExpressions(AxionTest):
    def test_a_thousand_terms(self):
        self.assertOutput("x = " + " + ".join(["1"] * 1000) + "\nprint x", ["1000"])

    def test_deep_parentheses(self):
        self.assertOutput("x = " + "(" * 500 + "1" + ")" * 500 + "\nprint x", ["1"])

    def test_beyond_every_limit_it_is_an_axiom_error(self):
        # How far the room reaches depends on the Python version (3.11 walks 60,000 terms,
        # 3.13 stops near 3,000). Either the answer is right or the error is Axion's own.
        code, out = run("y = 2\nx = " + " + ".join(["1"] * 60000) + "\nprint x + y")
        if code == 0:
            self.assertEqual(out, ["60002"])
        else:
            self.assertTrue(out[0].startswith("ERROR P217 line 2:1"), out[0])
            self.assertEqual(fix_of(out), "split it into several variables")


class ProgramFiles(unittest.TestCase):
    def launch(self, content):
        folder = Path(tempfile.mkdtemp())
        try:
            (folder / "p.ax").write_bytes(content)
            done = subprocess.run([sys.executable, "-B", "-m", "axionlang", str(folder / "p.ax")],
                                  capture_output=True, text=True,
                                  env={**os.environ, "PYTHONPATH": str(ROOT)})
            return done.returncode, done.stdout
        finally:
            shutil.rmtree(folder)

    def test_a_file_that_starts_with_the_invisible_mark(self):
        self.assertEqual(self.launch("﻿print 1\n".encode("utf-8")), (0, "1\n"))

    def test_a_file_that_is_not_text(self):
        code, out = self.launch(b"print \xff\xfe 1\n")
        self.assertEqual(code, 2)
        self.assertIn("PROGRAM FILE ERROR", out)
        self.assertNotIn("INTERNAL ERROR", out)


class ExistsAsAVariable(AxionTest):
    def test_before_then(self):
        source = 'names = ["a", "b"]\nexists = names contains "a"\nlabel = if exists then "yes" else "no"\nprint label'
        self.assertOutput(source, ["yes"])

    def test_before_the_words_after_a_value(self):
        self.assertOutput('exists = ["b", "a"]\nprint exists contains "a"\nprint exists sort\nprint exists join "-"',
                          ["true", '["a", "b"]', "b-a"])
        self.assertOutput("exists = 2.5\nprint exists round 0\nprint exists floor", ["3", "2"])


class TheRoundingRule(AxionTest):
    def test_parentheses_around_the_value_say_enough(self):
        source = "w = 5.2\nh = 3.1\nt = 0.5\ntiles = (w / t) ceiling * (h / t) ceiling\nprint tiles"
        self.assertOutput(source, ["77"])

    def test_each_side_rounded_on_its_own(self):
        self.assertOutput("a = 2.75\nprint a floor + a ceiling\nprint a round 1 * a round 0", ["5", "8.4"])

    def test_the_fractional_part_with_parentheses(self):
        self.assertOutput("a = 2.75\nprint a - (a floor)", ["0.75"])

    def test_what_cannot_be_read_is_still_refused(self):
        out = self.assertError("total = 10\ncount = 3\naverage = total / count round 2\nprint average", "V301")
        self.assertEqual(fix_of(out), "average = (total / count) round 2   (or, to round only that value: (count round 2))")
        out = self.assertError("a = 2.75\nx = a - a floor\nprint x", "V301")
        self.assertIn("(or, to round only that value: (a floor))", fix_of(out))


class ChangesThroughALoopVariable(AxionTest):
    def test_while_sees_them(self):
        source = ("xs = [{v: 1}, {v: 2}]\ntotal = 0\nwhile xs[0].v < 5\n  for x in xs\n    x.v = x.v + 1\n  end\n"
                  "  total = total + 1\nend\nprint total")
        self.assertOutput(source, ["4"])

    def test_a_parameter_is_not_changed_that_way(self):
        source = ("function total(xs: list of {v: number}) -> number\n  t = 0\n  for x in xs\n    x.v = x.v * 2\n"
                  "    t = t + x.v\n  end\n  return t\nend\nprint total([{v: 1}, {v: 2}])")
        out = self.assertError(source, "V324")
        self.assertIn("x is an element of the parameter xs, and a parameter cannot be changed.", out)
        fixed = source.replace("  t = 0\n", "  t = 0\n  new_xs = xs\n").replace("for x in xs", "for x in new_xs")
        self.assertOutput(fixed, ["6"])

    def test_reading_a_parameter_through_it_is_fine(self):
        source = ("function total(xs: list of {v: number}) -> number\n  t = 0\n  for x in xs\n    t = t + x.v\n"
                  "  end\n  return t\nend\nprint total([{v: 1}, {v: 2}])")
        self.assertOutput(source, ["3"])

    def test_a_list_reached_through_an_outer_loop_is_still_locked(self):
        out = self.assertError("grid = [[1, 2]]\nfor row in grid\n  for v in row\n    row add v\n  end\nend\nprint grid", "V316")
        self.assertIn("row cannot be changed inside a for loop over row.", out)
        self.assertError("grid = [[1, 2, 3]]\nfor row in grid\n  for v in row\n    row remove index 0\n    print v\n  end\nend",
                         "V316")

    def test_changing_another_row_is_still_allowed(self):
        source = "grid = [[1, 2], [3]]\nfor row in grid\n  row add 0\nend\nprint grid"
        self.assertOutput(source, ["[[1, 2, 0], [3, 0]]"])

    def test_a_piece_is_a_copy_so_its_elements_cannot_be_changed(self):
        source = "xs = [{v: 1}, {v: 2}, {v: 3}]\nfor x in xs[0 to 1]\n  x.v = 0\nend\nprint xs"
        self.assertError(source, "V315")

    def test_over_the_list_itself_it_works(self):
        self.assertOutput("xs = [{v: 1}, {v: 2}]\nfor x in xs\n  x.v = 0\nend\nprint xs", ["[{v: 0}, {v: 0}]"])


class RepairedHints(AxionTest):
    def hint(self, source, code, expected):
        out = self.assertError(source, code)
        self.assertEqual(fix_of(out), expected)
        return out

    def test_one_element_onto_a_result(self):
        source = ("function build(n: number) -> list of number\n  if n == 0\n    return [] of number\n  end\n"
                  "  return build(n - 1) + [n]\nend\nprint build(3)")
        self.hint(source, "V301", "build the list first: items = build(n - 1)   then   items add n"
                                  "   then use items in place of build(n - 1) + [n]")
        fixed = source.replace("  return build(n - 1) + [n]", "  items = build(n - 1)\n  items add n\n  return items")
        self.assertOutput(fixed, ["[1, 2, 3]"])

    def test_a_chain_of_python_choices_is_not_guessed(self):
        out = self.assertError("n = 5\nm = 2\nbig = n if n > m else m if m > 0 else 0\nprint big", "P210")
        self.assertIn("the inner choice in parentheses", fix_of(out))
        self.assertOutput("n = 5\nm = 0 - 1\nbig = if n > m then n else (if m > 0 then m else 0)\nprint big", ["5"])

    def test_two_loops_inside_brackets(self):
        out = self.assertError("xs = [1, 2]\nys = [x * y for x in xs for y in xs]\nprint ys", "P210")
        self.assertTrue(fix_of(out).startswith("write the loops out; the shape for one loop is:"))

    def test_as_date_after_an_addition(self):
        out = self.hint('start = "2026-10-05"\nprint start as days + 30 as date', "V301",
                        "print (start as days + 30) as date")
        self.assertIn("as date here applies only to 30, the value right before it.", out)
        self.assertOutput('start = "2026-10-05"\nprint (start as days + 30) as date', ["2026-11-04"])

    def test_raise_inside_a_function(self):
        source = "function f(n: number) -> number\n  if n < 0\n    raise ValueError(\"neg\")\n  end\n  return n\nend\nprint f(1)"
        out = self.assertError(source, "P210")
        self.assertIn("a function cannot stop the program", fix_of(out))
        self.assertNotIn("exit   ", fix_of(out))

    def test_elif_in_an_indented_block_gets_one_error(self):
        source = "x = 2\nif x == 1\n  print 1\nelif x == 2\n  print 2\nelif x == 3\n  print 3\nelse\n  print 0\nend"
        out = self.assertErrors(source, ["P210"])
        self.assertEqual(fix_of(out), "else if x == 2")
        self.assertIn("The same mistake is on line 6: fix it too.", out)

    def test_enumerate_from_one(self):
        self.hint("xs = [5, 6]\nfor i, x in enumerate(xs, 1)\n  print i + x\nend", "P202",
                  "for i in 0 to xs length - 1   and inside it: x = xs[i]   (the number that started from 1 is i + 1)")

    def test_a_sort_key_that_is_not_a_field(self):
        out = self.assertError('words = ["bb", "a"]\nwords.sort(key=len)\nprint words', "P210")
        self.assertIn("sort by takes the name of a field", fix_of(out))

    def test_pop_into_a_variable(self):
        self.hint("xs = [1, 2]\nx = xs.pop()\nprint x", "P210",
                  "two lines: x = xs[xs length - 1]   then   xs remove index xs length - 1")
        self.hint("xs = [1, 2]\nx = xs.pop(0)\nprint x", "P210", "two lines: x = xs[0]   then   xs remove index 0")
        self.assertOutput("xs = [1, 2]\nx = xs[xs length - 1]\nxs remove index xs length - 1\nprint x\nprint xs", ["2", "[1]"])

    def test_pop_alone_is_unchanged(self):
        self.hint("xs = [1, 2]\nxs.pop()\nprint xs", "P210", "xs remove index xs length - 1")

    def test_type_words_written_as_calls(self):
        out = self.assertError("xs = [1, 2]\nys = list(xs)\nprint ys", "P210")
        self.assertIn("list() does not exist in Axion.", out)
        self.hint('s = "4"\nn = number(s)\nprint n', "P210", "a text becomes a number with: s as number")
        self.hint("n = 4\ns = text(n)\nprint s", "P210", "a number becomes text with: n as text")

    def test_range_with_a_step(self):
        self.hint("for i in range(10, 0, -2)\n  print i\nend", "V303",
                  "count with while: i = 10   then   while i > 0   then   ...   then   i = i - 2   then   end")
        self.assertOutput("i = 10\nwhile i > 0\n  print i\n  i = i - 2\nend", ["10", "8", "6", "4", "2"])

    def test_is_none(self):
        out = self.assertError("x = 1\nif x is None\n  print x\nend", "P210")
        self.assertIn("Axion has no null", fix_of(out))

    def test_add_on_a_dictionary_offers_names_that_exist(self):
        self.hint('d = {"a": 1}\nd add "b"\nprint d', "V301", "d[k] = v")

    def test_sort_by_descending_on_numbers(self):
        self.hint("xs = [3, 1]\nprint xs sort by descending", "V309", "print xs sort descending")
        self.assertOutput("xs = [3, 1, 2]\nprint xs sort descending", ["[3, 2, 1]"])

    def test_a_split_of_a_split(self):
        out = self.assertError('s = "a,b;c"\nparts = s split "," split ";"\nprint parts', "V301")
        self.assertTrue(fix_of(out).startswith("split each part in a loop: for part in (s split \",\")"))
        self.assertNotIn("join", fix_of(out))

    def test_split_on_a_list_still_points_at_join(self):
        self.hint('words = ["a", "b"]\nprint words split ", "', "V301", 'print words join ", "')

    def test_a_piece_that_starts_before_the_list(self):
        self.hint("xs = [1, 2, 3]\ni = 0 - 1\nprint xs[i to 1]", "R403", "check first: if i >= 0")
        self.hint("xs = [1, 2, 3]\nj = 5\nprint xs[0 to j]", "R403", "check first: if xs length > j")

    def test_a_built_list_that_does_not_look_at_its_elements(self):
        self.hint("xs = [1, 2]\nzeros = [0 for x in xs]\nprint zeros", "P210",
                  "zeros = [] of number   then   for x in 1 to xs length   then   zeros add 0   then   end")
        self.assertOutput("xs = [1, 2]\nzeros = [] of number\nfor x in 1 to xs length\n  zeros add 0\nend\nprint zeros", ["[0, 0]"])

    def test_swapping_two_elements(self):
        self.hint("a = [3, 1]\ni = 0\na[i], a[i + 1] = a[i + 1], a[i]\nprint a", "P202",
                  "three lines: kept = a[i]   then   a[i] = a[i + 1]   then   a[i + 1] = kept")
        self.assertOutput("a = [3, 1]\ni = 0\nkept = a[i]\na[i] = a[i + 1]\na[i + 1] = kept\nprint a", ["[1, 3]"])

    def test_swapping_two_fields(self):
        self.hint("o = {x: 1, y: 2}\no.x, o.y = o.y, o.x\nprint o", "P202",
                  "three lines: kept = o.x   then   o.x = o.y   then   o.y = kept")


if __name__ == "__main__":
    unittest.main()


class TwoFactsAddedToTheCheatSheet(AxionTest):
    SHEET = (ROOT / "axionlang" / "CHEATSHEET.md").read_text(encoding="utf-8")

    def test_the_words_of_the_language_are_never_names(self):
        line = next(text for text in self.SHEET.split("\n") if "are never names" in text)
        for word in ("length", "value", "index", "text", "number", "list", "to", "end"):
            self.assertIn(f"`{word}`", line)
            self.assertError(f"{word} = 1\nprint {word}", "P214")

    def test_a_number_keeps_28_digits(self):
        self.assertIn("28 digits", self.SHEET)
        self.assertOutput("print 10 ** 27 + 1", ["1000000000000000000000000001"])
        self.assertError("print 10 ** 27 + 1\nprint 2 ** 100", "R412",      # was a rounded number
                         printed_before=["1000000000000000000000000001"])
