# Контракт банка (BANK) · SOAP · task_85, task_86, task_94

Mock-сервис: `src/mock_bank_ws` · порт `8023` · точка `/bank` · WSDL: `GET /bank`.
Авторизация: SOAP-заголовок `Security` с `Login`/`Password` (`MOCK_BANK_LOGIN`,
`MOCK_BANK_PASSWORD`).

## Почему SOAP

Банк и государственные системы редко отдают REST: WSDL даёт жёсткую схему, а
XDTO в 1С строит типы автоматически. Задания task_85 (публикация своего
web-сервиса) и task_86 (потребление внешнего) отрабатываются именно здесь.

## Транспорт

* `POST /bank` — тело SOAP 1.1, `Content-Type: text/xml; charset=utf-8`,
  заголовок `SOAPAction` не обязателен: операция определяется по имени первого
  элемента тела;
* ответ — SOAP-конверт с пространством имён `http://rih.example/bank`;
* ошибка — `<soap:Fault>` с `faultcode` и `faultstring`.

## Операции

### `GetStatement` — выписка

Запрос: `DateFrom`, `DateTo` (обе необязательные, формат `ГГГГ-ММ-ДД`).

Ответ: `DateFrom`, `DateTo`, `Total`, `Payments/Payment[]` с полями `PaymentId`,
`DocNumber`, `DocDate`, `Payer`, `Amount`, `Currency`, `Status`.

Ошибка: `InvalidPeriod` — дата начала больше даты конца.

### `SendPaymentOrder` — платёжное поручение

Запрос: `ExternalId` (ключ идемпотентности), `DocNumber`, `DocDate`, `Payer`,
`Payee`, `Amount`, `Currency`, `Purpose`.

Ответ: `PaymentId`, `Status` (`processing`), `Duplicate` (`true`/`false`).

Повтор с тем же `ExternalId` возвращает прежний `PaymentId` и `Duplicate = true`:
платёж не уходит в банк дважды (task_105). Это критично: задвоенный платёж —
финансовый инцидент, а не неудобство.

Ошибки: `InvalidAmount` — не число или ≤ 0.

### `GetPaymentStatus` — статус платежа

Запрос: `PaymentId`. Ответ: `PaymentId`, `Status`, `Amount`.
В mock статус переходит `processing → paid` при первом запросе.
Ошибка: `NotFound`.

### `GetRates` — курсы валют

Запрос: `Date` (необязательный). Ответ: `Rate[]` с `Date`, `CharCode`, `Nominal`,
`Value`.

**Кеширование обязательно** (task_94): курсы меняются раз в день, вызывать сервис
на каждое проведение документа — способ положить и банк, и себя. Схема: кеш на
дату → при промахе вызов → запись в регистр сведений `РИХ_КурсыВалют` →
повторный вызов не чаще одного раза в сутки и при явном обновлении регламентным
заданием.

## Обработка ошибок на стороне 1С

| faultcode | HTTP | Что делать |
|---|---|---|
| `InvalidPeriod`, `InvalidAmount` | 200 + Fault | не повторять: исправить данные |
| `NotFound` | 200 + Fault | проверить `PaymentId` по журналу |
| `Unauthorized` | 200 + Fault | не повторять: учётные данные (task_134) |
| `UnknownOperation` | 200 + Fault | ошибка интеграции: версия WSDL разошлась |
| — | 5xx / таймаут | повтор с задержкой, затем очередь и инцидент |

Важно: SOAP-ошибка приходит с HTTP 200 и телом `Fault`. Клиент, который смотрит
только на код состояния, «успешно» обработает отказ банка (task_86).

## Режимы сбоев

Заголовок `X-Fault-Mode` у `GET /bank` (WSDL): `garbage` отдаёт не-XML, чтобы
проверить обработку повреждённой схемы. Сбои вызовов отрабатываются на уровне
HTTP: таймауты nginx для `/bank` — 60 с.
