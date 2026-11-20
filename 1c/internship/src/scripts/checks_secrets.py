#!/usr/bin/env python3
"""Проверки task_134: сканер секретов и гигиена репозитория.

Сканер обязан: зажечься на тестовом «боевом» секрете, пропустить
учебные ключи стенда (allowlist), не найти секретов в текущем
дереве репозитория и подтвердить, что .env не отслеживается Git.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_secrets.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from scan_secrets import env_tracked, scan_tree  # noqa: E402

INTERN = Path(__file__).resolve().parents[2]
REPO = Path(__file__).resolve().parents[4]


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        combat = Path(tmp) / "leaked.py"
        # Фикстура собирается по частям: боевой формат целиком
        # в этом файле не лежит, иначе сканер ловит сам тест.
        fake_key = "AK" + "IA" + "Z" * 4 + "1234ABCDWXYZ"
        combat.write_text(
            f'AWS_KEY = "{fake_key}"\n'
            'db_pass' 'word = "prod-pass-2026"\n', encoding="utf-8")
        hits = scan_tree(Path(tmp))
        assert len(hits) >= 2, hits
        print(f"[ok] стража зажигается на тестовом боевом секрете: {len(hits)} находки")

        study = Path(tmp) / "study.py"
        study.write_text('KEY = "mock-loyalty-key"\n', encoding="utf-8")
        combat.unlink()
        assert scan_tree(Path(tmp)) == []
        print("[ok] учебные ключи стенда из allowlist сканер пропускает")

    assert scan_tree(INTERN) == [], scan_tree(INTERN)[:5]
    print("[ok] текущее дерево internship: секретов по шаблонам сканера нет")
    assert env_tracked(REPO) == []
    print("[ok] .env в индексе Git отсутствует (шаблон .env.example — без значений)")

    import re
    proc = subprocess.run(
        ["git", "log", "--all", "-p", "--unified=0", "-n", "300"],
        cwd=REPO, capture_output=True, text=True)
    combat_formats = re.compile(r"AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,}")
    # Единственное исключение — тестовое значение фикстуры этого
    # файла (AKIA + ZZZZ...): выдуманный ключ из коммита task_134,
    # настоящим секретом не был и ротации не требует. Всё остальное
    # боевого формата в истории — утечка.
    fake_fixture = "AKIA" + "ZZZZ1234ABCDWXYZ"  # по частям: см. выше
    leaked = [line for line in proc.stdout.splitlines()
              if line.startswith("+") and combat_formats.search(line)
              and "AKIA[0-9A-Z]" not in line
              and fake_fixture not in line]
    assert not leaked, leaked[:2]
    print("[ok] история Git (300 коммитов): боевых форматов ключей не найдено")


if __name__ == "__main__":
    main()
