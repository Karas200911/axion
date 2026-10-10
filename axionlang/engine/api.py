"""Axion as a library: check and run a program from Python in one call.

    import axionlang

    result = axionlang.run(program, {"price": 250, "count": 3})
    if result.ok:
        print(result.output)          # the lines the program printed
    else:
        print(result.error)           # the error text, as the terminal shows it
        result.error.code             # "R407", "V301", ...

    axionlang.check(program)              # only check: nothing is read, nothing runs
    axionlang.describe(data)              # the `input` lines for data of this shape
    axionlang.CHEATSHEET                  # the description of Axion to give to a model

The program is text, usually written by a model. The data is an ordinary Python dict: numbers
(int, float, Decimal), text, True / False, lists and dicts. Every run goes through the same
path as the command line (engine/runner.py), so nothing runs before all checks have passed.
"""

from decimal import Decimal
from pathlib import Path

from .errors import AxionError, AxionErrors
from .inputs import MAX_DATA_DEPTH, too_deep_message
from .lexer import lex
from .parser import parse
from .policy import DEFAULT_LIMITS, Policy, PolicyError
from .runner import bind_inputs, run_outcome

CHEATSHEET = (Path(__file__).resolve().parent.parent / "CHEATSHEET.md").read_text(encoding="utf-8")


class Error:
    """One Axion error. str(error) is the text the terminal shows; send it back to the model."""

    __slots__ = ("code", "line", "col", "message", "fix", "text")

    def __init__(self, code, line, col, message, fix, text):
        self.code = code            # "V301": the letter is the kind (L, P, V, S, R), see the spec
        self.line = line            # line of the program, from 1
        self.col = col              # character in that line, from 1
        self.message = message      # what is wrong
        self.fix = fix              # how to repair it, or None
        self.text = text            # the whole message

    def __str__(self):
        return self.text

    def __repr__(self):
        return f"<axiom.Error {self.code} line {self.line}:{self.col}: {self.message}>"


class Result:
    """What a run or a check ended with."""

    __slots__ = ("ok", "output", "error", "errors")

    def __init__(self, ok, output, error, errors):
        self.ok = ok                # True: the program passed every check and ran to its end
        self.output = output        # the printed lines; on a runtime error, those printed before it
        self.error = error          # the first Error, its text holding all of them; None when ok
        self.errors = errors        # every Error found in this pass, each with its own text

    @property
    def text(self):
        """The printed lines as one text."""
        return "\n".join(self.output)

    def __repr__(self):
        if self.ok:
            return f"<axiom.Result ok, {len(self.output)} line(s) printed>"
        return f"<axiom.Result stopped by {self.error.code}: {self.error.message}>"


def _result(source, output, error):
    if error is None:
        return Result(True, list(output), None, [])
    parts = error.errors if isinstance(error, AxionErrors) else [error]
    errors = [Error(e.code, e.line, e.col, e.message, e.fix, "\n".join(e.format(source))) for e in parts]
    first = errors[0]
    whole = Error(first.code, first.line, first.col, first.message, first.fix,
                  "\n".join(error.format(source)))
    return Result(False, list(output), whole, errors)


def _to_axiom(value, where, depth=0):
    """A Python value as the input check expects it: exact decimal numbers, plain lists and dicts.

    Data nested deeper than MAX_DATA_DEPTH is refused as R407 (an AxionError), not walked.
    """
    if depth > MAX_DATA_DEPTH:
        raise AxionError("R407", 1, 1, too_deep_message(where))
    if value is None or isinstance(value, (bool, str)):
        return value                              # None is refused later, by the input check (R407)
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        number = Decimal(repr(value)) if value == value and value not in (float("inf"), float("-inf")) else None
        if number is None:
            raise ValueError(f"{where}: {value} is not a number Axion accepts")
        return number
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError(f"{where}: {value} is not a number Axion accepts")
        return value
    if isinstance(value, (list, tuple)):
        return [_to_axiom(item, f"{where}[{i}]", depth + 1) for i, item in enumerate(value)]
    if isinstance(value, dict):
        for key in value:
            if not isinstance(key, str):
                raise TypeError(f"{where}: a key must be text, got {type(key).__name__} ({key!r})")
        return {key: _to_axiom(item, f"{where}.{key}", depth + 1) for key, item in value.items()}
    raise TypeError(f"{where}: Axion data is numbers, text, True / False, lists and dicts; "
                    f"got {type(value).__name__}")


def _data(data):
    if data is None:
        return None
    if not isinstance(data, dict):
        raise TypeError(f"data must be a dict of input names and values, got {type(data).__name__}")
    for key in data:
        if not isinstance(key, str):
            raise TypeError(f"data: an input name must be text, got {type(key).__name__} ({key!r})")
    return {key: _to_axiom(value, key, 1) for key, value in data.items()}   # the dict itself is level 0


def _policy(allow_read, limits):
    given = {key: value for key, value in limits.items() if value is not None}
    if isinstance(allow_read, str):
        raise TypeError('allow_read must be a list of folders, for example ["notes/"]')
    try:
        return Policy.from_dict({"allow_read": list(allow_read), **given})
    except PolicyError as exc:
        raise ValueError(str(exc)) from None


def _program(program):
    if not isinstance(program, str):
        raise TypeError(f"program must be the text of an Axion program, got {type(program).__name__}")
    return program


def run(program, data=None, *, allow_read=(), folder=None,
        max_steps=None, max_output_chars=None, max_list_size=None, max_depth=None,
        max_memory_mb=None):
    """Check an Axion program and the data, and run it. Returns a Result.

    program: the text of the program. data: a dict with a value for every `input` of the program.
    allow_read: folders the program may read, if it asks with `allow read`; folder: where those
    folders are (default: the current folder). max_...: limits of this run; the defaults are in
    engine/policy.py (1,000,000 steps, 100,000 printed characters, 1,000,000 elements, depth 200,
    256 MB of data kept by the program).

    A mistake of the program or unfit data is not an exception: it is result.ok == False and
    result.error. An exception (TypeError, ValueError) means the call itself is wrong.
    """
    policy = _policy(allow_read, dict(max_steps=max_steps, max_output_chars=max_output_chars,
                                      max_list_size=max_list_size, max_depth=max_depth,
                                      max_memory_mb=max_memory_mb))
    base_dir = Path(folder).resolve() if folder is not None else None
    source = _program(program)
    try:
        values = _data(data)
    except AxionError as error:              # data nested too deeply: refused, nothing runs
        return _result(source, [], error)
    return _result(*run_outcome(source, values, policy, base_dir))


def check(program, *, allow_read=()):
    """Check a program without running it and without data. Returns a Result with no output.

    Finds what can be found before a run: how the program is written (codes L and P), its
    meaning (V) and its permissions (S). What depends on the data shows only in run().
    """
    policy = _policy(allow_read, {})
    return _result(*run_outcome(_program(program), None, policy, None, execute=False))


def _type_of(value, where, depth=0):
    if depth > MAX_DATA_DEPTH:
        root = where.split("[")[0].split(".")[0]
        raise ValueError(f"{root} is nested more than {MAX_DATA_DEPTH} levels deep: "
                         f"it cannot be described as Axion inputs.")
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float, Decimal)):
        return "number"
    if isinstance(value, str):
        return "text"
    if isinstance(value, (list, tuple)):
        if not value:
            raise ValueError(f"{where} is an empty list: the type of its elements is unknown. "
                             f"Describe a sample that has at least one element.")
        kinds = [_type_of(item, f"{where}[{i}]", depth + 1) for i, item in enumerate(value)]
        for i, kind in enumerate(kinds):
            if kind != kinds[0]:
                raise ValueError(f"{where} mixes types: {where}[0] is {kinds[0]} and {where}[{i}] is "
                                 f"{kind}. An Axion list holds values of one type.")
        return f"list of {kinds[0]}"
    if isinstance(value, dict):
        if not value:
            raise ValueError(f"{where} is an empty dict: its fields are unknown. "
                             f"Describe a sample that has its fields.")
        for key in value:
            if not isinstance(key, str):
                raise TypeError(f"{where}: a key must be text, got {type(key).__name__} ({key!r})")
        return "{" + ", ".join(f"{key}: {_type_of(item, f'{where}.{key}', depth + 1)}"
                               for key, item in value.items()) + "}"
    if value is None:
        raise ValueError(f"{where} is None: Axion has no empty value. Leave it out or give a real value.")
    raise TypeError(f"{where}: Axion data is numbers, text, True / False, lists and dicts; "
                    f"got {type(value).__name__}")


def describe(data):
    """The `input` lines for data of this shape: what a program for this data starts with.

        axionlang.describe({"price": 250, "items": [{"name": "Cup", "qty": 2}]})
        -> 'input price: number\\ninput items: list of {name: text, qty: number}'

    Give a sample with real values: an empty list or dict cannot be described. A dict becomes an
    object with exactly these fields. The lines are proved before they are returned: Axion reads
    them and accepts this very data with them. Raises ValueError when the data cannot be
    described (the message says where and why).
    """
    if not isinstance(data, dict):
        raise TypeError(f"data must be a dict of input names and values, got {type(data).__name__}")
    for key in data:
        if not isinstance(key, str):
            raise TypeError(f"data: an input name must be text, got {type(key).__name__} ({key!r})")
    text = "\n".join(f"input {name}: {_type_of(value, name, 1)}" for name, value in data.items())
    source = text + "\n"
    try:
        bind_inputs(parse(lex(source), source), _data(data))
    except AxionError as error:
        raise ValueError("this data cannot be described as Axion inputs:\n"
                         + "\n".join(error.format(source))) from None
    return text


class AskResult(Result):
    """What ask() ended with: a Result plus the program the model wrote and how it got there."""

    __slots__ = ("program", "attempts", "history")

    def __init__(self, ok, output, error, errors, program, attempts, history):
        super().__init__(ok, output, error, errors)
        self.program = program      # the last program the model wrote ("" if none)
        self.attempts = attempts    # how many times the model was asked (0: the data was refused first)
        self.history = history      # one (program, error or None) pair per attempt

    def __repr__(self):
        if self.ok:
            return f"<axionlang.AskResult ok after {self.attempts} attempt(s)>"
        return f"<axionlang.AskResult stopped by {self.error.code} after {self.attempts} attempt(s)>"


def _strip_fence(reply):
    """The program inside a reply: a ``` fence around it is removed, nothing else is guessed."""
    text = reply.strip()
    if text.startswith("```"):
        lines = text.split("\n")[1:]               # the first line: ``` or ```axion
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def ask(model, question, data, *, shape=None, max_attempts=3, allow_read=(), folder=None,
        max_steps=None, max_output_chars=None, max_list_size=None, max_depth=None,
        max_memory_mb=None):
    """Ask a model to write an Axion program for a question, check it and run it on the data.

        def model(messages):                    # any model: OpenAI, Claude, local, a fake one
            r = client.chat.completions.create(model="...", messages=messages)
            return r.choices[0].message.content

        result = axionlang.ask(model, "Total of all prices", data, shape=SAMPLE)
        result.ok, result.output, result.program, result.attempts

    model: a function that takes a list of messages ({"role": ..., "content": ...}) and returns
    the reply text. Errors of the model itself (network, key) are not caught: they are yours.
    shape: a sample of what the data must look like. It is required: the data is checked against
    it before the model is asked, so malformed data costs no tokens and is never computed on.
    For a quick try pass shape=data; then malformed data is not caught, and you chose that.
    The model sees only the shape of the data (describe), never the values.
    If the program fails, its error goes back to the model, up to max_attempts times in all.
    """
    if shape is None:
        raise TypeError("shape is required: pass a sample of what the data must look like, "
                        "e.g. shape={\"prices\": [120, 450]}. For a quick try pass shape=data "
                        "(then malformed data is not caught).")
    if not callable(model):
        raise TypeError("model must be a function: messages -> reply text")
    if not isinstance(question, str) or not question.strip():
        raise TypeError("question must be a non-empty text")
    if not isinstance(max_attempts, int) or isinstance(max_attempts, bool) or max_attempts < 1:
        raise ValueError("max_attempts must be a whole number, 1 or more")
    limits = dict(allow_read=allow_read, folder=folder, max_steps=max_steps,
                  max_output_chars=max_output_chars, max_list_size=max_list_size,
                  max_depth=max_depth, max_memory_mb=max_memory_mb)

    inputs = describe(shape)
    # The data is checked against the shape before any token is spent.
    source = inputs + "\n"
    try:
        bind_inputs(parse(lex(source), source), _data(data))
    except AxionError as error:
        refused = _result(source, [], error)
        return AskResult(False, [], refused.error, refused.errors, "", 0, [])

    about_data = ("The program receives this data:\n" + inputs) if inputs else "The program receives no input data."
    messages = [
        {"role": "system", "content": CHEATSHEET},
        {"role": "user", "content": about_data + "\n\nTask: " + question.strip()
                                    + "\n\nReply with only the Axion program, no explanations."},
    ]
    history = []
    program, result = "", None
    for attempt in range(1, max_attempts + 1):
        reply = model(messages)
        if not isinstance(reply, str):
            raise TypeError(f"model must return text, got {type(reply).__name__}")
        program = _strip_fence(reply)
        if not program:
            history.append((program, None))
            result = None
            feedback = "Your reply contained no program. Reply with only the Axion program."
        else:
            result = run(program, data, **limits)
            history.append((program, None if result.ok else result.error))
            if result.ok:
                return AskResult(True, result.output, None, [], program, attempt, history)
            feedback = ("Axion returned an error:\n" + str(result.error)
                        + "\nFix the program. Reply with only the Axion program.")
        messages.append({"role": "assistant", "content": reply})
        messages.append({"role": "user", "content": feedback})

    if result is None:                          # the last reply had no program at all
        none = Error("NO_PROGRAM", 1, 1, "The model returned no program.", None,
                     "The model returned no program.")
        return AskResult(False, [], none, [none], program, max_attempts, history)
    return AskResult(False, result.output, result.error, result.errors, program, max_attempts, history)


__all__ = ["CHEATSHEET", "DEFAULT_LIMITS", "AskResult", "Error", "Result", "ask", "check", "describe", "run"]
