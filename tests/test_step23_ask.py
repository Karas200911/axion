"""axionlang.ask: a model writes the program, Axion checks the data and the program and runs it.

Every test uses a fake model: a function that returns prepared replies and records what it was
sent. No key and no network are needed.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import axionlang  # noqa: E402

SAMPLE = {"prices": [120, 450, 80]}
SUM = "input prices: list of number\nprint prices sum"


def fake(*replies):
    """A model that returns the replies in order and keeps every list of messages it got."""
    replies = list(replies)
    sent = []

    def model(messages):
        sent.append([dict(m) for m in messages])
        return replies.pop(0)

    model.sent = sent
    return model


class ItWorks(unittest.TestCase):
    def test_right_at_the_first_attempt(self):
        model = fake(SUM)
        r = axionlang.ask(model, "Total of all prices", {"prices": [120, 450, 80]}, shape=SAMPLE)
        self.assertEqual((r.ok, r.output, r.attempts, r.program), (True, ["650"], 1, SUM))
        self.assertEqual(len(model.sent), 1)

    def test_a_reply_in_a_fence(self):
        r = axionlang.ask(fake("```axion\n" + SUM + "\n```"), "Total", {"prices": [1, 2]}, shape=SAMPLE)
        self.assertEqual((r.ok, r.output, r.program), (True, ["3"], SUM))

    def test_an_error_goes_back_and_is_fixed(self):
        model = fake('input prices: list of number\nprint prices sum + "a"', SUM)
        r = axionlang.ask(model, "Total", {"prices": [1, 2]}, shape=SAMPLE)
        self.assertEqual((r.ok, r.output, r.attempts), (True, ["3"], 2))
        second = model.sent[1]
        self.assertEqual([m["role"] for m in second], ["system", "user", "assistant", "user"])
        self.assertIn("V301", second[-1]["content"])
        self.assertIn("Fix the program", second[-1]["content"])
        self.assertEqual([p for p, _ in r.history], ['input prices: list of number\nprint prices sum + "a"', SUM])

    def test_the_conversation_keeps_every_attempt(self):
        model = fake("print 1 + \"a\"", "print 2 + \"b\"", "print 3")
        r = axionlang.ask(model, "Three", {}, shape={})
        self.assertEqual((r.ok, r.attempts), (True, 3))
        self.assertEqual(len(model.sent[2]), 6)          # system, user, then two pairs

    def test_a_quick_try_with_shape_equal_to_data(self):
        data = {"prices": [5, 6]}
        self.assertEqual(axionlang.ask(fake(SUM), "Total", data, shape=data).output, ["11"])


class ItStops(unittest.TestCase):
    def test_after_max_attempts(self):
        model = fake('print 1 + "a"', 'print 1 + "b"', 'print 1 + "c"', "print 1")
        r = axionlang.ask(model, "One", {}, shape={})
        self.assertEqual((r.ok, r.attempts, r.error.code), (False, 3, "V301"))
        self.assertEqual(len(model.sent), 3)              # the fourth reply is never asked for
        self.assertEqual(r.program, 'print 1 + "c"')

    def test_max_attempts_can_be_set(self):
        model = fake('print 1 + "a"', "print 1")
        r = axionlang.ask(model, "One", {}, shape={}, max_attempts=1)
        self.assertEqual((r.ok, r.attempts, len(model.sent)), (False, 1, 1))


class MalformedData(unittest.TestCase):
    def test_refused_before_the_model_is_asked(self):
        model = fake(SUM)
        r = axionlang.ask(model, "Total", {"prices": [120, "450", 80]}, shape=SAMPLE)
        self.assertEqual((r.ok, r.attempts, r.error.code), (False, 0, "R407"))
        self.assertIn("prices[1] must be number, got text", r.error.message)
        self.assertEqual(model.sent, [])                  # no tokens spent

    def test_all_values_as_text_is_still_refused(self):
        r = axionlang.ask(fake(SUM), "Total", {"prices": ["120", "450"]}, shape=SAMPLE)
        self.assertEqual((r.ok, r.error.code), (False, "R407"))

    def test_a_missing_and_an_extra_field(self):
        self.assertEqual(axionlang.ask(fake(SUM), "T", {}, shape=SAMPLE).error.code, "R407")
        self.assertEqual(axionlang.ask(fake(SUM), "T", {"prices": [1], "x": 2}, shape=SAMPLE).error.code, "R407")

    def test_a_program_that_declares_other_types_is_sent_back(self):
        # the data fits the shape; the program declared it wrongly: that is the program's fault
        model = fake("input prices: list of text\nprint prices length", SUM)
        r = axionlang.ask(model, "Total", {"prices": [1, 2]}, shape=SAMPLE)
        self.assertEqual((r.ok, r.output, r.attempts), (True, ["3"], 2))
        self.assertIn("R407", model.sent[1][-1]["content"])


class WhatTheModelSees(unittest.TestCase):
    def test_only_the_shape_never_the_values(self):
        model = fake(SUM)
        axionlang.ask(model, "Total", {"prices": [987654, 123457]}, shape=SAMPLE)
        text = " ".join(m["content"] for m in model.sent[0])
        self.assertIn("input prices: list of number", text)
        self.assertNotIn("987654", text)
        self.assertNotIn("123457", text)

    def test_the_cheat_sheet_and_the_question(self):
        model = fake(SUM)
        axionlang.ask(model, "Total of all prices", {"prices": [1]}, shape=SAMPLE)
        self.assertEqual(model.sent[0][0], {"role": "system", "content": axionlang.CHEATSHEET})
        self.assertIn("Task: Total of all prices", model.sent[0][1]["content"])
        self.assertIn("Reply with only the Axion program", model.sent[0][1]["content"])


class EmptyReplies(unittest.TestCase):
    def test_an_empty_reply_is_a_failed_attempt(self):
        model = fake("   ", "print 7")
        r = axionlang.ask(model, "Seven", {}, shape={})
        self.assertEqual((r.ok, r.output, r.attempts), (True, ["7"], 2))
        self.assertIn("contained no program", model.sent[1][-1]["content"])

    def test_only_empty_replies(self):
        r = axionlang.ask(fake("", "```\n```"), "Seven", {}, shape={}, max_attempts=2)
        self.assertEqual((r.ok, r.error.code), (False, "NO_PROGRAM"))


class WrongCalls(unittest.TestCase):
    def test_shape_is_required(self):
        with self.assertRaises(TypeError) as caught:
            axionlang.ask(fake(SUM), "Total", {"prices": [1]})
        self.assertIn("shape is required", str(caught.exception))
        self.assertIn("shape=data", str(caught.exception))

    def test_the_model_must_return_text(self):
        with self.assertRaises(TypeError):
            axionlang.ask(lambda m: None, "Total", {"prices": [1]}, shape=SAMPLE)

    def test_the_model_must_be_a_function(self):
        with self.assertRaises(TypeError):
            axionlang.ask("gpt", "Total", {"prices": [1]}, shape=SAMPLE)

    def test_bad_max_attempts(self):
        with self.assertRaises(ValueError):
            axionlang.ask(fake(SUM), "Total", {"prices": [1]}, shape=SAMPLE, max_attempts=0)

    def test_errors_of_the_model_are_not_caught(self):
        def broken(messages):
            raise ConnectionError("no network")
        with self.assertRaises(ConnectionError):
            axionlang.ask(broken, "Total", {"prices": [1]}, shape=SAMPLE)


class LimitsPassThrough(unittest.TestCase):
    def test_a_launch_limit_reaches_the_run(self):
        loop = "x = 1\nwhile x > 0\nx = x + 1\nend"
        r = axionlang.ask(fake(loop), "Loop", {}, shape={}, max_attempts=1, max_steps=100)
        self.assertEqual(r.error.code, "R406")
        self.assertIn("100 steps", r.error.message)


if __name__ == "__main__":
    unittest.main()
