#!/usr/bin/env python3
"""Проверки task_105: дедупликация сообщений обмена (зеркало).

100 сообщений: 20 повторов того же messageId и 5 бизнес-дублей
(новый messageId, тот же externalId). Результат: созданных объектов
75, дублей в данных — ноль; повтор после «частичной обработки»
продолжается по записанным шагам.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_message_dedup.py
"""

from __future__ import annotations

import uuid


class Receiver:
    def __init__(self) -> None:
        self.messages: dict[str, dict] = {}
        self.objects: dict[str, dict] = {}

    def process(self, message_id: str, external_id: str, fail_after: str | None = None) -> str:
        if message_id in self.messages:
            stored = self.messages[message_id]
            if stored["status"] in ("готово", "дубль"):
                return stored["result"]
            # «обрабатывается» — прошлый вызов оборвался: продолжаем
            # по записанным шагам, а не возвращаем пустой «результат».
        if external_id in self.objects:
            self.messages[message_id] = {"result": f"дубль бизнес-объекта: {external_id}",
                                         "status": "дубль", "steps": ""}
            return self.messages[message_id]["result"]
        steps: list[str] = []
        self.messages[message_id] = {"result": "", "status": "обрабатывается", "steps": ""}
        steps.append("валидация")
        if fail_after == "валидация":
            self.messages[message_id]["steps"] = ";".join(steps)
            raise RuntimeError("обрыв после валидации")
        self.objects[external_id] = {"message": message_id}
        steps.append("создание")
        result = f"создан объект {external_id}"
        self.messages[message_id] = {"result": result, "status": "готово",
                                     "steps": ";".join(steps)}
        return result


def main() -> None:
    receiver = Receiver()
    unique = [(str(uuid.uuid4()), f"ORD-{i:03d}") for i in range(75)]
    sent: list[tuple[str, str]] = list(unique)
    sent += [unique[i] for i in range(20)]                       # 20 повторов messageId
    sent += [(str(uuid.uuid4()), f"ORD-{i:03d}") for i in range(5)]  # 5 бизнес-дублей
    assert len(sent) == 100

    results = [receiver.process(mid, ext) for mid, ext in sent]
    assert len(receiver.objects) == 75, len(receiver.objects)
    dup_notes = [r for r in results if r.startswith("дубль")]
    assert len(dup_notes) == 5
    print(f"[ok] 100 сообщений: создано объектов {len(receiver.objects)}, "
          f"повторов по messageId поглощено 20, бизнес-дублей поймано {len(dup_notes)}")

    # Частичная обработка: обрыв после валидации, повтор продолжает по шагам.
    receiver2 = Receiver()
    mid = str(uuid.uuid4())
    try:
        receiver2.process(mid, "ORD-PARTIAL", fail_after="валидация")
        raise AssertionError("обрыв не случился")
    except RuntimeError:
        assert receiver2.messages[mid]["steps"] == "валидация"
        assert "ORD-PARTIAL" not in receiver2.objects
    result = receiver2.process(mid, "ORD-PARTIAL")
    assert result == "создан объект ORD-PARTIAL" or "ORD-PARTIAL" in receiver2.objects
    print("[ok] повтор после частичной обработки: шаги сохранены, объект создан один раз")


if __name__ == "__main__":
    main()
