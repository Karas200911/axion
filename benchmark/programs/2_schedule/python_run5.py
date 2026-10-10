import sys, json, calendar
from decimal import Decimal

data = json.loads(sys.stdin.read())
n = int(data["n"])
total = Decimal(str(data["total"]).strip())
y, m, d = (int(x) for x in str(data["start"]).split("-"))

if n < 1:
    print("error: n must be 1 or more")
elif total < 0:
    print("error: total must not be negative")
elif (total * 100) != (total * 100).to_integral_value():
    print("error: total has fractions of a kopeck")
else:
    cents = int((total * 100).to_integral_value())
    base, rem = divmod(cents, n)
    out = []
    for i in range(n):
        c = base + (1 if i < rem else 0)
        idx = (m - 1) + i
        yy = y + idx // 12
        mm = idx % 12 + 1
        dd = min(d, calendar.monthrange(yy, mm)[1])
        amt = "%d.%02d" % (c // 100, c % 100)
        out.append("  %04d-%02d-%02d%9s" % (yy, mm, dd, amt))
    print("\n".join(out))
