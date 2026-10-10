"""A small bot: ask a question about a JSON file; a model writes an Axion program; Axion runs it.

    pip install axionlang openai
    export OPENAI_API_KEY=...            (never put the key in the code)
    python examples/ask_bot.py

Works with any OpenAI-compatible API. For another provider, change MODEL and add base_url=... below.
"""
import json

from openai import OpenAI

import axionlang

MODEL = ""                       # the name of any chat model you have access to

if not MODEL:
    print("Write the name of your model in MODEL at the top of this file.")
    raise SystemExit(1)

client = OpenAI()                # reads OPENAI_API_KEY from the environment


def model(messages):
    """Send the messages to the model and return its reply as text. axionlang.ask calls this."""
    reply = client.chat.completions.create(model=MODEL, messages=messages)
    return reply.choices[0].message.content


question = input("Question (or a .txt file with the task): ").strip()
if question.endswith(".txt"):
    # A long task with several paragraphs goes in a file: input() reads only one line.
    try:
        with open(question, encoding="utf-8") as file:
            question = file.read().strip()
    except FileNotFoundError:
        print("File not found:", question)
        raise SystemExit(1)
if not question:
    print("The question is empty.")
    raise SystemExit(1)

path = input("JSON file: ").strip()
try:
    with open(path, encoding="utf-8") as file:
        data = json.load(file)
except FileNotFoundError:
    print("File not found:", path)
    raise SystemExit(1)
except json.JSONDecodeError as error:
    print("This file is not valid JSON:", error)
    raise SystemExit(1)

try:
    # The data is this user's own file, so its shape is the sample (shape=data).
    # When a program is saved and reused on new data, pass a fixed sample instead.
    result = axionlang.ask(model, question, data, shape=data)
except (TypeError, ValueError) as error:          # e.g. an empty list or null in the data
    print("Axion cannot use this data:", error)
    raise SystemExit(1)

print()
print(f"Program from the model (attempts: {result.attempts}):")
print(result.program)
print()
if result.ok:
    print("Answer:")
    for line in result.output:
        print(line)
else:
    print("Axion stopped it:")
    print(result.error)
