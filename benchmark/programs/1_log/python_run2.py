import sys
import json
import re

data = json.loads(sys.stdin.read())
log = data["log"]

pat = re.compile(r'^(\d{4}-\d{2}-\d{2}) (\d{2}):\d{2}:\d{2} ([A-Za-z]+) ([A-Za-z0-9_]+):(.*)$', re.ASCII)

levels = {}
hours = {}
modules = {}
skipped = 0

for line in log.split("\n"):
    if line.strip() == "":
        continue
    m = pat.match(line)
    if not m:
        skipped += 1
        continue
    date, hh, lvl, mod = m.group(1), m.group(2), m.group(3).upper(), m.group(4)
    levels[lvl] = levels.get(lvl, 0) + 1
    if lvl == "ERROR":
        k = (date, hh)
        hours[k] = hours.get(k, 0) + 1
        modules[mod] = modules.get(mod, 0) + 1

out = []
out.append("Уровни:")
for name, c in sorted(levels.items(), key=lambda x: (-x[1], x[0])):
    out.append("  " + name.ljust(13) + str(c))
out.append("")
out.append("Ошибки по часам:")
for (date, hh), c in sorted(hours.items()):
    out.append("  " + date + " " + hh + ":00    " + str(c))
out.append("")
out.append("Ошибки по модулям:")
for name, c in sorted(modules.items(), key=lambda x: (-x[1], x[0])):
    out.append("  " + name.ljust(13) + str(c))
out.append("")
out.append("Пропущено строк: " + str(skipped))
print("\n".join(out))
