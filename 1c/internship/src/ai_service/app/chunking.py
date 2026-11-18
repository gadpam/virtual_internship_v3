"""Корпус знаний и чанкование (task_236).

Заготовка: читает Markdown-файлы корпуса и режет их на фрагменты.
В задании task_236 вы сравните три стратегии чанкования и зафиксируете параметры.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

from .config import get_settings


@dataclass
class Chunk:
    chunk_id: str
    document: str
    section: str
    version: str
    text: str
    metadata: Dict[str, str] = field(default_factory=dict)


def iter_documents(base_dir: str | None = None) -> List[Dict[str, str]]:
    """Список документов корпуса: путь, заголовок, версия (из front-matter или имени)."""
    settings = get_settings()
    root = Path(base_dir or settings.knowledge_base_dir)
    if not root.exists():
        return []
    docs = []
    for path in sorted(root.rglob("*.md")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        version = _extract_version(text) or "draft"
        docs.append({"path": str(path), "title": path.stem, "text": text, "version": version})
    return docs


def _extract_version(text: str) -> str | None:
    for line in text.splitlines()[:20]:
        if line.lower().startswith("версия:") or line.lower().startswith("version:"):
            return line.split(":", 1)[1].strip()
    return None


def chunk_by_paragraphs(document: Dict[str, str], size: int | None = None,
                        overlap: int | None = None) -> List[Chunk]:
    """Стратегия «по абзацам» (базовая). В task_236 добавьте по заголовкам и фиксированную."""
    settings = get_settings()
    size = size or settings.chunk_size
    overlap = overlap or settings.chunk_overlap
    text: str = document["text"]
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    # Раздел каждого абзаца определяем до нарезки: заголовок «# ...» открывает
    # раздел, и сам относится к нему. Фрагмент получает раздел своего ПЕРВОГО
    # абзаца — иначе весь фрагмент подписывался бы заголовком, который в него
    # уже не попал (task_236).
    entries: List[Tuple[str, str]] = []
    section = document["title"]
    for paragraph in paragraphs:
        if paragraph.startswith("#"):
            section = paragraph.lstrip("#").strip()
        entries.append((paragraph, section))

    chunks: List[Chunk] = []
    buffer: List[Tuple[str, str]] = []
    buffer_len = 0
    index = 0

    for paragraph, _ in entries:
        if buffer_len + len(paragraph) > size and buffer:
            chunks.append(_make_chunk(document, buffer[0][1], [text for text, _ in buffer], index))
            index += 1
            # при перекрытии хвостовой абзац уходит в следующий фрагмент вместе со своим разделом
            buffer = buffer[-1:] if overlap else []
            buffer_len = sum(len(text) for text, _ in buffer)
        buffer.append((paragraph, _))
        buffer_len += len(paragraph)

    if buffer:
        chunks.append(_make_chunk(document, buffer[0][1], [text for text, _ in buffer], index))
    return chunks


def _make_chunk(document: Dict[str, str], section: str, parts: List[str], index: int) -> Chunk:
    text = "\n\n".join(parts)
    return Chunk(
        chunk_id=f"{document['title']}#{index}",
        document=document["path"],
        section=section,
        version=document.get("version", "draft"),
        text=text,
        metadata={"title": document["title"]},
    )


def build_chunks() -> List[Chunk]:
    """Все фрагменты корпуса текущей стратегией (используется vectorstore.rebuild)."""
    chunks: List[Chunk] = []
    for document in iter_documents():
        chunks.extend(chunk_by_paragraphs(document))
    return chunks
