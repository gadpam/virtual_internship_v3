#!/usr/bin/env python3
"""Проверки task_133: токены интеграций вместо вечных ключей (зеркало).

HTTP-сервер с единой точкой проверки: POST /api/v1/token выдаёт
токен по client_credentials, маршруты защищены Bearer. В хранилище
только SHA-256 хеши токенов и секретов. Сценарии: выдан — работает;
отозван — 401; истёк — 401; ротация секрета без простоя (старый
в окне grace, потом мёртв); новый секрет работает.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_tokens.py
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

TTL = 60.0
STORE = {"clients": {}, "tokens": {}}


def h(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def add_client(name: str, secret: str, role: str) -> None:
    STORE["clients"][name] = {"secret": h(secret), "prev": "", "prev_until": 0,
                              "role": role, "active": True}


def issue(client: str, secret: str) -> str | None:
    record = STORE["clients"].get(client)
    if not record or not record["active"]:
        return None
    digest = h(secret)
    grace = digest == record["prev"] and time.time() <= record["prev_until"]
    if digest != record["secret"] and not grace:
        return None
    token = uuid.uuid4().hex + "-" + uuid.uuid4().hex
    STORE["tokens"][h(token)] = {"client": client, "role": record["role"],
                                 "expires": time.time() + TTL, "revoked": False}
    return token


def rotate(client: str) -> str:
    record = STORE["clients"][client]
    new_secret = uuid.uuid4().hex
    record["prev"], record["prev_until"] = record["secret"], time.time() + 2.0
    record["secret"] = h(new_secret)
    return new_secret


def token_valid(token: str) -> bool:
    record = STORE["tokens"].get(h(token))
    return bool(record and not record["revoked"] and time.time() <= record["expires"])


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/api/v1/token":
            token = issue(body.get("client", ""), body.get("secret", ""))
            if token is None:
                self._send(401, {"code": "RIH-401"})
            else:
                self._send(200, {"access_token": token, "token_type": "Bearer",
                                 "expires_in": TTL})
            return
        self._send(404, {"code": "RIH-404"})

    def do_GET(self) -> None:  # noqa: N802
        auth = self.headers.get("Authorization", "")
        token = auth[7:] if auth.startswith("Bearer ") else ""
        if not token_valid(token):
            self._send(401, {"code": "RIH-401"})
            return
        self._send(200, {"items": []})

    def log_message(self, *args) -> None:
        pass


def request(port: int, method: str, path: str,
            body: dict | None = None, token: str | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method)
    if token:
        req.add_header("Authorization", "Bearer " + token)
    data = None
    if body is not None:
        req.add_header("Content-Type", "application/json")
        data = json.dumps(body).encode()
    try:
        with urllib.request.urlopen(req, data=data, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read().decode() or "{}")


def main() -> None:
    global TTL
    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        add_client("shop", "secret-shop-1", "catalog-read")
        code, data = request(port, "POST", "/api/v1/token",
                             {"client": "shop", "secret": "secret-shop-1"})
        assert code == 200, (code, data)
        token = data["access_token"]
        assert request(port, "GET", "/api/v1/products", token=token)[0] == 200
        assert request(port, "GET", "/api/v1/products")[0] == 401
        print("[ok] токен выдан по client_credentials и работает; без токена — 401")

        STORE["tokens"][h(token)]["revoked"] = True
        assert request(port, "GET", "/api/v1/products", token=token)[0] == 401
        print("[ok] отозванный токен: 401 немедленно, не в конце TTL")

        TTL = 0.5
        code, data = request(port, "POST", "/api/v1/token",
                             {"client": "shop", "secret": "secret-shop-1"})
        short = data["access_token"]
        time.sleep(0.7)
        assert request(port, "GET", "/api/v1/products", token=short)[0] == 401
        TTL = 60.0
        print("[ok] просроченный токен: 401 (TTL зеркала сжат до 0.5 с)")

        new_secret = rotate("shop")
        assert issue("shop", new_secret)
        assert issue("shop", "secret-shop-1"), "старый секрет в grace обязан работать"
        time.sleep(2.2)
        assert issue("shop", "secret-shop-1") is None
        assert issue("shop", new_secret)
        print("[ok] ротация без простоя: новый секрет сразу, старый — окно grace 2 с, потом 401")

        blob = json.dumps(STORE)
        assert "secret-shop-1" not in blob and token not in blob
        print("[ok] в хранилище только хеши: открытых секретов и токенов нет")
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
