"""Command line: python -m axionlang program.ax [--input data.json] [--policy policy.json]

Files named in `read` are relative to the folder of the program.
Exit codes: 0 ok, 1 Axion error, 2 problem with the launch itself (missing file, bad
policy or data file, or a bug in Axion).
"""

import json
import sys
from pathlib import Path

from .engine.inputs import parse_json
from .engine.policy import Policy, PolicyError
from .engine.runner import run_source


def main(argv):
    usage = "Usage: python -m axionlang <program.ax> [--input data.json] [--policy policy.json]"
    if not argv:
        print(usage)
        return 2
    program_path, options = Path(argv[0]), {}
    rest = argv[1:]
    while rest:
        if len(rest) < 2 or rest[0] not in ("--input", "--policy"):
            print(usage)
            return 2
        options[rest[0]] = Path(rest[1])
        rest = rest[2:]
    for path in [program_path, *options.values()]:
        if not path.exists():
            print(f"File not found: {path}")
            return 2
    try:
        data = parse_json(options["--input"].read_text(encoding="utf-8")) if "--input" in options else None
    except ValueError as exc:
        print(f"DATA FILE ERROR: {options['--input']} is not valid JSON: {exc}")
        return 2
    try:
        policy = (Policy.from_dict(json.loads(options["--policy"].read_text(encoding="utf-8")))
                  if "--policy" in options else Policy())
    except (ValueError, PolicyError) as exc:
        print(f"POLICY FILE ERROR: {exc}")
        return 2
    try:
        text = program_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print(f"PROGRAM FILE ERROR: {program_path} is not a UTF-8 text file.")
        return 2
    try:
        code, lines = run_source(text, data, policy, base_dir=program_path.resolve().parent)
    except Exception as exc:  # a bug in Axion, never shown as an Axion error
        print(f"INTERNAL ERROR: {type(exc).__name__}: {exc}")
        return 2
    for line in lines:
        print(line)
    return code



def cli():
    """Entry point of the `axionlang` command."""
    raise SystemExit(main(sys.argv[1:]))


if __name__ == "__main__":
    cli()
