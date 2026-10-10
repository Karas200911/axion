"""Value rules shared by every stage (spec §3, §12/§16 print).

Runtime representation:
    number -> Decimal, text -> str, bool -> bool,
    list -> Python list, object -> Python dict (field -> value),
    dictionary -> MapValue (text key -> value, in the order the keys were added).
"""

import datetime
import re
import sys
from decimal import Context, Decimal, ROUND_HALF_EVEN

# number = decimal arithmetic with 28 significant digits.
CTX = Context(prec=28, rounding=ROUND_HALF_EVEN)
# Text that `as number` accepts (spec §10).
NUMBER_TEXT = re.compile(r"-?[0-9]+(\.[0-9]+)?")
# Room for `round`: a 28-digit number cut to some places may need more digits on the way.
CTX_WIDE = Context(prec=80)


class MapValue(dict):
    """A dictionary value. A class of its own so that it never passes for an object:
    an object prints as {name: "A"}, a dictionary as {"name": "A"}."""


def parse_date(text):
    """The number of days from 1970-01-01 for "2026-10-05", or None if it is not a date.

    One format: four digits, two, two, with dashes; and the day must exist in the calendar.
    """
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", text):
        return None
    try:
        day = datetime.date(int(text[0:4]), int(text[5:7]), int(text[8:10]))
    except ValueError:
        return None
    return (day - datetime.date(1970, 1, 1)).days


def fits(d: Decimal) -> bool:
    """A number has at most 28 digits before the point. A larger one would lose its last
    digits without a word, so it does not exist: not as a literal, not in the input data, not
    as a result. Digits after the point beyond the 28 are rounded, as in a division; a number
    that this rounding carries over the edge (28 nines and .5) does not fit either."""
    return d.adjusted() < 27 or d.is_zero() or CTX.plus(d).adjusted() < 28     # the usual case first


def text_number(text: str):
    """The number a text holds, or None when `as number` does not accept it."""
    if NUMBER_TEXT.fullmatch(text) is None:
        return None
    d = Decimal(text)
    return d if fits(d) else None


def format_number(d: Decimal) -> str:
    """Whole values without '.0', fractions without trailing zeros, never exponent form."""
    if d.is_zero():
        return "0"
    return format(d.normalize(CTX), "f")


def quote_text(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def literal(v) -> str:
    """A value written as an Axion literal (used inside lists and objects)."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, Decimal):
        return format_number(v)
    if isinstance(v, str):
        return quote_text(v)
    if isinstance(v, list):
        return "[" + ", ".join(literal(x) for x in v) + "]"
    if isinstance(v, MapValue):
        return "{" + ", ".join(f"{quote_text(k)}: {literal(x)}" for k, x in v.items()) + "}"
    if isinstance(v, dict):
        return "{" + ", ".join(f"{k}: {literal(x)}" for k, x in v.items()) + "}"
    raise TypeError(f"cannot format {type(v).__name__}")


def format_value(v) -> str:
    """How `print` shows a value: text raw, everything else as a literal."""
    if isinstance(v, str):
        return v
    return literal(v)


NUMBER_BYTES = sys.getsizeof(Decimal("1234567890.123456789"))   # one number object


def size_of(v):
    """About how many bytes a value takes in memory: what the memory limit counts.

    Text and containers by their real size in Python, a number as one number object, true and
    false as nothing (Python keeps one of each). A number or a text shared by several places is
    counted at each of them: the estimate may be higher than the truth, never lower.
    """
    if isinstance(v, str):
        return sys.getsizeof(v)
    if isinstance(v, bool):
        return 0
    if isinstance(v, Decimal):
        return NUMBER_BYTES
    if isinstance(v, list):
        return sys.getsizeof(v) + sum(size_of(x) for x in v)
    if isinstance(v, dict):                    # an object or a dictionary
        return sys.getsizeof(v) + sum(size_of(k) + size_of(x) for k, x in v.items())
    raise TypeError(f"cannot measure {type(v).__name__}")


def copy_value(v):
    """Axion has no references: assignment and passing always copy (spec §6)."""
    if isinstance(v, list):
        return [copy_value(x) for x in v]
    if isinstance(v, MapValue):
        return MapValue((k, copy_value(x)) for k, x in v.items())
    if isinstance(v, dict):
        return {k: copy_value(x) for k, x in v.items()}
    return v
