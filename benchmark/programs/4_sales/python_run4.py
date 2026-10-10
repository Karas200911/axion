import sys
import json
from fractions import Fraction
from bisect import bisect_left


def fmt(num, den=1):
    v = Fraction(num, den)
    neg = v < 0
    if neg:
        v = -v
    s = int((v * 100 + Fraction(1, 2)) // 1)
    res = "%d.%02d" % (s // 100, s % 100)
    if neg and s != 0:
        res = "-" + res
    return res


def weekly_sums(a):
    if not a:
        return "нет"
    sums = [sum(a[i:i + 7]) for i in range(0, len(a), 7)]
    return ", ".join(str(x) for x in sums)


def avg_median(a):
    if not a:
        return "нет", "нет"
    n = len(a)
    avg = fmt(sum(a), n)
    s = sorted(a)
    if n % 2:
        med = fmt(s[n // 2])
    else:
        med = fmt(s[n // 2 - 1] + s[n // 2], 2)
    return avg, med


def moving_avg(a):
    n = len(a)
    if n < 3:
        return "нет"
    res = []
    cur = a[0] + a[1] + a[2]
    res.append(fmt(cur, 3))
    for i in range(3, n):
        cur += a[i] - a[i - 3]
        res.append(fmt(cur, 3))
    return " ".join(res)


def best_four(a):
    n = len(a)
    if n < 4:
        return "нет"
    cur = a[0] + a[1] + a[2] + a[3]
    best = cur
    best_end = 3
    for i in range(4, n):
        cur += a[i] - a[i - 4]
        if cur > best:
            best = cur
            best_end = i
    return "дни %d-%d, сумма %d" % (best_end - 2, best_end + 1, best)


def longest_rise(a):
    n = len(a)
    if n == 0:
        return "нет"
    best_len = 1
    best_start = 0
    start = 0
    for i in range(1, n):
        if a[i] > a[i - 1]:
            pass
        else:
            start = i
        ln = i - start + 1
        if ln > best_len:
            best_len = ln
            best_start = start
    seg = a[best_start:best_start + best_len]
    return "дни %d-%d (%s)" % (best_start + 1, best_start + best_len,
                               ", ".join(str(x) for x in seg))


def top3(a):
    if not a:
        return "нет"
    top = []  # list of (value, day), best first
    for i, v in enumerate(a):
        day = i + 1
        pos = len(top)
        for j in range(len(top)):
            if v > top[j][0]:
                pos = j
                break
        if pos < 3:
            top.insert(pos, (v, day))
            if len(top) > 3:
                top.pop()
    return ", ".join("день %d (%d)" % (d, v) for v, d in top)


def count_ge20(a):
    s = sorted(a)
    return len(s) - bisect_left(s, 20)


def main():
    data = json.loads(sys.stdin.read())
    a = list(data.get("sales", []))
    avg, med = avg_median(a)
    out = [
        "1. Суммы по неделям: " + weekly_sums(a),
        "2. Среднее: " + avg + "   Медиана: " + med,
        "3. Скользящее среднее: " + moving_avg(a),
        "4. Лучшие 4 дня подряд: " + best_four(a),
        "5. Самый длинный рост подряд: " + longest_rise(a),
        "6. Топ-3 дня: " + top3(a),
        "7. Дней с продажами не меньше 20: " + str(count_ge20(a)),
    ]
    print("\n".join(out))


main()
