#!/usr/bin/env python3
"""Минимальный линтер модулей 1С по правилам Docs/CodingStandard.md (task_54, task_221).

Проверяет текстовые исходники .bsl в проекте 1C:EDT. Это НЕ замена vanessa-runner и
SonarQube/EDT-валидации: цель — научиться формализовать стандарт кодирования в
проверяемые правила и встроить их в CI.

Пример:
    python3 lint_bsl.py ../../Configuration/src --format text
    python3 lint_bsl.py ../../Configuration/src --format json --fail-on warning
"""
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List

MAX_PROCEDURE_LINES = 60
MAX_LINE_LENGTH = 140
MAX_MODULE_LINES = 1500

FORBIDDEN = [
    # Не ловим метод Запрос.Выполнить(): глобальная функция Выполнить(строка)
    # отличается тем, что перед ней нет точки/идентификатора (исправлено в task_8
    # после ложных срабатываний на текстах запросов).
    (re.compile(r"(?<![\w.])Выполнить\s*\(", re.IGNORECASE), "R001",
     "Выполнить() скрывает логику и ломает статический анализ — замените явным вызовом"),
    (re.compile(r"Перейти\s+~", re.IGNORECASE), "R003", "Перейти ~Метка затрудняет чтение кода"),
    (re.compile(r"\bЗапрос\s*=\s*Новый\s+Запрос\s*\(\s*\"", re.IGNORECASE), "R004",
     "Текст запроса должен собираться в переменной с комментариями, а не инлайн в конструкторе"),
    (re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af\u0600-\u06ff]"), "R006",
     "Символы чужой письменности (иероглифы, кана, хангыль, арабская вязь) — обычно следствие вставки"),
]

# Правила, которые зависят от контекста строки, проверяются отдельно от FORBIDDEN.
# R002: Сообщить() допустим только в клиентском контексте (&НаКлиенте).
MESSAGE_CALL = re.compile(r"\bСообщить\s*\(", re.IGNORECASE)
# R005: отступ пробелами ищем только вне строковых литералов — текст запроса
# форматируется по своим правилам (Docs/CodingStandard.md, §3).
INDENT_SPACES = re.compile(r"^ {4,}\S")
# Директивы компиляции: по ним определяем, серверный код перед нами или клиентский.
CONTEXT_DIRECTIVE = re.compile(r"^&(НаКлиентеНаСервере|НаКлиенте|НаСервере)(БезКонтекста)?$", re.IGNORECASE)

# Рекомендации: не блокируют сборку, но видны в отчёте (severity = info).
RECOMMENDED = [
    (re.compile(r"^\s*(Процедура|Функция)\s+\w+\s*\(.*\)\s*Экспорт", re.IGNORECASE), "R200",
     "Экспортный метод без комментария выше: опишите назначение, параметры и возвращаемое значение"),
]


class Issue:
    def __init__(self, path: str, line: int, code: str, severity: str, message: str) -> None:
        self.path = path
        self.line = line
        self.code = code
        self.severity = severity
        self.message = message

    def as_dict(self) -> Dict[str, object]:
        return {"file": self.path, "line": self.line, "rule": self.code,
                "severity": self.severity, "message": self.message}

    def __str__(self) -> str:
        return f"{self.path}:{self.line} [{self.severity}] {self.code} {self.message}"


def check_file(path: Path) -> List[Issue]:
    issues: List[Issue] = []
    relative = path.as_posix()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()

    if len(lines) > MAX_MODULE_LINES:
        issues.append(Issue(relative, 1, "R100", "warning",
                            f"модуль {len(lines)} строк (порог {MAX_MODULE_LINES}) — нужен план рефакторинга (task_217, task_219)"))

    procedure_start: Dict[str, int] = {}
    procedure_name = ""
    in_string_literal = False
    context = ""          # "" = не объявлен: для общего модуля считаем код серверным

    for number, raw in enumerate(lines, start=1):
        line = raw.rstrip()
        stripped = line.strip()
        starts_in_string = in_string_literal

        if len(line) > MAX_LINE_LENGTH:
            issues.append(Issue(relative, number, "R101", "info",
                                f"строка {len(line)} символов (порог {MAX_LINE_LENGTH})"))

        if stripped.count('"') % 2 == 1:
            in_string_literal = not in_string_literal

        directive = CONTEXT_DIRECTIVE.match(stripped)
        if directive:
            context = directive.group(1).lower()

        match = re.match(r"^\s*(Процедура|Функция)\s+(\w+)", stripped, re.IGNORECASE)
        if match and not in_string_literal:
            procedure_name = match.group(2)
            procedure_start[procedure_name] = number

        end_match = re.match(r"^\s*Конец(Процедуры|Функции)", stripped, re.IGNORECASE)
        if end_match and procedure_name and not in_string_literal:
            length = number - procedure_start.get(procedure_name, number)
            if length > MAX_PROCEDURE_LINES:
                issues.append(Issue(relative, procedure_start.get(procedure_name, number), "R102", "warning",
                                    f"метод {procedure_name}: {length} строк (порог {MAX_PROCEDURE_LINES})"))
            procedure_name = ""
            context = ""

        if not starts_in_string and not stripped.startswith("//"):
            if INDENT_SPACES.match(line):
                issues.append(Issue(relative, number, "R005", "error",
                                    "Отступ пробелами: стандарт требует табуляцию (1 таб на уровень вложенности)"))

            if MESSAGE_CALL.search(line) and context != "наклиенте":
                issues.append(Issue(relative, number, "R002", "error",
                                    "Сообщить() вне клиентского контекста: выведите сообщение пользователю "
                                    "на клиенте или пишите в журнал регистрации (task_50, task_51)"))

            for pattern, code, message in FORBIDDEN:
                if pattern.search(line):
                    issues.append(Issue(relative, number, code, "error", message))

        if not stripped.startswith("//"):
            for pattern, code, message in RECOMMENDED:
                if not pattern.search(line):
                    continue
                # пропускаем строки директив компиляции (&НаКлиенте и т. п.): комментарий
                # к методу стоит выше них
                previous = next((candidate.strip() for candidate in reversed(lines[:number - 1])
                                 if candidate.strip() and not CONTEXT_DIRECTIVE.match(candidate.strip())), "")
                if not previous.startswith("//"):
                    issues.append(Issue(relative, number, code, "info", message))

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Линтер модулей 1С (.bsl)")
    parser.add_argument("path", help="файл или каталог с исходниками")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--fail-on", choices=["error", "warning", "info"], default="error",
                        help="минимальная серьёзность, при которой возврат будет ненулевым")
    args = parser.parse_args()

    root = Path(args.path)
    if not root.exists():
        print(f"путь не найден: {root}", file=sys.stderr)
        return 2

    files = [root] if root.is_file() else sorted(root.rglob("*.bsl"))
    if not files:
        print(f"модули .bsl не найдены в {root}", file=sys.stderr)
        return 0

    all_issues: List[Issue] = []
    for file in files:
        all_issues.extend(check_file(file))

    if args.format == "json":
        print(json.dumps({"files": len(files), "issues": [i.as_dict() for i in all_issues]},
                         ensure_ascii=False, indent=2))
    else:
        print(f"проверено файлов: {len(files)}, замечаний: {len(all_issues)}")
        for issue in all_issues:
            print(issue)

    severity_rank = {"info": 0, "warning": 1, "error": 2}
    threshold = severity_rank[args.fail_on]
    blocking = [i for i in all_issues if severity_rank[i.severity] >= threshold]
    return 1 if blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())
