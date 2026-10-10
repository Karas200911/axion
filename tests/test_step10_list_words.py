"""Step 10: sort, sum, min, max, join; the loop variable is the element itself.

Decided after the first fresh-task test (tasks 10-14: 2 of 15 solved). All three models
reached for a ready-made sort; phi4 wrote `scores sum` and `words join ", "` letter for
letter; all three wrote `s.total = ...` inside `for s in spent`.

The five words are operations only right after a value. Everywhere else they are ordinary
names, because `sum = 0` is what every model writes.
"""
import unittest

from helpers import AxionTest

from axionlang.engine.lexer import KEYWORDS


def fix_of(out):
    return next((line[5:] for line in out if line.startswith("Fix: ")), None)


PEOPLE = 'ps = [{n: "a", p: 2}, {n: "b", p: 5}, {n: "c", p: 2}, {n: "d", p: 5}]\n'


class Sorting(AxionTest):
    def test_numbers(self):
        self.assertOutput("xs = [3, 1, 2]\nprint xs sort", ["[1, 2, 3]"])

    def test_descending(self):
        self.assertOutput("xs = [3, 1, 2]\nprint xs sort descending", ["[3, 2, 1]"])

    def test_gives_a_new_list(self):
        self.assertOutput("xs = [3, 1, 2]\nys = xs sort\nprint xs\nprint ys", ["[3, 1, 2]", "[1, 2, 3]"])

    def test_sort_in_place_is_an_assignment(self):
        self.assertOutput("xs = [3, 1]\nxs = xs sort\nprint xs", ["[1, 3]"])

    def test_by_field(self):
        self.assertOutput(PEOPLE + "for x in ps sort by p\nprint x.n\nend", ["a", "c", "b", "d"])

    def test_by_field_descending_keeps_equal_elements_in_order(self):
        self.assertOutput(PEOPLE + "for x in ps sort by p descending\nprint x.n\nend",
                          ["b", "d", "a", "c"])

    def test_best_element(self):
        self.assertOutput(PEOPLE + "print (ps sort by p descending)[0].n", ["b"])

    def test_top_three(self):
        # Task 11 of the first fresh test: nobody could write this by hand.
        source = (PEOPLE + "ranked = ps sort by p descending\nfor i in 0 to ranked length - 1\n"
                  "if i < 3\nprint (i + 1) as text + \". \" + ranked[i].n\nend\nend")
        self.assertOutput(source, ["1. b", "2. d", "3. a"])

    def test_elements_are_copies(self):
        source = PEOPLE + "r = ps sort by p\nr[0].p = 99\nprint ps[0].p\nprint r[0].p"
        self.assertOutput(source, ["2", "99"])

    def test_empty_and_decimal_and_negative(self):
        self.assertOutput("xs = [] of number\nprint xs sort", ["[]"])
        self.assertOutput("print [0.5, 0 - 3, 2, 0.25] sort", ["[-3, 0.25, 0.5, 2]"])

    def test_length_after_sort(self):
        self.assertOutput("print [2, 1] sort length", ["2"])

    def test_field_named_like_a_keyword(self):
        self.assertOutput("xs = [{value: 2}, {value: 1}]\nprint xs sort by value", ["[{value: 1}, {value: 2}]"])

    def test_text_is_sorted_by_character_code(self):
        # v0.3: text has an order (until then this was an error: "text has no order in Axion")
        self.assertOutput('print ["b", "a"] sort', ['["a", "b"]'])

    def test_objects_need_by(self):
        out = self.assertError(PEOPLE + "print ps sort", "V301")
        self.assertEqual(fix_of(out), "name a field: ps sort by n")

    def test_by_a_text_field(self):
        # v0.3: a text field sorts too
        self.assertOutput(PEOPLE + "for x in ps sort by n descending\nprint x.n\nend", ["d", "c", "b", "a"])

    def test_by_an_unknown_field(self):
        out = self.assertError(PEOPLE + "print ps sort by pp", "V309")
        self.assertEqual(fix_of(out), "did you mean p?")

    def test_by_on_numbers(self):
        out = self.assertError("xs = [1]\nprint xs sort by p", "V309")
        self.assertEqual(fix_of(out), "print xs sort")       # the whole line since the review of v0.3

    def test_not_a_list(self):
        self.assertError("x = 5\nprint x sort", "V301")

    def test_desc_gets_the_full_word(self):
        out = self.assertError("xs = [1]\nprint xs sort desc", "P202")
        self.assertEqual(fix_of(out), "print xs sort descending")
        self.assertOutput("xs = [1]\n" + fix_of(out), ["[1]"])

    def test_ascending_is_the_default(self):
        out = self.assertError("xs = [1]\nprint xs sort ascending", "P202")
        self.assertEqual(fix_of(out), "print xs sort")

    def test_by_comes_before_descending(self):
        out = self.assertError(PEOPLE + "print ps sort descending by p", "P202")
        self.assertEqual(fix_of(out), "print ps sort by p descending")

    def test_python_forms(self):
        out = self.assertError("xs = [2, 1]\nys = xs.sort()\nprint ys", "P210")
        self.assertEqual(fix_of(out), "ys = xs sort")
        out = self.assertError("xs = [2, 1]\nprint sorted(xs)", "V303")
        self.assertEqual(fix_of(out), "print xs sort")


class SumMinMax(AxionTest):
    def test_values(self):
        self.assertOutput("xs = [3, 1, 2.5]\nprint xs sum\nprint xs min\nprint xs max", ["6.5", "1", "3"])

    def test_sum_of_nothing_is_zero(self):
        self.assertOutput("xs = [] of number\nprint xs sum", ["0"])

    def test_min_and_max_of_nothing_are_runtime_errors(self):
        for word in ("min", "max"):
            out = self.assertError(f'xs = [] of number\nprint "a"\nprint xs {word}', "R409",
                                   printed_before=["a"])
            self.assertIn(f"{word} needs at least one element: xs is empty.", out)
            self.assertEqual(fix_of(out), "check first: if xs length > 0")

    def test_exact_decimals(self):
        self.assertOutput("print [0.1, 0.2] sum == 0.3", ["true"])

    def test_inside_an_expression(self):
        self.assertOutput("xs = [4, 6]\nprint xs sum / xs length", ["5"])
        self.assertOutput('xs = [4, 6]\nprint "max: " + xs max as text', ["max: 6"])

    def test_negative_numbers(self):
        # qwen2.5-coder:14b and phi4, task 14: the largest started at 0, the data was -3.
        self.assertOutput("xs = [0 - 3, 0 - 7]\nprint xs max", ["-3"])

    def test_objects_have_no_sum(self):
        out = self.assertError(PEOPLE + "print ps sum", "V301")
        self.assertIn("for x in ps, total = total + x.p", fix_of(out))

    def test_best_object_goes_through_sort(self):
        out = self.assertError(PEOPLE + "print ps max", "V301")
        self.assertEqual(fix_of(out), "take the first element after sorting: (ps sort by p descending)[0]")
        out = self.assertError(PEOPLE + "print ps min", "V301")
        self.assertEqual(fix_of(out), "take the first element after sorting: (ps sort by p)[0]")

    def test_text_list(self):
        self.assertError('print ["a"] sum', "V301")

    def test_python_forms(self):
        for word in ("sum", "min", "max"):
            out = self.assertError(f"xs = [1]\nprint {word}(xs)", "V303")
            self.assertEqual(fix_of(out), f"print xs {word}")
            out = self.assertError(f"xs = [1]\nprint xs.{word}()", "P210")
            self.assertEqual(fix_of(out), f"print xs {word}")


class Joining(AxionTest):
    def test_join(self):
        self.assertOutput('ws = ["tea", "coffee", "milk"]\nprint ws join ", "', ["tea, coffee, milk"])

    def test_one_and_none(self):
        self.assertOutput('print ["tea"] join ", "', ["tea"])
        self.assertOutput('ws = [] of text\nprint "[" + ws join ", " + "]"', ["[]"])

    def test_separator_is_the_value_right_after(self):
        self.assertOutput('ws = ["a", "b"]\nsep = "+"\nprint ws join sep + "!"', ["a+b!"])
        self.assertOutput('ws = ["a", "b"]\nsep = "+"\nprint ws join (sep + " ")', ["a+ b"])

    def test_length_of_the_result(self):
        self.assertOutput('print ["ab", "c"] join "-" length', ["4"])

    def test_numbers_are_not_joined(self):
        out = self.assertError('xs = [1, 2]\nprint xs join ", "', "V301")
        self.assertIn("join works on a list of text, got list of number.", out)
        self.assertIn("parts add n as text", fix_of(out))
        fixed = ('xs = [1, 2]\nparts = [] of text\nfor n in xs\nparts add n as text\nend\n'
                 'print parts join ", "')
        self.assertOutput(fixed, ["1, 2"])

    def test_separator_must_be_text(self):
        self.assertError('print ["a"] join 1', "V301")

    def test_python_form(self):
        # phi4 wrote words join ", "; the Python habit is ", ".join(words).
        out = self.assertError('ws = ["a", "b"]\nprint ", ".join(ws)', "P210")
        self.assertEqual(fix_of(out), 'print ws join ", "')
        self.assertOutput('ws = ["a", "b"]\n' + fix_of(out), ["a, b"])


class WordsStayNames(AxionTest):
    def test_no_new_keywords(self):
        self.assertEqual(len(KEYWORDS), 33)      # v0.3 added while, continue, exit
        for word in ("sort", "by", "descending", "sum", "min", "max", "join"):
            self.assertNotIn(word, KEYWORDS)

    def test_sum_as_a_variable(self):
        # Every model of the first fresh test wrote sum = 0.
        self.assertOutput("sum = 0\nfor x in [1, 2]\nsum = sum + x\nend\nprint sum", ["3"])

    def test_variable_and_operation_side_by_side(self):
        self.assertOutput("sum = [4, 5] sum\nmin = [4, 5] min\nmax = [4, 5] max\nprint sum + min + max", ["18"])

    def test_all_seven_as_names(self):
        source = ("sort = 1\nby = 2\ndescending = 3\njoin = 4\nmin = 5\nmax = 6\nsum = 7\n"
                  "print sort + by + descending + join + min + max + sum")
        self.assertOutput(source, ["28"])

    def test_field_and_parameter_names(self):
        self.assertOutput("o = {sum: 1, sort: 2}\nprint o.sum + o.sort", ["3"])
        self.assertOutput("function f(max: number) -> number\nreturn max + 1\nend\nprint f(1)", ["2"])

    def test_list_named_sum_can_be_summed(self):
        self.assertOutput("sum = [1, 2]\nprint sum sum", ["3"])


class UnknownWordAfterAValue(AxionTest):
    def test_names_what_exists(self):
        # phi4 got "Only one statement per line" for words join ", " and repeated its answer.
        # (reverse was the example here until v0.3 gave it a hint of its own)
        out = self.assertError("xs = [1]\nprint xs shuffle", "P202")
        self.assertIn("shuffle is not an operation in Axion.", out)
        self.assertIn("length, sort, sum, min, max, join", fix_of(out))

    def test_two_statements_are_still_two_statements(self):
        self.assertError("x = 1\nprint x y = 2", "P201")
        self.assertError("print 1 print 2", "P201")
        self.assertError("x = 1 2", "P201")

    def test_then_and_do(self):
        # llama3.2:3b and phi4 wrote then.
        out = self.assertError("x = 5\nif x > 1 then\nprint x\nend", "P210")
        self.assertEqual(fix_of(out), "if x > 1")
        out = self.assertError("for i in 1 to 2 do\nprint i\nend", "P210")
        self.assertEqual(fix_of(out), "for i in 1 to 2")

    def test_every_prefix_length_in_the_line_is_repaired(self):
        # gemma3:12b, task 13: the Fix repaired one length per attempt.
        source = 'a = "ab"\nb = "c"\nif length a > length b\nprint 1\nend'
        out = self.assertError(source, "P202")
        self.assertEqual(fix_of(out), "if a length > b length")
        self.assertOutput(source.replace("if length a > length b", fix_of(out)), ["1"])


class LoopVariableIsTheElement(AxionTest):
    def test_field_change_reaches_the_list(self):
        source = ('spent = [{c: "food", t: 50}, {c: "fun", t: 20}]\nfor s in spent\n'
                  'if s.c == "food"\ns.t = s.t + 100\nend\nend\nprint spent')
        self.assertOutput(source, ['[{c: "food", t: 150}, {c: "fun", t: 20}]'])

    def test_nested_lists(self):
        source = ("orders = [{items: [{q: 1}, {q: 2}]}]\nfor o in orders\nfor it in o.items\n"
                  "it.q = it.q * 10\nend\nend\nprint orders")
        self.assertOutput(source, ["[{items: [{q: 10}, {q: 20}]}]"])

    def test_adding_to_an_inner_list(self):
        self.assertOutput("rows = [[1], [2]]\nfor row in rows\nrow add 0\nend\nprint rows", ["[[1, 0], [2, 0]]"])

    def test_changing_is_a_use(self):
        # No "loop variable is never used" for a loop that only writes.
        self.assertOutput("xs = [{f: 1}]\nfor x in xs\nx.f = 0\nend\nprint xs", ["[{f: 0}]"])

    def test_copies_elsewhere_stay_copies(self):
        source = "xs = [{f: 1}]\nfor x in xs\ny = x\ny.f = 9\nprint y.f\nend\nprint xs"
        self.assertOutput(source, ["9", "[{f: 1}]"])
        self.assertOutput("xs = [{f: 1}]\nx = xs[0]\nx.f = 9\nprint xs\nprint x", ["[{f: 1}]", "{f: 9}"])

    def test_replacing_the_variable_is_still_an_error(self):
        self.assertError("xs = [1, 2]\nfor x in xs\nx = 0\nend\nprint xs", "V315")

    def test_the_list_itself_still_cannot_change_in_its_loop(self):
        self.assertError("st = [{q: 1}]\nfor s in st\ns.q = 2\nst add {q: 0}\nend", "V316")

    def test_loop_over_a_temporary_list_has_nothing_to_change(self):
        self.assertError("for o in [{a: 1}]\no.a = 2\nend", "V315")

    def test_field_type_is_still_checked(self):
        self.assertError('xs = [{f: 1}]\nfor x in xs\nx.f = "a"\nend\nprint xs', "V309")


if __name__ == "__main__":
    unittest.main()
