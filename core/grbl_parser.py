"""GRBL response parsing helpers and general utility functions.

Pure-logic module — no PySide6 / Qt dependencies.
Contains functions for parsing GRBL status responses, G-code lines,
and general-purpose helpers.
"""

import re
import time
from pathlib import Path


def clamp(n, lo, hi):
    return max(lo, min(hi, n))


def _read_text(path: str) -> list[str]:
    return Path(path).read_text(encoding="utf-8", errors="ignore").splitlines()


def _ts():
    return time.strftime("%H:%M:%S")


def _strip_gcode_line(line: str) -> str:
    if ";" in line:
        line = line.split(";", 1)[0]
    line = re.sub(r"\(.*?\)", "", line)
    return line.strip()


def _parse_words(line: str) -> dict:
    out = {}
    for tok in line.split():
        if len(tok) < 2:
            continue
        k, v = tok[0].upper(), tok[1:]
        try:
            out[k] = int(float(v)) if k in ("G", "M") else float(v)
        except ValueError:
            pass
    return out


def parse_xyz(csv_str: str):
    parts = csv_str.split(",")
    if len(parts) < 3:
        return None
    try:
        return float(parts[0]), float(parts[1]), float(parts[2])
    except ValueError:
        return None


def extract_field(line: str, key: str):
    token = f"{key}:"
    if token not in line:
        return None
    try:
        return line.split(token, 1)[1].split("|", 1)[0].strip()
    except Exception:
        return None


def extract_state(line: str):
    if not (line.startswith("<") and line.endswith(">")):
        return None
    try:
        return line[1:-1].split("|", 1)[0].strip()
    except Exception:
        return None
