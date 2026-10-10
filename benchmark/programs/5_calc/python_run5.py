import sys
import json
from fractions import Fraction

sys.setrecursionlimit(20000)


class Err(Exception):
    pass


def tokenize(s):
    toks = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == ' ':
            i += 1
        elif c in '0123456789.':
            j = i
            while j < n and (s[j] in '0123456789.'):
                j += 1
            toks.append(('num', s[i:j], i + 1))
            i = j
        elif c in '+-*/^()':
            toks.append(('op', c, i + 1))
            i += 1
        else:
            raise Err("ошибка: неизвестный символ '%s', позиция %d" % (c, i + 1))
    return toks


def evaluate(toks, n):
    pos = [0]

    def peek():
        return toks[pos[0]] if pos[0] < len(toks) else None

    def need_num():
        t = peek()
        p = t[2] if t else n + 1
        raise Err("ошибка: ожидалось число, позиция %d" % p)

    def expr():
        v = term()
        while True:
            t = peek()
            if t and t[0] == 'op' and t[1] in '+-':
                pos[0] += 1
                r = term()
                v = v + r if t[1] == '+' else v - r
            else:
                return v

    def term():
        v = unary()
        while True:
            t = peek()
            if t and t[0] == 'op' and t[1] in '*/':
                pos[0] += 1
                r = unary()
                if t[1] == '*':
                    v = v * r
                else:
                    if r == 0:
                        raise Err("ошибка: деление на ноль")
                    v = v / r
            else:
                return v

    def unary():
        t = peek()
        if t and t[0] == 'op' and t[1] == '-':
            pos[0] += 1
            return -unary()
        return power()

    def power():
        b = atom()
        t = peek()
        if t and t[0] == 'op' and t[1] == '^':
            pos[0] += 1
            e = unary()
            try:
                return b ** int(e)
            except ZeroDivisionError:
                raise Err("ошибка: деление на ноль")
        return b

    def atom():
        t = peek()
        if t is None:
            need_num()
        if t[0] == 'num':
            pos[0] += 1
            try:
                return Fraction(t[1])
            except Exception:
                raise Err("ошибка: ожидалось число, позиция %d" % t[2])
        if t[1] == '(':
            pos[0] += 1
            v = expr()
            t2 = peek()
            if t2 is None:
                raise Err("ошибка: не закрыта скобка")
            if t2[1] != ')':
                need_num()
            pos[0] += 1
            return v
        need_num()

    v = expr()
    if peek() is not None:
        need_num()
    return v


def fmt(v):
    neg = v < 0
    if neg:
        v = -v
    num, den = v.numerator, v.denominator
    ip, rem = divmod(num, den)
    s = str(ip)
    if rem:
        digits = []
        count = 0
        while rem and count < 400:
            rem *= 10
            d, rem = divmod(rem, den)
            digits.append(str(d))
            count += 1
        frac = ''.join(digits).rstrip('0')
        if frac:
            s += '.' + frac
    if neg and s != '0':
        s = '-' + s
    return s


def run(line):
    if line.replace(' ', '') == '':
        return "ошибка: пустое выражение"
    try:
        toks = tokenize(line)
        return fmt(evaluate(toks, len(line)))
    except Err as e:
        return str(e)


def main():
    raw = sys.stdin.buffer.read().decode('utf-8')
    data = json.loads(raw)
    out = [run(l) for l in data["lines"]]
    if out:
        sys.stdout.buffer.write(("\n".join(out) + "\n").encode('utf-8'))
    sys.stdout.buffer.flush()


main()
