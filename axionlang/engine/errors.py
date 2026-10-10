"""Axion errors: one class for every stage, one output format.

Format (spec §17):
    ERROR V301 line 2:7
    print 10 + "a"
          ^^^^^^^^
    Cannot add number and text.
    Fix: ...
    The same mistake is on lines 7, 12: fix them too.

The first letter of the code is the stage:
L lexer, P parser, V validator, R runtime, S security.

One pass reports up to MAX_ERRORS different mistakes (AxionErrors). The same mistake on
several lines is one error that names the other lines. Mistakes come in two waves: first the
ones in how the program is written (lexer, parser); only a program without those can be
checked for meaning (validator). A runtime error is always a single one.
"""

MAX_ERRORS = 5


class AxionError(Exception):
    def __init__(self, code, line, col, message, fix=None, length=1, affected=None):
        super().__init__(message)
        self.code = code
        self.line = line
        self.col = col
        self.message = message
        self.fix = fix
        self.length = max(1, length)
        self.affected = affected or []

    @property
    def stage(self):
        return {"L": "LEXER", "P": "PARSER", "V": "VALIDATION",
                "R": "RUNTIME", "S": "SECURITY"}[self.code[0]]

    def format(self, source):
        """Return the error as a list of output lines."""
        lines = source.split("\n")
        out = [f"ERROR {self.code} line {self.line}:{self.col}"]
        if 1 <= self.line <= len(lines) and lines[self.line - 1].strip():
            text = lines[self.line - 1]
            out.append(text)
            out.append(" " * (self.col - 1) + "^" * self.length)
        out.append(self.message)
        if self.fix:
            out.append(f"Fix: {self.fix}")
        if self.affected:
            out.append(also_on(sorted(set(self.affected))))
        return out


def also_on(lines):
    """The line that tells a model to repair every copy of a mistake in the same attempt."""
    nums = ", ".join(str(n) for n in lines)
    if len(lines) == 1:
        return f"The same mistake is on line {nums}: fix it too."
    return f"The same mistake is on lines {nums}: fix them too."


def merge(errors):
    """Identical mistakes become one error that names the other lines; the result is in line order."""
    groups = {}
    for e in sorted(errors, key=lambda e: (e.line, e.col)):
        own = e.line if getattr(e, "separate", False) else None    # keeps its own Fix
        first = groups.setdefault((e.code, e.message, own), e)
        if first is not e:
            first.affected = sorted((set(first.affected) | set(e.affected) | {e.line}) - {first.line})
    return list(groups.values())


class AxionErrors(AxionError):
    """Several errors found in one pass. Behaves like its first error (code, line, message)."""

    def __init__(self, errors):
        self.errors = merge(errors)
        first = self.errors[0]
        super().__init__(first.code, first.line, first.col, first.message, fix=first.fix,
                         length=first.length, affected=first.affected)

    def format(self, source):
        out = []
        for i, error in enumerate(self.errors[:MAX_ERRORS]):
            if i:
                out.append("")
            out.extend(error.format(source))
        hidden = len(self.errors) - MAX_ERRORS
        if hidden > 0:
            out += ["", f"({hidden} more error{'s' if hidden > 1 else ''} not shown: fix these first.)"]
        return out
