import sys
import json
import threading
from fractions import Fraction


class CalcError(Exception):
    pass


def is_digit(c):
    return c in '0123456789'


def tokenize(s):
    toks = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == ' ':
            i += 1
        elif is_digit(c) or c == '.':
            j = i
            while j < n and (is_digit(s[j]) or s[j] == '.'):
                j += 1
            text = s[i:j]
            try:
                val = Fraction(text)
            except (ValueError, ZeroDivisionError):
                raise CalcError("ошибка: ожидалось число, позиция %d" % (i + 1))
            toks.append(('num', val, i + 1))
            i = j
        elif c in '+-*/^()':
            toks.append((c, None, i + 1))
            i += 1
        else:
            raise CalcError("ошибка: неизвестный символ '%s', позиция %d" % (c, i + 1))
    return toks


def evaluate(toks, n):
    pos = [0]

    def peek():
        if pos[0] < len(toks):
            return toks[pos[0]]
        return None

    def expect_error(t):
        p = n + 1 if t is None else t[2]
        return CalcError("ошибка: ожидалось число, позиция %d" % p)

    def expr():
        v = term()
        while True:
            t = peek()
            if t and t[0] in '+-':
                pos[0] += 1
                r = term()
                v = v + r if t[0] == '+' else v - r
            else:
                return v

    def term():
        v = unary()
        while True:
            t = peek()
            if t and t[0] in '*/':
                pos[0] += 1
                r = unary()
                if t[0] == '*':
                    v = v * r
                else:
                    if r == 0:
                        raise CalcError("ошибка: деление на ноль")
                    v = v / r
            else:
                return v

    def unary():
        t = peek()
        if t and t[0] == '-':
            pos[0] += 1
            return -unary()
        return power()

    def power():
        b = atom()
        t = peek()
        if t and t[0] == '^':
            pos[0] += 1
            e = unary()
            if e.denominator != 1:
                raise CalcError("ошибка: ожидалось число, позиция %d" % t[2])
            ei = int(e)
            if ei < 0 and b == 0:
                raise CalcError("ошибка: деление на ноль")
            return b ** ei
        return b

    def atom():
        t = peek()
        if t is None:
            raise expect_error(None)
        if t[0] == 'num':
            pos[0] += 1
            return t[1]
        if t[0] == '(':
            pos[0] += 1
            v = expr()
            t2 = peek()
            if t2 is None:
                raise CalcError("ошибка: не закрыта скобка")
            if t2[0] != ')':
                raise expect_error(t2)
            pos[0] += 1
            return v
        raise expect_error(t)

    v = expr()
    t = peek()
    if t is not None:
        raise expect_error(t)
    return v


def fmt(f):
    if f.denominator == 1:
        return str(f.numerator)
    neg = f < 0
    a = abs(f)
    num, den = a.numerator, a.denominator
    k = 0
    while (num * 10 ** k) % den != 0:
        k += 1
    val = num * 10 ** k // den
    s = str(val).rjust(k + 1, '0')
    res = s[:-k] + '.' + s[-k:]
    res = res.rstrip('0').rstrip('.')
    return ('-' if neg else '') + res


def run(line):
    try:
        toks = tokenize(line)
        if not toks:
            return "ошибка: пустое выражение"
        return fmt(evaluate(toks, len(line)))
    except CalcError as e:
        return str(e)


def main():
    raw = sys.stdin.buffer.read().decode('utf-8')
    data = json.loads(raw)
    out = [run(l) for l in data["lines"]]
    if out:
        sys.stdout.buffer.write(("\n".join(out) + "\n").encode('utf-8'))
    sys.stdout.buffer.flush()


sys.setrecursionlimit(1000000)
started = False
for size in (512, 256, 64, 16):
    try:
        threading.stack_size(size * 1024 * 1024)
        th = threading.Thread(target=main)
        th.start()
        started = True
        th.join()
        break
    except (ValueError, RuntimeError, MemoryError):
        if started:
            break
if not started:
    main()
