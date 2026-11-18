# src/HTTPServices/

HTTP-сервисы: РИХ_Обмен (/health, /products, /orders, /orders/batch, /receipts/batch), РИХ_ЭДО, РИХ_Витрина (task_79…task_84, task_115, task_117)

Правила:
- имена объектов — с префиксом подсистемы `РИХ_` (см. ../../Docs/CodingStandard.md);
- каждый объект попадает в Git текстом (EDT-структура: папка объекта + .xml + Module.bsl);
- перед созданием объекта сверьтесь с ER-схемой модели данных (task_19) и реестром ADR.
