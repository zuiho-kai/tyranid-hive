"""检查 Codex CLI 是否可用，并验证最小命令可执行。"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile


def main() -> int:
    codex_bin = shutil.which("codex")
    if not codex_bin:
        print("codex CLI 未找到")
        return 1

    env = {
        **os.environ,
        "HIVE_ADAPTER": "codex",
    }
    cwd = tempfile.mkdtemp(prefix="hive-codex-")
    cmd = [
        "cmd.exe",
        "/c",
        codex_bin,
        "exec",
        "--dangerously-bypass-approvals-and-sandbox",
        "--skip-git-repo-check",
        "print hello from codex",
    ]

    print("codex_bin:", codex_bin)
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            cwd=cwd,
            env=env,
            timeout=120,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    finally:
        shutil.rmtree(cwd, ignore_errors=True)

    print("returncode:", completed.returncode)
    print("stdout:", completed.stdout[:800].strip())
    print("stderr:", completed.stderr[:400].strip())
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
