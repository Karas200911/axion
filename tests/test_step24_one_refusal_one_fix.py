"""Step 24: a refused allow read gives one error with a fix that can work.

Found on the playground: `allow read "/etc/"` was refused (S503), and the read below it got S501
with the fix `add at the top: allow read "/etc/"` -- the very line just refused. A model given
that fix would go round in circles. Now: the refusal has its own fix, the read under a refused
allow is not reported again, and no fix ever advises an absolute folder or one with ..
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import axionlang  # noqa: E402


def errors(program):
    return [(e.code, e.line, e.fix or "") for e in axionlang.check(program).errors]


class RefusedAllow(unittest.TestCase):
    def test_absolute_allow_gives_one_error(self):
        errs = errors('allow read "/etc/"\nt = read "/etc/passwd"\nprint t length as text')
        self.assertEqual([(c, l) for c, l, _ in errs], [("S503", 1)])

    def test_refusal_has_a_working_fix(self):
        (code, line, fix), = errors('allow read "/etc/"\nprint read "/etc/passwd"')
        self.assertIn('allow read "reports/"', fix)
        self.assertNotIn("/etc/", fix)

    def test_dotdot_allow_gives_one_error(self):
        errs = errors('allow read "../"\nprint read "../x.txt"')
        self.assertEqual([(c, l) for c, l, _ in errs], [("S503", 1)])

    def test_still_fails_closed(self):
        r = axionlang.run('allow read "/etc/"\nprint read "/etc/passwd"')
        self.assertFalse(r.ok)
        self.assertEqual(r.output, [])


class UndeclaredRead(unittest.TestCase):
    def test_absolute_path_fix_does_not_advise_absolute_folder(self):
        (code, line, fix), = errors('print read "/etc/passwd"')
        self.assertEqual(code, "S501")
        self.assertNotIn('allow read "/', fix)
        self.assertIn("relative", fix)

    def test_dotdot_path_fix_does_not_advise_dotdot(self):
        (code, line, fix), = errors('print read "../secret.txt"')
        self.assertEqual(code, "S501")
        self.assertNotIn("..", fix)

    def test_relative_path_keeps_the_old_fix(self):
        (code, line, fix), = errors('print read "reports/q1.txt"')
        self.assertEqual((code, fix), ("S501", 'add at the top: allow read "reports/"'))

    def test_following_the_fix_removes_the_error(self):
        program = 'print read "reports/q1.txt"'
        (_, _, fix), = errors(program)
        fixed = fix.removeprefix("add at the top: ") + "\n" + program
        r = axionlang.check(fixed, allow_read=["reports/"])
        self.assertTrue(r.ok, r.errors)


class AbsoluteReadUnderGoodAllow(unittest.TestCase):
    def test_fix_names_the_rule(self):
        errs = errors('allow read "reports/"\nprint read "/etc/passwd"')
        s503 = [f for c, _, f in errs if c == "S503"]
        self.assertEqual(len(s503), 1)
        self.assertIn("no / at the start", s503[0])


if __name__ == "__main__":
    unittest.main()
