"""The library face (engine/api.py): axionlang.run, axionlang.check, axionlang.describe, axionlang.CHEATSHEET.

The library and the command line go through one path (engine/runner.py), so these tests look at
what the library adds: Python data in, a Result out, and wrong calls refused loudly.
"""

import os
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import axionlang  # noqa: E402

SHOP = 'input price: number\ninput count: number\nprint "Итого: " + (price * count) as text\n'


class RunOk(unittest.TestCase):
    def test_result_of_a_good_run(self):
        r = axionlang.run(SHOP, {"price": 250, "count": 3})
        self.assertIs(r.ok, True)
        self.assertEqual(r.output, ["Итого: 750"])
        self.assertEqual(r.text, "Итого: 750")
        self.assertIsNone(r.error)
        self.assertEqual(r.errors, [])

    def test_no_inputs_no_data(self):
        self.assertEqual(axionlang.run("print 1000 * 10 / 100\n").output, ["100"])

    def test_python_floats_become_exact_numbers(self):
        r = axionlang.run("input a: number\ninput b: number\nprint a + b\n", {"a": 0.1, "b": 0.2})
        self.assertEqual(r.output, ["0.3"])

    def test_decimal_and_big_int_are_numbers(self):
        r = axionlang.run("input a: number\ninput b: number\nprint a + b\n", {"a": Decimal("1.50"), "b": 10 ** 20})
        self.assertEqual(r.output, ["100000000000000000001.5"])

    def test_lists_tuples_and_dicts(self):
        program = ('input items: list of {name: text, price: number, returned: bool}\n'
                   'total = 0\nfor it in items\n  if it.returned\n    total = total + it.price\n  end\nend\n'
                   'print total\n')
        data = {"items": ({"name": "Кружка", "price": 520, "returned": True},
                          {"name": "Чайник", "price": 1320.0, "returned": True},
                          {"name": "Ложка", "price": 150, "returned": False})}
        self.assertEqual(axionlang.run(program, data).output, ["1840"])

    def test_several_lines_and_text_property(self):
        r = axionlang.run('print "a"\nprint "b"\n')
        self.assertEqual(r.output, ["a", "b"])
        self.assertEqual(r.text, "a\nb")

    def test_the_callers_data_is_not_changed(self):
        data = {"xs": [1, 2, 3]}
        axionlang.run("input xs: list of number\nxs add 4\nprint xs\n", data)
        self.assertEqual(data, {"xs": [1, 2, 3]})

    def test_same_output_as_the_command_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "p.ax").write_text(SHOP, encoding="utf-8")
            (Path(tmp) / "d.json").write_text('{"price": 250, "count": "3"}', encoding="utf-8")
            done = subprocess.run([sys.executable, "-X", "utf8", "-m", "axionlang", "p.ax", "--input", "d.json"],
                                  cwd=tmp, capture_output=True, encoding="utf-8",
                                  env={**os.environ, "PYTHONPATH": str(ROOT)})
        r = axionlang.run(SHOP, {"price": 250, "count": "3"})
        self.assertEqual(done.returncode, 1)
        self.assertEqual(done.stdout.rstrip("\n"), str(r.error))


class RunStopped(unittest.TestCase):
    def test_mistake_in_the_program(self):
        r = axionlang.run('print "Итого: " + 750\n')
        self.assertIs(r.ok, False)
        self.assertEqual(r.output, [])
        e = r.error
        self.assertEqual((e.code, e.line, e.col), ("V301", 1, 7))
        self.assertEqual(e.message, "Cannot add text and number.")
        self.assertEqual(e.fix, 'print "Итого: " + 750 as text')
        self.assertEqual(str(e), 'ERROR V301 line 1:7\nprint "Итого: " + 750\n      ^^^^^^^^^^^^^^^\n'
                                 'Cannot add text and number.\nFix: print "Итого: " + 750 as text')
        self.assertEqual(len(r.errors), 1)

    def test_several_mistakes_in_one_pass(self):
        r = axionlang.run('x = 1\nprint "a" + 1\n')
        self.assertEqual([e.code for e in r.errors], ["V305", "V301"])
        self.assertEqual(r.error.code, "V305")                    # the first one
        self.assertIn("ERROR V305", str(r.error))                 # its text holds all of them
        self.assertIn("ERROR V301", str(r.error))
        self.assertNotIn("V305", str(r.errors[1]))                # each of errors has only its own

    def test_wrong_type_in_the_data(self):
        r = axionlang.run(SHOP, {"price": 250, "count": "3"})
        self.assertEqual(r.error.code, "R407")
        self.assertEqual(r.error.message, "Input data: count must be number, got text.")
        self.assertEqual(r.output, [])

    def test_true_is_not_a_number(self):
        r = axionlang.run("input n: number\nprint n\n", {"n": True})
        self.assertEqual(r.error.message, "Input data: n must be number, got true/false.")

    def test_none_is_refused_by_the_input_check(self):
        r = axionlang.run("input n: number\nprint n\n", {"n": None})
        self.assertEqual(r.error.code, "R407")

    def test_missing_and_extra_values(self):
        self.assertEqual(axionlang.run("input n: number\nprint n\n").error.message, "input n was not provided.")
        r = axionlang.run("input n: number\nprint n\n", {"n": 5, "extra": 1})
        self.assertEqual(r.error.message, "The input data has extra, which the program does not declare.")

    def test_runtime_error_keeps_what_was_printed(self):
        r = axionlang.run('input n: number\nprint "Начало"\nprint 10 / n\n', {"n": 0})
        self.assertIs(r.ok, False)
        self.assertEqual(r.output, ["Начало"])
        self.assertEqual(r.error.code, "R401")

    def test_syntax_error(self):
        r = axionlang.run('pritn "x"\n')
        self.assertEqual(r.error.code, "P202")


class Limits(unittest.TestCase):
    LOOP = "n = 1\nwhile n > 0\n  n = n + 1\nend\nprint n\n"

    def test_step_limit_of_this_run(self):
        r = axionlang.run(self.LOOP, max_steps=100)
        self.assertEqual(r.error.code, "R406")
        self.assertIn("more than 100 steps", r.error.message)

    def test_default_limit_stops_an_endless_loop(self):
        self.assertEqual(axionlang.run(self.LOOP).error.code, "R406")

    def test_output_limit(self):
        r = axionlang.run('for i in 1 to 100\n  print "xxxxxxxxxx"\nend\n', max_output_chars=50)
        self.assertEqual(r.error.code, "R406")


class Reading(unittest.TestCase):
    PROGRAM = 'allow read "notes/"\nt = read "notes/a.txt"\nprint t trim\n'

    def test_not_granted(self):
        self.assertEqual(axionlang.run(self.PROGRAM).error.code, "S502")

    def test_granted(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "notes").mkdir()
            (Path(tmp) / "notes" / "a.txt").write_text("секрет\n", encoding="utf-8")
            r = axionlang.run(self.PROGRAM, allow_read=["notes/"], folder=tmp)
        self.assertEqual(r.output, ["секрет"])

    def test_not_asked_by_the_program(self):
        r = axionlang.run('t = read "notes/a.txt"\nprint t\n', allow_read=["notes/"])
        self.assertEqual(r.error.code, "S501")


class Check(unittest.TestCase):
    def test_good_program_needs_no_data_and_does_not_run(self):
        r = axionlang.check('input n: number\nprint "side effect"\nprint 10 / n\n')
        self.assertIs(r.ok, True)
        self.assertEqual(r.output, [])

    def test_endless_loop_is_not_run(self):
        self.assertIs(axionlang.check(Limits.LOOP).ok, True)

    def test_mistake_is_found(self):
        r = axionlang.check('print "a" + 1\n')
        self.assertEqual(r.error.code, "V301")

    def test_permissions_are_checked(self):
        self.assertEqual(axionlang.check(Reading.PROGRAM).error.code, "S502")
        self.assertIs(axionlang.check(Reading.PROGRAM, allow_read=["notes/"]).ok, True)


class WrongCalls(unittest.TestCase):
    def test_program_must_be_text(self):
        with self.assertRaises(TypeError):
            axionlang.run(5)
        with self.assertRaises(TypeError):
            axionlang.check(None)

    def test_data_must_be_a_dict_with_text_names(self):
        with self.assertRaises(TypeError):
            axionlang.run("print 1\n", [1])
        with self.assertRaises(TypeError):
            axionlang.run("print 1\n", {1: 2})
        with self.assertRaises(TypeError):
            axionlang.run("print 1\n", {"o": {1: 2}})

    def test_values_axiom_has_no_place_for(self):
        with self.assertRaises(TypeError):
            axionlang.run("print 1\n", {"x": object()})
        for bad in (float("nan"), float("inf"), Decimal("NaN")):
            with self.assertRaises(ValueError):
                axionlang.run("print 1\n", {"x": bad})

    def test_limits_and_folders(self):
        with self.assertRaises(ValueError):
            axionlang.run("print 1\n", max_steps=0)
        with self.assertRaises(ValueError):
            axionlang.run("print 1\n", allow_read=["../x"])
        with self.assertRaises(TypeError):
            axionlang.run("print 1\n", allow_read="notes/")


class Describe(unittest.TestCase):
    def test_simple_and_nested(self):
        data = {"price": 250, "who": "Саша", "ok": True,
                "items": [{"name": "Кружка", "qty": 2, "returned": False}]}
        self.assertEqual(axionlang.describe(data),
                         "input price: number\ninput who: text\ninput ok: bool\n"
                         "input items: list of {name: text, qty: number, returned: bool}")

    def test_the_lines_accept_the_same_data(self):
        data = {"rates": [1.5, 2, Decimal("0.1")], "point": {"x": 1, "y": -2.5}, "tags": [["a"], ["b", "c"]]}
        lines = axionlang.describe(data)
        self.assertEqual(lines, "input rates: list of number\ninput point: {x: number, y: number}\n"
                                "input tags: list of list of text")
        r = axionlang.run(lines + "\nprint rates sum\nprint point.x + point.y\nprint tags length\n", data)
        self.assertEqual(r.output, ["3.6", "-1.5", "2"])

    def test_what_cannot_be_described(self):
        for bad, word in (({"xs": []}, "empty list"), ({"xs": [1, "a"]}, "mixes types"),
                          ({"x": None}, "None"), ({"o": {}}, "empty dict"),
                          ({"text": 1}, "keyword"), ({"a b": 1}, "ERROR")):
            with self.assertRaises(ValueError) as caught:
                axionlang.describe(bad)
            self.assertIn(word, str(caught.exception))

    def test_wrong_calls(self):
        with self.assertRaises(TypeError):
            axionlang.describe([1, 2])
        with self.assertRaises(TypeError):
            axionlang.describe({"x": object()})

    def test_objects_in_a_list_must_have_the_same_fields(self):
        with self.assertRaises(ValueError):
            axionlang.describe({"rows": [{"a": 1}, {"a": 1, "b": 2}]})


class Cheatsheet(unittest.TestCase):
    def test_it_is_the_file_given_to_models(self):
        self.assertTrue(axionlang.CHEATSHEET.startswith("# Axion v0.3"))
        self.assertEqual(axionlang.CHEATSHEET, (ROOT / "axionlang" / "CHEATSHEET.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
