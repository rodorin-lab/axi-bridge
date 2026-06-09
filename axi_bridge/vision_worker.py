#!/usr/bin/env python3
import argparse
import base64
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request


PARTY_BUS_PATH = "/dev/shm/axi_party_bus.jsonl"
DEFAULT_INTERVAL = 5.0
DEFAULT_MODEL = "gemini-2.5-flash"


def append_party_bus(text: str) -> None:
    payload = {
        "speaker": "vision",
        "text": text,
        "ts": time.time(),
    }
    with open(PARTY_BUS_PATH, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def get_api_key() -> str:
    return os.environ.get("GOOGLE_API_KEY", "")


def get_model_name() -> str:
    return os.environ.get("AXI_VISION_MODEL", DEFAULT_MODEL)


def choose_screenshot_command(output_path: str) -> list[str] | None:
    if shutil.which("grim"):
        return ["grim", output_path]
    return None


def capture_screenshot(output_path: str) -> tuple[bool, str]:
    command = choose_screenshot_command(output_path)
    if not command:
        return False, "grim not found"

    if os.environ.get("XDG_SESSION_TYPE") not in ("wayland", ""):
        return False, f"unsupported session type: {os.environ.get('XDG_SESSION_TYPE')}"

    if not os.environ.get("WAYLAND_DISPLAY"):
        return False, "WAYLAND_DISPLAY is not set"

    grim_env = os.environ.copy()
    grim_env["WAYLAND_DISPLAY"] = os.environ.get("WAYLAND_DISPLAY", "")
    grim_env["XDG_RUNTIME_DIR"] = os.environ.get("XDG_RUNTIME_DIR", "")
    grim_env["XDG_SESSION_TYPE"] = os.environ.get("XDG_SESSION_TYPE", "")

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            env=grim_env,
        )
    except Exception as exc:
        return False, str(exc)

    if result.returncode != 0:
        error_text = (result.stderr or "").strip() or f"exit {result.returncode}"
        return False, error_text

    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        return False, "empty screenshot"

    return True, "ok"


def call_vision_ai(image_path: str) -> str:
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set")

    with open(image_path, "rb") as image_file:
        image_data = base64.b64encode(image_file.read()).decode("ascii")

    prompt = "このゲーム画面を日本語で短く1文だけ説明してください。ゲーム状況説明だけを書いてください。"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": image_data,
                        }
                    },
                ]
            }
        ]
    }

    model_name = get_model_name()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=60) as response:
        response_body = response.read()

    body = json.loads(response_body)
    candidates = body.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise RuntimeError("invalid Gemini response: missing candidates")

    content = candidates[0].get("content")
    if not isinstance(content, dict):
        raise RuntimeError("invalid Gemini response: missing content")

    parts = content.get("parts")
    if not isinstance(parts, list) or not parts:
        raise RuntimeError("invalid Gemini response: missing parts")

    texts = []
    for part in parts:
        if isinstance(part, dict):
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(text.strip())

    if not texts:
        raise RuntimeError("invalid Gemini response: missing text")

    return " ".join(" ".join(texts).splitlines()).strip()


def run_once() -> None:
    os.makedirs(os.path.dirname(PARTY_BUS_PATH), exist_ok=True)
    open(PARTY_BUS_PATH, "a", encoding="utf-8").close()

    fd, image_path = tempfile.mkstemp(suffix=".png")
    os.close(fd)

    try:
        capture_ok, reason = capture_screenshot(image_path)
        if not capture_ok:
            append_party_bus(f"画面解析はダミーです。スクリーンショット取得は未完了です: {reason}")
            return

        try:
            summary = call_vision_ai(image_path)
        except (urllib.error.URLError, json.JSONDecodeError, RuntimeError) as exc:
            append_party_bus(f"画面解析はダミーです。Vision AI 呼び出しは未完了です: {exc}")
            return

        append_party_bus(summary)
    finally:
        try:
            os.unlink(image_path)
        except FileNotFoundError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL)
    args = parser.parse_args()

    if args.once:
        run_once()
        return 0

    while True:
        run_once()
        time.sleep(max(0.1, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
