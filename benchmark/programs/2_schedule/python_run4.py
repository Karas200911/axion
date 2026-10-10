import sys
import json
import calendar
from decimal import Decimal

d = json.loads(sys.stdin.read())
total = Decimal(str(d["total"]).strip())
n = int(d["n"])
start = str(d["start"]).strip()

if n < 1:
    print("error: n must be 1 or more")
elif total < 0:
    print("error: total must not be negative")
elif (total * 100) != (total * 100).to_integral_value():
    print("error: total has fractions of a kopeck")
else:
    cents = int((total * 100).to_integral_value())
    y, m, day = (int(x) for x in start.split("-"))
    base, rem = divmod(cents, n)
    out = []
    for i in range(n):
        amt = base + (1 if i < rem else 0)
        idx = (m - 1) + i
        yy = y + idx // 12
        mm = idx % 12 + 1
        dd = min(day, calendar.monthrange(yy, mm)[1])
        s = "%d.%02d" % (amt // 100, amt % 100)
        out.append("  %04d-%02d-%02d%s" % (yy, mm, dd, s.rjust(9)))
    print("\n".join(out))
