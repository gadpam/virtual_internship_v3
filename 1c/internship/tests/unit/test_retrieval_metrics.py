"""L1 · Модульные тесты метрик качества поиска (task_238, task_244).

Метрики живут в `src/ai_service/evaluation/metrics.py` и намеренно не импортируют
`app`: их можно проверить без поднятого сервиса. Именно эти цифры (hit@1, hit@5,
MRR, recall@10) попадают в отчёт о качестве RAG-поиска, поэтому они обязаны
считаться правильно на известных маленьких примерах.

Запуск: cd 1c/internship/tests && pytest -q unit/test_retrieval_metrics.py
"""
import sys
from pathlib import Path

import pytest

EVALUATION_ROOT = Path(__file__).resolve().parents[2] / "src" / "ai_service" / "evaluation"
sys.path.insert(0, str(EVALUATION_ROOT))

from metrics import (  # noqa: E402
    first_relevant_rank,
    hit_at_k,
    is_same_document,
    mean_reciprocal_rank,
    recall_at_k,
    reciprocal_rank,
    summarize,
)


class TestFirstRelevantRank:
    def test_first_position(self):
        assert first_relevant_rank(["a", "b", "c"], {"a"}) == 1

    def test_third_position(self):
        assert first_relevant_rank(["x", "y", "a"], {"a"}) == 3

    def test_none_when_absent(self):
        assert first_relevant_rank(["x", "y"], {"a"}) is None

    def test_accepts_iterable_expected(self):
        assert first_relevant_rank(["x", "b"], ["a", "b"]) == 2

    def test_empty_expected_raises(self):
        with pytest.raises(ValueError):
            first_relevant_rank(["a"], [])


class TestHitAtK:
    def test_hit_within_k(self):
        assert hit_at_k(["x", "a"], {"a"}, k=3) is True

    def test_miss_beyond_k(self):
        assert hit_at_k(["x", "y", "a"], {"a"}, k=2) is False

    def test_k_must_be_positive(self):
        with pytest.raises(ValueError):
            hit_at_k(["a"], {"a"}, k=0)


class TestReciprocalRank:
    def test_first_position_is_one(self):
        assert reciprocal_rank(["a", "b"], {"a"}) == pytest.approx(1.0)

    def test_third_position_is_one_third(self):
        assert reciprocal_rank(["x", "y", "a"], {"a"}) == pytest.approx(1 / 3)

    def test_absent_is_zero(self):
        assert reciprocal_rank(["x"], {"a"}) == pytest.approx(0.0)


class TestRecallAtK:
    def test_all_relevant_found(self):
        assert recall_at_k(["a", "b", "noise"], {"a", "b"}, k=3) == pytest.approx(1.0)

    def test_half_found(self):
        assert recall_at_k(["a", "noise"], {"a", "b"}, k=2) == pytest.approx(0.5)

    def test_k_truncates_found_list(self):
        assert recall_at_k(["noise", "a"], {"a"}, k=1) == pytest.approx(0.0)

    def test_duplicates_in_found_do_not_inflate_recall(self):
        assert recall_at_k(["a", "a", "a"], {"a", "b"}, k=3) == pytest.approx(0.5)

    def test_empty_expected_raises(self):
        with pytest.raises(ValueError):
            recall_at_k(["a"], set(), k=1)


class TestMeanReciprocalRank:
    def test_two_queries(self):
        cases = [(["a"], {"a"}), (["x", "b"], {"b"})]
        assert mean_reciprocal_rank(cases) == pytest.approx((1.0 + 0.5) / 2)

    def test_skips_cases_without_expected(self):
        assert mean_reciprocal_rank([(["a"], {"a"}), (["b"], set())]) == pytest.approx(1.0)

    def test_empty_cases_gives_zero(self):
        assert mean_reciprocal_rank([]) == pytest.approx(0.0)


class TestSummarize:
    def test_perfect_ranking(self):
        report = summarize([(["a"], {"a"}), (["b"], {"b"})])
        assert report["cases"] == 2
        assert report["skipped"] == 0
        assert report["hit@1"] == pytest.approx(1.0)
        assert report["hit@5"] == pytest.approx(1.0)
        assert report["mrr"] == pytest.approx(1.0)
        assert report["recall@10"] == pytest.approx(1.0)

    def test_half_hit_at_one(self):
        report = summarize([(["a"], {"a"}), (["x", "b"], {"b"})], hit_k=(1, 5))
        assert report["hit@1"] == pytest.approx(0.5)
        assert report["hit@5"] == pytest.approx(1.0)
        assert report["mrr"] == pytest.approx(0.75)

    def test_missing_relevant_document(self):
        report = summarize([(["x", "y"], {"a"})])
        assert report["hit@1"] == pytest.approx(0.0)
        assert report["mrr"] == pytest.approx(0.0)
        assert report["recall@10"] == pytest.approx(0.0)

    def test_skipped_cases_are_counted(self):
        report = summarize([(["a"], {"a"}), (["b"], set())])
        assert report["cases"] == 1
        assert report["skipped"] == 1

    def test_recall_k_is_configurable(self):
        report = summarize([(["n", "n", "n", "a"], {"a"})], hit_k=(1,), recall_k=3)
        assert report["hit@1"] == pytest.approx(0.0)
        assert report["recall@3"] == pytest.approx(0.0)
        assert "recall@10" not in report

    def test_multiple_expected_documents(self):
        report = summarize([(["a", "n", "b"], {"a", "b", "c"})], hit_k=(1, 3), recall_k=3)
        assert report["hit@1"] == pytest.approx(1.0)
        assert report["mrr"] == pytest.approx(1.0)
        # summarize() округляет до трёх знаков — сверяем с округлённым значением
        assert report["recall@3"] == pytest.approx(round(2 / 3, 3))


class TestСопоставлениеПутейДокументов:
    """Поиск возвращает путь от `KNOWLEDGE_BASE_DIR`, а эталон — от корня проекта.

    Без сравнения по хвосту пути метрики показывали бы ноль при полностью рабочем
    поиске — самая обидная ошибка в оценке качества.
    """

    def test_относительный_путь_совпадает_с_эталонным(self):
        assert is_same_document("../docs/knowledge_base/склад_поступление.md",
                                "internship/docs/knowledge_base/склад_поступление.md")

    def test_абсолютный_путь_совпадает_с_эталонным(self):
        assert is_same_document("/srv/rih/internship/docs/knowledge_base/аналитика_метрики.md",
                                "internship/docs/knowledge_base/аналитика_метрики.md")

    def test_эталон_короче_найденного(self):
        assert is_same_document("internship/docs/knowledge_base/интеграции_http.md",
                                "knowledge_base/интеграции_http.md")

    def test_windows_разделители(self):
        assert is_same_document("internship\\docs\\knowledge_base\\интеграции_форматы.md",
                                "knowledge_base/интеграции_форматы.md")

    def test_разные_документы_не_совпадают(self):
        assert not is_same_document("knowledge_base/склад_поступление.md",
                                    "knowledge_base/склад_перемещение.md")

    def test_одинаковое_имя_в_разных_каталогах_не_совпадает(self):
        assert not is_same_document("docs/api/README.md", "docs/knowledge_base/README.md")

    def test_корпус_смонтирован_в_контейнер_по_другому_пути(self):
        assert is_same_document("/data/knowledge_base/аналитика_метрики.md",
                                "internship/docs/knowledge_base/аналитика_метрики.md")

    def test_пустые_значения_не_совпадают(self):
        assert not is_same_document("", "a.md")
        assert not is_same_document("a.md", "")

    def test_ранг_считается_по_хвосту_пути(self):
        found = ["docs/kb/шум.md", "../docs/knowledge_base/склад_перемещение.md"]
        expected = {"internship/docs/knowledge_base/склад_перемещение.md"}
        assert first_relevant_rank(found, expected) == 2
        assert recall_at_k(found, expected, k=2) == pytest.approx(1.0)

    def test_сводка_не_теряет_совпадения_из_за_префиксов(self):
        report = summarize([
            (["/srv/rih/internship/docs/knowledge_base/аналитика_метрики.md"],
             ["internship/docs/knowledge_base/аналитика_метрики.md"]),
        ])
        assert report["hit@1"] == pytest.approx(1.0)
        assert report["mrr"] == pytest.approx(1.0)
