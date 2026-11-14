"""ASTRA formula workspace: a real solver (no AI) over a library of standard formulas + math plotting."""
from __future__ import annotations

import math
import re
from pathlib import Path

from ..errors import CrystaError
from . import calculator

C = {"c": 299792458.0, "G": 6.67430e-11, "h": 6.62607015e-34, "g": 9.80665, "k_B": 1.380649e-23, "R": 8.314462618, "N_A": 6.02214076e23, "e": 1.602176634e-19}
S = math.sqrt

# id: (name, subject, equation text, {var: (description, unit)}, {target: fn(**others)}, constants used)
FORMULAS = {
    "ohm": ("Ohm's law", "Electronics", "V = I × R", {"V": ("Voltage", "V"), "I": ("Current", "A"), "R": ("Resistance", "Ω")},
            {"V": lambda I, R: I * R, "I": lambda V, R: V / R, "R": lambda V, I: V / I}, ()),
    "power": ("Electrical power", "Electronics", "P = V × I", {"P": ("Power", "W"), "V": ("Voltage", "V"), "I": ("Current", "A")},
              {"P": lambda V, I: V * I, "V": lambda P, I: P / I, "I": lambda P, V: P / V}, ()),
    "capacitor_energy": ("Capacitor energy", "Electronics", "E = ½ C V²", {"E": ("Energy", "J"), "C": ("Capacitance", "F"), "V": ("Voltage", "V")},
                         {"E": lambda C, V: .5 * C * V ** 2, "C": lambda E, V: 2 * E / V ** 2, "V": lambda E, C: S(2 * E / C)}, ()),
    "rc_tau": ("RC time constant", "Electronics", "τ = R × C", {"tau": ("Time constant", "s"), "R": ("Resistance", "Ω"), "C": ("Capacitance", "F")},
               {"tau": lambda R, C: R * C, "R": lambda tau, C: tau / C, "C": lambda tau, R: tau / R}, ()),
    "newton2": ("Newton's second law", "Mechanics", "F = m × a", {"F": ("Force", "N"), "m": ("Mass", "kg"), "a": ("Acceleration", "m/s²")},
                {"F": lambda m, a: m * a, "m": lambda F, a: F / a, "a": lambda F, m: F / m}, ()),
    "kinetic": ("Kinetic energy", "Mechanics", "KE = ½ m v²", {"KE": ("Kinetic energy", "J"), "m": ("Mass", "kg"), "v": ("Speed", "m/s")},
                {"KE": lambda m, v: .5 * m * v ** 2, "m": lambda KE, v: 2 * KE / v ** 2, "v": lambda KE, m: S(2 * KE / m)}, ()),
    "momentum": ("Momentum", "Mechanics", "p = m × v", {"p": ("Momentum", "kg·m/s"), "m": ("Mass", "kg"), "v": ("Velocity", "m/s")},
                 {"p": lambda m, v: m * v, "m": lambda p, v: p / v, "v": lambda p, m: p / m}, ()),
    "speed": ("Average speed", "Mechanics", "v = d / t", {"v": ("Speed", "m/s"), "d": ("Distance", "m"), "t": ("Time", "s")},
              {"v": lambda d, t: d / t, "d": lambda v, t: v * t, "t": lambda d, v: d / v}, ()),
    "projectile_range": ("Projectile range (flat ground)", "Mechanics", "R = v² sin(2θ) / g", {"R": ("Range", "m"), "v": ("Launch speed", "m/s"), "theta": ("Launch angle", "°")},
                         {"R": lambda v, theta: v ** 2 * math.sin(math.radians(2 * theta)) / C["g"], "v": lambda R, theta: S(R * C["g"] / math.sin(math.radians(2 * theta)))}, ("g",)),
    "gravity_force": ("Newton's gravitation", "Astronomy", "F = G m₁ m₂ / r²", {"F": ("Force", "N"), "m1": ("Mass 1", "kg"), "m2": ("Mass 2", "kg"), "r": ("Distance", "m")},
                      {"F": lambda m1, m2, r: C["G"] * m1 * m2 / r ** 2, "r": lambda F, m1, m2: S(C["G"] * m1 * m2 / F)}, ("G",)),
    "escape_velocity": ("Escape velocity", "Astronomy", "v = √(2 G M / r)", {"v": ("Escape speed", "m/s"), "M": ("Central mass", "kg"), "r": ("Distance from centre", "m")},
                        {"v": lambda M, r: S(2 * C["G"] * M / r), "M": lambda v, r: v ** 2 * r / (2 * C["G"]), "r": lambda v, M: 2 * C["G"] * M / v ** 2}, ("G",)),
    "orbital_velocity": ("Circular orbital speed", "Astronomy", "v = √(G M / r)", {"v": ("Orbital speed", "m/s"), "M": ("Central mass", "kg"), "r": ("Orbit radius", "m")},
                         {"v": lambda M, r: S(C["G"] * M / r), "M": lambda v, r: v ** 2 * r / C["G"], "r": lambda v, M: C["G"] * M / v ** 2}, ("G",)),
    "orbital_period": ("Orbital period (Kepler III)", "Astronomy", "T = 2π √(a³ / G M)", {"T": ("Period", "s"), "a": ("Semi-major axis", "m"), "M": ("Central mass", "kg")},
                       {"T": lambda a, M: 2 * math.pi * S(a ** 3 / (C["G"] * M)), "a": lambda T, M: (C["G"] * M * (T / (2 * math.pi)) ** 2) ** (1 / 3), "M": lambda T, a: 4 * math.pi ** 2 * a ** 3 / (C["G"] * T ** 2)}, ("G",)),
    "schwarzschild": ("Schwarzschild radius", "Astronomy", "r_s = 2 G M / c²", {"rs": ("Horizon radius", "m"), "M": ("Mass", "kg")},
                      {"rs": lambda M: 2 * C["G"] * M / C["c"] ** 2, "M": lambda rs: rs * C["c"] ** 2 / (2 * C["G"])}, ("G", "c")),
    "mass_energy": ("Mass–energy equivalence", "Relativity", "E = m c²", {"E": ("Energy", "J"), "m": ("Mass", "kg")},
                    {"E": lambda m: m * C["c"] ** 2, "m": lambda E: E / C["c"] ** 2}, ("c",)),
    "wave": ("Wave speed", "Waves", "v = f × λ", {"v": ("Wave speed", "m/s"), "f": ("Frequency", "Hz"), "lam": ("Wavelength", "m")},
             {"v": lambda f, lam: f * lam, "f": lambda v, lam: v / lam, "lam": lambda v, f: v / f}, ()),
    "photon": ("Photon energy", "Waves", "E = h c / λ", {"E": ("Photon energy", "J"), "lam": ("Wavelength", "m")},
               {"E": lambda lam: C["h"] * C["c"] / lam, "lam": lambda E: C["h"] * C["c"] / E}, ("h", "c")),
    "ideal_gas": ("Ideal gas law", "Chemistry", "P V = n R T", {"P": ("Pressure", "Pa"), "V": ("Volume", "m³"), "n": ("Amount", "mol"), "T": ("Temperature", "K")},
                  {"P": lambda V, n, T: n * C["R"] * T / V, "V": lambda P, n, T: n * C["R"] * T / P, "n": lambda P, V, T: P * V / (C["R"] * T), "T": lambda P, V, n: P * V / (n * C["R"])}, ("R",)),
    "moles": ("Moles from mass", "Chemistry", "n = m / M", {"n": ("Amount", "mol"), "m": ("Mass", "g"), "M": ("Molar mass", "g/mol")},
              {"n": lambda m, M: m / M, "m": lambda n, M: n * M, "M": lambda m, n: m / n}, ()),
    "molarity": ("Molarity", "Chemistry", "c = n / V", {"c": ("Concentration", "mol/L"), "n": ("Amount", "mol"), "V": ("Volume", "L")},
                 {"c": lambda n, V: n / V, "n": lambda c, V: c * V, "V": lambda n, c: n / c}, ()),
}


def fmt(x):
    return f"{x:.6g}"


def library():
    out = []
    for fid, (name, subject, eq, vars_, solvers, consts) in FORMULAS.items():
        out.append({"id": fid, "name": name, "subject": subject, "equation": eq,
                    "variables": [{"symbol": k, "name": v[0], "unit": v[1], "solvable": k in solvers} for k, v in vars_.items()],
                    "constants": {k: C[k] for k in consts}})
    return out


def subjects():
    return sorted({f["subject"] for f in library()} | {"Mathematics"})


def solve(fid, values, target):
    if fid not in FORMULAS:
        raise CrystaError("Unknown formula.")
    name, subject, eq, vars_, solvers, consts = FORMULAS[fid]
    if target not in solvers:
        raise CrystaError(f"This tool can't solve for {target} in {name}.")
    needed = [k for k in vars_ if k != target]
    # only the variables the chosen solver actually takes
    import inspect
    params = list(inspect.signature(solvers[target]).parameters)
    missing = [p for p in params if p not in values]
    if missing:
        raise CrystaError("Please fill in: " + ", ".join(missing))
    try:
        args = {p: float(values[p]) for p in params}
    except (TypeError, ValueError):
        raise CrystaError("All values must be numbers.")
    try:
        res = solvers[target](**args)
    except ZeroDivisionError:
        raise CrystaError("That would divide by zero.")
    except (ValueError, OverflowError):
        raise CrystaError("Those numbers have no real solution (check signs and units).")
    if isinstance(res, complex) or math.isnan(res) or math.isinf(res):
        raise CrystaError("Those numbers have no real solution.")
    unit = vars_[target][1]
    sub = ", ".join(f"{k} = {fmt(v)} {vars_[k][1]}" for k, v in args.items())
    used = ", ".join(f"{k} = {C[k]:g}" for k in consts)
    return {"formula": name, "equation": eq, "target": target, "result": res, "unit": unit,
            "steps": [f"Equation: {eq}", f"Known: {sub}" + (f"; constants: {used}" if used else ""), f"Result: {target} = {fmt(res)} {unit}"],
            "note": "Use SI units unless the variable says otherwise."}


def plot(expr, lo=-10.0, hi=10.0, n=240):
    if not (isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and lo < hi and hi - lo <= 1e6):
        raise CrystaError("Choose a sensible x range.")
    pts = []
    for i in range(n + 1):
        x = lo + (hi - lo) * i / n
        try:
            y = float(calculator.evaluate_num(expr, {"x": x}))
            pts.append([x, y if math.isfinite(y) and abs(y) < 1e12 else None])
        except (ValueError, ZeroDivisionError, OverflowError):
            pts.append([x, None])
    if all(p[1] is None for p in pts):
        raise CrystaError("I couldn't evaluate that function. Use x, numbers, + - * / ^, sqrt, sin, cos, tan, log, ln, exp, abs, pi, e.")
    return {"expression": expr, "points": pts}


def topics(knowledge_dirs):
    """Parse '## Subject' / '### Topic' sections from knowledge/science_topics.md into cards."""
    for d in knowledge_dirs:
        f = Path(d) / "science_topics.md"
        if f.is_file():
            subj, out, cur = None, [], None
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.startswith("## "):
                    subj = line[3:].strip()
                elif line.startswith("### "):
                    cur = {"subject": subj, "title": line[4:].strip(), "text": ""}
                    out.append(cur)
                elif cur and line.strip():
                    cur["text"] += (" " if cur["text"] else "") + line.strip()
            return out
    return []
