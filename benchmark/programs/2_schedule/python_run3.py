import sys
import json
import calendar
from decimal import Decimal


def main():
    data = json.loads(sys.stdin.read())
    total = Decimal(str(data["total"]).strip())
    n = int(data["n"])
    start = str(data["start"]).strip()
    if n < 1:
        print("error: n must be 1 or more")
        return
    if total < 0:
        print("error: total must not be negative")
        return
    scaled = total * 100
    if scaled != scaled.to_integral_value():
        print("error: total has fractions of a kopeck")
        return
    cents = int(scaled)
    y, m, d = (int(p) for p in start.split("-"))
    base, rem = divmod(cents, n)
    out = []
    for i in range(n):
        amount = base + (1 if i < rem else 0)
        idx = (m - 1) + i
        yy = y + idx // 12
        mm = idx % 12 + 1
        dd = min(d, calendar.monthrange(yy, mm)[1])
        s = "%d.%02d" % (amount // 100, amount % 100)
        out.append("  %04d-%02d-%02d%s" % (yy, mm, dd, s.rjust(9)))
    print("\n".join(out))


main()
