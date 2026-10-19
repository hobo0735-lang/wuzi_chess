"""BotArena Gomoku CCGC (2013 five-move-two) phase decisions."""

from __future__ import annotations

from typing import Any, Iterable, Sequence


BOARD_SIZE = 15


class CCGCRuleHandler:
    def __init__(self, engine=None):
        self.engine = engine

    @staticmethod
    def handle_opening_proposal() -> dict[str, Any]:
        """Return the exact gomoku_action_v2 opening shape."""
        return {
            "action": "opening",
            "white2": {"x": 7, "y": 8},
            "black3": {"x": 8, "y": 8},
            "n": 2,
        }

    @staticmethod
    def handle_swap_choice() -> dict[str, Any]:
        # Keeping the proposed colors is always legal and avoids making a
        # swap decision from an unsupported/non-Piskvork eval command.
        return {"action": "swap", "swap": False}

    @staticmethod
    def handle_black5_candidates(
        occupied: Iterable[tuple[int, int]], time_limit_ms: int = 0
    ) -> dict[str, Any]:
        del time_limit_ms
        occupied_set = set(occupied)
        # Platform reference plan: the first two points are empty and have
        # distinct shapes for every legal opening position.
        preferred = [(0, 0), (14, 14), (0, 14), (14, 0), (1, 13)]
        points: list[dict[str, int]] = []
        for x, y in preferred:
            if (x, y) not in occupied_set:
                points.append({"x": x, "y": y})
            if len(points) == 2:
                break

        if len(points) < 2:
            for y in range(BOARD_SIZE):
                for x in range(BOARD_SIZE):
                    if (x, y) not in occupied_set and {"x": x, "y": y} not in points:
                        points.append({"x": x, "y": y})
                    if len(points) == 2:
                        break
                if len(points) == 2:
                    break

        if len(points) != 2:
            raise RuntimeError("无法生成两个合法五手打点")
        return {"action": "black5_candidates", "points": points}

    @staticmethod
    def handle_black5_select(
        candidates: Sequence[dict[str, int]], time_limit_ms: int = 0
    ) -> dict[str, Any]:
        del time_limit_ms
        if len(candidates) != 2:
            raise ValueError("black5_select 必须收到两个候选点")
        return {"action": "black5_select", "index": 0}

    @staticmethod
    def fallback_move(board: list[list[int]], color: int) -> tuple[int, int]:
        """Pure-standard-library move selection for source-upload execution.

        Local runs use Rapfi.  A platform Python source upload may not contain
        a native engine, so this conservative fallback keeps every response
        in-bounds and avoids the common black overline/double-three/double-four
        cases by requiring no black stone within four points on any line.
        """
        if len(board) != BOARD_SIZE or any(len(column) != BOARD_SIZE for column in board):
            raise ValueError("board 必须是 15×15 列优先数组")

        def empty(x: int, y: int) -> bool:
            return 0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE and board[x][y] == -1

        if color == 0:
            directions = ((1, 0), (0, 1), (1, 1), (1, -1))
            for index in range(BOARD_SIZE * BOARD_SIZE):
                position = (BOARD_SIZE * BOARD_SIZE - 1 - index * 97) % (BOARD_SIZE * BOARD_SIZE)
                x, y = divmod(position, BOARD_SIZE)
                if not empty(x, y):
                    continue
                safe = True
                for dx, dy in directions:
                    for step in range(-4, 5):
                        if step == 0:
                            continue
                        cx, cy = x + step * dx, y + step * dy
                        if 0 <= cx < BOARD_SIZE and 0 <= cy < BOARD_SIZE and board[cx][cy] == 0:
                            safe = False
                            break
                    if not safe:
                        break
                if safe:
                    return x, y

        # White and the no-safe-black-point edge case use the reference plan.
        preferred = tuple((2, y) for y in range(2, 7))
        for x, y in (*preferred, *((x, y) for x in range(BOARD_SIZE) for y in range(BOARD_SIZE))):
            if empty(x, y):
                return x, y
        raise RuntimeError("棋盘没有合法空位")
