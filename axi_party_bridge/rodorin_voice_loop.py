#!/usr/bin/env python3
"""
AXI Rodorin Voice Loop v2 — ReazonSpeech(GPU) + VAD

ロドリンの音声をマイクで拾い、ReazonSpeechで文字起こし、Party Busに送る。
openai-whisper版からの置き換え: GPU加速 + 補正辞書付き。
"""

import argparse
import io
import json
import math
import os
import signal
import struct
import subprocess
import sys
import time
import wave

PARTY_BUS_PATH = "/dev/shm/axi_party_bus.jsonl"
SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_BYTES = SAMPLE_RATE * 2 * FRAME_MS // 1000
VAD_SPEECH_THRESHOLD = 400
VAD_SILENCE_SEC = 2.0
MIN_SPEECH_SEC = 1.0
MAX_SPEECH_SEC = 5.0
MIN_TEXT_CHARS = 3
DEDUP_WINDOW_SEC = 12.0
TTS_MUTE_FLAG = "/dev/shm/nexus_tts_muting.flag"

# STT補正辞書
STT_CORRECTIONS = {
    "アップグディードス": "アップグレード",
    "ヘルメッセージ": "ヘルメス",
    "ノアワ": "ノア",
    "へるめす": "ヘルメス",
    "のあ": "ノア",
    "くりすたる": "クリスタル",
    "めだろっと": "メダロット",
}


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def append_party_bus(text: str) -> None:
    payload = {"speaker": "rodorin", "text": text, "ts": time.time()}
    with open(PARTY_BUS_PATH, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def apply_corrections(text: str) -> str:
    for wrong, correct in STT_CORRECTIONS.items():
        if wrong in text:
            text = text.replace(wrong, correct)
    return text


def should_skip_text(text: str, last_text: str, last_ts: float) -> bool:
    if len(text) < MIN_TEXT_CHARS:
        return True
    if text == last_text and time.time() - last_ts < DEDUP_WINDOW_SEC:
        return True
    return False


# --- ReazonSpeech ---
_stt_pipe = None
STT_MODEL_ID = "japanese-asr/distil-whisper-large-v3-ja-reazonspeech-small"

def load_stt():
    global _stt_pipe
    if _stt_pipe is None:
        from transformers import pipeline
        import torch
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        log(f"loading STT {STT_MODEL_ID} on {device}...")
        _stt_pipe = pipeline(
            "automatic-speech-recognition",
            model=STT_MODEL_ID,
            device=device,
            model_kwargs={"attn_implementation": "sdpa"} if device == "cuda:0" else {},
        )
        log("STT loaded")
    return _stt_pipe


def transcribe_pcm(pcm_data: bytes) -> str:
    import numpy as np
    model = load_stt()
    audio_np = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32) / 32768.0
    result = model(audio_np)
    text = result["text"].strip()
    return " ".join(text.split())


def rms_level(chunk: bytes) -> float:
    sample_count = len(chunk) // 2
    if sample_count <= 0:
        return 0.0
    samples = struct.unpack("<" + "h" * sample_count, chunk[: sample_count * 2])
    power = sum(s * s for s in samples) / sample_count
    return math.sqrt(power)


def choose_record_command() -> list[str]:
    source = os.environ.get(
        "AXI_LIVE_INPUT",
        "alsa_input.usb-Razer_Razer_Kraken_Ultimate_00000000-00.analog-stereo",
    )
    return [
        "parec", "--device", source,
        "--raw", "--channels=1", "--rate=16000", "--format=s16le",
    ]


def read_exact(stream, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = stream.read(size - len(data))
        if not chunk:
            break
        data.extend(chunk)
    return bytes(data)


def run_stdin_loop() -> int:
    last_text = ""
    last_ts = 0.0
    log("stdin mode: type a line and press Enter")
    for raw_line in sys.stdin:
        text = " ".join(raw_line.strip().split())
        if should_skip_text(text, last_text, last_ts):
            continue
        text = apply_corrections(text)
        append_party_bus(text)
        last_text = text
        last_ts = time.time()
        log(f"rodorin(stdin): {text}")
    return 0


def run_mic_loop() -> int:
    silence_limit = int(VAD_SILENCE_SEC * 1000 / FRAME_MS)
    min_bytes = int(SAMPLE_RATE * 2 * MIN_SPEECH_SEC)
    max_bytes = int(SAMPLE_RATE * 2 * MAX_SPEECH_SEC)

    recorder = subprocess.Popen(
        choose_record_command(),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=0,
    )
    assert recorder.stdout is not None

    def stop_recorder(*_args) -> None:
        try:
            recorder.terminate()
        except Exception:
            pass

    signal.signal(signal.SIGINT, stop_recorder)
    signal.signal(signal.SIGTERM, stop_recorder)

    last_text = ""
    last_ts = 0.0
    speech_buffer = bytearray()
    silence_frames = 0
    speaking = False

    log("mic mode: speak into the microphone")
    was_muted = False

    while True:
        # TTS再生中は録音スキップ（エコー防止）
        if os.path.exists(TTS_MUTE_FLAG):
            was_muted = True
            time.sleep(0.3)
            continue

        # ミュート解除直後はバッファを捨てる（TTS残響を除去）
        if was_muted:
            time.sleep(0.5)  # スピーカー残響が消えるまで待つ
            # parecのバッファを空読み
            recorder.stdout.read1(65536) if hasattr(recorder.stdout, 'read1') else None
            was_muted = False
            speech_buffer.clear()
            speaking = False
            silence_frames = 0
            continue

        chunk = read_exact(recorder.stdout, FRAME_BYTES)
        if len(chunk) < FRAME_BYTES:
            if recorder.poll() is not None:
                raise RuntimeError("audio recorder exited")
            time.sleep(0.05)
            continue

        level = rms_level(chunk)

        if not speaking:
            if level > VAD_SPEECH_THRESHOLD:
                speaking = True
                speech_buffer.clear()
                speech_buffer.extend(chunk)
                silence_frames = 0
            continue

        speech_buffer.extend(chunk)

        if level <= VAD_SPEECH_THRESHOLD:
            silence_frames += 1
        else:
            silence_frames = 0

        if silence_frames >= silence_limit or len(speech_buffer) >= max_bytes:
            raw = bytes(speech_buffer)
            speech_buffer.clear()
            speaking = False
            silence_frames = 0

            if len(raw) < min_bytes:
                continue

            try:
                text = transcribe_pcm(raw)
            except Exception as exc:
                log(f"transcribe error: {exc}")
                continue

            text = apply_corrections(text)

            if should_skip_text(text, last_text, last_ts):
                continue

            append_party_bus(text)
            last_text = text
            last_ts = time.time()
            log(f"rodorin: {text}")


def main() -> int:
    open(PARTY_BUS_PATH, "a", encoding="utf-8").close()

    parser = argparse.ArgumentParser()
    parser.add_argument("--stdin", action="store_true", help="read lines from stdin")
    args = parser.parse_args()

    if args.stdin:
        return run_stdin_loop()

    # STTを先にロード
    try:
        load_stt()
    except Exception as exc:
        log(f"STT load failed: {exc}")
        log("falling back to stdin mode")
        return run_stdin_loop()

    while True:
        try:
            return run_mic_loop()
        except KeyboardInterrupt:
            return 0
        except Exception as exc:
            log(f"voice loop error: {exc}")
            time.sleep(1.0)


if __name__ == "__main__":
    raise SystemExit(main())