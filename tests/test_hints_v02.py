"""Better hints, found by real models in test 0 (Gemini and an old small model).

Rule: a Fix is working code whenever possible, and never leads to a new error.
"""

import unittest

from helpers import AxionTest

OLD_MODEL = """input users: list of {name: text, age: number, verified: bool}
names = [] of text
for u in users
if u.age >= 18 and u.verified
names = names + [u.name]
end
end
print names"""


class Hints(AxionTest):
    def test_double_ampersand(self):
        out = self.assertError("a = true\nb = true\nprint a && b", "L101")
        self.assertIn("Fix: write and", out)

    def test_double_bar(self):
        out = self.assertError("a = true\nb = true\nprint a || b", "L101")
        self.assertIn("Fix: write or", out)

    def test_print_with_comma(self):
        out = self.assertError('n = 1\nprint("N: ", n)', "P202")
        self.assertIn("print takes exactly one value.", out)
        self.assertIn('Fix: one value per print: print "N: ", then print n; or join text with +', out)

    def test_print_with_parentheses_still_works(self):
        self.assertOutput("print (1 + 2) * 3\nprint(4)", ["9", "4"])

    def test_list_as_text_fix_is_code(self):
        out = self.assertError("xs = [1]\nprint xs as text", "V311")
        self.assertIn("Fix: print shows lists, objects and dictionaries directly: print xs", out)

    def test_list_plus_one_element(self):
        out = self.assertError(OLD_MODEL, "V301", data='{"users": []}')
        self.assertIn("Fix: names add u.name", out)      # v0.3: the Fix is the line itself

    def test_suggested_fix_works(self):
        fixed = OLD_MODEL.replace("names = names + [u.name]", "names add u.name")
        data = '{"users": [{"name": "Alex", "age": 20, "verified": true}]}'
        self.assertOutput(fixed, ['["Alex"]'], data=data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
