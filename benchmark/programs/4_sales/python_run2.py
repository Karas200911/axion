import sys
import json
from bisect import bisect_left


def weekly_sums(s):
    res = []
    for i in range(0, len(s), 7):
        res.append(str(sum(s[i:i + 7])))
    return "1. Суммы по неделям: " + (", ".join(res) if res else "нет")


def avg_median(s):
    n = len(s)
    if n == 0:
        return "2. Среднее: нет   Медиана: нет"
    avg = sum(s) / n
    t = sorted(s)
    if n % 2:
        med = float(t[n // 2])
    else:
        med = (t[n // 2 - 1] + t[n // 2]) / 2
    return "2. Среднее: %.2f   Медиана: %.2f" % (avg, med)


def moving(s):
    n = len(s)
    if n < 3:
        return "3. Скользящее среднее: нет"
    cur = s[0] + s[1] + s[2]
    out = ["%.2f" % (cur / 3)]
    for i in range(3, n):
        cur += s[i] - s[i - 3]
        out.append("%.2f" % (cur / 3))
    return "3. Скользящее среднее: " + " ".join(out)


def best4(s):
    n = len(s)
    if n < 4:
        return "4. Лучшие 4 дня подряд: нет"
    cur = s[0] + s[1] + s[2] + s[3]
    best = cur
    bi = 0
    for i in range(4, n):
        cur += s[i] - s[i - 4]
        if cur > best:
            best = cur
            bi = i - 3
    return "4. Лучшие 4 дня подряд: дни %d-%d, сумма %d" % (bi + 1, bi + 4, best)


def longest_rise(s):
    n = len(s)
    if n == 0:
        return "5. Самый длинный рост подряд: нет"
    bs, bl = 0, 1
    st = 0
    for i in range(1, n):
        if s[i] > s[i - 1]:
            ln = i - st + 1
            if ln > bl:
                bl = ln
                bs = st
        else:
            st = i
    vals = ", ".join(str(v) for v in s[bs:bs + bl])
    return "5. Самый длинный рост подряд: дни %d-%d (%s)" % (bs + 1, bs + bl, vals)


def top3(s):
    if not s:
        return "6. Топ-3 дня: нет"
    top = []
    for i, v in enumerate(s):
        pos = len(top)
        while pos > 0 and top[pos - 1][0] < v:
            pos -= 1
        if pos < 3:
            top.insert(pos, (v, i + 1))
            if len(top) > 3:
                top.pop()
    return "6. Топ-3 дня: " + ", ".join("день %d (%d)" % (d, v) for v, d in top)


def count20(s):
    t = sorted(s)
    c = len(t) - bisect_left(t, 20)
    return "7. Дней с продажами не меньше 20: %d" % c


def main():
    data = json.loads(sys.stdin.read())
    s = data.get("sales", [])
    lines = [
        weekly_sums(s),
        avg_median(s),
        moving(s),
        best4(s),
        longest_rise(s),
        top3(s),
        count20(s),
    ]
    print("\n".join(lines))


main()
