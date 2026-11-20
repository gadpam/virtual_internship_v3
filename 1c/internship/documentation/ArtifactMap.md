# Карта артефактов: задание → что должно появиться

Сгенерировано из данных заданий (`1c/tools/build_artifact_map.py`), не править руками.
Статус: **[есть]** — уже лежит в стенде, можно читать до задания;
**[создаётся]** — артефакт рождается в этом задании, путь — адрес результата.

## Q1

| Задание | Артефакты (путь от `1c/`) |
|---|---|
| task_0. Легенда виртуальной стажировки 1С и установка окружения | `project/tools/Environment.md` [есть]<br>`internship/tools/docker-compose.yml` [есть]<br>`internship/tools/VERSIONS.md` [есть] |
| task_1. Конфигуратор и EDT: два инструмента, одна конфигурация | `project/tools/Environment.md` [есть] |
| task_2. Выгрузка конфигурации в файлы и структура исходников | `internship/Configuration/src/CommonModules/РИХ_ОбщегоНазначения/Module.bsl` [есть] |
| task_3. Git и хранилище конфигурации: ветки, коммиты, захваты объектов | `Git Book: главы про ветвление и слияние` [создаётся] |
| task_4. Docker и docker compose: окружение RIH одной командой | `internship/tools/docker-compose.yml` [есть]<br>`internship/tools/.env.example` [есть]<br>`Документация Docker Compose` [создаётся] |
| task_5. Python-минимум: venv, скрипт, JSON и HTTP-запрос | `internship/data/` [есть]<br>`internship/src/scripts/README.md` [есть]<br>`Документация Python: venv, csv, json, urllib` [создаётся] |
| task_6. Конвенции именования и структура кода в 1С | `Стандарты разработки 1С: «Имена объектов», «Структура модуля»` [создаётся] |
| task_7. Структура конфигурации RIH: подсистемы и общие модули | `internship/Configuration/src/Subsystems/` [есть]<br>`ideas/architecture/Laws_of_architecture.txt` [создаётся] |
| task_8. БСП: что это и какими механизмами нельзя пренебрегать | `Документация БСП на ITS` [создаётся]<br>`internship/Configuration/src/Catalogs/` [есть]<br>`internship/Configuration/src/InformationRegisters/` [есть] |
| task_9. Роли, права доступа и RLS | `Документация: «Права доступа», «RLS»` [создаётся] |
| task_10. Стандарты разработки 1С: читаем, применяем, проверяем себя | `Стандарты разработки компании «1С» (ITS)` [создаётся] |
| task_11. SQL-минимум: SELECT, JOIN и GROUP BY на данных RIH | `internship/tools/docker-compose.yml` [есть]<br>`Документация PostgreSQL: SELECT, JOIN, GROUP BY` [создаётся] |
| task_12. Статический анализ и дымовые тесты: АПК, Sonar, проверки в привычку | `internship/tools/docker-compose.yml` [есть]<br>`internship/tools/ci/github-actions/ci.yml` [есть]<br>`internship/tools/ci/vanessa/vanessa-runner.json` [есть] |
| task_13. Типы данных, ссылки и объекты: цена получения данных | `internship/Configuration/src/CommonModules/РИХ_ОбщегоНазначения/Module.bsl` [есть] |
| task_14. Коллекции: массивы, структуры, соответствия, списки значений | `internship/Configuration/src/CommonModules/РИХ_ОбщегоНазначения/Module.bsl` [есть] |
| task_15. Даты, время и часовые пояса: где все ошибаются | `Синтакс-помощник: функции работы с датами` [создаётся] |
| task_16. Числа и деньги: почему не бывает «почти правильно» | `Стандарты: «Работа с числовыми данными»` [создаётся] |
| task_17. Строки, GUID, форматирование и разбор внешних данных | `internship/data/nomenclature_sample.csv` [есть] |
| task_18. Строки запросов и параметры: инъекции и читабельность | `Стандарты: «Работа с запросами»` [создаётся] |
| task_19. Проектирование модели данных: ER-схема подсистемы | `ideas/architecture/Laws_of_architecture.txt` [создаётся]<br>`ideas/scribing_notes/IdeaDescription.txt` [создаётся] |
| task_20. Справочник «Номенклатура»: реквизиты, иерархия, формы | `internship/Configuration/src/Catalogs/` [есть] |
| task_21. Документ «Поступление товаров»: табличная часть, проведение | `Документация: «Проведение документов»` [создаётся] |
| task_22. Регистр накопления «ТоварыНаСкладах»: остатки и обороты | `internship/Configuration/src/AccumulationRegisters/` [есть] |
| task_23. Регистр сведений «ЦеныНоменклатуры»: периодический РС и история | `Документация: «Регистры сведений»` [создаётся] |
| task_24. Характеристики, единицы измерения и справочник «Склады» | `Документация: «Планы видов характеристик»` [создаётся] |
| task_25. Основы языка запросов: выборка, условия, порядок | `internship/documentation/queries/` [есть] |
| task_26. Соединения: LEFT, INNER, и почему порядок имеет значение | `Курс ITS «Язык запросов»` [создаётся] |
| task_27. Группировки, агрегаты, HAVING и итоги | `Консоль запросов` [создаётся] |
| task_28. Временные таблицы: главный инструмент оптимизации | `internship/documentation/queries/task_28_optimization.md` [есть] |
| task_29. Как задавать вопросы аналитику: практикум делового общения | `project/ideas/documentation/IdeaDescription.txt` [есть] |
| task_30. Пакеты запросов, ВЫБОР, CASE и вычисляемые поля | `Консоль запросов: режим «Пакет запросов»` [создаётся] |
| task_31. Первый отчёт СКД: «Остатки товаров по складам» | `internship/Configuration/src/Reports/ОстаткиТоваровПоСкладам/` [есть] |
| task_32. Макет СКД руками: области, заголовки, условное оформление | `Документация: «Макет компоновки данных»` [создаётся] |
| task_33. Отборы, группировки, сортировки и вычисляемые поля | `internship/documentation/queries/` [есть] |
| task_34. Программное формирование отчёта и настройки пользователя | `internship/Configuration/src/Reports/ОстаткиТоваровПоСкладам/` [есть] |
| task_35. Отчёт на внешних данных: объединяем регистры и внешние источники | `internship/data/` [есть] |
| task_36. Производительность СКД: когда отчёт тормозит и что делать | `internship/documentation/performance/` [есть] |
| task_37. Управляемая форма документа: структура, команды, события | `internship/documentation/reports/` [есть] |
| task_38. Валидация ввода и сообщения пользователю | `internship/Configuration/src/CommonModules/` [есть] |
| task_39. Подсказки, быстрые действия и UX внутреннего инструмента | `ideas/architecture/POST_Ideas.txt` [создаётся] |
| task_40. Локализация: RU/EN и многоязычные данные | `Документация: «Локализация конфигурации»` [создаётся] |
| task_41. Мобильная платформа: ограничения и первый сценарий | `Документация: «Мобильная платформа 1С»` [создаётся] |
| task_42. Печать, внешние печатные формы и макеты | `Документация: «Печатные формы», БСП «Печать»` [создаётся] |
| task_43. Обработчики проведения: где живёт бизнес-логика | `internship/Configuration/src/CommonModules/` [есть] |
| task_44. Транзакции: когда нужны явные и когда они вредны | `Стандарты: «Транзакции»` [создаётся] |
| task_45. Блокировки: управляемые, мертвые захваты и гонки | `Стандарты: «Блокировки»` [создаётся] |
| task_46. Регистры последовательности и оперативный учёт | `Документация: «Последовательности»` [создаётся] |
| task_47. Фоновые и регламентные задания: расписания и безопасность | `Стандарты: «Регламентные и фоновые задания»` [создаётся] |
| task_48. Подписки на события, расширения и снимаемая доработка | `Документация: «Расширения конфигурации»` [создаётся] |
| task_49. Отладчик: точки останова, watch, выполнение по шагам | `Документация платформы: «Отладка конфигурации»` [создаётся] |
| task_50. Журнал регистрации и событийная модель диагностики | `Документация: «Журнал регистрации»` [создаётся] |
| task_51. Обработка ошибок: Попытка/Исключение и внятные сообщения | `Стандарты: «Обработка ошибок»` [создаётся] |
| task_52. Юнит-тесты в 1С: каркас, изоляция, AAA | `internship/Configuration/src/DataProcessors/` [есть]<br>`internship/tests/README.md` [есть] |
| task_53. Дымовые и приёмочные сценарии (vanessa-automation) | `internship/tests/features/` [есть] |
| task_54. Код-ревью и статический анализ: закрываем долги Q1 | `project/acceptance/CodeReviewChecklist.txt` [есть] |
| task_55. Массовая загрузка данных: 1 000 000 движений | `internship/tools/ (профили данных)` [создаётся] |
| task_56. Замер производительности: методики и инструменты | `internship/documentation/performance/baseline_q1.md` [создаётся] |
| task_57. Пакетная обработка: как не держать базу в транзакции час | `internship/documentation/performance/` [есть] |
| task_58. Индексы СУБД: почему запрос медленный и что с этим делать | `internship/tools/sql/` [есть] |
| task_59. Многопоточность в 1С: параллельные фоновые задания | `internship/documentation/performance/` [есть] |
| task_60. Кеширование, повторные вызовы и «дорогие» справочные данные | `Стандарты: «Производительность»` [создаётся] |
| task_61. Технологический журнал (ТЖР): настройка и чтение | `internship/tools/ (конфиг ТЖР)` [создаётся] |
| task_62. АПК: анализ программы и консоли запросов как рабочий инструмент | `internship/documentation/quality/` [есть] |
| task_63. Нагрузочное тестирование: 50 пользователей на одном стенде | `internship/documentation/performance/load_q1.md` [создаётся] |
| task_64. CI/CD: GitHub Actions, сборка конфигурации, автопубликация | `internship/tools/ci/github-actions/ci.yml` [есть]<br>`internship/tools/ci/vanessa/vanessa-runner.json` [есть] |
| task_65. Обновление конфигурации и базы: сценарии и риски | `Документация: «Механизм обновления конфигурации»` [создаётся] |
| task_66. Документация подсистемы: контракт, инструкция, ADR | `internship/documentation/adr/` [есть] |
| task_67. Code review квартала: полный разбор вашего кода | `project/acceptance/CodeReviewChecklist.txt` [есть] |
| task_68. Демо подсистемы: сценарий, данные, рассказ | `project/acceptance/DemoAndDefense.txt` [есть] |
| task_69. Защита архитектуры Q1: схемы, ADR, неудобные вопросы | `internship/documentation/architecture/` [есть] |
| task_70. Ретроспектива квартала: честный разбор | `internship/documentation/retro/` [есть] |
| task_71. Портфолио: статья и публичный артефакт по итогам Q1 | `project/ideas/architecture/POST_Ideas.txt` [есть] |
| task_72. План Q2: интеграции, контракты и подготовка стенда | `internship/src/mock_shop_api/` [есть]<br>`project/sprint_13/SprintOverview.txt` [есть] |

## Q2

| Задание | Артефакты (путь от `1c/`) |
|---|---|
| task_73. Карта интеграций RIH: кто с кем и зачем | `internship/documentation/architecture/integration_map.md` [создаётся] |
| task_74. HTTP и REST: методы, статусы, идемпотентность | `internship/src/mock_shop_api/` [есть]<br>`internship/tools/api/` [есть] |
| task_75. JSON и XML в 1С: штатные средства чтения и записи | `internship/Configuration/src/DataProcessors/` [есть] |
| task_76. Postman/Bruno: коллекции, окружения, автопроверки | `internship/tools/api/README.md` [есть] |
| task_77. OpenAPI 3.x: контракт как источник истины | `internship/docs/api/openapi.yaml` [есть] |
| task_78. Mock-сервисы: стабильный стенд вместо «партнёр опять упал» | `internship/src/mock_loyalty_api/` [есть]<br>`internship/src/mock_tk_api/` [есть] |
| task_79. Первый HTTP-сервис в 1С: маршруты и публикация | `internship/tools/docker-compose.yml (nginx)` [создаётся] |
| task_80. XDTO-модели и сериализация: структура вместо «строки на глаз» | `Документация: «XDTO»` [создаётся] |
| task_81. Авторизация и безопасность HTTP-сервиса | `project/acceptance/CodeReviewChecklist.txt (раздел «Безопасность»)` [создаётся] |
| task_82. Версионирование API и единый формат ошибок | `internship/docs/api/error_format.md` [есть] |
| task_83. POST/PUT/DELETE: приём заказов от онлайн-магазина | `internship/tests/features/` [есть] |
| task_84. Логирование вызовов сервиса и журнал интеграций | `internship/Configuration/src/InformationRegisters/ЖурналИнтеграций/` [есть] |
| task_85. Web-сервис (SOAP) в 1С: публикация и WSDL | `Документация: «Web-сервисы»` [создаётся] |
| task_86. Потребление внешнего SOAP-сервиса: WS-ссылки и прокси | `internship/src/mock_bank_ws/` [есть] |
| task_87. OData: стандартный REST-доступ к данным 1С | `Документация: «Интерфейс OData»` [создаётся] |
| task_88. Файловые обмены: каталоги, форматы, целостность | `internship/data/supplier_price/` [есть] |
| task_89. Форматы commerce: CommercialXML-подобный обмен и универсальный конвертер | `internship/data/commerceml_sample.xml` [есть] |
| task_90. ЭДО и юридически значимый документооборот: обзор и требования | `internship/docs/edo/` [есть] |
| task_91. Клиент онлайн-магазина: выгрузка каталога и остатков | `internship/docs/api/partner_shop.md` [есть] |
| task_92. Клиент программы лояльности: баланс, начисление, списание | `internship/src/mock_loyalty_api/` [есть] |
| task_93. Клиент транспортной компании и rate limiting | `internship/src/mock_tk_api/` [есть] |
| task_94. Курсы валют, справочники и кеширование внешних данных | `internship/Configuration/src/InformationRegisters/КурсыВалют/` [есть] |
| task_95. Ошибки партнёра: деградация, очередь, компенсация | `internship/Configuration/src/InformationRegisters/ОчередьОбмена/` [есть] |
| task_96. Контрактные тесты и документация для партнёра | `internship/docs/api/rih_http_services.md` [есть]<br>`internship/docs/api/error_format.md` [есть]<br>`internship/tests/fixtures/` [есть] |
| task_97. Топология обменов: узлы, направления, фильтры | `internship/documentation/architecture/exchange_topology.md` [есть] |
| task_98. Конвертация данных 2.0: правила обмена и ПКО | `Документация: «Конвертация данных 2.0»` [создаётся] |
| task_99. КД 2.0: документы, регистры и сложные соответствия | `internship/documentation/troubleshooting/exchange.md` [есть] |
| task_100. Миграция НСИ: 100 000 позиций без остановки работы | `internship/documentation/release/migration_plan.md` [есть] |
| task_101. Регистрация изменений, подписки и контроль целостности обмена | `internship/Configuration/src/Reports/РасхожденияОбмена/` [создаётся] |
| task_102. Конвертация данных 3.0: новый подход к правилам обмена | `Документация: «Конвертация данных 3.0»` [создаётся] |
| task_103. КД 3.0: документы, регистры и обмен с типовой конфигурацией | `internship/documentation/exchange/rih_bp.md` [есть] |
| task_104. Версии правил обмена и миграции контрактов | `internship/documentation/exchange/versioning.md` [есть] |
| task_105. Идемпотентность и дубли в обменах | `internship/tests/integration/` [есть] |
| task_106. Распределённая информационная база (РИБ) | `Документация: «Распределенная информационная база»` [создаётся] |
| task_107. Отладка обменов: журнал, сообщения, типичные ошибки | `internship/Configuration/src/DataProcessors/РИХ_МониторингОбменов/` [есть] |
| task_108. Документация обмена: регламент, SLA, ответственные | `internship/documentation/exchange/` [есть] |
| task_109. Синхронно или асинхронно: как выбрать и не ошибиться | `internship/documentation/adr/` [есть] |
| task_110. Очередь сообщений в 1С: надёжная отложенная обработка | `internship/Configuration/src/InformationRegisters/ОчередьОбмена/` [есть] |
| task_111. Брокер сообщений: RabbitMQ и обмен событиями | `internship/src/queue_consumer/` [есть]<br>`internship/tools/docker-compose.yml` [есть] |
| task_112. Порядок сообщений, дубли и согласованность | `internship/Configuration/src/Reports/РасхожденияОбмена/` [создаётся] |
| task_113. Регламентные задания обмена: расписания, окна, приоритеты | `internship/documentation/operations/schedule_map.md` [есть] |
| task_114. Мониторинг интеграций: дашборд, метрики, алерты | `internship/src/metrics_exporter/` [есть]<br>`internship/tools/docker-compose.yml; дашборд Superset — полный стенд docker-compose.full.yml (task_126)` [создаётся] |
| task_115. Приёмник документов ЭДО: жёсткая схема и аудит | `internship/docs/edo/samples/` [есть] |
| task_116. Маркировка и прослеживаемость: коды, агрегаты, выбытие | `internship/documentation/architecture/marking_model.md` [есть] |
| task_117. Кассы и ОФД-подобные данные: поток продаж | `internship/documentation/performance/receipts_load.md` [есть] |
| task_118. Банковские интеграции: выписки, платежи, статусы | `internship/data/bank_statement_sample.txt` [есть] |
| task_119. Регламентные отраслевые отчёты: форма, проверка, отправка | `internship/documentation/compliance/` [есть] |
| task_120. Каталог интеграций: реестр, владельцы, статусы | `internship/documentation/integration_registry.md` [есть] |
| task_121. OLTP vs OLAP: почему отчёт по оперативной базе — зло | `internship/documentation/adr/` [есть] |
| task_122. Построение витрины: таблицы, измерения, факты | `internship/Configuration/src/AccumulationRegisters/` [есть] |
| task_123. CDC: как получать только изменения | `internship/documentation/integrations/cdc.md` [есть] |
| task_124. Выгрузка данных: файлы, таблицы СУБД, потоковая передача | `internship/tools/sql/export/` [есть] |
| task_125. Согласованность витрины и «цифры не сходятся» | `internship/documentation/analytics/metrics_dictionary.md` [есть] |
| task_126. Подготовка BI-стенда: Superset в docker-compose | `internship/tools/docker-compose.yml` [есть]<br>`internship/tools/bi/README.md` [есть] |
| task_127. Таймауты: как одно значение спасает (или топит) систему | `internship/documentation/integrations/timeouts.md` [есть] |
| task_128. Повторные попытки: экспоненциальная задержка и джиттер | `internship/src/mock_shop_api/ (режим сбоев)` [создаётся] |
| task_129. Circuit breaker: не даём падающему партнёру убить нас | `internship/documentation/integrations/resilience.md` [есть] |
| task_130. Компенсации и сторно: когда «отменить» нельзя | `internship/documentation/architecture/saga.md` [есть] |
| task_131. Деградация: как работать, когда половина систем лежит | `internship/documentation/operations/degradation_matrix.md` [есть] |
| task_132. Учение по сбою: ломаем стенд по сценарию и чиним | `internship/documentation/operations/postmortems/` [есть] |
| task_133. Аутентификация сервисов: API-ключи, токены, OAuth2-подобный поток | `internship/docs/api/rih_http_services.md` [есть] |
| task_134. Управление секретами: где хранить пароли и ключи | `internship/tools/ci/github-actions/security.yml` [есть] |
| task_135. Персональные данные: минимизация, маскирование, хранение | `internship/documentation/security/pdn_registry.md` [есть] |
| task_136. Защита от атак: валидация, лимиты, инъекции, DoS | `internship/documentation/security/pentest_q2.md` [есть] |
| task_137. Аудит доступа и изменений: кто что сделал и кто смотрел | `internship/Configuration/src/Reports/АудитДоступа/` [есть] |
| task_138. Безопасная разработка: чек-лист и ревью безопасности | `internship/documentation/security/threat_models/` [есть] |
| task_139. Тестовые стенды и воспроизводимые данные | `internship/tests/fixtures/` [есть]<br>`internship/tools/docker-compose.test.yml` [есть] |
| task_140. Контрактные тесты: ловим изменения формата до прода | `internship/tests/contract/` [есть]<br>`internship/docs/api/openapi.yaml` [есть] |
| task_141. Интеграционные тесты: реальные вызовы против mock | `internship/tests/integration/` [есть] |
| task_142. Сквозной сценарий: от заказа до отчёта и витрины | `internship/tests/e2e/` [есть] |
| task_143. Нагрузочное тестирование интеграций | `internship/tests/load/` [есть]<br>`internship/documentation/performance/load_q2.md` [есть] |
| task_144. Тестовая пирамида интеграций и стратегия качества | `internship/documentation/testing_strategy.md` [есть] |
| task_145. Code review интеграционного контура | `project/acceptance/CodeReviewChecklist.txt` [есть] |
| task_146. Демо интеграций: живой обмен и управляемый сбой | `project/acceptance/DemoAndDefense.txt` [есть] |
| task_147. Защита интеграционной архитектуры: контракты, SLA, надёжность | `internship/documentation/architecture/` [есть] |
| task_148. Деловое общение: письмо партнёру, согласование контракта, эскалация | `internship/documentation/communication/templates.md` [есть] |
| task_149. Ретроспектива Q2 и статья об интеграциях | `project/ideas/architecture/POST_Ideas.txt` [есть] |
| task_150. План Q3: учёт, данные, СУБД, BI и тяжёлые запросы | `project/tools/Environment.md` [есть]<br>`project/sprint_26/SprintOverview.txt` [есть] |

## Q3

| Задание | Артефакты (путь от `1c/`) |
|---|---|
| task_151. Учётная модель: что такое счёт, проводка, субконто | `internship/documentation/accounting/model.md` [есть] |
| task_152. Регистр бухгалтерии в 1С: план счетов и аналитика | `internship/Configuration/src/ChartsOfAccounts/` [есть] |
| task_153. Трансляция проводок: документ → движения по бухгалтерии | `internship/Configuration/src/Catalogs/ПравилаТрансляции/` [есть] |
| task_154. НДС, себестоимость и расчёты: где живут настоящие сложности | `internship/documentation/accounting/vat_and_cost.md` [есть] |
| task_155. Закрытие периода: регламентная операция и её идемпотентность | `internship/Configuration/src/DataProcessors/РИХ_ЗакрытиеПериода/` [создаётся] |
| task_156. Сверка RIH и бухгалтерской базы: расхождения и их причины | `internship/Configuration/src/Reports/СверкаУчёта/` [создаётся] |
| task_157. Оборотно-сальдовая ведомость на СКД | `internship/Configuration/src/Reports/ОборотноСальдоваяВедомость/` [есть] |
| task_158. Анализ счёта, карточка счёта, оборотка по аналитике | `internship/Configuration/src/Reports/` [есть] |
| task_159. Доработка типовой конфигурации: расширения вместо правок | `internship/Configuration/src/Extensions/` [есть] |
| task_160. Обмен RIH ↔ БП: документы, НСИ, правила, сверка | `internship/documentation/exchange/rih_bp.md` [есть] |
| task_161. Внешние отчёты и обработки для БП: поставка без релиза | `internship/Configuration/src/ExternalReports/` [есть] |
| task_162. Регламентированная отчётность: формы, проверки, сроки | `internship/documentation/compliance/reporting_map.md` [есть] |
| task_163. Модель Документооборота: документы, процессы, задачи | `internship/documentation/docflow/processes.md` [создаётся] |
| task_164. Процесс согласования: этапы, исполнители, сроки, эскалация | `internship/documentation/docflow/approval_process.md` [создаётся] |
| task_165. Задачи и рабочие места: исполнитель, срок, результат | `internship/documentation/docflow/workspace.md` [создаётся] |
| task_166. Интеграция ДО ↔ RIH: документы, состояния, задачи | `internship/documentation/docflow/integration_doh_rih.md` [создаётся] |
| task_167. Доработка ДО: дополнительные реквизиты, печатные формы, процессы | `internship/Configuration/src/Extensions/` [есть] |
| task_168. Права, маршруты и контроль исполнения в ДО | `internship/Configuration/src/Reports/` [есть] |
| task_169. Зачем свои процессы, если есть ДО: границы и ADR | `internship/documentation/adr/` [есть] |
| task_170. Бизнес-процессы и задачи: карта маршрута и экземпляры | `internship/Configuration/src/BusinessProcesses/` [есть] |
| task_171. Сроки, напоминания, эскалация и делегирование | `internship/Configuration/src/Catalogs/ПравилаSLA/` [создаётся] |
| task_172. Рабочее место исполнителя процессов RIH | `internship/Configuration/src/DataProcessors/РИХ_МоиЗадачи/` [создаётся] |
| task_173. Аналитика процессов: сроки, узкие места, загрузка | `internship/documentation/analytics/process_metrics.md` [создаётся] |
| task_174. Интеграция процессов RIH с ДО и внешними трекерами | `internship/src/mock_tracker_api/` [есть] |
| task_175. Кросс-системный отчёт: данные из RIH, БП и ДО | `internship/Configuration/src/Reports/ПортфельКонтрагента/` [создаётся] |
| task_176. Регламентная отчётность по расписанию и рассылка | `internship/documentation/reports/scheduling.md` [создаётся] |
| task_177. Управленческие отчёты: KPI, динамика, план-факт | `internship/documentation/analytics/metrics_dictionary.md` [есть] |
| task_178. Внешние отчёты и обработки: поставка без снятия поддержки | `internship/Configuration/src/ExternalReports/` [есть]<br>`internship/tools/ci/` [есть] |
| task_179. Универсальные механизмы: допреквизиты, динамические списки, настройки | `Документация БСП: «Дополнительные реквизиты и сведения»` [создаётся] |
| task_180. Требования к отчётности: интервью, прототип, приёмка | `internship/documentation/requirements/functional/` [есть] |
| task_181. Как 1С хранит данные в СУБД: таблицы, поля, ссылки | `internship/tools/sql/explore/` [есть] |
| task_182. T-SQL для анализа: соединения, окна, CTE, агрегаты | `internship/tools/sql/analysis/` [есть] |
| task_183. Обработка данных скриптами: безопасно и воспроизводимо | `internship/tools/sql/maintenance/` [есть] |
| task_184. Сессии, блокировки и изоляция транзакций в СУБД | `internship/tools/sql/diagnostics/` [есть] |
| task_185. Tempdb, журнал транзакций и почему база «растёт» | `internship/documentation/operations/sql_capacity.md` [создаётся] |
| task_186. Внешние соединения и ODBC из 1С: когда оправданы | `internship/documentation/integrations/db_link.md` [создаётся] |
| task_187. Чтение плана выполнения: что там искать | `internship/tools/sql/plans/` [есть] |
| task_188. Индексы: что ускорить и за что заплатить | `internship/documentation/performance/index_task_188.md` [создаётся] |
| task_189. Статистика и параметризация: почему план «прыгает» | `internship/tools/sql/diagnostics/` [есть] |
| task_190. Тяжёлый запрос из жизни: разбор и оптимизация «отчёта директора» | `internship/documentation/performance/` [есть] |
| task_191. Кеширование, пул соединений и цена серверных вызовов | `internship/documentation/performance/client_server.md` [создаётся] |
| task_192. Оптимизация проведения документов и регистров под нагрузкой | `internship/documentation/performance/posting_load.md` [создаётся] |
| task_193. Резервное копирование: схема, расписание, проверка | `internship/tools/sql/backup/` [есть] |
| task_194. Восстановление после сбоя: сценарии и репетиция | `internship/documentation/operations/disaster_recovery.md` [создаётся] |
| task_195. Обслуживание СУБД: индексы, статистика, integrity check | `internship/tools/sql/maintenance/` [есть] |
| task_196. Мониторинг кластера 1С и СУБД: что смотреть ежедневно | `internship/documentation/operations/monitoring.md` [создаётся] |
| task_197. Обслуживание базы 1С: ТИИ, регистры, журналы, чистка | `internship/documentation/operations/monthly_maintenance.md` [создаётся] |
| task_198. Работа с администраторами: SLA, окна, эскалации | `internship/documentation/operations/raci_and_sla.md` [создаётся] |
| task_199. Архитектура кластера 1С: серверы, процессы, соединения | `internship/documentation/architecture/deployment.md` [создаётся] |
| task_200. Профиль нагрузки: кто, когда и сколько | `internship/documentation/performance/load_profile.md` [создаётся] |
| task_201. Полный нагрузочный прогон: целевая и пиковая нагрузка | `internship/documentation/performance/load_q3.md` [создаётся] |
| task_202. Capacity planning: что будет через год | `internship/documentation/operations/capacity_plan.md` [создаётся] |
| task_203. Профили производительности: тонкая настройка платформы | `internship/documentation/operations/platform_params.md` [создаётся] |
| task_204. Кейс «система легла»: расследование полного инцидента | `internship/documentation/operations/postmortems/` [есть] |
| task_205. Витрины в СУБД: схема, наполнение, инкрементальность | `internship/tools/sql/marts/` [есть] |
| task_206. Семантический слой: одно определение метрики для всех | `internship/documentation/analytics/metrics_dictionary.md` [есть] |
| task_207. Дашборды: три экрана для трёх ролей | `internship/tools/bi/dashboards/` [есть] |
| task_208. Доступы к аналитике и чувствительные данные | `internship/documentation/security/bi_access.md` [создаётся] |
| task_209. Самообслуживание аналитиков: границы и инструменты | `internship/documentation/analytics/self_service_guide.md` [создаётся] |
| task_210. Свежесть данных и доверие: SLA аналитики | `internship/documentation/analytics/freshness_sla.md` [создаётся] |
| task_211. ETL-конвейер: извлечение, преобразование, загрузка | `internship/tools/sql/etl/` [есть] |
| task_212. Правила качества данных: профилирование и проверки | `internship/Configuration/src/InformationRegisters/КачествоДанных/` [создаётся] |
| task_213. Дедупликация НСИ: поиск, слияние, история | `internship/Configuration/src/DataProcessors/РИХ_ДедупликацияНСИ/` [создаётся] |
| task_214. Мастер-данные (MDM): источник истины для НСИ | `internship/documentation/data_quality/mdm_policy.md` [создаётся] |
| task_215. Исторические данные и архивы: растущая база без тормозов | `internship/documentation/operations/archiving.md` [создаётся] |
| task_216. Предложение по развитию данных: RFC от разработчика | `internship/documentation/rfc/` [создаётся] |
| task_217. Разбор легаси: как читать чужой код на 2000 строк | `internship/legacy/` [есть] |
| task_218. Характеризационные тесты: фиксируем поведение до изменений | `internship/tests/legacy/` [есть] |
| task_219. Рефакторинг крупного модуля: малые шаги, зелёные тесты | `internship/documentation/refactoring/` [создаётся] |
| task_220. Реестр технического долга и работа с ним | `internship/backlog/tech_debt_register.md` [есть] |
| task_221. Стандарты в существующем коде: как внедрить, не остановив разработку | `internship/documentation/quality/standards_rollout.md` [создаётся] |
| task_222. Документация системы: как сделать знания общими | `internship/documentation/index.md` [есть] |
| task_223. Code review квартала: учёт, данные, производительность | `project/acceptance/CodeReviewChecklist.txt` [есть] |
| task_224. Демо учётного и аналитического контура | `project/acceptance/DemoAndDefense.txt` [есть] |
| task_225. Защита данных и производительности: разговор на языке цифр | `internship/documentation/architecture/` [есть] |
| task_226. Деловое общение: разговор с бухгалтерией и ИТ-службой | `internship/documentation/communication/templates.md` [есть] |
| task_227. Ретроспектива Q3 и сравнение трёх кварталов | `internship/documentation/retro/` [есть] |
| task_228. План Q4: AI-контур, мобильность, эксплуатация и финал | `project/tools/Environment.md` [есть]<br>`project/sprint_39/SprintOverview.txt` [есть] |

## Q4

| Задание | Артефакты (путь от `1c/`) |
|---|---|
| task_229. Окружение Python: venv, зависимости, запуск | `internship/src/ai_service/requirements.txt` [есть] |
| task_230. Скрипты на Python: файлы, JSON, CSV, HTTP | `internship/src/scripts/` [есть] |
| task_231. FastAPI: как устроен наш AI-сервис | `internship/src/ai_service/app/routes.py` [есть] |
| task_232. pytest: тесты Python-сервиса и совместная отладка | `internship/src/ai_service/tests/` [есть] |
| task_233. Python ↔ 1С: вызовы, форматы, ошибки, таймауты | `internship/Configuration/src/CommonModules/РИХ_AIКлиент/` [создаётся] |
| task_234. Совместная отладка с AI-командой: процесс и артефакты | `internship/documentation/integrations/debug_process.md` [создаётся] |
| task_235. Что такое эмбеддинги и векторный поиск: практика вместо теории | `internship/src/ai_service/notebooks/embeddings.md` [создаётся] |
| task_236. Корпус знаний: где взять данные и как их подготовить | `internship/docs/knowledge_base/` [есть] |
| task_237. Векторный индекс: pgvector/FAISS и его эксплуатация | `internship/src/ai_service/app/vectorstore.py` [есть] |
| task_238. Поиск и релевантность: эталонные вопросы и метрики | `internship/src/ai_service/evaluation/` [есть] |
| task_239. Гибридный поиск: ключевые слова + векторы | `internship/src/ai_service/app/retrieval.py` [есть] |
| task_240. Перестроение индекса, версионирование и стоимость | `internship/documentation/ai/cost_and_versions.md` [создаётся] |
| task_241. Первый RAG-запрос: контекст, промпт, ответ | `internship/src/ai_service/app/rag.py` [есть] |
| task_242. Цитирование и доверие: ответ со ссылкой на источник | `internship/docs/api/ai_service.md` [есть] |
| task_243. Галлюцинации: как находить и уменьшать | `internship/src/ai_service/evaluation/hallucinations.md` [создаётся] |
| task_244. Оценка качества ответов: от «нравится» к метрикам | `internship/src/ai_service/evaluation/quality.md` [создаётся] |
| task_245. Reranking, уточняющие вопросы и мультитёрн-диалог | `internship/src/ai_service/app/reranking.py` [есть] |
| task_246. Границы применения AI: где ассистент полезен, а где вреден | `internship/documentation/ai/usage_policy.md` [создаётся] |
| task_247. Форма ассистента в 1С: диалог, история, источники | `internship/Configuration/src/DataProcessors/РИХ_Помощник/` [создаётся] |
| task_248. Контекстные подсказки: помощь там, где пользователь работает | `internship/documentation/ai/context_help.md` [создаётся] |
| task_249. Права, аудит и лимиты использования ассистента | `internship/documentation/security/ai_access.md` [создаётся] |
| task_250. Эксплуатация AI-сервиса: мониторинг, деградация, обновления | `internship/documentation/operations/ai_service.md` [создаётся] |
| task_251. Пользователи: обучение, инструкция, сбор обратной связи | `internship/documentation/user_guides/ai_assistant.md` [создаётся] |
| task_252. Кейс AI в бизнес-процессе: измеримая польза | `internship/documentation/ai/case_study.md` [создаётся] |
| task_253. Мобильный проект: структура, ограничения, выбор сценария | `internship/Mobile/README.md` [есть] |
| task_254. Офлайн-данные: выгрузка, локальная работа, хранение | `internship/Mobile/src/` [создаётся] |
| task_255. Синхронизация и конфликты: два человека, один товар | `internship/documentation/mobile/sync_conflicts.md` [создаётся] |
| task_256. Сканер, камера и UX в перчатках | `internship/documentation/mobile/ux.md` [создаётся] |
| task_257. Публикация мобильного приложения и обновления | `internship/documentation/mobile/release.md` [создаётся] |
| task_258. Мобильная аналитика и эксплуатация: что видеть руководителю | `internship/documentation/mobile/operations.md` [создаётся] |
| task_259. Docker для 1С-стенда: сервисы, тома, сети | `internship/tools/docker-compose.yml` [есть] |
| task_260. Публикация 1С и nginx: порты, прокси, заголовки | `internship/tools/nginx/` [есть] |
| task_261. Секреты и конфигурация: .env, доступы, ротация | `internship/tools/.env.example` [есть] |
| task_262. Три стенда: dev, test, integration — и чем они отличаются | `internship/tools/docker-compose.test.yml` [есть] |
| task_263. Резервные копии стенда и восстановление инфраструктуры | `internship/tools/backup/` [создаётся] |
| task_264. Документация инфраструктуры и онбординг новичка | `internship/documentation/infrastructure/onboarding.md` [создаётся] |
| task_265. Конвейер сборки: от исходников до артефакта релиза | `internship/tools/ci/github-actions/ci.yml` [есть]<br>`internship/tools/ci/github-actions/release.yml` [есть] |
| task_266. Уровни тестов в конвейере: что и когда запускать | `internship/tools/ci/` [есть] |
| task_267. Версионирование релизов и обратная совместимость | `internship/documentation/release/changelog.md` [создаётся] |
| task_268. План релиза: окно, шаги, проверки, откат | `internship/documentation/release/release_plan.md` [создаётся] |
| task_269. Обработчики обновления и миграции данных в релизе | `internship/Configuration/src/DataProcessors/РИХ_ОбработчикиОбновления/` [создаётся] |
| task_270. Релиз-менеджмент: несколько команд, одна база, порядок изменений | `internship/documentation/release/release_train.md` [создаётся] |
| task_271. SLI/SLO: что значит «система работает хорошо» | `internship/documentation/operations/slo.md` [создаётся] |
| task_272. Алерты по симптомам: меньше шума, больше смысла | `internship/documentation/operations/runbooks/` [создаётся] |
| task_273. Дежурство: роли, процедуры, коммуникации | `internship/documentation/operations/oncall.md` [создаётся] |
| task_274. Расследование инцидентов: таймлайн, гипотезы, доказательства | `internship/documentation/operations/postmortems/` [есть] |
| task_275. Postmortem-культура: разбор без виноватых | `internship/documentation/operations/postmortems/` [есть] |
| task_276. Улучшение надёжности: план на основе данных года | `internship/documentation/rfc/reliability_plan.md` [создаётся] |
| task_277. ИТ-ландшафт холдинга: карта систем и потоков стоимости | `internship/documentation/architecture/landscape.md` [создаётся] |
| task_278. Целевая архитектура: куда идём и почему | `internship/documentation/architecture/target_state.md` [создаётся] |
| task_279. Технический roadmap: последовательность и стоимость | `internship/documentation/architecture/roadmap.md` [создаётся] |
| task_280. ADR-практика: решения, которые помнят через год | `internship/documentation/adr/` [есть] |
| task_281. Границы и контракты: как системы договариваются | `internship/documentation/integration_registry.md` [есть] |
| task_282. Стоимость владения и обоснование инвестиций | `internship/documentation/architecture/business_case.md` [создаётся] |
| task_283. Проектирование новой подсистемы: от требования до плана | `internship/documentation/architecture/new_subsystem.md` [создаётся] |
| task_284. Реализация подсистемы: малые шаги в живой системе | `internship/tests/` [есть] |
| task_285. Нетиповая доработка УТ: расширение вместо правки конфигурации | `internship/Configuration/src/Extensions/` [есть]<br>`internship/documentation/release/` [есть] |
| task_286. Нетиповая доработка Розницы: кассовый контур и обмен с УТ | `internship/documentation/release/` [есть]<br>`internship/Configuration/src/Extensions/` [есть] |
| task_287. Регресс после обновления типовой конфигурации: контур проверки доработок | `internship/documentation/release/` [есть]<br>`internship/documentation/architecture/dependencies.md` [создаётся] |
| task_288. Эволюция архитектуры: рефакторинг системы, а не модуля | `internship/documentation/refactoring/architecture_evolution.md` [создаётся] |
| task_289. Политики безопасности RIH: от требований к правилам | `internship/documentation/security/policies.md` [создаётся] |
| task_290. Управление доступами: выдача, пересмотр, отзыв | `internship/Configuration/src/Reports/ПраваПользователей/` [создаётся] |
| task_291. Работа с ПДн: реестр, основания, сроки, защита | `internship/documentation/security/pdn_registry.md` [есть] |
| task_292. Аудит нетиповых доработок: инвентаризация перед обновлением типовой конфигурации | `internship/documentation/compliance/audit_folder.md` [создаётся]<br>`internship/documentation/release/` [есть] |
| task_293. Безопасность цепочки поставки: зависимости и артефакты | `internship/tools/ci/github-actions/security.yml` [есть] |
| task_294. Инцидент безопасности: процедура и учебное расследование | `internship/documentation/security/incident_response.md` [создаётся] |
| task_295. Портфолио: собрать год в то, что можно показать | `internship/documentation/portfolio/` [создаётся] |
| task_296. Резюме на языке достижений | `internship/documentation/career/resume.md` [создаётся] |
| task_297. Рассказ о проекте: 2 минуты, 10 минут, 30 минут | `internship/documentation/career/project_story.md` [создаётся] |
| task_298. Технические собеседования: практика на реальных вопросах | `internship/documentation/career/interview_prep.md` [создаётся] |
| task_299. Сертификация 1С и внутренние аттестации: план | `internship/documentation/career/certification_plan.md` [создаётся] |
| task_300. План развития на следующий год: от Middle к Senior | `project/Skills_matrix.md` [есть]<br>`internship/documentation/career/development_plan.md` [создаётся] |
| task_301. Интеграционная сборка: все контуры в одном стенде | `internship/tools/docker-compose.full.yml` [есть] |
| task_302. Сквозной сценарий «день из жизни холдинга» | `internship/tests/golden_path/` [есть] |
| task_303. Полный регресс-прогон и стабилизация системы | `internship/documentation/quality/annual_report.md` [создаётся] |
| task_304. Единый комплект документации системы | `internship/documentation/index.md` [есть] |
| task_305. Передача системы: как бы вы ушли в отпуск на месяц | `internship/documentation/operations/handover.md` [создаётся] |
| task_306. Итоги года в цифрах: отчёт о проделанной работе | `internship/documentation/annual_report.md` [создаётся] |
| task_307. Финальное code review года | `internship/documentation/reviews/final_review.md` [создаётся] |
| task_308. Большое демо системы: 40 минут полного контура | `project/acceptance/DemoAndDefense.txt` [есть] |
| task_309. Защита годового проекта перед «комиссией» | `project/acceptance/DemoAndDefense.txt` [есть] |
| task_310. Ретроспектива года: честный разбор марафона | `internship/documentation/retro/year.md` [создаётся] |
| task_311. Вклад в сообщество: статья, доклад, помощь другим | `project/ideas/architecture/POST_Ideas.txt` [есть] |
| task_312. Выпуск: следующие шаги и закрытие года | `internship/documentation/career/` [создаётся]<br>`internship/documentation/annual_report.md` [создаётся] |
