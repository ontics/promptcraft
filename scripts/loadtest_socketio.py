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
        payload = {"name": cfg.name}
        if cfg.seat_number is not None:
            payload["seat_number"] = cfg.seat_number
        sio.emit("join_game", payload)

    @sio.on("prompt_sent")
    def on_prompt_sent(data):
        # Minimal signal that the server accepted the prompt.
        pass

    @sio.on("image_generated")
    def on_image_generated(data):
        # We don't download/process the image; this is just an ack signal.
        pass

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
        sio.emit("send_prompt", {"prompt": prompt})
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
        )
        t = threading.Thread(target=run_bot, args=(cfg,), daemon=True)
        t.start()
        threads.append(t)

    for t in threads:
        t.join()


if __name__ == "__main__":
    main()

