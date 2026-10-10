# Examples

Small Axion programs you can run right after `pip install axionlang`. From the repository root:

**Start here: the same program, good data and bad data.**

```
python -m axionlang examples/cart.ax --input examples/cart.json
```
```text
Total: 1170
```

```
python -m axionlang examples/cart.ax --input examples/cart_bad.json
```
```text
ERROR R407 line 3:1
input cart: list of {price: number, qty: number}
Input data: cart[0].price must be number, got text.
```

In `cart_bad.json` one price is `"500"` in quotes. Axion refuses the data before the first line runs,
instead of guessing what was meant.

## All examples

| File | Shows | Run |
|---|---|---|
| [`cart.ax`](cart.ax) | the `input` contract; good and bad data | `python -m axionlang examples/cart.ax --input examples/cart.json` |
| [`grade.ax`](grade.ax) | `if / else if`, a block inside a block | `python -m axionlang examples/grade.ax` |
| [`tax.ax`](tax.ax) | functions with typed parameters | `python -m axionlang examples/tax.ax` |
| [`words.ax`](words.ax) | text, a dictionary, a sort by two fields, `while`, `exit` | `python -m axionlang examples/words.ax --input examples/words.json` |
| [`read.ax`](read.ax) | reading a file: the program asks, you grant the folder | `python -m axionlang examples/read.ax --policy examples/policy.json` |
| [`ask_bot.py`](ask_bot.py) | a model writes the program from a question about your JSON file | `python examples/ask_bot.py` (needs an API key) |

Try `read.ax` without `--policy`: it stops with S502, because nobody granted the folder.
