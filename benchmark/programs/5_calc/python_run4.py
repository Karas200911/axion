import sys
import json
from fractions import Fraction


class CalcError(Exception):
    pass


def tokenize(line):
    toks = []
    i = 0
    n = len(line)
    while i < n:
        c = line[i]
        if c == ' ':
            i += 1
        elif c.isdigit() and c in '0123456789' or c == '.':
            j = i
            while j < n and (line[j] in '0123456789.'):
                j += 1
            toks.append(('num', line[i:j], i + 1))
            i = j
        elif c in '+-*/^()':
            toks.append((c, c, i + 1))
            i += 1
        else:
            raise CalcError("ошибка: неизвестный символ '%s', позиция %d" % (c, i + 1))
    return toks


class Parser:
    def __init__(self, toks, length):
        self.t = toks
        self.p = 0
        self.end = length + 1

    def peek(self):
        return self.t[self.p][0] if self.p < len(self.t) else None

    def pos(self):
        return self.t[self.p][2] if self.p < len(self.t) else self.end

    def expr(self):
        v = self.term()
        while self.peek() in ('+', '-'):
            op = self.peek()
            self.p += 1
            r = self.term()
            v = v + r if op == '+' else v - r
        return v

    def term(self):
        v = self.unary()
        while self.peek() in ('*', '/'):
            op = self.peek()
            self.p += 1
            r = self.unary()
            if op == '*':
                v = v * r
            else:
                if r == 0:
                    raise CalcError("ошибка: деление на ноль")
                v = v / r
        return v

    def unary(self):
        if self.peek() == '-':
            self.p += 1
            return -self.unary()
        return self.power()

    def power(self):
        base = self.atom()
        if self.peek() == '^':
            self.p += 1
            e = self.unary()
            if e.denominator == 1 and e >= 0:
                return base ** int(e)
            if base == 0 and e < 0:
                raise CalcError("ошибка: деление на ноль")
            return base ** e if e.denominator == 1 else Fraction(float(base) ** float(e))
        return base

    def atom(self):
        k = self.peek()
        if k == 'num':
            s = self.t[self.p][1]
            self.p += 1
            try:
                return Fraction(s)
            except Exception:
                raise CalcError("ошибка: ожидалось число, позиция %d" % self.t[self.p - 1][2])
        if k == '(':
            self.p += 1
            v = self.expr()
            if self.peek() == ')':
                self.p += 1
                return v
            if self.peek() is None:
                raise CalcError("ошибка: не закрыта скобка")
            raise CalcError("ошибка: ожидалось число, позиция %d" % self.pos())
        raise CalcError("ошибка: ожидалось число, позиция %d" % self.pos())


def fmt(f):
    if f.denominator == 1:
        return str(f.numerator)
    neg = f < 0
    f = abs(f)
    d = f.denominator
    k = 0
    while 10 ** k % d != 0:
        k += 1
        if k > 60:
            break
    if k > 60:
        s = ("%.15f" % float(f)).rstrip('0').rstrip('.')
        return ('-' if neg else '') + s
    digits = f.numerator * (10 ** k) // d
    s = str(digits).rjust(k + 1, '0')
    s = s[:-k] + '.' + s[-k:]
    s = s.rstrip('0').rstrip('.')
    return ('-' if neg else '') + s


def evaluate(line):
    if line.strip() == '':
        return "ошибка: пустое выражение"
    try:
        toks = tokenize(line)
        if not toks:
            return "ошибка: пустое выражение"
        p = Parser(toks, len(line))
        v = p.expr()
        if p.p < len(toks):
            raise CalcError("ошибка: ожидалось число, позиция %d" % p.pos())
        return fmt(v)
    except CalcError as e:
        return str(e)


def main():
    data = json.loads(sys.stdin.read())
    out = [evaluate(l) for l in data["lines"]]
    sys.stdout.write("\n".join(out) + ("\n" if out else ""))


main()
