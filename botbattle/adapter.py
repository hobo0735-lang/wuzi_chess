"""BotArena Traditional JSON adapter for Gomoku."""

from __future__ import annotations

from typing import Any

from algorithm.ccgc_rules import CCGCRuleHandler
from algorithm.time_manager import TimeManager


BOARD_SIZE = 15
EXPECTED_PROTOCOL = 2
EXPECTED_RULESET = "gomoku_ccgc_2013_five_move_two_v2"


def _is_empty(cell: Any) -> bool:
    return cell is None or cell == -1


def _board_matrix(request: dict[str, Any]) -> list[list[Any]] | None:
    board = request.get("board")
    if not isinstance(board, list) or len(board) != BOARD_SIZE:
        return None
    if any(not isinstance(row, list) or len(row) != BOARD_SIZE for row in board):
        return None
    return board


def _point(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, dict):
        return None
    x, y = value.get("x"), value.get("y")
    if isinstance(x, bool) or isinstance(y, bool):
        return None
    if not isinstance(x, int) or not isinstance(y, int):
        return None
    if 0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE:
        return x, y
    return None


def _history_coordinates(requests: list[Any], responses: list[Any]) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()

    def add(value: Any) -> None:
        point = _point(value)
        if point is not None and point not in seen:
            seen.add(point)
            result.append(point)

    for item in requests:
        if not isinstance(item, dict):
            continue
        for key in ("black1", "white2", "black3", "white4", "black5_selected", "last"):
            value = item.get(key)
            if isinstance(value, dict):
                add(value)
        opening = item.get("opening")
        if isinstance(opening, dict):
            for key in ("black1", "white2", "black3"):
                add(opening.get(key))

    for item in responses:
        if not isinstance(item, dict):
            continue
        action = item.get("response", item)
        if isinstance(action, dict) and action.get("action") == "move":
            add(action)
        elif isinstance(action, dict) and action.get("action") == "opening":
            # black1 is fixed by the referee; white2 and black3 are supplied
            # by the Bot's previous opening response.
            add({"x": 7, "y": 7})
            add(action.get("white2"))
            add(action.get("black3"))
    return result


def _opening_coordinates(requests: list[Any], responses: list[Any]) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []

    def add(value: Any) -> None:
        point = _point(value)
        if point is not None and point not in result:
            result.append(point)

    for item in [*requests, *responses]:
        if not isinstance(item, dict):
            continue
        action = item.get("response", item)
        if isinstance(action, dict) and action.get("action") == "opening":
            add({"x": 7, "y": 7})
            add(action.get("white2"))
            add(action.get("black3"))
        opening = item.get("opening")
        if isinstance(opening, dict):
            add(opening.get("black1", {"x": 7, "y": 7}))
            add(opening.get("white2"))
            add(opening.get("black3"))
    return result


def extract_moves(data: dict[str, Any], request: dict[str, Any]) -> list[tuple[int, int, int]]:
    """Return ordered ``(x, y, color)`` moves from the self-contained request."""
    matrix = _board_matrix(request)
    if matrix is None:
        raise ValueError("请求缺少合法的 15×15 board")

    cells: dict[tuple[int, int], int] = {}
    # BotArena board is board[x][y].
    for x, column in enumerate(matrix):
        for y, cell in enumerate(column):
            if _is_empty(cell):
                continue
            if isinstance(cell, bool) or not isinstance(cell, int) or cell not in (0, 1):
                raise ValueError(f"board 在 ({x},{y}) 包含非法棋子值: {cell!r}")
            cells[(x, y)] = cell

    requests = data.get("requests", [])
    responses = data.get("responses", [])
    hints = _history_coordinates(requests, responses)
    ordered: list[tuple[int, int]] = []
    for point in _opening_coordinates(requests, responses):
        if point in cells and point not in ordered:
            ordered.append(point)

    # After the opening, colors must alternate white4, black5, white6, ... .
    # Use protocol hints when available and the board as the authority for the
    # color; this preserves move order for Renju instead of row-major sorting.
    for index in range(len(ordered), len(cells)):
        expected_color = 1 if index % 2 == 1 else 0
        choices = [
            point for point in hints
            if point in cells and point not in ordered and cells[point] == expected_color
        ]
        if not choices:
            choices = [
                point for point, cell_color in cells.items()
                if point not in ordered and cell_color == expected_color
            ]
        if not choices:
            choices = [point for point in cells if point not in ordered]
        if not choices:
            break
        ordered.append(choices[0])
    return [(x, y, cells[(x, y)]) for x, y in ordered if (x, y) in cells]


def _phase(data: dict[str, Any], request: dict[str, Any]) -> str:
    value = request.get("phase", data.get("phase", "normal_play"))
    if not isinstance(value, str):
        raise ValueError("phase 必须是字符串")
    return value


def _my_color(data: dict[str, Any], request: dict[str, Any]) -> int:
    color = request.get("color", data.get("color"))
    if isinstance(color, int) and not isinstance(color, bool) and color in (0, 1):
        return color

    me = request.get("me", data.get("me", 0))
    seat_colors = request.get("seat_colors", data.get("seat_colors", {}))
    if isinstance(seat_colors, dict):
        value = seat_colors.get(str(me), seat_colors.get(me))
        if isinstance(value, int) and value in (0, 1):
            return value
    if isinstance(seat_colors, list) and isinstance(me, int) and 0 <= me < len(seat_colors):
        value = seat_colors[me]
        if isinstance(value, int) and value in (0, 1):
            return value
    return 0


def _remaining_seconds(data: dict[str, Any], request: dict[str, Any]) -> float:
    for source in (request, data):
        for key in ("remaining_time_ms", "time_left_ms", "remaining_ms"):
            value = source.get(key)
            if isinstance(value, (int, float)) and value >= 0:
                return float(value) / 1000.0
        value = source.get("remaining")
        if isinstance(value, (int, float)) and value >= 0:
            return float(value)
    return 900.0


def _occupied(request: dict[str, Any]) -> set[tuple[int, int]]:
    return {(x, y) for x, y, _ in extract_moves({"requests": [request], "responses": []}, request)}


def _candidate_list(data: dict[str, Any], request: dict[str, Any]) -> list[dict[str, int]]:
    for source in (request, data):
        value = source.get("candidates")
        if isinstance(value, list):
            points = [point for point in value if _point(point) is not None]
            return points
        value = source.get("black5_candidates")
        if isinstance(value, dict) and isinstance(value.get("points"), list):
            return [point for point in value["points"] if _point(point) is not None]
    return []


class BotBattleAdapter:
    """Translate one complete Traditional request into one exact response."""

    def __init__(self, rule_handler: CCGCRuleHandler, time_manager: TimeManager):
        self.rule_handler = rule_handler
        self.time_manager = time_manager

    def process_request(self, data: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValueError("协议顶层必须是 JSON 对象")
        requests = data.get("requests")
        responses = data.get("responses", [])
        if not isinstance(requests, list) or not requests or not isinstance(requests[-1], dict):
            raise ValueError("Traditional 请求必须包含非空 requests 数组")
        if not isinstance(responses, list):
            raise ValueError("responses 必须是数组")

        request = requests[-1]
        for key, expected in (
            ("protocol_version", EXPECTED_PROTOCOL),
            ("ruleset", EXPECTED_RULESET),
        ):
            if key in request and request[key] != expected:
                raise ValueError(f"不支持的 {key}: {request[key]!r}")

        phase = _phase(data, request)
        if phase == "opening_proposal":
            action = self.rule_handler.handle_opening_proposal()
        elif phase == "swap_choice":
            action = self.rule_handler.handle_swap_choice()
        elif phase == "black5_candidates":
            action = self.rule_handler.handle_black5_candidates(_occupied(request))
        elif phase == "black5_select":
            action = self.rule_handler.handle_black5_select(_candidate_list(data, request))
        elif phase in {"white4", "normal_play"}:
            moves = extract_moves(data, request)
            if phase == "normal_play" and request.get("pass_allowed") and len(moves) >= BOARD_SIZE * BOARD_SIZE:
                action = {"action": "pass"}
            else:
                if self.rule_handler.engine is None:
                    color = _my_color(data, request)
                    x, y = self.rule_handler.fallback_move(request["board"], color)
                else:
                    color = _my_color(data, request)
                    time_limit = self.time_manager.calculate_time_limit_ms(
                        _remaining_seconds(data, request), len(moves) + 1
                    )
                    x, y = self.rule_handler.engine.search_best_move(
                        moves, time_limit, own_color=color
                    )
                if (x, y) in {(mx, my) for mx, my, _ in moves}:
                    raise RuntimeError("Rapfi 返回了已占用的坐标")
                action = {"action": "move", "x": x, "y": y}
        else:
            raise ValueError(f"不支持的五子棋 phase: {phase}")

        return {"response": action}

    # Kept as a small compatibility alias for older local callers.
    def process_event(self, event: dict[str, Any]) -> dict[str, Any]:
        return self.process_request(event)

