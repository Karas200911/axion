# Task 2 — Payment schedule

*split an amount into monthly payments to the kopeck, with month ends*

Written by someone who does not know Axion. Both languages got the same text; only the last lines differ.

## The task

```text
TASK
The program receives total (an amount of money written as text, for example "1000.00"), n (a whole number) and start (a date, year-month-day).
Split total into n monthly payments. The first payment is on the date start.
- The payments add up to total exactly, to the kopeck (one hundredth). If total does not divide evenly, the extra kopecks go to the first payments, one kopeck each.
- Every next payment is one month later, on the same day of the month as start. If that month has no such day, the payment is on the last day of that month. The day of start is used for every month: after a short month the day comes back (see March in the example).
Print one line for every payment: two spaces, the date, then the amount with exactly two digits after the point, aligned to the right in 9 characters.
Errors. Check in this order and print only that one line:
- n is less than 1: "error: n must be 1 or more"
- total is negative: "error: total must not be negative"
- total has fractions of a kopeck (for example "100.005"): "error: total has fractions of a kopeck"
total is always a number written with digits and, possibly, a point; it may start with "-"; it is less than 1000000. start is always a correct date.
A second example: total "100.00", n 6, start "2027-11-30" gives 16.67 four times and then 16.66 twice, on 2027-11-30, 2027-12-30, 2028-01-30, 2028-02-29, 2028-03-30, 2028-04-30.
Example: for
{"total": "1000.00", "n": 3, "start": "2026-01-31"}
the output is exactly:
  2026-01-31   333.34
  2026-02-28   333.33
  2026-03-31   333.33
```

| Axion version ends with | Python version ends with |
|---|---|
| The first three lines of your program must be:<br>input total: text<br>input n: number<br>input start: text | Your program reads one JSON object from standard input, with the keys "total" (a text), "n" (a number) and "start" (a text), and prints the result to standard output. |

## Example from the task

Input data:

```json
{"total": "1000.00", "n": 3, "start": "2026-01-31"}
```

Expected output:

```text
  2026-01-31   333.34
  2026-02-28   333.33
  2026-03-31   333.33
```

Plus 11 hidden datasets that the model never saw.

## What Claude Sonnet wrote

Each language, 5 separate runs. All 10 programs below solved the task (visible and hidden data).

- **Axion:** [run 1](../programs/2_schedule/axion_run1.ax) · [run 2](../programs/2_schedule/axion_run2.ax) · [run 3](../programs/2_schedule/axion_run3.ax) · [run 4](../programs/2_schedule/axion_run4.ax) · [run 5](../programs/2_schedule/axion_run5.ax)
- **Python:** [run 1](../programs/2_schedule/python_run1.py) · [run 2](../programs/2_schedule/python_run2.py) · [run 3](../programs/2_schedule/python_run3.py) · [run 4](../programs/2_schedule/python_run4.py) · [run 5](../programs/2_schedule/python_run5.py)

These are the programs that were then run on the [spoiled data](../spoiled_data.md#task-2).
