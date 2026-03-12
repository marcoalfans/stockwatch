from __future__ import annotations

import argparse
import signal
import subprocess
import sys
import time
from pathlib import Path

from stocklab.bot.commands import run_bot_listener


BASE_DIR = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description="StockLab main launcher")
    parser.add_argument(
        "--mode",
        choices=["worker", "bot", "ops", "admin", "all-in-one", "bootstrap"],
        default="worker",
        help="worker = scheduler only, bot = telegram commands only, ops = scheduler + bot, admin = streamlit only, all-in-one = scheduler + bot + admin, bootstrap = init-db + collect-symbols + collect-events + collect-market",
    )
    parser.add_argument("--port", type=int, default=8501, help="Admin panel port")
    args = parser.parse_args()

    if args.mode == "bootstrap":
        _run([sys.executable, "run_jobs.py", "init-db"])
        _run([sys.executable, "run_jobs.py", "collect-symbols"])
        _run([sys.executable, "run_jobs.py", "collect-events"])
        _run([sys.executable, "run_jobs.py", "collect-market"])
        return

    if args.mode == "worker":
        _run([sys.executable, "run_jobs.py", "scheduler"])
        return

    if args.mode == "bot":
        run_bot_listener()
        return

    if args.mode == "admin":
        _run(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "streamlit_app.py",
                "--server.headless",
                "true",
                "--server.port",
                str(args.port),
            ]
        )
        return

    if args.mode == "ops":
        _run_parallel(
            [
                [sys.executable, "run_jobs.py", "scheduler"],
                [sys.executable, "-c", "from stocklab.bot.commands import run_bot_listener; run_bot_listener()"],
            ]
        )
        return

    _run_parallel(
        [
            [sys.executable, "run_jobs.py", "scheduler"],
            [sys.executable, "-c", "from stocklab.bot.commands import run_bot_listener; run_bot_listener()"],
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "streamlit_app.py",
                "--server.headless",
                "true",
                "--server.port",
                str(args.port),
            ],
        ]
    )


def _run(command: list[str]) -> None:
    subprocess.run(command, cwd=BASE_DIR, check=True)


def _run_parallel(commands: list[list[str]]) -> None:
    processes = [subprocess.Popen(command, cwd=BASE_DIR) for command in commands]

    def _shutdown(*_args) -> None:
        for proc in processes:
            if proc.poll() is None:
                proc.terminate()
        time.sleep(1)
        for proc in processes:
            if proc.poll() is None:
                proc.kill()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        while True:
            for proc in processes:
                if proc.poll() is not None:
                    raise SystemExit(proc.returncode or 1)
            time.sleep(2)
    finally:
        _shutdown()


if __name__ == "__main__":
    main()
