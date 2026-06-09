#!/usr/bin/env python3
import json
import os
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


PARTY_BUS_PATH = "/dev/shm/axi_party_bus.jsonl"
NOA_INBOX_PATH = "/dev/shm/axi_noa_inbox.jsonl"
HERMES_INBOX_PATH = "/dev/shm/axi_hermes_inbox.jsonl"
HOST = "127.0.0.1"
PORT = 8765
DEFAULT_CHATGPT_SPEAKER = "chatgpt_noah"


def ensure_files() -> None:
    for path in (PARTY_BUS_PATH, NOA_INBOX_PATH, HERMES_INBOX_PATH):
        open(path, "a", encoding="utf-8").close()


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: object) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def error_response(handler: BaseHTTPRequestHandler, status: int, message: str) -> None:
    json_response(handler, status, {"ok": False, "error": message})


def append_jsonl(path: str, payload: dict) -> None:
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def read_latest_jsonl(path: str, limit: int) -> list[object]:
    rows: deque[object] = deque(maxlen=max(1, limit))
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                rows.append({"raw": line, "error": "invalid_json"})
    return list(rows)


def read_request_json(handler: BaseHTTPRequestHandler) -> dict:
    length_header = handler.headers.get("Content-Length", "0")
    try:
        length = int(length_header)
    except ValueError as exc:
        raise ValueError("invalid Content-Length") from exc

    body = handler.rfile.read(max(0, length))
    if not body:
        return {}

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValueError("request body must be valid JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")

    return payload


def coerce_limit(value: object, default: int = 10) -> int:
    if value is None:
        return default
    if isinstance(value, str) and not value.strip():
        return default
    try:
        limit = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("limit must be an integer") from exc
    return max(1, min(limit, 200))


class AxiMCPHandler(BaseHTTPRequestHandler):
    server_version = "AxiMCP/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            json_response(
                self,
                200,
                {
                    "ok": True,
                    "service": "axi_party_mcp",
                    "endpoints": [
                        "GET /party/latest?limit=10",
                        "GET /inbox/noa?limit=10",
                        "GET /inbox/hermes?limit=10",
                        "POST /party/write",
                        "POST /rpc",
                    ],
                },
            )
            return

        if parsed.path == "/party/latest":
            params = parse_qs(parsed.query)
            try:
                limit = coerce_limit(params.get("limit", [10])[0], 10)
            except ValueError as exc:
                error_response(self, 400, str(exc))
                return
            json_response(
                self,
                200,
                {"ok": True, "items": read_latest_jsonl(PARTY_BUS_PATH, limit)},
            )
            return

        if parsed.path == "/inbox/noa":
            params = parse_qs(parsed.query)
            try:
                limit = coerce_limit(params.get("limit", [10])[0], 10)
            except ValueError as exc:
                error_response(self, 400, str(exc))
                return
            json_response(
                self,
                200,
                {"ok": True, "target": "noa", "items": read_latest_jsonl(NOA_INBOX_PATH, limit)},
            )
            return

        if parsed.path == "/inbox/hermes":
            params = parse_qs(parsed.query)
            try:
                limit = coerce_limit(params.get("limit", [10])[0], 10)
            except ValueError as exc:
                error_response(self, 400, str(exc))
                return
            json_response(
                self,
                200,
                {
                    "ok": True,
                    "target": "hermes",
                    "items": read_latest_jsonl(HERMES_INBOX_PATH, limit),
                },
            )
            return

        error_response(self, 404, "not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = read_request_json(self)
        except ValueError as exc:
            error_response(self, 400, str(exc))
            return

        if parsed.path == "/party/write":
            self.handle_party_write(payload)
            return

        if parsed.path == "/rpc":
            self.handle_rpc(payload)
            return

        error_response(self, 404, "not found")

    def handle_party_write(self, payload: dict) -> None:
        speaker = payload.get("speaker", DEFAULT_CHATGPT_SPEAKER)
        text = payload.get("text")
        if not isinstance(speaker, str) or not speaker.strip():
            error_response(self, 400, "speaker must be a non-empty string")
            return
        if not isinstance(text, str) or not text.strip():
            error_response(self, 400, "text must be a non-empty string")
            return

        message = {
            "speaker": speaker,
            "text": text,
            "ts": time.time(),
        }
        append_jsonl(PARTY_BUS_PATH, message)
        json_response(self, 200, {"ok": True, "item": message})

    def handle_rpc(self, payload: dict) -> None:
        method = payload.get("method")
        params = payload.get("params", {})
        req_id = payload.get("id")

        if not isinstance(params, dict):
            error_response(self, 400, "params must be a JSON object")
            return

        try:
            result = dispatch_rpc(method, params)
        except ValueError as exc:
            json_response(self, 400, {"jsonrpc": "2.0", "id": req_id, "error": {"message": str(exc)}})
            return

        json_response(self, 200, {"jsonrpc": "2.0", "id": req_id, "result": result})

    def log_message(self, format: str, *args: object) -> None:
        return


def dispatch_rpc(method: object, params: dict) -> dict:
    if method == "party_bus_write":
        speaker = params.get("speaker", DEFAULT_CHATGPT_SPEAKER)
        text = params.get("text")
        if not isinstance(speaker, str) or not speaker.strip():
            raise ValueError("speaker must be a non-empty string")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text must be a non-empty string")
        message = {"speaker": speaker, "text": text, "ts": time.time()}
        append_jsonl(PARTY_BUS_PATH, message)
        return {"ok": True, "item": message}

    if method == "party_bus_read_latest":
        limit = coerce_limit(params.get("limit"), 10)
        return {"ok": True, "items": read_latest_jsonl(PARTY_BUS_PATH, limit)}

    if method == "inbox_read":
        target = params.get("target")
        limit = coerce_limit(params.get("limit"), 10)
        if target == "noa":
            path = NOA_INBOX_PATH
        elif target == "hermes":
            path = HERMES_INBOX_PATH
        else:
            raise ValueError("target must be 'noa' or 'hermes'")
        return {"ok": True, "target": target, "items": read_latest_jsonl(path, limit)}

    raise ValueError("unknown method")


def main() -> int:
    ensure_files()
    server = ThreadingHTTPServer((HOST, PORT), AxiMCPHandler)
    print(f"axi_mcp_server listening on http://{HOST}:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
