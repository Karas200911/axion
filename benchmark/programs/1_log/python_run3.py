import sys
import json
import re

data = json.loads(sys.stdin.read())
log = data["log"]
pat = re.compile(r"^([0-9]{4}-[0-9]{2}-[0-9]{2}) ([0-9]{2}):[0-9]{2}:[0-9]{2} ([A-Za-z]+) ([A-Za-z0-9_]+):(.*)$", re.S)
levels = {}
hours = {}
mods = {}
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
        mods[mod] = mods.get(mod, 0) + 1

out = ["Уровни:"]
for k, v in sorted(levels.items(), key=lambda x: (-x[1], x[0])):
    out.append("  " + k.ljust(13) + str(v))
out.append("")
out.append("Ошибки по часам:")
for k in sorted(hours):
    out.append("  " + k[0] + " " + k[1] + ":00    " + str(hours[k]))
out.append("")
out.append("Ошибки по модулям:")
for k, v in sorted(mods.items(), key=lambda x: (-x[1], x[0])):
    out.append("  " + k.ljust(13) + str(v))
out.append("")
out.append("Пропущено строк: " + str(skipped))
sys.stdout.write("\n".join(out) + "\n")
