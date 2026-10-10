"""Axion v0.3, step 2: the dictionary.

Models reached for a dictionary in every test (`{}`, `{} of text to number`), and without
one every task about counting or grouping was a loop inside a loop. Decisions 5 and 6 of
the v0.3 design (2026-10-05): a small dictionary with six actions, text keys only.

    counts = {} of number                 empty: text keys, number values
    prices = {"tea": 2, "milk": 1.5}      with its values; every key in quotes
    counts[w]        counts[w] = 5        a missing key is an error when read
    counts contains w
    counts keys                           a list, in the order the keys were added
    counts remove key w
    counts length
    input stock: map of number

A name without quotes is a field of an object ({name: "A"}); a key in quotes makes a
dictionary. The two never mix.
"""
import unittest

from helpers import AxionTest, run


def fix_of(out):
    return next((line[5:] for line in out if line.startswith("Fix: ")), None)


def fixes(out):
    return [line[5:] for line in out if line.startswith("Fix: ")]


class Basics(AxionTest):
    def test_empty_then_filled(self):
        self.assertOutput('d = {} of number\nd["a"] = 1\nd["b"] = 2\nprint d\nprint d length',
                          ['{"a": 1, "b": 2}', "2"])

    def test_written_with_its_values(self):
        self.assertOutput('prices = {"tea": 2, "milk": 1.5}\nprint prices["milk"] * 2\nprint prices',
                          ["3", '{"tea": 2, "milk": 1.5}'])

    def test_a_key_set_again_keeps_its_place(self):
        self.assertOutput('d = {"a": 1, "b": 2}\nd["a"] = 9\nprint d\nprint d keys', ['{"a": 9, "b": 2}', '["a", "b"]'])

    def test_keys_come_in_the_order_they_were_added(self):
        self.assertOutput('d = {} of number\nd["z"] = 1\nd["a"] = 2\nd["m"] = 3\nprint d keys', ['["z", "a", "m"]'])

    def test_contains_asks_about_a_key(self):
        self.assertOutput('d = {"a": 1}\nprint d contains "a"\nprint d contains "b"\nprint not d contains "b"',
                          ["true", "false", "true"])

    def test_remove_key(self):
        self.assertOutput('d = {"a": 1, "b": 2}\nd remove key "a"\nprint d\nprint d length', ['{"b": 2}', "1"])

    def test_a_removed_key_added_again_goes_to_the_end(self):
        self.assertOutput('d = {"a": 1, "b": 2}\nd remove key "a"\nd["a"] = 3\nprint d keys', ['["b", "a"]'])

    def test_empty_dictionary_prints_and_measures(self):
        self.assertOutput("d = {} of text\nprint d\nprint d length\nprint d keys", ["{}", "0", "[]"])

    def test_keys_are_case_sensitive_and_may_be_any_text(self):
        self.assertOutput('d = {"A": 1, "a": 2, "": 3, "two words": 4}\nprint d["a"] + d[""] + d["two words"]', ["9"])

    def test_values_of_every_type(self):
        self.assertOutput('d = {"x": true}\nprint d["x"]', ["true"])
        self.assertOutput('d = {"x": [1, 2]}\nprint d["x"] sum', ["3"])
        self.assertOutput('d = {"x": {name: "A", n: 1}}\nprint d["x"].name', ["A"])
        self.assertOutput('d = {"x": {"y": 5}}\nprint d["x"]["y"]', ["5"])

    def test_a_key_computed_from_text(self):
        self.assertOutput('d = {} of number\nfor i in 1 to 3\n  d["k" + i as text] = i * i\nend\nprint d',
                          ['{"k1": 1, "k2": 4, "k3": 9}'])


class RealTasks(AxionTest):
    def test_word_count(self):
        source = ('line = "the cat and the dog and the bird"\ncounts = {} of number\n'
                  'for w in line split " "\n'
                  '  counts[w] = if counts contains w then counts[w] + 1 else 1\nend\n'
                  'for w in counts keys\n  print w + ": " + counts[w] as text\nend')
        self.assertOutput(source, ["the: 3", "cat: 1", "and: 2", "dog: 1", "bird: 1"])

    def test_grouping(self):
        source = ('people = [{name: "Ann", city: "Oslo"}, {name: "Bo", city: "Rome"}, {name: "Cy", city: "Oslo"}]\n'
                  'by_city = {} of list of text\n'
                  'for p in people\n'
                  '  if not by_city contains p.city\n    by_city[p.city] = [] of text\n  end\n'
                  '  by_city[p.city] add p.name\nend\n'
                  'for c in by_city keys\n  print c + ": " + by_city[c] join ", "\nend')
        self.assertOutput(source, ["Oslo: Ann, Cy", "Rome: Bo"])

    def test_top_by_count(self):
        source = ('counts = {"a": 3, "b": 7, "c": 5}\nrows = [] of {word: text, n: number}\n'
                  'for k in counts keys\n  rows add {word: k, n: counts[k]}\nend\n'
                  'for r in (rows sort by n descending)[0 to 1]\n  print r.word + " " + r.n as text\nend')
        self.assertOutput(source, ["b 7", "c 5"])

    def test_a_lookup_table_in_place_of_an_if_chain(self):
        source = ('names = {"1": "Mon", "2": "Tue", "3": "Wed"}\nfor d in [3, 1]\n  print names[d as text]\nend')
        self.assertOutput(source, ["Wed", "Mon"])

    def test_index_by_id(self):
        source = ('users = [{id: 7, name: "Ann"}, {id: 12, name: "Bo"}]\nby_id = {} of text\n'
                  'for u in users\n  by_id[u.id as text] = u.name\nend\nprint by_id["12"]')
        self.assertOutput(source, ["Bo"])


class Copies(AxionTest):
    def test_assignment_copies(self):
        self.assertOutput('a = {"x": 1}\nb = a\nb["x"] = 9\nb["y"] = 2\nprint a\nprint b', ['{"x": 1}', '{"x": 9, "y": 2}'])

    def test_a_function_gets_a_copy_and_cannot_change_its_parameter(self):
        source = 'function f(d: map of number) -> number\n  d["x"] = 5\n  return d["x"]\nend\nprint f({"x": 1})'
        self.assertError(source, "V324")

    def test_a_function_reads_and_returns_a_dictionary(self):
        source = ('function total(d: map of number) -> number\n  t = 0\n  for k in d keys\n    t = t + d[k]\n  end\n'
                  '  return t\nend\nfunction made() -> map of number\n  d = {} of number\n  d["a"] = 2\n  return d\nend\n'
                  'print total({"a": 1, "b": 2.5})\nprint made()')
        self.assertOutput(source, ["3.5", '{"a": 2}'])

    def test_a_value_inside_is_changed_in_place(self):
        source = 'd = {"a": [1, 2]}\nd["a"][0] = 9\nd["a"] add 3\nprint d'
        self.assertOutput(source, ['{"a": [9, 2, 3]}'])

    def test_a_field_of_an_object_inside(self):
        self.assertOutput('d = {"a": {n: 1}}\nd["a"].n = 5\nprint d["a"].n', ["5"])

    def test_changing_while_walking_its_keys_is_safe(self):
        # `keys` is a list of its own, so the loop does not walk the dictionary itself
        source = 'd = {"a": 1, "b": 2}\nfor k in d keys\n  d[k + k] = d[k]\n  d remove key k\nend\nprint d'
        self.assertOutput(source, ['{"aa": 1, "bb": 2}'])

    def test_equal_when_the_same_pairs(self):
        self.assertOutput('print {"a": 1, "b": 2} == {"b": 2, "a": 1}\nprint {"a": 1} == {"a": 2}', ["true", "false"])

    def test_inside_a_list_and_an_object(self):
        self.assertOutput('xs = [{"a": 1}, {"b": 2}]\nxs[1]["c"] = 3\nprint xs', ['[{"a": 1}, {"b": 2, "c": 3}]'])
        self.assertOutput('o = {tags: {"x": true}}\nprint o.tags contains "x"\nprint o', ["true", '{tags: {"x": true}}'])


class MissingKey(AxionTest):
    def test_reading_a_missing_key_stops_the_program(self):
        out = self.assertError('d = {"a": 1}\nk = "zz"\nprint d[k]', "R411")
        self.assertIn('There is no key "zz" in d.', out)
        self.assertEqual(fix_of(out), "check first: if d contains k")

    def test_nothing_is_printed_after_it(self):
        code, out = run('d = {"a": 1}\nprint "before"\nprint d["b"]\nprint "after"')
        self.assertEqual((code, out[0]), (1, "before"))
        self.assertNotIn("after", out)

    def test_removing_a_missing_key(self):
        out = self.assertError('d = {"a": 1}\nd remove key "b"\nprint d', "R411")
        self.assertEqual(fix_of(out), 'check first: if d contains "b"')

    def test_the_check_first_way(self):
        self.assertOutput('d = {"a": 1}\nn = if d contains "b" then d["b"] else 0\nprint n', ["0"])

    def test_changing_a_list_under_a_missing_key(self):
        self.assertError('d = {} of list of number\nd["a"] add 1\nprint d', "R411")


class Types(AxionTest):
    def test_a_key_is_text(self):
        out = self.assertError('d = {} of number\nn = 5\nd[n] = 1\nprint d', "V301")
        self.assertIn("A key of a dictionary is text, got number.", out)
        self.assertEqual(fix_of(out), "d[n as text] = 1")
        self.assertOutput('d = {} of number\nn = 5\nd[n as text] = 1\nprint d', ['{"5": 1}'])

    def test_a_number_key_when_reading_and_asking(self):
        self.assertEqual(fix_of(self.assertError('d = {"1": 2}\nn = 1\nprint d[n]', "V301")), "print d[n as text]")
        self.assertEqual(fix_of(self.assertError('d = {"1": 2}\nn = 1\nprint d contains n', "V301")),
                         "print d contains (n as text)")
        self.assertOutput('d = {"1": 2}\nn = 1\nprint d contains (n as text)\nprint d[n as text]', ["true", "2"])

    def test_the_value_type_is_fixed(self):
        out = self.assertError('d = {} of number\nd["a"] = "x"\nprint d', "V310")
        self.assertIn("d holds number; it cannot store text.", out)

    def test_values_of_one_type_in_a_written_dictionary(self):
        out = self.assertError('user = {"name": "A", "age": 3}\nprint user', "V310")
        self.assertIn("The values of a dictionary have one type, got text and number.", out)
        self.assertEqual(fix_of(out), 'for a record with different fields write the names without quotes: '
                                      '{name: "A", age: 3}')
        self.assertOutput('user = {name: "A", age: 3}\nprint user.name', ["A"])

    def test_an_object_is_not_read_with_brackets(self):
        out = self.assertError('user = {name: "A", age: 3}\nprint user["name"]', "V301")
        self.assertEqual(fix_of(out), "print user.name")

    def test_an_object_read_with_an_unknown_key(self):
        out = self.assertError('user = {name: "A"}\nk = "name"\nprint user[k]', "V301")
        self.assertIn('a dictionary: {"tea": 2, "milk": 1.5}', fix_of(out))

    def test_quotes_and_names_do_not_mix(self):
        for source in ('d = {"a": 1, b: 2}\nprint d', 'd = {a: 1, "b": 2}\nprint d'):
            out = self.assertError(source, "P202")
            self.assertIn("Do not mix them.", out[3])

    def test_a_key_twice(self):
        self.assertIn('The key "a" appears twice.', self.assertError('d = {"a": 1, "a": 2}\nprint d', "P202"))

    def test_two_dictionaries_of_different_types(self):
        self.assertError('a = {} of number\nb = {} of text\nprint a == b', "V308")
        self.assertError('a = {} of number\na = {"x": "y"}\nprint a', "V302")

    def test_dictionaries_have_no_order_and_no_sum(self):
        self.assertError('print {"a": 1} < {"b": 2}', "V308")
        self.assertError('d = {"a": 1}\nprint d sum', "V301")
        self.assertError('d = {"a": 1}\nprint d sort', "V301")

    def test_no_conversion_to_text(self):
        out = self.assertError('d = {"a": 1}\nprint "d: " + d as text', "V311")
        self.assertEqual(fix_of(out), "print shows lists, objects and dictionaries directly: print d")


class EmptyNeedsItsType(AxionTest):
    def test_the_type_comes_from_the_first_value_stored(self):
        out = self.assertError('d = {}\nd["a"] = 1\nprint d', "P213")
        self.assertIn("An empty dictionary needs the type of its values.", out)
        self.assertEqual(fix_of(out), "d = {} of number")

    def test_a_list_as_the_value(self):
        source = 'groups = {}\ngroups["a"] = [] of text\ngroups["a"] add "x"\nprint groups'
        self.assertEqual(fix_of(self.assertError(source, "P213")), "groups = {} of list of text")

    def test_the_counting_line_of_a_model(self):
        source = ('counts = {}\nfor w in ["a", "b", "a"]\n'
                  '  counts[w] = if counts contains w then counts[w] + 1 else 1\nend\nprint counts')
        self.assertEqual(fix_of(self.assertError(source, "P213")), "counts = {} of number")

    def test_nothing_is_stored_the_general_hint_stays(self):
        out = self.assertError("d = {}\nprint d", "P213")
        self.assertEqual(fix_of(out), "d = {} of number   (or {} of text, {} of bool, {} of list of number)")

    def test_a_list_and_a_dictionary_each_get_their_line(self):
        out = self.assertErrors('xs = []\nd = {}\nxs add "a"\nd["k"] = true\nprint xs\nprint d', ["P213", "P213"])
        self.assertEqual(fixes(out), ["xs = [] of text", "d = {} of bool"])

    def test_resetting_a_known_dictionary(self):
        out = self.assertError('d = {"a": 1}\nd = {}\nprint d', "P213")
        self.assertEqual(fix_of(out), "d = {} of number")

    def test_keys_are_text_so_only_the_value_type_is_written(self):
        for written in ("totals = {} of text to number", "totals = {} of text -> number"):
            out = self.assertError(written + "\nprint totals", "P202")
            self.assertEqual(fix_of(out), "totals = {} of number")
        out = self.assertError("g = {} of text -> list of {id: number}\nprint g", "P202")
        self.assertEqual(fix_of(out), "g = {} of list of {id: number}")

    def test_a_bare_empty_dictionary_never_runs(self):
        code, out = run('d = {}\nd["a"] = 1\nprint d')
        self.assertEqual(code, 1)
        self.assertNotIn('{"a": 1}', out)


class Statements(AxionTest):
    def test_add_is_for_lists(self):
        out = self.assertError('d = {"a": 1}\nd add 5\nprint d', "V301")
        self.assertEqual(fix_of(out), "d[k] = v")        # value is a reserved word: not offered as a name

    def test_remove_value_and_index_are_for_lists(self):
        out = self.assertError('d = {"a": 1}\nd remove value "a"\nprint d', "V301")
        self.assertIn("d is a dictionary: an entry is removed by its key.", out)
        self.assertEqual(fix_of(out), 'd remove key "a"')
        self.assertEqual(fix_of(self.assertError('d = {"a": 1}\nd remove index 0\nprint d', "V301")), "d remove key k")

    def test_remove_key_is_for_dictionaries(self):
        out = self.assertError('xs = ["a"]\nxs remove key "a"\nprint xs', "V301")
        self.assertIn("remove key works on a dictionary; xs is list of text.", out)

    def test_lists_keep_their_remove(self):
        self.assertOutput("xs = [1, 2, 3]\nxs remove index 0\nxs remove value 3\nprint xs", ["[2]"])

    def test_remove_needs_a_word(self):
        out = self.assertError('d = {"a": 1}\nd remove "a"\nprint d', "P202")
        self.assertIn("d remove key k", fix_of(out))

    def test_for_goes_over_the_keys(self):
        out = self.assertError('d = {"a": 1}\nfor k in d\n  print k\nend', "V301")
        self.assertIn("a dictionary is walked by its keys.", out[3])
        self.assertEqual(fix_of(out), "for k in d keys")
        self.assertOutput('d = {"a": 1}\nfor k in d keys\n  print k\nend', ["a"])

    def test_keys_only_on_a_dictionary(self):
        self.assertError("xs = [1]\nprint xs keys", "V301")
        out = self.assertError('o = {name: "A", age: 3}\nprint o keys', "V301")
        self.assertIn("o.name, o.age", fix_of(out))

    def test_keys_can_be_sorted_and_measured(self):
        self.assertOutput('d = {"b": 1, "a": 2}\nprint d keys sort\nprint d keys length', ['["a", "b"]', "2"])

    def test_an_unused_dictionary_is_reported_like_any_variable(self):
        self.assertError('d = {} of number\nd["a"] = 1', "V305")


class Input(AxionTest):
    def test_a_dictionary_from_the_input_data(self):
        source = ('input stock: map of number\ninput names: list of text\nfor n in names\n'
                  '  print n + ": " + (if stock contains n then stock[n] as text else "none")\nend')
        self.assertOutput(source, ["tea: 5", "rice: none"],
                          data='{"stock": {"tea": 5, "milk": 0}, "names": ["tea", "rice"]}')

    def test_the_order_of_the_data_is_kept(self):
        self.assertOutput("input d: map of text\nprint d keys", ['["z", "a"]'], data='{"d": {"z": "1", "a": "2"}}')

    def test_an_empty_object_is_an_empty_dictionary(self):
        self.assertOutput("input d: map of number\nprint d length", ["0"], data='{"d": {}}')

    def test_a_value_of_the_wrong_type(self):
        code, out = run("input stock: map of number\nprint stock", data='{"stock": {"tea": "x"}}')
        self.assertEqual(code, 1)
        self.assertIn('Input data: stock["tea"] must be number, got text.', out)

    def test_not_an_object(self):
        code, out = run("input stock: map of number\nprint stock", data='{"stock": [1]}')
        self.assertIn("Input data: stock must be map of number, got an array.", out)

    def test_dictionaries_of_objects_and_lists_of_dictionaries(self):
        self.assertOutput('input users: map of {age: number}\nprint users["ann"].age', ["30"],
                          data='{"users": {"ann": {"age": 30}}}')
        self.assertOutput("input rows: list of map of number\nprint rows[1] keys", ['["b"]'],
                          data='{"rows": [{"a": 1}, {"b": 2}]}')

    def test_the_type_name(self):
        for word in ("dict", "dictionary"):
            out = self.assertError(f"input stock: {word} of number\nprint stock", "P202")
            self.assertIn(f"The dictionary type is written map of T, not {word}.", out)
        self.assertError("input stock: map number\nprint stock", "P202")

    def test_map_is_still_a_name(self):
        self.assertOutput("map = 3\nkeys = 4\nkey = 5\nprint map + keys + key", ["12"])


class HabitsFromOtherLanguages(AxionTest):
    def test_get_with_a_default(self):
        out = self.assertError('d = {"a": 1}\nprint d.get("a", 0)', "P210")
        self.assertEqual(fix_of(out), 'print (if d contains "a" then d["a"] else 0)')
        self.assertOutput('d = {"a": 1}\nprint (if d contains "b" then d["b"] else 0)', ["0"])

    def test_the_counting_line(self):
        source = 'counts = {} of number\nw = "a"\ncounts[w] = counts.get(w, 0) + 1\nprint counts'
        out = self.assertError(source, "P210")
        self.assertEqual(fix_of(out), "counts[w] = (if counts contains w then counts[w] else 0) + 1")
        self.assertOutput(source.replace("counts.get(w, 0)", "(if counts contains w then counts[w] else 0)"),
                          ['{"a": 1}'])

    def test_get_without_a_default(self):
        self.assertEqual(fix_of(self.assertError('d = {"a": 1}\nprint d.get("a")', "P210")), 'print d["a"]')

    def test_keys_values_items(self):
        self.assertEqual(fix_of(self.assertError('d = {"a": 1}\nks = d.keys()\nprint ks', "P210")), "ks = d keys")
        for method in ("values", "items"):
            out = self.assertError(f'd = {{"a": 1}}\nprint d.{method}()', "P210")
            self.assertEqual(fix_of(out), "go over the keys: for k in d keys, and read d[k]")

    def test_two_loop_variables(self):
        out = self.assertError('d = {"a": 1}\nfor k, v in d.items()\n  print k\nend', "P202")
        self.assertIn("for has one variable.", out)
        self.assertTrue(fix_of(out).startswith("for k in d keys   and inside it: v = d[k]"))

    def test_in_becomes_contains(self):
        out = self.assertError('d = {"a": 1}\nif "a" in d\n  print 1\nend', "P202")
        self.assertEqual(fix_of(out), 'if d contains "a"')

    def test_del(self):
        out = self.assertError('d = {"a": 1}\ndel d["a"]\nprint d', "P210")
        self.assertEqual(fix_of(out), "for a dictionary: d remove key k   for a list: xs remove index i")

    def test_constructors(self):
        for call, expected in (("dict()", "{} of number"), ("set()", "seen contains x"),
                               ("defaultdict(int)", "counts = {} of number")):
            out = self.assertError(f"d = {call}\nprint d", "V303")
            self.assertIn(expected, fix_of(out), call)

    def test_len_of_a_dictionary(self):
        out = self.assertError('d = {"a": 1}\nprint len(d)', "V303")
        self.assertEqual(fix_of(out), "print d length")


if __name__ == "__main__":
    unittest.main()
