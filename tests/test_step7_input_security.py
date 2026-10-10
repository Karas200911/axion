"""Step 7 — input data, allow read, launch policy, resource limits.

Written from the v0.2 documentation (§1 layout, §14 input, §15 security).
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import AxionTest

ROOT = Path(__file__).resolve().parent.parent

CART = """input cart: list of {price: number, qty: number}
input discount: number
total = 0
for item in cart
total = total + item.price * item.qty
end
print total * (1 - discount)"""

CART_DATA = '{"cart": [{"price": 500, "qty": 2}, {"price": 300, "qty": 1}], "discount": 0.1}'


class Inputs(AxionTest):
    def test_cart(self):
        self.assertOutput(CART, ["1170"], data=CART_DATA)

    def test_same_program_other_data(self):
        self.assertOutput(CART, ["0"], data='{"cart": [], "discount": 0.5}')

    def test_decimal_numbers_from_json(self):
        self.assertOutput("input a: number\ninput b: number\nprint a + b == 0.3",
                          ["true"], data='{"a": 0.1, "b": 0.2}')

    def test_all_types(self):
        src = ('input t: text\ninput b: bool\ninput xs: list of text\ninput o: {n: number}\n'
               'print t\nprint b\nprint xs\nprint o')
        self.assertOutput(src, ["hi", "true", '["a"]', "{n: 1}"],
                          data='{"t": "hi", "b": true, "xs": ["a"], "o": {"n": 1}}')

    def test_object_fields_printed_in_declared_order(self):
        self.assertOutput("input o: {a: number, b: number}\nprint o", ["{a: 1, b: 2}"],
                          data='{"o": {"b": 2, "a": 1}}')

    def test_input_is_a_normal_variable(self):
        self.assertOutput("input n: number\nn = n + 1\nprint n", ["6"], data='{"n": 5}')

    def test_not_provided(self):
        out = self.assertError(CART, "R407", data='{"cart": []}')
        self.assertIn("input discount was not provided.", out)

    def test_no_data_at_all(self):
        self.assertError(CART, "R407")

    def test_wrong_type(self):
        out = self.assertError("input n: number\nprint n", "R407", data='{"n": "5"}')
        self.assertIn("Input data: n must be number, got text.", out)

    def test_null(self):
        self.assertError("input n: number\nprint n", "R407", data='{"n": null}')

    def test_missing_field(self):
        out = self.assertError(CART, "R407",
                               data='{"cart": [{"price": 1}], "discount": 0}')
        self.assertIn("Input data: cart[0] has no field qty.", out)

    def test_extra_field(self):
        self.assertError(CART, "R407",
                         data='{"cart": [{"price": 1, "qty": 1, "x": 1}], "discount": 0}')

    def test_undeclared_data(self):
        self.assertError("input n: number\nprint n", "R407", data='{"n": 1, "m": 2}')

    def test_nothing_runs_when_data_is_bad(self):
        self.assertError('input n: number\nprint "start"\nprint n', "R407", data='{"n": true}')

    def test_unused_input(self):
        self.assertError("input n: number\nprint 1", "V305", data='{"n": 1}')

    def test_input_after_code(self):
        self.assertError("x = 1\ninput n: number\nprint x + n", "P215")

    def test_input_needs_type(self):
        self.assertError("input n\nprint n", "P202")

    def test_input_in_block(self):
        self.assertError("if true\ninput n: number\nprint n\nend", "P215")

    def test_function_cannot_see_input(self):
        src = "input rate: number\nfunction tax(a: number) -> number\nreturn a * rate\nend\nprint tax(rate)"
        self.assertError(src, "V325", data='{"rate": 1}')


class Files(AxionTest):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / "reports").mkdir()
        (self.dir / "reports" / "q1.txt").write_text("revenue 100", encoding="utf-8")
        (self.dir / "secret.txt").write_text("password", encoding="utf-8")
        self.policy = {"allow_read": ["reports/"]}

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_read(self):
        src = 'allow read "reports/"\ncontent = read "reports/q1.txt"\nprint content'
        self.assertOutput(src, ["revenue 100"], policy=self.policy, base_dir=self.dir)

    def test_read_length(self):
        src = 'allow read "reports/"\nprint (read "reports/q1.txt") length'
        self.assertOutput(src, ["11"], policy=self.policy, base_dir=self.dir)

    def test_read_takes_the_whole_expression(self):
        src = 'allow read "reports/"\nname = "q1"\nprint read "reports/" + name + ".txt"'
        self.assertOutput(src, ["revenue 100"], policy=self.policy, base_dir=self.dir)

    def test_computed_path(self):
        src = 'allow read "reports/"\nname = "q1"\nprint read ("reports/" + name + ".txt")'
        self.assertOutput(src, ["revenue 100"], policy=self.policy, base_dir=self.dir)

    def test_read_without_allow(self):
        out = self.assertError('print read "reports/q1.txt"', "S501",
                               policy=self.policy, base_dir=self.dir)
        self.assertIn('Fix: add at the top: allow read "reports/"', out)

    def test_zero_rights_by_default(self):
        # The program asks, but nobody granted anything: it does not run.
        self.assertError('allow read "reports/"\nprint read "reports/q1.txt"', "S502", base_dir=self.dir)

    def test_request_wider_than_policy(self):
        self.assertError('allow read "./"\nprint read "secret.txt"', "S502",
                         policy=self.policy, base_dir=self.dir)

    def test_literal_path_outside_folder(self):
        self.assertError('allow read "reports/"\nprint read "secret.txt"', "S503",
                         policy=self.policy, base_dir=self.dir)

    def test_dot_dot(self):
        self.assertError('allow read "reports/"\nprint read "reports/../secret.txt"', "S503",
                         policy=self.policy, base_dir=self.dir)

    def test_absolute_path(self):
        self.assertError('allow read "reports/"\nprint read "/etc/passwd"', "S503",
                         policy=self.policy, base_dir=self.dir)

    def test_computed_dot_dot_at_runtime(self):
        src = 'allow read "reports/"\nup = ".."\nprint read ("reports/" + up + "/secret.txt")'
        self.assertError(src, "S503", policy=self.policy, base_dir=self.dir)

    @unittest.skipIf(os.name == "nt", "symlinks need extra rights on Windows")
    def test_symlink_leading_outside(self):
        os.symlink(self.dir / "secret.txt", self.dir / "reports" / "link.txt")
        src = 'allow read "reports/"\nprint read "reports/link.txt"'
        self.assertError(src, "S503", policy=self.policy, base_dir=self.dir)

    def test_missing_file(self):
        self.assertError('allow read "reports/"\nprint read "reports/nope.txt"', "R408",
                         policy=self.policy, base_dir=self.dir)

    def test_unused_allow(self):
        self.assertError('allow read "reports/"\nprint 1', "V305", policy=self.policy, base_dir=self.dir)

    def test_allow_after_code(self):
        self.assertError('print 1\nallow read "reports/"', "P215", policy=self.policy, base_dir=self.dir)

    def test_allow_after_input(self):
        src = 'input n: number\nallow read "reports/"\nprint n'
        self.assertError(src, "P215", policy=self.policy, base_dir=self.dir)

    def test_only_allow_read_exists(self):
        self.assertError('allow network "x"\nprint 1', "P202")

    def test_read_needs_text(self):
        self.assertError('allow read "reports/"\nprint read 5', "V301",
                         policy=self.policy, base_dir=self.dir)


class Limits(AxionTest):
    def test_steps(self):
        src = "total = 0\nfor i in 1 to 1000\ntotal = total + i\nend\nprint total"
        self.assertError(src, "R406", policy={"max_steps": 100})

    def test_steps_default_allows_normal_programs(self):
        self.assertOutput("total = 0\nfor i in 1 to 1000\ntotal = total + i\nend\nprint total", ["500500"])

    def test_huge_range(self):
        self.assertError("for i in 1 to 1000000000000\nprint i\nend", "R406")

    def test_list_growth(self):
        src = "xs = [] of number\nfor i in 1 to 10\nxs add i\nend\nprint xs"
        self.assertError(src, "R406", policy={"max_list_size": 5})

    def test_output_size(self):
        src = 'for i in 1 to 100\nif i > 0\nprint "line"\nend\nend'
        self.assertError(src, "R406", printed_before=["line"] * 10, policy={"max_output_chars": 50})


class CommandLine(unittest.TestCase):
    """The real command: python -m axionlang program.ax --input data.json --policy policy.json"""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.dir)

    def run_cli(self, *args):
        result = subprocess.run([sys.executable, "-m", "axionlang", *args],
                                capture_output=True, text=True, cwd=self.dir,
                                env={**os.environ, "PYTHONPATH": str(ROOT)})
        return result.returncode, result.stdout.splitlines()

    def test_program_with_input_file(self):
        (self.dir / "cart.ax").write_text(CART, encoding="utf-8")
        (self.dir / "data.json").write_text(CART_DATA, encoding="utf-8")
        self.assertEqual(self.run_cli("cart.ax", "--input", "data.json"), (0, ["1170"]))

    def test_policy_file(self):
        (self.dir / "r").mkdir()
        (self.dir / "r" / "a.txt").write_text("hello", encoding="utf-8")
        (self.dir / "p.ax").write_text('allow read "r/"\nprint read "r/a.txt"', encoding="utf-8")
        (self.dir / "policy.json").write_text('{"allow_read": ["r/"]}', encoding="utf-8")
        self.assertEqual(self.run_cli("p.ax", "--policy", "policy.json"), (0, ["hello"]))

    def test_bad_policy_file(self):
        (self.dir / "p.ax").write_text("print 1", encoding="utf-8")
        (self.dir / "policy.json").write_text('{"allow_everything": true}', encoding="utf-8")
        code, out = self.run_cli("p.ax", "--policy", "policy.json")
        self.assertEqual(code, 2)
        self.assertTrue(out[0].startswith("POLICY FILE ERROR"))

    def test_bad_json(self):
        (self.dir / "p.ax").write_text("input n: number\nprint n", encoding="utf-8")
        (self.dir / "d.json").write_text("{n: 1}", encoding="utf-8")
        code, out = self.run_cli("p.ax", "--input", "d.json")
        self.assertEqual(code, 2)
        self.assertTrue(out[0].startswith("DATA FILE ERROR"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
