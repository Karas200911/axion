"""Lexer: source text -> tokens with positions (spec §1, §3, §4).

Token kinds: NUMBER, TEXT, NAME, KEYWORD, OP, NEWLINE, EOF.
Every token knows its line, start column and end column (exclusive).
"""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from .errors import AxionError
from .values import fits, format_number

KEYWORDS = {
    "if", "else", "end", "for", "in", "function", "return",
    "true", "false", "and", "or", "not",
    "number", "text", "bool", "list", "of", "as", "is",
    "length", "add", "remove", "index", "value", "to",
    "print", "input", "allow", "read", "break",
    "while", "continue", "exit",
}

TWO_CHAR = ("==", "!=", "<=", ">=", "->", "//", "**")
ONE_CHAR = set("=+-*/%<>()[]{},:.")
OPENERS = {"(": ")", "[": "]", "{": "}"}
CLOSERS = {")": "(", "]": "[", "}": "{"}
DIGITS = "0123456789"


@dataclass
class Token:
    kind: str
    value: object
    line: int
    col: int
    end: int


def normalize_source(source):
    return source.replace("\r\n", "\n").replace("\r", "\n")


TERNARY = re.compile(r"^(\s*(?:[A-Za-z_][A-Za-z0-9_.\[\]]*\s*=|print|return)\s*)"
                     r"(.+?)\s*\?\s*(.+?)\s*:\s*(.+?)\s*$")


def line_with(src, i, replacement):
    """The line of position i with the one character at i replaced."""
    start = src.rfind("\n", 0, i) + 1
    end = src.find("\n", i)
    end = len(src) if end == -1 else end
    return (src[start:i] + replacement + src[i + 1:end]).strip()


def ternary_fix(src, i):
    """x = c ? a : b  ->  x = if c then a else b (the whole line when its shape is that simple)."""
    start = src.rfind("\n", 0, i) + 1
    end = src.find("\n", i)
    text = src[start:end if end != -1 else len(src)]
    match = TERNARY.match(text)
    if match is None or "?" in match.group(3) + match.group(4):
        return "write: if condition then a else b"
    head, cond, yes, no = match.groups()
    return f"{head.strip()} if {cond} then {yes} else {no}"


def lex(source):
    src = normalize_source(source)
    n = len(src)
    tokens = []
    stack = []          # open brackets: (char, line, col)
    i, line, col = 0, 1, 1
    def fail(code, message, l, c, length=1, fix=None):
        raise AxionError(code, l, c, message, fix=fix, length=length)

    def add(kind, value, length):
        tokens.append(Token(kind, value, line, col, col + length))

    while i < n:
        ch = src[i]

        if ch == "\n":
            if stack and stack[-1][0] == "(":
                fail("P204", "Line break inside ( ) is not allowed.", line, col,
                     fix="keep the expression on one line, or split it into variables")
            if not stack and tokens and tokens[-1].kind != "NEWLINE":
                add("NEWLINE", None, 1)
            i += 1
            line += 1
            col = 1
            continue

        if ch in " \t":                 # spaces and tabs have no meaning, at the line start too
            i += 1
            col += 1
            continue

        if ch == "#":
            while i < n and src[i] != "\n":
                i += 1
                col += 1
            continue

        # ".5"
        if ch == "." and i + 1 < n and src[i + 1] in DIGITS and not (
                tokens and (tokens[-1].kind in ("NAME", "NUMBER", "TEXT")
                            or tokens[-1].value in (")", "]", "}"))):
            j = i + 1
            while j < n and src[j] in DIGITS:
                j += 1
            text = src[i:j]
            fail("L104", f"Invalid number {text}.", line, col, length=j - i,
                 fix=f"write 0{text}")

        if ch in DIGITS:
            j = i
            while j < n and src[j] in DIGITS:
                j += 1
            if j < n and src[j] == ".":
                if j + 1 < n and src[j + 1] in DIGITS:
                    j += 1
                    while j < n and src[j] in DIGITS:
                        j += 1
                else:
                    text = src[i:j + 1]
                    fail("L104", f"Invalid number {text}.", line, col, length=len(text),
                         fix=f"write {src[i:j]}")
            if j < n and (src[j].isalpha() or src[j] in "_."):
                k = j
                while k < n and (src[k].isalnum() or src[k] in "_."):
                    k += 1
                text = src[i:k]
                fix = "use digits with an optional .fraction, e.g. 1000 or 2.5"
                try:
                    d = Decimal(text.replace("_", ""))
                    if d.is_finite() and fits(d):
                        fix = f"write {format_number(d)}"
                except InvalidOperation:
                    pass
                fail("L104", f"Invalid number {text}.", line, col, length=k - i, fix=fix)
            text = src[i:j]
            whole, _, frac = text.partition(".")
            canonical = format_number(Decimal(text))
            if len(whole) > 1 and whole[0] == "0":
                fail("L104", f"Invalid number {text}: a number cannot start with 0.",
                     line, col, length=j - i, fix=f"write {canonical}")
            if frac and frac.endswith("0"):
                fail("L104", f"Invalid number {text}: no trailing zeros after the point.",
                     line, col, length=j - i, fix=f"write {canonical}")
            if not fits(Decimal(text)):
                fail("L104", f"Invalid number {text}: a number keeps 28 digits.", line, col, length=j - i)
            add("NUMBER", Decimal(text), j - i)
            col += j - i
            i = j
            continue

        if ch == '"':
            j = i + 1
            buf = []
            while True:
                if j >= n or src[j] == "\n":
                    fail("L102", "Text is not closed.", line, col, length=j - i,
                         fix='close it with " on the same line; use \\n for a line break')
                c = src[j]
                if c == '"':
                    break
                if c == "\\":
                    nxt = src[j + 1] if j + 1 < n else ""
                    if nxt == '"':
                        buf.append('"')
                    elif nxt == "\\":
                        buf.append("\\")
                    elif nxt == "n":
                        buf.append("\n")
                    else:
                        shown = "\\" + nxt if nxt not in ("", "\n") else "\\"
                        fail("L103", f"Unknown escape {shown} in text.", line, col + (j - i),
                             length=2, fix='only \\" \\\\ \\n are allowed; for a backslash write \\\\')
                    j += 2
                    continue
                buf.append(c)
                j += 1
            length = j - i + 1
            add("TEXT", "".join(buf), length)
            col += length
            i = j + 1
            continue

        if ch == "'":
            j = src.find("'", i + 1)
            eol = src.find("\n", i + 1)
            if j != -1 and (eol == -1 or j < eol):
                fix = f'write "{src[i + 1:j]}"'
                length = j - i + 1
            else:
                fix = 'use double quotes: "..."'
                length = 1
            fail("L106", "Text must use double quotes.", line, col, length=length, fix=fix)

        if ch.isalpha() or ch == "_":
            j = i
            while j < n and (src[j].isalnum() or src[j] == "_"):
                j += 1
            word = src[i:j]
            add("KEYWORD" if word in KEYWORDS else "NAME", word, j - i)
            col += j - i
            i = j
            continue

        two = src[i:i + 2]
        if two in TWO_CHAR:
            add("OP", two, 2)
            col += 2
            i += 2
            continue

        if ch in ONE_CHAR:
            if ch in OPENERS:
                stack.append((ch, line, col))
            elif ch in CLOSERS:
                if not stack or stack[-1][0] != CLOSERS[ch]:
                    fail("P203", f"Unexpected {ch}: there is no matching opening bracket.",
                         line, col, fix=f"remove {ch} or add {CLOSERS[ch]} before it")
                stack.pop()
            add("OP", ch, 1)
            col += 1
            i += 1
            continue

        if ch == ";":
            fail("L101", "Axion has no ;.", line, col,
                 fix="put each statement on its own line")
        if src[i:i + 2] in ("&&", "||") or ch in "&|":
            word = "and" if ch == "&" else "or"
            length = 2 if src[i:i + 2] in ("&&", "||") else 1
            fail("L101", f"{src[i:i + length]} is not Axion syntax.", line, col, length=length,
                 fix=f"write {word}")
        if ch == "^":
            fail("L101", "A power is written ** in Axion.", line, col,
                 fix=line_with(src, i, "**"))
        if ch == "?":
            fail("L101", "Axion has no ? : operator.", line, col, fix=ternary_fix(src, i))
        if ch == "!":
            fail("L101", "Unknown character !.", line, col,
                 fix="use != for not equal, and not for negation")
        fail("L101", f"Unknown character {ch}.", line, col)

    if stack:
        ch, l, c = stack[-1]
        raise AxionError("P203", l, c, f"{ch} is never closed.", fix=f"add {OPENERS[ch]}")

    if tokens and tokens[-1].kind != "NEWLINE":
        add("NEWLINE", None, 1)
    tokens.append(Token("EOF", None, line, col, col + 1))
    return tokens
