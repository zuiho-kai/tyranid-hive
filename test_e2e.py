"""Real browser E2E for the web mission console."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("HIVE_PORT", "8876"))
BASE_URL = f"http://127.0.0.1:{PORT}"


def wait_for_health(timeout: int = 60) -> None:
    deadline = time.time() + timeout
    last_error = "unknown"
    while time.time() < deadline:
        try:
            with urlopen(f"{BASE_URL}/health", timeout=3) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                if '"service":"tyranid-hive"' in body.replace(" ", ""):
                    return
                last_error = body
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
        time.sleep(1)
    raise RuntimeError(f"Health check timed out: {last_error}")


def main() -> int:
    db_dir = tempfile.mkdtemp(prefix="hive-e2e-")
    db_path = Path(db_dir) / "web-demo.db"
    server_log_path = Path(db_dir) / "server.log"

    env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "HIVE_ADAPTER": "codex",
        "HIVE_PORT": str(PORT),
        "HIVE_DB_PATH": str(db_path),
        "NODE_PATH": str(ROOT / "dashboard" / "node_modules"),
    }

    with server_log_path.open("w", encoding="utf-8") as server_log:
        server = subprocess.Popen(
            [sys.executable, "start.py"],
            cwd=ROOT,
            env=env,
            stdout=server_log,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        try:
            wait_for_health()
            print(f"Service is up: {BASE_URL}")

            completed = subprocess.run(
                ["node", "demo/web_mission_e2e.spec.js"],
                cwd=ROOT,
                env={**env, "BASE_URL": BASE_URL},
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=900,
            )

            print(completed.stdout or "")
            print(completed.stderr or "")
            if completed.returncode != 0 and server_log_path.exists():
                tail = server_log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-80:]
                print("\n[server-log-tail]")
                print("\n".join(tail))
            return completed.returncode
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()


if __name__ == "__main__":
    raise SystemExit(main())
