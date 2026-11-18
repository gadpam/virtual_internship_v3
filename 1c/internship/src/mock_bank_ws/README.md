# Mock-сервис «Банк» (SOAP / веб-сервис)

Имитирует банковский веб-сервис по обмену платёжными документами. Работает по
SOAP 1.1 с XML-конвертом и WSDL — именно в таком виде банк обычно отдаёт
интеграцию (задания task_85, task_86).

Запуск: `uvicorn app.main:app --host 0.0.0.0 --port 8023`

- WSDL: `http://localhost:8023/bank?wsdl`
- Точка вызова: `POST http://localhost:8023/bank`

## Операции

| Операция | Назначение |
|---|---|
| `GetStatement` | банковская выписка за период (список платежей) |
| `SendPaymentOrder` | приём платёжного поручения из 1С |
| `GetPaymentStatus` | статус платежа по `paymentId` |
| `GetRates` | курсы валют на дату (используется в task_94) |

## Авторизация

SOAP-заголовок `Authentication` с `Login`/`Password` (по умолчанию
`bank_user` / `bank_password`). Без авторизации — SOAP Fault `AuthFailed`.

## Ошибки — только SOAP Fault

Важно для task_86: клиент 1С должен корректно разбирать Fault, а не получать HTTP 500.

| Fault code | Когда |
|---|---|
| `AuthFailed` | неверный логин/пароль |
| `InvalidPeriod` | дата начала больше даты конца |
| `NotFound` | неизвестный `paymentId` |
| `ServiceUnavailable` | режим сбоя `X-Fault-Mode: error500` |

## Тест без 1С

```bash
curl -s -X POST http://localhost:8023/bank -H 'Content-Type: text/xml' -d @- <<'XML'
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:bank="http://rih.local/bank">
  <soapenv:Header>
    <bank:Authentication><bank:Login>bank_user</bank:Login><bank:Password>bank_password</bank:Password></bank:Authentication>
  </soapenv:Header>
  <soapenv:Body>
    <bank:GetRates><bank:Date>2026-01-15</bank:Date></bank:GetRates>
  </soapenv:Body>
</soapenv:Envelope>
XML
```
