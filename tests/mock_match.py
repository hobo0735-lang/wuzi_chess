"""Feed one BotArena Traditional request envelope to main.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def run_mock_test(log_filepath: str) -> None:
    payload: Any = json.loads(Path(log_filepath).read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "input" in payload:
        payload = payload["input"]
    if not isinstance(payload, dict) or not isinstance(payload.get("requests"), list):
        raise ValueError("mock 文件必须是 BotArena Traditional requests/responses 信封")

    proc = subprocess.run(
        [sys.executable, "main.py"],
        input=json.dumps(payload, ensure_ascii=False) + "\n",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "main.py returned a failure")
    response = json.loads(proc.stdout)
    if not isinstance(response, dict) or not isinstance(response.get("response"), dict):
        raise AssertionError(f"invalid BotArena response: {response!r}")
    print(f"phase={payload['requests'][-1].get('phase')} -> {response}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("用法: python tests/mock_match.py <traditional_request.json>")
    run_mock_test(sys.argv[1])
