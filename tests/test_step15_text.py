"""Axion v0.3, step 1: text.

Until v0.3 a text could be joined, measured, compared with == and turned into a number,
and nothing else: it could not be taken apart, searched or put in order. Of the ten text
skills on the list of a middle developer one was expressible. Decisions 1-4 of the v0.3
design (2026-10-05):

1. `s split sep`, `s[i]`, `s[a to b]` (both ends included; the same for lists);
2. `s contains part` / `xs contains v`, `s starts with p`, `s ends with p`;
3. `s lower`, `s upper`, `s trim`;
4. text has an order: character by character, by character code.

Each is a word after a value, as `length` and `sum` are; elsewhere the words stay names.
"""
import unittest

from helpers import AxionTest, run

from axionlang.engine.lexer import KEYWORDS


def fix_of(out):
    return next((line[5:] for line in out if line.startswith("Fix: ")), None)


class Split(AxionTest):
    def test_words(self):
        self.assertOutput('print "ERROR 14:02 disk full" split " "', ['["ERROR", "14:02", "disk", "full"]'])

    def test_it_is_the_inverse_of_join(self):
        self.assertOutput('s = "a, b, c"\nprint (s split ", ") join ", " == s', ["true"])

    def test_a_log_line_taken_apart(self):
        source = ('line = "ERROR 14:02 disk full"\nparts = line split " "\n'
                  'time = parts[1] split ":"\nprint time[0] as number + 1')
        self.assertOutput(source, ["15"])

    def test_separator_of_several_characters(self):
        self.assertOutput('print "a => b => c" split " => "', ['["a", "b", "c"]'])

    def test_no_separator_in_the_text_gives_one_part(self):
        self.assertOutput('print "abc" split ","', ['["abc"]'])

    def test_empty_text_gives_one_empty_part(self):
        self.assertOutput('print "" split ","\nprint ("" split ",") length', ['[""]', "1"])

    def test_separators_side_by_side_give_empty_parts(self):
        # nothing is guessed away: two spaces are two separators
        self.assertOutput('print "a  b" split " "', ['["a", "", "b"]'])
        self.assertOutput('print ",a," split ","', ['["", "a", ""]'])

    def test_replacing_is_split_and_join(self):
        self.assertOutput('print ("2026-10-05" split "-") join "/"', ["2026/10/05"])

    def test_chained_after_other_words(self):
        self.assertOutput('print " A,b " trim lower split ","', ['["a", "b"]'])
        self.assertOutput('print "a b c" split " " length', ["3"])

    def test_separator_from_a_variable_or_a_field(self):
        self.assertOutput('o = {sep: "-"}\nprint "a-b" split o.sep', ['["a", "b"]'])

    def test_the_separator_is_required(self):
        out = self.assertError('s = "a b"\nprint s split', "P202")
        self.assertIn("split needs a value after it.", out)

    def test_empty_separator_written_in_the_program(self):
        out = self.assertError('s = "ab"\nprint s split ""', "V312")
        self.assertIn("The separator of split cannot be empty.", out)
        self.assertEqual(fix_of(out), "to go over the characters write: for ch in s")

    def test_empty_separator_at_run_time(self):
        out = self.assertError('s = "ab"\nsep = ""\nprint s split sep', "R410")
        self.assertIn('The separator of split cannot be empty: sep is "".', out)

    def test_only_text_is_split(self):
        self.assertError("print 5 split \",\"", "V301")
        self.assertError('print "a1b" split 1', "V301")

    def test_a_list_of_text_was_meant_to_be_joined(self):
        out = self.assertError('words = ["a", "b"]\nprint words split ", "', "V301")
        self.assertEqual(fix_of(out), 'print words join ", "')

    def test_an_index_right_after_the_separator_is_not_guessed(self):
        out = self.assertError('line = "a b"\nfirst = line split " "[0]\nprint first', "P202")
        self.assertIn("Put split and its value in parentheses before taking an element or a field.", out)
        self.assertEqual(fix_of(out), 'first = (line split " ")[0]')
        self.assertOutput('line = "a b"\nfirst = (line split " ")[0]\nprint first', ["a"])

    def test_an_indexed_variable_as_separator_is_fine(self):
        self.assertOutput('seps = ["-", "+"]\nprint "a+b" split seps[1]', ['["a", "b"]'])

    def test_the_result_obeys_the_list_limit(self):
        code, out = run('print ("a,b,c,d" split ",") length', policy={"max_list_size": 3})
        self.assertEqual(code, 1)
        self.assertTrue(out[0].startswith("ERROR R406"))


class Positions(AxionTest):
    def test_one_character(self):
        self.assertOutput('s = "hello"\nprint s[0]\nprint s[4]\nprint s[s length - 1]', ["h", "o", "o"])

    def test_a_character_is_text(self):
        self.assertOutput('s = "ab"\nprint s[0] + s[1] + "!"\nprint s[0] == "a"', ["ab!", "true"])

    def test_outside_the_text(self):
        out = self.assertError('s = "hello"\nprint s[5]', "R403")
        self.assertIn("Index 5 is out of range: s has 5 characters (valid: 0 to 4).", out)
        self.assertIn("it is empty", self.assertError('s = ""\nprint s[0]', "R403")[3])

    def test_negative_position_counts_from_nowhere(self):
        out = self.assertError('s = "hello"\nprint s[-1]', "V313")
        self.assertEqual(fix_of(out), "print s[s length - 1]")
        self.assertOutput('s = "hello"\nprint s[s length - 1]', ["o"])
        self.assertEqual(fix_of(self.assertError("xs = [1, 2, 3]\nlast = xs[-2]\nprint last", "V313")),
                         "last = xs[xs length - 2]")

    def test_a_position_is_a_whole_number(self):
        self.assertError('s = "abc"\nprint s[1.5]', "V313")
        self.assertError('s = "abc"\nprint s["0"]', "V301")
        self.assertError('s = "abc"\ni = 0.5\nprint s[i]', "R402")

    def test_text_is_not_changed_in_place(self):
        out = self.assertError('s = "hello"\ns[0] = "j"\nprint s', "V301")
        self.assertIn("Text cannot be changed in place.", out)
        self.assertOutput('s = "hello"\ns = "j" + s[1 to s length - 1]\nprint s', ["jello"])

    def test_a_number_still_has_no_positions(self):
        out = self.assertError("x = 5\nprint x[0]", "V301")
        self.assertIn("Only lists, text and dictionaries are read with [ ], got number.", out)


class Pieces(AxionTest):
    def test_both_ends_are_included(self):
        self.assertOutput('s = "ERROR 14:02"\nprint s[0 to 4]\nprint s[6 to 7]', ["ERROR", "14"])

    def test_up_to_the_end(self):
        self.assertOutput('s = "hello"\nprint s[1 to s length - 1]', ["ello"])

    def test_one_position_wide(self):
        self.assertOutput('s = "hello"\nprint s[2 to 2]', ["l"])

    def test_a_computed_empty_piece(self):
        # the first n characters, for n = 0: the same rule as a computed empty range
        self.assertOutput('s = "hello"\nn = 0\nprint s[0 to n - 1] == ""\nprint s[0 to n - 1] length',
                          ["true", "0"])

    def test_a_written_empty_piece_is_a_mistake(self):
        self.assertError('s = "hello"\nprint s[3 to 1]', "V317")

    def test_outside_the_text(self):
        out = self.assertError('s = "hello"\nprint s[3 to 9]', "R403")
        self.assertIn("The piece 3 to 9 is out of range: s has 5 characters (valid: 0 to 4).", out)
        self.assertEqual(fix_of(out), "check first: if s length > 9")

    def test_negative_start(self):
        self.assertError('s = "hello"\nprint s[-2 to 3]', "V313")
        self.assertError('s = "hello"\nprint s[(-2) to 3]', "V313")
        self.assertError('s = "hello"\na = 0 - 2\nprint s[a to 3]', "R403")

    def test_fraction_as_a_bound(self):
        self.assertError('s = "hello"\nprint s[0.5 to 2]', "V317")
        self.assertError('s = "hello"\na = 0.5\nprint s[a to 2]', "R402")

    def test_a_piece_of_a_list(self):
        self.assertOutput("xs = [5, 6, 7, 8]\nprint xs[1 to 2]\nprint xs[0 to 0]", ["[6, 7]", "[5]"])

    def test_a_piece_of_a_list_is_a_copy(self):
        self.assertOutput("xs = [[1], [2], [3]]\nys = xs[0 to 1]\nys[0] add 9\nprint xs\nprint ys",
                          ["[[1], [2], [3]]", "[[1, 9], [2]]"])

    def test_first_three_of_a_sorted_list(self):
        self.assertOutput("xs = [5, 1, 9, 7]\nprint (xs sort descending)[0 to 2]", ["[9, 7, 5]"])

    def test_a_piece_of_a_list_outside(self):
        out = self.assertError("xs = [5, 6]\nprint xs[0 to 2]", "R403")
        self.assertIn("The piece 0 to 2 is out of range: xs has 2 elements (valid: 0 to 1).", out)

    def test_a_piece_cannot_be_assigned(self):
        out = self.assertError("xs = [1, 2, 3]\nxs[0 to 1] = [9, 9]\nprint xs", "V301")
        self.assertIn("A piece cannot be assigned to.", out)

    def test_python_slices_are_rewritten(self):
        for written, fixed in (("print s[0:3]", "print s[0 to 2]"),
                               ("print s[:2]", "print s[0 to 1]"),
                               ("print s[1:]", "print s[1 to s length - 1]"),
                               ("print s[1:n]", "print s[1 to n - 1]")):
            out = self.assertError(f's = "hello"\nn = 4\n{written}\nprint n', "P202")
            self.assertIn("A piece is written with to, and to includes its last position.", out)
            self.assertEqual(fix_of(out), fixed)
            code, result = run(f's = "hello"\nn = 4\n{fixed}\nprint n')
            self.assertEqual(code, 0, result)

    def test_python_slices_give_the_same_text_as_in_python(self):
        s = "hello"
        for written, fixed, expected in (("s[0:3]", "s[0 to 2]", s[0:3]), ("s[:2]", "s[0 to 1]", s[:2]),
                                         ("s[1:]", "s[1 to s length - 1]", s[1:])):
            self.assertOutput(f's = "hello"\nprint {fixed}', [expected])

    def test_a_slice_from_the_end_gets_the_general_hint(self):
        out = self.assertError('s = "hello"\nprint s[-3:]', "P202")
        self.assertEqual(fix_of(out), "s[first to last]   (both ends are included)")


class Contains(AxionTest):
    def test_text_in_text(self):
        self.assertOutput('line = "disk full"\nprint line contains "disk"\nprint line contains "ram"',
                          ["true", "false"])

    def test_the_empty_text_is_in_every_text(self):
        self.assertOutput('print "abc" contains ""', ["true"])

    def test_case_matters(self):
        self.assertOutput('print "Disk" contains "disk"\nprint "Disk" lower contains "disk"', ["false", "true"])

    def test_value_in_a_list(self):
        self.assertOutput("xs = [5, 6, 7]\nprint xs contains 7\nprint xs contains 9", ["true", "false"])
        self.assertOutput('seen = ["a"]\nk = "a"\nprint seen contains k', ["true"])

    def test_objects_and_lists_as_elements(self):
        self.assertOutput('ps = [{n: "a", p: 1}]\nprint ps contains {n: "a", p: 1}\n'
                          'print ps contains {n: "a", p: 2}', ["true", "false"])
        self.assertOutput("xs = [[1, 2], [3]]\nprint xs contains [3]", ["true"])

    def test_negated_like_is_number(self):
        self.assertOutput("xs = [5]\nif not xs contains 9\n  print 1\nend", ["1"])

    def test_inside_conditions(self):
        source = 'a = ["x"]\nb = "xyz"\nif a contains "x" and b contains "y"\n  print "both"\nend'
        self.assertOutput(source, ["both"])

    def test_the_seen_so_far_pattern(self):
        source = ('seen = [] of number\nfor x in [3, 1, 3, 7, 1]\n  if not seen contains x\n'
                  '    seen add x\n  end\nend\nprint seen')
        self.assertOutput(source, ["[3, 1, 7]"])

    def test_a_field_as_the_value(self):
        self.assertOutput('r = {key: "k1"}\nseen = ["k1"]\nprint seen contains r.key', ["true"])

    def test_the_type_of_the_value_is_checked(self):
        out = self.assertError('xs = ["a"]\nprint xs contains 1', "V310")
        self.assertIn("xs holds text; it cannot contain number.", out)
        out = self.assertError('s = "a1"\nn = 1\nprint s contains n', "V301")
        self.assertEqual(fix_of(out), "print s contains (n as text)")
        self.assertOutput('s = "a1"\nn = 1\nprint s contains (n as text)', ["true"])

    def test_words_chain_from_left_to_right(self):
        # One rule for every word that takes a value (join, split, contains, round, ...):
        # the value is the one thing right after the word, and what follows goes on with
        # the result. So `xs contains 1 as text` is the answer as text.
        self.assertOutput('xs = [1, 2]\nprint "has: " + xs contains 1 as text', ["has: true"])
        self.assertOutput('print "a b c" split " " length', ["3"])
        self.assertOutput('print ["a", "b"] join "-" upper', ["A-B"])

    def test_a_converted_value_goes_in_parentheses(self):
        out = self.assertError('keys = ["1", "2"]\nn = 2\nprint keys contains n', "V310")
        self.assertEqual(fix_of(out), "print keys contains (n as text)")
        self.assertOutput('keys = ["1", "2"]\nn = 2\nprint keys contains (n as text)', ["true"])
        out = self.assertError('ids = [1, 2]\ns = "2"\nprint ids contains s', "V310")
        self.assertEqual(fix_of(out), "print ids contains (s as number)")

    def test_only_text_and_lists(self):
        out = self.assertError("n = 5\nprint n contains 5", "V301")
        self.assertIn("contains works on text, lists and dictionaries, got number.", out)

    def test_a_value_is_required(self):
        self.assertIn("contains needs a value after it.", self.assertError("xs = [1]\nprint xs contains", "P202"))

    def test_in_from_python_is_rewritten(self):
        for written, fixed in (("if x in xs", "if xs contains x"),
                               ("if not x in xs", "if not xs contains x"),
                               ("if x not in xs", "if not xs contains x"),
                               ("if r.key in xs", "if xs contains r.key"),
                               ('if "b" in s', 'if s contains "b"')):
            source = (f'xs = ["a"]\ns = "abc"\nx = "a"\nr = {{key: "a"}}\n{written}\n  print 1\n'
                      f'else\n  print 2\nend\nprint s + x + r.key + xs[0]')
            out = self.assertError(source, "P202")
            self.assertEqual(fix_of(out), fixed)
            code, result = run(source.replace(written, fixed))
            self.assertEqual(code, 0, result)

    def test_the_for_header_keeps_its_in(self):
        self.assertOutput('for x in ["a"]\n  print x\nend', ["a"])


class StartsAndEnds(AxionTest):
    def test_starts_with(self):
        self.assertOutput('name = "Dr. Who"\nprint name starts with "Dr."\nprint name starts with "Mr."',
                          ["true", "false"])

    def test_ends_with(self):
        self.assertOutput('f = "notes.txt"\nprint f ends with ".txt"\nprint f ends with ".md"', ["true", "false"])

    def test_a_short_text_is_simply_false(self):
        # through a piece this would stop the program: s[0 to 2] on a two-character text
        self.assertOutput('print "ab" starts with "abc"\nprint "" ends with ".txt"', ["false", "false"])

    def test_the_whole_text_and_the_empty_text(self):
        self.assertOutput('print "ab" starts with "ab"\nprint "ab" ends with ""', ["true", "true"])

    def test_negated_and_combined(self):
        self.assertOutput('f = "a.txt"\nif not f starts with "." and f ends with ".txt"\n  print "ok"\nend', ["ok"])

    def test_with_is_required(self):
        out = self.assertError('s = "abc"\nprint s starts "a"', "P202")
        self.assertIn("starts is followed by with.", out)
        self.assertEqual(fix_of(out), 'print s starts with "a"')

    def test_only_text(self):
        self.assertError('print 123 starts with "1"', "V301")
        self.assertError('print "123" ends with 3', "V301")


class CaseAndSpaces(AxionTest):
    def test_lower_and_upper(self):
        self.assertOutput('print "AbC" lower\nprint "AbC" upper', ["abc", "ABC"])

    def test_other_alphabets(self):
        self.assertOutput('print "Привет" upper\nprint "ÉCOLE" lower', ["ПРИВЕТ", "école"])

    def test_comparison_without_case(self):
        self.assertOutput('a = "Alice"\nb = "ALICE"\nprint a == b\nprint a lower == b lower', ["false", "true"])

    def test_first_letter_capital(self):
        self.assertOutput('w = "alice"\nprint w[0] upper + w[1 to w length - 1]', ["Alice"])

    def test_trim_both_ends(self):
        self.assertOutput('print "  Alice " trim + "!"', ["Alice!"])

    def test_trim_takes_tabs_and_line_breaks_and_keeps_the_inside(self):
        self.assertOutput('s = "\\n a  b \\n"\nprint s trim length\nprint s trim', ["4", "a  b"])

    def test_trim_of_only_spaces(self):
        self.assertOutput('print "   " trim == ""', ["true"])

    def test_only_text(self):
        out = self.assertError("print 5 lower", "V301")
        self.assertIn("lower works on text, got number.", out)
        self.assertError('print ["a"] trim', "V301")

    def test_strip_from_python(self):
        out = self.assertError('s = " a "\nprint s strip', "P202")
        self.assertIn("strip is written trim in Axion.", out)
        self.assertEqual(fix_of(out), "print s trim")


class Order(AxionTest):
    def test_comparison(self):
        self.assertOutput('print "apple" < "pear"\nprint "b" > "a"\nprint "a" <= "a"\nprint "b" >= "c"',
                          ["true", "true", "true", "false"])

    def test_a_longer_text_comes_after_its_beginning(self):
        self.assertOutput('print "app" < "apple"', ["true"])

    def test_capitals_come_before_small_letters(self):
        self.assertOutput('print "Zoe" < "adam"\nprint ["pear", "Zoe", "adam"] sort', ["true", '["Zoe", "adam", "pear"]'])

    def test_digits_in_text_compare_as_text(self):
        self.assertOutput('print "10" < "9"\nprint ["10", "9", "2"] sort', ["true", '["10", "2", "9"]'])

    def test_dates_written_year_month_day_sort_correctly(self):
        self.assertOutput('print ["2026-10-05", "2025-12-31", "2026-02-01"] sort',
                          ['["2025-12-31", "2026-02-01", "2026-10-05"]'])
        self.assertOutput('print "2026-10-05" > "2026-02-01"', ["true"])

    def test_sort_descending(self):
        self.assertOutput('print ["b", "c", "a"] sort descending', ['["c", "b", "a"]'])

    def test_sort_by_a_text_field_is_stable(self):
        source = ('ps = [{name: "Bo", n: 1}, {name: "Al", n: 2}, {name: "Bo", n: 3}]\n'
                  'for p in ps sort by name\n  print p.name + p.n as text\nend')
        self.assertOutput(source, ["Al2", "Bo1", "Bo3"])

    def test_ignoring_case_by_a_lower_field(self):
        source = ('names = ["bob", "Alice", "carl"]\nrows = [] of {name: text, key: text}\n'
                  'for n in names\n  rows add {name: n, key: n lower}\nend\n'
                  'for r in rows sort by key\n  print r.name\nend')
        self.assertOutput(source, ["Alice", "bob", "carl"])

    def test_text_against_a_number_is_still_a_mistake(self):
        out = self.assertError('age = "20"\nif age < 18\n  print 1\nend', "V308")
        self.assertIn("< compares two numbers or two texts, got text and number.", out)
        self.assertEqual(fix_of(out), "if age as number < 18")

    def test_bool_has_no_order(self):
        out = self.assertError("print true < false", "V308")
        self.assertIn("< compares numbers or text; bool has no order.", out)

    def test_a_list_of_bool_is_not_sorted(self):
        self.assertError("print [true, false] sort", "V301")

    def test_min_and_max_stay_for_numbers(self):
        self.assertError('print ["b", "a"] min', "V301")


class LoopOverCharacters(AxionTest):
    def test_one_character_at_a_time(self):
        self.assertOutput('for ch in "abc"\n  print ch\nend', ["a", "b", "c"])

    def test_counting(self):
        self.assertOutput('n = 0\nfor ch in "banana"\n  if ch == "a"\n    n = n + 1\n  end\nend\nprint n', ["3"])

    def test_reversing(self):
        self.assertOutput('out = ""\nfor ch in "abc"\n  out = ch + out\nend\nprint out', ["cba"])

    def test_empty_text_runs_no_pass(self):
        self.assertOutput('for ch in ""\n  print ch\nend\nprint "done"', ["done"])

    def test_the_character_is_read_only(self):
        self.assertError('for ch in "abc"\n  ch = "x"\n  print ch\nend', "V315")

    def test_it_must_be_used(self):
        self.assertError('for ch in "abc"\n  print 1\nend', "V305")

    def test_a_number_is_still_not_a_loop(self):
        out = self.assertError("n = 3\nfor i in n\n  print i\nend", "V301")
        self.assertIn("for needs a list or text, got number.", out)
        self.assertEqual(fix_of(out), "for i in 1 to n")


class MethodsFromOtherLanguages(AxionTest):
    CASES = (
        ('clean = s.strip()', "clean = s trim"),
        ('parts = s.split(",")', 'parts = s split ","'),
        ('low = s.lower()', "low = s lower"),
        ('up = s.upper()', "up = s upper"),
        ('ok = s.startswith("a")', 'ok = s starts with "a"'),
        ('ok = s.endswith("c")', 'ok = s ends with "c"'),
        ('ok = s.includes("b")', 'ok = s contains "b"'),
        ('t = s.replace("a", "b")', 't = (s split "a") join "b"'),
        ('parts = s.strip().lower().split(",")', 'parts = s trim lower split ","'),
        ('ok = s.lower().startswith("a")', 'ok = s lower starts with "a"'),
    )

    def test_every_method_gets_its_axiom_line_and_the_line_runs(self):
        for written, fixed in self.CASES:
            name = written.split(" ")[0]
            out = self.assertError(f's = "abc"\n{written}\nprint {name}', "P210")
            self.assertIn("Values have no methods in Axion.", out)
            self.assertEqual(fix_of(out), fixed, written)
            code, result = run(f's = "abc"\n{fixed}\nprint {name}')
            self.assertEqual(code, 0, f"{fixed}: {result}")

    def test_a_search_for_a_position_has_no_single_word(self):
        out = self.assertError('s = "abc"\nprint s.find("b")', "P210")
        self.assertIn("Axion has no search for a position", fix_of(out))

    def test_list_methods_are_unchanged(self):
        out = self.assertError("xs = [1]\nxs.append(2)\nprint xs", "P210")
        self.assertEqual(fix_of(out), "xs add 2")


class WordsStayNames(AxionTest):
    def test_no_new_keywords(self):
        self.assertEqual(len(KEYWORDS), 33)      # only while, continue, exit were added in v0.3
        for word in ("split", "contains", "starts", "ends", "with", "lower", "upper", "trim"):
            self.assertNotIn(word, KEYWORDS)

    def test_every_word_is_an_ordinary_name_elsewhere(self):
        source = ('lower = 1\nupper = 9\ntrim = 2\nsplit = 3\ncontains = 4\nstarts = 5\nends = 6\n'
                  'with = 7\nprint lower + upper + trim + split + contains + starts + ends + with')
        self.assertOutput(source, ["37"])

    def test_a_field_named_like_a_word(self):
        self.assertOutput('r = {lower: 1, upper: 5}\nprint r.upper - r.lower', ["4"])

    def test_an_unknown_word_lists_what_exists(self):
        # (reverse was the example here until v0.3 gave it a hint of its own)
        out = self.assertError('s = "abc"\nprint s capitalize', "P202")
        self.assertIn("capitalize is not an operation in Axion.", out)
        self.assertIn("split, contains, starts with, ends with, lower, upper, trim", fix_of(out))


class OldProgramsStillRun(AxionTest):
    def test_text_length_join_and_conversion(self):
        self.assertOutput('s = "42"\nprint s length\nprint s as number + 1\nprint ["a", "b"] join "-"',
                          ["2", "43", "a-b"])

    def test_numbers_sort_as_before(self):
        self.assertOutput("print [10, 9, 2] sort", ["[2, 9, 10]"])


if __name__ == "__main__":
    unittest.main()
