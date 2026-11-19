# -*- coding: utf-8 -*-
"""
Генератор карты «задание → артефакт» (ArtifactMap.md).

Собирает из данных заданий (1c/tools/q*_data_*.py) все ресурсы,
которые студент создаёт или использует, и помечает статус:
  [есть]        — файл/каталог уже лежит в стенде, можно читать;
  [создаётся]   — артефакт рождается в самом задании, путь — адрес результата.

Запуск:
  python3 1c/tools/build_artifact_map.py           # перегенерировать карту
  python3 1c/tools/build_artifact_map.py --check   # только проверить актуальность
"""
import glob
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))  # 1c/
OUT = os.path.join(ROOT, "internship", "documentation", "ArtifactMap.md")


def load_tasks():
    tasks = {}
    for path in sorted(glob.glob(os.path.join(HERE, "q*_data_*.py"))):
        name = os.path.basename(path)[:-3]
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for sprint in getattr(module, "SPRINTS", []):
            for t in sprint["tasks"]:
                tasks[t["num"]] = t
    return tasks


def render(tasks):
    lines = [
        "# Карта артефактов: задание → что должно появиться",
        "",
        "Сгенерировано из данных заданий (`1c/tools/build_artifact_map.py`), не править руками.",
        "Статус: **[есть]** — уже лежит в стенде, можно читать до задания;",
        "**[создаётся]** — артефакт рождается в этом задании, путь — адрес результата.",
        "",
    ]
    quarter_of = {}
    for n in sorted(tasks):
        quarter_of[n] = 1 if n <= 72 else 2 if n <= 150 else 3 if n <= 228 else 4
    for q in (1, 2, 3, 4):
        nums = [n for n in sorted(tasks) if quarter_of[n] == q and tasks[n].get("resources")]
        if not nums:
            continue
        lines.append("## Q%d" % q)
        lines.append("")
        lines.append("| Задание | Артефакты (путь от `1c/`) |")
        lines.append("|---|---|")
        for n in nums:
            arts = []
            for r in tasks[n]["resources"]:
                exists = os.path.exists(os.path.join(ROOT, r))
                arts.append("`%s` %s" % (r, "[есть]" if exists else "[создаётся]"))
            title = tasks[n]["title"].replace("|", "/")
            lines.append("| task_%d. %s | %s |" % (n, title, "<br>".join(arts)))
        lines.append("")
    return "\n".join(lines)


def main():
    tasks = load_tasks()
    text = render(tasks)
    if "--check" in sys.argv:
        current = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        if current != text:
            print("ArtifactMap.md устарела: перегенерируйте build_artifact_map.py")
            return 1
        print("ArtifactMap.md актуальна")
        return 0
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text)
    print("Записано:", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
