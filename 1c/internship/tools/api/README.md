# Коллекция API mock-магазина (task_74/76)

## Поднять стенд и проверить API за 5 минут

1. Моки стенда: в нашей среде сервисы уже слушают порты 8010–8024
   (Docker нет). На своей машине: `docker compose up -d mock_shop_api`
   из `internship/tools/` или локально —
   `cd internship/src/mock_shop_api && uvicorn app.main:app --port 8020`.
2. Живость: `curl http://127.0.0.1:8020/health` → `{"status":"ok",...}`.
3. Коллекция Bruno одной командой из этой папки:
   `npm exec --yes --package=@usebruno/cli -- bru run --env local`
   Ожидается: 8 запросов, 13 проверок, PASS. Порядок важен: запросы
   04–06 играют в идемпотентность одного заказа, 08 меняет его статус.
4. Тот же набор без Bruno (CI-исполнение): 
   `src/scripts/.venv/bin/python src/scripts/checks_http.py` — 11 проверок.

## Окружения и секреты

`environments/local.bru`: baseUrl и apiKey переменными. Ключ в файле —
учебный ключ учебного mock; боевой ключ в коллекцию не пишется,
подставляется из секретов CI/переменных окружения (task_134).
