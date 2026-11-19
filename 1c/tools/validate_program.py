# -*- coding: utf-8 -*-
"""
Валидатор программы стажировки 1С.

Проверяет источник истины (1c/tools/q*_data_*.py) и сгенерированную
программу (1c/project/**/YourTask.txt) на:

  1. компиляцию всех модулей данных и генератора (py_compile);
  2. целостность данных: номера заданий уникальны и непрерывны,
     названия не дублируются, у каждого задания есть DoD, подсказки
     и время формата «N ч»;
  3. перекрёстные ссылки task_NNN / sprint_NN — все существуют;
  4. сгенерированные файлы: легенда >= 6 непустых строк, теория
     >= 30 строк (сегмент ТЕОРИЯ), одно задание — один файл;
  5. шаблонность теории: абзац длиннее 80 символов, повторённый
     в 3+ заданиях, — ошибка; в 2 заданиях — предупреждение;
  6. баланс часов: суммы по кварталам (из времён заданий) совпадают
     с таблицей Roadmap.md;
  7. число code review равно числу спринтов;
  8. идемпотентность генератора: повторная сборка не меняет файлы.

Предупреждения (не валят прогон): ресурсы-артефакты, которых ещё нет
на диске (они создаются самими заданиями), и «тонкие» теории
(<= 33 строки при минимуме 30).

Запуск:
  python3 1c/tools/validate_program.py [--skip-idempotency] [--tests]
Выход: 0 — ошибок нет; 1 — есть ошибки.
"""
import argparse
import hashlib
import importlib.util
import os
import py_compile
import re
import subprocess
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))          # 1c/
REPO = os.path.abspath(os.path.join(ROOT, ".."))           # корень репозитория
PROJECT = os.path.join(ROOT, "project")
INTERNSHIP = os.path.join(ROOT, "internship")

FAILS = []
WARNS = []


def fail(msg):
    FAILS.append(msg)
    print("  [FAIL] " + msg)


def warn(msg):
    WARNS.append(msg)
    print("  [warn] " + msg)


def ok(msg):
    print("  [ ok ] " + msg)


def load_data():
    """Загрузить все модули q*_data_*.py, вернуть (tasks, sprints, quarters)."""
    import glob
    tasks, sprints = {}, []
    quarters = {}
    for path in sorted(glob.glob(os.path.join(HERE, "q*_data_*.py"))):
        name = os.path.basename(path)[:-3]
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        quarter = name.split("_")[0]  # q1..q4
        for sprint in getattr(module, "SPRINTS", []):
            sprints.append(sprint)
            for t in sprint["tasks"]:
                if t["num"] in tasks:
                    fail("дублирующийся номер задания: task_%d" % t["num"])
                tasks[t["num"]] = t
                quarters[t["num"]] = quarter
    return tasks, sprints, quarters


def check_compile():
    print("1. Компиляция модулей (py_compile)")
    import glob
    bad = 0
    for path in sorted(glob.glob(os.path.join(HERE, "*.py"))):
        try:
            py_compile.compile(path, doraise=True)
        except py_compile.PyCompileError as e:
            fail("не компилируется %s: %s" % (os.path.basename(path), e))
            bad += 1
    if not bad:
        ok("все модули 1c/tools компилируются")


def check_data(tasks, sprints, quarters):
    print("2. Целостность данных заданий")
    nums = sorted(tasks)
    if nums != list(range(len(nums))):
        fail("номера заданий не непрерывны: %d заданий, диапазон %d..%d"
             % (len(nums), nums[0], nums[-1]))
    else:
        ok("%d заданий, номера 0..%d непрерывны" % (len(nums), nums[-1]))
    titles = [t["title"] for t in tasks.values()]
    dup_titles = [x for x in set(titles) if titles.count(x) > 1]
    if dup_titles:
        fail("дублирующиеся названия заданий: %s" % dup_titles)
    for n, t in sorted(tasks.items()):
        if not t.get("dod") or len(t["dod"]) < 3:
            fail("task_%d: DoD короче 3 пунктов" % n)
        if not t.get("hints"):
            fail("task_%d: нет подсказок (hints)" % n)
        if not re.fullmatch(r"\d+ ч", str(t.get("time", "")).strip()):
            fail("task_%d: странное время %r" % (n, t.get("time")))
    ok("DoD, hints и время на месте у всех заданий")

    print("3. Перекрёстные ссылки")
    n_sprints = len(sprints)
    bad_refs = []
    for n, t in sorted(tasks.items()):
        blob = " ".join(str(t.get(k, "")) for k in ("context", "task", "hints"))
        for m in re.findall(r"task_(\d+)", blob):
            if int(m) not in tasks:
                bad_refs.append((n, "task_" + m))
        for m in re.findall(r"sprint_(\d+)", blob):
            if not (0 <= int(m) < n_sprints):
                bad_refs.append((n, "sprint_" + m))
    if bad_refs:
        fail("битые ссылки: %s" % bad_refs[:10])
    else:
        ok("все ссылки task_NNN и sprint_NN существуют (%d спринтов)" % n_sprints)
    return n_sprints


def check_generated(tasks):
    print("4. Сгенерированные файлы (легенда, теория, дубли абзацев)")
    import glob
    files = {}
    for p in glob.glob(os.path.join(PROJECT, "**", "YourTask.txt"), recursive=True):
        m = re.search(r"task_(\d+)", p)
        if m:
            files.setdefault(int(m.group(1)), []).append(p)
    for n in sorted(tasks):
        if n not in files:
            fail("task_%d: нет YourTask.txt" % n)
        elif len(files[n]) > 1:
            fail("task_%d: несколько YourTask.txt: %s" % (n, files[n]))
    para_owner = defaultdict(set)
    thin = []
    for n, paths in sorted(files.items()):
        s = open(paths[0], encoding="utf-8").read()
        if "ЛЕГЕНДА" not in s or "ТЕОРИЯ" not in s:
            fail("task_%d: нет раздела ЛЕГЕНДА или ТЕОРИЯ" % n)
            continue
        legend = s.split("ЛЕГЕНДА", 1)[1].split("ТЕОРИЯ", 1)[0]
        n_legend = len([l for l in legend.splitlines() if l.strip()])
        if n_legend < 6:
            fail("task_%d: легенда короче 6 строк (%d)" % (n, n_legend))
        seg = s.split("ТЕОРИЯ", 1)[1].split("ЗАДАНИЕ:", 1)[0]
        n_theory = len(seg.splitlines())
        if n_theory < 30:
            fail("task_%d: теория короче 30 строк (%d)" % (n, n_theory))
        elif n_theory <= 33:
            thin.append(n)
        for par in seg.split("\n\n"):
            t = " ".join(par.split())
            if len(t) > 80:
                para_owner[t].add(n)
    dups3 = {k: v for k, v in para_owner.items() if len(v) >= 3}
    dups2 = {k: v for k, v in para_owner.items() if len(v) == 2}
    if dups3:
        for k, v in list(dups3.items())[:5]:
            fail("шаблонный абзац теории в %d заданиях %s: %s..."
                 % (len(v), sorted(v)[:6], k[:70]))
    else:
        ok("шаблонных абзацев теории (3+ заданий) нет")
    if dups2:
        warn("абзацев теории, повторённых в 2 заданиях: %d" % len(dups2))
    if thin:
        warn("тонких теорий (30-33 строки): %d %s" % (len(thin), thin[:12]))
    else:
        ok("легенды и теории всех заданий в норме")


def check_hours(tasks, quarters):
    print("5. Баланс часов против Roadmap.md")
    sums = defaultdict(int)
    counts = defaultdict(int)
    for n, t in tasks.items():
        sums[quarters[n]] += int(str(t["time"]).split()[0])
        counts[quarters[n]] += 1
    roadmap = os.path.join(PROJECT, "Roadmap.md")
    text = open(roadmap, encoding="utf-8").read()
    found = {q: h for q, _cnt, h in
             re.findall(r"\bQ([1-4])\s*\|\s*(\d+)\s*\|\s*(\d+)\s*ч", text)}
    if not found:
        warn("не нашёл таблицу часов в Roadmap.md — сравнение пропущено")
        return
    for q in ("q1", "q2", "q3", "q4"):
        want = found.get(q[-1])
        if want is None:
            continue
        if sums[q] != int(want):
            fail("%s: сумма времён %d ч, в Roadmap.md — %s ч" % (q.upper(), sums[q], want))
    ok("часы по кварталам совпадают с Roadmap.md: "
       + ", ".join("Q%s=%d" % (q[-1], sums[q]) for q in ("q1", "q2", "q3", "q4")))


def check_reviews(n_sprints):
    print("6. Code review по спринтам")
    import glob
    reviews = glob.glob(os.path.join(PROJECT, "**", "CodeReviewTask.txt"), recursive=True)
    if len(reviews) != n_sprints:
        fail("CodeReviewTask.txt: %d, спринтов: %d" % (len(reviews), n_sprints))
    else:
        ok("%d code review на %d спринтов" % (len(reviews), n_sprints))


def check_resources(tasks):
    print("7. Ресурсы заданий (предупреждения)")
    missing = []
    for n, t in sorted(tasks.items()):
        for r in (t.get("resources") or []):
            if not os.path.exists(os.path.join(ROOT, r)):
                missing.append((n, r))
    warn("ресурсов-артефактов ещё нет на диске (создаются заданиями): %d" % len(missing))


def _hash_tree(base):
    out = {}
    for dirpath, _dirs, names in os.walk(base):
        for name in names:
            p = os.path.join(dirpath, name)
            with open(p, "rb") as f:
                out[os.path.relpath(p, base)] = hashlib.sha256(f.read()).hexdigest()
    return out


def check_idempotent():
    print("8. Идемпотентность генератора")
    before = _hash_tree(PROJECT)
    subprocess.run([sys.executable, os.path.join(HERE, "build_program.py")],
                   check=True, capture_output=True)
    after = _hash_tree(PROJECT)
    changed = [k for k in set(before) | set(after) if before.get(k) != after.get(k)]
    if changed:
        fail("генератор не идемпотентен, изменились: %s" % changed[:10])
    else:
        ok("повторная сборка не меняет файлы (%d файлов)" % len(after))


def check_tests():
    print("9. Тесты AI-сервиса (pytest)")
    svc = os.path.join(INTERNSHIP, "src", "ai_service")
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests"],
                       capture_output=True, text=True, cwd=svc)
    tail = (r.stdout + r.stderr).strip().splitlines()
    if r.returncode != 0:
        fail("pytest ai_service: %s" % (tail[-1] if tail else "ошибка"))
    else:
        ok("pytest ai_service: %s" % (tail[-1] if tail else "ок"))


def main():
    ap = argparse.ArgumentParser(description="Валидатор программы стажировки 1С")
    ap.add_argument("--skip-idempotency", action="store_true",
                    help="не перегенерировать программу при проверке")
    ap.add_argument("--tests", action="store_true",
                    help="дополнительно прогнать pytest AI-сервиса")
    args = ap.parse_args()

    tasks, sprints, quarters = load_data()
    check_compile()
    n_sprints = check_data(tasks, sprints, quarters)
    check_generated(tasks)
    check_hours(tasks, quarters)
    check_reviews(n_sprints)
    check_resources(tasks)
    if not args.skip_idempotency:
        check_idempotent()
    if args.tests:
        check_tests()

    print("\nИТОГ: ошибок %d, предупреждений %d" % (len(FAILS), len(WARNS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
