"""Parser: tokens -> AST (spec §1, §7).

Implemented so far: assignment, print, literals (number, text, bool, list,
object), names, parentheses, all operators of §7 with their ambiguity errors,
index / field / length / as / is, if / else if / else, for, list statements.
Every node keeps line, col and end (exclusive) for error messages.
"""

import re
from dataclasses import dataclass
from decimal import Decimal

from .axtypes import BOOL, NUMBER, TEXT, ListT, MapT, ObjectT
from .errors import AxionError
from .lexer import lex, normalize_source


# ---------- AST ----------

@dataclass
class Number:
    value: Decimal
    line: int
    col: int
    end: int


@dataclass
class Text:
    value: str
    line: int
    col: int
    end: int


@dataclass
class Bool:
    value: bool
    line: int
    col: int
    end: int


@dataclass
class Unary:
    op: str
    operand: object
    line: int
    col: int
    end: int


@dataclass
class Not:
    operand: object
    line: int
    col: int
    end: int


@dataclass
class Name:
    name: str
    line: int
    col: int
    end: int


@dataclass
class Group:
    inner: object
    line: int
    col: int
    end: int


@dataclass
class Binary:
    op: str
    left: object
    right: object
    line: int
    col: int
    end: int


@dataclass
class Assign:
    name: str
    value: object
    line: int
    col: int
    end: int


@dataclass
class Print:
    value: object
    line: int
    col: int
    end: int


@dataclass
class ListLit:
    items: list
    line: int
    col: int
    end: int


@dataclass
class EmptyList:
    elem_type: object
    line: int
    col: int
    end: int


@dataclass
class EmptyMap:         # {} of number   (value_type None: a bare {}, only while its type is worked out)
    value_type: object
    line: int
    col: int
    end: int


@dataclass
class MapLit:           # {"tea": 2, "milk": 1.5}
    pairs: list         # [(key text, key line, key col, value node)]
    line: int
    col: int
    end: int


@dataclass
class Keys:             # d keys   -> the keys as a list of text, in the order they were added
    target: object
    line: int
    col: int
    end: int


@dataclass
class Index:
    target: object
    index: object
    line: int
    col: int
    end: int


@dataclass
class Length:
    target: object
    line: int
    col: int
    end: int


@dataclass
class Range:
    start: object
    stop: object
    line: int
    col: int
    end: int


@dataclass
class SetItem:          # xs[i] = v
    target: object      # an Index node
    value: object
    line: int
    col: int
    end: int


@dataclass
class ListAdd:          # xs add v
    target: object
    value: object
    line: int
    col: int
    end: int


@dataclass
class ListRemove:       # xs remove index i / xs remove value v / d remove key k
    target: object
    mode: str           # "index", "value" or "key"
    value: object
    line: int
    col: int
    end: int


@dataclass
class ObjectLit:
    fields: list        # [(name, expression)] in written order
    line: int
    col: int
    end: int


@dataclass
class Field:            # obj.name
    target: object
    name: str
    line: int
    col: int
    end: int


@dataclass
class SetField:         # obj.name = v
    target: object      # a Field node
    value: object
    line: int
    col: int
    end: int


@dataclass
class As:               # value as type
    operand: object
    type: object
    line: int
    col: int
    end: int


@dataclass
class IsNumber:         # text is number
    operand: object
    line: int
    col: int
    end: int


@dataclass
class Sort:             # xs sort / xs sort by field / ... descending   -> a new list
    target: object
    field: object       # field name for "by", or None
    descending: bool
    line: int
    col: int
    end: int
    more: tuple = ()    # the next fields of "by a, b descending": (field, descending) each


@dataclass
class Aggregate:        # xs sum / xs min / xs max
    op: str
    target: object
    line: int
    col: int
    end: int


@dataclass
class Join:             # words join ", "
    target: object
    separator: object
    line: int
    col: int
    end: int


@dataclass
class TextOp:           # s lower / s upper / s trim
    op: str
    target: object
    line: int
    col: int
    end: int


@dataclass
class Split:            # s split ", "   -> a list of text (the inverse of join)
    target: object
    separator: object
    line: int
    col: int
    end: int


@dataclass
class Contains:         # s contains part / xs contains value
    target: object
    item: object
    line: int
    col: int
    end: int


@dataclass
class Affix:            # s starts with p / s ends with p
    op: str             # "starts" or "ends"
    target: object
    part: object
    line: int
    col: int
    end: int


@dataclass
class Round:            # x round 2 / x floor / x ceiling
    op: str             # "round", "floor" or "ceiling"
    target: object
    places: object      # the number of places for round, otherwise None
    line: int
    col: int
    end: int


@dataclass
class DateOp:           # s is date / s as days / n as date
    op: str             # "is date", "as days" or "as date"
    operand: object
    line: int
    col: int
    end: int


@dataclass
class Conditional:      # if c then a else b, as a value
    cond: object
    then: object
    otherwise: object
    line: int
    col: int
    end: int


@dataclass
class Param:
    name: str
    type: object
    line: int
    col: int


@dataclass
class Function:
    name: str
    params: list        # [Param]
    result: object      # a type, or None for "no result"
    body: list
    line: int
    col: int
    end: int
    name_col: int


@dataclass
class Return:
    value: object       # None for a bare return
    line: int
    col: int
    end: int


@dataclass
class Call:
    name: str
    args: list
    line: int
    col: int
    end: int


@dataclass
class CallStatement:    # f(x) on its own line
    call: object
    line: int
    col: int
    end: int


@dataclass
class Allow:            # allow read "folder/"
    folder: str
    line: int
    col: int
    end: int


@dataclass
class Input:            # input name: type
    name: str
    type: object
    line: int
    col: int
    end: int
    name_col: int


@dataclass
class Read:             # read "path"
    path: object
    line: int
    col: int
    end: int


@dataclass
class FormatText:       # f"Total: {x}" of Python. Never valid: the validator, which knows the
    parts: list         # types, answers with the exact Axion line. ("text", raw) | ("value", node, format)
    line: int
    col: int
    end: int


@dataclass
class Comprehension:    # [x * 2 for x in xs if x > 1] of Python. Never valid, for the same reason.
    item: object
    var: str
    iterable: object
    condition: object   # or None
    line: int
    col: int
    end: int


@dataclass
class Exists:           # exists "path": is there such a file? (the check that comes before read)
    path: object
    line: int
    col: int
    end: int


@dataclass
class For:
    var: str
    var_line: int
    var_col: int
    iterable: object
    body: list
    line: int
    col: int
    end: int


@dataclass
class While:
    condition: object
    body: list
    line: int
    col: int
    end: int


@dataclass
class Break:            # break: stop the nearest loop
    line: int
    col: int
    end: int


@dataclass
class Continue:         # continue: go on with the next pass of the nearest loop
    line: int
    col: int
    end: int


@dataclass
class Exit:             # exit: the program ends here, normally (main program only)
    line: int
    col: int
    end: int


@dataclass
class Branch:
    condition: object        # None for else
    body: list
    line: int                # position of the branch header (if / else if / else)
    col: int
    end: int


@dataclass
class If:
    branches: list           # if + else if branches, in order
    else_branch: object      # Branch or None
    line: int
    col: int
    end: int
    end_line: int = 0        # the line of the closing end (for the stray-else hint)


@dataclass
class Program:
    statements: list


# Habits from other languages, recognized and redirected (spec §17).
FOREIGN_STATEMENTS = {
    "elif": "Axion writes else if",
    "elseif": "Axion writes else if",
    "var": "no declarations: write name = value",
    "let": "no declarations: write name = value",
    "const": "no declarations: write name = value",
    "def": "write function name(param: type) -> type",
    "fn": "write function name(param: type) -> type",
    "func": "write function name(param: type) -> type",
    "pass": "Axion has no pass: a branch cannot be empty, so remove the empty branch",
    "del": "for a dictionary: d remove key k   for a list: xs remove index i",
}
# Statement words of other languages that Axion does not have, and what is written instead.
# They stay ordinary names when used as one (match = 3).
NO_TRY = ("check before the action instead (is number, is date, contains, length, exists, "
          "!= 0) and delete the try lines")
FOREIGN_WORDS = {
    "import": ("Axion has no import.", "delete this line: everything Axion has is always there"),
    "from": ("Axion has no import.", "delete this line: everything Axion has is always there"),
    "try": ("Axion has no try: an error is prevented, not caught.", NO_TRY),
    "except": ("Axion has no try: an error is prevented, not caught.", NO_TRY),
    "catch": ("Axion has no try: an error is prevented, not caught.", NO_TRY),
    "finally": ("Axion has no try: an error is prevented, not caught.", NO_TRY),
    "raise": ("Axion has no raise.", "two lines: print the message   then   exit"),
    "throw": ("Axion has no throw.", "two lines: print the message   then   exit"),
    "assert": ("Axion has no assert.", "write the check as an if: print the message, then exit"),
    "class": ("Axion has no classes.",
              "an object is written {field: value}; what a method did is a function that "
              "takes the object as a parameter"),
    "global": ("A function sees only its parameters.",
               "delete this line: pass the value in as a parameter and return the result"),
    "nonlocal": ("A function sees only its parameters.",
                 "delete this line: pass the value in as a parameter and return the result"),
    "switch": ("Axion has no switch.", "write a chain: if ... else if ... else ... end"),
    "match": ("Axion has no match.", "write a chain: if ... else if ... else ... end"),
    "with": ("Axion has no with.", 'a file is read in one step: text = read "folder/file.txt"'),
}
STATEMENT_STARTS = ("a line starts with a name (x = ...), print, if, for, while, function, "
                    "return, break, continue or exit")
AUGMENTED = ("+", "-", "*", "/", "//", "%", "**")
PYTHON_CHOICE = re.compile(r"(\s*(?:[A-Za-z_][A-Za-z0-9_.\[\]\"]*\s*=(?!=)|print|return)\s*)"
                           r"(.+?)\s+if\s+(.+?)\s+else\s+(.+?)\s*$")
TUPLE_ASSIGN = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(?!=)\s*(.+)$")
SORT_KEY_PART = re.compile(r"(-?)\s*(?:[A-Za-z_][A-Za-z0-9_]*)(?:\.([A-Za-z_][A-Za-z0-9_]*)"
                           r"|\[\s*\"([A-Za-z_][A-Za-z0-9_]*)\"\s*\])$")


def split_top(text):
    """The parts of `a, f(b, c), d` between the commas that are not inside brackets or text."""
    parts, depth, start, k = [], 0, 0, 0
    while k < len(text):
        ch = text[k]
        if ch == '"':
            k += 1
            while k < len(text) and text[k] != '"':
                k += 2 if text[k] == "\\" else 1
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(text[start:k].strip())
            start = k + 1
        k += 1
    parts.append(text[start:].strip())
    return parts


def python_sort_keys(args):
    """The arguments of sorted( ) / .sort( ) after the list, as Axion words:
    `key=lambda t: (-t.points, t.name)` -> "by points descending, name"; "" for none;
    None when they are not that simple."""
    keys, reverse = None, False
    for arg in args:
        name, _, value = (part.strip() for part in arg.partition("="))
        if name == "reverse" and value in ("True", "true", "False", "false"):
            reverse = value in ("True", "true")
        elif name == "key":
            body = re.match(r"lambda\s+[A-Za-z_][A-Za-z0-9_]*\s*:\s*(.+)$", value)
            if body is None:
                return None
            inner = body.group(1).strip()
            if inner.startswith("(") and inner.endswith(")"):
                inner = inner[1:-1]
            keys = []
            for part in split_top(inner):
                match = SORT_KEY_PART.match(part)
                if match is None:
                    return None
                keys.append((match.group(2) or match.group(3), match.group(1) == "-"))
        else:
            return None
    if keys is None:
        return "descending" if reverse else ""
    return "by " + ", ".join(name + (" descending" if down != reverse else "") for name, down in keys)


# if c then y = 1 else y = 2: one variable set in both cases is a value chosen with if.
ONE_LINE_IF = re.compile(r"if\s+(.+?)\s+then\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s+else\s+\2\s*=\s*(.+)$")

NO_METHODS = "Values have no methods in Axion."
# Words of other languages written bare after a value, and the Axion word for each.
BARE_HABITS = {"strip": "trim", "startswith": "starts with", "endswith": "ends with",
               "includes": "contains", "has": "contains", "ceil": "ceiling"}
OPERATIONS = ("after a value you can write: length, sort, sum, min, max, join, split, contains, "
              "starts with, ends with, lower, upper, trim, keys, round, floor, ceiling; "
              "anything else is a loop")
# Names that follow a value. After the name `exists` they mean that exists is a variable here
# (if exists then ..., exists contains x), not the file check, which stands before a path.
AFTER_A_VALUE = {"then", "else", "by", "descending", "sort", "sum", "min", "max", "join", "lower",
                 "upper", "trim", "round", "floor", "ceiling", "split", "contains", "starts",
                 "ends", "keys"}
SORT_HABITS = ("The order from high to low is written descending.",
               "sort already goes from low to high.",
               "sort by takes the name of a field alone: the element has no name here.",
               "The next field to sort by comes after a comma.")
NEEDS_ELSE = "A value chosen with if always needs else: there must be a value for both cases."
ONE_LINE_VALUE_IF = "A value chosen with if is written on one line, together with its else."


NO_COMPREHENSION = "A list is built with a loop in Axion, not inside [ ]."
COMPREHENSION_SHAPE = ("write the loops out; the shape for one loop is: ys = [] of number   then   "
                       "for x in xs   then   ys add x * 2   then   end")
NO_FORMAT_TEXT = ("Axion has no f\"...\": text is joined with +, and a number becomes text "
                  "with as text.")
FORMAT_TEXT_SHAPE = 'for example: "Total: " + total as text + " items"'


def split_colon(text):
    """`x:.2f` -> ["x", ".2f"]: split at the first colon that is not inside brackets."""
    depth = 0
    for k, ch in enumerate(text):
        depth += (ch in "([{") - (ch in ")]}")
        if ch == ":" and depth == 0:
            return [text[:k], text[k + 1:]]
    return [text]


def reverse_fix(xs):
    return (f"walk the positions from the end: for i in 0 to {xs} length - 1   and inside it "
            f"the element is {xs}[{xs} length - 1 - i]")


def joined_value_if(lines, number):
    """A value-if spread over lines, joined into one: (the line, the numbers of the other lines).

        price = if w <= 1 then 100
                else if w <= 5 then 250       ->  price = if w <= 1 then 100 else if w <= 5 then 250 else 600
                else 600

    The following lines belong to it when they start with else, carry a value, and stand
    deeper than the first line (a block else stands under its if, alone or with a condition).
    """
    def indent(text):
        return len(text) - len(text.lstrip())

    head = lines[number - 1]
    parts, numbers = [head.split("#")[0].strip()], []
    for k in range(number, len(lines)):
        text = lines[k].split("#")[0]
        if not text.strip():
            continue
        words = text.split()
        if words[0] != "else" or len(words) == 1 or indent(text) <= indent(head):
            break
        parts.append(text.strip())
        numbers.append(k + 1)
    return (" ".join(parts), numbers) if numbers else None


FOREIGN_VALUES = {
    "True": "write true",
    "False": "write false",
    "None": "Axion has no null; every variable holds a real value",
    "null": "Axion has no null; every variable holds a real value",
    "nil": "Axion has no null; every variable holds a real value",
}


def describe(tok):
    if tok.kind == "NEWLINE":
        return "end of line"
    if tok.kind == "EOF":
        return "end of program"
    if tok.kind == "TEXT":
        return "text"
    return str(tok.value)


COMPARISONS = ("==", "!=", "<", ">", "<=", ">=")

# Words that are operations only right after a value (xs sum); anywhere else they are
# ordinary names (sum = 0), because every model uses them as variable names.
LIST_WORDS = ("sort", "sum", "min", "max", "join")
# The same for text (v0.3): s lower, s split ",", s contains "a", s starts with "a".
TEXT_WORDS = ("lower", "upper", "trim")
NUMBER_WORDS = ("round", "floor", "ceiling")
VALUE_WORDS = (LIST_WORDS + TEXT_WORDS + NUMBER_WORDS
               + ("split", "contains", "starts", "ends", "keys"))

# Keywords that authors pick as variable names; where a value is expected they get P214.
NAME_LIKE_KEYWORDS = {"value", "index", "text", "number", "bool", "list", "add", "remove",
                      "input", "allow", "print", "break"}

# xs.append(1) and friends: habits from other languages (spec §17).
METHOD_HINTS = {
    "append": "xs add value", "push": "xs add value", "add": "xs add value",
    "remove": "xs remove value v, or xs remove index i", "pop": "xs remove index i",
    "len": "xs length", "length": "xs length", "size": "xs length", "count": "xs length",
    "sort": "xs sort", "sum": "xs sum", "min": "xs min", "max": "xs max",
    "join": "xs join separator",
    # text (v0.3)
    "split": "s split separator", "strip": "s trim", "trim": "s trim",
    "lower": "s lower", "upper": "s upper", "toLowerCase": "s lower", "toUpperCase": "s upper",
    "startswith": "s starts with part", "startsWith": "s starts with part",
    "endswith": "s ends with part", "endsWith": "s ends with part",
    "contains": "xs contains value", "includes": "xs contains value",
    "replace": '(s split "a") join "b"',
    "keys": "d keys", "values": "go over the keys: for k in d keys, and read d[k]",
    "items": "go over the keys: for k in d keys, and read d[k]",
    "get": "if d contains k then d[k] else 0",
    "find": "Axion has no search for a position: take the text apart with split, "
            "or go over the positions with a loop",
    "index": "Axion has no search for a position: go over the positions with a loop",
    "indexOf": "Axion has no search for a position: go over the positions with a loop",
    "reverse": "Axion has no reverse: walk the positions from the end with a loop",
    "extend": "two lists are joined with +: xs = xs + ys",
    "insert": "at the start: xs = [value] + xs   in the middle: "
              "xs = xs[0 to i - 1] + [value] + xs[i to xs length - 1]",
}
# method -> the Axion words that take its place when it has no argument / exactly one argument
METHOD_WORDS = {"strip": "trim", "trim": "trim", "lower": "lower", "upper": "upper",
                "toLowerCase": "lower", "toUpperCase": "upper"}
METHOD_WORDS_ONE = {"split": "split", "startswith": "starts with", "startsWith": "starts with",
                    "endswith": "ends with", "endsWith": "ends with", "contains": "contains",
                    "includes": "contains"}


class Parser:
    def __init__(self, tokens, source):
        self.tokens = tokens
        self.pos = 0
        self.depth = 0          # how many blocks we are inside (0 = top level)
        self.openers = []       # the if / for / function tokens of the open blocks, outermost first
        self.loose_empty_list = False   # accept a bare [] (only to work out its type for a Fix)
        self.comma_owner = 0    # inside f( ), [ ] or { }: there a comma separates the items
        self.lines = normalize_source(source).split("\n")
        # Does the program read files at all? (Hints for a needless allow line depend on it.)
        self.reads_files = any(
            (t.kind == "KEYWORD" and t.value == "read"
             and not (k and tokens[k - 1].kind == "KEYWORD" and tokens[k - 1].value == "allow"))
            or (t.kind == "NAME" and t.value == "exists" and tokens[k + 1].line == t.line
                and (tokens[k + 1].kind == "TEXT" or self.is_op("(", tokens[k + 1])
                     or (tokens[k + 1].kind == "NAME" and tokens[k + 1].value not in AFTER_A_VALUE)))
            for k, t in enumerate(tokens))

    def snippet(self, node):
        """The exact source text of a node (used to build Fix hints)."""
        return self.lines[node.line - 1][node.col - 1:node.end - 1]

    # --- helpers ---
    def cur(self):
        return self.tokens[self.pos]

    def peek(self, k=1):
        return self.tokens[min(self.pos + k, len(self.tokens) - 1)]

    def advance(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def is_op(self, value, tok=None):
        tok = tok or self.cur()
        return tok.kind == "OP" and tok.value == value

    def print_call_habit(self):
        """print("a", x) from other languages: detect a comma inside print( ... )."""
        start = self.pos
        open_tok = self.advance()
        if self.is_op(")") and self.peek().kind in ("NEWLINE", "EOF"):      # print()
            self.fail("P202", open_tok, "print needs a value.", fix='print ""   (an empty line)',
                      length=2)
        first = self.expression()
        if self.is_op(","):
            values = [first]
            while self.is_op(","):
                self.advance()
                if self.cur().kind in ("NAME", "KEYWORD") and self.is_op("=", self.peek()):
                    self.fail("P202", self.cur(), "print takes one value and always ends the line.",
                              fix="build the whole line first with +, then print it once",
                              length=self.peek().end - self.cur().col)      # print(x, end="")
                values.append(self.expression())
            each = ", then ".join(f"print {self.snippet(v)}" for v in values)
            raise AxionError("P202", first.line, first.col - 1,
                             "print takes exactly one value.",
                             fix=f"one value per print: {each}; or join text with +",
                             length=values[-1].end - first.col + 2)
        self.pos = start                    # an ordinary print (x): parse it normally

    def keyword_as_name(self, tok):
        self.fail("P214", tok, f"{tok.value} is a keyword and cannot be used as a name.",
                  fix=f"choose another name, e.g. my_{tok.value}")

    def fail(self, code, tok, message, fix=None, length=None, affected=None):
        raise AxionError(code, tok.line, tok.col, message, fix=fix,
                         length=length if length is not None else tok.end - tok.col,
                         affected=affected)

    # --- Fix hints show the whole corrected line, in the author's own names ---
    def whole_line(self, line, col_from, col_to, replacement):
        """The source line with columns [col_from, col_to) replaced."""
        text = self.lines[line - 1]
        return (text[:col_from - 1] + replacement + text[col_to - 1:]).strip()

    def lines_like(self, pattern, except_line):
        """Other lines with the same mistake (reported as 'The same mistake is on lines')."""
        return [k for k, text in enumerate(self.lines, 1)
                if k != except_line and re.match(pattern, text.lstrip())]

    def line_alone(self):
        """Parse one line without its block: a statement, or the header of if / else if / for / while."""
        tok = self.cur()
        if tok.kind in ("NEWLINE", "EOF"):
            return
        if tok.kind == "KEYWORD" and tok.value in ("end", "function", "allow", "input"):
            return
        if self.is_keyword("else"):
            self.advance()
            if not self.is_keyword("if"):
                return
        if self.is_keyword("if") or self.is_keyword("while"):
            self.advance()
            self.expression()
        elif self.is_keyword("for"):
            self.for_header()
            return
        else:
            self.statement()
        self.end_of_statement()

    def membership_habit(self, tok):
        """x in xs / x not in xs from other languages (in belongs to the for header only)."""
        negated = self.is_keyword("not", tok) and self.is_keyword("in", self.peek())
        if self.is_keyword("in", tok) or negated:
            last = self.peek() if negated else tok
            text = self.lines[tok.line - 1]
            path = r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*|\[[^\[\]]*\])*"
            value = r'(?:"[^"]*"|[0-9]+(?:\.[0-9]+)?|' + path + ")"
            left = re.search(f"({value})\\s*$", text[:tok.col - 1])
            right = re.match(f"\\s*({path})", text[last.end - 1:])
            fix = "write the list first: xs contains value"
            if left and right:
                test = f"{right.group(1)} contains {left.group(1)}"
                fix = (text[:left.start(1)] + ("not " if negated else "") + test
                       + text[last.end - 1 + right.end():]).strip()
            self.fail("P202", tok, "in works only in a for header; a membership test is "
                                   "written with contains.", fix=fix, length=last.end - tok.col)

    def stray_else(self, tok, body, message):
        """else after an if that an end has already closed: name that end."""
        last = body[-1] if body else None
        if isinstance(last, If):
            self.fail("P211", tok, f"This else comes after the end on line {last.end_line}, "
                                   f"which already closed its if.",
                      fix=f"remove the end on line {last.end_line}: an if chain has one end, "
                          f"after its last branch")
        self.fail("P211", tok, message)

    def closing_paren(self, line, open_col):
        """Column of the ) that closes the ( at open_col, or None."""
        text = self.lines[line - 1]
        depth, k, in_text = 0, open_col - 1, False
        while k < len(text):
            ch = text[k]
            if in_text:
                if ch == "\\":
                    k += 1
                elif ch == '"':
                    in_text = False
            elif ch == '"':
                in_text = True
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return k + 1
            k += 1
        return None

    @staticmethod
    def top_level_comma(args):
        """The arguments of a call split at commas outside brackets and text, or None if one."""
        parts, depth, start, in_text, k = [], 0, 0, False, 0
        while k < len(args):
            ch = args[k]
            if in_text:
                if ch == "\\":
                    k += 1
                elif ch == '"':
                    in_text = False
            elif ch == '"':
                in_text = True
            elif ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            elif ch == "," and depth == 0:
                parts.append(args[start:k].strip())
                start = k + 1
            k += 1
        if not parts:
            return None
        return parts + [args[start:].strip()]

    def method_fix(self, target, name):
        """xs.append(v) -> xs add v, written with the author's own names."""
        generic = METHOD_HINTS.get(name.value, "use the matching statement or operator")
        open_tok = self.cur()
        close_col = self.closing_paren(open_tok.line, open_tok.col)
        if isinstance(target, Name) and target.name in ("math", "Math") and close_col is not None:
            inside = self.lines[open_tok.line - 1][open_tok.col:close_col - 1].strip()
            parts = self.top_level_comma(inside) or [inside]
            parts = [p if re.fullmatch(r"[A-Za-z_0-9.\[\]]+", p) else f"({p})" for p in parts]
            shapes = {"sqrt": "({0} ** 0.5)", "floor": "({0} floor)", "ceil": "({0} ceiling)",
                      "trunc": "({0} floor)", "round": "({0} round 0)", "pow": "({0} ** {1})",
                      "abs": "(if {0} < 0 then 0 - {0} else {0})",
                      "fabs": "(if {0} < 0 then 0 - {0} else {0})"}
            shape = shapes.get(name.value)
            if shape and len(parts) == shape.count("{1}") + 1 and all(parts):
                return self.whole_line(open_tok.line, target.col, close_col + 1, shape.format(*parts))
            return "Axion has no math library: powers are **, a root is ** 0.5, and there are round, floor, ceiling"
        if close_col is None or name.value not in METHOD_HINTS:
            return generic
        text = self.lines[open_tok.line - 1]
        args = text[open_tok.col:close_col - 1].strip()
        xs = self.snippet(target)
        if name.value in ("len", "length", "size", "count"):
            if args:
                return generic
            return self.whole_line(open_tok.line, target.col, close_col + 1, f"{xs} length")
        alone_on_line = (not text[:target.col - 1].strip()
                         and not text[close_col:].split("#")[0].strip())
        if name.value == "sort":                     # xs.sort(key=lambda t: t.age, reverse=True)
            words = python_sort_keys(split_top(args)) if args else ""
            if words is None:
                return ("sort by takes the name of a field: build a list of objects that keep "
                        "the value to sort by in a field, then sort that list by it")
            value = f"{xs} sort {words}".strip()
            if alone_on_line:                        # as a statement it changed the list itself
                return f"{xs} = {value}"
            return self.whole_line(open_tok.line, target.col, close_col + 1, value)
        if name.value == "reverse":
            return reverse_fix(xs)
        if name.value == "extend":
            return f"{xs} = {xs} + {args}" if args and alone_on_line else generic
        if name.value == "insert":
            parts = self.top_level_comma(args)
            if parts and len(parts) == 2 and parts[0] == "0" and alone_on_line:
                return f"{xs} = [{parts[1]}] + {xs}"
            return generic
        if name.value in ("sum", "min", "max"):
            if args:
                return generic
            return self.whole_line(open_tok.line, target.col, close_col + 1, f"{xs} {name.value}")
        if name.value in METHOD_WORDS:               # s.strip() -> s trim
            if args:
                return generic
            return self.whole_line(open_tok.line, target.col, close_col + 1,
                                   f"{xs} {METHOD_WORDS[name.value]}")
        if name.value in METHOD_WORDS_ONE:           # s.split(",") -> s split ","
            if not args or self.top_level_comma(args):
                return generic
            return self.whole_line(open_tok.line, target.col, close_col + 1,
                                   f"{xs} {METHOD_WORDS_ONE[name.value]} {args}")
        if name.value == "keys":                     # d.keys() -> d keys
            if args:
                return generic
            return self.whole_line(open_tok.line, target.col, close_col + 1, f"{xs} keys")
        if name.value == "get":                      # d.get(k, 0) -> (if d contains k then d[k] else 0)
            parts = self.top_level_comma(args)
            if parts is None and args:
                return self.whole_line(open_tok.line, target.col, close_col + 1, f"{xs}[{args}]")
            if not parts or len(parts) != 2:
                return generic
            key, default = parts
            return self.whole_line(open_tok.line, target.col, close_col + 1,
                                   f"(if {xs} contains {key} then {xs}[{key}] else {default})")
        if name.value == "replace":                  # s.replace(a, b) -> (s split a) join b
            parts = self.top_level_comma(args)
            if not parts or len(parts) != 2:
                return generic
            return self.whole_line(open_tok.line, target.col, close_col + 1,
                                   f"({xs} split {parts[0]}) join {parts[1]}")
        if name.value == "join":                 # ", ".join(words) -> words join ", "
            if not args:
                return generic
            return self.whole_line(open_tok.line, target.col, close_col + 1, f"{args} join {xs}")
        if name.value in ("append", "push", "add"):
            statement = f"{xs} add {args}" if args else None
        elif name.value == "remove":
            statement = f"{xs} remove value {args}" if args else None
        elif name.value == "pop":
            where = args if args else f"{xs} length - 1"
            statement = f"{xs} remove index {where}"
            taken = re.fullmatch(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*", text[:target.col - 1])
            if taken and not text[close_col:].split("#")[0].strip():      # x = xs.pop()
                return f"two lines: {taken.group(1)} = {xs}[{where}]   then   {statement}"
        else:
            return generic
        if statement is None:
            return generic
        alone = not text[:target.col - 1].strip() and not text[close_col:].split("#")[0].strip()
        return statement if alone else f"use a statement on its own line: {statement}"

    # --- program and statements ---
    def parse(self):
        statements = []
        phase = 0                 # 0 = allow lines, 1 = input lines, 2 = code (spec §1)
        while self.cur().kind != "EOF":
            if self.cur().kind == "NEWLINE":
                self.advance()
                continue
            tok = self.cur()
            if self.is_keyword("else"):
                self.stray_else(tok, statements, "else without a matching if.")
            st = self.statement()
            if isinstance(st, Allow):
                if phase > 0:
                    self.fail("P215", tok, "allow must come first, before input and code.",
                              fix="move this line to the top of the program" if self.reads_files
                              else "delete this line: this program reads no files")
            elif isinstance(st, Input):
                if phase > 1:
                    self.fail("P215", tok, "input must come before the code.",
                              fix="move this line up, after the allow lines")
                phase = 1
            else:
                phase = 2
            statements.append(st)
            self.end_of_statement()
        return Program(statements)

    def statement(self):
        tok = self.cur()
        if tok.kind == "KEYWORD":
            if self.is_op("=", self.peek()):
                self.keyword_as_name(tok)
            if tok.value == "print":
                self.advance()
                if self.is_op("("):
                    self.print_call_habit()
                value = self.expression()
                return Print(value, tok.line, tok.col, value.end)
            if tok.value == "if":
                return self.if_statement()
            if tok.value == "for":
                return self.for_statement()
            if tok.value == "function":
                if self.depth > 0:
                    self.fail("P215", tok, "Functions can only be defined at the top level.",
                              fix="move this function out of the block")
                return self.function_definition()
            if tok.value in ("allow", "input"):
                if self.depth > 0:
                    self.fail("P215", tok, f"{tok.value} must be at the top of the program, not in a block.")
                return self.allow_statement() if tok.value == "allow" else self.input_statement()
            if tok.value == "return":
                self.advance()
                if self.cur().kind in ("NEWLINE", "EOF"):
                    return Return(None, tok.line, tok.col, tok.end)
                value = self.expression()
                return Return(value, tok.line, tok.col, value.end)
            if tok.value == "while":
                return self.while_statement()
            if tok.value in ("break", "continue", "exit"):
                self.advance()
                if tok.value == "exit":
                    self.exit_habits(tok)
                kind = {"break": Break, "continue": Continue, "exit": Exit}[tok.value]
                return kind(tok.line, tok.col, tok.end)
            if tok.value == "else":
                self.fail("P211", tok, "else without a matching if.")
            if tok.value == "end":
                above = next((text for text in reversed(self.lines[:tok.line - 1]) if text.strip()), "")
                if re.search(r"=\s*if\b.*\bthen\b.*\belse\b", above.split("#")[0]):
                    self.fail("P212", tok, "A value chosen with if has no end: its line is the "
                                           "whole of it.", fix="delete this end")
                self.fail("P212", tok, "end without an open block: there is one end too many "
                                       "at or above this line.",
                          fix="check the blocks above: every if, for, while and function has exactly one end")
            self.fail("P202", tok, f"A statement cannot start with {tok.value}.",
                      fix="start with a name (x = ...), print, if, for, while, function or return")
        if tok.kind == "NAME":
            self.elif_habit(tok)
            if tok.value in FOREIGN_STATEMENTS:
                self.fail("P210", tok, f"{tok.value} is not Axion syntax.",
                          fix=FOREIGN_STATEMENTS[tok.value])
            nxt = self.peek()
            used_as_name = ((nxt.kind == "OP" and nxt.value in ("=", "[", ".", "+", "-", "*", "/", "("))
                            or (nxt.kind == "KEYWORD" and nxt.value in ("add", "remove")))
            if tok.value in FOREIGN_WORDS and not used_as_name:
                message, fix = FOREIGN_WORDS[tok.value]
                said = re.match(r"\s*(?:raise|throw)\s+(?:new\s+)?[A-Za-z_.]+\((\".*\")\)\s*$",
                                self.lines[tok.line - 1].split("#")[0])
                if said:                             # raise ValueError("bad input")
                    fix = f"two lines: print {said.group(1)}   then   exit"
                if tok.value in ("raise", "throw") and any(o.value == "function" for o in self.openers):
                    fix = ("a function cannot stop the program: return a value that says what "
                           "went wrong, and let the main program print it and exit")
                self.fail("P210", tok, message, fix=fix,
                          affected=self.lines_like(tok.value + r"\b", tok.line))
            if self.is_op(",", nxt):
                self.tuple_assignment(tok)
            colon, equals = self.peek(), self.peek(2)
            if (self.is_op(":", colon) and self.is_op("=", equals) and colon.end == equals.col
                    and colon.line == equals.line):
                others = self.lines_like(r"[A-Za-z_][A-Za-z0-9_]*\s*:=", tok.line)
                self.fail("P210", colon, ":= is not Axion syntax; assignment is =.",
                          fix=self.whole_line(tok.line, colon.col, equals.end, "=")
                              + ("   (the same on every line)" if others else ""),
                          length=2, affected=others)
            if self.is_op("=", self.peek()):
                self.advance()
                self.advance()
                value = self.expression()
                return Assign(tok.value, value, tok.line, tok.col, value.end)
            return self.target_statement()
        if self.is_op("//"):
            self.fail("P210", tok, "A comment starts with #; // is whole division.",
                      fix=self.whole_line(tok.line, tok.col, tok.end, "#"), length=2)
        self.fail("P202", tok, f"Expected a statement, got {describe(tok)}.")

    def elif_habit(self, tok):
        if tok.kind == "NAME" and tok.value in ("elif", "elseif"):
            rest = self.lines[tok.line - 1][tok.end - 1:].strip()
            self.fail("P210", tok, f"{tok.value} is not Axion syntax.",
                      fix=f"else if {rest}" if rest else "Axion writes else if",
                      affected=self.lines_like(r"(elif|elseif)\b", tok.line))

    def target_statement(self):
        """Statements that change a part of a value: xs[i] = v, xs add v, xs remove ..."""
        tok = self.cur()
        target = self.access()
        if isinstance(target, Call) and self.cur().kind in ("NEWLINE", "EOF"):
            return CallStatement(target, target.line, target.col, target.end)
        if self.is_op(","):                      # xs[i], xs[j] = xs[j], xs[i]
            self.tuple_assignment(tok, at=self.cur())
        self.augmented(tok, target)
        if self.is_op("="):
            self.advance()
            value = self.expression()
            if isinstance(target, Index):
                return SetItem(target, value, tok.line, tok.col, value.end)
            if isinstance(target, Field):
                return SetField(target, value, tok.line, tok.col, value.end)
            self.fail("P202", tok, "Only a variable, a list element or a field can be assigned.",
                      length=target.end - target.col)
        if self.is_keyword("add"):
            self.advance()
            value = self.expression()
            return ListAdd(target, value, tok.line, tok.col, value.end)
        if self.is_keyword("remove"):
            remove_tok = self.advance()
            if self.is_keyword("index") or self.is_keyword("value") or self.is_word("key"):
                mode = self.advance().value
                value = self.expression()
                return ListRemove(target, mode, value, tok.line, tok.col, value.end)
            self.fail("P202", self.cur(), "remove needs index or value (for a dictionary: key).",
                      fix=f"{self.snippet(target)} remove index 0, or "
                          f"{self.snippet(target)} remove value x, or "
                          f"{self.snippet(target)} remove key k")
        name = self.snippet(target)
        word = self.cur()
        if word.kind == "NAME" and word.value in LIST_WORDS:
            line = self.lines[tok.line - 1].strip()
            if word.value == "sort":         # results sort by total descending
                self.fail("P202", tok, f"sort gives a new list; {name} itself does not change.",
                          fix=f"{name} = {line}", length=word.end - tok.col)
            self.fail("P202", tok, f"{name} {word.value} is a value, not a statement.",
                      fix=f"store it: result = {line}   or print it: print {line}",
                      length=word.end - tok.col)
        if isinstance(target, Name) and word.kind in ("NAME", "TEXT", "NUMBER") and word.line == tok.line:
            # two bare words (include math, goto 5): a statement word of another language
            self.fail("P202", tok, f"{name} is not a statement of Axion.", fix=STATEMENT_STARTS,
                      length=target.end - target.col)
        self.fail("P202", tok, "Expected a statement.",
                  fix=f"assign with {name} = value, or print with print {name}",
                  length=target.end - target.col)

    def augmented(self, tok, target):
        """x += 1, x++: the variable is written on both sides."""
        op, nxt = self.cur(), self.peek()
        if op.kind != "OP" or op.line != tok.line or nxt.col != op.end:
            return
        name = self.snippet(target)
        pattern = r"[A-Za-z_][A-Za-z0-9_.\[\]\" ]*?\s*(\+\+|--|(\+|-|\*\*|\*|//|/|%)=)"
        others = self.lines_like(pattern, tok.line)
        every = "   (the same on every line)" if others else ""
        if op.value in ("+", "-") and self.is_op(op.value, nxt) and self.peek(2).kind in ("NEWLINE", "EOF"):
            self.fail("P210", op, f"{op.value * 2} is not Axion syntax: the variable is written "
                                  f"on both sides.",
                      fix=f"{name} = {name} {op.value} 1" + every, length=2, affected=others)
        if op.value not in AUGMENTED or not self.is_op("=", nxt):
            return
        rest = self.lines[tok.line - 1][nxt.end - 1:].split("#")[0].strip()
        one = re.fullmatch(r"\[([^\[\],]+)\]", rest)
        simple = re.fullmatch(r'[A-Za-z0-9_.]+|"[^"]*"|[A-Za-z0-9_.]+\[[^\[\]]*\]|\(.*\)', rest)
        if op.value == "+" and one:                      # xs += [5]
            fix = f"{name} add {one.group(1).strip()}"
        else:
            value = rest if simple or op.value == "+" else f"({rest})"
            fix = f"{name} = {name} {op.value} {value}"
        self.fail("P210", op, f"{op.value}= is not Axion syntax: the variable is written on "
                              f"both sides.",
                  fix=fix + every, length=len(op.value) + 1, affected=others)

    def tuple_assignment(self, tok, at=None):
        """a, b = b, a % b   and   xs[i], xs[j] = xs[j], xs[i]: a line sets one variable."""
        message = "A line sets one variable."
        at = at or self.peek()
        text = self.lines[tok.line - 1].split("#")[0]
        equals = re.search(r"(?<![=!<>])=(?!=)", text)
        targets = split_top(text[:equals.start()].strip()) if equals else []
        values = split_top(text[equals.end():].strip()) if equals else []
        if len(targets) != 2 or len(values) != 2 or not all(targets + values):
            self.fail("P202", at, message, fix="write one line for each variable")
        first, second = targets
        simple = re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", first)
        mention = rf"\b{first}\b" if simple else re.escape(first)
        if re.search(mention, values[1]):            # the second value needs the old first
            keep = f"old_{first}" if simple else "kept"
            later = re.sub(mention, keep, values[1])
            fix = (f"three lines: {keep} = {first}   then   {first} = {values[0]}"
                   f"   then   {second} = {later}")
        else:
            fix = f"two lines: {first} = {values[0]}   then   {second} = {values[1]}"
        self.fail("P202", at, message, fix=fix)

    def end_of_statement(self):
        tok = self.cur()
        if tok.kind == "NEWLINE":
            self.advance()
            return
        if tok.kind == "EOF":
            return
        self.membership_habit(tok)
        self.colon_habit(tok)
        if self.is_keyword("end") and re.search(r"\bthen\b", self.lines[tok.line - 1][:tok.col - 1]):
            before = self.tokens[self.pos - 1]
            self.fail("P210", tok, "A value chosen with if has no end: its line is the whole of it.",
                      fix=self.whole_line(tok.line, before.end, tok.end, ""))
        if self.is_keyword("if"):                        # x = 1 if c else 2
            choice = PYTHON_CHOICE.match(self.lines[tok.line - 1].split("#")[0])
            fix = "write the condition first: if condition then a else b"
            if choice and not re.search(r"\b(if|else)\b", " ".join(choice.groups()[1:])):
                head, yes, cond, no = choice.groups()
                fix = f"{head.strip()} if {cond} then {yes} else {no}"
            elif choice:                     # a if c else b if d else e
                fix = ("write each condition first, the inner choice in parentheses: "
                       "if c then a else (if d then b else e)")
            self.fail("P210", tok, "A value chosen with if starts with if: if condition then a "
                                   "else b.", fix=fix)
        if tok.kind == "NAME" and tok.value in ("then", "do"):
            before = self.tokens[self.pos - 1]
            alone_on_line = self.peek().kind in ("NEWLINE", "EOF")
            fix = (self.whole_line(tok.line, before.end, tok.end, "") if alone_on_line else
                   "end the line after the "
                   f"{'condition' if tok.value == 'then' else 'loop header'}, put the rest on "
                   "the next lines and close the block with end")
            if tok.value == "then":
                one_line = ONE_LINE_IF.match(self.lines[tok.line - 1].strip())
                if one_line:                 # if c then y = 1 else y = 2
                    cond, name, yes, no = one_line.groups()
                    fix = f"{name} = if {cond} then {yes} else {no}"
                # then exists only in a value: x = if c then a else b
                self.fail("P210", tok, "A block if has no then: the line itself ends the "
                                       "condition.", fix=fix)
            self.fail("P210", tok, "Axion has no do: the line itself ends the loop header.",
                      fix=fix)
        before = self.tokens[self.pos - 1]
        after_value = (before.kind in ("NAME", "NUMBER", "TEXT")
                       or (before.kind == "OP" and before.value in (")", "]", "}"))
                       or (before.kind == "KEYWORD" and before.value in ("true", "false", "length")))
        if after_value:
            self.division_words(tok)
        if (before.kind == "NAME" and before.value in LIST_WORDS and before.line == tok.line
                and tok.kind == "NAME" and not self.is_op("=", self.peek())):
            self.list_word_first(before)                 # row_sum = sum row
        if tok.kind == "NAME" and after_value and not self.is_op("=", self.peek()):
            if tok.value in BARE_HABITS:             # s strip, s startswith "a"
                word = BARE_HABITS[tok.value]
                self.fail("P202", tok, f"{tok.value} is written {word} in Axion.",
                          fix=self.whole_line(tok.line, tok.col, tok.end, word),
                          length=tok.end - tok.col)
            if tok.value in ("reverse", "reversed"):
                self.fail("P202", tok, "Axion has no reverse.", fix=reverse_fix(self.snippet_before(tok)))
            # words join ", " exists, words reverse does not: say what does.
            self.fail("P202", tok, f"{tok.value} is not an operation in Axion.", fix=OPERATIONS)
        if tok.kind == "KEYWORD" and tok.value == "add" and after_value:
            self.add_as_value(tok)
        if tok.kind in ("NAME", "KEYWORD", "NUMBER", "TEXT"):
            self.fail("P201", tok, "Only one statement per line is allowed.",
                      fix="move this to its own line")
        if self.is_op("="):
            self.fail("P202", tok, "Unexpected =: assignment is a statement, not a value; "
                                   "compare with ==.",
                      fix=self.whole_line(tok.line, tok.col, tok.end, "=="))
        self.fail("P202", tok, f"Unexpected {describe(tok)}.")

    def colon_habit(self, tok):
        """if x > 2:  — a line does not end with a colon."""
        if not (self.is_op(":", tok) and self.peek().kind in ("NEWLINE", "EOF")):
            return
        others = [k for k, text in enumerate(self.lines, 1)
                  if k != tok.line and re.search(r":\s*$", text.split("#")[0])
                  and re.match(r"\s*(if|else|for|while|function|def|elif)\b", text)]
        self.fail("P210", tok, "A line does not end with : in Axion; the block is closed with end.",
                  fix=self.whole_line(tok.line, tok.col, tok.end, "")
                      + ("   (the same on every line)" if others else ""),
                  affected=others)

    def snippet_before(self, tok):
        """The source of the simple value (a name with fields and indexes) right before tok."""
        text = self.lines[tok.line - 1][:tok.col - 1].rstrip()
        match = re.search(r"[A-Za-z_][A-Za-z0-9_.\[\]]*$", text)
        return match.group(0) if match else "xs"

    def division_words(self, tok):
        """t div 60, t mod 60: the words of other languages for // and %."""
        if tok.kind == "NAME" and tok.value in ("div", "mod"):
            text = self.lines[tok.line - 1].strip()
            fixed = re.sub(r"\bmod\b", "%", re.sub(r"\bdiv\b", "//", text))
            self.fail("P202", tok, "Whole division is written // and the remainder %.",
                      fix=fixed)

    def list_word_first(self, word):
        """sum row, max scores, sort people by age: the word comes after the list."""
        fix = f"write the list first: xs {word.value}"
        try:
            operand = self.access()
        except AxionError:
            operand = None
        if operand is not None and operand.line == word.line:
            fix = self.whole_line(word.line, word.col, operand.end,
                                  f"{self.snippet(operand)} {word.value}")
        self.fail("P202", word, f"{word.value} comes after the list.", fix=fix,
                  length=word.end - word.col)

    def add_as_value(self, tok):
        """xs = xs add v, ys = xs add v: add is a statement, it changes the list in place."""
        match = re.match(r"(\w+)\s*=\s*(.+?)\s+add\s+(.+)$", self.lines[tok.line - 1].strip())
        if match is None:
            return
        name, source, value = match.groups()
        if name == source:
            fix = f"{name} add {value}"
        else:
            fix = f"two lines: {name} = {source}   then   {name} add {value}"
        self.fail("P202", tok, "add changes the list itself and gives no value.", fix=fix)

    # --- blocks (spec §11) ---
    def block(self, opener):
        """Statements up to else / end. `opener` is the token that started the block."""
        self.depth += 1
        self.openers.append(opener)
        try:
            return self.block_body(opener)
        finally:
            self.depth -= 1
            self.openers.pop()

    def block_body(self, opener):
        body = []
        indented = None           # is the body of this block written deeper than its opener?
        while True:
            tok = self.cur()
            if tok.kind == "NEWLINE":
                self.advance()
                continue
            if tok.kind == "EOF":
                chain = " (an if / else if / else chain has one end)" if opener.value == "if" else ""
                self.fail("P212", opener,
                          f"{opener.value} is never closed: an end is missing between this line "
                          f"and the end of the program.",
                          fix=f"add the missing end where this {opener.value} block really finishes{chain}")
            if self.is_keyword("else") or self.is_keyword("end"):
                if tok.value == "end" or opener.value == "if":
                    self.check_closer(tok, opener)
                return body
            if opener.value == "if":
                self.elif_habit(tok)          # under its if it is an else if, not a line outside
            if indented is None:
                indented = tok.col > opener.col
            elif indented and tok.col <= opener.col:
                # The body is indented and this line is not: by its look the block is over,
                # but no end has closed it.
                self.fail("P216", tok, f"This line is outside the {opener.value} on line "
                                       f"{opener.line} by its indentation, but that {opener.value} "
                                       f"has no end yet.",
                          fix=f"add an end for the {opener.value} before this line")
            body.append(self.statement())
            self.end_of_statement()

    def check_closer(self, tok, opener):
        """Indentation is optional, but it must not contradict end: an end (or else) stands
        exactly under the line that opened its block."""
        if tok.col == opener.col:
            return
        word = tok.value
        if tok.col < opener.col:
            outer = next((o for o in reversed(self.openers[:-1]) if o.col == tok.col), None)
            if outer is not None:
                self.fail("P216", tok, f"This {word} lines up with the {outer.value} on line "
                                       f"{outer.line}, but the {opener.value} on line {opener.line} "
                                       f"is still open.",
                          fix=f"add an end for the {opener.value} before this line")
            self.fail("P216", tok, f"This {word} closes the {opener.value} on line {opener.line} "
                                   f"but stands to the left of it.",
                      fix=f"put {word} exactly under its {opener.value}; if it was meant for an "
                          f"outer block, add the end that is missing above")
        self.fail("P216", tok, f"This {word} closes the {opener.value} on line {opener.line} "
                               f"but is indented deeper than it.",
                  fix=f"put {word} exactly under its {opener.value}; if it was meant for an inner "
                      f"block, an end above is extra")

    def if_statement(self):
        if_tok = self.advance()
        condition = self.expression()
        self.end_of_statement()
        branches = [Branch(condition, self.block(if_tok), if_tok.line, if_tok.col, condition.end)]
        else_branch = None

        while self.is_keyword("else"):
            else_tok = self.advance()
            if self.is_keyword("if"):
                self.advance()
                if else_branch is not None:
                    self.fail("P211", else_tok, "else if cannot come after else.",
                              fix="move else to the end of the chain")
                cond = self.expression()
                self.end_of_statement()
                branches.append(Branch(cond, self.block(if_tok), else_tok.line, else_tok.col, cond.end))
                continue
            if else_branch is not None:
                self.fail("P211", else_tok, "An if chain can have only one else.")
            if self.cur().kind not in ("NEWLINE", "EOF"):
                extra = self.cur()
                self.colon_habit(extra)
                rest = self.lines[extra.line - 1][extra.col - 1:].split("#")[0].strip()
                self.fail("P211", extra, "Nothing may follow else on its line.",
                          fix=f"write else if {rest}", length=len(rest))
            self.end_of_statement()
            else_branch = Branch(None, self.block(if_tok), else_tok.line, else_tok.col, else_tok.end)

        end_tok = self.advance()          # the block stopped on `end`
        return If(branches, else_branch, if_tok.line, if_tok.col, end_tok.end, end_tok.line)

    def for_header(self):
        for_tok = self.advance()
        var = self.cur()
        if self.is_op("("):
            self.fail("P210", for_tok, "C-style for is not Axion syntax.",
                      fix="for i in 0 to n - 1")
        if var.kind == "KEYWORD":
            self.keyword_as_name(var)
        if var.kind != "NAME":
            self.fail("P202", var, f"Expected a loop variable name, got {describe(var)}.",
                      fix="for x in xs")
        self.advance()
        if self.is_op(","):                          # for k, v in d.items()
            second = self.peek()
            value = second.value if second.kind == "NAME" else "value"
            rest = self.lines[var.line - 1].split("#")[0].partition(" in ")[2].strip().rstrip(":").strip()
            walked = re.fullmatch(r"(enumerate|zip)\((.*)\)|(.+)\.items\(\)", rest)
            parts = split_top(walked.group(2)) if walked and walked.group(2) else []
            fix = (f"for {var.value} in d keys   and inside it: {value} = d[{var.value}]"
                   f"   (for positions of a list: for i in 0 to xs length - 1)")
            if walked and walked.group(3):               # for k, v in d.items()
                d = walked.group(3)
                fix = f"for {var.value} in {d} keys   and inside it: {value} = {d}[{var.value}]"
            elif walked and walked.group(1) == "enumerate" and len(parts) in (1, 2):
                xs = parts[0]
                start = re.sub(r"^start\s*=\s*", "", parts[1]) if len(parts) == 2 else "0"
                fix = (f"for {var.value} in 0 to {xs} length - 1   and inside it: "
                       f"{value} = {xs}[{var.value}]")
                if start != "0":             # the count starts from 1: that is var + 1 inside
                    fix += f"   (the number that started from {start} is {var.value} + {start})"
            elif walked and walked.group(1) == "zip" and len(parts) == 2:
                fix = (f"for i in 0 to {parts[0]} length - 1   and inside it: "
                       f"{var.value} = {parts[0]}[i]   then   {value} = {parts[1]}[i]")
            self.fail("P202", self.cur(), "for has one variable.", fix=fix)
        if not self.is_keyword("in"):
            self.fail("P202", self.cur(), f"Expected in, got {describe(self.cur())}.",
                      fix=f"for {var.value} in xs")
        self.advance()
        iterable = self.expression()
        self.end_of_statement()
        return for_tok, var, iterable

    def for_statement(self):
        for_tok, var, iterable = self.for_header()
        body = self.block(for_tok)
        if self.is_keyword("else"):
            self.stray_else(self.cur(), body, "else cannot be used in a for loop.")
        end_tok = self.advance()
        return For(var.value, var.line, var.col, iterable, body,
                   for_tok.line, for_tok.col, end_tok.end)

    def while_statement(self):
        while_tok = self.advance()
        if self.cur().kind in ("NEWLINE", "EOF"):
            self.fail("P202", while_tok, "while needs a condition.", fix="while true")
        condition = self.expression()
        self.end_of_statement()
        body = self.block(while_tok)
        if self.is_keyword("else"):
            self.stray_else(self.cur(), body, "else cannot be used in a while loop.")
        end_tok = self.advance()
        return While(condition, body, while_tok.line, while_tok.col, end_tok.end)

    def exit_habits(self, tok):
        """exit() and exit(1) of other languages; exit takes nothing in Axion."""
        if self.cur().kind in ("NEWLINE", "EOF"):
            return
        rest = self.lines[tok.line - 1][tok.end - 1:].split("#")[0].rstrip()
        self.fail("P202", self.cur(), "exit is written alone: it ends the program and takes nothing.",
                  fix=self.whole_line(tok.line, tok.end, tok.end + len(rest), ""),
                  length=len(rest.strip()))

    def allow_statement(self):
        tok = self.advance()
        if not self.is_keyword("read"):
            what = self.cur().value if self.cur().kind in ("NAME", "KEYWORD") else None
            self.fail("P202", self.cur() if what else tok,
                      f"allow {what} does not exist in this version; only allow read." if what
                      else 'allow needs a permission and a folder: the only form is allow read "folder/".',
                      fix='allow read "folder/"' if self.reads_files
                      else "delete this line: this program reads no files")
        self.advance()
        path = self.cur()
        if path.kind != "TEXT" or not path.value.strip():
            self.fail("P202", path, "allow read needs a folder in quotes.", fix='allow read "reports/"')
        self.advance()
        return Allow(path.value, tok.line, tok.col, path.end)

    def input_statement(self):
        tok = self.advance()
        name = self.cur()
        if name.kind == "KEYWORD":
            self.keyword_as_name(name)
        if name.kind != "NAME":
            self.fail("P202", name, f"Expected an input name, got {describe(name)}.",
                      fix="input orders: list of {price: number}")
        self.advance()
        if not self.is_op(":"):
            self.fail("P202", self.cur(), f"input {name.value} needs a type.",
                      fix=f"input {name.value}: number")
        self.advance()
        t = self.type_spec()
        return Input(name.value, t, tok.line, tok.col, self.tokens[self.pos - 1].end, name.col)

    def function_definition(self):
        fn_tok = self.advance()
        name = self.cur()
        if name.kind == "KEYWORD":
            self.keyword_as_name(name)
        if name.kind != "NAME":
            self.fail("P202", name, f"Expected a function name, got {describe(name)}.",
                      fix="function name(param: number) -> number")
        self.advance()
        if not self.is_op("("):
            self.fail("P202", self.cur(), f"Expected ( after {name.value}.",
                      fix=f"function {name.value}() -> number")
        self.advance()
        params = []
        seen = set()
        while not self.is_op(")"):
            if params:
                if not self.is_op(","):
                    self.division_words(self.cur())
                    self.fail("P202", self.cur(), f"Expected , or ), got {describe(self.cur())}.")
                self.advance()
            p = self.cur()
            if p.kind == "KEYWORD":
                self.keyword_as_name(p)
            if p.kind != "NAME":
                self.fail("P202", p, f"Expected a parameter name, got {describe(p)}.")
            if p.value in seen:
                self.fail("P202", p, f"Parameter {p.value} appears twice.")
            seen.add(p.value)
            self.advance()
            if not self.is_op(":"):
                self.fail("P202", p, f"Parameter {p.value} needs a type.",
                          fix=f"{p.value}: number")
            self.advance()
            params.append(Param(p.value, self.type_spec(), p.line, p.col))
            if self.is_op("="):                 # b: number = 2
                before, default = self.tokens[self.pos - 1], self.advance()
                value = self.expression()
                self.fail("P202", default, "A parameter has no default value: every call "
                                           "passes every value.",
                          fix=self.whole_line(default.line, before.end, value.end, ""))
        self.advance()                      # )
        result = None
        if self.is_op("->"):
            self.advance()
            result = self.type_spec()
        self.end_of_statement()
        body = self.block(fn_tok)
        if self.is_keyword("else"):
            self.stray_else(self.cur(), body, "else without a matching if.")
        end_tok = self.advance()
        return Function(name.value, params, result, body, fn_tok.line, fn_tok.col,
                        end_tok.end, name.col)

    # --- types (spec §2): number, text, bool, list of T, {field: T} ---
    def type_spec(self):
        tok = self.cur()
        if tok.kind == "KEYWORD" and tok.value in (NUMBER, TEXT, BOOL):
            self.advance()
            return tok.value
        if self.is_keyword("list"):
            self.advance()
            if not self.is_keyword("of"):
                self.fail("P202", self.cur(), "Expected of after list.", fix="list of number")
            self.advance()
            return ListT(self.type_spec())
        if tok.kind == "NAME" and tok.value in ("map", "dict", "dictionary", "Map", "Dict"):
            self.advance()
            if tok.value != "map":
                self.fail("P202", tok, f"The dictionary type is written map of T, not {tok.value}.",
                          fix="map of number   (text keys, number values)",
                          length=tok.end - tok.col)
            if not self.is_keyword("of"):
                self.fail("P202", self.cur(), "Expected of after map.",
                          fix="map of number   (text keys, number values)")
            self.advance()
            return MapT(self.type_spec())
        if self.is_op("{"):
            self.advance()
            fields = {}
            while True:
                name_tok = self.field_name()
                if name_tok.value in fields:
                    self.fail("P202", name_tok, f"Field {name_tok.value} appears twice.")
                if not self.is_op(":"):
                    self.fail("P202", self.cur(), f"Expected : after {name_tok.value}.",
                              fix=f"{name_tok.value}: number")
                self.advance()
                fields[name_tok.value] = self.type_spec()
                if self.is_op(","):
                    self.advance()
                    continue
                if self.is_op("}"):
                    self.advance()
                    return ObjectT(fields)
                self.fail("P202", self.cur(), f"Expected , or }}, got {describe(self.cur())}.")
        self.fail("P202", tok, f"Expected a type, got {describe(tok)}.",
                  fix="number, text, bool, list of number, map of number or {name: text}")

    def field_name(self):
        """A field name: any name, keywords included (spec §6: allowed as field names)."""
        tok = self.cur()
        if tok.kind not in ("NAME", "KEYWORD"):
            self.fail("P202", tok, f"Expected a field name, got {describe(tok)}.")
        return self.advance()

    # --- expressions, lowest precedence first (spec §7) ---
    #   10 if then else   9 and, or   8 not   7 comparisons   5 + -   4 * / // %   3 unary -
    #   2.5 **   2 words after a value (length, as, round, ...)   1 primary
    def expression(self):
        if self.is_keyword("if"):
            return self.conditional()
        return self.logical()

    def conditional(self):
        """if c then a else b: a choice between two values. else is required.

        It is a whole expression (after =, print, return, add, in an argument or a list)
        or stands in parentheses; `"a" + if c then x else y + "z"` would have two readings.
        """
        if_tok = self.advance()
        cond = self.logical()
        shape = "if condition then a else b"
        if not self.is_word("then"):
            self.fail("P202", self.cur(), f"A value chosen with if is written: {shape}; "
                                          f"then is missing here.", fix=shape)
        self.advance()
        then = self.logical()
        if not self.is_keyword("else"):
            tok = self.cur()
            if tok.kind == "KEYWORD":
                self.end_of_statement()             # x in xs, a second statement, ...
            if tok.kind == "NAME":                  # the value after then stops at a wrong word:
                self.division_words(tok)            # that word is the mistake, not a missing else
                rest = self.lines[tok.line - 1][tok.end - 1:]
                self.fail("P202", tok, f"After the value of then comes else, not {tok.value}.",
                          fix=None if re.search(r"\belse\b", rest) else
                          self.whole_line(tok.line, tok.col, tok.end, "else"))
            joined = joined_value_if(self.lines, if_tok.line)
            if joined:
                self.fail("P202", if_tok, ONE_LINE_VALUE_IF, fix=joined[0],
                          length=if_tok.end - if_tok.col)
            fix = (self.whole_line(tok.line, tok.col, tok.col, " else ...")
                   if tok.line == if_tok.line else
                   f"{self.lines[if_tok.line - 1].strip()} else ...")
            self.fail("P202", tok, NEEDS_ELSE, fix=f"{fix}   (the value for the other case)")
        self.advance()
        otherwise = self.expression()               # else if ... then ... else ... chains
        return Conditional(cond, then, otherwise, if_tok.line, if_tok.col, otherwise.end)

    def is_keyword(self, value, tok=None):
        tok = tok or self.cur()
        return tok.kind == "KEYWORD" and tok.value == value

    def logical(self):
        node = self.negation()
        first_op = None
        while self.is_keyword("and") or self.is_keyword("or"):
            tok = self.cur()
            if first_op is not None and tok.value != first_op:
                self.fail("P205", tok, "and and or cannot be mixed without parentheses.",
                          fix=f"group one side, e.g. a {first_op} (b {tok.value} c)")
            first_op = tok.value
            self.advance()
            right = self.negation()
            node = Binary(tok.value, node, right, node.line, node.col, right.end)
        return node

    def negation(self):
        if not self.is_keyword("not"):
            return self.comparison()
        tok = self.advance()
        operand = self.comparison()
        if isinstance(operand, Binary):
            self.fail("P209", tok, "not before a compound expression needs parentheses.",
                      fix=f"not ({self.snippet(operand)})", length=operand.end - tok.col)
        return Not(operand, tok.line, tok.col, operand.end)

    def comparison(self):
        node = self.range_expr()
        if self.cur().kind == "OP" and self.cur().value in COMPARISONS:
            op_tok = self.advance()
            right = self.after_operator(self.range_expr, node, op_tok)
            if self.cur().kind == "OP" and self.cur().value in COMPARISONS:
                second = self.advance()
                third = self.range_expr()
                mid = self.snippet(right)
                self.fail("P206", second, "Comparisons cannot be chained.",
                          fix=(f"{self.snippet(node)} {op_tok.value} {mid} and "
                               f"{mid} {second.value} {self.snippet(third)}"))
            node = Binary(op_tok.value, node, right, node.line, node.col, right.end)
        return node

    def range_expr(self):
        node = self.additive()
        if self.is_keyword("to"):
            op_tok = self.advance()
            right = self.after_operator(self.additive, node, op_tok)
            if self.is_keyword("to"):
                self.fail("P202", self.cur(), "to cannot be chained.")
            node = Range(node, right, node.line, node.col, right.end)
        return node

    def additive(self):
        node = self.multiplicative()
        while self.cur().kind == "OP" and self.cur().value in ("+", "-"):
            op_tok = self.advance()
            right = self.after_operator(self.multiplicative, node, op_tok)
            node = Binary(op_tok.value, node, right, node.line, node.col, right.end)
        return node

    def multiplicative(self):
        node = self.unary()
        while self.cur().kind == "OP" and self.cur().value in ("*", "/", "//", "%"):
            op_tok = self.advance()
            right = self.after_operator(self.unary, node, op_tok)
            node = Binary(op_tok.value, node, right, node.line, node.col, right.end)
        return node

    def after_operator(self, parse_next, left, op_tok):
        """Right operand of a binary operator: a unary minus may not follow directly."""
        if self.is_op("-"):
            minus = self.advance()
            inner = self.primary()
            self.fail("P207", minus, "Unary minus cannot directly follow another operator.",
                      fix=self.whole_line(minus.line, minus.col, inner.end,
                                          f"(-{self.snippet(inner)})"),
                      length=inner.end - minus.col)
        return parse_next()

    def unary(self):
        tok = self.cur()
        if self.is_op("+"):
            self.fail("P208", tok, "Unary + is not allowed.", fix="remove the +")
        if self.is_op("-"):
            self.advance()
            if self.is_op("-"):
                self.fail("P207", tok, "-- is not allowed.",
                          fix="remove both minus signs, or write -(-x)", length=2)
            operand = self.power()
            return Unary("-", operand, tok.line, tok.col, operand.end)
        return self.power()

    def power(self):
        """x ** n. Higher than unary minus and than * /; 2 ** 3 ** 2 is 2 ** (3 ** 2)."""
        node = self.postfix()
        if self.is_op("**"):
            op_tok = self.advance()
            right = self.after_operator(self.unary, node, op_tok)
            node = Binary("**", node, right, node.line, node.col, right.end)
        return node

    def postfix(self):
        """Level 2: length, as, is — each binds to the value right before it, left to right.

        read is the exception: it takes the whole expression to its right as the path,
        so read "notes/" + name reads one file. (read p) length needs parentheses.
        """
        if self.is_keyword("read"):
            tok = self.advance()
            path = self.expression()
            return Read(path, tok.line, tok.col, path.end)
        if (self.is_word("exists") and self.peek().line == self.cur().line
                and (self.peek().kind == "TEXT"
                     or (self.peek().kind == "NAME" and self.peek().value not in AFTER_A_VALUE))):
            # exists is a word only right before a path; anywhere else it is an ordinary name.
            tok = self.advance()
            path = self.expression()
            return Exists(path, tok.line, tok.col, path.end)
        node = self.access()
        while True:
            if self.is_keyword("length"):
                tok = self.advance()
                node = Length(node, node.line, node.col, tok.end)
            elif self.is_keyword("as") and self.peek().kind == "NAME" and self.peek().value in ("days", "date"):
                self.advance()                              # s as days / n as date
                tok = self.advance()
                node = DateOp(f"as {tok.value}", node, node.line, node.col, tok.end)
            elif self.is_keyword("as"):
                self.advance()
                target = self.type_spec()
                node = As(node, target, node.line, node.col, self.tokens[self.pos - 1].end)
            elif self.is_keyword("is") and self.is_word("date", self.peek()):
                self.advance()                              # s is date
                tok = self.advance()
                node = DateOp("is date", node, node.line, node.col, tok.end)
            elif self.cur().kind == "NAME" and self.cur().value in ("floor", "ceiling"):
                tok = self.advance()                        # x floor / x ceiling
                node = Round(tok.value, node, None, node.line, node.col, tok.end)
            elif self.is_word("round"):
                tok = self.advance()                        # x round 2
                nxt = self.cur()
                if nxt.kind in ("NEWLINE", "EOF") or nxt.kind == "KEYWORD" or (
                        nxt.kind == "OP" and nxt.value not in ("(", "[")):
                    self.fail("P202", tok, "round needs the number of places after it.",
                              fix=self.whole_line(tok.line, tok.col, tok.end, "round 0")
                              + "   (0 places: a whole number)", length=tok.end - tok.col)
                places = self.operand_of("round", "x round 2", node)
                node = Round("round", node, places, node.line, node.col, places.end)
            elif self.is_keyword("is"):
                is_tok = self.advance()
                if not self.is_keyword("number"):
                    self.is_habit(node, is_tok)
                tok = self.advance()
                node = IsNumber(node, node.line, node.col, tok.end)
            elif self.cur().kind == "NAME" and self.cur().value in TEXT_WORDS:
                tok = self.advance()                       # s lower / s upper / s trim
                node = TextOp(tok.value, node, node.line, node.col, tok.end)
            elif self.is_word("keys"):
                tok = self.advance()                       # d keys
                node = Keys(node, node.line, node.col, tok.end)
            elif self.is_word("split"):
                self.advance()
                separator = self.operand_of("split", 'line split ","', node)
                node = Split(node, separator, node.line, node.col, separator.end)
            elif self.is_word("contains"):
                self.advance()
                item = self.operand_of("contains", "xs contains value", node)
                node = Contains(node, item, node.line, node.col, item.end)
            elif self.cur().kind == "NAME" and self.cur().value in ("starts", "ends"):
                tok = self.advance()
                if not self.is_word("with"):
                    self.fail("P202", tok, f"{tok.value} is followed by with.",
                              fix=self.whole_line(tok.line, tok.col, tok.end, f"{tok.value} with"),
                              length=tok.end - tok.col)
                self.advance()
                part = self.operand_of(f"{tok.value} with", f'name {tok.value} with "a"', node)
                node = Affix(tok.value, node, part, node.line, node.col, part.end)
            elif self.cur().kind == "NAME" and self.cur().value in LIST_WORDS:
                word = self.cur().value
                node = self.list_word(node)
                nxt = self.cur()
                if nxt.kind == "OP" and nxt.value in ("[", ".") and nxt.line == node.line:
                    # xs sort by id descending[0]: is [0] for the word or for the list?
                    self.fail("P202", nxt, f"Put {word} and its list in parentheses before "
                                           f"taking {'an element' if nxt.value == '[' else 'a field'}.",
                              fix=self.whole_line(node.line, node.col, node.end,
                                                  f"({self.snippet(node)})"))
            elif (self.is_op(".") and self.peek().kind in ("NAME", "KEYWORD")
                  and self.is_op("(", self.peek(2))):
                self.advance()
                self.method_call(node, self.advance())
            elif self.is_keyword("index") and self.cur().line == node.line:
                name = self.snippet(node)             # keys index k: the position of k in keys
                self.fail("P202", self.cur(), "Axion has no operation that finds the position "
                                              "of a value in a list.",
                          fix=f"find it with a loop: for i in 0 to {name} length - 1   "
                              f"and inside it: if {name}[i] == value")
            else:
                return node

    def operand_of(self, word, example, target=None):
        """The one value right after split / contains / starts with / ends with."""
        tok = self.cur()
        if tok.kind in ("NEWLINE", "EOF") or (tok.kind == "OP" and tok.value in (")", "]", ",")):
            self.fail("P202", tok, f"{word} needs a value after it.", fix=example)
        operand = self.access()
        root = operand
        while isinstance(root, (Index, Field)):
            root = root.target
        if root is not operand and isinstance(root, (Text, Number)) and target is not None:
            # line split " "[0]: read as it stands, [0] would belong to " ", not to the result
            whole = self.lines[target.line - 1][target.col - 1:root.end - 1]
            self.fail("P202", self.tokens[self.pos - 1], f"Put {word} and its value in "
                      f"parentheses before taking an element or a field.",
                      fix=self.whole_line(target.line, target.col, root.end, f"({whole})"))
        return operand

    def is_word(self, value, tok=None):
        tok = tok or self.cur()
        return tok.kind == "NAME" and tok.value == value

    def list_word(self, node):
        """xs sort [by field] [descending] / xs sum / xs min / xs max / xs join separator."""
        tok = self.advance()
        if tok.value == "join":
            separator = self.access()
            return Join(node, separator, node.line, node.col, separator.end)
        if tok.value != "sort":
            if self.is_word("by") and self.cur().line == tok.line:
                self.aggregate_by(node, tok)
            return Aggregate(tok.value, node, node.line, node.col, tok.end)
        field, descending, end, more = None, False, tok.end, []
        if self.is_word("by"):
            self.advance()
            field, descending, end = self.sort_key()
            while self.is_op(","):
                if self.comma_owner:
                    # f(xs sort by a, b): a second field, or the second argument? Not guessed.
                    whole = self.lines[node.line - 1][node.col - 1:end - 1]
                    self.fail("P202", self.cur(), "After sort by a comma adds the next field; "
                                                  "inside these brackets it could also separate "
                                                  "two items.",
                              fix=f"put the sort in parentheses: ({whole}, next_field) to sort by "
                                  f"both fields, or ({whole}), ... for two items")
                self.advance()
                more.append(self.sort_key())
                end = more[-1][2]
            return Sort(node, field, descending, node.line, node.col, end,
                        tuple((name, down) for name, down, _ in more))
        nxt = self.cur()
        if self.is_word("descending"):
            end, descending = self.advance().end, True
            if self.is_word("by"):                       # sort descending by age
                field_tok = self.peek()
                self.fail("P202", self.cur(), "by comes before descending.",
                          fix=self.whole_line(nxt.line, nxt.col, field_tok.end,
                                              f"by {field_tok.value} descending"))
        else:
            self.direction_habits(nxt)
        return Sort(node, field, descending, node.line, node.col, end)

    def sort_habit(self, tok, message, fix, length=None):
        """A habit in how a sort is written. One line may hold several of them
        (sort by t.points desc then by t.name): the Fix repairs them all at once."""
        for _ in range(8):
            again = alone(fix)
            if again is None or again.message not in SORT_HABITS or not again.fix or again.fix == fix:
                break
            fix = again.fix
        self.fail("P202", tok, message, fix=fix, length=length)

    def direction_habits(self, nxt):
        """desc, reverse, asc after sort: the one word is descending, and low to high is silent."""
        if nxt.kind == "NAME" and nxt.value in ("desc", "reverse", "reversed", "down"):
            self.sort_habit(nxt, SORT_HABITS[0],
                            self.whole_line(nxt.line, nxt.col, nxt.end, "descending"))
        if nxt.kind == "NAME" and nxt.value in ("asc", "ascending"):
            before = self.tokens[self.pos - 1]
            self.sort_habit(nxt, SORT_HABITS[1], self.whole_line(nxt.line, before.end, nxt.end, ""))

    def sort_key(self):
        """One field of sort by with its own direction: (name, descending, end)."""
        first = self.cur()
        if self.is_op("-") and self.peek().kind == "NAME":       # sort by -points
            name = self.peek()
            self.sort_habit(first, SORT_HABITS[0],
                            self.whole_line(first.line, first.col, name.end, f"{name.value} descending"))
        if first.kind not in ("NAME", "KEYWORD"):                # sort by (f(x.scores))
            self.fail("P202", first, "sort by takes the name of a number field, "
                                     "not an expression.",
                      fix="build a list of objects that keep this value in a field "
                          "(for example {name: text, result: number}), then sort that "
                          "list: rows sort by result")
        name = self.field_name()
        if self.is_op(".") and self.peek().kind in ("NAME", "KEYWORD"):      # sort by t.points
            inner = self.peek()
            self.sort_habit(name, SORT_HABITS[2],
                            self.whole_line(name.line, name.col, inner.end, inner.value),
                            length=inner.end - name.col)
        end, descending = name.end, False
        if self.is_word("descending"):
            end, descending = self.advance().end, True
        else:
            self.direction_habits(self.cur())
        if self.is_word("then") and self.is_word("by", self.peek()):         # ... then by diff
            before, by = self.tokens[self.pos - 1], self.peek()
            self.sort_habit(self.cur(), SORT_HABITS[3],
                            self.whole_line(by.line, before.end, by.end, ","),
                            length=by.end - self.cur().col)
        return name.value, descending, end

    def aggregate_by(self, node, word):
        """bookings max by id: only sort has by. max by could mean the number or the element."""
        by, field = self.cur(), self.peek()
        items = self.snippet(node)
        message = (f"{word.value} has no by: it works on a list of numbers. "
                   f"Only sort has by.")
        if field.kind not in ("NAME", "KEYWORD") or field.line != word.line:
            self.fail("P202", by, message)
        if word.value == "sum":
            self.fail("P202", by, message,
                      fix=f"add the numbers up in a loop: total = 0, then for x in {items} "
                          f"with total = total + x.{field.value}")
        order = " descending" if word.value == "max" else ""
        element = f"({items} sort by {field.value}{order})[0]"
        note = ("" if self.is_op(".", self.peek(2)) else
                f"   (this is the element; add .{field.value} for its number)")
        size = "largest" if word.value == "max" else "smallest"
        self.fail("P202", by, message,
                  fix=f"the element with the {size} {field.value}: "
                      + self.whole_line(node.line, node.col, field.end, element) + note)

    def is_habit(self, node, is_tok):
        """x is not number, x is "in", x is not y: habits from other languages."""
        nxt = self.cur()
        if self.is_keyword("not") and (self.is_keyword("number", self.peek())
                                       or self.is_word("date", self.peek())):
            last = self.peek()
            self.fail("P202", is_tok, f"is not {last.value} does not exist: put not before the value.",
                      fix=self.whole_line(node.line, node.col, last.end,
                                          f"not {self.snippet(node)} is {last.value}"),
                      length=last.end - is_tok.col)
        if nxt.kind == "KEYWORD" and nxt.value in ("text", "bool", "list"):
            self.fail("P202", nxt, "Only is number and is date exist: every type is known before the run.")
        last = self.advance() if self.is_keyword("not") else is_tok
        if self.cur().kind == "NAME" and self.cur().value in ("None", "null", "nil"):
            self.fail("P210", self.cur(), f"{self.cur().value} is not Axion syntax.",
                      fix="Axion has no null: every variable holds a real value, so compare with "
                          'one (0, "", an empty list: xs length == 0) or delete this check')
        self.fail("P202", is_tok, "is is not a comparison: it exists only as value is number.",
                  fix=self.whole_line(is_tok.line, is_tok.col, last.end,
                                      "!=" if last is not is_tok else "=="),
                  length=last.end - is_tok.col)

    def access(self):
        """Level 1: a primary value followed by any number of [index] and .field."""
        node = self.primary()
        while True:
            if self.is_op("["):
                self.advance()
                if self.is_op(":"):                  # s[:5]
                    self.python_slice(node, self.cur())
                index = self.owning_commas(self.expression, owned=False)
                close = self.cur()
                if self.is_op(":"):
                    self.python_slice(node, close)
                if not self.is_op("]"):
                    self.division_words(close)
                    self.fail("P202", close, f"Expected ], got {describe(close)}.")
                self.advance()
                node = Index(node, index, node.line, node.col, close.end)
            elif self.is_op("."):
                self.advance()
                name = self.field_name()
                if self.is_op("("):
                    self.method_call(node, name)
                node = Field(node, name.value, node.line, node.col, name.end)
            else:
                return node

    def method_call(self, target, name):
        """s.strip(), xs.append(v): values have no methods; the Fix is the Axion line."""
        if name.value in ("exit", "quit"):       # sys.exit(1)
            self.fail("P210", name, "exit is written alone: it ends the program and takes nothing.",
                      fix="exit")
        fix = self.method_fix(target, name)
        for _ in range(5):                       # s.lower().startswith("a"): repair every call
            again = alone(fix)                   # s.split(",")[0]: and add the parentheses
            if (again is None or not again.fix or again.fix == fix
                    or not (again.message == NO_METHODS or again.message.startswith("Put "))):
                break
            fix = again.fix
        self.fail("P210", name, NO_METHODS, fix=fix)

    def python_slice(self, target, colon):
        """s[0:5], s[:5], s[2:]: a piece is written with to, and to includes its end."""
        text = self.lines[colon.line - 1]
        name = self.snippet(target)
        if re.match(r"\[\s*:\s*:\s*-\s*1\s*\]", text[target.end - 1:]):      # xs[::-1]
            self.fail("P202", colon, "Axion has no reverse.", fix=reverse_fix(name))
        inside = re.match(r"\[([^\[\]:]*):([^\[\]:]*)\]", text[target.end - 1:])
        fix = f"{name}[first to last]   (both ends are included)"
        if inside:
            start, stop = inside.group(1).strip() or "0", inside.group(2).strip()
            if not stop:
                last = f"{name} length - 1"
            elif re.fullmatch(r"[0-9]+", stop):
                last = str(int(stop) - 1)
            else:
                last = f"{stop} - 1"
            if not (start.startswith("-") or stop.startswith("-") or last == "-1"):
                fix = (text[:target.end - 1] + f"[{start} to {last}]"
                       + text[target.end - 1 + inside.end():]).strip()
        self.fail("P202", colon, "A piece is written with to, and to includes its last position.",
                  fix=fix)

    def object_literal(self):
        open_tok = self.advance()
        if self.is_op("}"):
            close = self.advance()
            same_line = close.line == open_tok.line
            if self.is_keyword("of"):                      # {} of number
                self.advance()
                value_type = self.type_spec()
                if self.is_keyword("to") or self.is_op("->"):    # {} of text to number
                    arrow = self.advance()
                    start = self.pos
                    self.type_spec()
                    values = self.lines[arrow.line - 1][self.tokens[start].col - 1:
                                                        self.tokens[self.pos - 1].end - 1]
                    self.fail("P202", arrow, "A key is always text, so only the type of the "
                                             "values is written.",
                              fix=self.whole_line(open_tok.line, open_tok.col,
                                                  self.tokens[self.pos - 1].end, f"{{}} of {values}"),
                              length=arrow.end - arrow.col)
                last = self.tokens[self.pos - 1]
                end = last.end if last.line == open_tok.line else open_tok.end
                return EmptyMap(value_type, open_tok.line, open_tok.col, end)
            if self.loose_empty_list:
                return EmptyMap(None, open_tok.line, open_tok.col, close.end)
            line_fix = (self.whole_line(open_tok.line, open_tok.col, close.end, "{} of number")
                        if same_line else "{} of number")
            self.fail("P213", open_tok, "An empty dictionary needs the type of its values.",
                      fix=f"{line_fix}   (or {{}} of text, {{}} of bool, {{}} of list of number)",
                      length=close.end - open_tok.col if same_line else 1)
        if self.cur().kind == "TEXT":
            return self.map_literal(open_tok)
        fields = []
        seen = set()
        while True:
            if self.cur().kind == "TEXT":
                self.fail("P202", self.cur(), "An object has field names without quotes; a "
                                              "dictionary has every key in quotes. Do not mix them.",
                          fix='a record: {name: "A", age: 3}   a dictionary: {"tea": 2, "milk": 1.5}')
            name_tok = self.field_name()
            if name_tok.value in seen:
                self.fail("P202", name_tok, f"Field {name_tok.value} appears twice.")
            seen.add(name_tok.value)
            if not self.is_op(":"):
                self.fail("P202", self.cur(), f"Expected : after {name_tok.value}.",
                          fix=f"{name_tok.value}: value")
            self.advance()
            fields.append((name_tok.value, self.expression()))
            if self.is_op(","):
                self.advance()
                continue
            close = self.cur()
            if not self.is_op("}"):
                self.fail("P202", close, f"Expected , or }}, got {describe(close)}.")
            self.advance()
            end = close.end if close.line == open_tok.line else open_tok.end
            return ObjectLit(fields, open_tok.line, open_tok.col, end)

    def map_literal(self, open_tok):
        """{"tea": 2, "milk": 1.5}: every key is a text in quotes."""
        pairs, seen = [], set()
        while True:
            key = self.cur()
            if key.kind != "TEXT":
                self.fail("P202", key, "An object has field names without quotes; a dictionary "
                                       "has every key in quotes. Do not mix them.",
                          fix='a record: {name: "A", age: 3}   a dictionary: {"tea": 2, "milk": 1.5}')
            if key.value in seen:
                self.fail("P202", key, f'The key "{key.value}" appears twice.',
                          length=key.end - key.col)
            seen.add(key.value)
            self.advance()
            if not self.is_op(":"):
                self.fail("P202", self.cur(), f'Expected : after "{key.value}".',
                          fix=f'"{key.value}": value')
            self.advance()
            pairs.append((key.value, key.line, key.col, self.expression()))
            if self.is_op(","):
                self.advance()
                continue
            close = self.cur()
            if not self.is_op("}"):
                self.fail("P202", close, f"Expected , or }}, got {describe(close)}.")
            self.advance()
            end = close.end if close.line == open_tok.line else open_tok.end
            return MapLit(pairs, open_tok.line, open_tok.col, end)

    def call(self, name_tok):
        self.advance()                      # (
        args = []
        while not self.is_op(")"):
            if args:
                if not self.is_op(","):
                    self.division_words(self.cur())
                    self.fail("P202", self.cur(), f"Expected , or ), got {describe(self.cur())}.")
                self.advance()
            if self.cur().kind in ("NAME", "KEYWORD") and self.is_op("=", self.peek()):
                self.named_argument(name_tok)
            args.append(self.expression())
            if self.is_keyword("for"):          # sum(x * 2 for x in xs)
                args[-1] = self.comprehension(args[-1], args[-1])
        close = self.advance()
        return Call(name_tok.value, args, name_tok.line, name_tok.col, close.end)

    def named_argument(self, name_tok):
        """f(1, b=2), sorted(xs, key=lambda t: t.age): arguments have no names."""
        word = self.cur()
        text = self.lines[name_tok.line - 1]
        close_col = self.closing_paren(name_tok.line, name_tok.end)
        generic = "Arguments have no names in Axion: the values go in the order of the parameters."
        if close_col is None:
            self.fail("P202", word, generic, length=self.peek().end - word.col)
        args = split_top(text[name_tok.end:close_col - 1])
        before, after = text[:name_tok.col - 1], text[close_col:].split("#")[0].strip()
        plain = not after and re.fullmatch(r"\s*([A-Za-z_][A-Za-z0-9_]*\s*=|print|return|for\s+\w+\s+in)\s*",
                                           before)

        def put(value):
            return self.whole_line(name_tok.line, name_tok.col, close_col + 1,
                                   value if plain else f"({value})")

        words = python_sort_keys(args[1:]) if args[0] else None
        if name_tok.value == "sorted" and words is not None:
            self.fail("P210", name_tok, "sorted() does not exist in Axion: a sort is written "
                                        "after its list.",
                      fix=put(f"{args[0]} sort {words}".strip()), length=close_col + 1 - name_tok.col)
        if name_tok.value in ("min", "max") and words and words.startswith("by ") and "," not in words:
            field = words[3:].split()[0]
            order = " descending" if name_tok.value == "max" else ""
            self.fail("P210", name_tok, f"{name_tok.value}() does not exist in Axion; the element "
                                        f"with the {'largest' if order else 'smallest'} {field} "
                                        f"is the first one after a sort.",
                      fix=self.whole_line(name_tok.line, name_tok.col, close_col + 1,
                                          f"({args[0]} sort by {field}{order})[0]"),
                      length=close_col + 1 - name_tok.col)
        bare = [re.sub(r"^[A-Za-z_][A-Za-z0-9_]*\s*=(?!=)\s*", "", arg) for arg in args]
        fix = None
        if all(bare) and "lambda" not in text:
            fix = self.whole_line(name_tok.line, name_tok.end + 1, close_col, ", ".join(bare))
        self.fail("P202", word, generic, fix=fix, length=self.peek().end - word.col)

    def comprehension(self, item, start):
        """[x * 2 for x in xs if x > 1]: parsed whole, so that the validator can answer with
        the loop written out in the author's names and types."""
        for_tok = self.advance()
        var = self.cur()
        if var.kind != "NAME" or not self.is_keyword("in", self.peek()):
            self.fail("P210", for_tok, NO_COMPREHENSION, fix=COMPREHENSION_SHAPE)
        self.advance()
        self.advance()
        iterable = self.expression()
        condition = None
        if self.is_keyword("if"):
            self.advance()
            condition = self.expression()
        if self.is_keyword("for"):
            self.fail("P210", for_tok, NO_COMPREHENSION, fix=COMPREHENSION_SHAPE)
        return Comprehension(item, var.value, iterable, condition, start.line, start.col,
                             self.tokens[self.pos - 1].end)

    def format_text(self, tok):
        """f"Total: {x}": taken apart here, answered by the validator with the exact line."""
        text = self.advance()
        line = self.lines[tok.line - 1]
        raw = line[text.col:text.end - 2]
        parts, literal, k = [], "", 0

        def give_up():
            self.fail("P210", tok, NO_FORMAT_TEXT, fix=FORMAT_TEXT_SHAPE, length=text.end - tok.col)

        while k < len(raw):
            ch = raw[k]
            if raw[k:k + 2] in ("{{", "}}"):
                literal += ch
                k += 2
            elif ch == "{":
                depth, stop = 0, k + 1
                while stop < len(raw) and (raw[stop] != "}" or depth):
                    depth += (raw[stop] in "{[(") - (raw[stop] in "}])")
                    stop += 1
                if stop >= len(raw):
                    give_up()
                inside = raw[k + 1:stop]
                pieces = split_colon(inside)
                source = pieces[0].split("!")[0] if len(pieces[0].split("!")) == 2 and "!=" not in pieces[0] else pieces[0]
                padded = "\n" * (tok.line - 1) + " " * (text.col + k + 1) + source
                try:
                    sub = Parser(lex(padded), "\n".join(self.lines))
                    node = sub.expression()
                    if sub.cur().kind not in ("NEWLINE", "EOF"):
                        give_up()
                except AxionError:
                    give_up()
                if literal:
                    parts.append(("text", literal))
                    literal = ""
                parts.append(("value", node, pieces[1] if len(pieces) > 1 else ""))
                k = stop + 1
            else:
                literal += ch
                k += 1
        if literal:
            parts.append(("text", literal))
        return FormatText(parts, tok.line, tok.col, text.end)

    def list_literal(self):
        open_tok = self.advance()
        if self.is_op("]"):
            close = self.advance()
            if not self.is_keyword("of") and self.loose_empty_list:
                return EmptyList(None, open_tok.line, open_tok.col, close.end)
            if not self.is_keyword("of"):
                line_fix = (self.whole_line(open_tok.line, open_tok.col, close.end, "[] of text")
                            if close.line == open_tok.line else "[] of text")
                self.fail("P213", open_tok, "An empty list needs the type of its elements.",
                          fix=f"{line_fix}   (or [] of number, [] of bool, [] of {{name: text}})",
                          length=close.end - open_tok.col)
            self.advance()
            elem_type = self.type_spec()
            last = self.tokens[self.pos - 1]
            end = last.end if last.line == open_tok.line else open_tok.end
            return EmptyList(elem_type, open_tok.line, open_tok.col, end)
        items = [self.expression()]
        built = None
        if self.is_keyword("for"):                  # [x * 2 for x in xs]
            built = self.comprehension(items[0], open_tok)
        while self.is_op(","):
            self.advance()
            items.append(self.expression())
        close = self.cur()
        if not self.is_op("]"):
            self.fail("P202", close, f"Expected , or ], got {describe(close)}.")
        self.advance()
        end = close.end if close.line == open_tok.line else open_tok.end
        if built is not None:
            built.end = end
            return built
        return ListLit(items, open_tok.line, open_tok.col, end)

    def owning_commas(self, parse, *args, owned=True):
        """Parse a part where a comma separates items (owned) or does not (inside parentheses)."""
        saved, self.comma_owner = self.comma_owner, 1 if owned else 0
        try:
            return parse(*args)
        finally:
            self.comma_owner = saved

    def primary(self):
        tok = self.cur()
        if tok.kind == "NUMBER":
            self.advance()
            return Number(tok.value, tok.line, tok.col, tok.end)
        if tok.kind == "TEXT":
            self.advance()
            return Text(tok.value, tok.line, tok.col, tok.end)
        if tok.kind == "NAME":
            if tok.value in FOREIGN_VALUES:
                self.fail("P210", tok, f"{tok.value} is not Axion syntax.",
                          fix=FOREIGN_VALUES[tok.value])
            self.advance()
            if (tok.value in ("f", "F") and self.cur().kind == "TEXT"
                    and self.cur().col == tok.end and self.cur().line == tok.line):
                return self.format_text(tok)
            if self.is_op("("):
                return self.owning_commas(self.call, tok)
            return Name(tok.value, tok.line, tok.col, tok.end)
        if self.is_keyword("true") or self.is_keyword("false"):
            self.advance()
            return Bool(tok.value == "true", tok.line, tok.col, tok.end)
        if self.is_op("["):
            return self.owning_commas(self.list_literal)
        if self.is_op("{"):
            return self.owning_commas(self.object_literal)
        if self.is_op("("):
            self.advance()
            inner = self.owning_commas(self.expression, owned=False)
            close = self.cur()
            if not self.is_op(")"):
                self.membership_habit(close)
                self.division_words(close)
                self.fail("P202", close, f"Expected ), got {describe(close)}.")
            self.advance()
            return Group(inner, tok.line, tok.col, close.end)
        if self.is_keyword("is") and self.is_keyword("number", self.peek()):
            value = self.peek(2)
            simple = value.kind == "NAME" and self.peek(3).kind in ("NEWLINE", "EOF", "KEYWORD")
            self.fail("P202", tok, "is number comes after the value.",
                      fix=(self.whole_line(tok.line, tok.col, value.end, f"{value.value} is number")
                           if simple else "write the value first: s is number"),
                      length=self.peek().end - tok.col)
        if self.is_keyword("length"):
            self.advance()
            fix = "write the value first: xs length"
            try:
                operand = self.access()             # length form.password, length(xs), length xs[0]
            except AxionError:
                operand = None
            if operand is not None and operand.line == tok.line:
                value = operand
                if isinstance(operand, Group) and isinstance(operand.inner, (Name, Field, Index, Call)):
                    value = operand.inner
                fix = self.whole_line(tok.line, tok.col, operand.end, f"{self.snippet(value)} length")
                for _ in range(5):               # length a > length b: repair every one at once
                    again = alone(fix)
                    if (again is None or again.message != "length comes after the value."
                            or not again.fix or again.fix.startswith("write the value first")):
                        break
                    fix = again.fix
            self.fail("P202", tok, "length comes after the value.", fix=fix)
        if self.is_keyword("if"):
            self.fail("P202", tok, "if ... then ... else ... inside a longer expression "
                                   "needs parentheses.",
                      fix="put it in parentheses: (if condition then a else b)")
        if tok.kind == "KEYWORD" and tok.value in ("list", "text", "number") and self.is_op("(", self.peek()):
            fix = {"list": "a value is always copied, so write the list itself; a new list is "
                           "built with a loop and add",
                   "text": "a number becomes text with: n as text",
                   "number": "a text becomes a number with: s as number"}[tok.value]
            self.fail("P210", tok, f"{tok.value}() does not exist in Axion.", fix=fix)
        if self.is_keyword("input") and self.is_op("(", self.peek()):      # x = input()
            target = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", self.lines[tok.line - 1])
            name = target.group(1) if target else "name"
            self.fail("P210", tok, "A program does not ask for data while it runs: its data is "
                                   "declared at the top and comes with the launch.",
                      fix=f"delete this line and write at the top of the program: input {name}: text")
        if tok.kind == "KEYWORD" and tok.value in NAME_LIKE_KEYWORDS:
            self.keyword_as_name(tok)             # print value: the same mistake as value = 5
        self.fail("P202", tok, f"Expected a value, got {describe(tok)}.")


def parse(tokens, source):
    return Parser(tokens, source).parse()


def multiline_lines(lines):
    """Numbers of the lines that belong to a bracket left open across lines ([ ... ] over rows).

    Such a line is not a statement of its own, so it cannot be checked alone.
    """
    inside, depth = set(), 0
    for number, text in enumerate(lines, 1):
        start, k = depth, 0
        while k < len(text):
            ch = text[k]
            if ch == "#":
                break
            if ch == '"':
                k += 1
                while k < len(text) and text[k] != '"':
                    k += 2 if text[k] == "\\" else 1
            elif ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth = max(0, depth - 1)
            k += 1
        if start > 0 or depth > 0:
            inside.add(number)
    return inside


def alone(text):
    """The error of one line lexed and parsed alone, or None."""
    try:
        probe = Parser(lex(text), text)
        probe.depth, probe.reads_files = 1, True
        probe.line_alone()
    except AxionError as error:
        return error
    return None


def placeholder(text):
    """A correct line that opens or closes the same block as this broken one (same indentation)."""
    indent = text[:len(text) - len(text.lstrip())]
    words = text.split("#")[0].split()
    if words[:2] == ["else", "if"] or words[0] in ("elif", "elseif"):
        return indent + "else if true"
    if words[0] in ("else", "end"):
        return indent + words[0]
    if words[0] == "if" and re.search(r"\bthen\b\s*\S", text.split("#")[0]):
        return indent + "print 0"            # if c then y = 1 else y = 2: no block is opened
    if words[0] == "if":
        return indent + "if true"
    if words[0] == "for":
        return indent + "for axiom_item in [0]"
    if words[0] == "while":
        return indent + "while true"
    if words[0] == "function":
        return indent + "function axiom_function()"
    return indent + "print 0"


def syntax_errors(source, first):
    """Every mistake in how the program is written, found in one pass.

    1. Each line is lexed and parsed alone (a statement, or the header of if / else if /
       for): all lines with a mistake of their own are found, not only the first.
    2. Those lines are replaced by correct lines with the same role, and the program is
       parsed again: what fails now is a mistake in the blocks (a missing or extra end,
       an else without its if), which the first error would otherwise hide.
    """
    lines = normalize_source(source).split("\n")
    skip = multiline_lines(lines)
    found = {}
    for number, text in enumerate(lines, 1):
        if number in skip or not text.strip():
            continue
        error = alone(text)
        if error is not None:
            found[number] = error
    spread = set()                      # the else lines of a value-if written over several lines
    for number, error in list(found.items()):
        joined = joined_value_if(lines, number) if error.message == NEEDS_ELSE else None
        if joined:
            error.message, error.fix = ONE_LINE_VALUE_IF, joined[0]
            where = re.search(r"\bif\b", lines[number - 1])
            error.col, error.length = where.start() + 1, 2
            spread.update(joined[1])
    errors, broken = [first], set()
    if first.line in spread:            # the first error sits on such an else line: drop it
        errors = []
    for number, error in found.items():
        if number in spread:
            continue
        broken.add(number)
        if number != first.line:
            error.line, error.affected = number, []
            errors.append(error)
        elif first.message == NEEDS_ELSE and error.message == ONE_LINE_VALUE_IF:
            errors[0] = error
            error.line, error.affected = number, []
    if broken or spread:
        repaired = "\n".join("" if number in spread else
                             placeholder(text) if number in broken else text
                             for number, text in enumerate(lines, 1))
        try:
            Parser(lex(repaired), source).parse()
        except AxionError as error:
            # Every line is correct now, so this can only be a mistake in the blocks.
            if (error.code, error.line) != (first.code, first.line):
                errors.append(error)
    # length = 5 makes every later use of length fail in its own way: one mistake, many lines.
    names = {e.message.split(" ", 1)[0] for e in errors if e.code == "P214"}
    for error in errors:
        token = lines[error.line - 1][error.col - 1:error.col - 1 + error.length]
        if error.code != "P214" and token in names:
            error.code = "P214"
            error.message = f"{token} is a keyword and cannot be used as a name."
            error.fix = f"choose another name, e.g. my_{token}"
    return errors
