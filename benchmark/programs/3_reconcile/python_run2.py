import sys
import json
from decimal import Decimal, ROUND_HALF_UP


def cents(s):
    d = Decimal(s.strip().replace(",", "."))
    return int((d * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def fmt(c):
    sign = "-" if c < 0 else ""
    c = abs(c)
    return "%s%d.%02d" % (sign, c // 100, c % 100)


def load(records):
    data = {}
    counts = {}
    total = 0
    for r in records:
        i = r["id"].strip().upper()
        d = r["date"].strip()
        c = cents(r["amount"])
        if i in data:
            counts[i] += 1
        else:
            data[i] = (d, c)
            counts[i] = 1
            total += c
    return data, counts, total


def main():
    obj = json.load(sys.stdin)
    a, ca, ta = load(obj["a"])
    b, cb, tb = load(obj["b"])
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
            d, c = x[i]
            out.append("  %s  %s%9s" % (i, d, fmt(c)))
    out.append("")
    for name, cnt in (("A", ca), ("B", cb)):
        dups = ["%s (%d раза)" % (i, cnt[i]) for i in sorted(cnt) if cnt[i] > 1]
        if dups:
            out.append("Дубликаты в %s: %s" % (name, ", ".join(dups)))
            out.append("")
    out.append("Итого A: %s   Итого B: %s   Разница: %s" % (fmt(ta), fmt(tb), fmt(ta - tb)))
    print("\n".join(out))


main()
