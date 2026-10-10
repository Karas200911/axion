"""Step 11: indentation is optional, but it must not contradict end.

Decided after the first fresh-task test: gemma3:12b indents its code and closes blocks the
Python way (by dedenting), so it loses an end; Axion noticed that only at the end of the
program, thirty lines away. Earlier phi4 (task 5) lost one end and had one extra: the
program passed every check and meant something else.

Rules, only for blocks whose body is indented:
1. end and else stand exactly under the line that opened their block;
2. until a block is closed, its lines stand deeper than the line that opened it.
A program without indentation is checked exactly as before.
"""
import unittest

from helpers import AxionTest


def fix_of(out):
    return next((line[5:] for line in out if line.startswith("Fix: ")), None)


class Agreement(AxionTest):
    def test_well_indented_programs_run(self):
        source = ("xs = [1, 5]\nfor x in xs\n  if x > 2\n    print x\n  else if x > 0\n"
                  "    print 0\n  else\n    print 9\n  end\nend\nprint 7")
        self.assertOutput(source, ["0", "5", "7"])

    def test_unindented_programs_run_as_before(self):
        source = "xs = [1, 5]\nfor x in xs\nif x > 2\nprint x\nelse\nprint 0\nend\nend\nprint 7"
        self.assertOutput(source, ["0", "5", "7"])

    def test_function_and_four_spaces_and_tabs(self):
        self.assertOutput("function f(a: number) -> number\n    if a > 0\n        return a\n    end\n"
                          "    return 0\nend\nprint f(2)", ["2"])
        self.assertOutput("for x in [1]\n\tif x > 0\n\t\tprint x\n\tend\nend", ["1"])

    def test_multiline_list_inside_a_block(self):
        self.assertOutput("for x in [1]\n  ys = [\n1,\n2\n  ]\n  print ys length + x\nend", ["3"])

    def test_comments_and_blank_lines_do_not_count(self):
        self.assertOutput("for x in [1]\n# note\n\n  print x\n# another\nend", ["1"])

    def test_end_under_the_outer_block(self):
        # gemma3:12b, task 11.
        source = ("scores = [3, 1]\nlowest = scores[0]\nfor i in 1 to scores length - 1\n"
                  "  if scores[i] < lowest\n    lowest = scores[i]\nend\nprint lowest")
        out = self.assertError(source, "P216")
        self.assertEqual(out[0], "ERROR P216 line 6:1")
        self.assertIn("This end lines up with the for on line 3, but the if on line 4 is still open.", out)
        self.assertEqual(fix_of(out), "add an end for the if before this line")
        fixed = source.replace("    lowest = scores[i]\nend", "    lowest = scores[i]\n  end\nend")
        self.assertOutput(fixed, ["1"])

    def test_line_dedented_while_its_block_is_open(self):
        # gemma3:12b, task 14: the for was never closed; the old error pointed at the for itself.
        source = ('names = ["a"]\nn = 0\nfor name in names\n  if name == "a"\n    n = n + 1\n  end\n'
                  'print "sum: " + n as text')
        out = self.assertError(source, "P216")
        self.assertEqual(out[0], "ERROR P216 line 7:1")
        self.assertIn("This line is outside the for on line 3 by its indentation, but that for "
                      "has no end yet.", out)
        self.assertEqual(fix_of(out), "add an end for the for before this line")
        self.assertOutput(source.replace('  end\nprint', '  end\nend\nprint'), ["sum: 1"])

    def test_missing_and_extra_end_no_longer_cancel_out(self):
        # phi4, task 5: one end missing inside, one extra at the bottom. It used to run.
        source = ("xs = [1, 2]\nt = 0\nfor x in xs\n  if x > 1\n    t = t + x\n  t = t + 100\nend\n"
                  "end\nprint t")
        out = self.assertError(source, "P216")
        self.assertEqual(out[0], "ERROR P216 line 6:3")

    def test_else_must_stand_under_its_if(self):
        source = "x = 1\nif x > 0\n  print 1\n  else\n  print 2\nend"
        out = self.assertError(source, "P216")
        self.assertIn("This else closes the if on line 2 but is indented deeper than it.", out)

    def test_end_indented_with_the_body(self):
        out = self.assertError("x = 1\nif x > 0\n  print 1\n  end", "P216")
        self.assertIn("This end closes the if on line 2 but is indented deeper than it.", out)

    def test_end_left_of_its_opener_with_no_outer_block(self):
        out = self.assertError("x = 1\n  if x > 0\n    print 1\nend", "P216")
        self.assertIn("This end closes the if on line 2 but stands to the left of it.", out)

    def test_nothing_runs(self):
        source = 'print "start"\nfor x in [1]\n  if x > 0\n    print x\nend'
        out = self.assertError(source, "P216")
        self.assertTrue(out[0].startswith("ERROR P216"))

    def test_found_together_with_line_mistakes(self):
        source = "xs = []\nfor x in [1]\n  if x > 0\n    print x\nend\nprint xs"
        self.assertErrors(source, ["P213", "P216"])

    def test_broken_header_keeps_its_indentation_in_the_block_pass(self):
        # The if header is wrong; its end is in place: only the header is reported.
        self.assertErrors("for x in [1]\n  if x = 1\n    print x\n  end\nend", ["P202"])


class HintTexts(AxionTest):
    def test_extra_end_does_not_claim_the_place(self):
        # GPT removed the end the old hint pointed at; the extra one was 100 lines above.
        out = self.assertError("x = 1\nprint x\nend", "P212")
        self.assertIn("end without an open block: there is one end too many at or above this line.", out)
        self.assertEqual(fix_of(out), "check the blocks above: every if, for, while and function has exactly one end")

    def test_unclosed_block_without_indentation(self):
        out = self.assertError("for x in [1]\nprint x", "P212")
        self.assertIn("for is never closed: an end is missing between this line and the end "
                      "of the program.", out)
        self.assertEqual(fix_of(out), "add the missing end where this for block really finishes")

    def test_unused_variable_is_deleted_not_renamed(self):
        # GPT read "did you mean categories?" as "rename it".
        out = self.assertError("categories = [1]\ncategoryIndex = 0\nprint categories", "V305")
        self.assertEqual(fix_of(out), "delete every line that sets categoryIndex, or use it")

    def test_near_typo_still_names_the_other_variable(self):
        out = self.assertError("total = 1\ntotl = total + 1\nprint total", "V305")
        self.assertEqual(fix_of(out), "if you meant total, write total here; otherwise delete "
                                      "every line that sets totl")


if __name__ == "__main__":
    unittest.main()
