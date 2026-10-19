"""BotArena Gomoku Traditional Bot entrypoint."""

from __future__ import annotations

import json
import os
import sys
import traceback
from typing import Any

from algorithm.ccgc_rules import CCGCRuleHandler
from algorithm.engine_wrapper import RapfiEngine
from algorithm.time_manager import TimeManager
from botbattle.adapter import BotBattleAdapter


def _request_phase(data: dict[str, Any]) -> str:
    requests = data.get("requests", [])
    if isinstance(requests, list) and requests and isinstance(requests[-1], dict):
        value = requests[-1].get("phase", data.get("phase", "normal_play"))
        return value if isinstance(value, str) else "normal_play"
    return "normal_play"


def main() -> int:
    # Traditional mode sends one complete history and expects one response.
    raw_line = sys.stdin.buffer.readline()
    if not raw_line:
        return 0

    engine: RapfiEngine | None = None
    try:
        data = json.loads(raw_line.decode("utf-8", errors="strict"))
        phase = _request_phase(data)

        # Opening/swap/five-move decisions do not need the engine.  Delaying
        # startup makes the platform's first-turn precheck deterministic.
        if phase in {"white4", "normal_play"}:
            try:
                engine = RapfiEngine(
                    engine_path=os.getenv("RAPFI_ENGINE_PATH"),
                    timeout_ms=int(os.getenv("RAPFI_TIMEOUT_TURN", "6000")),
                )
            except (FileNotFoundError, OSError) as exc:
                # A Python source upload is allowed to run without native
                # binaries.  The adapter then uses its legal pure-Python
                # fallback; local Windows runs still use Rapfi automatically.
                sys.stderr.write(f"Rapfi unavailable, using safe fallback: {exc}\n")

        adapter = BotBattleAdapter(
            CCGCRuleHandler(engine),
            TimeManager(),
        )
        response = adapter.process_request(data)
        sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
        sys.stdout.flush()
        return 0
    except Exception as exc:
        # Never put diagnostics on stdout: the platform treats every stdout
        # line as protocol data.  A missing response is a clear Bot failure.
        sys.stderr.write(f"Bot error: {exc}\n")
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        return 1
    finally:
        if engine is not None:
            engine.terminate()


if __name__ == "__main__":
        raise SystemExit(main())
