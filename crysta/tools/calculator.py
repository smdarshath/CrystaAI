"""Safe calculator: AST evaluation only (never eval()), plus a few unit conversions."""
from __future__ import annotations

import ast
import math
import operator
import re

OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
       ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow}
UNARY = {ast.USub: operator.neg, ast.UAdd: operator.pos}
FUNCS = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan, "asin": math.asin, "acos": math.acos,
         "atan": math.atan, "log": math.log10, "ln": math.log, "exp": math.exp, "abs": abs, "round": round,
         "factorial": math.factorial, "floor": math.floor, "ceil": math.ceil}
CONSTS = {"pi": math.pi, "e": math.e, "tau": math.tau}


def _eval(node, env=None):
    if isinstance(node, ast.Expression):
        return _eval(node.body, env)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in OPS:
        left, right = _eval(node.left, env), _eval(node.right, env)
        if isinstance(node.op, ast.Pow) and abs(right) > 1000:
            raise ValueError("Exponent too large")
        return OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in UNARY:
        return UNARY[type(node.op)](_eval(node.operand, env))
    if isinstance(node, ast.Name) and env and node.id in env:
        return env[node.id]
    if isinstance(node, ast.Name) and node.id in CONSTS:
        return CONSTS[node.id]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCS and not node.keywords:
        args = [_eval(a, env) for a in node.args]
        if node.func.id == "factorial" and (len(args) != 1 or args[0] > 1000):
            raise ValueError("Factorial too large")
        return FUNCS[node.func.id](*args)
    raise ValueError("Unsupported expression")


def fmt(v):
    if isinstance(v, float):
        if v == int(v) and abs(v) < 1e15:
            return str(int(v))
        return f"{v:.10g}"
    return str(v)


def evaluate_num(expr, env=None):
    expr = expr.replace("^", "**").replace("×", "*").replace("÷", "/")
    try:
        return _eval(ast.parse(expr.strip(), mode="eval"), env)
    except ZeroDivisionError:
        raise
    except (SyntaxError, TypeError, OverflowError, ValueError):
        raise ValueError("bad expression")


def evaluate(expr):
    expr = expr.replace("^", "**").replace("×", "*").replace("÷", "/")
    expr = re.sub(r"(?<=\d),(?=\d{3}\b)", "", expr)
    try:
        tree = ast.parse(expr.strip(), mode="eval")
        return fmt(_eval(tree))
    except ZeroDivisionError:
        raise ValueError("Division by zero")
    except (SyntaxError, TypeError, OverflowError) as e:
        raise ValueError(f"Could not evaluate that ({type(e).__name__})")


WORD_OPS = [(r"\bto the power of\b", "**"), (r"\bsquared\b", "**2"), (r"\bcubed\b", "**3"),
            (r"\bmultiplied by\b", "*"), (r"\btimes\b", "*"), (r"\bplus\b", "+"), (r"\bminus\b", "-"),
            (r"\bdivided by\b", "/"), (r"\bover\b", "/"), (r"\bmod\b", "%"), (r"(?<=\d)\s*x\s*(?=\d)", "*")]
LEAD = r"^(?:please\s+)?(?:calculate|compute|solve|evaluate|what(?:'s| is)|whats|how much is|find|work out|tell me)\b\s*"

UNITS = {  # to base unit
    "length": {"m": 1, "meter": 1, "meters": 1, "km": 1000, "kilometer": 1000, "kilometers": 1000, "cm": 0.01,
               "mile": 1609.344, "miles": 1609.344, "mi": 1609.344, "ft": 0.3048, "feet": 0.3048, "inch": 0.0254, "inches": 0.0254},
    "mass": {"kg": 1, "kilogram": 1, "kilograms": 1, "g": 0.001, "gram": 0.001, "grams": 0.001, "lb": 0.45359237,
             "lbs": 0.45359237, "pound": 0.45359237, "pounds": 0.45359237},
}
TEMP = {"c": "c", "celsius": "c", "f": "f", "fahrenheit": "f", "k": "k", "kelvin": "k"}


def convert(text):
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*([a-z]+)\s+(?:to|in|into)\s+([a-z]+)\b", text.lower())
    if not m:
        return None
    val, a, b = float(m.group(1)), m.group(2), m.group(3)
    if a in TEMP and b in TEMP:
        c = {"c": val, "f": (val - 32) * 5 / 9, "k": val - 273.15}[TEMP[a]]
        out = {"c": c, "f": c * 9 / 5 + 32, "k": c + 273.15}[TEMP[b]]
        return f"{fmt(val)} {a} = {out:.6g} {b}"
    for table in UNITS.values():
        if a in table and b in table:
            return f"{fmt(val)} {a} = {val * table[a] / table[b]:.6g} {b}"
    return None


def extract_expression(text):
    """Return a math expression found in natural language, or None."""
    t = text.lower().strip().rstrip("?=! .")
    t = re.sub(LEAD, "", t).strip()
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(?:%|percent)\s*of\s*(\d+(?:\.\d+)?)", t)
    if m:
        return f"({m.group(1)}/100)*{m.group(2)}"
    t = re.sub(r"square root of\s*(\d+(?:\.\d+)?)", r"sqrt(\1)", t)
    t = re.sub(r"\bsqrt of\s*(\d+(?:\.\d+)?)", r"sqrt(\1)", t)
    for pat, rep in WORD_OPS:
        t = re.sub(pat, f" {rep} " if rep not in ("**2", "**3") else rep, t)
    t = t.strip()
    if not re.search(r"\d", t) or not re.search(r"[\+\-\*/%\^]|sqrt|sin|cos|tan|log|ln|factorial|exp", t):
        return None
    names = set(re.findall(r"[a-z_]+", t))
    if not names <= (set(FUNCS) | set(CONSTS)):
        return None
    if not re.fullmatch(r"[\d\s\.\+\-\*/%\^\(\),a-z_]+", t):
        return None
    return t


def calculate(text):
    """Natural-language or plain expression -> {'expression','result'} or raises ValueError."""
    conv = convert(text)
    if conv:
        return {"expression": text.strip(), "result": conv}
    expr = extract_expression(text) or text
    return {"expression": expr, "result": evaluate(expr)}
