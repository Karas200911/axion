"""Axion v0.3, step 4: while, continue, exit, recursion.

Decisions 11-14 of the v0.3 design (2026-10-05):

    while money < target     repeat while the condition is true
    continue                 go on with the next pass of the nearest loop
    exit                     the program ends here, normally (main program only)
    recursion                allowed; it was forbidden in v0.2

Each of the two things that may never end has two guards, one before the run and one in it:

    while       V328: the body must change a variable of the condition, or leave the loop
                itself (break, return, exit)                  + the step limit (R406)
    recursion   V322: the function must have a path that ends without calling itself,
                directly or through other functions           + the depth limit (R406)

Three keywords were added (33 now): while, continue, exit.
"""
import unittest

from helpers import AxionTest, run
from axionlang.engine.lexer import KEYWORDS


def fix_of(out):
    return next((line[5:] for line in out if line.startswith("Fix: ")), None)


FACT = ("function fact(n: number) -> number\n"
        "  if n <= 1\n"
        "    return 1\n"
        "  end\n"
        "  return n * fact(n - 1)\n"
        "end\n")
DOWN = ("function down(n: number) -> number\n"
        "  if n == 0\n"
        "    return 0\n"
        "  end\n"
        "  return 1 + down(n - 1)\n"
        "end\n")


class WhileLoop(AxionTest):
    def test_counts(self):
        self.assertOutput("i = 0\nwhile i < 3\n  print i\n  i = i + 1\nend", ["0", "1", "2"])

    def test_zero_passes(self):
        self.assertOutput("i = 5\nwhile i < 3\n  i = i + 1\nend\nprint i", ["5"])

    def test_unknown_number_of_repeats(self):
        # how many years until the money doubles: the task for which while was taken
        source = ("money = 1000\nyears = 0\nwhile money < 2000\n  money = money * 1.07\n"
                  "  years = years + 1\nend\nprint years")
        self.assertOutput(source, ["11"])

    def test_digits_of_a_number(self):
        source = ("n = 4096\ntotal = 0\nwhile n > 0\n  total = total + n % 10\n  n = n // 10\nend\n"
                  "print total")
        self.assertOutput(source, ["19"])

    def test_greatest_common_divisor(self):
        source = "a = 84\nb = 36\nwhile b != 0\n  rest = a % b\n  a = b\n  b = rest\nend\nprint a"
        self.assertOutput(source, ["12"])

    def test_merging_two_sorted_lists(self):
        source = ("a = [1, 4, 9]\nb = [2, 3, 10, 11]\nout = [] of number\ni = 0\nj = 0\n"
                  "while i < a length and j < b length\n"
                  "  if a[i] <= b[j]\n    out add a[i]\n    i = i + 1\n"
                  "  else\n    out add b[j]\n    j = j + 1\n  end\nend\n"
                  "while i < a length\n  out add a[i]\n  i = i + 1\nend\n"
                  "while j < b length\n  out add b[j]\n  j = j + 1\nend\nprint out")
        self.assertOutput(source, ["[1, 2, 3, 4, 9, 10, 11]"])

    def test_a_list_that_shrinks(self):
        self.assertOutput("xs = [3, 1]\nwhile xs length > 0\n  print xs[0]\n  xs remove index 0\nend",
                          ["3", "1"])

    def test_while_true_with_break(self):
        source = "i = 0\nwhile true\n  i = i + 1\n  if i > 3\n    break\n  end\nend\nprint i"
        self.assertOutput(source, ["4"])

    def test_break_leaves_only_the_nearest_loop(self):
        source = ("i = 0\nwhile i < 2\n  for x in [1, 2, 3]\n    if x == 2\n      break\n    end\n"
                  "    print x\n  end\n  i = i + 1\nend")
        self.assertOutput(source, ["1", "1"])

    def test_inside_a_function_with_return(self):
        source = ("function first_power(limit: number) -> number\n  p = 1\n  while true\n"
                  "    if p > limit\n      return p\n    end\n    p = p * 2\n  end\nend\n"
                  "print first_power(100)")
        self.assertOutput(source, ["128"])

    def test_a_variable_of_the_body_is_gone_after_end(self):
        out = self.assertError("n = 10\nwhile n > 0\n  n = n - 3\n  last = n\nend\nprint last", "V304")
        self.assertIn("last was created inside the while at line 2 and does not exist outside it.", out)

    def test_each_pass_starts_with_a_clean_block(self):
        source = "i = 0\nwhile i < 2\n  seen = i * 10\n  print seen\n  i = i + 1\nend"
        self.assertOutput(source, ["0", "10"])

    def test_condition_must_be_bool(self):
        out = self.assertError("x = 3\nwhile x\n  x = x - 1\nend", "V307")
        self.assertEqual(fix_of(out), "while x > 0")

    def test_while_one_is_while_true(self):
        out = self.assertError("while 1\n  break\nend", "V307")
        self.assertEqual(fix_of(out), "while true")

    def test_empty_body(self):
        out = self.assertError("x = 1\nwhile x < 3\nend", "V306")
        self.assertIn("The while body is empty.", out)

    def test_needs_a_condition(self):
        self.assertError("while\n  print 1\nend", "P202")

    def test_no_else(self):
        out = self.assertError("i = 0\nwhile i < 3\n  i = i + 1\nelse\n  print i\nend", "P211")
        self.assertIn("else cannot be used in a while loop.", out)

    def test_missing_end(self):
        out = self.assertError("i = 5\nwhile i > 0\n  i = i - 1\nprint i", "P216")
        self.assertIn("that while has no end yet", " ".join(out))

    def test_never_closed(self):
        out = self.assertError("i = 5\nwhile i > 0\ni = i - 1", "P212")
        self.assertIn("while is never closed", " ".join(out))

    def test_while_is_a_keyword_now(self):
        self.assertEqual(len(KEYWORDS), 33)
        for word in ("while", "continue", "exit"):
            self.assertIn(word, KEYWORDS)
            self.assertError(f"{word} = 1\nprint {word}", "P214")

    def test_a_broken_header_does_not_hide_other_lines(self):
        out = self.assertErrors("i = 0\nwhile i < < 3\n  i = = 1\nend\nprint i", ["P202", "P202"])
        self.assertEqual(len([line for line in out if line.startswith("ERROR")]), 2)


class WhileGuardBeforeTheRun(AxionTest):
    def test_the_body_changes_nothing_of_the_condition(self):
        out = self.assertError("i = 0\nn = 3\nwhile i < n\n  print i\nend", "V328")
        self.assertIn("This while can never stop: the body does not change i or n and has no break.", out)
        self.assertEqual(fix_of(out), "change i inside the loop, for example i = i + 1, "
                                      "or leave the loop with break")

    def test_the_fix_runs(self):
        self.assertOutput("i = 0\nn = 3\nwhile i < n\n  print i\n  i = i + 1\nend", ["0", "1", "2"])

    def test_nothing_runs(self):
        code, out = run('print "start"\ni = 0\nwhile i < 3\n  print i\nend')
        self.assertEqual(code, 1)
        self.assertNotIn("start", out)

    def test_while_true_needs_a_way_out(self):
        out = self.assertError("while true\n  print 1\nend", "V328")
        self.assertIn("This while can never stop: its condition has no variable, and the body "
                      "has no break.", out)

    def test_changing_any_variable_of_the_condition_is_enough(self):
        self.assertOutput("i = 0\nn = 3\nwhile i < n\n  n = n - 1\nend\nprint n", ["0"])

    def test_a_change_deep_inside_counts(self):
        source = "i = 0\nwhile i < 4\n  if i % 2 == 0\n    i = i + 3\n  else\n    i = i + 1\n  end\nend\nprint i"
        self.assertOutput(source, ["4"])

    def test_a_changed_field_counts(self):
        source = "job = {left: 3}\nwhile job.left > 0\n  job.left = job.left - 1\nend\nprint job.left"
        self.assertOutput(source, ["0"])

    def test_a_changed_dictionary_counts(self):
        source = ('seen = {} of number\nn = 0\nwhile not seen contains "c"\n  n = n + 1\n'
                  '  seen[["a", "b", "c"][n - 1]] = n\nend\nprint seen keys')
        self.assertOutput(source, ['["a", "b", "c"]'])

    def test_a_break_of_an_inner_loop_is_not_a_way_out(self):
        source = ("i = 0\nwhile i < 3\n  for x in [1, 2]\n    if x == 2\n      break\n    end\n"
                  "    print x\n  end\nend")
        self.assertError(source, "V328")

    def test_a_break_inside_an_if_is_a_way_out(self):
        source = "i = 0\nlimit = 2\nwhile limit > 0\n  i = i + 1\n  if i == 5\n    break\n  end\nend\nprint i"
        self.assertOutput(source, ["5"])

    def test_exit_is_a_way_out(self):
        self.assertOutput('ok = true\nwhile ok\n  print "once"\n  exit\nend', ["once"])

    def test_a_parameter_cannot_change_so_the_fix_is_a_copy(self):
        source = ("function count(n: number) -> number\n  total = 0\n  while n > 0\n"
                  "    total = total + 1\n  end\n  return total\nend\nprint count(3)")
        out = self.assertError(source, "V328")
        self.assertEqual(fix_of(out), "copy it before the loop (left = n), use the copy in the "
                                      "condition and change the copy inside the loop")

    def test_that_fix_runs(self):
        source = ("function count(n: number) -> number\n  total = 0\n  left = n\n  while left > 0\n"
                  "    total = total + 1\n    left = left - 1\n  end\n  return total\nend\nprint count(3)")
        self.assertOutput(source, ["3"])

    def test_errors_inside_the_body_are_still_reported(self):
        self.assertErrors("i = 0\nwhile i < 3\n  print j\nend", ["V328", "V303"])


class WhileGuardInTheRun(AxionTest):
    def test_the_step_limit_ends_a_loop_that_never_stops(self):
        source = "i = 0\nwhile i < 5\n  if i == 2\n    continue\n  end\n  i = i + 1\nend\nprint i"
        out = self.assertError(source, "R406", policy={"max_steps": 1000})
        self.assertIn("The program ran more than 1000 steps (the limit of the launch policy).", out)

    def test_every_pass_is_a_step(self):
        source = "i = 0\nwhile i < 100\n  i = i + 1\nend\nprint i"
        self.assertError(source, "R406", policy={"max_steps": 150})
        self.assertOutput(source, ["100"], policy={"max_steps": 250})

    def test_what_was_printed_stays(self):
        source = 'print "start"\ni = 0\nwhile true\n  i = i + 1\n  if i < 0\n    break\n  end\nend'
        self.assertError(source, "R406", printed_before=["start"], policy={"max_steps": 500})


class ContinueStatement(AxionTest):
    def test_in_for(self):
        self.assertOutput("for x in [1, 2, 3]\n  if x == 2\n    continue\n  end\n  print x\nend", ["1", "3"])

    def test_in_while(self):
        source = "i = 0\nwhile i < 4\n  i = i + 1\n  if i % 2 == 0\n    continue\n  end\n  print i\nend"
        self.assertOutput(source, ["1", "3"])

    def test_it_belongs_to_the_nearest_loop(self):
        source = ("for a in [1, 2]\n  for b in [1, 2, 3]\n    if b == 2\n      continue\n    end\n"
                  "    print a * 10 + b\n  end\nend")
        self.assertOutput(source, ["11", "13", "21", "23"])

    def test_checking_first_keeps_the_loop_flat(self):
        source = ('rows = ["4", "x", "", "6"]\ntotal = 0\nfor row in rows\n  if row == ""\n    continue\n  end\n'
                  '  if not row is number\n    print "bad: " + row\n    continue\n  end\n'
                  '  total = total + row as number\nend\nprint total')
        self.assertOutput(source, ["bad: x", "10"])

    def test_outside_a_loop(self):
        out = self.assertError("x = 1\ncontinue\nprint x", "V327")
        self.assertIn("continue works only inside a loop.", out)

    def test_a_function_called_in_a_loop_is_not_in_the_loop(self):
        self.assertError("function f()\n  continue\nend\nfor x in [1]\n  f()\n  print x\nend", "V327")

    def test_a_line_after_it_can_never_run(self):
        out = self.assertError("for x in [1]\n  print x\n  continue\n  print x\nend", "V319")
        self.assertIn("This line can never run: continue has already gone on to the next pass of "
                      "the loop.", out)

    def test_after_an_if_whose_every_branch_leaves(self):
        source = ("for x in [1, 2]\n  if x == 1\n    continue\n  else\n    break\n  end\n  print x\nend")
        out = self.assertError(source, "V319")
        self.assertIn("This line can never run: every branch above ends with break, continue or return.", out)

    def test_no_loop_else(self):
        self.assertError("for x in [1]\n  print x\nelse\n  print 0\nend", "P211")

    def test_as_a_field_name(self):
        self.assertOutput("o = {continue: 1, exit: 2, while: 3}\nprint o.continue + o.exit + o.while", ["6"])


class ExitStatement(AxionTest):
    def test_ends_the_program_normally(self):
        code, out = run('print "a"\nexit\n')
        self.assertEqual((code, out), (0, ["a"]))

    def test_checking_first_then_leaving(self):
        source = ('input rows: list of number\nif rows length == 0\n  print "no data"\n  exit\nend\n'
                  'print rows sum / rows length')
        self.assertOutput(source, ["no data"], data='{"rows": []}')
        self.assertOutput(source, ["3"], data='{"rows": [2, 4]}')

    def test_from_inside_loops(self):
        source = ('for a in [1, 2]\n  for b in [1, 2]\n    if a + b == 3\n      print "found"\n      exit\n'
                  '    end\n    print a + b\n  end\nend\nprint "never"')
        self.assertOutput(source, ["2", "found"])

    def test_a_line_after_it_can_never_run(self):
        out = self.assertError('x = 1\nif x == 1\n  print "bad"\n  exit\n  print x\nend\nprint x', "V319")
        self.assertIn("This line can never run: exit has already ended the program.", out)
        self.assertEqual(fix_of(out), "remove it, or move it before the exit")

    def test_at_the_top_level_too(self):
        self.assertError('print "a"\nexit\nprint "b"', "V319")

    def test_functions_may_be_defined_below_it(self):
        source = 'print twice(2)\nexit\nfunction twice(n: number) -> number\n  return n * 2\nend'
        self.assertOutput(source, ["4"])

    def test_not_in_a_function(self):
        source = "function check(n: number)\n  if n < 0\n    exit\n  end\n  print n\nend\ncheck(1)"
        out = self.assertError(source, "V329")
        self.assertIn("exit ends the whole program, so it works only in the main program, "
                      "not in a function.", out)

    def test_it_takes_nothing(self):
        for line in ("exit()", "exit(1)", "exit 1", 'exit "bad input"'):
            out = self.assertError(f"x = 2\nif x > 1\n  {line}\nend\nprint x", "P202")
            self.assertIn("exit is written alone: it ends the program and takes nothing.", out)
            self.assertEqual(fix_of(out), "exit")

    def test_return_in_the_main_program_points_at_exit(self):
        out = self.assertError("x = 1\nif x > 0\n  return\nend\nprint x", "V321")
        self.assertEqual(fix_of(out), "to end the program here write exit")

    def test_break_outside_a_loop_points_at_exit(self):
        out = self.assertError("x = 1\nif x > 0\n  break\nend\nprint x", "V327")
        self.assertEqual(fix_of(out), "remove it; to end the program here write exit")

    def test_an_error_before_exit_is_still_an_error(self):
        self.assertError("xs = [1]\nprint xs[3]\nexit", "R403")


class Recursion(AxionTest):
    def test_factorial(self):
        self.assertOutput(FACT + "print fact(5)\nprint fact(20)", ["120", "2432902008176640000"])

    def test_fibonacci(self):
        source = ("function fib(n: number) -> number\n  if n < 2\n    return n\n  end\n"
                  "  return fib(n - 1) + fib(n - 2)\nend\nprint fib(15)")
        self.assertOutput(source, ["610"])

    def test_the_stopping_case_as_a_value_if(self):
        source = ("function fact(n: number) -> number\n  return if n <= 1 then 1 else n * fact(n - 1)\n"
                  "end\nprint fact(6)")
        self.assertOutput(source, ["720"])

    def test_the_stopping_case_behind_and(self):
        source = ("function all_even(xs: list of number, i: number) -> bool\n"
                  "  return i >= xs length or (xs[i] % 2 == 0 and all_even(xs, i + 1))\nend\n"
                  "print all_even([2, 4, 6], 0)\nprint all_even([2, 5, 6], 0)")
        self.assertOutput(source, ["true", "false"])

    def test_two_functions_calling_each_other(self):
        source = ("function is_even(n: number) -> bool\n  if n == 0\n    return true\n  end\n"
                  "  return is_odd(n - 1)\nend\n"
                  "function is_odd(n: number) -> bool\n  if n == 0\n    return false\n  end\n"
                  "  return is_even(n - 1)\nend\nprint is_even(10)\nprint is_odd(10)")
        self.assertOutput(source, ["true", "false"])

    def test_one_stopping_case_is_enough_for_the_pair(self):
        source = ("function a(n: number) -> number\n  if n == 0\n    return 0\n  end\n  return b(n)\nend\n"
                  "function b(n: number) -> number\n  return a(n - 1) + 1\nend\nprint a(3)")
        self.assertOutput(source, ["3"])

    def test_a_function_without_a_result(self):
        source = ("function countdown(n: number)\n  print n\n  if n > 0\n    countdown(n - 1)\n  end\nend\n"
                  "countdown(2)")
        self.assertOutput(source, ["2", "1", "0"])

    def test_binary_search(self):
        source = ("function find(xs: list of number, v: number, low: number, high: number) -> number\n"
                  "  if low > high\n    return 0 - 1\n  end\n  mid = (low + high) // 2\n"
                  "  if xs[mid] == v\n    return mid\n  end\n"
                  "  if xs[mid] < v\n    return find(xs, v, mid + 1, high)\n  end\n"
                  "  return find(xs, v, low, mid - 1)\nend\n"
                  "xs = [1, 3, 5, 7, 9, 11]\nprint find(xs, 9, 0, xs length - 1)\nprint find(xs, 4, 0, xs length - 1)")
        self.assertOutput(source, ["4", "-1"])

    def test_a_list_built_on_the_way_back(self):
        source = ("function countdown(n: number) -> list of number\n  if n == 0\n    return [] of number\n  end\n"
                  "  rest = countdown(n - 1)\n  rest add n\n  return rest\nend\nprint countdown(4)")
        self.assertOutput(source, ["[1, 2, 3, 4]"])

    def test_each_call_has_its_own_variables(self):
        source = ("function depth(n: number) -> number\n  mine = n\n  if n > 0\n    below = depth(n - 1)\n"
                  "    return mine + below\n  end\n  return mine\nend\nprint depth(4)")
        self.assertOutput(source, ["10"])


class RecursionGuardBeforeTheRun(AxionTest):
    def test_no_path_without_the_call(self):
        out = self.assertError("function f(n: number) -> number\n  return f(n - 1)\nend\nprint f(3)", "V322")
        self.assertIn("f calls itself on every path, so it can never finish.", out)
        self.assertEqual(fix_of(out), "before this call add the case that stops: if ... return ... end")

    def test_every_branch_calls(self):
        source = ("function f(n: number) -> number\n  if n > 0\n    return f(n - 1)\n  else\n"
                  "    return f(n + 1)\n  end\nend\nprint f(3)")
        self.assertError(source, "V322")

    def test_the_call_comes_before_the_stopping_case(self):
        source = ("function f(n: number) -> number\n  below = f(n - 1)\n  if n == 0\n    return 0\n  end\n"
                  "  return below + 1\nend\nprint f(3)")
        self.assertError(source, "V322")

    def test_the_call_in_the_condition(self):
        source = ("function f(n: number) -> number\n  if f(n - 1) > 0\n    return 1\n  end\n  return 0\nend\n"
                  "print f(3)")
        self.assertError(source, "V322")

    def test_both_values_of_a_value_if_call(self):
        source = ("function f(n: number) -> number\n  return if n > 0 then f(n - 1) else f(n + 1)\nend\n"
                  "print f(3)")
        self.assertError(source, "V322")

    def test_a_function_without_a_result(self):
        out = self.assertError("function show(n: number)\n  print n\n  show(n - 1)\nend\nshow(3)", "V322")
        self.assertEqual(fix_of(out), "put this call inside an if, so that some path ends without it")

    def test_a_pair_without_a_stopping_case(self):
        source = ("function a(n: number) -> number\n  return b(n)\nend\n"
                  "function b(n: number) -> number\n  return a(n)\nend\nprint a(1)")
        out = self.assertErrors(source, ["V322"])            # one error for the circle, not two
        self.assertIn("a -> b -> a: these functions call each other on every path, so they can "
                      "never finish.", out)

    def test_a_function_that_only_uses_such_a_pair_is_not_blamed(self):
        source = ("function a(n: number) -> number\n  return b(n)\nend\n"
                  "function b(n: number) -> number\n  return a(n)\nend\n"
                  "function start(n: number) -> number\n  return a(n) + 1\nend\nprint start(1)")
        self.assertErrors(source, ["V322"])

    def test_nothing_runs(self):
        code, out = run('print "start"\nfunction f(n: number) -> number\n  return f(n - 1)\nend\nprint f(3)')
        self.assertEqual(code, 1)
        self.assertNotIn("start", out)

    def test_a_function_that_only_calls_itself_is_never_called(self):
        out = self.assertError(FACT + "print 1", "V305")
        self.assertIn("The function fact is never called.", out)

    def test_ordinary_calls_are_untouched(self):
        source = ("function twice(n: number) -> number\n  return n * 2\nend\n"
                  "function four(n: number) -> number\n  return twice(twice(n))\nend\nprint four(3)")
        self.assertOutput(source, ["12"])


class RecursionGuardInTheRun(AxionTest):
    def test_the_default_depth_is_200(self):
        self.assertOutput(DOWN + "print down(199)", ["199"])
        out = self.assertError(DOWN + "print down(200)", "R406")
        self.assertIn("Function calls went more than 200 deep (the limit of the launch policy).", out)
        self.assertEqual(fix_of(out), "check the case that stops down: with these values it is not reached")

    def test_a_stopping_case_that_is_never_reached(self):
        self.assertError(DOWN + "print down(0 - 1)", "R406")

    def test_what_was_printed_stays(self):
        self.assertError('print "start"\n' + DOWN + "print down(500)", "R406", printed_before=["start"])

    def test_the_launch_policy_sets_the_depth(self):
        self.assertOutput(DOWN + "print down(1000)", ["1000"], policy={"max_depth": 1500})
        self.assertError(DOWN + "print down(12)", "R406", policy={"max_depth": 10})

    def test_a_very_deep_recursion_does_not_break_the_interpreter(self):
        self.assertOutput(DOWN + "print down(4999)", ["4999"], policy={"max_depth": 5000})

    def test_the_depth_has_a_ceiling(self):
        from axionlang.engine.policy import Policy, PolicyError
        with self.assertRaises(PolicyError):
            Policy.from_dict({"max_depth": 5001})
        with self.assertRaises(PolicyError):
            Policy.from_dict({"max_depth": 0})

    def test_calls_one_after_another_are_not_depth(self):
        source = ("function one(n: number) -> number\n  return n + 1\nend\n"
                  "total = 0\nfor i in 1 to 500\n  total = one(total)\nend\nprint total")
        self.assertOutput(source, ["500"], policy={"max_depth": 2})

    def test_the_depth_is_free_again_after_an_inner_return(self):
        source = DOWN + "a = down(150)\nb = down(150)\nprint a + b"
        self.assertOutput(source, ["300"])


class UnreachableAfterWhileTrue(AxionTest):
    SOURCE = ("function first_over(limit: number) -> number\n  p = 1\n  while true\n"
              "    p = p * 2\n    if p > limit\n      return p\n    end\n  end\n{tail}end\n"
              "print first_over(10)")

    def test_no_return_is_needed_after_it(self):
        self.assertOutput(self.SOURCE.format(tail=""), ["16"])

    def test_a_line_after_it_can_never_run(self):
        out = self.assertError(self.SOURCE.format(tail="  return 0\n"), "V319")
        self.assertIn("This line can never run: the while true on line 3 has no break, so nothing "
                      "gets past it.", out)

    def test_with_a_break_the_function_needs_its_return(self):
        source = ("function first_over(limit: number) -> number\n  p = 1\n  while true\n"
                  "    p = p * 2\n    if p > limit\n      break\n    end\n  end\nend\nprint first_over(10)")
        self.assertError(source, "V318")


if __name__ == "__main__":
    unittest.main()
