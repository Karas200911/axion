import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from axionlang import run_source  # noqa: E402
from axionlang.engine.inputs import parse_json  # noqa: E402
from axionlang.engine.policy import Policy  # noqa: E402


def run(source, data=None, policy=None, base_dir=None):
    """data: JSON text; policy: a dict as in policy.json."""
    return run_source(source, parse_json(data) if data is not None else None,
                      Policy.from_dict(policy) if policy is not None else None, base_dir)


class AxionTest(unittest.TestCase):
    def assertOutput(self, source, expected, **launch):
        code, out = run(source, **launch)
        self.assertEqual(code, 0, "program failed:\n" + "\n".join(out))
        self.assertEqual(out, expected)

    def assertError(self, source, code, printed_before=(), **launch):
        """The program fails and one of its errors has this code; nothing else is printed first.

        Returns the lines of that error (one program may report up to 5 different errors).
        """
        exit_code, out = run(source, **launch)
        self.assertEqual(exit_code, 1, f"expected {code}, program succeeded: {out}")
        header = [i for i, line in enumerate(out) if line.startswith("ERROR ")]
        self.assertTrue(header, "no error was reported")
        self.assertEqual(out[:header[0]], list(printed_before), "unexpected output before error")
        for n, start in enumerate(header):
            if out[start].startswith(f"ERROR {code} "):
                stop = header[n + 1] if n + 1 < len(header) else len(out)
                block = out[start:stop]
                while block and not block[-1]:
                    block.pop()                       # the blank line between two errors
                return block
        self.fail(f"expected {code}, got:\n" + "\n".join(out[header[0]:]))

    def assertErrors(self, source, codes, **launch):
        """The program reports exactly these error codes, in this order."""
        exit_code, out = run(source, **launch)
        self.assertEqual(exit_code, 1, f"expected {codes}, program succeeded: {out}")
        found = [line.split()[1] for line in out if line.startswith("ERROR ")]
        self.assertEqual(found, list(codes), "\n".join(out))
        return out
