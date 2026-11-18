"""L1 · Модульные тесты чанкования корпуса AI-сервиса (task_236).

Проверяем стратегию «по абзацам» из `src/ai_service/app/chunking.py`: ограничение
размера, перекрытие (overlap), переход раздела по заголовку, версию документа и
метаданные. Тесты не требуют индекса, сети и внешних зависимостей — только код.

Запуск: cd 1c/internship/tests && pytest -q unit/test_chunking.py
"""
import sys
from pathlib import Path

import pytest

SERVICE_ROOT = Path(__file__).resolve().parents[2] / "src" / "ai_service"
sys.path.insert(0, str(SERVICE_ROOT))

from app.chunking import Chunk, _extract_version, chunk_by_paragraphs, iter_documents  # noqa: E402


def document(text, title="Регламент обмена заказами", path="/kb/reglaments/orders.md", version="1.2"):
    """Заготовка документа в том виде, в каком его отдаёт iter_documents()."""
    return {"path": path, "title": title, "text": text, "version": version}


class TestExtractVersion:
    def test_reads_russian_front_matter(self):
        assert _extract_version("Версия: 2.4\n\nТекст регламента.") == "2.4"

    def test_reads_english_front_matter(self):
        assert _extract_version("Version: 1.0\n\nBody") == "1.0"

    def test_returns_none_when_absent(self):
        assert _extract_version("Просто текст без версии") is None

    def test_ignores_version_line_beyond_first_20_lines(self):
        text = "\n".join([f"строка {i}" for i in range(25)] + ["Версия: 9.9"])
        assert _extract_version(text) is None


class TestChunkByParagraphs:
    def test_single_paragraph_is_one_chunk(self):
        chunks = chunk_by_paragraphs(document("Один короткий абзац."), size=900, overlap=150)
        assert len(chunks) == 1
        assert chunks[0].text == "Один короткий абзац."
        assert isinstance(chunks[0], Chunk)

    def test_chunk_id_is_unique_and_ordered(self):
        text = "\n\n".join(f"Абзац номер {i}. " * 12 for i in range(8))
        chunks = chunk_by_paragraphs(document(text), size=200, overlap=0)
        ids = [chunk.chunk_id for chunk in chunks]
        assert len(ids) == len(set(ids))
        assert ids[0].endswith("#0")
        assert ids[-1].endswith(f"#{len(chunks) - 1}")

    def test_document_and_version_are_carried_to_every_chunk(self):
        text = "\n\n".join(f"Фрагмент {i}. " * 20 for i in range(6))
        chunks = chunk_by_paragraphs(document(text, version="3.1", path="/kb/x.md"), size=250, overlap=40)
        assert chunks
        for chunk in chunks:
            assert chunk.document == "/kb/x.md"
            assert chunk.version == "3.1"
            assert chunk.metadata["title"] == "Регламент обмена заказами"

    def test_section_follows_markdown_heading(self):
        text = (
            "# Порядок обмена\n\n"
            "Первый абзац раздела про порядок.\n\n"
            "# Таймауты и ретраи\n\n"
            "Абзац про таймауты.\n\n"
            "Продолжение про таймауты."
        )
        chunks = chunk_by_paragraphs(document(text), size=60, overlap=0)
        sections = [chunk.section for chunk in chunks]
        assert "Порядок обмена" in sections
        assert "Таймауты и ретраи" in sections
        # раздел по умолчанию — заголовок документа, пока не встретился '#'
        assert chunks[0].section in ("Порядок обмена", "Регламент обмена заказами")

    def test_overlap_repeats_tail_of_previous_chunk(self):
        first = "Первый абзац с уникальным хвостом ХВОСТ-АЛЬФА."
        second = "Второй абзац, который длиннее первого и требует отдельного фрагмента."
        text = "\n\n".join([first, second])
        chunks = chunk_by_paragraphs(document(text), size=len(first) + len(second) - 5, overlap=1)
        assert len(chunks) >= 2
        # при overlap >= 1 последний абзац предыдущего фрагмента переходит в следующий
        assert chunks[0].text.split("\n\n")[-1] in chunks[1].text

    def test_no_overlap_does_not_duplicate_text(self):
        text = "\n\n".join([f"Абзац {i} " * 10 for i in range(4)])
        chunks = chunk_by_paragraphs(document(text), size=120, overlap=0)
        joined = "\n\n".join(chunk.text for chunk in chunks)
        assert joined.count("Абзац 3") == text.count("Абзац 3")

    def test_empty_text_produces_no_chunks(self):
        assert chunk_by_paragraphs(document("   \n\n  "), size=200, overlap=20) == []

    @pytest.mark.parametrize("size", [80, 200, 600, 2000])
    def test_various_sizes_never_raise_and_cover_all_paragraphs(self, size):
        paragraphs = [f"Абзац {i}: " + "текст " * 15 for i in range(10)]
        text = "\n\n".join(paragraphs)
        chunks = chunk_by_paragraphs(document(text), size=size, overlap=min(20, size // 4))
        assert chunks
        merged = "\n\n".join(chunk.text for chunk in chunks)
        for index in range(10):
            assert f"Абзац {index}:" in merged


class TestIterDocuments:
    def test_reads_markdown_files_from_directory(self, tmp_path):
        (tmp_path / "orders.md").write_text("Версия: 1.0\n\nПорядок обмена заказами.", encoding="utf-8")
        (tmp_path / "stock.md").write_text("Порядок выгрузки остатков.", encoding="utf-8")
        (tmp_path / "notes.txt").write_text("не markdown", encoding="utf-8")

        docs = iter_documents(str(tmp_path))
        titles = sorted(doc["title"] for doc in docs)
        assert titles == ["orders", "stock"]
        by_title = {doc["title"]: doc for doc in docs}
        assert by_title["orders"]["version"] == "1.0"
        assert by_title["stock"]["version"] == "draft"

    def test_missing_directory_returns_empty_list(self, tmp_path):
        assert iter_documents(str(tmp_path / "no-such-dir")) == []

    def test_document_dict_has_keys_expected_by_chunking(self, tmp_path):
        (tmp_path / "a.md").write_text("# Раздел\n\nТекст.", encoding="utf-8")
        doc = iter_documents(str(tmp_path))[0]
        assert set(doc) == {"path", "title", "text", "version"}
        # документ из iter_documents сразу пригоден для chunk_by_paragraphs
        assert chunk_by_paragraphs(doc, size=100, overlap=10)
