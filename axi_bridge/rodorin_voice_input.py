#!/usr/bin/env python3
import io
import json
import math
import os
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time
import wave

import whisper


PARTY_BUS_PATH = "/dev/shm/axi_party_bus.jsonl"
SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2
CHANNELS = 1
FRAME_MS = 100
FRAME_BYTES = SAMPLE_RATE * SAMPLE_WIDTH * CHANNELS * FRAME_MS // 1000
START_THRESHOLD = 900.0
STOP_THRESHOLD = 500.0
MIN_SPEECH_MS = 700
MAX_SPEECH_MS = 10000
MAX_PREBUFFER_MS = 400
SILENCE_HANGOVER_MS = 800
MIN_TEXT_CHARS = 3
DEDUP_WINDOW_SEC = 12.0
MODEL_NAME = os.environ.get("AXI_RODORIN_WHISPER_MODEL", "small")
LANGUAGE = "ja"


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def append_party_bus(text: str) -> None:
    payload = {
        "speaker": "rodorin",
        "text": text,
        "ts": time.time(),
    }
    with open(PARTY_BUS_PATH, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def normalize_text(text: str) -> str:
    return " ".join(text.strip().split())


def rms_level(chunk: bytes) -> float:
    if not chunk:
        return 0.0

    sample_count = len(chunk) // 2
    if sample_count <= 0:
        return 0.0

    samples = struct.unpack("<" + "h" * sample_count, chunk[: sample_count * 2])
    power = sum(sample * sample for sample in samples) / sample_count
    return math.sqrt(power)


def write_wav(path: str, pcm_data: bytes) -> None:
    with wave.open(path, "wb") as wav_file:
        wav_file.setnchannels(CHANNELS)
        wav_file.setsampwidth(SAMPLE_WIDTH)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(pcm_data)


def choose_record_command() -> list[str]:
    if shutil.which("parec"):
        return [
            "parec",
            "--raw",
            "--channels=1",
            "--rate=16000",
            "--format=s16le",
            "--device=@DEFAULT_SOURCE@",
        ]

    if shutil.which("rec"):
        return [
            "rec",
            "-q",
            "-t",
            "raw",
            "-b",
            "16",
            "-e",
            "signed-integer",
            "-c",
            "1",
            "-r",
            "16000",
            "-",
        ]

    raise RuntimeError("no supported recorder found; install parec or rec")


def load_model():
    model = whisper.load_model(MODEL_NAME)
    return model


def transcribe_pcm(model, pcm_data: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        temp_path = temp_file.name

    try:
        write_wav(temp_path, pcm_data)
        result = model.transcribe(
            temp_path,
            language=LANGUAGE,
            fp16=False,
            task="transcribe",
            temperature=0.0,
            verbose=False,
        )
        text = result.get("text", "")
        return normalize_text(text)
    finally:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass


def should_skip_text(text: str, last_text: str, last_ts: float) -> bool:
    if len(text) < MIN_TEXT_CHARS:
        return True

    now = time.time()
    if text == last_text and now - last_ts < DEDUP_WINDOW_SEC:
        return True

    return False


def open_recorder() -> subprocess.Popen:
    command = choose_record_command()
    return subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=0,
    )


def read_exact(stream: io.BufferedReader, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = stream.read(size - len(data))
        if not chunk:
            break
        data.extend(chunk)
    return bytes(data)


def capture_loop(model) -> None:
    prebuffer_limit = max(1, MAX_PREBUFFER_MS // FRAME_MS)
    silence_limit = max(1, SILENCE_HANGOVER_MS // FRAME_MS)
    min_frames = max(1, MIN_SPEECH_MS // FRAME_MS)
    max_frames = max(1, MAX_SPEECH_MS // FRAME_MS)

    last_text = ""
    last_ts = 0.0
    prebuffer: list[bytes] = []
    in_speech = False
    speech_frames: list[bytes] = []
    silent_frames = 0

    recorder = open_recorder()
    assert recorder.stdout is not None

    def stop_recorder(*_args) -> None:
        try:
            recorder.terminate()
        except Exception:
            pass

    signal.signal(signal.SIGINT, stop_recorder)
    signal.signal(signal.SIGTERM, stop_recorder)

    while True:
        chunk = read_exact(recorder.stdout, FRAME_BYTES)
        if len(chunk) < FRAME_BYTES:
            if recorder.poll() is not None:
                raise RuntimeError("audio recorder exited")
            time.sleep(0.05)
            continue

        level = rms_level(chunk)

        if not in_speech:
            prebuffer.append(chunk)
            if len(prebuffer) > prebuffer_limit:
                prebuffer.pop(0)

            if level >= START_THRESHOLD:
                in_speech = True
                speech_frames = list(prebuffer)
                silent_frames = 0
            continue

        speech_frames.append(chunk)
        if level < STOP_THRESHOLD:
            silent_frames += 1
        else:
            silent_frames = 0

        frame_count = len(speech_frames)
        finished = silent_frames >= silence_limit or frame_count >= max_frames
        if not finished:
            continue

        in_speech = False
        prebuffer = []

        if frame_count < min_frames:
            speech_frames = []
            silent_frames = 0
            continue

        pcm_data = b"".join(speech_frames)
        speech_frames = []
        silent_frames = 0

        try:
            text = transcribe_pcm(model, pcm_data)
        except Exception as exc:
            log(f"transcribe error: {exc}")
            continue

        if should_skip_text(text, last_text, last_ts):
            continue

        append_party_bus(text)
        last_text = text
        last_ts = time.time()
        log(f"rodorin: {text}")


def main() -> int:
    open(PARTY_BUS_PATH, "a", encoding="utf-8").close()
    try:
        model = load_model()
    except Exception as exc:
        log(f"failed to load whisper model '{MODEL_NAME}': {exc}")
        return 1

    while True:
        try:
            capture_loop(model)
        except KeyboardInterrupt:
            return 0
        except Exception as exc:
            log(f"voice loop error: {exc}")
            time.sleep(1.0)


if __name__ == "__main__":
    raise SystemExit(main())
