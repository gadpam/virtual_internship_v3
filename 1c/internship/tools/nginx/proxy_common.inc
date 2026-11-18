# Общие настройки проксирования. Подключается через include в каждом location.
proxy_http_version 1.1;
proxy_set_header   Host              $host;
proxy_set_header   X-Real-IP         $remote_addr;
proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_set_header   X-Forwarded-Proto $scheme;

# Пробрасываем correlationId дальше по цепочке: 1С → nginx → партнёр → обратно.
# Без этого сквозной разбор инцидента (task_189) невозможен.
proxy_set_header   X-Correlation-Id  $http_x_correlation_id;
proxy_set_header   X-Request-Id      $request_id;

proxy_set_header   Upgrade           $http_upgrade;
proxy_set_header   Connection        $connection_upgrade;

proxy_connect_timeout 5s;
proxy_send_timeout    30s;
proxy_read_timeout    30s;

# Не передаём клиенту «сырые» заголовки сервера-партнёра с версиями ПО
proxy_hide_header  X-Powered-By;
proxy_hide_header  Server;
