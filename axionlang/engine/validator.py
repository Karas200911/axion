"""Validator: checks the AST before anything runs (spec §5-§12, §17).

Implemented so far: types (number, text, bool, list of T), fixed variable types,
blocks and visibility, unused variables, operators, comparisons, logic,
if / else if / else, lists (literals, index, add, remove, length), ranges, for.
"""

import difflib
import re

from .axtypes import BOOL, NUMBER, PENDING, TEXT, ListT, MapT, ObjectT, short_name
from .errors import AxionError, AxionErrors
from .lexer import lex, normalize_source
from .parser import (Aggregate, Allow, As, Assign, Binary, Bool, Break, Call, CallStatement, EmptyList, Field,
                    For, Function, Group, If, Index, Input, IsNumber, Length, ListAdd, ListLit,
                    ListRemove, Name, Not, Number, ObjectLit, Print, Program, Range, Read,
                    Return, SetField, SetItem, Sort, Text, Unary)
from .parser import ONE_LINE_VALUE_IF, Conditional, Join, Parser, joined_value_if, placeholder
from .parser import Affix, Contains, Split, TextOp
from .parser import EmptyMap, Keys, MapLit
from .parser import DateOp, Round
from .parser import Continue, Exists, Exit, While
from .parser import (COMPREHENSION_SHAPE, FORMAT_TEXT_SHAPE, NO_COMPREHENSION, NO_FORMAT_TEXT,
                     Comprehension, FormatText, reverse_fix)
from .policy import Policy, normalize_folder, unsafe_path
from .values import NUMBER_TEXT, parse_date, text_number

ORDERING = ("<", ">", "<=", ">=")
ARITHMETIC = ("+", "-", "*", "/", "//", "%", "**")
EQUALITY = ("==", "!=")


def unwrap(node):
    while isinstance(node, Group):
        node = node.inner
    return node


def literal_number(node):
    """The value of a number literal (also -literal), or None if not a literal."""
    node = unwrap(node)
    if isinstance(node, Number):
        return node.value
    if isinstance(node, Unary) and isinstance(unwrap(node.operand), Number):
        return -unwrap(node.operand).value
    return None


def is_whole(d):
    return d == d.to_integral_value()


def root_name(node):
    """The variable at the root of an access path: items[0][1] -> items."""
    node = unwrap(node)
    while isinstance(node, (Index, Field)):
        node = unwrap(node.target)
    return node.name if isinstance(node, Name) else None


# Calls from other languages and their Axion form (spec §17). {0} = the first argument.
FOREIGN_FUNCTIONS = {
    "sum": "{0} sum", "min": "{0} min", "max": "{0} max", "sorted": "{0} sort",
    "len": "{0} length", "str": "{0} as text", "int": "{0} as number",
    "float": "{0} as number", "Number": "{0} as number", "String": "{0} as text",
    "range": "0 to {0} - 1",
    # numbers (v0.3). In parentheses on purpose: the Fix is put into the middle of a line,
    # and `10 - x floor` would not say what is rounded.
    "sqrt": "({0} ** 0.5)", "floor": "({0} floor)", "ceil": "({0} ceiling)",
    "round": "({0} round 0)", "trunc": "({0} floor)",
    "abs": "(if {0} < 0 then 0 - {0} else {0})",
    "lower": "{0} lower", "upper": "{0} upper", "trim": "{0} trim", "strip": "{0} trim",
}
# The same with two arguments.
FOREIGN_FUNCTIONS_TWO = {"round": "({0} round {1})", "pow": "({0} ** {1})",
                         "range": "{0} to {1} - 1"}


# Constructors of other languages for an empty collection, and what is written instead.
COUNTING = ("counts = {} of number   and in the loop: "
            "counts[w] = if counts contains w then counts[w] + 1 else 1")
FOREIGN_EMPTY = {
    "dict": "an empty dictionary names the type of its values: {} of number",
    "list": "an empty list names the type of its elements: [] of number",
    "set": "a list and contains: seen = [] of text   and   if not seen contains x",
    "defaultdict": COUNTING,
    "Counter": COUNTING,
}


def branches_of(statement):
    return statement.branches + ([statement.else_branch] if statement.else_branch else [])


def own_break(body):
    """Does this loop body hold a break of its own (a break of an inner loop does not count)?"""
    for st in body:
        if isinstance(st, Break):
            return True
        if isinstance(st, If) and any(own_break(b.body) for b in branches_of(st)):
            return True
    return False


def endless(statement):
    """while true without a break of its own: the lines after it can never run."""
    if not isinstance(statement, While):
        return False
    condition = unwrap(statement.condition)
    return isinstance(condition, Bool) and condition.value and not own_break(statement.body)


def always_returns(statement):
    """True if this statement ends the function on every path."""
    if isinstance(statement, Return):
        return True
    if isinstance(statement, If):
        return (statement.else_branch is not None
                and all(body_returns(b.body) for b in branches_of(statement)))
    return endless(statement)        # any other loop may run zero times


def body_returns(body):
    return any(always_returns(s) for s in body)


def always_leaves(statement):
    """True if nothing after this statement can run: it leaves on every path."""
    if isinstance(statement, (Return, Break, Continue, Exit)):
        return True
    if isinstance(statement, If):
        return (statement.else_branch is not None
                and all(any(always_leaves(s) for s in b.body) for b in branches_of(statement)))
    return endless(statement)


def leaving_words(statement):
    """The words that end the paths of a statement that always leaves (for the V319 message)."""
    if isinstance(statement, (Return, Break, Continue, Exit)):
        return {type(statement).__name__.lower()}
    words = set()
    if isinstance(statement, If):
        for branch in branches_of(statement):
            for st in branch.body:
                if always_leaves(st):
                    words |= leaving_words(st)
                    break
    return words


def leaves_loop(body):
    """Can this while body leave the loop by itself: a break of its own, a return, an exit?"""
    return own_break(body) or contains(body, (Return, Exit))


def changed_names(body):
    """Every variable that the statements of this body (at any depth) assign or change."""
    names = set()
    for st in body:
        if isinstance(st, Assign):
            names.add(st.name)
        elif isinstance(st, (SetItem, SetField, ListAdd, ListRemove)):
            names.add(root_name(st.target))
        elif isinstance(st, If):
            for branch in branches_of(st):
                names |= changed_names(branch.body)
        elif isinstance(st, (For, While)):
            inside = changed_names(st.body)
            if isinstance(st, For) and st.var in inside:     # for x in xs ... x.v = 1 changes xs
                inside.add(root_name(st.iterable))
            names |= inside
    return names


# --- can a function finish? (the guard that replaces the ban on recursion) ---
def must_call(node, blocked):
    """Is a blocked function called on every way of computing this expression?"""
    if isinstance(node, Call):
        return blocked(node.name) or any(must_call(a, blocked) for a in node.args)
    if isinstance(node, Conditional):
        return (must_call(node.cond, blocked)
                or (must_call(node.then, blocked) and must_call(node.otherwise, blocked)))
    if isinstance(node, Binary) and node.op in ("and", "or"):
        return must_call(node.left, blocked)     # the right side may be skipped
    if isinstance(node, (list, tuple)):
        return any(must_call(item, blocked) for item in node)
    if hasattr(node, "__dataclass_fields__"):
        return any(must_call(getattr(node, name), blocked) for name in node.__dataclass_fields__)
    return False


def outcomes(body, blocked):
    """How these statements can end without calling a blocked function:
    a set of "fall" (the next line runs), "return", "break", "continue"."""
    result = set()
    for st in body:
        ways = statement_outcomes(st, blocked)
        result |= ways - {"fall"}
        if "fall" not in ways:
            return result
    return result | {"fall"}


def statement_outcomes(st, blocked):
    if isinstance(st, Return):
        return set() if must_call(st.value, blocked) else {"return"}
    if isinstance(st, (Break, Continue)):
        return {type(st).__name__.lower()}
    if isinstance(st, Exit):
        return {"return"}
    if isinstance(st, If):
        result = set()
        for branch in st.branches:
            if must_call(branch.condition, blocked):
                return result
            result |= outcomes(branch.body, blocked)
        if st.else_branch is None:
            return result | {"fall"}
        return result | outcomes(st.else_branch.body, blocked)
    if isinstance(st, For):
        if must_call(st.iterable, blocked):
            return set()
        return {"fall"} | (outcomes(st.body, blocked) & {"return"})
    if isinstance(st, While):
        if must_call(st.condition, blocked):
            return set()
        inside = outcomes(st.body, blocked)
        condition = unwrap(st.condition)
        forever = isinstance(condition, Bool) and condition.value
        return (inside & {"return"}) | ({"fall"} if not forever or "break" in inside else set())
    return set() if must_call(st, blocked) else {"fall"}


def contains(node, kind):
    """Does this part of the AST hold a node of the given kind?"""
    if isinstance(node, kind):
        return True
    if isinstance(node, (list, tuple)):
        return any(contains(item, kind) for item in node)
    if hasattr(node, "__dataclass_fields__"):
        return any(contains(getattr(node, name), kind) for name in node.__dataclass_fields__)
    return False


class Suppressed(AxionError):
    """A statement that depends on a variable whose own line already failed: not reported."""


def names_in(node):
    """Every variable name mentioned anywhere inside this part of the AST."""
    if isinstance(node, (Assign, Call)):
        yield node.name
    if isinstance(node, Name):
        yield node.name
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from names_in(item)
    elif hasattr(node, "__dataclass_fields__"):
        for field in node.__dataclass_fields__:
            yield from names_in(getattr(node, field))


class Signature:
    def __init__(self, node):
        self.name = node.name
        self.params = node.params
        self.result = node.result
        self.node = node
        self.used = False

    def text(self):
        params = ", ".join(f"{p.name}: {p.type}" for p in self.params)
        result = f" -> {self.result}" if self.result is not None else ""
        return f"{self.name}({params}){result}"


class Position:
    def __init__(self, line, col):
        self.line, self.col = line, col


class Variable:
    def __init__(self, name, type_, pos, loop=False, param=False, source=None, counted=False,
                 root=None):
        self.name = name
        self.root = root             # the variable at the root of the list a loop variable walks
        self.type = type_
        self.pos = pos               # where it was created (for V305)
        self.loop = loop             # a for-loop variable is read-only (V315)
        self.source = source         # the list a loop variable walks over, as written (V315 hint)
        self.counted = counted       # the loop goes over a range (a to b): it may only count
        self.param = param           # a function parameter is read-only (V324)
        self.used = False


class Validator:
    def __init__(self, source, policy=None):
        self.policy = policy or Policy()
        self.allows = []             # [Allow node, folder, used] declared by the program
        self.lines = normalize_source(source).split("\n")
        self.scopes = [{}]           # stack of blocks: innermost last; name -> Variable
        self.dead = {}               # name -> (block kind, line) where it died (for V304)
        self.locked = []             # lists being iterated by enclosing for loops (V316)
        self.functions = {}          # name -> Signature
        self.current = None          # Signature of the function being checked, None = main
        self.calls = {}              # caller name (None = main) -> [(callee, Call node)]
        self.outer_names = set()     # variables of the main program (for V325)
        self.errors = []             # everything found so far (reported together, see errors.py)
        self.tainted = set()         # names whose creating line failed: their uses are not reported
        self.loops = 0               # how many loops enclose the current statement (V327)
        self.reads_files = True      # does the program contain a read at all?
        self.empty_lists = {}        # line of a bare `name = []` -> its element type, once known

    # --- scopes (spec §6) ---
    def lookup(self, name):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    def visible_names(self):
        return [n for scope in self.scopes for n in scope]

    def push(self):
        self.scopes.append({})

    def pop(self, kind, line):
        """Close a block: its variables must have been used, then they die."""
        scope = self.scopes.pop()
        self.check_unused(scope)
        for name, var in scope.items():
            self.dead[name] = (kind, line, var.pos)

    def check_unused(self, scope):
        for var in scope.values():
            if var.loop and var.counted:
                continue                 # for i in 1 to n: "repeat n times", i may stay unused
            if not var.used and var.name in self.tainted and not (var.loop or var.param):
                continue                 # another line that creates this name failed, and the
                #                          lines that read it were not checked: "unused" is a guess
            if not var.used:
                # A loose "did you mean" on an unused name reads as "rename it" (GPT did), so the
                # other name is offered only for a near-identical spelling (totl / total).
                others = [n for n in self.visible_names() if n != var.name]
                close = difflib.get_close_matches(var.name, others, n=1, cutoff=0.8)
                if var.param:
                    fix = "use it, or remove it"
                elif close:
                    fix = (f"if you meant {close[0]}, write {close[0]} here; otherwise delete "
                           f"every line that sets {var.name}")
                else:
                    fix = f"delete every line that sets {var.name}, or use it"
                if var.loop:             # a loop over a list of things that never looks at them
                    times = f"{var.source} length" if var.source else "n"
                    fix = (f"use {var.name} inside the loop; to only repeat N times write: "
                           f"for {var.name} in 1 to {times}")
                what = "loop variable" if var.loop else ("parameter" if var.param else "")
                self.errors.append(AxionError(
                    "V305", var.pos.line, var.pos.col,
                    f"{var.name} is created but never used."
                    if not what else f"The {what} {var.name} is never used.",
                    fix=fix, length=len(var.name)))

    def find(self, node):
        """Resolve a variable name (V303 / V304). Does not count as a use."""
        var = self.lookup(node.name)
        if var is not None:
            return var
        if node.name in self.tainted:
            raise Suppressed("V303", node.line, node.col, "depends on an earlier error")
        if self.current is not None and node.name in self.outer_names:
            self.fail("V325", node, f"The function {self.current.name} cannot see the outer "
                                    f"variable {node.name}.",
                      fix=f"add a parameter {node.name} and pass the value in the call")
        if node.name in self.dead:
            kind, line, born = self.dead[node.name]
            # "never used" for the same variable is an echo of this error: drop it.
            self.errors = [e for e in self.errors
                           if not (e.code == "V305" and (e.line, e.col) == (born.line, born.col))]
            self.fail("V304", node,
                      f"{node.name} was created inside the {kind} at line {line} "
                      f"and does not exist outside it.",
                      fix=f"create {node.name} before the {kind} and only change it inside")
        close = difflib.get_close_matches(node.name, self.visible_names(), n=1, cutoff=0.5)
        fix = f"did you mean {close[0]}?" if close else f"create it first: {node.name} = ..."
        if close:                        # a misspelt name: the real one is not "never used"
            self.lookup(close[0]).used = True
        self.fail("V303", node, f"Unknown variable {node.name}.", fix=fix)

    # --- helpers ---
    def snippet(self, node):
        return self.lines[node.line - 1][node.col - 1:node.end - 1]

    def whole_line(self, node, replacement):
        """The source line with this node replaced (Fix hints show the whole corrected line)."""
        text = self.lines[node.line - 1]
        return (text[:node.col - 1] + replacement + text[node.end - 1:]).strip()

    def as_operand(self, node):
        """Source of a node, wrapped in parentheses when a postfix `as` would bind wrongly."""
        text = self.snippet(node)
        wrap = (Binary, Unary, Not, Range, Conditional, Contains, Affix, Split)
        return f"({text})" if isinstance(node, wrap) else text

    def fail(self, code, node, message, fix=None):
        raise AxionError(code, node.line, node.col, message, fix=fix,
                         length=max(1, node.end - node.col))

    # --- statements ---
    def validate(self, program):
        assert isinstance(program, Program)
        self.collect(lambda: self.collect_functions(program.statements))
        self.reads_files = (contains(program.statements, (Read, Exists))
                            or "exists" in names_in(program.statements))    # exists("a.txt")
        self.outer_names = self.main_names(program.statements)
        self.statements(program.statements)
        self.check_unused(self.scopes[0])
        for node, folder, used in self.allows:
            if not used:
                self.collect(lambda: self.fail(
                    "V305", node, f'allow read "{folder}" is never used.',
                    fix="remove it: a program asks only for what it uses"))
        self.collect(self.check_recursion)
        for sig in self.functions.values():
            if not sig.used:
                node = sig.node
                self.errors.append(AxionError("V305", node.line, node.name_col,
                                              f"The function {sig.name} is never called.",
                                              fix="call it, or remove it", length=len(sig.name)))
        if self.errors:
            raise AxionErrors(self.errors)

    def collect(self, check):
        """Run one check; its error (if any) joins the list instead of stopping everything."""
        try:
            check()
        except Suppressed:
            pass
        except AxionError as error:
            self.errors.append(error)

    def abandon(self, statement):
        """A statement that failed: nothing it mentions is 'unused', and a variable it was
        creating is unknown from here on, so lines that need it are not reported again."""
        for name in names_in(statement):
            var = self.lookup(name)
            if var is not None:
                var.used = True
            if name in self.functions:
                self.functions[name].used = True
        if contains(statement, (Read, Exists)) or "exists" in names_in(statement):
            for entry in self.allows:
                entry[2] = True
        if isinstance(statement, Assign) and self.lookup(statement.name) is None:
            self.tainted.add(statement.name)

    def collect_functions(self, statements):
        """Pass 1: every function is known before any code is checked (call before definition)."""
        for st in statements:
            if isinstance(st, Function):
                if st.name in self.functions:
                    raise AxionError("P202", st.line, st.name_col,
                                     f"The function {st.name} is defined twice.",
                                     length=len(st.name))
                self.functions[st.name] = Signature(st)

    def main_names(self, statements):
        names = set()
        for st in statements:
            if isinstance(st, (Assign, Input)):
                names.add(st.name)
            elif isinstance(st, For):
                names.add(st.var)
                names |= self.main_names(st.body)
            elif isinstance(st, While):
                names |= self.main_names(st.body)
            elif isinstance(st, If):
                for b in branches_of(st):
                    names |= self.main_names(b.body)
        return names

    def statements(self, body):
        """A list of statements. Nothing may follow a statement that always returns (V319)."""
        dead = None                      # the statement after which nothing can run
        for st in body:
            try:
                if dead is not None and not isinstance(st, Function):
                    self.unreachable(st, dead)
                self.statement(st)
            except Suppressed:
                self.abandon(st)
            except AxionError as error:
                self.errors.append(error)
                self.abandon(st)
            if dead is None and always_leaves(st):
                dead = st

    def unreachable(self, st, dead):
        never = "This line can never run: "
        if isinstance(dead, Break):
            self.fail("V319", st, never + "break has already stopped the loop.",
                      fix="remove it, or move it before the break")
        if isinstance(dead, Continue):
            self.fail("V319", st, never + "continue has already gone on to the next pass of the loop.",
                      fix="remove it, or move it before the continue")
        if isinstance(dead, Exit):
            self.fail("V319", st, never + "exit has already ended the program.",
                      fix="remove it, or move it before the exit")
        if isinstance(dead, While):
            self.fail("V319", st, never + f"the while true on line {dead.line} has no break, so "
                                          f"nothing gets past it.",
                      fix="remove it, or leave that loop with break instead")
        if always_returns(dead):
            self.fail("V319", st, never + "the function has already returned.",
                      fix="remove it, or move it before the return")
        words = sorted(leaving_words(dead) | {"break", "return"})
        ends = ", ".join(words[:-1]) + " or " + words[-1]
        self.fail("V319", st, never + f"every branch above ends with {ends}.",
                  fix="remove it, or move it into a branch")

    def check_name_free(self, name, line, col):
        if name in self.functions:
            raise AxionError("V302", line, col, f"{name} is already the name of a function.",
                             fix=f"choose another name, e.g. {name}_value", length=len(name))

    def statement(self, node):
        if isinstance(node, Assign):
            self.assign(node)
        elif isinstance(node, Print):
            self.type_of(node.value)
        elif isinstance(node, If):
            self.if_statement(node)
        elif isinstance(node, For):
            self.for_statement(node)
        elif isinstance(node, SetItem):
            self.set_item(node)
        elif isinstance(node, SetField):
            self.set_field(node)
        elif isinstance(node, Function):
            self.function(node)
        elif isinstance(node, Allow):
            self.allow(node)
        elif isinstance(node, Input):
            self.check_name_free(node.name, node.line, node.name_col)
            self.scopes[0][node.name] = Variable(node.name, node.type, Position(node.line, node.name_col))
        elif isinstance(node, Return):
            self.return_statement(node)
        elif isinstance(node, While):
            self.while_statement(node)
        elif isinstance(node, (Break, Continue)):
            if self.loops == 0:
                word = type(node).__name__.lower()
                fix = "remove it"
                if word == "break" and self.current is None:
                    fix = "remove it; to end the program here write exit"
                self.fail("V327", node, f"{word} works only inside a loop.", fix=fix)
        elif isinstance(node, Exit):
            if self.current is not None:
                self.fail("V329", node, "exit ends the whole program, so it works only in the "
                                        "main program, not in a function.",
                          fix="leave the function with return and write exit in the main program")
        elif isinstance(node, CallStatement):
            result = self.call_type(node.call, as_statement=True)
            if result is not None:
                snip = self.snippet(node.call)
                self.fail("V320", node.call, f"The result of {node.call.name} is not used.",
                          fix=f"result = {snip}, or print {snip}")
        elif isinstance(node, ListAdd):
            self.list_add(node)
        elif isinstance(node, ListRemove):
            self.list_remove(node)
        else:
            raise TypeError(f"unknown statement {type(node).__name__}")

    def assign(self, node):
        value_type = self.type_of(node.value)
        var = self.lookup(node.name)
        if var is None:
            # A new name: created in the current (innermost) block.
            self.check_name_free(node.name, node.line, node.col)
            self.scopes[-1][node.name] = Variable(node.name, value_type, node)
            self.dead.pop(node.name, None)
            return
        if var.type == ListT(PENDING) and isinstance(value_type, ListT):
            self.settle_empty_list(var, value_type.elem)        # xs = []  ...  xs = other_list
            return
        if value_type == ListT(PENDING) and isinstance(var.type, ListT):
            self.empty_lists[node.line] = var.type.elem         # xs = [1]  ...  xs = []
            return
        if var.type == MapT(PENDING) and isinstance(value_type, MapT):
            if PENDING not in str(value_type.value):            # d = {}  ...  d = other
                var.type = value_type
                self.empty_lists[var.pos.line] = value_type.value
            return
        if value_type == MapT(PENDING) and isinstance(var.type, MapT):
            self.empty_lists[node.line] = var.type.value        # d = {"a": 1}  ...  d = {}
            return
        # An existing name: this modifies it.
        self.check_mutation(node.name, node)
        old = var.type
        if old != value_type:
            if {old, value_type} <= {NUMBER, TEXT} and not isinstance(unwrap(node.value), (Number, Text)):
                fix = (f"use a new name, or convert: "
                       f"{node.name} = {self.as_operand(node.value)} as {old}")
            else:
                fix = f"use a new name: {node.name}_{short_name(value_type)} = {self.snippet(node.value)}"
            self.fail("V302", node.value, f"{node.name} is {old}; it cannot hold {value_type}.", fix=fix)

    def check_mutation(self, name, node, inside=False):
        """A parameter cannot change; a loop variable cannot be replaced; a list cannot change
        inside a for loop over it.

        inside=True: the change is to a part of the value (x.f = v, x[i] = v, x add v).
        In `for x in xs` the variable x is the element itself, so such a change is a change
        of xs and is allowed; only x = v is not.
        """
        var = self.lookup(name)
        if var is not None and var.param:
            self.fail("V324", node, f"{name} is a parameter and cannot be changed.",
                      fix=f"copy it first: new_{name} = {name}")
        if var is not None and var.loop:
            if inside and var.source:
                var.used = True              # changing the element is a use of the loop variable
                if name in self.locked:      # for row in grid ... for v in row ... row add v
                    self.fail("V316", node, f"{name} cannot be changed inside a for loop over {name}.",
                              fix=f"loop over a copy: {name}_copy = {name}, then for ... in {name}_copy")
                owner = var
                while owner is not None and owner.loop and owner.root:
                    owner = self.lookup(owner.root)
                if owner is not None and owner.param:
                    self.fail("V324", node, f"{name} is an element of the parameter {owner.name}, "
                                            f"and a parameter cannot be changed.",
                              fix=f"copy it first: new_{owner.name} = {owner.name}, and loop over the copy")
                return
            if var.source and not inside:
                self.fail("V315", node, f"{name} is the loop variable and cannot be replaced.",
                          fix=f"to replace elements of {var.source} loop over positions: "
                              f"for i in 0 to {var.source} length - 1, then {var.source}[i] = ...")
            self.fail("V315", node, f"{name} is the loop variable and cannot be changed.",
                      fix=f"copy it first: new_{name} = {name}")
        if name in self.locked:
            self.fail("V316", node, f"{name} cannot be changed inside a for loop over {name}.",
                      fix=f"loop over a copy: {name}_copy = {name}, then for ... in {name}_copy")

    def container_type(self, node):
        """Type of an assignment target (xs, xs[i], ...). Changing a value is not a use."""
        node = unwrap(node)
        if isinstance(node, Name):
            return self.find(node).type
        if isinstance(node, Index):
            t = self.container_type(node.target)
            self.check_index(node, t)
            if isinstance(unwrap(node.index), Range):
                self.fail("V301", node, "A piece cannot be assigned to.",
                          fix="change the elements one by one, or build a new value")
            if t == TEXT:
                self.fail("V301", node, "Text cannot be changed in place.",
                          fix="build a new text from pieces with +")
            return t.value if isinstance(t, MapT) else t.elem
        if isinstance(node, Field):
            return self.field_type(node, self.container_type(node.target))
        self.fail("P202", node, "This cannot be changed: only variables, list elements and fields can.")

    def field_type(self, node, owner):
        if not isinstance(owner, ObjectT):
            fix = (self.whole_line(node, f"{self.snippet(node.target)} length")
                   if node.name == "length" and (isinstance(owner, ListT) or owner == TEXT) else None)
            self.fail("V309", node, f"{owner} has no fields; only objects do.", fix=fix)
        if node.name not in owner.fields:
            close = difflib.get_close_matches(node.name, list(owner.fields), n=1, cutoff=0.5)
            fields = ", ".join(owner.fields)
            self.fail("V309", node, f"There is no field {node.name}; fields are: {fields}.",
                      fix=f"did you mean {close[0]}?" if close else
                      "fields are fixed when the object is created")
        return owner.fields[node.name]

    def set_field(self, node):
        t = self.container_type(node.target)
        self.check_mutation(root_name(node.target), node.target, inside=True)
        vt = self.type_of(node.value)
        if vt != t:
            self.fail("V309", node.value,
                      f"Field {node.target.name} is {t}; it cannot hold {vt}.")

    def check_index(self, node, container):
        if isinstance(container, MapT):
            self.check_key(node, node.index)
            return
        if isinstance(container, ObjectT):
            name = self.snippet(node.target)
            key = unwrap(node.index)
            fix = None
            if isinstance(key, Text) and key.value in container.fields:      # o["name"]
                fix = self.whole_line(node, f"{name}.{key.value}")
            self.fail("V301", node, f"{name} is an object with fixed fields; a field is read "
                                    f"with a dot. A dictionary is written with its keys in quotes.",
                      fix=fix or 'a dictionary: {"tea": 2, "milk": 1.5}   or empty: {} of number')
        if not isinstance(container, ListT) and container != TEXT:
            self.fail("V301", node, f"Only lists, text and dictionaries are read with [ ], "
                                    f"got {container}.")
        if isinstance(unwrap(node.index), Range):             # s[0 to 4], xs[0 to 2]: a piece
            self.range_type(unwrap(node.index), piece=True)
            return
        t = self.type_of(node.index)
        if t != NUMBER:
            xs = self.snippet(node.target)
            self.fail("V301", node.index, f"An index must be a number, got {t}.",
                      fix=(f"a list is indexed by position only; to find an element by text, "
                           f"search: for i in 0 to {xs} length - 1" if t == TEXT else None))
        lit = literal_number(node.index)
        if lit is not None and (lit < 0 or not is_whole(lit)):
            xs = self.snippet(node.target)
            from_end = lit < 0 and is_whole(lit)              # xs[-1]: counting from the end
            self.fail("V313", node.index, "An index must be a whole number, 0 or greater.",
                      fix=(self.whole_line(node, f"{xs}[{xs} length - {-lit}]") if from_end
                           else "the first element is [0]"))

    def check_key(self, node, key):
        """d[k]: a key is text."""
        t = self.type_of(key)
        if t != TEXT:
            inside_brackets = isinstance(node, Index) and node.index is key
            as_text = f"{self.as_operand(key)} as text"
            fix = (self.whole_line(key, as_text if inside_brackets else f"({as_text})")
                   if t in (NUMBER, BOOL) else None)
            self.fail("V301", key, f"A key of a dictionary is text, got {t}.", fix=fix)

    def set_item(self, node):
        owner = unwrap(node.target.target)
        var = self.lookup(owner.name) if isinstance(owner, Name) else None
        if var is not None and var.type == MapT(PENDING):          # d = {}  ...  d[k] = v
            self.check_key(node.target, node.target.index)
            value_type = self.probe_type(node.value)
            if value_type is not None:
                var.type = MapT(value_type)
                self.empty_lists[var.pos.line] = value_type
            return
        elem = self.container_type(node.target)
        self.check_mutation(root_name(node.target), node.target, inside=True)
        t = self.type_of(node.value)
        if t != elem:
            self.fail("V310", node.value,
                      f"{self.snippet(node.target.target)} holds {elem}; it cannot store {t}.")

    def list_target(self, node, verb):
        t = self.container_type(node.target)
        if not isinstance(t, ListT):
            fix = None
            if isinstance(t, MapT):
                d = self.snippet(node.target)
                fix = f"{d}[k] = v" if verb == "add" else f"{d} remove key k"
            self.fail("V301", node.target, f"{verb} works only on lists; "
                                           f"{self.snippet(node.target)} is {t}.", fix=fix)
        self.check_mutation(root_name(node.target), node.target, inside=True)
        return t

    def list_add(self, node):
        t = self.list_target(node, "add")
        vt = self.type_of(node.value)
        var = self.lookup(node.target.name) if isinstance(node.target, Name) else None
        if var is not None and var.type == ListT(PENDING):
            self.settle_empty_list(var, vt)                     # xs = []  ...  xs add 5
            return
        if vt != t.elem:
            self.fail("V310", node.value,
                      f"{self.snippet(node.target)} holds {t.elem}; it cannot add {vt}.")

    def probe_type(self, node):
        """The type of a value stored into a collection whose own type is still being worked
        out (a bare [] or {}), or None. `counts[w] = if counts contains w then counts[w] + 1
        else 1` reads the collection itself; the parts that do not are enough to tell."""
        try:
            t = self.type_of(node)
            if PENDING not in str(t):
                return t
        except AxionError:
            pass
        node = unwrap(node)
        parts = []
        if isinstance(node, Conditional):
            parts = [node.otherwise, node.then]
        elif isinstance(node, Binary) and node.op in ("+", "-", "*", "/", "//", "%"):
            parts = [node.right, node.left]
        for part in parts:
            t = self.probe_type(part)
            if t is not None:
                return t
        return None

    def settle_empty_list(self, var, elem):
        """The first add to a list created as a bare [] tells what it holds."""
        if PENDING not in str(elem):
            var.type = ListT(elem)
            self.empty_lists[var.pos.line] = elem

    def map_literal(self, node):
        """{"tea": 2, "milk": 1.5}: every value has the same type."""
        first = None
        for key, _line, _col, value in node.pairs:
            t = self.type_of(value)
            if first is None:
                first = t
            elif t != first:
                self.fail("V310", value, f"The values of a dictionary have one type, "
                                         f"got {first} and {t}.",
                          fix="for a record with different fields write the names without "
                              "quotes: " + self.as_object(node))
        return MapT(first)

    def as_object(self, node):
        """A dictionary literal rewritten as an object literal, when its keys can be names."""
        if not all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) for key, *_ in node.pairs):
            return '{name: "A", age: 3}'
        return "{" + ", ".join(f"{key}: {self.snippet(value)}"
                               for key, _line, _col, value in node.pairs) + "}"

    def round_type(self, node):
        t = self.type_of(node.target)
        if t != NUMBER:
            fix = (f"convert first: {self.as_operand(node.target)} as number"
                   if t == TEXT else None)
            self.fail("V301", node, f"{node.op} works on a number, got {t}.", fix=fix)
        if node.places is not None:
            places = self.type_of(node.places)
            if places != NUMBER:
                fix = None
                inner = unwrap(node.places)
                if isinstance(inner, As):                    # total round 2 as text
                    fix = self.whole_line(node, f"({self.snippet(node.target)} round "
                                                f"{self.snippet(inner.operand)}) as {inner.type}")
                self.fail("V301", node.places, f"round needs the number of places, got {places}.",
                          fix=fix)
            lit = literal_number(node.places)
            if lit is not None and (lit < 0 or not is_whole(lit)):
                self.fail("V312", node.places, "The number of places is a whole number, 0 or greater.",
                          fix="0 gives a whole number, 2 gives two places after the point")
        return NUMBER

    def date_type(self, node):
        t = self.type_of(node.operand)
        x = self.snippet(node.operand)
        if node.op == "as date":                             # a number of days -> "2026-10-05"
            if t != NUMBER:
                fix = "the text is already a date; to check it: " + f"{x} is date" if t == TEXT else None
                self.fail("V311", node, f"as date turns a number of days into a date, got {t}.",
                          fix=fix)
            return TEXT
        if t != TEXT:                                        # is date / as days need a text
            fix = f"a number of days becomes a date with: {x} as date" if t == NUMBER else None
            self.fail("V311", node, f'{node.op} reads a date written as text ("2026-10-05"), got {t}.',
                      fix=fix)
        if node.op == "as days":
            lit = unwrap(node.operand)
            if isinstance(lit, Text) and parse_date(lit.value) is None:
                self.fail("V311", node, f'"{lit.value}" is not a date.',
                          fix='a date is year-month-day with two-digit month and day: "2026-10-05"')
            return NUMBER
        return BOOL

    def split_type(self, node):
        t, sep = self.type_of(node.target), self.type_of(node.separator)
        if t != TEXT:
            fix = None
            if t == ListT(TEXT) and sep == TEXT and isinstance(unwrap(node.target), Split):
                fix = (f"split each part in a loop: for part in {self.as_operand(node.target)}"
                       f"   and inside it: part split {self.snippet(node.separator)}")
            elif t == ListT(TEXT) and sep == TEXT:         # words split ", ": join was meant
                fix = self.whole_line(node, f"{self.snippet(node.target)} join "
                                            f"{self.snippet(node.separator)}")
            self.fail("V301", node, f"split takes text apart, got {t}.", fix=fix)
        if sep != TEXT:
            self.fail("V301", node.separator, f"The separator of split must be text, got {sep}.")
        lit = unwrap(node.separator)
        if isinstance(lit, Text) and lit.value == "":
            self.fail("V312", node.separator, "The separator of split cannot be empty.",
                      fix="to go over the characters write: for ch in "
                          f"{self.snippet(node.target)}")
        return ListT(TEXT)

    def contains_type(self, node):
        t, item = self.type_of(node.target), self.type_of(node.item)
        xs = self.snippet(node.target)
        if t == TEXT:
            if item != TEXT:
                fix = (self.whole_line(node.item, f"({self.snippet(node.item)} as text)")
                       if item in (NUMBER, BOOL) else None)
                self.fail("V301", node.item, f"{xs} is text, so contains looks for text, "
                                             f"got {item}.", fix=fix)
            return BOOL
        if isinstance(t, MapT):                              # d contains key
            self.check_key(node.target, node.item)
            return BOOL
        if isinstance(t, ListT):
            if item != t.elem:
                fix = None
                if t.elem == TEXT and item in (NUMBER, BOOL):      # keys contains n
                    fix = self.whole_line(node.item, f"({self.snippet(node.item)} as text)")
                elif t.elem == NUMBER and item == TEXT and not isinstance(unwrap(node.item), Text):
                    fix = self.whole_line(node.item, f"({self.snippet(node.item)} as number)")
                self.fail("V310", node.item, f"{xs} holds {t.elem}; it cannot contain {item}.",
                          fix=fix)
            return BOOL
        self.fail("V301", node, f"contains works on text, lists and dictionaries, got {t}.")

    def conditional_type(self, node):
        """if c then a else b: the condition is bool, both values have one type."""
        t = self.type_of(node.cond)
        if t != BOOL:
            cond = self.snippet(node.cond)
            hint = {NUMBER: f"{cond} > 0", TEXT: f'{cond} != ""'}.get(t)
            self.fail("V307", node.cond, f"The condition must be bool, got {t}.",
                      fix=f"compare it, e.g. if {hint} then ..." if hint else None)
        yes, no = self.type_of(node.then), self.type_of(node.otherwise)
        if yes != no:
            fix = None
            if {yes, no} == {NUMBER, TEXT}:
                number = node.then if yes == NUMBER else node.otherwise
                as_text = (f'"{self.snippet(number)}"' if isinstance(unwrap(number), Number)
                           else f"{self.as_operand(number)} as text")
                fix = f"make both text: write {as_text} instead of {self.snippet(number)}"
            self.fail("V301", node, f"Both values of if ... then ... else must have one type, "
                                    f"got {yes} and {no}.", fix=fix)
        return yes

    def list_remove(self, node):
        if node.mode == "key":                               # d remove key k
            t = self.container_type(node.target)
            d = self.snippet(node.target)
            if not isinstance(t, MapT):
                fix = (f"{d} remove value {self.snippet(node.value)}   or   {d} remove index i"
                       if isinstance(t, ListT) else None)
                self.fail("V301", node.target, f"remove key works on a dictionary; {d} is {t}.",
                          fix=fix)
            self.check_mutation(root_name(node.target), node.target, inside=True)
            self.check_key(node.target, node.value)
            return
        if isinstance(self.container_type(node.target), MapT):
            d = self.snippet(node.target)
            key = self.snippet(node.value) if self.type_of(node.value) == TEXT else "k"
            self.fail("V301", node.target, f"{d} is a dictionary: an entry is removed by its key.",
                      fix=f"{d} remove key {key}")
        t = self.list_target(node, "remove")
        vt = self.type_of(node.value)
        if node.mode == "index":
            if vt != NUMBER:
                self.fail("V301", node.value, f"remove index needs a number, got {vt}.")
            lit = literal_number(node.value)
            if lit is not None and (lit < 0 or not is_whole(lit)):
                self.fail("V313", node.value, "An index must be a whole number, 0 or greater.")
        elif vt != t.elem:
            self.fail("V310", node.value,
                      f"{self.snippet(node.target)} holds {t.elem}; it cannot contain {vt}.")

    def if_statement(self, node):
        for i, branch in enumerate(node.branches):
            t = self.type_of(branch.condition)
            if t != BOOL:
                cond = self.snippet(branch.condition)
                if isinstance(t, ListT):
                    hint = f"{cond} length > 0"
                else:
                    hint = {NUMBER: f"{cond} > 0", TEXT: f'{cond} != ""'}.get(t)
                keyword = "if" if i == 0 else "else if"
                self.fail("V307", branch.condition, f"The condition must be bool, got {t}.",
                          fix=f"{keyword} {hint}" if hint else None)
        all_branches = node.branches + ([node.else_branch] if node.else_branch else [])
        for i, branch in enumerate(all_branches):
            if not branch.body:
                self.empty_branch(node, i, branch)
            self.push()
            self.statements(branch.body)
            self.pop("if", node.line)

    def empty_branch(self, node, index, branch):
        if index == 0 and node.else_branch is not None and len(node.branches) == 1:
            cond = branch.condition
            inner = unwrap(cond)
            negated = (f"not {self.snippet(cond)}" if isinstance(inner, (Name, Bool)) or cond is not inner
                       else f"not ({self.snippet(cond)})")
            fix = f"if {negated}"
        elif index == 0 and len(node.branches) == 1 and node.else_branch is None:
            fix = "remove this if, or add an action"
        else:
            fix = "remove the empty branch"
        name = "if" if index == 0 else ("else" if branch.condition is None else "else if")
        raise AxionError("V306", branch.line, branch.col, f"The {name} branch is empty.",
                         fix=fix, length=len(name))

    def for_statement(self, node):
        t = self.type_of(node.iterable)
        if t == TEXT:
            t = ListT(TEXT)                       # for ch in s: one character at a time
        if isinstance(t, MapT):
            self.fail("V301", node.iterable, "for goes over a list or text; a dictionary is "
                                             "walked by its keys.",
                      fix=f"for {node.var} in {self.snippet(node.iterable)} keys")
        if not isinstance(t, ListT):
            fix = f"for {node.var} in 1 to {self.snippet(node.iterable)}" if t == NUMBER else None
            self.fail("V301", node.iterable, f"for needs a list or text, got {t}.", fix=fix)
        pos = Position(node.var_line, node.var_col)
        if self.lookup(node.var) is not None:
            raise AxionError("V315", pos.line, pos.col,
                             f"{node.var} already exists; a loop variable needs a new name.",
                             fix=f"for {node.var}_item in {self.snippet(node.iterable)}",
                             length=len(node.var))
        if not node.body:
            raise AxionError("V306", node.line, node.col, "The for body is empty.",
                             fix="add an action, or remove the loop", length=3)
        self.check_name_free(node.var, pos.line, pos.col)
        walked = unwrap(node.iterable)
        source = self.snippet(walked) if isinstance(walked, (Name, Index, Field)) else None
        if isinstance(walked, Index) and isinstance(unwrap(walked.index), Range):
            source = None                # a piece xs[a to b] is a copy: its elements are not xs's
        self.locked.append(root_name(node.iterable))
        self.push()
        self.scopes[-1][node.var] = Variable(node.var, t.elem, pos, loop=True, source=source,
                                             counted=isinstance(walked, Range),
                                             root=root_name(node.iterable) if source else None)
        self.loops += 1
        self.statements(node.body)       # never raises: errors inside are collected
        self.loops -= 1
        self.pop("for", node.line)
        self.locked.pop()

    def while_statement(self, node):
        t = self.type_of(node.condition)
        if t != BOOL:
            cond = self.snippet(node.condition)
            if literal_number(node.condition) is not None:
                hint = "true"
            elif isinstance(t, (ListT, MapT)):
                hint = f"{cond} length > 0"
            else:
                hint = {NUMBER: f"{cond} > 0", TEXT: f'{cond} != ""'}.get(t)
            self.fail("V307", node.condition, f"The condition must be bool, got {t}.",
                      fix=f"while {hint}" if hint else None)
        if not node.body:
            raise AxionError("V306", node.line, node.col, "The while body is empty.",
                             fix="add an action, or remove the loop", length=5)
        self.push()
        self.loops += 1
        self.statements(node.body)       # never raises: errors inside are collected
        self.loops -= 1
        self.collect(lambda: self.check_can_stop(node))     # before the block's names are gone
        self.pop("while", node.line)

    def check_can_stop(self, node):
        """The guard of while before the run (V328): the body must change a variable of the
        condition, or leave the loop itself. The step limit of the launch stays the second guard."""
        if leaves_loop(node.body):
            return
        names = [n for n in dict.fromkeys(names_in(node.condition)) if self.lookup(n) is not None]
        if set(names) & changed_names(node.body):
            return
        if not names:
            self.fail("V328", node.condition, "This while can never stop: its condition has no "
                                              "variable, and the body has no break.",
                      fix="add the way out inside the loop: an if with break")
        listed = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " or " + names[-1]
        free = [n for n in names if not (self.lookup(n).param or self.lookup(n).loop)]
        if free:
            first = free[0]
            example = f", for example {first} = {first} + 1" if self.lookup(first).type == NUMBER else ""
            fix = f"change {first} inside the loop{example}, or leave the loop with break"
        else:                            # only parameters and loop variables: they cannot change
            first = names[0]
            fix = (f"copy it before the loop (left = {first}), use the copy in the condition and "
                   f"change the copy inside the loop")
        self.fail("V328", node.condition, f"This while can never stop: the body does not change "
                                          f"{listed} and has no break.", fix=fix)

    # --- permissions (spec §15) ---
    def allow(self, node):
        folder = normalize_folder(node.folder)
        if unsafe_path(folder):
            # The request stays known (as used), so the reads below are not also reported:
            # one refusal, one fix.
            self.allows.append([node, folder, True])
            self.fail("S503", node, f'allow read "{node.folder}": the folder must be relative '
                                    f"and must not contain ..",
                      fix='Axion reads only inside the folder the host allows. Use a relative '
                          'folder, for example: allow read "reports/"')
        if not self.reads_files:
            # A request the program never uses comes first: the author can fix that one.
            self.fail("V305", node, f'allow read "{folder}" is never used.',
                      fix="remove it: a program asks only for what it uses")
        if not self.policy.permits_read(folder):
            # The request stays known, so the reads below are not also reported as undeclared.
            self.allows.append([node, folder, True])
            self.fail("S502", node, f'The launch policy does not allow reading "{folder}".',
                      fix="only the person running the program can grant this")
        self.allows.append([node, folder, False])

    def read_type(self, node):
        """read path -> text, exists path -> bool: one set of rules for the path of both."""
        word = "exists" if isinstance(node, Exists) else "read"
        result = BOOL if word == "exists" else TEXT
        path = node.path
        if isinstance(path, (Length, IsNumber)) or (isinstance(path, As) and path.type == NUMBER):
            # read p as number: the author wants the file converted, not the path.
            what = "number" if not isinstance(path, IsNumber) else "bool"
            self.fail("V301", path, f"{word} takes the whole expression after it as the path; "
                                    f"this one is {what}.", fix=self.read_fix(node))
        if isinstance(path, Binary) and path.op in ("and", "or"):      # exists p and ready
            self.fail("V301", path, f"{word} takes the whole expression after it as the path; "
                                    f"this one is bool.", fix=self.read_fix(node))
        if isinstance(path, (TextOp, Split, Contains, Affix, Round, DateOp)):  # read p trim
            done = self.lines[path.line - 1][self.inner_of(path).end - 1:path.end - 1].split()[0]
            self.fail("V301", path, f"{word} takes the whole expression after it as the path, "
                                    f"so {done} would apply to the path, not to the "
                                    f"{'file' if word == 'read' else 'answer'}.",
                      fix=self.read_fix(node) + f"   (or, for the path itself: {word} "
                                                f"({self.snippet(path)}))")
        t = self.type_of(node.path)
        if t != TEXT:
            self.fail("V301", node.path, f"{word} takes the whole expression after it as the path; "
                                         f"this one is {t}.", fix=self.read_fix(node))
        lit = unwrap(node.path)
        literal = lit.value if isinstance(lit, Text) else None
        if literal is not None and literal.endswith("/"):
            needs = "read needs a file" if word == "read" else "exists checks a file"
            self.fail("V326", node, f'{needs}; "{literal}" is a folder.',
                      fix=f'name a file inside it: {word} "{literal}file.txt"')
        folder_hint = (literal.rsplit("/", 1)[0] + "/") if literal and "/" in literal else "folder/"
        if not self.allows:
            # Never advise a folder that allow itself refuses (absolute, or with ..).
            fix = ("Axion cannot read outside its folder: use a relative path, for example: "
                   'allow read "reports/" and read "reports/file.txt"' if unsafe_path(folder_hint)
                   else f'add at the top: allow read "{folder_hint}"')
            self.fail("S501", node, "Reading files is not declared." if word == "read" else
                                    "Looking at files is not declared.", fix=fix)
        if literal is None:
            for entry in self.allows:        # a computed path may use any declared folder
                entry[2] = True
            return result
        if unsafe_path(literal):
            if any(unsafe_path(e[1]) and literal.startswith(e[1]) for e in self.allows):
                return result                # its allow read is already refused (S503 there)
            self.fail("S503", node.path, f'"{literal}" leaves the allowed folders.',
                      fix="use a relative path inside the allowed folders: no / at the start, no ..")
        for entry in self.allows:
            if literal.startswith(entry[1]):
                entry[2] = True
                return result
        declared = ", ".join(f'"{e[1]}"' for e in self.allows)
        self.fail("S503", node.path, f'"{literal}" is outside the declared folders ({declared}).',
                  fix=f'name a file inside {declared}, or declare allow read "{folder_hint}"')

    @staticmethod
    def inner_of(node):
        """The value a word after a value was applied to: s in `s trim`, `s length`, `s as number`."""
        return node.target if hasattr(node, "target") else node.operand

    def read_fix(self, node):
        """read p length / read p == "": the author meant (read p) length, (read p) == ""."""
        word = "exists" if isinstance(node, Exists) else "read"
        path = node.path
        if isinstance(path, (Length, As, IsNumber, TextOp, Split, Contains, Affix, Round, DateOp)):
            inner = self.inner_of(path)
            rest = self.lines[path.line - 1][inner.end - 1:path.end - 1]
            return self.whole_line(node, f"({word} {self.snippet(inner)}){rest}")
        if isinstance(path, Binary) and path.op in EQUALITY + ORDERING + ("and", "or"):
            rest = self.lines[path.line - 1][path.left.end - 1:path.end - 1]
            return self.whole_line(node, f"({word} {self.snippet(path.left)}){rest}")
        return None

    # --- functions (spec §13) ---
    def function(self, node):
        sig = self.functions[node.name]
        saved = (self.scopes, self.dead, self.locked, self.current, self.loops)
        # A function body is a separate world: it sees only its parameters and other functions.
        self.scopes, self.dead, self.locked, self.current, self.loops = [{}], {}, [], sig, 0
        try:
            for p in node.params:
                self.check_name_free(p.name, p.line, p.col)
                self.scopes[0][p.name] = Variable(p.name, p.type, Position(p.line, p.col), param=True)
            if not node.body:
                raise AxionError("V306", node.line, node.col, f"The function {node.name} is empty.",
                                 fix="add its body, or remove it", length=8)
            self.statements(node.body)
            self.check_unused(self.scopes[0])
            if sig.result is not None and not body_returns(node.body):
                raise AxionError("V318", node.line, node.name_col,
                                 f"{node.name} may finish without return; it must return "
                                 f"{sig.result} on every path.",
                                 fix="add a return at the end, or a return in every branch including else",
                                 length=len(node.name))
        finally:
            self.scopes, self.dead, self.locked, self.current, self.loops = saved

    def return_statement(self, node):
        if self.current is None:
            self.fail("V321", node, "return can only be used inside a function.",
                      fix="to end the program here write exit")
        sig = self.current
        if sig.result is None:
            self.fail("V321", node, f"{sig.name} has no result, so it cannot return.",
                      fix=f"remove return, or declare a result: function {sig.name}(...) -> type")
        if node.value is None:
            self.fail("V321", node, f"return needs a value: {sig.name} returns {sig.result}.")
        t = self.type_of(node.value)
        if t != sig.result:
            self.fail("V301", node.value, f"{sig.name} must return {sig.result}, got {t}.")

    def call_type(self, node, as_statement=False):
        sig = self.functions.get(node.name)
        if sig is None:
            if self.lookup(node.name) is not None:
                self.fail("V303", node, f"{node.name} is a variable, not a function.")
            for arg in node.args:                    # sum(x * 2 for x in xs)
                if isinstance(arg, Comprehension):
                    self.comprehension(arg, node)
            if node.name == "range" and len(node.args) == 3:      # range(10, 0, -2)
                a, b, step = (self.snippet(arg) for arg in node.args)
                down = step.lstrip("(").startswith("-")
                self.fail("V303", node, "range() does not exist in Axion, and a to b counts by 1.",
                          fix=f"count with while: i = {a}   then   while i {'>' if down else '<'} {b}"
                              f"   then   ...   then   i = i {'-' if down else '+'} "
                              f"{step.strip('()-') if down else step}   then   end")
            if node.name in ("reversed", "reverse") and len(node.args) == 1:
                self.fail("V303", node, f"{node.name}() does not exist in Axion: there is no reverse.",
                          fix=reverse_fix(self.snippet(node.args[0])))
            if node.name == "quit":
                self.fail("V303", node, "quit() does not exist in Axion.", fix="exit")
            if node.name == "exists" and len(node.args) == 1:        # exists("a.txt")
                self.fail("V303", node, "exists is written without brackets, like read.",
                          fix=self.whole_line(node, f"(exists {self.snippet(node.args[0])})"))
            if node.name in FOREIGN_EMPTY and (not node.args or node.name in ("defaultdict", "Counter")):
                self.fail("V303", node, f"{node.name}() does not exist in Axion.",
                          fix=FOREIGN_EMPTY[node.name])
            if node.name in FOREIGN_FUNCTIONS and len(node.args) == 1:
                self.fail("V303", node, f"{node.name}() does not exist in Axion.",
                          fix=self.foreign_call_fix(node))
            if node.name in FOREIGN_FUNCTIONS_TWO and len(node.args) == 2:   # round(x, 2)
                a, b = (self.as_operand(arg) for arg in node.args)
                self.fail("V303", node, f"{node.name}() does not exist in Axion.",
                          fix=self.whole_line(node, FOREIGN_FUNCTIONS_TWO[node.name].format(a, b)))
            if node.name in ("min", "max") and len(node.args) >= 2:      # min(3, n)
                items = ", ".join(self.snippet(arg) for arg in node.args)
                self.fail("V303", node, f"{node.name}() does not exist in Axion: "
                                        f"{node.name} is written after a list of numbers.",
                          fix=self.whole_line(node, f"[{items}] {node.name}"))
            close = difflib.get_close_matches(node.name, list(self.functions), n=1, cutoff=0.5)
            fix = f"did you mean {close[0]}?" if close else f"define it: function {node.name}(...)"
            if close:
                self.functions[close[0]].used = True
            self.fail("V303", node, f"Unknown function {node.name}.", fix=fix)
        if self.current is not sig:      # a function that only calls itself is still never called
            sig.used = True
        self.calls.setdefault(self.current.name if self.current else None, []).append((sig.name, node))
        if len(node.args) != len(sig.params):
            self.fail("V323", node, f"{sig.name} takes {len(sig.params)} argument(s), "
                                    f"got {len(node.args)}.", fix=sig.text())
        for arg, p in zip(node.args, sig.params):
            t = self.type_of(arg)
            if t != p.type:
                self.fail("V323", arg, f"The argument {p.name} of {sig.name} must be {p.type}, got {t}.",
                          fix=sig.text())
        if sig.result is None and not as_statement:
            self.fail("V323", node, f"{sig.name} returns nothing, so it cannot be used as a value.",
                      fix=f"call it on its own line: {self.snippet(node)}")
        return sig.result

    def foreign_call_fix(self, node):
        """str(x) -> x as text, written so that the Fix itself is valid for the type of x."""
        arg = node.args[0]
        template = FOREIGN_FUNCTIONS[node.name]
        if not template.endswith((" as text", " as number")):
            return self.whole_line(node, template.format(self.as_operand(arg)))      # len, range
        target = TEXT if template.endswith(" as text") else NUMBER
        source = self.type_of(arg)
        if node.name == "int" and source == NUMBER:  # int(7.5): the whole part of a number
            return self.whole_line(node, f"({self.as_operand(arg)} floor)")
        if source == target:                         # str(n as text): the value is already text
            return self.whole_line(node, self.snippet(arg))
        if (source, target) in {(NUMBER, TEXT), (BOOL, TEXT), (TEXT, NUMBER)}:
            return self.whole_line(node, template.format(self.as_operand(arg)))
        if isinstance(source, (ListT, ObjectT, MapT)):
            return f"print shows lists, objects and dictionaries directly: print {self.snippet(arg)}"
        return None

    def check_recursion(self):
        """Recursion is allowed when it can stop (V322): a function must have a path that ends
        without calling itself, directly or through other functions. The depth limit of the
        launch is the second guard."""
        finishing = set()                # functions with a path that ends
        grown = True
        while grown:
            grown = False
            for name, sig in self.functions.items():
                if name in finishing:
                    continue
                stuck = lambda callee: callee in self.functions and callee not in finishing
                if outcomes(sig.node.body, stuck) & {"fall", "return"}:
                    finishing.add(name)
                    grown = True
        reported = set()
        for start in self.functions:
            if start in finishing or start in reported:
                continue
            circle = self.circle_from(start, finishing)
            if circle is None:           # it only waits for another function that never ends
                continue
            path, node = circle
            reported.update(path)
            if len(path) == 1:
                has_result = self.functions[start].result is not None
                self.errors.append(AxionError(
                    "V322", node.line, node.col,
                    f"{start} calls itself on every path, so it can never finish.",
                    fix=(f"before this call add the case that stops: if ... return ... end"
                         if has_result else
                         f"put this call inside an if, so that some path ends without it"),
                    length=max(1, node.end - node.col)))
            else:
                chain = " -> ".join(path + [start])
                self.errors.append(AxionError(
                    "V322", node.line, node.col,
                    f"{chain}: these functions call each other on every path, so they can "
                    f"never finish.",
                    fix="give one of them a path that ends without the call",
                    length=max(1, node.end - node.col)))

    def circle_from(self, start, finishing):
        """A chain of calls from start back to start through functions that cannot finish:
        (the names on the chain, the first call of the chain), or None."""
        seen = set()
        stack = [(start, [start], None)]
        while stack:
            fn, path, first = stack.pop()
            for callee, node in self.calls.get(fn, []):
                if callee in finishing:
                    continue
                if callee == start:
                    return path, first or node
                if callee not in seen:
                    seen.add(callee)
                    stack.append((callee, path + [callee], first or node))
        return None

    # --- expressions ---
    def type_of(self, node):
        if isinstance(node, Number):
            return NUMBER
        if isinstance(node, Text):
            return TEXT
        if isinstance(node, Bool):
            return BOOL
        if isinstance(node, Group):
            return self.type_of(node.inner)
        if isinstance(node, Name):
            var = self.find(node)
            var.used = True
            return var.type
        if isinstance(node, Unary):
            t = self.type_of(node.operand)
            if t != NUMBER:
                self.fail("V301", node, f"Unary - needs a number, got {t}.")
            return NUMBER
        if isinstance(node, Not):
            t = self.type_of(node.operand)
            if t != BOOL:
                fix = (f"compare first, e.g. not ({self.snippet(node.operand)} == 0)"
                       if t == NUMBER else None)
                self.fail("V301", node, f"not needs a bool, got {t}.", fix=fix)
            return BOOL
        if isinstance(node, ListLit):
            return self.list_literal(node)
        if isinstance(node, FormatText):
            self.format_text(node)
        if isinstance(node, Comprehension):
            self.comprehension(node)
        if isinstance(node, EmptyList):
            return ListT(PENDING if node.elem_type is None else node.elem_type)
        if isinstance(node, Conditional):
            return self.conditional_type(node)
        if isinstance(node, Index):
            container = self.type_of(node.target)
            self.check_index(node, container)
            if isinstance(container, MapT):
                return container.value
            if container == TEXT or isinstance(unwrap(node.index), Range):
                return container                  # one character is text; a piece keeps the type
            return container.elem
        if isinstance(node, EmptyMap):
            return MapT(PENDING if node.value_type is None else node.value_type)
        if isinstance(node, MapLit):
            return self.map_literal(node)
        if isinstance(node, Keys):
            t = self.type_of(node.target)
            if not isinstance(t, MapT):
                fix = None
                if isinstance(t, ObjectT):
                    fix = "an object has fixed fields: read them by name, " + ", ".join(
                        f"{self.snippet(node.target)}.{f}" for f in t.fields)
                self.fail("V301", node, f"keys works on a dictionary, got {t}.", fix=fix)
            return ListT(TEXT)
        if isinstance(node, TextOp):
            t = self.type_of(node.target)
            if t != TEXT:
                self.fail("V301", node, f"{node.op} works on text, got {t}.")
            return TEXT
        if isinstance(node, Split):
            return self.split_type(node)
        if isinstance(node, Round):
            return self.round_type(node)
        if isinstance(node, DateOp):
            return self.date_type(node)
        if isinstance(node, Contains):
            return self.contains_type(node)
        if isinstance(node, Affix):
            t, part = self.type_of(node.target), self.type_of(node.part)
            if t != TEXT or part != TEXT:
                self.fail("V301", node, f"{node.op} with compares text with text, "
                                        f"got {t} and {part}.")
            return BOOL
        if isinstance(node, Length):
            t = self.type_of(node.target)
            if not isinstance(t, (ListT, MapT)) and t != TEXT:
                self.fail("V301", node, f"length works on lists, text and dictionaries, got {t}.")
            return NUMBER
        if isinstance(node, Range):
            return self.range_type(node)
        if isinstance(node, ObjectLit):
            return ObjectT({name: self.type_of(value) for name, value in node.fields})
        if isinstance(node, Field):
            return self.field_type(node, self.type_of(node.target))
        if isinstance(node, As):
            return self.as_type(node)
        if isinstance(node, Call):
            return self.call_type(node)
        if isinstance(node, (Read, Exists)):
            return self.read_type(node)
        if isinstance(node, IsNumber):
            t = self.type_of(node.operand)
            if t != TEXT:
                self.fail("V311", node, f"is number checks text only; this value is already {t}.")
            return BOOL
        if isinstance(node, Sort):
            return self.sort_type(node)
        if isinstance(node, Aggregate):
            return self.aggregate_type(node)
        if isinstance(node, Join):
            return self.join_type(node)
        if isinstance(node, Binary):
            return self.binary(node)
        raise TypeError(f"unknown expression {type(node).__name__}")

    # --- list operations: sort, sum, min, max, join ---
    def number_fields(self, shape):
        return [name for name, t in shape.fields.items() if t == NUMBER]

    def sort_type(self, node):
        t = self.type_of(node.target)
        xs = self.snippet(node.target)
        if not isinstance(t, ListT):
            self.fail("V301", node, f"sort works on lists, got {t}.")
        if node.field is None:
            if t.elem in (NUMBER, TEXT):
                return t
            fix = None
            if isinstance(t.elem, ObjectT) and self.sortable_fields(t.elem):
                fix = f"name a field: {xs} sort by {self.sortable_fields(t.elem)[0]}"
            self.fail("V301", node, f"sort without by works on a list of numbers or of text; "
                                    f"{xs} is {t}.", fix=fix)
        if not isinstance(t.elem, ObjectT):
            order = " descending" if node.descending or node.field == "descending" else ""
            self.fail("V309", node, f"sort by needs a list of objects; {xs} is {t}.",
                      fix=self.whole_line(node, f"{xs} sort{order}") if t.elem in (NUMBER, TEXT) else None)
        named = [node.field] + [name for name, _ in node.more]
        for k, name in enumerate(named):
            if name not in t.elem.fields:
                close = difflib.get_close_matches(name, list(t.elem.fields), n=1, cutoff=0.5)
                self.fail("V309", node, f"There is no field {name}; fields are: "
                                        f"{', '.join(t.elem.fields)}.",
                          fix=f"did you mean {close[0]}?" if close else None)
            if t.elem.fields[name] not in (NUMBER, TEXT):
                fields = self.sortable_fields(t.elem)
                self.fail("V301", node, f"sort by needs a number or text field; {name} is "
                                        f"{t.elem.fields[name]}.",
                          fix=f"sort by one of: {', '.join(fields)}" if fields else None)
            if name in named[:k]:
                self.fail("V309", node, f"sort by names the field {name} twice; the second "
                                        f"one changes nothing.", fix="remove one of them")
        return t

    @staticmethod
    def sortable_fields(obj):
        return [name for name, t in obj.fields.items() if t in (NUMBER, TEXT)]

    def aggregate_type(self, node):
        t = self.type_of(node.target)
        if t != ListT(NUMBER):
            xs = self.snippet(node.target)
            fix = None
            if isinstance(t, ListT) and isinstance(t.elem, ObjectT) and self.number_fields(t.elem):
                field = self.number_fields(t.elem)[0]
                fix = (f"{node.op} has no by: add the field up in a loop (for x in {xs}, "
                       f"total = total + x.{field})" if node.op == "sum" else
                       f"take the first element after sorting: ({xs} sort by {field}"
                       f"{' descending' if node.op == 'max' else ''})[0]")
            self.fail("V301", node, f"{node.op} works on a list of numbers, got {t}.", fix=fix)
        return NUMBER

    def join_type(self, node):
        t = self.type_of(node.target)
        if t != ListT(TEXT):
            fix = ("make a list of text first: parts = [] of text, then for n in "
                   f"{self.snippet(node.target)}, parts add n as text"
                   if t == ListT(NUMBER) else None)
            self.fail("V301", node, f"join works on a list of text, got {t}.", fix=fix)
        st = self.type_of(node.separator)
        if st != TEXT:
            self.fail("V301", node.separator, f"The separator of join must be text, got {st}.")
        return TEXT

    def list_literal(self, node):
        types = [self.type_of(item) for item in node.items]
        for i, t in enumerate(types[1:], start=2):
            if t != types[0]:
                self.fail("V310", node.items[i - 1],
                          f"All list elements must have one type: element 1 is {types[0]}, "
                          f"element {i} is {t}.")
        return ListT(types[0])

    def as_type(self, node):
        source = self.type_of(node.operand)
        target = node.type
        allowed = {(NUMBER, TEXT), (BOOL, TEXT), (TEXT, NUMBER)}
        if source == target:
            self.fail("V311", node, f"The value is already {target}.", fix=f"remove as {target}")
        if (source, target) not in allowed:
            fix = None
            if source == NUMBER and target == BOOL:
                fix = f"compare instead: {self.as_operand(node.operand)} != 0"
            elif isinstance(source, (ListT, ObjectT, MapT)):
                fix = f"print shows lists, objects and dictionaries directly: print {self.snippet(node.operand)}"
            self.fail("V311", node, f"{source} cannot be converted to {target}.", fix=fix)
        lit = unwrap(node.operand)
        if target == NUMBER and isinstance(lit, Text) and text_number(lit.value) is None:
            if NUMBER_TEXT.fullmatch(lit.value):
                self.fail("V314", node, f'"{lit.value}" is too large for a number: a number keeps 28 digits.')
            self.fail("V314", node, f'"{lit.value}" is not a number.',
                      fix="digits with an optional minus and .fraction, e.g. \"-2.5\"")
        return target

    def range_type(self, node, piece=False):
        for side in (node.start, node.stop):
            t = self.type_of(side)
            if t != NUMBER:
                self.fail("V301", side, f"to needs numbers, got {t}.")
            lit = literal_number(side)
            if lit is not None and not is_whole(lit):
                self.fail("V317", side, "Range bounds must be whole numbers.")
            if piece and lit is not None and lit < 0:
                self.fail("V313", side, "A position must be a whole number, 0 or greater.",
                          fix="the first position is 0; the last is length - 1")
        a, b = literal_number(node.start), literal_number(node.stop)
        if a is not None and b is not None and b < a:
            self.fail("V317", node, "This range is empty: to only counts up.",
                      fix=f"{self.snippet(node.stop)} to {self.snippet(node.start)}")
        return ListT(NUMBER)

    @staticmethod
    def one_element(node):
        node = unwrap(node)
        return isinstance(node, ListLit) and len(node.items) == 1

    # --- habits that need types for an exact answer ---
    def format_text(self, node):
        """f"Total: {x}" -> "Total: " + x as text, with as text only where the value needs it."""
        pieces, exact = [], True
        for part in node.parts:
            if part[0] == "text":
                pieces.append('"' + part[1] + '"')
                continue
            value, layout = part[1], part[2].strip()
            t = self.type_of(value)
            source = self.snippet(value)
            places = re.fullmatch(r"\.([0-9]+)f", layout)
            if t == NUMBER and places:
                pieces.append(f"({self.as_operand(value)} round {places.group(1)}) as text")
            elif layout or t not in (NUMBER, TEXT, BOOL):
                exact = False
            elif t == TEXT:
                pieces.append(f"({source})" if isinstance(value, Conditional) else source)
            else:
                pieces.append(f"{self.as_operand(value)} as text")
        fix = self.whole_line(node, " + ".join(pieces) or '""') if exact else FORMAT_TEXT_SHAPE
        self.fail("P210", node, NO_FORMAT_TEXT, fix=fix)

    def comprehension(self, node, call=None):
        """[x * 2 for x in xs if x > 1], sum(x.n for x in xs): the Fix is the loop written out
        with the author's names and the real element type."""
        message = NO_COMPREHENSION if call is None else (
            f"The loop is written out in Axion, not inside the brackets of {call.name}().")
        t = self.type_of(node.iterable)
        elem = TEXT if t == TEXT else t.elem if isinstance(t, ListT) else None
        if elem is None or self.lookup(node.var) is not None:
            self.fail("P210", node, message, fix=COMPREHENSION_SHAPE)
        self.scopes.append({node.var: Variable(node.var, elem, Position(node.line, node.col), loop=True)})
        try:
            item_type = self.type_of(node.item)
            if node.condition is not None:
                self.type_of(node.condition)
            walked = self.scopes[-1][node.var].used
        finally:
            self.scopes.pop()
        whole = call or node
        line = self.lines[node.line - 1].split("#")[0]
        target = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*", line)
        named = target is not None and line[target.end():].strip() == self.snippet(whole)
        item = self.snippet(node.item)
        if isinstance(node.item, Conditional):
            item = f"({item})"
        kind = call.name if call is not None and len(call.args) == 1 else "list"
        default, start, action = {
            "sum": ("total", "0", ["NAME = NAME + ITEM"]),
            "len": ("count", "0", ["NAME = NAME + 1"]),
            "any": ("found", "false", ["if ITEM", "NAME = true", "break", "end"]),
            "all": ("ok", "true", ["if not (ITEM)", "NAME = false", "break", "end"]),
        }.get(kind, ("items", f"[] of {item_type}", ["NAME add ITEM"]))
        name = target.group(1) if named else default
        over = self.snippet(node.iterable)
        if not walked:                   # [0 for x in xs]: only the number of elements matters
            over = f"1 to {self.as_operand(node.iterable)} length"
        lines = [f"{name} = {start}", f"for {node.var} in {over}"]
        if node.condition is not None:
            lines.append(f"if {self.snippet(node.condition)}")
        lines += [text.replace("NAME", name).replace("ITEM", item) for text in action]
        lines += ["end"] * (2 if node.condition is not None else 1)
        fix = "   then   ".join(lines)
        if not named:
            place = "the brackets" if kind == "list" else f"{call.name}(...)"
            fix += f"   then use {name} in place of {place}"
        self.fail("P210", node, message, fix=fix)

    def misplaced_round(self, node):
        """total / count round 2: round binds to count alone, and count is already whole, so
        the line would run and round nothing. A rounding at the right end of a calculation
        must say in parentheses what it rounds."""
        last = node
        while isinstance(last, Binary) and last.op in ARITHMETIC:
            last = last.right                        # the right end; parentheses stop the walk
        chain = []
        while isinstance(last, (As, Round)):
            chain.append(last)
            last = last.operand if isinstance(last, As) else last.target
        if not any(isinstance(link, Round) for link in chain):
            return
        if isinstance(last, Group):
            return                       # (h / t) ceiling: the parentheses say what is rounded
        left = node.left
        while isinstance(left, Binary) and left.op in ARITHMETIC:
            left = left.right
        if isinstance(left, Round):
            return                       # a floor + b floor: each value is rounded on its own
        calc = self.lines[node.line - 1][node.col - 1:last.end - 1]
        fixed = f"({calc})"
        for link in reversed(chain):
            if isinstance(link, As):
                fixed += f" as {link.type}"
            elif link.op == "round":
                fixed += f" round {self.snippet(link.places)}"
            else:
                fixed += f" {link.op}"
        rounding = next(link for link in chain if isinstance(link, Round))
        word, only = rounding.op, self.snippet(rounding)
        self.fail("V301", node, f"{word} here would apply only to {self.snippet(last)}, the value "
                                f"right before it. Put in parentheses what is to be rounded.",
                  fix=self.whole_line(node, fixed) + f"   (or, to round only that value: ({only}))")

    def misplaced_as(self, node):
        """ "N: " + a + 1 as text  ->  as binds to 1 only; the author meant (a + 1) as text."""
        left, right = unwrap(node.left), node.right
        if not (isinstance(right, As) and right.type == TEXT and isinstance(left, Binary)
                and left.op == "+"):
            return
        if (self.type_of(left.left) == TEXT and self.type_of(left.right) == NUMBER
                and self.type_of(right.operand) == NUMBER):
            self.fail("V301", node, "Cannot add text and number: as text applies only to "
                                    f"{self.snippet(right.operand)}.",
                      fix=f"{self.snippet(left.left)} + ({self.snippet(left.right)} + "
                          f"{self.snippet(right.operand)}) as text")

    def as_binds_to_last(self, node, left_type):
        """ 7 / 7 as text is 7 / (7 as text): suggest (7 / 7) as text."""
        right = node.right
        if (left_type == NUMBER and isinstance(right, As) and right.type == TEXT
                and self.type_of(right.operand) == NUMBER):
            return (f"as binds only to {self.snippet(right.operand)}; write "
                    f"({self.snippet(node.left)} {node.op} {self.snippet(right.operand)}) as text")
        return None

    def binary(self, node):
        if node.op == "+":
            self.misplaced_as(node)
        lt = self.type_of(node.left)
        if lt == NUMBER and node.op in ARITHMETIC:
            self.misplaced_round(node)
        rt = self.type_of(node.right)
        op = node.op

        if op in ("+", "-") and lt == NUMBER and isinstance(node.right, DateOp) and node.right.op == "as date":
            days = node.right.operand    # start as days + 30 as date: as date took only the 30
            whole = f"({self.snippet(node.left)} {op} {self.snippet(days)}) as date"
            self.fail("V301", node, f"as date here applies only to {self.snippet(days)}, the value "
                                    f"right before it.", fix=self.whole_line(node, whole))
        if op == "+":
            if lt == rt and lt in (NUMBER, TEXT):
                return lt
            if isinstance(lt, ListT) and lt == rt and not self.one_element(node.right):
                return lt                        # two lists joined into a new one
            fix = None
            if {lt, rt} == {NUMBER, TEXT} and not self.as_binds_to_last(node, lt):
                num, txt = (node.left, node.right) if lt == NUMBER else (node.right, node.left)
                joined = (f"{self.as_operand(num)} as text + {self.snippet(txt)}" if lt == NUMBER
                          else f"{self.snippet(txt)} + {self.as_operand(num)} as text")
                added = (f"{self.snippet(num)} + {self.as_operand(txt)} as number" if lt == NUMBER
                         else f"{self.as_operand(txt)} as number + {self.snippet(num)}")
                lit = unwrap(txt)
                if isinstance(lit, Text) and text_number(lit.value) is None:
                    fix = self.whole_line(node, joined)       # "N: " can never be a number
                else:
                    fix = f"to join text: {joined}; to add numbers: {added}"
            elif self.as_binds_to_last(node, lt):
                fix = self.as_binds_to_last(node, lt)
            elif isinstance(lt, ListT) and lt == rt:
                # xs + [5]: one element is added with add, so that there is one way to do it.
                item = self.snippet(unwrap(node.right).items[0])
                left = self.snippet(node.left)
                line = self.lines[node.line - 1].strip()
                target = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*", line)
                whole = target is not None and line[target.end():] == self.snippet(node)
                if whole and target.group(1) == left:
                    fix = f"{left} add {item}"
                elif whole:
                    fix = f"two lines: {target.group(1)} = {left}   then   {target.group(1)} add {item}"
                else:                    # return xs + [v], f(xs + [v]): the list is built first
                    fix = (f"build the list first: items = {left}   then   items add {item}"
                           f"   then use items in place of {self.snippet(node)}")
                self.fail("V301", node, "+ joins two lists; one element is added with add.", fix=fix)
            elif isinstance(lt, ListT) and isinstance(rt, ListT):
                fix = None                       # lists of different things do not join
            elif isinstance(lt, ListT) and rt == lt.elem:            # xs + 5
                fix = f"use the add statement on its own line: {self.snippet(node.left)} add {self.snippet(node.right)}"
            self.fail("V301", node, f"Cannot add {lt} and {rt}.", fix=fix)

        if op in ("-", "*", "/", "//", "%", "**"):
            if op == "*" and {lt, rt} == {TEXT, NUMBER}:             # "-" * 20
                piece, times = (node.left, node.right) if lt == TEXT else (node.right, node.left)
                self.fail("V301", node, "Text cannot be multiplied in Axion.",
                          fix=f'repeat it in a loop: line = ""   then   for i in 1 to '
                              f"{self.snippet(times)}   then   line = line + {self.snippet(piece)}"
                              f"   then   end")
            if lt != NUMBER or rt != NUMBER:
                fix = self.as_binds_to_last(node, lt) or (
                    "convert text to a number first: value as number" if TEXT in (lt, rt) else None)
                self.fail("V301", node, f"Operator {op} needs numbers, got {lt} and {rt}.", fix=fix)
            right = literal_number(node.right)
            if op == "/" and right is not None and right == 0:
                self.fail("V312", node, "Division by zero.", fix="divide by a number that is not 0")
            if op == "**":
                left = literal_number(node.left)
                if left is not None and right is not None:
                    if left == 0 and right < 0:
                        self.fail("V312", node, "Zero to a negative power is a division by zero.")
                    if left < 0 and not is_whole(right):
                        self.fail("V312", node, "A negative number has no root: its power must "
                                                "be a whole number.")
            if op in ("%", "//"):
                left = literal_number(node.left)
                for value in (left, right):
                    if value is not None and not is_whole(value):
                        self.fail("V312", node, f"{op} works only with whole numbers.",
                                  fix="for a result with a fraction use /" if op == "//" else None)
                if right is not None and right <= 0:
                    self.fail("V312", node, f"The divisor of {op} must be greater than 0.")
            return NUMBER

        if op in EQUALITY:
            if lt != rt:
                fix = None
                if {lt, rt} == {NUMBER, TEXT}:
                    txt = node.left if lt == TEXT else node.right
                    lit = unwrap(txt)
                    # Never suggest a fix that would fail: "abc" as number is itself an error.
                    if not isinstance(lit, Text) or text_number(lit.value) is not None:
                        fix = f"convert the text side: {self.as_operand(txt)} as number"
                self.fail("V308", node, f"Cannot compare {lt} with {rt}.", fix=fix)
            return BOOL

        if op in ORDERING:
            if lt == TEXT and rt == TEXT:
                return BOOL                      # character by character, by character code
            if lt != NUMBER or rt != NUMBER:
                bad = lt if lt != NUMBER else rt
                fix = "use == or != for bool, lists and objects"
                if {lt, rt} == {NUMBER, TEXT}:
                    txt = node.left if lt == TEXT else node.right
                    lit = unwrap(txt)
                    fix = None                   # "abc" can never be a number: nothing to offer
                    if not isinstance(lit, Text) or text_number(lit.value) is not None:
                        fix = self.whole_line(txt, f"{self.as_operand(txt)} as number")
                if {lt, rt} == {NUMBER, TEXT}:
                    self.fail("V308", node, f"{op} compares two numbers or two texts, "
                                            f"got {lt} and {rt}.", fix=fix)
                self.fail("V308", node, f"{op} compares numbers or text; {bad} has no order.",
                          fix=fix)
            return BOOL

        if op in ("and", "or"):
            if lt != BOOL or rt != BOOL:
                self.fail("V301", node, f"{op} needs bool on both sides, got {lt} and {rt}.",
                          fix="compare first, e.g. x > 0")
            return BOOL

        raise TypeError(f"unknown operator {op}")


def validate(program, source, policy=None):
    Validator(source, policy).validate(program)


EMPTY_LIST_LINE = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(\[\s*\]|\{\s*\})\s*(#.*)?$")


def empty_list_fixes(source, errors):
    """`name = []` (P213): give the exact line, with the type taken from the first add.

    The rule stays: an empty list names its element type. But the generic hint
    ("[] of text (or [] of number, ...)") leaves the choice to the author, and models
    repaired such lines one per attempt. Here the program is read once more with every
    bare `name = []` allowed, and the first `name add value` (or `name = other list`) tells
    the type. The other broken lines are replaced by correct ones first. Whenever this does
    not work out (a block mistake, a list nothing is added to) the generic hint stays.
    """
    lines = normalize_source(source).split("\n")
    wanted = {e.line: e for e in errors
              if e.code == "P213" and EMPTY_LIST_LINE.match(lines[e.line - 1])}
    if not wanted:
        return
    broken = {e.line for e in errors} - set(wanted)
    spread = set()                        # the else lines of a value-if written over several lines
    for e in errors:
        if e.message == ONE_LINE_VALUE_IF:
            spread.update((joined_value_if(lines, e.line) or ("", []))[1])
    repaired = "\n".join("" if number in spread else
                         placeholder(text) if number in broken else text
                         for number, text in enumerate(lines, 1))
    try:
        parser = Parser(lex(repaired), repaired)
        parser.loose_empty_list = True
        program = parser.parse()
    except AxionError:
        return
    probe = Validator(repaired)
    try:
        probe.validate(program)
    except AxionError:
        pass                              # its errors belong to the next wave; only types matter
    for line, error in wanted.items():
        if line in probe.empty_lists:
            name, brackets = EMPTY_LIST_LINE.match(lines[line - 1]).group(1, 2)
            error.fix = f"{name} = {brackets[0]}{brackets[-1]} of {probe.empty_lists[line]}"
            error.separate = True
