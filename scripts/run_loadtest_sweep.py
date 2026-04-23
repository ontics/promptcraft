#!/usr/bin/env python3
"""
Phase 1 local loadtest sweep.

Runs the PromptCraft server in stub mode and drives Socket.IO bot clients at a few
load levels. Captures structured [METRIC] logs and writes summaries under
repo-root analysis/loadtesting/local/.

This is intentionally a "no humans needed" harness to reproduce bursty prompt
storms similar to production incident conditions.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_ROOT = REPO_ROOT / "analysis" / "loadtesting" / "local"


def iso_z_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def pick_free_port(start: int = 8010, tries: int = 100) -> int:
    for port in range(start, start + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free port found")


@dataclass
class Scenario:
    name: str
    bots: int
    prompts_per_bot: int
    prompt_every_sec: float
    jitter_sec: float


def start_server(port: int, env: Dict[str, str], out_path: Path) -> subprocess.Popen:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    f = out_path.open("w", encoding="utf-8")
    cmd = [sys.executable, "app.py"]
    p = subprocess.Popen(
        cmd,
        cwd=str(REPO_ROOT / "promptcraft"),
        env=env,
        stdout=f,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return p


def run_bots(server_url: str, scenario: Scenario) -> None:
    cmd = [
        sys.executable,
        "scripts/loadtest_socketio.py",
        "--server",
        server_url,
        "--bots",
        str(scenario.bots),
        "--prompts-per-bot",
        str(scenario.prompts_per_bot),
        "--prompt-every-sec",
        str(scenario.prompt_every_sec),
        "--jitter-sec",
        str(scenario.jitter_sec),
        "--seat-numbers",
    ]
    subprocess.check_call(cmd, cwd=str(REPO_ROOT / "promptcraft"))


def stop_process(p: subprocess.Popen, timeout_sec: float = 5.0) -> None:
    if p.poll() is not None:
        return
    try:
        p.send_signal(signal.SIGINT)
    except Exception:
        try:
            p.terminate()
        except Exception:
            return
    t0 = time.time()
    while time.time() - t0 < timeout_sec:
        if p.poll() is not None:
            return
        time.sleep(0.1)
    try:
        p.kill()
    except Exception:
        pass


def parse_metric_lines(log_path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for line in log_path.read_text(errors="ignore").splitlines():
        if "[METRIC] " not in line:
            continue
        try:
            payload = line.split("[METRIC] ", 1)[1]
            if "}" in payload:
                payload = payload[: payload.rfind("}") + 1]
            rows.append(json.loads(payload))
        except Exception:
            continue
    return rows


def pct(values: List[float], p: float) -> Optional[float]:
    if not values:
        return None
    xs = sorted(values)
    k = (len(xs) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    if f == c:
        return xs[f]
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def summarize_metrics(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    events: Dict[str, int] = {}
    prompt_to_done: List[float] = []
    inflight_starts: List[int] = []
    errors: List[Dict[str, Any]] = []
    for r in rows:
        ev = r.get("event")
        if isinstance(ev, str):
            events[ev] = events.get(ev, 0) + 1
        if ev == "generation.done":
            v = r.get("prompt_to_done_seconds")
            if isinstance(v, (int, float)):
                prompt_to_done.append(float(v))
            if r.get("error_type"):
                errors.append(r)
        if ev == "generation.start":
            iv = r.get("inflight_generations")
            if isinstance(iv, (int, float)):
                inflight_starts.append(int(iv))
    out: Dict[str, Any] = {
        "event_counts": dict(sorted(events.items(), key=lambda kv: (-kv[1], kv[0]))),
        "peak_inflight": max(inflight_starts) if inflight_starts else None,
        "prompt_to_done_seconds": {
            "count": len(prompt_to_done),
            "min": min(prompt_to_done) if prompt_to_done else None,
            "p50": pct(prompt_to_done, 50),
            "p95": pct(prompt_to_done, 95),
            "max": max(prompt_to_done) if prompt_to_done else None,
        },
        "errors_count": len(errors),
        "first_error": errors[0] if errors else None,
    }
    return out


def write_csv(rows: List[Dict[str, Any]], out_csv: Path) -> None:
    # Minimal CSV: only fields we care about.
    keys = [
        "ts",
        "event",
        "gen_req_id",
        "session_id",
        "player_name",
        "onboarding",
        "round",
        "prompt_index",
        "prompt_len",
        "refinement",
        "skip_api",
        "api_seconds",
        "total_seconds",
        "prompt_to_done_seconds",
        "inflight_generations",
        "rss_mb",
        "error_type",
    ]
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8") as f:
        f.write(",".join(keys) + "\n")
        for r in rows:
            vals = []
            for k in keys:
                v = r.get(k)
                if v is None:
                    vals.append("")
                else:
                    s = str(v).replace('"', '""')
                    if "," in s or "\n" in s:
                        s = f"\"{s}\""
                    vals.append(s)
            f.write(",".join(vals) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=0, help="0 = auto-pick free port")
    ap.add_argument("--out-dir", default=str(OUT_ROOT), help="Output directory (default: analysis/loadtesting/local)")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    port = args.port or pick_free_port()
    base_env = os.environ.copy()
    base_env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "PORT": str(port),
            "FLASK_ENV": "production",  # disable reloader
            "PROMPTCRAFT_STUB_IMAGE_GEN": "1",
            "PROMPTCRAFT_LOADTEST_ALLOW_PROMPTS": "1",
            "PROMPTCRAFT_METRICS_HEARTBEAT_SEC": "5",
        }
    )

    scenarios = [
        Scenario(name="baseline_10bots_1s", bots=10, prompts_per_bot=3, prompt_every_sec=1.0, jitter_sec=0.2),
        Scenario(name="incident_like_25bots_1s", bots=25, prompts_per_bot=3, prompt_every_sec=1.0, jitter_sec=0.2),
        Scenario(name="stress_25bots_0p5s", bots=25, prompts_per_bot=3, prompt_every_sec=0.5, jitter_sec=0.2),
    ]

    run_id = f"{iso_z_now().replace(':','').replace('-','')}_p{port}"
    index: Dict[str, Any] = {"run_id": run_id, "port": port, "scenarios": []}

    for sc in scenarios:
        server_log = out_dir / f"{run_id}_{sc.name}_server.log"
        metrics_csv = out_dir / f"{run_id}_{sc.name}_metrics.csv"
        summary_json = out_dir / f"{run_id}_{sc.name}_summary.json"
        server_url = f"http://127.0.0.1:{port}"

        p = start_server(port, base_env, server_log)
        try:
            # Give the server a moment to bind.
            time.sleep(1.2)
            run_bots(server_url, sc)
            # Flush a heartbeat or two.
            time.sleep(1.0)
        finally:
            stop_process(p)

        rows = parse_metric_lines(server_log)
        summary = summarize_metrics(rows)
        write_csv(rows, metrics_csv)
        summary_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        index["scenarios"].append(
            {
                "name": sc.name,
                "server_log": str(server_log),
                "metrics_csv": str(metrics_csv),
                "summary_json": str(summary_json),
                "summary": summary,
            }
        )

    (out_dir / f"{run_id}_index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote outputs under: {out_dir}")
    print(f"Run index: {out_dir / f'{run_id}_index.json'}")


if __name__ == "__main__":
    main()

