# Benchmark: what happens when the data is bad

**The question:** a model writes a program, then the program meets data it did not expect.
Does it stop, or does it quietly print a wrong answer?

**The short answer:**

| Bad data | Axion | Python |
|---|---|---|
| Wrong type, `null`, missing or wrong shape | **stopped 160 of 160** | stopped 117 of 160, **answered silently 41** |
| Inputs built to hang it | **stopped 10 of 10** | **hung 10 of 10** |
| An extra field it does not need | refused 25 of 25 | **right 25 of 25** |

Same tasks, same model, same data for both languages. Every number here can be re-run with one command (below).

---

## How it was done

**1. Five tasks** from someone who does not know Axion. Real work, not toy examples:

| # | Task | What the program must do |
|---|---|---|
| 1 | [Server log report](tasks/1_log.md) | parse log lines, count levels, errors by hour and by module |
| 2 | [Payment schedule](tasks/2_schedule.md) | split an amount into monthly payments to the kopeck |
| 3 | [Reconciling two exports](tasks/3_reconcile.md) | compare records by id: case, spaces, comma decimals, duplicates |
| 4 | [Sales analysis](tasks/4_sales.md) | weekly sums, median, moving average, best 4 days |
| 5 | [Expression calculator](tasks/5_calc.md) | tokenizer and parser: `+ - * / ^`, parentheses, errors with positions |

**2. Claude Sonnet wrote each task 5 times in Axion and 5 times in Python.** Up to 6 attempts; only the error text went back to the model.
Both languages solved **25 of 25**. These 50 programs are in [`programs/`](programs).

**3. Every program met spoiled data.** [63 datasets](spoiled_data.md), written *before* any program ran and never changed:
a number sent as text, `true` instead of a number, a missing list, 31 February, `9 ^ 9 ^ 9`, an extra field, 100,000 log lines.
Each program ran on every dataset of its task, in its own process, with 10 seconds and 4 GB at most.
**630 runs.** A script, not a person, recorded each outcome in [`results.csv`](results.csv).

---

## One example

Task 4, sales by day. The second day arrives as `true` instead of a number.

**Python** (all 5 programs) printed a normal-looking report. It counted `true` as `1`:

```text
1. Суммы по неделям: 106, 120, 40
2. Среднее: 16.63   Медиана: 18.50
...
```

**Axion** (all 5 programs) refused before the first line ran:

```text
ERROR R407 line 1:1
input sales: list of number
Input data: sales[1] must be number, got true/false.
```

The Python report looks right and is wrong. Nobody would notice.

---

## All results

| Kind of data | Runs | Axion | Python |
|---|---|---|---|
| Wrong type, `null`, missing, wrong shape | 160 | stopped 160 | stopped 117 · own error line 2 · **answered silently 41** |
| A value the task promised never to send (31 Feb, a negative amount) | 70 | stopped 33 · own error line 2 · answered silently 35 | stopped 28 · own error line 6 · answered silently 35 · hung 1 |
| Extreme values (`9 ^ 9 ^ 9`, 10 billion payments, 40-digit numbers) | 40 | stopped 37 · right 3 | stopped 6 · right 12 · answered silently 9 · wrong 3 · **hung 10** |
| An extra field | 25 | **stopped 25** | right 25 |
| Big but valid (100,000 log lines) | 20 | **stopped 15 by the step limit** · right 5 | right 20 |

**What the outcomes mean.** *stopped*: ended with an error. *answered silently*: printed an answer although no right answer exists. *right / wrong*: the data was valid and the answer is known. *own error line*: the program printed the error message the task asked for. *hung*: no end in 10 seconds.

---

## Where Axion loses

- **Extra fields.** Real data from other services nearly always carries fields a program does not need. Axion refuses it; Python just works.
- **Big valid data.** With the default limit of 1,000,000 steps Axion gives up on 15 of 20. The limit can be raised, but Axion is about 50× slower than Python.
- **Meaning inside the right type** (31 February, a negative amount): a draw, 35 silent answers each. Axion checks types, not meaning.
- **A weaker model.** On the same five tasks Claude Haiku solved 3 of 5 in Axion and 5 of 5 in Python.
- **Cost.** The Axion cheat sheet goes into every request: about 3× more input tokens.

## Limits of this test

- One model (Claude Sonnet), five tasks.
- The spoiled data was written by the authors of Axion (before the runs, but still by them).
- The Python programs were not asked to validate their input. They could; the difference is what happens **by default**.
- The output labels of the tasks are in Russian, as their author wrote them. The models saw exactly that.

---

## Check it yourself

From the repository root:

```
python benchmark/run.py
```

About 2–5 minutes. It runs all 630 again, rewrites `results.csv` and prints the table above. No model and no key needed: it uses the stored programs.
On macOS and Windows the 4 GB memory cap per run is not available, so it is skipped; the 10-second limit still applies.

## Files

```
benchmark/
├── README.md            this page
├── tasks/               the five tasks, exactly as the model received them
├── programs/            the 50 programs Claude Sonnet wrote (axion_run1.ax … python_run5.py)
├── spoiled_data.md      the 63 spoiled datasets, one table
├── data/                the same datasets as compressed JSON, for run.py
├── results.csv          every one of the 630 runs: program, data, outcome, seconds
└── run.py               re-runs everything
```

*Measured in October 2026 with Axion 0.3. The original run (5 October) differed in one place: six extreme-number cases gave a wrong answer in Axion; a number past 28 digits now stops the program instead.*
