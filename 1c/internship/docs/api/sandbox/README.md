# Песочница партнёра RIH (task_96)

Примеры запускаются без нашей ИБ: против учебного контура магазина
стенда (`mock_shop_api`, тот же контракт, что у боевого RIH API).

```bash
export SHOP=http://127.0.0.1:8026          # учебный контур стенда
export KEY=mock-shop-key                   # учебный ключ песочницы

# 1. Здоровье (ключ не нужен к /health магазина — аналог нашего /hs/rih/health)
curl -s $SHOP/health

# 2. Каталог с пагинацией
curl -s "$SHOP/api/v1/products?limit=3&offset=3" -H "X-Api-Key: $KEY"

# 3. Приём заказа (ключ идемпотентности обязателен для повторов)
curl -s -X POST $SHOP/api/v1/orders -H "X-Api-Key: $KEY" \
  -H "Idempotency-Key: 00000000-0000-4000-8000-000000000001" \
  -H "Content-Type: application/json" \
  -d '{"external_id":"SANDBOX-1","customer_ref":"CL-1","lines":[{"sku":"SKU-00001","quantity":1,"price":10.0}],"created_at":"2026-11-17T10:00:00Z"}'

# 4. Тот же заказ повторно тем же ключом: duplicate=true, дубля нет
#    (повторите команду 3 без изменений)

# 5. Ошибка формата: пустые строки заказа → 422 в едином формате RIH
curl -s -X POST $SHOP/api/v1/orders -H "X-Api-Key: $KEY" \
  -H "Idempotency-Key: 00000000-0000-4000-8000-000000000002" \
  -H "Content-Type: application/json" \
  -d '{"external_id":"SANDBOX-2","customer_ref":"CL-1","lines":[],"created_at":"2026-11-17T10:00:00Z"}'
```

Ожидаемое поведение по шагам сверено контрактными тестами
(`src/scripts/checks_contract.py`): если пример разошёлся с ответом
контура — это инцидент контракта, а не «пример устарел».
