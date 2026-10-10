"""Input data (spec §14): JSON given by the runner, checked against `input` types
before the first line of the program runs.

    JSON number -> number      JSON string -> text      true / false -> bool
    JSON array  -> list of T   JSON object -> object with exactly the declared fields,
                               or, for `map of T`, a dictionary with any text keys
    null, a missing value, an extra field or a wrong type -> error R407, nothing runs.
"""

import json
from decimal import Decimal

from .axtypes import BOOL, NUMBER, TEXT, ListT, MapT, ObjectT
from .values import MapValue, fits


class InputMismatch(Exception):
    pass


# Data nested deeper than this is refused before anything walks it. No declared type comes near
# it, and walking deeper by recursion would end in a Python RecursionError instead of an answer.
MAX_DATA_DEPTH = 100


def too_deep_message(where):
    root = where.split("[")[0].split(".")[0]     # the input name; the full path would be 100 steps long
    return (f"Input data: {root} is nested more than {MAX_DATA_DEPTH} levels deep "
            f"(lists or objects inside each other).")


def _depth_fits(value):
    """True if no list or object in value is nested more than MAX_DATA_DEPTH levels (no recursion)."""
    stack = [(value, 0)]
    while stack:
        item, depth = stack.pop()
        if isinstance(item, (list, dict)):
            if depth > MAX_DATA_DEPTH:
                return False
            stack.extend((child, depth + 1) for child in (item.values() if isinstance(item, dict) else item))
    return True


def _reject_constant(name):
    raise ValueError(f"{name} is not a valid number")


def parse_json(text):
    """JSON with exact decimal numbers (no binary floats)."""
    too_deep = (f"the data is nested too deeply (more than {MAX_DATA_DEPTH} levels "
                f"of lists or objects are refused)")
    try:
        data = json.loads(text, parse_float=Decimal, parse_int=Decimal,
                          parse_constant=_reject_constant)
    except RecursionError:
        raise ValueError(too_deep) from None
    if not _depth_fits(data):
        raise ValueError(too_deep)
    return data


def json_kind(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true/false"
    if isinstance(value, Decimal):
        return "a number"
    if isinstance(value, str):
        return "text"
    if isinstance(value, list):
        return "an array"
    return "an object"


def convert(value, t, where):
    """Check one JSON value against an Axion type and return the Axion value."""
    if t == NUMBER:
        if isinstance(value, Decimal) and not isinstance(value, bool):
            if not fits(value):
                raise InputMismatch(f"{where} is too large for a number: a number keeps 28 digits.")
            return value
    elif t == TEXT:
        if isinstance(value, str):
            return value
    elif t == BOOL:
        if isinstance(value, bool):
            return value
    elif isinstance(t, ListT):
        if isinstance(value, list):
            return [convert(item, t.elem, f"{where}[{i}]") for i, item in enumerate(value)]
    elif isinstance(t, MapT):
        if isinstance(value, dict):
            return MapValue((key, convert(item, t.value, f'{where}["{key}"]'))
                            for key, item in value.items())
    elif isinstance(t, ObjectT):
        if isinstance(value, dict):
            missing = [f for f in t.fields if f not in value]
            extra = [f for f in value if f not in t.fields]
            if missing:
                raise InputMismatch(f"{where} has no field {missing[0]}.")
            if extra:
                raise InputMismatch(f"{where} has a field {extra[0]} that the program does not declare.")
            return {f: convert(value[f], ft, f"{where}.{f}") for f, ft in t.fields.items()}
    raise InputMismatch(f"{where} must be {t}, got {json_kind(value)}.")
