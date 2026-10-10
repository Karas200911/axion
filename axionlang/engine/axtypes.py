"""Axion types (spec §2).

Simple types are the strings "number", "text", "bool".
Compound types are ListT, ObjectT and MapT (a dictionary with text keys). Two types are equal when they
describe the same values: list of number == list of number;
objects with the same fields and field types, in any order (§9).
"""

NUMBER, TEXT, BOOL = "number", "text", "bool"

# The element type of a bare [] while its real type is being worked out for a Fix hint
# (validator.empty_list_fixes). A program that runs never has it.
PENDING = "?"


class ListT:
    __slots__ = ("elem",)

    def __init__(self, elem):
        self.elem = elem

    def __eq__(self, other):
        return isinstance(other, ListT) and other.elem == self.elem

    def __hash__(self):
        return hash(("list", self.elem))

    def __str__(self):
        return f"list of {self.elem}"


class ObjectT:
    __slots__ = ("fields",)

    def __init__(self, fields):
        self.fields = dict(fields)          # keeps the written order for messages

    def __eq__(self, other):
        return isinstance(other, ObjectT) and other.fields == self.fields

    def __hash__(self):
        return hash(frozenset(self.fields.items()))

    def __str__(self):
        return "{" + ", ".join(f"{k}: {v}" for k, v in self.fields.items()) + "}"


class MapT:
    """A dictionary: text keys, values of one type (v0.3). Written `map of T`."""
    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return isinstance(other, MapT) and other.value == self.value

    def __hash__(self):
        return hash(("map", self.value))

    def __str__(self):
        return f"map of {self.value}"


def short_name(t):
    """A word for a type, usable inside a variable name (age_text, items_list)."""
    if isinstance(t, ListT):
        return "list"
    if isinstance(t, ObjectT):
        return "object"
    if isinstance(t, MapT):
        return "map"
    return t
