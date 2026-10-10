import sys
import json
import threading
from fractions import Fraction


class CalcError(Exception):
    pass


DIG = '0123456789'


def tokenize(s):
    toks = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == ' ':
            i += 1
        elif c in DIG or c == '.':
            j = i
            while j < n and (s[j] in DIG or s[j] == '.'):
                j += 1
            toks.append(('num', s[i:j], i + 1))
            i = j
        elif c in '+-*/^()':
            toks.append(('op', c, i + 1))
            i += 1
        else:
            raise CalcError("ошибка: неизвестный символ '%s', позиция %d" % (c, i + 1))
    return toks


def evaluate(s):
    toks = tokenize(s)
    if not toks:
        raise CalcError("ошибка: пустое выражение")
    endpos = len(s) + 1
    pos = [0]

    def peek():
        if pos[0] < len(toks):
            return toks[pos[0]]
        return None

    def need_number_err():
        t = peek()
        p = t[2] if t else endpos
        return CalcError("ошибка: ожидалось число, позиция %d" % p)

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
                        raise CalcError("ошибка: деление на ноль")
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
            if e.denominator != 1:
                raise CalcError("ошибка: ожидалось число, позиция %d" % t[2])
            if b == 0 and e < 0:
                raise CalcError("ошибка: деление на ноль")
            return b ** int(e)
        return b

    def atom():
        t = peek()
        if t is None:
            raise need_number_err()
        if t[0] == 'num':
            try:
                v = Fraction(t[1])
            except Exception:
                raise need_number_err()
            pos[0] += 1
            return v
        if t[1] == '(':
            pos[0] += 1
            v = expr()
            t2 = peek()
            if t2 is None:
                raise CalcError("ошибка: не закрыта скобка")
            if t2[0] == 'op' and t2[1] == ')':
                pos[0] += 1
                return v
            raise need_number_err()
        raise need_number_err()

    v = expr()
    if pos[0] < len(toks):
        raise need_number_err()
    return v


def fmt(f):
    if f.denominator == 1:
        return str(f.numerator)
    neg = f < 0
    f = abs(f)
    ip = f.numerator // f.denominator
    rem = f - ip
    digits = ''
    while rem != 0:
        rem *= 10
        d = rem.numerator // rem.denominator
        digits += str(d)
        rem -= d
        if len(digits) > 60:
            break
    res = str(ip) + ('.' + digits if digits else '')
    return ('-' if neg else '') + res


def main():
    raw = sys.stdin.buffer.read().decode('utf-8')
    data = json.loads(raw)
    out = []
    for line in data["lines"]:
        try:
            out.append(fmt(evaluate(line)))
        except CalcError as e:
            out.append(str(e))
        except RecursionError:
            out.append("ошибка: ожидалось число, позиция %d" % (len(line) + 1))
    if out:
        sys.stdout.buffer.write(("\n".join(out) + "\n").encode('utf-8'))
    sys.stdout.buffer.flush()


sys.setrecursionlimit(200000)
try:
    threading.stack_size(128 * 1024 * 1024)
    th = threading.Thread(target=main)
    th.start()
    th.join()
except Exception:
    main()
