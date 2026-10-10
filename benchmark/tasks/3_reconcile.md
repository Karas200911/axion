# Task 3 — Reconciling two exports

*compare two exports by id: case, spaces, comma decimals, duplicates*

Written by someone who does not know Axion. Both languages got the same text; only the last lines differ.

> **About the Russian text.** The author of the tasks wrote the labels the program must *print* in Russian (for example `Уровни:`). The models received exactly this text, so it is kept as it was. Everything else is in English.

## The task

```text
TASK
The program receives two exports of operations, a and b. Every record has an id, a date and an amount; all three are text.
Rules:
- An id is compared without regard to case and to spaces at its ends: "t-1007 " and "T-1007" are the same id. In the report it is written in capital letters without those spaces.
- An amount may be written with a point or with a comma ("730.00", "730,00") and is compared as a number: "1500.00" and "1500.0" are equal.
- Full duplicates inside one export (the same id, date and amount) count as one record, and are named in the report. Inside one export an id never appears with different data.
Compare the records of a and b by id and print the report. Everywhere ids go in alphabetical order; an amount is printed with exactly two digits after the point.
1. "Совпало: <how many ids have the same date and amount in both>". If there are any, the next line: two spaces and those ids joined with ", ".
2. An empty line, then "Расхождения: <how many ids are in both but differ>" and one line for each. If the amounts differ: two spaces, the id, two spaces, "сумма: <amount in a> / <amount in b> (разница <the difference, without a sign>)". Otherwise the dates differ: two spaces, the id, two spaces, "дата: <date in a> / <date in b>".
3. An empty line, then "Только в A: <how many ids are only in a>" and one line for each: two spaces, the id, two spaces, the date, then the amount aligned to the right in 9 characters.
4. An empty line, then "Только в B: <how many>" and the same lines for the ids that are only in b.
5. An empty line. If a has duplicates: "Дубликаты в A: " and for every duplicated id "<id> (<how many times it was written> раза)", joined with ", "; then an empty line. The same for b with "Дубликаты в B: ".
6. The last line: "Итого A: <sum of a>   Итого B: <sum of b>   Разница: <sum of a minus sum of b>", with three spaces between the parts. A duplicate is counted once in a sum.
Each export must be handled in one pass, without a loop inside a loop.
Amounts are 0 or more and less than 100000. An id is written from 2 to 4 times when it is duplicated.
Example: for
{"a": [{"id": "T-1001", "date": "2026-09-01", "amount": "1500.00"}, {"id": "T-1002", "date": "2026-09-01", "amount": "250.50"}, {"id": "T-1003", "date": "2026-09-02", "amount": "99.99"}, {"id": "T-1004", "date": "2026-09-03", "amount": "1200.00"}, {"id": "T-1004", "date": "2026-09-03", "amount": "1200.00"}, {"id": "T-1006", "date": "2026-09-04", "amount": "0.10"}, {"id": "t-1007 ", "date": "2026-09-05", "amount": "730.00"}], "b": [{"id": "T-1001", "date": "2026-09-01", "amount": "1500.0"}, {"id": "T-1002", "date": "2026-09-01", "amount": "250.05"}, {"id": "T-1003", "date": "2026-09-03", "amount": "99.99"}, {"id": "T-1005", "date": "2026-09-03", "amount": "400.00"}, {"id": "T-1006", "date": "2026-09-04", "amount": "0.1"}, {"id": "T-1007", "date": "2026-09-05", "amount": "730,00"}]}
the output is exactly:
Совпало: 3
  T-1001, T-1006, T-1007

Расхождения: 2
  T-1002  сумма: 250.50 / 250.05 (разница 0.45)
  T-1003  дата: 2026-09-02 / 2026-09-03

Только в A: 1
  T-1004  2026-09-03  1200.00

Только в B: 1
  T-1005  2026-09-03   400.00

Дубликаты в A: T-1004 (2 раза)

Итого A: 3780.59   Итого B: 2980.14   Разница: 800.45
```

| Axion version ends with | Python version ends with |
|---|---|
| The first two lines of your program must be:<br>input a: list of {id: text, date: text, amount: text}<br>input b: list of {id: text, date: text, amount: text} | Your program reads one JSON object from standard input, with the keys "a" and "b" (each a list of objects with the text fields "id", "date", "amount"), and prints the report to standard output. |

## Example from the task

Input data:

```json
{"a": [{"id": "T-1001", "date": "2026-09-01", "amount": "1500.00"}, {"id": "T-1002", "date": "2026-09-01", "amount": "250.50"}, {"id": "T-1003", "date": "2026-09-02", "amount": "99.99"}, {"id": "T-1004", "date": "2026-09-03", "amount": "1200.00"}, {"id": "T-1004", "date": "2026-09-03", "amount": "1200.00"}, {"id": "T-1006", "date": "2026-09-04", "amount": "0.10"}, {"id": "t-1007 ", "date": "2026-09-05", "amount": "730.00"}], "b": [{"id": "T-1001", "date": "2026-09-01", "amount": "1500.0"}, {"id": "T-1002", "date": "2026-09-01", "amount": "250.05"}, {"id": "T-1003", "date": "2026-09-03", "amount": "99.99"}, {"id": "T-1005", "date": "2026-09-03", "amount": "400.00"}, {"id": "T-1006", "date": "2026-09-04", "amount": "0.1"}, {"id": "T-1007", "date": "2026-09-05", "amount": "730,00"}]}
```

Expected output:

```text
Совпало: 3
  T-1001, T-1006, T-1007

Расхождения: 2
  T-1002  сумма: 250.50 / 250.05 (разница 0.45)
  T-1003  дата: 2026-09-02 / 2026-09-03

Только в A: 1
  T-1004  2026-09-03  1200.00

Только в B: 1
  T-1005  2026-09-03   400.00

Дубликаты в A: T-1004 (2 раза)

Итого A: 3780.59   Итого B: 2980.14   Разница: 800.45
```

Plus 4 hidden datasets that the model never saw.

## What Claude Sonnet wrote

Each language, 5 separate runs. All 10 programs below solved the task (visible and hidden data).

- **Axion:** [run 1](../programs/3_reconcile/axion_run1.ax) · [run 2](../programs/3_reconcile/axion_run2.ax) · [run 3](../programs/3_reconcile/axion_run3.ax) · [run 4](../programs/3_reconcile/axion_run4.ax) · [run 5](../programs/3_reconcile/axion_run5.ax)
- **Python:** [run 1](../programs/3_reconcile/python_run1.py) · [run 2](../programs/3_reconcile/python_run2.py) · [run 3](../programs/3_reconcile/python_run3.py) · [run 4](../programs/3_reconcile/python_run4.py) · [run 5](../programs/3_reconcile/python_run5.py)

These are the programs that were then run on the [spoiled data](../spoiled_data.md#task-3).
