#!/usr/bin/env python3
"""
Socket.IO load test client for PromptCraft.

Goal: simulate N players connecting + spamming prompts to reproduce the bursty
load pattern that preceded mass disconnects, without needing humans.

Default behavior is SAFE for local testing:
- expects PROMPTCRAFT_STUB_IMAGE_GEN=1 on the server to avoid paid API calls
- sends short prompts
"""

from __future__ import annotations

import argparse
import random
import string
import threading
import time
from dataclasses import dataclass
from typing import Optional

import socketio  # python-socketio (client)

_LOCK = threading.Lock()
_COUNTERS = {
    "connect_ok": 0,
    "connect_error": 0,
    "server_error_event": 0,
    "prompt_sent_event": 0,
    "image_generated_event": 0,
}


def _rand_name(prefix: str = "Bot") -> str:
    suffix = "".join(random.choice(string.ascii_uppercase) for _ in range(4))
    return f"{prefix}-{suffix}"


@dataclass
class BotConfig:
    server_url: str
    name: str
    seat_number: Optional[int]
    prompt_every_sec: float
    prompts_total: int
    jitter_sec: float
    run_id: Optional[str]


def run_bot(cfg: BotConfig) -> None:
    sio = socketio.Client(
        reconnection=True,
        reconnection_attempts=10,
        reconnection_delay=0.5,
        reconnection_delay_max=5.0,
        logger=False,
        engineio_logger=False,
    )

    @sio.event
    def connect():
        with _LOCK:
            _COUNTERS["connect_ok"] += 1
        payload = {"name": cfg.name}
        if cfg.seat_number is not None:
            payload["seat_number"] = cfg.seat_number
        sio.emit("join_game", payload)

    @sio.event
    def connect_error(data):
        with _LOCK:
            _COUNTERS["connect_error"] += 1

    @sio.on("error")
    def on_error(data):
        # Server emitted an application-level error.
        with _LOCK:
            _COUNTERS["server_error_event"] += 1

    @sio.on("prompt_sent")
    def on_prompt_sent(data):
        # Minimal signal that the server accepted the prompt.
        with _LOCK:
            _COUNTERS["prompt_sent_event"] += 1

    @sio.on("image_generated")
    def on_image_generated(data):
        # We don't download/process the image; this is just an ack signal.
        with _LOCK:
            _COUNTERS["image_generated_event"] += 1

    @sio.event
    def disconnect():
        # Let reconnection logic handle it.
        pass

    sio.connect(cfg.server_url, transports=["websocket", "polling"])

    for i in range(cfg.prompts_total):
        # small jitter to avoid perfect sync
        if cfg.jitter_sec:
            time.sleep(random.random() * cfg.jitter_sec)
        prompt = f"loadtest prompt {i+1}"
        payload = {"prompt": prompt}
        if cfg.run_id:
            payload["loadtest_run_id"] = cfg.run_id
        sio.emit("send_prompt", payload)
        time.sleep(cfg.prompt_every_sec)

    sio.disconnect()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", required=True, help="e.g. http://localhost:8080 or https://your-railway.app")
    ap.add_argument("--bots", type=int, default=25)
    ap.add_argument("--prompts-per-bot", type=int, default=3)
    ap.add_argument("--prompt-every-sec", type=float, default=3.0)
    ap.add_argument("--jitter-sec", type=float, default=0.4)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--seat-numbers", action="store_true", help="Send seat_number 1..N")
    ap.add_argument("--run-id", default="", help="Tag prompts with loadtest_run_id for log filtering")
    args = ap.parse_args()

    random.seed(args.seed)

    threads = []
    for i in range(args.bots):
        cfg = BotConfig(
            server_url=args.server,
            name=_rand_name(),
            seat_number=(i + 1) if args.seat_numbers else None,
            prompt_every_sec=args.prompt_every_sec,
            prompts_total=args.prompts_per_bot,
            jitter_sec=args.jitter_sec,
            run_id=(args.run_id or None),
        )
        t = threading.Thread(target=run_bot, args=(cfg,), daemon=True)
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    with _LOCK:
        print("loadtest_summary", _COUNTERS)


if __name__ == "__main__":
    main()

