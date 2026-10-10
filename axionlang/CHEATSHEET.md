# Axion v0.3
Write only Axion. The validator rejects anything not described here; follow its "Fix:" hints.

## Layout
Order: `allow` lines, `input` lines, then code. One statement per line. Blocks end with `end`. Indent the body of every block by 2 spaces, and put `end` and `else` exactly under the `if` / `for` / `while` / `function` that opened the block. `#` comment.

## Types
`number` (decimal, 28 digits: 0.1 + 0.2 == 0.3), `text`, `bool`, `list of T`, `{field: T}` (object), `map of T` (dictionary: text keys, values of type T). No null. No implicit conversion.
Literals: `15` `99.5` `0.5` (never `.5` `5.0` `1e3`), `"hi"` (double quotes; escapes `\"` `\\` `\n`), `true` `false`, `[1, 2]`, `{name: "A", age: 3}` (object: bare field names), `{"tea": 2}` (dictionary: quoted keys). Empty ones always name their type: `[] of text`, `{} of number`.

## Variables
`x = expr` creates x; its type never changes. Every variable must be read. Values are copied (no references).
In a block, assigning an existing outer name modifies it; a new name is local and gone after `end`. Need a value after the block? Create it before:
```
result = "no"
if ok
  result = "yes"
end
```

## Operators (high to low)
`()` `x[i]` `x.f` `f()` | words after a value | `**` | unary `-` | `* / // %` | `+ -` | `to` | `== != < > <= >=` | `not` | `and` `or`
- `+`: two numbers, two texts or two lists: `"N: " + n as text`.
- `//` whole division, `%` remainder (integers, divisor > 0). `x ** 2` power, `x ** 0.5` square root.
- `x * (-1)`, not `x * -1`. No chains: `a < b and b < c`. `<` `>` also order text (by character code).
- Only `and` `or` `not`. Parenthesize when mixing `and`/`or`; `not (a > b)`.
- Conditions must be bool: `if n > 0`, `if s != ""`.

## Words after a value
A word applies to the one value right before it, and a chain goes left to right: `line trim lower split ","`. Anything longer needs parentheses: `(a + b) as text`, `(total / n) round 2`, `(s split ",")[0]`, `keys contains (n as text)`.
- `n as text`, `s as number` (an error if `s` is not a number: check `s is number`), `x length`.
- number: `x round 2` (a 5 goes away from zero), `x floor`, `x ceiling`.
- text: `s split ","` (a list of text), `s trim`, `s lower`, `s upper`, `s contains "a"`, `s starts with "a"`, `s ends with "a"`, `s[i]` (one character), `s[a to b]` (a piece, both ends included). Replace: `(s split "a") join "b"`.
- a date is text like `"2026-10-05"`: `s is date`, `s as days` (days since 1970-01-01: subtract two to get the difference), `n as date`. Weekday: `(s as days + 3) % 7`, 0 is Monday.
- list: `xs sum`, `xs min`, `xs max` (numbers), `words join ", "`, `xs contains v`, `xs[a to b]`, `xs sort`, `xs sort descending`, `people sort by age descending, name` (number or text fields; a new list; equal elements keep their order).

These words are operations only right after a value; `sum = 0` is an ordinary variable. But the words of the language itself are never names: `length`, `value`, `index`, `text`, `number`, `list`, `to`, `end`, ...

## Lists, objects, dictionaries
`xs[i]` (from 0, no negatives), `xs[i] = v`, `xs add v` (one element; never `xs + [v]`), `xs remove index i`, `xs remove value v` (exactly one match).
`a to b` = integers a..b inclusive: `for i in 0 to xs length - 1`.
Objects: fields fixed at creation; `o.f = v` keeps the type.
Dictionary: `d[k]` (a missing key is an error: check `d contains k`), `d[k] = v`, `d keys` (a list, in the order of adding), `d remove key k`, `d length`. A key is text: `d[n as text]`.
```
counts = {} of number
for w in words
  counts[w] = if counts contains w then counts[w] + 1 else 1
end
for w in counts keys
  print w + ": " + counts[w] as text
end
```
No `x in xs`: write `xs contains x`.

## if
```
if c
  ...
else if c
  ...
else
  ...
end
```
No empty branches.
A choice between two values fits in one line: `pad = if m < 10 then "0" else ""` (`else` is required, both values have one type; inside a longer expression put it in parentheses).

## Loops
```
for x in xs
  ...
end
while n > 0
  ...
end
```
`for ch in s` goes over the characters of a text. To repeat n times: `for i in 1 to n`.
`break` stops the nearest loop, `continue` goes on to its next pass. The body of `while` must change a variable of its condition or contain `break`.
In `for x in xs`, `x` is the element itself: `x.f = v` changes the list; `x = v` is not allowed. Do not add to or remove from `xs` inside its own loop.
`exit` ends the program (main program only).

## Functions
```
function f(a: number, b: text) -> number
  return a
end
```
Types required; omit `-> T` for no result. A function sees only its parameters and cannot change them. Every path returns. Use every result. Recursion needs a path that stops. Top level only.

## Input, output, files
`input orders: list of {price: number, qty: number}`, `input stock: map of number` (JSON data given by the runner).
`print expr`: exactly one value, no commas; every `print` is one whole line, so build the line first (`row = row + " more"`); text without quotes; lists and objects print as literals: `print xs` -> `["a", "b"]`.
Errors are prevented, not caught (no try): check first with `is number`, `is date`, `contains`, `length`, `!= 0`, `exists`.
Files, only when the task reads files: first line `allow read "dir/"`, then `t = read "dir/" + name` or `if exists "dir/" + name` (both take the whole expression after them; `(read p) length`). Otherwise write no `allow` line. Nothing else touches the system.

## Example
```
input items: list of {name: text, price: number}
total = 0
for it in items
  if it.price > 100
    total = total + it.price
  end
end
print "Total: " + total as text
```
