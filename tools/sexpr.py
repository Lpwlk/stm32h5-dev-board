"""Minimal KiCad S-expression reader (KiCad 6-9 files), stdlib only.

parse(text) -> nested lists: atoms are str, quoted strings are returned without
quotes. Use `find_all(node, "name")` / `prop(node, "Reference")` helpers.
"""
from __future__ import annotations


def parse(text: str) -> list:
    pos, n = 0, len(text)
    stack: list[list] = [[]]
    while pos < n:
        c = text[pos]
        if c in " \t\r\n":
            pos += 1
        elif c == "(":
            new: list = []
            stack[-1].append(new)
            stack.append(new)
            pos += 1
        elif c == ")":
            if len(stack) == 1:
                raise ValueError(f"unbalanced ')' at offset {pos}")
            stack.pop()
            pos += 1
        elif c == '"':
            pos += 1
            buf = []
            while pos < n and text[pos] != '"':
                if text[pos] == "\\" and pos + 1 < n:
                    pos += 1
                buf.append(text[pos])
                pos += 1
            pos += 1
            stack[-1].append("".join(buf))
        else:
            start = pos
            while pos < n and text[pos] not in " \t\r\n()":
                pos += 1
            stack[-1].append(text[start:pos])
    if len(stack) != 1:
        raise ValueError("unbalanced '(' at end of file")
    return stack[0][0] if stack[0] else []


def find_all(node: list, name: str) -> list[list]:
    return [c for c in node if isinstance(c, list) and c and c[0] == name]


def find(node: list, name: str):
    r = find_all(node, name)
    return r[0] if r else None


def prop(node: list, key: str) -> str:
    for p in find_all(node, "property"):
        if len(p) >= 3 and p[1] == key:
            return p[2]
    return ""
