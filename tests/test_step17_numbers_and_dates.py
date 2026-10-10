"""Axion v0.3, step 3: rounding, powers, dates.

Decisions 7, 16 and 18 of the v0.3 design (2026-10-05):

    x round 2        the school rule: a five goes away from zero
    x floor          down to a whole number        x ceiling     up to a whole number
    x ** n           a power; a root is the power 0.5
    s is date        "2026-10-05" is a date?
    s as days        a date to a number of days (from 1970-01-01)
    n as date        a number of days back to a date

Before v0.3 nothing could cut a fraction (10 / 3 printed 28 digits), a root could not be
computed at all, and a difference of two dates was thirty lines by hand.

One rule was found while building this and is checked here: a rounding at the right end
of a calculation (`total / count round 2`) binds to `count` alone and would round nothing,
silently. Axion refuses it and shows the line with parentheses.
"""
import unittest
from decimal import ROUND_HALF_UP, Decimal

from helpers import AxionTest, run


def fix_of(out):
    return next((line[5:] for line in out if line.startswith("Fix: ")), None)


class Rounding(AxionTest):
    def test_places(self):
        self.assertOutput("x = 10 / 3\nprint x round 2\nprint x round 0\nprint x round 5", ["3.33", "3", "3.33333"])

    def test_a_five_goes_away_from_zero(self):
        source = ("print 2.5 round 0\nprint 3.5 round 0\nprint 0.5 round 0\nprint 2.345 round 2\n"
                  "print 2.675 round 2\nprint 1.005 round 2\nprint (0 - 2.5) round 0\nprint (0 - 2.345) round 2")
        self.assertOutput(source, ["3", "4", "1", "2.35", "2.68", "1.01", "-3", "-2.35"])

    def test_below_five_goes_down(self):
        self.assertOutput("print 2.344 round 2\nprint 2.49 round 0\nprint (0 - 2.4) round 0", ["2.34", "2", "-2"])

    def test_it_agrees_with_decimal_half_up_everywhere(self):
        for text in ("0.125", "0.135", "1.5", "2.5", "-0.125", "99.995", "1234.5678", "0.049", "5", "-7.5"):
            for places in (0, 1, 2, 3):
                expected = Decimal(text).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
                code, out = run(f"x = 0 + ({text})\nprint x round {places}")
                self.assertEqual((code, Decimal(out[0])), (0, expected), (text, places))

    def test_the_result_is_a_number(self):
        self.assertOutput("x = 2.567 round 2\nprint x + 1\nprint x * 100", ["3.57", "257"])

    def test_no_trailing_zeros(self):
        # a number prints without them; showing exactly two places is not in v0.3 (decision 8)
        self.assertOutput("print 3.5 round 2\nprint 2 round 2\nprint 2.999 round 2", ["3.5", "2", "3"])

    def test_more_places_than_the_number_has(self):
        self.assertOutput("print 1.25 round 10\nprint 1.25 round 100", ["1.25", "1.25"])

    def test_floor_and_ceiling(self):
        source = ("print 7.5 floor\nprint 7.5 ceiling\nprint (0 - 7.5) floor\nprint (0 - 7.5) ceiling\n"
                  "print 5 floor\nprint 5 ceiling\nprint 0.001 ceiling\nprint 0.999 floor")
        self.assertOutput(source, ["7", "8", "-8", "-7", "5", "5", "1", "0"])

    def test_pages_boxes_hours(self):
        self.assertOutput("print (41 / 10) ceiling\nprint (40 / 10) ceiling", ["5", "4"])
        self.assertOutput("h = 7.75\nprint h floor\nprint (h - (h floor)) * 60", ["7", "45"])

    def test_places_from_a_variable(self):
        self.assertOutput("p = 1\nprint 2.55 round p", ["2.6"])

    def test_places_must_be_a_whole_number_from_zero(self):
        self.assertError("print 5 round 1.5", "V312")
        self.assertError("print 5 round (-1)", "V312")
        out = self.assertError("p = 0 - 1\nprint 5 round p", "R402")
        self.assertIn("The number of places is a whole number, 0 or greater: p is -1.", out)

    def test_round_needs_its_places(self):
        out = self.assertError("x = 5\nprint x round", "P202")
        self.assertIn("round needs the number of places after it.", out)
        self.assertTrue(fix_of(out).startswith("print x round 0"))

    def test_only_numbers(self):
        out = self.assertError('print "3.14159" round 2', "V301")
        self.assertEqual(fix_of(out), 'convert first: "3.14159" as number')
        self.assertError('print "a" floor', "V301")
        self.assertError("print [1.5] ceiling", "V301")

    def test_the_words_stay_names(self):
        self.assertOutput("round = 1\nfloor = 2\nceiling = 3\nprint round + floor + ceiling", ["6"])


class RoundingAtTheEndOfACalculation(AxionTest):
    def test_a_division_then_round(self):
        out = self.assertError("total = 10\ncount = 3\naverage = total / count round 2\nprint average", "V301")
        self.assertIn("round here would apply only to count, the value right before it. "
                      "Put in parentheses what is to be rounded.", out)
        self.assertEqual(fix_of(out), "average = (total / count) round 2"
                                      "   (or, to round only that value: (count round 2))")
        self.assertOutput("total = 10\ncount = 3\naverage = (total / count) round 2\nprint average", ["3.33"])

    def test_inside_a_printed_line(self):
        source = 'total = 10\ncount = 3\nprint "Average: " + total / count round 2 as text'
        out = self.assertError(source, "V301")
        self.assertTrue(fix_of(out).startswith('print "Average: " + (total / count) round 2 as text   (or'))
        self.assertOutput(source.replace("total / count round", "(total / count) round"), ["Average: 3.33"])

    def test_the_whole_calculation_is_wrapped_at_once(self):
        out = self.assertError("price = 100\nyears = 10\nprint price * 1.07 ** years round 2", "V301")
        self.assertTrue(fix_of(out).startswith("print (price * 1.07 ** years) round 2   (or"))
        self.assertOutput("price = 100\nyears = 10\nprint (price * 1.07 ** years) round 2", ["196.72"])

    def test_floor_and_ceiling_too(self):
        self.assertEqual(fix_of(self.assertError("x = 7.5\nprint 10 - x floor", "V301")),
                         "print (10 - x) floor   (or, to round only that value: (x floor))")
        self.assertTrue(fix_of(self.assertError("n = 41\nprint n / 10 ceiling", "V301"))
                        .startswith("print (n / 10) ceiling   (or"))

    def test_both_readings_run(self):
        self.assertOutput("x = 7.5\nprint (10 - x) floor\nprint 10 - (x floor)", ["2", "3"])

    def test_what_is_already_clear_is_accepted(self):
        source = ('x = 2.567\nprint "x: " + x round 2 as text\nprint x round 2 + 1\nprint 1 + (x round 1)\n'
                  'if x round 0 > 2\n  print "big"\nend\nprint (41 / 10) ceiling * 10')
        self.assertOutput(source, ["x: 2.57", "3.57", "3.6", "big", "50"])

    def test_round_then_as_text_is_the_chain(self):
        self.assertOutput('t = 3.14159\nprint "pi " + t round 2 as text', ["pi 3.14"])


class Powers(AxionTest):
    def test_whole_powers_are_exact(self):
        self.assertOutput("print 2 ** 10\nprint 3 ** 0\nprint 1.5 ** 2\nprint 10 ** 20", ["1024", "1", "2.25", "100000000000000000000"])

    def test_roots(self):
        self.assertOutput("print 16 ** 0.5\nprint 2 ** 0.5\nprint (27 ** (1 / 3)) round 6",
                          ["4", "1.414213562373095048801688724", "3"])

    def test_negative_powers(self):
        self.assertOutput("print 10 ** (0 - 2)\nprint 2 ** (-1)", ["0.01", "0.5"])

    def test_it_binds_tighter_than_times_and_minus(self):
        self.assertOutput("print 2 * 3 ** 2\nprint 0 - 2 ** 2\nprint (0 - 2) ** 2\nprint -2 ** 2", ["18", "-4", "4", "-4"])

    def test_it_groups_to_the_right(self):
        self.assertOutput("print 2 ** 3 ** 2\nprint (2 ** 3) ** 2", ["512", "64"])

    def test_compound_interest_and_distance(self):
        self.assertOutput("print (1000 * 1.07 ** 10) round 2", ["1967.15"])
        self.assertOutput("dx = 3\ndy = 4\nprint (dx ** 2 + dy ** 2) ** 0.5", ["5"])

    def test_zero_to_zero_is_one(self):
        self.assertOutput("print 0 ** 0\nz = 0\nprint z ** z", ["1", "1"])

    def test_a_root_of_a_negative_number(self):
        self.assertError("print (-4) ** 0.5", "V312")
        out = self.assertError("x = 0 - 4\nprint x ** 0.5", "R412")
        self.assertIn("A negative number has no root: x is -4 and the power is 0.5.", out)
        self.assertEqual(fix_of(out), "check first: if x >= 0")

    def test_zero_to_a_negative_power(self):
        self.assertError("print 0 ** (-1)", "V312")
        self.assertError("z = 0\nprint z ** (0 - 1)", "R401")

    def test_too_large(self):
        out = self.assertError("print 10 ** 2000000", "R412")
        self.assertIn("The result of ** is too large for a number.", out)

    def test_only_numbers(self):
        self.assertError('print "a" ** 2', "V301")

    def test_minus_right_after_it_needs_parentheses(self):
        self.assertError("print 2 ** -1", "P207")

    def test_caret_and_functions_of_other_languages(self):
        self.assertEqual(fix_of(self.assertError("print 2 ^ 10", "L101")), "print 2 ** 10")
        for written, fixed, expected in (
                ("print sqrt(x) + 1", "print (x ** 0.5) + 1", "5"),
                ("print pow(x, 2)", "print (x ** 2)", "256"),
                ("print round(x / 3, 2)", "print ((x / 3) round 2)", "5.33"),
                ("print round(x / 3)", "print ((x / 3) round 0)", "5"),
                ("print 100 - floor(x / 3)", "print 100 - ((x / 3) floor)", "95"),
                ("print ceil(x / 3)", "print ((x / 3) ceiling)", "6"),
                ("print abs(x - 20)", "print (if (x - 20) < 0 then 0 - (x - 20) else (x - 20))", "4"),
                ("print int(x / 3)", "print ((x / 3) floor)", "5")):
            out = self.assertError(f"x = 16\n{written}", "V303")
            self.assertEqual(fix_of(out), fixed, written)
            self.assertOutput(f"x = 16\n{fixed}", [expected])

    def test_the_math_library(self):
        out = self.assertError("x = 16\nprint math.sqrt(x) + math.floor(x / 3)", "P210")
        self.assertEqual(fix_of(out), "print (x ** 0.5) + ((x / 3) floor)")
        self.assertOutput("x = 16\nprint (x ** 0.5) + ((x / 3) floor)", ["9"])
        self.assertIn("Axion has no math library", fix_of(self.assertError("print math.sin(1)", "P210")))


class Dates(AxionTest):
    def test_is_date(self):
        source = ('for s in ["2026-10-05", "2024-02-29", "2026-02-29", "2026-13-01", "2026-1-5", '
                  '"05.10.2026", "", "2026-10-05 ", "0000-01-01"]\n  print s is date\nend')
        self.assertOutput(source, ["true", "true", "false", "false", "false", "false", "false", "false", "false"])

    def test_days_from_1970(self):
        self.assertOutput('print "1970-01-01" as days\nprint "1970-01-02" as days\nprint "1969-12-31" as days\n'
                          'print "2026-10-05" as days', ["0", "1", "-1", "20731"])

    def test_back_to_a_date(self):
        self.assertOutput("print 0 as date\nprint 20731 as date\nprint (0 - 1) as date",
                          ["1970-01-01", "2026-10-05", "1969-12-31"])

    def test_there_and_back(self):
        for day in ("2000-02-29", "1999-12-31", "2026-10-05", "0001-01-01", "9999-12-31"):
            self.assertOutput(f'print "{day}" as days as date', [day])

    def test_difference_and_adding_days(self):
        self.assertOutput('print "2026-10-05" as days - "2026-01-01" as days', ["277"])
        self.assertOutput('print ("2026-10-05" as days + 30) as date', ["2026-11-04"])
        self.assertOutput('print ("2024-02-28" as days + 1) as date\nprint ("2025-02-28" as days + 1) as date',
                          ["2024-02-29", "2025-03-01"])

    def test_day_of_the_week(self):
        # 0 is Monday: (days + 3) % 7
        names = '["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]'
        source = f'names = {names}\nfor d in ["2026-10-05", "1970-01-01", "2026-10-11", "1969-12-28"]\n' \
                 '  print names[(d as days + 3) % 7]\nend'
        self.assertOutput(source, ["Mon", "Thu", "Sun", "Sun"])

    def test_age_and_order_and_month(self):
        source = ('born = "1999-03-15"\ntoday = "2026-10-05"\nb = born split "-"\nt = today split "-"\n'
                  'age = t[0] as number - b[0] as number\n'
                  'if t[1] + t[2] < b[1] + b[2]\n  age = age - 1\nend\nprint age\n'
                  'print today > born\nprint today[0 to 6]')
        self.assertOutput(source, ["27", "true", "2026-10"])

    def test_not_a_date_at_run_time(self):
        out = self.assertError('d = "2026-13-01"\nprint d as days', "R413")
        self.assertIn('"2026-13-01" is not a date (year-month-day, like 2026-10-05).', out)
        self.assertEqual(fix_of(out), "check first: if d is date")
        self.assertOutput('d = "2026-13-01"\nprint if d is date then d as days else 0', ["0"])

    def test_not_a_date_written_in_the_program(self):
        out = self.assertError('print "05.10.2026" as days', "V311")
        self.assertIn('"05.10.2026" is not a date.', out)

    def test_wrong_types(self):
        self.assertIn("5 as date", fix_of(self.assertError("print 5 as days", "V311")))
        self.assertIn("is date", fix_of(self.assertError('print "2026-10-05" as date', "V311")))
        self.assertError("print 5 is date", "V311")
        self.assertError("print true as date", "V311")

    def test_days_must_be_whole_and_inside_the_calendar(self):
        self.assertError("print 1.5 as date", "R413")
        out = self.assertError("print 99999999 as date", "R413")
        self.assertIn("outside the calendar", out[3])

    def test_is_not_date(self):
        out = self.assertError('s = "x"\nif s is not date\n  print 1\nend', "P202")
        self.assertEqual(fix_of(out), "if not s is date")
        self.assertOutput('s = "x"\nif not s is date\n  print 1\nend', ["1"])

    def test_date_and_days_stay_names(self):
        self.assertOutput('date = "2026-10-05"\ndays = date as days\nprint days as date == date', ["true"])

    def test_number_conversions_are_unchanged(self):
        self.assertOutput('print "42" as number + 1\nprint 5 as text + "!"\nprint "x" is number', ["43", "5!", "false"])


if __name__ == "__main__":
    unittest.main()
