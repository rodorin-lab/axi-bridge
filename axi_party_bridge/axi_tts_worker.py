#!/usr/bin/env python3
"""
AXI TTS Worker v2.1 — edge-tts + ffmpeg + paplay + 直列キュー

1人ずつ順番に喋る。同時発話防止。
"""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time

TTS_MUTE_FLAG = "/dev/shm/nexus_tts_muting.flag"

PARTY_BUS_PATH = "/dev/shm/axi_party_bus.jsonl"
POLL_INTERVAL = 0.2

TARGET_SPEAKERS = {"noa", "chatgpt_noah", "hermes"}
VOICE_MAP = {
    "noa": "ja-JP-NanamiNeural",
    "chatgpt_noah": "en-US-AndrewMultilingualNeural",
    "hermes": "ja-JP-KeitaNeural",
}
SPEAKER_NAMES = {
    "noa": "ノア",
    "chatgpt_noah": "ChatGPTノア",
    "hermes": "ヘルメス",
}

# TTS直列キュー
tts_queue: asyncio.Queue | None = None


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


async def edge_tts_generate(text: str, voice: str) -> bytes:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice)
    chunks = []
    async for chunk in communicate.stream():
        if chunk.get("type") == "audio" and "data" in chunk:
            chunks.append(chunk["data"])
    return b"".join(chunks)


def play_audio(mp3_data: bytes) -> None:
    """MP3 → ffmpeg → WAV → paplay"""
    fd, mp3_path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    wav_path = mp3_path.replace(".mp3", ".wav")
    try:
        with open(mp3_path, "wb") as f:
            f.write(mp3_data)

        result = subprocess.run(
            ["ffmpeg", "-y", "-i", mp3_path, "-f", "wav", wav_path],
            capture_output=True, timeout=10,
        )
        if result.returncode != 0:
            log(f"ffmpeg error: {result.stderr.decode(errors='ignore')[:200]}")
            return

        result = subprocess.run(
            ["paplay", wav_path],
            capture_output=True, timeout=15,
        )
        if result.returncode != 0:
            log(f"paplay error: {result.stderr.decode(errors='ignore')[:200]}")
    except subprocess.TimeoutExpired:
        log("playback timeout")
    except Exception as e:
        log(f"play error: {e}")
    finally:
        for p in (mp3_path, wav_path):
            try:
                os.unlink(p)
            except FileNotFoundError:
                pass


async def tts_consumer() -> None:
    """キューから1つずつ取り出して再生（直列）。"""
    while True:
        speaker, text = await tts_queue.get()
        voice = VOICE_MAP.get(speaker, "ja-JP-NanamiNeural")
        log(f"tts: {SPEAKER_NAMES.get(speaker, speaker)} 「{text[:40]}」")
        # TTSミュートフラグON（Voice Loopがマイク入力をスキップ）
        open(TTS_MUTE_FLAG, "w").close()
        try:
            mp3 = await edge_tts_generate(text, voice)
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, play_audio, mp3)
        except Exception as e:
            log(f"tts error: {e}")
        finally:
            # ミュートフラグOFF
            try:
                os.unlink(TTS_MUTE_FLAG)
            except FileNotFoundError:
                pass
            tts_queue.task_done()


async def follow_party_bus() -> None:
    global tts_queue
    tts_queue = asyncio.Queue()

    # TTS消費タスク起動
    consumer_task = asyncio.create_task(tts_consumer())

    open(PARTY_BUS_PATH, "a", encoding="utf-8").close()
    log("tts worker v2.1: edge-tts + ffmpeg + paplay (serial queue)")
    last_spoken = ""

    with open(PARTY_BUS_PATH, "r", encoding="utf-8") as handle:
        handle.seek(0, os.SEEK_END)

        while True:
            line = handle.readline()
            if not line:
                await asyncio.sleep(POLL_INTERVAL)
                continue

            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue

            if not isinstance(payload, dict):
                continue

            speaker = payload.get("speaker")
            text = payload.get("text")
            msg_type = payload.get("type", "")

            if speaker not in TARGET_SPEAKERS or not isinstance(text, str):
                continue

            text = text.strip()
            if not text or msg_type == "status" or text == "thinking...":
                continue

            # 重複ガード
            spoken_key = f"{speaker}:{text}"
            if spoken_key == last_spoken:
                continue
            last_spoken = spoken_key

            # キューに入れる（即座に返る＝次のメッセージ読める）
            await tts_queue.put((speaker, text))


def main() -> int:
    try:
        asyncio.run(follow_party_bus())
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())