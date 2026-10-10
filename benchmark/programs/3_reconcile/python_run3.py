import sys
import json
from decimal import Decimal


def load(records):
    data = {}
    counts = {}
    for r in records:
        i = r["id"].strip().upper()
        d = r["date"]
        amt = Decimal(r["amount"].strip().replace(",", "."))
        counts[i] = counts.get(i, 0) + 1
        if i not in data:
            data[i] = (d, amt)
    return data, counts


def fmt(x):
    return "{:.2f}".format(x)


def main():
    obj = json.load(sys.stdin)
    a, ca = load(obj["a"])
    b, cb = load(obj["b"])
    out = []
    same = []
    diff = []
    for i in sorted(a):
        if i in b:
            if a[i] == b[i]:
                same.append(i)
            else:
                diff.append(i)
    out.append("Совпало: %d" % len(same))
    if same:
        out.append("  " + ", ".join(same))
    out.append("")
    out.append("Расхождения: %d" % len(diff))
    for i in diff:
        da, aa = a[i]
        db, ab = b[i]
        if aa != ab:
            out.append("  %s  сумма: %s / %s (разница %s)" % (i, fmt(aa), fmt(ab), fmt(abs(aa - ab))))
        else:
            out.append("  %s  дата: %s / %s" % (i, da, db))
    for name, x, y in (("A", a, b), ("B", b, a)):
        only = [i for i in sorted(x) if i not in y]
        out.append("")
        out.append("Только в %s: %d" % (name, len(only)))
        for i in only:
            d, amt = x[i]
            out.append("  %s  %s%s" % (i, d, fmt(amt).rjust(9)))
    out.append("")
    for name, c in (("A", ca), ("B", cb)):
        dups = [i for i in sorted(c) if c[i] > 1]
        if dups:
            out.append("Дубликаты в %s: " % name + ", ".join("%s (%d раза)" % (i, c[i]) for i in dups))
            out.append("")
    sa = sum((v[1] for v in a.values()), Decimal(0))
    sb = sum((v[1] for v in b.values()), Decimal(0))
    out.append("Итого A: %s   Итого B: %s   Разница: %s" % (fmt(sa), fmt(sb), fmt(sa - sb)))
    print("\n".join(out))


main()
