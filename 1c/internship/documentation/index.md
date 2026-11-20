# Документация RIH: индекс (task_66)

Одна страница на всё Quarter 1. Описания каждого задания —
`task_N_description.txt` рядом, рефлексии — `reflections/`.

## Подсистема и архитектура

- [Подсистема «Товары и склад»](architecture/subsystem_goods_warehouse.md)
- [Модель данных и ADR-1…4 спринта 3](architecture/task_19_data_model.md)
- [Последовательность учёта](architecture/task_46_sequence.md)
- [Локализация наименований (ADR)](architecture/task_40_localization_adr.md)
- ADR: [цена-регистр](adr/ADR-0002-prices-as-register.md) ·
  [распределение денег](adr/ADR-0003-money-distribution.md) ·
  [расширения](adr/ADR-0004-extensions-over-edits.md) ·
  [пакет 1000](adr/ADR-0005-batch-size-1000.md) ·
  [кэш порогов](adr/ADR-0006-session-cache-thresholds.md)

## Обмены и интеграции

- [Топология обменов](architecture/exchange_topology.md) ·
  [Регламент обмена с магазином](exchange/reglament_shop_exchange.md) ·
  [Версионирование обменов](exchange/versioning.md) ·
  [RIH ↔ БП](exchange/rih_bp.md) · [РИБ](exchange/rib.md)
- Диагностика: [проблемы обменов](troubleshooting/exchange.md) ·
  [мониторинг и инциденты](troubleshooting/exchange_monitoring.md)

## Пользователям и администраторам

- [Поступление и перемещение: инструкция товароведа](user_guides/goods_flow_instruction.md)
- [Печатная форма поступления](user_guides/task_42.md)
- [Администратор: данные, логи, задания](user_guides/admin_instruction.md)
- [UX документа приёма](ux/task_39.md) · [Мобильная инвентаризация](mobile/task_41_mobile_inventory.md)

## Качество и производительность

- [Стандарт кодирования](../Configuration/Docs/CodingStandard.md)
- [Качество конфигурации Q1](quality/q1_config_quality.md) · [Отладка: 10 приёмов](quality/task_49_debug.md)
- [Базлайн производительности](perf/baseline_q1_end.md) · [ТЖ](performance/tzh_task_61.md) · [Индексы](perf/task_58_indexes.md) · [Нагрузка](performance/load_task_63.md)
- [План обновления Q1](release/release_plan_q1.md) · [Backlog Q2](backlog_q2.md)
- Ревью спринтов: `reviews/sprint_0_review.md` … `reviews/sprint_11_review.md`
- Отчёт клиент-сервер: [task_37](reports/task_37_client_server.md)
