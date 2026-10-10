import sys
import json
import re
from collections import Counter

data = json.loads(sys.stdin.read())
log = data["log"]

pat = re.compile(r"([0-9]{4}-[0-9]{2}-[0-9]{2}) ([0-9]{2}):[0-9]{2}:[0-9]{2} ([A-Za-z]+) ([A-Za-z0-9_]+):(.*)", re.DOTALL)

levels = Counter()
hours = Counter()
modules = Counter()
skipped = 0

for line in log.split("\n"):
    if line.strip() == "":
        continue
    m = pat.fullmatch(line)
    if not m:
        skipped += 1
        continue
    date, hh, lvl, mod, _ = m.groups()
    lvl = lvl.upper()
    levels[lvl] += 1
    if lvl == "ERROR":
        hours[(date, hh)] += 1
        modules[mod] += 1

out = []
out.append("Уровни:")
for k, v in sorted(levels.items(), key=lambda kv: (-kv[1], kv[0])):
    out.append("  " + k.ljust(13) + str(v))
out.append("")
out.append("Ошибки по часам:")
for (d, h), v in sorted(hours.items()):
    out.append("  " + d + " " + h + ":00    " + str(v))
out.append("")
out.append("Ошибки по модулям:")
for k, v in sorted(modules.items(), key=lambda kv: (-kv[1], kv[0])):
    out.append("  " + k.ljust(13) + str(v))
out.append("")
out.append("Пропущено строк: " + str(skipped))
print("\n".join(out))
