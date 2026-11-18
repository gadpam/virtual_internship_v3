#!/usr/bin/env bash
# Генерация самоподписанного сертификата для учебного стенда RIH.
# Срок действия 825 дней, SAN — localhost и имена сервисов docker-сети.
set -euo pipefail

cd "$(dirname "$0")"

DAYS=825
CN="rih.local"

if [[ -f mock.crt && -f mock.key ]]; then
  echo "Сертификат уже существует: $(pwd)/mock.crt"
  echo "Для перегенерации удалите mock.crt и mock.key и запустите скрипт снова."
  exit 0
fi

openssl req -x509 -newkey rsa:2048 -nodes -sha256 \
  -days "${DAYS}" \
  -keyout mock.key \
  -out mock.crt \
  -subj "/C=BY/ST=Minsk/L=Minsk/O=Ritejl Grupp (uchebnyy stand)/CN=${CN}" \
  -addext "subjectAltName=DNS:localhost,DNS:rih.local,DNS:nginx,DNS:host.docker.internal,IP:127.0.0.1"

chmod 600 mock.key
chmod 644 mock.crt

echo "Готово:"
echo "  $(pwd)/mock.crt"
echo "  $(pwd)/mock.key"
openssl x509 -in mock.crt -noout -subject -dates
