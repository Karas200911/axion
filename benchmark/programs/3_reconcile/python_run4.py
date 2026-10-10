import sys
import json
from decimal import Decimal


def load(records):
    data = {}
    counts = {}
    total = Decimal(0)
    for r in records:
        i = r["id"].strip().upper()
        d = r["date"]
        amt = Decimal(r["amount"].strip().replace(",", "."))
        counts[i] = counts.get(i, 0) + 1
        if i not in data:
            data[i] = (d, amt)
            total += amt
    dups = {i: c for i, c in counts.items() if c > 1}
    return data, dups, total


def main():
    obj = json.loads(sys.stdin.read())
    a, da, ta = load(obj["a"])
    b, db, tb = load(obj["b"])
    same = []
    diff = []
    for i in sorted(a):
        if i in b:
            if a[i] == b[i]:
                same.append(i)
            else:
                diff.append(i)
    only_a = sorted(i for i in a if i not in b)
    only_b = sorted(i for i in b if i not in a)
    out = []
    out.append("Совпало: %d" % len(same))
    if same:
        out.append("  " + ", ".join(same))
    out.append("")
    out.append("Расхождения: %d" % len(diff))
    for i in diff:
        da_, aa = a[i]
        db_, ab = b[i]
        if aa != ab:
            out.append("  %s  сумма: %.2f / %.2f (разница %.2f)" % (i, aa, ab, abs(aa - ab)))
        else:
            out.append("  %s  дата: %s / %s" % (i, da_, db_))
    out.append("")
    out.append("Только в A: %d" % len(only_a))
    for i in only_a:
        d, m = a[i]
        out.append("  %s  %s%9s" % (i, d, "%.2f" % m))
    out.append("")
    out.append("Только в B: %d" % len(only_b))
    for i in only_b:
        d, m = b[i]
        out.append("  %s  %s%9s" % (i, d, "%.2f" % m))
    out.append("")
    if da:
        out.append("Дубликаты в A: " + ", ".join("%s (%d раза)" % (i, da[i]) for i in sorted(da)))
        out.append("")
    if db:
        out.append("Дубликаты в B: " + ", ".join("%s (%d раза)" % (i, db[i]) for i in sorted(db)))
        out.append("")
    out.append("Итого A: %.2f   Итого B: %.2f   Разница: %.2f" % (ta, tb, ta - tb))
    sys.stdout.write("\n".join(out) + "\n")


main()
