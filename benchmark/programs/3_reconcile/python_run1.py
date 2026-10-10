import sys
import json
from decimal import Decimal


def load(records):
    data = {}
    counts = {}
    total = Decimal(0)
    for r in records:
        i = r["id"].strip().upper()
        d = r["date"].strip()
        amt = Decimal(r["amount"].strip().replace(",", "."))
        if i in data:
            counts[i] += 1
        else:
            data[i] = (d, amt)
            counts[i] = 1
            total += amt
    return data, counts, total


def f(x):
    return "{:.2f}".format(x)


def main():
    obj = json.loads(sys.stdin.read())
    a, ca, ta = load(obj["a"])
    b, cb, tb = load(obj["b"])
    same = []
    diff = []
    for i in sorted(a):
        if i in b:
            if a[i] == b[i]:
                same.append(i)
            else:
                diff.append(i)
    only_a = [i for i in sorted(a) if i not in b]
    only_b = [i for i in sorted(b) if i not in a]
    out = []
    out.append("Совпало: %d" % len(same))
    if same:
        out.append("  " + ", ".join(same))
    out.append("")
    out.append("Расхождения: %d" % len(diff))
    for i in diff:
        da, aa = a[i]
        db, ab = b[i]
        if aa != ab:
            out.append("  %s  сумма: %s / %s (разница %s)" % (i, f(aa), f(ab), f(abs(aa - ab))))
        else:
            out.append("  %s  дата: %s / %s" % (i, da, db))
    out.append("")
    out.append("Только в A: %d" % len(only_a))
    for i in only_a:
        out.append("  %s  %s%s" % (i, a[i][0], f(a[i][1]).rjust(9)))
    out.append("")
    out.append("Только в B: %d" % len(only_b))
    for i in only_b:
        out.append("  %s  %s%s" % (i, b[i][0], f(b[i][1]).rjust(9)))
    out.append("")
    for name, c in (("A", ca), ("B", cb)):
        dups = [i for i in sorted(c) if c[i] > 1]
        if dups:
            out.append("Дубликаты в %s: " % name + ", ".join("%s (%d раза)" % (i, c[i]) for i in dups))
            out.append("")
    out.append("Итого A: %s   Итого B: %s   Разница: %s" % (f(ta), f(tb), f(ta - tb)))
    print("\n".join(out))


main()
