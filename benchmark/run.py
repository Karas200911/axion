"""Re-run the safety part of the benchmark: every program on every spoiled dataset.

    python benchmark/run.py          (from the repository root; about 2-5 minutes)

50 programs (5 tasks x 5 runs x 2 languages) x the spoiled datasets of their task = 630 runs.
Each run is a separate process with 10 seconds and 4 GB at most. The outcome of every run is
written to benchmark/results.csv and a summary is printed. Nothing here calls a model: the
programs are the ones Claude Sonnet wrote, stored in benchmark/programs/.
"""
import csv
import gzip
import json
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

try:
    import resource
except ImportError:          # Windows: no memory cap, the time limit still applies
    resource = None

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TIME_LIMIT = 10
MEMORY = 4 * 1024 ** 3
GROUPS = [
    ("TNMS", "Wrong type, null, missing or wrong shape"),
    ("V", "A value the task promised never to send"),
    ("X", "Extreme values"),
    ("E", "An extra field"),
    ("B", "Big but valid"),
]
KINDS = {"T": "wrong type", "N": "null", "M": "missing", "S": "wrong shape", "V": "promised never",
         "X": "extreme", "E": "extra field", "B": "big but valid"}


def limits():
    """The 4 GB cap per run. macOS does not allow it (and Windows has no `resource`):
    there the runs go without it, and the 10-second limit still applies."""
    if resource is not None:
        try:
            resource.setrlimit(resource.RLIMIT_AS, (MEMORY, MEMORY))
        except (ValueError, OSError):
            pass


def lines_of(text):
    out = text.split("\n")
    if out and out[-1] == "":
        out.pop()
    return out


def run_one(job):
    task, program, case = job
    lang = "axion" if program.suffix == ".ax" else "python"
    row = dict(task=task, program=program.name, language=lang, case=case["name"],
               kind=KINDS[case["kind"]], outcome="", seconds="", detail="")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        if lang == "python":
            (tmp / "program.py").write_text(program.read_text(encoding="utf-8"), encoding="utf-8")
            cmd, stdin = [sys.executable, "-X", "utf8", "-I", "program.py"], case["data"]
        else:
            (tmp / "program.ax").write_text(program.read_text(encoding="utf-8"), encoding="utf-8")
            (tmp / "data.json").write_text(case["data"], encoding="utf-8")
            cmd, stdin = [sys.executable, "-X", "utf8", "-m", "axionlang", "program.ax", "--input", "data.json"], ""
        started = time.time()
        try:
            done = subprocess.run(cmd, input=stdin, cwd=tmp, capture_output=True, encoding="utf-8",
                                  errors="replace", env={**os.environ, "PYTHONPATH": str(ROOT)},
                                  timeout=TIME_LIMIT, preexec_fn=limits if resource else None)
        except subprocess.TimeoutExpired:
            row.update(outcome="hung", seconds=TIME_LIMIT, detail=f"no end in {TIME_LIMIT} s")
            return row
        row["seconds"] = round(time.time() - started, 2)
    out, truth = lines_of(done.stdout), case["truth"]
    if done.returncode != 0:
        if lang == "axion":
            at = next((i for i, line in enumerate(out) if line.startswith("ERROR ")), None)
            if done.returncode != 1 or at is None:
                row.update(outcome="crashed", detail=(out[-1] if out else done.stderr.strip().split("\n")[-1])[:200])
            else:
                row.update(outcome="stopped", detail=" / ".join(out[at:at + 4])[:300])
        else:
            last = done.stderr.strip().split("\n")[-1] if done.stderr.strip() else f"exit code {done.returncode}"
            row.update(outcome="crashed" if done.returncode < 0 or last.startswith("MemoryError") else "stopped",
                       detail=last[:300])
        return row
    if isinstance(truth, list):
        row.update(outcome="right" if out == truth else "wrong", detail="" if out == truth else " | ".join(out[:3])[:300])
    elif truth.startswith("either:"):
        ok = out == json.loads(truth[7:])
        row.update(outcome="right" if ok else "wrong", detail="" if ok else " | ".join(out[:3])[:300])
    elif truth == "errline":
        ok = bool(out) and all(line.startswith("ошибка") for line in out)      # the task's own error lines
        row.update(outcome="own error line" if ok else "answered silently", detail=" | ".join(out[:3])[:300])
    else:
        own = bool(out) and all(line.startswith(("ошибка", "error")) for line in out)
        row.update(outcome="own error line" if own else "answered silently", detail=" | ".join(out[:4])[:300])
    return row


def summary(rows):
    order = ["stopped", "right", "own error line", "answered silently", "wrong", "hung", "crashed"]
    for kinds, title in GROUPS:
        names = [KINDS[k] for k in kinds]
        print(f"\n{title}")
        for lang in ("axion", "python"):
            mine = [r for r in rows if r["language"] == lang and r["kind"] in names]
            counts = {o: sum(1 for r in mine if r["outcome"] == o) for o in order}
            text = ", ".join(f"{o} {c}" for o, c in counts.items() if c)
            print(f"  {lang:<7} ({len(mine)} runs): {text}")


def main():
    with gzip.open(HERE / "data" / "spoiled_data.json.gz", "rt", encoding="utf-8") as f:
        cases = json.load(f)                      # compressed: the big datasets are 13 MB as text
    jobs = [(task, program, case)
            for task in sorted(cases)
            for program in sorted((HERE / "programs" / task).iterdir())
            for case in cases[task]]
    print(f"{len(jobs)} runs, two at a time...")
    started = time.time()
    with ThreadPoolExecutor(2) as pool:
        rows = list(pool.map(run_one, jobs))
    with open(HERE / "results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"done in {round(time.time() - started)} s; every run is in benchmark/results.csv")
    summary(rows)


if __name__ == "__main__":
    main()
