"""Step 25: data nested too deeply is refused with an Axion error, not a Python crash.

Found while checking injection through JSON (2026-10-09): a list inside a list 50,000 levels deep
made axionlang.run and `python -m axionlang --input` fall with a Python RecursionError. Nothing
ran and nothing was read, but a host that does not expect an exception could lose the request.
Now data deeper than 100 levels is refused: R407 from the library, a DATA FILE ERROR (exit 2)
from the command line, ValueError from describe. Both paths count levels the same way.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import axionlang  # noqa: E402
from axionlang.engine.inputs import MAX_DATA_DEPTH, parse_json  # noqa: E402

PROGRAM = "input x: list of number\nprint x length as text"


def nested(brackets):
    """A JSON-like list with this many levels of brackets in total: nested(2) == [[]]."""
    outer = []
    current = outer
    for _ in range(brackets - 1):
        inner = []
        current.append(inner)
        current = inner
    return outer


def json_text(brackets):
    return '{"x": ' + "[" * brackets + "]" * brackets + "}"


class Library(unittest.TestCase):
    def test_very_deep_data_is_r407(self):
        r = axionlang.run(PROGRAM, {"x": nested(50_000)})
        self.assertFalse(r.ok)
        self.assertEqual(r.error.code, "R407")
        self.assertIn("x is nested more than 100 levels deep", r.error.message)
        self.assertEqual(r.output, [])

    def test_the_message_is_short(self):
        r = axionlang.run(PROGRAM, {"x": nested(50_000)})
        self.assertLess(len(r.error.message), 200)

    def test_limit_edge(self):
        at_limit = axionlang.run(PROGRAM, {"x": nested(MAX_DATA_DEPTH)})
        self.assertEqual(at_limit.error.code, "R407")
        self.assertNotIn("nested more than", at_limit.error.message)   # the usual type error
        over = axionlang.run(PROGRAM, {"x": nested(MAX_DATA_DEPTH + 1)})
        self.assertIn("nested more than", over.error.message)

    def test_ordinary_nesting_still_works(self):
        program = ("input orders: list of {id: text, items: list of {price: number, qty: number}}\n"
                   "print orders[0].items[1].price as text")
        data = {"orders": [{"id": "a", "items": [{"price": 1, "qty": 2}, {"price": 3, "qty": 4}]}]}
        r = axionlang.run(program, data)
        self.assertTrue(r.ok, r.error)
        self.assertEqual(r.output, ["3"])

    def test_describe_refuses(self):
        with self.assertRaises(ValueError) as caught:
            axionlang.describe({"x": nested(500)})
        self.assertIn("x is nested more than 100 levels deep", str(caught.exception))

    def test_ask_refuses_before_the_model(self):
        calls = []

        def model(messages):
            calls.append(messages)
            return PROGRAM

        r = axionlang.ask(model, "count", {"x": nested(50_000)}, shape={"x": [1]})
        self.assertFalse(r.ok)
        self.assertEqual(r.error.code, "R407")
        self.assertEqual(r.attempts, 0)
        self.assertEqual(calls, [])


class CommandLine(unittest.TestCase):
    def run_cli(self, brackets):
        with tempfile.TemporaryDirectory() as folder:
            program = Path(folder, "p.ax")
            data = Path(folder, "d.json")
            program.write_text(PROGRAM + "\n", encoding="utf-8")
            data.write_text(json_text(brackets), encoding="utf-8")
            env = dict(os.environ, PYTHONPATH=str(ROOT))
            return subprocess.run([sys.executable, "-B", "-m", "axionlang", str(program), "--input", str(data)],
                                  capture_output=True, text=True, env=env, timeout=60)

    def test_very_deep_file_is_a_data_file_error(self):
        done = self.run_cli(100_000)
        self.assertEqual(done.returncode, 2)
        self.assertIn("DATA FILE ERROR", done.stdout)
        self.assertIn("nested too deeply", done.stdout)
        self.assertNotIn("Traceback", done.stdout + done.stderr)

    def test_between_100_and_python_limit_is_refused_too(self):
        done = self.run_cli(900)
        self.assertEqual(done.returncode, 2)
        self.assertIn("nested too deeply", done.stdout)

    def test_same_edge_as_the_library(self):
        self.assertEqual(self.run_cli(MAX_DATA_DEPTH).returncode, 1)        # parsed; a type error
        self.assertEqual(self.run_cli(MAX_DATA_DEPTH + 1).returncode, 2)    # refused as too deep

    def test_parse_json_raises_value_error(self):
        with self.assertRaises(ValueError):
            parse_json(json_text(100_000))
        self.assertEqual(json.loads(json.dumps(parse_json(json_text(3)), default=str)), {"x": [[[]]]})


if __name__ == "__main__":
    unittest.main()
