import sys
import json
from bisect import bisect_left


def fmt(num, den):
    neg = (num < 0) != (den < 0)
    num, den = abs(num), abs(den)
    v = (2 * num * 100 + den) // (2 * den)
    s = "%d.%02d" % (v // 100, v % 100)
    if neg and v != 0:
        s = "-" + s
    return s


def weekly(sales):
    if not sales:
        return "1. Суммы по неделям: нет"
    parts = [str(sum(sales[i:i + 7])) for i in range(0, len(sales), 7)]
    return "1. Суммы по неделям: " + ", ".join(parts)


def avg_median(sales, srt):
    n = len(sales)
    if n == 0:
        return "2. Среднее: нет   Медиана: нет"
    a = fmt(sum(sales), n)
    if n % 2:
        m = fmt(srt[n // 2], 1)
    else:
        m = fmt(srt[n // 2 - 1] + srt[n // 2], 2)
    return "2. Среднее: " + a + "   Медиана: " + m


def moving(sales):
    n = len(sales)
    if n < 3:
        return "3. Скользящее среднее: нет"
    out = []
    w = sales[0] + sales[1] + sales[2]
    out.append(fmt(w, 3))
    for i in range(3, n):
        w += sales[i] - sales[i - 3]
        out.append(fmt(w, 3))
    return "3. Скользящее среднее: " + " ".join(out)


def best4(sales):
    n = len(sales)
    if n < 4:
        return "4. Лучшие 4 дня подряд: нет"
    w = sales[0] + sales[1] + sales[2] + sales[3]
    best = w
    start = 0
    for i in range(4, n):
        w += sales[i] - sales[i - 4]
        if w > best:
            best = w
            start = i - 3
    return "4. Лучшие 4 дня подряд: дни %d-%d, сумма %d" % (start + 1, start + 4, best)


def longest_rise(sales):
    n = len(sales)
    if n == 0:
        return "5. Самый длинный рост подряд: нет"
    best_len = 1
    best_start = 0
    cur_start = 0
    for i in range(1, n):
        if sales[i] > sales[i - 1]:
            cur_len = i - cur_start + 1
            if cur_len > best_len:
                best_len = cur_len
                best_start = cur_start
        else:
            cur_start = i
    seg = sales[best_start:best_start + best_len]
    return "5. Самый длинный рост подряд: дни %d-%d (%s)" % (
        best_start + 1, best_start + best_len, ", ".join(str(x) for x in seg))


def top3(sales):
    if not sales:
        return "6. Топ-3 дня: нет"
    top = []
    for i, v in enumerate(sales):
        pos = len(top)
        while pos > 0 and top[pos - 1][0] < v:
            pos -= 1
        if pos < 3:
            top.insert(pos, (v, i + 1))
            if len(top) > 3:
                top.pop()
    return "6. Топ-3 дня: " + ", ".join("день %d (%d)" % (d, v) for v, d in top)


def count_ge(srt, x):
    return len(srt) - bisect_left(srt, x)


def main():
    data = json.loads(sys.stdin.read())
    sales = list(data.get("sales", []))
    srt = sorted(sales)
    lines = [
        weekly(sales),
        avg_median(sales, srt),
        moving(sales),
        best4(sales),
        longest_rise(sales),
        top3(sales),
        "7. Дней с продажами не меньше 20: %d" % count_ge(srt, 20),
    ]
    print("\n".join(lines))


main()
