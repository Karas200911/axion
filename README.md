# Axion

**A sandbox for code that AI writes.** The rules of the language fit on two pages. A model writes a
program from them; one call, `axionlang.run`, checks it and runs it safely. Or `axionlang.ask` does
it all: asks your model, checks, runs, and fixes by the errors.

```
pip install axionlang
```

Python 3.10+, no dependencies. **Experimental.**

**[Try it in the browser](https://karas200911.github.io/axion/)** first (the real engine runs in your browser; nothing is sent anywhere). Source: [github.com/Karas200911/axion](https://github.com/Karas200911/axion).

## Run a program

```python
import axionlang

program = """input cart: list of {price: number, qty: number}
total = 0
for item in cart
  total = total + item.price * item.qty
end
print "Total: " + total as text"""

result = axionlang.run(program, {"cart": [{"price": 500, "qty": 2}, {"price": 300, "qty": 1}]})
print(result.ok, result.output)        # True ['Total: 1300']

result = axionlang.run(program, {"cart": [{"price": "500", "qty": 2}]})
print(result.error)                    # R407 ... cart[0].price must be number, got text.
```

The first line, `input ...`, is a contract. The data is checked against it before the program
runs; data of the wrong type or shape is refused, nothing is converted or guessed.

More small programs to run in [`examples/`](https://github.com/Karas200911/axion/tree/main/examples), starting with the same cart on good and on bad data.

## Let your model write it

```python
def model(messages):                   # any provider: messages in, text out
    reply = client.chat.completions.create(model="...", messages=messages)
    return reply.choices[0].message.content

SAMPLE = {"cart": [{"price": 500, "qty": 2}]}      # a fixed sample of the data shape
result = axionlang.ask(model, "Total of the cart, 10% off above 1000", data, shape=SAMPLE)
print(result.ok, result.output, result.program, result.attempts)
```

`ask` checks `data` against `shape` before calling the model (malformed data costs no tokens),
sends the cheat sheet and the data shape (never the values), runs the program, and sends Axion's
error back to the model, up to 3 attempts. A full example: [`examples/ask_bot.py`](https://github.com/Karas200911/axion/blob/main/examples/ask_bot.py).

From a terminal: `python -m axionlang program.ax --input data.json [--policy policy.json]`.

## What it guarantees by default

- No writing files, no network, no system commands: the language has none.
- Reading files only if the program declares `allow read "folder/"` **and** you grant that folder (`allow_read=["folder/"]`). Relative paths only, no `..`.
- Limits, all on by default: 1,000,000 steps, 100,000 printed characters, 1,000,000 list elements, call depth 200, 256 MB of data in lists and dictionaries. Set your own: `axionlang.run(program, data, max_steps=200_000, max_memory_mb=64)`.
- No implicit conversions, numbers are exact decimals (0.1 + 0.2 == 0.3), and a number that does not fit in 28 digits stops the program instead of being rounded.
- A mistake of the program or the data is `result.ok == False` with an error code, a line and a fix, written to be sent back to a model.

## Why its own syntax, not Python?

It is an experiment. We are testing a hypothesis: a deterministic syntax with no syntactic sugar
helps models write correct code, so that small local models (14B–32B) could one day write reliable
code offline and for free. **That is not proven yet.** What already works: the engine refuses
inexact data, does no implicit conversions, and never guesses for the model.

## What we measured (Claude Sonnet, 5 tasks, October 2026)

Five tasks written by someone who does not know Axion; Sonnet solved each 5 times in Axion and 5
times in Python (both 25 of 25). Then every final program ran on 63 spoiled datasets written
before any run: 315 runs per language, outcomes recorded by a script.

| | Axion | Python |
|---|---|---|
| Data of the wrong type or shape (160 runs) | stopped 160 | stopped 117, answered silently 41 |
| Inputs built to hang (`9 ^ 9 ^ 9`, 10 billion payments; 10 runs) | stopped 10 | hung 10 |
| An extra field in the data (25 runs) | refused 25 | right 25 |
| Big but valid data (20 runs) | 15 stopped by the step limit | right 20 |

**Everything is in [`benchmark/`](https://github.com/Karas200911/axion/tree/main/benchmark)**: the tasks, the 50 programs, the 63 datasets, every run, and one command to re-run it all (`python benchmark/run.py`, a few minutes, no key needed).

Limits of this measurement: one model, five tasks, the spoiled data was written by the authors,
and the Python programs were not asked to validate their input.

## What Axion cannot do (yet)

- About **50 times slower** than Python. For small calculations, not heavy data.
- No libraries, no output other than printed lines (no JSON output), no reading CSV/Excel by itself.
- No way to print a number with exactly N decimal places in one step.
- It refuses any extra field in the data.
- The cheat sheet costs about 1,600 tokens in every request.
- A weaker model (Claude Haiku) solved 3 of 5 tasks in Axion against 5 of 5 in Python.
- It has not been attacked by security specialists. No hole is known; that is not a proof.

## Feedback

This is a first release to see whether anyone needs it. One question: **how do you run code that
an AI wrote today, and what is painful about it?** [Open an issue](https://github.com/Karas200911/axion/issues).

[MIT licence](https://github.com/Karas200911/axion/blob/main/LICENSE). Tests: `python -m unittest discover -s tests` (1,326), run on Linux and macOS, Python 3.10–3.14.
