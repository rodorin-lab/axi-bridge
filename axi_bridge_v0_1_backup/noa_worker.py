#!/usr/bin/env python3
import json
import os
import sys
import time
import urllib.error
import urllib.request


NOA_INBOX_PATH = "/dev/shm/axi_noa_inbox.jsonl"
PARTY_BUS_PATH = "/dev/shm/axi_party_bus.jsonl"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
POLL_INTERVAL = 0.2
REQUEST_TIMEOUT = 30


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def get_api_key() -> str:
    return os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OLLAMA_CLOUD_API_KEY") or ""


def get_base_url() -> str:
    return os.environ.get("AXI_NOA_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def get_model() -> str:
    return os.environ.get("AXI_NOA_MODEL", "")


def append_party_bus(text: str) -> None:
    payload = {
        "speaker": "noa",
        "text": text,
        "ts": time.time(),
    }
    with open(PARTY_BUS_PATH, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def build_request_body(text: str, model: str) -> bytes:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are Noa. Reply in Japanese with one short sentence only.",
            },
            {
                "role": "user",
                "content": text,
            },
        ],
        "temperature": 0.4,
    }
    return json.dumps(payload).encode("utf-8")


def call_model(text: str) -> str:
    api_key = get_api_key()
    model = get_model()

    if not api_key:
        raise RuntimeError("missing OPENROUTER_API_KEY or OLLAMA_CLOUD_API_KEY")
    if not model:
        raise RuntimeError("missing AXI_NOA_MODEL")

    url = get_base_url() + "/chat/completions"
    request = urllib.request.Request(
        url,
        data=build_request_body(text, model),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        body = response.read()

    payload = json.loads(body)
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("invalid API response: missing choices")

    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise RuntimeError("invalid API response: missing message")

    content = message.get("content")
    if not isinstance(content, str):
        raise RuntimeError("invalid API response: missing content")

    return " ".join(content.strip().splitlines()).strip()


def handle_line(line: str) -> None:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return

    if not isinstance(payload, dict):
        return

    if payload.get("to") != "noa":
        return

    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        return

    try:
        reply = call_model(text)
        if reply:
            append_party_bus(reply)
    except urllib.error.URLError as exc:
        log(f"API request failed: {exc}")
    except json.JSONDecodeError as exc:
        log(f"API response JSON error: {exc}")
    except Exception as exc:
        log(f"worker error: {exc}")


def follow_inbox() -> None:
    open(NOA_INBOX_PATH, "a", encoding="utf-8").close()
    open(PARTY_BUS_PATH, "a", encoding="utf-8").close()

    with open(NOA_INBOX_PATH, "r", encoding="utf-8") as handle:
        handle.seek(0, os.SEEK_END)
        while True:
            line = handle.readline()
            if not line:
                time.sleep(POLL_INTERVAL)
                continue
            handle_line(line)


def main() -> int:
    while True:
        try:
            follow_inbox()
        except FileNotFoundError:
            time.sleep(POLL_INTERVAL)
        except Exception as exc:
            log(f"fatal loop error: {exc}")
            time.sleep(1.0)


if __name__ == "__main__":
    raise SystemExit(main())
