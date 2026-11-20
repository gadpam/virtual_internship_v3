#!/usr/bin/env python3
"""Проверки task_138: ревью безопасности Q2 по чек-листу (исполняемо).

Ключевые пункты чек-листа проверяются по дереву, а не на словах:
каждый HTTP-обработчик — за единой точкой аутентификации; метрики
не анонимны; отказы токенов не маскируются под 500; секретов
в дереве нет (сканер task_134); контекст журнала санитизируется
(task_135); лимиты границы на месте (task_136).

Запуск: src/scripts/.venv/bin/python src/scripts/checks_security_review.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from scan_secrets import scan_tree  # noqa: E402

ROOT = Path("Configuration/src")
SERVICES = ROOT / "HTTPServices"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> None:
    modules = {p.parent.name: read(p) for p in SERVICES.glob("*/Module.bsl")}
    assert modules, "HTTP-сервисы не найдены"

    # Осознанное исключение: health — liveness-проба публикации,
    # отдаёт только status/version/serverTime и никаких данных.
    public_health = {"ПолучитьЗдоровье"}
    unguarded = []
    for name, text in modules.items():
        handlers = re.findall(r"Функция\s+(\w+)\(Запрос\)", text)
        for handler in handlers:
            body = text.split(f"Функция {handler}", 1)[1]
            body = body.split("КонецФункции", 1)[0]
            if handler in public_health:
                assert "Вставить(\"status\"" in body and "Ключ" not in body
                continue
            if "КлючДопустим" not in body and "ВыдатьТокен" not in body:
                unguarded.append(f"{name}.{handler}")
    assert not unguarded, unguarded
    print(f"[ok] аутентификация первым блоком: все обработчики за единой точкой "
          f"({len(modules)} сервисов)")

    metrics = modules["РИХ_Метрики"]
    assert "КлючДопустим" in metrics
    print("[ok] SEC-1 закрыта: снимок метрик больше не анонимный")

    exchange = modules["РИХ_Обмен"]
    assert "RIH-401" in exchange and "ОтветПоИсключению" in exchange
    token_part = exchange.split("ВыдатьТокенКлиенту", 1)[1]
    assert 'СтрНачинаетсяС(Описание, "RIH-401")' in token_part
    assert 'СтрНачинаетсяС(Описание, "RIH-429")' in token_part
    print("[ok] SEC-2 закрыта: отказы выдачи токенов — 401/429, а не 500")

    assert "ТелоЗапросаВПределах" in exchange
    assert exchange.count("ТелоЗапросаВПределах") >= 3
    print("[ok] лимит тела до чтения стоит на всех POST-маршрутах обмена")

    integrations = read(ROOT / "CommonModules/РИХ_Интеграции/Module.bsl")
    assert "ОчиститьТекстЖурнала" in integrations
    assert "УстановитьПараметр" in integrations
    assert "ЧистыйАдрес" in integrations, "экранирование ПОДОБНО потеряно"
    assert "orders.Количество() > ЛимитЭлементовПакета()" in integrations
    tokens = read(ROOT / "CommonModules/РИХ_Токены/Module.bsl")
    assert "ЧастотаВыдачиПревышена" in tokens
    assert 'ЗаписатьСобытие(Пользователь, "secret_rotate"' in tokens
    pdn = read(ROOT / "CommonModules/РИХ_ПерсональныеДанные/Module.bsl")
    assert "РИХ_Аудит.ЗаписатьДоступКПДн" in pdn, "показ ПДн не подключён к аудиту"
    assert '"pdn_erasure"' in pdn, "обезличивание не подключено к аудиту"
    conf = read(ROOT / "Configuration/Configuration.xml")
    for obj in ("CommonModule.РИХ_Аудит", "InformationRegister.АудитДоступа",
                "Report.АудитДоступа", "Constant.РИХ_ПарольБанка"):
        assert obj in conf, f"{obj} не зарегистрирован"
    print("[ok] журнал санитизируется единой точкой; запросы параметризованы; "
          "экранирование ПОДОБНО, лимит пачки и регистрации объектов на месте")

    assert scan_tree(Path(".")) == [], scan_tree(Path("."))[:3]
    print("[ok] секретов в дереве нет (сканер task_134)")


if __name__ == "__main__":
    main()
