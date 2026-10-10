import sys
import json
from fractions import Fraction
from decimal import Decimal, getcontext

getcontext().prec = 60


class CalcError(Exception):
    pass


def tokenize(s):
    toks = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == ' ':
            i += 1
        elif c.isdigit() and c in '0123456789' or c == '.':
            j = i
            while j < n and (s[j] in '0123456789.'):
                j += 1
            toks.append(('num', Fraction(Decimal(s[i:j])), i + 1))
            i = j
        elif c in '+-*/^()':
            toks.append(('op', c, i + 1))
            i += 1
        else:
            raise CalcError("ошибка: неизвестный символ '%s', позиция %d" % (c, i + 1))
    return toks


class Parser:
    def __init__(self, toks, n):
        self.t = toks
        self.p = 0
        self.n = n

    def peek(self):
        if self.p < len(self.t):
            return self.t[self.p]
        return None

    def expr(self):
        v = self.term()
        while True:
            t = self.peek()
            if t and t[0] == 'op' and t[1] in '+-':
                self.p += 1
                r = self.term()
                v = v + r if t[1] == '+' else v - r
            else:
                return v

    def term(self):
        v = self.unary()
        while True:
            t = self.peek()
            if t and t[0] == 'op' and t[1] in '*/':
                self.p += 1
                r = self.unary()
                if t[1] == '*':
                    v = v * r
                else:
                    if r == 0:
                        raise CalcError("ошибка: деление на ноль")
                    v = v / r
            else:
                return v

    def unary(self):
        t = self.peek()
        if t and t[0] == 'op' and t[1] == '-':
            self.p += 1
            return -self.unary()
        return self.power()

    def power(self):
        b = self.atom()
        t = self.peek()
        if t and t[0] == 'op' and t[1] == '^':
            self.p += 1
            e = self.unary()
            if e.denominator == 1 and e >= 0:
                return b ** int(e)
            if b == 0:
                raise CalcError("ошибка: деление на ноль")
            return Fraction(float(b) ** float(e))
        return b

    def atom(self):
        t = self.peek()
        if t is None:
            raise CalcError("ошибка: ожидалось число, позиция %d" % (self.n + 1))
        if t[0] == 'num':
            self.p += 1
            return t[1]
        if t[1] == '(':
            self.p += 1
            v = self.expr()
            t2 = self.peek()
            if t2 and t2[0] == 'op' and t2[1] == ')':
                self.p += 1
                return v
            if t2 is None:
                raise CalcError("ошибка: не закрыта скобка")
            raise CalcError("ошибка: ожидалось число, позиция %d" % t2[2])
        raise CalcError("ошибка: ожидалось число, позиция %d" % t[2])


def fmt(f):
    if f.denominator == 1:
        return str(f.numerator)
    d = Decimal(f.numerator) / Decimal(f.denominator)
    s = format(d, 'f')
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s


def evaluate(line):
    if line.strip(' ') == '':
        return "ошибка: пустое выражение"
    try:
        toks = tokenize(line)
        p = Parser(toks, len(line))
        v = p.expr()
        if p.peek() is not None:
            t = p.peek()
            raise CalcError("ошибка: ожидалось число, позиция %d" % t[2])
        return fmt(v)
    except CalcError as e:
        return str(e)


def main():
    data = json.loads(sys.stdin.read())
    out = [evaluate(l) for l in data["lines"]]
    sys.stdout.write("\n".join(out) + ("\n" if out else ""))


main()
