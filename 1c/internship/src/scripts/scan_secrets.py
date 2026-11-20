#!/usr/bin/env python3
"""Сканер секретов репозитория (task_134).

Ищет в рабочем дереве: известные форматы ключей (AWS, GitHub,
Slack, приватные ключи), присвоения паролей литералами, .env
в индексе Git. Учебные секреты стенда (mock-*-key и пароли моков
из их README) — документированный allowlist: учебный ключ — это
контур стенда, а не продакшен. Сканер обязан зажечься на тестовом
«боевом» секрете — самопроверка в checks_secrets.py.

Использование:
    scan_secrets.py [путь ...]     # по умолчанию — текущее дерево

Возврат: 0 — чисто; 1 — найдены кандидаты (файл и строка, без
самого секрета в отчёте).
"""

from __future__ import annotations

import math
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

PATTERNS = [
    ("ключ AWS", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("токен GitHub", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("токен Slack", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("приватный ключ", re.compile(r"-----BEGIN (RSA|OPENSSH|EC) PRIVATE KEY-----")),
    ("пароль литералом", re.compile(
        r"(?i)(password|passwd|пароль)\s*[:=]\s*[\"'][^\"'\s]{6,}[\"']")),
    ("секрет литералом", re.compile(
        r"(?i)(api[_-]?key|secret)\s*[:=]\s*[\"'][A-Za-z0-9_\-/+]{16,}[\"']")),
]

# Учебный контур стенда: ключи моков публичны из их README и не
# открывают ничего вне стенда. Боевой секрет в allowlist не попадёт.
ALLOWLIST = [
    re.compile(r"mock-[a-z-]*-key"),
    re.compile(r"bank_user|bank_password"),
    re.compile(r"CHANGE_ME|example|placeholder|заглушка", re.IGNORECASE),
]

SKIP_DIRS = {".git", "node_modules", ".venv", ".venv-tools", "__pycache__",
             ".venv-1c", "build"}
TEXT_SUFFIXES = {".py", ".bsl", ".md", ".txt", ".yml", ".yaml", ".json",
                 ".xml", ".sh", ".ini", ".cfg", ".toml", ".env", ".example", ""}


def allowed(line: str) -> bool:
    return any(pattern.search(line) for pattern in ALLOWLIST)


def entropy(text: str) -> float:
    if not text:
        return 0.0
    counts = Counter(text)
    total = len(text)
    return -sum((count / total) * math.log2(count / total)
                for count in counts.values())


def scan_file(path: Path) -> list[str]:
    findings = []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return findings
    for number, line in enumerate(lines, 1):
        if allowed(line):
            continue
        for name, pattern in PATTERNS:
            if pattern.search(line):
                findings.append(f"{path}:{number}: похоже на {name}")
                break
        else:
            literal = re.search(r"[\"']([A-Za-z0-9_\-/+]{24,})[\"']", line)
            if literal and entropy(literal.group(1)) > 4.5 \
                    and re.search(r"(?i)(key|token|secret|парол|passw)", line):
                findings.append(f"{path}:{number}: строка высокой энтропии у секрета")
    return findings


def scan_tree(root: Path) -> list[str]:
    findings = []
    for path in sorted(root.rglob("*")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix in TEXT_SUFFIXES and path.stat().st_size < 2_000_000:
            findings.extend(scan_file(path))
    return findings


def env_tracked(root: Path) -> list[str]:
    proc = subprocess.run(["git", "ls-files"], cwd=root,
                          capture_output=True, text=True)
    if proc.returncode != 0:
        return []
    return [f"{root}: файл {line} отслеживается Git (.env — утечка)"
            for line in proc.stdout.splitlines()
            if line.rsplit("/", 1)[-1] == ".env"]


def main(argv: list[str]) -> int:
    roots = [Path(arg) for arg in argv] or [Path.cwd()]
    findings: list[str] = []
    for root in roots:
        findings.extend(scan_tree(root))
        findings.extend(env_tracked(root))
    if findings:
        print("Найдены кандидаты в секреты (значения не печатаются):")
        for finding in findings:
            print(" -", finding)
        return 1
    print("Секретов не найдено: дерево чисто по шаблонам сканера")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
