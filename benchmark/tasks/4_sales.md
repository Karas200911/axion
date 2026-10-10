# Task 4 — Sales analysis

*weekly sums, median, moving average, best 4 days, longest growth*

Written by someone who does not know Axion. Both languages got the same text; only the last lines differ.

> **About the Russian text.** The author of the tasks wrote the labels the program must *print* in Russian (for example `Уровни:`). The models received exactly this text, so it is kept as it was. Everything else is in English.

## The task

```text
TASK
The program receives sales: the sales of consecutive days, whole numbers, 0 or more. Days are numbered from 1.
Write a separate function for every point and print seven lines. Numbers "with two places" have exactly two digits after the point.
1. "1. Суммы по неделям: " and the sums of every 7 days joined with ", " (the last week may be shorter).
2. "2. Среднее: <the average, with two places>   Медиана: <the median, with two places>" (three spaces between the parts). The median of an even number of days is the average of the two middle values.
3. "3. Скользящее среднее: " and, for every 3 days in a row (days 1-3, then 2-4, and so on), their average with two places, joined with one space.
4. "4. Лучшие 4 дня подряд: дни <first>-<last>, сумма <sum>" for the 4 days in a row with the largest sum (the earliest, if several are equal).
5. "5. Самый длинный рост подряд: дни <first>-<last> (<the sales of those days joined with ", ">)" for the longest run of days in which every day is greater than the day before (the earliest, if several are equally long; one day alone is a run of length 1).
6. "6. Топ-3 дня: " and the three days with the largest sales as "день <day> (<sales>)", joined with ", ", the largest first; with equal sales the earlier day first. If there are fewer than three days, all of them.
7. "7. Дней с продажами не меньше 20: <how many days have sales of 20 or more>".
When a point cannot be computed (no days at all; fewer than 3 days for point 3; fewer than 4 days for point 4), write "нет" in place of its value; point 2 for no days is "2. Среднее: нет   Медиана: нет". Point 7 for no days is 0.
Requirements: points 3 and 4 are done in one pass, without adding up the whole window again at every step; point 6 without sorting the whole list; point 7 with a binary search in a sorted copy.
Example: for
{"sales": [12, 15, 11, 18, 20, 19, 25, 7, 9, 14, 21, 22, 24, 23, 10, 30]}
the output is exactly:
1. Суммы по неделям: 120, 120, 40
2. Среднее: 17.50   Медиана: 18.50
3. Скользящее среднее: 12.67 14.67 16.33 19.00 21.33 17.00 13.67 10.00 14.67 19.00 22.33 23.00 19.00 21.00
4. Лучшие 4 дня подряд: дни 11-14, сумма 90
5. Самый длинный рост подряд: дни 8-13 (7, 9, 14, 21, 22, 24)
6. Топ-3 дня: день 16 (30), день 7 (25), день 13 (24)
7. Дней с продажами не меньше 20: 7
```

| Axion version ends with | Python version ends with |
|---|---|
| The first line of your program must be:<br>input sales: list of number | Your program reads one JSON object from standard input, with the key "sales" (a list of whole numbers), and prints the result to standard output. |

## Example from the task

Input data:

```json
{"sales": [12, 15, 11, 18, 20, 19, 25, 7, 9, 14, 21, 22, 24, 23, 10, 30]}
```

Expected output:

```text
1. Суммы по неделям: 120, 120, 40
2. Среднее: 17.50   Медиана: 18.50
3. Скользящее среднее: 12.67 14.67 16.33 19.00 21.33 17.00 13.67 10.00 14.67 19.00 22.33 23.00 19.00 21.00
4. Лучшие 4 дня подряд: дни 11-14, сумма 90
5. Самый длинный рост подряд: дни 8-13 (7, 9, 14, 21, 22, 24)
6. Топ-3 дня: день 16 (30), день 7 (25), день 13 (24)
7. Дней с продажами не меньше 20: 7
```

Plus 7 hidden datasets that the model never saw.

## What Claude Sonnet wrote

Each language, 5 separate runs. All 10 programs below solved the task (visible and hidden data).

- **Axion:** [run 1](../programs/4_sales/axion_run1.ax) · [run 2](../programs/4_sales/axion_run2.ax) · [run 3](../programs/4_sales/axion_run3.ax) · [run 4](../programs/4_sales/axion_run4.ax) · [run 5](../programs/4_sales/axion_run5.ax)
- **Python:** [run 1](../programs/4_sales/python_run1.py) · [run 2](../programs/4_sales/python_run2.py) · [run 3](../programs/4_sales/python_run3.py) · [run 4](../programs/4_sales/python_run4.py) · [run 5](../programs/4_sales/python_run5.py)

These are the programs that were then run on the [spoiled data](../spoiled_data.md#task-4).
