"""Piskvork/Rapfi process wrapper used by the BotArena adapter."""

from __future__ import annotations

import os
import platform
import queue
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Iterable, Sequence


BOARD_SIZE = 15
DEFAULT_TIMEOUT_MS = int(os.getenv("RAPFI_TIMEOUT_TURN", "6000"))
READ_EXTRA_SEC = float(os.getenv("RAPFI_READ_EXTRA_SEC", "1"))
_COORDINATE = re.compile(r"^\s*(-?\d+)\s*,\s*(-?\d+)\s*$")


def _find_engine(engine_path: str | None) -> str:
    candidates: list[Path] = []
    if engine_path:
        candidates.append(Path(engine_path))
    configured = os.getenv("RAPFI_ENGINE_PATH")
    if configured:
        candidates.append(Path(configured))

    root = Path(__file__).resolve().parents[1]
    candidates.extend(
        [
            root / "bin" / "rapfi",
            root / "gomoku-rapfi" / "Rapfi-engine" / "pbrain-rapfi-windows-sse.exe",
            root / "gomoku-rapfi" / "Rapfi-engine" / "pbrain-rapfi-linux-clang-sse",
        ]
    )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    searched = ", ".join(str(path) for path in candidates)
    raise FileNotFoundError(f"Rapfi Piskvork 引擎未找到，已搜索: {searched}")


class RapfiEngine:
    """Manage one Rapfi engine using the Piskvork protocol.

    ``player=1`` means the engine's own side and ``player=2`` means the
    opponent.  This is deliberately independent of seat number and supports
    BotArena's post-swap color change.
    """

    def __init__(
        self,
        engine_path: str | None = None,
        model_path: str | None = None,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ) -> None:
        del model_path  # Rapfi loads its model/config from its own directory.
        self.path = _find_engine(engine_path)
        self.timeout_ms = max(100, int(timeout_ms))
        self.lock = threading.Lock()
        self.process: subprocess.Popen[str] | None = None
        self._start()

    def _start(self) -> None:
        self.process = subprocess.Popen(
            [self.path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self._send(f"START {BOARD_SIZE}")
        self._drain_startup()
        self._send("INFO rule 4")
        self._send(f"INFO timeout_turn {self.timeout_ms}")

    def restart(self) -> None:
        self.terminate()
        self._start()

    def _send(self, command: str) -> None:
        if self.process is None or self.process.stdin is None:
            raise RuntimeError("Rapfi 引擎管道未启动")
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()

    def _drain_startup(self, max_lines: int = 50, max_seconds: float = 1.0) -> None:
        if self.process is None or self.process.stdout is None:
            return
        started = time.monotonic()
        for _ in range(max_lines):
            if time.monotonic() - started > max_seconds:
                break
            line = self.process.stdout.readline()
            if not line:
                break
            if line.strip().upper() == "OK":
                break

    def _read_best_move(self) -> tuple[int, int]:
        if self.process is None or self.process.stdout is None:
            raise RuntimeError("Rapfi 引擎管道未启动")
        deadline = time.monotonic() + self.timeout_ms / 1000.0 + READ_EXTRA_SEC
        last = ""
        while time.monotonic() < deadline:
            line = self.process.stdout.readline()
            if line == "":
                raise RuntimeError(f"Rapfi 引擎提前退出，最后输出: {last!r}")
            line = line.strip()
            if not line:
                continue
            last = line
            match = _COORDINATE.match(line)
            if match:
                x, y = int(match.group(1)), int(match.group(2))
                if 0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE:
                    return x, y
                raise RuntimeError(f"Rapfi 返回越界坐标: {x},{y}")
        raise TimeoutError(f"Rapfi 超时，最后输出: {last!r}")

    @staticmethod
    def _normalize_move(move: Sequence[int]) -> tuple[int, int, int | None]:
        if len(move) == 2:
            return int(move[0]), int(move[1]), None
        if len(move) >= 3:
            return int(move[0]), int(move[1]), int(move[2])
        raise ValueError(f"invalid move: {move!r}")

    def search_best_move(
        self,
        moves_history: Iterable[Sequence[int]],
        time_limit_ms: int,
        own_color: int = 0,
    ) -> tuple[int, int]:
        """Return a move from a history of ``(x, y, color)`` entries."""
        moves = list(moves_history)
        with self.lock:
            try:
                self._send("BOARD")
                for index, move in enumerate(moves):
                    x, y, color = self._normalize_move(move)
                    if not (0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE):
                        raise ValueError(f"move out of bounds: {x},{y}")
                    if color in (0, 1):
                        player = 1 if color == own_color else 2
                    else:
                        player = 1 if index % 2 == 0 else 2
                    self._send(f"{x},{y},{player}")
                self._send("DONE")
                return self._read_best_move()
            except Exception:
                self.restart()
                raise

    def get_top_n_moves(
        self,
        moves_history: Iterable[Sequence[int]],
        top_n: int = 2,
        time_limit_ms: int = 200,
    ) -> list[tuple[int, int]]:
        """Return deterministic legal candidates for the five-move phase.

        Rapfi's Piskvork protocol has no portable ``get_policy`` command.  The
        rule layer supplies the official two-point candidate list instead.
        This method remains as a compatibility helper for callers outside the
        BotArena adapter.
        """
        del time_limit_ms
        occupied = {(int(move[0]), int(move[1])) for move in moves_history}
        result: list[tuple[int, int]] = []
        for x, y in ((0, 0), (14, 14), (0, 14), (14, 0), (1, 13)):
            if (x, y) not in occupied:
                result.append((x, y))
            if len(result) >= top_n:
                break
        return result

    def evaluate_position(self, *args, **kwargs) -> float:
        raise NotImplementedError("Rapfi Piskvork 接口不提供 eval 命令")

    def terminate(self) -> None:
        process = self.process
        self.process = None
        if process is None:
            return
        try:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=1)
        except (OSError, subprocess.TimeoutExpired):
            try:
                process.kill()
            except OSError:
                pass
