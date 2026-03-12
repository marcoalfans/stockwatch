from __future__ import annotations

import argparse
import signal
import subprocess
import sys
import time
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description="StockLab main launcher")
    parser.add_argument(
        "--mode",
        choices=["worker", "admin", "all-in-one", "bootstrap"],
        default="worker",
        help="worker = scheduler only, admin = streamlit only, all-in-one = both, bootstrap = init-db + collect-symbols + collect-events + collect-market",
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

    scheduler_proc = subprocess.Popen([sys.executable, "run_jobs.py", "scheduler"], cwd=BASE_DIR)
    admin_proc = subprocess.Popen(
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
        cwd=BASE_DIR,
    )

    def _shutdown(*_args) -> None:
        for proc in [scheduler_proc, admin_proc]:
            if proc.poll() is None:
                proc.terminate()
        time.sleep(1)
        for proc in [scheduler_proc, admin_proc]:
            if proc.poll() is None:
                proc.kill()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        while True:
            if scheduler_proc.poll() is not None:
                raise SystemExit(scheduler_proc.returncode or 1)
            if admin_proc.poll() is not None:
                raise SystemExit(admin_proc.returncode or 1)
            time.sleep(2)
    finally:
        _shutdown()


def _run(command: list[str]) -> None:
    subprocess.run(command, cwd=BASE_DIR, check=True)


if __name__ == "__main__":
    main()
