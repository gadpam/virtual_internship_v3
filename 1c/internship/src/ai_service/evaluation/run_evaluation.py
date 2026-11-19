#!/usr/bin/env python3
"""Прогон оценки качества поиска (task_238).

Запуск:
    python3 evaluation/run_evaluation.py [--questions evaluation/golden_questions.json]

Считает hit@1, hit@5, MRR, recall@10 и печатает сводку. Результаты сохраняйте
в evaluation/reports/ с датой и параметрами конфигурации — это ваш базлайн.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from metrics import summarize  # noqa: E402
from retrieval_helpers import search_documents  # noqa: E402


def evaluate(questions_path: str) -> dict:
    with open(questions_path, encoding="utf-8") as handle:
        data = json.load(handle)

    questions = data.get("questions", [])
    if not questions:
        raise SystemExit("В эталонном наборе нет вопросов. Дополните golden_questions.json (task_238).")

    pairs = []
    for item in questions:
        expected = set(item.get("expected_documents", []))
        if not expected:
            continue
        pairs.append((search_documents(item["question"], top_k=10), expected))

    if not pairs:
        raise SystemExit(
            "Ни у одного вопроса не заполнено expected_documents — метрики считать не по чему (task_252)."
        )

    report = summarize(pairs, hit_k=(1, 5), recall_k=10)
    return {
        "questions": len(questions),
        "evaluated": report["cases"],
        "skipped": report["skipped"],
        "hit@1": report["hit@1"],
        "hit@5": report["hit@5"],
        "mrr": report["mrr"],
        "recall@10": report["recall@10"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Оценка качества векторного поиска RIH")
    parser.add_argument("--questions", default=os.path.join(os.path.dirname(__file__), "golden_questions.json"))
    parser.add_argument("--save", default="", help="Путь для сохранения отчёта (например reports/2026-01-15.json)")
    args = parser.parse_args()

    report = evaluate(args.questions)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.save:
        os.makedirs(os.path.dirname(args.save), exist_ok=True)
        with open(args.save, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
        print(f"Отчёт сохранён: {args.save}")
