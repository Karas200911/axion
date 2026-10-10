import sys
import json
from fractions import Fraction
from bisect import bisect_left


def fmt2(fr):
    fr = Fraction(fr)
    neg = fr < 0
    if neg:
        fr = -fr
    scaled = fr * 100
    q = scaled.numerator // scaled.denominator
    rem = scaled - q
    if rem >= Fraction(1, 2):
        q += 1
    if neg and q != 0:
        return "-%d.%02d" % (q // 100, q % 100)
    return "%d.%02d" % (q // 100, q % 100)


def weekly_sums(s):
    if not s:
        return "нет"
    res = []
    for i in range(0, len(s), 7):
        res.append(str(sum(s[i:i + 7])))
    return ", ".join(res)


def avg_median(s):
    if not s:
        return "нет", "нет"
    n = len(s)
    avg = Fraction(sum(s), n)
    t = sorted(s)
    if n % 2 == 1:
        med = Fraction(t[n // 2])
    else:
        med = Fraction(t[n // 2 - 1] + t[n // 2], 2)
    return fmt2(avg), fmt2(med)


def moving_avg(s):
    n = len(s)
    if n < 3:
        return "нет"
    cur = s[0] + s[1] + s[2]
    out = [fmt2(Fraction(cur, 3))]
    for i in range(3, n):
        cur += s[i] - s[i - 3]
        out.append(fmt2(Fraction(cur, 3)))
    return " ".join(out)


def best4(s):
    n = len(s)
    if n < 4:
        return "нет"
    cur = s[0] + s[1] + s[2] + s[3]
    best = cur
    bi = 0
    for i in range(4, n):
        cur += s[i] - s[i - 4]
        if cur > best:
            best = cur
            bi = i - 3
    return "дни %d-%d, сумма %d" % (bi + 1, bi + 4, best)


def longest_rise(s):
    n = len(s)
    if n == 0:
        return "нет"
    best_len = 1
    best_start = 0
    start = 0
    for i in range(1, n):
        if s[i] > s[i - 1]:
            length = i - start + 1
            if length > best_len:
                best_len = length
                best_start = start
        else:
            start = i
    seg = s[best_start:best_start + best_len]
    return "дни %d-%d (%s)" % (best_start + 1, best_start + best_len,
                               ", ".join(str(x) for x in seg))


def top3(s):
    if not s:
        return "нет"
    top = []  # list of (sales, day), best first
    for i, v in enumerate(s):
        day = i + 1
        pos = len(top)
        while pos > 0 and top[pos - 1][0] < v:
            pos -= 1
        if pos < 3:
            top.insert(pos, (v, day))
            if len(top) > 3:
                top.pop()
    return ", ".join("день %d (%d)" % (d, v) for v, d in top)


def count_ge20(s):
    if not s:
        return 0
    t = sorted(s)
    return len(t) - bisect_left(t, 20)


def main():
    data = json.loads(sys.stdin.read())
    s = data.get("sales", [])
    a, m = avg_median(s)
    print("1. Суммы по неделям: " + weekly_sums(s))
    print("2. Среднее: " + a + "   Медиана: " + m)
    print("3. Скользящее среднее: " + moving_avg(s))
    print("4. Лучшие 4 дня подряд: " + best4(s))
    print("5. Самый длинный рост подряд: " + longest_rise(s))
    print("6. Топ-3 дня: " + top3(s))
    print("7. Дней с продажами не меньше 20: " + str(count_ge20(s)))


main()
