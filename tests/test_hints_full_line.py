"""Hints found by test 1 on local models (qwen, llama, gemma, phi4).

Rule: a Fix shows the whole corrected line in the author's own names, and one cause
that spoils many lines is reported once, and the error names the other lines.
Each test also applies the Fix and checks that the corrected program really runs.
"""
import unittest

from helpers import AxionTest, run


def fix_of(out):
    return next(line[5:] for line in out if line.startswith("Fix: "))


class Indentation(AxionTest):
    """Leading spaces have no meaning (decided after the applied-task run: phi4, gemma3:12b
    and qwen2.5-coder:14b all indent nested code; the ban cost whole attempts)."""

    def test_valid_form(self):
        self.assertOutput("x = 1\nif x > 0\nprint x\nend", ["1"])

    def test_indented_program_runs_the_same(self):
        source = "x = 1\nif x > 0\n    print x\nelse\n    print 0\nend"
        self.assertOutput(source, ["1"])

    def test_nested_indentation(self):
        source = "xs = [1]\nfor x in xs\n  if x > 0\n    print x\n  end\nend"
        self.assertOutput(source, ["1"])

    def test_single_indented_line(self):
        self.assertOutput("x = 1\n  print x", ["1"])

    def test_blank_lines_with_spaces(self):
        self.assertOutput("x = 1\n   \n  print x\n\t\nprint x", ["1", "1"])

    def test_tabs(self):
        self.assertOutput("x = 1\n\tprint x\n\tprint x", ["1", "1"])

    def test_indentation_never_makes_a_block(self):
        # Only end closes a block: a dedent does not, and Axion says so on that very line.
        out = self.assertError("x = 1\nif x > 0\n    print x\nprint 2", "P216")
        self.assertEqual(out[0], "ERROR P216 line 4:1")
        # Without indentation there is nothing to compare: the block is simply never closed.
        self.assertError("x = 1\nif x > 0\nprint x\nprint 2", "P212")

    def test_error_position_counts_the_leading_spaces(self):
        out = self.assertError("x = 1\n    print y", "V303")
        self.assertEqual(out[:3], ["ERROR V303 line 2:11", "    print y", "          ^"])

    def test_fix_line_is_written_without_indentation(self):
        out = self.assertError("xs = [1]\nfor x in xs\n    print length xs\nend", "P202")
        self.assertEqual(fix_of(out), "print xs length")


class WholeLineFixes(AxionTest):
    def check(self, before, bad, code, fix, after="", expected=None):
        """bad fails with `code`; its Fix is `fix`; the program with the Fix applied runs."""
        out = self.assertError(before + bad + after, code)
        self.assertEqual(fix_of(out), fix)
        if expected is not None:
            self.assertOutput(before + fix + after, expected)

    def test_length_as_field(self):
        self.check("total = 10\nscores = [1, 2]\n", "avg = total / scores.length", "V309",
                   "avg = total / scores length", "\nprint avg", ["5"])

    def test_length_as_field_in_range(self):
        self.check("raw = [\"a\", \"b\"]\n", "for i in 0 to raw.length - 1", "V309",
                   "for i in 0 to raw length - 1", "\nprint raw[i]\nend", ["a", "b"])

    def test_length_as_field_on_text(self):
        self.check("s = \"abc\"\n", "print s.length", "V309", "print s length", "", ["3"])

    def test_len_call(self):
        self.check("total = 10\nscores = [1, 2]\n", "avg = total / len(scores)", "V303",
                   "avg = total / scores length", "\nprint avg", ["5"])

    def test_str_call_with_expression_keeps_parentheses(self):
        self.check("n = 1\n", "print \"N: \" + str(n + 1)", "V303",
                   "print \"N: \" + (n + 1) as text", "", ["N: 2"])

    def test_range_call(self):
        self.check("n = 2\n", "for i in range(n)", "V303",
                   "for i in 0 to n - 1", "\nprint i\nend", ["0", "1"])

    def test_method_add_uses_own_names(self):
        self.check("user = {name: \"A\"}\nqualified = [] of text\n", "qualified.add(user.name)",
                   "P210", "qualified add user.name", "\nprint qualified", ["[\"A\"]"])

    def test_method_append_and_push(self):
        for method in ("append", "push"):
            self.check("xs = [1]\n", f"xs.{method}(2 * (3 + 1))", "P210",
                       "xs add 2 * (3 + 1)", "\nprint xs", ["[1, 8]"])

    def test_method_with_text_argument_containing_parenthesis(self):
        self.check("xs = [\"a\"]\n", "xs.append(\")\")", "P210",
                   "xs add \")\"", "\nprint xs", ["[\"a\", \")\"]"])

    def test_method_remove_and_pop(self):
        self.check("xs = [1, 2]\n", "xs.remove(2)", "P210",
                   "xs remove value 2", "\nprint xs", ["[1]"])
        self.check("xs = [1, 2]\n", "xs.pop(0)", "P210",
                   "xs remove index 0", "\nprint xs", ["[2]"])
        self.check("xs = [1, 2]\n", "xs.pop()", "P210",
                   "xs remove index xs length - 1", "\nprint xs", ["[1]"])

    def test_method_length_call(self):
        self.check("xs = [1, 2]\n", "print xs.size()", "P210", "print xs length", "", ["2"])

    def test_method_inside_expression_points_to_a_statement(self):
        out = self.assertError("xs = [1]\nys = xs.append(2)", "P210")
        self.assertEqual(fix_of(out), "use a statement on its own line: xs add 2")

    def test_unknown_method_keeps_generic_hint(self):
        # (reverse was the example here until v0.3 gave it a hint of its own)
        out = self.assertError("xs = [1]\nxs.shuffle()", "P210")
        self.assertEqual(fix_of(out), "use the matching statement or operator")

    def test_empty_list_shows_the_line(self):
        self.check("", "result = []", "P213",
                   "result = [] of text   (or [] of number, [] of bool, [] of {name: text})")
        self.assertOutput("result = [] of text\nprint result", ["[]"])

    def test_elif_shows_the_line_and_lists_the_others(self):
        source = "x = 1\nif x > 5\nprint 5\nelif x > 3\nprint 3\nelif x > 0\nprint 1\nend"
        out = self.assertError(source, "P210")
        self.assertEqual(fix_of(out), "else if x > 3")
        self.assertIn("The same mistake is on line 6: fix it too.", out)
        self.assertOutput(source.replace("elif", "else if"), ["1"])

    def test_walrus_assignment(self):
        source = "total := 0\ntotal := total + 1\nprint total"
        out = self.assertError(source, "P210")
        self.assertEqual(out[0], "ERROR P210 line 1:7")
        self.assertIn(":= is not Axion syntax; assignment is =.", out)
        self.assertEqual(fix_of(out), "total = 0   (the same on every line)")
        self.assertIn("The same mistake is on line 2: fix it too.", out)
        self.assertOutput(source.replace(":=", "="), ["1"])

    def test_single_walrus_has_plain_fix(self):
        out = self.assertError("total := 0\nprint total", "P210")
        self.assertEqual(fix_of(out), "total = 0")

    def test_input_type_colon_is_not_a_walrus(self):
        self.assertOutput("input n: number\nprint n", ["3"], data='{"n": 3}')

    def test_prefix_is_number(self):
        self.check("item = \"5\"\n", "if is number item", "P202",
                   "if item is number", "\nprint item\nend", ["5"])

    def test_prefix_is_number_with_complex_value(self):
        out = self.assertError("raw = [\"5\"]\nif is number raw[0]\nprint 1\nend", "P202")
        self.assertEqual(fix_of(out), "write the value first: s is number")

    def test_prefix_length(self):
        self.check("total = 10\nscores = [1, 2]\n", "avg = total / length scores", "P202",
                   "avg = total / scores length", "\nprint avg", ["5"])

    def test_prefix_length_call(self):
        self.check("scores = [1, 2]\n", "print length(scores)", "P202",
                   "print scores length", "", ["2"])

    def test_unary_minus_after_operator_shows_the_line(self):
        self.check("pos = 3\n", "if pos == -1", "P207", "if pos == (-1)",
                   "\nprint 0\nelse\nprint pos\nend", ["3"])


class ReadOfFolder(AxionTest):
    """read "notes/" + name reads the folder: found while writing the applied tasks."""
    POLICY = {"allow_read": ["notes/"]}

    def setUp(self):
        import tempfile
        from pathlib import Path
        self.tmp = tempfile.TemporaryDirectory()
        (Path(self.tmp.name) / "notes").mkdir()
        (Path(self.tmp.name) / "notes" / "a.txt").write_text("hello", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def launch(self):
        return {"policy": self.POLICY, "base_dir": self.tmp.name}

    def test_valid_form(self):
        source = 'allow read "notes/"\nn = "a.txt"\nt = read "notes/" + n\nprint t'
        self.assertOutput(source, ["hello"], **self.launch())

    def test_parentheses_are_still_fine(self):
        source = 'allow read "notes/"\nn = "a.txt"\nt = read ("notes/" + n)\nprint t'
        self.assertOutput(source, ["hello"], **self.launch())

    def test_read_takes_the_whole_expression(self):
        # Written by qwen2.5-coder:14b and gemma3:12b in task 8.
        source = 'allow read "notes/"\nn = "a"\nprint read "notes/" + n + ".txt"'
        self.assertOutput(source, ["hello"], **self.launch())

    def test_read_inside_a_longer_line(self):
        source = 'allow read "notes/"\nprint "[" + (read "notes/a.txt") + "]"'
        self.assertOutput(source, ["[hello]"], **self.launch())

    def test_length_of_a_file_needs_parentheses(self):
        source = 'allow read "notes/"\nprint read "notes/a.txt" length'
        out = self.assertError(source, "V301", **self.launch())
        self.assertEqual(fix_of(out), 'print (read "notes/a.txt") length')
        self.assertOutput('allow read "notes/"\n' + fix_of(out), ["5"], **self.launch())

    def test_comparing_a_file_needs_parentheses(self):
        source = 'allow read "notes/"\nif read "notes/a.txt" == "hello"\nprint 1\nend'
        out = self.assertError(source, "V301", **self.launch())
        self.assertEqual(fix_of(out), 'if (read "notes/a.txt") == "hello"')
        self.assertOutput(source.replace('if read "notes/a.txt" == "hello"', fix_of(out)), ["1"],
                          **self.launch())

    def test_file_as_number_needs_parentheses(self):
        source = 'allow read "notes/"\np = "notes/a.txt"\nprint read p as number'
        out = self.assertError(source, "V301", **self.launch())
        self.assertEqual(fix_of(out), "print (read p) as number")

    def test_literal_path_as_number_needs_parentheses(self):
        # Without this the error was V314 ("notes/a.txt" is not a number): true but misleading.
        source = 'allow read "notes/"\nrate = read "notes/a.txt" as number\nprint rate'
        out = self.assertError(source, "V301", **self.launch())
        self.assertEqual(fix_of(out), 'rate = (read "notes/a.txt") as number')

    def test_read_folder_alone(self):
        out = self.assertError('allow read "notes/"\nprint read "notes/"', "V326", **self.launch())
        self.assertEqual(fix_of(out), 'name a file inside it: read "notes/file.txt"')

    def test_nothing_is_read_before_the_error(self):
        source = 'allow read "notes/"\nprint "start"\nprint read "notes/"'
        self.assertError(source, "V326", **self.launch())


if __name__ == "__main__":
    unittest.main()
