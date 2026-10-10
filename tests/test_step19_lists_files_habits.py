"""Axion v0.3, step 5: joining lists, a sort by several fields, exists, and habits.

Decisions 9, 10 and 15 of the v0.3 design (2026-10-05):

    all = a + b                                         two lists joined into a new one
    teams sort by points descending, diff descending    several fields, each with its direction
    if exists "rules/" + name                           the check that comes before read

The second half is about what a model writes out of habit from Python. Nothing here adds
to the language: each habit gets the Axion line as its Fix, in the author's own names,
and (where the test says so) that Fix is run to prove that it is a correct line.

Four hints of v0.2 did harm in test B and are repaired here: `exit` (told to assign to it),
`sort by teams.order`, `then by`, and an `end` after a value chosen with if.
"""
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from helpers import AxionTest, run


def fix_of(out):
    return next((line[5:] for line in out if line.startswith("Fix: ")), None)


TEAMS = ('teams = [{name: "B", points: 3, diff: 1}, {name: "A", points: 3, diff: 5}, '
         '{name: "C", points: 6, diff: 0}, {name: "D", points: 3, diff: 5}]\n')


class JoiningLists(AxionTest):
    def test_two_lists(self):
        self.assertOutput("a = [1, 2]\nb = [3]\nall = a + b\nprint all", ["[1, 2, 3]"])

    def test_the_sources_do_not_change(self):
        self.assertOutput("a = [1, 2]\nb = [3]\nall = a + b\nall add 4\nprint a\nprint b\nprint all",
                          ["[1, 2]", "[3]", "[1, 2, 3, 4]"])

    def test_the_result_is_a_copy_all_the_way_down(self):
        source = ("a = [{n: 1}]\nb = [{n: 2}]\nall = a + b\nall[0].n = 9\nprint a\nprint all")
        self.assertOutput(source, ["[{n: 1}]", "[{n: 9}, {n: 2}]"])

    def test_several_and_text_lists(self):
        self.assertOutput('print ["a"] + ["b", "c"] + ["d", "e"]', ['["a", "b", "c", "d", "e"]'])

    def test_at_the_start(self):
        self.assertOutput("xs = [2, 3]\nxs = [1] + xs\nprint xs", ["[1, 2, 3]"])

    def test_with_pieces(self):
        self.assertOutput("xs = [1, 2, 3, 4]\nprint xs[2 to 3] + xs[0 to 1]", ["[3, 4, 1, 2]"])

    def test_with_an_empty_list(self):
        self.assertOutput("a = [] of number\nb = [1]\nprint a + b\nprint (a + a) length", ["[1]", "0"])

    def test_the_element_types_must_agree(self):
        out = self.assertError('a = [1, 2]\nb = ["x"]\nprint a + b', "V301")
        self.assertIn("Cannot add list of number and list of text.", out)

    def test_one_element_is_still_added_with_add(self):
        out = self.assertError("xs = [1]\nxs = xs + [5]\nprint xs", "V301")
        self.assertIn("+ joins two lists; one element is added with add.", out)
        self.assertEqual(fix_of(out), "xs add 5")

    def test_one_element_into_another_name(self):
        out = self.assertError("xs = [1]\nys = xs + [5]\nprint ys", "V301")
        self.assertEqual(fix_of(out), "two lines: ys = xs   then   ys add 5")

    def test_a_list_plus_a_bare_element(self):
        out = self.assertError("xs = [1]\nprint xs + 5", "V301")
        self.assertEqual(fix_of(out), "use the add statement on its own line: xs add 5")

    def test_the_size_limit_holds(self):
        source = "a = 1 to 6\nb = a + a\nprint b length"
        self.assertOutput(source, ["12"], policy={"max_list_size": 12})
        self.assertError(source, "R406", policy={"max_list_size": 11})


class SortBySeveralFields(AxionTest):
    def test_two_fields_each_with_its_direction(self):
        source = TEAMS + "for t in teams sort by points descending, diff descending\n  print t.name\nend"
        self.assertOutput(source, ["C", "A", "D", "B"])

    def test_three_fields(self):
        source = TEAMS + "for t in teams sort by points descending, diff descending, name descending\n  print t.name\nend"
        self.assertOutput(source, ["C", "D", "A", "B"])

    def test_the_first_field_is_the_main_one(self):
        source = TEAMS + "for t in teams sort by diff, name\n  print t.name\nend"
        self.assertOutput(source, ["C", "B", "A", "D"])

    def test_equal_elements_keep_their_order(self):
        source = TEAMS + "for t in teams sort by points, diff\n  print t.name\nend"
        self.assertOutput(source, ["B", "A", "D", "C"])

    def test_it_is_the_two_passes_of_v02_in_one(self):
        one = TEAMS + "print teams sort by points descending, diff descending"
        two = TEAMS + "print (teams sort by diff descending) sort by points descending"
        self.assertEqual(run(one), run(two))

    def test_the_list_itself_does_not_change(self):
        self.assertOutput(TEAMS + "best = (teams sort by points descending, name)[0]\nprint best.name\nprint teams[0].name",
                          ["C", "B"])

    def test_an_unknown_second_field(self):
        out = self.assertError(TEAMS + "print teams sort by points, nam", "V309")
        self.assertEqual(fix_of(out), "did you mean name?")

    def test_a_field_named_twice(self):
        out = self.assertError(TEAMS + "print teams sort by points, points descending", "V309")
        self.assertIn("sort by names the field points twice; the second one changes nothing.", out)

    def test_inside_brackets_the_comma_is_not_guessed(self):
        out = self.assertError(TEAMS + "function first(xs: list of {name: text, points: number, diff: number}) -> text\n"
                                       "  return xs[0].name\nend\nprint first(teams sort by points, diff)", "P202")
        self.assertIn("After sort by a comma adds the next field; inside these brackets it could "
                      "also separate two items.", out)

    def test_in_parentheses_it_is_a_second_field(self):
        source = TEAMS + ("function first(xs: list of {name: text, points: number, diff: number}) -> text\n"
                          "  return xs[0].name\nend\nprint first((teams sort by points, diff))")
        self.assertOutput(source, ["B"])

    def test_one_field_inside_brackets_is_untouched(self):
        self.assertOutput(TEAMS + "print [teams sort by points descending][0][0].name", ["C"])


class SortHabits(AxionTest):
    """What the three models wrote in test B, and what they were told then."""

    def fixed(self, line, expected):
        out = self.assertError(TEAMS + line, "P202")
        self.assertEqual(fix_of(out), expected)
        code, _ = run(TEAMS + fix_of(out))
        self.assertEqual(code, 0, "the Fix itself is not a correct line")

    def test_then_by(self):
        self.fixed("print teams sort by points descending then by diff descending",
                   "print teams sort by points descending, diff descending")

    def test_the_element_named_in_the_field(self):
        self.fixed("print teams sort by teams.points", "print teams sort by points")
        self.fixed("print teams sort by t.points descending", "print teams sort by points descending")

    def test_a_minus_for_high_to_low(self):
        self.fixed("print teams sort by -points", "print teams sort by points descending")

    def test_every_habit_of_the_line_at_once(self):
        self.fixed("print teams sort by teams.points desc then by teams.name asc",
                   "print teams sort by points descending, name")

    def test_python_sorted_with_a_key(self):
        out = self.assertError(TEAMS + "print sorted(teams, key=lambda t: (-t.points, t.name))", "P210")
        self.assertEqual(fix_of(out), "print teams sort by points descending, name")

    def test_python_sorted_reverse(self):
        out = self.assertError(TEAMS + 'best = sorted(teams, key=lambda t: t["points"], reverse=True)[0]\nprint best', "P210")
        self.assertEqual(fix_of(out), "best = (teams sort by points descending)[0]")
        self.assertOutput(TEAMS + fix_of(out) + "\nprint best.name", ["C"])

    def test_python_sort_method(self):
        out = self.assertError(TEAMS + "teams.sort(key=lambda t: t.points, reverse=True)\nprint teams", "P210")
        self.assertEqual(fix_of(out), "teams = teams sort by points descending")

    def test_python_max_with_a_key(self):
        out = self.assertError(TEAMS + "best = max(teams, key=lambda t: t.points)\nprint best", "P210")
        self.assertEqual(fix_of(out), "best = (teams sort by points descending)[0]")

    def test_plain_sorted_reverse(self):
        out = self.assertError("xs = [3, 1]\nprint sorted(xs, reverse=True)", "P210")
        self.assertEqual(fix_of(out), "print xs sort descending")


class Exists(AxionTest):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / "rules").mkdir()
        (self.dir / "rules" / "a.txt").write_text("hello", encoding="utf-8")
        (self.dir / "rules" / "inner").mkdir()
        (self.dir / "secret.txt").write_text("no", encoding="utf-8")
        self.launch = {"policy": {"allow_read": ["rules/"]}, "base_dir": self.dir}

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_a_file_that_is_there(self):
        self.assertOutput('allow read "rules/"\nprint exists "rules/a.txt"', ["true"], **self.launch)

    def test_a_file_that_is_not(self):
        self.assertOutput('allow read "rules/"\nprint exists "rules/b.txt"', ["false"], **self.launch)

    def test_check_first_then_read(self):
        source = ('allow read "rules/"\ninput name: text\npath = "rules/" + name\n'
                  'if exists path\n  print read path\nelse\n  print "no file " + name\nend')
        self.assertOutput(source, ["hello"], data='{"name": "a.txt"}', **self.launch)
        self.assertOutput(source, ["no file zzz.txt"], data='{"name": "zzz.txt"}', **self.launch)

    def test_it_takes_the_whole_expression_as_the_path(self):
        source = 'allow read "rules/"\ninput name: text\nprint exists "rules/" + name\nprint not exists "rules/" + name'
        self.assertOutput(source, ["true", "false"], data='{"name": "a.txt"}', **self.launch)

    def test_a_folder_is_not_a_file(self):
        source = 'allow read "rules/"\ninput name: text\nprint exists "rules/" + name'
        self.assertOutput(source, ["false"], data='{"name": "inner"}', **self.launch)

    def test_it_needs_the_same_permission_as_read(self):
        out = self.assertError('print exists "rules/a.txt"', "S501", base_dir=self.dir)
        self.assertEqual(fix_of(out), 'add at the top: allow read "rules/"')

    def test_the_launch_must_allow_the_folder(self):
        self.assertError('allow read "rules/"\nprint exists "rules/a.txt"', "S502", base_dir=self.dir)

    def test_it_counts_as_using_the_permission(self):
        self.assertOutput('allow read "rules/"\nif exists "rules/a.txt"\n  print "ok"\nend', ["ok"], **self.launch)

    def test_outside_the_declared_folder(self):
        self.assertError('allow read "rules/"\nprint exists "secret.txt"', "S503", **self.launch)
        self.assertError('allow read "rules/"\nprint exists "rules/../secret.txt"', "S503", **self.launch)

    def test_a_computed_path_cannot_leave_either(self):
        source = 'allow read "rules/"\ninput name: text\nprint exists "rules/" + name'
        self.assertError(source, "S503", data='{"name": "../secret.txt"}', **self.launch)

    def test_a_folder_written_as_the_path(self):
        out = self.assertError('allow read "rules/"\nprint exists "rules/"', "V326", **self.launch)
        self.assertIn('exists checks a file; "rules/" is a folder.', out)

    def test_with_and_it_needs_parentheses(self):
        out = self.assertError('allow read "rules/"\nok = true\nprint exists "rules/a.txt" and ok', "V301", **self.launch)
        self.assertEqual(fix_of(out), 'print (exists "rules/a.txt") and ok')
        self.assertOutput('allow read "rules/"\nok = true\n' + fix_of(out), ["true"], **self.launch)

    def test_written_as_a_call(self):
        out = self.assertErrors('allow read "rules/"\nprint exists("rules/a.txt")', ["V303"], **self.launch)
        self.assertIn("exists is written without brackets, like read.", out)
        self.assertEqual(fix_of(out), 'print (exists "rules/a.txt")')

    def test_exists_stays_an_ordinary_name(self):
        self.assertOutput("exists = false\nfor x in [1, 2]\n  if x == 2\n    exists = true\n  end\nend\nprint exists", ["true"])
        self.assertOutput("exists = 3\nprint exists + 1", ["4"])

    def test_a_function_may_be_called_exists(self):
        source = "function exists(xs: list of number, v: number) -> bool\n  return xs contains v\nend\nprint exists([1, 2], 2)"
        self.assertOutput(source, ["true"])

    def test_nothing_is_read(self):
        # exists answers yes or no; the text of the file never enters the program
        self.assertOutput('allow read "rules/"\nfound = exists "rules/a.txt"\nprint found', ["true"], **self.launch)


class RemoveValueHint(AxionTest):
    def test_the_fix_is_the_check(self):
        out = self.assertError("xs = [1, 2]\nxs remove value 5\nprint xs", "R405")
        self.assertEqual(fix_of(out), "check first: if xs contains 5")


class Habit(AxionTest):
    def habit(self, source, code, expected_fix, message=None):
        out = self.assertError(source, code)
        self.assertEqual(fix_of(out), expected_fix)
        if message:
            self.assertIn(message, out)
        return out

    def runs(self, source, expected):
        self.assertOutput(source, expected)


class ChangingAVariable(Habit):
    def test_plus_equals(self):
        self.habit("x = 5\nx += 2\nprint x", "P210", "x = x + 2",
                   "+= is not Axion syntax: the variable is written on both sides.")

    def test_the_other_operators(self):
        self.habit("x = 5\nx -= 1 + 1\nprint x", "P210", "x = x - (1 + 1)")
        self.habit("x = 5\nx *= 2\nprint x", "P210", "x = x * 2")
        self.habit("x = 5\nx //= 2\nprint x", "P210", "x = x // 2")
        self.habit("x = 5\nx **= 2\nprint x", "P210", "x = x ** 2")

    def test_a_field_and_an_element(self):
        self.habit('d = {"a": 1}\nd["a"] += 1\nprint d', "P210", 'd["a"] = d["a"] + 1')
        self.habit("o = {n: 1}\no.n += 1\nprint o", "P210", "o.n = o.n + 1")

    def test_one_element_onto_a_list(self):
        self.habit("xs = [1]\nxs += [2]\nprint xs", "P210", "xs add 2")

    def test_two_lists(self):
        self.habit("xs = [1]\nys = [2, 3]\nxs += ys\nprint xs", "P210", "xs = xs + ys")
        self.runs("xs = [1]\nys = [2, 3]\nxs = xs + ys\nprint xs", ["[1, 2, 3]"])

    def test_plus_plus(self):
        self.habit("x = 5\nx++\nprint x", "P210", "x = x + 1")
        self.habit("x = 5\nx--\nprint x", "P210", "x = x - 1")

    def test_every_such_line_is_named(self):
        out = self.assertError("i = 0\nn = 0\nwhile i < 3\n  i += 1\n  n += i\nend\nprint n", "P210")
        self.assertEqual(fix_of(out), "i = i + 1   (the same on every line)")
        self.assertIn("The same mistake is on line 5: fix it too.", out)

    def test_two_names_in_one_line(self):
        self.habit("a = 1\nb = 2\na, b = 5, 6\nprint a + b", "P202", "two lines: a = 5   then   b = 6",
                   "A line sets one variable.")

    def test_a_swap_keeps_the_old_value(self):
        self.habit("a = 1\nb = 2\na, b = b, a\nprint a + b", "P202",
                   "three lines: old_a = a   then   a = b   then   b = old_a")

    def test_the_step_of_euclid(self):
        self.habit("a = 84\nb = 36\nwhile b != 0\n  a, b = b, a % b\nend\nprint a", "P202",
                   "three lines: old_a = a   then   a = b   then   b = old_a % b")
        self.runs("a = 84\nb = 36\nwhile b != 0\n  old_a = a\n  a = b\n  b = old_a % b\nend\nprint a", ["12"])


class Blocks(Habit):
    def test_a_colon_at_the_end(self):
        out = self.habit("x = 3\nif x > 2:\n  print x\nelse:\n  print 0\nend", "P210",
                         "if x > 2   (the same on every line)",
                         "A line does not end with : in Axion; the block is closed with end.")
        self.assertIn("The same mistake is on line 4: fix it too.", out)

    def test_a_colon_after_while_and_for(self):
        self.habit("i = 0\nwhile i < 3:\n  i = i + 1\nend\nprint i", "P210", "while i < 3")
        self.habit("for i in 1 to 3:\n  print i\nend", "P210", "for i in 1 to 3")

    def test_an_end_after_a_value_if_on_its_line(self):
        self.habit("c = true\nx = if c then 1 else 2 end\nprint x", "P210", "x = if c then 1 else 2",
                   "A value chosen with if has no end: its line is the whole of it.")

    def test_an_end_after_a_value_if_on_the_next_line(self):
        self.habit("c = true\nx = if c then 1 else 2\nend\nprint x", "P212", "delete this end")

    def test_an_ordinary_extra_end_is_unchanged(self):
        out = self.assertError("x = 1\nprint x\nend", "P212")
        self.assertIn("end without an open block: there is one end too many at or above this line.", out)

    def test_the_choice_of_python(self):
        self.habit("c = true\nx = 1 if c else 2\nprint x", "P210", "x = if c then 1 else 2",
                   "A value chosen with if starts with if: if condition then a else b.")
        self.habit('x = 3\nprint "big" if x > 2 else "small"', "P210", 'print if x > 2 then "big" else "small"')
        self.runs('x = 3\nprint if x > 2 then "big" else "small"', ["big"])

    def test_statement_words_axiom_does_not_have(self):
        self.habit("import math\nprint 1", "P210", "delete this line: everything Axion has is always there",
                   "Axion has no import.")
        self.habit("from collections import Counter\nprint 1", "P210",
                   "delete this line: everything Axion has is always there")
        out = self.assertError("x = 4\ntry:\n  print x\nexcept ValueError:\n  print 0\nend", "P210")
        self.assertIn("Axion has no try: an error is prevented, not caught.", out)
        self.assertIn("check before the action", fix_of(out))
        self.habit('raise ValueError("bad input")', "P210", 'two lines: print "bad input"   then   exit')
        out = self.assertError("class Team:\n  x = 1\nend", "P210")
        self.assertIn("Axion has no classes.", out)

    def test_those_words_stay_ordinary_names(self):
        self.runs('match = 3\nwith = 1\nclass = "a"\nprint match + with\nprint class', ["4", "a"])

    def test_an_unknown_first_word(self):
        out = self.assertError("goto 5", "P202")
        self.assertIn("goto is not a statement of Axion.", out)
        self.assertIn("print, if, for, while, function, return, break, continue or exit", fix_of(out))

    def test_a_lone_value_keeps_its_old_hint(self):
        self.habit("total = 1\ntotal", "P202", "assign with total = value, or print with print total")

    def test_ways_to_leave_from_other_languages(self):
        self.habit("quit()", "V303", "exit")
        self.habit("x = 1\nif x > 0\n  sys.exit(1)\nend\nprint x", "P210", "exit")

    def test_input_as_a_call(self):
        self.habit("x = input()\nprint x", "P210",
                   "delete this line and write at the top of the program: input x: text")


class Loops(Habit):
    def test_enumerate(self):
        self.habit("xs = [1, 2]\nfor i, x in enumerate(xs)\n  print i + x\nend", "P202",
                   "for i in 0 to xs length - 1   and inside it: x = xs[i]", "for has one variable.")
        self.runs("xs = [1, 2]\nfor i in 0 to xs length - 1\n  x = xs[i]\n  print i + x\nend", ["1", "3"])

    def test_zip(self):
        self.habit("xs = [1, 2]\nys = [3, 4]\nfor a, b in zip(xs, ys):\n  print a + b\nend", "P202",
                   "for i in 0 to xs length - 1   and inside it: a = xs[i]   then   b = ys[i]")

    def test_items(self):
        self.habit('d = {"a": 1}\nfor k, v in d.items()\n  print k\nend', "P202",
                   "for k in d keys   and inside it: v = d[k]")

    def test_range_with_two_ends(self):
        self.habit("for i in range(1, 4)\n  print i\nend", "V303", "for i in 1 to 4 - 1")
        self.runs("for i in 1 to 4 - 1\n  print i\nend", ["1", "2", "3"])

    def test_a_list_built_inside_brackets(self):
        self.habit("xs = [1, 2]\nys = [x * 2 for x in xs]\nprint ys", "P210",
                   "ys = [] of number   then   for x in xs   then   ys add x * 2   then   end",
                   "A list is built with a loop in Axion, not inside [ ].")
        self.runs("xs = [1, 2]\nys = [] of number\nfor x in xs\n  ys add x * 2\nend\nprint ys", ["[2, 4]"])

    def test_with_a_condition(self):
        self.habit("xs = [1, 2]\nys = [x for x in xs if x > 1]\nprint ys", "P210",
                   "ys = [] of number   then   for x in xs   then   if x > 1   then   ys add x"
                   "   then   end   then   end")

    def test_the_element_type_is_the_real_one(self):
        out = self.assertError('ps = [{name: "A", age: 3}]\nnames = [p.name for p in ps]\nprint names', "P210")
        self.assertTrue(fix_of(out).startswith("names = [] of text   then   for p in ps"))
        out = self.assertError('ps = [{name: "A", age: 3}]\nold = [p for p in ps if p.age > 2]\nprint old', "P210")
        self.assertTrue(fix_of(out).startswith("old = [] of {name: text, age: number}   then"))

    def test_inside_a_longer_line(self):
        out = self.assertError("xs = [{n: 1}]\nprint [x.n for x in xs] length", "P210")
        self.assertTrue(fix_of(out).endswith("then use items in place of the brackets"))

    def test_a_sum_over_a_loop(self):
        self.habit("xs = [1, 2]\nprint sum(x * 2 for x in xs)", "P210",
                   "total = 0   then   for x in xs   then   total = total + x * 2   then   end"
                   "   then use total in place of sum(...)",
                   "The loop is written out in Axion, not inside the brackets of sum().")

    def test_any_and_all(self):
        self.habit("xs = [1, 2]\nbig = any(x > 1 for x in xs)\nprint big", "P210",
                   "big = false   then   for x in xs   then   if x > 1   then   big = true   then   break"
                   "   then   end   then   end")
        self.habit("xs = [1, 2]\nfine = all(x > 0 for x in xs)\nprint fine", "P210",
                   "fine = true   then   for x in xs   then   if not (x > 0)   then   fine = false"
                   "   then   break   then   end   then   end")
        self.runs("xs = [1, 2]\nbig = false\nfor x in xs\n  if x > 1\n    big = true\n    break\n  end\nend\nprint big",
                  ["true"])

    def test_counting_with_len(self):
        out = self.assertError("xs = [1, 2]\nprint len([x for x in xs if x > 1])", "P210")
        self.assertTrue(fix_of(out).startswith("count = 0   then   for x in xs   then   if x > 1   then   count = count + 1"))

    def test_no_reverse(self):
        fix = "walk the positions from the end: for i in 0 to xs length - 1   and inside it the element is xs[xs length - 1 - i]"
        self.habit("xs = [1, 2]\nprint xs reverse", "P202", fix, "Axion has no reverse.")
        self.habit("xs = [1, 2]\nprint reversed(xs)", "V303", fix)
        self.habit("xs = [1, 2]\nprint xs[::-1]", "P202", fix)
        self.habit("xs = [1, 2]\nxs.reverse()\nprint xs", "P210", fix)
        self.runs("xs = [1, 2, 3]\nback = [] of number\nfor i in 0 to xs length - 1\n  back add xs[xs length - 1 - i]\nend\nprint back",
                  ["[3, 2, 1]"])

    def test_repeating_text(self):
        self.habit('n = 3\nprint "-" * n', "V301",
                   'repeat it in a loop: line = ""   then   for i in 1 to n   then   line = line + "-"   then   end',
                   "Text cannot be multiplied in Axion.")


class Text(Habit):
    def test_a_format_string(self):
        self.habit('x = 4\nname = "a"\nok = true\nprint f"Total: {x} for {name}, {ok}"', "P210",
                   'print "Total: " + x as text + " for " + name + ", " + ok as text',
                   'Axion has no f"...": text is joined with +, and a number becomes text with as text.')
        self.runs('x = 4\nname = "a"\nok = true\nprint "Total: " + x as text + " for " + name + ", " + ok as text',
                  ["Total: 4 for a, true"])

    def test_places_after_the_point(self):
        self.habit('x = 4\nprint f"{x * 2:.2f} and {x / 3:.1f}"', "P210",
                   'print ((x * 2) round 2) as text + " and " + ((x / 3) round 1) as text')
        self.runs('x = 4\nprint ((x * 2) round 2) as text + " and " + ((x / 3) round 1) as text', ["8 and 1.3"])

    def test_a_calculation_inside(self):
        self.habit('a = 1\nb = 2\nprint f"sum: {a + b}"', "P210", 'print "sum: " + (a + b) as text')

    def test_a_field_and_an_element(self):
        self.habit('p = {name: "A", ages: [3]}\nprint f"{p.name} is {p.ages[0]}"', "P210",
                   'print p.name + " is " + p.ages[0] as text')

    def test_only_a_value(self):
        self.habit('x = 4\nprint f"{x}"', "P210", "print x as text")

    def test_an_unknown_name_inside_is_the_real_error(self):
        out = self.assertError('print f"Total: {totl}"', "V303")
        self.assertIn("Unknown variable totl.", out)

    def test_what_cannot_be_rewritten_exactly(self):
        self.habit('xs = [1]\nprint f"{xs}"', "P210", 'for example: "Total: " + total as text + " items"')
        self.habit('x = 4\nprint f"{x:>10}"', "P210", 'for example: "Total: " + total as text + " items"')

    def test_f_stays_an_ordinary_name(self):
        self.runs('f = 2\nprint f * 3\ng = "a"\nprint g + "b"', ["6", "ab"])

    def test_a_method_then_an_element(self):
        self.habit('s = "a,b"\nprint s.split(",")[0]', "P210", 'print (s split ",")[0]')
        self.runs('s = "a,b"\nprint (s split ",")[0]', ["a"])


class Calls(Habit):
    def test_a_default_value(self):
        self.habit("function f(a: number, b: number = 2) -> number\n  return a + b\nend\nprint f(1, 2)", "P202",
                   "function f(a: number, b: number) -> number",
                   "A parameter has no default value: every call passes every value.")

    def test_a_named_argument(self):
        self.habit("function f(a: number, b: number) -> number\n  return a + b\nend\nprint f(1, b=2)", "P202",
                   "print f(1, 2)",
                   "Arguments have no names in Axion: the values go in the order of the parameters.")

    def test_print_without_a_value(self):
        self.habit("print()", "P202", 'print ""   (an empty line)')
        self.runs('print ""', [""])

    def test_print_that_does_not_end_the_line(self):
        self.habit('x = 1\nprint(x, end="")', "P202", "build the whole line first with +, then print it once")

    def test_insert_and_extend(self):
        self.habit("xs = [1]\nxs.insert(0, 5)\nprint xs", "P210", "xs = [5] + xs")
        self.habit("xs = [1]\nxs.extend([7, 8])\nprint xs", "P210", "xs = xs + [7, 8]")
        self.runs("xs = [1]\nxs = [5] + xs\nxs = xs + [7, 8]\nprint xs", ["[5, 1, 7, 8]"])


if __name__ == "__main__":
    unittest.main()


class CheatSheetIsTrue(AxionTest):
    """Every statement of the v0.3 cheat sheet that can be run is run here: the sheet is the
    only description of the language a model sees, so nothing in it may be wrong."""

    SHEET = (Path(__file__).resolve().parent.parent / "axionlang" / "CHEATSHEET.md").read_text(encoding="utf-8")

    def test_it_is_the_v03_sheet_and_names_every_new_thing(self):
        self.assertTrue(self.SHEET.startswith("# Axion v0.3"))
        for word in ("split", "trim", "lower", "upper", "contains", "starts with", "ends with",
                     "map of", "keys", "remove key", "round", "floor", "ceiling", "**",
                     "is date", "as days", "as date", "while", "continue", "exit", "exists",
                     "sort by age descending, name"):
            self.assertIn(word, self.SHEET)

    def test_what_v02_said_and_is_no_longer_true_is_gone(self):
        for old in ("the only loop", "No while", "No recursion", "No dictionaries", "lists have no `+`"):
            self.assertNotIn(old, self.SHEET)

    def test_the_chain_and_its_parentheses(self):
        self.assertOutput('s = " A,b "\nprint s trim lower split ","', ['["a", "b"]'])
        self.assertOutput("a = 1\nb = 2\nprint (a + b) as text", ["3"])
        self.assertOutput("total = 10\nn = 3\nprint (total / n) round 2", ["3.33"])
        self.assertOutput('s = "a,b"\nprint (s split ",")[0]', ["a"])
        self.assertOutput('keys = ["1", "2"]\nn = 2\nprint keys contains (n as text)', ["true"])

    def test_numbers(self):
        self.assertOutput("print 2.5 round 0\nprint 2.5 floor\nprint 2.1 ceiling", ["3", "2", "3"])
        self.assertOutput('print 2 ** 3\nprint 9 ** 0.5\nprint 7 // 2\nprint 7 % 2\nprint "a" < "b"\nprint [1] + [2, 3]',
                          ["8", "3", "3", "1", "true", "[1, 2, 3]"])

    def test_text(self):
        source = ('s = "banana"\nprint (s split "a") join "o"\nprint s[0]\nprint s[1 to 3]\nprint s starts with "ba"\n'
                  'print s ends with "na"\nprint s contains "nan"\nprint s upper')
        self.assertOutput(source, ["bonono", "b", "ana", "true", "true", "true", "BANANA"])

    def test_dates_and_the_weekday_line(self):
        source = ('s = "2026-10-05"\nprint s is date\nprint (s as days + 3) % 7\nprint (s as days + 30) as date\n'
                  'print "2026-10-07" as days - s as days')
        self.assertOutput(source, ["true", "0", "2026-11-04", "2"])       # 5 October 2026 is a Monday
        import datetime
        for text in ("1970-01-01", "1999-12-31", "2024-02-29", "2026-10-11"):
            expected = datetime.date.fromisoformat(text).weekday()        # 0 is Monday there too
            self.assertOutput(f'print ("{text}" as days + 3) % 7', [str(expected)])

    def test_lists(self):
        source = ("xs = [3, 1, 2]\nprint xs sum\nprint xs min\nprint xs max\nprint xs contains 2\nprint xs[0 to 1]\n"
                  "print xs sort\nprint xs sort descending")
        self.assertOutput(source, ["6", "1", "3", "true", "[3, 1]", "[1, 2, 3]", "[3, 2, 1]"])
        source = ('people = [{name: "B", age: 3}, {name: "A", age: 3}, {name: "C", age: 9}]\n'
                  "for p in people sort by age descending, name\n  print p.name\nend")
        self.assertOutput(source, ["C", "A", "B"])

    def test_the_counting_example(self):
        block = re.search(r"```\n(counts = .*?)```", self.SHEET, re.S).group(1)
        self.assertOutput('words = ["a", "b", "a"]\n' + block, ["a: 2", "b: 1"])

    def test_the_dictionary_line(self):
        self.assertOutput('d = {"tea": 2}\nn = 5\nd[n as text] = 1\nd remove key "tea"\nprint d\nprint d length',
                          ['{"5": 1}', "1"])

    def test_loops_and_exit(self):
        source = ('for ch in "ab"\n  print ch\nend\nn = 3\nwhile n > 0\n  n = n - 1\n  if n == 1\n    continue\n  end\n'
                  "  print n\nend\nexit")
        self.assertOutput(source, ["a", "b", "2", "0"])

    def test_the_last_example(self):
        block = re.search(r"## Example\n```\n(.*?)```", self.SHEET, re.S).group(1)
        self.assertOutput(block, ["Total: 450"],
                          data='{"items": [{"name": "a", "price": 150}, {"name": "b", "price": 50}, {"name": "c", "price": 300}]}')
