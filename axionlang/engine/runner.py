"""The one path every run takes (spec §14-§17):

    source -> lexer -> parser -> AST -> validator -> input check -> interpreter

Fail-closed: if lexing, parsing, validation or the input check fails, nothing is executed.
The command line (python -m axionlang) and the library (engine/api.py) both go through run_outcome, so a
program behaves the same whichever way it is started.
"""

from .errors import AxionError, AxionErrors
from .inputs import InputMismatch, convert
from .interpreter import Interpreter, with_room
from .lexer import lex, normalize_source
from .parser import Input, parse, syntax_errors
from .policy import Policy
from .validator import empty_list_fixes, validate


def bind_inputs(program, data):
    """Check the JSON data against every `input` declaration (spec §14)."""
    declared = [st for st in program.statements if isinstance(st, Input)]
    data = {} if data is None else data
    if not isinstance(data, dict):
        raise AxionError("R407", 1, 1, "The input data must be a JSON object: {\"name\": value}.")
    values = {}
    for st in declared:
        if st.name not in data:
            raise AxionError("R407", st.line, st.col, f"input {st.name} was not provided.",
                             fix=f'add "{st.name}" to the input data', length=st.end - st.col)
        try:
            values[st.name] = convert(data[st.name], st.type, st.name)
        except InputMismatch as exc:
            raise AxionError("R407", st.line, st.col, f"Input data: {exc}",
                             length=st.end - st.col) from None
    names = {st.name for st in declared}
    extra = [k for k in data if k not in names]
    if extra:
        line, col = (declared[0].line, declared[0].col) if declared else (1, 1)
        raise AxionError("R407", line, col,
                         f"The input data has {extra[0]}, which the program does not declare.",
                         fix=f"declare it: input {extra[0]}: type")
    return values


READING_DEPTH = 3000        # room for reading and checking very long or deeply nested lines


def run_outcome(source, data=None, policy=None, base_dir=None, execute=True):
    """Check and run Axion source. Returns (source, output_lines, error).

    source: the text as it was read (line ends made the same, the invisible first mark removed):
    error positions refer to it. output_lines: what the program printed before it ended or was
    stopped. error: the AxionError that stopped it, or None.
    data: input values (a dict from parse_json) or None; policy: a Policy or None.
    execute=False stops after the checks of the program itself: no data is read, nothing runs.
    """
    source = normalize_source(source)
    if source.startswith("\ufeff"):       # the invisible mark some editors put first in a file
        source = source[1:]
    policy = policy or Policy()
    room = max(policy.limits["max_depth"], READING_DEPTH)
    try:
        output, error = with_room(lambda: checked(source, data, policy, base_dir, execute), room)
    except MemoryError:
        # The interpreter turns this into R406 at the statement where it happened; this is for the
        # stages before it (a program text so large that reading it uses up the memory).
        output, error = [], AxionError("R406", 1, 1, "Python ran out of memory while reading or "
                                                     "checking the program.", length=1)
    except RecursionError:
        # Lexer, parser and validator walk an expression by recursion; this one is beyond them.
        lines = source.split("\n")
        longest = max(range(len(lines)), key=lambda k: len(lines[k]))
        output, error = [], AxionError("P217", longest + 1, 1,
                                       "An expression is too long or nested too deeply to check (most "
                                       "likely on this, the longest line).",
                                       fix="split it into several variables", length=1)
    return source, output, error


def checked(source, data, policy, base_dir, execute):
    try:
        try:
            program = parse(lex(source), source)
        except AxionError as first:           # collect the same kind of mistake on other lines
            found = syntax_errors(source, first)
            empty_list_fixes(source, found)
            raise AxionErrors(found) from None
        validate(program, source, policy)
        if not execute:
            return [], None
        inputs = bind_inputs(program, data)
    except AxionError as error:
        return [], error

    interpreter = Interpreter(source, policy, base_dir, inputs)
    try:
        interpreter.run(program)
    except AxionError as error:
        return interpreter.output, error
    return interpreter.output, None


def run_source(source, data=None, policy=None, base_dir=None):
    """Run Axion source. Returns (exit_code, output_lines), the error text included."""
    source, output, error = run_outcome(source, data, policy, base_dir)
    if error is None:
        return 0, output
    return 1, output + error.format(source)
