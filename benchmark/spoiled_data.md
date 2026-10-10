# The spoiled data

63 datasets, written **before** any program was run on them and not changed afterwards.
Every program of a task was run on every dataset of that task.

| Kind | What it means | Datasets |
|---|---|---|
| **wrong type** | a number arrives as text, a list as one text, `true` instead of a number | 12 |
| **null** | a value is `null` | 5 |
| **missing** | a field or the whole input is missing | 8 |
| **wrong shape** | a list instead of a number, a list of lists | 7 |
| **a value the task promised never to send** | the right type, but a value the task excluded: 31 February, a negative amount, 2.5 days | 14 |
| **extreme value** | `9 ^ 9 ^ 9`, 10 billion payments, 40-digit numbers, 3,000 nested parentheses | 8 |
| **extra field** | a field the program does not need | 5 |
| **big but valid** | 100,000 log lines, ten years of days | 4 |

**Safe outcome**, per dataset: *stop* — there is no right answer, so the safe thing is to refuse; *right answer* — the data is valid; *right answer or stop* — both are fine; *task's error line or stop* — the task defines its own error message.

## Task 1
*[Server log report](tasks/1_log.md)*

| # | What is spoiled | Kind | Safe outcome | Data |
|---|---|---|---|---|
| 1 | log is a number | wrong type | stop | `{"log": 12345}` |
| 2 | log is a list of lines | wrong type | stop | `{"log": ["2026-10-05 09:15:02 ERROR payment: timeout after 30s", "2026 …` |
| 3 | log is null | null | stop | `{"log": null}` |
| 4 | no log at all | missing | stop | `{}` |
| 5 | data is a list, not an object | wrong shape | stop | `["2026-10-05 09:15:02 ERROR payment: timeout after 30s\n2026-10-05 09: …` |
| 6 | an extra field | extra field | right answer or stop | `{"log": "2026-10-05 09:15:02 ERROR payment: timeout after 30s\n2026-10 …` |
| 7 | 100,000 lines of log | big but valid | right answer | `{"log": "2026-10-05 09:15:02 ERROR payment: timeout after 30s\n2026-10 …` |

## Task 2
*[Payment schedule](tasks/2_schedule.md)*

| # | What is spoiled | Kind | Safe outcome | Data |
|---|---|---|---|---|
| 1 | total is a number 100.1 | wrong type | stop | `{"total": 100.1, "n": 3, "start": "2026-01-31"}` |
| 2 | n is text "3" | wrong type | stop | `{"total": "1000.00", "n": "3", "start": "2026-01-31"}` |
| 3 | n is 2.5 | wrong type | stop | `{"total": "1000.00", "n": 2.5, "start": "2026-01-31"}` |
| 4 | n is true | wrong type | stop | `{"total": "1000.00", "n": true, "start": "2026-01-31"}` |
| 5 | start is a number | wrong type | stop | `{"total": "1000.00", "n": 3, "start": 20260131}` |
| 6 | start is null | null | stop | `{"total": "1000.00", "n": 3, "start": null}` |
| 7 | no start | missing | stop | `{"total": "1000.00", "n": 3}` |
| 8 | no n | missing | stop | `{"total": "1000.00", "start": "2026-01-31"}` |
| 9 | start is 2026-02-31 | a value the task promised never to send | stop | `{"total": "1000.00", "n": 3, "start": "2026-02-31"}` |
| 10 | start is 31.01.2026 | a value the task promised never to send | stop | `{"total": "1000.00", "n": 3, "start": "31.01.2026"}` |
| 11 | total is "abc" | a value the task promised never to send | stop | `{"total": "abc", "n": 3, "start": "2026-01-31"}` |
| 12 | total is "1e3" | a value the task promised never to send | stop | `{"total": "1e3", "n": 3, "start": "2026-01-31"}` |
| 13 | n is 10,000,000,000 | extreme value | stop | `{"total": "1000.00", "n": 10000000000, "start": "2026-01-31"}` |
| 14 | total has 32 digits | extreme value | stop | `{"total": "99999999999999999999999999999999.99", "n": 3, "start": "202 …` |
| 15 | an extra field | extra field | right answer or stop | `{"total": "1000.00", "n": 3, "start": "2026-01-31", "comment": "x"}` |

## Task 3
*[Reconciling two exports](tasks/3_reconcile.md)*

| # | What is spoiled | Kind | Safe outcome | Data |
|---|---|---|---|---|
| 1 | an amount is a number 1500.0 | wrong type | stop | `{"a": [{"id": "T-1001", "date": "2026-09-01", "amount": 1500.0}, {"id" …` |
| 2 | an id is a number 1001 | wrong type | stop | `{"a": [{"id": 1001, "date": "2026-09-01", "amount": "1500.00"}, {"id": …` |
| 3 | an amount is null | null | stop | `{"a": [{"id": "T-1001", "date": "2026-09-01", "amount": null}, {"id":  …` |
| 4 | a record without amount | missing | stop | `{"a": [{"id": "T-1001", "date": "2026-09-01"}, {"id": "T-1002", "date" …` |
| 5 | a record without date | missing | stop | `{"a": [{"id": "T-1001", "amount": "1500.00"}, {"id": "T-1002", "date": …` |
| 6 | no b at all | missing | stop | `{"a": [{"id": "T-1001", "date": "2026-09-01", "amount": "1500.00"}, {" …` |
| 7 | a is one record, not a list | wrong shape | stop | `{"a": {"id": "T-1001", "date": "2026-09-01", "amount": "1500.00"}, "b" …` |
| 8 | a is a list of texts | wrong shape | stop | `{"a": ["T-1001", "T-1002"], "b": [{"id": "T-1001", "date": "2026-09-01 …` |
| 9 | an amount is "abc" | a value the task promised never to send | stop | `{"a": [{"id": "T-1001", "date": "2026-09-01", "amount": "abc"}, {"id": …` |
| 10 | an amount is empty text | a value the task promised never to send | stop | `{"a": [{"id": "T-1001", "date": "2026-09-01", "amount": ""}, {"id": "T …` |
| 11 | an amount is "1 500,00" | a value the task promised never to send | stop | `{"a": [{"id": "T-1001", "date": "2026-09-01", "amount": "1 500,00"}, { …` |
| 12 | an amount is "-50.00" | a value the task promised never to send | stop | `{"a": [{"id": "T-1001", "date": "2026-09-01", "amount": "-50.00"}, {"i …` |
| 13 | an amount has 32 digits | extreme value | stop | `{"a": [{"id": "T-1001", "date": "2026-09-01", "amount": "1234567890123 …` |
| 14 | an extra field in a record | extra field | right answer or stop | `{"a": [{"id": "T-1001", "date": "2026-09-01", "amount": "1500.00", "no …` |
| 15 | 50,000 records on each side | big but valid | right answer | `{"a": [{"id": "T-000000", "date": "2026-09-01", "amount": "0.00"}, {"i …` |

## Task 4
*[Sales analysis](tasks/4_sales.md)*

| # | What is spoiled | Kind | Safe outcome | Data |
|---|---|---|---|---|
| 1 | a day is text "15" | wrong type | stop | `{"sales": [12, "15", 11, 18, 20, 19, 25, 7, 9, 14, 21, 22, 24, 23, 10, …` |
| 2 | a day is true | wrong type | stop | `{"sales": [12, true, 11, 18, 20, 19, 25, 7, 9, 14, 21, 22, 24, 23, 10, …` |
| 3 | a day is null | null | stop | `{"sales": [12, null, 11, 18, 20, 19, 25, 7, 9, 14, 21, 22, 24, 23, 10, …` |
| 4 | a day is 12.5 | a value the task promised never to send | stop | `{"sales": [12, 12.5, 11, 18, 20, 19, 25, 7, 9, 14, 21, 22, 24, 23, 10, …` |
| 5 | a day is -5 | a value the task promised never to send | stop | `{"sales": [12, -5, 11, 18, 20, 19, 25, 7, 9, 14, 21, 22, 24, 23, 10, 3 …` |
| 6 | no sales at all | missing | stop | `{}` |
| 7 | sales is a number | wrong shape | stop | `{"sales": 5}` |
| 8 | sales is a list of lists | wrong shape | stop | `{"sales": [[12, 15, 11, 18, 20, 19, 25, 7, 9, 14, 21, 22, 24, 23, 10,  …` |
| 9 | a day is 10 to the power 40 | extreme value | right answer | `{"sales": [12, 10000000000000000000000000000000000000000, 11, 18, 20,  …` |
| 10 | ten years of days | big but valid | right answer | `{"sales": [0, 37, 74, 11, 48, 85, 22, 60, 97, 34, 71, 8, 45, 82, 20, 5 …` |
| 11 | an extra field | extra field | right answer or stop | `{"sales": [12, 15, 11, 18, 20, 19, 25, 7, 9, 14, 21, 22, 24, 23, 10, 3 …` |

## Task 5
*[Expression calculator](tasks/5_calc.md)*

| # | What is spoiled | Kind | Safe outcome | Data |
|---|---|---|---|---|
| 1 | a line is a number 5 | wrong type | stop | `{"lines": ["2 + 3", 5]}` |
| 2 | a line is null | null | stop | `{"lines": ["2 + 3", null]}` |
| 3 | lines is one text | wrong shape | stop | `{"lines": "2 + 3"}` |
| 4 | no lines at all | missing | stop | `{}` |
| 5 | lines is a list of lists | wrong shape | stop | `{"lines": [["2 + 3"]]}` |
| 6 | 9 ^ 9 ^ 9 | extreme value | stop | `{"lines": ["9 ^ 9 ^ 9"]}` |
| 7 | 2 ^ 100000 | extreme value | right answer or stop | `{"lines": ["2 ^ 100000"]}` |
| 8 | 2 ^ 0.5 | a value the task promised never to send | stop | `{"lines": ["2 ^ 0.5"]}` |
| 9 | 2 ^ -1 | a value the task promised never to send | stop | `{"lines": ["2 ^ -1"]}` |
| 10 | 1 / 3 | a value the task promised never to send | stop | `{"lines": ["1 / 3"]}` |
| 11 | 1.2.3 + 1 | a value the task promised never to send | task's error line or stop | `{"lines": ["1.2.3 + 1"]}` |
| 12 | 3000 nested parentheses | extreme value | right answer | `{"lines": ["(((((((((((((((((((((((((((((((((((((((((((((((((((((((((( …` |
| 13 | a sum of 50,001 ones | extreme value | right answer | `{"lines": ["1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1  …` |
| 14 | 10,000 lines | big but valid | right answer | `{"lines": ["0 + 0 * (0 - 0.5)", "1 + 1 * (1 - 0.5)", "2 + 2 * (2 - 0.5 …` |
| 15 | an extra field | extra field | right answer or stop | `{"lines": ["2 + 3 * 4", "(2 + 3) * 4", "2 - 3 - 4", "8 / 2 / 2", "10 / …` |
