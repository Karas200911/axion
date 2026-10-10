"""Step 5 — objects and fields, as, is number.

Written from the v0.2 documentation (§9, §10).
"""

import unittest

from helpers import AxionTest

USERS = ('users = [{name: "Egor", age: 15, verified: true}, '
         '{name: "Alex", age: 20, verified: true}, {name: "Kate", age: 30, verified: false}]')


class Objects(AxionTest):
    def test_print_in_written_order(self):
        self.assertOutput('u = {name: "Egor", age: 15}\nprint u', ['{name: "Egor", age: 15}'])

    def test_field_read(self):
        self.assertOutput('u = {name: "Egor", age: 15}\nprint u.name\nprint u.age + 1', ["Egor", "16"])

    def test_nested_fields(self):
        src = 'p = {name: "Egor", address: {city: "Moscow", zip: "101000"}}\nprint p.address.city'
        self.assertOutput(src, ["Moscow"])

    def test_field_write(self):
        self.assertOutput('u = {name: "Egor", age: 15}\nu.age = 16\nprint u', ['{name: "Egor", age: 16}'])

    def test_nested_field_write(self):
        src = 'p = {address: {city: "Moscow"}}\np.address.city = "Kazan"\nprint p'
        self.assertOutput(src, ['{address: {city: "Kazan"}}'])

    def test_multiline(self):
        self.assertOutput('u = {\nname: "Egor",\nage: 15\n}\nprint u.name', ["Egor"])

    def test_keyword_field_names(self):
        src = 'item = {text: "a", value: 1, length: 3}\nprint item.text\nprint item.value + item.length'
        self.assertOutput(src, ["a", "4"])

    def test_field_length_vs_list_length(self):
        src = 'items = [{length: 9}]\nprint items length\nprint items[0].length'
        self.assertOutput(src, ["1", "9"])

    def test_cannot_add_field(self):
        self.assertError('u = {name: "Egor"}\nu.email = "x"\nprint u', "V309")

    def test_cannot_change_field_type(self):
        self.assertError('u = {age: 15}\nu.age = "16"\nprint u', "V309")

    def test_unknown_field_did_you_mean(self):
        out = self.assertError('u = {name: "Egor", age: 15}\nprint u.nmae', "V309")
        self.assertIn("Fix: did you mean name?", out)

    def test_field_on_non_object(self):
        self.assertError("x = 5\nprint x.a", "V309")

    def test_length_as_field_on_list(self):
        out = self.assertError("xs = [1, 2]\nprint xs.length", "V309")
        self.assertIn("Fix: print xs length", out)

    def test_empty_object(self):
        # v0.3: {} is an empty dictionary, and it must name the type of its values
        self.assertError("u = {}\nprint u", "P213")

    def test_duplicate_field(self):
        self.assertError("u = {a: 1, a: 2}\nprint u", "P202")

    def test_methods_do_not_exist(self):
        out = self.assertError("xs = [1]\nxs.append(2)\nprint xs", "P210")
        self.assertIn("Fix: xs add 2", out)


class Shapes(AxionTest):
    def test_field_order_does_not_matter_for_equality(self):
        self.assertOutput('a = {name: "Egor", age: 15}\nb = {age: 15, name: "Egor"}\nprint a == b',
                          ["true"])

    def test_different_values(self):
        self.assertOutput('a = {name: "Egor"}\nb = {name: "Alex"}\nprint a == b', ["false"])

    def test_different_fields(self):
        self.assertError('a = {name: "Egor", age: 15}\nc = {name: "Egor"}\nprint a == c', "V308")

    def test_different_field_types(self):
        self.assertError('a = {age: 15}\nd = {age: "15"}\nprint a == d', "V308")

    def test_list_elements_one_shape(self):
        self.assertError('xs = [{name: "A", age: 1}, {name: "B"}]\nprint xs', "V310")

    def test_list_elements_any_field_order(self):
        self.assertOutput('xs = [{a: 1, b: 2}, {b: 3, a: 4}]\nprint xs[1].a', ["4"])

    def test_reassign_same_shape(self):
        self.assertOutput('u = {name: "A"}\nu = {name: "B"}\nprint u.name', ["B"])

    def test_reassign_other_shape(self):
        self.assertError('u = {name: "A"}\nu = {age: 1}\nprint u', "V302")

    def test_empty_list_of_objects(self):
        src = 'us = [] of {name: text, age: number}\nus add {age: 3, name: "A"}\nprint us'
        self.assertOutput(src, ['[{age: 3, name: "A"}]'])

    def test_add_wrong_shape(self):
        self.assertError('us = [] of {name: text}\nus add {name: 1}\nprint us', "V310")

    def test_object_is_copied(self):
        self.assertOutput('a = {n: 1}\nb = a\nb.n = 2\nprint a.n\nprint b.n', ["1", "2"])

    def test_filter_users(self):
        src = (USERS + '\nnames = [] of text\nfor u in users\nif u.age >= 18 and u.verified\n'
               'names add u.name\nend\nend\nprint names')
        self.assertOutput(src, ['["Alex"]'])

    def test_cannot_change_field_of_iterated_list(self):
        src = 'us = [{n: 1}]\nfor u in us\nus[0].n = 5\nend\nprint us'
        self.assertError(src, "V316")

    def test_loop_variable_field_changes_the_list(self):
        # Was V315 until the fresh-task run: every model writes u.n = 5 and means the list.
        src = 'us = [{n: 1}]\nfor u in us\nu.n = 5\nend\nprint us'
        self.assertOutput(src, ["[{n: 5}]"])


class AsConversion(AxionTest):
    def test_number_to_text(self):
        self.assertOutput('age = 15\nprint "Age: " + age as text\nprint 2.5 as text\nprint (7 / 7) as text',
                          ["Age: 15", "2.5", "1"])

    def test_as_binds_to_the_last_value(self):
        # as binds to the value right before it: 7 / 7 as text = 7 / (7 as text).
        out = self.assertError("print 7 / 7 as text", "V301")
        self.assertIn("Fix: as binds only to 7; write (7 / 7) as text", out)
        out = self.assertError("print 1 + 2 as text", "V301")
        self.assertIn("Fix: as binds only to 2; write (1 + 2) as text", out)

    def test_bool_to_text(self):
        self.assertOutput('print "ok: " + true as text', ["ok: true"])

    def test_text_to_number(self):
        self.assertOutput('print "15" as number + 1\nprint "-2.5" as number\nprint "5.0" as number',
                          ["16", "-2.5", "5"])

    def test_parenthesized_expression(self):
        self.assertOutput('a = 1\nprint "Next: " + (a + 1) as text', ["Next: 2"])

    def test_chain_left_to_right(self):
        self.assertOutput('bad = ["x"]\nprint "Bad: " + bad length as text', ["Bad: 1"])

    def test_misplaced_as(self):
        out = self.assertError('age = 1\nprint "Next: " + age + 1 as text', "V301")
        self.assertIn('Fix: "Next: " + (age + 1) as text', out)

    def test_already_text(self):
        out = self.assertError('print "hi" as text', "V311")
        self.assertIn("Fix: remove as text", out)

    def test_number_to_bool(self):
        out = self.assertError("x = 1\nprint x as bool", "V311")
        self.assertIn("Fix: compare instead: x != 0", out)

    def test_bool_to_number(self):
        self.assertError("print true as number", "V311")

    def test_list_to_text(self):
        self.assertError("print [1] as text", "V311")

    def test_literal_not_a_number(self):
        for text in ('"abc"', '" 15"', '"1,5"', '"1e3"', '"+5"', '""'):
            with self.subTest(text=text):
                self.assertError(f"print {text} as number", "V314")

    def test_runtime_not_a_number(self):
        out = self.assertError('s = "abc"\nprint s as number', "R404")
        self.assertIn("Fix: check first: if s is number", out)


class IsNumber(AxionTest):
    def test_values(self):
        src = ('print "15" is number\nprint "-3" is number\nprint "99.5" is number\n'
               'print "abc" is number\nprint " 15" is number\nprint "" is number')
        self.assertOutput(src, ["true", "true", "true", "false", "false", "false"])

    def test_only_text(self):
        self.assertError("x = 5\nprint x is number", "V311")

    def test_only_is_number_exists(self):
        self.assertError('s = "a"\nprint s is text', "P202")

    def test_dirty_data(self):
        src = ('raw = ["15", "abc", "20", "1,5"]\ntotal = 0\nbad = 0\nfor s in raw\n'
               'if s is number\ntotal = total + s as number\nelse\nbad = bad + 1\nend\nend\n'
               'print total\nprint bad')
        self.assertOutput(src, ["35", "2"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
