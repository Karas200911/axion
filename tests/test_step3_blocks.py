"""Step 3 — if / else if / else, blocks and visibility, unused variables, empty branches.

Written from the v0.2 documentation (§6, §11).
"""

import unittest

from helpers import AxionTest

GRADE = """score = {score}
grade = "?"
if score >= 90
grade = "A"
else if score >= 75
grade = "B"
else if score >= 60
grade = "C"
else
grade = "F"
end
print grade"""


class IfElse(AxionTest):
    def test_true_branch_runs(self):
        self.assertOutput('if true\nprint "yes"\nend', ["yes"])

    def test_false_branch_skipped(self):
        self.assertOutput('if false\nprint "yes"\nend\nprint "after"', ["after"])

    def test_else(self):
        self.assertOutput('age = 10\nif age >= 18\nprint "adult"\nelse\nprint "child"\nend',
                          ["child"])

    def test_else_if_chain(self):
        for score, grade in ((95, "A"), (80, "B"), (65, "C"), (10, "F")):
            with self.subTest(score=score):
                self.assertOutput(GRADE.format(score=score), [grade])

    def test_only_first_true_branch_runs(self):
        self.assertOutput('s = 95\nif s >= 90\nprint "A"\nelse if s >= 75\nprint "B"\nend', ["A"])

    def test_else_is_optional(self):
        self.assertOutput('s = 50\nif s >= 90\nprint "A"\nelse if s >= 75\nprint "B"\nend\nprint "done"',
                          ["done"])

    def test_nested_if_has_its_own_end(self):
        src = ('s = 95\nperfect = true\nif s >= 90\nif perfect\nprint "wow"\nend\n'
               'else if s >= 75\nprint "good"\nend')
        self.assertOutput(src, ["wow"])

    def test_compound_condition(self):
        self.assertOutput('age = 20\nok = true\nif age >= 18 and ok\nprint "allowed"\nend', ["allowed"])

    def test_comments_and_blank_lines_in_blocks(self):
        self.assertOutput('if true\n# comment\n\nprint 1 # trailing\n\nend', ["1"])

    def test_condition_must_be_bool(self):
        out = self.assertError('age = 5\nif age\nprint age\nend', "V307")
        self.assertIn("Fix: if age > 0", out)
        out = self.assertError('name = "x"\nif name\nprint name\nend', "V307")
        self.assertIn('Fix: if name != ""', out)

    def test_else_if_condition_must_be_bool(self):
        self.assertError('s = 5\nif s > 9\nprint s\nelse if s\nprint s\nend', "V307")

    def test_all_branches_are_validated(self):
        # Fail-closed: an error in a branch that would never run still blocks the program.
        self.assertError('print 1\nif false\nprint 1 + "a"\nend', "V301")

    def test_runtime_error_inside_branch_keeps_output(self):
        self.assertError('z = 0\nprint 1\nif true\nprint 1 / z\nend', "R401", printed_before=["1"])


class IfSyntax(AxionTest):
    def test_elif(self):
        out = self.assertError('x = 1\nif x > 0\nprint x\nelif x < 0\nprint x\nend', "P210")
        self.assertIn("Fix: else if x < 0", out)

    def test_else_if_after_else(self):
        self.assertError('x = 1\nif x > 0\nprint x\nelse\nprint x\nelse if x < 0\nprint x\nend', "P211")

    def test_two_else(self):
        self.assertError('x = 1\nif x > 0\nprint x\nelse\nprint x\nelse\nprint x\nend', "P211")

    def test_condition_on_else(self):
        out = self.assertError('x = 1\nif x > 0\nprint x\nelse x < 0\nprint x\nend', "P211")
        self.assertIn("Fix: write else if x < 0", out)

    def test_else_without_if(self):
        self.assertError('else\nprint 1\nend', "P211")

    def test_missing_end(self):
        out = self.assertError('x = 1\nif x > 0\nprint x', "P212")
        self.assertEqual(out[0], "ERROR P212 line 2:1")

    def test_end_without_if(self):
        self.assertError('print 1\nend', "P212")

    def test_body_on_header_line(self):
        self.assertError('x = 1\nif x > 0 print x\nend', "P201")

    def test_indented_body(self):
        self.assertOutput('x = 1\nif x > 0\n    print x\nend', ["1"])


class EmptyBranches(AxionTest):
    def test_empty_if_branch(self):
        out = self.assertError('ok = true\nif ok\nelse\nprint "no"\nend', "V306")
        self.assertIn("Fix: if not ok", out)

    def test_empty_if_branch_compound_condition(self):
        out = self.assertError('a = 1\nif a > 0\nelse\nprint a\nend', "V306")
        self.assertIn("Fix: if not (a > 0)", out)

    def test_empty_else(self):
        self.assertError('ok = true\nif ok\nprint 1\nelse\nend', "V306")

    def test_empty_else_if(self):
        self.assertError('a = 1\nif a > 5\nprint a\nelse if a > 0\nend', "V306")

    def test_comment_only_branch_is_empty(self):
        self.assertError('ok = true\nif ok\n# todo\nend', "V306")


class Visibility(AxionTest):
    def test_modify_outer_variable(self):
        self.assertOutput('count = 0\nif true\ncount = 5\nend\nprint count', ["5"])

    def test_canonical_pattern(self):
        src = ('age = 20\nverified = true\nresult = "denied"\n'
               'if age >= 18 and verified\nresult = "allowed"\nend\nprint result')
        self.assertOutput(src, ["allowed"])

    def test_local_variable_inside_branch(self):
        self.assertOutput('if true\ntemp = 10\nprint temp\nend', ["10"])

    def test_local_dies_at_end(self):
        out = self.assertError('if true\ntemp = 10\nprint temp\nend\nprint temp', "V304")
        self.assertEqual(out[0], "ERROR V304 line 5:7")
        self.assertIn("Fix: create temp before the if and only change it inside", out)

    def test_branches_are_separate(self):
        self.assertError('ok = true\nif ok\na = 1\nprint a\nelse\nprint a\nend', "V304")

    def test_same_local_name_in_two_branches(self):
        src = 'ok = false\nif ok\nmsg = "yes"\nprint msg\nelse\nmsg = "no"\nprint msg\nend'
        self.assertOutput(src, ["no"])

    def test_inner_block_sees_outer_block(self):
        src = 'if true\nx = 1\nif true\nprint x\nend\nend'
        self.assertOutput(src, ["1"])

    def test_nothing_leaks_from_inner_block(self):
        src = 'if true\nif true\ny = 2\nprint y\nend\nprint y\nend'
        self.assertError(src, "V304")

    def test_type_of_outer_variable_is_fixed_inside_block(self):
        self.assertError('count = 0\nif true\ncount = "five"\nend\nprint count', "V302")

    def test_new_variable_after_block_with_same_name(self):
        src = 'if true\nx = 1\nprint x\nend\nx = "outer"\nprint x'
        self.assertOutput(src, ["1", "outer"])


class Unused(AxionTest):
    def test_unused_top_level(self):
        out = self.assertError("x = 5", "V305")
        self.assertEqual(out[0], "ERROR V305 line 1:1")

    def test_assigned_twice_never_read(self):
        self.assertError("x = 5\nx = 6", "V305")

    def test_unused_inside_block(self):
        self.assertError("if true\ntemp = 1\nprint 2\nend", "V305")

    def test_typo_suggests_existing_name(self):
        src = 'total = 0\npaid = true\nif paid\ntotl = total + 100\nend\nprint total'
        out = self.assertError(src, "V305")
        self.assertEqual(out[0], "ERROR V305 line 4:1")
        self.assertIn("Fix: if you meant total, write total here; otherwise delete every line that sets totl", out)

    def test_read_in_own_update_counts_as_use(self):
        self.assertOutput("x = 1\nx = x + 1\nprint x", ["2"])

    def test_used_only_in_condition(self):
        self.assertOutput('ok = true\nif ok\nprint 1\nend', ["1"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
