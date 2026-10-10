import sys
import json
from bisect import bisect_left


def fmt2(num, den):
    if den < 0:
        num, den = -num, -den
    neg = num < 0
    n = abs(num)
    q = (n * 200 + den) // (2 * den)
    s = "%d.%02d" % (q // 100, q % 100)
    if neg and q != 0:
        s = "-" + s
    return s


def weekly_sums(sales):
    if not sales:
        return "нет"
    return ", ".join(str(sum(sales[i:i + 7])) for i in range(0, len(sales), 7))


def avg_median(sales):
    n = len(sales)
    if n == 0:
        return "нет", "нет"
    avg = fmt2(sum(sales), n)
    s = sorted(sales)
    if n % 2:
        med = fmt2(s[n // 2], 1)
    else:
        med = fmt2(s[n // 2 - 1] + s[n // 2], 2)
    return avg, med


def moving_avg(sales):
    n = len(sales)
    if n < 3:
        return "нет"
    out = []
    w = sales[0] + sales[1] + sales[2]
    out.append(fmt2(w, 3))
    for i in range(3, n):
        w += sales[i] - sales[i - 3]
        out.append(fmt2(w, 3))
    return " ".join(out)


def best4(sales):
    n = len(sales)
    if n < 4:
        return "нет"
    w = sales[0] + sales[1] + sales[2] + sales[3]
    best = w
    start = 0
    for i in range(4, n):
        w += sales[i] - sales[i - 4]
        if w > best:
            best = w
            start = i - 3
    return "дни %d-%d, сумма %d" % (start + 1, start + 4, best)


def longest_rise(sales):
    n = len(sales)
    if n == 0:
        return "нет"
    best_len = 1
    best_start = 0
    cur_start = 0
    for i in range(1, n):
        if sales[i] > sales[i - 1]:
            pass
        else:
            cur_start = i
        ln = i - cur_start + 1
        if ln > best_len:
            best_len = ln
            best_start = cur_start
    seg = sales[best_start:best_start + best_len]
    return "дни %d-%d (%s)" % (best_start + 1, best_start + best_len,
                               ", ".join(str(x) for x in seg))


def top3(sales):
    if not sales:
        return "нет"
    top = []
    for i, v in enumerate(sales):
        day = i + 1
        pos = len(top)
        while pos > 0 and top[pos - 1][0] < v:
            pos -= 1
        if pos < 3:
            top.insert(pos, (v, day))
            if len(top) > 3:
                top.pop()
    return ", ".join("день %d (%d)" % (d, v) for v, d in top)


def count_ge(sales, limit=20):
    s = sorted(sales)
    return len(s) - bisect_left(s, limit)


def main():
    data = json.loads(sys.stdin.read())
    sales = data.get("sales", [])
    avg, med = avg_median(sales)
    print("1. Суммы по неделям: " + weekly_sums(sales))
    print("2. Среднее: " + avg + "   Медиана: " + med)
    print("3. Скользящее среднее: " + moving_avg(sales))
    print("4. Лучшие 4 дня подряд: " + best4(sales))
    print("5. Самый длинный рост подряд: " + longest_rise(sales))
    print("6. Топ-3 дня: " + top3(sales))
    print("7. Дней с продажами не меньше 20: " + str(count_ge(sales)))


main()
