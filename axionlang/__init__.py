"""Axion: a small language for calculations written by AI models, checked before they run.

    import axionlang
    result = axionlang.run(program_text, {"price": 250, "count": 3})
    result.ok, result.output, result.error

    # or let a model write the program; the data is checked against the shape first
    result = axionlang.ask(model, "Total of all prices", data, shape=SAMPLE)

From a terminal:
    python -m axionlang program.ax
    python -m axionlang program.ax --input data.json --policy policy.json

Pipeline: source -> lexer -> parser -> AST -> validator -> input check -> interpreter
(engine/runner.py). Fail-closed: if lexing, parsing, validation or the input check fails,
nothing is executed.
"""

from .engine.api import CHEATSHEET, AskResult, Error, Result, ask, check, describe, run  # noqa: F401
from .engine.policy import DEFAULT_LIMITS  # noqa: F401
from .engine.runner import run_source  # noqa: F401

__version__ = "0.3.0"
__all__ = ["CHEATSHEET", "DEFAULT_LIMITS", "AskResult", "Error", "Result", "ask", "check", "describe", "run",
           "run_source"]
