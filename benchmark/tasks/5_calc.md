# Task 5 — Expression calculator

*tokenizer and recursive descent: + - * / ^, parentheses, errors with positions*

Written by someone who does not know Axion. Both languages got the same text; only the last lines differ.

> **About the Russian text.** The author of the tasks wrote the labels the program must *print* in Russian (for example `Уровни:`). The models received exactly this text, so it is kept as it was. Everything else is in English.

## The task

```text
TASK
The program receives lines: a list of texts. Every text is an arithmetic expression. For every line, in order, print one line: its result, or an error.
Supported:
- whole numbers and numbers with a fraction (12, 0.5), and any number of spaces between the parts;
- the operations + - * / ^ and parentheses;
- the usual priority: the power ^ first, then * and /, then + and -. The operations + - * / go from left to right; the power goes from right to left (2 ^ 3 ^ 2 is 2 ^ 9);
- a unary minus, which is applied after the power: -2 ^ 2 is -4. It may stand before a number or a parenthesis, also right after another operation: 2 * -(1 + 1).
Results are exact: 0.1 + 0.2 gives exactly 0.3. A whole result is printed without a point (14, not 14.0); a fraction is printed without zeros at its end (2.5).
Work in two steps: first turn the line into a list of tokens, then compute the tokens. A ready-made evaluator of expressions must not be used.
Errors, one line each:
- the line is empty or holds only spaces: "ошибка: пустое выражение"
- a character that is not a digit, a point, a space, an operation or a parenthesis: "ошибка: неизвестный символ '<the character>', позиция <its position in the line, counted from 1>". It is found in the first step, so it comes before any other error.
- a number is expected (or an opening parenthesis, or a unary minus) and something else stands there: "ошибка: ожидалось число, позиция <the position of what stands there>". If the line ends at that place, the position is the length of the line plus 1.
- the line ends while a parenthesis is still open: "ошибка: не закрыта скобка"
- division by zero: "ошибка: деление на ноль"
The tests hold only these kinds of errors, and no more than one problem in a line. Every result in the tests is an exact decimal number of no more than 15 digits, and every power is a whole number, 0 or more.
Examples (a line, and what is printed for it):
2 + 3 * 4        ->  14
(2 + 3) * 4      ->  20
2 - 3 - 4        ->  -5
8 / 2 / 2        ->  2
10 / 4           ->  2.5
0.1 + 0.2        ->  0.3
-3 + 5           ->  2
2 * -(1 + 1)     ->  -4
2 ^ 3 ^ 2        ->  512
-2 ^ 2           ->  -4
1 / 0            ->  ошибка: деление на ноль
(1 + 2           ->  ошибка: не закрыта скобка
2 + * 3          ->  ошибка: ожидалось число, позиция 5
2 $ 3            ->  ошибка: неизвестный символ '$', позиция 3
(an empty line)  ->  ошибка: пустое выражение

For these fifteen lines, given in this order as
{"lines": ["2 + 3 * 4", "(2 + 3) * 4", "2 - 3 - 4", "8 / 2 / 2", "10 / 4", "0.1 + 0.2", "-3 + 5", "2 * -(1 + 1)", "2 ^ 3 ^ 2", "-2 ^ 2", "1 / 0", "(1 + 2", "2 + * 3", "2 $ 3", ""]}
the output is exactly:
14
20
-5
2
2.5
0.3
2
-4
512
-4
ошибка: деление на ноль
ошибка: не закрыта скобка
ошибка: ожидалось число, позиция 5
ошибка: неизвестный символ '$', позиция 3
ошибка: пустое выражение
```

| Axion version ends with | Python version ends with |
|---|---|
| The first line of your program must be:<br>input lines: list of text | Your program reads one JSON object from standard input, with the key "lines" (a list of texts), and prints one line of output for every line. |

## Example from the task

Input data:

```json
{"lines": ["2 + 3 * 4", "(2 + 3) * 4", "2 - 3 - 4", "8 / 2 / 2", "10 / 4", "0.1 + 0.2", "-3 + 5", "2 * -(1 + 1)", "2 ^ 3 ^ 2", "-2 ^ 2", "1 / 0", "(1 + 2", "2 + * 3", "2 $ 3", ""]}
```

Expected output:

```text
14
20
-5
2
2.5
0.3
2
-4
512
-4
ошибка: деление на ноль
ошибка: не закрыта скобка
ошибка: ожидалось число, позиция 5
ошибка: неизвестный символ '$', позиция 3
ошибка: пустое выражение
```

Plus 4 hidden datasets that the model never saw.

## What Claude Sonnet wrote

Each language, 5 separate runs. All 10 programs below solved the task (visible and hidden data).

- **Axion:** [run 1](../programs/5_calc/axion_run1.ax) · [run 2](../programs/5_calc/axion_run2.ax) · [run 3](../programs/5_calc/axion_run3.ax) · [run 4](../programs/5_calc/axion_run4.ax) · [run 5](../programs/5_calc/axion_run5.ax)
- **Python:** [run 1](../programs/5_calc/python_run1.py) · [run 2](../programs/5_calc/python_run2.py) · [run 3](../programs/5_calc/python_run3.py) · [run 4](../programs/5_calc/python_run4.py) · [run 5](../programs/5_calc/python_run5.py)

These are the programs that were then run on the [spoiled data](../spoiled_data.md#task-5).
