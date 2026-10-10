"""Interpreter: runs a validated AST (spec §3-§12).

Only data-dependent errors can happen here (RUNTIME).
Output is collected line by line so that a runtime error keeps
everything printed before it.
"""

import datetime
import sys
import threading
from decimal import (ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal, InvalidOperation,
                     Overflow)

from .errors import AxionError
from .lexer import normalize_source

from pathlib import Path

from .parser import Affix, Contains, Split, TextOp
from .parser import EmptyMap, Keys, MapLit
from .parser import DateOp, Round
from .parser import Continue, Exists, Exit, While
from .parser import (Aggregate, Allow, As, Assign, Binary, Bool, Break, Call, Conditional, Join, Sort, CallStatement, EmptyList, Field,
                    For, Function, Group, If, Index, Input, IsNumber, Length, ListAdd, ListLit,
                    ListRemove, Name, Not, Number, ObjectLit, Print, Range, Read, Return,
                    SetField, SetItem, Text, Unary)
from .policy import Policy, normalize_folder, unsafe_path
from .values import (CTX, CTX_WIDE, NUMBER_TEXT, MapValue, copy_value, fits, format_number,
                     format_value, parse_date, quote_text, size_of, text_number)




class ReturnSignal(Exception):
    """Carries a return value out of a function body (not an error)."""

    def __init__(self, value):
        super().__init__()
        self.value = value


class BreakSignal(Exception):
    """Carries a break out to the nearest loop (not an error)."""


class ContinueSignal(Exception):
    """Carries a continue out to the nearest loop, which goes on with its next pass."""


class ExitSignal(Exception):
    """Carries an exit out of the main program: a normal end."""


TOO_LARGE = "A number became too large here: a number keeps 28 digits and cannot grow without end."
OUT_OF_MEMORY = ("Python ran out of memory here: the program needs more memory than this computer "
                 "gives it.")


def is_whole(d):
    return d == d.to_integral_value()


FRAMES_PER_CALL = 60        # Python frames one Axion call may need (measured: 7 to 25)


def with_room(work, depth):
    """Run work() with enough stack for `depth` Axion calls inside one another.

    The interpreter walks the program by Python recursion, so a deep Axion recursion needs a
    deep Python stack: a thread of its own with a large stack, and a matching recursion limit.
    """
    frames = depth * FRAMES_PER_CALL + 2000
    result = {}

    def target():
        try:
            result["value"] = work()
        except BaseException as exc:      # handed over to the caller's thread
            result["error"] = exc

    old_limit = sys.getrecursionlimit()
    try:
        old_size = threading.stack_size(min(512, 16 + frames // 1000) * 1024 * 1024)
    except (ValueError, RuntimeError):    # this system cannot set the size: stay within the
        old_size, frames = None, 8000     # stack every thread has
    sys.setrecursionlimit(max(old_limit, frames))
    try:
        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        thread.join()
    finally:
        sys.setrecursionlimit(old_limit)
        if old_size is not None:
            threading.stack_size(old_size)
    if "error" in result:
        raise result["error"]
    return result["value"]


class Interpreter:
    def __init__(self, source, policy=None, base_dir=None, inputs=None):
        self.lines = normalize_source(source).split("\n")
        self.scopes = [dict(inputs or {})]   # input values are ready before line 1 (spec §14)
        self.output = []
        self.functions = {}
        self.policy = policy or Policy()
        self.limits = self.policy.limits
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()
        self.allowed = []             # folders declared with allow read
        self.steps = 0
        self.kept = 0                 # bytes of data stored so far (size_of), never decreases
        self.output_chars = 0
        self.depth = 0                # function calls inside one another right now

    # --- resource limits (spec §15), set by the launch policy ---
    def tick(self, node):
        self.steps += 1
        if self.steps > self.limits["max_steps"]:
            self.fail("R406", node, f"The program ran more than {self.limits['max_steps']} steps "
                                    f"(the limit of the launch policy).")

    def check_size(self, node, size, what="list", units="elements"):
        if size > self.limits["max_list_size"]:
            self.fail("R406", node, f"A {what} would have {size} {units}; the limit of the launch "
                                    f"policy is {self.limits['max_list_size']}.")

    def check_text(self, node, size):
        """A text is bounded like a list (the same limit): s = s + s cannot eat the memory."""
        self.check_size(node, size, "text", "characters")

    def keep(self, node, value):
        """A copy of a value put into a list or a dictionary, counted against max_memory_mb.

        Only data that enters a container is counted: an element added to a list, a value set at
        an index, a field, a dictionary entry, and the copies made inside list, object and
        dictionary values, pieces and sorts. One text or one list is bounded on its own
        (max_list_size), but many of them held together are not, so 20,000 large texts in a list
        or a thousand copies of a large list stop the program here instead of using up the memory.

        A plain variable is not counted: it holds one value at a time, bounded by max_list_size,
        and the number of names and of stacked calls (max_depth) is bounded too. So a loop that
        rebuilds a text or a number in a variable is free; only growing containers are measured.
        """
        self.kept += size_of(value)
        limit = self.limits["max_memory_mb"]
        if self.kept > limit * 1024 * 1024:
            self.fail("R406", node, f"The program kept more than {limit} MB of data "
                                    f"(the limit of the launch policy).")
        return copy_value(value)

    # --- helpers ---
    def snippet(self, node):
        return self.lines[node.line - 1][node.col - 1:node.end - 1]

    def fail(self, code, node, message, fix=None):
        raise AxionError(code, node.line, node.col, message, fix=fix,
                         length=max(1, node.end - node.col))

    # --- variables and blocks ---
    def assign(self, name, value):
        for scope in reversed(self.scopes):
            if name in scope:
                scope[name] = value       # existing name: modify it
                return
        self.scopes[-1][name] = value     # new name: lives in the current block

    def lookup(self, name):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        raise KeyError(name)              # impossible after validation

    def run_block(self, body, variables=None):
        self.scopes.append(dict(variables or {}))
        try:
            for statement in body:
                self.execute(statement)
        finally:
            self.scopes.pop()

    # --- statements ---
    def run(self, program):
        self.functions = {st.name: st for st in program.statements if isinstance(st, Function)}
        try:
            for statement in program.statements:
                self.execute(statement)
        except ExitSignal:
            pass                          # exit: the program is over, and that is not an error

    def call(self, node):
        fn = self.functions[node.name]
        args = [copy_value(self.evaluate(a)) for a in node.args]
        if self.depth >= self.limits["max_depth"]:
            self.fail("R406", node, f"Function calls went more than {self.limits['max_depth']} "
                                    f"deep (the limit of the launch policy).",
                      fix=f"check the case that stops {fn.name}: with these values it is not reached")
        saved = self.scopes
        # The function sees only its parameters (spec §13).
        self.scopes = [{p.name: v for p, v in zip(fn.params, args)}]
        self.depth += 1
        try:
            for statement in fn.body:
                self.execute(statement)
        except ReturnSignal as signal:
            return signal.value
        except RecursionError:            # the last line of defence; the depth limit comes first
            self.fail("R406", node, "Function calls went deeper than the interpreter can follow.",
                      fix=f"check the case that stops {fn.name}")
        finally:
            self.scopes = saved
            self.depth -= 1
        return None

    def execute(self, node):
        try:
            self.execute_one(node)
        except (Overflow, InvalidOperation):          # the last line of defence; number() comes first
            self.fail("R412", node, TOO_LARGE)
        except MemoryError:                           # the last line of defence; keep() comes first
            self.fail("R406", node, OUT_OF_MEMORY)

    def number(self, node, value):
        """The result of a calculation, or R412 when it has more than 28 digits before the point."""
        if not fits(value):
            self.fail("R412", node, TOO_LARGE)
        return value

    def execute_one(self, node):
        self.tick(node)
        if isinstance(node, Assign):
            self.assign(node.name, copy_value(self.evaluate(node.value)))
        elif isinstance(node, Print):
            text = format_value(self.evaluate(node.value))
            self.output_chars += len(text) + 1
            if self.output_chars > self.limits["max_output_chars"]:
                self.fail("R406", node, f"The program printed more than "
                                        f"{self.limits['max_output_chars']} characters "
                                        f"(the limit of the launch policy).")
            self.output.extend(text.split("\n"))
        elif isinstance(node, If):
            for branch in node.branches:
                if self.evaluate(branch.condition):
                    self.run_block(branch.body)
                    return
            if node.else_branch is not None:
                self.run_block(node.else_branch.body)
        elif isinstance(node, For):
            items = self.evaluate(node.iterable)
            for item in items:
                # Each pass starts with a clean block that holds only the loop variable.
                self.tick(node)
                try:
                    self.run_block(node.body, {node.var: item})
                except BreakSignal:
                    break
                except ContinueSignal:
                    continue
        elif isinstance(node, While):
            while self.evaluate(node.condition):
                self.tick(node)           # every pass is a step: the step limit ends a loop
                try:                      # that never stops
                    self.run_block(node.body)
                except BreakSignal:
                    break
                except ContinueSignal:
                    continue
        elif isinstance(node, SetItem):
            container = self.container(node.target.target)
            if isinstance(container, MapValue):               # d[k] = v: a new key or a new value
                key = self.evaluate(node.target.index)
                if key not in container:
                    self.check_size(node, len(container) + 1)
                    self.keep(node, key)                       # a new key is kept too
                container[key] = self.keep(node, self.evaluate(node.value))
                return
            i = self.check_index(node.target, container, self.evaluate(node.target.index))
            container[i] = self.keep(node, self.evaluate(node.value))
        elif isinstance(node, SetField):
            self.container(node.target.target)[node.target.name] = self.keep(node, self.evaluate(node.value))
        elif isinstance(node, ListAdd):
            items = self.container(node.target)
            self.check_size(node, len(items) + 1)
            items.append(self.keep(node, self.evaluate(node.value)))
        elif isinstance(node, ListRemove):
            self.list_remove(node)
        elif isinstance(node, (Function, Input)):
            pass                          # definitions and inputs do nothing when reached
        elif isinstance(node, Allow):
            self.allowed.append(normalize_folder(node.folder))
        elif isinstance(node, Return):
            raise ReturnSignal(copy_value(self.evaluate(node.value)))
        elif isinstance(node, CallStatement):
            self.call(node.call)
        elif isinstance(node, Break):
            raise BreakSignal()
        elif isinstance(node, Continue):
            raise ContinueSignal()
        elif isinstance(node, Exit):
            raise ExitSignal()
        else:
            raise TypeError(f"unknown statement {type(node).__name__}")

    def container(self, node):
        """The actual list a target refers to (not a copy), so it can be changed."""
        if isinstance(node, Group):
            return self.container(node.inner)
        if isinstance(node, Name):
            return self.lookup(node.name)
        if isinstance(node, Index):
            outer = self.container(node.target)
            if isinstance(outer, MapValue):
                return outer[self.check_key(node, outer, self.evaluate(node.index))]
            return outer[self.check_index(node, outer, self.evaluate(node.index))]
        if isinstance(node, Field):
            return self.container(node.target)[node.name]
        raise TypeError(f"not a target: {type(node).__name__}")

    def check_key(self, node, entries, key):
        """d[k] when k is not in d: the program stops (there is no silent 'nothing')."""
        if key not in entries:
            d, k = self.snippet(node.target), self.snippet(node.index)
            self.fail("R411", node, f"There is no key {quote_text(key)} in {d}.",
                      fix=f"check first: if {d} contains {k}")
        return key

    def check_index(self, node, items, index):
        name = self.snippet(node.target)
        if not is_whole(index):
            self.fail("R402", node, f"An index must be a whole number: "
                                    f"{self.snippet(node.index)} is {format_number(index)}.")
        n = len(items)
        if index < 0 or index >= n:
            valid = f"valid: 0 to {n - 1}" if n else "it is empty"
            what = "characters" if isinstance(items, str) else "elements"
            self.fail("R403", node, f"Index {format_number(index)} is out of range: "
                                    f"{name} has {n} {what} ({valid}).")
        return int(index)

    def piece(self, node, items, bounds):
        """s[a to b] / xs[a to b]: both ends included. b = a - 1 gives an empty piece."""
        a, b = self.evaluate(bounds.start), self.evaluate(bounds.stop)
        for side, value in ((bounds.start, a), (bounds.stop, b)):
            if not is_whole(value):
                self.fail("R402", side, f"A position must be a whole number: "
                                        f"{self.snippet(side)} is {format_number(value)}.")
        a, b, n = int(a), int(b), len(items)
        if b < a:
            return "" if isinstance(items, str) else []
        if a < 0 or b >= n:
            valid = f"valid: 0 to {n - 1}" if n else "it is empty"
            what = "characters" if isinstance(items, str) else "elements"
            self.fail("R403", node, f"The piece {a} to {b} is out of range: "
                                    f"{self.snippet(node.target)} has {n} {what} ({valid}).",
                      fix=(f"check first: if {self.snippet(bounds.start)} >= 0" if a < 0 else
                           f"check first: if {self.snippet(node.target)} length > "
                           f"{self.snippet(bounds.stop)}"))
        if isinstance(items, str):
            return items[a:b + 1]
        return [self.keep(node, v) for v in items[a:b + 1]]

    def list_remove(self, node):
        items = self.container(node.target)
        value = self.evaluate(node.value)
        if node.mode == "key":
            if value not in items:
                d, k = self.snippet(node.target), self.snippet(node.value)
                self.fail("R411", node, f"There is no key {quote_text(value)} in {d}.",
                          fix=f"check first: if {d} contains {k}")
            del items[value]
            return
        if node.mode == "index":
            fake = Index(node.target, node.value, node.line, node.col, node.end)
            del items[self.check_index(fake, items, value)]
            return
        matches = [i for i, x in enumerate(items) if x == value]
        if len(matches) != 1:
            xs, v = self.snippet(node.target), self.snippet(node.value)
            fix = (f"check first: if {xs} contains {v}" if not matches
                   else "use remove index to choose one")
            self.fail("R405", node, f"remove value needs exactly one match, found {len(matches)}.",
                      fix=fix)
        del items[matches[0]]

    # --- expressions ---
    def evaluate(self, node):
        if isinstance(node, (Number, Text, Bool)):
            return node.value
        if isinstance(node, Group):
            return self.evaluate(node.inner)
        if isinstance(node, Name):
            return self.lookup(node.name)
        if isinstance(node, Unary):
            return CTX.minus(self.evaluate(node.operand))
        if isinstance(node, Not):
            return not self.evaluate(node.operand)
        if isinstance(node, ListLit):
            self.check_size(node, len(node.items))
            return [self.keep(node, self.evaluate(item)) for item in node.items]
        if isinstance(node, EmptyList):
            return []
        if isinstance(node, EmptyMap):
            return MapValue()
        if isinstance(node, MapLit):
            self.check_size(node, len(node.pairs))
            return MapValue((key, self.keep(node, self.evaluate(value)))
                            for key, _line, _col, value in node.pairs)
        if isinstance(node, Keys):
            return list(self.evaluate(node.target))
        if isinstance(node, Index):
            items = self.evaluate(node.target)
            index = node.index
            while isinstance(index, Group):
                index = index.inner
            if isinstance(items, MapValue):                    # d[k]
                return items[self.check_key(node, items, self.evaluate(node.index))]
            if isinstance(index, Range):                       # s[0 to 4], xs[0 to 2]
                return self.piece(node, items, index)
            return items[self.check_index(node, items, self.evaluate(node.index))]
        if isinstance(node, TextOp):
            text = self.evaluate(node.target)
            return {"lower": text.lower, "upper": text.upper, "trim": text.strip}[node.op]()
        if isinstance(node, Round):
            return self.round(node)
        if isinstance(node, DateOp):
            return self.date(node)
        if isinstance(node, Split):
            separator = self.evaluate(node.separator)
            if separator == "":
                self.fail("R410", node.separator, f"The separator of split cannot be empty: "
                                                  f"{self.snippet(node.separator)} is \"\".",
                          fix=f"check first: if {self.snippet(node.separator)} != \"\"")
            parts = self.evaluate(node.target).split(separator)
            self.check_size(node, len(parts))
            return parts
        if isinstance(node, Contains):
            return self.evaluate(node.item) in self.evaluate(node.target)
        if isinstance(node, Affix):
            text, part = self.evaluate(node.target), self.evaluate(node.part)
            return text.startswith(part) if node.op == "starts" else text.endswith(part)
        if isinstance(node, Length):
            return Decimal(len(self.evaluate(node.target)))
        if isinstance(node, Range):
            return self.range_value(node)
        if isinstance(node, ObjectLit):
            return {name: self.keep(node, self.evaluate(value)) for name, value in node.fields}
        if isinstance(node, Field):
            return self.evaluate(node.target)[node.name]
        if isinstance(node, Call):
            return self.call(node)
        if isinstance(node, Read):
            return self.read(node)
        if isinstance(node, Exists):
            try:
                return self.file_of(node).is_file()
            except (OSError, ValueError):     # a name no file can have: then there is no such file
                return False
        if isinstance(node, IsNumber):
            return text_number(self.evaluate(node.operand)) is not None
        if isinstance(node, As):
            return self.convert(node)
        if isinstance(node, Sort):
            items = self.evaluate(node.target)
            # sorted() is stable in both directions: equal elements keep their order. So a
            # sort by several fields is done from the last field to the first.
            for field, descending in reversed([(node.field, node.descending), *node.more]):
                key = (lambda v, f=field: v[f]) if field is not None else None
                items = sorted(items, key=key, reverse=descending)
            return [self.keep(node, v) for v in items]
        if isinstance(node, Aggregate):
            return self.aggregate(node)
        if isinstance(node, Join):
            separator, parts = self.evaluate(node.separator), self.evaluate(node.target)
            self.check_text(node, sum(len(part) for part in parts) + len(separator) * max(0, len(parts) - 1))
            return separator.join(parts)
        if isinstance(node, Conditional):       # only the chosen value is computed
            return self.evaluate(node.then if self.evaluate(node.cond) else node.otherwise)
        if isinstance(node, Binary):
            return self.binary(node)
        raise TypeError(f"unknown expression {type(node).__name__}")

    def aggregate(self, node):
        items = self.evaluate(node.target)
        if node.op == "sum":
            total = Decimal(0)
            for v in items:
                total = self.number(node, CTX.add(total, v))
            return total
        if not items:
            name = self.snippet(node.target)
            self.fail("R409", node, f"{node.op} needs at least one element: {name} is empty.",
                      fix=f"check first: if {name} length > 0")
        return min(items) if node.op == "min" else max(items)

    def file_of(self, node):
        """The file that read or exists names, after the same permission checks for both."""
        path = self.evaluate(node.path)
        if unsafe_path(path) or not any(path.startswith(f) for f in self.allowed):
            declared = ", ".join(f'"{f}"' for f in self.allowed)
            self.fail("S503", node, f'"{path}" is outside the declared folders ({declared}).')
        target = self.base_dir / path
        # A symlink inside an allowed folder must not lead outside of it.
        real = target.resolve()
        inside = any(real.is_relative_to((self.base_dir / f).resolve()) for f in self.allowed)
        if not inside:
            self.fail("S503", node, f'"{path}" points outside the declared folders.')
        return target

    def read(self, node):
        path = self.evaluate(node.path)
        try:
            target = self.file_of(node)
            self.check_text(node, target.stat().st_size if target.is_file() else 0)
            return target.read_text(encoding="utf-8")
        except FileNotFoundError:
            fix = None
            if isinstance(node.path, Binary):
                fix = (f"read took all of {self.snippet(node.path)} as the path; to use the "
                       f"text of a file inside a longer expression, write (read path)")
            self.fail("R408", node, f'File "{path}" does not exist.', fix=fix)
        except (IsADirectoryError, PermissionError, UnicodeDecodeError, OSError, ValueError) as exc:
            self.fail("R408", node, f'File "{path}" cannot be read: {type(exc).__name__}.')

    def convert(self, node):
        value = self.evaluate(node.operand)
        if node.type == "text":
            return format_value(value) if not isinstance(value, str) else value
        # text as number
        number = text_number(value)
        if number is None:
            why = ": a number keeps 28 digits" if NUMBER_TEXT.fullmatch(value) else ""
            self.fail("R404", node, f'"{value}" cannot be converted to number{why}.',
                      fix=f"check first: if {self.snippet(node.operand)} is number")
        return number

    def round(self, node):
        """x round n: the school rule, a five goes away from zero. floor and ceiling give a
        whole number, down and up."""
        value = self.evaluate(node.target)
        if node.op != "round":
            mode = ROUND_FLOOR if node.op == "floor" else ROUND_CEILING
            return self.number(node, value.to_integral_value(rounding=mode))
        places = self.evaluate(node.places)
        if not is_whole(places) or places < 0:
            self.fail("R402", node.places, f"The number of places is a whole number, 0 or greater: "
                                           f"{self.snippet(node.places)} is {format_number(places)}.")
        if places > 28:
            return value                              # a number keeps 28 digits: nothing to cut
        return self.number(node, value.quantize(Decimal(1).scaleb(-int(places)), rounding=ROUND_HALF_UP,
                                                context=CTX_WIDE))

    def date(self, node):
        value = self.evaluate(node.operand)
        if node.op == "is date":
            return parse_date(value) is not None
        if node.op == "as days":
            days = parse_date(value)
            if days is None:
                self.fail("R413", node, f'"{value}" is not a date (year-month-day, like 2026-10-05).',
                          fix=f"check first: if {self.snippet(node.operand)} is date")
            return Decimal(days)
        if not is_whole(value):
            self.fail("R413", node, f"A date is a whole number of days: "
                                    f"{self.snippet(node.operand)} is {format_number(value)}.")
        try:
            return (datetime.date(1970, 1, 1) + datetime.timedelta(days=int(value))).isoformat()
        except (OverflowError, ValueError):
            self.fail("R413", node, f"{format_number(value)} days is outside the calendar "
                                    f"(years 0001 to 9999).")

    def power(self, node, base, exponent):
        """x ** n. A whole power is exact; a root is rounded to 28 digits."""
        if base == 0 and exponent < 0:
            self.fail("R401", node, f"Zero to a negative power is a division by zero: "
                                    f"{self.snippet(node.left)} is 0.")
        if base < 0 and not is_whole(exponent):
            self.fail("R412", node, f"A negative number has no root: {self.snippet(node.left)} is "
                                    f"{format_number(base)} and the power is {format_number(exponent)}.",
                      fix=f"check first: if {self.snippet(node.left)} >= 0")
        if base == 0 and exponent == 0:
            return Decimal(1)                         # the usual convention: x ** 0 is 1
        try:
            result = CTX.power(base, exponent)
        except (Overflow, InvalidOperation):
            result = None
        if result is None or not fits(result):        # 2 ** 100 would lose its last digits
            self.fail("R412", node, "The result of ** is too large for a number.")
        # 16 ** 0.5 comes out as 4.000...0 and 2 ** 0.5 with 28 digits: both print cleanly
        return result

    def range_value(self, node):
        a = self.evaluate(node.start)
        b = self.evaluate(node.stop)
        for side, value in ((node.start, a), (node.stop, b)):
            if not is_whole(value):
                self.fail("R402", side, f"Range bounds must be whole numbers: "
                                        f"{self.snippet(side)} is {format_number(value)}.")
        # b < a gives an empty list (a computed empty range, spec §8).
        self.check_size(node, max(0, int(b) - int(a) + 1))
        return [Decimal(i) for i in range(int(a), int(b) + 1)]

    def binary(self, node):
        op = node.op

        # and / or: the right side runs only if it can change the result.
        if op == "and":
            return self.evaluate(node.left) and self.evaluate(node.right)
        if op == "or":
            return self.evaluate(node.left) or self.evaluate(node.right)

        left = self.evaluate(node.left)
        right = self.evaluate(node.right)

        if op == "+":
            if isinstance(left, list):               # two lists joined into a new one
                self.check_size(node, len(left) + len(right))
                return left + right
            if isinstance(left, str):
                self.check_text(node, len(left) + len(right))
                return left + right
            return self.number(node, CTX.add(left, right))
        if op == "-":
            return self.number(node, CTX.subtract(left, right))
        if op == "*":
            return self.number(node, CTX.multiply(left, right))
        if op == "**":
            return self.power(node, left, right)
        if op == "/":
            if right.is_zero():
                self.fail("R401", node, f"Division by zero: {self.snippet(node.right)} is 0.")
            return self.number(node, CTX.divide(left, right))
        if op in ("%", "//"):
            for side, value in ((node.left, left), (node.right, right)):
                if not is_whole(value):
                    self.fail("R402", node, f"{op} works only with whole numbers: "
                                            f"{self.snippet(side)} is {format_number(value)}.",
                              fix="for a result with a fraction use /" if op == "//" else None)
            if right <= 0:
                self.fail("R402", node, f"The divisor of {op} must be greater than 0: "
                                        f"{self.snippet(node.right)} is {format_number(right)}.")
            result = CTX.remainder(left, right)
            remainder = CTX.add(result, right) if result < 0 else result
            if op == "%":
                return remainder
            # a == (a // b) * b + a % b, with a % b never negative: -7 // 2 is -4
            return CTX.divide(CTX.subtract(left, remainder), right)
        if op == "==":
            return left == right
        if op == "!=":
            return left != right
        if op == "<":
            return left < right
        if op == ">":
            return left > right
        if op == "<=":
            return left <= right
        if op == ">=":
            return left >= right
        raise TypeError(f"unknown operator {op}")
