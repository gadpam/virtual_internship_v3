# -*- coding: utf-8 -*-
"""
Генератор программы стажировки 1С.

Читает данные по кварталам (q1_data_a.py, q1_data_b.py, q2_data.py, q3_data.py, q4_data.py)
и создаёт:
  1c/project/sprint_N/SprintOverview.txt
  1c/project/sprint_N/task_M/YourTask.txt
  1c/project/sprint_N/task_M_code_review/CodeReviewTask.txt   (после каждого спринта)
  1c/project/Project_content_task_by_task.txt                 (оглавление года)

Запуск: python3 1c/tools/build_program.py
"""
import os
import sys
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
PROJECT = os.path.join(ROOT, "project")

FOOTER = """
#### Поддержка, вопросы и обратная связь по проекту:
* Телеграм-группа потока (ссылку выдаёт ментор)
* Телеграм автора: (@your_mentor_handle)
* Емейл: (your_email@example.com)
"""

SPRINT_TEMPLATE = """СПРИНТ {n} · {quarter} · {theme}

ЦЕЛЬ СПРИНТА
{goal}

РАМКИ
Спринт = одна неделя = 6 заданий: task_{first} ... task_{last}.
Темп: 2 задания в начале недели, 2 в середине, 1 в пятницу, 1 в выходной
+ рефлексия по всем заданиям недели.

ЗАДАНИЯ СПРИНТА
{task_list}

РЕЗУЛЬТАТЫ СПРИНТА (что должно появиться к выходным)
{outcomes}

СВЯЗЬ С ТРЕБОВАНИЯМИ РЫНКА
{links}

МАТЕРИАЛЫ
{resources}

ПРАВИЛА СПРИНТА
1. Не переходите к следующему заданию, пока не закрыто предыдущее (см. DefinitionOfDone.txt).
2. После каждого задания заполняйте internship/documentation/task_N_description.txt.
3. С task_31 каждое задание = отдельный атомарный коммит с сообщением "task_N: ...".
4. Застряли дольше 30 минут — формулируйте вопрос письменно (шаблон в DefinitionOfReady.txt)
   и идите к команде/ментору.
5. В конце спринта — code review (файл task_{last}_code_review/CodeReviewTask.txt).
{footer}"""


TASK_TEMPLATE = """ЗАДАНИЕ task_{num} · спринт {sprint} · {quarter}
Тема спринта: {theme}
{title}

Оценка времени: {time}

КОНТЕКСТ: зачем это нужно
{context}

ЗАДАНИЕ: что сделать
{task}

РЕЗУЛЬТАТ (Definition of Done):
{dod}

ПОДСКАЗКИ МЕНТОРА:
{hints}

МАТЕРИАЛЫ И ССЫЛКИ:
{resources}

НАПОМИНАНИЕ
- Работаем только в папке internship/ (папку project/ менять нельзя).
- После выполнения обязательно заполнить internship/documentation/task_{num}_description.txt
  (шаблон: project/documentation/task_0_description_template.txt).
- Общие критерии готовности: project/acceptance/DefinitionOfDone.txt
{footer}"""


CODE_REVIEW_TEMPLATE = """CODE REVIEW после спринта {sprint} ({quarter}: {theme})

Это не задание про код. Это задание про качество и про то, как вы умеете
объяснять и защищать свои решения.

ЧТО СДЕЛАТЬ
1. Соберите список того, что сделали за спринт: task_{first} ... task_{last}.
2. Пройдите чек-лист: project/acceptance/CodeReviewChecklist.txt
   (8 разделов: смысл, архитектура, стандарты, запросы, клиент-сервер,
   безопасность, тесты, документация/Git).
3. Для каждого раздела выпишите: что хорошо, что надо улучшить, что оставляем как есть.
4. Прогоните автоматические проверки: валидация EDT, статический анализ (АПК/Sonar),
   юнит-тесты, дымовые тесты. Приложите результат.
5. Отдайте код на ревью ментору или коллеге из потока. Соберите замечания в таблицу:
   замечание | критичность (Critical/Major/Minor) | решение | срок.
6. Закройте Critical и Major до старта следующего спринта. Minor — в backlog.
7. Напишите ответ ревьюеру: что принято, что отклонено и почему (аргументы, не эмоции).
8. Заполните рефлексию task_{last}_code_review_description.txt:
   три главных вывода о своём коде за спринт.

ФОРМАТ ОТВЕТА РЕВЬЮЕРУ
  Замечание: ...
  Согласен/не согласен: ...
  Аргумент: ...
  Что сделал: ... (коммит / задача в backlog с приоритетом)

КРИТЕРИИ ЗАКРЫТИЯ CODE REVIEW
- Нет открытых замечаний уровня Critical.
- Автоматические проверки зелёные (или падения объяснены и заведены в backlog).
- Таблица замечаний и ответ ревьюеру сохранены в internship/documentation/reviews/.
- Рефлексия заполнена.

ЗАЧЕМ ЭТО НУЖНО
Код-ревью — самая быстрая форма обучения в профессии. За год вы пройдёте 52 ревью.
Разница между стажёром и Middle чаще всего не в знаниях синтаксиса, а в том,
сколько раз его код разобрали чужие глаза.
{footer}"""


def load_data():
    """Загружает все файлы данных q*_data*.py и склеивает спринты. Порядок — по имени файла."""
    import glob
    sprints = []
    paths = sorted(glob.glob(os.path.join(HERE, "q*_data*.py")))
    if not paths:
        print("  [skip] файлы данных не найдены")
    for path in paths:
        module_name = os.path.splitext(os.path.basename(path))[0]
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sprints.extend(module.SPRINTS)
        print("  [ok]   %s: спринтов %d" % (module_name, len(module.SPRINTS)))
    sprints.sort(key=lambda s: s["n"])
    return sprints


REQ_LINKS = {
    0: "Вход в проект: окружение, правила, DoD/DoR.",
    1: "VCS Git, инструменты разработки, декомпозиция задач, конвенции именования.",
    2: "Знание БСП и стандартов разработки 1С, роли и права, статический анализ.",
    3: "Уверенное владение языком 1С, работа с данными, параметры запросов.",
    4: "Проектирование и разработка ПО на 1С 8.х: модель данных складского учёта.",
    5: "Уверенное владение языком запросов, навыки делового общения (вопросы аналитику).",
    6: "Уверенное владение СКД: отчёты, варианты, программное формирование.",
    7: "Разработка интерфейсов, локализация, мобильная платформа 1С (первое знакомство).",
    8: "Надёжность: транзакции, блокировки, последовательности, фоновые задания.",
    9: "Качество: отладка, логирование, обработка ошибок, юнит- и приёмочные тесты.",
    10: "Опыт работы с большими объёмами данных: загрузка, пакеты, индексы, многопоточность.",
    11: "Наблюдаемость и автоматизация: ТЖР, АПК, нагрузочное тестирование, CI/CD, обновления.",
    12: "Milestone Q1: code review, демо, защита архитектуры, ретроспектива, портфолио.",
}


def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def bullet_list(items, indent=""):
    return "\n".join(indent + "- " + item for item in items)


def numbered(items):
    return "\n".join(items if item.lstrip().startswith(tuple("0123456789")) else "- " + item
                     for item in items)


def build_sprint(sprint, tasks):
    n = sprint["n"]
    first, last = tasks[0]["num"], tasks[-1]["num"]
    links = REQ_LINKS.get(n, "")
    if not links:
        links = sprint.get("links", "")
    content = SPRINT_TEMPLATE.format(
        n=n,
        quarter=sprint["quarter"],
        theme=sprint["theme"],
        goal=sprint["goal"],
        first=first,
        last=last,
        task_list="\n".join("task_%d — %s (%s)" % (t["num"], t["title"], t["time"]) for t in tasks),
        outcomes=bullet_list(sprint["outcomes"]),
        links=links,
        resources=bullet_list(sprint.get("resources", [])),
        footer=FOOTER,
    )
    write_file(os.path.join(PROJECT, "sprint_%d" % n, "SprintOverview.txt"), content)


def build_tasks(sprint):
    n = sprint["n"]
    for t in sprint["tasks"]:
        content = TASK_TEMPLATE.format(
            num=t["num"],
            sprint=n,
            quarter=sprint["quarter"],
            theme=sprint["theme"],
            title=t["title"],
            time=t["time"],
            context=t["context"].strip(),
            task=t["task"].strip(),
            dod=bullet_list(t["dod"]),
            hints=bullet_list(t.get("hints", [])),
            resources=bullet_list(t.get("resources", [])),
            footer=FOOTER,
        )
        write_file(os.path.join(PROJECT, "sprint_%d" % n, "task_%d" % t["num"], "YourTask.txt"), content)
        # карточка code review после каждого спринта
    first, last = sprint["tasks"][0]["num"], sprint["tasks"][-1]["num"]
    cr = CODE_REVIEW_TEMPLATE.format(
        sprint=n, quarter=sprint["quarter"], theme=sprint["theme"],
        first=first, last=last, footer=FOOTER,
    )
    write_file(os.path.join(PROJECT, "sprint_%d" % n, "task_%d_code_review" % last, "CodeReviewTask.txt"), cr)


def build_content_file(sprints):
    lines = []
    lines.append("Программа проекта «Виртуальная Стажировка 1С — ГОД»")
    lines.append("Сквозной проект: Retail Integration Hub (RIH), торговый холдинг «Ритейл Групп»")
    lines.append("")
    total_tasks = sum(len(s["tasks"]) for s in sprints)
    lines.append("Масштаб: %d кварталов · %d спринтов · %d заданий · %d code review"
                 % (len(set(s["quarter"] for s in sprints)), len(sprints), total_tasks, len(sprints)))
    lines.append("Для сравнения: Виртуальная Стажировка Java — 263 задания, 3-4 месяца.")
    lines.append("")
    lines.append("Файл собирается автоматически: python3 1c/tools/build_program.py")
    lines.append("Данные программы: 1c/tools/q1_data_a.py, q1_data_b.py, q2_data.py, q3_data.py, q4_data.py")
    lines.append("")
    current_quarter = None
    quarter_titles = {
        "Q1": "КВАРТАЛ 1 · ПЛАТФОРМА, КОНФИГУРАЦИЯ, ЗАПРОСЫ, СКД, КАЧЕСТВО (испытательный срок)",
        "Q2": "КВАРТАЛ 2 · ИНТЕГРАЦИИ И ОБМЕНЫ (HTTP, SOAP, OData, JSON, XML, КД 2/3, очереди)",
        "Q3": "КВАРТАЛ 3 · УЧЁТНЫЕ СИСТЕМЫ, ДАННЫЕ И ПРОИЗВОДИТЕЛЬНОСТЬ (БП, ДО, MS SQL, BI)",
        "Q4": "КВАРТАЛ 4 · AI-КОНТУР, МОБИЛЬНОСТЬ, ЭКСПЛУАТАЦИЯ И ЗАЩИТА ГОДА (Python, RAG, CI/CD)",
    }
    for s in sprints:
        if s["quarter"] != current_quarter:
            current_quarter = s["quarter"]
            lines.append("")
            lines.append("=" * 78)
            lines.append(quarter_titles.get(current_quarter, current_quarter))
            lines.append("=" * 78)
        lines.append("")
        lines.append("SPRINT %d · %s" % (s["n"], s["theme"]))
        lines.append("-" * 78)
        for t in s["tasks"]:
            lines.append("task_%d - %s" % (t["num"], t["title"]))
        lines.append("")
        lines.append("task_%d_code_review - Code review по итогам спринта %d" % (s["tasks"][-1]["num"], s["n"]))
    lines.append("")
    lines.append("=" * 78)
    lines.append("ФИНАЛ ГОДА: защита годового проекта, портфолио, план развития (task_312)")
    lines.append("=" * 78)
    write_file(os.path.join(PROJECT, "Project_content_task_by_task.txt"), "\n".join(lines) + "\n")


def main():
    print("Загрузка данных программы...")
    sprints = load_data()
    if not sprints:
        print("Нет данных — нечего собирать.")
        return 1
    nums = [t["num"] for s in sprints for t in s["tasks"]]
    dups = set(x for x in nums if nums.count(x) > 1)
    if dups:
        print("ВНИМАНИЕ: дублирующиеся номера заданий: %s" % sorted(dups))
    gaps = [i for i in range(min(nums), max(nums) + 1) if i not in nums]
    if gaps:
        print("ВНИМАНИЕ: пропуски в нумерации: %s" % gaps)
    print("Сборка файлов...")
    for s in sprints:
        build_sprint(s, s["tasks"])
        build_tasks(s)
    build_content_file(sprints)
    print("Готово: %d спринтов, %d заданий, %d code review." % (len(sprints), len(nums), len(sprints)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
