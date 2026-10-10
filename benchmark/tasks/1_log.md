# Task 1 — Server log report

*parse log lines, count levels, errors by hour and by module*

Written by someone who does not know Axion. Both languages got the same text; only the last lines differ.

> **About the Russian text.** The author of the tasks wrote the labels the program must *print* in Russian (for example `Уровни:`). The models received exactly this text, so it is kept as it was. Everything else is in English.

## The task

```text
TASK
The program receives log: the text of a server log, its lines separated by "\n".
A correct line looks like this:
2026-10-05 09:15:02 ERROR payment: timeout after 30s
that is: a date (4 digits, 2 digits, 2 digits, with "-" between them), one space, a time HH:MM:SS (two digits each), one space, a level (a word of letters), one space, a module (a word and ":" right after it), and then the message.
- An empty line, or a line of spaces only, is skipped silently.
- Any other line that is not a correct line is counted as skipped.
- The case of the level does not matter: "error" and "ERROR" are the same level, and it is printed as ERROR.
Print the report:
1. "Уровни:" and then one line for every level: two spaces, the level padded with spaces on the right to 13 characters, then the number of lines with that level.
2. An empty line, then "Ошибки по часам:" and one line for every hour that has lines of the level ERROR: two spaces, the date, a space, the hour as HH:00, four spaces, the number of ERROR lines in that hour.
3. An empty line, then "Ошибки по модулям:" and one line for every module that has ERROR lines: two spaces, the module padded with spaces on the right to 13 characters, then the number of its ERROR lines.
4. An empty line, then "Пропущено строк: <the number of skipped lines>".
Levels and modules are sorted by their number, the largest first; with equal numbers, alphabetically. Hours go in the order of time.
Names of levels and modules are never longer than 12 characters; module names are written in small Latin letters. A section that has no lines consists of its title only.
Example: for
{"log": "2026-10-05 09:15:02 ERROR payment: timeout after 30s\n2026-10-05 09:47:11 INFO auth: user 42 logged in\n2026-10-05 10:03:45 ERROR auth: invalid token\n\n2026-10-05 10:20:00 WARNING payment: retry 2\n2026-10-05 10:59:59 ERROR payment: timeout after 30s\nбитая строка\n2026-10-05 11:00:00 ERROR payment: card declined\n2026-10-06 09:05:00 error auth: invalid token\n"}
the output is exactly:
Уровни:
  ERROR        5
  INFO         1
  WARNING      1

Ошибки по часам:
  2026-10-05 09:00    1
  2026-10-05 10:00    2
  2026-10-05 11:00    1
  2026-10-06 09:00    1

Ошибки по модулям:
  payment      3
  auth         2

Пропущено строк: 1
```

| Axion version ends with | Python version ends with |
|---|---|
| The first line of your program must be:<br>input log: text | Your program reads one JSON object from standard input, with the key "log" (a text), and prints the report to standard output. |

## Example from the task

Input data:

```json
{"log": "2026-10-05 09:15:02 ERROR payment: timeout after 30s\n2026-10-05 09:47:11 INFO auth: user 42 logged in\n2026-10-05 10:03:45 ERROR auth: invalid token\n\n2026-10-05 10:20:00 WARNING payment: retry 2\n2026-10-05 10:59:59 ERROR payment: timeout after 30s\nбитая строка\n2026-10-05 11:00:00 ERROR payment: card declined\n2026-10-06 09:05:00 error auth: invalid token\n"}
```

Expected output:

```text
Уровни:
  ERROR        5
  INFO         1
  WARNING      1

Ошибки по часам:
  2026-10-05 09:00    1
  2026-10-05 10:00    2
  2026-10-05 11:00    1
  2026-10-06 09:00    1

Ошибки по модулям:
  payment      3
  auth         2

Пропущено строк: 1
```

Plus 4 hidden datasets that the model never saw.

## What Claude Sonnet wrote

Each language, 5 separate runs. All 10 programs below solved the task (visible and hidden data).

- **Axion:** [run 1](../programs/1_log/axion_run1.ax) · [run 2](../programs/1_log/axion_run2.ax) · [run 3](../programs/1_log/axion_run3.ax) · [run 4](../programs/1_log/axion_run4.ax) · [run 5](../programs/1_log/axion_run5.ax)
- **Python:** [run 1](../programs/1_log/python_run1.py) · [run 2](../programs/1_log/python_run2.py) · [run 3](../programs/1_log/python_run3.py) · [run 4](../programs/1_log/python_run4.py) · [run 5](../programs/1_log/python_run5.py)

These are the programs that were then run on the [spoiled data](../spoiled_data.md#task-1).
